"""Kindred must still work when the language model is rate limited or down."""
import json
from pathlib import Path

import pytest

from app import agent, intake, llm, matcher
from tests.conftest import FakeLLM, FakeQloo

SAMPLES = json.loads((Path(__file__).resolve().parents[1] / "eval" / "notes.json").read_text())


# ---------- backup reader ----------

@pytest.mark.parametrize("note,expected", [
    ("74, widowed last year, loved gardening and Fleetwood Mac, can't drive, lives in Marrickville.",
     {"suburb": "Marrickville", "age_band": "55_and_older", "transport": "bus",
      "interests": ["gardening", "Fleetwood Mac"]}),
    ("Older woman in Newtown, uses a walker, used to sing in a choir, loves Agatha Christie books, doesn't drink.",
     {"suburb": "Newtown", "age_band": "55_and_older", "transport": "walking_short", "needs_step_free": True,
      "interests": ["choir", "Agatha Christie"]}),
    ("68, Glebe, former choir singer, loves Gilbert and Sullivan and gardening, can't drive, bus is fine.",
     {"suburb": "Glebe", "interests": ["Gilbert and Sullivan", "gardening"]}),
    ("Woman, 63, Ashfield, enjoys knitting and The Crown on TV, doesn't drink, catches the bus.",
     {"interests": ["knitting", "The Crown"]}),
    ("Man in his 40s in Randwick, into cricket and Studio Ghibli films, anxious in crowds, catches the bus.",
     {"age_band": "36_to_55", "transport": "bus", "interests": ["cricket", "Studio Ghibli"]}),
    ("Retired engineer, 70, Lewisham, into model trains and Doctor Who, drives.",
     {"transport": "car", "interests": ["model trains", "Doctor Who"]}),
])
def test_rules_reader(note, expected):
    p = intake.rules_profile(note)
    for k, v in expected.items():
        got = [i["name"] for i in p["interests"]] if k == "interests" else p[k]
        assert got == v, (k, got)


def test_rules_reader_handles_every_eval_note():
    for n in SAMPLES:
        p = intake.rules_profile(n["note"])
        assert p["suburb"], n["id"]
        assert 1 <= len(p["interests"]) <= 4, n["id"]
        assert all(i["kind"] == "unknown" for i in p["interests"])


def test_rules_reader_ignores_feelings_and_preferences():
    p = intake.rules_profile("34, Newtown, into vinyl records and Radiohead, quiet, prefers small places, walks.")
    assert [i["name"] for i in p["interests"]] == ["vinyl records", "Radiohead"]


def test_risk_check_still_runs_before_backup_reader():
    out = intake.parse_note(FakeLLM(RuntimeError("down")), "She wants to die, loves gardening, Marrickville")
    assert out["status"] == "risk"


def test_agent_works_end_to_end_without_model():
    note = "74, widowed, loved gardening and Fleetwood Mac, can't drive, lives in Marrickville."
    out = agent.run(note, FakeQloo(), FakeLLM())  # FakeLLM with no answers fails on every call
    assert out["status"] == "ok" and out["plan"]["steps"] and out["plan"]["source"] == "rules"
    assert "backup rules" in out["trace"][0]["detail"]


# ---------- unknown kind resolution ----------

def test_unknown_single_word_prefers_tag():
    r = matcher.resolve_interest(FakeQloo(), {"name": "gardening", "kind": "unknown"})
    assert r["signal"] == "tag"


def test_unknown_phrase_prefers_entity():
    r = matcher.resolve_interest(FakeQloo(), {"name": "Fleetwood Mac", "kind": "unknown"})
    assert r["signal"] == "entity" and r["id"] == "FM"


def test_leading_the_is_ignored_in_matching():
    assert matcher.name_match("the crown", "The Crown") == 1.0
    assert matcher.name_match("crown", "The Crown") == 1.0
    assert matcher.name_match("beatles", "The Beatles") == 1.0


# ---------- model fallback and saved answers ----------

class FakeGroq(llm.GroqLLM):
    def __init__(self, failing=(), **kw):
        self.model, self.fallback_model = "big", "small"
        self.use_cache, self.last_model, self.failing, self.calls = kw.get("use_cache", False), None, set(failing), []

    def _call(self, model, system, user):
        self.calls.append(model)
        if model in self.failing:
            raise RuntimeError("rate limited")
        return {"from": model}


def test_backup_model_used_when_main_fails():
    g = FakeGroq(failing={"big"})
    assert g.chat_json("s", "u") == {"from": "small"} and g.calls == ["big", "small"]


def test_error_when_both_models_fail():
    with pytest.raises(llm.LLMError) as e:
        FakeGroq(failing={"big", "small"}).chat_json("s", "u")
    assert "big" in str(e.value) and "small" in str(e.value)


def test_saved_answer_reused(tmp_path, monkeypatch):
    monkeypatch.setattr(llm, "CACHE_DIR", tmp_path)
    g = FakeGroq(use_cache=True)
    assert g.chat_json("s", "u") == {"from": "big"}
    g.failing = {"big", "small"}
    assert g.chat_json("s", "u") == {"from": "big"} and g.last_model == "saved answer"
    assert g.calls == ["big"]
