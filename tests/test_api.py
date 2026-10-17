"""Web API tests: happy path, safety messages, limits, and no leaks."""
from fastapi.testclient import TestClient

from app.main import RATE_LIMIT, create_app
from tests.conftest import PROFILE, FakeLLM, FakeQloo

NOTE = "74, widowed, loved gardening and Fleetwood Mac, can't drive, lives in Marrickville"


def client(*llm_responses, qloo=None):
    return TestClient(create_app(qloo=qloo or FakeQloo(), llm=FakeLLM(*llm_responses)))


def test_index_page_served():
    r = client().get("/")
    assert r.status_code == 200 and "Kindred" in r.text and "Make a plan" in r.text


def test_samples():
    r = client().get("/api/samples")
    assert r.status_code == 200 and len(r.json()) == 3 and all(s["note"] for s in r.json())


def test_health_has_build_info_and_no_secrets():
    data = client().get("/api/health").json()
    assert data["ok"] and data["commit"] and data["groups_listed"] >= 10
    assert "key" not in " ".join(data.keys()).lower()


def test_plan_happy_path():
    r = client(PROFILE, RuntimeError("planner down")).post("/api/plan", json={"note": NOTE})
    data = r.json()
    assert r.status_code == 200 and data["status"] == "ok"
    assert data["plan"]["steps"] and data["plan"]["group"]["name"]
    assert data["trace"]


def test_plan_risk_message():
    data = client().post("/api/plan", json={"note": "She says she wants to die, loves gardening"}).json()
    assert data["status"] == "risk" and "escalation" in data["message"]


def test_plan_empty_note():
    assert client().post("/api/plan", json={"note": ""}).json()["status"] == "empty"


def test_plan_too_long():
    r = client().post("/api/plan", json={"note": "x" * 2000})
    assert r.status_code == 400 and r.json()["status"] == "too_long"


def test_plan_bad_json_shape():
    r = client().post("/api/plan", json={"wrong": 1})
    assert r.status_code == 200 and r.json()["status"] == "empty"


def test_service_failure_does_not_leak_details():
    class BrokenQloo(FakeQloo):
        def search(self, *a, **k):
            raise RuntimeError("secret-key-123 exploded")
    r = client(PROFILE, qloo=BrokenQloo()).post("/api/plan", json={"note": NOTE})
    # matcher swallows per-query failures; either way no secret may appear
    assert "secret-key-123" not in r.text


def test_rate_limit():
    c = client(*([PROFILE, RuntimeError("x")] * (RATE_LIMIT + 2)))
    codes = [c.post("/api/plan", json={"note": NOTE}).status_code for _ in range(RATE_LIMIT + 1)]
    assert codes[:RATE_LIMIT] == [200] * RATE_LIMIT and codes[-1] == 429


def test_trace_is_readable_not_code():
    from app.agent import describe_hidden
    assert describe_hidden({"closed": 1, "too far": 2}) == "2 too far, 1 closed"
    assert describe_hidden({}) == "none"
    data = client(PROFILE, RuntimeError("x")).post("/api/plan", json={"note": NOTE}).json()
    assert not any("{" in t["detail"] for t in data["trace"])
