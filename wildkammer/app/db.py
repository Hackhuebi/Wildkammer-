"""Datenhaltung der Wildkammer: Stücke, Tüten und die aktive Wildart."""
import sqlite3
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

ZONE = ZoneInfo("Europe/Berlin")
SITZUNG_STUNDEN = 12
STORNO_MINUTEN = 60

SCHEMA = """
CREATE TABLE IF NOT EXISTS stuecke (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    art TEXT NOT NULL,
    begonnen TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS pakete (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    stueck_id INTEGER NOT NULL REFERENCES stuecke(id),
    art TEXT NOT NULL,
    teil TEXT NOT NULL,
    datum TEXT NOT NULL,
    gewicht_g INTEGER CHECK (gewicht_g IS NULL OR gewicht_g > 0),
    status TEXT NOT NULL DEFAULT 'entwurf'
        CHECK (status IN ('entwurf', 'lager', 'raus', 'storniert')),
    erstellt TEXT NOT NULL,
    ausgelagert TEXT
);
CREATE INDEX IF NOT EXISTS pakete_status ON pakete(status, datum);
CREATE TABLE IF NOT EXISTS werte (schluessel TEXT PRIMARY KEY, wert TEXT);
"""


def code(nummer):
    return f"W-{int(nummer):06d}"


def gewicht_text(gramm):
    """Kurzform fürs Etikett: 800 g oder 1,25 kg, ohne Gewicht leer."""
    if not gramm:
        return ""
    if gramm < 1000:
        return f"{gramm} g"
    return f"{gramm / 1000:.2f}".rstrip("0").rstrip(".").replace(".", ",") + " kg"


class Fehler(Exception):
    """Fachlicher Fehler mit einem festen Kennwort für Home Assistant."""

    def __init__(self, kennwort, **info):
        super().__init__(kennwort)
        self.kennwort = kennwort
        self.info = info


