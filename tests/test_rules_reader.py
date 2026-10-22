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
