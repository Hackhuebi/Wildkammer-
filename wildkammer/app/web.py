"""Weboberfläche und Schnittstelle der Wildkammer."""
import csv
import io
import os
import re
import tempfile
from collections import defaultdict
from urllib.parse import urlparse

from flask import Flask, Response, abort, jsonify, redirect, render_template_string, request, url_for

import zahlen
from db import Datenbank, Fehler, code

def _version():
    try:
        with open(os.path.join(os.path.dirname(__file__), "..", "config.yaml"), encoding="utf-8") as f:
            return re.search(r'version:\s*"([^"]+)"', f.read()).group(1)
    except (OSError, AttributeError):
        return ""


VERSION = _version()

STIL = """
:root { color-scheme: light dark;
  --grund:#f2f1ec; --flaeche:#ffffff; --flaeche2:#f7f6f2; --text:#1d1e1a; --leise:#6b6d64; --linie:#e3e1d9;
  --akzent:#2c6a4e; --akzent-hell:#e3efe8; --akzent-text:#fff; --warn:#b03a2b; --warn-hell:#fbe9e6; --warn-text:#fff;
  --schatten:0 1px 2px rgba(30,30,20,.06), 0 4px 14px rgba(30,30,20,.05); --rund:14px; --leiste:64px; }
@media (prefers-color-scheme: dark) { :root {
  --grund:#121310; --flaeche:#1d1f1b; --flaeche2:#252722; --text:#eceae3; --leise:#a2a49a; --linie:#33352f;
  --akzent:#72c29a; --akzent-hell:#1d3328; --akzent-text:#0d1a14; --warn:#f08e7c; --warn-hell:#3a1f1a; --warn-text:#2a0f0a;
  --schatten:none; } }
* { box-sizing:border-box; -webkit-tap-highlight-color:transparent; }
html { -webkit-text-size-adjust:100%; }
body { margin:0; background:var(--grund); color:var(--text);
  font:16px/1.45 -apple-system, BlinkMacSystemFont, "SF Pro Text", "Segoe UI", Roboto, system-ui, sans-serif; }
main { max-width:760px; margin:0 auto; padding:8px 16px calc(var(--leiste) + 28px + env(safe-area-inset-bottom)); }
header.kopf { position:sticky; top:0; z-index:5; margin:0 -16px 8px; padding:14px 16px 10px;
  background:color-mix(in srgb, var(--grund) 88%, transparent); -webkit-backdrop-filter:blur(14px); backdrop-filter:blur(14px); }
header.kopf h1 { font-size:1.9rem; line-height:1.15; letter-spacing:-.02em; margin:0; font-weight:800; }
a { color:var(--akzent); text-underline-offset:3px; }
h2 { font-size:.82rem; text-transform:uppercase; letter-spacing:.06em; color:var(--leise); font-weight:700; margin:26px 4px 8px; }
.karte { background:var(--flaeche); border:1px solid var(--linie); border-radius:var(--rund); padding:16px; box-shadow:var(--schatten); }
.karte + .karte { margin-top:10px; }
.zahlen { display:grid; grid-template-columns:repeat(auto-fit, minmax(140px, 1fr)); gap:18px 24px; }
.zahlen .zahl b { display:block; font-size:1.75rem; line-height:1.15; letter-spacing:-.02em; font-variant-numeric:tabular-nums; }
.leise { color:var(--leise); font-size:.88rem; }
.rollbar { overflow-x:auto; -webkit-overflow-scrolling:touch; }
.karte.rollbar { padding:4px 12px; }
table { border-collapse:collapse; width:100%; font-variant-numeric:tabular-nums; }
th,td { padding:11px 8px; border-bottom:1px solid var(--linie); text-align:left; white-space:nowrap; vertical-align:middle; }
tr:last-child > td { border-bottom:0; }
th { font-size:.75rem; text-transform:uppercase; letter-spacing:.05em; color:var(--leise); font-weight:700; }
td.r,th.r { text-align:right; }
form.filter { display:flex; gap:10px; flex-wrap:wrap; align-items:end; }
label { display:flex; flex-direction:column; gap:4px; font-size:.82rem; font-weight:600; color:var(--leise); }
/* 16px verhindert, dass das iPhone beim Antippen eines Feldes hineinzoomt. */
select,input,textarea { font:16px/1.3 inherit; font-family:inherit; font-weight:400; padding:10px 12px; min-height:44px;
  border:1px solid var(--linie); border-radius:10px; background:var(--flaeche2); color:var(--text); min-width:0; }
select:focus,input:focus,textarea:focus { outline:2px solid var(--akzent); outline-offset:0; border-color:transparent; }
button, a.knopf { font:inherit; font-weight:650; min-height:44px; padding:10px 16px; border-radius:12px; cursor:pointer;
  border:1px solid var(--akzent); background:var(--akzent); color:var(--akzent-text); touch-action:manipulation;
  transition:transform .08s ease, opacity .08s ease; }
button:active, a.knopf:active { transform:scale(.97); opacity:.85; }
button:disabled { opacity:.4; }
button.neben { background:var(--akzent-hell); border-color:transparent; color:var(--akzent); }
button.gross { width:100%; padding:15px; font-size:1.08rem; }
.meldung { padding:12px 14px; border-radius:12px; margin:4px 0 14px; background:var(--akzent-hell); color:var(--text);
  border-left:4px solid var(--akzent); }
.meldung.fehler { background:var(--warn-hell); border-left-color:var(--warn); }
.etikett { font-size:1.6rem; font-weight:800; letter-spacing:-.01em; margin:0; }
.zurueck { display:inline-flex; align-items:center; gap:6px; font-weight:650; text-decoration:none;
  padding:8px 0; margin-bottom:4px; }
.zurueck svg, .eimer svg { width:20px; height:20px; display:block; }
.eimer { display:inline-flex; padding:11px; margin:-11px; border-radius:10px; color:var(--warn); }
button.gefahr { background:var(--warn); border-color:var(--warn); color:var(--warn-text); }
.zeile { display:flex; gap:10px; margin-top:16px; flex-wrap:wrap; }
.zeile > * { flex:1; min-width:130px; }
a.knopf { display:flex; align-items:center; justify-content:center; text-decoration:none; padding:15px;
  font-size:1.08rem; background:var(--flaeche); color:var(--akzent); }
td.aktion { width:1%; text-align:center; padding-right:2px; }
/* Leiste unten wie bei iPhone-Apps */
nav.leiste { position:fixed; left:0; right:0; bottom:0; z-index:10; display:flex; justify-content:center;
  background:color-mix(in srgb, var(--flaeche) 90%, transparent); -webkit-backdrop-filter:blur(16px); backdrop-filter:blur(16px);
  border-top:1px solid var(--linie); padding:6px 4px calc(6px + env(safe-area-inset-bottom)); }
nav.leiste a { flex:1; max-width:120px; display:flex; flex-direction:column; align-items:center; gap:2px;
  min-height:50px; justify-content:center; text-decoration:none; color:var(--leise); font-size:.68rem; font-weight:600; border-radius:10px; }
nav.leiste a svg { width:25px; height:25px; }
nav.leiste a.an { color:var(--akzent); }
nav.leiste a:active { background:var(--flaeche2); }
input[type=checkbox], input[type=radio] { width:22px; height:22px; min-height:0; padding:0; accent-color:var(--akzent); flex:none; }
td a, .umbruch a { text-decoration:none; font-weight:650; }
details summary { min-height:44px; display:flex; align-items:center; }
.marke { display:inline-block; padding:2px 8px; border-radius:20px; font-size:.75rem; font-weight:700;
  background:var(--akzent-hell); color:var(--akzent); vertical-align:middle; }
.marke.warn { background:var(--warn-hell); color:var(--warn); }
ul.menue { list-style:none; margin:0; padding:0; }
ul.menue li + li { border-top:1px solid var(--linie); }
ul.menue a { display:flex; align-items:center; gap:14px; padding:14px 4px; text-decoration:none; color:var(--text); font-weight:600; }
ul.menue a svg { width:24px; height:24px; color:var(--akzent); flex:none; }
ul.menue a::after { content:"›"; margin-left:auto; color:var(--leise); font-size:1.4rem; line-height:1; }
/* Beträge rechtsbündig untereinander, Pfeil dahinter */
ul.menue a > .rechts { margin-left:auto; flex:none; text-align:right; }
ul.menue a:has(> .rechts)::after { margin-left:8px; }
"""

