# Tick & Tie: house rules for coding agents

- Model: **gpt-6-luna only**, through Portkey (`PORTKEY_API_KEY` from `.env` in the repo folder or the folder above). Never hardcode, print or commit keys.
- Every number shown to a candidate must come from a calculator in `ticktie/bank.py`, never from a model.
- Code decides grades (`engine._adjudicate`) and question choice (`mastery.pick_next`). Agents read and write prose only.
- Every system prompt lives in `ticktie/prompts/*.md`.
- New questions: add a `Template` with `gen`, `solve`, `traps` (misconception fingerprints) and `explain`, plus a test in `tests/test_bank.py`.
- UI: black + pink, plain HTML/CSS/JS in `web/` with no build step. It must stay usable on a phone.
- Before committing: `python -m pytest` must pass.
