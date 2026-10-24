# QA round 2, engineer D: usability, first-time user experience, visual polish

Date: Sat Oct 24 2026 · Branch: v2 · Build: the latest v2 code (server restarted after the plain-language opener change) · Server: port 8215, scratch data folder.
**No app code was changed.**

## How I tested

I did a cognitive walkthrough as three first-time personas. Each one went through the whole journey, driven by Playwright in Chromium. Answers were read from sqlite (bank.from_state), with at least 1.4 s between submits.

| Persona | Device | Intake | Placement answers | Drill |
|---|---|---|---|---|
| **P1 Maya**, sophomore who doesn't know EV or DCF | 1440x900. Every screen was also re-shot at 390x844. | Not sure yet, Networking, 60 days, Associate | 9: 3 right, 3 wrong, 3 "I don't know" | Fit & behavioral, 16 answers |
| **P2 Raj**, MBA career switcher | **Mobile 390x844 for the whole journey** (is_mobile, touch) | TMT, First rounds, 21 days, VP | 12: mostly right, some wrong, 1 "I don't know" | EV & valuation, 14 answers |
| **P3 Lee**, stressed senior with a Superday in 3 days | 1440x900 | Not sure yet, Superdays, 3 days, MD | 14: two-thirds right | Fit, 17 answers. Network outage simulated mid-drill. |
| **E Kim**, empty and error states | 1440 and 390 | defaults | 0 (ended at once) | API blocked (server unreachable) |

I also tested these separately: keyboard-only sign-in, a returning user with the wrong password, and focus order. On every screen an automated check measured: number of clickable controls, horizontal overflow, elements running off the right edge, clipped text, one-word-per-line wrapping, WCAG contrast of every text node, and banned or old jargon (Intermediate/Advanced/Basic/Foundations/mastery/misconception/Practise/sub-skill/token).

- Total API spend was about **$0.03** (135 LLM calls, $0.021 logged, plus an aborted first pass).
- Screenshots are in `C:/Users/ANAS/AppData/Local/Temp/claude/C--Users-ANAS-Desktop-Prob-and-Stat/a0cf80a0-8ce1-4782-89ed-7d7490e63cc7/scratchpad/qa2d/shots/`, named `{persona}_{NN}_{screen}_{d|m}.png`. In P2 the `_d` files are actually mobile, because the whole run was mobile.
- Raw audit JSON is `p1_audit.json`, `p2_audit.json`, `p3_audit.json`, `empty_audit.json`, `checks.json` and `p*_box.json`, in the `qa2d/` folder.
- Note: full-page screenshots show the sticky header and bottom tab bar part-way down the page. That is a capture artifact, not a bug.

## Owner feedback verification

| # | Verdict | Evidence |
|---|---|---|
| **U-01** Answer box clears | **Fixed.** I checked 82 submits across 3 personas: typed answers, "I don't know", and first and second attempts. The box was `""` straight after submit and `""` after the reply, every time. When the network fails, the draft is deliberately put back with the message "Your answer is still in the box". That is correct. | `p1_box.json`, `p2_box.json`, `p3_box.json`, `p3_17_network_error_d.png` |
| **U-02** Plain level names | **Fixed in the UI.** Getting started, Coffee-chat ready, First-round ready and Superday ready appear on results, home, plan, progress and the journey stepper. "Intermediate", "Advanced" and "Basic" appear nowhere. Leftovers: "mastery" (How it works, drill results), "misconception" (How it works), "superday level" in lowercase in the plan, and How it works says "three levels" next to a 4-step ladder (D-17). | audit `jargon` field |
| **U-03** Coherent, few buttons | **Mostly fixed.** The nav is Home · My plan · Practice · Progress. Every main screen has one primary button. Still not coherent: the coach's "next step" sentence contradicts the task card under it (D-01). How it works has 63–78 controls and a 6,600 px trace that is open by default (D-05). Intake has 33 controls (D-11). | see the table below |
| Text alignment / welcome cards | **Fixed.** No skinny wrapping, no overflow, no clipping on any screen at 1440 or 390. | audit `skinny`/`offRight`/`clipped` are empty |
| Finance Club moved | **Fixed.** It now lives under How it works → For finance clubs. | `p1_20_how_it_works_d.png` |

## Summary of issues

P0 = a first-time user gets stuck or misled · P1 = confusing or unpolished in a way a grader will notice · P2 = polish

