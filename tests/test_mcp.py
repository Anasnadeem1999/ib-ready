"""The MCP server's tools: no model calls, no answer key unless revealed, and grading matches the calculators."""

import asyncio

import pytest

import mcp_server as srv
from ticktie import bank


def test_question_hides_the_answer_and_check_is_exact():
    q = srv.get_practice_question("accounting", seed=7)
    assert set(q) == {"question_id", "title", "text", "level", "labels", "target_seconds"}  # no answer key
    real = srv._decode(q["question_id"])
    right = {k: v for k, v in real.values.items()}
    res = srv.check_answer(q["question_id"], right)
    assert res["all_required_right"] and all("answer" not in l for l in res["lines"])
    wrong = {k: v + 1000 for k, v in right.items()}
    res = srv.check_answer(q["question_id"], wrong, reveal=True)
    assert not res["all_required_right"] and res["worked_solution"] and "answer" in res["lines"][0]


def test_misconception_fingerprint_is_named():
    for seed in range(40):
        q = srv.get_practice_question("accounting", seed=seed)
        real = srv._decode(q["question_id"])
        if real.signatures:
            mid, sigs = next(iter(real.signatures.items()))
            res = srv.check_answer(q["question_id"], {**real.values, **sigs[0]})
            assert mid in {m["id"] for l in res["lines"] for m in l["misconceptions"]} or any(
                l["sign_flip"] or l["arithmetic_slip"] for l in res["lines"])
            return
    pytest.skip("no accounting template with a fingerprint")


def test_bad_inputs_are_clear_errors():
    with pytest.raises(ValueError):
        srv.get_practice_question("astrology")
    with pytest.raises(ValueError):
        srv.check_answer("not-a-question", {})
    with pytest.raises(ValueError):
        srv.explain_mistake("NOPE")
    assert srv.list_topics()["topics"] and "ACC_NO_TAX" in srv.mistakes_markdown()


def test_served_over_mcp():
    fastmcp = pytest.importorskip("fastmcp")

    async def go():
        async with fastmcp.Client(srv.mcp) as c:
            names = {t.name for t in await c.list_tools()}
            assert {"list_topics", "get_practice_question", "check_answer", "explain_mistake"} <= names
            r = await c.call_tool("get_practice_question", {"topic": "ev", "seed": 1})
            assert "question_id" in (r.data if r.data is not None else r.structured_content)
            res = await c.read_resource("ibready://mistakes")
            assert "mistake library" in res[0].text
    asyncio.run(go())
