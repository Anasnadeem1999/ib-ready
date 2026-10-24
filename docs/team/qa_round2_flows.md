# QA round 2: functional flows, API and data integrity (QA engineer A)

Tested Sat Oct 24 2026 on branch `v2`. First pass on a server started at 01:43 ET; every open finding below was then **re-checked on HEAD `062ee2b`** (server restarted on port 8211 at 12:07 ET with its own data folder). Port 8000/8200 and `ib-ready` were not touched. No app code was edited.
Method: Python `requests` against the API (answers built from the answer key in sqlite via `bank.from_state`, ≥1.3 s apart), sqlite checks of the stored state/plan, and Playwright spot checks (New York and Anchorage time zones). Model spend: **$0.077** across about 260 graded answers.
Scripts and JSON results: `C:/Users/ANAS/AppData/Local/Temp/claude/C--Users-ANAS-Desktop-Prob-and-Stat/a0cf80a0-8ce1-4782-89ed-7d7490e63cc7/scratchpad/qa2a/` (`journey.py`, `lifecycle.py`, `plans.py`, `auth.py`, `practice.py`, `carry.py`, `reverify*.py`; screenshots in `shots/`).

**Test suite:** `.venv/Scripts/python -m pytest -q` → **417 passed** on HEAD (348 passed on the earlier build). No failures.

**No P0s found.** There were no 500s in any run, and no crashes in the main journey for any of the three personas.

## Summary

