"""Session flow, end-of-session safety and the HTTP API, fully offline (FakeLLM in conftest.py)."""

import asyncio
import datetime as dt

import pytest

from ticktie import config, db, engine, llm
from ticktie import plan as planmod


def run(coro):
    return asyncio.run(coro)


def answer(sid, text="my answer"):
    return run(engine.answer(sid, text, 20))


def finish_diagnostic(pid):
    sid = engine.start_session(pid, "diagnostic", "associate", None)["id"]
    for _ in range(60):
        if answer(sid).get("complete"):
            break
    assert db.session(sid)["state"].get("complete")
    return sid


def answer_until(sid, done_q):
    for _ in range(40):
        if db.session(sid)["state"]["done_q"] >= done_q:
            return
        answer(sid)
    raise AssertionError("never reached done_q")


def done_count(pid):
    return sum(t["done"] for t in db.get_plan(pid)["tasks"])


# ---------------------------------------------------------------- end of session
def test_end_session_survives_coach_failure(pid, fake_llm):
    sid = engine.start_session(pid, "drill", "associate", None)["id"]
    answer_until(sid, 2)
    fake_llm.fail = {"Coach"}
    rep = run(engine.end_session(sid))
    assert rep["session"]["ended"]
    deb = rep["debrief"]
    assert set(deb) >= {"headline", "went_well", "work_on", "next_step", "encouragement", "plan_event"}
    assert any("Coach unavailable" in e["summary"] for e in rep["events"])


def test_end_session_twice_ticks_plan_once(pid, fake_llm):
    run(engine.end_session(finish_diagnostic(pid)))
    sid = engine.start_session(pid, "drill", "associate", None)["id"]
    answer_until(sid, 3)
    before = done_count(pid)
    hist = len(db.history(pid))
    run(engine.end_session(sid))
    run(engine.end_session(sid))
    assert done_count(pid) == before + 1
    assert len(db.history(pid)) - hist == len(engine.levels_for(pid))


def test_concurrent_end_session_runs_side_effects_once(pid, fake_llm, monkeypatch):
    run(engine.end_session(finish_diagnostic(pid)))
    sid = engine.start_session(pid, "drill", "associate", None)["id"]
    answer_until(sid, 3)
    before = done_count(pid)
    real = llm.run

    async def slow(*a, **k):
        await asyncio.sleep(0.05)
        return await real(*a, **k)

    monkeypatch.setattr(llm, "run", slow)

    async def both():
        return await asyncio.gather(engine.end_session(sid), engine.end_session(sid), return_exceptions=True)

    results = run(both())
    assert done_count(pid) == before + 1
    assert sum(1 for e in db.events(sid) if e["kind"] == "end") == 1
    assert any(isinstance(r, engine.Busy) for r in results) and any(isinstance(r, dict) for r in results)


def test_interviewer_failure_falls_back_and_saves_state(pid, fake_llm):
    sid = engine.start_session(pid, "mock", "associate", "accounting")["id"]
    n0 = db.mastery(pid)["accounting"]["n"]
    fake_llm.fail = {"Interviewer"}
    r = answer(sid)  # a right answer: graded, map updated, then the interviewer call fails
    assert not r["blocked"] and r["interviewer"]
    assert any("Interviewer unavailable" in e["summary"] for e in r["events"])
    st = db.session(sid)["state"]
    assert st["turns"] == 1  # the turn was saved, so a retry can't re-grade it
    n1 = db.mastery(pid)["accounting"]["n"]
    assert n1 == n0 + 1
    if r["resolved"] and r["action"] == "ack_next":
        assert r["next_question"] is not None


def test_no_answers_after_complete_diagnostic(pid, fake_llm):
    sid = finish_diagnostic(pid)
    calls = len(fake_llm.calls)
    r = answer(sid)
    assert r["blocked"] and r["reason"] == engine.FINISHED_REASON
    assert len(fake_llm.calls) == calls  # no model call


def test_no_regrade_after_practice_complete(pid, fake_llm):
    sid = engine.start_session(pid, "practice", "associate", "accounting")["id"]
    for _ in range(40):
        if answer(sid).get("complete"):
            break
    n = db.mastery(pid)["accounting"]["n"]
    r = answer(sid)
    assert r["blocked"] and db.mastery(pid)["accounting"]["n"] == n


