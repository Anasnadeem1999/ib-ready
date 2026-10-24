# Back-end review and spec (app-v2, branch `v2`)

Author: back-end / architecture reviewer. Date: Sat Oct 24 2026. Deadline: Mon Oct 26, 6 PM.
Scope: `ticktie/engine.py, mastery.py, plan.py, db.py, server.py, llm.py, config.py`, `run.py`, `render.yaml`, README.
This is a spec. No app code was changed. Every bug marked **(verified)** was reproduced offline with a stubbed LLM
(no API spend; script at `scratchpad/be_probe/probe.py` and `probe2.py`). The 114 existing tests still pass.

---

## 0. Priority table

P0 = fix before the deadline (crash in the main flow, corrupted progress, or a deploy/grading blocker).
P1 = should fix before the deadline if time allows (wrong numbers shown to users, robustness).
P2 = after the deadline or only if trivial.

| # | Pri | File / function | Problem | Exact fix |
|---|---|---|---|---|
| 1 | P0 | `engine.end_session` (engine.py:692-711) | **(verified)** Only `BudgetExceeded` is caught around the Coach call. Any gateway error, content-filter error, `UsageLimitExceeded` or missing key raises a 500 **after** the side effects ran (placement written, `lvl:` keys bumped with `n_inc=2`, plan rebuilt or ticked, `history` snapshot written). The session never ends, and every retry repeats them. Probe: one drill session ticked **2** plan tasks (0 -> 2); history rows 0 -> 14 after two failed ends. | (a) Wrap the coach block in `except Exception as e:` (keep `BudgetExceeded` message) and log `Guard/safety "Coach skipped (<ExcName>)"`, then use `_fallback_debrief`. (b) Make side effects run once: see #2. |
| 2 | P0 | `engine.end_session` (engine.py:643-717) | **(verified)** Not idempotent and not concurrency-safe. Two overlapping `/end` calls (double-click, auto-end on `complete` + End button, a retry after a timeout) both pass the `ended and debrief` check while the first awaits the Planner/Coach. Probe: concurrent ends ticked 2 plan tasks and wrote 2 `end` events. | Add `_ENDING: set[str]` next to `_INFLIGHT`. At the top: `if sid in _ENDING: raise ValueError("Already ending this session.")`. Wrap the body in `try/finally: _ENDING.discard(sid)`. Put the side effects (placement, `lvl:` floor, `build_plan`, `mark_done`, `snapshot`) under `if not state.get("finalized"):` and immediately after them set `state["finalized"] = True; db.save_state(sid, state)`. Then call the coach and `db.end_session`. In `engine.answer`, also refuse if `sid in _ENDING`. |
| 3 | P0 | `engine._answer` step 6 / `_interviewer_message` (engine.py:615-621) | **(verified)** The interviewer call happens **after** BKT, level, sub-skill and misconception writes (step 5) but **before** `save_state` (step 7). A non-content-filter error there (timeout, 5xx after retries, `UsageLimitExceeded`, schema-validation failure) returns 500 with the mastery already written and the state (attempts, `done_q`, current question) not saved. The candidate resubmits the same answer and it is counted twice. Probe: accounting `n` 0 -> 1 (failed turn) -> 2 (retry of the **same** question). | In `_interviewer_message`, change `except Exception as e: if not llm.is_content_filter(e): raise` to: catch every `Exception`; log `Guard/safety "Interviewer unavailable (<ExcName>); used the safe message."` and `break` to the existing fallback. The fallback text already exists for every action. (Re-raise only `asyncio.CancelledError`, which is not an `Exception` subclass, so nothing to do.) |
| 4 | P0 | `engine._answer` (engine.py:317-321) | **(verified)** Answers are accepted after `state["complete"]`. Diagnostic: the specialist LLM call is paid for, then `_advance_diagnostic` does `d["skills"][d["i"]]` with `i == len(skills)` -> `IndexError` -> 500. Mock/practice/drill: the last question stays `current`, so it is re-graded and BKT updates again (probe: `n` 11 -> 12 on the same question). Reachable via double-submit, hands-free voice mode, or a slow `/end`. | After the `ended` check: `if state.get("complete"): return {"blocked": True, "reason": "This session is complete. End it to see your debrief.", "session": _public_session(sid), "events": []}`. Defensive: in `_advance_diagnostic` start with `if d["i"] >= len(d["skills"]): state["complete"] = True; return`. |
| 5 | P0 | `engine._pick` practice branch (engine.py:119-124) + UI `#q-skill` (app.js:215) | **(verified)** The practice dropdown lists every skill, including `industry`. For a generalist or a profile with no intake, `mastery.pool` excludes all industry questions, `cands == []`, and `mastery.choose([])` raises `ValueError: min() iterable argument is empty` inside `POST /api/session` -> 500. | In `_pick` practice: `cands = mastery.pool(group, skill=focus, levels=(lvl,)) or mastery.pool(group, skill=focus) or mastery.pool(group, skill="accounting")`. In `start_session`: `if focus == "industry" and not mastery.pool(group, skill="industry"): focus = "accounting" if mode == "practice" else None`. Optional UI: hide `industry` unless `S.dash.intake.group` is a non-generalist group. |
| 6 | P0 | `render.yaml`, git | Branch `v2` exists only locally (`origin` has only `main`). A Render Blueprint deploys the repo's default branch, so it would ship v1. | Push `v2`, then either merge into `main` or add `branch: v2` under the service in `render.yaml`. Re-check the live URL serves the v2 UI (placement, plan, calendar). |
| 7 | P0 | `requirements.txt` | Unpinned (`pydantic-ai-slim[openai]>=1.0`, etc.). The code depends on current pydantic-ai behaviour (`result.usage` is a **property** in the installed 2.61.0; `OpenAIChatModelSettings(openai_reasoning_effort=...)`). A fresh clone or a Render build on a newer release can break at runtime. | Pin exactly what `.venv` runs: `fastapi==0.162.0`, `uvicorn==0.54.0`, `pydantic==2.14.1`, `pydantic-ai-slim[openai]==2.61.0`, `openai==3.37.0`, `python-dotenv==1.2.4`, `pytest==9.1.1`. Do a clean `python -m venv` + `pip install -r requirements.txt` + `pytest` once on Python 3.12 (Render's version) before submission. |
| 8 | P0 | `config.py:15-18` (.env discovery) | **(verified)** `load_dotenv(override=False)` skips a key that is already **set, even to an empty string**. If a grader copies `.env.example` to `.env` inside the repo (as the README's own wording invites) **and** keeps the real key one folder up, `PORTKEY_API_KEY=""` from the repo file masks the real key -> "No API key found". | Replace the loop with: `from dotenv import dotenv_values` then `for f in ENV_FILES: if f.exists(): for k, v in dotenv_values(f).items(): if v and not os.environ.get(k): os.environ[k] = v`. The first non-empty value wins; a real environment variable still wins. Add test `test_empty_repo_env_does_not_mask_parent_key` (section 5). |
| 9 | P1 | `llm.py:107, 132-146` | No request timeout. pydantic-ai's default HTTP client timeout is **600 s** (`_http.DEFAULT_HTTP_TIMEOUT`), and the OpenAI SDK also retries twice inside our own 3-attempt loop (up to 9 attempts). A hung gateway holds the session in `_INFLIGHT` for minutes; the UI shows "Still grading". | `SETTINGS = OpenAIChatModelSettings(openai_reasoning_effort="none", temperature=0.2, timeout=30, request_timeout=60)`. Build the provider from `AsyncOpenAI(base_url=..., api_key=..., max_retries=0, timeout=30)` via `OpenAIProvider(openai_client=client)` so retries happen only in `llm.run`. Add `"ModelRequestTimeout"` to the names in `_transient`. |
| 10 | P1 | `plan._today` (plan.py:34), `engine.dashboard` streak (engine.py:824-838) | Timezones. Render runs in UTC. `date.today()` and `date(..., 'localtime')` use the server's zone, so a New Haven user practising after 8 PM ET (7 PM in winter) sees tomorrow's "today" tasks, "behind" status flips a day early, and the streak can break or double. The streak also keys on `s.started`, not on when the answers happened. | Client sends `X-TZ-Offset: new Date().getTimezoneOffset()` in `api()` (app.js:26). Server: `def user_today(offset_min: int) -> date: return (datetime.now(timezone.utc) - timedelta(minutes=offset_min)).date()`; clamp offset to [-840, 840]. Pass `today` into `planmod.build/progress/mark_done` (replace `_today()` with a parameter defaulting to `_today()` so tests keep working). Streak: `SELECT t.ts FROM turns t JOIN sessions s ... WHERE s.profile_id=?` and convert each `ts` with the same offset in Python. Use offsets, **not** `zoneinfo`: Windows has no tz database unless `tzdata` is installed. |
| 11 | P1 | `engine.build_plan` (engine.py:720-749) via `/api/plan/rebuild` | Rebuilding the plan (done automatically when intake is re-saved after the diagnostic, app.js:144) recreates every task with `done=False`. **All completed plan progress is lost.** | Before `db.save_plan`, carry progress over: `old = db.get_plan(pid)`; for each done task in `old` (in date order), call `planmod.mark_done(plan, t["type"], t["skill"] if t["type"] == "drill" else None)`. Keep the original `completed` date if present. |
| 12 | P1 | `engine.end_session` diagnostic branch (engine.py:655-664) + `engine.dashboard` `diag_done` (engine.py:829) | **(verified)** Ending a diagnostic early: (a) with zero answers, `diagnostic_done=True` but no plan exists, so the UI thinks placement is done; (b) a skill in progress is dropped even if the candidate already climbed levels (e.g. passed Basic and Intermediate in DCF, then ended). | (a) `diag_done` = `bool(db.get_profile_json(pid, "placement"))`, not "an ended diagnostic session exists". (b) In `end_session`, if `not state.get("complete")` and the current skill was started (`d["level"] > first_level(...)`), add `results[skill] = d["level"] - 1`. Add `"partial": True` to the plan event and say so in the results screen: "Placement is partial: N of M skills placed." |
| 13 | P1 | `engine.end_session` (engine.py:694) | **(verified)** The coach budget check reuses `_budget_check` with the live state, which includes `turns >= MAX_TURNS_PER_SESSION`. A session that hit the turn cap (whose message says "End it to get your debrief") gets **no** coach debrief. | `_budget_check(sid, pid, {**state, "last_turn": 0, "turns": 0})`. |
| 14 | P1 | `server.py` (no endpoint), app.js `S.session` | Refresh mid-session: state is saved server-side, but there is no way back in. The browser loses `S.session`; the session stays open forever (never ended: no snapshot, no plan tick, not counted in `sessions`). | Add `GET /api/session/{sid}` (auth + `own_session`) returning `_public_session(sid)` plus `"transcript": [{"question","answer","interviewer","verdict"}]` from `db.turns(sid)`, and `GET /api/session/open` returning the newest session with `ended IS NULL AND started > now-12h` for the profile (or `null`). app.js: `localStorage.tt_session = s.id` on start, remove it on end; on boot, if present, call `GET /api/session/{id}` and offer "Resume your interview". |
| 15 | P1 | `engine.save_intake` (engine.py:215), `plan.days_until` (plan.py:38-44) | **(verified)** `interview_date` is stored unvalidated (`"not-a-date"` saved as-is and shown on the dashboard). A **past** date silently becomes "3 days left" (clamped), so the plan says the interview is in 3 days. | `save_intake`: `try: d = date.fromisoformat(s[:10]) except ValueError: d = None`; store `d.isoformat()` or `None`. `days_until`: return `(days, status)`, with `status = "past"` when `d < today`, and in that case use `default_days` (21) for the maths. Plan gets `"interview_passed": True` and the summary headline says "Your interview date has passed; this is a 3-week maintenance plan. Update the date in your profile." |
| 16 | P1 | `server.py` `/api/costs`, `/api/club` (server.py:196-221) | Both are **unauthenticated** and global. `/api/club` with 1-3 members effectively shows one person's misconceptions; `/api/costs` exposes usage of every user. Every other personal endpoint is authenticated and ownership-checked (verified: `/api/me, intake, dashboard, plan/rebuild, map, session, answer, end, events, feedback`). | Add `prof: dict = Depends(current_profile)` to both (the UI already sends the token). In `club()`, drop misconceptions with `members < 3` and return `"members"` only when `>= 3` (else `"too_few_members": True`). |
| 17 | P1 | `db.conn` / `db.init` (db.py:75-93) | Every DB call opens and commits its own connection in the default rollback-journal mode with `synchronous=FULL`. **(measured)** One graded mock turn = **26 connections, ~97 ms** with a stubbed LLM, all on the event-loop thread (the `answer`/`end`/`rebuild` handlers are `async def`). Sync handlers (`dashboard`, `signin`, `start`) run in the thread pool at the same time, so "database is locked" is possible under a pilot burst. | In `init()`: `c.execute("PRAGMA journal_mode=WAL")` (persistent). In `conn()`: `sqlite3.connect(config.DB_PATH, timeout=10)` then `c.execute("PRAGMA synchronous=NORMAL")` and `c.execute("PRAGMA busy_timeout=10000")`. Move `DATA_DIR.mkdir` into `init()`. Add `data/*.db-wal` and `data/*.db-shm` to `.gitignore`. |
| 18 | P1 | `db.init` SCHEMA (db.py:69-71) | Missing indexes for hot queries: `tokens_since` (runs twice per turn, joins all events from the last day, no index on `ts`), every per-profile `sessions` lookup, and `login_failures`. | Add: `CREATE INDEX IF NOT EXISTS ix_events_kind_ts ON events(kind, ts);` `CREATE INDEX IF NOT EXISTS ix_sessions_profile ON sessions(profile_id);` `CREATE INDEX IF NOT EXISTS ix_login_failures ON login_failures(name, ts);` `CREATE INDEX IF NOT EXISTS ix_auth_tokens_profile ON auth_tokens(profile_id);` All are `IF NOT EXISTS`, so they are safe on existing DBs. |
| 19 | P1 | `README.md` | Out of date for the fresh-clone test: says 64 tests (now 114), promises port 8000 (run.py picks the first free port from 8000), and PowerShell `activate` can fail under the default execution policy. | See section 4.2 for the exact replacement steps. |
| 20 | P1 | branding | "Tick & Tie" is hard-coded in 8 places. | `APP_NAME` spec in section 3.2. |
| 21 | P2 | `engine._answer` step 5 (engine.py:399-402) | Misconception hits are recorded on **every** non-redirect attempt, but BKT updates once per resolved question. A question answered wrong twice with the same trap counts 2 hits (inflates `active`, selection weight `min(hits,3)` and the club numbers). | Keep `state["current"]["mids"]` (union over attempts); call `record_misconception(..., True, ...)` once per mid when the question resolves (`if resolved`). |
| 22 | P2 | `engine._answer` what-if (engine.py:404-425, 444-452) | What-ifs are not counted toward `done_q` (correct, intended), but they **are** separate BKT evidence for the same template (skill + `lvl:` + `sub:` keys). One template can give 2 updates, so "interview-ready" (n >= 3) can come from 2 templates. Also, with 10 questions and up to 6 turns each, a mock can hit `MAX_TURNS_PER_SESSION=60` before the goal. | Decision for the team: keep what-ifs as evidence (document it in the report) **or** apply the what-if update only to `sub:` keys. Raise `MAX_TURNS_PER_SESSION` to 80, or stop offering what-ifs when `turns > 45`. |
| 23 | P2 | `mastery.current_level` (mastery.py:55-62), diagnostic floor (engine.py:660-662) | Levels only ratchet up. The diagnostic floors `lvl:` keys at 0.8 with `n_inc=2`, so re-taking the diagnostic and placing **lower** has no effect: old `lvl:` keys lift the level right back. If `first_level(skill) > 1` and the first answer is wrong, the skill is placed at `first_level - 1`, a level that was never tested. Fit can only place at 0-2 (never Advanced) because both fit questions use one level. | Document "levels are achievements" in the report. If re-placement should lower levels: in the diagnostic `end_session`, for `L > placed` do `db.set_key(pid, f"lvl:{sk}:{L}", min(get_key, 0.5), n_inc=0)`. Fit: after a pass, set `d["level"] = min(d["level"] + 1, 3)`. |
| 24 | P2 | `engine.end_session` plan ticking (engine.py:666-674) | `state["target"]["task"]` (the exact plan task a drill was started for) is stored but ignored; `mark_done` ticks the earliest drill of that skill. A 3-question mock (goal 10) ticks a mock task. | If `target.task` is not None and that task is open, tick it by id; else fall back to `mark_done`. Threshold: `done_q >= max(3, (state.get("goal") or 8) // 2)`. |
| 25 | P2 | `db.sign_in` (db.py:114-152) | Two simultaneous sign-ups with a new name: the second `INSERT INTO credentials` hits the PK -> `IntegrityError` -> 500. Profiles have no unique name constraint. | Catch `sqlite3.IntegrityError` -> `AuthError("That name was just taken. Try signing in.")`. Migration: `CREATE UNIQUE INDEX IF NOT EXISTS ux_profiles_lname ON profiles(lower(name))`, guarded by `SELECT lower(name) FROM profiles GROUP BY 1 HAVING COUNT(*)>1` returning nothing. |
| 26 | P2 | `server.admin_export` (server.py:229) | `hmac.compare_digest(str, str)` raises `TypeError` for non-ASCII header values (500 instead of 404). | `hmac.compare_digest(expected.encode(), x_admin_token.encode())`. |
| 27 | P2 | auth tokens | No server-side sign-out: tokens live 30 days and are never deleted. | `POST /api/signout` -> `DELETE FROM auth_tokens WHERE token=?`; in `sign_in`, also `DELETE FROM auth_tokens WHERE created < now-30d`. |
| 28 | P2 | `AnswerIn.seconds` (server.py:147) | Client-supplied, unvalidated (negative, huge, NaN) -> corrupts the speed averages. | `seconds: float | None = Field(default=None, ge=0, le=3600)`. |
| 29 | P2 | `llm.run` (llm.py:198-213) | When the gateway answers as the wrong model, the call is logged to jsonl but `ModelPolicyError` is raised before `add_event`, so session/day budgets undercount. Failed runs (`UsageLimitExceeded`) record no usage at all. | Return `rec` on the exception (`ModelPolicyError(msg, rec)`) and have the engine `add_event(..., rec)` before re-raising. Low impact. |
| 30 | P2 | `server._startup` (server.py:24) | `@app.on_event` is deprecated in FastAPI. | `lifespan` context manager calling `db.init()`. |
| 31 | P2 | `engine._answer` what-if (engine.py:431, 445) | `bank.variation` may return `None` (bank.py:1687/1690); `_choose_action` only checks `vary is not None`, so `nq.to_state()` could raise. No current `vary` returns `None`, so this is latent. | `if action == "ack_whatif" and nq is None: action = "ack_next"` before step 6. |

---

## 1. Code review, by topic

### 1.1 Turn handling (`engine.answer` / `_answer`)
- **Ordering and atomicity.** Step 5 writes mastery, `lvl:`, `sub:` and misconception rows (up to about 8 separate commits), then awaits the interviewer, then saves state. Any exception between them leaves a half-applied turn (P0 #3). The minimal fix is #3 (the interviewer can no longer raise). A safer ordering for after the deadline: compute everything, `save_state`, then do the mastery writes in **one** `db.transaction()` (section 3.1).
- **Single-flight.** `_INFLIGHT` is an in-process set. It is correct only with one uvicorn worker. Make that explicit in `render.yaml` (`--workers 1`) and in a comment. The `finally` block re-reads and re-writes the whole state just to set `last_turn`. Since `_answer` already sets `state["last_turn"]` and saves, the `finally` is needed only on the exception path (perf, section 2).
- **Complete sessions** keep accepting answers (P0 #4).
- **Rate-limit semantics.** `last_turn` is refreshed on blocked turns too, so a client retrying faster than 1/s stays blocked. That is acceptable.
- **Content-filter path** (engine.py:354-370) correctly saves no attempt and records a `blocked` turn.
- **No key.** `agents.specialist()` -> `llm.model()` raises `ModelPolicyError` before any write; the server maps it to 503 with a clear message. Good. With fix #1, ending a session also works without a key (fallback debrief).

### 1.2 Diagnostic placement (`_advance_diagnostic`)
- It works for the happy path. 17 answers place a generalist on the probe.
- Edge cases: an answer after completion (#4), ending mid-diagnostic (#12), the untested `first_level - 1` placement, and fit capped at 2 (#23).
- `_progress` handles `i == len(skills)` via `min(...)`. `_pick` does not, but it is guarded by `not state.get("complete")`.

### 1.3 BKT and evidence accounting
- `bkt_update` is fine and bounded. Double-counting paths: interviewer-failure retry (#3), answers after completion (#4), end retries re-applying the diagnostic floor (`n_inc=2` each time) (#1/#2), and misconception hits per attempt (#21). What-if counting (#22) is a design choice; write it down.
- `db.set_mastery` and `db.set_key` do the same thing (`n_inc=1`). Fold `set_mastery` into `set_key`.

### 1.4 Plan, calendar and progress (`plan.py`)
- The plan arithmetic is deterministic and tested. Issues: the server timezone (#10), past dates (#15), and rebuild wiping progress (#11).
- Calendar overflow: when tasks don't fit, the `while` loop parks the rest on `days-2`. When `days = 7k+1`, `days-2` is a mock day (for example days=8: mock days {6,7}), so drills land on a mock day. Cosmetic. If it is fixed: `day_idx = max(d for d in range(days-1) if d not in mock_days)`.
- `progress()` compares ISO strings, which is fine.

### 1.5 Data integrity and migrations
- Migrations today: only `profiles.intake/placement` via `PRAGMA table_info`. New tables use `IF NOT EXISTS`. That is OK for a v1 DB.
- Proposal (small, safe): a versioned migration list in `db.init()` keyed on `PRAGMA user_version`:
  ```python
  MIGRATIONS = [
      lambda c: None,  # v1: baseline (SCHEMA + intake/placement columns)
      lambda c: c.executescript(INDEXES_V2),             # v2: indexes from #18
      lambda c: c.execute("PRAGMA journal_mode=WAL"),     # v3
  ]
  v = c.execute("PRAGMA user_version").fetchone()[0]
  for i in range(v, len(MIGRATIONS)):
      MIGRATIONS[i](c); c.execute(f"PRAGMA user_version={i+1}")
  ```
- **Session-state schema drift.** State is a JSON blob. Any key added later (`done_q`, `goal`, `levels_start`, `diag.fit_seen`, `finalized`) is missing from older open sessions. Add `_normalize(state)` in `_answer`/`end_session`: `state.setdefault("done_q", 0); state.setdefault("goal", GOALS.get(state["mode"])); state.setdefault("followups", 0); state.setdefault("first_verdict", None); state.setdefault("phase", "answer")`.
- There are no foreign keys. Deletions don't exist, so this is acceptable.
- `club_opt_in` defaults to 1 and no UI changes it. Disclose it on the sign-in screen, or default to 0 with a toggle (P2, privacy).

### 1.6 API consistency (auth and ownership)
| Endpoint | Auth | Ownership | Note |
|---|---|---|---|
| `POST /api/signin` | n/a | n/a | Lockout by name: anyone can lock a name for 15 min (accepted trade-off) |
| `GET /api/me, /dashboard, /map`, `POST /intake, /plan/rebuild, /session` | yes | profile from token | ok |
| `POST /session/{sid}/answer, /end`, `GET /events` | yes | `own_session` -> 404 | ok |
| `POST /feedback` | yes | `own_session` if `session_id` given | ok |
| `GET /api/costs, /api/club` | **no** | global | #16 |
| `GET /api/admin/export` | `X-Admin-Token` | 404 if not configured | constant-time compare; #26 |
| `GET /api/health, /api/meta` | no | public | ok (key **source** name only, never the key) |

Error shape: `HTTPException` returns `{"detail": ...}` and the catch-all returns `{"error": ...}`. app.js handles both. Leave it.

---

## 2. Performance

Measured offline (stubbed LLM, local SSD, Python 3.13): **26 SQLite connections and ~97 ms of synchronous work per graded mock turn**, all on the event-loop thread. Import of `ticktie.server` takes **~2.0 s** (pydantic-ai, plus `bank.py` building and asserting all templates), which is fine for Render. Real latency is dominated by 2 LLM calls per turn (specialist + interviewer). The DB matters for **concurrency**, not single-user speed: while one turn does its 97 ms of blocking DB work, every other user's request waits.

Specific fixes, in order of value per minute:
1. **WAL + `synchronous=NORMAL` + `busy_timeout`** (#17). This cuts the fsync cost of the ~12 commits per turn and removes "database is locked" between the threadpool and the event loop.
2. **Stop re-reading the event log to slice it.** `ev_start = len(db.events(sid))` (engine.py:322) loads and JSON-decodes **every** event of the session just to count them, and the return then calls `db.events(sid)[ev_start:]` again. Replace both with `db.max_event_id(sid)` (`SELECT COALESCE(MAX(id),0) FROM events WHERE session_id=?`) and `db.events(sid, after_id=...)` (`... AND id>? ORDER BY id`). Same in the blocked paths.
3. **Budget check:** `tokens_since` runs twice per turn over a JOIN of all events in the last 24 h. Add `ix_events_kind_ts` (#18). If the pilot grows: keep a `usage_daily(day, profile_id, tokens)` table updated in `add_event` for `kind='llm'`.
4. **`_public_session(sid)` re-reads the session** right after `save_state`. Pass `state`/`s` in: `_public_session(sid, s=None)`. `answer()`'s `finally` re-reads and re-saves state on every turn; do it only when `_answer` raised.
5. **One transaction for the resolution writes.** Add `db.tx()` (a `conn()` you pass down) and give `set_key`, `record_misconception`, `add_event` and `add_turn` an optional `c=` parameter. This turns about 10 connect/commit cycles into 1. Do it only if time allows; WAL gets most of the gain.
6. **Dashboard N+1s:** `weakness_map` loads every turn of the profile (`SELECT t.*`, including the `diagnosis` JSON) just to compute average seconds and a count. Replace with `SELECT t.skill, AVG(t.seconds) avg_s, SUM(t.verdict IS NOT NULL) answered FROM turns t JOIN sessions s ... GROUP BY t.skill`. `levels_for` runs 2-3 times per dashboard request (each is 2 queries); compute once and pass it down.
7. **Offloading.** Wrapping engine DB work in `asyncio.to_thread` is **not** recommended before the deadline (it changes the concurrency model; `_INFLIGHT` would need a lock). Revisit only if more than ~20 users are active at once.

---

## 3. Architecture

### 3.1 Is the split clean?
Mostly yes: `bank` (questions + calculators), `mastery` (pure selection/BKT), `plan` (pure plan maths), `guard`, `agents`, `llm`, `db`, `server` (thin HTTP). The exceptions:
- `engine.py` (849 lines) mixes four jobs: the turn state machine, grading (`_adjudicate`, `_choose_action`, `_final_verdict`, which are pure), end-of-session/plan orchestration, and read models (`weakness_map`, `dashboard`, `_report`).
- Raw SQL leaks out of `db.py` in `engine.dashboard` (streak/diag-done queries) and in `server.costs`/`admin_export`.
- Timekeeping (`time.time()`, `date.today()`) is scattered, which caused #10.

**Minimal refactors that lower risk before Monday (no file moves):**
1. Move the 3 SQL blocks into `db.py` functions: `db.activity_timestamps(pid)`, `db.diag_done(pid)`, `db.cost_summary()`, `db.export_all()`. This is mechanical and testable.
2. In `engine.py`, extract `_apply_resolution(pid, sid, q, final_verdict, mids) -> (p_old, p_new)` (today's lines 404-419) and `_finalize_session(pid, sid, s, state) -> plan_event` (lines 654-676). These are the functions fixes #1-#3 touch; isolating them keeps the diffs small and reviewable.
3. Add `ticktie/clock.py` (about 10 lines: `user_today(offset_min)`, `now()`) and pass `today` into `plan.py`.
4. Defer the split of `engine.py` into `engine/turns.py`, `engine/grading.py`, `views.py` until after the deadline.

### 3.2 `APP_NAME`: rename the product in one place
**config.py** (after the `.env` loading so it can be overridden from `.env` or Render):
```python
APP_NAME = os.environ.get("APP_NAME", "Tick & Tie")
APP_TAGLINE = os.environ.get("APP_TAGLINE", "IB technicals, diagnosed")
```
**server.py**
- `app = FastAPI(title=config.APP_NAME, docs_url="/docs")`
- `/api/meta`: add `"app": {"name": config.APP_NAME, "tagline": config.APP_TAGLINE}`
- `/api/health`: add `"app": config.APP_NAME`

**run.py** (import after `uvicorn` so `.env` is loaded by config):
```python
from ticktie.config import APP_NAME
print(f"\n  {APP_NAME} is running at {url}\n  (Ctrl+C to stop)\n")
```
Also change the module docstring to "Start the app: python run.py".

**agents.py `_prompt`:** `.replace("{canary}", CANARY).replace("{app_name}", config.APP_NAME)` (import `config`). Use `.replace`, **not** `str.format`: the prompts contain literal braces/JSON.

**Prompts:** replace the literal "Tick & Tie" with `{app_name}` in `coach.md:1`, `diagnostician_base.md:1`, `interviewer.md:1`, `planner.md:1`. The name sits at the top of the system prompt, so renaming changes the cached prefix once. That is harmless.

**web/index.html:** keep the current text as the no-JS fallback, and add hooks:
```html
<title data-app-title>Tick &amp; Tie · IB interview coach</title>
<div class="brand-name" data-app-name>Tick &amp; Tie</div><div class="brand-sub" data-app-tagline>IB technicals, diagnosed</div>
```
**web/app.js** `init()`, right after `S.meta = await api("/api/meta")`:
```js
const APP = S.meta.app?.name || "Tick & Tie";
document.title = `${APP} · IB interview coach`;
$$("[data-app-name]").forEach((e) => (e.textContent = APP));
$$("[data-app-tagline]").forEach((e) => (e.textContent = S.meta.app?.tagline || e.textContent));
```
Replace the literal `"Tick & Tie"` speaker labels at app.js:342 and :348 with `S.meta.app.name`.

**Leave unchanged on purpose:** the localStorage keys `tt_*` (renaming would sign everyone out), the package name `ticktie`, `TICKTIE_*` env vars, the DB file name, and the Render service `name:` (it is in the URL). Optionally add `APP_NAME` to `render.yaml` envVars.

**Test:** `test_app_name_flows_everywhere` (section 5).

---

## 4. Deployment readiness

### 4.1 `render.yaml`
| Item | Status | Action |
|---|---|---|
| `runtime: python`, `PYTHON_VERSION=3.12.7` | ok (local is 3.13.15; nothing 3.13-specific is used) | Verify the pinned requirements install on 3.12 (#7) |
| `buildCommand: pip install -r requirements.txt` | ok once pinned | none |
| `startCommand: uvicorn ticktie.server:app --host 0.0.0.0 --port $PORT` | ok | Add `--workers 1` (required by `_INFLIGHT`/`_ENDING`) and `--proxy-headers` |
| `healthCheckPath: /api/health` | ok, but it never touches the DB or disk | Optional: `/api/health` runs `SELECT 1` via `db.conn()` and returns 503 on failure, so a missing or unwritable disk fails the deploy instead of the first sign-in |
| `disk` at `/var/data` + `TICKTIE_DATA_DIR=/var/data` | ok (Starter plan supports disks; a disk means no zero-downtime deploys, which is fine) | none |
| `PORTKEY_API_KEY sync:false` | ok | Paste the key in the dashboard |
| `TICKTIE_ADMIN_TOKEN generateValue` | ok | Copy it from the dashboard before running the export |
| **branch** | **v1 would deploy** | #6: `branch: v2` or merge |
| `APP_NAME` | n/a | Optional env var |

### 4.2 Fresh clone in under 10 minutes (README replacement for "Run it locally")
1. `git clone https://github.com/Anasnadeem1999/tick-and-tie.git && cd tick-and-tie` (plus `git checkout v2` if it is not merged).
2. The key: put `PORTKEY_API_KEY=...` in a `.env` **in this folder or the folder above it**. If you have one above, you don't need one here (after fix #8, an empty one here also does no harm).
3. Windows (no activation needed, avoids PowerShell execution-policy errors):
   `python -m venv .venv` -> `.venv\Scripts\python -m pip install -r requirements.txt` -> `.venv\Scripts\python run.py`
   Mac/Linux: `python3 -m venv .venv && .venv/bin/pip install -r requirements.txt && .venv/bin/python run.py`
4. The browser opens on the **first free port from 8000** (8000, 8001, ...); the terminal prints the exact URL. `--no-browser` and `PORT=xxxx` are supported.
5. Tests: `python -m pytest` -> 114 tests (update the number whenever tests are added).
Measured install footprint is small (pure-Python wheels); 3-5 minutes is realistic.

### 4.3 Behaviour without a key
The server starts, `/api/meta.key_present=false`, and the UI shows `#key-warning`. Sign-in, intake, dashboard and starting a session all work. The first answer returns **503** "No API key found. Put PORTKEY_API_KEY in a .env file in this folder or the folder above it". Ending a session currently 503s if it has graded turns (coach). After fix #1 it ends with the computed fallback debrief.

### 4.4 Windows/Mac paths
Paths are `pathlib` throughout, and files are read and written with `encoding="utf-8"`. `TICKTIE_DATA_DIR` accepts forward slashes on Windows. Two caveats: (a) the repo lives under `Desktop`, which is often OneDrive-synced, and SQLite + OneDrive sync can produce lock or "database is locked" errors. Recommend `TICKTIE_DATA_DIR` outside synced folders for demos. (b) `zoneinfo` needs `tzdata` on Windows, which is why #10 uses UTC offsets.

---

## 5. Tests to add

### 5.1 Offline LLM stub (`tests/conftest.py`)
`engine` calls `llm.run(...)` through the module attribute, so monkeypatching `ticktie.llm.run` intercepts every model call. Agents are built with `llm.model()` (which raises without a key), so give them pydantic-ai's `TestModel` and clear the `lru_cache`s.
```python
import pytest
from pydantic_ai.models.test import TestModel
from ticktie import agents, config, db, engine, llm

class _Res:
    def __init__(self, out): self.output = out

def _rec(name):
    return llm.CallRecord(name, 100, 0, 20, 1, 0, "gpt-6-luna", True, 1, 0.0)

class FakeLLM:
    """Scriptable stand-in for llm.run. verdict: 'right' | 'wrong'; fail: set of agent names that raise."""
    def __init__(self): self.verdict, self.fail, self.calls = "right", set(), []
    async def __call__(self, agent, agent_name, prompt, deps=None, session_id=None):
        self.calls.append(agent_name)
        if any(f in agent_name for f in self.fail):
            raise RuntimeError("simulated gateway failure")
        if deps is not None:  # a specialist diagnostician
            q, ok = deps.question, self.verdict == "right"
            sv = [agents.StatedValue(label=l.key, value=q.values[l.key] if ok else q.values[l.key] * 3 + 7)
                  for l in q.labels] if q.kind == "numeric" else []
            return _Res(agents.Diagnosis(stated_values=sv,
                        key_points_hit=list(range(len(q.key_points))) if ok else [],
                        reasoning_quality="strong" if ok else "none", rationale="ok", evidence_quote="x")), _rec(agent_name)
        if agent_name == "Interviewer": return _Res(agents.InterviewerMsg(message="Good. Next one.")), _rec(agent_name)
        if agent_name == "Coach": return _Res(agents.Debrief(headline="Done.", next_session="Drill.")), _rec(agent_name)
        if agent_name == "Planner": return _Res(agents.PlanSummary(headline="h", why="w", first_step="f")), _rec(agent_name)
        raise AssertionError(agent_name)

@pytest.fixture
def tmp_db(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "t.db")
    monkeypatch.setattr(config, "LOG_PATH", tmp_path / "llm.jsonl")
    db.init()

@pytest.fixture
def fake_llm(monkeypatch, tmp_db):
    f = FakeLLM()
    monkeypatch.setattr(llm, "run", f)
    monkeypatch.setattr(llm, "_model", TestModel())
    for fn in (agents.specialist, agents.interviewer, agents.coach, agents.planner):
        fn.cache_clear()
    monkeypatch.setattr(config, "MIN_SECONDS_BETWEEN_TURNS", 0.0)  # no sleeps in tests
    engine._INFLIGHT.clear()
    yield f
    for fn in (agents.specialist, agents.interviewer, agents.coach, agents.planner):
        fn.cache_clear()

@pytest.fixture
def client(fake_llm):
    from fastapi.testclient import TestClient
    from ticktie.server import app
    with TestClient(app) as c:  # runs the startup hook -> db.init() on the tmp DB
        r = c.post("/api/signin", json={"name": "Tester", "password": "secret123"})
        c.headers["X-Auth-Token"] = r.json()["token"]
        yield c
```
(The existing `tests/test_auth.py` `tmp_db` fixture can then be deleted in favour of the shared one.) `from fastapi.testclient import TestClient` already imports in the current venv, so no new dependency is needed.

### 5.2 Regression tests for the bugs (`tests/test_engine_flow.py`)
| Test | Asserts |
|---|---|
| `test_end_session_survives_coach_failure` (#1) | `fake_llm.fail={"Coach"}`; drill with 4 answers; `end_session` returns a report, `ended` is set, and the debrief equals the fallback shape (`headline` starts with "You answered") |
| `test_end_session_is_idempotent_and_ticks_plan_once` (#1/#2) | Diagnostic -> plan; drill with 4 answers; first `end_session` with Coach failing (before the fix this raises) then a second call; exactly 1 plan task is `done`, and `history` rows grew by exactly `len(bank.SKILLS)` |
| `test_concurrent_end_session_runs_side_effects_once` (#2) | `asyncio.gather(end_session(sid), end_session(sid), return_exceptions=True)` with a stub that awaits `asyncio.sleep(0.05)`; 1 plan task ticked, 1 `kind='end'` event, one result is a report and the other a `ValueError` or report |
| `test_interviewer_failure_falls_back_and_saves_state` (#3) | `fail={"Interviewer"}`; correct mock answer -> response `interviewer` is a FALLBACKS text, `done_q == 1`, and skill `n` increments exactly once; a second answer is graded against a **new** `current.template_id` |
| `test_no_answers_after_complete_diagnostic` (#4) | Run the diagnostic until `complete`; the next `answer` returns `blocked=True`, `fake_llm.calls` did not grow, and no exception |
| `test_no_regrade_after_goal_complete` (#4) | Practice until `complete`; one more answer -> `blocked`, mastery `n` unchanged |
| `test_practice_industry_for_generalist_does_not_crash` (#5) | `start_session(pid, "practice", "associate", "industry")` returns a question whose `skill != "industry"`; also via `client.post("/api/session", ...)` -> 200 |
| `test_turn_cap_still_gets_coach_debrief` (#13) | Set `state.turns = MAX_TURNS_PER_SESSION`; `end_session` -> `"Coach"` in `fake_llm.calls` |
| `test_empty_diagnostic_is_not_marked_done` (#12a) | Start a diagnostic and end it immediately -> `dashboard()["diagnostic_done"] is False` |
| `test_partial_diagnostic_keeps_in_progress_skill` (#12b) | Pass 2 accounting questions then end -> `placement["accounting"] >= 1` |
| `test_rebuild_plan_keeps_completed_tasks` (#11) | Tick 2 tasks, call `build_plan(pid)`, then `progress(plan)["done"] == 2` |
| `test_misconception_counted_once_per_question` (#21, if done) | Two wrong attempts matching the same trap -> `hits == 1` |

### 5.3 Pure-function tests (`tests/test_plan.py`, `tests/test_config.py`)
| Test | Asserts |
|---|---|
| `test_past_interview_date_is_flagged` (#15) | Monkeypatch `plan._today` to 2026-10-24; `days_until("2026-01-01")` gives status `"past"`; `build(...)["interview_passed"] is True` |
| `test_save_intake_rejects_bad_date` (#15) | `save_intake(pid, {"interview_date": "not-a-date"})["interview_date"] is None`; `"2026-11-03"` round-trips |
| `test_user_today_uses_client_offset` (#10) | With the UTC clock at 2026-10-25 01:30, `user_today(240)` (EDT) == 2026-10-24 |
| `test_streak_uses_answer_time_and_offset` (#10) | Insert turns at 23:50 local on two consecutive days -> streak 2 |
| `test_empty_repo_env_does_not_mask_parent_key` (#8) | `tmp/repo/.env` has `PORTKEY_API_KEY=` and `tmp/.env` has `PORTKEY_API_KEY=k`; after `importlib.reload(config)` with `REPO_ROOT` pointed at `tmp/repo` (refactor the loader into `load_env(files)` so it is testable without reload) -> `os.environ["PORTKEY_API_KEY"] == "k"` |
| `test_llm_settings_have_timeout` (#9) | `llm.SETTINGS["timeout"] <= 60` |
| `test_requirements_are_pinned` (#7) | Every non-comment line in `requirements.txt` contains `==` |

### 5.4 API tests (`tests/test_api.py`, TestClient + FakeLLM, fully offline)
| Test | Asserts |
|---|---|
| `test_e2e_signin_intake_diagnostic_plan_drill` | `POST /api/intake` -> `POST /api/session {"mode":"diagnostic"}` -> loop `POST /answer` until `complete` -> `POST /end` returns `placement` and `plan_progress` -> `GET /api/dashboard` has `plan` and `diagnostic_done` -> `POST /api/session {"mode":"drill"}` -> 4 answers -> `/end` -> dashboard `progress.done == 1`. Assert `answer` responses never contain `expected` values before the question resolves (no answer-key leak) |
| `test_personal_endpoints_require_token` | Without the header, each of `GET /api/me, /dashboard, /map, /costs, /club`, `POST /intake, /plan/rebuild, /session, /feedback` -> 401 |
| `test_cannot_touch_another_users_session` | User B gets 404 on `POST /api/session/{A_sid}/answer`, `/end`, `GET /events`, and `POST /feedback {"session_id": A_sid}` |
| `test_admin_export_hidden_without_token` | No env -> 404; env set + wrong token -> 404; non-ASCII token -> 404 (not 500); right token -> 200 with keys `feedback, sessions, turns, events` |
| `test_no_key_gives_503_not_500` | `fake_llm` not applied; `monkeypatch.setattr(config, "PORTKEY_API_KEY", None)` and `OPENAI_API_KEY=None`, `llm._model=None`, caches cleared -> `/answer` returns 503 with "No API key" in the `error` field; `/end` returns 200 (after #1) |
| `test_meta_exposes_app_name` / `test_app_name_flows_everywhere` | `monkeypatch.setattr(config, "APP_NAME", "Foo")`, then `/api/meta["app"]["name"] == "Foo"`, `agents._prompt("coach.md")` contains "Foo" and not "Tick & Tie", and `"{app_name}"` does not appear in any rendered prompt |
| `test_resume_session_endpoint` (#14) | Start a session, `GET /api/session/{sid}` returns the same `question.title`; `GET /api/session/open` returns that id; after `/end` it returns `null` |

---

## 6. Suggested order of work (about 4-5 focused hours)
1. #4, #5, #3, #1 + #2, #13 (engine.py only, each a few lines) plus their tests from 5.2. About 1.5 h.
2. #8, #9, #7 (config/llm/requirements), then re-run the full suite and do a clean-venv install. About 45 min.
3. #6 deploy branch + `--workers 1`, then deploy and smoke-test the live URL (sign in, diagnostic, end, plan). About 45 min.
4. #17/#18 WAL + indexes, #16 auth on costs/club, `APP_NAME`. About 1 h.
5. If time remains: #10 timezone, #11 plan carry-over, #12, #14 resume, #15 dates.
