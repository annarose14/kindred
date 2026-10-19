"""Follow up: the worker reports back and Kindred adapts only that week."""
import json

from fastapi.testclient import TestClient

from app import agent, safety
from app.main import create_app
from tests.conftest import MARRICKVILLE, PROFILE, FakeLLM, FakeQloo, place


def plan_for(q, profile=PROFILE):
    out = agent.run(None, q, FakeLLM(RuntimeError("x")), profile_override=profile)
    assert out["status"] == "ok"
    return out


def rich_qloo():
    near_park = place("P1", "Marrickville Park", "park", tags=["Relaxing"])
    quiet_lib = place("L1", "Marrickville Library", "library", tags=["Quiet"])
    busy_cafe = place("C1", "Busy Cafe", "cafe", tags=["Bustling"])
    calm_cafe = place("C2", "Calm Cafe", "cafe", lat=-33.9110, lon=151.1560, tags=["Cozy"])
    far_centre = place("CC1", "Far Community Hall", "community_center", lat=-33.94, lon=151.16)
    near_centre = place("CC2", "Near Community Hall", "community_center", lat=-33.9112, lon=151.1556)
    museum = place("M1", "Small Museum", "museum", tags=["Quiet"])
    return FakeQloo(by_category={"park": [near_park], "library": [quiet_lib], "cafe": [busy_cafe, calm_cafe],
                                 "community_center": [far_centre, near_centre], "museum": [museum]})


def test_went_well_marks_done_and_points_to_next():
    q = rich_qloo()
    out = plan_for(q)
    res = agent.adapt(q, out["profile"], out["plan"]["steps"], 1, "went")
    assert res["status"] == "ok" and res["steps"][0]["done"] is True
    assert "Next:" in res["message"] and res["steps"][1]["place"] == out["plan"]["steps"][1]["place"]


def test_all_done_suggests_group():
    q = rich_qloo()
    out = plan_for(q)
    steps = out["plan"]["steps"]
    for w in range(1, len(steps) + 1):
        steps = agent.adapt(q, out["profile"], steps, w, "went")["steps"]
    res = agent.adapt(q, out["profile"], steps, 1, "went")
    assert "group" in res["message"]


def test_too_busy_replaces_with_quieter_and_stays_strict():
    q = rich_qloo()
    steps = [{"week": 1, "place": {"id": "C1", "name": "Busy Cafe", "category": "Cafe", "pressure": 2,
                                     "distance_km": 0.1}, "action": "a", "why": "w"}]
    res = agent.adapt(q, PROFILE, steps, 1, "not_yet", "too_busy")
    new = res["steps"][0]
    assert new["place"]["id"] != "C1" and new["place"]["pressure"] <= 2
    assert new["changed"] == {"from": "Busy Cafe", "because": "it felt too busy or loud"}
    assert res["profile"]["strict_calm"] is True


def test_plan_ends_with_a_social_step_when_one_exists():
    out = plan_for(rich_qloo())
    pressures = [s["place"]["pressure"] for s in out["plan"]["steps"]]
    assert pressures == sorted(pressures) and pressures[-1] >= 2


def test_too_far_picks_something_closer():
    q = rich_qloo()
    steps = [{"week": 1, "place": {"id": "CC1", "name": "Far Community Hall", "category": "Community centre",
                                     "pressure": 3, "distance_km": 3.3}, "action": "a", "why": "w"}]
    res = agent.adapt(q, PROFILE, steps, 1, "not_yet", "too_far")
    assert res["steps"][0]["place"]["distance_km"] < 3.1
    assert res["profile"]["transport"] == PROFILE["transport"]  # how they travel is unchanged


def test_not_ready_picks_gentler_place():
    q = rich_qloo()
    steps = [{"week": 1, "place": {"id": "CC2", "name": "Near Community Hall", "category": "Community centre",
                                     "pressure": 3, "distance_km": 0.1}, "action": "a", "why": "w"}]
    res = agent.adapt(q, PROFILE, steps, 1, "not_yet", "not_ready")
    assert res["steps"][0]["place"]["pressure"] < 3


