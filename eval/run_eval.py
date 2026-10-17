"""Kindred vs a plain LLM on the same notes.

Usage (from ~/kindred):  python -m eval.run_eval          (resumes: keeps notes that already worked)
                         python -m eval.run_eval --fresh  (redo every note)
Writes private files to eval/private/ (git ignored, because they contain Qloo data):
  results.json        everything both systems produced, plus automatic checks
  blind_review.html   plans shown as A and B in random order, for a human to judge
  key.json            which of A/B is Kindred (open only after rating)
Prints a summary of the automatic checks.

Fairness: the baseline uses the same model, the same note and the same safety instructions
(calm places, no alcohol venues, within reach, real places only). The only difference is that
Kindred grounds its choices in Qloo and checks them with code.
"""
import html
import json
import random
import sys
import time
from pathlib import Path

from app import agent, intake, safety
from app.llm import GroqLLM
from app.matcher import name_match
from app.suburbs import find_suburb
from qloo_client import QlooClient

HERE = Path(__file__).resolve().parent
NEARBY_KM = 15  # Qloo's name search is worldwide; a same-name place further away is a different place.
PRIVATE = HERE / "private"
SEED = 2026
PAUSE = 4  # seconds between notes, to stay under the free model's rate limit

BASELINE_SYSTEM = """You help a social prescribing link worker in Sydney, Australia.
Read the note about a lonely person and suggest a gentle 3 week plan of 3 specific, REAL,
currently open places near their suburb (week 1 quietest, week 3 most social), plus one real
local group or club they could join later. Only suggest places that are calm, not alcohol
focused, and within reach given how they travel. Never invent places.
Return only JSON:
{"steps": [{"week": 1, "place_name": string, "suburb": string, "action": string, "why": string}],
 "group": {"name": string, "where": string, "when": string, "how_to_join": string}}"""


def baseline_plan(llm, note, wait=15):
    raw = None
    for attempt in range(2):
        try:
            raw = llm.chat_json(BASELINE_SYSTEM, note)
            break
        except Exception as e:
            if attempt == 1:
                return {"error": type(e).__name__}
            time.sleep(wait)
    steps = []
    for s in (raw.get("steps") or [])[:3]:
        if isinstance(s, dict) and s.get("place_name"):
            steps.append({"name": str(s["place_name"])[:80], "suburb": str(s.get("suburb", ""))[:40],
                          "action": str(s.get("action", ""))[:200], "why": str(s.get("why", ""))[:300]})
    g = raw.get("group") if isinstance(raw.get("group"), dict) else None
    return {"steps": steps, "group": g}


def verify_place(q, name, suburb, origin, profile, entity_id=None):
    """Look the place up in Qloo near the suburb. Returns a dict of checks.

    entity_id: the Qloo ID of the place a system actually suggested, when it has one. If the
    lookup returns that exact place it is used, so a different place with a similar name
    (e.g. "Taste Baguette & Grill" for "Taste Baguette") is never checked by mistake.
    """
    out = {"found": False, "distance_km": None, "within_reach": None, "alcohol_focused": None, "closed": None}
    try:
        results = q.search(f"{name} {suburb}".strip(), types="urn:entity:place", take=5)
    except Exception:
        return out
    # Among same-name results, use the one nearest the person's suburb (chains have many branches).
    matches = [r for r in results
               if name_match(name, r.get("name", "")) >= 0.9 or name_match(r.get("name", ""), name) >= 0.9]
    if entity_id:
        # We know exactly which place was suggested: a similar name with a different ID is a
        # different place, so it must not be checked in its place.
        matches = [r for r in matches
                   if r.get("entity_id") == entity_id or name_match(name, r.get("name", "")) == 1.0]
    if not matches:
        return out
    with_dist = [(safety.distance_km(r, origin), r) for r in matches]
    near = [x for x in with_dist if x[0] is not None and x[0] <= NEARBY_KM]
    if not near:
        out["far_namesake_km"] = min((d for d, _ in with_dist if d is not None), default=None)
        return out
    # Best match first: the very place suggested, then an exact name, then the nearest.
    def rank(x):
        d, r = x
        same_place = bool(entity_id) and r.get("entity_id") == entity_id
        exact = name_match(name, r.get("name", "")) == 1.0
        return (not same_place, not exact, d)
    best = min(near, key=rank)[1]
    out["found"] = True
    out["matched_name"] = best.get("name")
    dist = safety.distance_km(best, origin)
    if dist is not None:
        out["distance_km"] = round(dist, 1)
        limit = safety.MAX_KM.get(profile.get("transport", "bus"), 5.0)
        out["within_reach"] = dist <= limit
    out["alcohol_focused"] = safety.alcohol_level(best) == 2
    out["closed"] = safety.is_closed(best)
    return out


def summarise(rows, system):
    places = [p for r in rows for p in r[system]["checks"]]
    n = len(places)
    if not n:
        return {"places": 0}
    found = [p for p in places if p["found"]]
    with_dist = [p for p in found if p["within_reach"] is not None]
    return {
        "places": n,
        "found_in_qloo": len(found),
        "found_pct": round(100 * len(found) / n),
        "within_reach_pct": round(100 * sum(p["within_reach"] for p in with_dist) / len(with_dist)) if with_dist else None,
        "alcohol_focused": sum(1 for p in found if p["alcohol_focused"]),
        "closed": sum(1 for p in found if p["closed"]),
        "plans_with_3_steps": sum(1 for r in rows if len(r[system]["steps"]) == 3),
    }


