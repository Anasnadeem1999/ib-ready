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
import re
import time

from . import agents, bank, config, db, guard, llm, mastery
from . import plan as planmod
from .misconceptions import LIBRARY

OPENERS = {
    "associate": "Hi, thanks for making time. We'll keep this conversational, with a few technicals, and I'll dig into "
                 "your reasoning as we go. Talk me through your thinking out loud. First one:",
    "vp": "Let's get into it. I'll move quickly and push on anything vague, so be precise. Go:",
    "director": "Thanks for coming in. I want to get a sense of who you are and how you think, and we'll cover some "
                "technicals along the way. Let's start:",
    "md": "Good to meet you. I'm less interested in rehearsed answers than in how you think and why you're here. "
          "Let's talk:",
}
DIAGNOSTIC_OPENER = ("This is a quick check, not a test. I'll ask about 10 to 20 short questions on accounting, valuation, "
                     "DCF, M&A, LBOs{group} and fit. Each topic starts easy and only gets harder while you're getting "
                     "them right. Answer the way you would out loud, one try each, and it's fine to say you're not sure. "
                     "At the end you'll see where you stand and get a plan built around it.")


def level_phrase(level: int | None) -> str:
    """'Coffee-chat ready' -> 'coffee-chat level', for plain-language sentences."""
    name = bank.LEVELS.get(level or 0, bank.LEVEL0_LABEL)
    return name.removesuffix(" ready").lower() + " level"


def _topic(skill: str, sub: str | None) -> str:
    name = bank.SUBSKILLS.get(sub, ("", ""))[1] if sub else ""
    return f"{bank.SKILLS[skill]} ({name})" if name else bank.SKILLS[skill]
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
FINISHED_REASON = "This session is finished — see your results."
RESUME_WINDOW_SECONDS = 12 * 3600  # an unfinished session older than this is not offered for resume


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
        reason = f"Placement: {bank.SKILLS[skill]}, a {bank.LEVELS[lvl]} question."
    elif mode == "drill":
        tg = state["target"]
        t = mastery.pick_targeted(group, tg["skill"], tg["level"], tg["subskill"], asked, act, rng)
        sub = bank.SUBSKILLS.get(tg["subskill"], ("", ""))[1]
        reason = f"Practice target: {bank.SKILLS[tg['skill']]}" + (f" / {sub}" if sub else "") + f", {bank.LEVELS[tg['level']]} questions."
        if (tg["subskill"] and t.subskill != tg["subskill"]) or t.difficulty != tg["level"] or t.skill != tg["skill"]:
            reason += (f" No fresh question left for that exact target, so the closest one: "
                       f"{bank.SUBSKILLS.get(t.subskill, ('', bank.SKILLS[t.skill]))[1]}, {bank.LEVELS[t.difficulty]}.")
    elif mode == "practice":
        focus = state.get("focus") or "accounting"
        lvl = state.get("level") or mastery.target_level(levels_for(pid).get(focus, 0))
        t, served = mastery.pick_practice(group, focus, lvl, asked, act, rng)
        if state.get("focus_swapped"):
            reason = (f"Practice: Group specifics needs a coverage group (set one in your profile), "
                      f"so {bank.SKILLS[t.skill]} ({bank.LEVELS[t.difficulty]}) instead.")
        elif served is None:
            reason = f"Practice: {bank.SKILLS[focus]}, {bank.LEVELS[lvl]} questions only."
        elif t.skill != focus:
            reason = (f"Practice: no {bank.SKILLS[focus]} questions for this group, "
                      f"so {bank.SKILLS[t.skill]} ({bank.LEVELS[t.difficulty]}) instead.")
        else:
            reason = (f"Practice: {bank.SKILLS[focus]}. No fresh {bank.LEVELS[lvl]} question left, "
                      f"so the closest level with one ({bank.LEVELS[served]}).")
    else:  # mock
        levels = levels_for(pid)
        t = mastery.pick_mock(group, state["persona"], levels, bank.GROUP_WEIGHTS.get(group, {}), asked, act, rng,
                              state.get("focus"))
        reason = (f"Mock with the {agents.PERSONAS[state['persona']][0]}: "
                  f"{'fit question' if t.skill == 'fit' else bank.SKILLS[t.skill]}, a {bank.LEVELS[t.difficulty]} question.")
    hits = [x for x in t.misconceptions if x in act]
    if hits:
        reason += " Re-tests: " + ", ".join(LIBRARY[h].name for h in hits) + "."
    params = t.gen(rng)
    if t.kind == "behavioral":
        generalist = not group or group == "generalist"
        params = {"group": "investment banking" if generalist else bank.GROUPS.get(group, "this group").split(" (")[0]}
        if generalist:
            params["generalist"] = True
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


def budget_tokens(input_tokens: int, cached_tokens: int, output_tokens: int) -> float:
    """Tokens as budgets count them: cached input at a tenth, as it is priced (Lecture 11), so the
    caps track cost and a long cached playbook doesn't use up a normal session."""
    return (input_tokens - cached_tokens) + cached_tokens / 10 + output_tokens


def _budget_check(sid: str, pid: str, state: dict, debrief: bool = False) -> None:
    use = db.session_usage(sid)
    if not debrief and budget_tokens(use["input_tokens"], use["cached_tokens"], use["output_tokens"]) >= config.SESSION_TOKEN_BUDGET:
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


def _public_session(sid: str, s: dict | None = None) -> dict:
    s = s or db.session(sid)
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
        "interview_date": (lambda d: d.isoformat() if d else None)(planmod.parse_date(intake.get("interview_date"))),
        "hours_per_week": max(1.0, min(hours, 40.0)),
        "persona": intake.get("persona") if intake.get("persona") in agents.PERSONAS else "associate",
    }
    clean["interview_status"] = planmod.interview_status(clean["interview_date"])
    old = _intake(pid)
    db.set_profile_json(pid, "intake", {k: v for k, v in clean.items() if k != "interview_status"})
    if old and (old.get("group") or "generalist") != clean["group"]:
        # "Group specifics" means a different set of questions now: the old group's level doesn't carry over.
        placed = db.get_profile_json(pid, "placement")
        if "industry" in placed:
            placed.pop("industry")
            db.set_profile_json(pid, "placement", placed)
        db.reset_skill(pid, "industry")
        clean["group_changed"] = True
    return clean


def _task_target(pid: str, task_id: int | None) -> dict | None:
    """The plan task the candidate clicked "Start" on, if it exists and is still open."""
    if task_id is None:
        return None
    plan = db.get_plan(pid)
    return next((t for t in (plan or {}).get("tasks", []) if t.get("id") == task_id and not t.get("done")), None)


