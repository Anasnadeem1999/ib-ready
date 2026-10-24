"""Personal action plan: built by code from the diagnostic, the deadline and the hours available.

Every number in the plan is computed here, so it's explainable and testable:
  * target  = one level up per skill (Basic -> Intermediate -> Advanced), or Advanced practice if already there
  * drills  = 3 per level to climb + 1 per weak sub-skill (+1 maintenance drill per week at Advanced)
  * mocks   = 1 per week + 1 final mock before the interview
  * hours   = drills x 20 min + mocks x 30 min + 15% review time
If the hours needed exceed the hours available, the plan keeps the highest-priority work
(weakest skills and sub-skills first) and says so.
"""

from __future__ import annotations

import datetime as dt
import math

from . import bank, mastery

DRILL_MIN = 20       # a drill = 8 targeted questions
MOCK_MIN = 30        # a mock = 10 mixed questions with a chosen interviewer
REVIEW_SHARE = 0.15
DRILLS_PER_LEVEL = 3
DRILL_QUESTIONS = 8
MOCK_QUESTIONS = 10

STAGES = {
    "networking": "Networking / coffee chats",
    "first_rounds": "First-round interviews",
    "superdays": "Superdays",
    "offer": "Have an offer, staying sharp",
}


def _today() -> dt.date:
    return dt.date.today()


def days_until(date_str: str | None, default_days: int = 21) -> int:
    try:
        d = dt.date.fromisoformat(date_str) if date_str else None
    except ValueError:
        d = None
    days = (d - _today()).days if d else default_days
    return max(3, min(days, 90))


