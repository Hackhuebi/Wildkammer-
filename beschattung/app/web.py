"""Weboberfläche der Beschattung: gleiche Optik wie die Wildkammer, steuert die Rollos über Home Assistant."""
import os
import re
from urllib.parse import urlparse

from flask import Flask, abort, jsonify, render_template_string, request

import raeume as raeume_modul
from ha import DIENSTE, NUR_LAMELLEN, HomeAssistant


def _version():
    try:
        with open(os.path.join(os.path.dirname(__file__), "..", "config.yaml"), encoding="utf-8") as f:
            return re.search(r'version:\s*"([^"]+)"', f.read()).group(1)
    except (OSError, AttributeError):
        return ""


VERSION = _version()

# Farben, Schrift und Leiste wie in der Wildkammer (wildkammer/app/web.py), damit beide Apps zusammenpassen.
STIL = """
:root { color-scheme: light dark;
  --grund:#f2f1ec; --flaeche:#ffffff; --flaeche2:#f7f6f2; --text:#1d1e1a; --leise:#6b6d64; --linie:#e3e1d9;
  --akzent:#2c6a4e; --akzent-hell:#e3efe8; --akzent-text:#fff; --warn:#b03a2b; --warn-hell:#fbe9e6; --warn-text:#fff;
  --faehrt:#2f6fb0; --faehrt-hell:#e4eef8;
  --schatten:0 1px 2px rgba(30,30,20,.06), 0 4px 14px rgba(30,30,20,.05); --rund:14px; --leiste:64px; }
@media (prefers-color-scheme: dark) { :root {
  --grund:#121310; --flaeche:#1d1f1b; --flaeche2:#252722; --text:#eceae3; --leise:#a2a49a; --linie:#33352f;
  --akzent:#72c29a; --akzent-hell:#1d3328; --akzent-text:#0d1a14; --warn:#f08e7c; --warn-hell:#3a1f1a; --warn-text:#2a0f0a;
  --faehrt:#7fb2e8; --faehrt-hell:#1b2836;
  --schatten:none; } }
* { box-sizing:border-box; -webkit-tap-highlight-color:transparent; }
html { -webkit-text-size-adjust:100%; }
body { margin:0; background:var(--grund); color:var(--text);
  font:16px/1.45 -apple-system, BlinkMacSystemFont, "SF Pro Text", "Segoe UI", Roboto, system-ui, sans-serif; }
main { max-width:760px; margin:0 auto; padding:8px 16px calc(var(--leiste) + 28px + env(safe-area-inset-bottom)); }
header.kopf { position:sticky; top:0; z-index:5; margin:0 -16px 8px; padding:14px 16px 10px;
  background:color-mix(in srgb, var(--grund) 88%, transparent); -webkit-backdrop-filter:blur(14px); backdrop-filter:blur(14px); }
header.kopf h1 { font-size:1.9rem; line-height:1.15; letter-spacing:-.02em; margin:0; font-weight:800; }
h2 { font-size:.82rem; text-transform:uppercase; letter-spacing:.06em; color:var(--leise); font-weight:700; margin:26px 4px 8px; }
.karte { background:var(--flaeche); border:1px solid var(--linie); border-radius:var(--rund); padding:16px; box-shadow:var(--schatten); }
.karte + .karte { margin-top:10px; }
.zahlen { display:grid; grid-template-columns:repeat(3, 1fr); gap:18px 24px; }
.zahlen .zahl b { display:block; font-size:1.75rem; line-height:1.15; letter-spacing:-.02em; font-variant-numeric:tabular-nums; }
.leise { color:var(--leise); font-size:.88rem; }
button { font:inherit; font-weight:650; min-height:44px; padding:10px 16px; border-radius:12px; cursor:pointer;
  border:1px solid var(--akzent); background:var(--akzent); color:var(--akzent-text); touch-action:manipulation;
  transition:transform .08s ease, opacity .08s ease; display:inline-flex; align-items:center; justify-content:center; gap:6px; }
button:active { transform:scale(.97); opacity:.85; }
button:disabled { opacity:.4; }
button.neben { background:var(--akzent-hell); border-color:transparent; color:var(--akzent); }
button svg { width:20px; height:20px; flex:none; }
.meldung { padding:12px 14px; border-radius:12px; margin:4px 0 14px; background:var(--warn-hell); color:var(--text);
  border-left:4px solid var(--warn); }
.meldung[hidden] { display:none; }
.zeile { display:flex; gap:10px; margin-top:14px; flex-wrap:wrap; }
.zeile > * { flex:1; min-width:0; }
.zeile button { white-space:nowrap; padding:10px 8px; }
nav.leiste { position:fixed; left:0; right:0; bottom:0; z-index:10; display:flex; justify-content:center;
  background:color-mix(in srgb, var(--flaeche) 90%, transparent); -webkit-backdrop-filter:blur(16px); backdrop-filter:blur(16px);
  border-top:1px solid var(--linie); padding:6px 4px calc(6px + env(safe-area-inset-bottom)); }
nav.leiste a { flex:1; max-width:120px; display:flex; flex-direction:column; align-items:center; gap:2px;
  min-height:50px; justify-content:center; text-decoration:none; color:var(--leise); font-size:.68rem; font-weight:600; border-radius:10px; }
nav.leiste a svg { width:25px; height:25px; }
nav.leiste a.an { color:var(--akzent); }
nav.leiste a:active { background:var(--flaeche2); }
ul.menue { list-style:none; margin:0; padding:0; }
ul.menue li + li { border-top:1px solid var(--linie); }
ul.menue a { display:flex; align-items:center; gap:14px; padding:12px 4px; text-decoration:none; color:var(--text); font-weight:600; }
ul.menue a::after { content:"›"; margin-left:8px; color:var(--leise); font-size:1.4rem; line-height:1; }
ul.menue .txt { display:flex; flex-direction:column; min-width:0; }
ul.menue .txt small { font-weight:500; font-size:.8rem; }
ul.menue .rechts { margin-left:auto; flex:none; text-align:right; font-variant-numeric:tabular-nums; }
/* Symbol im Kästchen: grün = offen, grau = zu, blau = fährt */
.sym { width:40px; height:40px; border-radius:12px; display:flex; align-items:center; justify-content:center; flex:none;
  background:var(--flaeche2); color:var(--leise); transition:background .2s, color .2s; }
.sym svg { width:24px; height:24px; }
.sym.offen { background:var(--akzent-hell); color:var(--akzent); }
.sym.faehrt { background:var(--faehrt-hell); color:var(--faehrt); }
.sym.weg { background:var(--warn-hell); color:var(--warn); }
.sym.gross { width:48px; height:48px; border-radius:14px; }
.sym.gross svg { width:28px; height:28px; }
.balken { height:5px; border-radius:3px; background:var(--flaeche2); margin-top:6px; overflow:hidden; }
.balken i { display:block; height:100%; border-radius:3px; background:var(--akzent); transition:width .4s; }
.raumtasten { display:flex; gap:8px; padding:4px 0 12px; }
.raumtasten button { flex:1; min-height:40px; padding:8px; }
.rollo .oben { display:flex; align-items:center; gap:14px; }
.rollo .oben .txt { flex:1; min-width:0; }
.rollo .oben .txt b { display:block; font-size:1.05rem; }
.pz { font-size:1.75rem; font-weight:750; letter-spacing:-.02em; font-variant-numeric:tabular-nums; }
.pz small { font-size:.9rem; color:var(--leise); font-weight:600; }
.regler { display:flex; flex-direction:column; gap:4px; margin-top:16px; font-size:.82rem; font-weight:600; color:var(--leise); }
.regler span { display:flex; justify-content:space-between; }
input[type=range] { width:100%; height:32px; accent-color:var(--akzent); margin:0; }
.tasten { display:grid; grid-template-columns:repeat(3, 1fr); gap:8px; margin-top:14px; }
.fuss { text-align:center; margin-top:24px; }
"""