def test_not_their_thing_changes_kind_of_place():
    q = rich_qloo()
    steps = [{"week": 1, "place": {"id": "L1", "name": "Marrickville Library", "category": "Library",
                                     "pressure": 1, "distance_km": 0.1}, "action": "a", "why": "w"}]
    res = agent.adapt(q, PROFILE, steps, 1, "not_yet", "not_their_thing")
    assert res["steps"][0]["place"]["category"] != "Library"


def test_no_option_keeps_plan_and_says_so():
    q = FakeQloo(by_category={"park": [place("P1", "Only Park", "park")]})
    steps = [{"week": 1, "place": {"id": "P1", "name": "Only Park", "category": "Park", "pressure": 0,
                                     "distance_km": 0.1}, "action": "a", "why": "w"}]
    res = agent.adapt(q, PROFILE, steps, 1, "not_yet", "not_ready")
    assert res["steps"][0]["place"]["id"] == "P1" and "No better option" in res["message"]


def test_bad_inputs_rejected():
    q = rich_qloo()
    good = [{"week": 1, "place": {"id": "P1", "name": "x"}}]
    assert agent.adapt(q, PROFILE, good, 5, "went")["status"] == "bad_request"
    assert agent.adapt(q, PROFILE, good, 1, "not_yet", "because")["status"] == "bad_request"
    assert agent.adapt(q, PROFILE, [{"place": "junk"}], 1, "went")["status"] == "bad_request"
    assert agent.adapt(q, PROFILE, [], 1, "went")["status"] == "bad_request"


def test_strict_calm_hides_one_loud_tag():
    p = place("x", "Cafe", "cafe", tags=["Bustling"])
    assert safety.check_place(p, PROFILE, MARRICKVILLE)[0]
    assert not safety.check_place(p, dict(PROFILE, strict_calm=True), MARRICKVILLE)[0]


def test_api_adapt_round_trip():
    q = rich_qloo()
    c = TestClient(create_app(qloo=q, llm=FakeLLM()))
    out = plan_for(q)
    body = {"profile": out["profile"], "steps": out["plan"]["steps"], "week": 1, "outcome": "went"}
    r = c.post("/api/adapt", json=body)
    assert r.status_code == 200 and r.json()["steps"][0]["done"] is True
    r = c.post("/api/adapt", json=dict(body, week=9))
    assert r.status_code == 400
    r = c.post("/api/adapt", json=dict(body, steps=[{"place": {"id": "x", "name": "y" * 30000}}]))
    assert r.status_code == 400 and r.json()["status"] == "too_long"


def test_too_far_with_nothing_closer_keeps_profile_and_explains():
    q = FakeQloo(by_category={"park": [place("P1", "Only Park", "park")]})
    steps = [{"week": 1, "place": {"id": "P1", "name": "Only Park", "category": "Park", "pressure": 0,
                                     "distance_km": 0.1}, "action": "a", "why": "w"}]
    res = agent.adapt(q, PROFILE, steps, 1, "not_yet", "too_far")
    assert res["steps"][0]["place"]["id"] == "P1"
    assert res["profile"]["transport"] == PROFILE["transport"]
    assert "already the nearest" in res["message"]


def test_too_far_twice_never_shrinks_how_they_travel():
    q = rich_qloo()
    steps = [{"week": 1, "place": {"id": "CC1", "name": "Far Community Hall", "category": "Community centre",
                                     "pressure": 3, "distance_km": 3.3}, "action": "a", "why": "w"}]
    first = agent.adapt(q, PROFILE, steps, 1, "not_yet", "too_far")
    second = agent.adapt(q, first["profile"], first["steps"], 1, "not_yet", "too_far")
    assert second["profile"]["transport"] == PROFILE["transport"]


def test_too_far_can_offer_a_quiet_library_instead_of_a_park():
    q = FakeQloo(by_category={"park": [place("P9", "Far Park", "park", lat=-33.925, lon=151.156)],
                              "library": [place("L1", "Near Library", "library", tags=["Quiet"])]})
    steps = [{"week": 1, "place": {"id": "P9", "name": "Far Park", "category": "Park", "pressure": 0,
                                     "distance_km": 1.6}, "action": "a", "why": "w"}]
    res = agent.adapt(q, PROFILE, steps, 1, "not_yet", "too_far")
    assert res["steps"][0]["place"]["name"] == "Near Library"
