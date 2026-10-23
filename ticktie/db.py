"""SQLite persistence. The database file is created automatically on first run."""

from __future__ import annotations

import hashlib
import hmac
import json
import secrets
import sqlite3
import time
import uuid
from contextlib import contextmanager

from . import bank, config
from .mastery import P_INIT

SCHEMA = """
CREATE TABLE IF NOT EXISTS profiles (
  id TEXT PRIMARY KEY, name TEXT NOT NULL, created REAL NOT NULL, club_opt_in INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS sessions (
  id TEXT PRIMARY KEY, profile_id TEXT NOT NULL, mode TEXT NOT NULL, persona TEXT NOT NULL,
  focus TEXT, started REAL NOT NULL, ended REAL, state TEXT NOT NULL, debrief TEXT,
  mastery_start TEXT
);
CREATE TABLE IF NOT EXISTS turns (
  id INTEGER PRIMARY KEY AUTOINCREMENT, session_id TEXT NOT NULL, ts REAL NOT NULL,
  template_id TEXT, skill TEXT, kind TEXT, question TEXT, answer TEXT, seconds REAL,
  verdict TEXT, error_type TEXT, misconceptions TEXT, diagnosis TEXT, interviewer TEXT,
  input_tokens INTEGER DEFAULT 0, cached_tokens INTEGER DEFAULT 0, output_tokens INTEGER DEFAULT 0,
  cost_usd REAL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS mastery (
  profile_id TEXT NOT NULL, skill TEXT NOT NULL, p REAL NOT NULL, n INTEGER NOT NULL,
  PRIMARY KEY (profile_id, skill)
);
CREATE TABLE IF NOT EXISTS misconceptions (
  profile_id TEXT NOT NULL, mid TEXT NOT NULL, hits INTEGER NOT NULL DEFAULT 0,
  clean_streak INTEGER NOT NULL DEFAULT 0, exposures INTEGER NOT NULL DEFAULT 0,
  last_ts REAL, evidence TEXT NOT NULL DEFAULT '[]',
  PRIMARY KEY (profile_id, mid)
);
CREATE TABLE IF NOT EXISTS events (
  id INTEGER PRIMARY KEY AUTOINCREMENT, session_id TEXT NOT NULL, ts REAL NOT NULL,
  actor TEXT NOT NULL, kind TEXT NOT NULL, summary TEXT NOT NULL, detail TEXT,
  input_tokens INTEGER DEFAULT 0, cached_tokens INTEGER DEFAULT 0, output_tokens INTEGER DEFAULT 0,
  cost_usd REAL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS credentials (
  profile_id TEXT PRIMARY KEY, salt TEXT NOT NULL, pw_hash TEXT NOT NULL, iterations INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS auth_tokens (
  token TEXT PRIMARY KEY, profile_id TEXT NOT NULL, created REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS login_failures (
  name TEXT NOT NULL, ts REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS feedback (
  id INTEGER PRIMARY KEY AUTOINCREMENT, profile_id TEXT NOT NULL, session_id TEXT, ts REAL NOT NULL,
  rating INTEGER, vs_current TEXT, found_new TEXT, time_to_find TEXT, prep_today TEXT,
  quote TEXT, consent INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS ix_events_session ON events(session_id);
CREATE INDEX IF NOT EXISTS ix_turns_session ON turns(session_id);
"""


@contextmanager
def conn():
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(config.DB_PATH)
    c.row_factory = sqlite3.Row
    try:
        yield c
        c.commit()
    finally:
        c.close()


def init() -> None:
    with conn() as c:
        c.executescript(SCHEMA)


def new_id() -> str:
    return uuid.uuid4().hex[:12]


# ---------------------------------------------------------------- auth (Lecture 8: salted slow hash, lockout)
PBKDF2_ITERATIONS = 200_000
MAX_FAILURES = 5
LOCKOUT_SECONDS = 15 * 60


class AuthError(Exception):
    pass


def _hash(password: str, salt: bytes, iterations: int) -> str:
    return hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations).hex()


