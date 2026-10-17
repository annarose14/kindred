from app import safety
from tests.conftest import (BREWERY, CAFE, CLOSED_CAFE, FAR_PARK, LIBRARY, LOUD_CAFE, MARRICKVILLE,
                            PARK, PROFILE, place)


def test_distance_known_value():
    # Marrickville to Randwick is roughly 8.5 km
    d = safety.haversine_km(-33.9106, 151.1553, -33.9145, 151.2410)
    assert 7.5 < d < 9.5


def test_closed_by_flag_and_by_name():
    assert safety.is_closed(CLOSED_CAFE)
    assert safety.is_closed(place("x", "Old Cafe", "cafe", closed=True))
    assert not safety.is_closed(CAFE)


def test_alcohol_levels():
    assert safety.alcohol_level(BREWERY) == 2
    assert safety.alcohol_level(place("x", "Corner Pub", "pub")) == 2
    assert safety.alcohol_level(place("x", "Bistro", "restaurant", tags=["Alcohol"])) == 1
    assert safety.alcohol_level(PARK) == 0


def test_loudness_calm_vs_rowdy():
    assert safety.loudness(LOUD_CAFE) >= 2
    assert safety.loudness(LIBRARY) < 0


def test_check_place_excludes_unsafe():
    for p, reason in [(CLOSED_CAFE, "closed"), (BREWERY, "alcohol focused"), (LOUD_CAFE, "too loud")]:
        ok, reasons, _ = safety.check_place(p, PROFILE, MARRICKVILLE)
        assert not ok and reason in reasons


def test_check_place_distance_depends_on_transport():
    ok_bus, _, _ = safety.check_place(FAR_PARK, dict(PROFILE, transport="bus"), MARRICKVILLE)
    ok_car, _, _ = safety.check_place(FAR_PARK, dict(PROFILE, transport="car"), MARRICKVILLE)
    assert not ok_bus and ok_car


def test_alcohol_allowed_when_profile_says_so():
    ok, _, _ = safety.check_place(BREWERY, dict(PROFILE, avoid_alcohol=False), MARRICKVILLE)
    assert ok


def test_step_free_notes():
    p = dict(PROFILE, needs_step_free=True)
    assert "accessibility listed" in safety.check_place(LIBRARY, p, MARRICKVILLE)[2]
    assert "access not listed, phone ahead" in safety.check_place(PARK, p, MARRICKVILLE)[2]


def test_missing_location_is_not_excluded():
    p = place("x", "No Coords Cafe", "cafe")
    p["location"] = {}
    ok, _, _ = safety.check_place(p, PROFILE, MARRICKVILLE)
    assert ok