def test_answer_after_end_is_blocked_not_error(pid, fake_llm):
    sid = engine.start_session(pid, "mock", "associate", None)["id"]
    run(engine.end_session(sid))
    r = answer(sid)
    assert r["blocked"] and r["reason"] == engine.FINISHED_REASON


def test_practice_industry_for_generalist_does_not_crash(pid):
    out = engine.start_session(pid, "practice", "associate", "industry")
    assert out["question"]["skill"] != "industry"


def test_turn_cap_still_gets_coach_debrief(pid, fake_llm):
    sid = engine.start_session(pid, "mock", "associate", None)["id"]
    answer(sid)
    st = db.session(sid)["state"]
    st["turns"] = config.MAX_TURNS_PER_SESSION
    db.save_state(sid, st)
    fake_llm.calls.clear()
    run(engine.end_session(sid))
    assert "Coach" in fake_llm.calls


# ---------------------------------------------------------------- placement (QA-03)
def test_empty_diagnostic_is_not_marked_done(pid):
    sid = engine.start_session(pid, "diagnostic", "associate", None)["id"]
    run(engine.end_session(sid))
    d = engine.dashboard(pid)
    assert d["diagnostic_done"] is False and d["plan"] is None and d["can_retake_placement"]


def test_partial_diagnostic_places_and_builds_plan(pid):
    sid = engine.start_session(pid, "diagnostic", "associate", None)["id"]
    answer(sid)
    answer(sid)  # two right accounting answers: climbed at least one level
    rep = run(engine.end_session(sid))
    placed = db.get_profile_json(pid, "placement")
    assert placed["accounting"] >= 1
    assert set(placed) >= {"ev", "dcf", "ma", "lbo", "fit"}  # the rest placed at level 0 (Getting started)
    d = engine.dashboard(pid)
    assert d["diagnostic_done"] and d["plan"] is not None and "ev" in d["placement_partial"]
    assert rep["is_placement"] and rep["placement_partial"]
    assert rep["debrief"]["plan_event"] == "plan_created_partial"


def test_retake_full_placement_clears_partial_flag(pid):
    sid = engine.start_session(pid, "diagnostic", "associate", None)["id"]
    answer(sid)
    run(engine.end_session(sid))
    run(engine.end_session(finish_diagnostic(pid)))
    assert engine.dashboard(pid)["placement_partial"] == []


# ---------------------------------------------------------------- plan (QA-04, QA-11, contract #8)
def test_rebuild_plan_keeps_completed_tasks(pid):
    run(engine.end_session(finish_diagnostic(pid)))
    plan = db.get_plan(pid)
    drills = [t for t in plan["tasks"] if t["type"] == "drill"][:2]
    for t in drills:
        planmod.mark_done(plan, "drill", t["skill"])
    db.save_plan(pid, plan)
    total = len(plan["tasks"])
    new = run(engine.build_plan(pid))
    done = [t for t in new["tasks"] if t["done"]]
    assert len(done) == 2 and {t["date"] for t in done} == {t["date"] for t in drills}
    assert len(new["tasks"]) == total  # unchanged inputs: no inflation


def test_start_specific_plan_task_targets_and_ticks_it(pid):
    run(engine.end_session(finish_diagnostic(pid)))
    plan = db.get_plan(pid)
    drills = [t for t in plan["tasks"] if t["type"] == "drill"]
    pick = next((t for t in reversed(drills) if t["skill"] != drills[0]["skill"]), drills[-1])
    out = engine.start_session(pid, "drill", "associate", None, None, task_id=pick["id"])
    st = db.session(out["id"])["state"]
    assert st["target"]["skill"] == pick["skill"] and st["target"]["level"] == pick["level"]
    answer_until(out["id"], 3)
    run(engine.end_session(out["id"]))
    ticked = next(t for t in db.get_plan(pid)["tasks"] if t["id"] == pick["id"])
    assert ticked["done"]


def test_group_change_resets_group_specifics(pid):
    engine.save_intake(pid, {"group": "tmt"})
    db.set_profile_json(pid, "placement", {"industry": 1, "accounting": 2})
    db.set_key(pid, "lvl:industry:1", 0.9, n_inc=3)
    out = engine.save_intake(pid, {"group": "fig"})
    assert out.get("group_changed")
    assert "industry" not in db.get_profile_json(pid, "placement")
    assert engine.levels_for(pid)["industry"] == 0 and engine.levels_for(pid)["accounting"] == 2