def _svg(pfad, breite="1.9"):
    return ('<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="' + breite + '" stroke-linecap="round" '
            f'stroke-linejoin="round" aria-hidden="true">{pfad}</svg>')


SYMBOLE = {
    "haus": _svg('<path d="M4 10.5 12 4l8 6.5V19a1.5 1.5 0 0 1-1.5 1.5h-4v-6h-5v6h-4A1.5 1.5 0 0 1 4 19z"/>'),
    "sofa": _svg('<path d="M5 11V8.5A2.5 2.5 0 0 1 7.5 6h9A2.5 2.5 0 0 1 19 8.5V11"/><path d="M3.5 13a1.5 1.5 0 0 1 3 0v1.5h11V13a1.5 1.5 0 0 1 3 0v4.5h-17zM6 17.5V19M18 17.5V19"/>'),
    "galerie": _svg('<rect x="5" y="3.5" width="14" height="17" rx="1.5"/><path d="M12 3.5v17M5 12h14"/>'),
    "bad": _svg('<path d="M4 12h16v2.5a4.5 4.5 0 0 1-4.5 4.5h-7A4.5 4.5 0 0 1 4 14.5zM7 19l-1 1.5M17 19l1 1.5"/><path d="M6.5 12V6a2 2 0 0 1 3.8-.9"/>'),
    "bett": _svg('<path d="M3.5 18.5V7M3.5 14.5h17v4M20.5 14.5v-3a2.5 2.5 0 0 0-2.5-2.5h-7v5.5"/><circle cx="7.3" cy="11.2" r="1.8"/>'),
    "kind": _svg('<circle cx="12" cy="13" r="6.5"/><circle cx="6.5" cy="6.5" r="2.2"/><circle cx="17.5" cy="6.5" r="2.2"/><path d="M10 15c1 1 3 1 4 0"/>'),
    "buero": _svg('<rect x="3.5" y="5" width="17" height="11" rx="1.5"/><path d="M9 20h6M12 16v4"/>'),
    "raff": _svg('<path d="M4 4h16M5 8h14M5 11.5h14M5 15h14M5 18.5h14M12 4v14.5"/>'),
    "roll": _svg('<rect x="4.5" y="4" width="15" height="16" rx="1.5"/><path d="M4.5 8h15M4.5 11.5h15M4.5 15h15"/>'),
    "fenster": _svg('<rect x="5" y="3.5" width="14" height="17" rx="1.5"/><path d="M5 9.5h14"/><path d="m9 15 3-2.5 3 2.5"/>'),
    "hoch": _svg('<path d="M12 19V5M6 11l6-6 6 6"/>', "2.4"),
    "runter": _svg('<path d="M12 5v14M6 13l6 6 6-6"/>', "2.4"),
    "stopp": _svg('<rect x="7" y="7" width="10" height="10" rx="1.5"/>', "2.4"),
    "lamellen": _svg('<path d="M5 6l14 3M5 11l14 3M5 16l14 3"/>'),
}

