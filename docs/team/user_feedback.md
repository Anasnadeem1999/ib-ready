# Feedback from Anas (pilot user), logged 2026-10-24

Source: Anas using the v1 instance at http://127.0.0.1:8000. Every item must be verified fixed in v2 by QA before release.

| # | Area | Feedback | Likely cause / note | Owner |
|---|---|---|---|---|
| U-01 | Interview: answer box | After submitting, the answer stays in the answer box, and it's still there for the next question. Expected: once submitted, the box clears, and the answer appears only as the submitted message the diagnosis is based on. | v1 clears the textarea on submit, but speech recognition can write the transcript back into the box after the clear (an `onresult`/`onend` restart after stopMic). It may also come from the browser restoring the textarea. Fix: clear the box, abort recognition (`abort()`, not `stop()`), ignore late results with a per-turn token, and set `autocomplete="off"`. | Front end + QA |
| U-02 | Dashboard: levels | "Intermediate / Advanced" is not intuitive for an undergrad who doesn't know banking. | Levels need plain-language meaning, e.g. "Coffee-chat ready → First-round ready → Superday ready", with a one-line explanation and what to do next. | UX + front end + content |
| U-03 | Overall UI coherence | Not intuitive for a random user: too many buttons, things don't feel coherent, some elements don't make sense. Needs to be to the point. | Cut the screens down: one clear primary action per screen, fewer controls, consistent wording, and progressive disclosure for advanced options. | UX + front end; QA "first-time user" test |
| U-04 | Bar | Anas needs 100/100. Every rubric row must be defensible with evidence. | — | Me (final review) |

Earlier feedback, already in progress:
- **Name:** "IB Ready" was unclear, so the app is now **IB Ready**.
- **"Finance Club" tab:** confusing, so it moves to "How it works → For finance clubs".
- **Text alignment:** paragraphs were misaligned.
- **Audience:** the app must make sense to a university student who doesn't know banking.
- **Debrief tone:** nurturing and stress-aware, but never calling a wrong answer right.
