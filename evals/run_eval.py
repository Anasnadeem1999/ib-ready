"""Diagnosis accuracy: IB Ready vs a cheaper IB Ready vs plain gpt-6-luna ("ChatGPT").

    python -m evals.run_eval            # all three systems
    python -m evals.run_eval --only ibready

    python -m evals.run_eval --set holdout
    python -m evals.run_eval --set behavioral   # fit answers: fairness (verdict match, unfair flags)
    python -m evals.run_eval --set industry     # group-specific technicals

Writes evals/results/<set>_eval.json and .md.

Item format: {"id", "t" (template id), "p" (params; numbers or text such as a group
name), "expect" (main misconception id, NONE or INCOMPLETE), "a" (the answer)}.
Optional, used by the behavioral set: "expect_verdict" (engine verdicts that count
as fair) and "forbid_mids" (misconception ids it would be unfair to flag).
"""

from __future__ import annotations

import argparse
import asyncio
import json
import time
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field
from pydantic_ai import Agent

from ibready import agents, bank, guard, llm
from ibready.engine import _adjudicate
from ibready.misconceptions import LIBRARY

HERE = Path(__file__).parent
OUT = HERE / "results"


# ---------------------------------------------------------------- systems
def lite_specialist(key: str) -> Agent:
    """Cost-cut variant: same tool and output, but no long domain playbook in the prompt."""
    name, skills, _ = agents.SPECIALISTS[key]
    instructions = "\n\n".join([agents._prompt("diagnostician_base.md"), agents._library_block(skills)])
    a = Agent(llm.model(), deps_type=agents.DiagDeps, output_type=agents.Diagnosis, instructions=instructions,
              name=name + " (lite)", retries=1)
    full = agents.specialist(key)
    for tool in full._function_toolset.tools.values():
        a._function_toolset.add_tool(tool)
    return a


class BaselineGrade(BaseModel):
    is_correct: bool = Field(description="True only if every number and the reasoning are right.")
    error_type: Literal["none", "arithmetic", "conceptual", "incomplete"]
    misconception_ids: list[str] = Field(default_factory=list, description="Ids from the list that the answer shows.")
    explanation: str


BASELINE_PROMPT = (
    "You are an experienced investment banker grading a candidate's answer to a technical interview question. "
    "Decide whether the answer is fully correct: right numbers and sound reasoning. If it is not, say what kind of "
    "error it is and which misconceptions from the list below it shows (use the ids exactly). Be rigorous: check "
    "the arithmetic yourself.\n\nMisconception list:\n"
    + "\n".join(f"- {m.id}: {m.name}" for m in LIBRARY.values())
)


def baseline_agent() -> Agent:
    return Agent(llm.model(), output_type=BaselineGrade, instructions=BASELINE_PROMPT, name="Baseline")


# ---------------------------------------------------------------- runners
async def run_ibready(item: dict, q: bank.Question, lite: bool, agents_cache: dict) -> dict:
    key = agents.specialist_for(q)
    ag = agents_cache.setdefault((key, lite), lite_specialist(key) if lite else agents.specialist(key))
    deps = agents.DiagDeps(question=q)
    prompt = agents.diagnosis_prompt(q, guard.wrap_untrusted(item["a"]), [], False)
    res, rec = await llm.run(ag, "eval", prompt, deps=deps)
    verdict, etype, mids, _ = _adjudicate(q, res.output, False)
    return {"pred_correct": verdict in ("correct", "correct_unexplained"), "verdict": verdict, "error_type": etype,
            "mids": mids, "rec": rec.to_dict()}


async def run_baseline(item: dict, q: bank.Question, ag: Agent) -> dict:
    prompt = f"QUESTION:\n{q.text}\n\nCANDIDATE ANSWER:\n{item['a']}"
    res, rec = await llm.run(ag, "eval", prompt)
    g: BaselineGrade = res.output
    mids = [m for m in g.misconception_ids if m in LIBRARY]
    if g.error_type == "arithmetic" and "GEN_ARITHMETIC" not in mids:
        mids.append("GEN_ARITHMETIC")
    return {"pred_correct": g.is_correct, "verdict": "correct" if g.is_correct else "incorrect",
            "error_type": g.error_type, "mids": mids, "rec": rec.to_dict()}


SETS = ["labeled", "holdout", "behavioral", "industry"]


def params_of(item: dict) -> dict:
    """Numbers become floats; text params (e.g. a coverage group's name) pass through."""
    return {k: (float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else v) for k, v in item["p"].items()}


def _ratio(a: int, b: int) -> float:
    return a / b if b else 0.0