TEXTE = {"open": "Offen", "closed": "Zu", "opening": "Fährt hoch", "closing": "Fährt runter"}


def zustand_von(z, typ):
    """Macht aus dem Home-Assistant-Zustand das, was die Oberfläche anzeigt."""
    if not z or z.get("state") in (None, "unavailable", "unknown"):
        return {"klasse": "weg", "text": "Nicht erreichbar", "pos": None, "tilt": None, "offen": False}
    s, a = z["state"], z.get("attributes") or {}
    pos, tilt = a.get("current_position"), a.get("current_tilt_position")
    if pos is None:
        pos = 100 if s == "open" else 0 if s == "closed" else None
    text = TEXTE.get(s, s)
    if s == "open" and pos is not None and pos < 100:
        text = "Teilweise offen"
    if typ == "raff" and tilt is not None:
        text += f" · Lamellen {tilt}\u00a0%"
    klasse = "faehrt" if s in ("opening", "closing") else "offen" if s == "open" else "zu"
    return {"klasse": klasse, "text": text, "pos": pos, "tilt": tilt, "offen": s != "closed"}


RAHMEN = """<!doctype html><html lang="de"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta name="theme-color" content="#f2f1ec" media="(prefers-color-scheme: light)">
<meta name="theme-color" content="#121310" media="(prefers-color-scheme: dark)">
<meta name="apple-mobile-web-app-capable" content="yes">
<title>{{ titel }}</title>
<style>{{ stil|safe }}</style></head><body><main>
<header class="kopf"><h1>{{ titel }}</h1></header>
<nav class="leiste" aria-label="Räume">
  <a href="{{ url_for('uebersicht') }}" class="{{ 'an' if aktiv == '' }}">{{ symbole.haus|safe }}Übersicht</a>
  {% for r in raeume %}<a href="{{ url_for('raum', schluessel=r.schluessel) }}" class="{{ 'an' if aktiv == r.schluessel }}">{{ symbole.get(r.symbol, symbole.haus)|safe }}{{ r.name }}</a>{% endfor %}
</nav>
<div class="meldung" id="meldung" role="status" {{ '' if meldung else 'hidden' }}>{{ meldung or '' }}</div>
"""

