"""Approximate suburb centres (lat, lon) for the pilot area: Inner West, inner city, eastern suburbs and Botany Bay."""

import re

SUBURBS = {
    "alexandria": (-33.9050, 151.1950),
    "annandale": (-33.8810, 151.1700),
    "ashfield": (-33.8880, 151.1250),
    "balmain": (-33.8580, 151.1790),
    "birchgrove": (-33.8520, 151.1820),
    "bondi": (-33.8915, 151.2767),
    "botany": (-33.9450, 151.1960),
    "camperdown": (-33.8890, 151.1770),
    "chippendale": (-33.8880, 151.1990),
    "clovelly": (-33.9130, 151.2630),
    "coogee": (-33.9200, 151.2550),
    "croydon": (-33.8830, 151.1150),
    "darlinghurst": (-33.8790, 151.2190),
    "darlington": (-33.8910, 151.1950),
    "dulwich hill": (-33.9045, 151.1380),
    "eastlakes": (-33.9300, 151.2120),
    "enmore": (-33.9000, 151.1720),
    "erskineville": (-33.9030, 151.1860),
    "glebe": (-33.8790, 151.1860),
    "haberfield": (-33.8810, 151.1390),
    "kensington": (-33.9100, 151.2240),
    "kingsford": (-33.9240, 151.2270),
    "leichhardt": (-33.8830, 151.1570),
    "lewisham": (-33.8970, 151.1450),
    "lilyfield": (-33.8740, 151.1650),
    "maroubra": (-33.9500, 151.2400),
    "marrickville": (-33.9106, 151.1553),
    "mascot": (-33.9260, 151.1930),
    "newtown": (-33.8975, 151.1790),
    "paddington": (-33.8840, 151.2310),
    "petersham": (-33.8945, 151.1550),
    "potts point": (-33.8700, 151.2250),
    "pyrmont": (-33.8700, 151.1940),
    "randwick": (-33.9145, 151.2410),
    "redfern": (-33.8930, 151.2040),
    "rosebery": (-33.9180, 151.2040),
    "rozelle": (-33.8620, 151.1710),
    "st peters": (-33.9110, 151.1780),
    "stanmore": (-33.8935, 151.1650),
    "summer hill": (-33.8915, 151.1380),
    "surry hills": (-33.8860, 151.2110),
    "sydenham": (-33.9160, 151.1680),
    "tempe": (-33.9230, 151.1610),
    "ultimo": (-33.8790, 151.1970),
    "waterloo": (-33.9000, 151.2070),
    "waverley": (-33.8980, 151.2510),
    "woollahra": (-33.8870, 151.2450),
    "zetland": (-33.9080, 151.2090),
}


def normalise(name):
    return " ".join(str(name or "").lower().replace(",", " ").replace("nsw", "").split())


def find_suburb(name):
    """Return (canonical_name, (lat, lon)) or (None, None)."""
    key = normalise(name)
    if key in SUBURBS:
        return key, SUBURBS[key]
    # Whole words only, longest name first, so "botany" never matches inside "botanical".
    for sub in sorted(SUBURBS, key=len, reverse=True):
        if re.search(rf"\b{re.escape(sub)}\b", key):
            return sub, SUBURBS[sub]
    return None, None