def sign_in(name: str, password: str) -> tuple[dict, str, bool]:
    """Log in, or create the profile if the name is new. Returns (profile, token, created)."""
    name = name.strip()[:40]
    if len(name) < 2:
        raise AuthError("Use at least 2 characters for your name.")
    if len(password) < 6:
        raise AuthError("Use a password of at least 6 characters.")
    with conn() as c:
        recent = c.execute("SELECT COUNT(*) n FROM login_failures WHERE lower(name)=lower(?) AND ts>?",
                           (name, time.time() - LOCKOUT_SECONDS)).fetchone()["n"]
        if recent >= MAX_FAILURES:
            raise AuthError("Too many wrong passwords. This profile is locked for 15 minutes.")
        row = c.execute("SELECT * FROM profiles WHERE lower(name)=lower(?)", (name,)).fetchone()
    created = False
    if row is None:
        prof = get_or_create_profile(name)
        salt = secrets.token_bytes(16)
        with conn() as c:
            c.execute("INSERT INTO credentials VALUES (?,?,?,?)",
                      (prof["id"], salt.hex(), _hash(password, salt, PBKDF2_ITERATIONS), PBKDF2_ITERATIONS))
        created = True
    else:
        prof = dict(row)
        wrong = False
        with conn() as c:
            cred = c.execute("SELECT * FROM credentials WHERE profile_id=?", (prof["id"],)).fetchone()
            if cred is None:  # profile from before logins existed: claim it with this password
                salt = secrets.token_bytes(16)
                c.execute("INSERT INTO credentials VALUES (?,?,?,?)",
                          (prof["id"], salt.hex(), _hash(password, salt, PBKDF2_ITERATIONS), PBKDF2_ITERATIONS))
            elif not hmac.compare_digest(_hash(password, bytes.fromhex(cred["salt"]), cred["iterations"]), cred["pw_hash"]):
                c.execute("INSERT INTO login_failures VALUES (?,?)", (name, time.time()))
                wrong = True  # raise only after the failure is committed, or the lockout never counts it
        if wrong:
            raise AuthError("That name is taken and the password doesn't match. Pick another name, or check your password.")
    token = secrets.token_urlsafe(24)
    with conn() as c:
        c.execute("INSERT INTO auth_tokens VALUES (?,?,?)", (token, prof["id"], time.time()))
    return prof, token, created


def profile_for_token(token: str | None) -> dict | None:
    if not token:
        return None
    with conn() as c:
        row = c.execute("""SELECT p.* FROM auth_tokens t JOIN profiles p ON p.id=t.profile_id
                           WHERE t.token=? AND t.created>?""", (token, time.time() - 30 * 86400)).fetchone()
    return dict(row) if row else None


# ---------------------------------------------------------------- feedback (pilot evidence)
def add_feedback(pid: str, sid: str | None, **kw) -> None:
    cols = ["profile_id", "session_id", "ts"] + list(kw)
    vals = [pid, sid, time.time()] + list(kw.values())
    with conn() as c:
        c.execute(f"INSERT INTO feedback ({','.join(cols)}) VALUES ({','.join('?' * len(cols))})", vals)


def all_feedback() -> list[dict]:
    with conn() as c:
        rows = c.execute("""SELECT f.*, p.name FROM feedback f JOIN profiles p ON p.id=f.profile_id ORDER BY f.id""").fetchall()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------- profiles
def get_or_create_profile(name: str) -> dict:
    name = name.strip()[:40] or "Candidate"
    with conn() as c:
        row = c.execute("SELECT * FROM profiles WHERE lower(name)=lower(?)", (name,)).fetchone()
        if row:
            return dict(row)
        pid = new_id()
        c.execute("INSERT INTO profiles (id, name, created) VALUES (?,?,?)", (pid, name, time.time()))
        for s in bank.SKILLS:
            c.execute("INSERT INTO mastery VALUES (?,?,?,0)", (pid, s, P_INIT))
        return {"id": pid, "name": name, "created": time.time(), "club_opt_in": 1}