SKRIPT = """
<script>
const ZUSTAND = {{ url_for('api_zustand')|tojson }}, AKTION = {{ url_for('api_aktion')|tojson }};
const meldung = document.getElementById('meldung');
let schnellBis = 0, laeuft = null, ziehen = new Set();
function zeige(text) { meldung.textContent = text || ''; meldung.hidden = !text; }
function anwenden(daten) {
  for (const [id, z] of Object.entries(daten.rollos)) {
    document.querySelectorAll('[data-id="' + id + '"]').forEach(el => {
      el.querySelectorAll('[data-text]').forEach(t => t.textContent = z.text);
      el.querySelectorAll('[data-pos]').forEach(p => p.innerHTML = z.pos == null ? '–' : z.pos + '<small> %</small>');
      el.querySelectorAll('.sym').forEach(s => { s.classList.remove('offen', 'zu', 'faehrt', 'weg'); s.classList.add(z.klasse); });
      el.querySelectorAll('.balken i').forEach(b => b.style.width = (z.pos || 0) + '%');
      el.querySelectorAll('input[data-regler]').forEach(r => {
        const w = r.dataset.regler === 'set_cover_tilt_position' ? z.tilt : z.pos;
        if (w != null && !ziehen.has(r)) { r.value = w; r.previousElementSibling.lastElementChild.textContent = w + ' %'; }
      });
    });
  }
  for (const [k, v] of Object.entries(daten.zahlen)) { const el = document.getElementById('zahl-' + k); if (el) el.textContent = v; }
}
async function holen() {
  try {
    const a = await fetch(ZUSTAND, {cache: 'no-store'}); const d = await a.json();
    if (d.ok) { anwenden(d); if (meldung.dataset.netz) { zeige(''); delete meldung.dataset.netz; } }
  } catch (e) { zeige('Keine Verbindung zu Home Assistant.'); meldung.dataset.netz = '1'; }
}
function planen() { clearTimeout(laeuft); laeuft = setTimeout(async () => { if (!document.hidden) await holen(); planen(); },
  Date.now() < schnellBis ? 1000 : 4000); }
async function aktion(ziel, dienst, wert) {
  try {
    const a = await fetch(AKTION, {method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({ziel, dienst, wert})});
    const d = await a.json();
    if (!d.ok) { zeige(d.fehler || 'Das hat nicht geklappt.'); return; }
    zeige(''); schnellBis = Date.now() + 20000; holen(); planen();
  } catch (e) { zeige('Keine Verbindung zu Home Assistant.'); }
}
document.addEventListener('click', e => {
  const k = e.target.closest('button[data-dienst]'); if (!k) return;
  e.preventDefault();
  if (k.dataset.frage && !confirm(k.dataset.frage)) return;
  aktion(k.dataset.ziel || k.closest('[data-id]').dataset.id, k.dataset.dienst, k.dataset.wert ? Number(k.dataset.wert) : null);
});
document.querySelectorAll('input[data-regler]').forEach(r => {
  const anzeige = () => r.previousElementSibling.lastElementChild.textContent = r.value + ' %';
  r.addEventListener('pointerdown', () => ziehen.add(r));
  r.addEventListener('input', anzeige);
  r.addEventListener('change', () => { ziehen.delete(r); aktion(r.closest('[data-id]').dataset.id, r.dataset.regler, Number(r.value)); });
});
document.addEventListener('visibilitychange', () => { if (!document.hidden) holen(); });
planen();
</script>
"""
ENDE = SKRIPT + "</main></body></html>"

