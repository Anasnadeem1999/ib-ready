"""FastAPI app: serves the web UI and the JSON API from one process."""

from __future__ import annotations

import hmac
import os
import traceback

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import agents, bank, config, db, engine, llm
from .misconceptions import LIBRARY

WEB = config.REPO_ROOT / "web"

app = FastAPI(title="Tick & Tie", docs_url="/docs")
app.mount("/static", StaticFiles(directory=WEB), name="static")


@app.on_event("startup")
def _startup() -> None:
    db.init()


@app.exception_handler(llm.ModelPolicyError)
async def _policy(_: Request, exc: llm.ModelPolicyError):
    return JSONResponse(status_code=503, content={"error": str(exc)})


@app.exception_handler(Exception)
async def _any(_: Request, exc: Exception):
    traceback.print_exc()
    return JSONResponse(status_code=500, content={"error": "Something went wrong on our side. Please try again."})


@app.get("/")
def index() -> FileResponse:
    return FileResponse(WEB / "index.html")


# ---------------------------------------------------------------- auth
def current_profile(x_auth_token: str | None = Header(default=None)) -> dict:
    prof = db.profile_for_token(x_auth_token)
    if prof is None:
        raise HTTPException(401, "Please sign in again.")
    return prof


def own_session(sid: str, prof: dict) -> dict:
    s = db.session(sid)
    if s is None or s["profile_id"] != prof["id"]:
        raise HTTPException(404, "Session not found.")
    return s


class SignIn(BaseModel):
    name: str = Field(min_length=1, max_length=40)
    password: str = Field(min_length=1, max_length=200)


@app.post("/api/signin")
def signin(body: SignIn) -> dict:
    try:
        prof, token, created = db.sign_in(body.name, body.password)
    except db.AuthError as e:
        raise HTTPException(400, str(e))
    return {"profile": {"id": prof["id"], "name": prof["name"]}, "token": token, "created": created}


@app.get("/api/me")
def me(prof: dict = Depends(current_profile)) -> dict:
    return {"id": prof["id"], "name": prof["name"]}


# ---------------------------------------------------------------- meta
@app.get("/api/health")
def health() -> dict:
    return {"ok": True, "model": config.MODEL_NAME, "key": config.key_source()}


@app.get("/api/meta")
def meta() -> dict:
    return {
        "skills": bank.SKILLS,
        "personas": {k: v[0] for k, v in agents.PERSONAS.items()},
        "modes": {"diagnostic": "Diagnostic", "drill": "Targeted drill", "mixed": "Mixed"},
        "prices": config.PRICE_PER_M,
        "limits": {"session_tokens": config.SESSION_TOKEN_BUDGET, "attempts": config.MAX_ATTEMPTS_PER_QUESTION,
                   "followups": config.MAX_FOLLOWUPS_PER_QUESTION, "answer_chars": config.MAX_ANSWER_CHARS},
        "question_count": len(bank.TEMPLATES),
        "key_present": config.key_source() is not None,
    }


# ---------------------------------------------------------------- profile + sessions (signed in)
@app.get("/api/map")
def profile_map(prof: dict = Depends(current_profile)) -> dict:
    return engine.weakness_map(prof["id"])


class SessionIn(BaseModel):
    mode: str = "diagnostic"
    persona: str = "associate"
    focus: str | None = None


@app.post("/api/session")
def start(body: SessionIn, prof: dict = Depends(current_profile)) -> dict:
    return engine.start_session(prof["id"], body.mode, body.persona, body.focus)


class AnswerIn(BaseModel):
    text: str = Field(max_length=20000)
    seconds: float | None = None


@app.post("/api/session/{sid}/answer")
async def answer(sid: str, body: AnswerIn, prof: dict = Depends(current_profile)) -> dict:
    own_session(sid, prof)
    try:
        return await engine.answer(sid, body.text, body.seconds)
    except ValueError as e:
        raise HTTPException(400, str(e))


@app.post("/api/session/{sid}/end")
async def end(sid: str, prof: dict = Depends(current_profile)) -> dict:
    own_session(sid, prof)
    try:
        return await engine.end_session(sid)
    except ValueError as e:
        raise HTTPException(400, str(e))


@app.get("/api/session/{sid}/events")
def events(sid: str, prof: dict = Depends(current_profile)) -> dict:
    own_session(sid, prof)
    return {"events": db.events(sid), "usage": db.session_usage(sid)}