PFEIL = (
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" '
    'stroke-linejoin="round" aria-hidden="true"><path d="M19 12H5M11 6l-6 6 6 6"/></svg>'
)
EIMER = (
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" '
    'stroke-linejoin="round" aria-hidden="true"><path d="M4 7h16M9 7V4h6v3M6.5 7l1 13h9l1-13M10 11v5M14 11v5"/></svg>'
)

def _symbol(pfad):
    return ('<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" '
            f'stroke-linejoin="round" aria-hidden="true">{pfad}</svg>')


SYMBOLE = {
    "fleisch": _symbol('<path d="M15.5 4.5c3 1.2 4.6 4.6 3.4 7.6-1.4 3.6-5.6 7.4-9.6 7.4-3.2 0-5.3-2.3-5.3-5 0-3.6 3.3-5 5.2-6.9 1.9-1.9 3.4-4.1 6.3-3.1z"/><circle cx="14" cy="9.5" r="1.6"/>'),
    # Regal mit Wurst und Honigglas
    "wurst": _symbol('<path d="M3.5 4v16M20.5 4v16M3.5 11.5h17M3.5 19.5h17"/><path d="M6.5 11.5c0-2 1.5-3.5 4-3.5"/><rect x="13" y="13.5" width="4.5" height="6" rx="1.2"/><path d="M13.5 13.5v-1h3.5v1"/>'),
    "bestellungen": _symbol('<rect x="5" y="3.5" width="14" height="17" rx="2.5"/><path d="M9 8h6M9 12h6M9 16h3.5"/>'),
    "packliste": _symbol('<path d="M3.5 8 12 4l8.5 4v8L12 20l-8.5-4z"/><path d="M3.5 8 12 12l8.5-4M12 12v8"/>'),
    "heute": _symbol('<path d="M4 10.5 12 4l8 6.5V19a1.5 1.5 0 0 1-1.5 1.5h-4v-6h-5v6h-4A1.5 1.5 0 0 1 4 19z"/>'),
    "mehr": _symbol('<circle cx="5.5" cy="12" r="1.3"/><circle cx="12" cy="12" r="1.3"/><circle cx="18.5" cy="12" r="1.3"/>'),
    "kunden": _symbol('<circle cx="9" cy="8.5" r="3.2"/><path d="M3.5 19c.6-3.2 2.8-5 5.5-5s4.9 1.8 5.5 5"/><path d="M15.5 5.6a3 3 0 0 1 0 5.8M17.5 14.4c1.7.6 2.7 2.2 3 4.6"/>'),
    "scannen": _symbol('<path d="M4 8V5.5A1.5 1.5 0 0 1 5.5 4H8M16 4h2.5A1.5 1.5 0 0 1 20 5.5V8M20 16v2.5a1.5 1.5 0 0 1-1.5 1.5H16M8 20H5.5A1.5 1.5 0 0 1 4 18.5V16"/><path d="M8 9v6M11 9v6M14 9v6M17 9v6"/>'),
    "glocke": _symbol('<path d="M6 16.5V11a6 6 0 0 1 12 0v5.5l1.5 2h-15z"/><path d="M10 20.5a2 2 0 0 0 4 0"/>'),
    "preise": _symbol('<path d="M3.5 12.5 11 5h7.5v7.5L11 20z"/><circle cx="15" cy="9" r="1.4"/>'),
    "sicherung": _symbol('<path d="M12 3.5 5 6v5.5c0 4.2 3 7.6 7 9 4-1.4 7-4.8 7-9V6z"/><path d="m9 12 2.2 2.2L15.5 10"/>'),
}

