"""The interview director: deterministic code that runs the agents.

Code, not a model, is the boss here, on purpose:
* it picks every question from the weakness map, so the AI can't choose easy
  questions to make the candidate look good (Goodhart's law);
* it makes the final grading call from the calculator checks, so no answer
  text can talk its way to "correct";
* it enforces budgets, caps and output filters before anything is shown.
"""

from __future__ import annotations

import json
import random
import time

from . import agents, bank, config, db, guard, llm, mastery
from . import plan as planmod
from .misconceptions import LIBRARY

OPENERS = {
    "associate": "Hi, thanks for making time. We'll keep this conversational: a few technicals, and I'll dig into "
                 "your reasoning as we go. Talk me through your thinking out loud. First one:",
    "vp": "Let's get into it. I'll move quickly and push on anything vague, so be precise. Go:",
    "director": "Thanks for coming in. I want to get a sense of who you are and how you think, and we'll cover some "
                "technicals along the way. Let's start:",
    "md": "Good to meet you. I'm less interested in rehearsed answers than in how you think and why you're here. "
          "Let's talk:",
}
DIAGNOSTIC_OPENER = ("This is your placement interview: about 10-20 questions across accounting, valuation, DCF, M&A, LBOs"
                     "{group} and fit. Each skill starts at Basic and moves up as you get questions right. One attempt each, "
                     "no notes. When it's done you'll get your level and a personal action plan.")
DIAG_ACKS = {True: ["Good.", "Right.", "Noted, good.", "OK, that works."], False: ["Noted.", "OK, let's keep going.", "Got it, moving on."]}

FALLBACKS = {
    "nudge": "Not quite. Take another look at {items} and walk me through that part again.",
    "probe_why": "Your numbers are right. Now tell me why: what's driving the key step there?",
    "ack_next": "Good. Let's move on.",
    "ack_whatif": "Good. Let me change one thing.",
    "note_next": "Your numbers were right, but the why matters as much as the what. Have a look at the worked answer, then let's keep going.",
    "reveal": "Let's look at the worked answer together. The key idea is in the note below. Then we'll keep going.",
    "redirect": "Let's keep this to the interview. Answer the question in front of you.",
}

GOALS = {"drill": 8, "mock": 10, "practice": 8}


class BudgetExceeded(Exception):
    pass


# ---------------------------------------------------------------- helpers
def _rng(state: dict) -> random.Random:
    return random.Random(f"{state['seed']}-{state['turns']}-{len(state['asked'])}")


def _active(pid: str) -> dict[str, int]:
    return {m["mid"]: m["hits"] for m in db.misconceptions(pid) if m["active"]}


def levels_for(pid: str) -> dict[str, int]:
    placed = db.get_profile_json(pid, "placement")
    keys = db.mastery_all(pid)
    return {s: mastery.current_level(s, int(placed.get(s, 0)), keys) for s in bank.SKILLS}


def weak_subskills(pid: str, limit: int = 8) -> list[str]:
    """Sub-skills with low mastery, plus those behind active misconceptions, weakest first."""
    keys = db.mastery_all(pid)
    scores: dict[str, float] = {}
    for k, v in keys.items():
        if k.startswith("sub:") and v["n"] > 0 and v["p"] < 0.55:
            scores[k[4:]] = v["p"]
    active = _active(pid)
    for t in bank.TEMPLATES.values():
        if any(m in active for m in t.misconceptions) and t.subskill:
            scores[t.subskill] = min(scores.get(t.subskill, 1.0), 0.3)
    return [k for k, _ in sorted(scores.items(), key=lambda kv: kv[1]) if k in bank.SUBSKILLS][:limit]


def _intake(pid: str) -> dict:
    return db.get_profile_json(pid, "intake")


def _drill_target(pid: str, focus: str | None, level: int | None) -> dict:
    """What a drill aims at: the next open plan task, else the weakest sub-skill, else the weakest skill."""
    levels = levels_for(pid)
    if focus in bank.SKILLS:
        return {"skill": focus, "subskill": None, "level": level or mastery.target_level(levels.get(focus, 0)), "task": None}
    plan = db.get_plan(pid)
    if plan:
        nxt = next((t for t in plan["tasks"] if not t["done"] and t["type"] == "drill"), None)
        if nxt:
            return {"skill": nxt["skill"], "subskill": nxt["subskill"], "level": nxt["level"], "task": nxt["id"]}
    weak = weak_subskills(pid)
    if weak:
        sk = bank.SUBSKILLS[weak[0]][0]
        return {"skill": sk, "subskill": weak[0], "level": max(levels.get(sk, 0), 1), "task": None}
    sk = min(bank.TECHNICAL, key=lambda s: levels.get(s, 0))
    return {"skill": sk, "subskill": None, "level": mastery.target_level(levels.get(sk, 0)), "task": None}


