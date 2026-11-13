import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from test_korrekturen import bestellung, frei  # noqa: E402
from test_verkauf import api, c, tuete, uhr, zugang  # noqa: F401,E402


def test_packliste_auswahl_gesamt_und_ausliefern(c):
    zugang(c, "Salami", 5)
    zugang(c, "Knacker", 3)
    tuete(c, "Reh", "Keule", 900)
    a = bestellung(c, "Jonas Muster", [{"produkt": "Salami", "menge": 2}, {"produkt": "Knacker", "menge": 1}])
    b = bestellung(c, "Greta", [{"produkt": "Salami", "menge": 1}, {"wildart": "Reh", "teil": "Keule", "menge": 1}])
    d = bestellung(c, "Ben", [{"produkt": "Knacker", "menge": 2}])
    html = c.get("/packliste").get_data(as_text=True)
    for oid in (a, b, d):
        assert f'name="b" value="{oid}"' in html
    html = c.get(f"/packliste?b={a}&b={b}").get_data(as_text=True)
    assert "Gesamt für 2 Bestellungen" in html
    assert '<td class="umbruch">Salami</td><td class="zahl"><b>3</b>' in html
    assert '<td class="umbruch">Knacker</td><td class="zahl"><b>1</b>' in html
    assert "Reh Keule</td>" in html and "W-000001" in html and "Ben" not in html
    assert "kassieren" in html
    r = c.get(f"/packliste.ics?b={a}&b={b}&datum=2026-11-12&zeit=17:30&dauer=90")
    assert r.mimetype == "text/calendar" and "charset=utf-8" in r.headers["Content-Type"] and "attachment" in r.headers["Content-Disposition"]
    text = r.get_data(as_text=True)
    assert "DTSTART:20261112T173000" in text and "DTEND:20261112T190000" in text
    assert all(len(z.encode()) <= 75 for z in text.split("\r\n"))
    entfaltet = text.replace("\r\n ", "")
    assert "3 × Salami" in entfaltet and "Jonas Muster (#" in entfaltet and "Greta" in entfaltet
    assert c.get(f"/packliste.ics?b={a}&datum=morgen&zeit=17:00").status_code == 400
    r = c.post("/packliste/ausliefern", data={"b": [str(a), str(b)]})
    assert "2+Bestellungen+ausgeliefert" in r.headers["Location"] and "f=1" not in r.headers["Location"]
    assert frei(c, "Salami")["frei"] == 2 and frei(c, "Knacker")["reserviert"] == 2
    # Gelieferte erscheinen nicht mehr in der Auswahl.
    html = c.get("/packliste").get_data(as_text=True)
    assert f'value="{a}"' not in html and f'value="{d}"' in html


def test_packliste_unter_ingress(c):
    zugang(c, "Salami", 1)
    a = bestellung(c, "Finn", [{"produkt": "Salami", "menge": 1}])
    pfad = "/api/hassio_ingress/abc"
    html = c.get(f"/packliste?b={a}", headers={"X-Ingress-Path": pfad}).get_data(as_text=True)
    assert f'action="{pfad}/packliste.ics"' in html and f'action="{pfad}/packliste/ausliefern"' in html
    assert f'href="{pfad}/packliste?neu=1"' in html


def test_abgeschlossen_filter(c):
    zugang(c, "Salami", 3)
    a = bestellung(c, "Anna", [{"produkt": "Salami", "menge": 1}])
    b = bestellung(c, "Bert", [{"produkt": "Salami", "menge": 1}])
    c.post(f"/bestellungen/{a}/ausgeliefert")
    c.post(f"/bestellungen/{a}/bezahlt")
    c.post(f"/bestellungen/{b}/ausgeliefert")  # geliefert, aber nicht bezahlt
    html = c.get("/bestellungen?filter=abgeschlossen").get_data(as_text=True)
    assert "Anna" in html and "Bert" not in html and "Abgeschlossen" in html
    assert api(c, "bestellungen", filter="abgeschlossen")["anzahl"] == 1


def test_lagerwert(c):
    zugang(c, "Salami", 3)  # 16 €
    zugang(c, "Bratwurst", 2)  # 7 €
    bestellung(c, "Anna", [{"produkt": "Salami", "menge": 1}])
    html = c.get("/wurst").get_data(as_text=True)
    assert "Wert <b>48,00 €</b>" in html
    assert "<strong>5</strong>" in html and "<strong>62,00 €</strong>" in html
    assert "davon bestellt</td><td class=\"zahl leise\">16,00 €" in html
    assert "davon frei</td><td class=\"zahl leise\">46,00 €" in html


