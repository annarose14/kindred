"""Tests for problems found in the evaluation run (17 Oct): thin suburbs, short plans, slow calls."""
from app import agent, matcher, planner
from tests.conftest import PROFILE, FakeLLM, FakeQloo, place


def test_one_word_genre_needs_exact_match():
    assert matcher.name_match("documentaries", "CNBC Documentaries") == 0.0
    assert matcher.name_match("chess", "Chess") == 1.0
    assert matcher.name_match("fleetwood mac", "Fleetwood Mac Live") == 0.9


def test_neighbours_are_nearest_and_within_reach():
    n = matcher.neighbours("lewisham", "bus")
    assert n and "lewisham" not in n and len(n) <= 2
    assert set(n) <= {"petersham", "summer hill", "dulwich hill", "stanmore", "ashfield", "marrickville"}
    assert matcher.neighbours("nowhere", "bus") == []


class SuburbQloo(FakeQloo):
    """Only the neighbouring suburb has places."""
    def insights(self, params):
        self.calls.append(("insights", dict(params)))
        if params["filter.location.query"].startswith("petersham") and params["filter.tags"].endswith("park"):
            return [place("NP", "Petersham Park", "park", lat=-33.8945, lon=151.1550, tags=["Relaxing"]),
                    place("NP2", "Second Park", "park", lat=-33.8950, lon=151.1540, tags=["Quiet"])]
        if params["filter.location.query"].startswith("petersham") and params["filter.tags"].endswith("library"):
            return [place("NL", "Petersham Library", "library", lat=-33.8945, lon=151.1560)]
        return []


def test_find_places_searches_extra_suburbs_but_measures_from_home():
    lewisham = dict(PROFILE, suburb="Lewisham")
    out = matcher.find_places(SuburbQloo(), lewisham, extra_suburbs=["petersham"])
    assert len(out["candidates"]) == 3
    assert all(c["distance_km"] is not None and c["distance_km"] < 2 for c in out["candidates"])


def test_agent_searches_neighbours_when_thin_and_logs_it():
    lewisham = dict(PROFILE, suburb="Lewisham", transport="bus")
    out = agent.run(None, SuburbQloo(), FakeLLM(RuntimeError("x")), profile_override=lewisham)
    assert out["status"] == "ok" and len(out["plan"]["steps"]) == 3
    line = next(t["detail"] for t in out["trace"] if t["step"] == "nearby")
    assert "Lewisham" in line and "Petersham" in line


def test_fallback_fills_three_steps_even_with_same_type():
    cands = [{"id": f"c{i}", "name": f"Cafe {i}", "category": "Cafe", "pressure": 2, "score": 1 - i / 10,
              "evidence": ["Popular with people who enjoy chess"], "liked_by": ["chess"], "feel": []}
             for i in range(3)]
    plan = planner.fallback_plan(cands)
    assert [s["place"]["name"] for s in plan["steps"]] == ["Cafe 0", "Cafe 1", "Cafe 2"]


def test_fallback_still_prefers_variety_and_order():
    cands = [
        {"id": "a", "name": "Cafe A", "category": "Cafe", "pressure": 2, "score": 0.9, "evidence": []},
        {"id": "b", "name": "Cafe B", "category": "Cafe", "pressure": 2, "score": 0.8, "evidence": []},
        {"id": "p", "name": "Park P", "category": "Park", "pressure": 0, "score": 0.5, "evidence": []},
    ]
    names = [s["place"]["name"] for s in planner.fallback_plan(cands)["steps"]]
    assert names == ["Park P", "Cafe A", "Cafe B"]


def test_llm_client_fails_fast():
    import inspect
    from app import llm
    src = inspect.getsource(llm.GroqLLM.__init__)
    assert "timeout=15.0" in src and "max_retries=0" in src


def test_qloo_client_fails_fast_on_network_errors(monkeypatch):
    import requests
    import qloo_client
    assert qloo_client.TIMEOUT <= 10
    c = qloo_client.QlooClient(api_key="secret-key", use_cache=False)

    def boom(*a, **k):
        raise requests.ConnectionError("down")
    monkeypatch.setattr(c.session, "get", boom)
    try:
        c.get("/search", {"query": "x"})
        assert False, "should raise"
    except qloo_client.QlooError as e:
        assert "Network problem" in str(e) and "secret" not in str(e)
