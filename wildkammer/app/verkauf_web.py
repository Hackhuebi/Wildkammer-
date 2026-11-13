"""Seiten und Schnittstelle für Wurst, Kunden und Bestellungen."""
import re
from flask import abort, jsonify, redirect, render_template_string, request, url_for

from db import Fehler, code
from verkauf import KATEGORIEN, Verkauf, euro, wurst_code

FEHLERTEXT = {
    "bestand_nicht_ausreichend": "Nicht genug frei im Lager",
    "kunde_unklar": "Kunde nicht eindeutig",
    "produkt_unklar": "Produkt nicht eindeutig",
    "produkt_unbekannt": "Produkt unbekannt",
    "betrag_zu_hoch": "Betrag ist höher als der offene Betrag",
    "betrag_ungueltig": "Betrag ungültig",
    "nichts_offen": "Es ist nichts mehr offen",
    "schon_ausgeliefert": "Schon ausgeliefert, Stornieren nicht möglich",
    "reservierung_unterschritten": "Der Bestand darf nicht unter die reservierte Menge fallen",
    "grund_fehlt": "Für eine Korrektur bitte einen Grund angeben",
    "menge_ungueltig": "Menge ungültig",
    "produkt_existiert": "Dieses Produkt gibt es schon",
    "preis_offen": "Für Fleisch ohne Kilopreis bitte den Betrag eingeben",
    "name_ungueltig": "Bitte einen Namen eingeben",
    "bestellung_nicht_offen": "Diese Bestellung ist nicht mehr offen",
    "rabatt_zu_hoch": "Der Rabatt ist höher als der Bestellwert",
    "position_unbekannt": "Position nicht gefunden",
    "datum_ungueltig": "Datum ungültig",
    "bestellung_leer": "Die Bestellung wäre leer. Bitte stattdessen stornieren",
    "bestellung_storniert": "Die Bestellung ist storniert",
    "teilweise_geliefert": "Es wurde schon ein Teil geliefert. Bitte erst die Lieferung zurücknehmen",
    "erst_stornieren": "Nur stornierte Bestellungen können gelöscht werden",
    "gleicher_kunde": "Bitte einen anderen Kunden wählen",
    "kunde_unbekannt": "Kunde unbekannt",
    "packung_unbekannt": "Diese Packung gibt es nicht",
    "packung_schon_raus": "Diese Packung wurde schon ausgebucht",
    "packung_nicht_raus": "Diese Packung ist noch im Lager",
    "text_fehlt": "Bitte einen Text eingeben",
    "text_zu_lang": "Der Text ist zu lang (höchstens 500 Zeichen)",
    "vormerkung_unbekannt": "Notiz nicht gefunden",
    "nichts_gewaehlt": "Bitte bei mindestens einem Produkt eine Anzahl wählen",
    "art_ungueltig": "Bitte Entnahme oder Zugang wählen",
    "kunde_hat_bestellungen": "Der Kunde hat Bestellungen. Bitte zusammenführen statt löschen",
}

# Stand 09.11.2026 aus der vollständigen Übersicht: (Kunde, Positionen, Rabatt in Cent, bezahlt in Cent, geliefert)


STIL_EXTRA = """
.raster { display:grid; grid-template-columns:repeat(auto-fit,minmax(170px,1fr)); gap:12px; }
.form-zeile { display:flex; gap:10px; flex-wrap:wrap; align-items:end; }
.form-zeile label { flex:1; min-width:120px; }
.inline { display:inline; margin:0; }
button.klein { padding:6px 12px; min-height:36px; font-size:.9rem; }
.ok { color:var(--akzent); font-weight:700; }
.reiter { display:flex; gap:8px; overflow-x:auto; margin:0 -16px 12px; padding:2px 16px; scrollbar-width:none; }
.reiter::-webkit-scrollbar { display:none; }
.reiter a { flex:none; padding:8px 14px; border-radius:20px; text-decoration:none; font-weight:600; font-size:.92rem;
  background:var(--flaeche); color:var(--text); border:1px solid var(--linie); }
.reiter a.an { background:var(--text); color:var(--grund); border-color:var(--text); }
.posten { margin:0; padding-left:18px; }
td.zahl, th.zahl { text-align:right; }
td.umbruch { white-space:normal; min-width:110px; }
.status { display:flex; flex-direction:column; gap:6px; align-items:flex-start; }
.status form { margin:0; }
.status button { min-width:92px; }
button svg { width:18px; height:18px; display:block; color:var(--warn); }
table.knapp th, table.knapp td { padding:7px 6px; }
label.haken { flex-direction:row; gap:10px; align-items:center; font-size:1rem; color:inherit; margin:6px 0; }
label.haken input { width:22px; height:22px; margin:0; flex:none; }
details.karte summary { cursor:pointer; }
:root { --warn-text:#fff; }
@media (prefers-color-scheme: dark) { :root { --warn-text:#2a0f0a; } }
.stepper { display:inline-flex; align-items:center; gap:6px; }
.stepper input { width:52px; height:44px; padding:0; text-align:center; font-size:1.1rem; font-weight:700;
  -moz-appearance:textfield; appearance:textfield; }
.stepper input::-webkit-outer-spin-button, .stepper input::-webkit-inner-spin-button { -webkit-appearance:none; margin:0; }
button.st { width:44px; height:44px; padding:0; border-radius:10px; font-size:1.5rem; font-weight:700; line-height:1;
  display:inline-flex; align-items:center; justify-content:center; touch-action:manipulation; }
button.st.minus { background:var(--warn); border-color:var(--warn); color:var(--warn-text); }
button.st.plus { background:var(--akzent); border-color:var(--akzent); color:var(--akzent-text); }
button.st:disabled { opacity:.25; }
.feld { display:flex; flex-direction:column; gap:3px; font-size:.85rem; color:var(--leise); }
.modus { display:flex; gap:0; margin:0 0 12px; border:1px solid var(--linie); border-radius:12px; overflow:hidden; }
.modus label { flex:1; flex-direction:row; justify-content:center; align-items:center; gap:0; padding:10px;
  font-size:1rem; font-weight:700; color:var(--text, inherit); cursor:pointer; }
.modus input { position:absolute; opacity:0; width:1px; height:1px; }
.modus label:has(input:checked).rot { background:var(--warn); color:var(--warn-text); }
.modus label:has(input:checked).gruen { background:var(--akzent); color:var(--akzent-text); }
tr.gruppe th { padding-top:18px; font-size:.8rem; color:var(--text); }
.karte.notiz { border-left:4px solid #d4a017; }
tr.summe td { border-top:2px solid var(--linie); }
tr.weniger td { background:color-mix(in srgb, var(--warn) 10%, transparent); }
tr.gewaehlt td { background:color-mix(in srgb, var(--akzent) 12%, transparent); }
button.rot { background:var(--warn); border-color:var(--warn); color:var(--warn-text); }
"""

# Macht aus jedem <input data-stepper> ein Feld mit großem Minus (rot) und Plus (grün) für das Handy.
SKRIPT = """<script>
(function () {
  function grenze(i, w, d) { return i.getAttribute(w) === null || i.getAttribute(w) === "" ? d : Number(i.getAttribute(w)); }
  function knopf(text, klasse, schritt, i) {
    var b = document.createElement("button");
    b.type = "button"; b.className = "st " + klasse; b.textContent = text;
    b.setAttribute("aria-label", (schritt < 0 ? "weniger " : "mehr ") + (i.getAttribute("aria-label") || ""));
    b.addEventListener("click", function () {
      var v = parseInt(i.value || "0", 10) || 0;
      v = Math.min(grenze(i, "max", Infinity), Math.max(grenze(i, "min", 0), v + schritt));
      i.value = (v === 0 && i.hasAttribute("data-leer")) ? "" : v;
      i.dispatchEvent(new Event("input", { bubbles: true }));
    });
    return b;
  }
  function ruesten(i) {
    if (i.dataset.fertig) return; i.dataset.fertig = "1";
    var h = document.createElement("span"); h.className = "stepper";
    i.parentNode.insertBefore(h, i);
    var minus = knopf("\u2212", "minus", -1, i), plus = knopf("+", "plus", 1, i);
    h.appendChild(minus); h.appendChild(i); h.appendChild(plus);
    function pruefen() {
      var v = parseInt(i.value || "0", 10) || 0;
      minus.disabled = i.disabled || v <= grenze(i, "min", 0);
      plus.disabled = i.disabled || v >= grenze(i, "max", Infinity);
    }
    i.addEventListener("input", pruefen); i.addEventListener("grenze", pruefen); pruefen();
  }
  window.wkStepper = function () { document.querySelectorAll("input[data-stepper]").forEach(ruesten); };
  window.wkStepper();
})();
</script>"""

TEXT_STATUS = {"offen": "Offen", "ausgeliefert": "Ausgeliefert", "storniert": "Storniert"}


def kurz(b):
    """Knappe Fassung einer Bestellung, z. B. für Claude."""
    posten = [f"{z['menge']} × {z['produktname']}" for z in b["wurst"]]
    posten += [f"{f['art']} {f['teil']} ({f['code']}"
               + (f", {f['gewicht_g']} g" if f["gewicht_g"] else "") + ")" for f in b["fleisch"]]
    return {
        "bestellung_id": b["id"], "kunde": b["kunde"], "datum": b["datum"],
        "status": TEXT_STATUS.get(b["status"], b["status"]), "positionen": posten,
        "summe": euro(b["summe_cent"]) + (" (Fleischpreis teils offen)" if b["preis_offen"] else ""),
        "rabatt": euro(b["rabatt_cent"]) if b["rabatt_cent"] else "",
        "bezahlt": euro(b["bezahlt_cent"]), "offen": euro(b["offen_cent"]),
        "vollstaendig_bezahlt": b["bezahlt"], "ausgeliefert": b["status"] == "ausgeliefert",
    }


