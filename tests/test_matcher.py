from app import matcher
from app.suburbs import find_suburb
from tests.conftest import FakeQloo


def test_resolve_artist_prefers_exact_name(q):
    r = matcher.resolve_interest(q, {"name": "Fleetwood Mac", "kind": "artist"})
    assert r["id"] == "FM" and r["signal"] == "entity"


def test_resolve_hobby_prefers_keyword_tag(q):
    r = matcher.resolve_interest(q, {"name": "gardening", "kind": "activity"})
    assert r["id"] == "urn:tag:keyword:qloo:gardening" and r["signal"] == "tag"


def test_resolve_unknown_returns_none(q):
    assert matcher.resolve_interest(q, {"name": "zzzz", "kind": "activity"}) is None
    assert matcher.resolve_interest(q, {"name": "", "kind": "artist"}) is None


def test_artist_not_found_falls_back_to_tags(q):
    r = matcher.resolve_interest(q, {"name": "gardening", "kind": "artist"})
    assert r["signal"] == "tag"


def test_find_places_filters_and_explains(q, profile):
    out = matcher.find_places(q, profile)
    names = [c["name"] for c in out["candidates"]]
    assert "Marrickville Park" in names
    assert not any("Now closed" in n or "Brewery" in n or "Centennial" in n or "Bustle" in n
                   for n in names)
    assert out["excluded"] == {"closed": 1, "alcohol focused": 1, "too far": 1, "too loud": 1}
    for c in out["candidates"]:
        assert c["evidence"], f"{c['name']} has no evidence"


def test_gardening_tag_boosts_park_to_top(q, profile):
    out = matcher.find_places(q, profile)
    top = out["candidates"][0]
    assert top["name"] == "Marrickville Park"
    assert any("Community gardening" in e for e in top["evidence"])


def test_age_band_is_sent_to_qloo(q, profile):
    matcher.find_places(q, profile)
    insight_calls = [c[1] for c in q.calls if c[0] == "insights"]
    assert insight_calls and all(c["signal.demographics.age"] == "55_and_older" for c in insight_calls)
    assert all(c["filter.location.query"] == "marrickville, Sydney" for c in insight_calls)


def test_bad_age_band_not_sent(q, profile):
    profile["age_band"] = "ninety"
    matcher.find_places(q, profile)
    assert all("signal.demographics.age" not in c[1] for c in q.calls if c[0] == "insights")


def test_unknown_suburb(q, profile):
    profile["suburb"] = "Perth"
    assert matcher.find_places(q, profile)["error"] == "unknown_suburb"


def test_no_interests_found(q, profile):
    profile["interests"] = [{"name": "zzzz", "kind": "activity"}]
    assert matcher.find_places(q, profile)["error"] == "no_interests_found"


def test_one_failing_category_does_not_break(profile):
    q = FakeQloo(fail_categories={"cafe", "library"})
    out = matcher.find_places(q, profile)
    assert out["candidates"] and "error" not in out


def test_max_two_per_category(profile):
    many = [dict(FakeQloo().by_category["park"][0], entity_id=f"P{i}", name=f"Park {i}") for i in range(6)]
    others = FakeQloo().by_category
    q = FakeQloo(by_category=dict(others, park=many))
    out = matcher.find_places(q, profile)
    assert len([c for c in out["candidates"] if c["category"] == "Park"]) == 2


def test_same_place_from_two_interests_counted_once_per_interest(q, profile):
    out = matcher.find_places(q, profile)
    park = next(c for c in out["candidates"] if c["name"] == "Marrickville Park")
    assert park["interest_count"] == 2


def test_find_suburb_variants():
    assert find_suburb("Marrickville NSW 2204")[0] == "marrickville"
    assert find_suburb("  dulwich HILL ")[0] == "dulwich hill"
    assert find_suburb(None) == (None, None)
