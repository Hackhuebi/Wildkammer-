import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from test_verkauf import api, c, tuete, uhr, zugang  # noqa: F401,E402


def frei(c, name):
    return {w["produkt"]: w for w in api(c, "bestand")["wurst"]}[name]


def bestellung(c, kunde, positionen):
    api(c, "kunde_anlegen", name=kunde)
    a = api(c, "bestellung_anlegen", kunde=kunde, positionen=positionen)
    assert a["ok"], a
    return a["angelegt"]["bestellung_id"]


def positions_ids(c, oid):
    import re
    html = c.get(f"/bestellungen/{oid}").get_data(as_text=True)
    return {int(m) for m in re.findall(r'name="m(\d+)"', html)}, html


def test_menge_aendern_entfernen_und_dazu(c):
    zugang(c, "Salami", 5)
    zugang(c, "Knacker", 2)
    oid = bestellung(c, "Greta", [{"produkt": "Salami", "menge": 2}, {"produkt": "Knacker", "menge": 1}])
    ids, _ = positions_ids(c, oid)
    salami, knacker = sorted(ids)
    r = c.post(f"/bestellungen/{oid}/aendern", data={f"m{salami}": "4", f"m{knacker}": "0"})
    assert "ge%C3%A4ndert" in r.headers["Location"]
    assert frei(c, "Salami")["frei"] == 1 and frei(c, "Knacker")["frei"] == 2
    # Mehr als frei geht nicht, und es bleibt alles beim Alten.
    r = c.post(f"/bestellungen/{oid}/aendern", data={f"m{salami}": "6", "datum": "2026-11-01"})
    assert "f=1" in r.headers["Location"]
    assert frei(c, "Salami")["frei"] == 1
    assert "2026-11-01" not in c.get(f"/bestellungen/{oid}").get_data(as_text=True)
    # Neues Produkt dazu und Datum ändern.
    html = c.get(f"/bestellungen/{oid}").get_data(as_text=True)
    import re
    knacker_id = re.search(r'<option value="(\d+)" data-frei="2">Knacker \(frei 2\)', html).group(1)
    r = c.post(f"/bestellungen/{oid}/aendern", data={"neu_produkt": knacker_id, "neu_menge": "2", "datum": "2026-11-01"})
    assert "f=1" not in r.headers["Location"]
    assert frei(c, "Knacker")["frei"] == 0
    assert 'value="2026-11-01"' in c.get(f"/bestellungen/{oid}").get_data(as_text=True)


def test_leere_bestellung_verboten(c):
    zugang(c, "Salami", 1)
    oid = bestellung(c, "Ben", [{"produkt": "Salami", "menge": 1}])
    (pos,), _ = positions_ids(c, oid)
    r = c.post(f"/bestellungen/{oid}/aendern", data={f"m{pos}": "0"})
    assert "f=1" in r.headers["Location"]
    assert frei(c, "Salami")["frei"] == 0


def test_fleisch_tauschen(c):
    tuete(c, "Reh", "Keule", 900)
    tuete(c, "Reh", "Keule", 1000)
    tuete(c, "Reh", "Blatt", 700)
    oid = bestellung(c, "Moritz", [{"wildart": "Reh", "teil": "Keule", "menge": 1}])
    html = c.get(f"/bestellungen/{oid}").get_data(as_text=True)
    import re
    zeile = re.search(r'name="weg" value="(\d+)"', html).group(1)
    r = c.post(f"/bestellungen/{oid}/aendern", data={"weg": zeile, "neu_fleisch": "Reh:Blatt", "neu_tueten": "1"})
    assert "f=1" not in r.headers["Location"]
    b = api(c, "bestellungen", kunde="Moritz")["bestellungen"][0]
    assert len(b["positionen"]) == 1 and "Blatt" in b["positionen"][0]
    assert {f["teil"]: f["freie_tueten"] for f in api(c, "bestand")["fleisch"]} == {"Keule": 2}


