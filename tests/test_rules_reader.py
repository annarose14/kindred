"""The backup reader (used when the language model is busy) must understand everyday phrasing."""
import pytest

from app import intake


@pytest.mark.parametrize("note,expected", [
    ("Man in Kensington, 30, plays chess, walks", ["chess"]),
    ("Randwick, 80, interested in birds and opera", ["birds", "opera"]),
    ("She paints and reads crime novels, Stanmore, 66", ["painting", "crime"]),
    ("Glebe, 33, watches The Office a lot", ["The Office"]),
    ("Erskineville woman, 40, big Beyonce fan, yoga", ["Beyonce", "yoga"]),
    ("Older woman, Leichhardt, used to play piano, takes the bus", ["piano"]),
    ("He sings, Maroubra, 70, walks a little", ["singing"]),
    ("Coogee, 45, she is a fan of Harry Potter and baking", ["Harry Potter", "baking"]),
    ("68, Glebe, loves Gilbert and Sullivan and gardening, bus is fine.", ["Gilbert and Sullivan", "gardening"]),
])
def test_everyday_phrasing_is_understood(note, expected):
    assert [i["name"] for i in intake.rules_profile(note)["interests"]] == expected


def test_suburb_is_never_an_interest():
    names = [i["name"] for i in intake.rules_profile("Enjoys cooking Italian food, Haberfield, 75")["interests"]]
    assert names == ["cooking Italian food"]


def test_needs_and_travel_are_not_interests():
    p = intake.rules_profile("72, Bondi, loves jazz, uses a walker, doesn't drink, takes the bus")
    assert [i["name"] for i in p["interests"]] == ["jazz"]


from tests.conftest import FakeLLM


def test_model_returning_plain_names_still_works():
    out = intake.parse_note(FakeLLM({"suburb": "Glebe", "interests": ["gardening", "jazz"]}),
                            "70, Glebe, loves gardening and jazz, takes the bus")
    assert out["status"] == "ok" and [i["name"] for i in out["profile"]["interests"]] == ["gardening", "jazz"]


def test_model_returning_a_string_of_interests_still_works():
    out = intake.parse_note(FakeLLM({"suburb": "Glebe", "interests": "gardening, jazz"}),
                            "70, Glebe, loves gardening and jazz, takes the bus")
    assert [i["name"] for i in out["profile"]["interests"]] == ["gardening", "jazz"]


def test_model_missing_interests_falls_back_to_rules():
    out = intake.parse_note(FakeLLM({"suburb": "Kensington", "interests": []}),
                            "Man in Kensington, 30, plays chess, walks")
    assert out["status"] == "ok" and out["reader"] == "model+rules"
    assert [i["name"] for i in out["profile"]["interests"]] == ["chess"]


def test_model_missing_suburb_is_filled_from_rules():
    out = intake.parse_note(FakeLLM({"interests": [{"name": "opera", "kind": "music"}]}),
                            "Randwick, 80, interested in birds and opera")
    assert out["profile"]["suburb"] == "Randwick"
    assert [i["name"] for i in out["profile"]["interests"]] == ["opera"]  # model's answer is kept


def test_truly_no_interest_still_asks_for_one():
    out = intake.parse_note(FakeLLM({"suburb": "Glebe", "interests": []}),
                            "70, lives alone in Glebe, takes the bus")
    assert out["status"] == "no_interests"


from app.agent import MESSAGES
from app.suburbs import SUBURBS, find_suburb


def test_new_suburbs_are_found_as_whole_words():
    assert find_suburb("near Mascot Woolworths")[0] == "mascot"
    assert find_suburb("Potts Point")[0] == "potts point"
    assert find_suburb("loves the botanical garden, Marrickville")[0] == "marrickville"
    assert len(SUBURBS) == 48


def test_no_interest_message_explains_what_to_write():
    msg = MESSAGES["no_interests"]
    assert "suburb" in msg and "For example" in msg
