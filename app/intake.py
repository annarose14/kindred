"""Read a link worker's free text note into a structured, privacy safe profile."""
import re

RISK_PATTERNS = [re.compile(p) for p in (
    r"suicid",
    r"\bwants? to die\b",
    r"\b(kill|hurt|harm)(s|ing)? (myself|himself|herself|themselves|themself)\b",
    r"\bself[\s-]?harm",
    r"\bend(s|ing)? (my|his|her|their) (own )?life\b",
    r"\boverdos",
    r"\bno reason to live\b",
    r"\bbetter off dead\b",
    r"\b(doesn'?t|does not|don'?t|do not) want to (be here|live|go on)\b",
)]
TRANSPORTS = {"walking_short", "walking", "bus", "car"}
AGE_BANDS = {"35_and_younger", "36_to_55", "55_and_older"}
KINDS = {"artist", "movie", "tv_show", "book", "podcast", "person", "video_game", "activity"}
MAX_NOTE_CHARS = 1500

SYSTEM = """You turn a social prescribing link worker's note into JSON.
Never include the person's name or any identifying detail. Return only this JSON:
{
 "age_band": "35_and_younger" | "36_to_55" | "55_and_older" | null,
 "suburb": string or null,
 "interests": [{"name": string, "kind": "artist"|"movie"|"tv_show"|"book"|"person"|"podcast"|"activity"}],
 "transport": "walking_short" | "walking" | "bus" | "car",
 "needs_step_free": boolean,
 "avoid_alcohol": boolean,
 "prefers_calm": boolean,
 "goal": short string
}
Rules: interests are specific things they love. Use the bare name only:
"Agatha Christie books" -> {"name": "Agatha Christie", "kind": "book"};
"Studio Ghibli films" -> {"name": "Studio Ghibli", "kind": "movie"};
"Fleetwood Mac" -> {"name": "Fleetwood Mac", "kind": "artist"};
"used to sing in a choir" -> {"name": "choir", "kind": "activity"}.
Use "activity" for hobbies and sports, as one or two words. Max 4 interests.
Age: "older", "elderly", "retired", "pensioner" or 55+ -> "55_and_older"; 36 to 55 or "middle aged"
-> "36_to_55"; 35 or under, "student", "young" -> "35_and_younger"; otherwise null. "walking_short" means they can only walk a little.
"can't drive" with no other detail means "bus". Default avoid_alcohol true and prefers_calm true
unless the note clearly says otherwise. needs_step_free is true for wheelchair, walker, frame or
trouble with stairs."""


def has_risk(note):
    text = " ".join(note.lower().split())
    return any(p.search(text) for p in RISK_PATTERNS)


def clean_note(note):
    note = str(note or "").strip()[:MAX_NOTE_CHARS]
    note = re.sub(r"\b[\w.+-]+@[\w-]+\.[\w.]+\b", "[email]", note)
    note = re.sub(r"\b(?:\+?61|0)[\d ]{8,12}\b", "[phone]", note)
    return note


def validate_profile(raw):
    raw = raw if isinstance(raw, dict) else {}
    interests = []
    for i in raw.get("interests") or []:
        if not isinstance(i, dict):
            continue
        name = str(i.get("name", "")).strip()[:60]
        kind = str(i.get("kind", "activity")).strip().lower()
        if name:
            interests.append({"name": name, "kind": kind if kind in KINDS else "activity"})
    age = raw.get("age_band")
    transport = raw.get("transport")
    return {
        "age_band": age if age in AGE_BANDS else None,
        "suburb": (str(raw.get("suburb")).strip()[:40] if raw.get("suburb") else None),
        "interests": interests[:4],
        "transport": transport if transport in TRANSPORTS else "bus",
        "needs_step_free": bool(raw.get("needs_step_free", False)),
        "avoid_alcohol": raw.get("avoid_alcohol", True) is not False,
        "prefers_calm": raw.get("prefers_calm", True) is not False,
        "goal": str(raw.get("goal") or "feel more connected")[:120],
    }


def parse_note(llm, note):
    """Returns {'status': 'ok'|'risk'|'empty'|'error', 'profile': ...}."""
    note = clean_note(note)
    if len(note) < 10:
        return {"status": "empty", "profile": None}
    if has_risk(note):
        return {"status": "risk", "profile": None}
    try:
        raw = llm.chat_json(SYSTEM, note)
    except Exception:
        return {"status": "error", "profile": None}
    profile = validate_profile(raw)
    if not profile["interests"]:
        return {"status": "no_interests", "profile": profile}
    return {"status": "ok", "profile": profile}