| ID | Sev | Screen | Issue | Suggested fix |
|---|---|---|---|---|
| D-01 | **P1** | Results: "Your first step" / "Your next step" (all personas) | The coach's sentence talks about a different topic than the task card under it, and it uses the internal word "diagnostic". P1: *"For your next diagnostic, focus on behavioral answers … and a short CAPM calculation walkthrough"* above **Fit & behavioral practice**. P3: *"focus on stock compensation mechanics, rate sensitivity…"* above **Fit & behavioral practice**. After a drill: *"In your next networking drill, focus on fit questions"* above **DCF & WACC practice**. The one obvious next step contradicts itself. | Tie the sentence to the task shown. Either generate it from `next.task` (`"Next: {taskTitle}. {one line on why}"`), or drop the LLM sentence when its skill ≠ the task's skill. Add to the coach prompt: "Never say 'diagnostic', 'drill' or 'session'. Say 'your next practice'." Post-filter: `.replace(/\bdiagnostic\b/gi, "practice")`. |
| D-02 | **P1** | Mobile interview (P2) | After each answer the mobile verdict chip is scrolled into view with `setTimeout(..., 0)`. That runs **after** `addQuestion()` has scrolled to the new question, so the new question ends up hidden under the composer. The student sees "Correct ✓" and an empty box that says "Attempt 1 of 2", but no question. | In `renderDiag`, skip the delayed scroll when a next question follows. Or in `handleTurn`, after `addQuestion`, run `setTimeout(() => qEl.scrollIntoView({block:"start"}), 50)`. |
| D-03 | **P1** | Mobile placement and drill results | The "Your first step" card with the **Start** button comes after the journey, every topic and the full coach notes, about 2,000 px down (`p2_09_placement_results_d.png`). The one next step is below 3 screens of reading. | On ≤768 px put `#res-next` straight after the header: `@media (max-width:768px){ #view-results .res-grid{display:flex;flex-direction:column} #res-next{order:-1} }`. Or add a sticky bottom CTA "Start first practice". |
| D-04 | **P1** | Placement start (desktop) | When the first question loads the page is scrolled 52 px (`scrollY=52`). The session bar's top sits at y=40, under the 64 px sticky header, so the "Placement interview" pill and "Topic 1 of 6" are cut off (`p1_05_placement_start_d.png`). | Leave enough room above the session bar when scrolling: `.session-bar{scroll-margin-top:76px}` and `.msg,.qcard{scroll-margin-top:140px}`. Or make the session bar `position:sticky; top:64px`. |
| D-05 | **P1** | How it works | 63 controls on desktop and 78 on mobile. The page is 6,630 px tall because **"Latest session, step by step" is open by default** (`#trace-wrap.open === true`): about 80 rows of "Director / Interviewer / details". The student came for "how levels work". Also visible: raw `cached_input` in the pricing line, "75%+ mastery", "(or misconception)", and "you'll practise". | `#trace-wrap` closed by default (remove `open`). Pricing copy: "per million tokens: input $0.10 · cached input $0.01 · output $0.50". Replace "(75%+ mastery)" with "(about 3 in 4 right)". Delete "(or misconception)". Change "practise" to "practice". |
| D-06 | **P1** | Placement: welcome vs session bar | The welcome step says *"A 15-minute placement interview across **7 topics**"*. The session bar says *"Topic 1 of **6**"* for generalists (7 only once a coverage group is picked). | Welcome copy: "across 6–7 topics". Or "**covering the core IB topics**". |
| D-07 | **P1** | Drill results (all) | The header says "**Good work. Here's what changed.**" while "What changed" shows *Confidence 15% → 15%* (P1, mostly wrong answers). It isn't honest and the two messages contradict each other. The kind pill says "**15 questions**", but the session bar counted "Question x of 8", because second attempts and follow-ups are counted as questions. | Choose the title from the data. If no level or confidence went up: "Session complete. Here's what to work on next." Use "Good work" only when at least one topic improved. Count questions with `done_q`, not turns: "8 questions · 15 answers". |
| D-08 | **P1** | Practice: Fit drill | The question card titled **"Why this group"** asks "Why do you want to work in investment banking?". The next card is **"Why investment banking"** asking "Why investment banking?", so the same question is asked twice. The follow-up asks "what draws you to **this group**" of a student who chose "Not sure yet". | Fix the `b_why_group` text in the bank, or its title. For generalists, phrase it "Why banking, and what kind of team interests you?". Don't serve `b_why_ib` in the same session after `b_why_group`. |
| D-09 | **P1** | Error state (server unreachable) | The toast says just "**Failed to fetch**", the raw browser error (`e_05_api_down_practice_d.png`). The interview's inline error is kind, but it also shows "(Failed to fetch)". | In `api()`, map `TypeError` to: "We can't reach IB Ready right now. Check your connection and try again. Nothing you've done is lost." Use the same wording in the interview error, without the raw text. |
| D-10 | **P1** | Coach notes / results / plan for P1 (sophomore) | Jargon with no explanation reaches the newcomer: "CAPM", "1.75x MOIC", "treasury stock method", "Paper LBO", "Returns math (MOIC, IRR)", "$500mm", "D&A, SBC". The "?" chips cover topic names only, not these terms. The opener also lists "DCF, M&A, LBOs" before the student knows them. | Add to the coach prompt: "If the student's stage is networking or overall level ≤ 1, write for someone new to finance: spell out every acronym on first use, e.g. 'CAPM (the formula for the return shareholders expect)'." Add glossary entries for MOIC, IRR, CAPM, D&A, SBC and mm, and auto-link known glossary terms in coach notes with `tip()`. |
| D-11 | P2 | Intake | 33 controls. The 16 team tiles have no subtitles, so a sophomore can't tell FIG, DCM, ECM, "Financial Sponsors" or "REITs" apart. "Not sure yet" is pre-selected, which helps. | Collapse both team groups behind `<details><summary>I know which team I want</summary>` when "Not sure yet" is selected. Add a 3-word subtitle per tile, e.g. FIG "Banks & insurers", Financial Sponsors "Private-equity clients", LevFin/DCM "Raising debt", ECM "IPOs & stock sales". |
| D-12 | P2 | Interview: speaker label | The interviewer is labelled "**ASSOCIATE (FIRST ROUND)**" for a student who chose *Networking / coffee chats*. | Label with the persona only ("Associate"), or with the stage the student picked. |
| D-13 | P2 | Fit drill opener | "Let's practice Fit & behavioral … together. 8 quick questions… **Hi, thanks for making time.** We'll keep this conversational, **with a few technicals**". The greeting comes after the briefing, and a Fit drill has no technicals. | Order: greeting, then briefing. Leave out "with a few technicals" when focus = fit. |
| D-14 | P2 | Practice (all modes after placement) | "I don't know this one" exists only in placement. A sophomore in a drill who doesn't know has to make up a wrong answer twice before the model answer appears. | Show `#idk-btn` in drills too, labelled "Show me how", which submits "I don't know" and reveals the worked answer. |
| D-15 | P2 | Results | Two summaries say the same thing: the callout under the H1 and the coach-notes headline (`p1_09`, `p3_09`). "Strongest" goes on every topic at the top level, e.g. 4 topics for P3 and 3 for P1, so it stops meaning anything. | Drop the callout when coach notes exist. Award "Strongest" only to the single highest topic, and only if it's above the overall level. |
| D-16 | P2 | Overall level | The overall milestone looks inconsistent. P2: 3 topics First-round and 3 Getting started gives "Coffee-chat ready". P3: 4 First-round and 2 Coffee-chat gives "First-round ready". Nothing says how "overall" is worked out. | Add one line under "You are here": "Your overall milestone is where most of your topics are." (or whatever the rule is). |
| D-17 | P2 | How it works: milestones | "Every topic has **three levels**", but the ladder shows 4 (Getting started + 3). | "Every topic moves through three milestones after Getting started: …" |
| D-18 | P2 | Plan | "Week of Dec 21 · **1 tasks**". The stat tile "13.2h of practice on the calendar, plus about 2h of review (51.4h available)" wraps to 5 lines. Only the first "Today" task has a Start button. "superday level" is lowercase. For P3 the plan says "3 practice days · 1 rest day a week" with no rest day, and LBO shows Goal Superday with **0** practices. The task circles still look like checkboxes. | Pluralise. Tile: "**13h** planned practice" with the review and available hours in the tooltip. Give every Today task a Start button, or none (one primary at the top). Capitalise "Superday". Hide "1 rest day a week" when days < 7. Show "—" for 0 practices with a tooltip "no time before your interview; review the mistake card instead". Replace `○` with a number or a ✓ only once done. |
| D-19 | P2 | Home | The coach-mark arrow for "This is always your next step. Just press **Start**" points at the bottom-left of the card, not at Start (right). It also covers the journey stepper. "That's everything planned for today" reads oddly when nothing is done. | Anchor the coach mark to `#upnext .primary`. Copy: "This is your only task today." / "Then: M&A practice." |
| D-20 | P2 | Progress | Each topic card has two progress visuals: the level meter and a flat sparkline that looks like an empty bar. Confidence and level disagree visually (EV "Getting started" 42% vs Accounting "Coffee chat" 27%). "seen 16×" on a mistake pattern after one session feels punishing. The pill and the title sit on one line in one card and stack in the others. | Hide the sparkline until there are 3 or more data points. Tooltip: "Confidence is how sure we are at your current milestone." Show "seen often" when more than 5. Always stack pill and title (`.mis-card .pill{display:block}`). |
| D-21 | P2 | Empty plan | The heading and body repeat each other ("Your plan appears after your placement interview." twice). It says "practise". The button just says "**Start**". The paused-placement page shows "Behind the scenes" and "Help us improve" with 0 answers. | Body: "It counts back from your interview date and fits the hours you have, so you only practice what moves the needle." Button: "Start placement interview". Hide the survey and Behind the scenes when n = 0. |
| D-22 | P2 | End session | A native `confirm()` dialog says "We'll update your skills…" even when 0 questions were answered. | Use an in-app modal. For placement with 0 answers: "Leave the placement? You can restart it any time." |
| D-23 | P2 | Contrast | Green chips "Strongest" / "Fixed ✓" are 4.40:1 (`#237e5b` on `#e2f5ec`). The "Calculator" actor label in How it works is 4.36:1. Both are small text, so they fail AA (4.5). Everything else passes (the "IB" logo flag is a gradient false positive). | `--ok-ink: #1d6b4c` (about 5.6:1 on `#e2f5ec`). |
| D-24 | P2 | Keyboard | The whole journey works from the keyboard: Tab, Enter submits, `:focus-visible` rings on buttons and links, box-shadow focus on inputs. But on the welcome page the order is Username → Password → Continue → *Skip to content* → logo → How it works, because the skip link comes after the form. | Make the skip link the first focusable element in the DOM (before the header). |
| D-25 | P2 | Mobile results | "Technology, Media & Telecom specifics" wraps to 4 lines next to its "?". The mobile "See feedback ▴" button has about 30 px of empty space above it inside the verdict chip. | Topic label "TMT specifics" (full name in the tooltip). `.msg.ai.v-* .verdict{margin-bottom:0}`, `.msg.ai.v-* .small-btn{margin-top:6px}`. |

