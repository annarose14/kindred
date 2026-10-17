"""Turn a patient's interests into taste matched, safe, nearby places using Qloo."""
import unicodedata
from concurrent.futures import ThreadPoolExecutor

from app import safety
from app.suburbs import find_suburb

PLACE = "urn:entity:place"
CATEGORY_PREFIX = "urn:tag:category:place:"

# slug: (label, social pressure 0 quiet to 3 most social)
# The first six were checked against the live API on 17 Oct 2026.
BASE_CATEGORIES = {
    "park": ("Park", 0),
    "botanical_garden": ("Garden", 0),
    "library": ("Library", 1),
    "museum": ("Museum", 1),
    "cafe": ("Cafe", 2),
    "community_center": ("Community centre", 3),
}
# Extra calm, social place types. Only used if Qloo confirms the category tag exists.
EXTRA_CATEGORIES = {
    "book_store": ("bookstore", "Bookshop", 1),
    "art_gallery": ("art gallery", "Gallery", 1),
    "garden": ("garden", "Garden", 0),
    "community_garden": ("community garden", "Community garden", 2),
    "tea_house": ("tea house", "Tea house", 2),
    "bakery": ("bakery", "Bakery", 2),
    "cultural_center": ("cultural center", "Cultural centre", 3),
    "senior_citizen_center": ("senior center", "Seniors centre", 3),
    "recreation_center": ("recreation center", "Recreation centre", 3),
}
TAG_PREFERENCE = [
    "urn:tag:keyword:qloo:",
    "urn:tag:interests:qloo:",
    "urn:tag:activity_type:qloo:",
    "urn:tag:genre:place:",
    "urn:tag:subgenre:qloo:",
    "urn:tag:genre:media:",
]
AGE_BANDS = {"35_and_younger", "36_to_55", "55_and_older"}
MAX_PER_CATEGORY = 2
# Social prescribing usually works through libraries, parks, gardens and community centres,
# so these get a small boost, and food places (cafe, bakery, tea house) are capped at two.
CIVIC = {"Library", "Park", "Garden", "Community centre", "Community garden", "Seniors centre", "Cultural centre"}
FOOD = {"Cafe", "Bakery", "Tea house"}
CIVIC_BONUS = 0.12
MAX_FOOD = 2
FEEL_TYPES = {"urn:tag:ambience:qloo", "urn:tag:setting:qloo"}
AMENITY_TYPES = {"urn:tag:amenity:qloo", "urn:tag:amenities:place"}
USEFUL_AMENITIES = ("bench", "shade", "seating", "garden", "trees", "lawn", "water view",
                    "quiet room", "lift", "ramp")
# Words that sound odd or unhelpful on a social prescription.
FEEL_BLOCK = ("restroom", "toilet", "commercial", "efficient", "premium", "roadside", "gastronomic",
              "indulgent", "lively", "buzzing", "trendy", "upscale", "expensive", "city center", "central",
              "gender", "credit", "parking", "wifi", "takeout", "delivery", "catering", "gift")
FEEL_NOISE = {"place", "safe", "credit cards", "takeout", "delivery", "catering services",
              "gift wrapping", "parking", "wifi", "free wifi"}

# Words people add that are not part of the name: "Agatha Christie books" -> "Agatha Christie".
FILLER = {"books", "book", "novels", "films", "film", "movies", "movie", "music", "songs", "song",
          "albums", "shows", "show", "series", "tv", "the", "band", "anything", "by", "old", "classic"}
# For each kind the person mentioned, which Qloo types to try, in order.
SEARCH_ORDER = {
    "artist": ["artist", "person"],
    "book": ["person", "book"],
    "movie": ["movie", "person", "brand", "tv_show"],
    "tv_show": ["tv_show", "movie", "person"],
    "person": ["person", "artist"],
    "podcast": ["podcast", "person"],
    "video_game": ["video_game", "brand"],
}


