import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "wildkammer" / "app"))
from test_korrekturen import bestellung  # noqa: E402
from test_verkauf import api, c, uhr, zugang  # noqa: F401,E402


def test_ueberfaellig_und_nachricht(c, uhr):
    import erinnerung
    zugang(c, "Salami", 5)
    a = bestellung(c, "Erik Probst", [{"produkt": "Salami", "menge": 2}])
    b = bestellung(c, "Greta", [{"produkt": "Salami", "menge": 1}])
    d = bestellung(c, "Ben", [{"produkt": "Salami", "menge": 1}])
    c.post(f"/bestellungen/{a}/ausgeliefert")
    c.post(f"/bestellungen/{b}/ausgeliefert")
    c.post(f"/bestellungen/{b}/bezahlt")  # bezahlt: keine Erinnerung
    uhr.t += timedelta(days=2)
    c.post(f"/bestellungen/{d}/ausgeliefert")  # erst seit heute geliefert
    uhr.t += timedelta(days=2)
    # Einstellungen über die Seite
    r = c.post("/erinnerung", data={"tage": "3", "uhrzeit": "18:00", "ziel": "mobile_app_iphone"})
    assert "f=1" not in r.headers["Location"]
    html = c.get("/erinnerung").get_data(as_text=True)
    assert "Erik Probst" in html and "Greta" not in html and "Ben<" not in html and "vor 4 Tagen" in html
    assert "seit über 3 Tagen unbezahlt" in c.get("/").get_data(as_text=True)
    # Versand: erst ab Uhrzeit, dann nur einmal am Tag
    vk = c.application.config["VERKAUF"]
    gesendet = []
    anfrage = lambda url, daten=None: gesendet.append((url, daten))
    jetzt = uhr.t.replace(hour=17, minute=59)
    assert erinnerung.pruefen(vk, jetzt, anfrage) is None and not gesendet
    assert erinnerung.pruefen(vk, jetzt.replace(hour=18, minute=0), anfrage) == 1
    url, daten = gesendet[0]
    assert url.endswith("/services/notify/mobile_app_iphone")
    assert "Erik Probst" in daten["message"] and "seit 4 Tagen" in daten["message"] and "unbezahlt" in daten["title"]
    assert erinnerung.pruefen(vk, jetzt.replace(hour=20), anfrage) is None and len(gesendet) == 1
    # Ausgeschaltet
    c.post("/erinnerung", data={"tage": "0", "uhrzeit": "18:00", "ziel": "mobile_app_iphone"})
    assert erinnerung.pruefen(vk, jetzt.replace(hour=21), anfrage) is None
    assert "Erinnerung ist aus" in c.get("/erinnerung").get_data(as_text=True)


def test_zuruecknehmen_loescht_lieferdatum(c, uhr):
    zugang(c, "Salami", 2)
    a = bestellung(c, "Erik Probst", [{"produkt": "Salami", "menge": 1}])
    c.post(f"/bestellungen/{a}/ausgeliefert")
    c.post(f"/bestellungen/{a}/zuruecknehmen")
    uhr.t += timedelta(days=10)
    c.post("/erinnerung", data={"tage": "3", "uhrzeit": "18:00", "ziel": "x"})
    assert "Nichts überfällig" in c.get("/erinnerung").get_data(as_text=True)


def test_ungueltige_eingaben(c):
    assert "f=1" in c.post("/erinnerung", data={"tage": "drei", "uhrzeit": "18:00"}).headers["Location"]
    assert "f=1" in c.post("/erinnerung", data={"tage": "3", "uhrzeit": "25:00"}).headers["Location"]