def test_save_intake_rejects_bad_date(pid):
    assert engine.save_intake(pid, {"interview_date": "not-a-date"})["interview_date"] is None
    assert engine.save_intake(pid, {"interview_date": "2026-11-03"})["interview_date"] == "2026-11-03"


def test_fallback_debrief_shape_and_tone():
    summary = {"questions": [{"title": "Walk me through a DCF", "skill": "DCF", "verdict": "correct", "misconceptions": []},
                             {"title": "EV bridge", "skill": "EV", "verdict": "incorrect",
                              "misconceptions": ["EV_CASH_ADD"]}],
               "misconceptions_seen": ["EV_CASH_ADD"]}
    d = engine._fallback_debrief(summary, None)
    assert set(d) == {"headline", "went_well", "work_on", "next_step", "encouragement"}
    assert len(d["went_well"]) <= 3 and len(d["work_on"]) <= 2
    assert d["headline"].startswith("Thanks")
    for w in d["work_on"]:
        assert set(w) == {"misconception_id", "name", "why", "try_this"}


# ---------------------------------------------------------------- HTTP API
def test_e2e_signin_intake_placement_plan_drill(client):
    tomorrow3w = (dt.date.today() + dt.timedelta(days=21)).isoformat()
    assert client.post("/api/intake", json={"group": "generalist", "stage": "first_rounds",
                                            "interview_date": tomorrow3w, "hours_per_week": 6}).status_code == 200
    s = client.post("/api/session", json={"mode": "diagnostic"}).json()
    sid = s["id"]
    for _ in range(60):
        r = client.post(f"/api/session/{sid}/answer", json={"text": "answer", "seconds": 20}).json()
        for c in r.get("checks", []):
            if not r["resolved"]:
                assert c["expected"] is None  # no answer key before the question resolves
        if r.get("complete"):
            break
    rep = client.post(f"/api/session/{sid}/end").json()
    assert rep["is_placement"] and rep["placement"] and rep["plan_progress"]
    dash = client.get("/api/dashboard").json()
    assert dash["diagnostic_done"] and dash["plan"]
    d = client.post("/api/session", json={"mode": "drill"}).json()
    for _ in range(40):
        r = client.post(f"/api/session/{d['id']}/answer", json={"text": "answer"}).json()
        if r["progress"]["answered"] >= 3:
            break
    rep = client.post(f"/api/session/{d['id']}/end").json()
    assert rep["touched_skills"] and not rep["is_placement"]
    assert client.get("/api/dashboard").json()["progress"]["done"] == 1


@pytest.mark.parametrize("method,path", [
    ("get", "/api/me"), ("get", "/api/dashboard"), ("get", "/api/map"), ("get", "/api/costs"), ("get", "/api/club"),
    ("get", "/api/session/active"), ("post", "/api/intake"), ("post", "/api/plan/rebuild"), ("post", "/api/session"),
    ("post", "/api/feedback"),
])
def test_personal_endpoints_require_token(client, method, path):
    client.headers.pop("X-Auth-Token")
    r = getattr(client, method)(path, **({"json": {}} if method == "post" else {}))
    assert r.status_code == 401


def test_cannot_touch_another_users_session(client):
    sid = client.post("/api/session", json={"mode": "mock"}).json()["id"]
    other = client.post("/api/signin", json={"name": "Someone Else", "password": "secret123"}).json()["token"]
    client.headers["X-Auth-Token"] = other
    assert client.post(f"/api/session/{sid}/answer", json={"text": "x"}).status_code == 404
    assert client.post(f"/api/session/{sid}/end").status_code == 404
    assert client.get(f"/api/session/{sid}/events").status_code == 404
    assert client.post("/api/feedback", json={"session_id": sid, "rating": 5}).status_code == 404
    assert client.get("/api/session/active").json()["session"] is None


def test_admin_export_hidden_without_token(client, monkeypatch):
    monkeypatch.delenv("TICKTIE_ADMIN_TOKEN", raising=False)
    assert client.get("/api/admin/export", headers={"X-Admin-Token": "x"}).status_code == 404
    monkeypatch.setenv("TICKTIE_ADMIN_TOKEN", "s3cret")
    assert client.get("/api/admin/export", headers={"X-Admin-Token": "wrong"}).status_code == 404
    assert client.get("/api/admin/export", headers={"X-Admin-Token": "s3cret"}).json().keys() >= {
        "feedback", "sessions", "turns", "events", "costs", "club"}


