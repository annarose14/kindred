"""When someone doesn't drink at all, places that serve alcohol are hidden too, not just pubs."""
import pytest

from app import intake, safety
from tests.conftest import MARRICKVILLE, PROFILE, place

DELI = place("D", "Sideways Deli Cafe", "cafe", tags=["Wine", "Cozy"])  # serves alcohol, not a pub


def test_default_allows_cafe_that_serves_wine():
    assert safety.check_place(DELI, PROFILE, MARRICKVILLE)[0]


def test_no_alcohol_hides_it():
    ok, reasons, _ = safety.check_place(DELI, dict(PROFILE, no_alcohol=True), MARRICKVILLE)
    assert not ok and reasons == ["serves alcohol"]


def test_no_alcohol_still_reports_pubs_as_alcohol_focused():
    pub = place("P", "Corner Pub", "pub")
    assert safety.check_place(pub, dict(PROFILE, no_alcohol=True), MARRICKVILLE)[1] == ["alcohol focused"]


@pytest.mark.parametrize("note,expected", [
    ("Woman in her 70s, Dulwich Hill, loves crosswords, doesn't drink.", True),
    ("Man, 50, Newtown, sober for two years, likes jazz.", True),
    ("Teetotal retired teacher in Glebe who loves opera.", True),
    ("Man, 55, Kingsford, enjoys chess, avoids pubs.", False),
    ("Woman, 60, Coogee, enjoys a glass of wine, loves swimming.", False),
])
def test_backup_reader_detects_not_drinking(note, expected):
    assert intake.rules_profile(note)["no_alcohol"] is expected


def test_validate_keeps_flag_only_when_true():
    assert intake.validate_profile({"no_alcohol": True})["no_alcohol"] is True
    assert intake.validate_profile({"no_alcohol": "yes"})["no_alcohol"] is False
    assert intake.validate_profile({})["no_alcohol"] is False


def test_model_prompt_explains_the_difference():
    assert "avoids pubs" in intake.SYSTEM and "no_alcohol" in intake.SYSTEM
