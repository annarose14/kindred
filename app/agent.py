"""The Kindred agent: note -> profile -> Qloo taste match -> safety checks -> plan.

Every step is written to a trace so the link worker (and judges) can see why.
The agent acts on its own when results are weak:
  * if Qloo doesn't recognise an interest, it asks the LLM for well known examples and retries;
  * if too few safe places are found, it widens the travel distance once.
"""
import time

from app import groups, intake, matcher, planner
from app.suburbs import find_suburb

MIN_CANDIDATES = 3
# Only named films, shows, books, artists and people are retried through well known examples.
# Hobbies are never swapped for a loosely related title (no "birdwatching" -> "The Birds").
MEDIA_KINDS = {"artist", "movie", "tv_show", "book", "person", "podcast"}
WIDER = {"walking_short": "walking", "walking": "bus", "bus": "car"}

ALT_SYSTEM = """Qloo's taste database did not recognise a named film studio, series, author, band or
artist. Suggest up to 3 of its most famous works or members so they can be searched by exact title.
Examples: "Studio Ghibli" -> "Spirited Away" (movie); "Pixar" -> "Toy Story" (movie).
Only give works that ARE the thing named, never something merely similar. Return only JSON:
{"alternatives": [{"name": string, "kind": "artist"|"movie"|"tv_show"|"book"|"person"|"activity"}]}"""

MESSAGES = {
    "empty": "Please add a short note about the person: interests, suburb and how they get around.",
    "risk": ("This note mentions possible risk of harm. Kindred is not the right first step. "
             "Please follow your service's escalation process now."),
    "error": "The note couldn't be read just now. Please try again in a moment.",
    "no_interests": ("Kindred plans gentle first steps for someone who is lonely, so it needs a short note "
                     "about the person: their suburb, how they get around, and at least one thing they love "
                     "(a hobby, band, film, book or food). For example: \"70, Mascot, loves fried rice and "
                     "Elvis, takes the bus.\""),
    "unknown_suburb": ("That suburb isn't in the pilot area yet. Kindred covers inner Sydney: the Inner West, "
                       "inner city, eastern suburbs and Mascot. For example Marrickville, Newtown, Glebe, "
                       "Surry Hills, Randwick, Bondi or Mascot."),
    "no_interests_found": "Qloo didn't recognise those interests. Try naming a specific band, film or hobby.",
    "no_places": "No safe matches nearby. Try allowing a longer trip or adding another interest.",
}


def _names(items):
    """['A', 'B'] -> "'A' and 'B'" for a readable trace."""
    items = [f"'{i}'" for i in items]
    return " and ".join([", ".join(items[:-1]), items[-1]]) if len(items) > 1 else (items[0] if items else "nothing")


def describe_hidden(excluded):
    """{'too far': 2, 'closed': 1} -> '2 too far, 1 closed' (largest first)."""
    if not excluded:
        return "none"
    items = sorted(excluded.items(), key=lambda kv: (-kv[1], kv[0]))
    return ", ".join(f"{n} {reason}" for reason, n in items)


def retry_with_examples(q, llm, interest):
    """Ask the LLM for concrete examples of an interest Qloo didn't know, and try them."""
    try:
        raw = llm.chat_json(ALT_SYSTEM, f"Interest: {interest['name']} (kind: {interest.get('kind')})")
        alts = raw.get("alternatives", []) if isinstance(raw, dict) else []
    except Exception:
        return None, []
    tried = []
    for alt in alts[:3]:
        if not isinstance(alt, dict) or not alt.get("name"):
            continue
        tried.append(str(alt["name"])[:60])
        r = matcher.resolve_interest(q, alt)
        if r:
            r["label"] = f"{r['matched']} ({interest['name']})"
            return r, tried
    return None, tried