def test_no_key_gives_503_and_session_still_ends(client, monkeypatch):
    from ticktie import agents
    monkeypatch.setattr(config, "PORTKEY_API_KEY", None)
    monkeypatch.setattr(config, "OPENAI_API_KEY", None)
    monkeypatch.setattr(llm, "_model", None)
    for fn in (agents.specialist, agents.interviewer, agents.coach, agents.planner):
        getattr(fn, "cache_clear", lambda: None)()
    sid = client.post("/api/session", json={"mode": "mock"}).json()["id"]
    r = client.post(f"/api/session/{sid}/answer", json={"text": "my answer"})
    assert r.status_code == 503 and "No API key" in r.json()["error"]
    assert client.post(f"/api/session/{sid}/end").status_code == 200


def test_meta_exposes_app_name(client):
    m = client.get("/api/meta").json()
    assert m["app_name"] == config.APP_NAME == "IB Ready" and m["tagline"] == config.APP_TAGLINE
    assert client.get("/api/health").json()["ok"]


def test_active_session_resume(client):
    assert client.get("/api/session/active").json() == {"session": None}
    s = client.post("/api/session", json={"mode": "drill"}).json()
    client.post(f"/api/session/{s['id']}/answer", json={"text": "answer"})
    a = client.get("/api/session/active").json()["session"]
    assert a["id"] == s["id"] and a["opener"] is None and "question" in a and "progress" in a and "events" in a
    client.post(f"/api/session/{s['id']}/end")
    assert client.get("/api/session/active").json() == {"session": None}


def test_finished_session_answer_is_blocked(client):
    s = client.post("/api/session", json={"mode": "mock"}).json()
    client.post(f"/api/session/{s['id']}/end")
    r = client.post(f"/api/session/{s['id']}/answer", json={"text": "more"}).json()
    assert r["blocked"] and r["reason"] == "This session is finished — see your results."


def test_dashboard_today_follows_client_timezone(client):
    utc_today = dt.datetime.now(dt.timezone.utc).date()
    east = client.get("/api/dashboard", headers={"X-TZ-Offset": "-840"}).json()["today"]  # UTC+14
    west = client.get("/api/dashboard", headers={"X-TZ-Offset": "720"}).json()["today"]   # UTC-12
    default = client.get("/api/dashboard").json()["today"]
    assert default == utc_today.isoformat()
    assert dt.date.fromisoformat(east) - dt.date.fromisoformat(west) == dt.timedelta(days=1)


def test_costs_and_club_signed_in(client):
    assert client.get("/api/costs").status_code == 200
    c = client.get("/api/club").json()
    assert c["too_few_members"] and c["misconceptions"] == []


# ---------------------------------------------------------------- QA round 2 grading, through the full turn
def _set_question(sid, tid, params):
    st = db.session(sid)["state"]
    q = engine.bank.build(engine.bank.TEMPLATES[tid], params)
    st["current"] = {**q.to_state(), "whatif": False}
    st["attempts"], st["followups"], st["phase"], st["first_verdict"] = 0, 0, "answer", None
    db.save_state(sid, st)


def test_wrong_claim_with_right_numbers_nudges_and_hits_the_map(pid, fake_llm):
    sid = engine.start_session(pid, "drill", "associate", "dcf")["id"]
    _set_question(sid, "dcf_unlever_beta", {"t": 0.2, "de": 0.5, "bL": 1.68})
    fake_llm.mids = ["DCF_BETA_DIRECTION"]
    fake_llm.fail = {"Interviewer"}  # the safe fallback must name the concept, with no numbers
    r = answer(sid)
    assert (r["verdict"], r["error_type"], r["action"]) == ("incomplete", "conceptual", "nudge")
    assert "DCF_BETA_DIRECTION" in {m["mid"] for m in db.misconceptions(pid) if m["hits"]}
    lib = engine.LIBRARY["DCF_BETA_DIRECTION"].name.lower()
    assert lib in r["interviewer"].lower() and not any(ch.isdigit() for ch in r["interviewer"])


