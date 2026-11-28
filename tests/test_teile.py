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
