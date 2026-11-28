import importlib
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "wildkammer" / "app"))
from test_verkauf import api, c, uhr  # noqa: F401,E402


def test_teilstueck_anlegen_und_loeschen(c):
    r = c.post("/teilstuecke", data={"name": "  haxe ", "varianten": "Hachse, Haxen, haxe"})
    assert "f=1" not in r.headers["Location"]
    html = c.get("/teilstuecke").get_data(as_text=True)
    assert "<b>Haxe</b>" in html and "auch: hachse, haxen" in html and "Oberschale" in html
    for name in ("Keule", "keule", "haxe", "Ha(xe)", "x" * 40, ""):
        assert "f=1" in c.post("/teilstuecke", data={"name": name}).headers["Location"], name
    vk = c.application.config["VERKAUF"]
    d = yaml.safe_load(vk.teile_paket())
    a = d["wildkammer_teile"]["automation"][0]
    assert [t["id"] for t in a["triggers"]] == ["Haxe", "Haxe#menge", "Haxe#drucke"]
    assert "(drucke|druck) [ein] [etikett] [für] (haxe|hachse|haxen) {gewicht}" in a["triggers"][0]["command"]
    assert a["actions"][2]["action"] == "script.wild_sprache_etikett"
    tid = vk.teilstuecke()[0]["id"]
    c.post("/teilstuecke", data={"loeschen": str(tid)})
    assert yaml.safe_load(vk.teile_paket()) == {"wildkammer_teile": {"automation": []}}
    # Mit eigenem Teilstück kann die Wildkammer Tüten anlegen
    c.post("/api/wildart", json={"art": "Reh"})
    assert c.post("/api/anlegen", json={"teil": "Haxe"}).get_json()["teil"] == "Haxe"


def test_eingespielt_wird_nur_die_erzeugte_datei(tmp_path, monkeypatch):
    ha = tmp_path / "homeassistant"
    (ha / "packages").mkdir(parents=True)
    (ha / "packages" / "wildetikett.yaml").write_text("bleibt\n")
    monkeypatch.setenv("WILDKAMMER_PAKETE", str(tmp_path / "gibtsnicht"))
    monkeypatch.setenv("WILDKAMMER_HA_PAKETE", str(ha / "packages"))
    monkeypatch.setenv("WILDKAMMER_HA_SICHERUNG", str(ha / "sicherung"))
    import einspielen
    e = importlib.reload(einspielen)
    aufrufe = []
    ha_api = lambda pfad, daten=None: aufrufe.append(pfad) or {"result": "valid"}
    assert e.einspielen(ha_api, lambda *a: None, erzeugt={"wildkammer_teile.yaml": "x: 1\n"}, nur_erzeugt=True) == "neu"
    assert (ha / "packages" / "wildkammer_teile.yaml").read_text() == "x: 1\n"
    assert (ha / "packages" / "wildetikett.yaml").read_text() == "bleibt\n"
    assert aufrufe[-1] == "/services/homeassistant/reload_all"
    assert e.einspielen(ha_api, lambda *a: None, erzeugt={"wildkammer_teile.yaml": "x: 1\n"}, nur_erzeugt=True) == "gleich"


def test_etikett_von_hand(c):
    gedruckt = []
    c.application.config["DRUCKEN"] = lambda e: gedruckt.append(e) or True
    html = c.get("/etikett").get_data(as_text=True)
    assert "Oberschale" in html and 'type="date"' in html
    r = c.post("/etikett", data={"art": "Reh", "teil": "Keule ausgelöst", "datum": "2025-10-03",
                                 "gramm": "900", "anzahl": "2"})
    assert "2+Etiketten" in r.headers["Location"]
    assert [e["datum"] for e in gedruckt] == ["03.10.2025", "03.10.2025"]
    assert gedruckt[0]["teil"] == "Keule ausgelöst" and gedruckt[0]["gewicht_text"] == "900 g"
    # Aktive Wildart der Sprachsteuerung bleibt unberührt
    assert c.get("/api/status").get_json()["art"] == ""
    # Zukunftsdatum abgelehnt
    assert c.post("/etikett", data={"art": "Reh", "teil": "Keule", "datum": "2099-01-01"}).status_code == 200
    # Druckfehler: Rest bleibt als Entwurf, nichts weiter angelegt
    c.application.config["DRUCKEN"] = lambda e: False
    c.post("/etikett", data={"art": "Damwild", "teil": "Hack", "datum": "2025-01-01", "anzahl": "3"})
    html = c.get("/fleisch").get_data(as_text=True)
    assert html.count("Damwild – Hack") == 1 and "Nicht eingebucht" in html
    # Nochmal drucken bucht den Entwurf ein
    c.application.config["DRUCKEN"] = lambda e: True
    nummer = int(gedruckt[-1]["nummer"]) + 1
    assert "eingebucht" in c.post(f"/s/{nummer}/drucken").headers["Location"]


