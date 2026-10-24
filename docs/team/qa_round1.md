# QA round 1: exploratory test of app-v2 (branch v2)

Tested 2026-10-24 on a local server (port 8205) with its own data folder. The live pilot (port 8000, `ib-ready`) was not touched.
Method: three personas driven end to end through the UI with Playwright (sign in, intake, placement, results, every tab), then edge cases through the UI and the API. Answers were built from the answer key in sqlite (`bank.from_state`). Model spend: about $0.014 across 61 graded answers.
Screenshots and scripts are in `C:/Users/ANAS/AppData/Local/Temp/claude/C--Users-ANAS-Desktop-Prob-and-Stat/a0cf80a0-8ce1-4782-89ed-7d7490e63cc7/scratchpad/qa1/` (screenshots in `shots/`, shortened to `SHOTS/` below).

## Summary

| ID | Sev | Area | Title |
|---|---|---|---|
| QA-01 | P0 | Practice | "Group specifics" practice crashes with a 500 for Generalist users |
| QA-02 | P1 | Grading | The calculator marks known misconception answers as correct (tolerance wider than the trap) |
| QA-03 | P1 | Placement / plan | Ending the placement early marks it "done", builds no plan, and you can't retake it |
| QA-04 | P1 | Dashboard / plan | "Start" on a Today's-plan task always starts the first open drill, not the task you clicked |
| QA-05 | P1 | Session | Refreshing or signing out mid-session loses the session with no way to resume |
| QA-06 | P1 | Practice | Practice repeats the same conceptual question (M&A Basic asks "Why companies acquire" 4 times in a row) |
| QA-07 | P1 | Practice / plan | Level filters aren't strict for Group specifics: Basic and Advanced quietly serve Intermediate. The plan also schedules "Advanced drill: Group specifics", which has no questions |
| QA-08 | P1 | Plan | Interview date in the past, today or tomorrow: a 3-day plan with tasks after the interview |
| QA-09 | P1 | Plan | With many hours a week, all drills are crammed into the first 3 days (200 min/day) while the summary says about 19 min/day |
| QA-10 | P1 | Plan | When the plan is compressed, the per-skill "Drills" column still shows the uncompressed counts (27 vs 3 actual) |
| QA-11 | P1 | Plan / skills | Switching group carries the old group's "specifics" level over (TMT Basic becomes FIG Basic without a FIG question) |
| QA-12 | P1 | Plan | Calendar "today" highlight and default interview date use UTC, so they're off by one day in US evenings |
| QA-13 | P1 | Navigation | Browser Back leaves the app (no history for tabs) |
| QA-14 | P1 | Mobile | Plan and Agents pages scroll sideways at 390 px. After an answer, the Live diagnosis is below the fold. Two tabs are hidden off-screen |
| QA-15 | P2 | Plan | The interview date is clamped to 90 days without telling the user. Plan ends in January for a May interview |
| QA-16 | P2 | Plan | Hours don't add up: "12.8h total" vs about 11h of tasks on the calendar (15% review time not shown) |
| QA-17 | P2 | Dashboard | Sessions ended with 0 answers count as "sessions". Abandoned (refreshed) sessions don't count |
| QA-18 | P2 | Survey | Feedback with only "Found a weak spot" or "How long" filled is rejected |
| QA-19 | P2 | Composer | No character limit or counter. A 5,000-character answer is cut to 2,000 and only a small Safety card says so |
| QA-20 | P2 | Dashboard | "Practise anything" defaults to Associate, not the interviewer chosen at intake |
| QA-21 | P2 | Accessibility | Clickable skill cards can't be reached by keyboard. Rating buttons have no aria-pressed |
| QA-22 | P2 | Skills / copy | Advanced user sees "Target: Advanced" / "next: Advanced". Fit can never be placed above Intermediate |
| QA-23 | P2 | Skills | Placed level and mastery % disagree (a skill "Basic" at 27% mastery, labelled weak) |
| QA-24 | P2 | Auth | The wrong-password message says the name exists (name enumeration) |

---

## Details

### QA-01 (P0): Practise "Group specifics" crashes for Generalist
- **Area:** Dashboard → Practise anything
- **Steps:** Intake with Generalist. On the dashboard choose skill "Group specifics" (any level) and click Practise. Or POST `/api/session {"mode":"practice","focus":"industry"}`.
- **Expected:** Either the option is hidden for Generalist, or a friendly message appears.
- **Actual:** 500 "Something went wrong on our side." The server log shows `ValueError: min() iterable argument is empty` in `engine._pick` (practice branch → `mastery.choose([])`). The session row is created before `_pick`, so each attempt likely leaves an orphan session. The dropdown always lists "Group specifics", even though the dashboard hides that skill for Generalist.
- **Screenshot:** n/a (toast). Reproduced through the API for all four level options.