def test_lieferung_zuruecknehmen(c):
    zugang(c, "Salami", 3)
    tuete(c, "Reh", "Keule", 900)
    oid = bestellung(c, "Erik", [{"produkt": "Salami", "menge": 2}, {"wildart": "Reh", "teil": "Keule", "menge": 1}])
    c.post(f"/bestellungen/{oid}/ausgeliefert")
    s = frei(c, "Salami")
    assert s["frei"] == 1 and s["reserviert"] == 0
    r = c.post(f"/bestellungen/{oid}/zuruecknehmen")
    assert "f=1" not in r.headers["Location"]
    s = frei(c, "Salami")
    assert s["frei"] == 1 and s["reserviert"] == 2  # Bestand wieder 3, davon 2 für die Bestellung
    html = c.get(f"/bestellungen/{oid}").get_data(as_text=True)
    assert "Offen" in html and "nicht geliefert" in html
    # Die Tüte ist wieder im Lager, aber weiter der Bestellung zugeordnet.
    assert api(c, "bestand")["fleisch"] == []


def test_frueher_geliefert_ohne_lagerbewegung(c):
    zugang(c, "Jagdwurst", 2)
    oid = bestellung(c, "Jan", [{"produkt": "Jagdwurst", "menge": 2}])
    r = c.post(f"/bestellungen/{oid}/frueher")
    assert "f=1" not in r.headers["Location"]
    s = frei(c, "Jagdwurst")
    assert s["frei"] == 2 and s["reserviert"] == 0
    # Zurücknehmen bucht nichts zurück, weil nichts abgebucht wurde.
    c.post(f"/bestellungen/{oid}/zuruecknehmen")
    s = frei(c, "Jagdwurst")
    assert s["frei"] == 0 and s["reserviert"] == 2


def test_nur_offene_aendern_und_loeschen_nach_storno(c):
    zugang(c, "Salami", 2)
    oid = bestellung(c, "Emil", [{"produkt": "Salami", "menge": 1}])
    assert "f=1" in c.post(f"/bestellungen/{oid}/loeschen").headers["Location"]
    c.post(f"/bestellungen/{oid}/storno")
    assert "f=1" in c.post(f"/bestellungen/{oid}/aendern", data={"datum": "2026-01-01"}).headers["Location"]
    r = c.post(f"/bestellungen/{oid}/loeschen")
    assert "f=1" not in r.headers["Location"]
    assert c.get(f"/bestellungen/{oid}").status_code == 404


def test_kunden_zusammenfuehren_und_loeschen(c):
    zugang(c, "Salami", 2)
    a = api(c, "kunde_anlegen", name="Karl Beispiel")["kunde_id"]
    b = api(c, "kunde_anlegen", name="Karl Otto Beispiel")["kunde_id"]
    api(c, "bestellung_anlegen", kunde_id=a, positionen=[{"produkt": "Salami", "menge": 1}])
    assert "f=1" in c.post(f"/kunden/{a}/loeschen").headers["Location"]
    r = c.post(f"/kunden/{a}/zusammenfuehren", data={"nach": str(b)})
    assert r.headers["Location"].split("?")[0].endswith(f"/kunden/{b}")
    assert api(c, "bestellungen", kunde_id=b)["anzahl"] == 1
    html = c.get("/kunden").get_data(as_text=True)
    assert "Karl Otto Beispiel" in html and ">Karl Beispiel<" not in html
    leer = api(c, "kunde_anlegen", name="Testkunde")["kunde_id"]
    assert "f=1" not in c.post(f"/kunden/{leer}/loeschen").headers["Location"]
    assert "Testkunde" not in c.get("/kunden").get_data(as_text=True)