class Datenbank:
    def __init__(self, pfad, uhr=None):
        self.pfad = str(pfad)
        self.uhr = uhr or (lambda: datetime.now(ZONE))
        # Beides läuft bewusst außerhalb einer Transaktion.
        v = sqlite3.connect(self.pfad, timeout=15)
        try:
            v.execute("PRAGMA journal_mode=WAL")
            v.executescript(SCHEMA)
        finally:
            v.close()

    def _verbindung(self):
        v = sqlite3.connect(self.pfad, timeout=15, isolation_level=None)
        v.row_factory = sqlite3.Row
        v.execute("PRAGMA foreign_keys=ON")
        return _Transaktion(v)

    def _wert(self, v, schluessel):
        z = v.execute("SELECT wert FROM werte WHERE schluessel=?", (schluessel,)).fetchone()
        return z["wert"] if z else None

    def _setze(self, v, schluessel, wert):
        v.execute(
            "INSERT INTO werte(schluessel, wert) VALUES(?, ?) "
            "ON CONFLICT(schluessel) DO UPDATE SET wert=excluded.wert",
            (schluessel, wert),
        )

    def _aktiv(self, v):
        """Liefert das aktive Stück oder None, wenn nichts gesetzt oder abgelaufen ist."""
        sid, bis = self._wert(v, "stueck_id"), self._wert(v, "aktiv_bis")
        if not sid or not bis or datetime.fromisoformat(bis) < self.uhr():
            return None
        return v.execute("SELECT * FROM stuecke WHERE id=?", (int(sid),)).fetchone()

    def _verlaengern(self, v, stueck_id):
        self._setze(v, "stueck_id", str(stueck_id))
        bis = self.uhr() + timedelta(hours=SITZUNG_STUNDEN)
        self._setze(v, "aktiv_bis", bis.isoformat())

    def _neues_stueck(self, v, art):
        c = v.execute(
            "INSERT INTO stuecke(art, begonnen) VALUES(?, ?)", (art, self.uhr().isoformat())
        )
        self._verlaengern(v, c.lastrowid)
        return c.lastrowid

    def aktiv(self):
        with self._verbindung() as v:
            z = self._aktiv(v)
            return dict(z) if z else None

    def setze_art(self, art):
        with self._verbindung() as v:
            z = self._aktiv(v)
            if z and z["art"] == art:
                self._verlaengern(v, z["id"])
                return {"art": art, "stueck": z["id"], "neu": False}
            return {"art": art, "stueck": self._neues_stueck(v, art), "neu": True}

    def neues_stueck(self):
        with self._verbindung() as v:
            z = self._aktiv(v)
            if not z:
                raise Fehler("wildart_fehlt")
            return {"art": z["art"], "stueck": self._neues_stueck(v, z["art"]), "neu": True}

    def anlegen(self, teil, gewicht_g=None):
        """Reserviert eine Nummer. Im Bestand zählt die Tüte erst nach dem Druck."""
        with self._verbindung() as v:
            z = self._aktiv(v)
            if not z:
                raise Fehler("wildart_fehlt")
            jetzt = self.uhr()
            c = v.execute(
                "INSERT INTO pakete(stueck_id, art, teil, datum, gewicht_g, erstellt) "
                "VALUES(?, ?, ?, ?, ?, ?)",
                (z["id"], z["art"], teil, jetzt.date().isoformat(), gewicht_g, jetzt.isoformat()),
            )
            self._verlaengern(v, z["id"])
            return self._etikett(v, c.lastrowid)

    def gedruckt(self, nummer):
        with self._verbindung() as v:
            c = v.execute(
                "UPDATE pakete SET status='lager' WHERE id=? AND status='entwurf'", (nummer,)
            )
            if c.rowcount == 0:
                raise Fehler("nicht_gefunden")
            self._setze(v, "letztes", str(nummer))
            return self._etikett(v, nummer)

    def _etikett(self, v, nummer):
        p = v.execute("SELECT * FROM pakete WHERE id=?", (nummer,)).fetchone()
        j, m, t = p["datum"].split("-")
        return {
            "nummer": f"{p['id']:06d}",
            "code": code(p["id"]),
            "art": p["art"],
            "teil": p["teil"],
            "datum": f"{t}.{m}.{j}",
            "stueck": p["stueck_id"],
            "gewicht_g": p["gewicht_g"],
            # Bewusst ein Leerzeichen statt leerem Text: So bleibt das Etikettenfeld gültig.
            "gewicht_text": gewicht_text(p["gewicht_g"]) or " ",
        }

    def letztes(self):
        with self._verbindung() as v:
            n = self._wert(v, "letztes")
            if not n:
                raise Fehler("nichts_vorhanden")
            return self._etikett(v, int(n))

    def storno(self):
        """Nimmt die zuletzt gedruckte Tüte heraus, aber nur kurz nach dem Druck."""
        with self._verbindung() as v:
            n = self._wert(v, "letztes")
            p = v.execute("SELECT * FROM pakete WHERE id=?", (n or 0,)).fetchone()
            grenze = self.uhr() - timedelta(minutes=STORNO_MINUTEN)
            if (
                not p
                or p["status"] != "lager"
                or datetime.fromisoformat(p["erstellt"]) < grenze
            ):
                raise Fehler("nichts_vorhanden")
            v.execute("UPDATE pakete SET status='storniert' WHERE id=?", (p["id"],))
            self._setze(v, "letztes", "")
            return self._etikett(v, p["id"])

    def paket(self, nummer):
        with self._verbindung() as v:
            z = v.execute("SELECT * FROM pakete WHERE id=?", (nummer,)).fetchone()
            return dict(z) if z else None

    def auslagern(self, nummer):
        with self._verbindung() as v:
            c = v.execute(
                "UPDATE pakete SET status='raus', ausgelagert=? WHERE id=? AND status='lager'",
                (self.uhr().isoformat(), nummer),
            )
            return c.rowcount == 1

    def alt_grenze(self, monate=12):
        """Eingepackt an oder vor diesem Tag gilt als alt (gleiche Rechnung wie der Filter „älter als“)."""
        return (self.uhr().date() - timedelta(days=monate * 30)).isoformat()

    def alte_tueten(self, monate=12):
        with self._verbindung() as v:
            return [dict(z) for z in v.execute(
                "SELECT * FROM pakete WHERE status = 'lager' AND datum <= ? ORDER BY datum, id", (self.alt_grenze(monate),))]

    def entwuerfe(self, tage=14):
        """Tüten, deren Druck als fehlgeschlagen gemeldet wurde. Manche wurden trotzdem gedruckt."""
        grenze = (self.uhr() - timedelta(days=tage)).isoformat()
        with self._verbindung() as v:
            return [dict(p) for p in v.execute(
                "SELECT * FROM pakete WHERE status = 'entwurf' AND erstellt >= ? ORDER BY id DESC", (grenze,))]

    def entwurf_verwerfen(self, nummer):
        with self._verbindung() as v:
            return v.execute("DELETE FROM pakete WHERE id = ? AND status = 'entwurf'", (nummer,)).rowcount == 1

    def loeschen(self, nummer):
        """Nimmt die Tüte aus dem Bestand. Sie bleibt als gelöscht auffindbar."""
        with self._verbindung() as v:
            c = v.execute(
                "UPDATE pakete SET status='storniert' WHERE id=? AND status IN ('lager', 'raus')",
                (nummer,),
            )
            return c.rowcount == 1

    def einlagern(self, nummer):
        with self._verbindung() as v:
            c = v.execute(
                "UPDATE pakete SET status='lager', ausgelagert=NULL "
                "WHERE id=? AND status IN ('raus', 'storniert')",
                (nummer,),
            )
            return c.rowcount == 1

    def gewicht(self, nummer, gramm):
        with self._verbindung() as v:
            v.execute("UPDATE pakete SET gewicht_g=? WHERE id=?", (gramm, nummer))

    def liste(self, art="", teil="", status="lager", monate=0, jahr=0):
        sql, werte = "SELECT * FROM pakete WHERE status != 'entwurf'", []
        if status:
            sql += " AND status=?"
            werte.append(status)
        if art:
            sql += " AND art=?"
            werte.append(art)
        if teil:
            sql += " AND teil=?"
            werte.append(teil)
        if monate:
            sql += " AND datum <= ?"
            werte.append((self.uhr().date() - timedelta(days=int(monate) * 30)).isoformat())
        if jahr:
            sql += " AND substr(datum, 1, 4) = ?"
            werte.append(str(jahr))
        with self._verbindung() as v:
            return [dict(z) for z in v.execute(sql + " ORDER BY datum, id", werte)]

    def auswahl(self):
        """Werte für die Filter: alles, was im Datenbestand wirklich vorkommt."""
        with self._verbindung() as v:
            f = "FROM pakete WHERE status != 'entwurf' ORDER BY 1"
            return {
                "arten": [z[0] for z in v.execute(f"SELECT DISTINCT art {f}")],
                "teile": [z[0] for z in v.execute(f"SELECT DISTINCT teil {f}")],
                "jahre": [z[0] for z in v.execute(f"SELECT DISTINCT substr(datum,1,4) {f}")],
            }

    def sicherung(self, ziel):
        q = sqlite3.connect(self.pfad)
        z = sqlite3.connect(str(ziel))
        try:
            with z:
                q.backup(z)
        finally:
            q.close()
            z.close()


class _Transaktion:
    """Hält jede Aktion in einer eigenen, sofort sperrenden Transaktion."""

    def __init__(self, verbindung):
        self.v = verbindung

    def __enter__(self):
        self.v.execute("BEGIN IMMEDIATE")
        return self.v

    def __exit__(self, typ, wert, spur):
        self.v.execute("ROLLBACK" if typ else "COMMIT")
        self.v.close()
        return False
