"""Welche Rollos es gibt und in welchem Raum sie hängen.

Ohne eigene Datei gilt STANDARD. Wer etwas ändern will, legt in Home Assistant
/config/beschattung.yaml an (Aufbau wie unten in BEISPIEL) und startet das Add-on neu.
"""
import os
import re

TYPEN = ("raff", "roll", "fenster")

STANDARD = [
    {"name": "Wohnen", "symbol": "sofa", "rollos": [
        {"entity": "cover.raffstore_wohnzimmer_gros_venetian_blinds_6", "name": "Wohnzimmer groß", "typ": "raff"},
        {"entity": "cover.raffstore_wohnzimmer_klein_venetian_blinds", "name": "Wohnzimmer klein", "typ": "raff"},
        {"entity": "cover.raffstore_kuche_venetian_blinds_2", "name": "Küche", "typ": "raff"},
        {"entity": "cover.raffstore_hwr_venetian_blinds_7", "name": "HWR", "typ": "raff"},
    ]},
    {"name": "Galerie", "symbol": "galerie", "rollos": [
        {"entity": "cover.galeriefenster", "name": "Galeriefenster", "typ": "fenster"},
        {"entity": "cover.rollladen_galerie", "name": "Rollladen", "typ": "roll"},
        {"entity": "cover.raffstore_galerie_links_venetian_blinds_9", "name": "Raffstore links", "typ": "raff"},
        {"entity": "cover.raffstore_galerie_rechts_venetian_blinds_3", "name": "Raffstore rechts", "typ": "raff"},
    ]},
    {"name": "Bad", "symbol": "bad", "rollos": [
        {"entity": "cover.raffstore_bad_ost_venetian_blinds_4", "name": "Raffstore Ost", "typ": "raff"},
        {"entity": "cover.raffstore_bad_sud_venetian_blinds", "name": "Raffstore Süd", "typ": "raff"},
        {"entity": "cover.rollladen_bad", "name": "Rollladen", "typ": "roll"},
    ]},
    {"name": "Zimmer", "symbol": "bett", "rollos": [
        {"entity": "cover.raffstore_kinderzimmer_venetian_blinds_8", "name": "Kinderzimmer Raffstore", "typ": "raff"},
        {"entity": "cover.rolladen_kinderzimmer_roller_shutter_5", "name": "Kinderzimmer Rollladen", "typ": "roll"},
        {"entity": "cover.rolladen_schlafzimmer_roller_shutter_6", "name": "Schlafzimmer", "typ": "roll"},
        {"entity": "cover.rollladen_gz", "name": "Gästezimmer", "typ": "roll"},
        {"entity": "cover.rollladen_buro", "name": "Büro", "typ": "roll"},
    ]},
]

BEISPIEL = """\
# /config/beschattung.yaml
- name: Wohnen
  symbol: sofa            # sofa, galerie, bad, bett, kind, buero, haus
  rollos:
    - entity: cover.raffstore_kuche_venetian_blinds_2
      name: Küche
      typ: raff           # raff = Raffstore mit Lamellen, roll = Rollladen, fenster = Fenster
"""


def _schluessel(name):
    s = name.lower().replace("ä", "ae").replace("ö", "oe").replace("ü", "ue").replace("ß", "ss")
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-") or "raum"


def pruefen(raeume):
    """Prüft den Aufbau und ergänzt den Kurznamen für die Adresse. Wirft ValueError bei Fehlern."""
    if not isinstance(raeume, list) or not raeume:
        raise ValueError("Es muss mindestens einen Raum geben.")
    gesehen, schluessel, ergebnis = set(), set(), []
    for r in raeume:
        if not isinstance(r, dict) or not str(r.get("name", "")).strip():
            raise ValueError("Jeder Raum braucht einen Namen.")
        name = str(r["name"]).strip()
        k = _schluessel(name)
        while k in schluessel or k in ("api", "static"):
            k += "-2"
        schluessel.add(k)
        rollos = []
        for o in r.get("rollos") or []:
            e = str((o or {}).get("entity", "")).strip()
            if not re.fullmatch(r"cover\.[a-z0-9_]+", e):
                raise ValueError(f"Ungültige Entität in {name}: {e or '(leer)'}")
            if e in gesehen:
                raise ValueError(f"{e} steht doppelt in der Liste.")
            gesehen.add(e)
            typ = o.get("typ", "roll")
            if typ not in TYPEN:
                raise ValueError(f"Unbekannter Typ {typ} bei {e}")
            rollos.append({"entity": e, "name": str(o.get("name") or e).strip(), "typ": typ})
        if not rollos:
            raise ValueError(f"Raum {name} hat keine Rollos.")
        ergebnis.append({"name": name, "symbol": str(r.get("symbol", "haus")), "schluessel": k, "rollos": rollos})
    return ergebnis


def laden(pfad=None):
    pfad = pfad or os.environ.get("BESCHATTUNG_DATEI", "/config/beschattung.yaml")
    if os.path.exists(pfad):
        import yaml
        with open(pfad, encoding="utf-8") as f:
            try:
                return pruefen(yaml.safe_load(f)), None
            except (ValueError, yaml.YAMLError) as fehler:
                return pruefen(STANDARD), f"{pfad} enthält einen Fehler, es gilt die Standardaufteilung: {fehler}"
    return pruefen(STANDARD), None