def _pick(pid: str, state: dict, sid: str) -> bank.Question:
    rng = _rng(state)
    group = _intake(pid).get("group")
    act = _active(pid)
    asked = state["asked"]
    mode = state["mode"]
    if mode == "diagnostic":
        d = state["diag"]
        skill, lvl = d["skills"][d["i"]], d["level"]
        t = mastery.pick_targeted(group, skill, lvl, None, asked, act, rng)
        reason = f"Placement: {bank.SKILLS[skill]} at {bank.LEVELS[lvl]} level."
    elif mode == "drill":
        tg = state["target"]
        t = mastery.pick_targeted(group, tg["skill"], tg["level"], tg["subskill"], asked, act, rng)
        sub = bank.SUBSKILLS.get(tg["subskill"], ("", ""))[1]
        reason = f"Drill target: {bank.SKILLS[tg['skill']]}" + (f" / {sub}" if sub else "") + f" at {bank.LEVELS[tg['level']]}."
    elif mode == "practice":
        focus = state.get("focus") or "accounting"
        lvl = state.get("level") or mastery.target_level(levels_for(pid).get(focus, 0))
        cands = mastery.pool(group, skill=focus, levels=(lvl,)) or mastery.pool(group, skill=focus)
        t = mastery.choose(cands, asked, act, rng)
        reason = f"Practice: {bank.SKILLS[focus]}, {bank.LEVELS[lvl]} only."
    else:  # mock
        levels = levels_for(pid)
        t = mastery.pick_mock(group, state["persona"], levels, bank.GROUP_WEIGHTS.get(group, {}), asked, act, rng,
                              state.get("focus"))
        reason = (f"Mock with the {agents.PERSONAS[state['persona']][0]}: "
                  f"{'fit question' if t.skill == 'fit' else bank.SKILLS[t.skill]} at {bank.LEVELS[t.difficulty]}.")
    hits = [x for x in t.misconceptions if x in act]
    if hits:
        reason += " Re-tests: " + ", ".join(LIBRARY[h].name for h in hits) + "."
    params = t.gen(rng)
    if t.kind == "behavioral":
        params = {"group": bank.GROUPS.get(group, "this group").split(" (")[0]
                  if group and group != "generalist" else "investment banking"}
    q = bank.build(t, params)
    asked.append(t.id)
    state["current"] = {**q.to_state(), "whatif": False}
    state["attempts"] = 0
    state["followups"] = 0
    state["phase"] = "answer"
    state["first_verdict"] = None
    state["q_started"] = time.time()
    db.add_event(sid, "Director", "pick", f"Picked \"{t.title}\" ({bank.LEVELS[t.difficulty]}).",
                 {"template": t.id, "reason": reason, "params": q.params, "subskill": t.subskill})
    return q


def _current(state: dict) -> bank.Question:
    cur = state["current"]
    q = bank.from_state(cur)
    q.text = cur["text"]
    if cur.get("whatif"):
        q.title = q.title + ": what-if"
    return q


def _budget_check(sid: str, pid: str, state: dict) -> None:
    use = db.session_usage(sid)
    if use["input_tokens"] + use["output_tokens"] >= config.SESSION_TOKEN_BUDGET:
        raise BudgetExceeded(f"Session token budget reached ({config.SESSION_TOKEN_BUDGET:,} tokens). "
                             f"End the session to get your debrief.")
    day = time.time() - 86400
    if db.tokens_since(day, pid) >= config.DAILY_PROFILE_TOKEN_BUDGET:
        raise BudgetExceeded("Daily token budget for this profile reached. Come back tomorrow.")
    if db.tokens_since(day) >= config.DAILY_GLOBAL_TOKEN_BUDGET:
        raise BudgetExceeded("The app's daily token budget is used up. Try again tomorrow.")
    if state["turns"] >= config.MAX_TURNS_PER_SESSION:
        raise BudgetExceeded("This session hit its turn limit. End it to get your debrief.")
    if time.time() - state.get("last_turn", 0) < config.MIN_SECONDS_BETWEEN_TURNS:
        raise BudgetExceeded("Slow down a little: one answer per second.")


def _progress(state: dict) -> dict:
    if state["mode"] == "diagnostic":
        d = state["diag"]
        done_sk = d["i"]
        cur = d["skills"][min(d["i"], len(d["skills"]) - 1)]
        return {"kind": "diagnostic", "skills_done": done_sk, "skills_total": len(d["skills"]),
                "pct": round(100 * done_sk / len(d["skills"])), "answered": state.get("done_q", 0),
                "label": "Placement complete" if state.get("complete") else
                f"Placement: {bank.SKILLS[cur]} · {bank.LEVELS[d['level']]}",
                "placed": dict(d["results"])}
    goal = state.get("goal") or 8
    done = state.get("done_q", 0)
    return {"kind": state["mode"], "answered": done, "goal": goal, "pct": round(100 * min(done, goal) / goal),
            "label": f"Question {min(done + 1, goal)} of {goal}" if not state.get("complete") else "Session complete"}


def _public_session(sid: str) -> dict:
    s = db.session(sid)
    st = s["state"]
    q = _current(st)
    return {
        "id": sid, "mode": s["mode"], "persona": s["persona"], "persona_label": agents.PERSONAS[s["persona"]][0],
        "focus": s["focus"], "question": {**q.to_public(), "whatif": st["current"].get("whatif", False),
                                          "attempt": st["attempts"] + 1, "phase": st["phase"],
                                          "attempts_allowed": 1 if st["mode"] == "diagnostic" else config.MAX_ATTEMPTS_PER_QUESTION},
        "progress": _progress(st), "complete": bool(st.get("complete")),
        "usage": db.session_usage(sid), "budget": config.SESSION_TOKEN_BUDGET, "ended": bool(s["ended"]),
    }


# ---------------------------------------------------------------- public API
def save_intake(pid: str, intake: dict) -> dict:
    try:
        hours = float(intake.get("hours_per_week") or 5)
    except (TypeError, ValueError):
        hours = 5.0
    clean = {
        "group": intake.get("group") if intake.get("group") in bank.GROUPS else "generalist",
        "stage": intake.get("stage") if intake.get("stage") in planmod.STAGES else "networking",
        "interview_date": str(intake.get("interview_date") or "")[:10] or None,
        "hours_per_week": max(1.0, min(hours, 40.0)),
        "persona": intake.get("persona") if intake.get("persona") in agents.PERSONAS else "associate",
    }
    db.set_profile_json(pid, "intake", clean)
    return clean


