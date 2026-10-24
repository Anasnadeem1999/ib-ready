# UX spec for app-v2: an IB interview coach that a newcomer can use without help

Owner: UI/UX designer · Status: spec only (no app code changed) · Date: Sat Oct 24 2026 · Due: Mon Oct 26, 6 PM

**How I tested:** I ran the app on port 8201 with a scratch data folder and went through it twice in Chromium at 1440x900 and 390x844:
- as a **new student**: sign-in errors, intake, every tab before placement, the full placement interview, results, plan, dashboard, skills map, a targeted drill with wrong and right answers, the "skills updated" screen, Agents & cost, and Finance Club;
- as a **returning student**: sign out, sign in again, dashboard, edit targets, wrong-password error.

That came to 29 graded answers, about $0.007. The 45 screenshots are in
`C:/Users/ANAS/AppData/Local/Temp/claude/C--Users-ANAS-Desktop-Prob-and-Stat/a0cf80a0-8ce1-4782-89ed-7d7490e63cc7/scratchpad/ux/shots/`. Names follow `NN_screen_d.png` (desktop) and `NN_screen_m.png` (mobile). Shot IDs in this spec (S01, S08, …) refer to those files.

**What the rubric checks:** "Look + feel (10): good-looking, easy to use, clean layout, clear buttons; a newcomer can figure it out." Grading is on the first impression, so the welcome screen and the first 60 seconds matter most.

---

## 0. Priority table (do P0 before Monday; P1 if time allows; P2 is polish)

| # | Pri | Area | Problem (evidence) | Fix (section) | Effort |
|---|-----|------|--------------------|---------------|--------|
| 1 | **P0** | Welcome | The 4 "how it works" cards are broken. Text wraps one word per line, the cards nest inside each other, and the numbers come out as 1/2, 3/4, 5/6, 7/8. This is the first thing a grader sees (S01, desktop and mobile). Cause: `.steps div` also matches the inner `<div>`. | Change the selector to `.steps > div` (§4.6 CSS-1) | 5 min |
| 2 | **P0** | Dashboard | The empty "Today's plan" text wraps one word per line, because the `li` inherits the 3-column task grid (S03 dashboard). The empty trace list in Agents & cost has the same bug. | Add an `.empty` class (CSS-2) | 5 min |
| 3 | **P0** | Name | "Tick & Tie" means nothing to a student, and the subtitle "IB technicals, diagnosed" is jargon. | Rename to **IB Ready** (user decision, §5) | 20 min |
| 4 | **P0** | Nav | There are 6 tabs. Two of them ("Agents & cost", "Finance Club") are not for students. "Interview" silently sends you back to the Dashboard when no session is running, which is a dead end. On mobile the tabs wrap onto 2 lines and the last two are pushed off-screen. | New nav: **Home · My plan · Practice · Progress**. Agents & cost and Finance Club move into **How it works** (§1) | 1 h |
| 5 | **P0** | Results / debrief | It feels harsh and noisy. Headlines say "exposed a clear gap". Seven skill rows show "30% → 17% ▼" in red, but the 30% "before" is a made-up starting value nobody earned. The survey takes as much space as the debrief. The coach's `next_session` sentence is never shown. Token cost appears in the footer. | Restructure into "What went well / One thing to work on / Your next step". Show only the skills this session touched. Hide the made-up starting value. Collapse the survey. Change the coach tone (§2.8, §2.8a) | 2 h |
| 6 | **P0** | Jargon | Coverage/product groups, Superday, Associate/VP/MD, mastery, misconception, sub-skill, EV/DCF/WACC/LBO, "line item" and "Live diagnosis" are never explained. | Add a `?` tooltip glossary (§2.12) and student-facing renames (§1.3) | 1.5 h |
| 7 | **P0** | First run | Nothing explains what happens next. The tabs can be opened before intake (dashboard says "Generalist / not sure yet" and "30% mastery" before any answer). | Hide the tabs until intake is saved. Add a 3-step "How this works" panel and coach marks (§2.11) | 1 h |
| 8 | **P0** | Contrast | White text on the primary button (`#7c6ad6`) is 4.3:1. `--ok` is 3.4:1, `--bad` 3.9:1, butter-ink and peach-ink are about 4.1:1, and the sparkline placeholder is about 2.6:1. All fail WCAG AA. Nothing has a visible `:focus-visible` style. | Token swaps and a focus ring (§4.1, §4.5) | 30 min |
| 9 | **P0** | Interview | The live cost/token meter sits in the top bar during student sessions. The "This turn's agents" card takes a third of the side panel. The side panel's right border is clipped (S05b, S10). The verdict dot is out of line with the verdict title. | Move cost and agents behind a "Behind the scenes" toggle. Fix the clipping (CSS-4, CSS-5) | 45 min |
| 10 | **P1** | Hierarchy | Every section title is the same 12 px grey uppercase `.card-title`, so nothing stands out. Page widths jump between 860, 1000 and 1280 px. The Plan page has no page heading, unlike the other pages. | Type scale, a section-title component, 3 container widths (§4.2–4.4) | 1 h |
| 11 | **P1** | Dashboard | Each skill card shows two progress bars (the level ladder and the mastery bar). "LBO: Advanced · next: Advanced" makes no sense. On mobile, today's tasks sit below 7 skill cards. The main button reads "Next: Basic drill: Fit & behavioral, Strengths and weaknesses" (64 characters). | One progress element per skill. A short button label. Today's tasks first on mobile (§2.6) | 1.5 h |
| 12 | **P1** | Plan | The task circles look like checkboxes but do nothing. The plan summary has a large empty area. Weak sub-skill rows are not lined up with the skill pills. Dates show as ISO ("2026-11-14"). | §2.5, CSS-9/10 | 1 h |
| 13 | **P1** | Errors | All errors appear in one bottom toast with a rose border, even success messages ("Plan rebuilt"). The sign-in error shows about 450 px away from the form. There is no `role="status"`. | Inline form errors and toast variants (§2.13) | 45 min |
| 14 | **P1** | Intake | The stage subtitles repeat the title ("First-round interviews / First rounds"). The groups have no explanation. "Practise" (UK spelling) and "Practice" are mixed. | §2.2 copy | 20 min |
| 15 | **P1** | Mobile | The session bar is cramped. The composer pushes Submit below the fold. The 3 Momentum stats stack into 3 tall boxes. The labels in the results rows wrap to 4 lines. | §3 | 1 h |
| 16 | **P2** | Polish | Inline `style=""` attributes all over `index.html`. No `prefers-reduced-motion` support. Sparkline placeholder text floats in the middle of the card. Uneven heights of the skill cards on the Skills page. | CSS-6/7, §4.7 | 1 h |

