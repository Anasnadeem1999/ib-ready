"""FastAPI app: serves the web UI and the JSON API from one process."""

from __future__ import annotations

import hmac
import os
import time
import traceback
from collections import deque
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import agents, bank, config, db, engine, llm
from . import plan as planmod
from .misconceptions import LIBRARY

WEB = config.REPO_ROOT / "web"

@asynccontextmanager
async def _lifespan(_: FastAPI):
    db.init()
    yield


app = FastAPI(title=config.APP_NAME, docs_url="/docs", lifespan=_lifespan)
app.mount("/static", StaticFiles(directory=WEB), name="static")


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


def tz_offset(x_tz_offset: str | None = Header(default=None)) -> int | None:
    """Minutes, JS getTimezoneOffset() convention (New York in winter = 300). Absent or bad -> UTC."""
    try:
        return max(-840, min(int(float(x_tz_offset)), 840)) if x_tz_offset not in (None, "") else None
    except (TypeError, ValueError):
        return None


def own_session(sid: str, prof: dict) -> dict:
    s = db.session(sid)
    if s is None or s["profile_id"] != prof["id"]:
        raise HTTPException(404, "Session not found.")
    return s


class SignIn(BaseModel):
    name: str = Field(min_length=1, max_length=40)
    password: str = Field(min_length=1, max_length=200)


_RATE: dict[tuple[str, str], deque] = {}  # (bucket, client IP) -> recent timestamps (one process, see render.yaml)


def _rate_ok(bucket: str, ip: str, limit: int, window: float, record: bool = True) -> bool:
    now = time.time()
    q = _RATE.setdefault((bucket, ip), deque())
    while q and q[0] <= now - window:
        q.popleft()
    if len(q) >= limit:
        return False
    if record:
        q.append(now)
    return True


def client_ip(request: Request) -> str:
    # behind Render's proxy, uvicorn --proxy-headers + FORWARDED_ALLOW_IPS=* puts the real client here
    return request.client.host if request.client else "unknown"


@app.post("/api/signin")
def signin(body: SignIn, request: Request) -> dict:
    ip = client_ip(request)
    if not _rate_ok("signin", ip, config.SIGNIN_PER_IP_PER_MINUTE, 60):
        raise HTTPException(429, "Too many sign-in attempts from this network. Wait a minute and try again.")
    if not db.name_exists(body.name):
        if not _rate_ok("signup", ip, config.SIGNUPS_PER_IP_PER_HOUR, 3600, record=False):
            raise HTTPException(429, "Too many new profiles from this network in the last hour. Try again later.")
    try:
        prof, token, created = db.sign_in(body.name, body.password, ip)
    except db.AuthError as e:
        raise HTTPException(400, str(e))
    if created:
        _rate_ok("signup", ip, config.SIGNUPS_PER_IP_PER_HOUR, 3600)
    return {"profile": {"id": prof["id"], "name": prof["name"]}, "token": token, "created": created}


@app.get("/api/me")
def me(prof: dict = Depends(current_profile)) -> dict:
    return {"id": prof["id"], "name": prof["name"]}


@app.post("/api/signout")
def signout(x_auth_token: str | None = Header(default=None)) -> dict:
    if x_auth_token:
        db.delete_token(x_auth_token)
    return {"ok": True}


# ---------------------------------------------------------------- meta
@app.get("/api/health")
def health() -> JSONResponse:
    try:  # a missing or read-only disk fails the health check (and the deploy) instead of the first sign-in
        with db.conn() as c:
            c.execute("SELECT 1")
    except Exception as e:
        return JSONResponse(status_code=503, content={"ok": False, "error": type(e).__name__})
    return JSONResponse({"ok": True, "app": config.APP_NAME, "model": config.MODEL_NAME, "key": config.key_source()})


@app.get("/api/meta")
def meta() -> dict:
    return {
        "app_name": config.APP_NAME,
        "tagline": config.APP_TAGLINE,
        "skills": bank.SKILLS,
        "personas": {k: v[0] for k, v in agents.PERSONAS.items()},
        "modes": {"diagnostic": "Placement diagnostic", "drill": "Targeted drill", "mock": "Mock interview",
                  "practice": "Free practice"},
        "levels": bank.LEVELS,
        "groups": [{"id": k, "name": v, "kind": bank.GROUP_KIND[k]} for k, v in bank.GROUPS.items()],
        "stages": planmod.STAGES,
        "subskills": {k: {"skill": v[0], "name": v[1]} for k, v in bank.SUBSKILLS.items()},
        "prices": config.PRICE_PER_M,
        "limits": {"session_tokens": config.SESSION_TOKEN_BUDGET, "attempts": config.MAX_ATTEMPTS_PER_QUESTION,
                   "followups": config.MAX_FOLLOWUPS_PER_QUESTION, "answer_chars": config.MAX_ANSWER_CHARS},
        "question_count": len(bank.TEMPLATES),
        "key_present": config.key_source() is not None,
    }