def test_near_miss_turn_shows_a_neutral_rounding_note(pid, fake_llm):
    sid = engine.start_session(pid, "drill", "associate", "dcf")["id"]
    _set_question(sid, "mkt_rates_wacc", {"we": 0.7, "w0": 0.1, "b": 0.8, "t": 0.4, "g": 0.03, "bp": 100.0})
    fake_llm.offsets = {"wacc_new": -0.09}
    fake_llm.unmatched_error = "arithmetic"
    fake_llm.mids = ["GEN_ARITHMETIC"]
    r = answer(sid)
    assert (r["verdict"], r["error_type"], r["action"]) == ("incomplete", "rounding", "nudge")
    assert r["note"].startswith("Close. Check your rounding") and r["misconceptions"] == []
    assert "GEN_ARITHMETIC" not in {m["mid"] for m in db.misconceptions(pid) if m["hits"]}


def test_wrong_optional_line_item_is_a_nudge_not_a_fail(pid, fake_llm):
    sid = engine.start_session(pid, "drill", "associate", "accounting")["id"]
    _set_question(sid, "acc_asset_sale", {"B": 60.0, "P": 100.0, "t": 0.25})
    fake_llm.offsets = {"ppe": -190.0}
    r = answer(sid)
    assert r["verdict"] == "incomplete" and r["action"] == "nudge"
    assert [c["status"] for c in r["checks"] if c["name"].lower().startswith("change in pp")] == ["wrong"]


def test_openers_are_plain_language(pid):
    for mode, focus in (("drill", "ma"), ("practice", "ma"), ("diagnostic", None), ("mock", None)):
        o = engine.start_session(pid, mode, "associate", focus)["opener"]
        assert "Targeted drill" not in o and "drill" not in o.lower() and "practis" not in o.lower()
        assert o.count(":") <= 1, o
    assert engine.start_session(pid, "practice", "associate", "ma", 1)["opener"].startswith(
        "Practice: M&A, coffee-chat level questions.")
    assert engine.start_session(pid, "diagnostic", "associate", None)["opener"].startswith("This is a quick check, not a test.")


# ---------------------------------------------------------------- safety QA round 2 (S1, S2, abuse limits)
def _numbers_in(obj) -> str:
    import json as _json
    return _json.dumps(obj).replace(",", "")


def test_unresolved_wrong_attempt_leaks_no_answer_key(client, fake_llm):
    import json as _json
    sid = client.post("/api/session", json={"mode": "drill", "focus": "dcf"}).json()["id"]
    _set_question(sid, "dcf_tv", {"F": 100.0, "w": 0.10, "g": 0.02})  # answer key: TV = 1,275
    fake_llm.verdict = "wrong"
    fake_llm.rationale = "The right terminal value is 1,275, not what they said."
    fake_llm.interviewer_message = "Close, but the answer is 1,275."  # blocked by the output filter
    r = client.post(f"/api/session/{sid}/answer", json={"text": "TV is about 900"}).json()
    assert r["action"] == "nudge" and not r["resolved"]
    ev = client.get(f"/api/session/{sid}/events").json()
    for body in (r, ev):
        text = _json.dumps(body)
        assert "1275" not in text and "1,275" not in text, body
    # kept server-side for the owner's export
    with db.conn() as c:
        private = " ".join(row["private"] or "" for row in c.execute("SELECT private FROM events WHERE session_id=?", (sid,)))
    assert "1275" in private and "the answer is 1,275" in private


def test_resolved_question_shows_the_answer_key_in_the_trace(client, fake_llm):
    sid = client.post("/api/session", json={"mode": "drill", "focus": "dcf"}).json()["id"]
    _set_question(sid, "dcf_tv", {"F": 100.0, "w": 0.10, "g": 0.02})
    fake_llm.verdict = "wrong"
    client.post(f"/api/session/{sid}/answer", json={"text": "900"})
    r = client.post(f"/api/session/{sid}/answer", json={"text": "still 900"}).json()  # second miss: reveal
    assert r["action"] == "reveal"
    calc = [e for e in r["events"] if e["actor"] == "Calculator"]
    assert calc and calc[-1]["detail"]["checks"][0]["expected"] == 1275.0