# Welcher Reiter unten leuchtet: nach dem ersten Pfadteil.
BEREICH = {"": "heute", "heute": "heute", "fleisch": "fleisch", "s": "fleisch", "wurst": "wurst", "w": "wurst", "preise": "wurst",
           "bestellungen": "bestellungen", "packliste": "bestellungen",
           "kunden": "mehr", "scan": "mehr", "sicherung": "mehr", "mehr": "mehr"}

RAHMEN = """<!doctype html><html lang="de"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta name="theme-color" content="#f2f1ec" media="(prefers-color-scheme: light)">
<meta name="theme-color" content="#121310" media="(prefers-color-scheme: dark)">
<meta name="apple-mobile-web-app-capable" content="yes"><meta name="format-detection" content="telephone=no">
<title>{{ titel }}</title>
<style>{{ stil|safe }}</style></head><body><main>
{% set bereich = bereich_von(request.path) %}
<header class="kopf"><h1>{{ 'Fleisch' if titel == 'Wildkammer' else titel }}</h1></header>
<nav class="leiste" aria-label="Hauptmenü">
{% for ziel, schluessel, name in [('heute','heute','Heute'),('bestand','fleisch','Fleisch'),('wurst','wurst','Lager'),('bestellungen','bestellungen','Bestellungen'),('mehr','mehr','Mehr')] %}
<a href="{{ url_for(ziel) }}" class="{{ 'an' if bereich == schluessel }}" {{ 'aria-current=page' if bereich == schluessel }}>{{ symbole[schluessel]|safe }}{{ name }}</a>{% endfor %}
</nav>
{% if meldung %}<div class="meldung {{ 'fehler' if fehler }}" role="status">{{ meldung }}</div>{% endif %}
"""
ENDE = "</main></body></html>"

