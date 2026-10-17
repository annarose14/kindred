"""Fakes so tests run offline, fast and free, using shapes seen in real Qloo responses."""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

MARRICKVILLE = (-33.9106, 151.1553)


def place(pid, name, cat, lat=-33.911, lon=151.156, tags=(), closed=False, access=()):
    t = [{"id": f"urn:tag:category:place:{cat}", "name": cat.title(), "type": "urn:tag:category:place"}]
    t += [{"id": f"urn:tag:x:{n.lower()}", "name": n, "type": "urn:tag:ambience:qloo"} for n in tags]
    t += [{"id": f"urn:tag:acc:{n.lower()}", "name": n, "type": "urn:tag:accessibility:place"} for n in access]
    return {"entity_id": pid, "name": name, "location": {"lat": lat, "lon": lon},
            "properties": {"address": f"{name} St Marrickville", "is_closed": closed}, "tags": t}


PARK = place("P1", "Marrickville Park", "park", tags=["Community gardening", "Benches", "Relaxing"])
LIBRARY = place("L1", "Marrickville Library", "library", tags=["Quiet", "Cozy"],
                access=["Wheelchair accessible entrance"])
CAFE = place("C1", "Fleetwood Macchiato", "cafe", tags=["Relaxing", "Breakfast"])
COMMUNITY = place("CC1", "Addison Road Community Centre", "community_center", tags=["Community oriented"])
CLOSED_CAFE = place("C2", "Narrative - Now closed", "cafe", tags=["Takeout"])
BREWERY = place("B1", "Willie the Boatman Brewery", "cafe", tags=["Craft beer", "Alcohol"])
FAR_PARK = place("P2", "Centennial Park", "park", lat=-33.8970, lon=151.2330, tags=["Relaxing"])
LOUD_CAFE = place("C3", "Cafe Bustle", "cafe", tags=["Rowdy", "Late night", "Bustling"])

ARTISTS = {"fleetwood mac": [
    {"name": "Fleetwood Mac", "entity_id": "FM"},
    {"name": "Eddie Boyd With Peter Green's Fleetwood Mac", "entity_id": "FM2"},
]}
TAGS = {"gardening": [
    {"name": "Gardening", "id": "urn:tag:genre:media:gardening"},
    {"name": "Gardening", "id": "urn:tag:keyword:qloo:gardening"},
]}


class FakeQloo:
    def __init__(self, by_category=None, fail_categories=()):
        self.calls = []
        self.fail_categories = set(fail_categories)
        self.by_category = by_category or {
            "park": [PARK, FAR_PARK], "library": [LIBRARY], "cafe": [CLOSED_CAFE, BREWERY, CAFE, LOUD_CAFE],
            "community_center": [COMMUNITY], "museum": [], "botanical_garden": [],
        }

    def search(self, query, types=None, take=5):
        self.calls.append(("search", query, types))
        return ARTISTS.get(query.lower(), []) if types == "urn:entity:artist" else []

    def tags(self, query, take=10):
        self.calls.append(("tags", query))
        return TAGS.get(query.lower(), [])

    def insights(self, params):
        self.calls.append(("insights", dict(params)))
        cat = params["filter.tags"].rsplit(":", 1)[-1]
        if cat in self.fail_categories:
            raise RuntimeError("boom")
        return list(self.by_category.get(cat, []))


class FakeLLM:
    """Returns queued responses in order; raises if the queue item is an Exception."""
    def __init__(self, *responses):
        self.responses = list(responses)
        self.prompts = []

    def chat_json(self, system, user):
        self.prompts.append((system, user))
        if not self.responses:
            raise RuntimeError("no more fake responses")
        r = self.responses.pop(0)
        if isinstance(r, Exception):
            raise r
        return json.loads(json.dumps(r))


PROFILE = {
    "age_band": "55_and_older", "suburb": "Marrickville",
    "interests": [{"name": "Fleetwood Mac", "kind": "artist"}, {"name": "gardening", "kind": "activity"}],
    "transport": "bus", "needs_step_free": False, "avoid_alcohol": True, "prefers_calm": True,
    "goal": "meet people",
}


@pytest.fixture
def q():
    return FakeQloo()


@pytest.fixture
def profile():
    return json.loads(json.dumps(PROFILE))
