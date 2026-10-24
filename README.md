# IB Ready: an IB interview coach that finds out *why* you got it wrong

**Run it:** locally from a fresh clone in about 3 minutes (below). No hosted copy; `render.yaml` is a ready one-click Render blueprint.

**Report and slides (open in any browser):** [report](https://anasnadeem1999.github.io/ib-ready/report.html) · [slides](https://anasnadeem1999.github.io/ib-ready/slides.html). The same self-contained files are in `docs/` (download and double-click; GitHub's file view shows HTML as code).

**Author:** Anas Nadeem (Yale SOM, MGT 409 AI Foundations for Managers, Fall 2026)

IB Ready (code name and package: `ticktie`, "Tick & Tie") runs mock investment banking interviews: accounting, EV, DCF, M&A, LBOs, group specifics and fit. **Code checks every number you say.** For each question, deterministic calculators compute the right answer *and* the exact wrong answer each common misconception produces, so a mistake is matched to its cause, not guessed at by the model. Each question uses new numbers, so you can't memorise answers. A short placement interview sets your level per skill, the app builds a dated action plan up to your interview, a weakness map steers every drill at your weakest spot, and every technical answer is checked for length so you learn to answer concisely. You can type or speak your answers.

## Run it locally (about 5 minutes)

You need Python 3.10+ (3.12 recommended) and an API key.

1. Clone the repo and enter it:
   ```bash
   git clone https://github.com/Anasnadeem1999/ib-ready.git
   cd ib-ready
   ```
2. The key: put `PORTKEY_API_KEY=your-key-here` in a `.env` file **in this folder or in the folder above it**. The app checks both; the first non-empty value wins, so an empty `.env` copied from `.env.example` here does no harm.
3. Create a virtual environment and install. No activation needed (this avoids PowerShell's execution-policy error):
   ```bash
   # Windows
   python -m venv .venv
   .venv\Scripts\python -m pip install -r requirements.txt
   # Mac / Linux
   python3 -m venv .venv
   .venv/bin/python -m pip install -r requirements.txt
   ```
4. Start the app:
   ```bash
   .venv\Scripts\python run.py      # Windows
   .venv/bin/python run.py           # Mac / Linux
   ```
   Your browser opens on the **first free port from 8000** (8000, 8001, ...); the terminal prints the exact link. Options: `--no-browser`, or set `PORT=8123`.
5. Pick a name and password (it creates a private profile), fill in your group and interview date, take the **placement interview**, and answer as you would out loud. The 🎤 **Speak** button works in Chrome and Edge.

No database setup is needed: a SQLite file is created in `data/` on first run (set `TICKTIE_DATA_DIR` to put it elsewhere; avoid OneDrive-synced folders). Without a key the app still starts and shows a warning; grading needs the key. The product name lives in one place: `APP_NAME` in `ticktie/config.py` (or the `APP_NAME` environment variable).

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
python -m pytest                           # 500 offline tests (no API calls): calculators, grading, plan, guard, logins, full API flow
python -m evals.run_eval --set holdout     # grading accuracy vs plain gpt-6-luna (uses the API)
python -m evals.redteam                    # 14 attacks through the full app (uses the API)
```
Results are in `evals/results/`.

## Use it from any AI agent (MCP server, optional)

`mcp_server.py` exposes the calculators and the mistake library as an MCP server, so Claude Code, Codex, Cursor or Claude Desktop can run IB Ready drills. The tools are `list_topics`, `get_practice_question`, `check_answer` and `explain_mistake`. It also exposes the resource `ibready://mistakes` and the prompt `mock_interview`. It makes no model calls and costs $0, and the answer key stays on the server unless the caller asks for a reveal.

```bash
.venv\Scripts\python -m pip install -r requirements-mcp.txt     # Mac/Linux: .venv/bin/python ...
```
Add it to your agent's MCP config (e.g. `.mcp.json`), using absolute paths:
```json
{"mcpServers": {"ib-ready": {"command": "<repo>/.venv/Scripts/python", "args": ["<repo>/mcp_server.py"]}}}
```

The repo also has a coding-agent playbook for adding questions, in `.codex/skills/add-ib-question/SKILL.md`, and house rules for coding agents, in `AGENTS.md`.

## Repo map
```
run.py                 start the app
mcp_server.py          the same calculators as an MCP server (optional)
ticktie/               backend (FastAPI + PydanticAI)
  bank.py              question templates, calculators, misconception fingerprints
  misconceptions.py    the misconception library (names + teaching notes)
  agents.py            specialist, interviewer and coach agents
  engine.py            the director: grading rules, actions, weakness-map updates
  mastery.py           Bayesian knowledge tracing + question selection
  plan.py              the dated action plan (computed, never by a model)
  guard.py             safety filters
  db.py                SQLite: profiles, hashed logins, sessions, trace, feedback
  prompts/             every system prompt, one file each
web/                   front end (plain HTML/CSS/JS, no build step)
evals/                 labeled answer sets, eval runner, red-team suite, results
tests/                 offline tests (conftest.py stubs the model, so they need no key or network)
render.yaml            one-click deploy on Render (branch main, 1 GB disk at /var/data)
```

Built with an AI coding assistant (Claude Code), in the "building agents with agents" style of the course.