def start_session(profile_id: str, mode: str, persona: str, focus: str | None, level: int | None = None) -> dict:
    if mode not in ("diagnostic", "drill", "mock", "practice"):
        mode = "mock"
    if persona not in agents.PERSONAS:
        persona = "associate"
    if focus not in bank.SKILLS:
        focus = None
    if level not in (1, 2, 3):
        level = None
    if mode == "practice" and not focus:
        focus = "accounting"
    intake = _intake(profile_id)
    group = intake.get("group")
    state = {"seed": random.randrange(1_000_000), "mode": mode, "persona": persona, "focus": focus, "level": level,
             "asked": [], "turns": 0, "last_turn": 0.0, "done_q": 0, "goal": GOALS.get(mode),
             "levels_start": levels_for(profile_id)}
    if mode == "diagnostic":
        skills = mastery.diagnostic_skills(group)
        state["diag"] = {"skills": skills, "i": 0, "level": mastery.first_level(group, skills[0]), "results": {},
                         "fit_seen": 0, "fit_pass": 0}
    if mode == "drill":
        state["target"] = _drill_target(profile_id, focus, level)
    sid = db.create_session(profile_id, mode, persona, focus, state)
    db.add_event(sid, "Director", "start", f"Started a {mode} session with the {agents.PERSONAS[persona][0]}.",
                 {"focus": focus, "level": level, "group": group, "target": state.get("target")})
    _pick(profile_id, state, sid)
    db.save_state(sid, state)
    out = _public_session(sid)
    if mode == "diagnostic":
        gname = bank.GROUPS.get(group or "generalist", "")
        out["opener"] = DIAGNOSTIC_OPENER.format(
            group=f", {gname.split(' (')[0]} specifics" if group and group != "generalist" else "")
    elif mode == "drill":
        tg = state["target"]
        sub = bank.SUBSKILLS.get(tg["subskill"], ("", ""))[1]
        out["opener"] = (f"Targeted drill: {bank.SKILLS[tg['skill']]}" + (f", {sub}" if sub else "") +
                         f", {bank.LEVELS[tg['level']]} level, {GOALS['drill']} questions. " + OPENERS[persona])
    else:
        out["opener"] = OPENERS[persona]
    out["events"] = db.events(sid)
    return out


def _advance_diagnostic(pid: str, state: dict, passed: bool, sid: str) -> None:
    """Adaptive placement: climb a skill's levels while answers are right, then move to the next skill."""
    d = state["diag"]
    skill = d["skills"][d["i"]]
    group = _intake(pid).get("group")
    placed = None
    if skill == "fit":
        d["fit_seen"] += 1
        d["fit_pass"] += int(passed)
        if d["fit_seen"] >= 2:
            placed = d["fit_pass"]  # 0, 1 or 2
    elif passed and d["level"] < 3 and mastery.pool(group, skill=skill, levels=(d["level"] + 1,)):
        d["level"] += 1
    else:
        placed = d["level"] if passed else d["level"] - 1
    if placed is not None:
        placed = max(0, placed)
        d["results"][skill] = placed
        db.add_event(sid, "Director", "placement",
                     f"Placed {bank.SKILLS[skill]} at {bank.LEVELS.get(placed, 'Foundations')}.",
                     {"skill": skill, "level": placed})
        d["i"] += 1
        if d["i"] >= len(d["skills"]):
            state["complete"] = True
        else:
            d["level"] = mastery.first_level(group, d["skills"][d["i"]])


_INFLIGHT: set[str] = set()  # sessions with a turn being graded right now


async def answer(sid: str, raw_text: str, seconds: float | None) -> dict:
    """One candidate turn. Only one turn per session can run at a time."""
    if sid in _INFLIGHT:
        db.add_event(sid, "Guard", "safety", "Blocked: a second answer arrived while the first was still being graded.",
                     {"type": "rate"})
        return {"blocked": True, "reason": "Still grading your last answer.", "session": _public_session(sid),
                "events": db.events(sid)[-1:]}
    _INFLIGHT.add(sid)
    try:
        out = await _answer(sid, raw_text, seconds)
    finally:
        _INFLIGHT.discard(sid)
        s = db.session(sid)
        if s:
            st = s["state"]
            st["last_turn"] = time.time()  # rate limit counts from the END of the last turn
            db.save_state(sid, st)
    return out