def test_stueckzahl_schnitzel(c):
    c.post("/teilstuecke", data={"name": "Schnitzel"})
    vk = c.application.config["VERKAUF"]
    tid = vk.teilstuecke()[0]["id"]
    ids = lambda: [t["id"] for t in yaml.safe_load(vk.teile_paket())["wildkammer_teile"]["automation"][0]["triggers"]]
    assert "Schnitzel#menge" in ids()
    c.post("/teilstuecke", data={"zaehlbar_id": str(tid), "an": "1"})
    assert ids() == ["Schnitzel", "Schnitzel#stueck", "Schnitzel#drucke"]
    a = yaml.safe_load(vk.teile_paket())["wildkammer_teile"]["automation"][0]
    assert "#stueck" in a["actions"][2]["data"]["stueckzahl"]
    # Sprachweg: Add-on bekommt stueckzahl und liefert das Etikett „4x Schnitzel“
    c.post("/api/wildart", json={"art": "Reh"})
    e = c.post("/api/anlegen", json={"teil": "Schnitzel", "gewicht_g": 0, "stueckzahl": 4}).get_json()
    assert e["teil"] == "Schnitzel" and e["teil_etikett"] == "4x Schnitzel"
    e = c.post("/api/anlegen", json={"teil": "Hack", "gewicht_g": 0, "stueckzahl": 0}).get_json()
    assert e["teil_etikett"] == "Hack"
    # Von Hand
    c.application.config["DRUCKEN"] = lambda e: e["teil_etikett"] == "5x Schnitzel"
    r = c.post("/etikett", data={"art": "Reh", "teil": "Schnitzel", "datum": "2025-12-01", "stueckzahl": "5"})
    assert "eingebucht" in r.headers["Location"]


def test_etikett_datum_und_preis(c):
    gedruckt = []
    c.application.config["DRUCKEN"] = lambda e: gedruckt.append(e) or True
    c.post("/etikett", data={"art": "Reh", "teil": "Keule", "datum_art": "monat", "monat": "2025-10"})
    assert gedruckt[-1]["datum"] == "10/2025"
    c.post("/etikett", data={"art": "Reh", "teil": "Keule", "datum_art": "keins"})
    assert gedruckt[-1]["datum"] == " " and gedruckt[-1]["preis_text"] == " "
    assert c.post("/etikett", data={"art": "Reh", "teil": "Keule", "datum_art": "monat", "monat": "2099-01"}).status_code == 200
    # Preis: braucht Gewicht und Kilopreis
    assert "Gewicht" in c.post("/etikett", data={"art": "Reh", "teil": "Keule", "preis": "1"}).get_data(as_text=True)
    assert "kein Kilopreis" in c.post("/etikett", data={"art": "Reh", "teil": "Keule", "gramm": "800", "preis": "1"}).get_data(as_text=True)
    c.application.config["VERKAUF"].fleischpreis_setzen("Reh", "Keule", "22,50")
    r = c.post("/etikett", data={"art": "Reh Bock", "teil": "Keule", "gramm": "800", "preis": "1"})
    assert r.status_code == 303 and gedruckt[-1]["preis_text"] == "18,00 €" and gedruckt[-1]["gewicht_text"] == "800 g"
    # Nachdruck behält Preis und Datumsform
    n = int(gedruckt[-1]["nummer"])
    c.post(f"/s/{n}/drucken")
    assert gedruckt[-1]["preis_text"] == "18,00 €"
    assert "Eingepackt 10/2025" in c.get(f"/s/{n - 2}").get_data(as_text=True)


