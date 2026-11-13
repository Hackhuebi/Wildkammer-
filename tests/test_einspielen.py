import importlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "wildkammer" / "app"))


def _laden(tmp_path, monkeypatch):
    quelle, ha = tmp_path / "pakete", tmp_path / "homeassistant"
    quelle.mkdir(); (ha / "packages").mkdir(parents=True)
    monkeypatch.setenv("WILDKAMMER_PAKETE", str(quelle))
    monkeypatch.setenv("WILDKAMMER_HA_PAKETE", str(ha / "packages"))
    monkeypatch.setenv("WILDKAMMER_HA_SICHERUNG", str(ha / "wildkammer-sicherung"))
    import einspielen
    return importlib.reload(einspielen), quelle, ha


def test_kopiert_sichert_und_laedt_neu(tmp_path, monkeypatch):
    e, quelle, ha = _laden(tmp_path, monkeypatch)
    (quelle / "wildetikett.yaml").write_text("neu: 1\n")
    (ha / "packages" / "wildetikett.yaml").write_text("alt: 1\n")
    (ha / "packages" / "ecp202.yaml").write_text("fremd: 1\n")
    aufrufe, meldungen = [], []
    ha_api = lambda pfad, daten=None: aufrufe.append(pfad) or {"result": "valid"}
    assert e.einspielen(ha_api, lambda t, x: meldungen.append(t), "2.11.0") == "neu"
    assert (ha / "packages" / "wildetikett.yaml").read_text() == "neu: 1\n"
    assert (ha / "packages" / "ecp202.yaml").read_text() == "fremd: 1\n"  # fremde Pakete bleiben
    sicherungen = list((ha / "wildkammer-sicherung").iterdir())
    assert len(sicherungen) == 1 and sicherungen[0].read_text() == "alt: 1\n" and sicherungen[0].suffix == ".bak"
    assert aufrufe == ["/config/core/check_config", "/services/homeassistant/reload_all"]
    assert meldungen == ["Wildkammer aktualisiert"]
    # Zweiter Start ohne Änderung: nichts passiert
    assert e.einspielen(ha_api, lambda t, x: meldungen.append(t)) == "gleich"
    assert len(aufrufe) == 2


def test_fehlerhafte_konfiguration_wird_zurueckgenommen(tmp_path, monkeypatch):
    e, quelle, ha = _laden(tmp_path, monkeypatch)
    (quelle / "wildetikett.yaml").write_text("kaputt\n")
    (quelle / "wildkammer_verkauf.yaml").write_text("neu\n")
    (ha / "packages" / "wildetikett.yaml").write_text("alt\n")
    meldungen = []
    ergebnis = e.einspielen(lambda p, d=None: {"result": "invalid", "errors": "Zeile 3"},
                            lambda t, x: meldungen.append((t, x)))
    assert ergebnis == "zurueck"
    assert (ha / "packages" / "wildetikett.yaml").read_text() == "alt\n"
    assert not (ha / "packages" / "wildkammer_verkauf.yaml").exists()
    assert "nicht eingespielt" in meldungen[0][0] and "Zeile 3" in meldungen[0][1]


def test_ohne_home_assistant_ordner_passiert_nichts(tmp_path, monkeypatch):
    monkeypatch.setenv("WILDKAMMER_PAKETE", str(tmp_path / "fehlt"))
    import einspielen
    e = importlib.reload(einspielen)
    assert e.einspielen(lambda *a: None, lambda *a: None) == "aus"


def test_mitgelieferte_pakete_sind_aktuell():
    wurzel = Path(__file__).parent.parent / "wildkammer" / "pakete"
    namen = sorted(p.name for p in wurzel.glob("*.yaml"))
    assert namen == ["wildetikett.yaml", "wildkammer_verkauf.yaml"]
    assert all("9cea996fbc0962ebe6d27af33baf87e9" in (wurzel / n).read_text() for n in namen)


def test_umzug_ueber_share(tmp_path, monkeypatch):
    (tmp_path / "share").mkdir()
    monkeypatch.setenv("WILDKAMMER_UMZUG", str(tmp_path / "share" / "wildkammer" / "letzter.db"))
    import einspielen
    e = importlib.reload(einspielen)
    from db import Datenbank
    alt = tmp_path / "alt" / "wildkammer.db"
    alt.parent.mkdir()
    d = Datenbank(str(alt))
    d.setze_art("Reh")
    assert e.daten_ablegen(d)
    neu = tmp_path / "neu" / "wildkammer.db"
    assert e.daten_holen(str(neu))
    assert Datenbank(str(neu)).liste(status="entwurf") == [] and neu.exists()
    # Vorhandene Daten werden nie überschrieben
    assert not e.daten_holen(str(neu))
