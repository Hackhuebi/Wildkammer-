import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "wildkammer", "app"))
import druck


def test_zweiter_versuch():
    antworten = [RuntimeError("weg"), {"service_response": {"gedruckt": True}}]
    def ha(pfad, daten):
        a = antworten.pop(0)
        if isinstance(a, Exception):
            raise a
        return a
    assert druck.drucken({"nummer": "1"}, ha=ha, schlafen=lambda s: None)
    assert not druck.drucken({"nummer": "1"}, ha=lambda p, d: {"service_response": {"gedruckt": False}}, schlafen=lambda s: None)