No P0s: no persona ever got stuck, and no screen misled them about whether an answer was right. The grader was honest. For example, P1 pasted the model "framework" as a fit answer and was told kindly that it was advice rather than an answer.

## Clickable controls per screen (desktop / mobile)

The counts include the ~8 nav controls and every "?" chip.

| Screen | Desktop | Mobile | Flag |
|---|---|---|---|
| Welcome / sign-in | 6 | 6 | ✓ excellent |
| Intake | 33 | 33 | ⚠ too many (D-11) |
| Placement turn | 18–21 | 11–14 | ok |
| Placement results | 37 | 37–38 | ⚠ heavy, mostly "?" chips + Behind the scenes + survey |
| My plan | 19–27 | 22 | ok |
| Home | 21 | 22 | ok |
| Practice launcher | 20 | 20 | ok (the extras sit in a collapsed "Practice something else") |
| Drill turn | 17–23 | 10–16 | ok |
| Drill results | 40 | 40 | ⚠ heavy |
| Progress | 31 | 34 | ok for a detail page |
| How it works | **63** | **78** | ✗ too many (D-05) |

## Notes per screen

**Welcome.** Clear from the first glance. All personas know what it is ("Practice investment banking interviews…") and what to do (one form, one "Continue"). "New here? Pick any username and password" removes the sign-up worry. The short-password error shows inline in red under the field. The wrong-password error is inline and kind ("That username and password don't match. Check your password, or pick a different username to start fresh."). Small tone point: "learn why you got each one wrong" assumes failure. "…and learn *why* behind every answer" would be kinder (optional).

