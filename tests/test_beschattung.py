import importlib
import sys
from pathlib import Path

import pytest

APP = Path(__file__).parents[1] / "beschattung" / "app"


@pytest.fixture
def mod():
    # Beide Add-ons haben ein web.py: das der Beschattung sauber laden.
    for name in ("web", "ha", "raeume"):
        sys.modules.pop(name, None)
    sys.path.insert(0, str(APP))
    try:
        yield importlib.import_module("web"), importlib.import_module("raeume")
    finally:
        sys.path.remove(str(APP))
        for name in ("web", "ha", "raeume"):
            sys.modules.pop(name, None)


class FalschesHA:
    def __init__(self):
        self.aufrufe = []
        self.z = {
            "cover.raffstore_kuche_venetian_blinds_2": {"entity_id": "cover.raffstore_kuche_venetian_blinds_2", "state": "open",
                                                        "attributes": {"current_position": 60, "current_tilt_position": 50}},
            "cover.rollladen_bad": {"entity_id": "cover.rollladen_bad", "state": "closed", "attributes": {"current_position": 0}},
            "cover.rollladen_gz": {"entity_id": "cover.rollladen_gz", "state": "opening", "attributes": {"current_position": 30}},
        }

    def zustaende(self, ids):
        return {k: v for k, v in self.z.items() if k in ids}

    def dienst(self, dienst, ids, wert=None):
        self.aufrufe.append((dienst, list(ids), wert))


@pytest.fixture
def app(mod):
    web, raeume = mod
    ha = FalschesHA()
    a = web.erstelle_app(raeume.pruefen(raeume.STANDARD), ha)
    return a.test_client(), ha


def test_uebersicht_zeigt_raeume_und_zahlen(app):
    c, _ = app
    t = c.get("/").get_data(as_text=True)
    assert "Wohnzimmer groß" in t and "Gästezimmer" in t
    assert 'id="zahl-offen">1<' in t and 'id="zahl-faehrt">1<' in t
    assert "Teilweise offen · Lamellen 50\u00a0%" in t
    assert "Nicht erreichbar" in t  # Rollos ohne Zustand


def test_raumseite_nur_raffstores_mit_lamellen(app):
    c, _ = app
    t = c.get("/raum/bad").get_data(as_text=True)
    assert t.count('data-regler="set_cover_tilt_position"') == 2
    assert c.get("/raum/gibtsnicht").status_code == 404


def test_aktionen(app):
    c, ha = app
    assert c.post("/api/aktion", json={"ziel": "raum:bad", "dienst": "close_cover"}).get_json()["ok"]
    assert ha.aufrufe[-1] == ("close_cover", ["cover.raffstore_bad_ost_venetian_blinds_4",
                                              "cover.raffstore_bad_sud_venetian_blinds", "cover.rollladen_bad"], None)
    c.post("/api/aktion", json={"ziel": "raum:bad", "dienst": "set_cover_tilt_position", "wert": 50})
    assert "cover.rollladen_bad" not in ha.aufrufe[-1][1]
    c.post("/api/aktion", json={"ziel": "cover.rollladen_gz", "dienst": "set_cover_position", "wert": 42.4})
    assert ha.aufrufe[-1] == ("set_cover_position", ["cover.rollladen_gz"], 42)


@pytest.mark.parametrize("daten", [
    {"ziel": "cover.fremd", "dienst": "open_cover"},
    {"ziel": "alle", "dienst": "toggle"},
    {"ziel": "cover.rollladen_gz", "dienst": "set_cover_position", "wert": 140},
    {"ziel": "cover.rollladen_gz", "dienst": "set_cover_tilt_position", "wert": 50},
])
def test_ungueltige_aktionen(app, daten):
    c, ha = app
    assert c.post("/api/aktion", json=daten).status_code == 400
    assert not ha.aufrufe


def test_fremde_webseite_darf_nicht_steuern(app):
    c, ha = app
    r = c.post("/api/aktion", json={"ziel": "alle", "dienst": "open_cover"}, headers={"Origin": "http://boese.example"})
    assert r.status_code == 403 and not ha.aufrufe


def test_eigene_datei_und_fehler(mod, tmp_path):
    _, raeume = mod
    p = tmp_path / "b.yaml"
    p.write_text("- name: Büro\n  rollos:\n    - entity: cover.rollladen_buro\n      typ: roll\n", encoding="utf-8")
    r, hinweis = raeume.laden(str(p))
    assert r[0]["schluessel"] == "buero" and hinweis is None
    p.write_text("- name: Büro\n  rollos:\n    - entity: licht.falsch\n", encoding="utf-8")
    r, hinweis = raeume.laden(str(p))
    assert "Fehler" in hinweis and len(r) == 4