BESTAND = RAHMEN + """
{% if entwuerfe %}<h2>Nicht eingebucht</h2>
<div class="karte">
  <p class="leise">Hier meldete der Drucker einen Fehler. Hast du das Etikett, tippe auf Einbuchen. Kam keins, auf Verwerfen.</p>
  {% for p in entwuerfe %}<div class="zeile" style="justify-content:space-between;align-items:center;gap:8px;margin:8px 0">
    <span><b>{{ p.art }} – {{ p.teil }}</b><br><span class="leise">{{ code(p.id) }} · {{ de(p.datum) }}{% if p.gewicht_g %} · {{ p.gewicht_g }} g{% endif %}</span></span>
    <span style="display:flex;gap:6px">
      <form method="post" action="{{ url_for('tuete_einbuchen', nummer=p.id) }}"><input type="hidden" name="zurueck" value="liste"><button>Einbuchen</button></form>
      <form method="post" action="{{ url_for('tuete_verwerfen', nummer=p.id) }}"><button class="neben">Verwerfen</button></form>
    </span></div>{% endfor %}
</div>{% endif %}
<div class="karte zahlen">
  <div class="zahl"><b>{{ zeilen|length }}</b><span class="leise">Tüten in dieser Auswahl</span></div>
  <div class="zahl"><b>{{ kg }}</b><span class="leise">kg, davon {{ gewogen }} von {{ zeilen|length }} Tüten gewogen</span></div>
  <div class="zahl"><b>{{ aktiv.art if aktiv else '–' }}</b>
    <span class="leise">{{ 'aktive Wildart, Stück ' ~ aktiv.id if aktiv else 'keine Wildart aktiv' }}</span></div>
</div>
<h2>Auswahl</h2>
<form class="filter karte" method="get">
  <label>Status<select name="status">
    {% for w, n in [('lager','Im Lager'),('raus','Ausgelagert'),('storniert','Gelöscht'),('','Alle')] %}
    <option value="{{ w }}" {{ 'selected' if f.status == w }}>{{ n }}</option>{% endfor %}</select></label>
  <label>Wildart<select name="art"><option value="">Alle</option>
    {% for a in wahl.arten %}<option {{ 'selected' if f.art == a }}>{{ a }}</option>{% endfor %}</select></label>
  <label>Teilstück<select name="teil"><option value="">Alle</option>
    {% for a in wahl.teile %}<option {{ 'selected' if f.teil == a }}>{{ a }}</option>{% endfor %}</select></label>
  <label>Jahr<select name="jahr"><option value="0">Alle</option>
    {% for a in wahl.jahre %}<option {{ 'selected' if f.jahr|string == a }}>{{ a }}</option>{% endfor %}</select></label>
  <label>Älter als<select name="monate">
    {% for m, n in [(0,'egal'),(3,'3 Monate'),(6,'6 Monate'),(12,'12 Monate')] %}
    <option value="{{ m }}" {{ 'selected' if f.monate == m }}>{{ n }}</option>{% endfor %}</select></label>
  <button>Anzeigen</button>
  <a href="{{ url_for('export', **request.args) }}">Als CSV für Excel</a>
</form>
{% if matrix %}<h2>Übersicht in Tüten</h2><div class="karte rollbar"><table>
  <tr><th>Teilstück</th>{% for a in spalten %}<th class="r">{{ a }}</th>{% endfor %}<th class="r">Summe</th></tr>
  {% for t, werte in matrix %}<tr><td>{{ t }}</td>{% for a in spalten %}
    <td class="r">{{ werte.get(a, '') }}</td>{% endfor %}<td class="r"><b>{{ werte.values()|sum }}</b></td></tr>{% endfor %}
</table></div>{% endif %}
<h2>Einzelne Tüten, älteste zuerst</h2><div class="karte rollbar">
{% if zeilen %}<table>
  <tr><th></th><th>Nummer</th><th>Wildart</th><th>Teilstück</th><th>Datum</th><th class="r">Gewicht</th><th>Stück</th><th>Status</th></tr>
  {% for p in zeilen %}<tr><td class="aktion">{% if p.status != 'storniert' %}<a class="eimer" title="Löschen" aria-label="{{ code(p.id) }} löschen"
      href="{{ url_for('tuete_loeschen', nummer=p.id) }}">{{ eimer|safe }}</a>{% endif %}</td>
    <td><a href="{{ url_for('tuete', nummer=p.id) }}">{{ code(p.id) }}</a></td>
    <td>{{ p.art }}</td><td>{{ p.teil }}</td>
    <td>{{ de(p.datum) }}{% if p.status == 'lager' and p.datum <= alt_grenze %} <span class="marke warn">über 1 Jahr</span>{% endif %}</td>
    <td class="r">{{ p.gewicht_g ~ ' g' if p.gewicht_g else '–' }}</td><td>{{ p.stueck_id }}</td><td>{{ namen[p.status] }}</td></tr>{% endfor %}
</table>{% else %}<p class="leise">In dieser Auswahl gibt es keine Tüten.</p>{% endif %}</div>
""" + ENDE

