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


def test_null_euro_bestellung_gilt_als_bezahlt(c):
    zugang(c, "Rapshonig", 2)  # Preis 0 €
    a = bestellung(c, "Greta", [{"produkt": "Raps", "menge": 1}])
    c.post(f"/bestellungen/{a}/ausgeliefert")
    assert api(c, "bestellungen", kunde="Greta")["anzahl"] == 0          # nicht mehr offen
    assert api(c, "bestellungen", filter="abgeschlossen")["anzahl"] == 1
    assert "Greta" not in c.get("/").get_data(as_text=True)