def registrieren(app, d, rahmen, ende, kontext):
    vk = Verkauf(d)
    app.config["VERKAUF"] = vk
    rahmen = rahmen.replace("<style>{{ stil|safe }}", "<style>{{ stil|safe }}" + STIL_EXTRA)

    def seite(vorlage, titel, **werte):
        meldung = request.args.get("m")
        fehler = request.args.get("f") == "1"
        return render_template_string(rahmen + vorlage + SKRIPT + ende, titel=titel, meldung=meldung, fehler=fehler,
                                      euro=euro, status_text=TEXT_STATUS, kategorien=KATEGORIEN, **kontext, **werte)

    def zurueck(ziel, meldung, fehler=False):
        return redirect(url_for(ziel[0], **ziel[1], m=meldung, **({"f": "1"} if fehler else {})), 303)

    def formular(ziel, aktion):
        """Führt eine Formularaktion aus und meldet Fehler verständlich auf der Seite."""
        try:
            text = aktion()
            return zurueck(ziel, text)
        except Fehler as f:
            info = f.info
            text = FEHLERTEXT.get(f.kennwort, f.kennwort)
            if "ware" in info:
                text += f": {info['ware']}" + (f" (frei: {info['frei']})" if "frei" in info else "")
            return zurueck(ziel, text + ".", True)

    # ======================= Seiten =======================
    @app.get("/wurst")
    def wurst():
        vorlage = """
<h2>Wurstlager</h2>
<form method="post" action="{{ url_for('wurst_aendern_mehrere') }}" id="lager"
  onsubmit="return confirm(document.getElementById('lager-knopf').textContent + '?')">
<div class="karte rollbar"><table class="knapp">
{% for p in produkte %}{% if loop.first or p.kategorie != loop.previtem.kategorie %}
<tr class="gruppe"><th>{{ kategorien[p.kategorie] }}</th><th class="zahl">Lager</th><th>Ändern</th></tr>{% endif %}<tr>
  <td class="umbruch"><a href="{{ url_for('wurst_produkt', pid=p.id) }}">{{ p.name }}</a><br>
    <span class="leise">{{ euro(p.preis_cent) }} · {{ [p.frei, 0]|max }} frei{% if p.reserviert %}, {{ p.reserviert }} bestellt{% endif %}</span><br>
    <span class="leise">Wert <b>{{ euro(p.bestand * p.preis_cent) }}</b></span></td>
  <td class="zahl"><b>{{ p.bestand }}</b></td>
  <td><input name="n{{ p.id }}" type="number" min="{{ -([p.frei, 0]|max) }}" max="10000" step="1"
    data-stepper data-leer placeholder="0" aria-label="{{ p.name }}"></td>
</tr>{% endfor %}
</table></div>
<div class="karte form-zeile" style="margin-top:10px">
  <label id="lager-grund" hidden>Grund für die Entnahme<select name="grund">{% for g in ['Eigenverbrauch', 'Geschenk', 'Probe', 'Verdorben', 'Sonstiges'] %}
    <option>{{ g }}</option>{% endfor %}</select></label>
  <button class="gross" id="lager-knopf" disabled>Mit + und − ändern</button>
</div>
</form>
<script>
(function () {
  var f = document.getElementById("lager"), knopf = document.getElementById("lager-knopf");
  var felder = f.querySelectorAll("input[data-stepper]");
  function stueck(n) { return n + " Stück"; }
  function aktualisieren() {
    var plus = 0, minus = 0;
    felder.forEach(function (i) {
      var n = parseInt(i.value || "0", 10) || 0;
      if (n > 0) plus += n; else minus -= n;
      i.style.color = n > 0 ? "var(--akzent)" : n < 0 ? "var(--warn)" : "";
      var tr = i.closest("tr");
      tr.classList.toggle("gewaehlt", n > 0); tr.classList.toggle("weniger", n < 0);
    });
    document.getElementById("lager-grund").hidden = minus === 0;
    var teile = [];
    if (plus) teile.push(stueck(plus) + " einbuchen");
    if (minus) teile.push(stueck(minus) + " entnehmen");
    knopf.disabled = !teile.length;
    knopf.className = "gross" + (minus && !plus ? " rot" : "");
    knopf.textContent = teile.length ? teile.join(" und ") : "Mit + und − ändern";
  }
  f.addEventListener("input", aktualisieren); f.addEventListener("change", aktualisieren); aktualisieren();
})();
</script>
<p class="leise">+ bucht neue Ware ein, − nimmt sie heraus (z. B. Eigenverbrauch). Bestellte Ware kann nicht entnommen werden.
Alles wird zusammen gebucht oder gar nichts.</p>
<h2>Lagerwert</h2>
<div class="karte rollbar"><table class="knapp">
{% for k, w in lagerwert.gruppen.items() %}
<tr class="gruppe"><th>{{ kategorien[k] }}</th><th class="zahl">Lager</th><th class="zahl">Wert</th></tr>
{% for p in produkte if p.kategorie == k and p.bestand %}<tr><td class="umbruch">{{ p.name }}</td><td class="zahl">{{ p.bestand }}</td>
  <td class="zahl">{{ euro(p.bestand * p.preis_cent) }}</td></tr>{% endfor %}
<tr class="summe"><td>Summe {{ kategorien[k] }}</td><td style="text-align:right">{{ w.stueck }}</td>
  <td style="text-align:right"><strong>{{ euro(w.gesamt) }}</strong></td></tr>
{% endfor %}
<tr class="summe"><td><strong>Gesamt</strong></td><td style="text-align:right"><strong>{{ lagerwert.stueck }}</strong></td>
  <td style="text-align:right"><strong>{{ euro(lagerwert.gesamt) }}</strong></td></tr>
<tr><td class="leise" colspan="2">davon bestellt</td><td class="zahl leise">{{ euro(lagerwert.bestellt) }}</td></tr>
<tr><td class="leise" colspan="2">davon frei</td><td class="zahl leise">{{ euro(lagerwert.frei) }}</td></tr>
</table></div>
<p class="leise">Wert = Lagerbestand × aktueller Preis. Rabatte sind nicht abgezogen.</p>
<h2>Neues Produkt</h2>
<form class="karte form-zeile" method="post" action="{{ url_for('wurst_neu') }}">
  <label>Art<select name="kategorie" onchange="this.form.einheit.value = this.value === 'honig' ? 'Glas 500 g' : 'Packung'">
    {% for k, n in kategorien.items() %}<option value="{{ k }}">{{ n }}</option>{% endfor %}</select></label>
  <label>Name<input name="name" required maxlength="60"></label>
  <label>Einheit<input name="einheit" value="Packung" required></label>
  <label>Preis (€)<input name="preis" inputmode="decimal" placeholder="7,00"></label>
  <button>Anlegen</button>
</form>
<p><a href="{{ url_for('preise') }}">Kilopreise für Fleisch</a></p>
<h2>Letzte Bewegungen</h2>
<div class="karte rollbar"><table class="knapp"><tr><th>Bewegung</th><th class="zahl">Menge</th></tr>
{% for b in bewegungen %}<tr><td class="umbruch">{{ b.name }}<br><span class="leise">{{ de(b.erstellt[:10]) }}
  {{ b.erstellt[11:16] }} · {{ b.art }}{{ ' · ' ~ b.grund if b.grund }}</span></td>
<td class="zahl">{{ '%+d' % b.menge }}</td></tr>{% endfor %}
</table></div>"""
        produkte = vk.produkte()
        gesamt = sum(max(p["bestand"], 0) * p["preis_cent"] for p in produkte)
        bestellt = sum(max(min(p["reserviert"], p["bestand"]), 0) * p["preis_cent"] for p in produkte)
        gruppen = {}
        for p in produkte:
            g = gruppen.setdefault(p["kategorie"], {"stueck": 0, "gesamt": 0})
            g["stueck"] += max(p["bestand"], 0)
            g["gesamt"] += max(p["bestand"], 0) * p["preis_cent"]
        lagerwert = {"stueck": sum(max(p["bestand"], 0) for p in produkte), "gesamt": gesamt,
                     "bestellt": bestellt, "frei": gesamt - bestellt, "gruppen": gruppen}
        return seite(vorlage, "Lager", produkte=produkte, bewegungen=vk.bewegungen(anzahl=20), lagerwert=lagerwert)

    @app.post("/wurst/neu")
    def wurst_neu():
        f = request.form
        return formular(("wurst", {}), lambda: (vk.produkt_anlegen(f.get("name"), f.get("einheit"), f.get("preis"), f.get("kategorie", "wurst")),
                                                "Produkt angelegt.")[1])

    # ======================= Heute =======================
    KNAPP = 5  # ab weniger freien Packungen oder Gläsern gilt eine Ware als knapp

    @app.get("/")
    def heute():
        offen = vk.bestellungen("nicht_ausgeliefert")
        for b in offen:
            teile = [f"{z['menge'] - z['ausgeliefert']} × {z['produktname']}" for z in b["wurst"] if z["menge"] > z["ausgeliefert"]]
            teile += [f"{f['art']} {f['teil']}" for f in b["fleisch"] if not f["ausgeliefert"]]
            b["posten"] = ", ".join(teile)
        produkte = vk.produkte()
        knapp = [p for p in produkte if p["frei"] < KNAPP]
        schulden = sorted((k for k in vk.kunden() if k["offen_cent"] > 0), key=lambda k: -k["offen_cent"])
        im_lager = d.liste(status="lager")
        jetzt = d.uhr()
        tage = ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag"]
        vorlage = """
<p class="leise" style="margin:-4px 4px 14px">{{ datum_text }}</p>
{% if pliste %}<h2>Packliste</h2>
<a href="{{ url_for('packliste') }}" class="karte" style="display:block;text-decoration:none;color:inherit">
  <table class="knapp">
  {% for name, n in pwurst %}<tr><td class="umbruch">{{ name }}</td><td class="r"><b>{{ n }}</b></td></tr>{% endfor %}
  {% for name, n in pfleisch %}<tr><td class="umbruch">{{ name }}</td><td class="r"><b>{{ n }}</b> {{ 'Tüte' if n == 1 else 'Tüten' }}</td></tr>{% endfor %}
  </table>
  <p class="leise" style="margin:10px 0 0">Für {{ pliste|map(attribute='kunde')|join(', ') }} · <span style="color:var(--akzent);font-weight:650">Öffnen ›</span></p>
</a>{% endif %}
{% if notizen %}<h2>Notizen</h2>""" + NOTIZEN + """
<p class="leise" style="margin:8px 4px"><a href="{{ url_for('notizen') }}">Alle Notizen und neue Notiz ›</a></p>{% endif %}
{% if entwuerfe or alte or knapp or faellig %}<h2>Hinweise</h2>
<div class="karte" style="padding:4px 14px"><ul class="menue">
  {% if faellig %}<li><a href="{{ url_for('erinnerung_seite') }}"><span class="marke warn">{{ faellig|length }}</span>
    <span>{{ 'Lieferung' if faellig|length == 1 else 'Lieferungen' }} seit über {{ erinnerung_tage }} Tagen unbezahlt<br>
    <span class="leise" style="font-weight:400">{% for b in faellig %}{{ b.kunde }}{{ ', ' if not loop.last }}{% endfor %}</span></span></a></li>{% endif %}
  {% if entwuerfe %}<li><a href="{{ url_for('bestand') }}"><span class="marke warn">{{ entwuerfe|length }}</span>
    <span>{{ 'Tüte' if entwuerfe|length == 1 else 'Tüten' }} nicht eingebucht<br><span class="leise" style="font-weight:400">Drucker hat einen Fehler gemeldet</span></span></a></li>{% endif %}
  {% if alte %}<li><a href="{{ url_for('bestand', monate=12) }}"><span class="marke warn">{{ alte|length }}</span>
    <span>{{ 'Tüte' if alte|length == 1 else 'Tüten' }} über 1 Jahr im Frost<br><span class="leise" style="font-weight:400">älteste vom {{ de(alte[0].datum) }}: {{ alte[0].art }} {{ alte[0].teil }}</span></span></a></li>{% endif %}
  {% if knapp %}<li><a href="{{ url_for('wurst') }}"><span class="marke warn">{{ knapp|length }}</span>
    <span>Wird knapp<br><span class="leise" style="font-weight:400">{% for p in knapp %}{{ p.name }} ({{ [p.frei, 0]|max }} frei){{ ', ' if not loop.last }}{% endfor %}</span></span></a></li>{% endif %}
</ul></div>{% endif %}
<div class="karte zahlen" style="margin-top:14px">
  <div class="zahl"><b>{{ offen|length }}</b><span class="leise">Bestellungen zu liefern</span></div>
  <div class="zahl"><b>{{ euro(schulden|sum(attribute='offen_cent')) }}</b><span class="leise">noch zu kassieren</span></div>
  <div class="zahl"><b>{{ produkte|selectattr('kategorie', 'equalto', 'wurst')|sum(attribute='frei') }}</b><span class="leise">Wurst frei (Packungen)</span></div>
  <div class="zahl"><b>{{ produkte|selectattr('kategorie', 'equalto', 'honig')|sum(attribute='frei') }}</b><span class="leise">Honig frei (Gläser)</span></div>
  <div class="zahl"><b>{{ im_lager|length }}</b><span class="leise">Fleischtüten im Lager</span></div>
</div>
<h2>Zu liefern</h2>
{% if offen %}<div class="karte" style="padding:4px 14px"><ul class="menue">
  {% for b in offen[:8] %}<li><a href="{{ url_for('bestellung', oid=b.id) }}"><span style="min-width:0">{{ b.kunde }}
    <span class="leise" style="font-weight:400">#{{ b.id }}</span><br>
    <span class="leise" style="font-weight:400">{{ b.posten }}</span></span>
    <span class="rechts">{% if b.offen_cent %}<span class="marke">{{ euro(b.offen_cent) }}</span>{% else %}<span class="marke">bezahlt</span>{% endif %}</span></a></li>{% endfor %}
</ul></div>
{% if offen|length > 8 %}<p class="leise" style="margin:8px 4px"><a href="{{ url_for('bestellungen', filter='nicht_ausgeliefert') }}">Alle {{ offen|length }} anzeigen</a></p>{% endif %}
{% if not pliste %}<p><a class="knopf" href="{{ url_for('packliste', neu=1) }}">Packliste erstellen</a></p>{% endif %}
{% else %}<div class="karte"><p class="leise" style="margin:0">Alles ausgeliefert.</p></div>{% endif %}
{% if schulden %}<h2>Noch zu kassieren</h2>
<div class="karte rollbar"><table class="knapp">
{% for k in schulden[:8] %}<tr><td class="umbruch"><a href="{{ url_for('kunde', kid=k.id) }}">{{ k.name }}</a></td>
  <td class="zahl">{{ euro(k.offen_cent) }}</td></tr>{% endfor %}
</table></div>
{% if schulden|length > 8 %}<p class="leise" style="margin:8px 4px"><a href="{{ url_for('bestellungen', filter='unbezahlt') }}">Alle unbezahlten Bestellungen</a></p>{% endif %}{% endif %}
<p><a class="knopf" href="{{ url_for('bestellung_neu') }}" style="margin-top:20px">Neue Bestellung</a></p>"""
        pliste, pwurst, pfleisch = _packliste(vk.packliste_ids())
        erinnerung_tage = int(vk.einstellung("erinnerung_tage") or 0)
        return seite(vorlage, "Heute", faellig=vk.ueberfaellig(erinnerung_tage) if erinnerung_tage else [],
                     erinnerung_tage=erinnerung_tage, notizen=vk.vormerkungen(anzahl=5), notiz_zurueck="heute", pliste=pliste, pwurst=pwurst, pfleisch=pfleisch, offen=offen, produkte=produkte, knapp=knapp, schulden=schulden,
                     im_lager=im_lager, entwuerfe=d.entwuerfe(), alte=d.alte_tueten(),
                     datum_text=f"{tage[jetzt.weekday()]}, {jetzt:%d.%m.%Y}")

    # ======================= Zahlungserinnerung =======================
    @app.route("/erinnerung", methods=["GET", "POST"])
    def erinnerung_seite():
        import erinnerung
        f = request.form
        if request.method == "POST":
            if f.get("aktion") == "test":
                ziel = f.get("ziel") or vk.einstellung("erinnerung_ziel")
                try:
                    liste = vk.ueberfaellig()
                    erinnerung.senden(ziel, "Wildkammer: Test",
                                      erinnerung.text(liste) if liste else "So sieht die Zahlungserinnerung aus.")
                except Exception as fehler:
                    return redirect(url_for("erinnerung_seite", m=f"Nicht gesendet: {fehler}", f=1), 303)
                return redirect(url_for("erinnerung_seite", m="Test-Nachricht gesendet."), 303)
            try:
                tage = max(0, min(60, int(f.get("tage") or 0)))
            except ValueError:
                return redirect(url_for("erinnerung_seite", m="Bitte eine Zahl bei Tage eingeben.", f=1), 303)
            uhrzeit = f.get("uhrzeit") or "18:00"
            if not re.fullmatch(r"([01]\d|2[0-3]):[0-5]\d", uhrzeit):
                return redirect(url_for("erinnerung_seite", m="Uhrzeit ungültig.", f=1), 303)
            vk.einstellung_setzen("erinnerung_tage", tage)
            vk.einstellung_setzen("erinnerung_uhrzeit", uhrzeit)
            vk.einstellung_setzen("erinnerung_ziel", (f.get("ziel") or "").strip())
            # nach einer Änderung darf heute noch einmal erinnert werden
            vk.einstellung_setzen("erinnerung_zuletzt", "")
            return redirect(url_for("erinnerung_seite", m="Gespeichert."), 303)
        try:
            handys, handy_fehler = erinnerung.geraete(), ""
        except Exception as fehler:
            handys, handy_fehler = [], str(fehler)
        tage = int(vk.einstellung("erinnerung_tage") or 0)
        vorlage = """
<form class="karte" method="post">
  <p class="leise" style="margin-top:0">Einmal am Tag eine Nachricht aufs Handy, wenn gelieferte Bestellungen
  länger als eingestellt nicht bezahlt sind. 0 Tage schaltet die Erinnerung aus.</p>
  <div class="form-zeile">
    <div class="feld">Nach Tagen<input name="tage" type="number" min="0" max="60" value="{{ tage }}" data-stepper aria-label="Tage"></div>
    <label>Uhrzeit<input name="uhrzeit" type="time" value="{{ uhrzeit }}" required></label>
  </div>
  <div class="form-zeile" style="margin-top:10px">
  {% if handys %}<label style="flex:1">Handy<select name="ziel">
    <option value="">– bitte wählen –</option>
    {% for h in handys %}<option value="{{ h }}" {{ 'selected' if h == ziel }}>{{ h[11:]|replace('_', ' ') }}</option>{% endfor %}
  </select></label>
  {% else %}<label style="flex:1">Handy (Dienstname)<input name="ziel" value="{{ ziel }}" placeholder="mobile_app_iphone_von_julius"></label>{% endif %}
  </div>
  {% if handy_fehler %}<p class="leise">Handys konnten nicht gelesen werden: {{ handy_fehler }}</p>{% endif %}
  <div class="zeile"><button>Speichern</button>
    <button class="neben" name="aktion" value="test" {{ 'disabled' if not (ziel or handys) }}>Test-Nachricht</button></div>
</form>
<h2>Jetzt fällig{% if tage %} (über {{ tage }} {{ 'Tag' if tage == 1 else 'Tage' }}){% endif %}</h2>
{% if not tage %}<div class="karte"><p class="leise" style="margin:0">Erinnerung ist aus.</p></div>
{% elif faellig %}<div class="karte" style="padding:4px 14px"><ul class="menue">
  {% for b in faellig %}<li><a href="{{ url_for('bestellung', oid=b.id) }}"><span>{{ b.kunde }}<br>
    <span class="leise" style="font-weight:400">geliefert vor {{ b.tage }} {{ 'Tag' if b.tage == 1 else 'Tagen' }}</span></span>
    <span class="rechts"><span class="marke warn">{{ euro(b.offen_cent) }}</span></span></a></li>{% endfor %}
</ul></div>
{% else %}<div class="karte"><p class="leise" style="margin:0">Nichts überfällig.</p></div>{% endif %}"""
        return seite(vorlage, "Zahlungserinnerung", tage=tage, uhrzeit=vk.einstellung("erinnerung_uhrzeit"),
                     ziel=vk.einstellung("erinnerung_ziel"), handys=handys, handy_fehler=handy_fehler,
                     faellig=vk.ueberfaellig() if tage else [])

    # ======================= Notizen =======================
    NOTIZEN = """
{% for n in notizen %}<div class="karte notiz">
  <div style="display:flex;gap:10px;align-items:flex-start">
    <div style="flex:1;min-width:0">
      {% if n.kunde %}<a href="{{ url_for('kunde', kid=n.kunde_id) }}"><b>{{ n.kunde }}</b></a>{% endif %}
      <p style="margin:2px 0 4px;white-space:pre-wrap">{{ n.text }}</p>
      <span class="leise">{{ de(n.erstellt[:10]) }}</span>
    </div>
    <form method="post" action="{{ url_for('notiz_erledigt', vid=n.id) }}"><input type="hidden" name="zurueck" value="{{ notiz_zurueck or 'notizen' }}">
      <button class="neben klein" title="Erledigt">✓ Erledigt</button></form>
  </div>
  {% if n.kunde_id %}<p style="margin:10px 0 0"><a href="{{ url_for('bestellung_neu', kunde=n.kunde_id) }}">Bestellung für {{ n.kunde }} anlegen ›</a></p>{% endif %}
</div>{% endfor %}"""

    @app.get("/notizen")
    def notizen():
        vorlage = """
<form class="karte" method="post" action="{{ url_for('notiz_neu') }}">
  <label>Notiz<textarea name="text" rows="3" maxlength="500" required
    placeholder="z. B. Wenn Schwein da ist: ein ganzes, zerlegt"></textarea></label>
  <div class="form-zeile" style="margin-top:10px">
    <label>Kunde (freiwillig)<select name="kunde"><option value="">– kein Kunde –</option>
      {% for k in kunden %}<option value="{{ k.id }}">{{ k.name }}</option>{% endfor %}
      <option value="neu">Neuer Kunde …</option></select></label>
    <label>Name bei neuem Kunden<input name="neuer_kunde" maxlength="80"></label>
  </div>
  <p><button class="gross">Notiz speichern</button></p>
</form>
<h2>Offen</h2>
{% if notizen %}""" + NOTIZEN + """{% else %}<div class="karte"><p class="leise" style="margin:0">Keine offenen Notizen.</p></div>{% endif %}
{% if erledigt %}<h2>Erledigt</h2>
<div class="karte" style="padding:4px 14px">{% for n in erledigt %}
  <div style="display:flex;gap:10px;align-items:center;padding:10px 0;{{ 'border-top:1px solid var(--linie)' if not loop.first }}">
    <span style="flex:1;min-width:0"><s class="leise">{{ n.text }}</s>{% if n.kunde %}<br><span class="leise">{{ n.kunde }}</span>{% endif %}</span>
    <form method="post" action="{{ url_for('notiz_loeschen', vid=n.id) }}" onsubmit="return confirm('Notiz löschen?')">
      <button class="neben klein" aria-label="Löschen">{{ eimer|safe }}</button></form>
  </div>{% endfor %}</div>{% endif %}"""
        return seite(vorlage, "Notizen", notizen=vk.vormerkungen(), erledigt=vk.vormerkungen(offen=False, anzahl=20),
                     kunden=vk.kunden())

    @app.post("/notizen/neu")
    def notiz_neu():
        f = request.form

        def tun():
            kid = f.get("kunde") or None
            if kid == "neu":
                kid, _ = vk.kunde_anlegen(f.get("neuer_kunde"))
            vk.vormerkung_anlegen(f.get("text"), kunde_id=kid)
            return "Notiz gespeichert."
        return formular(("notizen", {}), tun)

    @app.post("/notizen/<int:vid>/erledigt")
    def notiz_erledigt(vid):
        try:
            vk.vormerkung_erledigen(vid)
        except Fehler:
            pass
        ziel = request.form.get("zurueck", "")
        if ziel == "heute":
            return redirect(url_for("heute", m="Notiz erledigt."), 303)
        if ziel.startswith("kunde:") and ziel[6:].isdigit():
            return redirect(url_for("kunde", kid=int(ziel[6:]), m="Notiz erledigt."), 303)
        return redirect(url_for("notizen", m="Erledigt."), 303)

    @app.post("/notizen/<int:vid>/loeschen")
    def notiz_loeschen(vid):
        vk.vormerkung_loeschen(vid)
        return redirect(url_for("notizen", m="Gelöscht."), 303)

    # ======================= Packliste =======================
    def _packliste(ids):
        """Ausgewählte offene Bestellungen mit dem, was noch zu liefern ist, und die Gesamtmengen."""
        liste, wurst, fleisch = [], {}, {}
        for oid in ids:
            try:
                b = vk.bestellung(oid)
            except Fehler:
                continue
            if b["status"] != "offen":
                continue
            b["rest_wurst"] = [(z["produktname"], z["menge"] - z["ausgeliefert"]) for z in b["wurst"]
                               if z["menge"] > z["ausgeliefert"]]
            b["rest_fleisch"] = [f for f in b["fleisch"] if not f["ausgeliefert"]]
            for name, n in b["rest_wurst"]:
                wurst[name] = wurst.get(name, 0) + n
            for f in b["rest_fleisch"]:
                k = f"{f['art']} {f['teil']}"
                fleisch[k] = fleisch.get(k, 0) + 1
            liste.append(b)
        return liste, sorted(wurst.items()), sorted(fleisch.items())

    def _packtext(liste, wurst, fleisch):
        text = ["GESAMT"] + [f"{n} × {name}" for name, n in wurst] + [f"{n} Tüte(n) {name}" for name, n in fleisch]
        for b in liste:
            text += ["", f"{b['kunde']} (#{b['id']})"
                     + (f" – kassieren {euro(b['offen_cent'])}" if b["offen_cent"] else " – bezahlt")]
            text += [f"  {n} × {name}" for name, n in b["rest_wurst"]]
            text += [f"  {f['art']} {f['teil']} {f['code']}" for f in b["rest_fleisch"]]
        return "\n".join(text)

    def _gewaehlt():
        return [int(x) for x in request.values.getlist("b") if str(x).isdigit()]

    @app.post("/packliste/speichern")
    def packliste_speichern():
        ids = vk.packliste_setzen(_gewaehlt())
        if not ids:
            return redirect(url_for("packliste", neu=1, m="Bitte mindestens eine Bestellung wählen.", f=1), 303)
        return redirect(url_for("packliste", m="Packliste gespeichert. Sie steht jetzt auch auf „Heute“."), 303)

    @app.post("/packliste/leeren")
    def packliste_leeren():
        vk.packliste_setzen([])
        return redirect(url_for("packliste", neu=1, m="Packliste gelöscht."), 303)

    @app.get("/packliste")
    def packliste():
        ids = _gewaehlt()
        gespeichert = vk.packliste_ids()
        if not ids and not request.args.get("neu"):
            ids = gespeichert
        if not ids:
            vorlage = """
<p class="leise">Wähle die Bestellungen, die du ausliefern willst.</p>
<form method="post" action="{{ url_for('packliste_speichern') }}">
<div class="karte">
  {% for b in offen %}<label class="haken"><input type="checkbox" name="b" value="{{ b.id }}" {{ 'checked' if b.id in gespeichert }}>
    <span><b>{{ b.kunde }}</b> <span class="leise">#{{ b.id }} · {{ de(b.datum) }}</span><br>
    <span class="leise">{{ b.posten }}</span></span></label>
  {% else %}<p class="leise">Keine offenen Bestellungen.</p>{% endfor %}
</div>
{% if offen %}<p class="zeile"><button type="button" class="neben" onclick="var c=this.form.querySelectorAll('input[name=b]');
  var alle=[].every.call(c,function(x){return x.checked});c.forEach(function(x){x.checked=!alle})">Alle / keine</button>
  <button class="gross">Packliste speichern</button></p>{% endif %}
</form>"""
            offen = vk.bestellungen("nicht_ausgeliefert")
            for b in offen:
                teile = [f"{z['menge'] - z['ausgeliefert']} × {z['produktname']}" for z in b["wurst"] if z["menge"] > z["ausgeliefert"]]
                teile += [f"{f['art']} {f['teil']}" for f in b["fleisch"] if not f["ausgeliefert"]]
                b["posten"] = ", ".join(teile)
            offen.sort(key=lambda b: b["kunde"].casefold())
            return seite(vorlage, "Packliste", offen=offen, gespeichert=gespeichert)
        liste, wurst, fleisch = _packliste(ids)
        vorlage = """
<a class="zurueck" href="{{ url_for('packliste', neu=1) }}">{{ pfeil|safe }} Auswahl ändern</a>
{% if gespeichert_ist %}<p class="leise" style="margin:0 4px 6px">Gespeichert. Gelieferte Bestellungen fallen von selbst heraus.</p>{% endif %}
<h2>Gesamt für {{ liste|length }} Bestellung{{ 'en' if liste|length != 1 }}</h2>
<div class="karte rollbar"><table class="knapp">
{% for name, n in wurst %}<tr><td class="umbruch">{{ name }}</td><td class="zahl"><b>{{ n }}</b></td></tr>{% endfor %}
{% for name, n in fleisch %}<tr><td class="umbruch">{{ name }}</td><td class="zahl"><b>{{ n }}</b> {{ 'Tüte' if n == 1 else 'Tüten' }}</td></tr>{% endfor %}
{% if not wurst and not fleisch %}<tr><td class="leise">Nichts mehr zu liefern.</td></tr>{% endif %}
</table></div>
<h2>Einzeln</h2>
{% for b in liste %}<div class="karte">
  <p><a href="{{ url_for('bestellung', oid=b.id) }}"><b>{{ b.kunde }}</b></a> <span class="leise">#{{ b.id }}</span>
  {% if b.offen_cent %}<span style="float:right">kassieren <b>{{ euro(b.offen_cent) }}</b>{% if b.preis_offen %} +{% endif %}</span>
  {% else %}<span class="ok" style="float:right">✓ bezahlt</span>{% endif %}</p>
  <ul class="posten">{% for name, n in b.rest_wurst %}<li>{{ n }} × {{ name }}</li>{% endfor %}
  {% for f in b.rest_fleisch %}<li>{{ f.art }} {{ f.teil }} <span class="leise">{{ f.code }}{{ (' · ' ~ f.gewicht_g ~ ' g') if f.gewicht_g }}</span></li>{% endfor %}</ul>
</div>{% endfor %}
<h2>Kalendereintrag</h2>
<form class="karte form-zeile" method="get" action="{{ url_for('packliste_ics') }}">
  {% for b in liste %}<input type="hidden" name="b" value="{{ b.id }}">{% endfor %}
  <label>Datum<input type="date" name="datum" value="{{ heute }}" required></label>
  <label>Uhrzeit<input type="time" name="zeit" value="17:00" required></label>
  <label>Dauer (Min.)<input type="number" name="dauer" value="60" min="15" max="600" step="15" inputmode="numeric"></label>
  <button class="neben">Termin herunterladen</button>
</form>
<p class="leise">Die Kalenderdatei funktioniert im Handy-Browser, aber nicht in der Home-Assistant-App.
  Dort die Liste kopieren oder teilen und im Kalender in die Notiz einfügen.</p>
<div class="karte">
  <textarea id="packtext" rows="8" style="width:100%;font-size:.9rem">{{ packtext }}</textarea>
  <p class="zeile" style="gap:8px;margin-top:8px">
    <button type="button" class="neben" id="kopieren">Kopieren</button>
    <button type="button" class="neben" id="teilen" hidden>Teilen …</button>
  </p>
  <p class="leise" id="kopiert" hidden></p>
</div>
<script>
(function () {
  var t = document.getElementById("packtext"), hinweis = document.getElementById("kopiert");
  function melden(text) { hinweis.textContent = text; hinweis.hidden = false; }
  document.getElementById("kopieren").addEventListener("click", function () {
    var fertig = function () { melden("✓ Kopiert. Jetzt im Kalender in die Notiz einfügen."); };
    var vonHand = function () {
      t.focus(); t.select(); t.setSelectionRange(0, t.value.length);
      var ok = false; try { ok = document.execCommand("copy"); } catch (e) {}
      ok ? fertig() : melden("Kopieren wurde blockiert: Text im Feld lange drücken, „Alles auswählen“, „Kopieren“.");
    };
    if (navigator.clipboard && window.isSecureContext) navigator.clipboard.writeText(t.value).then(fertig, vonHand);
    else vonHand();
  });
  var teilen = document.getElementById("teilen");
  if (navigator.share) {
    teilen.hidden = false;
    teilen.addEventListener("click", function () {
      navigator.share({ title: "Packliste", text: t.value }).catch(function () {});
    });
  }
})();
</script>
{% if liste %}<h2>Ausliefern</h2>
<form class="karte" method="post" action="{{ url_for('packliste_ausliefern') }}"
  onsubmit="return confirm('Alle {{ liste|length }} Bestellungen als geliefert buchen? Die Ware verlässt das Lager.')">
  {% for b in liste %}<input type="hidden" name="b" value="{{ b.id }}">{% endfor %}
  <button class="gross">Alle als geliefert buchen</button></form>{% endif %}
{% if gespeichert_ist %}<form method="post" action="{{ url_for('packliste_leeren') }}" onsubmit="return confirm('Packliste löschen? Die Bestellungen bleiben erhalten.')">
  <p><button class="neben" style="width:100%">Packliste löschen</button></p></form>{% endif %}"""
        return seite(vorlage, "Packliste", liste=liste, wurst=wurst, fleisch=fleisch, heute=vk._heute(),
                     gespeichert_ist=sorted(ids) == sorted(gespeichert),
                     packtext=_packtext(liste, wurst, fleisch))

    def _ics_text(t):
        return t.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")

    def _falten(zeile):
        """Kalenderzeilen dürfen höchstens 75 Byte lang sein."""
        teile, rest = [], zeile.encode("utf-8")
        while len(rest) > (75 if not teile else 74):
            n = 75 if not teile else 74
            while (rest[n] & 0xC0) == 0x80:  # kein UTF-8-Zeichen zerteilen
                n -= 1
            teile.append(rest[:n].decode("utf-8"))
            rest = rest[n:]
        teile.append(rest.decode("utf-8"))
        return "\r\n ".join(teile)

    @app.get("/packliste.ics")
    def packliste_ics():
        import re as _re
        from datetime import datetime, timedelta, timezone
        from flask import Response
        liste, wurst, fleisch = _packliste(_gewaehlt())
        datum, zeit = request.args.get("datum", ""), request.args.get("zeit", "17:00")
        if not _re.fullmatch(r"\d{4}-\d{2}-\d{2}", datum) or not _re.fullmatch(r"\d{2}:\d{2}", zeit):
            abort(400)
        try:
            dauer = max(15, min(600, int(request.args.get("dauer") or 60)))
            start = datetime.strptime(f"{datum} {zeit}", "%Y-%m-%d %H:%M")
        except ValueError:
            abort(400)
        ende = start + timedelta(minutes=dauer)
        text = _packtext(liste, wurst, fleisch).split("\n")
        kunden = ", ".join(b["kunde"] for b in liste)
        zeilen = [
            "BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//Wildkammer//Packliste//DE", "CALSCALE:GREGORIAN",
            "BEGIN:VEVENT",
            f"UID:packliste-{start:%Y%m%d%H%M}-{'-'.join(str(b['id']) for b in liste)}@wildkammer",
            f"DTSTAMP:{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}",
            f"DTSTART:{start:%Y%m%dT%H%M%S}", f"DTEND:{ende:%Y%m%dT%H%M%S}",
            "SUMMARY:" + _ics_text(f"Wurst ausliefern: {kunden}" if len(kunden) <= 60 else f"Wurst ausliefern ({len(liste)} Bestellungen)"),
            "DESCRIPTION:" + _ics_text("\n".join(text)),
            "END:VEVENT", "END:VCALENDAR",
        ]
        inhalt = "\r\n".join(_falten(z) for z in zeilen) + "\r\n"
        return Response(inhalt.encode("utf-8"), content_type="text/calendar; charset=utf-8",
                        headers={"Content-Disposition": f"attachment; filename=packliste-{datum}.ics"})

    @app.post("/packliste/ausliefern")
    def packliste_ausliefern():
        ids, ok, fehler = _gewaehlt(), 0, []
        for oid in ids:
            try:
                vk.ausliefern(oid)
                ok += 1
            except Fehler as e:
                fehler.append(f"#{oid}: {FEHLERTEXT.get(e.kennwort, e.kennwort)}")
        text = f"{ok} Bestellung{'en' if ok != 1 else ''} ausgeliefert." + (" " + "; ".join(fehler) + "." if fehler else "")
        return redirect(url_for("bestellungen", filter="alle", m=text, **({"f": "1"} if fehler else {})), 303)

    @app.get("/w/<int:nummer>")
    def wurstpaket(nummer):
        w = vk.wurstpaket(nummer)
        if not w:
            abort(404)
        vorlage = """
<a class="zurueck" href="{{ url_for('wurst') }}">{{ pfeil|safe }} Zurück zum Wurstlager</a>
<div class="karte">
  <p class="leise">{{ pcode }} · hergestellt {{ de(w.erstellt[:10]) }}</p>
  <p class="etikett"><a href="{{ url_for('wurst_produkt', pid=w.produkt_id) }}">{{ w.name }}</a></p>
  {% if w.status == 'lager' %}<p><span class="ok">Im Lager</span></p>
  <form method="post" action="{{ url_for('wurstpaket_aus', nummer=w.id) }}">
    <label>Grund<select name="grund">{% for g in ['Eigenverbrauch', 'Verkauf ohne Bestellung', 'Geschenk', 'Probe', 'Verdorben', 'Sonstiges'] %}
      <option>{{ g }}</option>{% endfor %}</select></label>
    <p><button class="gross rot">Packung ausbuchen</button></p>
  </form>
  <p class="leise">Für Packungen an Kunden mit Bestellung stattdessen die Bestellung ausliefern, sonst zählt sie doppelt.</p>
  {% else %}<p><b>Ausgebucht</b> am {{ de(w.raus[:10]) }} · {{ w.grund }}</p>
  <form method="post" action="{{ url_for('wurstpaket_zurueck', nummer=w.id) }}"
    onsubmit="return confirm('Packung wieder ins Lager buchen?')">
    <button class="neben">Versehen – zurück ins Lager</button></form>{% endif %}
</div>"""
        return seite(vorlage, wurst_code(nummer), w=w, pcode=wurst_code(nummer))

    @app.post("/w/<int:nummer>/aus")
    def wurstpaket_aus(nummer):
        return formular(("wurstpaket", {"nummer": nummer}),
                        lambda: (vk.wurstpaket_entnehmen(nummer, request.form.get("grund")), "Ausgebucht.")[1])

    @app.post("/w/<int:nummer>/zurueck")
    def wurstpaket_zurueck(nummer):
        return formular(("wurstpaket", {"nummer": nummer}),
                        lambda: (vk.wurstpaket_zurueck(nummer), "Wieder im Lager.")[1])

    @app.post("/wurst/aendern")
    def wurst_aendern_mehrere():
        f = request.form
        posten = {int(k[1:]): v.strip() for k, v in f.items() if k[:1] == "n" and k[1:].isdigit() and v.strip()}

        def tun():
            rein, raus = vk.wurst_aenderungen(posten, f.get("grund"))
            teile = ([f"{rein} eingebucht"] if rein else []) + ([f"{raus} entnommen"] if raus else [])
            return "Stück: " + ", ".join(teile) + "."
        return formular(("wurst", {}), tun)

    @app.post("/wurst/buchen")
    def wurst_buchen():
        f = request.form
        art = f.get("art")
        posten = {int(k[1:]): v.strip() for k, v in f.items() if k[:1] == "n" and k[1:].isdigit() and v.strip()}

        def tun():
            n = vk.wurst_buchen_mehrere(posten, art, f.get("grund"))
            return f"{n} {'Packung' if n == 1 else 'Packungen'} " + ("eingebucht." if art == "zugang" else "entnommen.")
        return formular(("wurst", {}), tun)

    @app.post("/wurst/entnahme")
    def wurst_entnahme():
        f = request.form

        def tun():
            try:
                pid = int(f.get("produkt", ""))
            except ValueError:
                raise Fehler("produkt_unbekannt")
            neu = vk.wurst_buchen(pid, f.get("menge"), "entnahme", f.get("grund"))
            return f"Entnommen. Neuer Bestand: {neu}."
        return formular(("wurst", {}), tun)

    @app.post("/wurst/<int:pid>/zugang")
    def wurst_zugang(pid):
        return formular(("wurst", {}), lambda: f"Neuer Bestand: {vk.wurst_buchen(pid, request.form.get('menge'), 'zugang')}.")

    @app.get("/wurst/<int:pid>")
    def wurst_produkt(pid):
        p = vk.produkt(pid)
        if not p:
            abort(404)
        vorlage = """
<a class="zurueck" href="{{ url_for('wurst') }}">{{ pfeil|safe }} Zurück zum Wurstlager</a>
<div class="karte zahlen">
  <div class="zahl"><b>{{ p.frei }}</b><span class="leise">frei</span></div>
  <div class="zahl"><b>{{ p.reserviert }}</b><span class="leise">reserviert</span></div>
  <div class="zahl"><b>{{ p.bestand }}</b><span class="leise">im Lager</span></div>
</div>
<h2>Produkt</h2>
<form class="karte form-zeile" method="post" action="{{ url_for('wurst_aendern', pid=p.id) }}">
  <label>Art<select name="kategorie">{% for k, n in kategorien.items() %}
    <option value="{{ k }}" {{ 'selected' if p.kategorie == k }}>{{ n }}</option>{% endfor %}</select></label>
  <label>Name<input name="name" value="{{ p.name }}" required maxlength="60"></label>
  <label>Einheit<input name="einheit" value="{{ p.einheit }}" required></label>
  <label>Preis (€)<input name="preis" inputmode="decimal" value="{{ '%.2f' % (p.preis_cent / 100) }}"></label>
  <label>Aktiv<select name="aktiv"><option value="1" {{ 'selected' if p.aktiv }}>Ja</option>
    <option value="0" {{ 'selected' if not p.aktiv }}>Nein</option></select></label>
  <button>Speichern</button>
</form>
<p class="leise">Ein neuer Preis gilt nur für neue Bestellungen.</p>
<h2>Inventurkorrektur</h2>
<form class="karte form-zeile" method="post" action="{{ url_for('wurst_korrektur', pid=p.id) }}">
  <label>Abweichung (z. B. -2)<input name="menge" type="number" required></label>
  <label>Grund<input name="grund" required placeholder="Gezählt, verdorben …"></label>
  <button class="neben">Korrektur buchen</button>
</form>
<h2>Bewegungen</h2>
<div class="karte rollbar"><table><tr><th>Zeit</th><th class="zahl">Menge</th><th>Art</th><th>Grund</th></tr>
{% for b in bewegungen %}<tr><td>{{ b.erstellt[:16].replace('T', ' ') }}</td><td class="zahl">{{ '%+d' % b.menge }}</td>
<td>{{ b.art }}</td><td>{{ b.grund }}</td></tr>{% endfor %}</table></div>"""
        return seite(vorlage, p["name"], p=p, bewegungen=vk.bewegungen(pid, 50))

    @app.post("/wurst/<int:pid>/aendern")
    def wurst_aendern(pid):
        f = request.form
        return formular(("wurst_produkt", {"pid": pid}), lambda: (vk.produkt_aendern(
            pid, f.get("name"), f.get("einheit"), f.get("preis"), f.get("aktiv") == "1", f.get("kategorie")),
            "Gespeichert.")[1])

    @app.post("/wurst/<int:pid>/korrektur")
    def wurst_korrektur(pid):
        f = request.form
        return formular(("wurst_produkt", {"pid": pid}),
                        lambda: f"Neuer Bestand: {vk.wurst_buchen(pid, f.get('menge'), 'korrektur', f.get('grund'))}.")

    @app.route("/preise", methods=["GET", "POST"])
    def preise():
        if request.method == "POST":
            f = request.form
            return formular(("preise", {}), lambda: (vk.fleischpreis_setzen(
                f.get("art"), f.get("teil"), f.get("preis")), "Kilopreis gespeichert.")[1])
        vorlage = """
<h2>Kilopreise für Fleisch</h2>
<p class="leise">Der Preis einer Tüte ergibt sich aus Kilopreis und Gewicht. Ohne Kilopreis oder Gewicht bleibt er offen.
Ein Preis für „Reh“ gilt auch für „Reh Bock“, solange dort kein eigener steht.</p>
<form class="karte form-zeile" method="post">
  <label>Wildart<input name="art" list="arten" required></label>
  <label>Teilstück<input name="teil" list="teile" required></label>
  <label>€ pro kg (leer = löschen)<input name="preis" inputmode="decimal"></label>
  <button>Speichern</button>
</form>
<datalist id="arten">{% for a in arten %}<option value="{{ a }}">{% endfor %}</datalist>
<datalist id="teile">{% for t in teile %}<option value="{{ t }}">{% endfor %}</datalist>
<div class="karte rollbar"><table><tr><th>Wildart</th><th>Teilstück</th><th class="zahl">€/kg</th></tr>
{% for p in preise %}<tr><td>{{ p.art }}</td><td>{{ p.teil }}</td><td class="zahl">{{ euro(p.preis_kg_cent) }}</td></tr>
{% else %}<tr><td colspan="3" class="leise">Noch keine Kilopreise.</td></tr>{% endfor %}</table></div>"""
        frei = vk.fleisch_frei()
        arten = sorted({f["art"] for f in frei} | {f["art"].split(" ")[0] for f in frei})
        return seite(vorlage, "Kilopreise", preise=vk.fleischpreise(), arten=arten,
                     teile=sorted({f["teil"] for f in frei}))

    @app.get("/kunden")
    def kunden():
        vorlage = """
<div class="karte rollbar"><table class="knapp"><tr><th>Name</th><th class="zahl">Offen</th></tr>
{% for k in kunden %}<tr><td class="umbruch"><a href="{{ url_for('kunde', kid=k.id) }}">{{ k.name }}</a>
  {% if k.telefon %}<br><a class="leise" style="font-weight:400" href="tel:{{ k.telefon|replace(' ', '') }}">{{ k.telefon }}</a>{% endif %}</td>
<td class="zahl">{{ euro(k.offen_cent) if k.offen_cent else '–' }}</td></tr>
{% else %}<tr><td colspan="2" class="leise">Noch keine Kunden.</td></tr>{% endfor %}</table></div>
<h2>Neuer Kunde</h2>
<form class="karte form-zeile" method="post" action="{{ url_for('kunde_neu') }}">
  <label>Name<input name="name" required maxlength="80"></label>
  <label>Telefon<input name="telefon" type="tel"></label>
  <button>Kunde anlegen</button>
</form>
"""
        return seite(vorlage, "Kunden", kunden=vk.kunden())

    @app.post("/kunden/neu")
    def kunde_neu():
        f = request.form

        def anlegen():
            kid, neu = vk.kunde_anlegen(f.get("name"), f.get("telefon"))
            return "Kunde angelegt." if neu else "Diesen Kunden gibt es schon."
        return formular(("kunden", {}), anlegen)

    @app.route("/kunden/<int:kid>", methods=["GET", "POST"])
    def kunde(kid):
        k = vk.kunde(kid)
        if not k:
            abort(404)
        if request.method == "POST":
            f = request.form
            return formular(("kunde", {"kid": kid}), lambda: (vk.kunde_aendern(
                kid, f.get("name"), f.get("telefon"), f.get("email"), f.get("adresse"), f.get("notiz")),
                "Gespeichert.")[1])
        vorlage = """
<a class="zurueck" href="{{ url_for('kunden') }}">{{ pfeil|safe }} Zurück zu den Kunden</a>
<form class="karte form-zeile" method="post">
  <label>Name<input name="name" value="{{ k.name }}" required></label>
  <label>Telefon<input name="telefon" type="tel" value="{{ k.telefon }}"></label>
  <label>E-Mail<input name="email" type="email" value="{{ k.email }}"></label>
  <label>Adresse<input name="adresse" value="{{ k.adresse }}"></label>
  <label>Notiz<input name="notiz" value="{{ k.notiz }}"></label>
  <button>Speichern</button>
</form>
<p><a class="knopf" href="{{ url_for('bestellung_neu', kunde=k.id) }}">Neue Bestellung für {{ k.name }}</a></p>
{% if notizen %}<h2>Notizen</h2>""" + NOTIZEN + """{% endif %}
<h2>Bestellungen</h2>
{% set liste = bestellungen %}{% include_tabelle %}
{% if andere or not bestellungen %}<details class="karte"><summary><b>Doppelt angelegt oder Tippfehler?</b></summary>
{% if andere %}<form class="form-zeile" method="post" action="{{ url_for('kunde_zusammenfuehren', kid=k.id) }}"
  onsubmit="return confirm('Alle Bestellungen von {{ k.name|e }} auf den gewählten Kunden übertragen?')">
  <label>Bestellungen übertragen auf<select name="nach" required>
    <option value="" disabled selected>Bitte wählen</option>
    {% for a in andere %}<option value="{{ a.id }}">{{ a.name }}</option>{% endfor %}</select></label>
  <button class="neben">Zusammenführen</button></form>
<p class="leise">{{ k.name }} verschwindet danach aus der Kundenliste.</p>{% endif %}
{% if not bestellungen %}<form method="post" action="{{ url_for('kunde_loeschen', kid=k.id) }}"
  onsubmit="return confirm('{{ k.name|e }} löschen?')"><button class="gefahr">Kunden löschen</button></form>{% endif %}
</details>{% endif %}"""
        return seite(vorlage.replace("{% include_tabelle %}", TABELLE), k["name"], k=k,
                     bestellungen=vk.bestellungen("alle", kid), zurueck_zu=url_for("kunde", kid=kid),
                     andere=[a for a in vk.kunden() if a["id"] != kid],
                     notizen=vk.vormerkungen(kunde_id=kid), notiz_zurueck=f"kunde:{kid}")

    @app.post("/kunden/<int:kid>/zusammenfuehren")
    def kunde_zusammenfuehren(kid):
        try:
            nach = int(request.form.get("nach", 0))
            vk.kunden_zusammenfuehren(kid, nach)
        except ValueError:
            return zurueck(("kunde", {"kid": kid}), "Bitte einen Kunden wählen.", True)
        except Fehler as e:
            return zurueck(("kunde", {"kid": kid}), FEHLERTEXT.get(e.kennwort, e.kennwort) + ".", True)
        return zurueck(("kunde", {"kid": nach}), "Kunden zusammengeführt.")

    @app.post("/kunden/<int:kid>/loeschen")
    def kunde_loeschen(kid):
        try:
            vk.kunde_loeschen(kid)
        except Fehler as e:
            return zurueck(("kunde", {"kid": kid}), FEHLERTEXT.get(e.kennwort, e.kennwort) + ".", True)
        return zurueck(("kunden", {}), "Kunde gelöscht.")

    TABELLE = """
<div class="karte rollbar"><table class="knapp">
<tr><th>Bestellung</th><th class="zahl">Summe</th><th>Status</th></tr>
{% for b in liste %}<tr>
  <td class="umbruch"><a href="{{ url_for('bestellung', oid=b.id) }}"><b>{{ b.kunde }}</b></a><br>
    <span class="leise">#{{ b.id }} · {{ de(b.datum) }}</span></td>
  <td class="zahl">{{ euro(b.summe_cent) }}{% if b.preis_offen %} +{% endif %}</td>
  <td><div class="status">{% if b.status == 'storniert' %}<span class="leise">storniert</span>{% else %}
      {% if b.bezahlt %}<span class="ok">✓ bezahlt</span>
      {% elif b.preis_offen %}<span class="leise">Preis offen</span>
      {% else %}<form method="post" action="{{ url_for('bestellung_bezahlt', oid=b.id) }}">
      <input type="hidden" name="zurueck" value="{{ zurueck_zu }}"><button class="klein neben">bezahlt</button></form>{% endif %}
      {% if b.status == 'ausgeliefert' %}<span class="ok">✓ geliefert</span>
      {% else %}<form method="post" action="{{ url_for('bestellung_ausgeliefert', oid=b.id) }}"
        onsubmit="return confirm('{{ b.kunde|e }}: alles als geliefert buchen?')">
      <input type="hidden" name="zurueck" value="{{ zurueck_zu }}"><button class="klein neben">geliefert</button></form>{% endif %}
      {% endif %}</div></td>
</tr>{% else %}<tr><td colspan="4" class="leise">Keine Bestellungen.</td></tr>{% endfor %}
</table></div>"""

    @app.get("/bestellungen")
    def bestellungen():
        f = request.args.get("filter", "offen")
        if f not in ("offen", "unbezahlt", "nicht_ausgeliefert", "abgeschlossen", "alle"):
            f = "offen"
        vorlage = """
<div class="karte zahlen">
  <div class="zahl"><b>{{ euro(u.umsatz_cent) }}</b><span class="leise">Umsatz</span></div>
  <div class="zahl"><b>{{ euro(u.bezahlt_cent) }}</b><span class="leise">bezahlt</span></div>
  <div class="zahl"><b>{{ euro(u.offen_cent) }}</b><span class="leise">offen</span></div>
  <div class="zahl"><b>{{ u.nicht_ausgeliefert }}</b><span class="leise">nicht ausgeliefert</span></div>
</div>
{% if u.preis_offen %}<p class="leise">{{ u.preis_offen }} Bestellung(en) enthalten Fleisch ohne Preis („+“).</p>{% endif %}
<div class="zeile" style="margin:12px 0"><a class="knopf" href="{{ url_for('bestellung_neu') }}">Neue Bestellung</a>
  <a class="knopf" href="{{ url_for('packliste') }}">Packliste</a>
  <a class="knopf" href="{{ url_for('notizen') }}">Notizen{% if anzahl_notizen %} ({{ anzahl_notizen }}){% endif %}</a></div>
<div class="reiter">{% for w, n in [('offen','Offen'),('unbezahlt','Unbezahlt'),('nicht_ausgeliefert','Nicht ausgeliefert'),('abgeschlossen','Abgeschlossen'),('alle','Alle')] %}
<a class="{{ 'an' if filter == w }}" href="{{ url_for('bestellungen', filter=w) }}">{{ n }}</a>{% endfor %}</div>
{% set liste = bestellungen %}""" + TABELLE
        return seite(vorlage, "Bestellungen", anzahl_notizen=len(vk.vormerkungen()), u=vk.umsatz(), bestellungen=vk.bestellungen(f), filter=f,
                     zurueck_zu=url_for("bestellungen", filter=f))

    @app.route("/bestellungen/neu", methods=["GET", "POST"])
    def bestellung_neu():
        if request.method == "POST":
            f = request.form
            positionen = []
            for p in vk.produkte():
                n = f.get(f"w{p['id']}", "").strip()
                if n and n != "0":
                    positionen.append({"produkt_id": p["id"], "menge": n})
            for schluessel, n in f.items():
                # Feldname "f:<Wildart>:<Teilstück>" bleibt stabil, auch wenn sich das Lager inzwischen ändert.
                if schluessel.startswith("f:") and n.strip() not in ("", "0") and schluessel.count(":") >= 2:
                    _, art, teil = schluessel.split(":", 2)
                    positionen.append({"wildart": art, "teil": teil, "menge": n.strip()})
            if not positionen:
                return zurueck(("bestellung_neu", {}), "Bitte mindestens eine Menge eingeben.", True)
            try:
                kid = f.get("kunde")
                if kid == "neu":
                    kid, _ = vk.kunde_anlegen(f.get("neuer_kunde"))
                b = vk.bestellung_anlegen(positionen, kunde_id=kid)
            except Fehler as e:
                text = FEHLERTEXT.get(e.kennwort, e.kennwort)
                if "ware" in e.info:
                    text += f": {e.info['ware']} (frei: {e.info.get('frei', '?')})"
                return zurueck(("bestellung_neu", {}), text + ".", True)
            return redirect(url_for("bestellung", oid=b["id"], m="Bestellung angelegt."), 303)
        vorlage = """
<a class="zurueck" href="{{ url_for('bestellungen') }}">{{ pfeil|safe }} Zurück zu den Bestellungen</a>
<form method="post">
<div class="karte form-zeile">
  <label>Kunde<select name="kunde" required>
    <option value="" disabled {{ 'selected' if not vorauswahl }}>Bitte wählen</option>
    {% for k in kunden %}<option value="{{ k.id }}" {{ 'selected' if vorauswahl == k.id }}>{{ k.name }}</option>{% endfor %}
    <option value="neu">Neuer Kunde …</option></select></label>
  <label>Name bei neuem Kunden<input name="neuer_kunde" maxlength="80"></label>
</div>
<h2>Wurst und Honig</h2>
<div class="karte rollbar"><table class="knapp">
{% for p in produkte %}{% if loop.first or p.kategorie != loop.previtem.kategorie %}
<tr class="gruppe"><th>{{ kategorien[p.kategorie] }}</th><th>Menge</th></tr>{% endif %}<tr><td class="umbruch">{{ p.name }}<br><span class="leise">{{ p.frei }} frei · {{ euro(p.preis_cent) }}</span></td>
<td><input name="w{{ p.id }}" type="number" min="0" max="{{ [p.frei, 0]|max }}" inputmode="numeric"
  data-stepper data-leer placeholder="0" {{ 'disabled' if p.frei <= 0 }} aria-label="{{ p.name }}"></td></tr>{% endfor %}</table></div>
<h2>Fleisch (Tüten, älteste zuerst)</h2>
<div class="karte rollbar"><table class="knapp"><tr><th>Ware</th><th>Tüten</th></tr>
{% for g in fleisch %}<tr><td class="umbruch">{{ g.art }} {{ g.teil }}<br><span class="leise">{{ g.anzahl }} frei · älteste vom {{ de(g.aelteste) }}</span></td>
<td><input name="f:{{ g.art }}:{{ g.teil }}" type="number" min="0" max="{{ g.anzahl }}" inputmode="numeric"
  data-stepper data-leer placeholder="0" aria-label="{{ g.art }} {{ g.teil }}"></td></tr>
{% else %}<tr><td colspan="2" class="leise">Kein freies Fleisch im Lager.</td></tr>{% endfor %}</table></div>
<p><button class="gross">Bestellung speichern</button></p>
</form>"""
        try:
            vor = int(request.args.get("kunde", 0))
        except ValueError:
            vor = 0
        return seite(vorlage, "Neue Bestellung", kunden=vk.kunden(), produkte=vk.produkte(),
                     fleisch=vk.fleisch_frei(), vorauswahl=vor)

    @app.get("/bestellungen/<int:oid>")
    def bestellung(oid):
        try:
            b = vk.bestellung(oid)
        except Fehler:
            abort(404)
        vorlage = """
<a class="zurueck" href="{{ url_for('bestellungen') }}">{{ pfeil|safe }} Zurück zu den Bestellungen</a>
<div class="karte">
  <p class="leise">Bestellung #{{ b.id }} · {{ de(b.datum) }} · {{ status_text[b.status] }}</p>
  <p class="etikett"><a href="{{ url_for('kunde', kid=b.kunde_id) }}">{{ b.kunde }}</a></p>
  <div class="rollbar"><table class="knapp">
  <tr><th>Position</th><th class="zahl">Summe</th></tr>
  {% for z in b.wurst %}<tr><td class="umbruch">{{ z.menge }} × {{ z.produktname }}<br>
    <span class="leise">je {{ euro(z.einzelpreis_cent) }} · geliefert {{ z.ausgeliefert }} von {{ z.menge }}</span></td>
    <td class="zahl">{{ euro(z.menge * z.einzelpreis_cent) }}</td></tr>{% endfor %}
  {% for f in b.fleisch %}<tr><td class="umbruch">{{ f.art }} {{ f.teil }}<br>
    <span class="leise"><a href="{{ url_for('tuete', nummer=f.paket_id) }}">{{ f.code }}</a>
    · {{ (f.gewicht_g ~ ' g') if f.gewicht_g else 'ohne Gewicht' }} · {{ 'geliefert' if f.ausgeliefert else 'nicht geliefert' }}</span></td>
    <td class="zahl">{{ euro(f.preis_cent) }}</td></tr>{% endfor %}
  {% if b.rabatt_cent %}<tr><td>Rabatt</td><td class="zahl">− {{ euro(b.rabatt_cent) }}</td></tr>{% endif %}
  <tr><th>Gesamt</th><th class="zahl">{{ euro(b.summe_cent) }}</th></tr>
  </table></div>
  <p>Bezahlt {{ euro(b.bezahlt_cent) }} · Offen <b>{{ euro(b.offen_cent) }}</b>
     {% if b.preis_offen %}<br><span class="leise">Für einige Tüten fehlt Kilopreis oder Gewicht.</span>{% endif %}</p>
  {% if b.status != 'storniert' %}
  <div class="zeile">
    {% if not b.bezahlt and not b.preis_offen %}<form method="post" action="{{ url_for('bestellung_bezahlt', oid=b.id) }}">
      <button class="gross">Als bezahlt markieren</button></form>{% endif %}
    {% if b.status == 'offen' %}<form method="post" action="{{ url_for('bestellung_ausgeliefert', oid=b.id) }}"
      onsubmit="return confirm('Alles als geliefert buchen? Die Ware verlässt dann das Lager.')">
      <button class="gross neben">Alles ausliefern</button></form>{% endif %}
  </div>{% endif %}
</div>
{% if b.status != 'storniert' and not b.bezahlt %}
<h2>Teilzahlung oder freier Betrag</h2>
<form class="karte form-zeile" method="post" action="{{ url_for('bestellung_bezahlt', oid=b.id) }}">
  <label>Betrag (€)<input name="betrag" inputmode="decimal" required></label>
  <label>Art<input name="methode" placeholder="Bar, PayPal …"></label>
  <button class="neben">Buchen</button>
</form>{% endif %}
{% if b.status != 'storniert' %}<h2>Rabatt</h2>
<form class="karte form-zeile" method="post" action="{{ url_for('bestellung_rabatt', oid=b.id) }}">
  <label>Rabatt auf die ganze Bestellung (€)<input name="rabatt" inputmode="decimal"
    value="{{ ('%.2f' % (b.rabatt_cent / 100)).replace('.', ',') if b.rabatt_cent else '' }}" placeholder="0,00"></label>
  <button class="neben">Speichern</button>
</form>{% endif %}
{% if b.zahlungen %}<h2>Zahlungen</h2><div class="karte rollbar"><table class="knapp">
<tr><th>Zahlung</th><th class="zahl">Betrag</th><th></th></tr>
{% for z in b.zahlungen %}<tr><td class="umbruch">{{ de(z.datum[:10]) }}{% if z.methode %}<br><span class="leise">{{ z.methode }}</span>{% endif %}</td>
<td class="zahl">{{ euro(z.betrag_cent) }}</td><td><form class="inline" method="post" action="{{ url_for('zahlung_loeschen', oid=b.id, zid=z.id) }}"
  onsubmit="return confirm('Zahlung über {{ euro(z.betrag_cent) }} löschen?')">
  <button class="klein neben" aria-label="Zahlung löschen">{{ eimer|safe }}</button></form></td></tr>{% endfor %}
</table></div>{% endif %}
{% if b.status == 'offen' %}<h2>Bestellung ändern</h2>
<form class="karte" method="post" action="{{ url_for('bestellung_aendern', oid=b.id) }}">
  <div class="form-zeile"><label>Datum<input name="datum" type="date" value="{{ b.datum }}"></label></div>
  {% if b.wurst %}<p class="leise">Menge auf 0 setzen entfernt die Position.</p>
  <div class="rollbar"><table class="knapp">
  {% for z in b.wurst %}{% set pf = produkte|selectattr('id', 'equalto', z.produkt_id)|first %}
  <tr><td class="umbruch">{{ z.produktname }}{% if z.ausgeliefert %}<br>
    <span class="leise">mind. {{ z.ausgeliefert }} (schon geliefert)</span>{% endif %}</td>
    <td><input name="m{{ z.id }}" type="number" min="{{ z.ausgeliefert }}" inputmode="numeric" value="{{ z.menge }}"
      max="{{ z.menge + ([pf.frei, 0]|max if pf else 0) }}" data-stepper aria-label="{{ z.produktname }}"></td></tr>{% endfor %}
  </table></div>{% endif %}
  {% set offen_fleisch = b.fleisch|rejectattr('ausgeliefert')|list %}
  {% if offen_fleisch %}<p><b>Tüten entfernen</b></p>
  {% for f in offen_fleisch %}<label class="haken"><input type="checkbox" name="weg" value="{{ f.id }}">
    {{ f.art }} {{ f.teil }} · {{ f.code }}</label>{% endfor %}{% endif %}
  <p><b>Wurst dazu</b></p>
  <div class="form-zeile">
    <label>Produkt<select name="neu_produkt" data-ziel="neu_menge"><option value="" data-frei="0">–</option>
      {% for p in produkte if p.frei > 0 %}<option value="{{ p.id }}" data-frei="{{ p.frei }}">{{ p.name }} (frei {{ p.frei }})</option>{% endfor %}</select></label>
    <div class="feld">Menge<input name="neu_menge" type="number" min="0" max="0" inputmode="numeric" data-stepper data-leer
      placeholder="0" aria-label="Menge neues Produkt"></div>
  </div>
  {% if fleisch %}<p><b>Fleisch dazu</b></p>
  <div class="form-zeile">
    <label>Ware<select name="neu_fleisch" data-ziel="neu_tueten"><option value="" data-frei="0">–</option>
      {% for g in fleisch %}<option value="{{ g.art }}:{{ g.teil }}" data-frei="{{ g.anzahl }}">{{ g.art }} {{ g.teil }} (frei {{ g.anzahl }})</option>{% endfor %}</select></label>
    <div class="feld">Tüten<input name="neu_tueten" type="number" min="0" max="0" inputmode="numeric" data-stepper data-leer
      placeholder="0" aria-label="Anzahl Tüten"></div>
  </div>{% endif %}
  <p><button class="gross">Änderungen speichern</button></p>
</form>
<script>
document.querySelectorAll("select[data-ziel]").forEach(function (s) {
  var i = s.form.elements[s.dataset.ziel];
  function setzen() {
    var frei = Number(s.selectedOptions[0].dataset.frei || 0);
    i.max = frei;
    var v = parseInt(i.value || "0", 10) || 0;
    if (frei && v === 0) i.value = 1;
    if (v > frei) i.value = frei || "";
    i.dispatchEvent(new Event("grenze"));
  }
  s.addEventListener("change", setzen);
});
</script>
{% if not geliefert_teil %}<h2>Schon früher geliefert?</h2>
<form class="karte" method="post" action="{{ url_for('bestellung_frueher', oid=b.id) }}"
  onsubmit="return confirm('Als geliefert markieren, ohne den Wurstbestand zu verringern?')">
  <p class="leise">Für Lieferungen, die vor dem Eintragen des Lagerbestands passiert sind. Der Wurstbestand bleibt gleich.</p>
  <button class="neben">Als früher geliefert markieren</button></form>{% endif %}
{% endif %}
{% if b.status == 'ausgeliefert' or geliefert_teil %}<h2>Lieferung zurücknehmen</h2>
<form class="karte" method="post" action="{{ url_for('bestellung_zuruecknehmen', oid=b.id) }}"
  onsubmit="return confirm('Lieferung zurücknehmen? Gebuchte Ware kommt zurück ins Lager.')">
  <p class="leise">Die Bestellung ist danach wieder offen. Was beim Ausliefern vom Lager abgebucht wurde, kommt zurück.</p>
  <button class="neben">Lieferung zurücknehmen</button></form>{% endif %}
{% if b.status == 'storniert' %}<h2>Endgültig löschen</h2>
<form class="karte" method="post" action="{{ url_for('bestellung_loeschen', oid=b.id) }}"
  onsubmit="return confirm('Bestellung #{{ b.id }} endgültig löschen? Auch ihre Zahlungen werden gelöscht.')">
  <button class="gefahr">Bestellung löschen</button></form>{% endif %}
{% if b.status == 'offen' %}<h2>Stornieren</h2>
<form class="karte" method="post" action="{{ url_for('bestellung_storno', oid=b.id) }}"
  onsubmit="return confirm('Bestellung #{{ b.id }} wirklich stornieren?')">
  <p class="leise">Die reservierte Ware wird wieder frei. Zahlungen bleiben gespeichert.</p>
  <button class="gefahr">Bestellung stornieren</button></form>{% endif %}"""
        geliefert_teil = b["status"] == "offen" and (any(z["ausgeliefert"] for z in b["wurst"])
                                                      or any(f["ausgeliefert"] for f in b["fleisch"]))
        return seite(vorlage, f"Bestellung {oid}", b=b, geliefert_teil=geliefert_teil,
                     produkte=vk.produkte() if b["status"] == "offen" else [],
                     fleisch=vk.fleisch_frei() if b["status"] == "offen" else [])

    def _ziel_nach(oid):
        z = request.form.get("zurueck", "")
        # Nur eigene Seiten als Rücksprung zulassen.
        if z.startswith(request.script_root + "/") and "//" not in z and "\\" not in z:
            return z
        return url_for("bestellung", oid=oid)

    def _mit_meldung(adresse, text, fehler=False):
        trenn = "&" if "?" in adresse else "?"
        from urllib.parse import quote
        return redirect(f"{adresse}{trenn}m={quote(text)}" + ("&f=1" if fehler else ""), 303)

    def _aktion(oid, tun, ok_text):
        ziel = _ziel_nach(oid)
        try:
            tun()
            return _mit_meldung(ziel, ok_text)
        except Fehler as e:
            return _mit_meldung(ziel, FEHLERTEXT.get(e.kennwort, e.kennwort) + ".", True)

    @app.post("/bestellungen/<int:oid>/bezahlt")
    def bestellung_bezahlt(oid):
        f = request.form
        return _aktion(oid, lambda: vk.zahlung(oid, f.get("betrag") or None, f.get("methode", "")),
                       f"Zahlung für #{oid} gebucht.")

    @app.post("/bestellungen/<int:oid>/ausgeliefert")
    def bestellung_ausgeliefert(oid):
        return _aktion(oid, lambda: vk.ausliefern(oid), f"#{oid} ausgeliefert.")

    @app.post("/bestellungen/<int:oid>/rabatt")
    def bestellung_rabatt(oid):
        return _aktion(oid, lambda: vk.rabatt_setzen(oid, request.form.get("rabatt")), "Rabatt gespeichert.")

    @app.post("/bestellungen/<int:oid>/zahlung/<int:zid>/loeschen")
    def zahlung_loeschen(oid, zid):
        return _aktion(oid, lambda: vk.zahlung_loeschen(oid, zid), "Zahlung gelöscht.")

    @app.post("/bestellungen/<int:oid>/aendern")
    def bestellung_aendern(oid):
        f = request.form
        mengen = {}
        for schluessel, wert in f.items():
            if schluessel.startswith("m") and schluessel[1:].isdigit() and wert.strip() != "":
                mengen[int(schluessel[1:])] = wert.strip()
        neu = {}
        if f.get("neu_produkt") and f.get("neu_menge", "").strip():
            neu[int(f["neu_produkt"])] = f["neu_menge"].strip()
        fleisch_neu = []
        if f.get("neu_fleisch") and f.get("neu_tueten", "").strip() and ":" in f["neu_fleisch"]:
            art, teil = f["neu_fleisch"].split(":", 1)
            fleisch_neu.append((art, teil, f["neu_tueten"].strip()))
        weg = [int(x) for x in f.getlist("weg") if x.isdigit()]

        ziel = _ziel_nach(oid)
        try:
            vk.bestellung_aendern(oid, mengen, neu, weg, fleisch_neu, f.get("datum") or None)
        except Fehler as e:
            text = FEHLERTEXT.get(e.kennwort, e.kennwort)
            if "ware" in e.info:
                text += f": {e.info['ware']} (frei: {e.info.get('frei', '?')})"
            return _mit_meldung(ziel, text + ".", True)
        return _mit_meldung(ziel, "Bestellung geändert.")

    @app.post("/bestellungen/<int:oid>/zuruecknehmen")
    def bestellung_zuruecknehmen(oid):
        return _aktion(oid, lambda: vk.lieferung_zuruecknehmen(oid), f"Lieferung von #{oid} zurückgenommen.")

    @app.post("/bestellungen/<int:oid>/frueher")
    def bestellung_frueher(oid):
        return _aktion(oid, lambda: vk.frueher_geliefert(oid), f"#{oid} als früher geliefert markiert.")

    @app.post("/bestellungen/<int:oid>/loeschen")
    def bestellung_loeschen(oid):
        try:
            vk.bestellung_loeschen(oid)
        except Fehler as e:
            return _mit_meldung(url_for("bestellung", oid=oid), FEHLERTEXT.get(e.kennwort, e.kennwort) + ".", True)
        return _mit_meldung(url_for("bestellungen", filter="alle"), f"#{oid} gelöscht.")

    @app.post("/bestellungen/<int:oid>/storno")
    def bestellung_storno(oid):
        return _aktion(oid, lambda: vk.stornieren(oid), f"#{oid} storniert.")

    # ======================= Schnittstelle für Home Assistant und Claude =======================
    def daten():
        d2 = request.get_json(silent=True)
        return d2 if isinstance(d2, dict) else {}

    def bestellnummer(x):
        try:
            return int(str(x.get("bestellung_id", "")).lstrip("#"))
        except ValueError:
            raise Fehler("bestellung_unbekannt")

    def bestand_api(x):
        suche = str(x.get("suche") or "").strip().casefold()
        wurst = [{"produkt": p["name"], "art": KATEGORIEN[p["kategorie"]], "frei": p["frei"], "reserviert": p["reserviert"],
                  "preis": euro(p["preis_cent"]), "einheit": p["einheit"]} for p in vk.produkte()]
        fleisch = [{"wildart": g["art"], "teil": g["teil"], "freie_tueten": g["anzahl"],
                    "kg_gewogen": round(g["gramm"] / 1000, 2), "gewogene_tueten": g["gewogen"],
                    "aelteste_vom": g["aelteste"]} for g in vk.fleisch_frei()]
        if suche:
            wurst = [w for w in wurst if suche in w["produkt"].casefold()]
            fleisch = [f for f in fleisch if suche in f"{f['wildart']} {f['teil']}".casefold()]
        return {"wurst": wurst, "fleisch": fleisch}

    def bestellung_api(x):
        b = vk.bestellung_anlegen(x.get("positionen"), kunde_id=x.get("kunde_id"), kunde=x.get("kunde"),
                                  notiz=x.get("notiz", ""))
        return {"angelegt": kurz(b)}

    def bestellungen_api(x):
        kid = x.get("kunde_id")
        if not kid and x.get("kunde"):
            kid = vk._kunde_klaeren(kunde=x.get("kunde"))["id"]
        liste = vk.bestellungen(x.get("filter") or "offen", int(kid) if kid else None)
        return {"anzahl": len(liste), "bestellungen": [kurz(b) for b in liste[:50]]}

    def _notiz_kurz(n):
        return {"notiz_id": n["id"], "kunde": n["kunde"] or "", "text": n["text"], "vom": kontext["de"](n["erstellt"][:10]),
                "erledigt": bool(n["erledigt"])}

    def _ganz_id(wert):
        try:
            return int(float(str(wert).strip().lstrip("#")))
        except ValueError:
            raise Fehler("vormerkung_unbekannt")

    def aendern_api(x):
        oid = int(bestellnummer(x))
        mengen, neu = {}, {}
        if x.get("produkt"):
            p = vk.produkt_finden(x["produkt"])
            menge = x.get("menge")
            if menge in (None, ""):
                raise Fehler("menge_ungueltig", hinweis="Neue Gesamtmenge angeben, 0 entfernt die Position")
            pos = [z for z in vk.bestellung(oid)["wurst"] if z["produkt_id"] == p["id"]]
            if pos:
                mengen[pos[0]["id"]] = menge
            else:
                neu[p["id"]] = menge
        b = vk.bestellung_aendern(oid, mengen, neu, datum=str(x.get("datum") or "").strip() or None)
        return {"geaendert": kurz(b)}

    def wurst_api(x, art):
        p = vk.produkt_finden(x.get("produkt"))
        neu = vk.wurst_buchen(p["id"], x.get("menge"), art, x.get("grund", ""))
        return {"produkt": p["name"], "bestand_jetzt": neu}

    def produkt_preis_api(x):
        p = vk.produkt_finden(x.get("produkt"))
        vk.produkt_aendern(p["id"], p["name"], p["einheit"], x.get("preis"), True)
        return {"produkt": p["name"], "preis": euro(vk.produkt(p["id"])["preis_cent"])}

    def umsatz_api(_):
        u = vk.umsatz()
        return {k: (euro(w) if k.endswith("_cent") else w) for k, w in u.items()}

    AKTIONEN = {
        "bestand": bestand_api,
        "kunden_suchen": lambda x: {"treffer": vk.kunden_suchen(x.get("name"))},
        "kunde_anlegen": lambda x: dict(zip(("kunde_id", "neu"), vk.kunde_anlegen(
            x.get("name"), x.get("telefon"), notiz=x.get("notiz")))),
        "bestellung_anlegen": bestellung_api,
        "bestellung_aendern": aendern_api,
        "notiz": lambda x: {"notiz": _notiz_kurz(vk.vormerkung_anlegen(
            x.get("text"), kunde_id=x.get("kunde_id"), kunde=x.get("kunde")))},
        "notizen": lambda x: {"notizen": [_notiz_kurz(n) for n in vk.vormerkungen()]},
        "notiz_erledigt": lambda x: {"notiz": _notiz_kurz(vk.vormerkung_erledigen(_ganz_id(x.get("notiz_id"))))},
        "lieferung_zuruecknehmen": lambda x: {"zurueckgenommen": kurz(vk.lieferung_zuruecknehmen(int(bestellnummer(x))))},
        "bestellungen": bestellungen_api,
        "bezahlt": lambda x: {"bestellung": kurz(vk.zahlung(bestellnummer(x), x.get("betrag"), x.get("methode", "")))},
        "ausgeliefert": lambda x: {"bestellung": kurz(vk.ausliefern(bestellnummer(x)))},
        "stornieren": lambda x: {"bestellung": kurz(vk.stornieren(bestellnummer(x)))},
        "wurst_zugang": lambda x: wurst_api(x, "zugang"),
        "wurst_korrektur": lambda x: wurst_api(x, "korrektur"),
        "wurst_entnahme": lambda x: wurst_api(x, "entnahme"),
        "rabatt": lambda x: {"bestellung": kurz(vk.rabatt_setzen(bestellnummer(x), x.get("betrag")))},
        "wurst_preis": produkt_preis_api,
        "fleischpreis": lambda x: (vk.fleischpreis_setzen(x.get("wildart"), x.get("teil"), x.get("preis_kg")),
                                   {"gespeichert": True})[1],
        "umsatz": umsatz_api,
    }

    @app.post("/api/verkauf/<aktion>")
    def verkauf_api(aktion):
        if aktion not in AKTIONEN:
            raise Fehler("aktion_unbekannt", erlaubt=sorted(AKTIONEN))
        return jsonify(ok=True, **AKTIONEN[aktion](daten()))

    # Wurstetiketten: Jede gedruckte Packung zählt erst nach erfolgreichem Druck.
    @app.post("/api/wurst/druckauftrag")
    def wurst_druckauftrag():
        x = daten()
        p = vk.produkt_finden(x.get("produkt")) if x.get("produkt") else vk.produkt(int(x.get("produkt_id") or 0))
        if not p:
            raise Fehler("produkt_unbekannt")
        return jsonify(ok=True, **vk.druckauftrag(p["id"]))

    @app.post("/api/wurst/gedruckt/<auftrag>")
    def wurst_gedruckt(auftrag):
        return jsonify(ok=True, neu_gebucht=vk.druck_bestaetigen(auftrag))
