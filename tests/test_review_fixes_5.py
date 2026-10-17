"""Problems found reading the 20 evaluation plans side by side (18 Oct)."""
import pytest

from app import agent, matcher, safety
from app.groups import match_group
from app.suburbs import find_suburb
from tests.conftest import MARRICKVILLE, PROFILE, FakeLLM, FakeQloo, place


def fits(label, tag):
    return bool(matcher._stems(label) & matcher._stems(tag))


# 1. nonsense "tagged X, which fits Y" lines
@pytest.mark.parametrize("label,tag", [
    ("Dancing with the Stars", "Fried rice with beef"),
    ("Wheel of Fortune", "Wheelchair accessible seating"),
    ("Thomas & Friends", "Family friendly"),
])
def test_no_false_evidence(label, tag):
    assert not fits(label, tag)


@pytest.mark.parametrize("label,tag", [
    ("gardening", "Community gardening"), ("dancing", "Dance hall"), ("painting", "Paint and sip"),
    ("cricket", "Cricket ground"), ("swimming", "Swimming pool"),
])
def test_real_evidence_still_found(label, tag):
    assert fits(label, tag)


# 2. accents
def test_accents_ignored():
    assert matcher.name_match("andre rieu", "André Rieu") == 1.0
    assert matcher.name_match("beyonce", "Beyoncé") == 1.0


# 3. hobbies are never swapped for a loosely related title
def test_hobby_is_not_retried_through_examples():
    profile = dict(PROFILE, interests=[{"name": "birdwatching", "kind": "activity"},
                                       {"name": "gardening", "kind": "activity"}])
    llm = FakeLLM({"alternatives": [{"name": "The Birds", "kind": "movie"}]}, RuntimeError("plan"))
    out = agent.run(None, FakeQloo(), llm, profile_override=profile)
    assert all("Birds" not in i["matched"] for i in out["match"]["interests"])
    assert any("skipped rather than guessed" in t["detail"] for t in out["trace"])
    assert len(llm.prompts) == 1  # only the planner was asked, never for examples


def test_hobby_found_through_joined_spelling_or_main_noun():
    class TagQloo(FakeQloo):
        def tags(self, query, take=10):
            table = {"birdwatching": [{"name": "Bird watching", "id": "urn:tag:keyword:qloo:bird_watching"}],
                     "dancing": [{"name": "Dancing", "id": "urn:tag:keyword:qloo:dancing"}]}
            return table.get(query, [])
    q = TagQloo()
    assert matcher.resolve_interest(q, {"name": "birdwatching", "kind": "activity"})["matched"] == "Bird watching"
    r = matcher.resolve_interest(q, {"name": "ballroom dancing", "kind": "activity"})
    assert r["matched"] == "Dancing" and r["label"] == "ballroom dancing"


# 4. feel words
def test_feel_words_are_calm_and_sensible():
    p = place("x", "Cafe", "cafe", tags=["Social", "Lively", "Cozy", "Gender neutral restroom", "Commercial", "Peaceful"])
    assert matcher.place_feel(p) == ["Social", "Cozy", "Peaceful"]


# 5. not three cafes; civic places preferred
def test_at_most_two_food_places_and_civic_first():
    cafes = [place(f"C{i}", f"Cafe {i}", "cafe", tags=["Cozy"]) for i in range(3)]
    bakeries = [place(f"B{i}", f"Bakery {i}", "bakery", tags=["Cozy"]) for i in range(2)]
    lib = [place("L1", "Local Library", "library", tags=["Quiet"])]
    q = FakeQloo(by_category={"cafe": cafes, "bakery": bakeries, "library": lib})
    q._kindred_categories = {"cafe": {"label": "Cafe", "pressure": 2}, "bakery": {"label": "Bakery", "pressure": 2},
                             "library": {"label": "Library", "pressure": 1}}
    out = matcher.find_places(q, PROFILE)
    cats = [c["category"] for c in out["candidates"]]
    assert sum(c in matcher.FOOD for c in cats) == 2 and cats[0] == "Library"


# 6. shops and services
@pytest.mark.parametrize("name", ["Woolworths Park Sydney", "Coles Marrickville", "Priceline Pharmacy",
                                  "Corner Chemist", "Newtown Bottle Shop", "McDonald's Kingsford",
                                  "KFC Randwick", "Subway Newtown", "UNSW Bookshop"])
def test_shops_are_not_social_venues(name):
    assert "not a social venue" in safety.check_place(place("x", name, "cafe"), PROFILE, MARRICKVILLE)[1]


# 7. seniors groups only for older people
def test_seniors_group_not_offered_to_young_person():
    young = dict(PROFILE, age_band="35_and_younger", suburb="Enmore", transport="walking")
    g = match_group(young, [{"label": "K-pop", "matched": "K-pop", "kind": "activity"}], find_suburb("enmore")[1])
    assert g is None or g.get("id") not in {"g_st_peters_gathering", "g_randwick_coffee", "g_iw_library_clubs"}


def test_seniors_group_still_offered_to_older_person():
    g = match_group(PROFILE, [{"label": "Fleetwood Mac", "matched": "Fleetwood Mac", "kind": "artist"}], MARRICKVILLE)
    assert g["id"] == "g_st_peters_gathering" and "audience" not in g


def test_food_cap_never_makes_a_short_plan():
    cafes = [place(f"C{i}", f"Cafe {i}", "cafe", tags=["Cozy"]) for i in range(2)]
    bakeries = [place(f"B{i}", f"Bakery {i}", "bakery", tags=["Cozy"]) for i in range(2)]
    q = FakeQloo(by_category={"cafe": cafes, "bakery": bakeries})
    q._kindred_categories = {"cafe": {"label": "Cafe", "pressure": 2}, "bakery": {"label": "Bakery", "pressure": 2}}
    out = matcher.find_places(q, PROFILE)
    assert len(out["candidates"]) == 3


def test_same_category_cap_never_makes_a_short_plan():
    parks = [place(f"P{i}", f"Park {i}", "park", tags=["Quiet"]) for i in range(4)]
    out = matcher.find_places(FakeQloo(by_category={"park": parks}), PROFILE)
    assert len(out["candidates"]) == 3


@pytest.mark.parametrize("name", ["Subwaye Cafe", "Kfcafe", "Newtown Library", "Bourke Street Bakery"])
def test_ordinary_places_still_allowed(name):
    assert "not a social venue" not in safety.check_place(place("x", name, "cafe"), PROFILE, MARRICKVILLE)[1]
