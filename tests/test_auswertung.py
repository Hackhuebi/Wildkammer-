import sys
from datetime import timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from test_korrekturen import bestellung  # noqa: E402
from test_verkauf import api, c, uhr, zugang  # noqa: F401,E402


def test_umsatz_einnahmen_zeitraum_und_produkt(c, uhr):
    zugang(c, "Salami", 10)      # 16 €
    zugang(c, "Rapshonig", 10)
    api(c, "wurst_preis", produkt="Rapshonig", preis="6")
    start = uhr.t.date()
    a = bestellung(c, "Erik Probst", [{"produkt": "Salami", "menge": 2}, {"produkt": "Raps", "menge": 1}])  # 38 €
    c.post(f"/bestellungen/{a}/erhalten", data={"betrag": "35", "art": "fertig"})  # 3 € Rabatt
    uhr.t += timedelta(days=40)
    b = bestellung(c, "Greta", [{"produkt": "Raps", "menge": 3}])  # 18 €
    c.post(f"/bestellungen/{b}/erhalten", data={"betrag": "10", "art": "teil"})
    ende = uhr.t.date()
    vk = c.application.config["VERKAUF"]
    alles = vk.auswertung(start.isoformat(), ende.isoformat())
    assert alles["umsatz_cent"] == 3500 + 1800 and alles["einnahmen_cent"] == 3500 + 1000
    assert alles["rabatt_cent"] == 300 and alles["brutto_cent"] == 3800 + 1800 and alles["bestellungen"] == 2
    assert [(r["name"], r["menge"], r["cent"]) for r in alles["zeilen"]] == [("Salami", 2, 3200), ("Rapshonig", 4, 2400)]
    assert len(alles["monate"]) == 2
    # Nur der erste Monat
    erster = vk.auswertung(start.isoformat(), (start + timedelta(days=10)).isoformat())
    assert erster["umsatz_cent"] == 3500 and erster["einnahmen_cent"] == 3500
    # Produktfilter
    honig = vk.auswertung(start.isoformat(), ende.isoformat(), "honig")
    assert honig["umsatz_cent"] == 2400 and honig["bestellungen"] == 2 and [r["name"] for r in honig["zeilen"]] == ["Rapshonig"]
    pid = [p["id"] for p in vk.produkte() if p["name"] == "Salami"][0]
    salami = vk.auswertung(start.isoformat(), ende.isoformat(), f"p:{pid}")
    assert salami["umsatz_cent"] == 3200 and salami["bestellungen"] == 1
    # Seite
    html = c.get(f"/auswertung?von={start}&bis={ende}&produkt=honig").get_data(as_text=True)
    assert "24,00 €" in html and "vor Rabatt" in html and "Einnahmen (Zahlungen)" not in html
    html = c.get(f"/auswertung?von={start}&bis={ende}").get_data(as_text=True)
    assert "53,00 €" in html and "45,00 €" in html and "Nach Monat" in html
    assert "f=1" in c.get("/auswertung?von=gestern&bis=heute").headers["Location"]
    assert c.get("/auswertung").status_code == 200


def test_stornierte_zaehlen_nicht(c):
    zugang(c, "Salami", 2)
    a = bestellung(c, "Ben", [{"produkt": "Salami", "menge": 1}])
    c.post(f"/bestellungen/{a}/storno")
    assert "Keine Verkäufe" in c.get("/auswertung").get_data(as_text=True)


def test_neue_bestellung_neuer_kunde_vorausgewaehlt(c):
    zugang(c, "Salami", 2)
    api(c, "kunde_anlegen", name="Greta")
    html = c.get("/bestellungen/neu").get_data(as_text=True)
    assert '<option value="neu" selected>' in html
    kid = api(c, "kunde_anlegen", name="Ben")["kunde_id"]
    html = c.get(f"/bestellungen/neu?kunde={kid}").get_data(as_text=True)
    assert '<option value="neu" >' in html and f'<option value="{kid}" selected>' in html
