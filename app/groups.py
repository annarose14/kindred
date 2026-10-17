"""Real local groups for the final, social step of a plan.

Qloo knows places, not choirs or garden clubs, so this short list is hand checked from
official council, library and organisation pages. Every entry keeps its source link and the
date it was checked, so a link worker can confirm details before referring someone.
Locations are approximate (suburb or street level) and only used for distance.
"""
from app import safety

CHECKED = "2026-10-17"

GROUPS = [
    {
        "id": "g_addison_garden",
        "name": "Addison Road Community Garden",
        "suburb": "Marrickville",
        "where": "Addison Road Community Centre, 142 Addison Road, Marrickville",
        "when": "Working bee on the third Sunday of each month, 11am to 1pm",
        "join": "Drop in at a working bee, or email addison.rd.community.garden@gmail.com",
        "keywords": ["garden", "gardening", "plants", "vegetables", "compost", "outdoors",
                     "sustainability", "nature", "growing"],
        "location": (-33.9050, 151.1630),
        "source": "https://www.innerwest.nsw.gov.au/explore/parks-sport-and-recreation/community-gardens/addison-road-community-garden",
    },
    {
        "id": "g_neac_garden",
        "name": "NEAC Graveyard Community Garden",
        "suburb": "Newtown",
        "where": "Behind the caretaker's cottage, Camperdown Cemetery, Church Street, Newtown",
        "when": "Working bee every Saturday, 10.30am to 1.30pm",
        "join": "New members and visitors are welcome to drop in during a working bee",
        "keywords": ["garden", "gardening", "plants", "vegetables", "outdoors", "nature",
                     "growing", "history"],
        "location": (-33.8935, 151.1790),
        "source": "https://www.innerwest.nsw.gov.au/community-gardens/neac-graveyard-community-garden",
    },
    {
        "id": "g_randwick_garden",
        "name": "Randwick Community Organic Garden",
        "suburb": "Randwick",
        "where": "Paine Reserve, Randwick (enter via Fennelly Street)",
        "when": "Working bee on the third Sunday of each month, 9am to 11am",
        "join": "Visitors welcome at working bees; membership is open to all",
        "keywords": ["garden", "gardening", "organic", "plants", "vegetables", "outdoors",
                     "nature", "growing", "sustainability"],
        "location": (-33.9100, 151.2440),
        "source": "https://sites.google.com/rcog.org.au/rcog/",
    },
    {
        "id": "g_haberfield_shed",
        "name": "Haberfield Men's Shed",
        "suburb": "Haberfield",
        "where": "Mary MacKillop Outreach Centre, 1 to 5 Rogers Avenue, Haberfield",
        "when": "Tuesday, Wednesday and Friday, 10am to 12pm",
        "join": "Phone 02 8752 2500",
        "keywords": ["woodwork", "woodworking", "tools", "making", "fixing", "repair",
                     "carpentry", "building", "diy", "cars", "metalwork", "crafts"],
        "location": (-33.8810, 151.1390),
        "source": "https://www.innerwest.nsw.gov.au/sheds",
    },
    {
        "id": "g_leichhardt_shed",
        "name": "Leichhardt Community Men's Shed",
        "suburb": "Rozelle",
        "where": "Building B703, South Crescent, Callan Park, Rozelle",
        "when": "Tuesdays, 9.30am to 1.30pm",
        "join": "Phone 0493 463 132 or visit lcmsi.com",
        "keywords": ["woodwork", "woodworking", "tools", "making", "fixing", "repair",
                     "carpentry", "building", "diy", "cars", "metalwork", "crafts"],
        "location": (-33.8640, 151.1640),
        "source": "https://www.innerwest.nsw.gov.au/sheds",
    },
    {
        "id": "g_marrickville_shed",
        "name": "Marrickville Men's Shed",
        "suburb": "Redfern",
        "where": "107 Redfern Street, Redfern",
        "when": "Thursdays, 10am to 3pm",
        "join": "Phone 0414 620 519",
        "keywords": ["woodwork", "woodworking", "tools", "making", "fixing", "repair",
                     "carpentry", "building", "diy", "cars", "metalwork", "crafts"],
        "location": (-33.8930, 151.2040),
        "source": "https://www.innerwest.nsw.gov.au/sheds",
    },
    {
        "id": "g_walk_marrickville",
        "name": "Heart Foundation Walking groups (Marrickville)",
        "suburb": "Marrickville",
        "where": "Several free groups meet in Marrickville, e.g. Sunrise Walkers and Enmore Energisers",
        "when": "Morning walks; check the listing for days and meeting points",
        "join": "Free; register on the Heart Foundation Walking site",
        "keywords": ["walking", "walks", "exercise", "fitness", "outdoors", "nature", "hiking",
                     "bushwalking", "running"],
        "location": (-33.9106, 151.1553),
        "source": "https://walking.heartfoundation.org.au/walking/location/marrickville-s-sydney-nsw-2204",
    },
    {
        "id": "g_iw_book_clubs",
        "name": "Inner West Libraries book clubs",
        "suburb": "Marrickville",
        "where": "Inner West library branches (e.g. Marrickville, Stanmore, Dulwich Hill)",
        "when": "Monthly; up to 10 members per club",
        "join": "Email Library@innerwest.nsw.gov.au or phone 9392 5588 to ask about vacancies",
        "keywords": ["books", "reading", "novels", "literature", "mystery", "crime", "poetry",
                     "writing", "authors"],
        "media_kinds": ["book", "person"],
        "locations": [(-33.9100, 151.1560), (-33.8945, 151.1650), (-33.9045, 151.1380),
                      (-33.8830, 151.1570), (-33.9150, 151.1690)],  # Marrickville, Stanmore, Dulwich Hill, Leichhardt, St Peters
        "source": "https://www.innerwest.nsw.gov.au/library-programs-and-events/book-clubs",
    },
    {
        "id": "g_iw_library_clubs",
        "audience": "seniors",
        "name": "Inner West Libraries adult programs",
        "suburb": "Marrickville",
        "where": "Inner West library branches",
        "when": "Varies: Scrabble, Canasta, knitting, film clubs, Family History Research Group",
        "join": "Phone the library on 9392 5588",
        "keywords": ["knitting", "crafts", "sewing", "scrabble", "cards", "canasta", "games",
                     "film", "films", "movies", "cinema", "history", "family history", "puzzles"],
        "media_kinds": ["movie", "tv_show"],
        "locations": [(-33.9100, 151.1560), (-33.8945, 151.1650), (-33.9045, 151.1380),
                      (-33.8830, 151.1570), (-33.9150, 151.1690)],  # Marrickville, Stanmore, Dulwich Hill, Leichhardt, St Peters
        "source": "https://www.innerwest.nsw.gov.au/live/community-wellbeing/seniors/activities-for-seniors/social-get-togethers-for-seniors",
    },
    {
        "id": "g_st_peters_gathering",
        "audience": "seniors",
        "name": "St Peters Gathering",
        "suburb": "St Peters",
        "where": "St Peters Town Hall",
        "when": "First Wednesday of each month, 10am to 1pm",
        "join": "Phone 02 9558 7504",
        "keywords": [],
        "general": True,
        "location": (-33.9110, 151.1780),
        "source": "https://www.innerwest.nsw.gov.au/live/community-wellbeing/seniors/activities-for-seniors/social-get-togethers-for-seniors",
    },
    {
        "id": "g_randwick_knit",
        "audience": "seniors",
        "name": "The Knit-in Group",
        "suburb": "Randwick",
        "where": "Margaret Martin Library, Randwick",
        "when": "Fourth Friday of the month, 12.30pm to 2.30pm (listed for 2024, check current dates)",
        "join": "Contact Randwick City Library",
        "keywords": ["knitting", "crochet", "crafts", "sewing", "yarn"],
        "location": (-33.9145, 151.2410),
        "source": "https://www.randwick.nsw.gov.au/library/library-services/seniors/seniors-events",
    },
    {
        "id": "g_randwick_ukulele",
        "audience": "seniors",
        "name": "Ukulele Strumming Club",
        "suburb": "Maroubra",
        "where": "Lionel Bowen Library, Maroubra",
        "when": "Last Friday of the month, 10.30am to 11.30am (listed for 2024, check current dates)",
        "join": "Contact Randwick City Library",
        "keywords": ["ukulele", "guitar", "playing music", "instrument", "singing", "choir",
                     "strumming"],
        "location": (-33.9500, 151.2400),
        "source": "https://www.randwick.nsw.gov.au/library/library-services/seniors/seniors-events",
    },
    {
        "id": "g_randwick_coffee",
        "audience": "seniors",
        "name": "Coffee Conversations Connect",
        "suburb": "Maroubra",
        "where": "Lionel Bowen Library, Maroubra",
        "when": "Tuesdays every two weeks, 10.30am to 12pm (listed for 2024, check current dates)",
        "join": "Contact Randwick City Library",
        "keywords": ["conversation", "coffee", "chatting", "english", "language"],
        "general": True,
        "location": (-33.9500, 151.2400),
        "source": "https://www.randwick.nsw.gov.au/library/library-services/seniors/seniors-events",
    },
    {
        "id": "g_randwick_table_tennis",
        "audience": "seniors",
        "name": "Table Tennis For Fun",
        "suburb": "Maroubra",
        "where": "Lionel Bowen Library, Maroubra",
        "when": "Mondays and Fridays, 1pm to 3pm (listed for 2024, check current dates)",
        "join": "Contact Randwick City Library",
        "keywords": ["table tennis", "ping pong", "tennis", "badminton"],
        "location": (-33.9500, 151.2400),
        "source": "https://www.randwick.nsw.gov.au/library/library-services/seniors/seniors-events",
    },
]