async def _answer(sid: str, raw_text: str, seconds: float | None) -> dict:
    s = db.session(sid)
    if s is None or s["ended"]:
        raise ValueError("Session not found or already ended.")
    pid, state = s["profile_id"], s["state"]
    ev_start = len(db.events(sid))

    try:
        _budget_check(sid, pid, state)
    except BudgetExceeded as e:
        db.add_event(sid, "Guard", "safety", "Blocked: " + str(e), {"type": "budget"})
        return {"blocked": True, "reason": str(e), "session": _public_session(sid),
                "events": db.events(sid)[ev_start:]}

    state["turns"] += 1
    state["last_turn"] = time.time()
    q = _current(state)
    explain_only = state["phase"] == "why"

    # ---------- 1. input guard
    ic = guard.check_input(raw_text)
    if ic.flags or ic.truncated:
        db.add_event(sid, "Guard", "safety",
                     "Input flagged: " + ", ".join(ic.flags + (["answer truncated"] if ic.truncated else [])),
                     {"flags": ic.flags, "truncated": ic.truncated, "zero_width_removed": ic.zero_width_removed})
    if not ic.text:
        return {"blocked": True, "reason": "Type an answer first.", "session": _public_session(sid),
                "events": db.events(sid)[ev_start:]}
    wrapped = guard.wrap_untrusted(ic.text)

    # ---------- 2. specialist diagnosis (LLM + calculator tool)
    spec_key = agents.specialist_for(q)
    spec = agents.specialist(spec_key)
    deps = agents.DiagDeps(question=q)
    prompt = agents.diagnosis_prompt(q, wrapped, ic.flags, explain_only)
    try:
        result, rec = await llm.run(spec, agents.SPECIALISTS[spec_key][0], prompt, deps=deps, session_id=sid)
    except Exception as e:
        if not llm.is_content_filter(e):
            raise
        # The provider's own safety filter refused the text. Nothing is graded; no attempt is used.
        db.add_event(sid, "Guard", "safety",
                     "Provider content filter (Azure prompt shield) refused the answer. Nothing was graded.",
                     {"layer": "provider", "error": str(e)[:200], "filter_flags": ic.flags})
        msg = FALLBACKS["redirect"]
        db.save_state(sid, state)
        db.add_turn(sid, template_id=q.template_id, skill=q.skill, kind=q.kind, question=q.text, answer=ic.text,
                    seconds=seconds, verdict=None, error_type="blocked", misconceptions=[], interviewer=msg,
                    diagnosis={"blocked": "content_filter", "flags": ic.flags})
        return {"blocked": False, "interviewer": msg, "verdict": "redirect", "final_verdict": None,
                "error_type": "blocked", "action": "redirect", "resolved": False, "explain_only": explain_only,
                "checks": [], "misconceptions": [], "rationale": None, "solution": None,
                "answered_question": {"title": q.title, "skill": q.skill, "kind": q.kind, "seconds": seconds, "target": q.target_seconds},
                "session": _public_session(sid), "events": db.events(sid)[ev_start:], "next_question": None}
    d: agents.Diagnosis = result.output
    db.add_event(sid, agents.SPECIALISTS[spec_key][0], "llm",
                 f"Diagnosed the answer: reasoning {d.reasoning_quality}.",
                 {"rationale": d.rationale, "misconceptions": d.misconceptions,
                  "stated": [v.model_dump() for v in d.stated_values], "manipulation": d.manipulation_attempt,
                  "model": rec.model_resolved}, rec)

    # ---------- 3. deterministic adjudication (the code makes the call)
    verdict, error_type, mids, checks = _adjudicate(q, d, explain_only)
    if deps.tool_calls:
        db.add_event(sid, "Calculator", "tool", "check_numbers: " + ", ".join(
            f"{c.name} {c.status}" + (f" ({', '.join(c.matches)})" if c.matches else "") for c in checks if c.status != "missing"),
            {"checks": [c.to_dict() for c in checks]})
    manipulated = d.manipulation_attempt or any(
        f in ic.flags for f in ("grade manipulation", "instruction override", "score tampering", "role hijack",
                                "answer/prompt extraction", "system/developer prompt reference", "fake message tags"))
    if manipulated:
        db.add_event(sid, "Guard", "safety",
                     "Grader lock: manipulation attempt detected. The grade comes only from the calculator checks.",
                     {"llm_flag": d.manipulation_attempt, "filter_flags": ic.flags, "verdict_after_lock": verdict})
    no_content = (not d.key_points_hit and not any(c.status != "missing" for c in checks))
    if manipulated and no_content:
        verdict = "redirect"  # nothing to grade but the attack itself: no credit, no attempt used

    # ---------- 4. choose the next action
    action, resolved = _choose_action(state, q, verdict, explain_only)

    # ---------- 5. update the weakness map when the question resolves
    evidence = {"q": q.title, "quote": d.evidence_quote[:160], "ts": time.time()}
    if verdict not in ("redirect",):
        for mid in mids:
            db.record_misconception(pid, mid, True, evidence)
    final_verdict = None
    if resolved and verdict != "redirect":
        final_verdict = _final_verdict(state, verdict, explain_only)
        p_old = db.mastery(pid)[q.skill]["p"]
        p_new = mastery.bkt_update(p_old, final_verdict, q.kind)
        db.set_mastery(pid, q.skill, p_new)
        # the same evidence also updates this level and this sub-skill
        for key in (f"lvl:{q.skill}:{q.difficulty}", f"sub:{q.subskill}"):
            db.set_key(pid, key, mastery.bkt_update(db.get_key(pid, key), final_verdict, q.kind))
        if final_verdict == "correct":
            for mid in q.misconceptions:
                if mid not in mids:
                    db.record_misconception(pid, mid, False, None)
        db.add_event(sid, "Director", "mastery",
                     f"{bank.SKILLS[q.skill]} mastery {round(p_old * 100)}% -> {round(p_new * 100)}% ({final_verdict}).",
                     {"skill": q.skill, "p_old": p_old, "p_new": p_new, "verdict": final_verdict,
                      "subskill": q.subskill, "level": q.difficulty})
        if not state["current"].get("whatif"):
            state["done_q"] = state.get("done_q", 0) + 1
        if state["mode"] == "diagnostic":
            _advance_diagnostic(pid, state, final_verdict in ("correct", "correct_unexplained"), sid)
        elif state.get("goal") and state["done_q"] >= state["goal"] and action != "ack_whatif":
            state["complete"] = True
    if state["phase"] == "answer" and state["first_verdict"] is None and verdict != "redirect":
        state["first_verdict"] = verdict

    # ---------- 6. interviewer message (LLM) through the output filters
    # A what-if follow-up is computed by the calculator first, so the interviewer can only introduce it.
    nq = bank.variation(q, _rng(state)) if action == "ack_whatif" else None
    if state["mode"] == "diagnostic" and action != "redirect":
        # placement is a quick screen: a short neutral acknowledgement, no coaching mid-test (and no extra model call)
        msg = _rng(state).choice(DIAG_ACKS[final_verdict in ("correct", "correct_unexplained")])
        if state.get("complete"):
            msg = "That's the placement done. Let's look at where you stand."
    else:
        msg = await _interviewer_message(sid, state, q, verdict, action, checks, mids, wrapped, d,
                                         followup=nq.text if nq else None)

    # ---------- 7. advance the interview
    solution = q.solution if (action == "reveal" or resolved) else None
    next_q = None
    if action == "ack_whatif":
        state["current"] = {**nq.to_state(), "text": nq.text, "whatif": True}
        state["attempts"] = 0
        state["phase"] = "answer"
        state["followups"] += 1
        state["first_verdict"] = None
        db.add_event(sid, "Director", "pick", f"What-if follow-up on \"{q.title}\", recomputed by the calculator.",
                     {"params": nq.params})
        next_q = nq
    elif action == "probe_why":
        state["phase"] = "why"
        state["followups"] += 1
    elif action == "nudge":
        state["attempts"] += 1
    elif action in ("ack_next", "reveal", "note_next", "diag_next") and not state.get("complete"):
        next_q = _pick(pid, state, sid)
    db.save_state(sid, state)

    # ---------- 8. persist the turn
    use_turn = rec.to_dict()
    db.add_turn(sid, template_id=q.template_id, skill=q.skill, kind=q.kind, question=q.text, answer=ic.text,
                seconds=seconds, verdict=verdict if verdict != "redirect" else None, error_type=error_type,
                misconceptions=mids, interviewer=msg,
                diagnosis={"diagnosis": d.model_dump(), "checks": [c.to_dict() for c in checks],
                           "action": action, "final_verdict": final_verdict, "explain_only": explain_only,
                           "flags": ic.flags},
                input_tokens=use_turn["input_tokens"], cached_tokens=use_turn["cached_tokens"],
                output_tokens=use_turn["output_tokens"], cost_usd=use_turn["cost_usd"])

    show_detail = resolved or action == "reveal"
    return {
        "blocked": False,
        "interviewer": msg,
        "verdict": verdict,
        "final_verdict": final_verdict,
        "error_type": error_type,
        "action": action,
        "resolved": resolved,
        "explain_only": explain_only,
        "checks": [{"name": c.name, "status": c.status, "stated": c.stated,
                    "expected": c.expected if show_detail else None,
                    "required": next(l.required for l in q.labels if l.key == c.label)} for c in checks],
        "misconceptions": [{"id": m, "name": LIBRARY[m].name, "fix": LIBRARY[m].fix} for m in mids] if show_detail else [],
        "rationale": d.rationale if show_detail else None,
        "solution": solution,
        "answered_question": {"title": q.title, "skill": q.skill, "kind": q.kind, "seconds": seconds, "target": q.target_seconds},
        "session": _public_session(sid),
        "events": db.events(sid)[ev_start:],
        "next_question": next_q.to_public() if next_q else None,
        "complete": bool(state.get("complete")),
        "progress": _progress(state),
    }


