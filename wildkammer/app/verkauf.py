"""Verkauf: Wurstlager, Kunden, Bestellungen, Zahlungen und Auslieferung.

Bestellt werden kann nur, was frei im Lager ist. Wurst wird als Menge reserviert,
Fleisch als einzelne Tüten (die ältesten passenden zuerst).
"""
import difflib
import json
import re
from datetime import datetime, timedelta
import unicodedata

from db import Fehler, code

SCHEMA = """
CREATE TABLE IF NOT EXISTS wurstprodukte (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL COLLATE NOCASE UNIQUE,
    einheit TEXT NOT NULL DEFAULT 'Stück',
    preis_cent INTEGER NOT NULL DEFAULT 0 CHECK (preis_cent >= 0),
    aktiv INTEGER NOT NULL DEFAULT 1 CHECK (aktiv IN (0, 1)),
    erstellt TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS wurstbewegungen (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    produkt_id INTEGER NOT NULL REFERENCES wurstprodukte(id),
    menge INTEGER NOT NULL CHECK (menge != 0),
    art TEXT NOT NULL,
    grund TEXT NOT NULL DEFAULT '',
    erstellt TEXT NOT NULL,
    referenz TEXT UNIQUE
);
CREATE TABLE IF NOT EXISTS kunden (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    telefon TEXT NOT NULL DEFAULT '',
    email TEXT NOT NULL DEFAULT '',
    adresse TEXT NOT NULL DEFAULT '',
    notiz TEXT NOT NULL DEFAULT '',
    aktiv INTEGER NOT NULL DEFAULT 1,
    erstellt TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS bestellungen (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    kunde_id INTEGER NOT NULL REFERENCES kunden(id),
    datum TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'offen',
    notiz TEXT NOT NULL DEFAULT '',
    erstellt TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS bestellpositionen (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    bestellung_id INTEGER NOT NULL REFERENCES bestellungen(id),
    produkt_id INTEGER NOT NULL REFERENCES wurstprodukte(id),
    produktname TEXT NOT NULL,
    einheit TEXT NOT NULL,
    menge INTEGER NOT NULL CHECK (menge > 0),
    einzelpreis_cent INTEGER NOT NULL CHECK (einzelpreis_cent >= 0),
    ausgeliefert INTEGER NOT NULL DEFAULT 0 CHECK (ausgeliefert >= 0)
);
CREATE TABLE IF NOT EXISTS bestell_fleisch (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    bestellung_id INTEGER NOT NULL REFERENCES bestellungen(id),
    paket_id INTEGER NOT NULL REFERENCES pakete(id),
    preis_cent INTEGER CHECK (preis_cent IS NULL OR preis_cent >= 0),
    ausgeliefert INTEGER NOT NULL DEFAULT 0 CHECK (ausgeliefert IN (0, 1))
);
CREATE TABLE IF NOT EXISTS zahlungen (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    bestellung_id INTEGER NOT NULL REFERENCES bestellungen(id),
    betrag_cent INTEGER NOT NULL CHECK (betrag_cent > 0),
    datum TEXT NOT NULL,
    methode TEXT NOT NULL DEFAULT '',
    notiz TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS auslieferungen (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    bestellung_id INTEGER NOT NULL REFERENCES bestellungen(id),
    position_id INTEGER NOT NULL,
    menge INTEGER NOT NULL CHECK (menge > 0),
    datum TEXT NOT NULL,
    notiz TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS fleischpreise (
    art TEXT NOT NULL COLLATE NOCASE,
    teil TEXT NOT NULL COLLATE NOCASE,
    preis_kg_cent INTEGER NOT NULL CHECK (preis_kg_cent >= 0),
    PRIMARY KEY (art, teil)
);
CREATE TABLE IF NOT EXISTS wurst_druckauftraege (
    id TEXT PRIMARY KEY,
    produkt_id INTEGER NOT NULL REFERENCES wurstprodukte(id),
    erstellt TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'offen'
);
CREATE TABLE IF NOT EXISTS wurstpakete (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    auftrag TEXT NOT NULL UNIQUE,
    produkt_id INTEGER NOT NULL REFERENCES wurstprodukte(id),
    erstellt TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'entwurf',
    raus TEXT,
    grund TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS vormerkungen (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    kunde_id INTEGER REFERENCES kunden(id),
    text TEXT NOT NULL,
    erstellt TEXT NOT NULL,
    erledigt TEXT,
    bestellung_id INTEGER REFERENCES bestellungen(id)
);
CREATE TABLE IF NOT EXISTS chargen (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    produkt_id INTEGER NOT NULL REFERENCES wurstprodukte(id),
    name TEXT NOT NULL,
    beginn TEXT NOT NULL,
    kosten_cent INTEGER CHECK (kosten_cent IS NULL OR kosten_cent >= 0),
    notiz TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS einstellungen (
    schluessel TEXT PRIMARY KEY,
    wert TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS packliste (
    bestellung_id INTEGER PRIMARY KEY REFERENCES bestellungen(id)
);
CREATE INDEX IF NOT EXISTS wurstbewegungen_produkt ON wurstbewegungen(produkt_id);
CREATE INDEX IF NOT EXISTS bestellungen_kunde ON bestellungen(kunde_id, datum);
CREATE INDEX IF NOT EXISTS bestell_fleisch_paket ON bestell_fleisch(paket_id);
"""

HONIG = ["Rapshonig", "Lindenhonig"]
KATEGORIEN = {"wurst": "Wurst", "honig": "Honig"}

STARTSORTIMENT = [
    ("Salami", "Stück", 1600), ("Jagdwurst", "Stück", 700),
    ("Pfefferbeißer 5er-Pack", "Packung", 500), ("Pfefferbeißer 10er-Pack", "Packung", 1000),
    ("Knacker", "Packung", 1000), ("Bratwurst", "Packung", 700),
]

# Zählt nur Bestellungen, die nicht storniert sind.
RESERVIERT_WURST = """
    SELECT COALESCE(SUM(bp.menge - bp.ausgeliefert), 0) FROM bestellpositionen bp
    JOIN bestellungen b ON b.id = bp.bestellung_id
    WHERE bp.produkt_id = ? AND b.status != 'storniert'
"""
BESTAND_WURST = "SELECT COALESCE(SUM(menge), 0) FROM wurstbewegungen WHERE produkt_id = ?"
# Tüten, die schon einer offenen Bestellung gehören.
FLEISCH_VERGEBEN = """
    SELECT bf.paket_id FROM bestell_fleisch bf JOIN bestellungen b ON b.id = bf.bestellung_id
    WHERE b.status != 'storniert'
"""

_ZAHLWORT = {"fünfer": "5er", "fuenfer": "5er", "zehner": "10er", "fünf": "5er", "zehn": "10er"}
_FUELL = {"pack", "packung", "packungen", "packs", "stück", "stueck", "x", "mal", "der", "die", "das", "von"}


def euro(cent):
    if cent is None:
        return "Preis offen"
    return f"{cent / 100:.2f}".replace(".", ",") + " €"


def _flach(text):
    t = unicodedata.normalize("NFKC", str(text or "")).casefold().replace("ß", "ss")
    for a, b in (("ä", "ae"), ("ö", "oe"), ("ü", "ue")):
        t = t.replace(a, b)
    return t


def _woerter(text):
    t = _flach(text)
    t = re.sub(r"(\d+)\s*(?:er)?[\s-]*(?:pack|packung)", r"\1er", t)
    w = re.findall(r"[a-z0-9]+", t)
    w = [_ZAHLWORT.get(x, x) for x in w]
    w = [y for x in w for y in ([x[:-5], "honig"] if x.endswith("honig") and len(x) > 6 else [x])]
    w = [{"linde": "linden"}.get(x, x) for x in w]
    w = [x + "er" if x.isdigit() else x for x in w]
    return [x for x in w if x not in _FUELL]


def _cent(wert):
    """Euro als Zahl oder Text in Cent. Leer ergibt None."""
    if wert is None or str(wert).strip() == "":
        return None
    try:
        c = round(float(str(wert).replace("€", "").replace(",", ".").strip()) * 100)
    except ValueError:
        raise Fehler("betrag_ungueltig")
    if c < 0 or c > 10_000_000:
        raise Fehler("betrag_ungueltig")
    return c


def _ganz(wert, feld="menge"):
    # Home Assistant liefert Zahlen aus Eingabefeldern manchmal als "3.0".
    text = str(wert).strip().replace(",", ".")
    try:
        zahl = float(text)
    except (TypeError, ValueError):
        raise Fehler(f"{feld}_ungueltig")
    if not zahl.is_integer() or abs(zahl) > 10**9:
        raise Fehler(f"{feld}_ungueltig")
    return int(zahl)


def wurst_code(nummer):
    return f"P-{int(nummer):06d}"


