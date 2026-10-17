"""Private diagnostics: show every flagged place and short plans (reads eval/private/results.json).

Usage (from ~/kindred):  python -m eval.inspect_results
"""
import json
from pathlib import Path

data = json.loads((Path(__file__).resolve().parent / "private" / "results.json").read_text())
print("FLAGGED KINDRED PLACES (alcohol, closed, out of reach, not found)")
for r in data["rows"]:
    for step, c in zip(r["kindred"]["steps"], r["kindred"]["checks"]):
        flags = [k for k, bad in (("NOT FOUND", not c["found"]), ("alcohol", c.get("alcohol_focused")),
                                  ("closed", c.get("closed")), ("out of reach", c.get("within_reach") is False)) if bad]
        if flags:
            print(f"  {r['id']} {r['suburb']}: {step['name']!r} -> matched {c.get('matched_name')!r}, "
                  f"{c.get('distance_km')} km, {', '.join(flags)}")
print("\nSHORT KINDRED PLANS")
for r in data["rows"]:
    if len(r["kindred"]["steps"]) < 3:
        print(f"  {r['id']} {r['suburb']}: {len(r['kindred']['steps'])} steps | note: {r['note']}")
print("\nPLAIN LLM PLACES THAT WERE FOUND")
for r in data["rows"]:
    for step, c in zip(r["baseline"]["steps"], r["baseline"]["checks"]):
        if c["found"]:
            print(f"  {r['id']}: {step['name']!r} -> {c.get('distance_km')} km, reach {c.get('within_reach')}")