---

## 1. Information architecture

### 1.1 New top nav (student)

| Order | Tab label | Replaces | What it holds |
|---|---|---|---|
| 1 | **Home** | Dashboard | Next step, today's tasks, level, streak |
| 2 | **My plan** | My plan | Day-by-day plan, skill targets |
| 3 | **Practice** | Interview + "Practise anything" card | When no session is running: a launcher (Targeted drill / Mock interview / Pick a topic). During a session: the interview screen. It is never a silent redirect. |
| 4 | **Progress** | Skills map | Skill levels, mistake patterns, history |

Right side of the top bar:
- a `How it works` text link (opens the page below);
- an avatar chip `Anas ▾` with a menu: *Edit my goals*, *How it works*, *Sign out*.

### 1.2 "How it works" page (grader / transparency, not in the student tabs)

The route is `#how-it-works`. It has three anchored sections:
1. **How your answers are checked.** A plain-English diagram: Interviewer asks → Calculator checks your numbers → Specialist finds the mistake pattern → Coach writes your debrief → Planner updates your plan. One sentence each.
2. **Agents & cost.** The current trace and cost tables, moved here unchanged, under the heading "Behind the scenes: agents & cost". This is where graders find the token and cost evidence.
3. **For finance clubs.** The current Finance Club view, renamed. Intro copy: *"Running a finance club? This anonymised view shows which mistakes are most common across everyone using this app, so you can plan workshops. No names or answers are ever shown."*

**Why move Finance Club off the student nav:** A student opening the app does not know they are in a "club". The tab sounds like a social feature or a sign-up wall, and it shows other people's data next to their own prep, which adds pressure. It is a B2B/admin view, and its real value is as evidence of the business model for graders. That belongs on a page that explains itself. It stays one click away, so the demo video can still show it.

**Why move Agents & cost:** A cost meter in dollars and tokens during a mock interview is irrelevant to a student. It also distracts and suggests "this is a dev tool". The rubric still rewards showing it, so it moves to How it works. Add a "Behind the scenes" toggle in the interview side panel (off by default, remembered in localStorage) for demo recordings.

### 1.3 Student-facing renames (labels only; API and IDs unchanged)

| Current | New | Reason |
|---|---|---|
| Tick & Tie | IB Ready | §5 |
| IB technicals, diagnosed | Practice IB interviews. Learn why. Get a plan. | Plain language |
| Dashboard | Home | Familiar |
| Interview (tab) | Practice | Covers drills and mocks |
| Skills map | Progress | Says what the student gets from it |
| Agents & cost | How it works → Behind the scenes | §1.2 |
| Finance Club | How it works → For finance clubs | §1.2 |
| Edit targets | Edit my goals | Plain language |
| Live diagnosis | Feedback on your answer | Plain language |
| This turn's agents | Behind the scenes (hidden by default) | §1.2 |
| Misconception(s) | Mistake pattern(s) | Students don't use "misconception" |
| active / cleared (tags) | Still working on it / Fixed ✓ | Less alarming |
| Mastery 41% | Confidence 41%, with a `?` tooltip | "Mastery" sounds like a grade |
| Foundations (level 0) | Not yet placed (before any answer) / Getting started (after) | Avoid "Foundations" vs "Basic" confusion |
| Momentum | Your streak | Plain language |
| Practise anything | Practice on your own (moves to the Practice tab) | US spelling, clearer |
| Placement interview | Placement interview, with the helper text *"a 15-minute check to find your starting level"* | Explain on first use |
| Debrief / FOCUS NEXT | Your coach's notes / One thing to work on next | Kinder tone |
| Send feedback / 30-second feedback | Help us improve (optional) | Keep, but secondary |
| Hands-free | Hands-free voice mode, with a `?` tooltip | Unclear |
| Rebuild plan from my latest results | Update my plan with my latest results | Clearer |

Use **US spelling** ("practice") everywhere.

---

## 2. Screen-by-screen spec

Shared layout rules: a sticky top bar 64 px tall; page containers per §4.4; every page starts with a **page header** (H1 + one-line lead, left-aligned with the cards below); section titles use the §4.2 `section-title`, not the uppercase micro-label.

### 2.1 Welcome / sign-in
**Purpose:** In 5 seconds, a student understands what this is, that it is safe to try, and how to start.

```
[logo] IB Ready                                           (no tabs)
          Practice IB interviews. Learn why. Get a plan.
┌──────────────── 7/12 ────────────────┐ ┌──────── 5/12 ────────┐
│ H1  Practice investment banking        │ │ H2 Get started         │
│     interviews, and learn why you      │ │ Username  [________]   │
│     got each one wrong.                │ │ Password  [________]   │
│ Lead (max 60ch)                        │ │ helper text            │
│ ┌─1─ Find your level (15 min) ───────┐│ │ [ Continue ] primary   │
│ ├─2─ Get a day-by-day plan ──────────┤│ │ inline error slot      │
│ ├─3─ Practice with an AI interviewer ┤│ └────────────────────────┘
│ └─4─ Watch your skills grow ─────────┘│ "New to IB? That's fine" note
└────────────────────────────────────────┘
```

