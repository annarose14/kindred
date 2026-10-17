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
WIDER = {"walking_short": "walking", "walking": "bus", "bus": "car"}

ALT_SYSTEM = """Qloo's taste database did not recognise an interest. Suggest up to 3 very famous,
mainstream films, TV shows, books or artists that people with this interest typically love, so they
can be searched by exact title. Prefer household names over niche ones.
Examples: a film studio -> its most famous films; a genre -> its best known artists;
a hobby like model trains -> "Thomas & Friends" (tv_show), "The Polar Express" (movie).
Return only JSON:
{"alternatives": [{"name": string, "kind": "artist"|"movie"|"tv_show"|"book"|"person"|"activity"}]}"""

MESSAGES = {
    "empty": "Please add a short note about the person: interests, suburb and how they get around.",
    "risk": ("This note mentions possible risk of harm. Kindred is not the right first step. "
             "Please follow your service's escalation process now."),
    "error": "The note couldn't be read just now. Please try again in a moment.",
    "no_interests": "Kindred needs at least one thing the person enjoys (a hobby, band, film or book).",
    "unknown_suburb": "That suburb isn't in the pilot area yet. Try an Inner West or eastern suburbs suburb.",
    "no_interests_found": "Qloo didn't recognise those interests. Try naming a specific band, film or hobby.",
    "no_places": "No safe matches nearby. Try allowing a longer trip or adding another interest.",
}


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
        how = " (language model unavailable, read with backup rules)" if parsed.get("reader") == "rules" else ""
        log("read_note", f"Found {len(profile['interests'])} interests in {profile['suburb']}{how}")

    resolved, unresolved = matcher.resolve_all(q, profile.get("interests", []))
    for i in resolved:
        log("understand", f"'{i['label']}' -> Qloo {i['signal']} '{i['matched']}'")
    for interest in unresolved:
        r, tried = retry_with_examples(q, llm, interest)
        if r:
            resolved.append(r)
            log("retry", f"Qloo didn't know '{interest['name']}'; tried {tried}, used '{r['matched']}'")
        else:
            log("retry", f"Qloo didn't know '{interest['name']}'; examples {tried} also not found, skipped")

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
