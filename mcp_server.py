"""IB Ready as an MCP server: the calculators and the mistake library, for any AI agent.

    pip install -r requirements-mcp.txt
    python mcp_server.py            # stdio transport (Claude Code, Claude Desktop, Codex, Cursor)

This exposes the deterministic half of the app: question generation, number checking against the
answer key and every misconception fingerprint, and the mistake library. Nothing here calls a model,
so it costs $0 per call, and no answer key leaves the server unless the caller asks for a reveal.
The web app's specialist agents call the same `bank.check_numbers` through their `check_numbers` tool:
one set of functions, two ways in (Lecture 9).
"""

from __future__ import annotations

import base64
import json
import random

from ibready import bank
from ibready.misconceptions import LIBRARY

try:
    from fastmcp import FastMCP
except ImportError:  # the web app does not need fastmcp; only this server does
    FastMCP = None


def _encode(q: bank.Question) -> str:
    raw = json.dumps({"t": q.template_id, "p": q.params}, separators=(",", ":"))
    return base64.urlsafe_b64encode(raw.encode()).decode()


def _decode(question_id: str) -> bank.Question:
    try:
        d = json.loads(base64.urlsafe_b64decode(question_id.encode()))
        return bank.build(bank.TEMPLATES[d["t"]], d["p"])
    except Exception as e:  # noqa: BLE001
        raise ValueError("Unknown question_id. Get one from get_practice_question.") from e


def list_topics() -> dict:
    """The topics (skills), the three levels, and how many question templates each topic has."""
    counts: dict[str, int] = {}
    for t in bank.TEMPLATES.values():
        counts[t.skill] = counts.get(t.skill, 0) + 1
    return {"topics": [{"key": k, "name": v, "templates": counts.get(k, 0)} for k, v in bank.SKILLS.items()],
            "levels": {str(k): v for k, v in bank.LEVELS.items()}}


def get_practice_question(topic: str, level: int | None = None, seed: int | None = None) -> dict:
    """A fresh IB interview question with new numbers. Returns the question text, the numbers a full
    answer must state (labels), and a question_id to pass to check_answer. Never returns the answer.

    topic: a topic key from list_topics (e.g. "accounting", "ev", "dcf", "ma", "lbo").
    level: 1 Coffee-chat ready, 2 First-round ready, 3 Superday ready (optional).
    """
    pool = [t for t in bank.TEMPLATES.values() if t.skill == topic and t.kind == "numeric"
            and (level is None or t.difficulty == level)]
    if not pool:
        raise ValueError(f"No numeric questions for topic={topic!r} level={level!r}. See list_topics.")
    rng = random.Random(seed)
    t = rng.choice(sorted(pool, key=lambda x: x.id))
    q = bank.build(t, t.gen(rng))
    return {"question_id": _encode(q), "title": q.title, "text": q.text, "level": bank.LEVELS.get(q.difficulty),
            "labels": [{"key": l.key, "name": l.name, "unit": l.unit, "required": l.required} for l in q.labels],
            "target_seconds": q.target_seconds}


def check_answer(question_id: str, numbers: dict[str, float], reveal: bool = False) -> dict:
    """Check the candidate's numbers with the calculator. numbers maps label keys to signed values
    (decreases negative, percents as 25 for 25%). Each line comes back correct, wrong or missing, with
    the misconception whose fingerprint matches a wrong number. Set reveal=True to include the answer key.
    """
    q = _decode(question_id)
    checks = bank.check_numbers(q, {k: float(v) for k, v in numbers.items()})
    lines = []
    for c in checks:
        line = {"label": c.label, "name": c.name, "you": c.stated, "status": c.status,
                "arithmetic_slip": c.slip, "sign_flip": c.sign_flip,
                "misconceptions": [{"id": m, "name": LIBRARY[m].name} for m in c.matches if m in LIBRARY]}
        if reveal:
            line["answer"] = c.expected
        lines.append(line)
    required = [c for c, l in zip(checks, q.labels) if l.required]
    out = {"all_required_right": all(c.status == "correct" for c in required), "lines": lines}
    if reveal:
        out["worked_solution"] = q.solution
    return out


def explain_mistake(misconception_id: str) -> dict:
    """What a named mistake pattern sounds like and how to fix it."""
    m = LIBRARY.get(misconception_id)
    if m is None:
        raise ValueError("Unknown misconception id. Read the ibready://mistakes resource for the list.")
    return {"id": m.id, "topic": m.skill, "name": m.name, "sounds_like": m.tell, "fix": m.fix}


def mistakes_markdown() -> str:
    return "# IB Ready mistake library\n\n" + "\n".join(
        f"- **{m.id}** ({m.skill}): {m.name}. Sounds like: \"{m.tell}\"" for m in LIBRARY.values())


def mock_interview_prompt(topic: str = "accounting") -> str:
    return (f"Run a short {topic} mock interview. Call get_practice_question, ask it, wait for my answer, "
            "pull every number I commit to and call check_answer. Grade only from its result: never call a "
            "number right that the tool marks wrong. Name any matched mistake with explain_mistake, then ask "
            "the next question. Reveal the answer only after my second try.")


if FastMCP is not None:
    mcp = FastMCP("ib-ready")
    mcp.tool(list_topics)
    mcp.tool(get_practice_question)
    mcp.tool(check_answer)
    mcp.tool(explain_mistake)
    mcp.resource("ibready://mistakes")(mistakes_markdown)
    mcp.prompt(name="mock_interview")(mock_interview_prompt)


if __name__ == "__main__":
    if FastMCP is None:
        raise SystemExit("Install the MCP extra first: pip install -r requirements-mcp.txt")
    mcp.run()