### QA-02 (P1): The calculator accepts misconception answers as correct
- **Area:** Grading (`bank.check_numbers`, label tolerances)
- **Steps:** Advanced persona, placement LBO Advanced (`mkt_rates_lbo`). Answer "I think new IRR is 13.7", which is the base-case IRR, the classic "rates have no effect" mistake.
- **Expected:** Incorrect, tagged MKT_RATES_NO_EFFECT.
- **Actual:** IRR checked "correct" (13.7 vs key 13.21; `tol_abs=1.0`). The verdict was "Right numbers, thin reasoning", which counts as a pass, so the candidate was placed at **Advanced** LBO. The specialist even flagged MKT_RATES_NO_EFFECT. The correct check runs before the trap check, so whenever a trap value is inside the tolerance the trap is never detected.
- **How often it happens:** 300 random draws per template, counting how often a trap's required values fall inside the correct tolerance:

  | Template | Share | Example |
  |---|---|---|
  | mkt_rates_lbo | 99% | PRETAX trap 17.78 vs key 18.06 |
  | dcf_pv | 75% | simple-discount trap |
  | mkt_rates_wacc | 71% | PRETAX trap |
  | ev_tsm | 40% | all-options trap |
  | ev_bridge | 21% | sign trap 1270 vs 1280 |
  | rx_waterfall | 9% | pro-rata trap |

  The rest are at 2% or below.
- **Fix ideas:** Check the traps first (or use tolerance = min(tol, half the gap to the nearest trap)). Or regenerate params until key and traps are separable.
- **Screenshot:** SHOTS/Max_03_results.png (LBO "placed at Advanced")

### QA-03 (P1): Ending the placement early breaks onboarding
- **Steps:** New profile, intake, start the placement. Click End session after 0 or 2 answers.
- **Expected:** The placement can be resumed or retaken, or a partial plan is built from the skills placed so far, with a clear message.
- **Actual:** `placement = {}`, no plan is built, and `diagnostic_done` becomes **true** (it counts any ended diagnostic). The dashboard then shows level "Foundations" (not "Not placed yet"), plan progress "–", and the main button switches to "Mock interview". There is no button left to start the placement. Edit targets now says "Save and rebuild my plan", which builds a Foundations plan from no evidence. Answers already given (for example, 2 correct accounting answers) give no placement credit.
- **Screenshot:** reproduced through the API (profiles EarlyEnd0, EarlyEnd2)

### QA-04 (P1): "Start" on a specific task starts a different drill
- **Steps:** Average persona dashboard. Today's plan lists: Fit drill, Accounting drill, EV drill. Click **Start** on the 3rd (EV & valuation).
- **Expected:** An EV & valuation, Multiples drill.
- **Actual:** "Targeted drill: Fit & behavioral, Teamwork and leadership stories". `startTask()` calls `startSession("drill", persona)` without the task's skill, sub-skill or level, so `_drill_target` always picks the first open drill. On the results screen, `mark_done` then ticks the earliest open drill of that skill.
- **Screenshot:** SHOTS/edge_drill_from_last_task.png

### QA-05 (P1): Refresh or sign-out mid-session loses the session
- **Steps:** Start a drill, answer one question. Press F5 (or sign out and back in).
- **Expected:** You're back on the same question, or offered "Resume your session".
- **Actual:** You land on the dashboard. `S.session` is null and the Interview tab sends you to the dashboard. The server session stays open forever: it is never ended, no debrief, and it doesn't count toward the plan or the "sessions" stat. Answers already graded do update mastery.
- **Screenshot:** SHOTS/edge_after_reload.png

### QA-06 (P1): Practice repeats the same question verbatim
- **Steps:** Practise M&A, level Basic. Answer correctly 3 times.
- **Expected:** Different questions, or a note that only one Basic M&A question exists and the level is widening.
- **Actual:** "Why companies acquire" is asked 4 times in a row. The practice branch uses `mastery.choose()` on a strict pool with no freshness rule; `pick_targeted` has one, practice doesn't. Other thin pools hit the same problem: EV/LBO/Fit Advanced (1 template each), Accounting Advanced (2).
- **Screenshot:** API log (profile Edge1)