**Copy**
- H1: **Practice investment banking interviews, and learn *why* you got each one wrong.**
- Lead: *An AI interviewer asks you real IB interview questions. Your numbers are checked by a calculator, every mistake is explained, and you get a study plan that fits the time you have before your interview.*
- Steps (number, bold title, one line):
  1. **Find your level**: a 15-minute placement interview across 7 topics.
  2. **Get your plan**: what to practice each day until your interview.
  3. **Practice**: short drills and full mock interviews. Type or speak.
  4. **See yourself improve**: every session updates your progress.
- Card H2: **Get started**
- Field labels: **Username** (placeholder `e.g. anas`), **Password** (placeholder `At least 6 characters`).
- Helper: *New here? Pick any username and password. That creates your private profile. Use the same pair next time to continue.*
- Button: **Continue**
- Reassurance under the card (small, muted): *New to investment banking? Start anyway. The placement interview begins with the basics, and every term has a ? you can tap.*

**Acceptance criteria**
- Each step card shows its number once. Body text wraps normally (at least 6 words per line at 1440).
- The H1 is at most 3 lines at 1440 and at most 4 lines at 390.
- Errors (short password, name taken / wrong password) show inline under the password field with `role="alert"`, not as a toast.
- The sign-in card is above the fold on mobile. On mobile the order is H1, lead, **form**, then steps.

### 2.2 Intake ("Your goals")
**Purpose:** Collect 5 inputs in under a minute, without the student needing to know IB vocabulary.

```
Page header: H1 "Tell us about your interviews"  lead
Progress dots: ● ○ ○ ○ ○  (optional: one card per step on mobile)
Card 1  Which team are you aiming for? (?)   [Not sure yet ★ first]
        Industry teams (coverage) (?) ......  Deal-type teams (product) (?) ......
Card 2  Where are you in recruiting?         4 options with real descriptions
Card 3  When is your interview?  [date]  "23 days away"   |  Hours per week  [slider] 6 h
Card 4  Who should interview you? (?)        4 personas
[ Save and start my placement interview ]   helper under button
```

**Copy**
- H1: **Tell us about your interviews**
- Lead: *Five quick questions so your practice matches your interviews. You can change these any time.*
- Q1: **Which team are you aiming for?** Tooltip: *Banks are split into industry teams (coverage groups, such as Healthcare) and deal-type teams (product groups, such as M&A). If you don't know yet, pick "Not sure yet". You'll get general questions.* Show **"Not sure yet / Generalist"** as the first option and pre-select it, so the form never blocks.
- Sub-labels: *Industry teams (coverage groups)* and *Deal-type teams (product groups)*.
- Q2 options, replacing the redundant subtitles:
  - Networking / coffee chats: *No interviews scheduled yet*
  - First-round interviews: *Phone or video screens*
  - Superdays: *Final-round, back-to-back interviews*
  - Have an offer: *Staying sharp before you start*
- Q3: **When is your next interview?** Helper: *No date yet? Pick roughly when recruiting starts.* Show a live "N days away" next to the date field.
- Q4: **How many hours a week can you practice?** Value: `6 hours / week`.
- Q5: **Who should interview you?** Tooltip: *Bankers interview differently depending on seniority. Associates focus on technical questions. Managing Directors focus on your story and fit. Start with Associate if you're unsure.* Persona subtitles stay.
- Button (first run): **Start my 15-minute placement interview**. Button (editing): **Save and update my plan**.
- Helper under the button (first run): *Next: about 10–20 questions, one attempt each, no notes. It's a check, not a test. Wrong answers just tell us where to start.*

**Acceptance criteria**
- The form can always be submitted, because Q1 has a default.
- Every field label is at least 14 px, ink colour (not muted).
- The selected option shows a check icon as well as the colour (not colour alone).
- Option tiles in a row have equal height (`align-items: stretch`).

### 2.3 Placement interview
**Purpose:** Find the student's level with low stress, and make it clear this is not graded like an exam.

This is the same layout as the interview screen (§2.7), with these differences:
- The session bar shows **"Placement interview · Topic 2 of 7: Valuation"** and a progress bar. Do not show the difficulty level ("Advanced") during placement, because it adds pressure.
- The first message is a **pinned intro card**, not a chat bubble: *"This is a check, not a test. About 15 minutes, one try per question. If you don't know something, say so and we'll move on. That's useful information too."* Add a **"I don't know this one"** ghost button in the composer during placement, which submits the text "I don't know".
- The feedback panel during placement shows only the verdict and one line (*"Noted. Full explanations come in your drills."*). Showing a long model answer after every wrong answer turns the check into a lecture.

**Acceptance criteria**
- No difficulty labels and no cost/token meter are visible.
- "I don't know this one" exists and moves the session on.
- The progress label counts topics, not raw question numbers.

### 2.4 Placement results (first "results" screen)
**Purpose:** Tell the student their level honestly and kindly, and hand them their plan.

```
pill "Placement complete"
H1  You're starting at Intermediate. Nice foundation.
lead  Your interview is in 21 days. Here's where you stand and what to do first.
┌ Your starting levels ─────────────────────────────────────────┐
│ Skill (tooltip)   ▮▮▯ Intermediate     "Strongest"/"Start here" │  ← 7 rows, sorted strongest→start-here
└───────────────────────────────────────────────────────────────┘
┌ Your coach's notes ───────────┐ ┌ Your first step ───────────────┐
│ What went well (2–3 bullets)   │ │ Basic drill · Accounting         │
│ Where to start (1–2 items)     │ │ Working capital · 20 min         │
└────────────────────────────────┘ │ [ Start first drill ]  primary  │
                                   │ See my full plan → (link)        │
                                   └──────────────────────────────────┘
▸ Help us improve (optional, 30 sec)    (collapsed)
```