class FeedbackIn(BaseModel):
    session_id: str | None = None
    rating: int | None = Field(default=None, ge=1, le=10)
    vs_current: str | None = Field(default=None, max_length=40)
    found_new: str | None = Field(default=None, max_length=40)
    time_to_find: str | None = Field(default=None, max_length=40)
    prep_today: str | None = Field(default=None, max_length=300)
    quote: str | None = Field(default=None, max_length=1000)
    consent: bool = False


@app.post("/api/feedback")
def feedback(body: FeedbackIn, prof: dict = Depends(current_profile)) -> dict:
    if body.session_id:
        own_session(body.session_id, prof)
    db.add_feedback(prof["id"], body.session_id, rating=body.rating, vs_current=body.vs_current,
                    found_new=body.found_new, time_to_find=body.time_to_find, prep_today=body.prep_today,
                    quote=body.quote, consent=int(body.consent))
    return {"ok": True}


# ---------------------------------------------------------------- tokenomics + club (aggregates only)
@app.get("/api/costs")
def costs() -> dict:
    with db.conn() as c:
        per_agent = [dict(r) for r in c.execute(
            """SELECT actor, COUNT(*) calls, SUM(input_tokens) input_tokens, SUM(cached_tokens) cached_tokens,
                      SUM(output_tokens) output_tokens, SUM(cost_usd) cost_usd
               FROM events WHERE kind='llm' GROUP BY actor ORDER BY cost_usd DESC""")]
        answers = c.execute("SELECT COUNT(*) n FROM turns").fetchone()["n"]
        sess = c.execute("SELECT COUNT(DISTINCT session_id) n FROM turns").fetchone()["n"]
        tot = c.execute("""SELECT COALESCE(SUM(input_tokens),0) i, COALESCE(SUM(cached_tokens),0) cch,
                           COALESCE(SUM(output_tokens),0) o, COALESCE(SUM(cost_usd),0) usd
                           FROM events WHERE kind='llm'""").fetchone()
    per_answer = {k: (tot[k] / answers if answers else 0) for k in ("i", "cch", "o", "usd")}
    return {"per_agent": per_agent, "answers": answers, "sessions": sess,
            "total": dict(tot), "per_answer": per_answer, "prices": config.PRICE_PER_M}


@app.get("/api/club")
def club() -> dict:
    s = db.club_summary()
    for m in s["misconceptions"]:
        lib = LIBRARY.get(m["mid"])
        m["name"] = lib.name if lib else m["mid"]
        m["skill"] = bank.SKILLS.get(lib.skill, "General") if lib else ""
    for k in s["skills"]:
        k["name"] = bank.SKILLS.get(k["skill"], k["skill"])
    return s


# ---------------------------------------------------------------- owner export (pilot evidence)
@app.get("/api/admin/export")
def admin_export(x_admin_token: str | None = Header(default=None)) -> dict:
    """Pilot data for the report. Disabled unless TICKTIE_ADMIN_TOKEN is set on the server."""
    expected = os.environ.get("TICKTIE_ADMIN_TOKEN")
    if not expected or not x_admin_token or not hmac.compare_digest(expected, x_admin_token):
        raise HTTPException(404, "Not found")
    with db.conn() as c:
        sessions = [dict(r) for r in c.execute(
            """SELECT s.id, p.name, s.mode, s.persona, s.started, s.ended, s.mastery_start, s.debrief
               FROM sessions s JOIN profiles p ON p.id=s.profile_id ORDER BY s.started""")]
        turns = [dict(r) for r in c.execute(
            """SELECT t.session_id, t.ts, t.template_id, t.skill, t.question, t.answer, t.seconds, t.verdict,
                      t.error_type, t.misconceptions, t.interviewer, t.input_tokens, t.cached_tokens,
                      t.output_tokens, t.cost_usd FROM turns t ORDER BY t.id""")]
        events = [dict(r) for r in c.execute(
            "SELECT session_id, ts, actor, kind, summary, detail, input_tokens, cached_tokens, output_tokens, cost_usd FROM events ORDER BY id")]
    return {"feedback": db.all_feedback(), "sessions": sessions, "turns": turns, "events": events,
            "costs": costs(), "club": club()}