### QA-07 (P1): Group specifics level filter isn't strict, and Advanced group drills are planned anyway
- **Steps:** FIG (or TMT) profile. Practise "Group specifics" at Basic or Advanced.
- **Expected:** Only questions at that level, or "No Advanced questions for FIG yet".
- **Actual:** An Intermediate question is served (every group-specific question is level 2 except a few). The Director trace even says "Practice: Group specifics, Advanced only." In the plan, the advanced candidate gets "Advanced drill: Group specifics" and the skill card says "next: Advanced", but no Advanced FIG or TMT questions exist. FIG has only 2 group questions in total, so FIG mocks and drills repeat quickly.
- **Screenshot:** SHOTS/edge_practice_industry_advanced.png, SHOTS/Max_04_dashboard.png

### QA-08 (P1): Interview date in the past, today or tomorrow
- **Steps:** Edit targets. Set the date to 10 days ago, today, or tomorrow. Save and rebuild.
- **Expected:** Past dates rejected (the date input has no `min`). Today/tomorrow get a "cram" plan that ends by the interview.
- **Actual:** `days_until` clamps to at least 3, so all three give a 3-day plan: "Target: Intermediate in 3 days". For a past date, every task is after the interview. For tomorrow, 3 of 6 tasks, including the "Final mock", are scheduled after the interview. The dashboard still shows "interview 2026-10-14".
- **Screenshot:** API (profile Ava, plan dumps)

### QA-09 (P1): Calendar crams every drill into the first days
- **Steps:** 20 h/week, interview in 60 days. Rebuild the plan.
- **Expected:** Drills spread across about 51 practice days. "About N min per practice day" matches the calendar.
- **Actual:** Calendar: Oct 24 200 min, Oct 25 200 min, Oct 26 140 min, then only a 30-min mock each week for 8 weeks. The summary says "about 19 min per practice day". `per_day_min = hours/6` fills each day to capacity instead of spacing tasks. The same thing at 6 h/week shows 60 min/day vs "about 43 min".
- **Screenshot:** SHOTS/mobile_plan.png (6 h/week variant: 60-min days vs "about 43 min")

### QA-10 (P1): Plan table drill counts don't match the plan after compression
- **Steps:** 1 h/week, 21 days. Rebuild.
- **Expected:** The per-skill Drills column adds up to the "targeted drills" total.
- **Actual:** The rows show 6/2/4/4/2/4/5 (27 drills) but the plan has 3 drills (Fit, Accounting, DCF). EV, M&A, LBO and Group specifics get no drills, yet the table promises them. `rows` are built before compression and never updated.

### QA-11 (P1): Switching group keeps the old group's level
- **Steps:** TMT profile placed "TMT specifics: Basic". Edit targets → FIG → Save and rebuild.
- **Expected:** FIG specifics unplaced (Foundations), or a prompt to take a short FIG placement.
- **Actual:** "Financial Institutions specifics: Basic", with no FIG question ever answered. Mastery, placement and level are stored under the generic `industry` skill.

### QA-12 (P1): UTC date bugs in the browser
- **Steps:** Browser in America/New_York at 21:30 on Sat Oct 24. Open My plan.
- **Expected:** "Sat, Oct 24 · today".
- **Actual:** "Sun, Oct 25 · today" is highlighted (`new Date().toISOString()` is UTC). The intake's default "interview in 21 days" uses the same UTC call. Meanwhile the dashboard's "Today's plan" uses server-local time, so the two disagree every US evening.
- **Screenshot:** SHOTS/tz_plan_today_label.png

### QA-13 (P1): Back button leaves the app
- **Steps:** Signed in, click My plan, then Skills map, then press browser Back.
- **Expected:** Back to My plan.
- **Actual:** The app is left entirely (about:blank in the test; in real use, the previous site). There's no `history.pushState` or hash routing. On mobile this happens easily.

### QA-14 (P1): Mobile (390x844) layout issues
- My plan: the page is 425 px wide (plan-summary card overflows), so it scrolls sideways. SHOTS/mobile_plan.png
- Agents & cost: 399 px wide (stat cards overflow).
- Interview: after submitting, the Live diagnosis card starts at y=968, below the composer and off-screen. The user can't see which line items were right without scrolling past the input. The card is also 404 px wide. SHOTS/mobile_interview_after_answer.png
- Top tabs scroll sideways with no cue, so "Agents & cost" and "Finance Club" are off-screen.
- Welcome, Intake, Dashboard, Skills, Club and Results fit within 390 px (SHOTS/mobile_*.png).