class Verkauf:
    def __init__(self, datenbank):
        self.d = datenbank
        with self.d._verbindung() as v:
            for befehl in SCHEMA.split(";"):
                if befehl.strip():
                    v.execute(befehl)
            spalten = [z[1] for z in v.execute("PRAGMA table_info(bestellungen)")]
            if "rabatt_cent" not in spalten:
                v.execute("ALTER TABLE bestellungen ADD COLUMN rabatt_cent INTEGER NOT NULL DEFAULT 0")
            # Startsortiment nur beim allerersten Start, damit Umbenennungen bleiben.
            if v.execute("SELECT COUNT(*) FROM wurstprodukte").fetchone()[0] == 0:
                jetzt = self._jetzt()
                v.executemany(
                    "INSERT INTO wurstprodukte(name, einheit, preis_cent, erstellt) VALUES(?, ?, ?, ?)",
                    [(n, e, p, jetzt) for n, e, p in STARTSORTIMENT],
                )
            # Seit 2.13: Lieferdatum für die Zahlungserinnerung. Alte Lieferungen bekommen das Datum der
            # letzten Auslieferung bzw. das Bestelldatum.
            if "ausgeliefert_am" not in [z[1] for z in v.execute("PRAGMA table_info(bestellungen)")]:
                v.execute("ALTER TABLE bestellungen ADD COLUMN ausgeliefert_am TEXT")
                v.execute("UPDATE bestellungen SET ausgeliefert_am = COALESCE("
                          "(SELECT MAX(a.datum) FROM auslieferungen a WHERE a.bestellung_id = bestellungen.id), "
                          "datum || 'T12:00:00') WHERE status = 'ausgeliefert'")
            # Honig kam später dazu: gleiche Tabelle, Produkte haben eine Kategorie.
            if "kategorie" not in [z[1] for z in v.execute("PRAGMA table_info(wurstprodukte)")]:
                v.execute("ALTER TABLE wurstprodukte ADD COLUMN kategorie TEXT NOT NULL DEFAULT 'wurst'")
                jetzt = self._jetzt()
                for name in HONIG:
                    if not v.execute("SELECT 1 FROM wurstprodukte WHERE name = ?", (name,)).fetchone():
                        v.execute("INSERT INTO wurstprodukte(name, einheit, preis_cent, erstellt, kategorie) "
                                  "VALUES(?, 'Glas 500 g', 0, ?, 'honig')", (name, jetzt))

    def _jetzt(self):
        return self.d.uhr().isoformat()

    def _heute(self):
        return self.d.uhr().date().isoformat()

    # ---------------- Wurst ----------------
    def produkte(self, nur_aktiv=True):
        with self.d._verbindung() as v:
            sql = "SELECT * FROM wurstprodukte" + (" WHERE aktiv = 1" if nur_aktiv else "")
            aus = []
            # Wurst zuerst, dann Honig
            for p in v.execute(sql + " ORDER BY aktiv DESC, kategorie = 'honig', name"):
                p = dict(p)
                p["bestand"] = v.execute(BESTAND_WURST, (p["id"],)).fetchone()[0]
                p["reserviert"] = v.execute(RESERVIERT_WURST, (p["id"],)).fetchone()[0]
                p["frei"] = p["bestand"] - p["reserviert"]
                aus.append(p)
            return aus

    def produkt(self, pid):
        return next((p for p in self.produkte(False) if p["id"] == pid), None)

    def produkt_finden(self, text):
        """Findet ein Wurstprodukt aus freier Sprache, z. B. "10er Pfefferbeißer"."""
        with self.d._verbindung() as v:
            alle = [dict(p) for p in v.execute("SELECT * FROM wurstprodukte WHERE aktiv = 1")]
        frage = set(_woerter(text))
        if not frage:
            raise Fehler("produkt_unklar", eingabe=str(text), auswahl=[p["name"] for p in alle])
        gleich = [p for p in alle if set(_woerter(p["name"])) == frage]
        if len(gleich) == 1:
            return gleich[0]
        teil = [p for p in alle if frage <= set(_woerter(p["name"]))]
        if len(teil) == 1:
            return teil[0]
        if len(teil) > 1:
            raise Fehler("produkt_unklar", eingabe=str(text), auswahl=[p["name"] for p in teil])
        # Tippfehler oder Verhörer: nur ein eindeutiger, sehr ähnlicher Treffer zählt.
        f = " ".join(sorted(frage))
        werte = sorted(
            ((difflib.SequenceMatcher(None, f, " ".join(sorted(_woerter(p["name"])))).ratio(), p) for p in alle),
            key=lambda x: -x[0],
        )
        if werte and werte[0][0] >= 0.8 and (len(werte) == 1 or werte[1][0] < werte[0][0] - 0.1):
            return werte[0][1]
        raise Fehler("produkt_unbekannt", eingabe=str(text), auswahl=[p["name"] for p in alle])

    def produkt_anlegen(self, name, einheit, preis, kategorie="wurst"):
        name, einheit = (name or "").strip(), (einheit or "").strip() or "Stück"
        kategorie = kategorie if kategorie in KATEGORIEN else "wurst"
        if not name or len(name) > 60:
            raise Fehler("name_ungueltig")
        with self.d._verbindung() as v:
            if v.execute("SELECT 1 FROM wurstprodukte WHERE name = ?", (name,)).fetchone():
                raise Fehler("produkt_existiert")
            c = v.execute(
                "INSERT INTO wurstprodukte(name, einheit, preis_cent, erstellt, kategorie) VALUES(?, ?, ?, ?, ?)",
                (name, einheit, _cent(preis) or 0, self._jetzt(), kategorie),
            )
            return c.lastrowid

    def produkt_aendern(self, pid, name, einheit, preis, aktiv, kategorie=None):
        name, einheit = (name or "").strip(), (einheit or "").strip()
        if not name or not einheit:
            raise Fehler("name_ungueltig")
        with self.d._verbindung() as v:
            if v.execute("SELECT 1 FROM wurstprodukte WHERE name = ? AND id != ?", (name, pid)).fetchone():
                raise Fehler("produkt_existiert")
            v.execute(
                "UPDATE wurstprodukte SET name = ?, einheit = ?, preis_cent = ?, aktiv = ? WHERE id = ?",
                (name, einheit, _cent(preis) or 0, 1 if aktiv else 0, pid),
            )
            if kategorie in KATEGORIEN:
                v.execute("UPDATE wurstprodukte SET kategorie = ? WHERE id = ?", (kategorie, pid))

    def wurst_buchen(self, pid, menge, art, grund=""):
        """Zugang, Entnahme ohne Kunde (z. B. Eigenverbrauch) oder Inventurkorrektur mit Grund."""
        menge = _ganz(menge)
        if art in ("zugang", "entnahme") and not 0 < menge <= 10000:
            raise Fehler("menge_ungueltig")
        if art == "entnahme":
            menge, grund = -menge, (grund or "").strip() or "Eigenverbrauch"
        if art == "korrektur" and (menge == 0 or not (grund or "").strip()):
            raise Fehler("grund_fehlt")
        if art not in ("zugang", "korrektur", "entnahme"):
            raise Fehler("art_ungueltig")
        with self.d._verbindung() as v:
            return self._buchen(v, pid, menge, art, grund)

    def _buchen(self, v, pid, menge, art, grund):
        p = v.execute("SELECT name FROM wurstprodukte WHERE id = ?", (pid,)).fetchone()
        if not p:
            raise Fehler("produkt_unbekannt")
        bestand = v.execute(BESTAND_WURST, (pid,)).fetchone()[0]
        reserviert = v.execute(RESERVIERT_WURST, (pid,)).fetchone()[0]
        if bestand + menge < reserviert:
            raise Fehler("reservierung_unterschritten", ware=p["name"], frei=max(bestand - reserviert, 0),
                         reserviert=reserviert, bestand=bestand)
        v.execute(
            "INSERT INTO wurstbewegungen(produkt_id, menge, art, grund, erstellt) VALUES(?, ?, ?, ?, ?)",
            (pid, menge, art, (grund or "").strip(), self._jetzt()),
        )
        return bestand + menge

    def wurst_aenderungen(self, posten, grund=""):
        """Plus bucht Zugang, Minus Entnahme, für mehrere Produkte auf einmal: alles oder nichts.
        posten: {produkt_id: +/-menge}. Liefert (eingebucht, entnommen)."""
        posten = {int(pid): _ganz(m) for pid, m in posten.items()}
        posten = {pid: m for pid, m in posten.items() if m}
        if not posten:
            raise Fehler("nichts_gewaehlt")
        if any(abs(m) > 10000 for m in posten.values()):
            raise Fehler("menge_ungueltig")
        grund = (grund or "").strip() or "Eigenverbrauch"
        with self.d._verbindung() as v:
            for pid, m in posten.items():
                self._buchen(v, pid, m, "zugang" if m > 0 else "entnahme", "" if m > 0 else grund)
        return (sum(m for m in posten.values() if m > 0), -sum(m for m in posten.values() if m < 0))

    def wurst_buchen_mehrere(self, posten, art, grund=""):
        """Bucht Zugang oder Entnahme für mehrere Produkte auf einmal: alles oder nichts.
        posten: {produkt_id: menge}. Liefert die Gesamtzahl der gebuchten Packungen."""
        if art not in ("zugang", "entnahme"):
            raise Fehler("art_ungueltig")
        posten = {int(pid): _ganz(m) for pid, m in posten.items()}
        posten = {pid: m for pid, m in posten.items() if m}
        if not posten:
            raise Fehler("nichts_gewaehlt")
        if any(not 0 < m <= 10000 for m in posten.values()):
            raise Fehler("menge_ungueltig")
        grund = (grund or "").strip() or ("Eigenverbrauch" if art == "entnahme" else "")
        with self.d._verbindung() as v:
            for pid, m in posten.items():
                self._buchen(v, pid, -m if art == "entnahme" else m, art, grund)
        return sum(posten.values())

    def bewegungen(self, pid=None, anzahl=40):
        sql = ("SELECT w.*, p.name FROM wurstbewegungen w JOIN wurstprodukte p ON p.id = w.produkt_id"
               + (" WHERE w.produkt_id = ?" if pid else "") + " ORDER BY w.id DESC LIMIT ?")
        with self.d._verbindung() as v:
            return [dict(z) for z in v.execute(sql, ((pid, anzahl) if pid else (anzahl,)))]

    def druckauftrag(self, pid):
        import uuid
        with self.d._verbindung() as v:
            p = v.execute("SELECT * FROM wurstprodukte WHERE id = ? AND aktiv = 1", (pid,)).fetchone()
            if not p:
                raise Fehler("produkt_unbekannt")
            token = uuid.uuid4().hex
            v.execute("INSERT INTO wurst_druckauftraege(id, produkt_id, erstellt) VALUES(?, ?, ?)",
                      (token, pid, self._jetzt()))
            # Jede Packung bekommt eine kurze Nummer für den QR-Code. Sie zählt erst nach dem Druck.
            nummer = v.execute("INSERT INTO wurstpakete(auftrag, produkt_id, erstellt) VALUES(?, ?, ?)",
                               (token, pid, self._jetzt())).lastrowid
            j, m, t = self._heute().split("-")
            name = p["name"]
            teile = name.split(" ", 1)
            return {"auftrag": token, "produkt": name, "datum": f"{t}.{m}.{j}", "nummer": nummer,
                    "code": wurst_code(nummer), "zeile1": teile[0], "zeile2": teile[1] if len(teile) > 1 else ""}

    def druck_bestaetigen(self, token):
        """Erst nach erfolgreichem Druck zählt die Packung. Doppelte Meldungen zählen nicht doppelt."""
        with self.d._verbindung() as v:
            a = v.execute("SELECT * FROM wurst_druckauftraege WHERE id = ?", (token,)).fetchone()
            if not a:
                raise Fehler("auftrag_unbekannt")
            if a["status"] == "gedruckt":
                return False
            v.execute("UPDATE wurst_druckauftraege SET status = 'gedruckt' WHERE id = ?", (token,))
            v.execute("UPDATE wurstpakete SET status = 'lager' WHERE auftrag = ? AND status = 'entwurf'", (token,))
            v.execute(
                "INSERT INTO wurstbewegungen(produkt_id, menge, art, grund, erstellt, referenz) "
                "VALUES(?, 1, 'zugang', 'Etikett gedruckt', ?, ?)",
                (a["produkt_id"], self._jetzt(), "druck:" + token),
            )
            return True

    def wurstpaket(self, nummer):
        with self.d._verbindung() as v:
            z = v.execute("SELECT w.*, p.name, p.einheit FROM wurstpakete w JOIN wurstprodukte p ON p.id = w.produkt_id "
                          "WHERE w.id = ? AND w.status != 'entwurf'", (nummer,)).fetchone()
            return dict(z) if z else None

    def wurstpaket_entnehmen(self, nummer, grund=""):
        """Gescannte Packung verlässt das Lager ohne Kunde. Bestellte Ware bleibt geschützt."""
        grund = (grund or "").strip() or "Eigenverbrauch"
        with self.d._verbindung() as v:
            z = v.execute("SELECT * FROM wurstpakete WHERE id = ? AND status != 'entwurf'", (nummer,)).fetchone()
            if not z:
                raise Fehler("packung_unbekannt")
            if z["status"] != "lager":
                raise Fehler("packung_schon_raus")
            self._buchen(v, z["produkt_id"], -1, "entnahme", f"{grund} ({wurst_code(nummer)})")
            v.execute("UPDATE wurstpakete SET status = 'raus', raus = ?, grund = ? WHERE id = ?",
                      (self._jetzt(), grund, nummer))

    def wurstpaket_zurueck(self, nummer):
        """Macht eine versehentliche Entnahme per Scan rückgängig."""
        with self.d._verbindung() as v:
            z = v.execute("SELECT * FROM wurstpakete WHERE id = ?", (nummer,)).fetchone()
            if not z or z["status"] != "raus":
                raise Fehler("packung_nicht_raus")
            self._buchen(v, z["produkt_id"], 1, "korrektur", f"Scan rückgängig ({wurst_code(nummer)})")
            v.execute("UPDATE wurstpakete SET status = 'lager', raus = NULL, grund = '' WHERE id = ?", (nummer,))

    # ---------------- Fleisch ----------------
    def fleisch_frei(self):
        """Freie Tüten im Lager, gruppiert nach Wildart und Teilstück."""
        with self.d._verbindung() as v:
            zeilen = v.execute(f"""
                SELECT art, teil, COUNT(*) AS anzahl, MIN(datum) AS aelteste,
                       COALESCE(SUM(gewicht_g), 0) AS gramm, COUNT(gewicht_g) AS gewogen
                FROM pakete WHERE status = 'lager' AND id NOT IN ({FLEISCH_VERGEBEN})
                GROUP BY art, teil ORDER BY art, teil""").fetchall()
            return [dict(z) for z in zeilen]

    def fleisch_vergeben(self):
        """Tüten im Lager, die einer Bestellung gehören: paket_id -> Bestellnummer."""
        with self.d._verbindung() as v:
            return {z[0]: z[1] for z in v.execute("""
                SELECT bf.paket_id, bf.bestellung_id FROM bestell_fleisch bf
                JOIN bestellungen b ON b.id = bf.bestellung_id
                WHERE b.status != 'storniert' AND bf.ausgeliefert = 0""")}

    def _fleisch_auswahl(self, v, art, teil, menge, ausgeschlossen=()):
        art, teil = (art or "").strip(), (teil or "").strip()
        if not art or not teil:
            raise Fehler("fleisch_unklar", hinweis="Wildart und Teilstück angeben")
        frei = v.execute(f"""
            SELECT * FROM pakete WHERE status = 'lager' AND id NOT IN ({FLEISCH_VERGEBEN})
            ORDER BY datum, id""").fetchall()
        # "Reh" passt auch auf "Reh Bock"; das Teilstück muss genau passen.
        passend = [p for p in frei if p["id"] not in ausgeschlossen
                   and (_flach(p["art"]) == _flach(art) or _flach(p["art"]).startswith(_flach(art) + " "))
                   and _flach(p["teil"]) == _flach(teil)]
        if len(passend) < menge:
            vorhanden = sorted({f"{p['art']} {p['teil']}" for p in frei})
            raise Fehler("bestand_nicht_ausreichend", ware=f"{art} {teil}", frei=len(passend),
                         gewuenscht=menge, im_lager=vorhanden[:40])
        return passend[:menge]

    def fleischpreise(self):
        with self.d._verbindung() as v:
            return [dict(z) for z in v.execute("SELECT * FROM fleischpreise ORDER BY art, teil")]

    def fleischpreis_setzen(self, art, teil, preis_kg):
        art, teil = (art or "").strip(), (teil or "").strip()
        if not art or not teil:
            raise Fehler("fleisch_unklar")
        cent = _cent(preis_kg)
        with self.d._verbindung() as v:
            if cent is None:
                v.execute("DELETE FROM fleischpreise WHERE art = ? AND teil = ?", (art, teil))
            else:
                v.execute(
                    "INSERT INTO fleischpreise(art, teil, preis_kg_cent) VALUES(?, ?, ?) "
                    "ON CONFLICT(art, teil) DO UPDATE SET preis_kg_cent = excluded.preis_kg_cent",
                    (art, teil, cent),
                )

    def _tuetenpreis(self, v, paket):
        """Kilopreis mal Gewicht. Ohne Kilopreis oder Gewicht bleibt der Preis offen."""
        if not paket["gewicht_g"]:
            return None
        for art in (paket["art"], paket["art"].split(" ")[0]):
            z = v.execute("SELECT preis_kg_cent FROM fleischpreise WHERE art = ? AND teil = ?",
                          (art, paket["teil"])).fetchone()
            if z:
                return round(z[0] * paket["gewicht_g"] / 1000)
        return None

    # ---------------- Kunden ----------------
    def kunden(self):
        with self.d._verbindung() as v:
            aus = []
            for k in v.execute("SELECT * FROM kunden WHERE aktiv = 1 ORDER BY name COLLATE NOCASE"):
                k = dict(k)
                k["offen_cent"] = sum(
                    b["offen_cent"] for b in self._bestellungen(v, kunde_id=k["id"], filter="alle"))
                aus.append(k)
            return aus

    def kunde(self, kid):
        with self.d._verbindung() as v:
            z = v.execute("SELECT * FROM kunden WHERE id = ?", (kid,)).fetchone()
            return dict(z) if z else None

    def kunden_suchen(self, name):
        """Ähnliche Kunden, beste zuerst. Erkennt auch Vor- oder Nachnamen allein."""
        q = _flach(name).strip()
        if not q:
            return []
        with self.d._verbindung() as v:
            alle = [dict(k) for k in v.execute("SELECT id, name FROM kunden WHERE aktiv = 1")]
        treffer = []
        for k in alle:
            n = _flach(k["name"])
            teile = n.split()
            wert = max([difflib.SequenceMatcher(None, q, n).ratio()]
                       + [difflib.SequenceMatcher(None, q, t).ratio() for t in teile])
            if q == n:
                wert = 2.0
            elif q in teile or all(w in teile for w in q.split()):
                wert = max(wert, 1.0)
            if wert >= 0.6:
                treffer.append({"id": k["id"], "name": k["name"], "aehnlichkeit": round(min(wert, 1.0), 2),
                                "genau": q == n})
        return sorted(treffer, key=lambda t: (not t["genau"], -t["aehnlichkeit"]))[:6]

    def kunde_anlegen(self, name, telefon="", email="", adresse="", notiz=""):
        name = " ".join((name or "").split())
        if not name or len(name) > 80:
            raise Fehler("name_ungueltig")
        with self.d._verbindung() as v:
            z = v.execute("SELECT id FROM kunden WHERE name = ? COLLATE NOCASE AND aktiv = 1", (name,)).fetchone()
            if z:
                return z[0], False
            c = v.execute(
                "INSERT INTO kunden(name, telefon, email, adresse, notiz, erstellt) VALUES(?, ?, ?, ?, ?, ?)",
                (name, telefon or "", email or "", adresse or "", notiz or "", self._jetzt()),
            )
            return c.lastrowid, True

    def kunde_aendern(self, kid, name, telefon, email, adresse, notiz):
        name = " ".join((name or "").split())
        if not name:
            raise Fehler("name_ungueltig")
        with self.d._verbindung() as v:
            v.execute("UPDATE kunden SET name = ?, telefon = ?, email = ?, adresse = ?, notiz = ? WHERE id = ?",
                      (name, telefon or "", email or "", adresse or "", notiz or "", kid))

    def _kunde_klaeren(self, kunde_id=None, kunde=None):
        if kunde_id not in (None, "", 0, "0"):
            k = self.kunde(_ganz(kunde_id, "kunde"))
            if not k or not k["aktiv"]:
                raise Fehler("kunde_unbekannt")
            return k
        treffer = self.kunden_suchen(kunde or "")
        genau = [t for t in treffer if t["genau"]]
        if len(genau) == 1:
            return self.kunde(genau[0]["id"])
        # Bewusst keine automatische Neuanlage: Ein Verhörer würde sonst einen zweiten Kunden erzeugen.
        raise Fehler("kunde_unklar", eingabe=str(kunde or ""), vorschlaege=treffer)

    # ---------------- Bestellungen ----------------
    @staticmethod
    def positionen_lesen(roh):
        """Akzeptiert eine Liste oder einen JSON-Text mit Positionen."""
        if isinstance(roh, str):
            try:
                roh = json.loads(roh) if roh.strip() else []
            except ValueError:
                raise Fehler("positionen_ungueltig", hinweis='JSON-Liste, z. B. [{"produkt": "Salami", "menge": 2}]')
        if isinstance(roh, dict):
            roh = [roh]
        if not isinstance(roh, list) or not roh or not all(isinstance(x, dict) for x in roh):
            raise Fehler("positionen_ungueltig", hinweis='JSON-Liste, z. B. [{"produkt": "Salami", "menge": 2}]')
        return roh

    def bestellung_anlegen(self, positionen, kunde_id=None, kunde=None, notiz=""):
        k = self._kunde_klaeren(kunde_id, kunde)
        positionen = self.positionen_lesen(positionen)
        wurst, fleisch = {}, []
        for pos in positionen:
            menge = _ganz(pos.get("menge", 1))
            if not 0 < menge <= 100:
                raise Fehler("menge_ungueltig")
            if pos.get("produkt_id") or pos.get("produkt"):
                if pos.get("produkt_id"):
                    p = self.produkt(_ganz(pos["produkt_id"], "produkt"))
                    if not p or not p["aktiv"]:
                        raise Fehler("produkt_unbekannt")
                else:
                    p = self.produkt_finden(pos["produkt"])
                wurst[p["id"]] = wurst.get(p["id"], 0) + menge
            elif pos.get("wildart") or pos.get("teil") or pos.get("teilstueck"):
                fleisch.append((pos.get("wildart"), pos.get("teil") or pos.get("teilstueck"), menge))
            else:
                raise Fehler("positionen_ungueltig", hinweis="Jede Position braucht produkt oder wildart und teil")
        with self.d._verbindung() as v:
            # Alles wird in einer Sperre geprüft und gebucht: entweder die ganze Bestellung oder nichts.
            gewaehlt = []
            for pid, menge in wurst.items():
                p = v.execute("SELECT * FROM wurstprodukte WHERE id = ?", (pid,)).fetchone()
                frei = v.execute(BESTAND_WURST, (pid,)).fetchone()[0] - v.execute(RESERVIERT_WURST, (pid,)).fetchone()[0]
                if frei < menge:
                    raise Fehler("bestand_nicht_ausreichend", ware=p["name"], frei=max(frei, 0), gewuenscht=menge)
            for art, teil, menge in fleisch:
                # Dieselbe Ware zweimal genannt: keine Tüte doppelt vergeben.
                gewaehlt += self._fleisch_auswahl(v, art, teil, menge, {g["id"] for g in gewaehlt})
            c = v.execute("INSERT INTO bestellungen(kunde_id, datum, notiz, erstellt) VALUES(?, ?, ?, ?)",
                          (k["id"], self._heute(), (notiz or "")[:200], self._jetzt()))
            oid = c.lastrowid
            for pid, menge in wurst.items():
                p = v.execute("SELECT * FROM wurstprodukte WHERE id = ?", (pid,)).fetchone()
                v.execute(
                    "INSERT INTO bestellpositionen(bestellung_id, produkt_id, produktname, einheit, menge, "
                    "einzelpreis_cent) VALUES(?, ?, ?, ?, ?, ?)",
                    (oid, pid, p["name"], p["einheit"], menge, p["preis_cent"]),
                )
            for paket in gewaehlt:
                v.execute("INSERT INTO bestell_fleisch(bestellung_id, paket_id, preis_cent) VALUES(?, ?, ?)",
                          (oid, paket["id"], self._tuetenpreis(v, paket)))
        return self.bestellung(oid)

    def _bestellungen(self, v, kunde_id=None, filter="offen"):
        sql = "SELECT b.*, k.name AS kunde FROM bestellungen b JOIN kunden k ON k.id = b.kunde_id"
        bed, werte = [], []
        if kunde_id:
            bed.append("b.kunde_id = ?")
            werte.append(kunde_id)
        if filter in ("offen", "unbezahlt", "nicht_ausgeliefert", "abgeschlossen"):
            bed.append("b.status != 'storniert'")
        sql += (" WHERE " + " AND ".join(bed) if bed else "") + " ORDER BY b.id DESC"
        aus = []
        for b in v.execute(sql, werte):
            b = self._zusammenfassen(v, dict(b))
            if filter == "offen" and b["bezahlt"] and b["status"] == "ausgeliefert":
                continue
            if filter == "unbezahlt" and (b["bezahlt"] or b["status"] == "storniert"):
                continue
            if filter == "nicht_ausgeliefert" and b["status"] != "offen":
                continue
            if filter == "abgeschlossen" and not (b["bezahlt"] and b["status"] == "ausgeliefert"):
                continue
            aus.append(b)
        return aus

    def _zusammenfassen(self, v, b):
        oid = b["id"]
        b["wurst"] = [dict(z) for z in v.execute("SELECT * FROM bestellpositionen WHERE bestellung_id = ?", (oid,))]
        b["fleisch"] = [dict(z) for z in v.execute("""
            SELECT bf.*, p.art, p.teil, p.datum AS eingepackt, p.gewicht_g FROM bestell_fleisch bf
            JOIN pakete p ON p.id = bf.paket_id WHERE bf.bestellung_id = ? ORDER BY p.datum, p.id""", (oid,))]
        for f in b["fleisch"]:
            f["code"] = code(f["paket_id"])
        summe = sum(z["menge"] * z["einzelpreis_cent"] for z in b["wurst"])
        summe += sum(f["preis_cent"] or 0 for f in b["fleisch"])
        b["positionen_cent"] = summe
        b["rabatt_cent"] = b.get("rabatt_cent") or 0
        summe = max(summe - b["rabatt_cent"], 0)
        b["preis_offen"] = any(f["preis_cent"] is None for f in b["fleisch"])
        b["summe_cent"] = summe
        b["bezahlt_cent"] = v.execute("SELECT COALESCE(SUM(betrag_cent), 0) FROM zahlungen WHERE bestellung_id = ?",
                                      (oid,)).fetchone()[0]
        b["offen_cent"] = 0 if b["status"] == "storniert" else max(summe - b["bezahlt_cent"], 0)
        b["bezahlt"] = b["status"] != "storniert" and summe > 0 and b["bezahlt_cent"] >= summe and not b["preis_offen"]
        b["zahlungen"] = [dict(z) for z in v.execute(
            "SELECT * FROM zahlungen WHERE bestellung_id = ? ORDER BY id", (oid,))]
        return b

    def bestellungen(self, filter="offen", kunde_id=None):
        with self.d._verbindung() as v:
            return self._bestellungen(v, kunde_id=kunde_id, filter=filter)

    def bestellung(self, oid):
        with self.d._verbindung() as v:
            b = v.execute("SELECT b.*, k.name AS kunde FROM bestellungen b JOIN kunden k ON k.id = b.kunde_id "
                          "WHERE b.id = ?", (oid,)).fetchone()
            if not b:
                raise Fehler("bestellung_unbekannt")
            return self._zusammenfassen(v, dict(b))

    def zahlung(self, oid, betrag=None, methode="", notiz=""):
        """Ohne Betrag wird der ganze offene Rest gebucht."""
        b = self.bestellung(oid)
        if b["status"] == "storniert":
            raise Fehler("bestellung_storniert")
        cent = _cent(betrag)
        offen = b["summe_cent"] - b["bezahlt_cent"]
        if cent is None:
            if b["preis_offen"]:
                raise Fehler("preis_offen", hinweis="Für Fleisch ohne Kilopreis den Betrag nennen")
            cent = offen
        if cent <= 0:
            raise Fehler("nichts_offen")
        if cent > offen and not b["preis_offen"]:
            raise Fehler("betrag_zu_hoch", offen=offen)
        with self.d._verbindung() as v:
            v.execute("INSERT INTO zahlungen(bestellung_id, betrag_cent, datum, methode, notiz) VALUES(?, ?, ?, ?, ?)",
                      (oid, cent, self._jetzt(), (methode or "")[:40], (notiz or "")[:200]))
        return self.bestellung(oid)

    def bezahlt_mit(self, oid, betrag, methode=""):
        """Der Kunde hat diesen Betrag gegeben und damit ist die Bestellung erledigt:
        Was zum offenen Rest fehlt, wird als Rabatt erlassen. Kein Rabatt von Hand nötig."""
        b = self.bestellung(oid)
        if b["status"] == "storniert":
            raise Fehler("bestellung_storniert")
        cent = _cent(betrag)
        if cent is None or cent < 0:
            raise Fehler("betrag_ungueltig")
        if b["preis_offen"]:
            # Ohne vollständigen Preis gibt es keinen Rest, der erlassen werden könnte
            return self.zahlung(oid, betrag, methode) if cent else b
        offen = b["summe_cent"] - b["bezahlt_cent"]
        if offen <= 0:
            raise Fehler("nichts_offen")
        if cent > offen:
            raise Fehler("betrag_zu_hoch", offen=offen)
        with self.d._verbindung() as v:
            if offen - cent:
                v.execute("UPDATE bestellungen SET rabatt_cent = rabatt_cent + ? WHERE id = ?", (offen - cent, oid))
            if cent:
                v.execute("INSERT INTO zahlungen(bestellung_id, betrag_cent, datum, methode, notiz) VALUES(?, ?, ?, ?, ?)",
                          (oid, cent, self._jetzt(), (methode or "")[:40], ""))
        return self.bestellung(oid)

    def rabatt_setzen(self, oid, betrag):
        """Rabatt in Euro für die ganze Bestellung. 0 oder leer entfernt ihn."""
        b = self.bestellung(oid)
        if b["status"] == "storniert":
            raise Fehler("bestellung_storniert")
        cent = _cent(betrag) or 0
        if cent > b["positionen_cent"]:
            raise Fehler("rabatt_zu_hoch", positionen=euro(b["positionen_cent"]))
        with self.d._verbindung() as v:
            v.execute("UPDATE bestellungen SET rabatt_cent = ? WHERE id = ?", (cent, oid))
        return self.bestellung(oid)

    def bestellung_abgeschlossen(self, kunde_id, wurst, notiz="", rabatt_cent=0):
        """Trägt einen früheren, schon gelieferten Verkauf nach. Der Bestand bleibt dabei unverändert,
        weil die Ware die Kammer längst verlassen hat."""
        with self.d._verbindung() as v:
            c = v.execute("INSERT INTO bestellungen(kunde_id, datum, status, notiz, erstellt, rabatt_cent, ausgeliefert_am) "
                          "VALUES(?, ?, 'ausgeliefert', ?, ?, ?, ?)",
                          (kunde_id, self._heute(), notiz, self._jetzt(), rabatt_cent, self._jetzt()))
            oid = c.lastrowid
            for name, menge in wurst.items():
                p = v.execute("SELECT * FROM wurstprodukte WHERE name = ?", (name,)).fetchone()
                if not p:
                    raise Fehler("produkt_unbekannt", eingabe=name)
                v.execute(
                    "INSERT INTO bestellpositionen(bestellung_id, produkt_id, produktname, einheit, menge, "
                    "einzelpreis_cent, ausgeliefert) VALUES(?, ?, ?, ?, ?, ?, ?)",
                    (oid, p["id"], p["name"], p["einheit"], menge, p["preis_cent"], menge))
        return self.bestellung(oid)

    def bestellungen_mit_notiz_entfernen(self, notiz):
        """Entfernt eine frühere Übernahme komplett, solange davon nichts ausgeliefert wurde."""
        with self.d._verbindung() as v:
            ids = [z[0] for z in v.execute("SELECT id FROM bestellungen WHERE notiz = ?", (notiz,))]
            for oid in ids:
                geliefert = v.execute("SELECT COUNT(*) FROM auslieferungen WHERE bestellung_id = ?", (oid,)).fetchone()[0]
                geliefert += v.execute("SELECT COUNT(*) FROM bestell_fleisch WHERE bestellung_id = ? AND ausgeliefert = 1",
                                       (oid,)).fetchone()[0]
                if geliefert:
                    raise Fehler("schon_ausgeliefert", bestellung_id=oid)
            for oid in ids:
                for tabelle in ("zahlungen", "auslieferungen", "bestellpositionen", "bestell_fleisch"):
                    v.execute(f"DELETE FROM {tabelle} WHERE bestellung_id = ?", (oid,))
                v.execute("DELETE FROM bestellungen WHERE id = ?", (oid,))
            return len(ids)

    # ---------------- Vormerkungen ----------------
    # Notizen wie "wenn du mal Schwein hast, ein ganzes": keine Bestellung, keine Reservierung, kein Betrag.
    # Ein Kunde ist freiwillig.
    def vormerkung_anlegen(self, text, kunde_id=None, kunde=None):
        text = (text or "").strip()
        if not text:
            raise Fehler("text_fehlt")
        if len(text) > 500:
            raise Fehler("text_zu_lang")
        k = self._kunde_klaeren(kunde_id, kunde) if (kunde_id not in (None, "", 0, "0") or (kunde or "").strip()) else None
        with self.d._verbindung() as v:
            vid = v.execute("INSERT INTO vormerkungen(kunde_id, text, erstellt) VALUES(?, ?, ?)",
                            (k["id"] if k else None, text, self._jetzt())).lastrowid
        return self.vormerkung(vid)

    def vormerkung(self, vid):
        with self.d._verbindung() as v:
            z = v.execute("SELECT m.*, k.name AS kunde FROM vormerkungen m LEFT JOIN kunden k ON k.id = m.kunde_id "
                          "WHERE m.id = ?", (vid,)).fetchone()
        if not z:
            raise Fehler("vormerkung_unbekannt")
        return dict(z)

    def vormerkungen(self, offen=True, kunde_id=None, anzahl=50):
        sql = ("SELECT m.*, k.name AS kunde FROM vormerkungen m LEFT JOIN kunden k ON k.id = m.kunde_id WHERE "
               + ("m.erledigt IS NULL" if offen else "m.erledigt IS NOT NULL"))
        werte = []
        if kunde_id:
            sql += " AND m.kunde_id = ?"
            werte.append(int(kunde_id))
        sql += " ORDER BY m.erstellt" if offen else " ORDER BY m.erledigt DESC"
        with self.d._verbindung() as v:
            return [dict(z) for z in v.execute(sql + f" LIMIT {int(anzahl)}", werte)]

    def vormerkung_erledigen(self, vid, bestellung_id=None):
        self.vormerkung(vid)
        with self.d._verbindung() as v:
            v.execute("UPDATE vormerkungen SET erledigt = ?, bestellung_id = ? WHERE id = ? AND erledigt IS NULL",
                      (self._jetzt(), bestellung_id, vid))
        return self.vormerkung(vid)

    def vormerkung_loeschen(self, vid):
        with self.d._verbindung() as v:
            v.execute("DELETE FROM vormerkungen WHERE id = ?", (vid,))

    # ---------------- Chargen ----------------
    # Eine Charge beginnt zu einem Zeitpunkt: Alles, was danach eingebucht wird, gehört zu ihr, bis die nächste
    # beginnt. Verkauft und entnommen wird rechnerisch immer aus der ältesten Charge mit Restbestand.
    def _startcharge(self, v, pid, name):
        if not v.execute("SELECT 1 FROM chargen WHERE produkt_id = ?", (pid,)).fetchone():
            v.execute("INSERT INTO chargen(produkt_id, name, beginn) VALUES(?, ?, '0000-00-00')", (pid, f"{name} Start"))

    def charge_neu(self, pid, name="", kosten=None):
        p = self.produkt(pid)
        if not p:
            raise Fehler("produkt_unbekannt")
        jetzt = self.d.uhr()
        name = (name or "").strip() or f"{p['name']} {jetzt:%m/%Y}"
        with self.d._verbindung() as v:
            self._startcharge(v, pid, p["name"])
            basis, n = name, 2
            while v.execute("SELECT 1 FROM chargen WHERE produkt_id = ? AND name = ?", (pid, name)).fetchone():
                name, n = f"{basis} ({n})", n + 1
            cid = v.execute("INSERT INTO chargen(produkt_id, name, beginn, kosten_cent) VALUES(?, ?, ?, ?)",
                            (pid, name[:80], jetzt.isoformat(), _cent(kosten))).lastrowid
        return cid

    def charge_aendern(self, cid, name, kosten):
        name = (name or "").strip()
        if not name:
            raise Fehler("name_fehlt")
        with self.d._verbindung() as v:
            if not v.execute("UPDATE chargen SET name = ?, kosten_cent = ? WHERE id = ?",
                             (name[:80], _cent(kosten), cid)).rowcount:
                raise Fehler("charge_unbekannt")

    def chargen(self, pid=None):
        """Chargen mit rechnerischer Zuordnung: eingebucht, verkauft, entnommen, Rest, Umsatz nach Rabatt,
        Rabattanteil, Kosten und Gewinn."""
        with self.d._verbindung() as v:
            produkte = [dict(p) for p in v.execute(
                "SELECT id, name, preis_cent, kategorie FROM wurstprodukte" + (" WHERE id = ?" if pid else "")
                + " ORDER BY kategorie = 'honig', name", (pid,) if pid else ())]
            for p in produkte:
                self._startcharge(v, p["id"], p["name"])
            alle_chargen = [dict(c) for c in v.execute("SELECT * FROM chargen ORDER BY produkt_id, beginn, id")]
            bewegungen = [dict(b) for b in v.execute("SELECT * FROM wurstbewegungen ORDER BY erstellt, id")]
        bestellungen = {}

        def stueckpreis(oid, produkt_id):
            if oid not in bestellungen:
                try:
                    bestellungen[oid] = self.bestellung(oid)
                except Fehler:
                    bestellungen[oid] = None
            b = bestellungen[oid]
            if not b:
                return 0, 0
            z = next((z for z in b["wurst"] if z["produkt_id"] == produkt_id), None)
            if not z:
                return 0, 0
            anteil = z["einzelpreis_cent"] * b["rabatt_cent"] / b["positionen_cent"] if b["positionen_cent"] else 0
            return z["einzelpreis_cent"], anteil

        ergebnis = []
        for p in produkte:
            ch = [c for c in alle_chargen if c["produkt_id"] == p["id"]]
            for c in ch:
                c.update(eingebucht=0, verkauft=0, entnommen=0, rest=0, umsatz=0.0, rabatt=0.0)
            verbrauch = {}
            for b in (b for b in bewegungen if b["produkt_id"] == p["id"]):
                oid = int(b["grund"][len("Bestellung #"):]) if b["grund"].startswith("Bestellung #") else None
                if b["menge"] > 0 and b["art"] == "ruecknahme" and oid in verbrauch:
                    rest = b["menge"]
                    while rest and verbrauch[oid]:
                        c, q, preis, anteil = verbrauch[oid].pop()
                        n = min(q, rest)
                        c["rest"] += n; c["verkauft"] -= n
                        c["umsatz"] -= n * (preis - anteil); c["rabatt"] -= n * anteil
                        if q > n:
                            verbrauch[oid].append((c, q - n, preis, anteil))
                        rest -= n
                    continue
                if b["menge"] > 0:
                    c = [c for c in ch if c["beginn"] <= b["erstellt"]][-1]
                    c["eingebucht"] += b["menge"]; c["rest"] += b["menge"]
                    continue
                offen = -b["menge"]
                preis, anteil = stueckpreis(oid, p["id"]) if b["art"] == "auslieferung" and oid else (0, 0)
                while offen:
                    c = next((c for c in ch if c["rest"] > 0), ch[-1])
                    n = min(offen, c["rest"]) if c["rest"] > 0 else offen
                    c["rest"] -= n
                    if b["art"] == "auslieferung":
                        c["verkauft"] += n; c["umsatz"] += n * (preis - anteil); c["rabatt"] += n * anteil
                        verbrauch.setdefault(oid, []).append((c, n, preis, anteil))
                    else:
                        c["entnommen"] += n
                    offen -= n
            for c in ch:
                umsatz, rabatt = round(c.pop("umsatz")), round(c.pop("rabatt"))
                ergebnis.append({**c, "produkt": p["name"], "kategorie": p["kategorie"], "umsatz_cent": umsatz,
                                 "rabatt_cent": rabatt, "lagerwert_cent": max(c["rest"], 0) * p["preis_cent"],
                                 "gewinn_cent": None if c["kosten_cent"] is None else umsatz - c["kosten_cent"]})
        return ergebnis

    # ---------------- Einstellungen und Zahlungserinnerung ----------------
    STANDARD = {"erinnerung_tage": "3", "erinnerung_uhrzeit": "18:00", "erinnerung_ziel": "", "erinnerung_zuletzt": ""}

    def einstellung(self, schluessel):
        with self.d._verbindung() as v:
            z = v.execute("SELECT wert FROM einstellungen WHERE schluessel = ?", (schluessel,)).fetchone()
        return z[0] if z else self.STANDARD.get(schluessel, "")

    def einstellung_setzen(self, schluessel, wert):
        with self.d._verbindung() as v:
            v.execute("INSERT INTO einstellungen(schluessel, wert) VALUES(?, ?) "
                      "ON CONFLICT(schluessel) DO UPDATE SET wert = excluded.wert", (schluessel, str(wert)))

    def ueberfaellig(self, tage=None):
        """Geliefert, aber seit mindestens `tage` Tagen nicht (ganz) bezahlt."""
        tage = int(self.einstellung("erinnerung_tage") if tage is None else tage)
        grenze = (self.d.uhr() - timedelta(days=tage)).isoformat()
        with self.d._verbindung() as v:
            ids = [z[0] for z in v.execute(
                "SELECT id FROM bestellungen WHERE status = 'ausgeliefert' AND ausgeliefert_am <= ? "
                "ORDER BY ausgeliefert_am", (grenze,))]
        heute = self.d.uhr().date()
        liste = []
        for oid in ids:
            b = self.bestellung(oid)
            if b["offen_cent"] > 0:
                b["tage"] = (heute - datetime.fromisoformat(b["ausgeliefert_am"]).date()).days
                liste.append(b)
        return liste

    # ---------------- Packliste ----------------
    def packliste_ids(self):
        """Gespeicherte Packliste. Gelieferte oder stornierte Bestellungen fallen von selbst heraus."""
        with self.d._verbindung() as v:
            v.execute("DELETE FROM packliste WHERE bestellung_id NOT IN "
                      "(SELECT id FROM bestellungen WHERE status = 'offen')")
            return [z[0] for z in v.execute(
                "SELECT p.bestellung_id FROM packliste p JOIN bestellungen b ON b.id = p.bestellung_id ORDER BY b.id")]

    def packliste_setzen(self, ids):
        with self.d._verbindung() as v:
            v.execute("DELETE FROM packliste")
            v.executemany("INSERT OR IGNORE INTO packliste(bestellung_id) SELECT id FROM bestellungen "
                          "WHERE id = ? AND status = 'offen'", [(int(i),) for i in ids])
        return self.packliste_ids()

    # ---------------- Korrekturen ----------------
    def _offen(self, v, oid):
        b = v.execute("SELECT * FROM bestellungen WHERE id = ?", (oid,)).fetchone()
        if not b:
            raise Fehler("bestellung_unbekannt")
        if b["status"] != "offen":
            raise Fehler("bestellung_nicht_offen", status=b["status"])
        return b

    def bestellung_aendern(self, oid, mengen=None, neu=None, fleisch_weg=(), fleisch_neu=None, datum=None):
        """Ändert eine offene Bestellung in einem Schritt.
        mengen: {position_id: neue Menge} (0 entfernt), neu: {produkt_id: Menge},
        fleisch_weg: Zeilen-IDs der Tüten, fleisch_neu: [(Wildart, Teilstück, Anzahl)]."""
        with self.d._verbindung() as v:
            self._offen(v, oid)
            for pos_id, menge in (mengen or {}).items():
                menge = _ganz(menge)
                z = v.execute("SELECT * FROM bestellpositionen WHERE id = ? AND bestellung_id = ?",
                              (pos_id, oid)).fetchone()
                if not z:
                    raise Fehler("position_unbekannt")
                if menge == z["menge"]:
                    continue
                if menge < z["ausgeliefert"] or menge < 0 or menge > 1000:
                    raise Fehler("menge_ungueltig", ware=z["produktname"])
                if menge > z["menge"]:
                    frei = (v.execute(BESTAND_WURST, (z["produkt_id"],)).fetchone()[0]
                            - v.execute(RESERVIERT_WURST, (z["produkt_id"],)).fetchone()[0])
                    if frei < menge - z["menge"]:
                        raise Fehler("bestand_nicht_ausreichend", ware=z["produktname"], frei=max(frei, 0))
                if menge == 0:
                    v.execute("DELETE FROM bestellpositionen WHERE id = ?", (pos_id,))
                else:
                    v.execute("UPDATE bestellpositionen SET menge = ? WHERE id = ?", (menge, pos_id))
            for pid, menge in (neu or {}).items():
                menge = _ganz(menge)
                if menge <= 0:
                    continue
                p = v.execute("SELECT * FROM wurstprodukte WHERE id = ? AND aktiv = 1", (pid,)).fetchone()
                if not p:
                    raise Fehler("produkt_unbekannt")
                frei = v.execute(BESTAND_WURST, (pid,)).fetchone()[0] - v.execute(RESERVIERT_WURST, (pid,)).fetchone()[0]
                if frei < menge:
                    raise Fehler("bestand_nicht_ausreichend", ware=p["name"], frei=max(frei, 0))
                z = v.execute("SELECT id FROM bestellpositionen WHERE bestellung_id = ? AND produkt_id = ?",
                              (oid, pid)).fetchone()
                if z:
                    v.execute("UPDATE bestellpositionen SET menge = menge + ? WHERE id = ?", (menge, z[0]))
                else:
                    v.execute("INSERT INTO bestellpositionen(bestellung_id, produkt_id, produktname, einheit, menge, "
                              "einzelpreis_cent) VALUES(?, ?, ?, ?, ?, ?)",
                              (oid, pid, p["name"], p["einheit"], menge, p["preis_cent"]))
            for zid in fleisch_weg:
                v.execute("DELETE FROM bestell_fleisch WHERE id = ? AND bestellung_id = ? AND ausgeliefert = 0",
                          (zid, oid))
            gewaehlt = []
            for art, teil, menge in (fleisch_neu or []):
                gewaehlt += self._fleisch_auswahl(v, art, teil, _ganz(menge), {g["id"] for g in gewaehlt})
            for paket in gewaehlt:
                v.execute("INSERT INTO bestell_fleisch(bestellung_id, paket_id, preis_cent) VALUES(?, ?, ?)",
                          (oid, paket["id"], self._tuetenpreis(v, paket)))
            if datum:
                if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", datum):
                    raise Fehler("datum_ungueltig")
                v.execute("UPDATE bestellungen SET datum = ? WHERE id = ?", (datum, oid))
            rest = v.execute("SELECT COUNT(*) FROM bestellpositionen WHERE bestellung_id = ?", (oid,)).fetchone()[0]
            rest += v.execute("SELECT COUNT(*) FROM bestell_fleisch WHERE bestellung_id = ?", (oid,)).fetchone()[0]
            if rest == 0:
                raise Fehler("bestellung_leer")
        return self.bestellung(oid)

    def lieferung_zuruecknehmen(self, oid):
        """Macht eine Auslieferung rückgängig. Gebuchte Wurst kommt zurück ins Lager, Tüten zurück ins Fach."""
        with self.d._verbindung() as v:
            b = v.execute("SELECT * FROM bestellungen WHERE id = ?", (oid,)).fetchone()
            if not b:
                raise Fehler("bestellung_unbekannt")
            if b["status"] == "storniert":
                raise Fehler("bestellung_storniert")
            jetzt = self._jetzt()
            for a in v.execute("SELECT a.*, p.produkt_id FROM auslieferungen a JOIN bestellpositionen p "
                               "ON p.id = a.position_id WHERE a.bestellung_id = ?", (oid,)).fetchall():
                v.execute("INSERT INTO wurstbewegungen(produkt_id, menge, art, grund, erstellt) "
                          "VALUES(?, ?, 'ruecknahme', ?, ?)", (a["produkt_id"], a["menge"], f"Bestellung #{oid}", jetzt))
            v.execute("DELETE FROM auslieferungen WHERE bestellung_id = ?", (oid,))
            # Früher gelieferte, nachgetragene Bestellungen hatten keine Lagerbewegung; dann bleibt auch das Lager gleich.
            v.execute("UPDATE bestellpositionen SET ausgeliefert = 0 WHERE bestellung_id = ?", (oid,))
            for f in v.execute("SELECT * FROM bestell_fleisch WHERE bestellung_id = ? AND ausgeliefert = 1", (oid,)).fetchall():
                v.execute("UPDATE pakete SET status = 'lager', ausgelagert = NULL WHERE id = ? AND status = 'raus'",
                          (f["paket_id"],))
            v.execute("UPDATE bestell_fleisch SET ausgeliefert = 0 WHERE bestellung_id = ?", (oid,))
            v.execute("UPDATE bestellungen SET status = 'offen', ausgeliefert_am = NULL WHERE id = ?", (oid,))
        return self.bestellung(oid)

    def frueher_geliefert(self, oid):
        """Markiert eine offene Bestellung als schon früher geliefert, ohne den Wurstbestand zu ändern.
        Für Lieferungen, die vor dem Eintragen des Bestands passiert sind."""
        with self.d._verbindung() as v:
            self._offen(v, oid)
            if v.execute("SELECT COUNT(*) FROM auslieferungen WHERE bestellung_id = ?", (oid,)).fetchone()[0]:
                raise Fehler("teilweise_geliefert")
            v.execute("UPDATE bestellpositionen SET ausgeliefert = menge WHERE bestellung_id = ?", (oid,))
            for f in v.execute("SELECT * FROM bestell_fleisch WHERE bestellung_id = ?", (oid,)).fetchall():
                v.execute("UPDATE pakete SET status = 'raus', ausgelagert = ? WHERE id = ? AND status = 'lager'",
                          (self._jetzt(), f["paket_id"]))
            v.execute("UPDATE bestell_fleisch SET ausgeliefert = 1 WHERE bestellung_id = ?", (oid,))
            v.execute("UPDATE bestellungen SET status = 'ausgeliefert', ausgeliefert_am = ? WHERE id = ?",
                      (self._jetzt(), oid))
        return self.bestellung(oid)

    def bestellung_loeschen(self, oid):
        """Löscht eine stornierte Bestellung endgültig, z. B. einen Irrtum."""
        with self.d._verbindung() as v:
            b = v.execute("SELECT * FROM bestellungen WHERE id = ?", (oid,)).fetchone()
            if not b:
                raise Fehler("bestellung_unbekannt")
            if b["status"] != "storniert":
                raise Fehler("erst_stornieren")
            for tabelle in ("zahlungen", "auslieferungen", "bestellpositionen", "bestell_fleisch"):
                v.execute(f"DELETE FROM {tabelle} WHERE bestellung_id = ?", (oid,))
            v.execute("DELETE FROM bestellungen WHERE id = ?", (oid,))

    def kunden_zusammenfuehren(self, von, nach):
        """Hängt alle Bestellungen von einem doppelten Kunden an den richtigen und blendet den doppelten aus."""
        if int(von) == int(nach):
            raise Fehler("gleicher_kunde")
        with self.d._verbindung() as v:
            if not v.execute("SELECT 1 FROM kunden WHERE id = ? AND aktiv = 1", (nach,)).fetchone():
                raise Fehler("kunde_unbekannt")
            v.execute("UPDATE bestellungen SET kunde_id = ? WHERE kunde_id = ?", (nach, von))
            v.execute("UPDATE vormerkungen SET kunde_id = ? WHERE kunde_id = ?", (nach, von))
            v.execute("UPDATE kunden SET aktiv = 0 WHERE id = ?", (von,))

    def kunde_loeschen(self, kid):
        with self.d._verbindung() as v:
            if v.execute("SELECT COUNT(*) FROM bestellungen WHERE kunde_id = ?", (kid,)).fetchone()[0]:
                raise Fehler("kunde_hat_bestellungen")
            v.execute("UPDATE kunden SET aktiv = 0 WHERE id = ?", (kid,))

    def zahlung_loeschen(self, oid, zid):
        """Für versehentlich gebuchte Zahlungen."""
        with self.d._verbindung() as v:
            c = v.execute("DELETE FROM zahlungen WHERE id = ? AND bestellung_id = ?", (zid, oid))
            if c.rowcount != 1:
                raise Fehler("zahlung_unbekannt")
        return self.bestellung(oid)

    def ausliefern(self, oid, position_id=None, menge=None):
        """Ohne Angabe wird alles Offene ausgeliefert. Wurst verlässt dann das Lager, Fleisch wird ausgelagert."""
        with self.d._verbindung() as v:
            b = v.execute("SELECT * FROM bestellungen WHERE id = ?", (oid,)).fetchone()
            if not b:
                raise Fehler("bestellung_unbekannt")
            if b["status"] != "offen":
                raise Fehler("bestellung_nicht_offen", status=b["status"])
            jetzt = self._jetzt()
            positionen = v.execute(
                "SELECT * FROM bestellpositionen WHERE bestellung_id = ? AND ausgeliefert < menge"
                + (" AND id = ?" if position_id else ""), (oid, position_id) if position_id else (oid,)).fetchall()
            for p in positionen:
                n = p["menge"] - p["ausgeliefert"] if menge is None else _ganz(menge)
                if not 0 < n <= p["menge"] - p["ausgeliefert"]:
                    raise Fehler("menge_ungueltig")
                if v.execute(BESTAND_WURST, (p["produkt_id"],)).fetchone()[0] < n:
                    raise Fehler("bestand_nicht_ausreichend", ware=p["produktname"])
                v.execute("UPDATE bestellpositionen SET ausgeliefert = ausgeliefert + ? WHERE id = ?", (n, p["id"]))
                v.execute("INSERT INTO wurstbewegungen(produkt_id, menge, art, grund, erstellt) "
                          "VALUES(?, ?, 'auslieferung', ?, ?)", (p["produkt_id"], -n, f"Bestellung #{oid}", jetzt))
                v.execute("INSERT INTO auslieferungen(bestellung_id, position_id, menge, datum) VALUES(?, ?, ?, ?)",
                          (oid, p["id"], n, jetzt))
            if not position_id:
                for f in v.execute("SELECT * FROM bestell_fleisch WHERE bestellung_id = ? AND ausgeliefert = 0",
                                   (oid,)).fetchall():
                    v.execute("UPDATE bestell_fleisch SET ausgeliefert = 1 WHERE id = ?", (f["id"],))
                    v.execute("UPDATE pakete SET status = 'raus', ausgelagert = ? WHERE id = ? AND status = 'lager'",
                              (jetzt, f["paket_id"]))
            rest = v.execute("SELECT COUNT(*) FROM bestellpositionen WHERE bestellung_id = ? AND ausgeliefert < menge",
                             (oid,)).fetchone()[0]
            rest += v.execute("SELECT COUNT(*) FROM bestell_fleisch WHERE bestellung_id = ? AND ausgeliefert = 0",
                              (oid,)).fetchone()[0]
            if rest == 0:
                v.execute("UPDATE bestellungen SET status = 'ausgeliefert', ausgeliefert_am = ? WHERE id = ?",
                      (self._jetzt(), oid))
        return self.bestellung(oid)

    def stornieren(self, oid):
        with self.d._verbindung() as v:
            b = v.execute("SELECT * FROM bestellungen WHERE id = ?", (oid,)).fetchone()
            if not b:
                raise Fehler("bestellung_unbekannt")
            geliefert = v.execute("SELECT COALESCE(SUM(ausgeliefert), 0) FROM bestellpositionen WHERE bestellung_id = ?",
                                  (oid,)).fetchone()[0]
            geliefert += v.execute("SELECT COALESCE(SUM(ausgeliefert), 0) FROM bestell_fleisch WHERE bestellung_id = ?",
                                   (oid,)).fetchone()[0]
            if geliefert:
                raise Fehler("schon_ausgeliefert")
            v.execute("UPDATE bestellungen SET status = 'storniert' WHERE id = ?", (oid,))
        return self.bestellung(oid)

    def auswertung(self, von, bis, produkt=""):
        """Umsatz nach Bestelldatum, Einnahmen nach Zahlungsdatum, jeweils von–bis einschließlich.
        produkt: "" (alles), "wurst", "honig", "fleisch" oder "p:<produkt_id>"."""
        for tag in (von, bis):
            if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", tag or ""):
                raise Fehler("datum_ungueltig")
        art = {p["id"]: p["kategorie"] for p in self.produkte(nur_aktiv=False)}
        with self.d._verbindung() as v:
            alle = [b for b in self._bestellungen(v, filter="alle")
                    if b["status"] != "storniert" and von <= b["datum"] <= bis]
            zahlungen = v.execute(
                "SELECT z.datum, z.betrag_cent FROM zahlungen z JOIN bestellungen b ON b.id = z.bestellung_id "
                "WHERE b.status != 'storniert' AND substr(z.datum, 1, 10) BETWEEN ? AND ?", (von, bis)).fetchall()

        def passt(kategorie, pid=None):
            if not produkt:
                return True
            if produkt.startswith("p:"):
                return pid is not None and str(pid) == produkt[2:]
            return kategorie == produkt

        zeilen, monate, preis_offen = {}, {}, 0
        for b in alle:
            m = monate.setdefault(b["datum"][:7], {"umsatz_cent": 0, "einnahmen_cent": 0})
            if not produkt:
                m["umsatz_cent"] += b["summe_cent"]
            for z in b["wurst"]:
                k = art.get(z["produkt_id"], "wurst")
                if not passt(k, z["produkt_id"]):
                    continue
                r = zeilen.setdefault(("p", z["produkt_id"]), {"name": z["produktname"], "kategorie": k,
                                                               "menge": 0, "cent": 0, "einheit": z["einheit"]})
                r["menge"] += z["menge"]
                r["cent"] += z["menge"] * z["einzelpreis_cent"]
                if produkt:
                    m["umsatz_cent"] += z["menge"] * z["einzelpreis_cent"]
            for f in b["fleisch"]:
                if not passt("fleisch"):
                    continue
                r = zeilen.setdefault(("f", f["art"], f["teil"]), {"name": f"{f['art']} {f['teil']}", "kategorie": "fleisch",
                                                                  "menge": 0, "cent": 0, "einheit": "Tüte"})
                r["menge"] += 1
                r["cent"] += f["preis_cent"] or 0
                preis_offen += f["preis_cent"] is None
                if produkt:
                    m["umsatz_cent"] += f["preis_cent"] or 0
        for datum, cent in zahlungen:
            monate.setdefault(datum[:7], {"umsatz_cent": 0, "einnahmen_cent": 0})["einnahmen_cent"] += cent
        reihenfolge = {"wurst": 0, "honig": 1, "fleisch": 2}
        liste = sorted(zeilen.values(), key=lambda r: (reihenfolge.get(r["kategorie"], 9), -r["cent"], r["name"]))
        return {
            "zeilen": liste,
            "brutto_cent": sum(r["cent"] for r in liste),
            "rabatt_cent": sum(b["rabatt_cent"] for b in alle),
            "umsatz_cent": sum(b["summe_cent"] for b in alle) if not produkt else sum(r["cent"] for r in liste),
            "einnahmen_cent": sum(c for _, c in zahlungen),
            "bestellungen": len(alle) if not produkt else len({b["id"] for b in alle if any(
                passt(art.get(z["produkt_id"], "wurst"), z["produkt_id"]) for z in b["wurst"]) or (
                passt("fleisch") and b["fleisch"])}),
            "monate": sorted(monate.items()),
            "preis_offen": preis_offen,
        }

    def umsatz(self):
        with self.d._verbindung() as v:
            alle = self._bestellungen(v, filter="alle")
        gueltig = [b for b in alle if b["status"] != "storniert"]
        return {
            "bestellungen": len(gueltig),
            "umsatz_cent": sum(b["summe_cent"] for b in gueltig),
            "bezahlt_cent": sum(min(b["bezahlt_cent"], b["summe_cent"]) for b in gueltig),
            "offen_cent": sum(b["offen_cent"] for b in gueltig),
            "nicht_ausgeliefert": sum(1 for b in gueltig if b["status"] == "offen"),
            "preis_offen": sum(1 for b in gueltig if b["preis_offen"]),
        }