def run(note, q, llm, profile_override=None):
    trace, t0 = [], time.time()

    def log(step, detail):
        trace.append({"step": step, "detail": detail, "ms": int((time.time() - t0) * 1000)})

    if profile_override:
        profile = intake.validate_profile(profile_override)
        log("read_note", "Used the edited profile")
    else:
        parsed = intake.parse_note(llm, note)
        if parsed["status"] != "ok":
            log("read_note", f"Stopped: {parsed['status']}")
            return {"status": parsed["status"], "message": MESSAGES[parsed["status"]],
                    "profile": parsed["profile"], "trace": trace}
        profile = parsed["profile"]
        how = {"rules": " (language model unavailable, read with backup rules)",
               "model+rules": " (backup rules found interests the language model missed)"}.get(parsed.get("reader"), "")
        log("read_note", f"Found {len(profile['interests'])} interests in {profile['suburb']}{how}")

    resolved, unresolved = matcher.resolve_all(q, profile.get("interests", []))
    for i in resolved:
        log("understand", f"'{i['label']}' → Qloo {i['signal']} '{i['matched']}'")
    for interest in unresolved:
        if interest.get("kind") not in MEDIA_KINDS:
            log("retry", f"Qloo didn't know '{interest['name']}' as a hobby; skipped rather than guessed")
            continue
        r, tried = retry_with_examples(q, llm, interest)
        if r:
            resolved.append(r)
            log("retry", f"Qloo didn't know '{interest['name']}'; tried {_names(tried)}, used '{r['matched']}'")
        else:
            log("retry", f"Qloo didn't know '{interest['name']}'; tried {_names(tried)}, none found, so skipped")

    match = matcher.find_places(q, profile, resolved=resolved)
    if match.get("error"):
        log("match", f"Stopped: {match['error']}")
        return {"status": match["error"], "message": MESSAGES[match["error"]],
                "profile": profile, "trace": trace}
    log("match", f"{len(match['candidates'])} safe places from {len(match['categories_used'])} place "
                 f"types; hidden: {describe_hidden(match['excluded'])}")

    if len(match["candidates"]) < MIN_CANDIDATES and profile["transport"] in WIDER:
        wider = dict(profile, transport=WIDER[profile["transport"]])
        retry = matcher.find_places(q, wider, resolved=resolved)
        if len(retry.get("candidates", [])) > len(match["candidates"]):
            match = retry
            match["widened_to"] = wider["transport"]
            log("widen", f"Too few matches, widened travel to '{wider['transport']}'")

    if len(match["candidates"]) < MIN_CANDIDATES:
        nearby = matcher.neighbours(match.get("suburb"), match.get("widened_to") or profile["transport"])
        if nearby:
            travel = dict(profile, transport=match.get("widened_to") or profile["transport"])
            retry = matcher.find_places(q, travel, resolved=resolved, extra_suburbs=nearby)
            if len(retry.get("candidates", [])) > len(match["candidates"]):
                retry["widened_to"] = match.get("widened_to")
                match = retry
                log("nearby", f"Few matches in {profile['suburb']}; also searched {', '.join(n.title() for n in nearby)}")

    if not match["candidates"]:
        return {"status": "no_places", "message": MESSAGES["no_places"], "profile": profile,
                "match": match, "trace": trace}

    plan = planner.make_plan(llm, profile, match["candidates"])
    detail = f"Plan written by {plan['source']} with {len(plan['steps'])} steps"
    if plan.get("fallback_reason"):
        detail += f" (LLM plan rejected: {plan['fallback_reason']})"
    if plan.get("skipped"):
        detail += f" (skipped: {plan['skipped']})"
    log("plan", detail)
    _, origin = find_suburb(profile.get("suburb"))
    plan["group"] = groups.match_group(profile, match["interests"], origin)
    if plan["group"]:
        log("group", f"Suggested '{plan['group']['name']}' as the social next step: "
                     f"{plan['group']['reason']}")
    else:
        log("group", "No checked local group nearby fits yet; the worker can add one")
    return {"status": "ok", "profile": profile, "match": match, "plan": plan, "trace": trace}


# ---------- follow up: adapt one week after the worker reports back ----------
CLOSER_KM = 0.2  # "too far" needs somewhere clearly closer, not 50 metres closer
REASONS = {
    "too_far": "it was too far",
    "too_busy": "it felt too busy or loud",
    "not_their_thing": "it wasn't their kind of place",
    "not_ready": "they weren't ready yet",
}


