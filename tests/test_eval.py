"""Tests for the evaluation helpers (offline)."""
import json

from eval import run_eval, score
from tests.conftest import MARRICKVILLE, PROFILE, FakeLLM, FakeQloo, place


class PlaceSearchQloo(FakeQloo):
    def search(self, query, types=None, take=5):
        if types == "urn:entity:place":
            if "marrickville park" in query.lower():
                return [place("P1", "Marrickville Park", "park")]
            if "corner pub" in query.lower():
                return [place("PB", "Corner Pub", "pub")]
            if "far cafe" in query.lower():
                return [place("FC", "Far Cafe", "cafe", lat=-33.80, lon=151.30)]
            return []
        return super().search(query, types, take)


def test_verify_found_near():
    c = run_eval.verify_place(PlaceSearchQloo(), "Marrickville Park", "Marrickville", MARRICKVILLE, PROFILE)
    assert c["found"] and c["within_reach"] and not c["alcohol_focused"]


def test_verify_not_found_is_not_guessed():
    c = run_eval.verify_place(PlaceSearchQloo(), "Imaginary Tea Garden", "Marrickville", MARRICKVILLE, PROFILE)
    assert c["found"] is False and c["within_reach"] is None


def test_verify_flags_pub():
    pub = run_eval.verify_place(PlaceSearchQloo(), "Corner Pub", "Marrickville", MARRICKVILLE, PROFILE)
    assert pub["alcohol_focused"]


def test_far_namesake_counts_as_not_found():
    far = run_eval.verify_place(PlaceSearchQloo(), "Far Cafe", "Marrickville", MARRICKVILLE, PROFILE)
    assert far["found"] is False and far["far_namesake_km"] > 15


def test_found_but_beyond_reach_within_15km():
    q = BranchQloo()
    q.search = lambda query, types=None, take=5: [place("M", "Mid Cafe", "cafe", lat=-33.95, lon=151.156)]
    c = run_eval.verify_place(q, "Mid Cafe", "Marrickville", MARRICKVILLE, dict(PROFILE, transport="walking_short"))
    assert c["found"] and c["within_reach"] is False


def test_baseline_plan_parsing_and_errors():
    llm = FakeLLM({"steps": [{"place_name": "X Park", "suburb": "Newtown", "why": "w"}, "junk", {"why": "no name"}],
                   "group": {"name": "G"}})
    plan = run_eval.baseline_plan(llm, "note")
    assert [s["name"] for s in plan["steps"]] == ["X Park"] and plan["group"]["name"] == "G"
    assert run_eval.baseline_plan(FakeLLM(RuntimeError("x"), RuntimeError("y")), "note", wait=0) == {"error": "RuntimeError"}


def _row(found_flags):
    return {"kindred": {"steps": [{}] * 3, "checks": [{"found": f, "within_reach": f or None,
                                                       "alcohol_focused": False, "closed": False} for f in found_flags]},
            "baseline": {"steps": [], "checks": []}}


def test_summarise():
    s = run_eval.summarise([_row([True, True, False])], "kindred")
    assert s["places"] == 3 and s["found_pct"] == 67 and s["within_reach_pct"] == 100
    assert run_eval.summarise([_row([])], "baseline") == {"places": 0}


def test_blind_page_hides_system_names_and_escapes():
    rows = [{"id": "n01", "note": "<b>note</b>",
             "kindred": {"steps": [{"name": "K Park", "why": "k"}], "group": {"name": "KG"}},
             "baseline": {"steps": [{"name": "B Cafe", "why": "b"}], "group": None}}]
    page = run_eval.blind_page(rows, {"n01": {"A": "baseline", "B": "kindred"}})
    assert "Kindred" not in page.split("<h2>")[1] and "&lt;b&gt;note" in page
    assert page.index("B Cafe") < page.index("K Park")  # A is baseline here


def test_tally_maps_choices_through_key():
    key = {"n01": {"A": "kindred", "B": "baseline"}, "n02": {"A": "baseline", "B": "kindred"}, "n03": {"A": "kindred", "B": "baseline"}}
    ratings = [{"id": "n01", "choice": "a"}, {"id": "n02", "choice": "B"}, {"id": "n03", "choice": "tie"},
               {"id": "n04", "choice": "A"}, {"id": "n01", "choice": ""}]
    assert score.tally(ratings, key) == (3, {"kindred": 2, "baseline": 0, "tie": 1})


def test_notes_file_is_valid_and_risk_free():
    from app import intake
    from pathlib import Path
    notes = json.loads((Path(run_eval.__file__).parent / "notes.json").read_text())
    assert len(notes) == 20 and len({n["id"] for n in notes}) == 20
    assert not any(intake.has_risk(n["note"]) for n in notes)


class BranchQloo(FakeQloo):
    def search(self, query, types=None, take=5):
        if types == "urn:entity:place":
            return [place("FAR", "Chain Cafe", "cafe", lat=-33.80, lon=151.30),
                    place("NEAR", "Chain Cafe", "cafe", lat=-33.911, lon=151.156)]
        return super().search(query, types, take)


def test_verify_uses_nearest_branch_of_a_chain():
    c = run_eval.verify_place(BranchQloo(), "Chain Cafe", "Marrickville", MARRICKVILLE, PROFILE)
    assert c["found"] and c["within_reach"] and c["distance_km"] < 1


class LookalikeQloo(FakeQloo):
    def search(self, query, types=None, take=5):
        if types == "urn:entity:place":
            grill = place("GRILL", "Taste Baguette & Grill", "bar", lat=-33.88, lon=151.18)
            grill["properties"] = {"is_closed": True}
            return [grill, place("TB", "Taste Baguette", "cafe", lat=-33.911, lon=151.156)]
        return super().search(query, types, take)


def test_verify_prefers_exact_name_over_lookalike():
    c = run_eval.verify_place(LookalikeQloo(), "Taste Baguette", "Marrickville", MARRICKVILLE, PROFILE)
    assert c["matched_name"] == "Taste Baguette" and not c["closed"] and not c["alcohol_focused"]


def test_verify_prefers_the_suggested_place_id():
    c = run_eval.verify_place(LookalikeQloo(), "Taste Baguette", "Marrickville", MARRICKVILLE, PROFILE,
                              entity_id="TB")
    assert c["matched_name"] == "Taste Baguette" and c["within_reach"]


def test_lookalike_still_used_when_it_is_the_only_match():
    class OnlyGrill(LookalikeQloo):
        def search(self, query, types=None, take=5):
            return LookalikeQloo.search(self, query, types, take)[:1]
    c = run_eval.verify_place(OnlyGrill(), "Taste Baguette", "Marrickville", MARRICKVILLE, PROFILE)
    assert c["matched_name"] == "Taste Baguette & Grill"


def test_lookalike_with_a_different_id_is_not_found():
    class OnlyGrill(LookalikeQloo):
        def search(self, query, types=None, take=5):
            return LookalikeQloo.search(self, query, types, take)[:1]
    c = run_eval.verify_place(OnlyGrill(), "Taste Baguette", "Marrickville", MARRICKVILLE, PROFILE,
                              entity_id="TB")
    assert not c["found"] and c["closed"] is None and c["alcohol_focused"] is None
