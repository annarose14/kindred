"""Run once the key arrives: shows what Qloo returns for a sample patient."""
from qloo_client import QlooClient

q = QlooClient()

print("\n1. Search: Fleetwood Mac")
artists = q.search("Fleetwood Mac", types="urn:entity:artist")
for a in artists[:3]:
    print("  ", a.get("name"), "|", a.get("entity_id"))

print("\n2. Tags: gardening")
for t in q.tags("gardening")[:5]:
    print("  ", t.get("name"), "|", t.get("id"))

if artists:
    artist_id = artists[0]["entity_id"]
    print("\n3. Places in Marrickville liked by Fleetwood Mac fans")
    places = q.insights({
        "filter.type": "urn:entity:place",
        "signal.interests.entities": artist_id,
        "filter.location.query": "Marrickville, Sydney",
        "take": 8,
    })
    for p in places:
        tags = [t.get("name") for t in p.get("tags", [])[:3]]
        print("  ", p.get("name"), "|", tags)
    if not places:
        print("   (empty: we will try other location parameters)")

print("\nProbe finished")
