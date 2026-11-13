import sys
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

sys.path.insert(0, str(Path(__file__).parents[1] / "wildkammer" / "app"))
from web import erstelle_app, nummer_aus  # noqa: E402


class Uhr:
    def __init__(self):
        self.t = datetime(2026, 11, 5, 16, 0, tzinfo=ZoneInfo("Europe/Berlin"))

    def __call__(self):
        return self.t


@pytest.fixture
def uhr():
    return Uhr()


@pytest.fixture
def c(tmp_path, uhr):
    return erstelle_app(tmp_path / "t.db", uhr).test_client()


def drucken(c, teil="Hack"):
    a = c.post("/api/anlegen", json={"teil": teil}).get_json()
    assert a["ok"]
    assert c.post(f"/api/gedruckt/{int(a['nummer'])}").get_json()["ok"]
    return a


def test_ohne_wildart_kein_etikett(c):
    assert c.post("/api/anlegen", json={"teil": "Hack"}).get_json() == {"ok": False, "fehler": "wildart_fehlt"}


def test_etikett_daten(c):
    c.post("/api/wildart", json={"art": "Reh"})
    a = drucken(c, "Rücken")
    assert (a["code"], a["nummer"], a["art"], a["teil"], a["datum"], a["stueck"]) == (
        "W-000001", "000001", "Reh", "Rücken", "05.11.2026", 1)


def test_ungedruckte_tuete_zaehlt_nicht(c):
    c.post("/api/wildart", json={"art": "Reh"})
    c.post("/api/anlegen", json={"teil": "Hack"})
    assert c.get("/api/bestand?teil=Hack").get_json()["anzahl"] == 0
    # Die Seite zeigt den Entwurf, damit ein trotz Fehlermeldung gedrucktes Etikett nachgebucht werden kann.
    html = c.get("/s/1").get_data(as_text=True)
    assert "Nicht eingebucht" in html and "Diese Tüte löschen" not in html
    r = c.post("/scan", data={"eingabe": "W-000001"})
    assert r.status_code == 303 and r.headers["Location"].endswith("/s/1")
    assert c.get("/api/bestand?teil=Hack").get_json()["anzahl"] == 0
    c.post("/s/1/einbuchen")
    assert c.get("/api/bestand?teil=Hack").get_json()["anzahl"] == 1
    c.post("/s/1/einbuchen")  # doppelt schadet nicht
    assert c.get("/api/bestand?teil=Hack").get_json()["anzahl"] == 1
    assert c.get("/s/99").status_code == 404


def test_stuecknummer(c):
    assert c.post("/api/wildart", json={"art": "Reh"}).get_json()["stueck"] == 1
    assert c.post("/api/wildart", json={"art": "Reh"}).get_json()["neu"] is False
    assert c.post("/api/neues-stueck").get_json()["stueck"] == 2
    assert c.post("/api/wildart", json={"art": "Schwarzwild"}).get_json()["stueck"] == 3


def test_wildart_laeuft_ab(c, uhr):
    c.post("/api/wildart", json={"art": "Reh"})
    uhr.t += timedelta(hours=11)
    assert drucken(c)["art"] == "Reh"
    uhr.t += timedelta(hours=11)  # jeder Druck verlängert die Sitzung
    assert drucken(c)["art"] == "Reh"
    uhr.t += timedelta(hours=13)
    assert c.post("/api/anlegen", json={"teil": "Hack"}).get_json()["fehler"] == "wildart_fehlt"


def test_datum_springt_mit_dem_tag(c, uhr):
    c.post("/api/wildart", json={"art": "Reh"})
    uhr.t += timedelta(hours=9)
    assert drucken(c)["datum"] == "06.11.2026"


def test_storno_und_nochmal(c, uhr):
    c.post("/api/wildart", json={"art": "Reh"})
    drucken(c, "Hack")
    b = drucken(c, "Keule")
    assert c.get("/api/letztes").get_json()["code"] == b["code"]
    assert c.post("/api/storno").get_json()["code"] == b["code"]
    assert c.post("/api/storno").get_json()["fehler"] == "nichts_vorhanden"
    assert c.get("/api/bestand").get_json()["anzahl"] == 1


def test_storno_nur_kurz_nach_dem_druck(c, uhr):
    c.post("/api/wildart", json={"art": "Reh"})
    drucken(c)
    uhr.t += timedelta(minutes=61)
    assert c.post("/api/storno").get_json()["fehler"] == "nichts_vorhanden"


def test_qr_link_bucht_nicht_ohne_klick(c):
    c.post("/api/wildart", json={"art": "Reh"})
    drucken(c)
    assert "Auslagern" in c.get("/s/1").text
    c.get("/s/1")
    assert c.get("/api/bestand").get_json()["anzahl"] == 1
    assert c.post("/s/1/aus").status_code == 303
    assert c.get("/api/bestand").get_json()["anzahl"] == 0
    c.post("/s/1/ein")
    assert c.get("/api/bestand").get_json()["anzahl"] == 1