# Groups are a weekly commitment, so allow a bit further than for a casual visit.
GROUP_MAX_KM = {"walking_short": 2.0, "walking": 3.0, "bus": 7.0, "car": 12.0}


def _norm(text):
    return " ".join(str(text).lower().replace("-", " ").split())


def _keyword_hit(group, label):
    """True if any group keyword and the interest share a word (gardening ~ garden)."""
    label = _norm(label)
    words = set(label.split())
    for kw in group["keywords"]:
        kw = _norm(kw)
        if kw == label or kw in label or (len(label) >= 4 and label in kw):
            return True
        if any(len(w) >= 4 and len(k) >= 4 and (w.startswith(k[:5]) or k.startswith(w[:5]))
               for w in words for k in kw.split()):
            return True
    return False


def match_group(profile, interests, origin):
    """Pick the best real group for the final step, or None.

    interests: resolved interests from the matcher (label, matched, kind).
    Specific interest matches win over general social groups; nearer wins over further.
    """
    limit = GROUP_MAX_KM.get(profile.get("transport", "bus"), 7.0)
    best = None
    older = profile.get("age_band") == "55_and_older"
    for g in GROUPS:
        if g.get("audience") == "seniors" and not older:
            continue  # listed on council seniors pages
        spots = g.get("locations") or [g["location"]]
        dist = min(safety.haversine_km(origin[0], origin[1], *loc) for loc in spots) if origin else None
        if dist is not None and dist > limit:
            continue
        reason = None
        for i in interests:
            names = [i.get("label", ""), i.get("matched", "")]
            if any(_keyword_hit(g, n) for n in names):
                reason = f"Matches their interest in {i['label']}"
                break
            if i.get("kind") in g.get("media_kinds", []):
                reason = f"A shared way to enjoy {i['label']}"
                break
        if reason is None and g.get("general"):
            reason = "A friendly local social group"
        if reason is None:
            continue
        rank = (0 if not reason.startswith("A friendly") else 1, dist if dist is not None else 99)
        if best is None or rank < best[0]:
            best = (rank, g, reason, dist)
    if not best:
        return None
    _, g, reason, dist = best
    return dict({k: v for k, v in g.items() if k not in ("keywords", "media_kinds", "general", "location", "locations", "audience")},
                reason=reason, distance_km=round(dist, 1) if dist is not None else None,
                checked=CHECKED)
