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
