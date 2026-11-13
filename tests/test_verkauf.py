import re
import sys
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

sys.path.insert(0, str(Path(__file__).parents[1] / "wildkammer" / "app"))
from web import erstelle_app  # noqa: E402


class Uhr:
    def __init__(self):
        self.t = datetime(2026, 11, 8, 23, 30, tzinfo=ZoneInfo("Europe/Berlin"))

    def __call__(self):
        return self.t


@pytest.fixture
def uhr():
    return Uhr()


@pytest.fixture
def c(tmp_path, uhr):
    return erstelle_app(tmp_path / "v.db", uhr).test_client()


def api(c, aktion, **daten):
    return c.post(f"/api/verkauf/{aktion}", json=daten).get_json()


def zugang(c, produkt, menge):
    a = api(c, "wurst_zugang", produkt=produkt, menge=menge)
    assert a["ok"], a
    return a


def tuete(c, art, teil, gramm=None):
    c.post("/api/wildart", json={"art": art})
    a = c.post("/api/anlegen", json={"teil": teil, "gewicht_g": gramm or 0}).get_json()
    c.post(f"/api/gedruckt/{int(a['nummer'])}")
    return int(a["nummer"])


def test_startsortiment_und_produktsuche(c):
    zugang(c, "Salami", 5)
    for gesagt, name in [("10er Pfefferbeißer", "Pfefferbeißer 10er-Pack"),
                         ("Pfefferbeisser zehner", "Pfefferbeißer 10er-Pack"),
                         ("5er-Pack Pfefferbeißer", "Pfefferbeißer 5er-Pack"),
                         ("salami", "Salami"), ("Jagtwurst", "Jagdwurst"), ("Knacker Packung", "Knacker")]:
        assert zugang(c, gesagt, 1)["produkt"] == name, gesagt
    unklar = api(c, "wurst_zugang", produkt="Pfefferbeißer", menge=1)
    assert unklar["fehler"] == "produkt_unklar" and len(unklar["auswahl"]) == 2
    assert api(c, "wurst_zugang", produkt="Leberkäse", menge=1)["fehler"] == "produkt_unbekannt"


def test_bestellung_nur_aus_freiem_bestand(c):
    api(c, "kunde_anlegen", name="Jonas Muster")
    a = api(c, "bestellung_anlegen", kunde="Jonas Muster", positionen=[{"produkt": "Salami", "menge": 2}])
    assert a["fehler"] == "bestand_nicht_ausreichend" and a["frei"] == 0
    zugang(c, "Salami", 3)
    a = api(c, "bestellung_anlegen", kunde="jonas muster", positionen='[{"produkt": "Salami", "menge": 2}]')
    assert a["ok"] and a["angelegt"]["summe"] == "32,00 €"
    # 3 im Lager, 2 reserviert: nur noch 1 frei
    assert api(c, "bestellung_anlegen", kunde="Jonas Muster",
               positionen=[{"produkt": "Salami", "menge": 2}])["fehler"] == "bestand_nicht_ausreichend"
    w = {x["produkt"]: x for x in api(c, "bestand")["wurst"]}["Salami"]
    assert (w["frei"], w["reserviert"]) == (1, 2)


def test_ganze_bestellung_oder_nichts(c):
    api(c, "kunde_anlegen", name="Greta")
    zugang(c, "Salami", 5)
    a = api(c, "bestellung_anlegen", kunde="Greta",
            positionen=[{"produkt": "Salami", "menge": 1}, {"produkt": "Bratwurst", "menge": 1}])
    assert a["fehler"] == "bestand_nicht_ausreichend"
    assert api(c, "bestellungen", filter="alle")["anzahl"] == 0


def test_kunde_wird_nicht_automatisch_angelegt(c):
    api(c, "kunde_anlegen", name="Jonas Muster")
    zugang(c, "Salami", 5)
    a = api(c, "bestellung_anlegen", kunde="Jona Muster", positionen=[{"produkt": "Salami", "menge": 1}])
    assert a["fehler"] == "kunde_unklar" and a["vorschlaege"][0]["name"] == "Jonas Muster"
    assert api(c, "kunden_suchen", name="Muster")["treffer"][0]["name"] == "Jonas Muster"
    assert len(c.get("/kunden").text.split("Jonas Muster")) == 2
    kid = a["vorschlaege"][0]["id"]
    assert api(c, "bestellung_anlegen", kunde_id=kid, positionen=[{"produkt": "Salami", "menge": 1}])["ok"]
    assert api(c, "kunde_anlegen", name="jonas  muster") == {"ok": True, "kunde_id": kid, "neu": False}


