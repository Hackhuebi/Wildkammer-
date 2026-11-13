"""Zahlungserinnerung: schickt einmal am Tag eine Nachricht aufs Handy, wenn gelieferte Bestellungen
länger als eingestellt unbezahlt sind. Läuft im Add-on, geschickt wird über die Home-Assistant-App."""
import json
import os
import threading
import time
import urllib.request
from datetime import datetime

from verkauf import euro


def _anfrage(url, daten=None):
    token = os.environ.get("SUPERVISOR_TOKEN")
    if not token:
        raise RuntimeError("Kein Zugang zu Home Assistant (nur im Add-on verfügbar)")
    a = urllib.request.Request(url, data=None if daten is None else json.dumps(daten).encode(),
                               method="GET" if daten is None else "POST",
                               headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"})
    with urllib.request.urlopen(a, timeout=30) as antwort:
        text = antwort.read().decode() or "null"
        return json.loads(text)


def geraete():
    """Handys mit Home-Assistant-App, an die Home Assistant Nachrichten schicken kann."""
    dienste = _anfrage("http://supervisor/core/api/services")
    for d in dienste:
        if d.get("domain") == "notify":
            return sorted(k for k in d.get("services", {}) if k.startswith("mobile_app_"))
    return []


_ziel_url = None


def _app_url():
    """Pfad, der beim Antippen der Nachricht die Wildkammer in der App öffnet."""
    global _ziel_url
    if _ziel_url is None:
        try:
            info = _anfrage("http://supervisor/addons/self/info")
            _ziel_url = f"/hassio/ingress/{info['data']['slug']}"
        except Exception:
            _ziel_url = ""
    return _ziel_url


def text(liste):
    zeilen = [f"{b['kunde']}: {euro(b['offen_cent'])} (seit {b['tage']} {'Tag' if b['tage'] == 1 else 'Tagen'})"
              for b in liste]
    return "\n".join(zeilen)


def senden(ziel, titel, nachricht, anfrage=_anfrage):
    daten = {"title": titel, "message": nachricht}
    url = _app_url() if anfrage is _anfrage else ""
    if url:
        daten["data"] = {"url": url, "clickAction": url}
    anfrage(f"http://supervisor/core/api/services/notify/{ziel}", daten)


def pruefen(vk, jetzt=None, anfrage=_anfrage):
    """Einmal am Tag ab der eingestellten Uhrzeit. Gibt die Zahl der gemeldeten Bestellungen zurück
    (None, wenn heute nichts zu tun war)."""
    jetzt = jetzt or vk.d.uhr()
    tage, ziel = int(vk.einstellung("erinnerung_tage") or 0), vk.einstellung("erinnerung_ziel")
    heute = jetzt.date().isoformat()
    if tage <= 0 or not ziel or vk.einstellung("erinnerung_zuletzt") == heute:
        return None
    if jetzt.strftime("%H:%M") < vk.einstellung("erinnerung_uhrzeit"):
        return None
    liste = vk.ueberfaellig(tage)
    if liste:
        titel = (f"Wildkammer: {len(liste)} Bestellung{'en' if len(liste) != 1 else ''} "
                 f"seit über {tage} Tagen unbezahlt" if tage > 1 else "Wildkammer: unbezahlte Lieferungen")
        senden(ziel, titel, text(liste), anfrage)
    vk.einstellung_setzen("erinnerung_zuletzt", heute)
    return len(liste)


def starten(vk):
    def schleife():
        while True:
            try:
                pruefen(vk, datetime.now())
            except Exception as fehler:  # Nachricht ist ein Zusatz; das Lager läuft weiter
                print("Wildkammer: Erinnerung fehlgeschlagen:", fehler)
            time.sleep(60)
    threading.Thread(target=schleife, daemon=True, name="erinnerung").start()