def test_kilopreise_auswahl(c):
    c.post("/teilstuecke", data={"name": "Schnitzel"})
    html = c.get("/preise").get_data(as_text=True)
    assert "<option >Schnitzel</option>" in html.replace("<option  >", "<option >") or ">Schnitzel</option>" in html
    assert ">Oberschale</option>" in html and ">Schwarzwild</option>" in html
    c.post("/preise", data={"art": "Reh", "teil": "Schnitzel", "preis": "29,90"})
    html = c.get("/preise?art=Reh&teil=Schnitzel").get_data(as_text=True)
    assert 'value="29,90"' in html and "selected>Schnitzel" in html


def test_kilopreise_nur_grundarten(c):
    c.post("/api/wildart", json={"art": "Schwarzwild Frili"})
    n = int(c.post("/api/anlegen", json={"teil": "Keule"}).get_json()["nummer"])
    c.post(f"/api/gedruckt/{n}")
    c.application.config["VERKAUF"].fleischpreis_setzen("Schwarzwild Bache", "Keule", "15")
    html = c.get("/preise").get_data(as_text=True)
    assert "<td>Schwarzwild Bache</td>" in html.replace('">Schwarzwild Bache</a>', ">Schwarzwild Bache</td>").replace("<td><a href", "<td><a href") or "Schwarzwild Bache" in html
    html = c.get("/preise").get_data(as_text=True)
    assert ">Schwarzwild</option>" in html and "Frili</option>" not in html and "Muffelwild" not in html


def test_kilopreise_reihenfolge(c):
    vk = c.application.config["VERKAUF"]
    for art in ("Damwild", "Reh", "Schwarzwild", "Rotwild"):
        vk.fleischpreis_setzen(art, "Keule", "10")
    html = c.get("/preise").get_data(as_text=True)
    auswahl = html.split('name="art"')[1].split("</select>")[0]
    assert [auswahl.index(a) for a in (">Schwarzwild<", ">Reh<", ">Rotwild<", ">Damwild<")] == sorted(
        auswahl.index(a) for a in (">Schwarzwild<", ">Reh<", ">Rotwild<", ">Damwild<"))
    tabelle = html.split("<table>")[1]
    pos = [tabelle.index(f">{a}</a>") for a in ("Schwarzwild", "Reh", "Rotwild", "Damwild")]
    assert pos == sorted(pos)


def test_erneut_drucken_und_letzte(c):
    c.application.config["DRUCKEN"] = lambda e: False
    r = c.post("/etikett", data={"art": "Schwarzwild", "teil": "Keule", "datum_art": "monat", "monat": "2025-10",
                                 "gramm": "800", "anzahl": "3"})
    ziel = r.headers["Location"]
    assert "nicht=" in ziel and "rest=2" in ziel
    html = c.get(ziel).get_data(as_text=True)
    assert "Erneut drucken" in html and "Danach noch 2 offen" in html and 'value="800"' in html
    nummer = int(ziel.split("nicht=")[1].split("&")[0])
    c.application.config["DRUCKEN"] = lambda e: True
    r = c.post(f"/s/{nummer}/drucken", data={"zurueck": "etikett", "rest": "2"})
    html = c.get(r.headers["Location"]).get_data(as_text=True)
    assert "Noch 2 offen" in html and 'name="anzahl" type="number" inputmode="numeric" min="1" max="20" value="2"' in html
    # Zuletzt: gleiche Eingabe mit anderem Gewicht nur einmal, neueste oben
    c.post("/etikett", data={"art": "Schwarzwild", "teil": "Keule", "datum_art": "monat", "monat": "2025-10", "gramm": "650"})
    c.post("/etikett", data={"art": "Reh", "teil": "Rücken", "datum_art": "keins"})
    html = c.get("/etikett").get_data(as_text=True)
    zuletzt = html.split("Zuletzt")[1].split("<h2>Etikett")[0]
    assert zuletzt.count("Schwarzwild – Keule") == 1 and zuletzt.index("Reh – Rücken") < zuletzt.index("Schwarzwild")
    assert "650 g" in zuletzt and "10/2025" in zuletzt
    html = c.get("/etikett?v=1").get_data(as_text=True)
    assert 'value="650"' in html and 'value="2025-10"' in html and '<option value="monat" selected' in html