| ID | Sev | Area | Title |
|---|---|---|---|
| F-01 | P1 | Placement / results | If you end the placement partway through a topic, the results screen says "no topic placed, restart" even though the server placed it and built a plan |
| F-02 | P1 | Grading / content | The app's own worked answer for "Two ways to get terminal value" is graded wrong (8 of 8 times), so strong candidates get placed at Getting started in DCF |
| F-03 | P1 | Plan rebuild | Completed tasks keep their original scheduled date: they show up after a moved-up interview, and the plan ends up with two "Final mock interview" tasks |
| F-04 | P2 | Plan rebuild | After a rebuild with completed tasks, "min per practice day", "practice days" and the per-topic drill counts no longer match the calendar |
| F-05 | P2 | Drill / trace | Sub-skill drills drift to other sub-skills after 2–3 questions, but the trace still names the target sub-skill |
| F-06 | P2 | Plan | Interview today: a drill and the "Final mock" are scheduled on the interview day |
| F-07 | P2 | Session lifecycle | A finished placement whose `/end` never arrives can't be recovered: it isn't offered for resume and no placement or plan is created |
| F-08 | P2 | Group specifics plan | FIG/TMT users at First-round in Group specifics get 3 drills "towards First-round ready", which can never raise their level |
| F-09 | P2 | Budget UX | The per-profile daily cap (about 100 answers) is only reported after the user types an answer. Starting a session isn't blocked |
| F-10 | P2 | Practice / trace | API only: a Generalist asking for Group specifics practice silently gets Accounting, and the trace doesn't say why |
| F-11 | P2 | Auth | Lockout is per name, so anyone can lock a classmate out for 15 minutes with 5 wrong passwords |
| F-12 | P2 | Deploy | `render.yaml` deploys `branch: v2`, but `origin` still has only `main` (backend review #6 is still open) |

---

## Details

### F-01 (P1): Ending the placement mid-topic shows "nothing placed" while the server did place a topic
- **Repro:** New generalist profile, intake, start the placement. Answer the first two accounting questions correctly (Basic → Intermediate, now on Advanced). Click End.
- **Expected:** The results screen shows Accounting placed at First-round ready, marked as partial, with the plan's first step.
- **Actual:** `POST /end` returns `"placement": {}` and `"placement_partial": true`. In `app.js` `renderResults`, an empty `r.placement` means the screen says "Placement paused · Let's finish your placement next time. You ended before we could place any topic." and shows **Restart placement interview**. But `_finalize` *did* credit the topic in progress: the profile has `accounting: 2` and a partial plan was built (`plan_created_partial`, `diagnostic_done: true`). Home then shows a plan and a First-round Accounting level that the results screen just said doesn't exist. The same gap applies whenever a skill was in progress: credit for the in-progress skill never reaches `r.placement`.
- **Cause:** `_report` returns `state["diag"]["results"]`, but the in-progress credit is only added to a local copy in `_finalize` (engine.py `_finalize`, `results = dict(d.get("results", {}))`).
- **Fix idea:** In `_finalize`, store the final placed dict in `state["placed_final"]` (or write it back into `d["results"]`) and have `_report` return that.
- Re-verified on HEAD 062ee2b (`reverify.json`).

### F-02 (P1): `c_dcf_tv_methods` model answer fails its own rubric
- **Repro:** Practise DCF, Basic, until "Two ways to get terminal value" comes up. Paste the worked answer the app shows (`template.solution`).
- **Expected:** Correct.
- **Actual:** 7 of 7 runs on the earlier build were graded "incomplete" (key points [2,3] hit). On HEAD 062ee2b it was graded **"incorrect"** (key point [2] only): "You could strengthen the answer by stating each formula and explicitly describing the cross-check." The rubric needs both formulas and the two-way cross-check, but the solution text has neither. **Impact:** In placement, one attempt that isn't a pass places DCF at `first_level − 1`. The TMT persona, answering "well" every time, was placed at **Getting started in DCF** only because of this question, and the plan then scheduled 4 Basic DCF drills. Students who copy the shown model answer next time are told they're wrong again.
- **Fix:** Add the two formulas and the "check the implied growth / implied multiple" sentence to the solution (bank.py around line 1912), or drop key points 1, 2 and 4 to "nice to have". All other conceptual and behavioral solutions served in these runs were graded correct, so this looks isolated. A full solution self-grading sweep was not run.

### F-03 (P1): Plan rebuild keeps completed tasks on their old dates (tasks after the interview, duplicate Final mock)
- **Repro:** Any profile with a plan for an interview in 30 days. Start the **Final mock interview** task by `task_id` today, answer 3, then End: the task is ticked. Edit targets: interview in 2 days → Save and rebuild.
- **Expected:** Completed tasks sit on the day they were done (`completed`), and nothing appears after the interview.
- **Actual:** The plan has the new final-prep tasks **plus** a done "Final mock interview" dated **2026-11-22**, a month after the new interview date (2026-10-26). Every rebuild also has **two** "Final mock interview" rows, because `carry_over` never lets a done final mock replace the new final mock. On HEAD, a drill done today but scheduled for Oct 28 also stays on Oct 28 ("2 tasks on/after interview"). Reproduced for all 3 journey users (`carry.py` output).
- **Fix:** In `plan.carry_over`, set `t["date"] = t.get("completed", t["date"])` for carried done tasks, and let a done mock replace the final mock when it is the only mock left, or drop `final` from carried tasks.

### F-04 (P2): `carry_over` leaves derived plan numbers stale
After a rebuild with done tasks, `minutes_per_practice_day`, `practice_days` and `skills[].drills` are not recomputed (only `drills/mocks/questions/hours_planned/review_hours` are). Examples on HEAD: 1 h/week → "about 26 min a practice day" vs a calendar average of 33. `practice_days` 8 vs 7. Row "DCF drills 0" while a (done) DCF drill is on the plan. Even with unchanged inputs: 26 vs 27 min, 26 vs 25 days. Fix: move the derived-stats block of `build()` into a helper and call it at the end of `carry_over`.

### F-05 (P2): Sub-skill drill drifts off-target while the trace claims the target
- **Repro (HEAD):** Generalist plan task "Drill: Fit & behavioral, Why banking, group and firm (towards Coffee-chat ready)". Start by `task_id` and answer 5.
- **Actual:** b_why_group, b_why_ib, b_why_firm, then **b_failure (fit.experiences)** and **b_weakness (fit.self_awareness)**. Every pick event still says "Practice target: Fit & behavioral / Why banking, group and firm". Same pattern earlier with "Teamwork and leadership stories" (only 2 Basic templates): 2 of 4 questions were off-target. The drill opener promises "8 questions" on that sub-skill.
- **Fix:** When `pick_targeted` relaxes the sub-skill, append "No fresh <sub-skill> question left, so a related <skill> question." to the reason, as practice already does. Optionally set the drill goal to min(8, available + numeric repeats).

### F-06 (P2): Interview "today" schedules work on the interview day
Interview date = today → plan = "Drill: Accounting" + "Final mock interview", both dated today (the docstring says "never on/after the interview day"). Reasonable as a morning warm-up, but the "Final mock" label and the rule conflict. Either allow it explicitly (title "Warm-up before your interview") or schedule nothing and show a "good luck" card. Tomorrow and 2 days out are correct: nothing on or after the interview date.

### F-07 (P2): Completed placement without `/end` is lost
A diagnostic with `complete: true` but `ended IS NULL` (tab closed or network dropped right after the last answer, or `/end` failed) is excluded by `active_session` (`if ... state.get("complete"): continue`) and is never finalized. Dashboard: `diagnostic_done: false`, no plan, so the student must redo the whole 15-minute placement. Reproduced by setting the state in sqlite. Fix: `active_session` returns complete-but-unended sessions with `"needs_end": true`, and the UI calls `/end` on boot (or `dashboard` finalizes them).

### F-08 (P2): Group-specifics drills that can't move the level
FIG persona placed at First-round in Group specifics: the plan has 3 drills titled "Drill: Group specifics (towards First-round ready; no Superday ready questions yet)". FIG has only 3 group questions (1 Basic, 2 Intermediate), so the drills alternate fig_ptbv / c_fig_no_ev and cannot raise the level. Suggest scheduling at most 1 maintenance drill when `target_available` is false, and wording it "Keep sharp: Group specifics".

### F-09 (P2): Daily per-profile token cap hit after about 100 answers, reported late
The practice sweep (≈100 answers on one profile) hit "Daily token budget for this profile reached. Come back tomorrow." (≈5.4k tokens per graded answer, cap 600k). That's fine for students. But `POST /api/session` still starts sessions, so the user sees the question, types an answer, and only then is refused. Suggest checking the budget in `start_session` (or showing it on Home).

### F-10 (P2): Generalist + Group specifics (API only)
`POST /api/session {"mode":"practice","focus":"industry"}` for a Generalist returns 200 with Accounting. The trace says "Practice: Accounting, Coffee-chat ready questions only." and doesn't mention the switch. The UI hides the option for Generalists, so this is API-only.

### F-11 (P2): Lockout can be triggered by anyone
5 wrong passwords lock the name for 15 minutes, case-insensitively, with no other factor. Acceptable for a class pilot. Note it in the report's limitations.

### F-12 (P2): Deploy branch not on GitHub
`render.yaml` has `branch: v2`, but `git branch -r` shows only `origin/main`. Push `v2` before deploying (owner action, not a code bug).

---

## What passed (this round)

**Journeys (generalist/associate, TMT/VP, FIG/MD):** sign-up → intake → full placement (12/15/19 questions) → plan → drill started by `task_id` on a *non-first* task (target = that task's skill, sub-skill and level) → End after 3 answers ticks **that** task id. A mock started by `task_id` (the Final mock, even when sent with `mode: "drill"`) runs as a mock and ticks that mock. Dashboard: progress % = done/total, streak 1, sessions = ended sessions with ≥1 graded answer, answered = graded turns, today's tasks = tasks dated user-today. Rebuild keeps completed tasks (carried 2), and a second rebuild is stable. TMT→FIG: `industry` placement removed, mastery reset to 0.3/n=0, plan row Getting started → Coffee-chat, response has `group_changed: true`.

**Session lifecycle:** resume via `/api/session/active` (same id, same question, transcript, progress) for drills and placement, and in the UI after F5 and after sign-in ("Continue your practice session"). Answer after end/complete → `blocked`, **0 model calls, 0 turns**. Double `/end` → 200 with the same debrief. Three concurrent `/end` → 409, 409, 200, with exactly 1 plan tick, 1 `end` event and 1 Coach call. End with 0 answers → no Coach call, not counted as a session, no tick. 1 or 2 answers → debrief, counted, no tick (threshold 3). Turn cap (turns=80) → blocked with no model call, and `/end` still writes a Coach debrief. Rate limit: the second answer within 1 s → "Slow down". Three concurrent submits → 1 graded, 2 "Still grading", 1 turn stored. Whitespace / zero-width answer → "Type an answer first.", no model call. `seconds: -5` → 422, a 20,001-character answer → 422, unknown session → 404, unknown `task_id` → falls back cleanly.

**Plan edge cases:** past date → 21-day maintenance plan with the "date has passed" headline and `interview_status: past`. Tomorrow and 2 days → final-prep (1–2 drills + 1 mock), nothing on or after the interview. 3/7/30/90 days → nothing on or after the interview, nothing before today. 120 days → capped at 90 with `horizon_capped: true` (the UI explains). 1 h/week → compressed to 3 drills + 5 mocks. 20/40 h/week → spread out, max 30 min/day (no cramming). On fresh builds, minutes/day = calendar average and per-skill drill counts = scheduled drills in every scenario. Invalid date → stored as none. Time zone at a date boundary (UTC 05:44): `X-TZ-Offset: -300` / `-840` → today Oct 24; `+540` / `+840` → Oct 23 for plan `created`, dashboard `today` and "interview today". Garbage header → UTC, 200. Playwright in Anchorage vs New York: "interview in 31 days" vs "30 days", and the calendar "today" highlight follows local time.

**Auth:** all 13 personal endpoints (including `/api/costs` and `/api/club`) → 401 without a token or with a garbage token. Another user's session id → 404 for answer, end, events and feedback, and it's not visible in their `/active`. Admin export → 404 with no header, a guessed token or a non-ASCII token. Sign-out invalidates the token. Lockout after 5 wrong passwords (the 6th attempt, even with the right password, is refused). Name/password length checks → 400/422.

**Practice filters (generalist + FIG, 7 skills × 3 levels, ≈100 answers):** every technical skill at every level serves the exact level while a fresh question exists. Every fallback carries an honest reason ("No fresh Superday ready question left, so the closest level with one (First-round ready)"). **0 back-to-back repeats of word questions**; numeric questions repeat only non-adjacently (new numbers). FIG Group specifics falls back honestly. Fit L1–L3 matched. (`c_ma_sellside` was served as Fit L2 on the first build; HEAD moves it to M&A, so that's fixed.)

**Calculator traps (QA-02):** 300 random draws per numeric template: **0 templates** where a misconception's values fall inside the correct tolerance (was up to 99%).

## Verified fixed: round-1 items (`qa_round1.md`)

| ID | Status | Evidence |
|---|---|---|
| QA-01 | Fixed | Generalist industry practice → 200 (Accounting), no 500 |
| QA-02 | Fixed | 0 trap/key overlaps in 300 draws per template |
| QA-03 | Fixed (but see F-01) | 0 answers: `diagnostic_done: false`, no plan, retake allowed. Partial: plan built, `placement_partial` listed, retake allowed |
| QA-04 | Fixed | `task_id` starts and ticks exactly the clicked task (drill and mock) |
| QA-05 | Fixed | `/api/session/active` + UI auto-resume after F5 and sign-in |
| QA-06 | Fixed | No back-to-back word repeats in 42 practice combos |
| QA-07 | Practice fixed (honest fallback). Plan partly open (F-08) | |
| QA-08 | Fixed (interview-today nuance in F-06) | |
| QA-09 | Fixed | 20 h/week: max 30 min/day, spread over the horizon |
| QA-10 | Fixed for fresh builds. Regresses after a rebuild (F-04) | |
| QA-11 | Fixed | TMT→FIG resets Group specifics |
| QA-12 | Fixed | `X-TZ-Offset` honoured; UI dates local |
| QA-13 | Fixed | Back from results stays in the app (`#home`) |
| QA-15 | Fixed | `horizon_capped` + UI line |
| QA-16 | Fixed | `hours_planned` + `review_hours` shown separately |
| QA-17 | Fixed | 0-answer sessions not counted |
| QA-19 | Fixed | `maxLength` set from `/api/meta` + counter |
| QA-20 | Fixed | Practice persona defaults to the intake persona |
| QA-14, 18, 21, 22, 23 | Not in my scope (UI / QA engineer B) | |
| QA-24 | Not changed (message still confirms a name exists). Accepted P2 | |

## Verified fixed: backend review P0/P1 (`backend_review.md`)

| # | Status | Evidence |
|---|---|---|
| 1 | Fixed | `_end_session` catches any exception and falls back to the computed debrief (code) |
| 2 | Fixed | Concurrent ends: 409/409/200, 1 tick, 1 end event, 1 Coach call. `finalized` flag |
| 3 | Fixed | `_interviewer_message` catches `Exception` → safe message (code) |
| 4 | Fixed | Answer after complete → blocked, 0 model calls |
| 5 | Fixed | See QA-01 |
| 6 | **Open** | F-12 (v2 not pushed) |
| 7 | Fixed | `requirements.txt` pinned |
| 8 | Fixed | `load_env` uses the first non-empty value (code) |
| 9 | Fixed | `LLM_TIMEOUT_SECONDS=45` |
| 10 | Fixed | User-today on plan, progress, mark_done and streak |
| 11 | Fixed (date issue F-03) | Completed tasks carried over |
| 12 | Fixed (UI gap F-01) | `diagnostic_done` = placement exists. In-progress credit given |
| 13 | Fixed | Turn-capped session still gets a Coach debrief |
| 14 | Fixed | `/api/session/active` |
| 15 | Fixed | Bad date → none. Past → maintenance plan with headline |
| 16 | Fixed | `/api/costs` and `/api/club` 401 without a token. Club hides <3 members |
| 17 | Fixed | WAL + `busy_timeout` |
| 18 | Fixed | Indexes present |
| 25 / 26 / 27 / 28 | Fixed | IntegrityError handled; non-ASCII admin token → 404; sign-out works; `seconds` validated (422) |