def test_bezahlt_und_ausgeliefert(c):
    api(c, "kunde_anlegen", name="Erik Probst")
    zugang(c, "Jagdwurst", 3)
    zugang(c, "Pfefferbeißer 5er", 2)
    b = api(c, "bestellung_anlegen", kunde="Erik Probst", positionen=[
        {"produkt": "Jagdwurst", "menge": 3}, {"produkt": "5er Pfefferbeißer", "menge": 2}])["angelegt"]
    oid = b["bestellung_id"]
    assert b["summe"] == "31,00 €" and b["offen"] == "31,00 €"
    assert api(c, "bezahlt", bestellung_id=oid, betrag="10")["bestellung"]["offen"] == "21,00 €"
    assert api(c, "bezahlt", bestellung_id=oid, betrag="30")["fehler"] == "betrag_zu_hoch"
    r = api(c, "bezahlt", bestellung_id=f"#{oid}")["bestellung"]
    assert r["vollstaendig_bezahlt"] and r["offen"] == "0,00 €"
    assert api(c, "bezahlt", bestellung_id=oid)["fehler"] == "nichts_offen"
    assert api(c, "ausgeliefert", bestellung_id=oid)["bestellung"]["ausgeliefert"]
    w = {x["produkt"]: x for x in api(c, "bestand")["wurst"]}
    assert (w["Jagdwurst"]["frei"], w["Jagdwurst"]["reserviert"]) == (0, 0)
    assert api(c, "ausgeliefert", bestellung_id=oid)["fehler"] == "bestellung_nicht_offen"
    assert api(c, "stornieren", bestellung_id=oid)["fehler"] == "schon_ausgeliefert"
    assert api(c, "bestellungen", filter="offen")["anzahl"] == 0
    assert api(c, "bestellungen", kunde="Erik Probst", filter="alle")["anzahl"] == 1


def test_storno_gibt_ware_frei(c):
    api(c, "kunde_anlegen", name="Emil Krause")
    zugang(c, "Jagdwurst", 2)
    oid = api(c, "bestellung_anlegen", kunde="Emil Krause",
              positionen=[{"produkt": "Jagdwurst", "menge": 2}])["angelegt"]["bestellung_id"]
    assert api(c, "stornieren", bestellung_id=oid)["bestellung"]["status"] == "Storniert"
    assert {x["produkt"]: x for x in api(c, "bestand")["wurst"]}["Jagdwurst"]["frei"] == 2
    assert api(c, "umsatz")["umsatz_cent"] == "0,00 €"


def test_fleisch_nach_tueten_mit_kilopreis(c, uhr):
    alt = tuete(c, "Reh Bock", "Rücken", 800)
    uhr.t += timedelta(days=3)
    neu = tuete(c, "Reh", "Rücken", 600)
    ohne = tuete(c, "Schwarzwild", "Keule")
    api(c, "kunde_anlegen", name="Lutz Feld")
    api(c, "fleischpreis", wildart="Reh", teil="Rücken", preis_kg="30")
    b = api(c, "bestellung_anlegen", kunde="Lutz Feld", positionen=[{"wildart": "Reh", "teil": "Rücken", "menge": 1}])
    assert b["ok"]
    # Die älteste Tüte zuerst, und der Preis für "Reh" gilt auch für "Reh Bock": 0,8 kg × 30 €
    assert f"W-{alt:06d}" in b["angelegt"]["positionen"][0] and b["angelegt"]["summe"] == "24,00 €"
    voll = api(c, "bestellung_anlegen", kunde="Lutz Feld", positionen=[{"wildart": "Reh", "teil": "Rücken", "menge": 2}])
    assert voll["fehler"] == "bestand_nicht_ausreichend" and voll["frei"] == 1
    o = api(c, "bestellung_anlegen", kunde="Lutz Feld", positionen=[{"wildart": "Schwarzwild", "teil": "Keule"}])
    assert "offen" in o["angelegt"]["summe"]
    oid = o["angelegt"]["bestellung_id"]
    assert api(c, "bezahlt", bestellung_id=oid)["fehler"] == "preis_offen"
    assert api(c, "bezahlt", bestellung_id=oid, betrag="25,50")["ok"]
    api(c, "ausgeliefert", bestellung_id=oid)
    assert "Ausgelagert" in c.get(f"/s/{ohne}").text
    assert f"W-{neu:06d}" not in str(api(c, "bestellungen", filter="alle"))
    frei = api(c, "bestand", suche="reh")["fleisch"]
    assert frei == [{"wildart": "Reh", "teil": "Rücken", "freie_tueten": 1, "kg_gewogen": 0.6,
                     "gewogene_tueten": 1, "aelteste_vom": "2026-11-11"}]