# ---------------------------------------------------------------- grading logic
def _adjudicate(q: bank.Question, d: agents.Diagnosis, explain_only: bool):
    """Return (verdict, error_type, misconception ids, label checks).

    The model's job was to *read*; the decision is made here, from the
    calculator checks for numeric questions and the key-point coverage for
    conceptual ones.
    """
    skill_ok = {m.id for m in LIBRARY.values() if m.skill in (q.skill, "any")} | set(q.misconceptions)
    llm_mids = [m for m in d.misconceptions if m in LIBRARY and m in skill_ok]

    if q.kind == "numeric" and not explain_only:
        stated = {v.label: v.value for v in d.stated_values if any(l.key == v.label for l in q.labels)}
        checks = bank.check_numbers(q, stated)
        wrong = [c for c in checks if c.status == "wrong"]
        missing_req = [c for c in checks if c.status == "missing" and
                       next(l.required for l in q.labels if l.key == c.label)]
        if wrong:
            matched = sorted({m for c in wrong for m in c.matches})
            all_slips = all(c.slip for c in wrong)
            if matched:
                etype = "conceptual"
                mids = matched + [m for m in llm_mids if m not in matched and m not in ("GEN_MEMORISED", "GEN_ARITHMETIC")]
            elif all_slips or d.unmatched_error == "arithmetic":
                # Deterministic slip detector (one digit off, transposed, decimal shift) wins over the model.
                etype, mids = "arithmetic", ["GEN_ARITHMETIC"]
            else:
                etype = "conceptual"
                mids = [m for m in llm_mids if m not in ("GEN_MEMORISED", "GEN_ARITHMETIC")]
            return "incorrect", etype, mids, checks
        if missing_req:
            return "incomplete", "incomplete", [m for m in llm_mids if m != "GEN_MEMORISED"], checks
        if d.reasoning_quality in ("weak", "none"):
            return "correct_unexplained", "unexplained", [], checks
        return "correct", "none", [], checks

    # conceptual question, or a "why" follow-up
    n = max(len(q.key_points), 1)
    cover = len(set(i for i in d.key_points_hit if 0 <= i < n)) / n
    mids = [m for m in llm_mids if m != "GEN_ARITHMETIC"]
    if explain_only:
        if cover >= 0.5 and d.reasoning_quality in ("strong", "adequate"):
            return "correct", "none", [], []
        return "correct_unexplained", "unexplained", ["GEN_MEMORISED"], []
    if mids or cover < 0.34 or d.reasoning_quality == "none":
        return "incorrect", "conceptual", mids, []
    if cover < 0.67 or d.reasoning_quality == "weak":
        return "incomplete", "incomplete", [], []
    return "correct", "none", [], []


