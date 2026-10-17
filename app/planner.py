"""Build a gentle 3 step plan. The LLM may only choose and order Qloo matched places.

Facts shown to the link worker ("why") are built in code from Qloo evidence, never by the LLM,
so the agent cannot claim a place runs a choir, a class or a group unless the data says so.
"""
import json
import re

CLAIM_WORDS = re.compile(
    r"\b(join|joining|session|sessions|class|classes|group|groups|club|clubs|hosts?|hosted|"
    r"workshop|workshops|meet-?ups?|event|events|program|programs|volunteer\w*|lessons?|"
    r"fully accessible|wheelchair accessible|free)\b", re.I)

SYSTEM = """You help a social prescribing link worker plan gentle first steps for a lonely person.
Choose 3 places from the candidate list by "id" and order them by "pressure" from lowest
(week 1, quiet and solo) to highest (week 3, where people gather). Prefer 3 different kinds of
place, and use at most one cafe, bakery or tea house unless there is no other choice.
Never invent places.
For each step write one short "action" (under 20 words) about simply visiting the place,
e.g. "Short walk around the gardens on a weekday morning". Do NOT claim the place runs groups,
classes, sessions, events or programs, and do NOT claim accessibility. Do NOT assume a job,
family, routine or time of day beyond "a quiet time" or "a weekday morning". You know nothing
beyond the candidate data.
Return only JSON:
{"summary": string under 30 words for the link worker,
 "steps": [{"place_id": string, "action": string}],
 "conversation_starter": one friendly question the worker can ask the person about the plan}"""


def _brief(candidates):
    return [{k: c.get(k) for k in ("id", "name", "category", "pressure", "distance_km", "feel",
                                   "evidence")} for c in candidates]


def _join(items):
    items = list(items)
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " and " + items[-1]


def explain(place):
    """Plain, factual reason from Qloo data only: how it feels, who likes it, what fits."""
    parts = []
    feel = place.get("feel") or []
    if feel:
        parts.append(_join(feel).capitalize())
    liked = place.get("liked_by") or []
    if liked:
        parts.append(f"popular with people who enjoy {_join(liked)}")
    fits = [e for e in place.get("evidence", []) if e.startswith("Tagged")]
    if fits:
        parts.append(fits[0][0].lower() + fits[0][1:])
    if not parts:
        return "Nearby and calm."
    text = "; ".join(parts) + "."
    return text[0].upper() + text[1:]


def safe_action(text, place):
    """Keep the LLM's wording unless it claims something the data doesn't show."""
    text = " ".join(str(text or "").split())[:160]
    known = " ".join([place.get("name") or ""] + (place.get("evidence") or [])).lower()
    for m in CLAIM_WORDS.finditer(text):
        if m.group(0).lower() not in known:
            return f"Visit {place['name']} at a quiet time"
    return text or f"Visit {place['name']} at a quiet time"


def validate_plan(raw, candidates):
    """Return (plan or None, reason). Skips bad steps; needs at least 2 good ones."""
    if not isinstance(raw, dict):
        return None, "not a JSON object"
    by_id = {c["id"]: c for c in candidates}
    steps, used, skipped = [], set(), []
    for s in (raw.get("steps") or [])[:3]:
        pid = s.get("place_id") if isinstance(s, dict) else None
        if pid not in by_id:
            skipped.append(f"unknown place {pid!r}")
            continue
        if pid in used:
            skipped.append("repeated place")
            continue
        used.add(pid)
        place = by_id[pid]
        steps.append({"week": len(steps) + 1, "place": place,
                      "action": safe_action(s.get("action"), place), "why": explain(place)})
    if len(steps) < min(2, len(candidates)):
        return None, "too few valid steps (" + ", ".join(skipped or ["none given"]) + ")"
    return {
        "summary": " ".join(str(raw.get("summary", "")).split())[:300],
        "steps": steps,
        "conversation_starter": " ".join(str(raw.get("conversation_starter", "")).split())[:200],
        "source": "agent",
        "skipped": skipped,
    }, "ok"


FOOD = {"Cafe", "Bakery", "Tea house"}


def _kind(c):
    return "Food" if c.get("category") in FOOD else c.get("category")


def fallback_plan(candidates, reason=""):
    """Week 1 quietest, week 3 most social, week 2 in between; different kinds of place when possible."""
    by_quiet = sorted(candidates, key=lambda c: (c.get("pressure", 2), -c["score"]))
    by_social = sorted(candidates, key=lambda c: (-c.get("pressure", 2), -c["score"]))
    chosen = []
    if by_quiet:
        chosen.append(by_quiet[0])
    social = next((c for c in by_social if c not in chosen and _kind(c) != _kind(chosen[0])), None) \
        or next((c for c in by_social if c not in chosen), None)
    if social:
        chosen.append(social)
    used = {_kind(c) for c in chosen}
    middle = next((c for c in by_quiet if c not in chosen and _kind(c) not in used), None) \
        or next((c for c in by_quiet if c not in chosen), None)
    if middle:
        chosen.append(middle)
    chosen = sorted(chosen, key=lambda c: (c.get("pressure", 2), -c["score"]))
    steps = [{"week": i + 1, "place": c, "action": f"Visit {c['name']} at a quiet time",
              "why": explain(c)} for i, c in enumerate(chosen)]
    return {"summary": "Gentle first steps, quietest place first.", "steps": steps,
            "conversation_starter": "Which of these feels easiest to try first?",
            "source": "rules", "fallback_reason": reason}


def make_plan(llm, profile, candidates):
    if not candidates:
        return None
    user = json.dumps({"goal": profile.get("goal"), "candidates": _brief(candidates)})
    try:
        plan, reason = validate_plan(llm.chat_json(SYSTEM, user), candidates)
    except Exception as e:
        plan, reason = None, f"LLM error: {type(e).__name__}"
    return plan or fallback_plan(candidates, reason)
