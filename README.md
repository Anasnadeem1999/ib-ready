# Tick & Tie: an IB technical interviewer that finds out *why* you got it wrong

**Live app:** _link added after deployment_
**Author:** Anas Nadeem (Yale SOM, MGT 409 AI Foundations for Managers, Fall 2026)

Tick & Tie runs mock investment banking technical interviews: accounting, EV, DCF, M&A, LBOs, and markets and rates. **Code checks every number you say.** For each question, deterministic calculators compute the right answer *and* the exact wrong answer each common misconception produces, so a mistake is matched to its cause, not guessed at by the model. Each question uses new numbers, so you can't memorise answers. A weakness map tracks your misconceptions across sessions and steers the next question at your weakest spot. You can type or speak your answers.

## Run it locally (about 3 minutes)

You need Python 3.10+ and an API key.

1. Clone the repo and enter it:
   ```bash
   git clone https://github.com/Anasnadeem1999/tick-and-tie.git
   cd tick-and-tie
   ```
2. Put your key in a `.env` file, **either in this folder or in the folder above it**. The app checks both, in that order. See `.env.example`:
   ```
   PORTKEY_API_KEY=your-key-here
   ```
3. Create a virtual environment and install:
   ```bash
   python -m venv .venv
   .venv\Scripts\activate          # Windows
   source .venv/bin/activate       # Mac / Linux
   pip install -r requirements.txt
   ```
4. Start the app:
   ```bash
   python run.py
   ```
   Your browser opens at **http://127.0.0.1:8000**. If not, open it yourself; the terminal prints the exact port.
5. Pick a name and password (it creates a private profile), choose **Diagnostic**, and answer as you would out loud. The 🎤 **Speak** button works in Chrome and Edge.

No database setup is needed: a SQLite file is created in `data/` on first run.

## How it works

| Piece | What it does |
|---|---|
| **Director** (`ticktie/engine.py`, plain code) | The boss. It picks every question from the weakness map, makes the final grading call from the calculator checks, enforces attempts, budgets and caps, and decides what the interviewer does next. |
| **Specialist diagnosticians** (Accounting, Valuation, Deals, Markets) | gpt-6-luna agents with long domain playbooks, which are cached. They read the answer, pull out every number, and call the `check_numbers` tool. |
| **`check_numbers` tool → calculators** (`ticktie/bank.py`) | Compares each number with the answer key and with every misconception's wrong-number fingerprint. It also spots pure arithmetic slips. |
| **Interviewer** | A gpt-6-luna agent that voices the next line (nudge, "why?" probe, what-if follow-up, or reveal) in an Associate or VP persona. Its output is filtered before it is shown. |
| **Coach** | Writes the end-of-session debrief from the app's own grading data. |
| **Guard** (`ticktie/guard.py`) | Input filter for injection, hidden characters and length; output filter for answer leaks, invented numbers and prompt leaks. Also budgets and rate limits. |

All agents run on **gpt-6-luna** through the course Portkey gateway. Every call checks which model actually answered, because the gateway silently swaps unknown model names.

## Tests and evaluations

```bash
python -m pytest                           # 64 offline tests: calculators, grading rules, guard, logins
python -m evals.run_eval --set holdout     # grading accuracy vs plain gpt-6-luna (uses the API)
python -m evals.redteam                    # 14 attacks through the full app (uses the API)
```
Results are in `evals/results/`.

## Repo map
```
run.py                 start the app
ticktie/               backend (FastAPI + PydanticAI)
  bank.py              question templates, calculators, misconception fingerprints
  misconceptions.py    the misconception library (names + teaching notes)
  agents.py            specialist, interviewer and coach agents
  engine.py            the director: grading rules, actions, weakness-map updates
  mastery.py           Bayesian knowledge tracing + question selection
  guard.py             safety filters
  db.py                SQLite: profiles, hashed logins, sessions, trace, feedback
  prompts/             every system prompt, one file each
web/                   front end (plain HTML/CSS/JS, no build step)
evals/                 labeled answer sets, eval runner, red-team suite, results
tests/                 offline tests
render.yaml            one-click deploy on Render
```

Built with an AI coding assistant (Claude Code), in the "building agents with agents" style of the course.