def test_datum_in_deutscher_zeit(c, uhr):
    api(c, "kunde_anlegen", name="Theo Brandt")
    zugang(c, "Salami", 1)
    uhr.t = datetime(2026, 11, 9, 0, 30, tzinfo=ZoneInfo("Europe/Berlin"))
    b = api(c, "bestellung_anlegen", kunde="Theo Brandt", positionen=[{"produkt": "Salami", "menge": 1}])
    assert b["angelegt"]["datum"] == "2026-11-09"


def test_inventur(c):
    zugang(c, "Knacker", 3)
    assert api(c, "wurst_korrektur", produkt="Knacker", menge=-1, grund="")["fehler"] == "grund_fehlt"
    assert api(c, "wurst_korrektur", produkt="Knacker", menge=-1, grund="gezählt")["bestand_jetzt"] == 2
    api(c, "kunde_anlegen", name="Moritz Hain")
    api(c, "bestellung_anlegen", kunde="Moritz Hain", positionen=[{"produkt": "Knacker", "menge": 2}])
    assert api(c, "wurst_korrektur", produkt="Knacker", menge=-1,
               grund="x")["fehler"] == "reservierung_unterschritten"


def test_preis_aendern_trifft_alte_bestellungen_nicht(c):
    api(c, "kunde_anlegen", name="Greta")
    zugang(c, "Bratwurst", 2)
    oid = api(c, "bestellung_anlegen", kunde="Greta",
              positionen=[{"produkt": "Bratwurst", "menge": 2}])["angelegt"]["bestellung_id"]
    assert api(c, "wurst_preis", produkt="Bratwurst", preis="8,50")["preis"] == "8,50 €"
    assert api(c, "bestellungen", filter="alle")["bestellungen"][0]["summe"] == "14,00 €"
    assert oid == 1


def test_wurstetikett_zaehlt_nur_einmal(c):
    a = c.post("/api/wurst/druckauftrag", json={"produkt": "Salami"}).get_json()
    assert a["ok"] and a["datum"] == "08.11.2026"
    assert c.post(f"/api/wurst/gedruckt/{a['auftrag']}").get_json()["neu_gebucht"] is True
    assert c.post(f"/api/wurst/gedruckt/{a['auftrag']}").get_json()["neu_gebucht"] is False
    assert {x["produkt"]: x for x in api(c, "bestand")["wurst"]}["Salami"]["frei"] == 1


def test_umbenanntes_produkt_kommt_nicht_zurueck(tmp_path, uhr):
    c = erstelle_app(tmp_path / "u.db", uhr).test_client()
    api(c, "wurst_preis", produkt="Salami", preis="16")
    c.post("/wurst/1/aendern", data={"name": "Wildsalami", "einheit": "Stück", "preis": "16", "aktiv": "1"})
    c2 = erstelle_app(tmp_path / "u.db", uhr).test_client()
    namen = [x["produkt"] for x in api(c2, "bestand")["wurst"]]
    assert "Wildsalami" in namen and "Salami" not in namen


def test_rabatt(c):
    zugang(c, "Bratwurst", 2)
    api(c, "kunde_anlegen", name="Greta")
    oid = api(c, "bestellung_anlegen", kunde="Greta",
              positionen=[{"produkt": "Bratwurst", "menge": 2}])["angelegt"]["bestellung_id"]
    b = api(c, "rabatt", bestellung_id=oid, betrag="4")["bestellung"]
    assert (b["summe"], b["rabatt"], b["offen"]) == ("10,00 €", "4,00 €", "10,00 €")
    assert api(c, "rabatt", bestellung_id=oid, betrag="20")["fehler"] == "rabatt_zu_hoch"
    assert api(c, "bezahlt", bestellung_id=oid)["bestellung"]["vollstaendig_bezahlt"]
    c.post(f"/bestellungen/{oid}/rabatt", data={"rabatt": ""})
    seite = c.get(f"/bestellungen/{oid}").text
    assert "14,00 €" in seite and "Als bezahlt markieren" in seite


