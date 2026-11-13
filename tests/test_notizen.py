import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from test_korrekturen import bestellung, frei  # noqa: E402
from test_verkauf import api, c, uhr, zugang  # noqa: F401,E402


def test_notiz_mit_und_ohne_kunde(c):
    kid = api(c, "kunde_anlegen", name="Max Bauer")["kunde_id"]
    r = c.post("/notizen/neu", data={"text": "Wenn Schwein da ist: ein ganzes", "kunde": str(kid)})
    assert "f=1" not in r.headers["Location"]
    c.post("/notizen/neu", data={"text": "Neue Vakuumbeutel bestellen", "kunde": ""})
    assert "f=1" in c.post("/notizen/neu", data={"text": "  "}).headers["Location"]
    html = c.get("/notizen").get_data(as_text=True)
    assert "Wenn Schwein da ist: ein ganzes" in html and "Max Bauer" in html and "Vakuumbeutel" in html
    assert f"/bestellungen/neu?kunde={kid}" in html
    # Auf Heute, beim Kunden und als Zahl bei den Bestellungen
    assert "Wenn Schwein da ist" in c.get("/").get_data(as_text=True)
    assert "Wenn Schwein da ist" in c.get(f"/kunden/{kid}").get_data(as_text=True)
    assert "Vakuumbeutel" not in c.get(f"/kunden/{kid}").get_data(as_text=True)
    assert "Notizen (2)" in c.get("/bestellungen").get_data(as_text=True)
    # Keine Bestellung, keine Reservierung
    assert api(c, "bestellungen", filter="alle")["anzahl"] == 0


def test_notiz_neuer_kunde_und_erledigen(c):
    c.post("/notizen/neu", data={"text": "Halbes Reh", "kunde": "neu", "neuer_kunde": "Lena"})
    n = api(c, "notizen")["notizen"]
    assert n[0]["kunde"] == "Lena" and n[0]["text"] == "Halbes Reh"
    r = c.post(f"/notizen/{n[0]['notiz_id']}/erledigt", data={"zurueck": "heute"})
    assert r.headers["Location"].split("?")[0].endswith("/")
    assert api(c, "notizen")["notizen"] == []
    html = c.get("/notizen").get_data(as_text=True)
    assert "<s class=\"leise\">Halbes Reh</s>" in html and "Halbes Reh" not in c.get("/").get_data(as_text=True)
    c.post(f"/notizen/{n[0]['notiz_id']}/loeschen")
    assert "Halbes Reh" not in c.get("/notizen").get_data(as_text=True)


def test_notiz_ueber_claude(c):
    api(c, "kunde_anlegen", name="Jonas Probe")
    a = api(c, "notiz", text="Ein ganzes Schwein, wenn da", kunde="Jonas Probe")
    assert a["ok"] and a["notiz"]["kunde"] == "Jonas Probe"
    assert api(c, "notiz", text="Ohne Kunde")["ok"]
    assert api(c, "notiz", text="x", kunde="Jona")["fehler"] == "kunde_unklar"
    assert api(c, "notiz", text="")["fehler"] == "text_fehlt"
    assert api(c, "notiz_erledigt", notiz_id=f"#{a['notiz']['notiz_id']}")["notiz"]["erledigt"]
    assert [n["text"] for n in api(c, "notizen")["notizen"]] == ["Ohne Kunde"]


def test_zusammenfuehren_nimmt_notizen_mit(c):
    a = api(c, "kunde_anlegen", name="Karl Beispiel")["kunde_id"]
    b = api(c, "kunde_anlegen", name="Karl B.")["kunde_id"]
    api(c, "notiz", text="Keule", kunde_id=a)
    c.post(f"/kunden/{a}/zusammenfuehren", data={"nach": str(b)})
    assert api(c, "notizen")["notizen"][0]["kunde"] == "Karl B."


def test_notizen_unter_ingress(c):
    pfad = "/api/hassio_ingress/abc"
    api(c, "notiz", text="Test")
    html = c.get("/notizen", headers={"X-Ingress-Path": pfad}).get_data(as_text=True)
    assert f'action="{pfad}/notizen/neu"' in html and f'action="{pfad}/notizen/1/erledigt"' in html


def test_startseite_reihenfolge(c):
    zugang(c, "Salami", 3)
    bestellung(c, "Erik Probst", [{"produkt": "Salami", "menge": 2}])
    api(c, "notiz", text="Ein ganzes Schwein")
    html = c.get("/").get_data(as_text=True)
    # Standard: Notizen ganz unten
    assert html.index("<h2>Zu liefern</h2>") < html.index("Neue Bestellung</a>") < html.index("<h2>Notizen</h2>")
    for _ in range(5):
        c.post("/heute/anpassen", data={"baustein": "notizen", "tun": "hoch"})
    html = c.get("/").get_data(as_text=True)
    assert html.index("<h2>Notizen</h2>") < html.index("<h2>Zu liefern</h2>")
    c.post("/heute/anpassen", data={"baustein": "zuliefern", "tun": "umschalten"})
    html = c.get("/").get_data(as_text=True)
    assert "<h2>Zu liefern</h2>" not in html and "<h2>Notizen</h2>" in html
    seite = c.get("/heute/anpassen").get_data(as_text=True)
    assert "line-through" in seite and 'class="an"' in seite
    c.post("/heute/anpassen", data={"tun": "zuruecksetzen"})
    html = c.get("/").get_data(as_text=True)
    assert html.index("<h2>Zu liefern</h2>") < html.index("<h2>Notizen</h2>")
    assert c.post("/heute/anpassen", data={"baustein": "quatsch", "tun": "hoch"}).status_code == 303


def test_bestellliste_zeigt_positionen(c):
    zugang(c, "Salami", 3)
    zugang(c, "Knacker", 1)
    c.post("/api/wildart", json={"art": "Reh"})
    t = c.post("/api/anlegen", json={"teil": "Rücken"}).get_json()
    c.post(f"/api/gedruckt/{int(t['nummer'])}")
    bestellung(c, "Erik Probst", [{"produkt": "Salami", "menge": 2}, {"produkt": "Knacker", "menge": 1},
                                  {"wildart": "Reh", "teil": "Rücken", "menge": 1}])
    html = c.get("/bestellungen").get_data(as_text=True)
    assert '<span class="posten">2× Salami, 1× Knacker, Reh Rücken</span>' in html


def test_knopf_neue_bestellung_verschiebbar(c):
    html = c.get("/").get_data(as_text=True)
    assert html.count("Neue Bestellung</a>") == 1
    for _ in range(8):
        c.post("/heute/anpassen", data={"baustein": "neu", "tun": "hoch"})
    html = c.get("/").get_data(as_text=True)
    assert html.index("Neue Bestellung</a>") < html.index("<h2>Zu liefern</h2>")
    c.post("/heute/anpassen", data={"baustein": "neu", "tun": "umschalten"})
    assert "Neue Bestellung</a>" not in c.get("/").get_data(as_text=True)
