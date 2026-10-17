"""Deeper probe: fields, multi signals, place categories, age audiences."""
import json
from qloo_client import QlooClient, QlooError

q = QlooClient()
LOC = "Marrickville, Sydney"


def show(title, params, n=6):
    print(f"\n== {title}")
    try:
        places = q.insights(params)
    except QlooError as e:
        print("   ERROR:", e)
        return []
    if not places:
        print("   (empty)")
    for p in places[:n]:
        tags = [t.get("name") for t in p.get("tags", [])[:4]]
        print("  ", p.get("name"), "|", tags)
    return places


fm = q.search("Fleetwood Mac", types="urn:entity:artist")[0]["entity_id"]
cricket = q.tags("cricket")
garden_kw = "urn:tag:keyword:qloo:gardening"

print("\n== Cricket tags")
for t in cricket[:5]:
    print("  ", t.get("name"), "|", t.get("id"))

print("\n== Place category tags")
for word in ["park", "library", "community center", "botanical garden", "cafe", "museum"]:
    ids = [t["id"] for t in q.tags(word) if t.get("id", "").startswith("urn:tag:category:place")]
    print(f"   {word}: {ids[:3]}")

places = show("A. Fleetwood Mac fans + gardening keyword", {
    "filter.type": "urn:entity:place",
    "signal.interests.entities": fm,
    "signal.interests.tags": garden_kw,
    "filter.location.query": LOC,
    "take": 10,
})

show("B. Same, audience aged 55 and older", {
    "filter.type": "urn:entity:place",
    "signal.interests.entities": fm,
    "signal.demographics.age": "55_and_older",
    "filter.location.query": LOC,
    "take": 10,
})

park_tags = [t["id"] for t in q.tags("park") if t.get("id", "").startswith("urn:tag:category:place")]
if park_tags:
    show("C. Parks only, Fleetwood Mac fans", {
        "filter.type": "urn:entity:place",
        "signal.interests.entities": fm,
        "filter.tags": park_tags[0],
        "filter.location.query": LOC,
        "take": 10,
    })

show("D. Cafes, 2km radius", {
    "filter.type": "urn:entity:place",
    "signal.interests.entities": fm,
    "filter.tags": "urn:tag:category:place:cafe",
    "filter.location.query": LOC,
    "filter.location.radius": 2000,
    "take": 10,
})

if places:
    print("\n== Full fields of first place (keys and properties)")
    p = places[0]
    print("   top keys:", sorted(p.keys()))
    print("   properties keys:", sorted(p.get("properties", {}).keys()))
    print("   location:", p.get("location"))
    print("   address:", p.get("properties", {}).get("address"))
    print("   all tag types:", sorted({t.get("type") for t in p.get("tags", [])}))
    with open("cache/sample_place.json", "w") as f:
        json.dump(p, f, indent=2)
    print("   saved full sample to cache/sample_place.json (private)")

print("\nProbe 2 finished")
