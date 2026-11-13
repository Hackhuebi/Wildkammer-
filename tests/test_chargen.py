import re
import sys
from datetime import timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from test_korrekturen import bestellung, frei  # noqa: E402
from test_verkauf import api, c, uhr, zugang  # noqa: F401,E402


def _ch(c, name):
    return {x["charge"]: x for x in api(c, "chargen", produkt=name)["chargen"]}


def test_fifo_umsatz_rabatt_und_gewinn(c, uhr):
    zugang(c, "Salami", 3)                         # Startcharge, 16 € je Stück
    uhr.t += timedelta(minutes=1)
    neu = api(c, "charge_neu", produkt="Salami", kosten="40")
    assert neu["ok"] and neu["charge"]["name"].startswith("Salami ") and neu["charge"]["kosten"] == "40,00 €"
    uhr.t += timedelta(minutes=1)
    zugang(c, "Salami", 4)                         # gehört zur neuen Charge
    assert frei(c, "Salami")["frei"] == 7          # Lager bleibt eine Zahl
    a = bestellung(c, "Erik Probst", [{"produkt": "Salami", "menge": 5}])  # 80 €
    c.post(f"/bestellungen/{a}/ausgeliefert")
    c.post(f"/bestellungen/{a}/erhalten", data={"betrag": "70", "art": "fertig"})  # 10 € Rabatt
    ch = _ch(c, "Salami")
    start, zweite = ch["Salami Start"], ch[neu["charge"]["name"]]
    assert (start["eingebucht"], start["verkauft"], start["uebrig"]) == (3, 3, 0)
    assert (zweite["eingebucht"], zweite["verkauft"], zweite["uebrig"]) == (4, 2, 2)
    assert start["umsatz"] == "42,00 €" and start["rabatte"] == "6,00 €" and start["gewinn"] == ""
    assert zweite["umsatz"] == "28,00 €" and zweite["rabatte"] == "4,00 €" and zweite["gewinn"] == "-12,00 €"
    # Eigenverbrauch zählt ohne Umsatz
    api(c, "wurst_entnahme", produkt="Salami", menge=1, grund="Eigenverbrauch")
    assert _ch(c, "Salami")[neu["charge"]["name"]]["entnommen"] == 1


def test_lieferung_zuruecknehmen_gibt_charge_zurueck(c, uhr):
    zugang(c, "Salami", 2)
    a = bestellung(c, "Greta", [{"produkt": "Salami", "menge": 2}])
    c.post(f"/bestellungen/{a}/ausgeliefert")
    assert _ch(c, "Salami")["Salami Start"]["verkauft"] == 2
    c.post(f"/bestellungen/{a}/zuruecknehmen")
    s = _ch(c, "Salami")["Salami Start"]
    assert (s["verkauft"], s["uebrig"], s["umsatz"]) == (0, 2, "0,00 €")


def test_chargen_seite_und_auswertung(c, uhr):
    zugang(c, "Rapshonig", 10)
    html = c.get("/wurst").get_data(as_text=True)
    pid = re.search(r'href="[^"]*/wurst/(\d+)">Rapshonig', html).group(1)
    r = c.post(f"/wurst/{pid}/charge", data={"name": "Raps Frühjahr 2027", "kosten": "25,50"})
    assert "f=1" not in r.headers["Location"]
    seite = c.get(f"/wurst/{pid}").get_data(as_text=True)
    assert "Raps Frühjahr 2027" in seite and "Rapshonig Start" in seite and 'value="25,50"' in seite
    cid = re.search(r'/wurst/\d+/charge/(\d+)"[^>]*>\s*<label>Name<input name="name" value="Raps Frühjahr 2027"', seite)
    assert cid
    c.post(f"/wurst/{pid}/charge/{cid.group(1)}", data={"name": "Raps 2027", "kosten": "30"})
    assert "Raps 2027" in c.get(f"/wurst/{pid}").get_data(as_text=True)
    r = c.get("/auswertung?produkt=honig")
    html = r.get_data(as_text=True)
    assert r.status_code == 200, html[-600:]
    import re as _re
    assert "<h2>Nach Charge</h2>" in html, _re.findall(r'<h2>[^<]*</h2>|class="meldung[^"]*">[^<]*', html) and "Raps 2027" in html and "Rapshonig Start" in html
    assert "Salami Start" not in html
    # Doppelter Name bekommt eine Nummer
    c.post(f"/wurst/{pid}/charge", data={"name": "Raps 2027"})
    assert "Raps 2027 (2)" in c.get(f"/wurst/{pid}").get_data(as_text=True)