def start_session(profile_id: str, mode: str, persona: str, focus: str | None, level: int | None = None,
                  task_id: int | None = None) -> dict:
    task = _task_target(profile_id, task_id)
    if task is not None:  # a specific plan task decides the mode and the target
        mode = "drill" if task["type"] == "drill" else "mock"
    if mode not in ("diagnostic", "drill", "mock", "practice"):
        mode = "mock"
    if persona not in agents.PERSONAS:
        persona = "associate"
    if focus not in bank.SKILLS:
        focus = None
    if level not in (1, 2, 3):
        level = None
    intake = _intake(profile_id)
    group = intake.get("group")
    focus_swapped = focus == "industry" and not mastery.pool(group, skill="industry")
    if focus_swapped:
        focus = None  # a generalist has no group-specific questions
    if mode == "practice" and not focus:
        focus = "accounting"
    state = {"seed": random.randrange(1_000_000), "mode": mode, "persona": persona, "focus": focus, "level": level,
             "asked": [], "turns": 0, "last_turn": 0.0, "done_q": 0, "goal": GOALS.get(mode),
             "levels_start": levels_for(profile_id), "stage": intake.get("stage") or "first_rounds",
             "plan_task": task["id"] if task else None, "focus_swapped": focus_swapped}
    if mode == "diagnostic":
        skills = mastery.diagnostic_skills(group)
        state["diag"] = {"skills": skills, "i": 0, "level": mastery.first_level(group, skills[0]), "results": {},
                         "fit_seen": 0, "fit_pass": 0}
    if mode == "drill":
        if task is not None and task["type"] == "drill":
            state["target"] = {"skill": task["skill"], "subskill": task["subskill"], "level": task["level"] or 1,
                               "task": task["id"]}
        else:
            state["target"] = _drill_target(profile_id, focus, level)
        state["plan_task"] = state["target"].get("task")
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
        out["opener"] = (f"Let's practice {_topic(tg['skill'], tg['subskill'])} together. {GOALS['drill']} quick questions "
                         f"at {level_phrase(tg['level'])}. " + OPENERS[persona])
    elif mode == "practice":
        lvl = state.get("level") or mastery.target_level(state["levels_start"].get(focus, 0))
        out["opener"] = (f"Practice: {bank.SKILLS[focus]}, {level_phrase(lvl)} questions. "
                         "Take your time and talk me through your thinking.")
    else:
        out["opener"] = OPENERS[persona]
    out["events"] = db.events(sid)
    return out


def active_session(pid: str) -> dict:
    """The newest open, not-complete session (for resuming after a refresh), in start_session's shape."""
    for sid in db.open_sessions(pid, time.time() - RESUME_WINDOW_SECONDS):
        s = db.session(sid)
        if s is None or s["state"].get("complete") or "current" not in s["state"]:
            continue
        out = _public_session(sid, s)
        out["opener"] = None
        out["events"] = db.events(sid)
        out["transcript"] = [{"question": t["question"], "answer": t["answer"], "interviewer": t["interviewer"],
                              "verdict": t["verdict"]} for t in db.turns(sid)]
        return {"session": out}
    return {"session": None}


def _advance_diagnostic(pid: str, state: dict, passed: bool, sid: str) -> None:
    """Adaptive placement: climb a skill's levels while answers are right, then move to the next skill."""
    d = state["diag"]
    if d["i"] >= len(d["skills"]):
        state["complete"] = True
        return
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
                     f"Placed {bank.SKILLS[skill]} at {bank.LEVELS.get(placed, bank.LEVEL0_LABEL)}.",
                     {"skill": skill, "level": placed})
        d["i"] += 1
        if d["i"] >= len(d["skills"]):
            state["complete"] = True
        else:
            d["level"] = mastery.first_level(group, d["skills"][d["i"]])


_INFLIGHT: set[str] = set()  # sessions with a turn being graded right now
_ENDING: set[str] = set()    # sessions whose end-of-session work is running right now
_INFLIGHT_PROFILES: set[str] = set()  # one graded turn per profile at a time (protects the token budget)


async def answer(sid: str, raw_text: str, seconds: float | None, pid: str | None = None) -> dict:
    """One candidate turn. Only one turn per session can run at a time."""
    if sid in _ENDING:
        return {"blocked": True, "reason": FINISHED_REASON, "session": _public_session(sid), "events": [],
                "complete": True}
    if sid in _INFLIGHT:
        db.add_event(sid, "Guard", "safety", "Blocked: a second answer arrived while the first was still being graded.",
                     {"type": "rate"})
        return {"blocked": True, "reason": "Still grading your last answer.", "session": _public_session(sid),
                "events": db.events(sid)[-1:]}
    if pid is None:
        s0 = db.session(sid)
        pid = s0["profile_id"] if s0 else None
    if pid in _INFLIGHT_PROFILES:
        return {"blocked": True, "reason": "You're already answering in another tab. One answer at a time.",
                "session": _public_session(sid), "events": []}
    _INFLIGHT.add(sid)
    if pid:
        _INFLIGHT_PROFILES.add(pid)
    try:
        return await _answer(sid, raw_text, seconds)
    except Exception:
        s = db.session(sid)
        if s:  # rate limit counts from the END of the last turn, even a failed one
            st = s["state"]
            st["last_turn"] = time.time()
            db.save_state(sid, st)
        raise
    finally:
        _INFLIGHT.discard(sid)
        _INFLIGHT_PROFILES.discard(pid)


def _normalize(state: dict) -> dict:
    """Fill keys added after a session was created (older rows in an existing database)."""
    state.setdefault("done_q", 0)
    state.setdefault("goal", GOALS.get(state.get("mode")))
    state.setdefault("followups", 0)
    state.setdefault("attempts", 0)
    state.setdefault("first_verdict", None)
    state.setdefault("phase", "answer")
    state.setdefault("last_turn", 0.0)
    state.setdefault("turns", 0)
    state.setdefault("asked", [])
    return state