def _choose_action(state: dict, q: bank.Question, verdict: str, explain_only: bool) -> tuple[str, bool]:
    """(action, resolved?) - resolved means the question is finished and the map updates."""
    if verdict == "redirect":
        return "redirect", False
    if state["mode"] == "diagnostic":
        return "diag_next", True  # one attempt per placement question
    if explain_only:
        return ("ack_next" if verdict == "correct" else "note_next"), True
    if verdict == "correct":
        can_whatif = (state["followups"] < config.MAX_FOLLOWUPS_PER_QUESTION and not state["current"].get("whatif")
                      and bank.TEMPLATES[q.template_id].vary is not None and q.kind == "numeric"
                      and _rng(state).random() < 0.5)
        return ("ack_whatif" if can_whatif else "ack_next"), True
    if verdict == "correct_unexplained":
        if state["followups"] < config.MAX_FOLLOWUPS_PER_QUESTION and q.kind == "numeric":
            return "probe_why", False
        return "note_next", True
    # incorrect / incomplete
    if state["attempts"] + 1 < config.MAX_ATTEMPTS_PER_QUESTION:
        return "nudge", False
    return "reveal", True


def _final_verdict(state: dict, verdict: str, explain_only: bool) -> str:
    """What the weakness map learns. The first attempt is what an interviewer actually sees."""
    first = state.get("first_verdict")
    if explain_only:
        return "correct" if verdict == "correct" else "correct_unexplained"
    if first in (None, verdict):
        return verdict
    if first in ("incorrect", "incomplete") and verdict == "correct":
        return "incomplete"  # got there with a nudge: partial credit
    return verdict if verdict != "correct" else first


# ---------------------------------------------------------------- interviewer
async def _interviewer_message(sid, state, q, verdict, action, checks, mids, wrapped, d, followup=None) -> str:
    persona = state["persona"]
    wrong_items = [c.name for c in checks if c.status == "wrong"]
    missing_items = [c.name for c in checks if c.status == "missing" and
                     next(l.required for l in q.labels if l.key == c.label)]
    ctx = {
        "action": action,
        "question": q.text,
        "verdict": verdict,
        "line_items_right": [c.name for c in checks if c.status == "correct"],
        "line_items_to_revisit": wrong_items + missing_items,
        "missing_key_points": [kp for i, kp in enumerate(q.key_points) if i not in set(d.key_points_hit)][:3]
        if q.kind == "conceptual" else [],
        "misconception_fix": [LIBRARY[m].fix for m in mids][:1] if action == "reveal" else [],
        "key_idea_to_name": q.key_points[:2] if action == "note_next" else [],
        "grader_note": d.rationale if action in ("probe_why",) else "",
        "followup_shown_on_screen": followup or "",
    }
    prompt = ("TURN CONTEXT (from the interview engine):\n" + json.dumps(ctx, indent=1) + "\n\n" + wrapped)

    stated_nums = [v.value for v in d.stated_values]
    allowed = list(q.params.values()) + stated_nums + _numbers_in_text(q.text)
    if action == "reveal":
        allowed += list(q.values.values()) + _numbers_in_text(" ".join(ctx["misconception_fix"]))
    forbidden = [] if action == "reveal" else list(q.values.values())

    agent = agents.interviewer(persona)
    note = ""
    for attempt in range(2):
        try:
            result, rec = await llm.run(agent, "Interviewer", prompt + note, session_id=sid)
        except Exception as e:
            if not llm.is_content_filter(e):
                raise
            db.add_event(sid, "Guard", "safety", "Provider content filter refused the interviewer prompt; used the safe message.",
                         {"layer": "provider"})
            break
        msg = result.output.message.strip()
        oc = guard.check_output(msg, allowed, forbidden)
        db.add_event(sid, "Interviewer", "llm", f"Drafted the reply ({action}).",
                     {"draft": msg, "filter_ok": oc.ok, "filter_reasons": oc.reasons, "model": rec.model_resolved}, rec)
        if oc.ok:
            return msg
        db.add_event(sid, "Guard", "safety", "Output blocked before it reached the candidate: " + "; ".join(oc.reasons),
                     {"draft": msg, "reasons": oc.reasons})
        note = ("\n\nYOUR PREVIOUS DRAFT WAS BLOCKED (" + "; ".join(oc.reasons) +
                "). Rewrite it using no numbers at all.")
    items = ", ".join(ctx["line_items_to_revisit"]) or "your reasoning"
    fb = FALLBACKS[action].format(items=items.lower())
    db.add_event(sid, "Guard", "safety", "Used the safe fallback message.", {"message": fb})
    return fb


def _numbers_in_text(text: str) -> list[float]:
    return guard._numbers_in(text)