def test_nicht_eingebuchte_tueten(c):
    c.post("/api/wildart", json={"art": "Reh"})
    c.post("/api/anlegen", json={"teil": "Oberschale"})
    c.post("/api/anlegen", json={"teil": "Hack"})
    html = c.get("/fleisch").get_data(as_text=True)
    assert "Nicht eingebucht" in html and "Reh – Oberschale" in html and "Reh – Hack" in html
    r = c.post("/s/1/einbuchen", data={"zurueck": "liste"})
    assert r.headers["Location"].split("?")[0].endswith("/fleisch")
    c.post("/s/2/verwerfen")
    html = c.get("/fleisch").get_data(as_text=True)
    assert "Nicht eingebucht" not in html
    assert c.get("/api/bestand?teil=Oberschale").get_json()["anzahl"] == 1
    assert c.get("/s/2").status_code == 404
    c.post("/s/1/verwerfen")  # Eingebuchte Tüten lassen sich so nicht löschen
    assert c.get("/api/bestand?teil=Oberschale").get_json()["anzahl"] == 1


def test_packliste_text_zum_kopieren(c):
    zugang(c, "Salami", 2)
    a = bestellung(c, "Erik Probst", [{"produkt": "Salami", "menge": 2}])
    html = c.get(f"/packliste?b={a}").get_data(as_text=True)
    assert 'id="packtext"' in html and "GESAMT\n2 × Salami" in html and "Erik Probst (#" in html


def test_heute_startseite(c):
    zugang(c, "Salami", 10)
    zugang(c, "Knacker", 2)
    a = bestellung(c, "Erik Probst", [{"produkt": "Salami", "menge": 2}])
    c.post("/api/wildart", json={"art": "Reh"})
    c.post("/api/anlegen", json={"teil": "Hack"})  # Entwurf, nie bestätigt
    html = c.get("/").get_data(as_text=True)
    assert "<h1>Heute</h1>" in html and 'class="an"' in html
    assert "nicht eingebucht" in html
    assert "Wird knapp" in html and "Knacker (2 frei)" in html and "Salami (" not in html
    assert "Erik Probst" in html and f"#{a}" in html and "2 × Salami" in html
    assert "Packliste erstellen" in html and "Noch zu kassieren" in html
    assert "über 1 Jahr" not in html


def test_alte_tueten(c, uhr):
    from datetime import timedelta
    c.post("/api/wildart", json={"art": "Schwarzwild"})
    t = c.post("/api/anlegen", json={"teil": "Keule"}).get_json()
    c.post(f"/api/gedruckt/{int(t['nummer'])}")
    uhr.t += timedelta(days=400)
    html = c.get("/").get_data(as_text=True)
    assert "über 1 Jahr im Frost" in html and "Schwarzwild Keule" in html
    assert "über 1 Jahr</span>" in c.get("/fleisch").get_data(as_text=True)


def test_gespeicherte_packliste_auf_heute(c):
    zugang(c, "Salami", 5)
    a = bestellung(c, "Erik Probst", [{"produkt": "Salami", "menge": 2}])
    b = bestellung(c, "Greta", [{"produkt": "Salami", "menge": 1}])
    d = bestellung(c, "Ben", [{"produkt": "Salami", "menge": 1}])
    assert "Packliste erstellen" in c.get("/").get_data(as_text=True)
    r = c.post("/packliste/speichern", data={"b": [str(a), str(b)]})
    assert r.headers["Location"].split("?")[0].endswith("/packliste")
    # Ohne Parameter zeigt die Packliste die gespeicherte Auswahl
    html = c.get("/packliste").get_data(as_text=True)
    assert "Gesamt für 2 Bestellungen" in html and "Packliste löschen" in html
    html = c.get("/").get_data(as_text=True)
    assert "<h2>Packliste</h2>" in html and "Für Erik Probst, Greta" in html and "Packliste erstellen" not in html
    assert '<td class="umbruch">Salami</td><td class="r"><b>3</b>' in html
    # Auswahl ändern zeigt die gespeicherten Häkchen
    html = c.get("/packliste?neu=1").get_data(as_text=True)
    assert f'value="{a}" checked' in html and f'value="{d}" >' in html
    # Geliefert fällt heraus, zuletzt verschwindet die Liste ganz
    c.post(f"/bestellungen/{a}/ausgeliefert")
    assert "Für Greta ·" in c.get("/").get_data(as_text=True)
    c.post(f"/bestellungen/{b}/storno")
    html = c.get("/").get_data(as_text=True)
    assert "<h2>Packliste</h2>" not in html and "Packliste erstellen" in html
    assert c.post("/packliste/speichern", data={}).headers["Location"].find("f=1") > 0


def test_packliste_loeschen(c):
    zugang(c, "Salami", 1)
    a = bestellung(c, "Finn", [{"produkt": "Salami", "menge": 1}])
    c.post("/packliste/speichern", data={"b": str(a)})
    c.post("/packliste/leeren")
    assert "<h2>Packliste</h2>" not in c.get("/").get_data(as_text=True)