- Remove the **before → after** bars on the placement screen. The "before" is a made-up 30% starting value, so "30% → 17% ▼" in red is both scary and meaningless. Show **one level meter per skill** (3 segments).
- Remove the coloured "placed at" chips that repeat the table.
- H1 pattern: `You're starting at {overall}.` plus a supportive clause picked from the data: "Nice foundation." (Intermediate+), or "That's a normal place to start." (Basic or below).
- The primary button text is short (**Start first drill**). The task name goes on the line above, not inside the button.

**Acceptance criteria:** no red ▼ on the placement screen; the CTA label is at most 24 characters; the survey is collapsed by default.

### 2.5 My plan
**Purpose:** Show "what do I do today, and is this doable?"

```
Page header: H1 "Your plan to Advanced"   lead "21 days · about 43 min a day · 1 rest day a week"   [Update my plan] ghost
┌ Today ─────────────────────────────── primary card, full width ┐
│ ○ Basic drill · Accounting: Working capital      20 min [Start] │
│ ○ Basic drill · Fit: Strengths & weaknesses      20 min [Start] │
└─────────────────────────────────────────────────────────────────┘
┌ Why this plan (coach summary) ─┐ ┌ Where you are → where you're going ┐
│ headline + why (max 3 lines)   │ │ Skill   Now ▮▯▯ → Goal ▮▮▯  drills  │
│ 3 stats: 12.8 h · 29 · 3        │ │   ↳ Focus on: Working capital       │
└────────────────────────────────┘ └────────────────────────────────────┘
Coming up  (week grouped: "This week" / "Next week" / "Week of Nov 9")
  day cards, past days collapsed, done tasks ✓ and struck through
```

**Copy:** H1 `Your plan to {target}`. Stats labels: *hours planned (of 18 available)*, *short drills*, *mock interviews*. Button: **Update my plan**, with the tooltip *Rebuilds the plan from your latest results. Finished tasks stay finished.*

- The day-card circles must either be **status icons** (not interactive: smaller, no border on pending tasks, a ✓ when done) or get a Start button. Use **Start buttons only on Today's tasks**.
- Write dates as "Sat, Nov 14". Never "2026-11-14".
- Add a tooltip on "drill" and "mock interview" the first time they appear (§2.12).

**Acceptance criteria:** there is a page H1; Today is the first card; the "Focus on" sub-row is indented to line up with the skill pill text (CSS-10); no empty white area in the summary card (CSS-9).

### 2.6 Home (dashboard)
**Purpose:** In one glance, answer "what should I do now?". Everything else is secondary.

```
H1 Good evening, Anas          [Edit my goals] ghost
lead  TMT · Interview Sat, Nov 14 (21 days)
┌ Up next ───────────────────────────── hero card, primary-soft bg ┐
│ Basic drill · Fit & behavioral                                   │
│ Strengths and weaknesses · about 20 min                           │
│ [ Start ] primary        Then: 2 more tasks today                 │
└───────────────────────────────────────────────────────────────────┘
┌ Your level ┐ ┌ Plan progress ┐ ┌ Your streak ┐   (3 compact stat cards, equal height)
┌ Today's tasks (list) ────────┐ ┌ Your skills (compact list, 7 rows) ───────┐
│ ✓ / ○ rows with Start         │ │ Accounting  ▮▯▯ Basic   "Start here" chip  │
└───────────────────────────────┘ │ …  "See all progress →"                    │
                                  └────────────────────────────────────────────┘
```

- Replace the large skill cards on Home with a **compact list**: name, 3-segment level meter, level label, optional "Start here" chip. The detailed cards stay on Progress, so they are not duplicated.
- **One progress element per skill.** Use the 3-segment level meter, where the current segment is partly filled by confidence %. Drop the separate mastery bar.
- When a skill is at the top level: show "Top level ✓" instead of "next: Advanced".
- Before placement: the hero card reads **"Start here: 15-minute placement interview"** with the button **Start placement**. Skill rows show "Not yet placed" with no percentages (not "30% mastery · 0 graded").
- The "Practice on your own" controls move to the Practice tab launcher.
- Plan status pill: `On track` / `A little behind (that's OK)` / `Ahead`, with a tooltip explaining how it is computed.

**Acceptance criteria:** the primary button label is at most 20 characters; on mobile "Up next" and "Today's tasks" appear before skills; no percentage is shown before a skill has at least 1 graded answer.

### 2.7 Practice: interview / drill screen
**Purpose:** A calm, focused chat where it is always clear what to do next.

```
Session bar: [Targeted drill · Associate]  Question 3 of 8 ▮▮▮▯▯  [🔊 Read aloud] [🎙 Hands-free ?]  [End session]
┌ chat (max 760px) ───────────────────────────┐ ┌ Feedback on your answer ───┐
│ Interviewer bubble                           │ │ ● Not quite                  │
│ Question card: [Accounting] Working capital  │ │   One number is off. Try     │
│   Title / text                    ⏱ 0:42/1:00 │ │   again: you have 1 more try.│
│ You bubble                                   │ │ ✓ Net income  you: -24       │
└──────────────────────────────────────────────┘ │ ✗ Cash        you: 0         │
┌ composer ────────────────────────────────────┐ │ Mistake pattern card         │
│ textarea                                      │ │ ▸ Worked solution            │
│ Attempt 2 of 2 · aim for 60s   [🎙 Speak] [Submit answer] │ └──────────────────────────────┘
└──────────────────────────────────────────────┘ ▸ Behind the scenes (off)
```

- Move **End session** from the composer to the session bar (as a ghost button), so it is not next to Submit. Ask for confirmation if fewer than 3 answers have been given: *"End now? We'll update your skills with what you've answered so far."*
- The cost/token meter and "This turn's agents" go inside the collapsible **Behind the scenes** section (off by default).
- Empty feedback state: *"Answer the question and your feedback appears here: which numbers were right, and why."*
- Rename the verdicts (keep the colours): Correct → **Correct ✓**. Right numbers, thin reasoning → **Right answer, explain more**. Incomplete → **Almost there**. Not quite → **Not quite yet**. Redirected → **Let's get back to the question**.
- Rename the "Grader's note:" prefix to **Why:**.
- Placeholder: *Answer as you would out loud: what changes, by how much, and why. Press Enter to send (Shift+Enter for a new line).*
- Timer: show `0:42 / 1:00`. When over time, turn amber with the text "Over time. That's fine, finish your thought."