def profile(pid: str) -> dict | None:
    with conn() as c:
        row = c.execute("SELECT * FROM profiles WHERE id=?", (pid,)).fetchone()
        return dict(row) if row else None


def mastery(pid: str) -> dict[str, dict]:
    with conn() as c:
        rows = c.execute("SELECT skill, p, n FROM mastery WHERE profile_id=?", (pid,)).fetchall()
    out = {s: {"p": P_INIT, "n": 0} for s in bank.SKILLS}
    for r in rows:
        out[r["skill"]] = {"p": r["p"], "n": r["n"]}
    return out


def set_mastery(pid: str, skill: str, p: float) -> None:
    with conn() as c:
        c.execute("""INSERT INTO mastery VALUES (?,?,?,1)
                     ON CONFLICT(profile_id, skill) DO UPDATE SET p=excluded.p, n=n+1""", (pid, skill, p))


def misconceptions(pid: str) -> list[dict]:
    with conn() as c:
        rows = c.execute("SELECT * FROM misconceptions WHERE profile_id=? ORDER BY hits DESC", (pid,)).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        d["evidence"] = json.loads(d["evidence"])
        d["active"] = d["hits"] > 0 and d["clean_streak"] < 2
        out.append(d)
    return out


def record_misconception(pid: str, mid: str, hit: bool, evidence: dict | None) -> None:
    with conn() as c:
        row = c.execute("SELECT * FROM misconceptions WHERE profile_id=? AND mid=?", (pid, mid)).fetchone()
        if row is None:
            ev = [evidence] if (hit and evidence) else []
            c.execute("INSERT INTO misconceptions VALUES (?,?,?,?,?,?,?)",
                      (pid, mid, 1 if hit else 0, 0 if hit else 1, 1, time.time(), json.dumps(ev)))
            return
        ev = json.loads(row["evidence"])
        if hit and evidence:
            ev = (ev + [evidence])[-5:]
        c.execute("""UPDATE misconceptions SET hits=hits+?, clean_streak=?, exposures=exposures+1,
                     last_ts=?, evidence=? WHERE profile_id=? AND mid=?""",
                  (1 if hit else 0, 0 if hit else row["clean_streak"] + 1, time.time(), json.dumps(ev), pid, mid))


# ---------------------------------------------------------------- sessions
def create_session(pid: str, mode: str, persona: str, focus: str | None, state: dict) -> str:
    sid = new_id()
    with conn() as c:
        c.execute("INSERT INTO sessions (id, profile_id, mode, persona, focus, started, state, mastery_start) "
                  "VALUES (?,?,?,?,?,?,?,?)",
                  (sid, pid, mode, persona, focus, time.time(), json.dumps(state), json.dumps(mastery(pid))))
    return sid


def session(sid: str) -> dict | None:
    with conn() as c:
        row = c.execute("SELECT * FROM sessions WHERE id=?", (sid,)).fetchone()
    if not row:
        return None
    d = dict(row)
    d["state"] = json.loads(d["state"])
    d["mastery_start"] = json.loads(d["mastery_start"] or "{}")
    d["debrief"] = json.loads(d["debrief"]) if d["debrief"] else None
    return d


def save_state(sid: str, state: dict) -> None:
    with conn() as c:
        c.execute("UPDATE sessions SET state=? WHERE id=?", (json.dumps(state), sid))


def end_session(sid: str, debrief: dict) -> None:
    with conn() as c:
        c.execute("UPDATE sessions SET ended=?, debrief=? WHERE id=?", (time.time(), json.dumps(debrief), sid))


def add_turn(sid: str, **kw) -> None:
    cols = ["session_id", "ts"] + list(kw)
    vals = [sid, time.time()] + [json.dumps(v) if isinstance(v, (dict, list)) else v for v in kw.values()]
    with conn() as c:
        c.execute(f"INSERT INTO turns ({','.join(cols)}) VALUES ({','.join('?' * len(cols))})", vals)


