"""Shared fixtures: a throwaway database per test and an offline stand-in for the model.

`engine` calls the model only through `llm.run(...)` (a module attribute), so replacing it with
FakeLLM intercepts every specialist, interviewer, coach and planner call. The agents themselves are
built on pydantic-ai's TestModel so no API key or network is needed.
"""

import pytest
from pydantic_ai.models.test import TestModel

from ticktie import agents, config, db, engine, llm


class _Res:
    def __init__(self, out):
        self.output = out


def _rec(name: str) -> llm.CallRecord:
    return llm.CallRecord(name, 100, 0, 20, 1, 0, "gpt-6-luna", True, 1, 0.0)


class FakeLLM:
    """Scriptable stand-in for llm.run.

    verdict: "right" states every answer-key number and hits every key point; "wrong" states numbers
    that match nothing and hits no key point. fail: agent-name substrings that raise a gateway error.
    """

    def __init__(self):
        self.verdict = "right"
        self.fail: set[str] = set()
        self.calls: list[str] = []
        self.prompts: dict[str, str] = {}    # last prompt per agent
        self.mids: list[str] = []            # misconception ids the "specialist" flags
        self.offsets: dict[str, float] = {}  # label -> amount added to the true value (for near misses)
        self.unmatched_error = "none"
        self.rationale = "ok"
        self.extra_values: list = []         # extra (label, value) pairs the "specialist" reports (hedging)
        self.interviewer_message = "Good. Next one."
        self.coach_text = {"headline": "Solid work today.", "went_well": ["Clear structure."], "work_on": [],
                           "next_step": "Run a drill on your weakest skill.", "encouragement": "Keep going."}

    async def __call__(self, agent, agent_name, prompt, deps=None, session_id=None):
        self.calls.append(agent_name)
        self.prompts[agent_name] = prompt
        if any(f in agent_name for f in self.fail):
            raise RuntimeError("simulated gateway failure")
        if deps is not None:  # a specialist diagnostician
            q, ok = deps.question, self.verdict == "right"
            sv = ([agents.StatedValue(label=l.key, value=(q.values[l.key] + self.offsets.get(l.key, 0.0) if ok
                                                          else q.values[l.key] * 3 + 7777))
                   for l in q.labels] if q.kind == "numeric" else [])
            sv += [agents.StatedValue(label=k, value=v) for k, v in self.extra_values]
            if q.kind == "numeric":
                deps.tool_calls += 1  # the real specialist calls check_numbers once
            return _Res(agents.Diagnosis(
                stated_values=sv, key_points_hit=list(range(len(q.key_points))) if ok else [],
                misconceptions=list(self.mids), unmatched_error=self.unmatched_error,
                reasoning_quality="strong" if ok else "none", rationale=self.rationale,
                evidence_quote="x")), _rec(agent_name)
        if agent_name == "Interviewer":
            return _Res(agents.InterviewerMsg(message=self.interviewer_message)), _rec(agent_name)
        if agent_name == "Coach":
            return _Res(agents.Debrief.model_validate(self.coach_text)), _rec(agent_name)
        if agent_name == "Planner":
            return _Res(agents.PlanSummary(headline="Your plan.", why="Weakest areas first.",
                                           first_step="Start today.")), _rec(agent_name)
        raise AssertionError(f"unexpected agent {agent_name}")


def _clear_agent_caches():
    for fn in (agents.specialist, agents.interviewer, agents.coach, agents.planner):
        clear = getattr(fn, "cache_clear", None)
        if clear:
            clear()


@pytest.fixture
def tmp_db(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "t.db")
    monkeypatch.setattr(config, "LOG_PATH", tmp_path / "llm_calls.jsonl")
    db.init()
    return tmp_path


@pytest.fixture
def fake_llm(tmp_db, monkeypatch):
    f = FakeLLM()
    monkeypatch.setattr(llm, "run", f)
    monkeypatch.setattr(llm, "_model", TestModel())
    monkeypatch.setattr(config, "MIN_SECONDS_BETWEEN_TURNS", 0.0)  # no sleeping between answers in tests
    _clear_agent_caches()
    engine._INFLIGHT.clear()
    engine._ENDING.clear()
    engine._INFLIGHT_PROFILES.clear()
    from ticktie import server
    server._RATE.clear()
    yield f
    _clear_agent_caches()


@pytest.fixture
def pid(fake_llm):
    prof, _, _ = db.sign_in("Tester", "secret123")
    return prof["id"]


@pytest.fixture
def client(fake_llm):
    from fastapi.testclient import TestClient

    from ticktie.server import app

    with TestClient(app) as c:  # runs the lifespan hook -> db.init() on the temp database
        r = c.post("/api/signin", json={"name": "Api Tester", "password": "secret123"})
        c.headers["X-Auth-Token"] = r.json()["token"]
        yield c