async def _answer(sid: str, raw_text: str, seconds: float | None) -> dict:
    s = db.session(sid)
    if s is None:
        raise ValueError("Session not found.")
    pid, state = s["profile_id"], _normalize(s["state"])
    if s["ended"] or state.get("complete"):
        # finished: nothing more to grade, and no model call
        return {"blocked": True, "reason": FINISHED_REASON, "session": _public_session(sid, s), "events": [],
                "complete": True}
    ev_start = db.max_event_id(sid)

    try:
        _budget_check(sid, pid, state)
    except BudgetExceeded as e:
        db.add_event(sid, "Guard", "safety", "Blocked: " + str(e), {"type": "budget"})
        return {"blocked": True, "reason": str(e), "session": _public_session(sid),
                "events": db.events(sid, ev_start)}

    state["turns"] += 1
    state["last_turn"] = time.time()
    q = _current(state)
    explain_only = state["phase"] == "why"

    # ---------- 1. input guard
    ic = guard.check_input(raw_text)
    soft = list(getattr(ic, "soft_flags", []) or [])
    if ic.flags or ic.truncated or soft:
        db.add_event(sid, "Guard", "safety",
                     "Input flagged: " + ", ".join(ic.flags + soft + (["answer truncated"] if ic.truncated else [])),
                     {"flags": ic.flags, "soft_flags": soft, "truncated": ic.truncated,
                      "zero_width_removed": ic.zero_width_removed})
    if not ic.text:
        return {"blocked": True, "reason": "Type an answer first.", "session": _public_session(sid),
                "events": db.events(sid, ev_start)}
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
                "session": _public_session(sid), "events": db.events(sid, ev_start), "next_question": None}
    d: agents.Diagnosis = result.output

    # ---------- 3. deterministic adjudication (the code makes the call)
    verdict, error_type, mids, checks = _adjudicate(q, d, explain_only)
    length = length_check(q, ic.text, explain_only)
    locked_verdict = verdict
    manipulated = d.manipulation_attempt or any(
        f in ic.flags for f in ("grade manipulation", "instruction override", "score tampering", "role hijack",
                                "answer/prompt extraction", "system/developer prompt reference", "fake message tags"))
    no_content = (not d.key_points_hit and not any(c.status != "missing" for c in checks))
    if manipulated and no_content:
        verdict = "redirect"  # nothing to grade but the attack itself: no credit, no attempt used

    # ---------- 4. choose the next action
    action, resolved = _choose_action(state, q, verdict, explain_only)

    # The trace goes to the browser, so it may only carry the answer key once it is earned (resolved or
    # revealed). Until then the specialist's rationale and the calculator's expected values are kept
    # server-side only (events.private, for the owner's export).
    earned = resolved or action == "reveal"
    spec_detail = {"misconceptions": d.misconceptions, "stated": [v.model_dump() for v in d.stated_values],
                   "manipulation": d.manipulation_attempt, "model": rec.model_resolved}
    if earned:
        spec_detail["rationale"] = d.rationale
    db.add_event(sid, agents.SPECIALISTS[spec_key][0], "llm", f"Diagnosed the answer: reasoning {d.reasoning_quality}.",
                 spec_detail, rec, private=None if earned else {"rationale": d.rationale})
    if deps.tool_calls:
        full = [c.to_dict() for c in checks]
        shown = full if earned else [{k: v for k, v in c.items() if k != "expected"} for c in full]
        db.add_event(sid, "Calculator", "tool", "check_numbers: " + ", ".join(
            f"{c.name} {c.status}" + (f" ({', '.join(c.matches)})" if c.matches else "") for c in checks if c.status != "missing"),
            {"checks": shown}, private=None if earned else {"checks": full})
    if manipulated:
        db.add_event(sid, "Guard", "safety",
                     "Grader lock: manipulation attempt detected. The grade comes only from the calculator checks.",
                     {"llm_flag": d.manipulation_attempt, "filter_flags": ic.flags, "verdict_after_lock": locked_verdict})

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
    if action == "ack_whatif" and nq is None:  # this template had no what-if after all
        action = "ack_next"
        if state.get("goal") and state["done_q"] >= state["goal"]:
            state["complete"] = True
    if state["mode"] == "diagnostic" and action != "redirect":
        # placement is a quick screen: a short neutral acknowledgement, no coaching mid-test (and no extra model call)
        msg = _rng(state).choice(DIAG_ACKS[final_verdict in ("correct", "correct_unexplained")])
        if state.get("complete"):
            msg = "That's the placement done. Let's look at where you stand."
    else:
        msg = await _interviewer_message(sid, state, q, verdict, action, checks, mids, wrapped, d, error_type=error_type,
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
    state["last_turn"] = time.time()  # rate limit counts from the END of the turn
    db.save_state(sid, state)

    # ---------- 8. persist the turn
    use_turn = rec.to_dict()
    db.add_turn(sid, template_id=q.template_id, skill=q.skill, kind=q.kind, question=q.text, answer=ic.text,
                seconds=seconds, verdict=verdict if verdict != "redirect" else None, error_type=error_type,
                misconceptions=mids, interviewer=msg,
                diagnosis={"diagnosis": d.model_dump(), "checks": [c.to_dict() for c in checks],
                           "action": action, "final_verdict": final_verdict, "explain_only": explain_only,
                           "flags": ic.flags, "length": length if verdict != "redirect" else None},
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
        "checks": [{"name": c.name, "status": c.status, "stated": c.stated, "hedged": getattr(c, "hedged", False),
                    "expected": c.expected if show_detail else None,
                    "required": next(l.required for l in q.labels if l.key == c.label)} for c in checks],
        "misconceptions": [{"id": m, "name": LIBRARY[m].name, "fix": LIBRARY[m].fix} for m in mids] if show_detail else [],
        "rationale": (grading_note(q, checks, error_type) or d.rationale) if show_detail else None,
        "note": grading_note(q, checks, error_type),
        "length": length if verdict != "redirect" else None,
        "solution": solution,
        "answered_question": {"title": q.title, "skill": q.skill, "kind": q.kind, "seconds": seconds, "target": q.target_seconds},
        "session": _public_session(sid, {**s, "state": state}),
        "events": db.events(sid, ev_start),
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
        stated, hedged = _committed_values(q, d)
        checks = bank.check_numbers(q, stated)
        for i, c in enumerate(checks):
            if c.label in hedged:  # two different answers for one line item: no credit for it
                checks[i] = bank.LabelCheck(c.label, c.name, hedged[c.label][-1], "wrong", c.expected, [])
                checks[i].hedged = True
        required = {l.key: l.required for l in q.labels}
        wrong_req = [c for c in checks if c.status == "wrong" and required[c.label]]
        wrong_opt = [c for c in checks if c.status == "wrong" and not required[c.label]]
        missing_req = [c for c in checks if c.status == "missing" and required[c.label]]
        concept_mids = [m for m in llm_mids if m not in ("GEN_MEMORISED", "GEN_ARITHMETIC")]
        if wrong_req:
            matched = sorted({m for c in wrong_req + wrong_opt for m in c.matches})
            if matched:
                return "incorrect", "conceptual", matched + [m for m in concept_mids if m not in matched], checks
            real = [c for c in wrong_req if not getattr(c, "hedged", False)]
            if len(real) < len(wrong_req) and all(_near_miss(q, c) for c in real):
                return "incomplete", "hedged", [], checks  # nudge: "commit to one answer"
            wrong_req = real
            if all(_near_miss(q, c) for c in wrong_req):
                # Close to the truth and no trap explains it: interview-style rounding. Don't invent a cause.
                return "incomplete", "rounding", [], checks
            if all(c.slip for c in wrong_req) or d.unmatched_error == "arithmetic":
                # Deterministic slip detector (one digit off, transposed, decimal shift) wins over the model.
                return "incorrect", "arithmetic", ["GEN_ARITHMETIC"], checks
            return "incorrect", "conceptual", concept_mids, checks
        if missing_req:
            return "incomplete", "incomplete", [m for m in llm_mids if m != "GEN_MEMORISED"], checks
        if wrong_opt:
            # Every required number is right; only a supporting line item is off: nudge on that line, don't fail.
            matched = sorted({m for c in wrong_opt for m in c.matches})
            if matched:
                return "incomplete", "conceptual", matched, checks
            if any(getattr(c, "hedged", False) for c in wrong_opt):
                return "incomplete", "hedged", [], checks
            return "incomplete", ("rounding" if all(_near_miss(q, c) for c in wrong_opt) else "incomplete"), [], checks
        # Right numbers, but the answer also states a wrong idea that the specialist flagged and quoted
        # (e.g. "the unlevered beta is usually higher"): the claim is what an interviewer would catch.
        claimed = [m for m in concept_mids if m in q.misconceptions or LIBRARY[m].skill == q.skill]
        if claimed and d.evidence_quote.strip():
            return "incomplete", "conceptual", claimed, checks
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
    if q.kind == "behavioral":
        # Fit answers: a flagged habit means "nudge", not "fail", unless the answer has little substance.
        mids = [m for m in llm_mids if m.startswith("FIT_")]
        if cover < 0.34 or d.reasoning_quality == "none":
            return "incorrect", "conceptual", mids, []
        if mids or cover < 0.67 or d.reasoning_quality == "weak":
            return "incomplete", "incomplete", mids, []  # the ids still feed the weakness map
        return "correct", "none", [], []
    if mids or cover < 0.25 or d.reasoning_quality == "none":
        return "incorrect", "conceptual", mids, []
    if cover < 0.67 or d.reasoning_quality == "weak":
        # thin but right (at least a quarter of the key points, no wrong idea): nudge, don't fail
        return "incomplete", "incomplete", [], []
    return "correct", "none", [], []


def _committed_values(q: bank.Question, d) -> tuple[dict[str, float], dict[str, list[float]]]:
    """The number the candidate committed to per label, and the labels they hedged on
    ("6 or maybe 7.5"): more than one distinct value (beyond the label's tolerance) for one label."""
    labels = {l.key: l for l in q.labels}
    seen: dict[str, list[float]] = {}
    for v in d.stated_values:
        if v.label in labels:
            vals = seen.setdefault(v.label, [])
            if not any(labels[v.label].close(v.value, x) for x in vals):
                vals.append(v.value)
    stated = {k: vals[0] for k, vals in seen.items() if len(vals) == 1}
    return stated, {k: vals for k, vals in seen.items() if len(vals) > 1}


def hedge_note(checks: list) -> str:
    items = [c.name.lower() for c in checks if getattr(c, "hedged", False)]
    return f"You gave two different answers for {', '.join(items) or 'one line item'}. Commit to one."


def grading_note(q: bank.Question, checks: list, error_type: str | None) -> str | None:
    """The neutral note shown instead of a model rationale for rounding and hedging."""
    if error_type == "rounding":
        return rounding_note(q, checks)
    if error_type == "hedged":
        return hedge_note(checks)
    return None


# ---------------------------------------------------------------- delivery: answer length (code, not the model)
CONCISE_MIN_WORDS = 45   # about 20 seconds spoken: the floor for any technical answer
CONCISE_FACTOR = 1.75    # room over the model answer before it counts as long
CONCISE_TIPS = {
    "numeric": "Lead with the number, then give one line of why. Stop there and let the interviewer ask for more.",
    "conceptual": "Answer in one sentence first, then add two or three supporting points. Stop there and let the interviewer ask for more.",
}


def length_check(q: bank.Question, text: str, explain_only: bool = False) -> dict | None:
    """Word count against a target built from the model answer. Coaching only: it never changes the grade.

    Fit answers are exempt (they should run about two minutes), and so is the short "why" follow-up.
    """
    if q.kind not in CONCISE_TIPS or explain_only:
        return None
    words = len(text.split())
    target = max(CONCISE_MIN_WORDS, 5 * round(CONCISE_FACTOR * len(q.solution.split()) / 5))
    too_long = words > target
    return {"words": words, "target": target, "too_long": too_long,
            "tip": CONCISE_TIPS[q.kind] if too_long else None}


def delivery_summary(questions: list[dict]) -> dict | None:
    """Session-level read on answer length, from the per-answer checks."""
    rated = [q for q in questions if q.get("word_target")]
    if not rated:
        return None
    long = [q for q in rated if q.get("too_long")]
    avg = lambda k, xs: round(sum(x[k] for x in xs) / len(xs))  # noqa: E731
    if long:
        tip = ("Your long answers averaged " + str(avg("words", long)) + " words against a target of about "
               + str(avg("word_target", long)) + ". " + CONCISE_TIPS["conceptual"])
    else:
        tip = "Your answers were the right length. Interviewers notice that."
    return {"long": len(long), "of": len(rated), "tip": tip}


def concise_trend(pid: str, last: int = 20) -> dict | None:
    """Share of the candidate's recent technical answers that ran long, across sessions."""
    checks = []
    for t in db.profile_turns(pid):
        try:
            ln = json.loads(t["diagnosis"] or "{}").get("length")
        except (TypeError, ValueError):
            ln = None
        if ln:
            checks.append(bool(ln.get("too_long")))
    if not checks:
        return None
    recent, before = checks[-last:], checks[:-last][-last:]
    return {"answers": len(recent), "long": sum(recent),
            "pct_long": round(100 * sum(recent) / len(recent)),
            "pct_long_before": round(100 * sum(before) / len(before)) if before else None}


def _near_miss(q: bank.Question, c) -> bool:
    """Within twice the label's tolerance of the truth: a rounding miss, not a method error."""
    lab = next((l for l in q.labels if l.key == c.label), None)
    if lab is None or c.stated is None or c.expected is None or getattr(c, "hedged", False):
        return False
    s, t = (c.stated, c.expected) if lab.is_signed else (abs(c.stated), abs(c.expected))
    return abs(s - t) <= 2 * max(lab.tol_abs, lab.tol_rel * abs(t))


def rounding_note(q: bank.Question, checks: list) -> str:
    items = [c.name for c in checks if c.status == "wrong" and _near_miss(q, c)]
    return "Close. Check your rounding" + (f" on {', '.join(items).lower()}" if items else "") + "."


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
async def _interviewer_message(sid, state, q, verdict, action, checks, mids, wrapped, d, followup=None,
                               error_type: str | None = None) -> str:
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
        if q.kind in ("conceptual", "behavioral") else [],
        "misconception_fix": [LIBRARY[m].fix for m in mids][:1] if action == "reveal" else [],
        "key_idea_to_name": q.key_points[:2] if action == "note_next" else [],
        "grader_note": d.rationale if action in ("probe_why",) else "",
        # right numbers but a wrong idea: name the concept to revisit (names only, no numbers)
        "concept_to_revisit": [LIBRARY[m].name for m in mids if m in LIBRARY][:1]
        if action == "nudge" and error_type == "conceptual" else [],
        "rounding_note": rounding_note(q, checks) if error_type == "rounding" else "",
        "hedge_note": hedge_note(checks) if error_type == "hedged" else "",
        "followup_shown_on_screen": followup or "",
    }
    prompt = ("TURN CONTEXT (from the interview engine):\n" + json.dumps(ctx, indent=1) + "\n\n" + wrapped)

    stated_nums = [v.value for v in d.stated_values]
    allowed = list(q.params.values()) + stated_nums + _numbers_in_text(q.text)
    if q.kind == "behavioral":  # a fit reply may echo the candidate's own numbers ("my 3 internships")
        allowed += _numbers_in_text(wrapped)
    if action == "reveal":
        allowed += list(q.values.values()) + _numbers_in_text(" ".join(ctx["misconception_fix"]))
    forbidden = [] if action == "reveal" else list(q.values.values())

    agent = _interviewer_agent(persona, state.get("stage") or "first_rounds")
    note = ""
    for attempt in range(2):
        try:
            result, rec = await llm.run(agent, "Interviewer", prompt + note, session_id=sid)
        except Exception as e:
            # The grade and weakness-map update are already written, so the turn must finish:
            # any failure here (content filter, timeout, gateway error) falls back to a safe line.
            if llm.is_content_filter(e):
                db.add_event(sid, "Guard", "safety", "Provider content filter refused the interviewer prompt; used the safe message.",
                             {"layer": "provider"})
            else:
                db.add_event(sid, "Guard", "safety", f"Interviewer unavailable ({type(e).__name__}); used the safe message.",
                             {"layer": "model", "error": str(e)[:200]})
            break
        msg = result.output.message.strip()
        oc = guard.check_output(msg, allowed, forbidden)
        # a blocked draft never reaches the browser, not even in the trace (kept server-side for the export);
        # the filter's reasons can quote the leaked number, so the public copy drops numbers
        shown = _public_reasons(oc.reasons)
        db.add_event(sid, "Interviewer", "llm", f"Drafted the reply ({action}).",
                     {**({"draft": msg} if oc.ok else {}), "filter_ok": oc.ok, "filter_reasons": shown,
                      "model": rec.model_resolved}, rec,
                     private=None if oc.ok else {"draft": msg, "filter_reasons": oc.reasons})
        if oc.ok:
            return msg
        db.add_event(sid, "Guard", "safety", "Output blocked before it reached the candidate: " + "; ".join(shown),
                     {"reasons": shown}, private={"draft": msg, "reasons": oc.reasons})
        note = ("\n\nYOUR PREVIOUS DRAFT WAS BLOCKED (" + "; ".join(oc.reasons) +
                "). Rewrite it using no numbers at all.")
    items = ", ".join(ctx["line_items_to_revisit"]) or "your reasoning"
    fb = FALLBACKS[action].format(items=items.lower())
    if action == "nudge" and error_type == "rounding":
        fb = ctx["rounding_note"] + " Give me the number again, a little more precisely."
    elif action == "nudge" and error_type == "hedged":
        fb = ctx["hedge_note"] + " Which one is your final answer, and why?"
    elif action == "nudge" and ctx["concept_to_revisit"]:
        fb = f"Your numbers hold up. One thing you said needs another look: {ctx['concept_to_revisit'][0].lower()}. Walk me through that part again."
    db.add_event(sid, "Guard", "safety", "Used the safe fallback message.", {"message": fb})
    return fb


def _interviewer_agent(persona: str, stage: str):
    try:
        return agents.interviewer(persona, stage)
    except TypeError:  # agents.interviewer(persona) before the stage-aware prompt landed
        return agents.interviewer(persona)


def _public_reasons(reasons: list[str]) -> list[str]:
    """Filter reasons for the browser: drop any quoted number ("answer leak (1275)" -> "answer leak")."""
    out = []
    for r in reasons:
        r = re.sub(r"\s*\([^)]*\d[^)]*\)", "", r)
        out.append(re.sub(r"[-+$]?\d[\d,.]*%?", "a number", r))
    return out


def _numbers_in_text(text: str) -> list[float]:
    return guard._numbers_in(text)


# ---------------------------------------------------------------- end of session
class Busy(ValueError):
    """The session is being graded or wrapped up right now (HTTP 409)."""


PLAN_TICK_MIN_ANSWERS = 3  # a drill or mock counts toward the plan once this many questions were finished


async def end_session(sid: str, tz: int | None = None) -> dict:
    """Finish a session. Safe to call twice or concurrently: the side effects run once."""
    s = db.session(sid)
    if s is None:
        raise ValueError("Session not found.")
    if s["ended"] and s["debrief"]:
        return _report(sid, tz)
    if sid in _ENDING:
        raise Busy("This session is already being wrapped up.")
    if sid in _INFLIGHT:
        raise Busy("Still grading your last answer. Try again in a moment.")
    _ENDING.add(sid)
    try:
        return await _end_session(s, tz)
    finally:
        _ENDING.discard(sid)


async def _finalize(s: dict, state: dict, tz: int | None) -> str | None:
    """Placement -> plan, or tick the plan; snapshot the skills. Runs once per session (state['finalized'])."""
    sid, pid = s["id"], s["profile_id"]
    today = planmod.user_today(tz)
    plan_event = None
    if s["mode"] == "diagnostic":
        d = state.get("diag", {})
        skills = d.get("skills", [])
        results = dict(d.get("results", {}))
        group = _intake(pid).get("group")
        partial: list[str] = []
        if not state.get("complete") and d.get("i", 0) < len(skills):
            cur = skills[d["i"]]
            # credit for a skill in progress: levels already climbed count
            if cur != "fit" and d.get("level", 0) > mastery.first_level(group, cur):
                results[cur] = d["level"] - 1
        if results:  # at least one skill placed (an empty placement changes nothing)
            old = db.get_profile_json(pid, "placement")
            demonstrated = dict(results)
            if not state.get("complete"):
                partial = [sk for sk in skills if sk not in results]
                for sk in partial:
                    results.setdefault(sk, int(old.get(sk, 0)))
            db.set_profile_json(pid, "placement", {**old, **results})
            state["placement_result"] = {"placed": demonstrated, "not_reached": partial}
            for sk, L in demonstrated.items():  # demonstrated levels count as achieved
                for lvl in range(1, L + 1):
                    db.set_key(pid, f"lvl:{sk}:{lvl}", max(db.get_key(pid, f"lvl:{sk}:{lvl}"), 0.8), n_inc=2)
            await build_plan(pid, sid, tz, partial=partial)
            plan_event = "plan_created_partial" if partial else "plan_created"
    else:
        plan = db.get_plan(pid)
        if plan and state.get("done_q", 0) >= PLAN_TICK_MIN_ANSWERS:
            kind = "drill" if s["mode"] in ("drill", "practice") else "mock"
            skill = (state.get("target") or {}).get("skill") or state.get("focus")
            ticked = planmod.mark_done(plan, kind, skill if kind == "drill" else None, today,
                                       task_id=state.get("plan_task"))
            if ticked:
                db.save_plan(pid, plan)
                plan_event = f"ticked: {ticked['title']}"
                db.add_event(sid, "Director", "plan", f"Plan task completed: {ticked['title']}.", {"task": ticked})
    db.snapshot(pid, levels_for(pid))
    return plan_event


async def _end_session(s: dict, tz: int | None) -> dict:
    sid, pid = s["id"], s["profile_id"]
    state = _normalize(s["state"])
    if not state.get("finalized"):
        plan_event = await _finalize(s, state, tz)
        state["finalized"] = True
        state["plan_event"] = plan_event
        db.save_state(sid, state)
    plan_event = state.get("plan_event")

    ts = db.turns(sid)
    levels_after = levels_for(pid)
    m_end = db.mastery(pid)
    summary = {
        "mode": s["mode"],
        "stage": state.get("stage"),
        "questions": [{"title": shorten(t["question"], 90), "skill": bank.SKILLS.get(t["skill"], t["skill"]), "kind": t["kind"],
                       "verdict": t["verdict"], "error_type": t["error_type"],
                       "line_items_right": [c["name"] for c in ((t["diagnosis"] or {}).get("checks") or [])
                                            if c.get("status") == "correct"],
                       "misconceptions": t["misconceptions"] or [],
                       "evidence": (t["diagnosis"] or {}).get("diagnosis", {}).get("evidence_quote", ""),
                       "seconds": round(t["seconds"]) if t["seconds"] else None,
                       **_length_fields((t["diagnosis"] or {}).get("length"))}
                      for t in ts if t["verdict"]],
        "misconceptions_seen": sorted({m for t in ts for m in (t["misconceptions"] or [])}),
        "mastery_start": {bank.SKILLS[k]: round(v["p"] * 100) for k, v in s["mastery_start"].items() if k in bank.SKILLS},
        "mastery_end": {bank.SKILLS[k]: round(v["p"] * 100) for k, v in m_end.items()},
        "levels_end": {bank.SKILLS[k]: bank.LEVELS.get(v, bank.LEVEL0_LABEL) for k, v in levels_after.items()},
    }
    debrief = None
    if summary["questions"]:
        allowed = [float(x) for x in list(summary["mastery_start"].values()) + list(summary["mastery_end"].values())]
        allowed += [float(q["seconds"]) for q in summary["questions"] if q["seconds"]] + [float(len(summary["questions"]))]
        allowed += _numbers_in_text(json.dumps(summary))
        try:
            _budget_check(sid, pid, {**state, "last_turn": 0, "turns": 0}, debrief=True)  # one capped call; daily caps still apply
            note = ""
            for _attempt in range(2):  # one retry when the output filter blocks the draft
                result, rec = await llm.run(agents.coach(), "Coach", json.dumps(summary, indent=1) + note, session_id=sid)
                deb = _map_debrief(result.output)
                text = " ".join([deb["headline"], *deb["went_well"], deb["next_step"], deb["encouragement"],
                                 *[w["why"] + " " + w["try_this"] for w in deb["work_on"]]])
                oc = guard.check_output(text, allowed, [])
                db.add_event(sid, "Coach", "llm", "Wrote the debrief.", {"filter_ok": oc.ok, "reasons": oc.reasons}, rec)
                if oc.ok:
                    debrief = deb
                    break
                db.add_event(sid, "Guard", "safety", "Coach debrief blocked: " + "; ".join(oc.reasons), {})
                note = ("\n\nYOUR PREVIOUS DEBRIEF WAS BLOCKED (" + "; ".join(oc.reasons) +
                        "). Rewrite it using no digits that are not in the summary.")
        except BudgetExceeded as e:
            db.add_event(sid, "Guard", "safety", "Coach skipped: " + str(e), {})
        except Exception as e:  # gateway down, no key, timeout: the session still ends, with the computed debrief
            db.add_event(sid, "Guard", "safety", f"Coach unavailable ({type(e).__name__}); used the computed debrief.",
                         {"error": str(e)[:200]})
    if debrief is None:
        debrief = _fallback_debrief(summary, db.get_plan(pid))
    # The next step is tied to the task the results card shows (code, not the coach, picks it: QA D-01).
    nxt = (planmod.progress(plan_now, planmod.user_today(tz))["next"] if (plan_now := db.get_plan(pid)) else None)
    if nxt:
        debrief["next_step"] = next_step_line(nxt)
    debrief["delivery"] = delivery_summary(summary["questions"])
    debrief["plan_event"] = plan_event
    db.end_session(sid, debrief)
    db.add_event(sid, "Director", "end", "Session ended.", {})
    return _report(sid, tz)


def shorten(text: str, n: int) -> str:
    """Cut at a word boundary with an ellipsis, never mid-word."""
    text = " ".join((text or "").split())
    if len(text) <= n:
        return text
    cut = text[:n].rsplit(" ", 1)[0].rstrip(",;:.")
    return cut + "…"


def _length_fields(ln: dict | None) -> dict:
    return {"words": ln["words"], "word_target": ln["target"], "too_long": ln["too_long"]} if ln else {}


def _map_debrief(output) -> dict:
    """Coach output -> the debrief contract, whatever version of agents.Debrief produced it."""
    d = output.model_dump() if hasattr(output, "model_dump") else dict(output)
    went = d.get("went_well") or d.get("strengths") or []
    work = d.get("work_on")
    if work is None:
        work = [{"misconception_id": f.get("misconception_id"), "why": f.get("why_it_matters"), "try_this": f.get("drill")}
                for f in d.get("focus_areas", [])]
    work_on = []
    for w in work:
        mid = w.get("misconception_id")
        if mid in LIBRARY:
            work_on.append({"misconception_id": mid, "name": LIBRARY[mid].name,
                            "why": w.get("why") or w.get("why_it_matters") or "",
                            "try_this": w.get("try_this") or w.get("drill") or LIBRARY[mid].fix})
    return {"headline": str(d.get("headline") or ""), "went_well": [str(x) for x in went][:3], "work_on": work_on[:2],
            "next_step": str(d.get("next_step") or d.get("next_session") or ""),
            "encouragement": str(d.get("encouragement") or "")}


def _fallback_debrief(summary: dict, plan: dict | None = None) -> dict:
    """The computed debrief (no model): warm, honest, and in the same shape as the coach's."""
    qs = summary["questions"]
    n = len(qs)
    right = [q for q in qs if q["verdict"] == "correct"]
    partly = [q for q in qs if q["verdict"] in ("correct_unexplained", "incomplete")]
    if n == 0:
        headline = "Thanks for stopping by. Nothing was graded this time, so there's no read on your skills yet."
    elif len(right) == n:
        headline = f"Thanks for putting in the reps today: all {n} of your answers were right."
    elif right:
        headline = f"Thanks for putting in the reps today: {len(right)} of {n} answers were fully right. Here is what to work on next."
    else:
        headline = "Thanks for putting in the reps today. Nothing was fully right yet, which is what practice is for. Here is what to work on next."
    went_well, seen = [], set()
    for q in right:
        if q["skill"] not in seen:
            seen.add(q["skill"])
            went_well.append(f"{q['skill']}: you got \"{shorten(q['title'], 60)}\" right.")
    if not went_well and partly:
        went_well.append(f"{partly[0]['skill']}: you were partly there on \"{shorten(partly[0]['title'], 60)}\".")
    counts: dict[str, int] = {}
    for q in qs:
        for m in q["misconceptions"]:
            counts[m] = counts.get(m, 0) + 1
    top = [m for m, _ in sorted(counts.items(), key=lambda kv: -kv[1]) if m in LIBRARY][:2]
    work_on = [{"misconception_id": m, "name": LIBRARY[m].name,
                "why": "Interviewers listen for this in the first minute, and it's easy to fix once you see it.",
                "try_this": LIBRARY[m].fix} for m in top]
    nxt = next((t for t in (plan or {}).get("tasks", []) if not t.get("done")), None)
    if nxt:
        next_step = f"Next on your plan: {nxt['title']}."
    elif top:
        next_step = f"Next time, practice {bank.SKILLS.get(LIBRARY[top[0]].skill, 'your weakest skill')} for a few short questions."
    else:
        next_step = "Try a mock interview to put it all together."
    if n and len(right) / n >= 0.7:
        encouragement = "Strong session. Keep the habit going and these answers will be automatic on the day."
    elif n:
        encouragement = "Every miss you find here is one you won't make in the real interview."
    else:
        encouragement = "One short practice session is enough to get started."
    return {"headline": headline, "went_well": went_well[:3], "work_on": work_on, "next_step": next_step,
            "encouragement": encouragement}


def next_task_title(task: dict) -> str:
    """The task's name as the UI shows it ("Accounting practice", "Mock interview")."""
    if task.get("type") == "mock":
        return "Final mock interview" if task.get("final") else "Mock interview"
    return f"{bank.SKILLS.get(task.get('skill'), 'Topic')} practice"


def next_task_why(task: dict | None) -> str:
    """One plain line on why the next plan task comes next. Code writes it from the task itself,
    so the sentence above the task card can never talk about a different topic (QA D-01)."""
    if not task:
        return ""
    if task.get("type") == "mock":
        if task.get("final"):
            return "It's your last full run-through before the interview, with mixed questions like the real thing."
        return "Mixed questions, like the real interview, so you practice switching between topics."
    sub = bank.SUBSKILLS.get(task.get("subskill") or "", (None, None))[1]
    if sub:
        return f"It's first on your plan because your answers showed {sub.lower()} needs work. Fixing it lifts the whole topic."
    lvl = bank.LEVELS.get(task.get("level") or 0)
    return ("It's first on your plan, which starts with the topics that need the most work"
            + (f". The questions are pitched at {lvl}." if lvl else "."))


def next_step_line(task: dict | None) -> str:
    return f"Next: {next_task_title(task)}. {next_task_why(task)}" if task else ""


async def build_plan(pid: str, sid: str | None = None, tz: int | None = None, partial: list[str] | None = None) -> dict:
    """Code computes the plan; the Planner agent only writes the plain-English summary of it.
    Completed tasks from the previous plan are kept (with their dates); only the remaining work is rebuilt."""
    intake = _intake(pid)
    levels = levels_for(pid)
    old = db.get_plan(pid)
    plan = planmod.build(intake, levels, weak_subskills(pid), planmod.user_today(tz))
    plan = planmod.carry_over(plan, old)
    plan["placement_partial_skills"] = partial if partial is not None else (old or {}).get("placement_partial_skills", [])
    facts = {k: plan[k] for k in ("group_name", "days_left", "hours_per_week", "overall_label", "target_label", "drills",
                                  "mocks", "questions", "hours_planned", "hours_available", "compressed",
                                  "minutes_per_practice_day", "final_prep", "interview_passed", "stage")}
    facts["skills"] = [{"skill": r["name"], "now": bank.LEVELS.get(r["current"], bank.LEVEL0_LABEL),
                        "target": bank.LEVELS[r["target"]], "drills": r["drills"],
                        "weak_subskills": [w["name"] for w in r["weak_subskills"]]} for r in plan["skills"]]
    summary = None
    try:
        if sid:
            s = db.session(sid)
            _budget_check(sid, pid, {**(s["state"] if s else {}), "turns": 0, "last_turn": 0})
            result, rec = await llm.run(agents.planner(), "Planner", json.dumps(facts, indent=1), session_id=sid)
            text = " ".join([result.output.headline, result.output.why, result.output.first_step])
            oc = guard.check_output(text, _numbers_in_text(json.dumps(facts)) + [float(x) for x in range(0, 13)], [])
            db.add_event(sid, "Planner", "llm", "Wrote the action-plan summary.", {"filter_ok": oc.ok, "reasons": oc.reasons}, rec)
            if oc.ok:
                summary = result.output.model_dump()
    except Exception as e:  # the plan itself never depends on the model
        if sid:
            db.add_event(sid, "Guard", "safety", f"Planner summary skipped ({type(e).__name__}); used the computed summary.", {})
    if plan.get("final_prep"):
        headline = "Your interview is almost here, so this is a short final-prep plan on your weakest areas."
    elif plan.get("interview_passed"):
        headline = ("Your interview date has passed, so this is a 3-week plan to stay sharp. "
                    "Update the date when you have the next one.")
    else:
        headline = f"You're at {plan['overall_label']} overall. Target: {plan['target_label']} in {plan['days_left']} days."
    plan["summary"] = summary or {
        "headline": headline,
        "why": f"{plan['drills']} short practice sessions and {plan['mocks']} mock interviews, about {plan['hours_planned']} hours in total.",
        "first_step": f"Start with: {next((t['title'] for t in plan['tasks'] if not t['done']), 'a mock interview')}.",
    }
    db.save_plan(pid, plan)
    return plan


def _report(sid: str, tz: int | None = None) -> dict:
    s = db.session(sid)
    pid = s["profile_id"]
    ts = db.turns(sid)
    start_levels = s["state"].get("levels_start", {})
    end_levels = levels_for(pid)
    plan = db.get_plan(pid)
    is_placement = s["mode"] == "diagnostic"
    return {
        "session": {"id": sid, "mode": s["mode"], "persona": s["persona"], "started": s["started"], "ended": s["ended"]},
        "debrief": s["debrief"],
        "is_placement": is_placement,
        # what was actually credited (includes a topic in progress when the placement ended early)
        "placement": ((s["state"].get("placement_result") or {}).get("placed")
                      or s["state"].get("diag", {}).get("results")) if is_placement else None,
        "placement_not_reached": (s["state"].get("placement_result") or {}).get("not_reached", []) if is_placement else [],
        "placement_partial": bool(is_placement and not s["state"].get("complete")),
        "touched_skills": sorted({t["skill"] for t in ts if t["verdict"] and t["skill"]}),
        "mastery_start": s["mastery_start"],
        "mastery_end": db.mastery(pid),
        "levels_start": start_levels, "levels_end": end_levels,
        "level_ups": [{"skill": k, "name": bank.SKILLS[k], "from": bank.LEVELS.get(start_levels.get(k, 0), bank.LEVEL0_LABEL),
                       "to": bank.LEVELS.get(v, bank.LEVEL0_LABEL)} for k, v in end_levels.items() if v > start_levels.get(k, 0)],
        "plan_progress": (prog := planmod.progress(plan, planmod.user_today(tz)) if plan else None),
        "next_why": next_task_why(prog["next"]) if prog else "",
        # questions finished (a second attempt or a follow-up is not a new question); "turns" counts every answer
        "questions_done": int(s["state"].get("done_q", 0)),
        "turns": [{"question": t["question"], "verdict": t["verdict"], "skill": t["skill"],
                   "misconceptions": t["misconceptions"], "seconds": t["seconds"]} for t in ts],
        "usage": db.session_usage(sid),
        "events": db.events(sid),
    }


def weakness_map(pid: str) -> dict:
    m = db.mastery(pid)
    keys = db.mastery_all(pid)
    mis = db.misconceptions(pid)
    avg_secs, answered = db.skill_speed_and_count(pid)
    levels = levels_for(pid)
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
                    "level": levels.get(k, 0), "level_name": bank.LEVELS.get(levels.get(k, 0), bank.LEVEL0_LABEL),
                    "target": mastery.target_level(levels.get(k, 0)),
                    "avg_seconds": round(avg_secs[k]) if avg_secs.get(k) else None,
                    "subskills": sorted(subs.get(k, []), key=lambda x: x["p"]),
                    "history": hist.get(k, [])} for k, v in m.items()],
        "misconceptions": [{"id": x["mid"], "name": LIBRARY[x["mid"]].name, "skill": LIBRARY[x["mid"]].skill,
                            "hits": x["hits"], "active": x["active"], "clean_streak": x["clean_streak"],
                            "fix": LIBRARY[x["mid"]].fix, "evidence": x["evidence"]}
                           for x in mis if x["mid"] in LIBRARY and x["hits"] > 0],
        "answered": answered,
    }