STOP = {"with", "from", "into", "your", "this", "that", "and", "the", "for", "of", "on", "in", "a", "an",
        "to", "at", "by", "their", "about", "or", "its"}
SUFFIXES = ("ings", "ing", "ers", "er", "es", "ed", "s", "e")


def _plain(text):
    """Lower case without accents: "André Rieu" -> "andre rieu"."""
    text = unicodedata.normalize("NFKD", str(text).lower())
    return "".join(ch for ch in text if not unicodedata.combining(ch))


def _words(text):
    return "".join(ch if ch.isalnum() or ch == " " else " " for ch in _plain(text)).split()


def _stem(word):
    for suf in SUFFIXES:
        if word.endswith(suf) and len(word) - len(suf) >= 3:
            return word[: -len(suf)]
    return word


def _stems(text):
    """Meaningful word stems: gardening ~ garden, but wheel != wheelchair and "with" is ignored."""
    return {_stem(w) for w in _words(text) if w not in STOP and len(w) >= 3}


def _joined(text):
    return _stem("".join(w for w in _words(text) if w not in STOP))


def clean_label(name):
    words = _words(name)
    kept = [w for w in words if w not in FILLER]
    return " ".join(kept) if kept else " ".join(words)


def name_match(label, candidate):
    """1.0 exact; 0.9 all words present with at most 1 extra; else 0. A leading "the" is ignored."""
    a = [w for w in _words(label) if w != "the"]
    b = [w for w in _words(candidate) if w != "the"]
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0
    if len(a) == 1:
        return 0.0  # one word like "documentaries" must not become "CNBC Documentaries"
    if set(a) <= set(b) and len(b) - len(a) <= 1:
        return 0.9
    return 0.0


def tag_fits(label, tag_name):
    """Every meaningful word of the interest must appear in the tag ("studio ghibli" != "yoga studio").
    Joined spellings count: "birdwatching" fits "Bird watching"."""
    need = _stems(label)
    have = _stems(tag_name)
    if need and need <= have:
        return True
    return bool(need) and _joined(label) == _joined(tag_name)


UNKNOWN_ORDER = ["artist", "tv_show", "movie", "person", "book"]


def _entity_lookup(q, label, name, order):
    best, best_score = None, 0.0
    for t in order:
        try:
            results = q.search(label, types=f"urn:entity:{t}", take=5)
        except Exception:
            results = []
        for r in results:
            score = name_match(label, r.get("name", ""))
            if score > best_score:
                best, best_score = (r, t), score
        if best_score == 1.0:
            break
    if not best:
        return None
    r, t = best
    return {"label": name, "matched": r.get("name"), "kind": t, "signal": "entity", "id": r.get("entity_id")}


def tag_variants(label):
    """Ways to look a hobby up: as written, joined ("bird watching"), then its main noun
    ("ballroom dancing" -> "dancing"). Never a loose association like a TV show."""
    words = [w for w in label.split() if w not in STOP]
    out = [label]
    if len(words) > 1:
        out += ["".join(words), words[-1]]
    elif words and len(words[0]) > 6:
        out.append(words[0])
    return list(dict.fromkeys(v for v in out if v))


def _tag_lookup(q, label, name):
    for variant in tag_variants(label):
        try:
            tags = q.tags(variant, take=15)
        except Exception:
            tags = []
        for prefix in TAG_PREFERENCE:
            for t in tags:
                if str(t.get("id", "")).startswith(prefix) and tag_fits(variant, t.get("name", "")):
                    return {"label": name, "matched": t.get("name"), "kind": "activity",
                            "signal": "tag", "id": t["id"]}
    return None