### QA-15 (P2): Dates beyond 90 days are clamped without telling the user
For an interview on 2027-05-12, the plan says "in 90 days" and ends on 2027-01-21, with nothing in the last 4 months.

### QA-16 (P2): Plan hours don't reconcile
"12.8h total, of 18h available", but the calendar's day minutes add up to about 11h. The 15% review time is in the total but never shown as a task or explained on the page.

### QA-17 (P2): Momentum "sessions" is inconsistent
Ending a session immediately (0 answers) adds 1 to "sessions". A refreshed or abandoned session with answers adds 0 but its answers count toward "answers graded".

### QA-18 (P2): Survey validation
Clicking Send with nothing filled gives "Pick a rating or write a line first." (fine). But filling only "Found a weak spot" or "How long would finding these take" gives the same rejection, and that data is lost.

### QA-19 (P2): Long answers are cut without telling the user
The textarea has no `maxlength` or counter. A 5,000-character answer is cut to 2,000 server-side. The only sign is "Input flagged: answer truncated" in the Safety card, which on mobile is below the fold.

### QA-20 (P2): Practise anything ignores the intake interviewer
An MD-intake user's "Practise anything" persona dropdown defaults to "Associate (first round)", so practice sessions run with the Associate.

### QA-21 (P2): Keyboard and accessibility
Tab order on sign-in is fine (name → password → Continue), and Enter submits. The dashboard skill cards are clickable `div`s with no tabindex or role. Rating 1–10 buttons have no `aria-pressed`. The focus ring is the browser default only (1px auto) on the purple primary button.

### QA-22 (P2): Copy at the top of the ladder
- An Advanced user sees "Target: Advanced", and every Advanced skill says "next: Advanced".
- Fit placement maxes out at 2 (number of fit passes), so Fit can never be placed at Advanced.

### QA-23 (P2): Placed level and mastery % disagree
Average persona: Accounting "Basic" with 27% mastery bar (red-ish, "weak"). Novice: Accounting "Basic" at 54%. Same level, very different bars, because one wrong answer at Intermediate drags the overall skill mastery down. Confusing for students.

### QA-24 (P2): Auth message reveals that a name exists
Wrong password gives "That name is taken and the password doesn't match." This is acceptable for a class pilot, but it confirms which names exist.

---

## Persona results (UI, end to end)

| Persona | Intake | Placement | Plan |
|---|---|---|---|
| Novice (Nova) | Generalist, Networking, Associate | 8 questions, Foundations overall (Accounting Basic) | 26 drills + 3 mocks, 11.7h of 18h |
| Average (Ava) | TMT, First rounds, VP | 13 questions, Basic in every technical skill + TMT; Intermediate wrong | 29 drills + 3 mocks |
| Advanced (Max) | FIG, Superdays, MD | 18 questions, Advanced in all 5 technical skills (LBO wrongly, see QA-02), FIG Intermediate | 24 drills + 3 mocks |

**Mock fit share** (40 sampled first questions per persona, FIG):

| Interviewer | Measured | Spec |
|---|---|---|
| Associate | 12.5% | 10% |
| VP | 22.5% | 25% |
| Director | 47.5% | 50% |
| MD | 67.5% | 70% |

This is consistent with `FIT_SHARE`.

**Practise filters:** skill and level were strictly respected for every technical skill and Fit at every level (Generalist and FIG). The exceptions are Group specifics (QA-01, QA-07) and repetition (QA-06).

## What worked well
- The placement flow is smooth. It adapts as designed (climbs while right, moves on at the first miss), and the results screen with placement chips and before/after bars is clear.
- Double-clicking Submit sends only one answer (client `S.busy`). Two concurrent API posts are handled: the second gets "Still grading your last answer."
- Empty and whitespace-only answers are refused without using an attempt.
- Speaking-style answers are read well: "um so net income goes down like six and uh cash, cash goes up like four" was graded correct on a write-down question.
- An answer of just numbers gets the right numbers credited, then "probe why" (good coaching behaviour).
- Answering after a session has ended gets a clean 400. Ending twice is idempotent.
- The Fit/MD mix, debrief quality, and the diagnosis panel (line-item checks, misconception, worked solution) all look good. The Agents & cost trace is detailed and cheap (about $0.0002 per graded answer).
- Sign-in validation: the 6-character minimum is enforced client-side, and the wrong-password message is clear.
- No JavaScript console errors in any run.