**Acceptance criteria:** no $ or token counts are visible by default; the verdict dot lines up with the first line of the title; the side panel's right border is fully visible; on mobile, Submit is visible without scrolling while the textarea is focused.

### 2.8 Post-session: "Skills updated" + debrief
**Purpose:** Leave the student feeling capable and clear on one next step, while staying honest.

```
pill "Drill complete · 8 questions"
H1  Good work. Here's what changed.
lead  You practiced Fit & behavioral for 14 minutes.
┌ What changed ───────────────────────────────────────────────┐
│ Only skills touched this session:                            │
│ Fit & behavioral   ▮▯▯ Basic   28% → 14%  "Dipped this time" │
│   helper: Early dips are normal. One bad answer moves a new  │
│   skill a lot. It recovers as you practice.                  │
│ ▸ Show all skills                                             │
└───────────────────────────────────────────────────────────────┘
┌ Your coach's notes ──────────────────┐ ┌ Your next step ─────────────┐
│ headline (supportive, honest)         │ │ {next_session sentence}     │
│ What went well  • • •                 │ │ Basic drill · Accounting     │
│ One thing to work on                  │ │ Working capital · 20 min     │
│  ┌ Mistake pattern name ───────────┐  │ │ [ Start next drill ]         │
│  │ Why it matters: …               │  │ │ Back to Home (link)          │
│  │ Try this: …                     │  │ │ Plan: 1 of 32 tasks done     │
│  └─────────────────────────────────┘  │ └──────────────────────────────┘
│ ▸ 2 more things to work on            │
└───────────────────────────────────────┘
▸ Help us improve (optional, 30 sec)   — collapsed card, then the current survey
```

**Tone rules (honest but kind)**
- Never put a red ▼ next to a percentage on its own. A dip uses the amber "Dipped this time" chip plus the normalising helper line above. Level-ups keep the celebratory chip ("⬆ Level up! Accounting: Basic → Intermediate").
- Show only **one** focus area by default. The rest go behind "N more things to work on". One action reduces overwhelm.
- Label the focus parts **Why it matters:** and **Try this:** (today they run together in one paragraph).
- Always show the coach's `next_session` sentence. The API already returns it but the UI drops it.
- Remove the token/cost footer (it moves to Behind the scenes).
- If the session had no mistakes: *"No mistake patterns this session. That's a clean run."*
- If fewer than 3 answers were given: *"Short session, so this is a light read. A few more answers next time will sharpen your picture."*

### 2.8a Coach prompt change (owner: prompt/agent engineer; listed here because it decides how the debrief feels)
Add to `ticktie/prompts/coach.md` under Rules:
> - Tone: a warm, honest mentor talking to a stressed student. Start with what went well. Describe gaps as the next thing to practice ("work on…", "next, practice…"). Never use "exposed", "failed", "poor", "weak" or "gap" in the headline.
> - The headline names one real strength and one next focus, in under 25 words.
> - Never soften a factual error into "correct". Honesty about what was wrong is required.

Example headline before: *"This short drill exposed a clear gap in fit answers: you often gave generic or unsupported responses…"*
After: *"Your resume walkthrough landed well. Next, back each answer with one specific example."*

### 2.9 Progress (skills map)
**Purpose:** Answer "Where am I strong, what keeps tripping me up, and is it improving?"

- Page header: H1 **Your progress**. Lead: *Each topic has three levels: Basic, Intermediate and Advanced. You reach a level when you answer at least 2 questions at that level with 75%+ confidence (?). Topics marked "Start here" are where your drills begin.*
- Skill cards: equal heights, with the Drill button pinned to the bottom (CSS-7). Button label: **Practice {skill}**.
- Sub-skill chips: add a legend row ("● Needs work ● Solid ○ Not tried yet") so the meaning does not rely on red/green alone. Add an icon (! / ✓) inside each chip.
- Rename the right column to **Mistake patterns**, with the lead *"Mistakes you've made more than once, with your own words, so you can see the pattern. Fix one twice in a row and it's marked Fixed ✓."*
- Sparkline empty state: a left-aligned HTML caption, *"Your trend line appears after your next session."* (CSS-6).

### 2.10 How it works (§1.2)
Its H1 is **How it works**. It has three anchored sections, in-page jump links at the top, and the existing tables restyled with `.tbl`. The cost KPI uses plain words: *"Cost per graded answer: $0.0005, about 2,000 answers for $1."*

### 2.11 First-run guide
Two parts, both dismissible, and both saved in localStorage (`ibr_tour_done`):
1. **"How this works" panel** on Home before placement (it replaces the empty dashboard):
   > **Welcome, Anas. Here's how this works.**
   > ① **Placement interview** (15 min): find your level in 7 topics. ② **Your plan**: we schedule short drills and mock interviews until your interview date. ③ **Practice daily**: each session updates your plan.
   > [ Start placement interview ] primary · *Not now* link
2. **Coach marks after placement**: 3 steps, a tooltip bubble with an arrow, "1 of 3" counter, Next / Skip:
   1. On the **Up next** card: *"This is always your next step. Just press Start."*
   2. On the **My plan** tab: *"Your day-by-day schedule until Sat, Nov 14."*
   3. On the **Progress** tab: *"See each topic's level and the mistakes you keep repeating."*

**Acceptance criteria:** the tour shows once per profile; Esc closes it; focus moves to the bubble; the bubble does not cover the element it points at.

