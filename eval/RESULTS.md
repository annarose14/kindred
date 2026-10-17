# Evaluation: Kindred vs a plain LLM

20 realistic link worker notes across the pilot suburbs (see `eval/notes.json`).
Both systems use the same model, the same note and the same safety instructions.
The only difference: Kindred grounds every place in Qloo and checks it with code.

## Automatic checks on every suggested place

| Check | Kindred | Plain LLM |
|---|---|---|
| Places suggested | 58 | 60 |
| Confirmed as a real place within 15 km (name lookup) | 72% | 13% |
| Within reach for how they travel (of found places) | 98% | 75% |
| Alcohol focused venues (of found places) | 0 | 0 |
| Closed venues (of found places) | 0 | 0 |

How to read this: every Kindred place is a Qloo place with real coordinates, chosen by distance and safety rules in code. The name lookup above is a separate, stricter check applied the same way to both systems. It misses some real places (its rate on Kindred's places, which are all real, shows how many), so both figures understate reality by a similar amount. Qloo's name search is worldwide, so a same-name place more than 15 km away counts as not found (for example a library with the same name in London).

## Blind human review

Not rated yet.

## Limitations

* One rater, 20 notes: a small, early check, not a clinical trial.
* Qloo coverage of small community venues varies by suburb.
* Groups come from a hand checked list of 14 local groups, not from Qloo.
