"""Kindred web app: serves the page and the agent API.

Run locally:  uvicorn app.main:app --reload --port 8000
Privacy: notes are never logged or stored. Only counts and timings are kept in memory.
"""
import os
import subprocess
import time
from collections import defaultdict, deque
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from app import agent, groups

ROOT = Path(__file__).resolve().parent.parent
STATIC = ROOT / "static"
MAX_NOTE = 1500
RATE_LIMIT = 12          # plans per IP
RATE_WINDOW = 10 * 60    # seconds

SAMPLES = [
    {"title": "Widowed gardener, Marrickville",
     "note": "74, widowed last year, loved gardening and Fleetwood Mac, can't drive, lives in Marrickville."},
    {"title": "New to Randwick, anxious in crowds",
     "note": "Man in his 40s in Randwick, recently moved here, into cricket and Studio Ghibli films, "
             "anxious in crowds, catches the bus."},
    {"title": "Former choir singer with a walker, Newtown",
     "note": "Older woman in Newtown, uses a walker, used to sing in a choir, loves Agatha Christie "
             "books, doesn't drink."},
]


class PlanRequest(BaseModel):
    note: str = ""


def _git_commit():
    sha = os.getenv("RENDER_GIT_COMMIT") or os.getenv("GIT_COMMIT")
    if sha:
        return sha[:7]
    try:
        return subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT,
                                       stderr=subprocess.DEVNULL, text=True).strip()
    except Exception:
        return "unknown"


def create_app(qloo=None, llm=None):
    """qloo and llm can be injected (tests use fakes). Otherwise real clients are made lazily."""
    application = FastAPI(title="Kindred", docs_url="/api/docs", redoc_url=None)
    application.state.qloo = qloo
    application.state.llm = llm
    application.state.hits = defaultdict(deque)
    application.state.stats = {"plans": 0, "started": time.time()}
    commit = _git_commit()

    def clients():
        if application.state.qloo is None:
            from qloo_client import QlooClient
            application.state.qloo = QlooClient()
        if application.state.llm is None:
            from app.llm import GroqLLM
            application.state.llm = GroqLLM()
        return application.state.qloo, application.state.llm

    def rate_limited(ip):
        now, q = time.time(), application.state.hits[ip]
        while q and now - q[0] > RATE_WINDOW:
            q.popleft()
        if len(q) >= RATE_LIMIT:
            return True
        q.append(now)
        return False

    @application.api_route("/", methods=["GET", "HEAD"], include_in_schema=False)
    def index():
        return FileResponse(STATIC / "index.html")

    @application.get("/api/samples")
    def samples():
        return SAMPLES

    @application.api_route("/api/health", methods=["GET", "HEAD"])
    def health():
        return {
            "ok": True,
            "commit": commit,
            "qloo_base": os.getenv("QLOO_BASE_URL", "https://hackathon.api.qloo.com"),
            "llm_model": os.getenv("GROQ_MODEL", "openai/gpt-oss-120b"),
            "groups_listed": len(groups.GROUPS),
            "groups_checked": groups.CHECKED,
            "plans_made_since_start": application.state.stats["plans"],
        }

    @application.post("/api/plan")
    def plan(body: PlanRequest, request: Request):
        ip = request.headers.get("x-forwarded-for", request.client.host if request.client else "?")
        ip = ip.split(",")[0].strip()
        if rate_limited(ip):
            return JSONResponse(status_code=429, content={
                "status": "rate_limited",
                "message": "That's a lot of plans in a short time. Please wait a few minutes and try again."})
        note = (body.note or "").strip()
        if len(note) > MAX_NOTE:
            return JSONResponse(status_code=400, content={
                "status": "too_long",
                "message": f"Please keep the note under {MAX_NOTE} characters."})
        try:
            q, llm = clients()
            result = agent.run(note, q, llm)
        except Exception as e:  # never leak keys or stack traces to the page
            return JSONResponse(status_code=503, content={
                "status": "unavailable",
                "message": "Kindred can't reach its data services right now. Please try again shortly.",
                "error_type": type(e).__name__})
        application.state.stats["plans"] += 1
        return result

    if STATIC.exists():
        application.mount("/static", StaticFiles(directory=STATIC), name="static")
    return application


app = create_app()