def resolve_interest(q, interest):
    """Map {'name','kind'} to a Qloo entity or tag. Returns None if Qloo has no good match.

    A wrong match is worse than no match, so names must match closely.
    kind "unknown" comes from the backup note reader: one word is tried as a hobby tag first,
    longer phrases as a named artist, show, film, person or book first.
    """
    name = str(interest.get("name", "")).strip()
    kind = str(interest.get("kind", "activity")).strip().lower()
    label = clean_label(name)
    if not label:
        return None
    if kind == "unknown":
        if len(label.split()) == 1:
            return _tag_lookup(q, label, name) or _entity_lookup(q, label, name, UNKNOWN_ORDER)
        return _entity_lookup(q, label, name, UNKNOWN_ORDER) or _tag_lookup(q, label, name)
    if kind in SEARCH_ORDER:
        found = _entity_lookup(q, label, name, SEARCH_ORDER[kind])
        if found:
            return found
    return _tag_lookup(q, label, name)


def resolve_all(q, interests):
    resolved, unresolved = [], []
    for i in interests[:4]:
        r = resolve_interest(q, i)
        (resolved if r else unresolved).append(r or i)
    return resolved, unresolved


def categories_for(q):
    """Base categories plus any extra ones Qloo confirms. Cached on the client."""
    cached = getattr(q, "_kindred_categories", None)
    if cached:
        return cached
    cats = {slug: {"label": lab, "pressure": pr} for slug, (lab, pr) in BASE_CATEGORIES.items()}
    for slug, (word, lab, pr) in EXTRA_CATEGORIES.items():
        try:
            ids = {t.get("id") for t in q.tags(word, take=10)}
        except Exception:
            ids = set()
        if CATEGORY_PREFIX + slug in ids:
            cats[slug] = {"label": lab, "pressure": pr}
    try:
        q._kindred_categories = cats
    except AttributeError:
        pass
    return cats


def _query(q, resolved, category, suburb, age_band):
    params = {
        "filter.type": PLACE,
        "filter.tags": CATEGORY_PREFIX + category,
        "filter.location.query": f"{suburb}, Sydney",
        "take": 15,
    }
    key = "signal.interests.entities" if resolved["signal"] == "entity" else "signal.interests.tags"
    params[key] = resolved["id"]
    if age_band in AGE_BANDS:
        params["signal.demographics.age"] = age_band
    try:
        return q.insights(params)
    except Exception:  # one failed query must not break the whole plan
        return []


def place_feel(place):
    """Up to 3 calm, descriptive tags, e.g. ['Relaxing', 'Benches', 'Shade']."""
    out = []
    for t in place.get("tags", []):
        n = str(t.get("name", ""))
        low = n.lower()
        useful = t.get("type") in AMENITY_TYPES and any(w in low for w in USEFUL_AMENITIES)
        if (t.get("type") not in FEEL_TYPES and not useful) or low in FEEL_NOISE:
            continue
        if any(w in low for w in safety.LOUD_TAG_WORDS + safety.ALCOHOL_TAG_WORDS + FEEL_BLOCK):
            continue
        if n not in out:
            out.append(n)
        if len(out) == 3:
            break
    return out


def neighbours(suburb, transport, n=2):
    """Nearest other pilot suburbs the person could reach, nearest first."""
    from app.suburbs import SUBURBS
    home = SUBURBS.get(suburb)
    if not home:
        return []
    reach = max(safety.MAX_KM.get(transport, 5.0), 2.5)
    near = sorted((safety.haversine_km(*home, *loc), name) for name, loc in SUBURBS.items() if name != suburb)
    return [name for d, name in near if d <= reach][:n]