**Intake.** The heading, "5 quick questions" and the numbered questions make the purpose obvious, and the next step ("Start my 15-minute placement interview") is unmistakable. The helper "It's a check, not a test" is good for P3. P1 is lost in the 16 team tiles (D-11). "Judgement" is UK spelling; use "Judgment".

**Placement.** The intro card "This is a check, not a test" sets the tone. "I don't know this one" is visible and works, and placement feedback is just "Not quite yet · Noted". The timer "0:00 / 1:30" plus "aim for 1:30" is mild pressure; acceptable. Problems: D-04 (clipped bar), D-06 (6 vs 7), D-12 (label). On mobile the composer takes about 30% of the screen, which is acceptable.

**Placement results.** The title is plain and kind ("You're coffee-chat ready. Nice foundation." / "You're first-round ready. Strong start."). The journey stepper and "You are here / Next milestone" explain the levels well, which addresses U-02. Problems: D-01, D-03, D-10, D-15. On desktop the topic rows have a 700 px gap between the name and the meter; capping `.placement-row` at 720 px would tidy it.

**My plan.** "Your plan to First-round ready" and the Today card answer "what do I do today?". P3 gets a "Time is tight" banner, which suits a stressed senior. "Why this plan" is one dense paragraph of sub-skill names (D-10, D-18).

