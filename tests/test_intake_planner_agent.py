from app import agent, intake, planner, matcher
from tests.conftest import PROFILE, FakeLLM

NOTE = "74, widowed, loved gardening and Fleetwood Mac, can't drive, lives in Marrickville"


# ---------- intake ----------

def test_risk_note_stops_before_llm():
    llm = FakeLLM(PROFILE)
    out = intake.parse_note(llm, "Lonely, says she wants to die. Likes gardening.")
    assert out["status"] == "risk" and llm.prompts == []


def test_empty_note():
    assert intake.parse_note(FakeLLM(), "  hi ")["status"] == "empty"


def test_llm_failure_is_handled():
    assert intake.parse_note(FakeLLM(RuntimeError("down")), NOTE)["status"] == "error"


def test_contact_details_removed_before_llm():
    llm = FakeLLM(PROFILE)
    intake.parse_note(llm, NOTE + " email jo@example.com phone 0412 345 678")
    sent = llm.prompts[0][1]
    assert "jo@example.com" not in sent and "0412" not in sent


def test_validate_profile_cleans_bad_values():
    p = intake.validate_profile({"age_band": "old", "transport": "rocket",
                                 "interests": [{"name": "x", "kind": "weird"}, "junk", {"name": ""}],
                                 "avoid_alcohol": None})
    assert p["age_band"] is None and p["transport"] == "bus"
    assert p["interests"] == [{"name": "x", "kind": "activity"}]
    assert p["avoid_alcohol"] is True and p["prefers_calm"] is True


def test_validate_profile_handles_non_dict():
    assert intake.validate_profile(None)["interests"] == []


def test_max_four_interests():
    p = intake.validate_profile({"interests": [{"name": str(i)} for i in range(9)]})
    assert len(p["interests"]) == 4


# ---------- planner ----------

def _candidates(q):
    return matcher.find_places(q, PROFILE)["candidates"]


def test_valid_llm_plan_used(q):
    cands = _candidates(q)
    llm = FakeLLM({"summary": "s", "conversation_starter": "c",
                   "steps": [{"place_id": cands[0]["id"], "action": "Short walk"},
                             {"place_id": cands[1]["id"], "action": "Coffee"}]})
    plan = planner.make_plan(llm, PROFILE, cands)
    assert plan["source"] == "agent" and plan["steps"][0]["place"]["id"] == cands[0]["id"]
    assert plan["steps"][0]["action"] == "Short walk"


def test_invented_place_rejected_uses_fallback(q):
    cands = _candidates(q)
    llm = FakeLLM({"steps": [{"place_id": "MADE_UP", "action": "a", "why": "w"}]})
    plan = planner.make_plan(llm, PROFILE, cands)
    assert plan["source"] == "rules"
    ids = {c["id"] for c in cands}
    assert all(s["place"]["id"] in ids for s in plan["steps"])


def test_duplicate_steps_rejected(q):
    cands = _candidates(q)
    pid = cands[0]["id"]
    llm = FakeLLM({"steps": [{"place_id": pid}, {"place_id": pid}]})
    assert planner.make_plan(llm, PROFILE, cands)["source"] == "rules"


def test_extra_steps_trimmed_to_three(q):
    cands = _candidates(q)
    assert len(cands) >= 4
    plan = planner.make_plan(FakeLLM({"steps": [{"place_id": c["id"]} for c in cands]}), PROFILE, cands)
    assert plan["source"] == "agent" and len(plan["steps"]) == 3


def test_fallback_goes_quiet_to_social(q):
    plan = planner.fallback_plan(_candidates(q))
    order = [s["place"]["pressure"] for s in plan["steps"]]
    assert order == sorted(order) and len({s["place"]["category"] for s in plan["steps"]}) == len(order)


def test_no_candidates_no_plan():
    assert planner.make_plan(FakeLLM(), PROFILE, []) is None


# ---------- whole agent ----------

def test_agent_happy_path(q):
    cands = _candidates(q)
    llm = FakeLLM(PROFILE, {"summary": "s", "steps": [{"place_id": cands[0]["id"]}]})
    out = agent.run(NOTE, q, llm)
    assert out["status"] == "ok" and out["plan"]["steps"]
    assert [t["step"] for t in out["trace"]] == ["read_note", "understand", "understand", "match", "plan"]


def test_agent_survives_planner_llm_failure(q):
    out = agent.run(NOTE, q, FakeLLM(PROFILE, RuntimeError("down")))
    assert out["status"] == "ok" and out["plan"]["source"] == "rules"


def test_agent_risk_message(q):
    out = agent.run("He said he might hurt myself soon, likes cricket", q, FakeLLM())
    assert out["status"] == "risk" and "escalation" in out["message"]
    assert not any(c[0] == "insights" for c in q.calls)


def test_agent_widens_search_when_thin(q):
    walking = dict(PROFILE, transport="walking_short")
    from tests.conftest import place
    near = place("N1", "Near Park", "park", tags=["Relaxing"])
    mid = place("M1", "Mid Library", "library", lat=-33.9106, lon=151.1700)  # about 1.4 km away
    mid2 = place("M2", "Mid Museum", "museum", lat=-33.9000, lon=151.1553)  # about 1.2 km away
    from tests.conftest import FakeQloo
    q2 = FakeQloo(by_category={"park": [near], "library": [mid], "museum": [mid2]})
    out = agent.run(None, q2, FakeLLM(RuntimeError("x")), profile_override=walking)
    assert out["status"] == "ok" and out["match"].get("widened_to") == "walking"
    assert "widen" in [t["step"] for t in out["trace"]]


def test_agent_no_places(profile):
    from tests.conftest import FakeQloo, BREWERY
    q2 = FakeQloo(by_category={"cafe": [BREWERY]})
    out = agent.run(None, q2, FakeLLM(), profile_override=profile)
    assert out["status"] == "no_places" and out["message"]


import pytest


@pytest.mark.parametrize("text", [
    "says she wants to die", "He WANTS  TO DIE some days", "talked about suicide",
    "suicidal thoughts last month", "has been hurting himself", "history of self-harm",
    "self harm risk", "wants to end her life", "took an overdose", "feels better off dead",
    "doesn't want to be here anymore", "said he does not want to live",
])
def test_risk_detected(text):
    assert intake.has_risk(text)


@pytest.mark.parametrize("text", [
    "loves gardening and Fleetwood Mac", "dying to try the new cafe",
    "harmony singing in a choir", "watches Die Hard every Christmas",
    "the plants keep dying", "wants to live near the park",
])
def test_no_false_alarm(text):
    assert not intake.has_risk(text)