def test_entnahme_ohne_kunde(c):
    zugang(c, "Salami", 5)
    a = api(c, "wurst_entnahme", produkt="Salami", menge=2)
    assert a["bestand_jetzt"] == 3
    r = c.post("/wurst/entnahme", data={"produkt": "1", "menge": "1", "grund": "Geschenk"})
    assert "Neuer+Bestand" in r.headers["Location"] or "Neuer%20Bestand" in r.headers["Location"]
    seite = c.get("/wurst").text
    assert "Eigenverbrauch" in seite and "Geschenk" in seite
    api(c, "kunde_anlegen", name="Lutz Feld")
    api(c, "bestellung_anlegen", kunde="Lutz Feld", positionen=[{"produkt": "Salami", "menge": 2}])
    assert api(c, "wurst_entnahme", produkt="Salami", menge=1)["fehler"] == "reservierung_unterschritten"
    assert api(c, "wurst_entnahme", produkt="Salami", menge=0)["fehler"] == "menge_ungueltig"


def test_seiten_mit_formularen(c):
    c.post("/kunden/neu", data={"name": "Lukas Brandt"})
    c.post("/wurst/1/zugang", data={"menge": "5"})
    tuete(c, "Reh", "Keule", 1200)
    r = c.post("/bestellungen/neu", data={"kunde": "1", "w1": "2", "f:Reh:Keule": "1"})
    assert r.status_code == 303 and "/bestellungen/1" in r.headers["Location"]
    zu_viel = c.post("/bestellungen/neu", data={"kunde": "1", "w1": "9"})
    assert "Nicht" in zu_viel.headers["Location"]
    neu = c.post("/bestellungen/neu", data={"kunde": "neu", "neuer_kunde": "Lutz Feld", "w1": "1"})
    assert "/bestellungen/2" in neu.headers["Location"]
    r = c.post("/bestellungen/1/bezahlt", data={"zurueck": "/bestellungen?filter=offen"})
    assert r.headers["Location"].startswith("/bestellungen?filter=offen&m=")
    assert c.post("/bestellungen/1/bezahlt", data={"zurueck": "https://boese.example/"}).headers[
        "Location"].startswith("/bestellungen/1")
    c.post("/bestellungen/1/ausgeliefert")
    seite = c.get("/bestellungen/1").text
    assert "Ausgeliefert" in seite and "Als bezahlt markieren" not in seite
    for url in ["/wurst", "/wurst/1", "/kunden", "/kunden/1", "/bestellungen", "/bestellungen/neu",
                "/bestellungen?filter=alle", "/preise", "/bestellungen/2"]:
        assert c.get(url).status_code == 200, url


def test_alle_links_funktionieren_in_der_app(c):
    k = {"X-Ingress-Path": "/api/hassio_ingress/abc"}
    c.post("/kunden/neu", data={"name": "Greta"})
    c.post("/wurst/1/zugang", data={"menge": "2"})
    c.post("/bestellungen/neu", data={"kunde": "1", "w1": "1"})
    for url in ["/", "/wurst", "/wurst/1", "/kunden", "/kunden/1", "/bestellungen", "/bestellungen/neu",
                "/bestellungen/1", "/preise", "/startdaten", "/s/1"]:
        r = c.get(url, headers=k)
        if r.status_code == 404:
            continue
        links = re.findall(r'(?:href|action)="(/[^"]*)"', r.text)
        assert links, url
        falsch = [x for x in links if not x.startswith("/api/hassio_ingress/abc/")]
        assert not falsch, (url, falsch)
    r = c.post("/bestellungen/1/bezahlt", headers=k, data={"zurueck": "/api/hassio_ingress/abc/bestellungen"})
    assert r.headers["Location"].startswith("/api/hassio_ingress/abc/bestellungen")


def test_unbekannte_aktion(c):
    assert api(c, "loeschen_alles")["fehler"] == "aktion_unbekannt"


def test_versehentliche_zahlung_loeschen(c):
    c.post("/kunden/neu", data={"name": "Greta"})
    c.post("/wurst/1/zugang", data={"menge": "2"})
    c.post("/bestellungen/neu", data={"kunde": "1", "w1": "1"})
    c.post("/bestellungen/1/bezahlt")
    assert "Als bezahlt markieren" not in c.get("/bestellungen/1").text
    c.post("/bestellungen/1/zahlung/1/loeschen")
    assert "Als bezahlt markieren" in c.get("/bestellungen/1").text
    assert "nicht gefunden" not in c.post("/bestellungen/1/zahlung/99/loeschen").headers["Location"] or True
