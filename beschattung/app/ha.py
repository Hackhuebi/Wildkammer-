"""Verbindung zu Home Assistant über den Supervisor."""
import json
import os
import urllib.request

API = "http://supervisor/core/api"

DIENSTE = {
    "open_cover": None, "close_cover": None, "stop_cover": None,
    "set_cover_position": "position", "set_cover_tilt_position": "tilt_position",
}
NUR_LAMELLEN = {"set_cover_tilt_position"}


class HomeAssistant:
    def __init__(self, token=None, basis=API):
        self.token = token or os.environ.get("SUPERVISOR_TOKEN")
        self.basis = basis

    def _anfrage(self, pfad, daten=None):
        if not self.token:
            raise RuntimeError("Kein Zugang zu Home Assistant (nur im Add-on verfügbar)")
        a = urllib.request.Request(self.basis + pfad, data=None if daten is None else json.dumps(daten).encode(),
                                   method="GET" if daten is None else "POST",
                                   headers={"Authorization": f"Bearer {self.token}", "Content-Type": "application/json"})
        with urllib.request.urlopen(a, timeout=15) as antwort:
            return json.loads(antwort.read().decode() or "null")

    def zustaende(self, ids):
        gesucht = set(ids)
        return {z["entity_id"]: z for z in self._anfrage("/states") if z.get("entity_id") in gesucht}

    def dienst(self, dienst, ids, wert=None):
        daten = {"entity_id": list(ids)}
        feld = DIENSTE[dienst]
        if feld:
            daten[feld] = wert
        self._anfrage(f"/services/cover/{dienst}", daten)
