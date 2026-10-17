"""Tests for problems found while reviewing real plans on 17 Oct."""
from app import agent, matcher, planner, safety
from tests.conftest import MARRICKVILLE, PROFILE, FakeLLM, FakeQloo, place


class SearchQloo(FakeQloo):
    """Search returns misleading near misses, like the real API did."""
    DATA = {
        ("studio ghibli", "movie"): [{"name": "Taylor Swift: Folklore: The Long Pond Studio Sessions",
                                      "entity_id": "TS"}],
        ("studio ghibli", "brand"): [{"name": "Studio Ghibli", "entity_id": "SG"}],
        ("agatha christie", "book"): [{"name": "The Bedside, Bathtub and Armchair Companion to Agatha Christie",
                                       "entity_id": "COMP"}],
        ("agatha christie", "person"): [{"name": "Agatha Christie", "entity_id": "AC"}],
        ("obscure band", "artist"): [{"name": "Totally Different Band", "entity_id": "X"}],
    }

    def search(self, query, types=None, take=5):
        self.calls.append(("search", query, types))
        return self.DATA.get((query.lower(), types.rsplit(":", 1)[-1]), [])

    def tags(self, query, take=10):
        return {"choir": [{"name": "Chorus Line", "id": "urn:tag:keyword:qloo:chorus_line"},
                          {"name": "Choir", "id": "urn:tag:keyword:qloo:choir"}]}.get(query.lower(), [])


# Fix 1 and 2: wrong entity matches
def test_studio_ghibli_not_taylor_swift():
    r = matcher.resolve_interest(SearchQloo(), {"name": "Studio Ghibli", "kind": "movie"})
    assert r["id"] == "SG"


def test_author_books_match_the_author():
    r = matcher.resolve_interest(SearchQloo(), {"name": "Agatha Christie books", "kind": "book"})
    assert r["id"] == "AC" and r["kind"] == "person"


def test_near_miss_is_rejected_not_guessed():
    assert matcher.resolve_interest(SearchQloo(), {"name": "obscure band", "kind": "artist"}) is None


def test_tag_must_share_a_word():
    r = matcher.resolve_interest(SearchQloo(), {"name": "choir", "kind": "activity"})
    assert r["matched"] == "Choir"


def test_clean_label():
    assert matcher.clean_label("Agatha Christie books") == "agatha christie"
    assert matcher.clean_label("the Beatles") == "beatles"
    assert matcher.clean_label("Books") == "books"


# Fix 3: the LLM cannot invent groups, sessions or accessibility
def _cands():
    return matcher.find_places(FakeQloo(), PROFILE)["candidates"]


def test_invented_choir_session_is_rewritten():
    cands = _cands()
    llm = FakeLLM({"steps": [
        {"place_id": cands[0]["id"], "action": "Join a short choir session here"},
        {"place_id": cands[1]["id"], "action": "It is fully accessible, enjoy a coffee"}]})
    plan = planner.make_plan(llm, PROFILE, cands)
    for s in plan["steps"]:
        assert "session" not in s["action"].lower() and "accessible" not in s["action"].lower()
        assert s["action"].startswith("Visit ")


def test_claim_allowed_when_in_evidence():
    p = {"id": "x", "name": "Inner West Gardening Club", "evidence": []}
    assert planner.safe_action("Say hello at the gardening club", p) == "Say hello at the gardening club"


def test_why_comes_only_from_evidence():
    cands = _cands()
    llm = FakeLLM({"steps": [{"place_id": c["id"], "why": "It hosts weekly choirs"} for c in cands[:2]]})
    plan = planner.make_plan(llm, PROFILE, cands)
    for s in plan["steps"]:
        assert "choir" not in s["why"].lower() and "hosts" not in s["why"].lower()
        assert "popular with people who enjoy" in s["why"].lower()


# Fix 4: specialist services are not social venues
def test_specialist_places_excluded():
    for name in ["Asylum Seekers Centre", "UNSW Faculty of Law and Justice", "Randwick Hospital",
                 "Newtown Medical Clinic", "Sydney University Sports Hall"]:
        ok, reasons, _ = safety.check_place(place("x", name, "community_center"), PROFILE, MARRICKVILLE)
        assert not ok and "not a social venue" in reasons, name


def test_normal_community_centre_kept():
    ok, _, _ = safety.check_place(place("x", "Addison Road Community Centre", "community_center"),
                                  PROFILE, MARRICKVILLE)
    assert ok


# Fix 5: crowded tourist spots
def test_tourist_queue_spot_is_too_loud():
    p = place("x", "Famous Pastry", "cafe", tags=["Tourist attraction", "Bustling", "Long line"])
    assert not safety.check_place(p, PROFILE, MARRICKVILLE)[0]


def test_one_loud_tag_is_penalised_not_hidden():
    calm = place("a", "Calm Cafe", "cafe", tags=["Relaxing"])
    busy = place("b", "Busy Cafe", "cafe", tags=["Bustling"])
    out = matcher.find_places(FakeQloo(by_category={"cafe": [busy, calm]}), PROFILE)
    assert [c["name"] for c in out["candidates"]] == ["Calm Cafe", "Busy Cafe"]


# Fix 7: the trace says why the LLM plan was rejected
def test_trace_shows_fallback_reason():
    out = agent.run(None, FakeQloo(), FakeLLM({"steps": [{"place_id": "NOPE"}]}), profile_override=PROFILE)
    plan_line = out["trace"][-1]["detail"]
    assert "rules" in plan_line and "unknown place" in plan_line