def test_scannerfeld(c):
    c.post("/api/wildart", json={"art": "Reh"})
    drucken(c)
    r = c.post("/scan", data={"eingabe": "http://192.168.178.50:8099/s/000001"})
    assert "W-000001 ausgelagert" in r.text
    assert "war nicht im Lager" in c.post("/scan", data={"eingabe": "W-000001"}).text
    assert "gibt es nicht" in c.post("/scan", data={"eingabe": "W-999"}).text


@pytest.mark.parametrize("ein,aus", [("W-000123", 123), ("w000123", 123), ("123", 123),
                                     ("http://x:8099/s/000123", 123), ("abc", None), ("", None), (None, None)])
def test_nummer_aus(ein, aus):
    assert nummer_aus(ein) == aus


def test_bestand_als_satz(c):
    c.post("/api/wildart", json={"art": "Reh"})
    drucken(c)
    drucken(c)
    c.post("/api/wildart", json={"art": "Schwarzwild"})
    drucken(c)
    assert c.get("/api/bestand?teil=Hack").get_json()["text"] == "Hack: 2 Tüten Reh, 1 Tüte Schwarzwild"
    assert c.get("/api/bestand?teil=Leber").get_json()["text"] == "Leber: nichts vorhanden"


def test_filter_gewicht_und_csv(c, uhr):
    c.post("/api/wildart", json={"art": "Reh"})
    drucken(c, "Rücken")
    uhr.t += timedelta(days=200)
    c.post("/api/wildart", json={"art": "Reh"})
    drucken(c, "Hack")
    c.post("/s/1/gewicht", data={"gramm": "850"})
    alt = c.get("/fleisch?monate=6").text
    assert "W-000001" in alt and "W-000002" not in alt
    assert "0,8" in c.get("/fleisch").text or "0,9" in c.get("/fleisch").text
    csv_text = c.get("/export.csv?monate=6").data.decode("utf-8")
    assert csv_text.startswith("﻿Nummer;") and "Rücken" in csv_text and "850" in csv_text
    assert "W-000002" not in csv_text


@pytest.mark.parametrize("ein,g,text", [(800, 800, "800 g"), ("800", 800, "800 g"), (1000, 1000, "1 kg"),
                                        (1250, 1250, "1,25 kg"), (1500, 1500, "1,5 kg")])
def test_gewicht_beim_anlegen(c, ein, g, text):
    c.post("/api/wildart", json={"art": "Reh"})
    a = c.post("/api/anlegen", json={"teil": "Keule", "gewicht_g": ein}).get_json()
    assert (a["gewicht_g"], a["gewicht_text"]) == (g, text)
    assert c.post("/api/gedruckt/1").get_json()["gewicht_text"] == text
    assert c.get("/api/letztes").get_json()["gewicht_g"] == g


@pytest.mark.parametrize("ein", [None, "", 0, "0"])
def test_ohne_gewicht_bleibt_das_feld_frei(c, ein):
    c.post("/api/wildart", json={"art": "Reh"})
    a = c.post("/api/anlegen", json={"teil": "Keule", "gewicht_g": ein}).get_json()
    assert a["ok"] and a["gewicht_g"] is None and a["gewicht_text"] == " "


@pytest.mark.parametrize("ein", [-5, 50001, "abc"])
def test_unplausibles_gewicht_legt_nichts_an(c, ein):
    c.post("/api/wildart", json={"art": "Reh"})
    a = c.post("/api/anlegen", json={"teil": "Keule", "gewicht_g": ein}).get_json()
    assert a == {"ok": False, "fehler": "gewicht_ungueltig"}
    assert c.post("/api/gedruckt/1").get_json()["fehler"] == "nicht_gefunden"


def test_status(c):
    assert c.get("/api/status").get_json() == {"ok": True, "art": "", "stueck": 0}
    c.post("/api/wildart", json={"art": "Reh"})
    assert c.get("/api/status").get_json() == {"ok": True, "art": "Reh", "stueck": 1}


def test_bestand_nennt_kilo_nur_bei_gewicht(c):
    c.post("/api/wildart", json={"art": "Reh"})
    a = c.post("/api/anlegen", json={"teil": "Hack", "gewicht_g": 500}).get_json()
    c.post(f"/api/gedruckt/{int(a['nummer'])}")
    drucken(c)
    t = c.get("/api/bestand?teil=Hack").get_json()["text"]
    assert t == "Hack: 2 Tüten Reh. 1 davon gewogen, zusammen 0,5 Kilogramm"