TUETE = RAHMEN + """
<a class="zurueck" href="{{ url_for('bestand') }}">{{ pfeil|safe }} Zurück zum Fleisch</a>
<div class="karte">
  <p class="leise">{{ code(p.id) }} · Stück {{ p.stueck_id }} · {{ namen[p.status] }}</p>
  <p class="etikett">{{ p.art }} – {{ p.teil }}</p>
  <p>Eingepackt am {{ de(p.datum) }}{% if p.gewicht_g %} · {{ p.gewicht_g }} g{% endif %}</p>
  {% if p.status == 'entwurf' %}
  <p><b>Nicht eingebucht.</b> Der Drucker hat beim Druck einen Fehler gemeldet. Wenn du dieses Etikett in der Hand hast,
  wurde es doch gedruckt.</p>
  <form method="post" action="{{ url_for('tuete_einbuchen', nummer=p.id) }}"><button class="gross">Jetzt einbuchen</button></form>
  {% elif p.status == 'lager' %}
  <form method="post" action="{{ url_for('tuete_aus', nummer=p.id) }}"><button class="gross">Auslagern</button></form>
  {% elif p.status in ('raus', 'storniert') %}
  <form method="post" action="{{ url_for('tuete_ein', nummer=p.id) }}"><button class="neben gross">Zurück ins Lager</button></form>
  {% endif %}
</div>
{% if p.status != 'entwurf' %}
<h2>Gewicht</h2>
<form class="filter karte" method="post" action="{{ url_for('tuete_gewicht', nummer=p.id) }}">
  <label>Gramm<input name="gramm" type="number" inputmode="numeric" min="1" max="50000" value="{{ p.gewicht_g or '' }}"></label>
  <button class="neben">Speichern</button>
</form>
{% if p.status != 'storniert' %}
<h2>Löschen</h2>
<div class="karte"><a class="eimer" style="margin:0;padding:0;align-items:center;gap:8px;font-weight:600"
  href="{{ url_for('tuete_loeschen', nummer=p.id) }}">{{ eimer|safe }} Diese Tüte löschen</a></div>
{% endif %}
{% endif %}
""" + ENDE

LOESCHEN = RAHMEN + """
<a class="zurueck" href="{{ url_for('bestand') }}">{{ pfeil|safe }} Zurück zum Fleisch</a>
<div class="karte">
  <p class="etikett">{{ p.art }} – {{ p.teil }}</p>
  <p class="leise">{{ code(p.id) }} · {{ de(p.datum) }}{% if p.gewicht_g %} · {{ p.gewicht_g }} g{% endif %}</p>
  <p>Diese Tüte aus dem Bestand löschen? Du findest sie danach noch unter dem Status „Gelöscht“ und kannst sie zurückholen.</p>
  <div class="zeile">
    <a class="knopf" href="{{ url_for('bestand') }}">Abbrechen</a>
    <form method="post"><button class="gefahr gross">Löschen</button></form>
  </div>
</div>
""" + ENDE

SCAN = RAHMEN + """
<div class="karte">
  <form method="post" class="filter"><label style="flex:1">Etikett scannen oder Nummer eintippen; die Tüte wird sofort ausgelagert.
    <input name="eingabe" autofocus autocomplete="off" placeholder="W-000123 oder P-000045"></label><button>Auslagern</button></form>
</div>
{% if letzte %}<h2>Zuletzt</h2><p><a href="{{ url_for('tuete', nummer=letzte.id) }}">{{ code(letzte.id) }}</a>
  {{ letzte.art }} – {{ letzte.teil }}</p>{% endif %}
""" + ENDE

NAMEN = {"lager": "Im Lager", "raus": "Ausgelagert", "storniert": "Gelöscht", "entwurf": "Entwurf"}


def de(datum):
    j, m, t = datum.split("-")
    return f"{t}.{m}.{j}"