### 2.12 Jargon tooltips ("?" glossary)
Component: an 18 px circular `?` button (`aria-label="What is {term}?"`). On hover, focus or tap it opens a popover (max width 280 px). Esc and click-outside close it. Keep the glossary in one JS object.

| Term | Tooltip copy |
|---|---|
| Coverage group | An industry team (e.g. Healthcare). They advise companies in one sector. |
| Product group | A deal-type team (e.g. M&A, Leveraged Finance). They specialise in one kind of transaction. |
| Superday | The final round: several back-to-back interviews in one day. |
| Associate / VP / Director / MD | Banker seniority, junior to senior. Juniors ask more technical questions; seniors ask more about your story and fit. |
| Placement interview | A 15-minute check of your current level. It's not graded; it sets your starting point. |
| Drill | A short (about 20 min) set of questions on one topic at one level. |
| Mock interview | A full practice interview across mixed topics, like the real thing. |
| Confidence (mastery) | How sure we are that you can answer this topic correctly, based on your recent answers. |
| Mistake pattern | The specific wrong idea behind an answer (e.g. "forgets the tax effect"). Fixing the pattern fixes many questions. |
| Sub-skill | A smaller piece of a topic, like "working capital" inside Accounting. |
| Accounting / 3 statements | How the income statement, balance sheet and cash flow statement link together. |
| EV & valuation | What a company is worth to all its investors, and how bankers compare companies. |
| DCF & WACC | Valuing a company from its future cash flows, discounted at its cost of capital. |
| M&A | Mergers and acquisitions: one company buying another. |
| LBO | Leveraged buyout: buying a company mostly with debt, as private equity firms do. |
| Fit & behavioral | "Why banking?", your story, strengths and weaknesses. |
| Line item | One number the interviewer expects in your answer, such as net income or cash. |

Put tooltips on: the skill names (first occurrence per screen), intake Q1/Q2/Q5, the session-bar mode pill, the verdict check rows ("line item"), and Confidence %.

### 2.13 Empty, loading and error states

| State | Copy / behaviour |
|---|---|
| Home before placement | The "How this works" panel (§2.11); skills show "Not yet placed". |
| Plan before placement | Illustration-free card: **Your plan appears after your placement interview.** *It takes about 15 minutes.* [Start placement] |
| Progress before placement | **Nothing to show yet.** *Answer a few questions and your levels appear here.* [Start placement] |
| Mistake patterns, none | **No mistake patterns yet.** *That's either a clean run or you're just getting started.* |
| Practice tab, no session | A launcher (not a redirect). Three tiles: **Continue my plan** (next task), **Mock interview** (persona select), **Pick a topic** (skill + level selects). |
| How it works, no session | *Run any session to see its step-by-step trace here.* |
| For finance clubs, no data | *No answers yet across the club. Data appears as members practice.* |
| Thinking (chat) | Keep "Checking your numbers…" with the dots. After 8 s add: *"Still working, thanks for waiting."* |
| Toast variants | `toast--error` (rose border, `role="alert"`), `toast--success` (mint border, `role="status"`), `toast--info` (sky). "Plan updated" uses success. 6 s auto-dismiss plus an × button. |
| Sign-in errors | Inline under the password field (not a toast). Name taken / wrong password: *"That username exists and the password doesn't match. Check your password, or pick a different username to start fresh."* Short password: the native message is replaced by *"Use at least 6 characters."* |
| Network / LLM error mid-answer | Inline in chat: *"We couldn't grade that one. Your answer is still in the box."* [Try again]. Restore the textarea text (today the text is cleared before the request). |
| Rate limit | *"Easy, that was fast! Give it a second and press Submit again."* |
| Mic blocked | Keep the current copy, shown as an info toast. |

---

## 3. Mobile (390 px)
- **Nav:** a fixed bottom tab bar with 4 icons and labels (Home, Plan, Practice, Progress), 56 px tall, with a safe-area inset. The top bar keeps only the logo and the avatar. This fixes the 2-line wrapping and the hidden tabs in S08_m and S10_m.
- **Welcome:** the form comes before the steps (use `order`).
- **Home:** order is Up next → Today's tasks → stats as a 3-column compact row (keep `repeat(3,1fr)`, smaller numbers) → skills list.
- **Interview:** the session bar collapses to `Q3/8 ▮▮▯` plus a ⋯ menu (voice, hands-free, end). The composer is sticky at the bottom; the textarea is 2 rows and grows to 5; Submit is always visible. The feedback panel appears as a bottom sheet after each answer ("See feedback ▴").
- **Results:** delta rows stack: skill name and level on one line, the bar on the next, then the numbers. No 4-line label wraps.
- **Tap targets** are at least 44x44 px (the survey scale buttons are 32 px today; make them 40 px with 6 px gaps, wrapping 5+5).

---

## 4. Visual system

### 4.1 Colour tokens (pastel, light; contrast-corrected)

```css
:root{
  /* surfaces */
  --bg:#f6f4fb; --surface:#ffffff; --surface-2:#f1eef9; --line:#e4dff0;
  /* text */
  --ink:#2b2840;            /* 14.5:1 on white */
  --muted:#5f5a75;          /* was #6f6a85 (4.4:1 on surface-2) → 5.7:1 on surface-2, 6.6:1 on white */
  --subtle:#7a7590;         /* replaces #9a95b0 for placeholders/captions; ≥4.5:1 on white */
  /* brand */
  --primary:#6a56c9;        /* was #7c6ad6 (4.3:1 with white) → 5.5:1 */
  --primary-hover:#5b48b8;
  --primary-2:#a596ec; --primary-soft:#ece8fb;
  /* status (text-safe inks) */
  --ok:#237e5b;             /* was #2f9e74 (3.4:1) → 5.0:1 */
  --warn-ink:#8a5a00;       /* amber text; keep #d99a1e for fills only */
  --bad:#b83d62;            /* was #d9557a (3.9:1) → 5.3:1 */
  --info:#2a6fa6;
  /* skill pastels (fills) stay; inks corrected */
  --sky-ink:#2a6fa6; --peach-ink:#a8521f; --butter-ink:#7f5f00; --rose-ink:#b83d62;
  --mint-ink:#237e5b; --lav-ink:#5e4cc2; --lilac-ink:#7a4fc4;
  --focus:#6a56c9;
}
```
Rule: pastel colours are **only for fills**. Text and icons always use the `-ink` colours. Never use colour as the only signal; always add an icon or word.

