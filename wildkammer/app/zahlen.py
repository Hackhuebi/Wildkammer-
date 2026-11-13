"""Versteht gesprochene Mengen und Gewichte, in Ziffern und in Worten."""
import re

EINER = {
    "ein": 1, "eins": 1, "eine": 1, "einen": 1, "einem": 1, "zwei": 2, "zwo": 2, "drei": 3, "vier": 4,
    "fünf": 5, "sechs": 6, "sieben": 7, "acht": 8, "neun": 9,
}
ZWEISTELLIG = {
    "zehn": 10, "elf": 11, "zwölf": 12, "dreizehn": 13, "vierzehn": 14, "fünfzehn": 15,
    "sechzehn": 16, "siebzehn": 17, "achtzehn": 18, "neunzehn": 19,
}
ZEHNER = {
    "zwanzig": 20, "dreißig": 30, "dreissig": 30, "vierzig": 40, "fünfzig": 50,
    "sechzig": 60, "siebzig": 70, "achtzig": 80, "neunzig": 90,
}


def _unter_hundert(w):
    if w in EINER:
        return EINER[w]
    if w in ZWEISTELLIG:
        return ZWEISTELLIG[w]
    if w in ZEHNER:
        return ZEHNER[w]
    for zehner, wert in ZEHNER.items():
        if w.endswith("und" + zehner):
            einer = w[: -len("und" + zehner)]
            if einer in EINER:
                return EINER[einer] + wert
    return None


def wort_zu_zahl(w):
    """Wandelt ein zusammengeschriebenes Zahlwort bis 49999 um, sonst None."""
    w = w.strip().lower()
    if not w:
        return None
    summe = 0
    if "tausend" in w:
        vorne, w = w.split("tausend", 1)
        tausender = 1 if not vorne else wort_zu_zahl(vorne)
        if tausender is None or tausender >= 50:
            return None
        summe += tausender * 1000
        if not w:
            return summe
    if "hundert" in w:
        vorne, w = w.split("hundert", 1)
        hunderter = 1 if not vorne else EINER.get(vorne)
        if hunderter is None:
            return None
        summe += hunderter * 100
        if not w:
            return summe
        if w.startswith("und") and _unter_hundert(w[3:]) is not None:
            w = w[3:]
    rest = _unter_hundert(w)
    return None if rest is None else summe + rest


def _ganz(t):
    t = t.strip()
    if re.fullmatch(r"\d+", t):
        return int(t)
    if re.fullmatch(r"\d{1,2}\.\d{3}", t):
        return int(t.replace(".", ""))
    return wort_zu_zahl(t)


def menge(text):
    """Liefert 1 ohne Angabe, sonst 1 bis 10; None bei allem anderen."""
    t = "" if text is None else str(text).strip().lower()
    if not t:
        return 1
    t = re.sub(r"\s*(?:mal|x)$", "", t).strip()
    n = _ganz(t)
    return n if n is not None and 1 <= n <= 10 else None


def _kommazahl(t):
    """Für Kilo: 1,5 / 1.5 / eins komma fünf / ein / zwei."""
    t = t.strip()
    m = re.fullmatch(r"(\d+)[,.](\d{1,3})", t)
    if m:
        return float(f"{m.group(1)}.{m.group(2)}")
    m = re.fullmatch(r"(.+?)\s+komma\s+(.+)", t)
    if m:
        vorne = _ganz(m.group(1))
        ziffern = [_ganz(x) for x in m.group(2).split()]
        if vorne is None or not ziffern or None in ziffern or any(z > 99 for z in ziffern):
            return None
        return float(f"{vorne}." + "".join(str(z) for z in ziffern))
    return _ganz(t)


def gewicht(text):
    """Liefert Gramm, None ohne Angabe; bei Unbrauchbarem ValueError."""
    t = re.sub(r"\s+", " ", ("" if text is None else str(text)).strip().lower()).rstrip(".")
    if not t:
        return None
    t = re.sub(r"^(?:mit|ca\.?|circa|etwa|ungefähr|von)\s+", "", t)
    t = t.replace("kilogramm", "kilo").replace("kg", " kilo ")
    t = re.sub(r"\s+", " ", t).strip()
    g = None
    if t in ("anderthalb kilo", "eineinhalb kilo"):
        g = 1500
    elif t in ("halbes kilo", "ein halbes kilo", "ein halbes pfund kilo"):
        g = 500
    elif t in ("ein pfund", "pfund"):
        g = 500
    else:
        m = re.fullmatch(r"(.+?) ?kilo(?: und)?(?: (.+?))?(?: ?(?:gramm|g))?", t)
        if m:
            kilo = _kommazahl(m.group(1))
            zusatz = _ganz(m.group(2)) if m.group(2) else 0
            if kilo is not None and zusatz is not None and zusatz < 1000:
                g = round(kilo * 1000) + zusatz
        else:
            m = re.fullmatch(r"(.+?) ?(?:gramm|g)?", t)
            if m:
                g = _ganz(m.group(1))
                # Eine sehr kleine Zahl ohne Einheit ist wahrscheinlich ein Verhörer.
                if g is not None and g < 20:
                    g = None
    if g is None or not 0 < g <= 50000:
        raise ValueError(text)
    return g