def build(intake: dict, levels: dict[str, int], weak_subskills: list[str]) -> dict:
    group = intake.get("group") or "generalist"
    hours_week = max(1.0, min(float(intake.get("hours_per_week") or 5), 40.0))
    days = days_until(intake.get("interview_date"))
    weeks = days / 7

    skills = [s for s in mastery.diagnostic_skills(group)]
    weights = bank.GROUP_WEIGHTS.get(group, {})
    rows, tasks = [], []
    for s in skills:
        cur = levels.get(s, 0)
        tgt = mastery.target_level(cur)
        steps = max(tgt - cur, 0)
        weak = [w for w in weak_subskills if bank.SUBSKILLS.get(w, ("",))[0] == s]
        drills = steps * DRILLS_PER_LEVEL + len(weak)
        if cur >= 3:
            drills = max(drills, math.ceil(weeks))  # maintenance at Advanced
        # group emphasis: heavier-weighted skills get an extra drill, lighter ones may drop one
        wt = weights.get(s, 1.0)
        drills = max(1 if steps or weak or cur >= 3 else 0, round(drills * wt))
        priority = (cur, -len(weak), -wt)
        rows.append({"skill": s, "name": bank.SKILLS[s], "current": cur, "target": tgt, "drills": drills,
                     "weak_subskills": [{"id": w, "name": bank.SUBSKILLS[w][1]} for w in weak], "priority": priority})
        for i in range(drills):
            sub = weak[i] if i < len(weak) else None
            lvl = min(cur + 1, 3) if i >= len(weak) else max(cur, 1)
            tasks.append({"type": "drill", "skill": s, "subskill": sub, "level": max(lvl, 1),
                          "minutes": DRILL_MIN, "priority": priority, "seq": i})

    # one mock per full week (on day 7, 14, ...) plus a final mock the day before the interview, de-duplicated
    mock_days = sorted({7 * (k + 1) - 1 for k in range(max(0, math.floor(weeks)))} | {days - 1})
    mock_days = [d for d in mock_days if d <= days - 1]
    mocks = len(mock_days)
    need_min = sum(t["minutes"] for t in tasks) + mocks * MOCK_MIN
    need_min = round(need_min * (1 + REVIEW_SHARE))
    avail_min = round(hours_week * 60 * weeks)
    compressed = need_min > avail_min
    if compressed:
        # keep the highest-priority drills (lowest level, most weak sub-skills, heaviest group weight)
        budget = avail_min / (1 + REVIEW_SHARE) - mocks * MOCK_MIN
        tasks.sort(key=lambda t: (t["seq"], t["priority"]))
        kept, used = [], 0
        for t in tasks:
            if used + t["minutes"] <= budget:
                kept.append(t)
                used += t["minutes"]
        tasks = kept

    # ---- calendar: round-robin across skills so every day mixes the weakest areas
    tasks.sort(key=lambda t: (t["seq"], t["priority"]))
    practice_days = min(days, max(3, round(days * 6 / 7)))       # one rest day a week
    per_day_min = max(DRILL_MIN, hours_week * 60 / 6)
    schedule: list[dict] = []
    day_idx, day_used = 0, 0
    start = _today()
    for t in tasks:
        while day_idx in mock_days or day_used + t["minutes"] > per_day_min:
            day_idx += 1
            day_used = 0
            if day_idx >= days - 1:
                day_idx = max(0, days - 2)
                break
        t["date"] = (start + dt.timedelta(days=day_idx)).isoformat()
        day_used += t["minutes"]
    for m, d in enumerate(mock_days):
        tasks.append({"type": "mock", "skill": None, "subskill": None, "level": None, "minutes": MOCK_MIN,
                      "date": (start + dt.timedelta(days=d)).isoformat(), "final": d == days - 1})
    tasks.sort(key=lambda t: (t["date"], t["type"] != "drill"))
    for i, t in enumerate(tasks):
        t["id"] = i
        t["done"] = False
        t.pop("priority", None)
        t.pop("seq", None)
        if t["type"] == "drill":
            sub = bank.SUBSKILLS.get(t["subskill"], (None, None))[1]
            t["title"] = f"{bank.LEVELS[t['level']]} drill: {bank.SKILLS[t['skill']]}" + (f", {sub}" if sub else "")
        else:
            t["title"] = "Final mock interview" if t.get("final") else "Mock interview"

    tech = [levels.get(s, 0) for s in bank.TECHNICAL]
    overall = int(sum(tech) / len(tech) + 0.5) if tech else 0  # nearest level (4 of 5 skills at Basic = Basic)
    for r in rows:
        r.pop("priority", None)
    n_drills = sum(1 for t in tasks if t["type"] == "drill")
    total_min = round((n_drills * DRILL_MIN + mocks * MOCK_MIN) * (1 + REVIEW_SHARE))
    return {
        "created": _today().isoformat(),
        "group": group, "group_name": bank.GROUPS.get(group, group), "stage": intake.get("stage"),
        "days_left": days, "hours_per_week": hours_week,
        "overall_level": overall, "overall_label": bank.LEVELS.get(overall, "Foundations"),
        "target_level": mastery.target_level(overall), "target_label": bank.LEVELS[mastery.target_level(overall)],
        "skills": rows,
        "drills": n_drills, "mocks": mocks, "questions": n_drills * DRILL_QUESTIONS + mocks * MOCK_QUESTIONS,
        "hours_needed": round(need_min / 60, 1), "hours_planned": round(total_min / 60, 1),
        "hours_available": round(avail_min / 60, 1), "compressed": compressed,
        "minutes_per_practice_day": round(total_min / max(practice_days, 1)),
        "tasks": tasks,
    }


def progress(plan: dict) -> dict:
    """How the candidate is doing against the plan today."""
    today = _today().isoformat()
    tasks = plan.get("tasks", [])
    done = [t for t in tasks if t["done"]]
    due = [t for t in tasks if t["date"] <= today]          # due by the end of today
    due_done = [t for t in due if t["done"]]
    overdue = [t for t in tasks if t["date"] < today and not t["done"]]  # only earlier days count as late
    status = "on track"
    if overdue:
        status = "behind"
    elif len(done) > len(due):
        status = "ahead"
    nxt = next((t for t in tasks if not t["done"]), None)
    return {"done": len(done), "total": len(tasks), "pct": round(100 * len(done) / max(len(tasks), 1)),
            "due": len(due), "due_done": len(due_done), "status": status, "next": nxt,
            "today": [t for t in tasks if t["date"] == today]}


def mark_done(plan: dict, kind: str, skill: str | None) -> dict | None:
    """Tick the earliest open task that matches a finished session."""
    for t in plan.get("tasks", []):
        if t["done"] or t["type"] != kind:
            continue
        if kind == "drill" and skill and t["skill"] != skill:
            continue
        t["done"] = True
        t["completed"] = _today().isoformat()
        return t
    return None
