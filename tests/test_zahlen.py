import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parents[1] / "wildkammer" / "app"))
import zahlen  # noqa: E402
from web import erstelle_app  # noqa: E402


@pytest.mark.parametrize("wort,zahl", [
    ("ein", 1), ("zwo", 2), ("zwölf", 12), ("fünfundsiebzig", 75), ("hundert", 100), ("einhundert", 100),
    ("achthundert", 800), ("achthundertfünfzig", 850), ("zweihundertfünfundsiebzig", 275),
    ("zweihundertundfünfzig", 250), ("tausend", 1000), ("eintausendzweihundert", 1200),
    ("zweitausend", 2000), ("zwölftausend", 12000), ("toaster", None), ("", None),
    ("achtundhundert", None), ("hundertfoo", None),
])
def test_zahlwort(wort, zahl):
    assert zahlen.wort_zu_zahl(wort) == zahl


@pytest.mark.parametrize("text,g", [
    ("800 Gramm", 800), ("800 g", 800), ("800g", 800), ("800", 800), ("achthundert gramm", 800),
    ("mit 800 Gramm", 800), ("etwa 650 Gramm", 650), ("1.250 Gramm", 1250), ("1250 gramm", 1250),
    ("1 Kilo", 1000), ("ein Kilo", 1000), ("2 kg", 2000), ("2kg", 2000), ("zwei Kilogramm", 2000),
    ("1,5 Kilo", 1500), ("1.5 Kilo", 1500), ("1,25 kg", 1250), ("eins komma fünf kilo", 1500),
    ("zwei komma fünf kilo", 2500), ("eins komma zwei fünf kilo", 1250),
    ("1 Kilo 200", 1200), ("ein Kilo zweihundert", 1200), ("1 Kilo 200 Gramm", 1200),
    ("ein kilo und zweihundert gramm", 1200), ("anderthalb Kilo", 1500), ("eineinhalb kilo", 1500),
    ("ein halbes Kilo", 500), ("ein Pfund", 500), ("", None), (None, None), ("   ", None),
])
def test_gewicht(text, g):
    assert zahlen.gewicht(text) == g


@pytest.mark.parametrize("text", [
    "im Ofen", "vom Reh", "60 Kilo", "0 Gramm", "5", "zwei", "-5 gramm", "1 Kilo 1200", "kilo", "gramm",
    "99999 Gramm",
])
def test_unbrauchbares_gewicht(text):
    with pytest.raises(ValueError):
        zahlen.gewicht(text)


@pytest.mark.parametrize("text,n", [
    ("", 1), (None, 1), ("3", 3), ("3 mal", 3), ("3mal", 3), ("3x", 3), ("drei mal", 3), ("dreimal", 3),
    ("Zwei", 2), ("zehn", 10), ("11", None), ("0", None), ("toaster", None), ("viele", None),
])
def test_menge(text, n):
    assert zahlen.menge(text) == n


def test_schnittstelle(tmp_path):
    c = erstelle_app(tmp_path / "t.db").test_client()
    assert c.post("/api/eingabe", json={"gewicht": "1,5 Kilo", "menge": "dreimal"}).get_json() == {
        "ok": True, "anzahl": 3, "gewicht_g": 1500}
    assert c.post("/api/eingabe", json={}).get_json() == {"ok": True, "anzahl": 1, "gewicht_g": 0}
    assert c.post("/api/eingabe", json={"gewicht": "im Ofen"}).get_json()["fehler"] == "gewicht_ungueltig"
    assert c.post("/api/eingabe", json={"menge": "viele"}).get_json()["fehler"] == "menge_ungueltig"


def test_echte_zahlen_statt_text(tmp_path):
    """Home Assistant wandelt "2" und "800" von sich aus in Zahlen um."""
    assert zahlen.menge(2) == 2
    assert zahlen.gewicht(800) == 800
    c = erstelle_app(tmp_path / "z.db").test_client()
    assert c.post("/api/eingabe", json={"gewicht": 800, "menge": 2}).get_json() == {
        "ok": True, "anzahl": 2, "gewicht_g": 800}
