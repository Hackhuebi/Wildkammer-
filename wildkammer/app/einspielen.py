"""Spielt die mitgelieferten Home-Assistant-Pakete beim Start des Add-ons ein.

Damit reicht für ein Update ein Tipp auf "Aktualisieren": Das Add-on kopiert seine YAML-Dateien
nach /homeassistant/packages, sichert vorher die alten, lässt Home Assistant die Konfiguration
prüfen und lädt neu. Ist die neue Konfiguration fehlerhaft, kommen die alten Dateien zurück.
"""
import json
import os
import shutil
import time
import urllib.request

QUELLE = os.environ.get("WILDKAMMER_PAKETE", "/pakete")
ZIEL = os.environ.get("WILDKAMMER_HA_PAKETE", "/homeassistant/packages")
SICHERUNG = os.environ.get("WILDKAMMER_HA_SICHERUNG", "/homeassistant/wildkammer-sicherung")
API = "http://supervisor/core/api"


def _ha(pfad, daten=None):
    token = os.environ.get("SUPERVISOR_TOKEN")
    if not token:
        return None
    anfrage = urllib.request.Request(
        API + pfad, data=json.dumps(daten or {}).encode(), method="POST",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"})
    with urllib.request.urlopen(anfrage, timeout=120) as antwort:
        text = antwort.read().decode() or "{}"
        return json.loads(text)


def _melden(titel, text):
    try:
        _ha("/services/persistent_notification/create",
            {"title": titel, "message": text, "notification_id": "wildkammer_update"})
    except Exception as fehler:  # Meldung ist nur ein Zusatz
        print("Wildkammer: Meldung fehlgeschlagen:", fehler)


def einspielen(ha=_ha, melden=_melden, version=""):
    """Gibt zurück: 'gleich', 'neu', 'zurueck' (Fehler, alte Dateien wiederhergestellt) oder 'aus'."""
    if not os.path.isdir(QUELLE) or not os.path.isdir(os.path.dirname(ZIEL)):
        return "aus"
    os.makedirs(ZIEL, exist_ok=True)
    geaendert = []
    for name in sorted(os.listdir(QUELLE)):
        if not name.endswith(".yaml"):
            continue
        neu = open(os.path.join(QUELLE, name), encoding="utf-8").read()
        ziel = os.path.join(ZIEL, name)
        alt = open(ziel, encoding="utf-8").read() if os.path.exists(ziel) else None
        if alt != neu:
            geaendert.append((name, alt, neu))
    if not geaendert:
        return "gleich"
    stempel = time.strftime("%Y-%m-%d_%H-%M-%S")
    os.makedirs(SICHERUNG, exist_ok=True)
    for name, alt, neu in geaendert:
        if alt is not None:
            # Endung .bak, damit Home Assistant die Sicherung nie als Paket lädt
            with open(os.path.join(SICHERUNG, f"{name}.{stempel}.bak"), "w", encoding="utf-8") as f:
                f.write(alt)
        with open(os.path.join(ZIEL, name), "w", encoding="utf-8") as f:
            f.write(neu)
    namen = ", ".join(n for n, _, _ in geaendert)
    try:
        pruefung = ha("/config/core/check_config")
    except Exception as fehler:
        pruefung = {"result": "unbekannt", "errors": str(fehler)}
    if pruefung is not None and pruefung.get("result") == "invalid":
        for name, alt, _ in geaendert:
            pfad = os.path.join(ZIEL, name)
            if alt is None:
                os.remove(pfad)
            else:
                with open(pfad, "w", encoding="utf-8") as f:
                    f.write(alt)
        melden("Wildkammer: Update nicht eingespielt",
               f"Die neuen Dateien ({namen}) waren fehlerhaft und wurden nicht übernommen. "
               f"Es läuft weiter die alte Fassung.\n\n{pruefung.get('errors', '')}")
        return "zurueck"
    try:
        ha("/services/homeassistant/reload_all")
        melden("Wildkammer aktualisiert",
               f"Version {version}: {namen} eingespielt und neu geladen. Falls ein Sprachbefehl oder Druck "
               "nicht geht: Home Assistant einmal neu starten. Sicherung der alten Dateien: wildkammer-sicherung.")
    except Exception as fehler:
        print("Wildkammer: Neu laden fehlgeschlagen:", fehler)
        melden("Wildkammer aktualisiert", f"Version {version}: {namen} eingespielt. Bitte Home Assistant neu starten.")
    return "neu"


UMZUG = os.environ.get("WILDKAMMER_UMZUG", "/share/wildkammer/wildkammer-letzter-start.db")


def daten_holen(pfad_db):
    """Neues Add-on ohne Datenbank: die Kopie vom letzten Start übernehmen (Umzug oder Neuinstallation)."""
    if os.path.exists(pfad_db) or not os.path.exists(UMZUG):
        return False
    os.makedirs(os.path.dirname(pfad_db) or ".", exist_ok=True)
    shutil.copyfile(UMZUG, pfad_db)
    return True


def daten_ablegen(datenbank):
    """Kopie der Datenbank nach /share, damit sie ein Neuinstallieren oder den Umzug übersteht."""
    if not os.path.isdir(os.path.dirname(os.path.dirname(UMZUG))):
        return False
    os.makedirs(os.path.dirname(UMZUG), exist_ok=True)
    zwischen = UMZUG + ".neu"
    datenbank.sicherung(zwischen)
    os.replace(zwischen, UMZUG)
    return True


if __name__ == "__main__":
    print("Wildkammer: Pakete", einspielen())