UEBERSICHT = RAHMEN + """
<div class="karte zahlen">
  <div class="zahl"><b id="zahl-offen">{{ zahlen.offen }}</b><span class="leise">offen</span></div>
  <div class="zahl"><b id="zahl-zu">{{ zahlen.zu }}</b><span class="leise">zu</span></div>
  <div class="zahl"><b id="zahl-faehrt">{{ zahlen.faehrt }}</b><span class="leise">in Bewegung</span></div>
</div>
<div class="zeile">
  <button data-ziel="alle" data-dienst="open_cover">{{ symbole.hoch|safe }}Alle auf</button>
  <button class="neben" data-ziel="alle" data-dienst="close_cover" data-frage="Alle Raffstores und Rollläden schließen?">{{ symbole.runter|safe }}Alle zu</button>
  {% if hat_lamellen %}<button class="neben" data-ziel="alle" data-dienst="set_cover_tilt_position" data-wert="50">{{ symbole.lamellen|safe }}Lamellen</button>{% endif %}
</div>
{% for r in raeume %}
<h2>{{ r.name }}</h2>
<div class="karte" style="padding:4px 14px">
  <ul class="menue">
  {% for o in r.rollos %}{% set z = zustaende[o.entity] %}
    <li data-id="{{ o.entity }}"><a href="{{ url_for('raum', schluessel=r.schluessel) }}#{{ o.entity }}">
      <span class="sym {{ z.klasse }}">{{ symbole[o.typ]|safe }}</span>
      <span class="txt"><span>{{ o.name }}</span><small class="leise" data-text>{{ z.text }}</small></span>
      <span class="rechts pz" style="font-size:1.15rem" data-pos>{% if z.pos is none %}–{% else %}{{ z.pos }}<small> %</small>{% endif %}</span>
    </a></li>
  {% endfor %}
  </ul>
  <div class="raumtasten">
    <button class="neben" data-ziel="raum:{{ r.schluessel }}" data-dienst="open_cover">{{ symbole.hoch|safe }}Auf</button>
    <button class="neben" data-ziel="raum:{{ r.schluessel }}" data-dienst="close_cover">{{ symbole.runter|safe }}Zu</button>
  </div>
</div>
{% endfor %}
<p class="leise fuss">Beschattung {{ version }}</p>
""" + ENDE

RAUM = RAHMEN + """
<div class="zeile" style="margin-top:4px">
  <button data-ziel="raum:{{ r.schluessel }}" data-dienst="open_cover">{{ symbole.hoch|safe }}Auf</button>
  <button class="neben" data-ziel="raum:{{ r.schluessel }}" data-dienst="stop_cover">{{ symbole.stopp|safe }}Stopp</button>
  <button class="neben" data-ziel="raum:{{ r.schluessel }}" data-dienst="close_cover">{{ symbole.runter|safe }}Zu</button>
</div>
<h2>Einzeln</h2>
{% for o in r.rollos %}{% set z = zustaende[o.entity] %}
<div class="karte rollo" id="{{ o.entity }}" data-id="{{ o.entity }}">
  <div class="oben">
    <span class="sym gross {{ z.klasse }}">{{ symbole[o.typ]|safe }}</span>
    <div class="txt"><b>{{ o.name }}</b><span class="leise" data-text>{{ z.text }}</span></div>
    <span class="pz" data-pos>{% if z.pos is none %}–{% else %}{{ z.pos }}<small> %</small>{% endif %}</span>
  </div>
  <label class="regler"><span><span>{{ 'Höhe' if o.typ == 'raff' else 'Offen' }}</span><span>{{ z.pos if z.pos is not none else 0 }} %</span></span>
    <input type="range" min="0" max="100" step="5" value="{{ z.pos or 0 }}" data-regler="set_cover_position" aria-label="Position {{ o.name }}"></label>
  {% if o.typ == 'raff' %}
  <label class="regler"><span><span>Lamellen</span><span>{{ z.tilt if z.tilt is not none else 0 }} %</span></span>
    <input type="range" min="0" max="100" step="5" value="{{ z.tilt or 0 }}" data-regler="set_cover_tilt_position" aria-label="Lamellen {{ o.name }}"></label>
  {% endif %}
  <div class="tasten">
    <button class="neben" data-dienst="open_cover" aria-label="Auf">{{ symbole.hoch|safe }}</button>
    <button class="neben" data-dienst="stop_cover" aria-label="Stopp">{{ symbole.stopp|safe }}</button>
    <button class="neben" data-dienst="close_cover" aria-label="Zu">{{ symbole.runter|safe }}</button>
  </div>
</div>
{% endfor %}
""" + ENDE


