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
KINDS = {"artist", "movie", "tv_show", "book", "podcast", "person", "video_game", "activity", "unknown"}
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


# ---------- backup reader: used only when the language model is unavailable ----------
TRIGGERS = re.compile(r"\b(loves?|loved|likes?|liked|enjoys?|enjoyed|into|adores?|fan of|passionate about|"
                      r"keen on|used to)\b", re.I)
STOP_WORDS = ("lives", "living", "uses", "use ", "can ", "can't", "cannot", "doesn't", "does not", "don't",
              "has ", "had ", "wants", "feels", "feeling", "catches", "takes the", "walks", "drives", "anxious",
              "recently", "moved", "works", "widow", "retired", "years", "year old", "needs", "prefers",
              "avoids", "bus", "since", "lonely", "isolated", "recovering", "single", "limited",
              "quiet", "shy", "small places", "calm", "low", "independent")
FILLER_START = re.compile(r"^(a|an|going to|watching|listening to|playing|reading|sing(ing)? in a|"
                          r"to sing in a|to)\s+", re.I)
LOWER_THE = re.compile(r"^the\s+(?=[a-z])")  # "the theatre" -> "theatre", but keep "The Crown"
FILLER_END = re.compile(r"\s+(on tv|on the tv|books|novels|films|movies|music|songs|shows|a lot|"
                        r"very much|so much)$", re.I)


def _age_band(text):
    t = text.lower()
    m = re.search(r"\b(\d{2})s\b", t) or re.search(r"\b(\d{2})\b(?!\s*(km|min|minutes|m\b))", t)
    if m:
        age = int(m.group(1))
        if age >= 55:
            return "55_and_older"
        if age >= 36:
            return "36_to_55"
        if age >= 16:
            return "35_and_younger"
    if re.search(r"\b(older|elderly|retired|pensioner|widow|widower|grandmother|grandfather)\b", t):
        return "55_and_older"
    if re.search(r"\b(young|student|teen|twenties)\b", t):
        return "35_and_younger"
    return None


def _transport(text):
    t = text.lower()
    if re.search(r"\b(walker|wheelchair|frame|walking stick|cane|bad hip|short walks?|walk a little|"
                 r"can only walk|limited mobility)\b", t):
        return "walking_short"
    if re.search(r"\b(can'?t|cannot|doesn'?t|does not|no longer) drive\b", t):
        return "bus"
    if re.search(r"\b(drives|has a car|by car)\b", t):
        return "car"
    if re.search(r"\b(walks|walk everywhere|walking)\b", t) and "bus" not in t:
        return "walking"
    return "bus"


def _interests(text):
    found, active = [], False
    for clause in re.split(r"[,.;]|\bbut\b", text):
        clause = clause.strip()
        if not clause:
            active = False
            continue
        m = TRIGGERS.search(clause)
        if m:
            clause, active = clause[m.end():].strip(), True
        elif not active or any(w in clause.lower() for w in STOP_WORDS):
            active = False
            continue
        raw = [x.strip() for x in re.split(r"\s+and\s+|\s*&\s*|/", clause) if x.strip()]
        parts, i = [], 0
        while i < len(raw):  # "Gilbert and Sullivan", "Simon and Garfunkel" stay together
            one = lambda x: len(x.split()) == 1 and x[:1].isupper()
            if i + 1 < len(raw) and one(raw[i]) and one(raw[i + 1]):
                parts.append(f"{raw[i]} and {raw[i + 1]}")
                i += 2
            else:
                parts.append(raw[i])
                i += 1
        for part in parts:
            part = FILLER_START.sub("", part)
            part = FILLER_END.sub("", LOWER_THE.sub("", part)).strip(" '\"")
            if 2 < len(part) <= 40 and len(part.split()) <= 5 and not any(w in part.lower() for w in STOP_WORDS):
                found.append({"name": part, "kind": "unknown"})
    seen, out = set(), []
    for i in found:
        key = i["name"].lower()
        if key not in seen:
            seen.add(key)
            out.append(i)
    return out[:4]


def rules_profile(note):
    """Read a note without the language model. Qloo later confirms which interests are real."""
    from app.suburbs import find_suburb
    suburb, _ = find_suburb(note)
    t = note.lower()
    return validate_profile({
        "age_band": _age_band(note),
        "suburb": suburb.title() if suburb else None,
        "interests": _interests(note),
        "transport": _transport(note),
        "needs_step_free": bool(re.search(r"\b(wheelchair|walker|frame|step free|stairs)\b", t)),
        "avoid_alcohol": True,
        "prefers_calm": True,
        "goal": "feel more connected",
    })


def parse_note(llm, note):
    """Returns {'status': 'ok'|'risk'|'empty'|'no_interests', 'profile': ..., 'reader': 'model'|'rules'}."""
    note = clean_note(note)
    if len(note) < 10:
        return {"status": "empty", "profile": None}
    if has_risk(note):
        return {"status": "risk", "profile": None}
    reader = "model"
    try:
        profile = validate_profile(llm.chat_json(SYSTEM, note))
    except Exception:
        profile, reader = rules_profile(note), "rules"
    if not profile["interests"]:
        return {"status": "no_interests", "profile": profile, "reader": reader}
    return {"status": "ok", "profile": profile, "reader": reader}
