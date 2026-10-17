"""Plain code rules that decide which places are safe and suitable.

These rules never depend on the LLM, so they can be tested and trusted.
"""
import math
import re

ALCOHOL_CATEGORIES = {
    "bar", "pub", "brewery", "night_club", "nightclub", "winery",
    "cocktail_bar", "wine_bar", "beer_garden", "distillery", "brewpub",
    "sports_bar", "liquor_store",
}
ALCOHOL_NAME_WORDS = ("brewery", "brewing", "taproom", "tavern", "distillery", "wine bar")
ALCOHOL_TAG_WORDS = (
    "alcohol", "hard liquor", "craft beer", "cocktail", "beer", "wine", "brewery", "happy hour",
)
LOUD_TAG_WORDS = ("rowdy", "late night", "bustling", "loud", "party", "nightlife",
                  "tourist", "crowd", "busy", "queue", "long line", "instagram")
# Specialist services and institutions: real places, but not social venues to send someone to.
SPECIALIST_WORDS = ("asylum", "refugee", "faculty", "university", "college", "school", "hospital",
                    "clinic", "medical", "legal", "court", "police", "council chambers", "detention",
                    "rehab", "centrelink", "headquarters", "office")
# Places that are never a good social prescription: gambling, tattoo, vape and adult venues.
UNSUITABLE_WORDS = ("tattoo", "piercing", "vape", "tobacco", "smoke shop", "casino", "pokies",
                    "betting", "tab", "bookmaker", "adult", "sex shop", "pawn")
UNSUITABLE_CATEGORIES = {"tattoo_shop", "tattoo_parlor", "casino", "betting_shop", "gambling",
                         "vape_shop", "tobacco_shop", "adult_entertainment", "pawn_shop"}
# Businesses you can't actually visit and sit in.
NOT_VISITABLE_WORDS = ("pre-order", "pre order", "preorder", "online only", "order online",
                       "delivery only", "catering", "wholesale", "ghost kitchen", "pop-up", "pop up")
# Physically demanding venues: hidden for older or less mobile people unless it's their interest.
PHYSICAL_WORDS = ("boulder", "climbing", "gym", "crossfit", "trampoline", "ninja", "parkour",
                  "boxing", "martial art", "skate", "f45", "rock wall")
CALM_TAG_WORDS = ("relaxing", "quiet", "cozy", "comfortable", "calm", "peaceful", "community oriented")
ACCESS_TAG_TYPE = "urn:tag:accessibility:place"

# How far someone can reasonably go, in km, by how they get around.
MAX_KM = {"walking_short": 0.8, "walking": 1.5, "bus": 5.0, "car": 10.0}


def haversine_km(lat1, lon1, lat2, lon2):
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = p2 - p1
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def tag_names(place):
    return [str(t.get("name", "")).lower() for t in place.get("tags", [])]


def category_ids(place):
    out = set()
    for t in place.get("tags", []):
        tid = str(t.get("id", ""))
        if tid.startswith("urn:tag:category:place:"):
            out.add(tid.rsplit(":", 1)[-1])
    return out


def is_closed(place):
    props = place.get("properties", {}) or {}
    if props.get("is_closed") is True:
        return True
    name = str(place.get("name", "")).lower()
    return "now closed" in name or "permanently closed" in name


def alcohol_level(place):
    """0 = not alcohol focused, 1 = serves alcohol, 2 = alcohol is the point."""
    if category_ids(place) & ALCOHOL_CATEGORIES:
        return 2
    name = str(place.get("name", "")).lower()
    if any(w in name for w in ALCOHOL_NAME_WORDS):
        return 2
    hits = sum(1 for n in tag_names(place) if any(w in n for w in ALCOHOL_TAG_WORDS))
    if hits >= 2:
        return 2
    return 1 if hits == 1 else 0


def loudness(place):
    names = tag_names(place)
    loud = sum(1 for n in names if any(w in n for w in LOUD_TAG_WORDS))
    calm = sum(1 for n in names if any(w in n for w in CALM_TAG_WORDS))
    return loud - calm


def accessibility_tags(place):
    return [t.get("name") for t in place.get("tags", []) if t.get("type") == ACCESS_TAG_TYPE]


def distance_km(place, origin):
    loc = place.get("location") or {}
    if origin is None or "lat" not in loc or "lon" not in loc:
        return None
    return haversine_km(origin[0], origin[1], loc["lat"], loc["lon"])


def is_specialist(place):
    name = str(place.get("name", "")).lower()
    return any(re.search(rf"\b{w}", name) for w in SPECIALIST_WORDS)


def is_unsuitable(place):
    if category_ids(place) & UNSUITABLE_CATEGORIES:
        return True
    name = str(place.get("name", "")).lower()
    return any(re.search(rf"\b{w}\b", name) for w in UNSUITABLE_WORDS)


def is_not_visitable(place):
    name = str(place.get("name", "")).lower()
    return any(w in name for w in NOT_VISITABLE_WORDS)


def is_too_physical(place, profile):
    vulnerable = (profile.get("age_band") == "55_and_older" or profile.get("needs_step_free")
                  or profile.get("transport") == "walking_short")
    if not vulnerable:
        return False
    # Name and venue type only, never descriptive tags: a park with a skate ramp or a
    # climbing frame is still a calm park, but a bouldering gym with a cafe is still a gym.
    text = " ".join([str(place.get("name", "")).lower()] + sorted(category_ids(place)))
    hits = [w for w in PHYSICAL_WORDS if w in text]
    if not hits:
        return False
    liked = " ".join(str(i.get("name", "")).lower() for i in profile.get("interests", []))
    families = {"boulder": "climb", "rock wall": "climb", "climbing": "climb", "gym": "fitness",
                "crossfit": "fitness", "f45": "fitness", "martial art": "martial", "boxing": "box"}
    return not any(w[:5] in liked or families.get(w, "~") in liked for w in hits)


def check_place(place, profile, origin):
    """Return (ok, reasons_excluded, notes) for one place."""
    reasons, notes = [], []
    if is_closed(place):
        reasons.append("closed")
    if is_specialist(place) or is_unsuitable(place):
        reasons.append("not a social venue")
    if is_not_visitable(place):
        reasons.append("not a place to visit")
    level = alcohol_level(place)
    if profile.get("avoid_alcohol", True) and level == 2:
        reasons.append("alcohol focused")
    elif profile.get("no_alcohol") and level >= 1:
        reasons.append("serves alcohol")
    loud_limit = 1 if profile.get("strict_calm") else 2
    if profile.get("prefers_calm", True) and loudness(place) >= loud_limit:
        reasons.append("too loud")
    if is_too_physical(place, profile):
        reasons.append("too physical")

    dist = distance_km(place, origin)
    limit = MAX_KM.get(profile.get("transport", "bus"), MAX_KM["bus"])
    if dist is not None and dist > limit:
        reasons.append(f"too far ({dist:.1f} km)")

    if profile.get("needs_step_free"):
        if accessibility_tags(place):
            notes.append("accessibility listed")
        else:
            notes.append("access not listed, phone ahead")
    return (not reasons), reasons, notes
