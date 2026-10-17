"""Tests for problems found in the third real review (17 Oct)."""
from app import matcher, safety
from tests.conftest import MARRICKVILLE, PROFILE, FakeQloo, place


def test_wrong_category_is_dropped():
    tattoo = place("T", "Thirteen Feet Tattoo", "tattoo_shop")
    gallery = place("G", "Real Gallery", "art_gallery", tags=["Quiet"])
    q = FakeQloo(by_category={"museum": [tattoo, gallery]})
    q.by_category["museum"][1] = place("G", "Real Gallery", "museum", tags=["Quiet"])
    out = matcher.find_places(q, PROFILE)
    assert [c["name"] for c in out["candidates"]] == ["Real Gallery"]
    assert out["excluded"]["wrong type"] == 1


def test_place_without_category_tags_is_kept():
    p = place("N", "No Category Park", "park")
    p["tags"] = [{"id": "urn:tag:x:relaxing", "name": "Relaxing", "type": "urn:tag:ambience:qloo"}]
    out = matcher.find_places(FakeQloo(by_category={"park": [p]}), PROFILE)
    assert [c["name"] for c in out["candidates"]] == ["No Category Park"]


def test_unsuitable_places_hidden():
    for name, cat in [("Ink Tattoo Studio", "cafe"), ("Newtown TAB", "cafe"),
                      ("Star Casino Lounge", "cafe"), ("Cloud Vape Bar", "cafe"),
                      ("Anything", "tattoo_shop")]:
        ok, reasons, _ = safety.check_place(place("x", name, cat), PROFILE, MARRICKVILLE)
        assert not ok and "not a social venue" in reasons, name


def test_tab_word_does_not_hit_normal_names():
    for name in ["Tabletop Games Cafe", "Stable Cafe", "Kebab House"]:
        assert not safety.is_unsuitable(place("x", name, "cafe")), name


def test_feel_ignores_noise_keeps_useful_amenities():
    p = place("x", "Park", "park", tags=["Relaxing"])
    p["tags"] += [
        {"name": "Gift wrapping", "type": "urn:tag:amenities:place"},
        {"name": "Catering services", "type": "urn:tag:amenities:place"},
        {"name": "Benches", "type": "urn:tag:amenities:place"},
        {"name": "Safe", "type": "urn:tag:ambience:qloo"},
    ]
    assert matcher.place_feel(p) == ["Relaxing", "Benches"]


def test_unknown_popularity_ranks_lower_at_equal_qloo_rank():
    known = place("A", "Known Library", "library", tags=["Relaxing"])
    known["popularity"] = 0.6
    unknown = place("B", "Unknown Museum", "museum", tags=["Relaxing"])
    unknown["popularity"] = 0
    out = matcher.find_places(FakeQloo(by_category={"museum": [unknown], "library": [known]}), PROFILE)
    assert [c["name"] for c in out["candidates"]] == ["Known Library", "Unknown Museum"]
