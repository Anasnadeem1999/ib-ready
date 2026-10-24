---
name: add-ib-question
description: Add a new IB interview question template to IB Ready (ticktie/bank.py) with its calculator,
  misconception fingerprints and tests. Use when asked to add, extend or fix a technical question.
---

# Add an IB Ready question

## Steps
1. **Pick the slot.** Choose the topic (`SKILLS` key), level (1 Coffee-chat, 2 First-round, 3 Superday) and
   sub-skill (`SUBSKILLS`). Add the id to `META` in `ticktie/bank.py`.
2. **Write the `Template`.** It needs `gen` (random but realistic inputs), `solve` (the calculator: returns every
   label's true value), `labels` (what a full answer must state, with units and `required`), `explain` (the
   worked solution, built only from `solve`'s numbers), `key_points`, and `target_seconds`.
3. **Add the traps.** For each misconception in `ticktie/misconceptions.py` that this question can catch, a
   function returning the *wrong* numbers that mistake produces. If the mistake is new, add it to the library
   first (`id`, `skill`, `name`, `tell`, `fix`).
4. **Test it** in `tests/test_bank.py`: the true answer passes `check_numbers`, each trap is matched to its id,
   and `explain` mentions every required number. Run `python -m pytest`.

## House rules
- Never put a number in question text or explanations that the calculator did not produce.
- Paraphrase, never copy, published question banks (copyright, public repo).
- Plain words for an undergrad. US spelling. No em dashes in candidate-facing text.
- Keep the model answer concise: `engine.length_check` uses it to set the answer-length target.

## Tiny example
```python
ACC_CAPEX = Template(
    id="acc_capex", skill="accounting", difficulty=1, kind="numeric",
    title="3-statement walk: buying PP&E",
    text=lambda p: f"A company buys {money(p['X'])} of PP&E with cash. Walk me through the three statements.",
    gen=lambda r: {"X": float(r.choice([50, 100, 200, 500])), "t": r.choice(TAXES)},
    solve=lambda p: {"ni": 0.0, "cash": -p["X"], "ppe": p["X"]},
    labels=[Label("ni", "Change in net income", "$"), Label("cash", "Change in cash", "$")],
    traps={"ACC_CAPEX_EXPENSED": lambda p: [{"ni": -p["X"]}]},
    ...
)
```