def find_places(q, profile, resolved=None, limit=8, extra_suburbs=(), exclude_ids=()):
    """Main matching step. Returns dict with candidates, excluded summary and interest mapping."""
    suburb, origin = find_suburb(profile.get("suburb"))
    if suburb is None:
        return {"error": "unknown_suburb", "candidates": [], "excluded": {}, "interests": []}

    if resolved is None:
        resolved, _ = resolve_all(q, profile.get("interests", []))
    if not resolved:
        return {"error": "no_interests_found", "candidates": [], "excluded": {}, "interests": []}

    cats = categories_for(q)
    search_in = [suburb] + [x for x in extra_suburbs if x != suburb]
    jobs = [(r, c, where) for where in search_in for r in resolved for c in cats]
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(
            lambda job: _query(q, job[0], job[1], job[2], profile.get("age_band")), jobs))

    places, hits = {}, {}
    for (r, cat, _where), found in zip(jobs, results):
        for rank, p in enumerate(found):
            pid = p.get("entity_id")
            if not pid:
                continue
            places.setdefault(pid, (p, cat))
            hits.setdefault(pid, []).append((r, rank))

    candidates, excluded = [], {}
    exclude_ids = set(exclude_ids)
    for pid, (p, cat) in places.items():
        if pid in exclude_ids:
            continue
        own = safety.category_ids(p)
        if own and cat not in own:
            excluded["wrong type"] = excluded.get("wrong type", 0) + 1
            continue
        ok, reasons, notes = safety.check_place(p, profile, origin)
        if not ok:
            for reason in reasons:
                key = reason.split(" (")[0]
                excluded[key] = excluded.get(key, 0) + 1
            continue

        score, liked_by, matched = 0.0, [], set()
        for r, rank in sorted(hits[pid], key=lambda x: x[1]):
            if r["label"] in matched:
                continue
            matched.add(r["label"])
            score += 1.0 / (rank + 3)
            liked_by.append(r["label"])
        evidence = [f"Popular with people who enjoy {r}" for r in liked_by]

        tnames = [t.get("name", "") for t in p.get("tags", [])]
        for r in resolved:
            stems = _stems(r["label"])
            for tn in tnames:
                if stems & _stems(tn) or (len(stems) == 1 and _joined(r["label"]) == _joined(tn)):
                    score += 0.3
                    evidence.append(f"Tagged \"{tn}\", which fits {r['label']}")
                    break

        loud = safety.loudness(p)
        score -= (0.15 if loud > 0 else 0.05) * max(-3, min(3, loud))
        if safety.alcohol_level(p) == 1:
            score -= 0.15
        dist = safety.distance_km(p, origin)
        if dist is not None:
            score -= 0.05 * dist
        if cats[cat]["label"] in CIVIC:
            score += CIVIC_BONUS
        if not p.get("popularity"):
            score -= 0.1  # little data about this place, prefer better known ones

        props = p.get("properties", {}) or {}
        candidates.append({
            "id": pid,
            "name": p.get("name"),
            "category": cats[cat]["label"],
            "pressure": cats[cat]["pressure"],
            "address": props.get("address"),
            "distance_km": round(dist, 1) if dist is not None else None,
            "hours": props.get("hours"),
            "description": props.get("short_description") or props.get("description"),
            "liked_by": liked_by,
            "feel": place_feel(p),
            "evidence": evidence,
            "notes": notes,
            "interest_count": len(matched),
            "popularity": p.get("popularity"),
            "score": round(score, 4),
        })

    candidates.sort(key=lambda c: (-c["score"], c["name"] or ""))
    picked, per_cat = [], {}
    food = 0
    for c in candidates:
        if per_cat.get(c["category"], 0) >= MAX_PER_CATEGORY:
            continue
        if c["category"] in FOOD:
            if food >= MAX_FOOD:
                continue
            food += 1
        per_cat[c["category"]] = per_cat.get(c["category"], 0) + 1
        picked.append(c)
        if len(picked) >= limit:
            break
    # Make sure at least one social place (pressure 3 or 2) is offered when one exists.
    if picked and max(c["pressure"] for c in picked) < 2:
        social = next((c for c in candidates if c["pressure"] >= 2 and c not in picked), None)
        if social:
            picked[-1 if len(picked) >= limit else len(picked):] = [social]

    return {"suburb": suburb, "candidates": picked, "excluded": excluded, "interests": resolved,
            "categories_used": sorted(cats)}