# ---------------------------------------------------------------- end of session
async def end_session(sid: str) -> dict:
    s = db.session(sid)
    if s is None:
        raise ValueError("Session not found.")
    if s["ended"] and s["debrief"]:
        return _report(sid)
    pid = s["profile_id"]
    state = s["state"]
    ts = db.turns(sid)

    # ---- placement (diagnostic) -> plan; drills and mocks tick off the plan
    plan_event = None
    if s["mode"] == "diagnostic":
        results = dict(state.get("diag", {}).get("results", {}))
        if results:
            placed = {**db.get_profile_json(pid, "placement"), **results}
            db.set_profile_json(pid, "placement", placed)
            for sk, L in results.items():  # demonstrated levels count as achieved
                for lvl in range(1, L + 1):
                    db.set_key(pid, f"lvl:{sk}:{lvl}", max(db.get_key(pid, f"lvl:{sk}:{lvl}"), 0.8), n_inc=2)
            await build_plan(pid, sid)
            plan_event = "plan_created"
    else:
        plan = db.get_plan(pid)
        if plan and state.get("done_q", 0) >= 3:
            kind = "drill" if s["mode"] in ("drill", "practice") else "mock"
            skill = (state.get("target") or {}).get("skill") or state.get("focus")
            ticked = planmod.mark_done(plan, kind, skill if kind == "drill" else None)
            if ticked:
                db.save_plan(pid, plan)
                plan_event = f"ticked: {ticked['title']}"
                db.add_event(sid, "Director", "plan", f"Plan task completed: {ticked['title']}.", {"task": ticked})
    levels_after = levels_for(pid)
    db.snapshot(pid, levels_after)

    m_end = db.mastery(pid)
    summary = {
        "mode": s["mode"],
        "questions": [{"title": t["question"][:80], "skill": bank.SKILLS.get(t["skill"], t["skill"]),
                       "verdict": t["verdict"], "misconceptions": t["misconceptions"] or [],
                       "evidence": (t["diagnosis"] or {}).get("diagnosis", {}).get("evidence_quote", ""),
                       "seconds": round(t["seconds"]) if t["seconds"] else None}
                      for t in ts if t["verdict"]],
        "misconceptions_seen": sorted({m for t in ts for m in (t["misconceptions"] or [])}),
        "mastery_start": {bank.SKILLS[k]: round(v["p"] * 100) for k, v in s["mastery_start"].items() if k in bank.SKILLS},
        "mastery_end": {bank.SKILLS[k]: round(v["p"] * 100) for k, v in m_end.items()},
        "levels_end": {bank.SKILLS[k]: bank.LEVELS.get(v, "Foundations") for k, v in levels_after.items()},
    }
    debrief = None
    if summary["questions"]:
        try:
            _budget_check(sid, pid, {**state, "last_turn": 0})
            result, rec = await llm.run(agents.coach(), "Coach", json.dumps(summary, indent=1), session_id=sid)
            deb = result.output
            text = " ".join([deb.headline, *deb.strengths, deb.next_session,
                             *[f.why_it_matters + " " + f.drill for f in deb.focus_areas]])
            allowed = [float(x) for x in list(summary["mastery_start"].values()) + list(summary["mastery_end"].values())]
            allowed += [float(q["seconds"]) for q in summary["questions"] if q["seconds"]] + [float(len(summary["questions"]))]
            allowed += _numbers_in_text(json.dumps(summary))
            oc = guard.check_output(text, allowed, [])
            db.add_event(sid, "Coach", "llm", "Wrote the debrief.", {"filter_ok": oc.ok, "reasons": oc.reasons}, rec)
            if oc.ok:
                debrief = deb.model_dump()
                debrief["focus_areas"] = [{**f, "name": LIBRARY[f["misconception_id"]].name}
                                          for f in debrief["focus_areas"] if f["misconception_id"] in LIBRARY]
            else:
                db.add_event(sid, "Guard", "safety", "Coach debrief blocked: " + "; ".join(oc.reasons), {})
        except BudgetExceeded as e:
            db.add_event(sid, "Guard", "safety", "Coach skipped: " + str(e), {})
    if debrief is None:
        debrief = _fallback_debrief(summary)
    debrief["plan_event"] = plan_event
    db.end_session(sid, debrief)
    db.add_event(sid, "Director", "end", "Session ended.", {})
    return _report(sid)


async def build_plan(pid: str, sid: str | None = None) -> dict:
    """Code computes the plan; the Planner agent only writes the plain-English summary of it."""
    intake = _intake(pid)
    levels = levels_for(pid)
    plan = planmod.build(intake, levels, weak_subskills(pid))
    facts = {k: plan[k] for k in ("group_name", "days_left", "hours_per_week", "overall_label", "target_label", "drills",
                                  "mocks", "questions", "hours_planned", "hours_available", "compressed",
                                  "minutes_per_practice_day")}
    facts["skills"] = [{"skill": r["name"], "now": bank.LEVELS.get(r["current"], "Foundations"),
                        "target": bank.LEVELS[r["target"]], "drills": r["drills"],
                        "weak_subskills": [w["name"] for w in r["weak_subskills"]]} for r in plan["skills"]]
    summary = None
    try:
        if sid:
            result, rec = await llm.run(agents.planner(), "Planner", json.dumps(facts, indent=1), session_id=sid)
            text = " ".join([result.output.headline, result.output.why, result.output.first_step])
            oc = guard.check_output(text, _numbers_in_text(json.dumps(facts)) + [float(x) for x in range(0, 13)], [])
            db.add_event(sid, "Planner", "llm", "Wrote the action-plan summary.", {"filter_ok": oc.ok, "reasons": oc.reasons}, rec)
            if oc.ok:
                summary = result.output.model_dump()
    except Exception as e:  # the plan itself never depends on the model
        if sid:
            db.add_event(sid, "Guard", "safety", f"Planner summary skipped ({type(e).__name__}); used the computed summary.", {})
    plan["summary"] = summary or {
        "headline": f"You're at {plan['overall_label']} overall. Target: {plan['target_label']} in {plan['days_left']} days.",
        "why": f"{plan['drills']} targeted drills and {plan['mocks']} mock interviews, about {plan['hours_planned']} hours in total.",
        "first_step": f"Start with: {next((t['title'] for t in plan['tasks'] if not t['done']), 'a mock interview')}.",
    }
    db.save_plan(pid, plan)
    return plan