def nummer_aus(text):
    """Liest eine Nummer aus Klartext, W-Code oder dem Link im QR-Code."""
    t = (text or "").strip()
    m = re.search(r"/s/(\d{1,9})/?$", t) or re.fullmatch(r"(?:[Ww]-?)?(\d{1,9})", t)
    return int(m.group(1)) if m else None


def _ganz(wert):
    try:
        return max(int(wert), 0)
    except (TypeError, ValueError):
        return 0


def _gewicht(wert):
    """Leer oder 0 heißt: kein Gewicht genannt. Alles andere muss plausibel sein."""
    if wert in (None, "", 0, "0"):
        return None
    try:
        gramm = int(wert)
    except (TypeError, ValueError):
        raise Fehler("gewicht_ungueltig")
    if not 0 < gramm <= 50000:
        raise Fehler("gewicht_ungueltig")
    return gramm


def _text(daten, feld):
    wert = str((daten or {}).get(feld, "")).strip()
    return wert if 0 < len(wert) <= 40 else None


def erstelle_app(pfad, uhr=None):
    app = Flask(__name__)
    d = Datenbank(pfad, uhr)
    def bereich_von(pfad):
        teil = (pfad or "/").strip("/").split("/")[0].split(".")[0]
        return BEREICH.get(teil, "")

    kontext = dict(stil=STIL, code=code, de=de, namen=NAMEN, pfeil=PFEIL, eimer=EIMER,
                   bereich_von=bereich_von, symbole=SYMBOLE)

    @app.get("/mehr")
    def mehr():
        vorlage = RAHMEN + """
<div class="karte" style="padding:4px 14px"><ul class="menue">
  <li><a href="{{ url_for('packliste') }}">{{ symbole.packliste|safe }}Packliste</a></li>
  <li><a href="{{ url_for('kunden') }}">{{ symbole.kunden|safe }}Kunden</a></li>
  <li><a href="{{ url_for('scan') }}">{{ symbole.scannen|safe }}Scannen</a></li>
  <li><a href="{{ url_for('erinnerung_seite') }}">{{ symbole.glocke|safe }}Zahlungserinnerung</a></li>
  <li><a href="{{ url_for('preise') }}">{{ symbole.preise|safe }}Kilopreise Fleisch</a></li>
  <li><a href="{{ url_for('sicherung') }}">{{ symbole.sicherung|safe }}Sicherung</a></li>
</ul></div>
<p class="leise" style="text-align:center;margin-top:24px">Wildkammer {{ version }}</p>
""" + ENDE
        return render_template_string(vorlage, titel="Mehr", version=VERSION, **kontext)
    innen = app.wsgi_app

    def mit_ingress_pfad(umgebung, antwort):
        # In der Home-Assistant-App liegt die Seite unter einem eigenen Pfad.
        pfad_ha = umgebung.get("HTTP_X_INGRESS_PATH", "")
        if re.fullmatch(r"/api/hassio_ingress/[\w-]+", pfad_ha):
            umgebung["SCRIPT_NAME"] = pfad_ha
        return innen(umgebung, antwort)

    app.wsgi_app = mit_ingress_pfad

    @app.before_request
    def herkunft_pruefen():
        # Fremde Webseiten dürfen im Heimnetz keine Tüten auslagern.
        # Über die App prüft Home Assistant die Anmeldung schon selbst.
        herkunft = request.headers.get("Origin")
        if request.script_root:
            return
        if request.method == "POST" and herkunft and urlparse(herkunft).netloc != request.host:
            abort(403)

    @app.errorhandler(Fehler)
    def fachfehler(f):
        return jsonify(ok=False, fehler=f.kennwort, **f.info), 200

    def filter_werte():
        a = request.args
        return dict(
            art=a.get("art", ""), teil=a.get("teil", ""), status=a.get("status", "lager"),
            monate=_ganz(a.get("monate")), jahr=_ganz(a.get("jahr")),
        )

    # ---------- Schnittstelle für Home Assistant ----------
    @app.post("/api/wildart")
    def api_wildart():
        art = _text(request.get_json(silent=True), "art")
        if not art:
            raise Fehler("eingabe_fehlt")
        return jsonify(ok=True, **d.setze_art(art))

    @app.post("/api/neues-stueck")
    def api_neues_stueck():
        return jsonify(ok=True, **d.neues_stueck())

    @app.post("/api/anlegen")
    def api_anlegen():
        daten = request.get_json(silent=True) or {}
        teil = _text(daten, "teil")
        if not teil:
            raise Fehler("eingabe_fehlt")
        return jsonify(ok=True, **d.anlegen(teil, _gewicht(daten.get("gewicht_g"))))

    @app.post("/api/eingabe")
    def api_eingabe():
        """Übersetzt die gesprochene Menge und das Gewicht. Legt selbst nichts an."""
        daten = request.get_json(silent=True) or {}
        anzahl = zahlen.menge(daten.get("menge"))
        if anzahl is None:
            raise Fehler("menge_ungueltig")
        try:
            gramm = zahlen.gewicht(daten.get("gewicht"))
        except ValueError:
            raise Fehler("gewicht_ungueltig")
        return jsonify(ok=True, anzahl=anzahl, gewicht_g=gramm or 0)

    @app.get("/api/status")
    def api_status():
        z = d.aktiv()
        return jsonify(ok=True, art=z["art"] if z else "", stueck=z["id"] if z else 0)

    @app.post("/api/gedruckt/<int:nummer>")
    def api_gedruckt(nummer):
        return jsonify(ok=True, **d.gedruckt(nummer))

    @app.get("/api/letztes")
    def api_letztes():
        return jsonify(ok=True, **d.letztes())

    @app.post("/api/storno")
    def api_storno():
        return jsonify(ok=True, **d.storno())

    @app.get("/api/bestand")
    def api_bestand():
        teil = request.args.get("teil", "")
        zeilen = d.liste(teil=teil, art=request.args.get("art", ""))
        je = defaultdict(int)
        for p in zeilen:
            je[p["art"]] += 1
        teile = ", ".join(f"{n} {'Tüte' if n == 1 else 'Tüten'} {a}" for a, n in sorted(je.items()))
        text = f"{teil or 'Bestand'}: {teile}" if teile else f"{teil or 'Bestand'}: nichts vorhanden"
        gewogen = [p["gewicht_g"] for p in zeilen if p["gewicht_g"]]
        if gewogen:
            kilo = f"{sum(gewogen) / 1000:.1f}".replace(".", ",")
            text += f". {len(gewogen)} davon gewogen, zusammen {kilo} Kilogramm"
        return jsonify(ok=True, anzahl=len(zeilen), je_art=je, text=text)

    # ---------- Oberfläche ----------
    @app.get("/fleisch")
    def bestand():
        f = filter_werte()
        zeilen = d.liste(**f)
        gewogen = [p["gewicht_g"] for p in zeilen if p["gewicht_g"]]
        je = defaultdict(lambda: defaultdict(int))
        for p in zeilen:
            je[p["teil"]][p["art"]] += 1
        spalten = sorted({p["art"] for p in zeilen})
        kg = f"{sum(gewogen) / 1000:.1f}".replace(".", ",")
        return render_template_string(
            BESTAND, titel="Wildkammer", meldung=request.args.get("m"), f=f, zeilen=zeilen, wahl=d.auswahl(), aktiv=d.aktiv(),
            kg=kg, gewogen=len(gewogen), spalten=spalten, entwuerfe=d.entwuerfe(), alt_grenze=d.alt_grenze(),
            matrix=[(t, dict(w)) for t, w in sorted(je.items())], **kontext,
        )

    def _tuete_oder_404(nummer, entwurf_ok=False):
        p = d.paket(nummer)
        if not p or (p["status"] == "entwurf" and not entwurf_ok):
            abort(404)
        return p

    @app.get("/s/<int:nummer>")
    def tuete(nummer):
        # Auch Entwürfe zeigen: Der Drucker meldet manchmal einen Fehler, obwohl das Etikett gedruckt wurde.
        p = _tuete_oder_404(nummer, entwurf_ok=True)
        return render_template_string(
            TUETE, titel=code(nummer), p=p, meldung=request.args.get("m"), **kontext
        )

    @app.post("/s/<int:nummer>/einbuchen")
    def tuete_einbuchen(nummer):
        p = _tuete_oder_404(nummer, entwurf_ok=True)
        if p["status"] == "entwurf":
            d.gedruckt(nummer)
        if request.form.get("zurueck") == "liste":
            return redirect(url_for("bestand", m=f"{code(nummer)} eingebucht."), 303)
        return redirect(url_for("tuete", nummer=nummer, m="Eingebucht."), 303)

    @app.post("/s/<int:nummer>/verwerfen")
    def tuete_verwerfen(nummer):
        d.entwurf_verwerfen(nummer)
        return redirect(url_for("bestand", m=f"{code(nummer)} verworfen."), 303)

    @app.post("/s/<int:nummer>/aus")
    def tuete_aus(nummer):
        _tuete_oder_404(nummer)
        d.auslagern(nummer)
        return redirect(url_for("tuete", nummer=nummer, m="Ausgelagert."), 303)

    @app.post("/s/<int:nummer>/ein")
    def tuete_ein(nummer):
        _tuete_oder_404(nummer)
        d.einlagern(nummer)
        return redirect(url_for("tuete", nummer=nummer, m="Wieder im Lager."), 303)

    @app.route("/s/<int:nummer>/loeschen", methods=["GET", "POST"])
    def tuete_loeschen(nummer):
        p = _tuete_oder_404(nummer)
        if request.method == "POST":
            d.loeschen(nummer)
            return redirect(url_for("bestand", m=f"{code(nummer)} gelöscht."), 303)
        return render_template_string(LOESCHEN, titel="Löschen", p=p, **kontext)

    @app.post("/s/<int:nummer>/gewicht")
    def tuete_gewicht(nummer):
        _tuete_oder_404(nummer)
        g = _ganz(request.form.get("gramm"))
        d.gewicht(nummer, g if 0 < g <= 50000 else None)
        return redirect(url_for("tuete", nummer=nummer, m="Gewicht gespeichert."), 303)

    @app.route("/scan", methods=["GET", "POST"])
    def scan():
        meldung, fehler, letzte = None, False, None
        if request.method == "POST":
            # Wurstpackungen (QR mit /w/ oder P-Nummer) öffnen ihre Seite; dort wird der Grund gewählt.
            w = re.search(r"/w/(\d{1,9})/?$", (request.form.get("eingabe") or "").strip()) \
                or re.fullmatch(r"[Pp]-?(\d{1,9})", (request.form.get("eingabe") or "").strip())
            if w:
                return redirect(url_for("wurstpaket", nummer=int(w.group(1))), 303)
            n = nummer_aus(request.form.get("eingabe"))
            p = d.paket(n) if n else None
            if p and p["status"] == "entwurf":
                return redirect(url_for("tuete", nummer=n), 303)
            if not p:
                meldung, fehler = "Diese Nummer gibt es nicht.", True
            elif d.auslagern(n):
                meldung, letzte = f"{code(n)} ausgelagert.", d.paket(n)
            else:
                meldung, fehler, letzte = f"{code(n)} war nicht im Lager.", True, p
        return render_template_string(
            SCAN, titel="Scannen", meldung=meldung, fehler=fehler, letzte=letzte, **kontext
        )

    @app.get("/export.csv")
    def export():
        f = filter_werte()
        puffer = io.StringIO()
        s = csv.writer(puffer, delimiter=";")
        s.writerow(["Nummer", "Wildart", "Teilstück", "Datum", "Gewicht (g)", "Stück", "Status", "Ausgelagert"])
        for p in d.liste(**f):
            s.writerow([
                code(p["id"]), p["art"], p["teil"], de(p["datum"]), p["gewicht_g"] or "",
                p["stueck_id"], NAMEN[p["status"]], (p["ausgelagert"] or "")[:16].replace("T", " "),
            ])
        # Das BOM lässt Excel die Umlaute richtig lesen.
        return Response(
            "﻿" + puffer.getvalue(), mimetype="text/csv; charset=utf-8",
            headers={"Content-Disposition": "attachment; filename=wildkammer.csv"},
        )

    @app.get("/sicherung")
    def sicherung():
        fd, name = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        try:
            d.sicherung(name)
            with open(name, "rb") as q:
                inhalt = q.read()
        finally:
            os.unlink(name)
        return Response(
            inhalt, mimetype="application/octet-stream",
            headers={"Content-Disposition": "attachment; filename=wildkammer.db"},
        )

    import verkauf_web

    verkauf_web.registrieren(app, d, RAHMEN, ENDE, kontext)
    return app


if __name__ == "__main__":
    import einspielen

    try:
        print("Wildkammer: Pakete", einspielen.einspielen(version=VERSION))
    except Exception as fehler:  # Das Lager soll auch dann laufen, wenn das Einspielen scheitert
        print("Wildkammer: Pakete nicht eingespielt:", fehler)
    pfad = os.environ.get("WILDKAMMER_DB", "/data/wildkammer.db")
    if einspielen.daten_holen(pfad):
        print("Wildkammer: Daten aus /share übernommen")
    anwendung = erstelle_app(pfad)
    try:
        einspielen.daten_ablegen(Datenbank(pfad))
    except Exception as fehler:
        print("Wildkammer: Kopie nach /share fehlgeschlagen:", fehler)
    import erinnerung
    from verkauf import Verkauf

    erinnerung.starten(Verkauf(Datenbank(pfad)))
    from waitress import serve

    serve(anwendung, host="0.0.0.0", port=8099, threads=4)