**Home.** The best screen: greeting, days to interview, one Up Next hero with Start, the journey and topics. The coach mark is helpful, but its arrow is in the wrong place (D-19).

**Practice launcher.** Ideal: one hero (Next in your plan → Start), with everything else folded away.

**Drill.** The verdict, "Details unlock after your next try", the mistake pattern card and the model answer are clear. "Attempt 2 of 2" is explicit. Voice menu: two plain checkboxes ("Read questions aloud", "Hands-free mode ?"). It's clear, but the "Voice ▾" button popover overlaps the chat; fine. Problems: D-02 (mobile), D-08, D-13, D-14.

**Drill results.** "What changed", with only the touched topic and "Show all topics", is a good reduction. Problems: D-07 and D-01.

**Progress.** Clear legend (Needs work / Solid / Not tried yet). "Practice this topic →" on each card. The mistake patterns quote the student's own words, which makes the feedback feel personal. Problems: D-20.

**How it works.** The "New to IB? Start here" primer and the "How your answers are checked" 5-step strip are excellent for P1 and graders. The page is buried under the expanded trace (D-05).

**Profile menu.** Three clear items: Edit my goals / How it works / Sign out (red).

**Empty and error states.** Before intake the tabs are hidden (correct). With 0 answers you get "Let's finish your placement next time" and a single "Restart placement interview", which is good. Empty plan and progress pages explain themselves and offer Start (D-21). Network failure in the interview is kind and keeps the draft. Global API failure gives a raw toast (D-09).

**Mobile 390x844.** No horizontal overflow on any screen. The bottom tab bar has icons and labels, and the composer buttons are full width. Problems: D-02, D-03, D-25.

## Would a confused undergrad succeed?

- **P1 Maya (sophomore, no finance): Yes, with friction.** She signs in, picks "Not sure yet", finishes placement using "I don't know", and the Start buttons always point her somewhere. Where she stumbles: acronyms in the coach notes (CAPM, MOIC), a "first step" sentence that talks about CAPM above a Fit task, and a drill that asks "why banking" twice. Shots: `p1_01_welcome_d.png`, `p1_04_intake_filled_d.png`, `p1_08_placement_turn2_idk_m.png`, `p1_09_placement_results_d.png`, `p1_11_home_d.png`, `p1_15_drill_wrong_feedback_d.png`, `p1_18_drill_results_d.png`.
- **P2 Raj (MBA, mobile): Yes.** The flow is smooth and the language suits him. On mobile he twice loses the new question under the composer (D-02) and has to scroll 3 screens to find "Start" on results (D-03). Shots: `p2_09_placement_results_d.png`, `p2_11_home_d.png`, `p2_15_drill_wrong_feedback_d.png`, `p2_16_drill_right_feedback_d.png` (all 390 wide).
- **P3 Lee (Superday in 3 days): Yes.** He gets a compressed 3-day plan with a "Time is tight" note, an honest "first-round ready", and a kind recovery when the network fails. He would be annoyed by "Good work" after a flat session (D-07) and the mismatched next-step sentence (D-01). Shots: `p3_09_placement_results_d.png`, `p3_10_plan_d.png`, `p3_17_network_error_d.png`, `p3_19_drill_results_d.png`.

Empty and error shots: `e_01_ended_placement_0answers_d.png`, `e_03_empty_plan_m.png`, `e_05_api_down_practice_d.png`, `x_wrong_password_d.png`.
