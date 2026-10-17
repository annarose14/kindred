"""Tests for problems found in the second real review (17 Oct)."""
from app import agent, matcher, planner
from tests.conftest import PROFILE, FakeLLM, FakeQloo, place


# Fix 1: "Studio Ghibli" must never become "Yoga studio"
def test_tag_needs_every_word():
    assert not matcher.tag_fits("studio ghibli", "Yoga studio")
    assert matcher.tag_fits("choir", "Choir")
    assert matcher.tag_fits("gardening", "Gardening")
    assert matcher.tag_fits("cricket", "Cricket ground")


class GhibliQloo(FakeQloo):
    def search(self, query, types=None, take=5):
        self.calls.append(("search", query, types))
        if query.lower() == "spirited away" and types == "urn:entity:movie":
            return [{"name": "Spirited Away", "entity_id": "SA"}]
        return super().search(query, types, take)

    def tags(self, query, take=10):
        if query.lower() == "studio ghibli":
            return [{"name": "Yoga studio", "id": "urn:tag:keyword:qloo:yoga_studio"}]
        return super().tags(query, take)


def test_agent_retries_unknown_interest_with_examples():
    profile = dict(PROFILE, interests=[{"name": "Studio Ghibli", "kind": "movie"}])
    llm = FakeLLM({"alternatives": [{"name": "Totoro Fake", "kind": "movie"},
                                    {"name": "Spirited Away", "kind": "movie"}]},
                  RuntimeError("planner down"))
    out = agent.run(None, GhibliQloo(), llm, profile_override=profile)
    assert out["status"] == "ok"
    labels = [i["label"] for i in out["match"]["interests"]]
    assert labels == ["Spirited Away (Studio Ghibli)"]
    retry = next(t for t in out["trace"] if t["step"] == "retry")
    assert "Spirited Away" in retry["detail"]


def test_retry_failure_is_logged_not_guessed():
    profile = dict(PROFILE, interests=[{"name": "Studio Ghibli", "kind": "movie"},
                                       {"name": "gardening", "kind": "activity"}])
    llm = FakeLLM({"alternatives": [{"name": "Nothing Known", "kind": "movie"}]}, RuntimeError("x"))
    out = agent.run(None, GhibliQloo(), llm, profile_override=profile)
    assert [i["label"] for i in out["match"]["interests"]] == ["gardening"]
    assert any("skipped" in t["detail"] for t in out["trace"] if t["step"] == "retry")


def test_retry_survives_llm_error():
    profile = dict(PROFILE, interests=[{"name": "Studio Ghibli", "kind": "movie"}])
    out = agent.run(None, GhibliQloo(), FakeLLM(RuntimeError("down")), profile_override=profile)
    assert out["status"] == "no_interests_found"


# Fix 2: "why" says how the place feels, and joins interests naturally
def test_why_includes_feel_and_joins_interests():
    c = {"feel": ["Relaxing", "Benches"], "liked_by": ["gardening", "Fleetwood Mac"],
         "evidence": ['Popular with people who enjoy gardening',
                      'Tagged "Community gardening", which fits gardening']}
    why = planner.explain(c)
    assert why.startswith("Relaxing and benches; popular with people who enjoy gardening and Fleetwood Mac")
    assert 'tagged "Community gardening"' in why


def test_feel_skips_loud_and_alcohol_tags():
    p = place("x", "Cafe", "cafe", tags=["Bustling", "Alcohol", "Cozy", "Place", "Quiet", "Garden", "Shade"])
    assert matcher.place_feel(p) == ["Cozy", "Quiet", "Garden"]


# Fix 3: more place types, but only ones Qloo confirms
class CategoryQloo(FakeQloo):
    def tags(self, query, take=10):
        if query == "bookstore":
            return [{"name": "Book store", "id": "urn:tag:category:place:book_store"}]
        if query == "tea house":
            return [{"name": "Tea", "id": "urn:tag:keyword:qloo:tea"}]  # not a category: rejected
        return super().tags(query, take)


def test_extra_categories_only_when_confirmed():
    cats = matcher.categories_for(CategoryQloo())
    assert "book_store" in cats and "tea_house" not in cats and "park" in cats


def test_social_place_always_offered_when_available(profile):
    quiet = [place(f"P{i}", f"Park {i}", "park", tags=["Relaxing"]) for i in range(2)]
    lib = [place("L1", "Library", "library")]
    centre = place("CC", "Community Hall", "community_center")
    q = FakeQloo(by_category={"park": quiet, "library": lib, "community_center": [centre]})
    out = matcher.find_places(q, profile, limit=3)
    assert any(c["pressure"] >= 2 for c in out["candidates"])


def test_plan_orders_by_pressure():
    cands = matcher.find_places(FakeQloo(), PROFILE)["candidates"]
    plan = planner.fallback_plan(cands)
    pressures = [s["place"]["pressure"] for s in plan["steps"]]
    assert pressures == sorted(pressures) and pressures[-1] >= 2