def score(rows: list[dict]) -> dict:
    right = [r for r in rows if r["expect"] == "NONE"]
    wrong = [r for r in rows if r["expect"] != "NONE"]
    n = len(rows)
    verdict_ok = sum((r["pred_correct"] == (r["expect"] == "NONE")) for r in rows)
    caught = sum(not r["pred_correct"] for r in wrong)
    named = sum((not r["pred_correct"]) and (r["expect"] in r["mids"] or
                (r["expect"] == "INCOMPLETE" and r["verdict"] in ("incomplete", "incorrect"))) for r in wrong)
    false_alarm = sum(not r["pred_correct"] for r in right)
    tok_in = sum(r["rec"]["input_tokens"] for r in rows)
    tok_c = sum(r["rec"]["cached_tokens"] for r in rows)
    tok_o = sum(r["rec"]["output_tokens"] for r in rows)
    cost = sum(r["rec"]["cost_usd"] for r in rows)
    out = {
        "n": n, "n_correct_answers": len(right), "n_wrong_answers": len(wrong),
        "verdict_accuracy": _ratio(verdict_ok, n),
        "wrong_answers_caught": _ratio(caught, len(wrong)),
        "exact_misconception_named": _ratio(named, len(wrong)),
        "false_alarms_on_correct": _ratio(false_alarm, len(right)),
        "avg_input_tokens": _ratio(tok_in, n), "avg_cached_tokens": _ratio(tok_c, n), "avg_output_tokens": _ratio(tok_o, n),
        "cost_per_answer_usd": _ratio(cost, n), "avg_ms": _ratio(sum(r["rec"]["ms"] for r in rows), n),
    }
    # Fairness metrics (behavioral set): did the engine land on an acceptable verdict, and did it
    # flag any misconception that would be unfair for this answer?
    fair_rows = [r for r in rows if r.get("expect_verdict")]
    if fair_rows:
        out["verdict_match"] = _ratio(sum(r["verdict"] in r["expect_verdict"] for r in fair_rows), len(fair_rows))
        out["unfair_flags"] = _ratio(sum(bool(set(r["mids"]) & set(r.get("forbid_mids") or [])) for r in fair_rows),
                                     len(fair_rows))
    return out


async def main(only: list[str], args_set: str = "labeled") -> None:
    data = json.loads((HERE / f"{args_set}_answers.json").read_text(encoding="utf-8"))["items"]
    OUT.mkdir(exist_ok=True)
    sem = asyncio.Semaphore(5)
    cache: dict = {}
    base = baseline_agent()
    results: dict[str, list[dict]] = {}

    async def one(system: str, item: dict) -> dict:
        t = bank.TEMPLATES[item["t"]]
        q = bank.build(t, params_of(item))
        async with sem:
            for attempt in range(3):
                try:
                    if system == "baseline":
                        r = await run_baseline(item, q, base)
                    else:
                        r = await run_ibready(item, q, system == "ibready_lite", cache)
                    break
                except Exception as e:  # transient gateway errors: retry, then record the failure
                    if attempt == 2:
                        r = {"pred_correct": True, "verdict": "error", "error_type": str(e)[:80], "mids": [],
                             "rec": {"input_tokens": 0, "cached_tokens": 0, "output_tokens": 0, "cost_usd": 0, "ms": 0}}
                    await asyncio.sleep(2)
        extra = {k: item[k] for k in ("expect_verdict", "forbid_mids") if k in item}
        return {"id": item["id"], "t": item["t"], "expect": item["expect"], **extra, **r}

    # The lite variant drops the domain playbook; for fit and industry the playbook IS the grading logic.
    systems = only or (["ibready", "ibready_lite", "baseline"] if args_set in ("labeled", "holdout") else ["ibready", "baseline"])
    for system in systems:
        t0 = time.time()
        rows = await asyncio.gather(*(one(system, it) for it in data))
        results[system] = sorted(rows, key=lambda r: r["id"])
        s = score(results[system])
        print(f"{system:14} verdict {s['verdict_accuracy']:.0%} | caught {s['wrong_answers_caught']:.0%} | "
              f"named {s['exact_misconception_named']:.0%} | false alarms {s['false_alarms_on_correct']:.0%} | "
              f"${s['cost_per_answer_usd']:.5f}/answer | {time.time() - t0:.0f}s"
              + (f" | fair verdict {s['verdict_match']:.0%} | unfair flags {s['unfair_flags']:.0%}" if "verdict_match" in s else ""))

    prev = {}
    if (OUT / f"{args_set}_eval.json").exists() and only:
        prev = json.loads((OUT / f"{args_set}_eval.json").read_text(encoding="utf-8")).get("systems", {})
    allsys = {**prev, **{k: {"summary": score(v), "rows": v} for k, v in results.items()}}
    (OUT / f"{args_set}_eval.json").write_text(json.dumps({"run_at": time.strftime("%Y-%m-%d %H:%M"),
                                                         "systems": allsys}, indent=1), encoding="utf-8")
    fair = any("verdict_match" in v["summary"] for v in allsys.values())
    md = ["| System | Verdict accuracy | Wrong answers caught | Exact misconception named | False alarms on correct | "
          + ("Fair verdict | Unfair flags | " if fair else "") + "Tokens in (cached) / out | Cost per answer |",
          "|---|---|---|---|---|---|---|" + ("---|---|" if fair else "")]
    for k, v in allsys.items():
        s = v["summary"]
        fair_cols = (f"{s.get('verdict_match', 0):.0%} | {s.get('unfair_flags', 0):.0%} | " if fair else "")
        md.append(f"| {k} | {s['verdict_accuracy']:.0%} | {s['wrong_answers_caught']:.0%} | {s['exact_misconception_named']:.0%} | "
                  f"{s['false_alarms_on_correct']:.0%} | {fair_cols}{s['avg_input_tokens']:.0f} ({s['avg_cached_tokens']:.0f}) / {s['avg_output_tokens']:.0f} | "
                  f"${s['cost_per_answer_usd']:.5f} |")
    (OUT / f"{args_set}_eval.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print("\n".join(md))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", nargs="*", default=[])
    ap.add_argument("--set", default="labeled", choices=SETS)
    a = ap.parse_args()
    asyncio.run(main(a.only, a.set))