def test_hedged_answer_turn_asks_to_commit(pid, fake_llm):
    sid = engine.start_session(pid, "drill", "associate", "dcf")["id"]
    _set_question(sid, "dcf_tv", {"F": 100.0, "w": 0.10, "g": 0.02})
    fake_llm.extra_values = [("tv", 1500.0)]  # "1,275, or maybe 1,500"
    r = answer(sid)
    assert r["verdict"] == "incomplete" and r["error_type"] == "hedged" and r["note"].endswith("Commit to one.")
    assert r["checks"][0]["status"] == "wrong" and r["checks"][0]["hedged"]


def test_club_counts_only_members_with_graded_answers(pid):
    for i in range(4):
        db.sign_in(f"Empty Profile {i}", "secret123")
    assert db.club_summary()["members"] == 0
    sid = engine.start_session(pid, "mock", "associate", None)["id"]
    answer(sid)
    assert db.club_summary()["members"] == 1


def test_lockout_is_per_name_and_ip(tmp_db):
    db.sign_in("Victim", "rightpass", "1.1.1.1")
    for _ in range(db.MAX_FAILURES):
        with pytest.raises(db.AuthError):
            db.sign_in("Victim", "wrongpass", "6.6.6.6")
    with pytest.raises(db.AuthError, match="locked"):
        db.sign_in("Victim", "rightpass", "6.6.6.6")
    assert db.sign_in("Victim", "rightpass", "1.1.1.1")[0]["name"] == "Victim"  # the owner's network still works


def test_signin_and_signup_rate_limits(client, monkeypatch):
    monkeypatch.setattr(config, "SIGNUPS_PER_IP_PER_HOUR", 2)  # the fixture already created one profile
    assert client.post("/api/signin", json={"name": "Second Person", "password": "secret123"}).status_code == 200
    r = client.post("/api/signin", json={"name": "Third Person", "password": "secret123"})
    assert r.status_code == 429 and "new profiles" in r.json()["detail"]
    assert client.post("/api/signin", json={"name": "Second Person", "password": "secret123"}).status_code == 200
    monkeypatch.setattr(config, "SIGNIN_PER_IP_PER_MINUTE", 5)
    codes = [client.post("/api/signin", json={"name": "Second Person", "password": "secret123"}).status_code
             for _ in range(5)]
    assert codes[-1] == 429


def test_one_graded_turn_per_profile(pid, fake_llm):
    a = engine.start_session(pid, "mock", "associate", None)["id"]
    engine._INFLIGHT_PROFILES.add(pid)  # a turn is being graded in another tab
    calls = len(fake_llm.calls)
    r = answer(a)
    assert r["blocked"] and "another tab" in r["reason"] and len(fake_llm.calls) == calls
    engine._INFLIGHT_PROFILES.discard(pid)
    assert not answer(a)["blocked"]


def test_coach_summary_has_error_type_and_right_line_items(pid, fake_llm):
    import json as _json
    sid = engine.start_session(pid, "drill", "associate", "dcf")["id"]
    _set_question(sid, "dcf_tv", {"F": 100.0, "w": 0.10, "g": 0.02})
    answer(sid)
    run(engine.end_session(sid))
    qs = _json.loads(fake_llm.prompts["Coach"])["questions"]
    tv = engine.bank.TEMPLATES["dcf_tv"].labels[0].name
    assert qs[0]["error_type"] == "none" and qs[0]["line_items_right"] == [tv]


def test_partial_placement_report_shows_the_credited_topic(pid):
    sid = engine.start_session(pid, "diagnostic", "associate", None)["id"]
    answer(sid)
    answer(sid)  # climbing accounting, not yet placed when the session ends
    rep = run(engine.end_session(sid))
    assert rep["placement"].get("accounting", 0) >= 1 and "ev" in rep["placement_not_reached"]


def test_generalist_group_specifics_practice_explains_the_swap(pid):
    sid = engine.start_session(pid, "practice", "associate", "industry")["id"]
    pick = next(e for e in db.events(sid) if e["kind"] == "pick")
    assert "coverage group" in pick["detail"]["reason"]


def test_drill_trace_admits_when_it_leaves_the_exact_target(pid):
    out = engine.start_session(pid, "drill", "associate", "ma", 3)
    st = db.session(out["id"])["state"]
    pick = next(e for e in db.events(out["id"]) if e["kind"] == "pick")
    t = engine.bank.TEMPLATES[st["current"]["template_id"]]
    if t.difficulty != st["target"]["level"]:
        assert "closest one" in pick["detail"]["reason"]
    else:
        assert "closest one" not in pick["detail"]["reason"]