def _streak(pid: str, today, tz: int | None) -> int:
    """Consecutive days with at least one answer, ending today (or yesterday), in the user's time zone."""
    import datetime as _dt
    days = {planmod.local_date(ts, tz) for ts in db.answer_timestamps(pid)}
    day, streak = today, 0
    if day not in days:
        day -= _dt.timedelta(days=1)
    while day in days:
        streak += 1
        day -= _dt.timedelta(days=1)
    return streak


def dashboard(pid: str, tz: int | None = None) -> dict:
    """Everything the home screen needs: level, plan progress, today's tasks, streak, skills, next step."""
    today = planmod.user_today(tz)
    intake = _intake(pid)
    plan = db.get_plan(pid)
    wm = weakness_map(pid)
    placement = db.get_profile_json(pid, "placement")
    tech = [s["level"] for s in wm["skills"] if s["key"] in bank.TECHNICAL]
    overall = int(sum(tech) / len(tech) + 0.5) if tech else 0
    return {
        "intake": intake, "needs_intake": not intake,
        "diagnostic_done": bool(placement),  # at least one skill placed
        "can_retake_placement": True,
        "placement_partial": (plan or {}).get("placement_partial_skills") or [],
        "today": today.isoformat(),
        "interview_status": planmod.interview_status(intake.get("interview_date"), today),
        "overall_level": overall, "overall_label": bank.LEVELS.get(overall, bank.LEVEL0_LABEL),
        "target_label": bank.LEVELS[mastery.target_level(overall)],
        "plan": plan, "progress": planmod.progress(plan, today) if plan else None,
        "streak": _streak(pid, today, tz), "sessions": db.count_ended_sessions(pid), "answered": wm["answered"],
        "skills": wm["skills"], "misconceptions": wm["misconceptions"],
        "concise": concise_trend(pid),
        "group_name": bank.GROUPS.get(intake.get("group", "generalist"), "Generalist"),
    }