### 4.2 Type scale (base 16 px; body is 15 px today, raise to 16 px for readability)

| Token | Size / line-height / weight | Use |
|---|---|---|
| `--fs-display` | 44/1.1/800, -0.02em (mobile 32) | Welcome H1 only |
| `--fs-h1` | 28/1.25/800 (mobile 24) | Page header H1 |
| `--fs-h2` | 20/1.3/700 | Results/debrief headline, card hero titles |
| `--fs-h3` (`.section-title`) | 16/1.4/700, ink, sentence case | **Card titles** (replaces the uppercase micro-label) |
| `--fs-body` | 16/1.55/400 | Body |
| `--fs-small` | 14/1.5/400 | Helpers, meta |
| `--fs-caption` | 12/1.4/600, uppercase, 0.06em | **Only** eyebrows/pills (e.g. "Placement complete") |

Line length: paragraphs `max-width: 65ch`. Numbers use `font-variant-numeric: tabular-nums`.

### 4.3 Spacing scale (4-pt base)
`--s-1:4px --s-2:8px --s-3:12px --s-4:16px --s-5:24px --s-6:32px --s-7:48px --s-8:64px`
- Card padding: 24 px (16 px on mobile). Gap between cards: 16 px. Gap between page sections: 32 px. Page header to first card: 24 px.
- The radius stays at 16 px for cards, 12 px for inner tiles, 10 px for inputs/buttons, 999 px for pills.

### 4.4 Layout and alignment rules
1. Three container widths only: `--w-narrow:720px` (welcome form flows, intake, results), `--w-default:1120px` (Home, Plan, Progress, How it works), `--w-wide:1280px` (Practice/interview). Everything is centered with `margin-inline:auto`.
2. **The page header's left edge equals the left edge of the first card.** No extra inset (today results/intake use 1000/860 widths while the top bar uses 1280, so headings jump around).
3. Inside a card: the title, body and lists share one left edge. Do not indent bullets past the title; use `padding-left: 1.1em` with `list-style-position: outside`.
4. Cards in the same row have equal height (`align-items: stretch`). Action buttons sit at the bottom-left of a card (`margin-top: auto`), except the page-level primary CTA, which goes top-right in the page header.
5. Paragraph text is left-aligned (never centered, except in empty states).
6. Section titles do not hold controls, except one right-aligned text link ("See all →").

### 4.5 Buttons and focus
| Variant | Style | Use |
|---|---|---|
| Primary | `--primary` bg, white, 700, 44 px tall, radius 10 | **One per screen region** (Start, Continue, Submit answer) |
| Secondary | white bg, 1.5 px `--primary-2` border, `--primary` text | See my plan, Practice {skill} |
| Ghost / tertiary | transparent, `--muted` text, underline on hover | Edit my goals, Not now, End session |
| Text link | `--primary`, 600, with an arrow → | "See all progress →" |
| Destructive confirm | `--bad` text, ghost | Sign out confirm |

Labels are verb-first, at most 24 characters, and never contain dynamic task names (task names go in the line above the button).

Focus:
```css
:where(button,a,input,select,textarea,summary,[tabindex]):focus-visible{
  outline:3px solid var(--focus); outline-offset:2px; border-radius:10px; }
input:focus,select:focus,textarea:focus{ outline:none; border-color:var(--primary); box-shadow:0 0 0 4px var(--primary-soft); }
```
Also: `.opt` tiles get `aria-pressed`, and the `.tab` buttons get `aria-current="page"`.

### 4.6 Concrete CSS fixes (selectors from `web/styles.css`)

