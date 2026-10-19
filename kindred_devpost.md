# Kindred: Devpost submission text

Paste each section into the matching Devpost field. Devpost supports Markdown.

---

## Project name
Kindred

## Tagline (short description, max ~200 characters)
An agent that turns a lonely person's tastes into a gentle three week plan of real, safe places nearby, so social prescribing link workers can help them take the first step.

---

## Inspiration

One in three Australians reports feeling lonely, and long term loneliness is linked to health risks on the scale of smoking. Australia and the UK now have **social prescribing**: a GP refers a lonely patient to a link worker, whose job is to reconnect them with their community.

The hardest part is the very first step. "Join a club" rarely works for someone who hasn't left the house in months. What works is something that already feels like *them*: a place where people who share their tastes already go, close enough to reach, calm enough to walk into alone. Finding that for every patient, by hand, takes a link worker hours.

Qloo knows what people with similar tastes enjoy. We wanted to use that to give link workers a better first step, in seconds.

## What it does

A link worker writes a short note, the way they normally would:

> *74, widowed last year, loved gardening and Fleetwood Mac, can't drive, lives in Marrickville.*

Kindred returns a printable **social prescription**:

* **Three weeks, from quiet to social.** Week 1 is the calmest (a park), week 3 the most social (a café or community centre). Every step names a real place, its distance, and why it fits, using Qloo's own evidence: *"popular with people who enjoy gardening and Fleetwood Mac; tagged Community gardening"*.
* **A real local group** for when they're ready, from a hand checked list with source links and a "checked" date. Here: the Addison Road Community Garden working bee, 0.9 km away.
* **Safety by default.** Pubs and alcohol focused places, closed, loud or tourist crowded venues, physically demanding places for frail people, and anything beyond how far the person can travel are all hidden. For someone who doesn't drink, places that serve alcohol are hidden too.
* **Follow up.** Each week can be marked *It went well* or *Didn't happen* with a reason: too far, too busy, not ready, not their thing. Kindred adapts only that week, and says plainly when there's no better option.
* **A full decision trace.** "How Kindred decided" shows what Qloo understood, how many places were hidden and why, and every step the agent took.

No sign in. Notes are never stored. Contact details are removed before anything reaches a model.

## How we built it

**Qloo is the core of Kindred; the LLM never picks a place on its own.**

1. **Read the note.** A risk check runs first, in plain code: notes that mention self harm stop immediately and tell the worker to follow their escalation process. Then an LLM (gpt-oss-120b on Groq) extracts age band, suburb, travel, interests and needs. If the LLM is down or rate limited, a rules based reader takes over, so the demo never breaks.
2. **Resolve interests in Qloo.** `/search` and `/v2/tags` turn "Fleetwood Mac" into an artist entity and "gardening" into a keyword tag. If Qloo doesn't know a film franchise or author, the agent asks for a well known work ("Studio Ghibli" becomes *Spirited Away*) and tries again. Hobbies are never swapped for loosely related titles.
3. **Find taste matched places.** `/v2/insights` with `filter.type=urn:entity:place`, one call per place category (parks, gardens, libraries, museums, bookshops, cafés, community centres and more), with `filter.location.query`, the person's interests as signals, and `signal.demographics.age`.
4. **Check every place in code.** Distance from the suburb, category tags, `is_closed`, and Qloo's descriptive tags feed transparent safety rules.
5. **Recover when results are thin.** The agent widens travel slightly, then searches neighbouring suburbs.
6. **Plan.** The LLM orders the checked places from quiet to social, but it can only return IDs from the checked list. The "why" text is written in code from Qloo evidence, so it can't be invented. If the LLM fails, a rules planner does the same job.
7. **Match a group** from 14 hand checked groups (council and library pages), by interest, age and distance.

**Stack:** Python, FastAPI, Qloo Insights API, Groq, plain HTML and JavaScript, hosted on Render, 214 offline tests on GitHub Actions.

## Results

We compared Kindred with a plain LLM on 20 realistic notes. Both used the same model, the same note and the same instructions (calm places, no alcohol venues, within reach, real places only). Every suggested place was then looked up by name in Qloo the same way for both.

| Check | Kindred | Plain LLM |
|---|---|---|
| Confirmed as a real place within 15 km | **72%** | 13% |
| Within reach for how the person travels | **98%** | 75% |
| Alcohol focused or closed venues | 0 | 0 |

The plain LLM's plans *sound* more specific ("Glebe Community Choir", "Kingsford Chess Club"), but 87% of its places could not be confirmed as real places nearby. Every Kindred place is a real Qloo place with coordinates. When too few safe places are in reach, Kindred gives a shorter plan rather than inventing one.

## Challenges we ran into

* **Name matching.** Early versions turned "Studio Ghibli" into a yoga studio and "documentaries" into a TV channel. We built strict name rules (accents, joined spellings, word stems, a leading "the") and tested each failure.
* **Evidence that sounded right but wasn't.** "Wheel of Fortune" matched a "Wheelchair accessible" tag. Word stems and stop words fixed it.
* **Places that are real but wrong.** Specialist services, tattoo shops listed as galleries, supermarkets, fast food chains, a bouldering gym for an 80 year old. Each became a rule and a test.
* **The API's quirks.** Search is worldwide and the radius filter isn't reliable, so distance is enforced in code. Category filters are loose, so each place's own category tags are checked.
* **A fair evaluation.** Our first checker matched same name places in London and Toowoomba, and a lookalike restaurant 4 km away. We fixed it to use the nearest branch within 15 km, prefer the exact place suggested, and ignore lookalikes.
* **Rate limits on free models.** Fast timeouts, a backup model, a saved answer cache and the rules fallbacks mean a plan always comes back.

## Accomplishments that we're proud of

* Every place Kindred suggests is real, checked and explained with Qloo evidence.
* The agent is transparent: a link worker can see exactly why each place was chosen and what was hidden.
* It works on a phone, prints as a one page prescription, and keeps working when the LLM doesn't.
* 214 tests, including every bad match we found while testing.

## What we learned

Taste data is strongest when it's combined with hard constraints. Qloo tells us what someone is likely to enjoy; code makes sure it's safe, reachable and real; the LLM is best used for reading messy notes and ordering, not for inventing. We also learned that an honest "no better option" is more useful than a confident wrong answer.

## What's next for Kindred

* Test with practising social prescribing link workers.
* More cities, starting with other Sydney councils.
* Connect to local service directories for groups instead of a hand checked list.
* Let the worker edit a step before printing, and track outcomes over time.

---

## Built with
python, fastapi, qloo, groq, llm, javascript, html, css, render, github-actions, pytest

## Links
* Live demo: https://kindred-9rzv.onrender.com
* Code (MIT licence): https://github.com/annarose14/kindred
