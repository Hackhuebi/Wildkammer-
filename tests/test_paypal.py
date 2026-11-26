import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from test_korrekturen import bestellung  # noqa: E402
from test_verkauf import api, c, uhr, zugang  # noqa: F401,E402


def _einstellen(c, name):
    return c.post("/erinnerung", data={"tage": "3", "uhrzeit": "18:00", "ziel": "", "paypal": name})


def test_paypal_link_auf_bestellseite_und_fuer_claude(c):
    zugang(c, "Salami", 3)
    a = bestellung(c, "Erik Probst", [{"produkt": "Salami", "menge": 2}])  # 32 €
    html = c.get(f"/bestellungen/{a}").get_data(as_text=True)
    assert "PayPal.me-Namen" in html and "paypal.me/" not in html
    assert "f=1" not in _einstellen(c, "https://paypal.me/testname").headers["Location"]
    html = c.get(f"/bestellungen/{a}").get_data(as_text=True)
    assert "https://paypal.me/testname/32.00EUR" in html
    assert "Hallo Erik, für deine Bestellung (2× Salami) sind noch 32,00 € offen." in html
    c.post(f"/bestellungen/{a}/erhalten", data={"betrag": "10,50", "art": "teil"})
    b = api(c, "bestellungen", kunde="Erik Probst")["bestellungen"][0]
    assert b["paypal_link"] == "https://paypal.me/testname/21.50EUR"
    c.post(f"/bestellungen/{a}/bezahlt")
    assert "paypal.me" not in c.get(f"/bestellungen/{a}").get_data(as_text=True)


def test_paypal_name_pruefen(c):
    assert "f=1" in _einstellen(c, "name mit leerzeichen").headers["Location"]
    _einstellen(c, "paypal.me/anderer/")
    assert 'value="anderer"' in c.get("/erinnerung").get_data(as_text=True)
    _einstellen(c, "")
    assert 'value=""' in c.get("/erinnerung").get_data(as_text=True)


def test_null_euro_bestellung_erst_nach_tippen_bezahlt(c):
    zugang(c, "Rapshonig", 3)  # Preis 0 €
    a = bestellung(c, "Greta", [{"produkt": "Raps", "menge": 1}])
    c.post(f"/bestellungen/{a}/ausgeliefert")
    # Fällt auf: steht weiter als unbezahlt da
    assert api(c, "bestellungen", kunde="Greta")["anzahl"] == 1
    r = c.post(f"/bestellungen/{a}/bezahlt")
    assert "f=1" not in r.headers["Location"]
    assert api(c, "bestellungen", kunde="Greta")["anzahl"] == 0
    assert api(c, "bestellungen", filter="abgeschlossen")["anzahl"] == 1
    # Auch über "Erhalten 0 € – Erledigt" und über Claude
    b = bestellung(c, "Ben", [{"produkt": "Raps", "menge": 1}])
    c.post(f"/bestellungen/{b}/erhalten", data={"betrag": "0,00", "art": "fertig"})
    assert api(c, "bestellungen", kunde="Ben", filter="unbezahlt")["anzahl"] == 0
    d = bestellung(c, "Lena", [{"produkt": "Raps", "menge": 1}])
    assert api(c, "bezahlt", bestellung_id=d)["bestellung"]["vollstaendig_bezahlt"]


def test_halb_erledigte_bestellungen_oben(c):
    zugang(c, "Salami", 6)
    beides = bestellung(c, "Anna", [{"produkt": "Salami", "menge": 1}])
    geliefert = bestellung(c, "Ben", [{"produkt": "Salami", "menge": 1}])
    bezahlt = bestellung(c, "Greta", [{"produkt": "Salami", "menge": 1}])
    fertig = bestellung(c, "Lena", [{"produkt": "Salami", "menge": 1}])
    c.post(f"/bestellungen/{geliefert}/ausgeliefert")
    c.post(f"/bestellungen/{bezahlt}/bezahlt")
    c.post(f"/bestellungen/{fertig}/ausgeliefert")
    c.post(f"/bestellungen/{fertig}/bezahlt")
    html = c.get("/bestellungen?filter=alle").get_data(as_text=True)
    pos = {n: html.index(f"{n}</") for n in ("Anna", "Ben", "Greta", "Lena")}
    assert max(pos["Ben"], pos["Greta"]) < pos["Anna"] < pos["Lena"]