def blind_page(rows, key):
    css = ("body{font:17px/1.5 system-ui,sans-serif;max-width:1200px;margin:2rem auto;padding:0 1rem;color:#1F1A2E}"
           ".pair{display:grid;grid-template-columns:1fr 1fr;gap:1rem;margin:1rem 0 2.5rem}"
           ".plan{border:1px solid #E3DFEC;border-radius:12px;padding:1rem 1.2rem}h2{margin-top:2.5rem}"
           ".note{background:#F7F5FB;padding:.8rem 1rem;border-radius:10px}li{margin-bottom:.5rem}"
           "@media(max-width:800px){.pair{grid-template-columns:1fr}}")
    parts = [f"<!doctype html><meta charset=utf-8><title>Blind review</title><style>{css}</style>",
             "<h1>Blind review: which plan would you give this person?</h1>",
             "<p>For each note, read plan A and plan B. Without searching which system made which, "
             "write in <b>eval/private/ratings.csv</b>: note id, A or B or tie, and a few words why. "
             "Judge on: fits what they love, safe and calm, realistic to reach, specific enough to act on. "
             "Whether each place really exists is measured separately by the automatic checks, so judge "
             "the plan as written.</p>"]
    for r in rows:
        nid = r["id"]
        sides = {key[nid]["A"]: "A", key[nid]["B"]: "B"}
        blocks = {}
        for system in ("kindred", "baseline"):
            items = "".join(
                f"<li><b>Week {i + 1}: {html.escape(s['name'])}</b><br>{html.escape(s.get('why', ''))}</li>"
                for i, s in enumerate(r[system]["steps"]))
            g = r[system].get("group") or {}
            gtxt = html.escape(str(g.get("name", "none")))
            blocks[sides[system]] = f"<div class=plan><h3>Plan {sides[system]}</h3><ol>{items}</ol><p><b>Group:</b> {gtxt}</p></div>"
        parts.append(f"<h2>{nid}</h2><p class=note>{html.escape(r['note'])}</p><div class=pair>{blocks['A']}{blocks['B']}</div>")
    return "\n".join(parts)


def main():
    PRIVATE.mkdir(exist_ok=True)
    notes = json.loads((HERE / "notes.json").read_text())
    q, llm = QlooClient(), GroqLLM()
    rng = random.Random(SEED)
    rows, key = [], {}
    previous = {}
    results_file = PRIVATE / "results.json"
    if "--fresh" not in sys.argv and results_file.exists():
        for r in json.loads(results_file.read_text()).get("rows", []):
            if r.get("status") == "ok" and r["kindred"]["steps"] and r["baseline"]["steps"]:
                previous[r["id"]] = r

    for n, item in enumerate(notes):
        key[item["id"]] = dict(zip(("A", "B"), rng.sample(["kindred", "baseline"], 2)))
        if item["id"] in previous:
            rows.append(previous[item["id"]])
            print(f"{item['id']}: kept from the last run")
            continue
        if n:
            time.sleep(PAUSE)
        t0 = time.time()
        k = agent.run(item["note"], q, llm)
        base = baseline_plan(llm, item["note"])
        profile = k.get("profile") or intake.validate_profile({})
        suburb_name, origin = find_suburb(profile.get("suburb") or item["note"])

        k_steps = [{"name": s["place"]["name"], "why": s["why"], "id": s["place"].get("id")}
                   for s in (k.get("plan") or {}).get("steps", [])]
        k_group = (k.get("plan") or {}).get("group")
        row = {
            "id": item["id"], "note": item["note"], "status": k["status"], "suburb": suburb_name,
            "kindred": {"steps": k_steps, "group": {"name": k_group["name"]} if k_group else None,
                        "checks": [verify_place(q, s["name"], suburb_name or "", origin, profile, s.get("id"))
                                   for s in k_steps]},
            "baseline": {"steps": base.get("steps", []), "group": base.get("group"),
                         "checks": [verify_place(q, s["name"], s.get("suburb") or suburb_name or "", origin, profile)
                                    for s in base.get("steps", [])]},
            "seconds": round(time.time() - t0, 1),
        }
        rows.append(row)
        kf = sum(c["found"] for c in row["kindred"]["checks"])
        bf = sum(c["found"] for c in row["baseline"]["checks"])
        reader = next((t["detail"] for t in k.get("trace", []) if t["step"] == "read_note"), "")
        row["read_with_rules"] = "backup rules" in reader
        print(f"{item['id']}: {row['status']:>8}{' (rules)' if row['read_with_rules'] else ''} | Kindred places found {kf}/{len(k_steps)} | "
              f"plain LLM found {bf}/{len(row['baseline']['steps'])} | {row['seconds']}s")

    summary = {"kindred": summarise(rows, "kindred"), "baseline": summarise(rows, "baseline")}
    (PRIVATE / "results.json").write_text(json.dumps({"summary": summary, "rows": rows}, indent=2))
    (PRIVATE / "key.json").write_text(json.dumps(key, indent=2))
    (PRIVATE / "blind_review.html").write_text(blind_page(rows, key))
    ratings = PRIVATE / "ratings.csv"
    if not ratings.exists():
        ratings.write_text("id,choice,why\n" + "".join(f"{r['id']},,\n" for r in rows))

    print("\nSUMMARY (automatic checks)")
    for system, s in summary.items():
        print(f"  {system:9s} {s}")
    print("\nNext: open eval/private/blind_review.html, fill eval/private/ratings.csv, then run "
          "python -m eval.score")


if __name__ == "__main__":
    main()