def test_links_unter_ingress(c):
    zugang(c, "Salami", 1)
    oid = bestellung(c, "Finn", [{"produkt": "Salami", "menge": 1}])
    pfad = "/api/hassio_ingress/abc"
    html = c.get(f"/bestellungen/{oid}", headers={"X-Ingress-Path": pfad}).get_data(as_text=True)
    for ziel in ("aendern", "frueher", "storno"):
        assert f'action="{pfad}/bestellungen/{oid}/{ziel}"' in html
    kid = api(c, "kunde_anlegen", name="Finn")["kunde_id"]
    api(c, "kunde_anlegen", name="Lutz")
    html = c.get(f"/kunden/{kid}", headers={"X-Ingress-Path": pfad}).get_data(as_text=True)
    assert f'action="{pfad}/kunden/{kid}/zusammenfuehren"' in html


def test_api_fuer_claude(c):
    zugang(c, "Salami", 3)
    zugang(c, "Bratwurst", 1)
    oid = bestellung(c, "Jonas", [{"produkt": "Salami", "menge": 2}])
    a = api(c, "bestellung_aendern", bestellung_id=str(oid), produkt="salami", menge="3", datum="")
    assert a["ok"] and a["geaendert"]["positionen"] == ["3 × Salami"]
    a = api(c, "bestellung_aendern", bestellung_id=f"#{oid}", produkt="Bratwurst", menge=1)
    assert a["ok"] and "1 × Bratwurst" in a["geaendert"]["positionen"]
    assert api(c, "bestellung_aendern", bestellung_id=oid, produkt="Salami", menge=5)["fehler"] == "bestand_nicht_ausreichend"
    assert api(c, "bestellung_aendern", bestellung_id=oid, produkt="Salami", menge="")["fehler"] == "menge_ungueltig"
    assert api(c, "bestellung_aendern", bestellung_id=oid, produkt="Salami", menge="0")["ok"]
    c.post(f"/bestellungen/{oid}/ausgeliefert")
    assert frei(c, "Bratwurst")["frei"] == 0
    a = api(c, "lieferung_zuruecknehmen", bestellung_id=oid)
    assert a["ok"] and a["zurueckgenommen"]["status"] == "Offen"
    assert frei(c, "Bratwurst")["reserviert"] == 1 and frei(c, "Salami")["frei"] == 3


def test_ha_zahl_mit_komma_null(c):
    zugang(c, "Salami", 2)
    oid = bestellung(c, "Leon", [{"produkt": "Salami", "menge": "1.0"}])
    assert api(c, "bestellung_aendern", bestellung_id=oid, produkt="Salami", menge="2.0")["ok"]
    assert api(c, "bestellung_aendern", bestellung_id=oid, produkt="Salami", menge="1.5")["fehler"] == "menge_ungueltig"


def test_lager_mehrere_entnehmen_und_einbuchen(c):
    zugang(c, "Salami", 3)
    zugang(c, "Knacker", 2)
    oid = bestellung(c, "Lutz", [{"produkt": "Salami", "menge": 2}])
    assert oid
    ids = {w["produkt"]: None for w in api(c, "bestand")["wurst"]}
    import re
    html = c.get("/wurst").get_data(as_text=True)
    pid = dict((n, i) for i, n in re.findall(r'name="n(\d+)".*?aria-label="([^"]+)"', html, re.S))
    assert set(pid) == set(ids) and "data-stepper" in html
    # Mehr als frei bei Salami: nichts wird gebucht, auch Knacker nicht.
    r = c.post("/wurst/buchen", data={"art": "entnahme", f"n{pid['Salami']}": "2", f"n{pid['Knacker']}": "1"})
    assert "f=1" in r.headers["Location"]
    assert frei(c, "Knacker")["frei"] == 2
    r = c.post("/wurst/buchen", data={"art": "entnahme", "grund": "Geschenk",
                                      f"n{pid['Salami']}": "1", f"n{pid['Knacker']}": "2", f"n{pid['Jagdwurst']}": ""})
    assert "3+Packungen+entnommen" in r.headers["Location"] and "f=1" not in r.headers["Location"]
    assert frei(c, "Salami")["frei"] == 0 and frei(c, "Knacker")["frei"] == 0
    assert "Geschenk" in c.get("/wurst").get_data(as_text=True)
    r = c.post("/wurst/buchen", data={"art": "zugang", f"n{pid['Bratwurst']}": "4", f"n{pid['Knacker']}": "1"})
    assert "5+Packungen+eingebucht" in r.headers["Location"]
    assert "f=1" in c.post("/wurst/buchen", data={"art": "entnahme"}).headers["Location"]
    assert "f=1" in c.post("/wurst/buchen", data={"art": "korrektur", f"n{pid['Bratwurst']}": "1"}).headers["Location"]