def _clean_steps(steps):
    out = []
    for s in (steps or [])[:3]:
        place = s.get("place") if isinstance(s, dict) else None
        if not isinstance(place, dict) or not place.get("id"):
            return None
        out.append(dict(s))
    return out or None


def adapt(q, profile, steps, week, outcome, reason=None):
    """Update a plan after follow up. Only the reported week changes; nothing is stored."""
    trace, t0 = [], time.time()

    def log(step, detail):
        trace.append({"step": step, "detail": detail, "ms": int((time.time() - t0) * 1000)})

    steps = _clean_steps(steps)
    if not steps or not isinstance(week, int) or not 1 <= week <= len(steps):
        return {"status": "bad_request", "message": "That week isn't part of this plan."}
    profile = intake.validate_profile(profile)
    current = steps[week - 1]["place"]

    if outcome == "went":
        steps[week - 1] = dict(steps[week - 1], done=True, changed=None)
        nxt = next((s for s in steps if not s.get("done")), None)
        message = (f"Week {week} went well. Next: {nxt['place']['name']}." if nxt
                   else "All three weeks done. This is a good moment to suggest the group.")
        log("follow_up", f"Week {week} at {current['name']} went well")
        return {"status": "ok", "steps": steps, "profile": profile, "message": message, "trace": trace}

    if outcome != "not_yet" or reason not in REASONS:
        return {"status": "bad_request", "message": "Please choose what got in the way."}

    adjusted = dict(profile)
    max_pressure = current.get("pressure", 2)
    avoid_category = None
    if reason == "too_far":
        # How they travel hasn't changed; this place was just further than they managed.
        # Look for somewhere clearly closer, allowing an equally quiet library or museum too.
        max_pressure = max(max_pressure, 1)
    elif reason == "too_busy":
        adjusted["strict_calm"] = True
    elif reason == "not_ready":
        max_pressure = max(0, max_pressure - 1)
    elif reason == "not_their_thing":
        avoid_category = current.get("category")
    log("follow_up", f"Week {week} didn't happen because {REASONS[reason]}")

    resolved, _ = matcher.resolve_all(q, adjusted.get("interests", []))
    exclude = {s["place"]["id"] for s in steps}
    current_km = current.get("distance_km")

    def acceptable(c):
        if c.get("pressure", 2) > max_pressure or (avoid_category and c["category"] == avoid_category):
            return False
        if reason == "too_far" and current_km is not None and c.get("distance_km") is not None:
            return c["distance_km"] <= current_km - CLOSER_KM
        return True

    found = matcher.find_places(q, adjusted, resolved=resolved, exclude_ids=exclude, limit=20)
    options = [c for c in found.get("candidates", []) if acceptable(c)]
    if not options and found.get("suburb"):
        nearby = matcher.neighbours(found["suburb"], adjusted["transport"])
        if nearby:
            found = matcher.find_places(q, adjusted, resolved=resolved, exclude_ids=exclude,
                                        extra_suburbs=nearby, limit=20)
            options = [c for c in found.get("candidates", []) if acceptable(c)]
            log("nearby", f"Also searched {', '.join(n.title() for n in nearby)}")

    if not options:
        log("adapt", "No better option found; plan kept")
        if reason == "too_far":
            hint = (f"{current['name']} is already the nearest calm place that fits. "
                    "A lift, a companion for the first visit, or a shorter stay there may help.")
        else:
            hint = (f"No better option than {current['name']} nearby yet. "
                    "It may help to talk through what would make it easier.")
        # Nothing changed, so the person's details stay exactly as they were.
        return {"status": "ok", "steps": steps, "profile": profile, "trace": trace, "message": hint}

    best = max(options, key=lambda c: c["score"])
    steps[week - 1] = {"week": week, "place": best, "action": f"Visit {best['name']} at a quiet time",
                       "why": planner.explain(best), "done": False,
                       "changed": {"from": current["name"], "because": REASONS[reason]}}
    log("adapt", f"Replaced {current['name']} with {best['name']} because {REASONS[reason]}")
    return {"status": "ok", "steps": steps, "profile": adjusted, "trace": trace,
            "message": f"Week {week} changed to {best['name']}, because {REASONS[reason]}."}
