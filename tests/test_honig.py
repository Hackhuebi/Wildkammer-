import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from test_korrekturen import bestellung, frei  # noqa: E402
from test_verkauf import api, c, uhr, zugang  # noqa: F401,E402


def test_honig_ist_da_und_wird_gefunden(c):
    b = api(c, "bestand")
    honig = [w for w in b["wurst"] if w["art"] == "Honig"]
    assert [h["produkt"] for h in honig] == ["Lindenhonig", "Rapshonig"]
    assert all(h["einheit"] == "Glas 500 g" for h in honig)
    for wort, ziel in [("Rapshonig", "Rapshonig"), ("raps", "Rapshonig"), ("Raps Honig", "Rapshonig"),
                       ("Linde", "Lindenhonig"), ("lindenhonig", "Lindenhonig")]:
        assert zugang(c, wort, 1)["produkt"] == ziel, wort
    assert api(c, "wurst_zugang", produkt="Honig", menge=1)["fehler"] == "produkt_unklar"


def test_honig_bestellen_und_lager(c):
    zugang(c, "Rapshonig", 10)
    zugang(c, "Salami", 2)
    api(c, "wurst_preis", produkt="Rapshonig", preis="6,50")
    oid = bestellung(c, "Anna", [{"produkt": "Raps", "menge": 3}, {"produkt": "Salami", "menge": 1}])
    b = api(c, "bestellungen", kunde="Anna")["bestellungen"][0]
    assert "3 × Rapshonig" in b["positionen"] and b["summe"] == "35,50 €"
    assert frei(c, "Rapshonig")["frei"] == 7
    html = c.get("/wurst").get_data(as_text=True)
    assert "<h1>Lager</h1>" in html
    assert html.index('<tr class="gruppe"><th>Wurst</th>') < html.index('<tr class="gruppe"><th>Honig</th>')
    assert "Summe Honig" in html and "65,00 €" in html
    assert ">Lager</a>" in html
    assert oid


def test_alte_datenbank_bekommt_honig_einmal(tmp_path, uhr):
    import sqlite3
    from web import erstelle_app
    pfad = tmp_path / "alt.db"
    erstelle_app(pfad, uhr)
    v = sqlite3.connect(pfad)
    # Zustand vor dem Update nachbauen: keine Spalte, kein Honig
    v.execute("DELETE FROM wurstprodukte WHERE kategorie = 'honig'")
    v.execute("ALTER TABLE wurstprodukte DROP COLUMN kategorie")
    v.commit(); v.close()
    c = erstelle_app(pfad, uhr).test_client()
    assert len([w for w in api(c, "bestand")["wurst"] if w["art"] == "Honig"]) == 2
    # Gelöschter Honig kommt beim nächsten Start nicht wieder
    pid = re.search(r'href="[^"]*/wurst/(\d+)">Rapshonig', c.get("/wurst").get_data(as_text=True)).group(1)
    c.post(f"/wurst/{pid}/aendern", data={"name": "Rapshonig", "einheit": "Glas 500 g", "preis": "0", "aktiv": "0", "kategorie": "honig"})
    c = erstelle_app(pfad, uhr).test_client()
    assert [w["produkt"] for w in api(c, "bestand")["wurst"] if w["art"] == "Honig"] == ["Lindenhonig"]


def test_neues_produkt_mit_art(c):
    c.post("/wurst/neu", data={"kategorie": "honig", "name": "Waldhonig", "einheit": "Glas 500 g", "preis": "7"})
    assert [w for w in api(c, "bestand")["wurst"] if w["produkt"] == "Waldhonig"][0]["art"] == "Honig"
