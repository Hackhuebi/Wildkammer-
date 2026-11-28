"""Druckt ein Etikett aus der App heraus über das Home-Assistant-Skript wild_etikett_rendern."""
import einspielen


def drucken(etikett, ha=None):
    """True, wenn Home Assistant den Druck bestätigt. Ohne Home Assistant oder bei Druckerfehler False."""
    ha = ha or einspielen._ha
    try:
        antwort = ha("/services/script/wild_etikett_rendern?return_response", {"e": etikett})
    except Exception as fehler:
        print("Wildkammer: Druck fehlgeschlagen:", fehler)
        return False
    return bool(((antwort or {}).get("service_response") or {}).get("gedruckt"))
