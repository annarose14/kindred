"""Run the real agent (Qloo + Groq) on sample notes and print what a link worker would see."""
import sys

from app import agent
from app.llm import GroqLLM
from qloo_client import QlooClient

SAMPLES = [
    "74, widowed last year, loved gardening and Fleetwood Mac, can't drive, lives in Marrickville.",
    "Man in his 40s in Randwick, recently moved here, into cricket and Studio Ghibli films, "
    "anxious in crowds, catches the bus.",
    "Older woman in Newtown, uses a walker, used to sing in a choir, loves Agatha Christie books, "
    "doesn't drink.",
]


def show(note, out):
    print("\n" + "=" * 70)
    print("NOTE:", note)
    print("STATUS:", out["status"], "|", out.get("message", ""))
    p = out.get("profile")
    if p:
        print("PROFILE:", p)
    m = out.get("match") or {}
    for i in m.get("interests", []):
        print(f"  Qloo understood '{i['label']}' as '{i['matched']}' ({i['signal']})")
    if m.get("excluded"):
        print("  Hidden for safety:", m["excluded"])
    plan = out.get("plan")
    if plan:
        print(f"\nPLAN ({plan['source']}): {plan['summary']}")
        for s in plan["steps"]:
            pl = s["place"]
            print(f"  Week {s['week']}: {pl['name']} [{pl['category']}, {pl['distance_km']} km, popularity {pl.get('popularity')}]")
            print(f"     {s['action']}")
            print(f"     Why: {s['why']}")
            print(f"     Evidence: {pl['evidence']}")
            if pl["notes"]:
                print(f"     Notes: {pl['notes']}")
        g = plan.get("group")
        if g:
            print(f"  When ready, a group: {g['name']} ({g['suburb']}, {g['distance_km']} km)")
            print(f"     {g['reason']}. {g['when']}. {g['join']}")
            print(f"     Source (checked {g['checked']}): {g['source']}")
        if plan.get("conversation_starter"):
            print("  Conversation starter:", plan["conversation_starter"])
    print("\nTRACE:")
    for t in out["trace"]:
        print(f"  {t['ms']:>6} ms  {t['step']}: {t['detail']}")


if __name__ == "__main__":
    q, llm = QlooClient(), GroqLLM()
    notes = [" ".join(sys.argv[1:])] if len(sys.argv) > 1 else SAMPLES
    for note in notes:
        show(note, agent.run(note, q, llm))