# ---------------------------------------------------------------- profile + sessions (signed in)
class IntakeIn(BaseModel):
    group: str = "generalist"
    stage: str = "networking"
    interview_date: str | None = None
    hours_per_week: float = 5
    persona: str = "associate"


@app.post("/api/intake")
def intake(body: IntakeIn, prof: dict = Depends(current_profile)) -> dict:
    return engine.save_intake(prof["id"], body.model_dump())


@app.get("/api/dashboard")
def dashboard(prof: dict = Depends(current_profile), tz: int | None = Depends(tz_offset)) -> dict:
    return engine.dashboard(prof["id"], tz)


@app.post("/api/plan/rebuild")
async def rebuild_plan(prof: dict = Depends(current_profile), tz: int | None = Depends(tz_offset)) -> dict:
    return await engine.build_plan(prof["id"], tz=tz)


@app.get("/api/map")
def profile_map(prof: dict = Depends(current_profile)) -> dict:
    return engine.weakness_map(prof["id"])


class SessionIn(BaseModel):
    mode: str = "mock"
    persona: str = "associate"
    focus: str | None = None
    level: int | None = None
    task_id: int | None = None  # start this specific plan task (its skill, sub-skill and level)


@app.post("/api/session")
def start(body: SessionIn, prof: dict = Depends(current_profile)) -> dict:
    return engine.start_session(prof["id"], body.mode, body.persona, body.focus, body.level, body.task_id)


@app.get("/api/session/active")
def active_session(prof: dict = Depends(current_profile)) -> dict:
    """The newest open, unfinished session, so a page refresh can resume it; else {"session": null}."""
    return engine.active_session(prof["id"])


class AnswerIn(BaseModel):
    text: str = Field(max_length=20000)
    seconds: float | None = Field(default=None, ge=0, le=3600)


@app.post("/api/session/{sid}/answer")
async def answer(sid: str, body: AnswerIn, prof: dict = Depends(current_profile)) -> dict:
    own_session(sid, prof)
    try:
        return await engine.answer(sid, body.text, body.seconds, prof["id"])
    except ValueError as e:
        raise HTTPException(400, str(e))


@app.post("/api/session/{sid}/end")
async def end(sid: str, prof: dict = Depends(current_profile), tz: int | None = Depends(tz_offset)) -> dict:
    own_session(sid, prof)
    try:
        return await engine.end_session(sid, tz)
    except engine.Busy as e:
        raise HTTPException(409, str(e))
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
def _costs() -> dict:
    c = db.cost_summary()
    tot, answers = c["total"], c["answers"]
    c["per_answer"] = {k: (tot[k] / answers if answers else 0) for k in ("i", "cch", "o", "usd")}
    c["prices"] = config.PRICE_PER_M
    return c


@app.get("/api/costs")
def costs(prof: dict = Depends(current_profile)) -> dict:
    return _costs()


CLUB_MIN_MEMBERS = 3  # never show a misconception that fewer than 3 members share (no singling anyone out)


def _club() -> dict:
    s = db.club_summary()
    s["misconceptions"] = [m for m in s["misconceptions"] if m["members"] >= CLUB_MIN_MEMBERS]
    s["too_few_members"] = s["members"] < CLUB_MIN_MEMBERS
    if s["too_few_members"]:
        s["skills"] = []
    for m in s["misconceptions"]:
        lib = LIBRARY.get(m["mid"])
        m["name"] = lib.name if lib else m["mid"]
        m["skill"] = bank.SKILLS.get(lib.skill, "General") if lib else ""
    s["skills"] = [dict(k, name=bank.SKILLS[k["skill"]]) for k in s["skills"] if k["skill"] in bank.SKILLS]
    return s


@app.get("/api/club")
def club(prof: dict = Depends(current_profile)) -> dict:
    return _club()


# ---------------------------------------------------------------- owner export (pilot evidence)
@app.get("/api/admin/export")
def admin_export(x_admin_token: str | None = Header(default=None)) -> dict:
    """Pilot data for the report. Disabled unless TICKTIE_ADMIN_TOKEN is set on the server."""
    expected = os.environ.get("TICKTIE_ADMIN_TOKEN")
    if not expected or not x_admin_token or not hmac.compare_digest(expected.encode(), x_admin_token.encode()):
        raise HTTPException(404, "Not found")
    return {**db.export_all(), "costs": _costs(), "club": _club()}
