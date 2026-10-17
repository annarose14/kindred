"""Real local groups for the social step, and the too-physical check."""
import re

from app import agent, groups, safety
from app.suburbs import find_suburb
from tests.conftest import MARRICKVILLE, PROFILE, FakeLLM, FakeQloo, place

NEWTOWN = find_suburb("Newtown")[1]
RANDWICK = find_suburb("Randwick")[1]


def interest(label, kind="activity", matched=None):
    return {"label": label, "matched": matched or label, "kind": kind}


# ---------- data quality: every group must be checkable ----------

def test_every_group_has_source_and_details():
    ids = set()
    for g in groups.GROUPS:
        assert g["id"] not in ids
        ids.add(g["id"])
        assert re.match(r"https://", g["source"]), g["name"]
        for field in ("name", "suburb", "where", "when", "join"):
            assert g[field].strip(), (g["name"], field)
        spots = g.get("locations") or [g["location"]]
        for lat, lon in spots:
            assert -34.1 < lat < -33.7 and 151.0 < lon < 151.4, g["name"]
        assert g["keywords"] or g.get("general") or g.get("media_kinds"), g["name"]


def test_old_listings_say_check_dates():
    for g in groups.GROUPS:
        if "2024" in g["when"]:
            assert "check" in g["when"].lower(), g["name"]


# ---------- matching ----------

def test_gardener_in_marrickville_gets_addison_road():
    g = groups.match_group(PROFILE, [interest("gardening")], MARRICKVILLE)
    assert g["id"] == "g_addison_garden" and "gardening" in g["reason"]
    assert g["checked"] and g["source"].startswith("https://")
    assert "keywords" not in g and "location" not in g


def test_gardener_in_newtown_gets_nearest_garden():
    g = groups.match_group(dict(PROFILE, transport="walking_short"), [interest("gardening")], NEWTOWN)
    assert g["id"] == "g_neac_garden"


def test_author_fan_gets_book_club_via_media_kind():
    g = groups.match_group(dict(PROFILE, transport="walking_short"),
                           [interest("Agatha Christie", kind="person")], NEWTOWN)
    assert g["id"] == "g_iw_book_clubs" and "Agatha Christie" in g["reason"]


def test_specific_match_beats_general_group():
    g = groups.match_group(PROFILE, [interest("Fleetwood Mac", "artist"), interest("knitting")], MARRICKVILLE)
    assert g["id"] == "g_iw_library_clubs"


def test_no_specific_match_falls_back_to_general():
    g = groups.match_group(PROFILE, [interest("Fleetwood Mac", "artist")], MARRICKVILLE)
    assert g["id"] == "g_st_peters_gathering" and g["reason"] == "A friendly local social group"


def test_cricket_is_not_forced_into_a_walking_group():
    g = groups.match_group(PROFILE, [interest("cricket")], RANDWICK)
    assert g is None or g["id"] not in ("g_walk_marrickville", "g_randwick_table_tennis")


def test_too_far_groups_are_skipped():
    far = (-33.80, 151.00)  # well outside the pilot area
    assert groups.match_group(dict(PROFILE, transport="walking_short"), [interest("gardening")], far) is None


def test_no_origin_still_works():
    assert groups.match_group(PROFILE, [interest("gardening")], None)["id"]


def test_agent_attaches_group_and_logs_it():
    out = agent.run(None, FakeQloo(), FakeLLM(RuntimeError("x")), profile_override=PROFILE)
    assert out["plan"]["group"]["id"] == "g_addison_garden"
    assert any(t["step"] == "group" and "Addison" in t["detail"] for t in out["trace"])


# ---------- too physical ----------

BOULDER = place("BH", "BlocHaus Bouldering Marrickville", "recreation_center", tags=["Modern"])


def test_bouldering_hidden_for_older_person():
    ok, reasons, _ = safety.check_place(BOULDER, PROFILE, MARRICKVILLE)
    assert not ok and "too physical" in reasons


def test_bouldering_ok_for_younger_person():
    young = dict(PROFILE, age_band="36_to_55")
    assert safety.check_place(BOULDER, young, MARRICKVILLE)[0]


def test_bouldering_ok_if_older_person_loves_climbing():
    climber = dict(PROFILE, interests=[{"name": "rock climbing", "kind": "activity"}])
    assert safety.check_place(BOULDER, climber, MARRICKVILLE)[0]


def test_gym_hidden_for_walker_user_any_age():
    p = dict(PROFILE, age_band="36_to_55", needs_step_free=True)
    assert "too physical" in safety.check_place(place("g", "Anytime Gym", "gym"), p, MARRICKVILLE)[1]


# ---------- review 5 fixes ----------

def test_park_with_skate_ramp_is_not_too_physical():
    park = place("P", "Marrickville Park", "park", tags=["Skate park", "Climbing frame", "Benches"])
    assert safety.check_place(park, PROFILE, MARRICKVILLE)[0]


def test_bouldering_still_hidden_by_name():
    assert "too physical" in safety.check_place(BOULDER, PROFILE, MARRICKVILLE)[1]


def test_online_only_business_hidden():
    for name in ["Annie Makes Cakes (Pre-order online)", "Cake Co - Delivery only", "Ghost Kitchen Eats"]:
        ok, reasons, _ = safety.check_place(place("x", name, "bakery"), PROFILE, MARRICKVILLE)
        assert not ok and "not a place to visit" in reasons, name


def test_normal_bakery_is_visitable():
    assert safety.check_place(place("x", "Bourke Street Bakery", "bakery"), PROFILE, MARRICKVILLE)[0]


def test_planner_prompt_forbids_assumed_routine():
    from app import planner
    assert "Do NOT assume a job" in planner.SYSTEM


def test_bouldering_gym_with_cafe_inside_still_hidden():
    gym = place("BH2", "BlocHaus Bouldering Marrickville | Sydney", "recreation_center", tags=["Modern"])
    gym["tags"].append({"id": "urn:tag:category:place:cafe", "name": "Cafe", "type": "urn:tag:category:place"})
    assert "too physical" in safety.check_place(gym, PROFILE, MARRICKVILLE)[1]


def test_climbing_gym_category_hidden_even_with_plain_name():
    gym = place("CG", "The Wall Marrickville", "climbing_gym")
    assert "too physical" in safety.check_place(gym, PROFILE, MARRICKVILLE)[1]
