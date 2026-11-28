"""Druckt ein Etikett aus der App heraus über das Home-Assistant-Skript wild_etikett_rendern."""
import time

import einspielen


def _einmal(etikett, ha):
    try:
        antwort = ha("/services/script/wild_etikett_rendern?return_response", {"e": etikett})
    except Exception as fehler:
        print("Wildkammer: Druck fehlgeschlagen:", fehler)
        return False
    return bool(((antwort or {}).get("service_response") or {}).get("gedruckt"))


def drucken(etikett, ha=None, versuche=2, pause=4, schlafen=time.sleep):
    """True, wenn Home Assistant den Druck bestätigt. Der B1 wacht beim ersten Verbindungsversuch oft erst auf,
    deshalb ein zweiter Versuch nach kurzer Pause. Ohne Home Assistant (kein Token) gar kein Versuch."""
    ha = ha or einspielen._ha
    for nr in range(versuche):
        if _einmal(etikett, ha):
            return True
        if nr + 1 < versuche:
            schlafen(pause)
    return False