def test_ungueltiges_gewicht_wird_nicht_gespeichert(c):
    c.post("/api/wildart", json={"art": "Reh"})
    drucken(c)
    for falsch in ["-5", "abc", "99999", "0"]:
        c.post("/s/1/gewicht", data={"gramm": falsch})
        assert " g</p>" not in c.get("/s/1").text


def test_html_wird_maskiert(c):
    c.post("/api/wildart", json={"art": "<script>x</script>"})
    drucken(c)
    assert "<script>x" not in c.get("/fleisch").text


def test_fremde_herkunft_abgewiesen(c):
    c.post("/api/wildart", json={"art": "Reh"})
    drucken(c)
    assert c.post("/s/1/aus", headers={"Origin": "http://boese.example"}).status_code == 403
    assert c.get("/api/bestand").get_json()["anzahl"] == 1
    assert c.post("/s/1/aus", headers={"Origin": "http://localhost"}).status_code == 303


def test_loeschen_mit_rueckfrage(c):
    c.post("/api/wildart", json={"art": "Reh"})
    drucken(c)
    start = c.get("/fleisch").text
    assert "/s/1/loeschen" in start
    frage = c.get("/s/1/loeschen")
    assert frage.status_code == 200 and "Wirklich" not in frage.text and "löschen?" in frage.text
    assert c.get("/api/bestand").get_json()["anzahl"] == 1  # Aufruf allein löscht nichts
    a = c.post("/s/1/loeschen")
    assert a.status_code == 303
    assert "W-000001 gelöscht." in c.get(a.headers["Location"]).text
    assert c.get("/api/bestand").get_json()["anzahl"] == 0
    gel = c.get("/fleisch?status=storniert").text
    assert "W-000001" in gel and "Gelöscht" in gel and "/s/1/loeschen" not in gel
    c.post("/s/1/ein")
    assert c.get("/api/bestand").get_json()["anzahl"] == 1


def test_loeschen_ist_auch_nach_dem_auslagern_moeglich(c):
    c.post("/api/wildart", json={"art": "Reh"})
    drucken(c)
    c.post("/s/1/aus")
    c.post("/s/1/loeschen")
    assert "Gelöscht" in c.get("/s/1").text


def test_zurueck_pfeil(c):
    c.post("/api/wildart", json={"art": "Reh"})
    drucken(c)
    assert "Zurück zum Fleisch" in c.get("/s/1").text
    k = {"X-Ingress-Path": "/api/hassio_ingress/abc"}
    assert 'class="zurueck" href="/api/hassio_ingress/abc/fleisch"' in c.get("/s/1", headers=k).text


def test_loeschen_von_fremder_seite_abgewiesen(c):
    c.post("/api/wildart", json={"art": "Reh"})
    drucken(c)
    assert c.post("/s/1/loeschen", headers={"Origin": "http://boese.example"}).status_code == 403


def test_seite_in_der_home_assistant_app(c):
    k = {"X-Ingress-Path": "/api/hassio_ingress/abc-123", "Origin": "https://x.ui.nabu.casa"}
    c.post("/api/wildart", json={"art": "Reh"})
    drucken(c)
    start = c.get("/fleisch", headers=k).text
    for link in ['/api/hassio_ingress/abc-123/s/1"', '/api/hassio_ingress/abc-123/mehr"',
                 '/api/hassio_ingress/abc-123/wurst"', '/api/hassio_ingress/abc-123/export.csv']:
        assert link in start
    mehr = c.get("/mehr", headers=k).text
    for link in ['/api/hassio_ingress/abc-123/scan"', '/api/hassio_ingress/abc-123/sicherung"',
                 '/api/hassio_ingress/abc-123/kunden"']:
        assert link in mehr
    seite = c.get("/s/1", headers=k).text
    assert 'action="/api/hassio_ingress/abc-123/s/1/aus"' in seite
    a = c.post("/s/1/aus", headers=k)
    assert a.status_code == 303 and a.headers["Location"].startswith("/api/hassio_ingress/abc-123/s/1")
    assert c.get("/api/bestand").get_json()["anzahl"] == 0


def test_falscher_app_pfad_wird_ignoriert(c):
    c.post("/api/wildart", json={"art": "Reh"})
    drucken(c)
    k = {"X-Ingress-Path": "http://boese.example", "Origin": "http://boese.example"}
    assert "boese" not in c.get("/fleisch", headers=k).text
    assert c.post("/s/1/aus", headers=k).status_code == 403


def test_sicherung_ist_lesbar(c, tmp_path):
    import sqlite3
    c.post("/api/wildart", json={"art": "Reh"})
    drucken(c)
    f = tmp_path / "s.db"
    f.write_bytes(c.get("/sicherung").data)
    assert sqlite3.connect(f).execute("SELECT count(*) FROM pakete").fetchone()[0] == 1
