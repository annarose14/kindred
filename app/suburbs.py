"""Approximate suburb centres (lat, lon) for the pilot area: Inner West, eastern suburbs, Randwick."""

SUBURBS = {
    "alexandria": (-33.9050, 151.1950),
    "annandale": (-33.8810, 151.1700),
    "ashfield": (-33.8880, 151.1250),
    "balmain": (-33.8580, 151.1790),
    "bondi": (-33.8915, 151.2767),
    "camperdown": (-33.8890, 151.1770),
    "clovelly": (-33.9130, 151.2630),
    "coogee": (-33.9200, 151.2550),
    "dulwich hill": (-33.9045, 151.1380),
    "enmore": (-33.9000, 151.1720),
    "erskineville": (-33.9030, 151.1860),
    "glebe": (-33.8790, 151.1860),
    "kensington": (-33.9100, 151.2240),
    "kingsford": (-33.9240, 151.2270),
    "leichhardt": (-33.8830, 151.1570),
    "marrickville": (-33.9106, 151.1553),
    "maroubra": (-33.9500, 151.2400),
    "newtown": (-33.8975, 151.1790),
    "paddington": (-33.8840, 151.2310),
    "petersham": (-33.8945, 151.1550),
    "randwick": (-33.9145, 151.2410),
    "redfern": (-33.8930, 151.2040),
    "st peters": (-33.9110, 151.1780),
    "stanmore": (-33.8935, 151.1650),
    "summer hill": (-33.8915, 151.1380),
    "surry hills": (-33.8860, 151.2110),
}


def normalise(name):
    return " ".join(str(name or "").lower().replace(",", " ").replace("nsw", "").split())


def find_suburb(name):
    """Return (canonical_name, (lat, lon)) or (None, None)."""
    key = normalise(name)
    if key in SUBURBS:
        return key, SUBURBS[key]
    for sub in SUBURBS:
        if sub in key:
            return sub, SUBURBS[sub]
    return None, None
