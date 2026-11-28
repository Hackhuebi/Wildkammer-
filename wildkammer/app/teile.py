"""Eigene Teilstücke: Die Wildkammer erzeugt daraus ein Home-Assistant-Paket mit den passenden Sprachbefehlen
für Etiketten, genau wie bei den mitgelieferten Teilstücken in wildetikett.yaml."""
import json
import re

# Mitgelieferte Teilstücke (stehen fest in wildetikett.yaml)
STANDARD = ["Braten", "Keule", "Rücken", "Filet", "Blatt", "Nacken", "Rippen", "Gulasch", "Ragout", "Hack",
            "Wurstfleisch", "Knochen", "Leber", "Herz", "Bauch", "Oberschale", "Unterschale", "Nuss", "Hüfte"]
ERLAUBT = re.compile(r"[A-Za-zÄÖÜäöüß][A-Za-zÄÖÜäöüß \-]{0,29}")
DATEI = "wildkammer_teile.yaml"

_w = "zwei drei vier fünf sechs sieben acht neun zehn".split()
_z = [str(i) for i in range(2, 11)]
MENGE = "(" + "|".join(_z + [z + "x" for z in _z] + [z + "mal" for z in _z] + _w + [w + "mal" for w in _w]) + ") [mal]"
ANZAHL = "(" + "|".join(_z + _w) + ")"


def name_pruefen(name):
    name = " ".join((name or "").split())
    if not ERLAUBT.fullmatch(name):
        return None
    return name[0].upper() + name[1:]


def woerter(name, varianten=""):
    """Gesprochene Formen: der Name und die Varianten, klein geschrieben, ohne Dopplungen."""
    alle = [name] + [v for v in re.split(r"[,;/]", varianten or "")]
    sauber = []
    for w in alle:
        w = " ".join(w.split()).lower()
        if w and ERLAUBT.fullmatch(w) and w not in sauber:
            sauber.append(w)
    return sauber


def _ausloeser(name, formen):
    w = "(" + "|".join(formen) + ")" if len(formen) > 1 else formen[0]
    return [
        {"trigger": "conversation", "id": name, "command": [
            f"[etikett] {w}", f"[etikett] {w} {{gewicht}}",
            f"(drucke|druck) [ein] [etikett] [für] {w}", f"(drucke|druck) [ein] [etikett] [für] {w} {{gewicht}}"]},
        {"trigger": "conversation", "id": f"{name}#menge", "command": [f"{MENGE} {w}", f"{MENGE} {w} {{gewicht}}"]},
        {"trigger": "conversation", "id": f"{name}#drucke", "command": [
            f"(drucke|druck) {ANZAHL} (etikett|etiketten) [für] {w}",
            f"(drucke|druck) {ANZAHL} (etikett|etiketten) [für] {w} {{gewicht}}"]},
    ]


AKTIONEN = [
    {"action": "rest_command.wild_eingabe",
     "data": {"gewicht": "{{ trigger.slots.gewicht | default('') }}",
              "menge": "{% set w = trigger.sentence.split(' ') %}"
                       "{{ w[1] if '#drucke' in trigger.id else w[0] if '#menge' in trigger.id else '' }}"},
     "response_variable": "eingabe"},
    {"if": "{{ not eingabe.content.ok }}", "then": [
        {"set_conversation_response": "{% if eingabe.content.fehler == 'gewicht_ungueltig' %}Das Gewicht habe ich "
                                      "nicht verstanden.{% elif eingabe.content.fehler == 'menge_ungueltig' %}Die Menge "
                                      "habe ich nicht verstanden.{% else %}Die Wildkammer hat einen Fehler gemeldet."
                                      "{% endif %} Es wurde nichts gedruckt."},
        {"stop": "Eingabe nicht verstanden"}]},
    {"action": "script.wild_sprache_etikett",
     "data": {"teil": "{{ trigger.id.split('#')[0] }}", "gewicht_g": "{{ eingabe.content.gewicht_g }}",
              "anzahl": "{{ eingabe.content.anzahl }}"},
     "response_variable": "r"},
    {"set_conversation_response":
        "{% if r.ok %}{% if eingabe.content.anzahl > 1 %}{{ eingabe.content.anzahl }} mal {% endif %}"
        "{{ trigger.id.split('#')[0] }}{% set g = eingabe.content.gewicht_g %}"
        "{% if g and g < 1000 %}, {{ g }} Gramm{% elif g %}, {{ (g / 1000) | string | replace('.', ',') }} Kilo{% endif %}"
        ", {{ r.art }}.{% if r.druck_unsicher %} Der Drucker hat einen Fehler gemeldet, eingebucht ist es trotzdem. "
        "Kam kein Etikett, sag Storno.{% endif %}"
        "{% elif r.fehler == 'wildart_fehlt' %}Erst die Wildart sagen."
        "{% elif r.fehler == 'druck' %}Der Drucker hat nicht gedruckt. Bitte prüfen und noch einmal sagen."
        "{% else %}Das hat nicht geklappt.{% endif %}"},
]


def paket(eigene):
    """eigene: [(name, varianten)] -> Inhalt von wildkammer_teile.yaml (JSON ist gültiges YAML)."""
    kopf = ("# Wird von der Wildkammer erzeugt (Mehr → Teilstücke) und bei jeder Änderung überschrieben.\n"
            "# Eigene Änderungen bitte nicht hier machen.\n")
    ausloeser = []
    for name, varianten in eigene:
        formen = woerter(name, varianten)
        if formen:
            ausloeser += _ausloeser(name, formen)
    if not ausloeser:
        return kopf + "wildkammer_teile:\n  automation: []\n"
    automation = [{"id": "wild_sprache_eigene_teile", "alias": "Wild-Sprache: Etikett (eigene Teilstücke)",
                   "mode": "queued", "max": 20, "triggers": ausloeser, "actions": AKTIONEN}]
    return kopf + "wildkammer_teile:\n  automation: " + json.dumps(automation, ensure_ascii=False, indent=2).replace("\n", "\n  ") + "\n"