def erstelle_app(raeume=None, ha=None, hinweis=None):
    app = Flask(__name__)
    if raeume is None:
        raeume, hinweis = raeume_modul.laden()
    ha = ha or HomeAssistant()
    typ_von = {o["entity"]: o["typ"] for r in raeume for o in r["rollos"]}
    alle = list(typ_von)

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
        # Fremde Webseiten dürfen im Heimnetz keine Rollos fahren.
        herkunft = request.headers.get("Origin")
        if request.script_root:
            return
        if request.method == "POST" and herkunft and urlparse(herkunft).netloc != request.host:
            abort(403)

    def zustaende():
        try:
            roh, fehler = ha.zustaende(alle), None
        except Exception as f:
            roh, fehler = {}, f"Home Assistant antwortet nicht: {f}"
        z = {e: zustand_von(roh.get(e), typ_von[e]) for e in alle}
        zahlen = {"offen": sum(1 for v in z.values() if v["klasse"] == "offen"),
                  "zu": sum(1 for v in z.values() if v["klasse"] == "zu"),
                  "faehrt": sum(1 for v in z.values() if v["klasse"] == "faehrt")}
        return z, zahlen, fehler

    kontext = dict(stil=STIL, symbole=SYMBOLE, raeume=raeume, version=VERSION)

    @app.get("/")
    def uebersicht():
        z, zahlen, fehler = zustaende()
        return render_template_string(UEBERSICHT, titel="Beschattung", aktiv="", zustaende=z, zahlen=zahlen,
                                      meldung=fehler or hinweis, hat_lamellen="raff" in typ_von.values(), **kontext)

    @app.get("/raum/<schluessel>")
    def raum(schluessel):
        r = next((r for r in raeume if r["schluessel"] == schluessel), None)
        if not r:
            abort(404)
        z, _, fehler = zustaende()
        return render_template_string(RAUM, titel=r["name"], aktiv=schluessel, r=r, zustaende=z,
                                      meldung=fehler or hinweis, **kontext)

    @app.get("/api/zustand")
    def api_zustand():
        z, zahlen, fehler = zustaende()
        if fehler:
            return jsonify(ok=False, fehler=fehler), 502
        return jsonify(ok=True, rollos=z, zahlen=zahlen)

    @app.post("/api/aktion")
    def api_aktion():
        daten = request.get_json(silent=True) or {}
        ziel, dienst, wert = str(daten.get("ziel", "")), daten.get("dienst"), daten.get("wert")
        if dienst not in DIENSTE:
            return jsonify(ok=False, fehler="Unbekannte Aktion."), 400
        if ziel == "alle":
            ids = alle
        elif ziel.startswith("raum:"):
            r = next((r for r in raeume if r["schluessel"] == ziel[5:]), None)
            ids = [o["entity"] for o in r["rollos"]] if r else []
        else:
            ids = [ziel] if ziel in typ_von else []
        if not ids:
            return jsonify(ok=False, fehler="Dieses Rollo kenne ich nicht."), 400
        if dienst in NUR_LAMELLEN:
            ids = [e for e in ids if typ_von[e] == "raff"]
            if not ids:
                return jsonify(ok=False, fehler="Hier gibt es keine Lamellen."), 400
        if DIENSTE[dienst]:
            if isinstance(wert, bool) or not isinstance(wert, (int, float)) or not 0 <= wert <= 100:
                return jsonify(ok=False, fehler="Wert muss zwischen 0 und 100 liegen."), 400
            wert = int(round(wert))
        else:
            wert = None
        try:
            ha.dienst(dienst, ids, wert)
        except Exception as f:
            return jsonify(ok=False, fehler=f"Home Assistant hat abgelehnt: {f}"), 502
        return jsonify(ok=True, anzahl=len(ids))

    return app


if __name__ == "__main__":
    from waitress import serve

    serve(erstelle_app(), host="0.0.0.0", port=8099, threads=4)