def turns(sid: str) -> list[dict]:
    with conn() as c:
        rows = c.execute("SELECT * FROM turns WHERE session_id=? ORDER BY id", (sid,)).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        for k in ("misconceptions", "diagnosis"):
            if d.get(k):
                d[k] = json.loads(d[k])
        out.append(d)
    return out


def profile_turns(pid: str) -> list[dict]:
    with conn() as c:
        rows = c.execute("""SELECT t.* FROM turns t JOIN sessions s ON s.id=t.session_id
                            WHERE s.profile_id=? ORDER BY t.id""", (pid,)).fetchall()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------- events (agent trace + audit trail)
def add_event(sid: str, actor: str, kind: str, summary: str, detail: dict | None = None, rec=None) -> dict:
    tok = rec.to_dict() if rec is not None else {}
    ev = {
        "ts": time.time(), "actor": actor, "kind": kind, "summary": summary, "detail": detail or {},
        "input_tokens": tok.get("input_tokens", 0), "cached_tokens": tok.get("cached_tokens", 0),
        "output_tokens": tok.get("output_tokens", 0), "cost_usd": tok.get("cost_usd", 0.0),
    }
    with conn() as c:
        c.execute("INSERT INTO events (session_id, ts, actor, kind, summary, detail, input_tokens, cached_tokens, "
                  "output_tokens, cost_usd) VALUES (?,?,?,?,?,?,?,?,?,?)",
                  (sid, ev["ts"], actor, kind, summary, json.dumps(ev["detail"]), ev["input_tokens"],
                   ev["cached_tokens"], ev["output_tokens"], ev["cost_usd"]))
    return ev


def events(sid: str) -> list[dict]:
    with conn() as c:
        rows = c.execute("SELECT * FROM events WHERE session_id=? ORDER BY id", (sid,)).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        d["detail"] = json.loads(d["detail"] or "{}")
        out.append(d)
    return out


def session_usage(sid: str) -> dict:
    with conn() as c:
        r = c.execute("""SELECT COALESCE(SUM(input_tokens),0) i, COALESCE(SUM(cached_tokens),0) c,
                         COALESCE(SUM(output_tokens),0) o, COALESCE(SUM(cost_usd),0) usd, COUNT(*) n
                         FROM events WHERE session_id=? AND kind='llm'""", (sid,)).fetchone()
    return {"input_tokens": r["i"], "cached_tokens": r["c"], "output_tokens": r["o"], "cost_usd": r["usd"],
            "llm_calls": r["n"]}


def tokens_since(since: float, pid: str | None = None) -> int:
    q = """SELECT COALESCE(SUM(e.input_tokens + e.output_tokens),0) t FROM events e
           JOIN sessions s ON s.id=e.session_id WHERE e.kind='llm' AND e.ts>=?"""
    args: list = [since]
    if pid:
        q += " AND s.profile_id=?"
        args.append(pid)
    with conn() as c:
        return int(c.execute(q, args).fetchone()["t"])


# ---------------------------------------------------------------- club view
def club_summary() -> dict:
    with conn() as c:
        members = c.execute("SELECT COUNT(*) n FROM profiles WHERE club_opt_in=1").fetchone()["n"]
        mis = c.execute("""SELECT mid, COUNT(*) members, SUM(hits) hits FROM misconceptions m
                           JOIN profiles p ON p.id=m.profile_id
                           WHERE p.club_opt_in=1 AND hits>0 GROUP BY mid ORDER BY members DESC, hits DESC""").fetchall()
        sk = c.execute("""SELECT skill, AVG(p) avg_p, SUM(n) answers FROM mastery m JOIN profiles p ON p.id=m.profile_id
                          WHERE p.club_opt_in=1 GROUP BY skill""").fetchall()
        answered = c.execute("""SELECT COUNT(*) n FROM turns t JOIN sessions s ON s.id=t.session_id
                                JOIN profiles p ON p.id=s.profile_id WHERE p.club_opt_in=1 AND t.verdict IS NOT NULL""").fetchone()["n"]
    return {"members": members, "answers": answered,
            "misconceptions": [dict(r) for r in mis], "skills": [dict(r) for r in sk]}