def _fallback_debrief(summary: dict) -> dict:
    mis = summary["misconceptions_seen"]
    return {
        "headline": f"You answered {len(summary['questions'])} questions this session.",
        "strengths": [],
        "focus_areas": [{"misconception_id": m, "name": LIBRARY[m].name, "why_it_matters": LIBRARY[m].tell, "drill": LIBRARY[m].fix}
                        for m in mis[:3] if m in LIBRARY],
        "next_session": "Run a drill session on your weakest skill.",
    }


def _report(sid: str) -> dict:
    s = db.session(sid)
    pid = s["profile_id"]
    ts = db.turns(sid)
    start_levels = s["state"].get("levels_start", {})
    end_levels = levels_for(pid)
    plan = db.get_plan(pid)
    return {
        "session": {"id": sid, "mode": s["mode"], "persona": s["persona"], "started": s["started"], "ended": s["ended"]},
        "debrief": s["debrief"],
        "mastery_start": s["mastery_start"],
        "mastery_end": db.mastery(pid),
        "levels_start": start_levels, "levels_end": end_levels,
        "level_ups": [{"skill": k, "name": bank.SKILLS[k], "from": bank.LEVELS.get(start_levels.get(k, 0), "Foundations"),
                       "to": bank.LEVELS.get(v, "Foundations")} for k, v in end_levels.items() if v > start_levels.get(k, 0)],
        "placement": s["state"].get("diag", {}).get("results") if s["mode"] == "diagnostic" else None,
        "plan_progress": planmod.progress(plan) if plan else None,
        "turns": [{"question": t["question"], "verdict": t["verdict"], "skill": t["skill"],
                   "misconceptions": t["misconceptions"], "seconds": t["seconds"]} for t in ts],
        "usage": db.session_usage(sid),
        "events": db.events(sid),
    }


def weakness_map(pid: str) -> dict:
    m = db.mastery(pid)
    keys = db.mastery_all(pid)
    mis = db.misconceptions(pid)
    ts = db.profile_turns(pid)
    levels = levels_for(pid)
    speed = {}
    for s in bank.SKILLS:
        secs = [t["seconds"] for t in ts if t["skill"] == s and t["seconds"]]
        speed[s] = round(sum(secs) / len(secs)) if secs else None
    subs = {}
    for sub, (sk, name) in bank.SUBSKILLS.items():
        k = keys.get(f"sub:{sub}")
        if k:
            subs.setdefault(sk, []).append({"id": sub, "name": name, "p": k["p"], "n": k["n"]})
    hist: dict[str, list] = {}
    for h in db.history(pid):
        hist.setdefault(h["key"], []).append({"ts": h["ts"], "p": h["p"], "level": h["level"]})
    return {
        "skills": [{"key": k, "name": bank.SKILLS[k], "p": v["p"], "n": v["n"], "label": mastery.level(v["p"], v["n"]),
                    "level": levels.get(k, 0), "level_name": bank.LEVELS.get(levels.get(k, 0), "Foundations"),
                    "target": mastery.target_level(levels.get(k, 0)),
                    "avg_seconds": speed[k], "subskills": sorted(subs.get(k, []), key=lambda x: x["p"]),
                    "history": hist.get(k, [])} for k, v in m.items()],
        "misconceptions": [{"id": x["mid"], "name": LIBRARY[x["mid"]].name, "skill": LIBRARY[x["mid"]].skill,
                            "hits": x["hits"], "active": x["active"], "clean_streak": x["clean_streak"],
                            "fix": LIBRARY[x["mid"]].fix, "evidence": x["evidence"]}
                           for x in mis if x["mid"] in LIBRARY and x["hits"] > 0],
        "answered": len([t for t in ts if t["verdict"]]),
    }


def dashboard(pid: str) -> dict:
    """Everything the home screen needs: level, plan progress, today's tasks, streak, skills, next step."""
    intake = _intake(pid)
    plan = db.get_plan(pid)
    wm = weakness_map(pid)
    with db.conn() as c:
        days = [r["d"] for r in c.execute(
            """SELECT DISTINCT date(s.started, 'unixepoch', 'localtime') d FROM sessions s
               JOIN turns t ON t.session_id=s.id WHERE s.profile_id=? ORDER BY d DESC""", (pid,))]
        n_sessions = c.execute("SELECT COUNT(*) n FROM sessions WHERE profile_id=? AND ended IS NOT NULL", (pid,)).fetchone()["n"]
        diag_done = c.execute("SELECT COUNT(*) n FROM sessions WHERE profile_id=? AND mode='diagnostic' AND ended IS NOT NULL",
                              (pid,)).fetchone()["n"] > 0
    import datetime as _dt
    streak, day = 0, _dt.date.today()
    dayset = set(days)
    if day.isoformat() not in dayset:
        day -= _dt.timedelta(days=1)
    while day.isoformat() in dayset:
        streak += 1
        day -= _dt.timedelta(days=1)
    tech = [s["level"] for s in wm["skills"] if s["key"] in bank.TECHNICAL]
    overall = int(sum(tech) / len(tech) + 0.5) if tech else 0
    return {
        "intake": intake, "needs_intake": not intake, "diagnostic_done": diag_done,
        "overall_level": overall, "overall_label": bank.LEVELS.get(overall, "Foundations"),
        "target_label": bank.LEVELS[mastery.target_level(overall)],
        "plan": plan, "progress": planmod.progress(plan) if plan else None,
        "streak": streak, "sessions": n_sessions, "answered": wm["answered"],
        "skills": wm["skills"], "misconceptions": wm["misconceptions"],
        "group_name": bank.GROUPS.get(intake.get("group", "generalist"), "Generalist"),
    }
