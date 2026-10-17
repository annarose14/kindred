"""Score the blind review and write a public summary (numbers only, no Qloo data).

Usage (from ~/kindred):  python -m eval.score
Reads eval/private/results.json, key.json and ratings.csv. Writes eval/RESULTS.md.
"""
import csv
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PRIVATE = HERE / "private"


def tally(ratings, key):
    wins = {"kindred": 0, "baseline": 0, "tie": 0}
    rated = 0
    for r in ratings:
        nid, choice = r.get("id", "").strip(), r.get("choice", "").strip().upper()
        if nid not in key or choice not in ("A", "B", "TIE"):
            continue
        rated += 1
        wins["tie" if choice == "TIE" else key[nid][choice]] += 1
    return rated, wins


def pct(a, b):
    return f"{round(100 * a / b)}%" if b else "n/a"


def write_results(summary, rated, wins, n_notes):
    k, b = summary["kindred"], summary["baseline"]
    lines = [
        "# Evaluation: Kindred vs a plain LLM",
        "",
        f"{n_notes} realistic link worker notes across the pilot suburbs (see `eval/notes.json`).",
        "Both systems use the same model, the same note and the same safety instructions.",
        "The only difference: Kindred grounds every place in Qloo and checks it with code.",
        "",
        "## Automatic checks on every suggested place",
        "",
        "| Check | Kindred | Plain LLM |",
        "|---|---|---|",
        f"| Places suggested | {k['places']} | {b['places']} |",
        f"| Confirmed as a real place within 15 km (name lookup) | {k['found_pct']}% | {b['found_pct']}% |",
        f"| Within reach for how they travel (of found places) | {k['within_reach_pct']}% | {b['within_reach_pct']}% |",
        f"| Alcohol focused venues (of found places) | {k['alcohol_focused']} | {b['alcohol_focused']} |",
        f"| Closed venues (of found places) | {k['closed']} | {b['closed']} |",
        "",
        "How to read this: every Kindred place is a Qloo place with real coordinates, chosen by distance "
        "and safety rules in code. The name lookup above is a separate, stricter check applied the same way "
        "to both systems. It misses some real places (its rate on Kindred's places, which are all real, shows "
        "how many), so both figures understate reality by a similar amount. "
        "Qloo's name search is worldwide, so a same-name place more than 15 km away counts as not found "
        "(for example a library with the same name in London).",
        "",
        "## Blind human review",
        "",
    ]
    if rated:
        lines += [
            f"{rated} notes rated without knowing which plan came from which system.",
            "",
            "| Preferred | Count | Share |",
            "|---|---|---|",
            f"| Kindred | {wins['kindred']} | {pct(wins['kindred'], rated)} |",
            f"| Plain LLM | {wins['baseline']} | {pct(wins['baseline'], rated)} |",
            f"| Tie | {wins['tie']} | {pct(wins['tie'], rated)} |",
        ]
    else:
        lines.append("Not rated yet.")
    lines += ["", "## Limitations", "",
              "* One rater, 20 notes: a small, early check, not a clinical trial.",
              "* Qloo coverage of small community venues varies by suburb.",
              "* Groups come from a hand checked list of 14 local groups, not from Qloo."]
    (HERE / "RESULTS.md").write_text("\n".join(lines) + "\n")


def main():
    data = json.loads((PRIVATE / "results.json").read_text())
    key = json.loads((PRIVATE / "key.json").read_text())
    path = PRIVATE / "ratings.csv"
    ratings = list(csv.DictReader(path.open())) if path.exists() else []
    rated, wins = tally(ratings, key)
    write_results(data["summary"], rated, wins, len(data["rows"]))
    print(f"Rated {rated} notes: Kindred {wins['kindred']}, plain LLM {wins['baseline']}, tie {wins['tie']}")
    print("Wrote eval/RESULTS.md")


if __name__ == "__main__":
    main()