| ID | Problem (shot) | Fix |
|---|---|---|
| **CSS-1** | Welcome steps nest, wrap one word per line and double-count (S01) | `.steps > div { display:grid; grid-template-columns:32px 1fr; gap:12px; align-items:start; … }` and `.steps > div::before { … }`. Remove the rules on `.steps div` (they match the inner `<div>`). Put the step counter on `.steps > div` only. |
| **CSS-2** | Empty "Today's plan" and empty trace wrap one word per line (S03) | JS: render `<li class="empty">`. CSS: `.today li.empty, .trace-list li.empty { display:block; background:none; padding:8px 0; color:var(--muted); }` |
| **CSS-3** | `.card-title` is uppercase 12 px muted on every card, so there is no hierarchy | Add `.section-title{font-size:16px;font-weight:700;color:var(--ink);text-transform:none;letter-spacing:0;margin:0 0 12px;display:flex;justify-content:space-between;align-items:baseline}`. Keep `.card-title` only as an eyebrow. |
| **CSS-4** | Side panel's right border is clipped by the scroll container (S05b, S10) | `.side-col { overflow-y:auto; overflow-x:hidden; padding:2px 6px 8px 2px; scrollbar-gutter:stable; } .side-col > .card{min-width:0} .rationale,.solution p{overflow-wrap:anywhere}` |
| **CSS-5** | Verdict dot is centered on a 2-line block | `.verdict{align-items:flex-start} .verdict .dot{margin-top:7px}` |
| **CSS-6** | Sparkline placeholder floats in the middle of the card (SVG text plus `preserveAspectRatio`) | Render `<p class="spark-empty">` instead of the SVG. `.spark-empty{font-size:13px;color:var(--subtle);margin:8px 0 0;text-align:left}` |
| **CSS-7** | Skill cards are uneven; Drill buttons sit at different heights (S09) | `.skill-card{display:flex;flex-direction:column} .skill-card .skill-detail{margin-top:auto;padding-top:12px}` |
| **CSS-8** | Results next-box: the long CTA wraps and the buttons stack out of line (S11) | `.next-box{flex-wrap:wrap} .next-box > div:last-child{display:flex;gap:8px;flex:none;align-items:center}` plus the short label (§2.8). |
| **CSS-9** | Plan summary card stretches with an empty area (S07) | `.plan-head{align-items:start}`; add a `.page-head` H1 to the Plan view. |
| **CSS-10** | Weak sub-skill rows are not lined up with the skill pill; a border line splits the pair | JS: `<tr class="subrow">`. CSS: `.ladder-table tr:has(+ .subrow) td{border-bottom:0} .ladder-table .subrow td{padding:0 6px 10px 18px;font-size:13px;color:var(--muted)}` |
| **CSS-11** | Club rows: the % sits higher than the bar | `.club-row{align-items:end}` |
| **CSS-12** | Results delta labels wrap to 4 lines on mobile (S11_m) | `@media(max-width:640px){.delta-row{grid-template-columns:1fr auto;row-gap:6px}.delta-row .bar{grid-column:1/-1;grid-row:2}}` |
| **CSS-13** | Tabs wrap onto 2 lines on mobile (S08_m) | `.tab{white-space:nowrap}` now; bottom tab bar per §3 later. |
| **CSS-14** | The 3 Momentum stats stack into tall boxes on mobile | Remove `.stat-row` from the `@media(max-width:640px)` one-column rule; `.stat b{font-size:18px}` on mobile. |
| **CSS-15** | Mixed container widths (860 / 1000 / 1280) | `.intake,.results{max-width:var(--w-narrow)}` (results can use `--w-default` for the 2-col notes); `main{max-width:var(--w-default)}`; `#view-interview{max-width:var(--w-wide)}` |
| **CSS-16** | Inline styles in `index.html` (`style="margin:0"`, `style="margin-top:8px"`, `style="display:flex;gap:8px"`, debrief `style="font-weight:700…"`) | Replace them with utility classes `.mt-0 .mt-2 .row-gap-2 .eyebrow`; the debrief subheads become `<h4 class="eyebrow">`. |
| **CSS-17** | Hover lift and pop animations ignore motion settings | `@media (prefers-reduced-motion: reduce){*{animation:none!important;transition:none!important}}` |
| **CSS-18** | Placeholder colour is too light | `::placeholder{color:var(--subtle);opacity:1}` |
| **CSS-19** | Plan day-card circles look like checkboxes | `.day .task .tick{width:16px;height:16px;border-width:1.5px}`; done = filled; pending = dashed `--line`; `aria-hidden`. |
| **CSS-20** | The toast only has an error style | `.toast--success{border-color:var(--ok)} .toast--info{border-color:var(--info)}` |

### 4.7 Component inventory
These are what the spec relies on:
- `page-head` (H1 + lead + optional actions)
- `section-title`
- `card` / `card--hero` (primary-soft background)
- `level-meter` (3 segments, current segment partly filled, aria-label "Basic, 41% confident")
- `chip` (status: start-here / fixed / dipped / level-up)
- `task-row`
- `tooltip` (`?`)
- `coach-mark`
- `toast` (3 variants)
- `empty-state` (title + one line + one button)
- `bottom-tabbar` (mobile)
- `details` disclosure (survey, more focus areas, behind the scenes)

---

## 5. Name

**Decided by the user: IB Ready.** Every copy line, heading and brand reference in this spec uses it.

- **Brand lock-up:** a gradient tile with an "IB" monogram (no ✓, which echoed "Tick"), then **IB Ready** (800 weight, 17 px).
- **Subtitle:** *Investment banking interview practice*.
- **Tagline** (welcome lead-in, README, slides): ***Practice IB interviews. Learn why. Get a plan.***
- **Page `<title>`:** `IB Ready · Investment banking interview practice`.
- **System speaker label in chat** (currently "Tick & Tie"): **IB Ready**.
- **Welcome first line** (an optional eyebrow above the H1): *Get IB ready, even if you're new to finance.*
- **Why it works:** "IB" plus "Ready" says what it is for and how you will feel, and a student needs no explanation. It avoids the Superday AI, BIWS, WSO and Wall Street Prep names. I have not run a trademark or domain check; do a quick web search before the demo.

Other ideas I considered (for the record only): IB Prep Coach (*Practice IB interviews. Learn why. Get a plan.*), Mock Banker (*An AI banker who interviews you, then coaches you.*), Technicals Coach (*Nail the IB technical questions, one mistake at a time.*), Banker Ready (*From "what's EBITDA?" to final round.*), First Round Coach (*Calm, honest practice for your banking interviews.*).

**Where to rename** (owner: front-end):
- `web/index.html` (`<title>`, `.brand-name`, `.brand-sub`)
- `web/app.js` (the "Tick & Tie" speaker label in `handleTurn`)
- `ticktie/prompts/coach.md` line 1
- the README and slides
- `AGENTS.md`: update its title. Its rule "UI: black + pink" contradicts the pastel direction the user asked for, so change it to "UI: pastel light theme (tokens in docs/team/ux_spec.md §4.1)". Otherwise coding agents may "fix" the palette back.

Internal package names (`ticktie/`, `TICKTIE_DATA_DIR`, `tt_` localStorage keys) can stay, so nothing breaks.

---

## 6. Hand-off checklist (definition of done for Look + feel)
- [ ] P0 rows 1–9 done, and docs/capture.py screenshots re-taken.
- [ ] A new user can go from welcome to the first placement question in under 60 s without help (test with one non-finance friend).
- [ ] The student nav shows no dollars, tokens or agents; the How it works page shows all of them.
- [ ] Every screen has one obvious primary button.
- [ ] axe/Lighthouse accessibility score ≥ 95 on Home, Practice and Results.
- [ ] At 390 px: no horizontal scroll, no word-per-line wrapping, tabs visible, Submit visible.