def test_wurstetikett_mit_qr_und_scan(c):
    a = c.post("/api/wurst/druckauftrag", json={"produkt": "10er Pfefferbeißer"}).get_json()
    assert a["ok"] and a["code"] == "P-000001" and a["zeile1"] == "Pfefferbeißer" and a["zeile2"] == "10er-Pack"
    # Vor dem Druck gibt es die Packung noch nicht.
    assert c.get(f"/w/{a['nummer']}").status_code == 404
    c.post(f"/api/wurst/gedruckt/{a['auftrag']}")
    assert frei(c, "Pfefferbeißer 10er-Pack")["frei"] == 1
    # Scannen leitet auf die Packung, dort wird ausgebucht.
    r = c.post("/scan", data={"eingabe": f"http://192.168.178.60:8099/w/{a['nummer']}"})
    assert r.headers["Location"].endswith(f"/w/{a['nummer']}")
    assert c.post("/scan", data={"eingabe": "p-000001"}).headers["Location"].endswith("/w/1")
    assert "Packung ausbuchen" in c.get("/w/1").get_data(as_text=True)
    c.post("/w/1/aus", data={"grund": "Geschenk"})
    assert frei(c, "Pfefferbeißer 10er-Pack")["frei"] == 0
    assert "f=1" in c.post("/w/1/aus").headers["Location"]  # nicht doppelt
    c.post("/w/1/zurueck")
    assert frei(c, "Pfefferbeißer 10er-Pack")["frei"] == 1


def test_gescannte_packung_schuetzt_bestellte_ware(c):
    a = c.post("/api/wurst/druckauftrag", json={"produkt": "Salami"}).get_json()
    c.post(f"/api/wurst/gedruckt/{a['auftrag']}")
    bestellung(c, "Moritz", [{"produkt": "Salami", "menge": 1}])
    assert "f=1" in c.post(f"/w/{a['nummer']}/aus").headers["Location"]
    assert frei(c, "Salami")["reserviert"] == 1


def test_lager_plus_minus_gemischt(c):
    import re
    zugang(c, "Salami", 3)
    bestellung(c, "Lutz", [{"produkt": "Salami", "menge": 2}])
    html = c.get("/wurst").get_data(as_text=True)
    pid = dict((n, i) for i, n in re.findall(r'name="n(\d+)".*?aria-label="([^"]+)"', html, re.S))
    assert f'name="n{pid["Salami"]}" type="number" min="-1"' in html  # nur freie Ware kann raus
    assert 'name="art"' not in html  # keine Reiter mehr
    r = c.post("/wurst/aendern", data={f"n{pid['Salami']}": "-1", f"n{pid['Bratwurst']}": "4", "grund": "Geschenk"})
    assert "4+eingebucht,+1+entnommen" in r.headers["Location"]
    assert frei(c, "Salami")["frei"] == 0 and frei(c, "Bratwurst")["frei"] == 4
    # Zu viel entnommen: nichts wird gebucht, auch der Zugang nicht.
    r = c.post("/wurst/aendern", data={f"n{pid['Salami']}": "-1", f"n{pid['Knacker']}": "2"})
    assert "f=1" in r.headers["Location"] and frei(c, "Knacker")["frei"] == 0
    assert "f=1" in c.post("/wurst/aendern", data={}).headers["Location"]
