"""Personal action plan: built by code from the diagnostic, the deadline and the hours available.

Every number in the plan is computed here, so it's explainable and testable:
  * target  = one level up per skill (Coffee-chat ready -> First-round ready -> Superday ready), or top-level practice if already there
  * drills  = 3 per level to climb + 1 per weak sub-skill (+1 maintenance drill per week at the top level)
  * mocks   = 1 per week + 1 final mock before the interview
  * hours   = drills x 20 min + mocks x 30 min + 15% review time
If the hours needed exceed the hours available, the plan keeps the highest-priority work
(weakest skills and sub-skills first) and says so.

Calendar rules: drills are spread evenly over the practice days before the interview (never on a
mock day, the weekly rest day, or on/after the interview day); only (skill, level) pairs that have
questions for the candidate's group are scheduled; an interview within 2 days gets a short
final-prep plan (1-2 drills + 1 mock). "Today" is the user's date (see user_today).
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


def user_today(offset_min: int | None = None) -> dt.date:
    """The user's calendar date. offset_min follows JS getTimezoneOffset(): minutes to ADD to local
    time to get UTC (New York in winter = 300). None means UTC. Offsets need no tz database
    (Windows has none without the tzdata package)."""
    now = dt.datetime.now(dt.timezone.utc)
    if offset_min is None:
        return now.date()
    off = max(-840, min(int(offset_min), 840))
    return (now - dt.timedelta(minutes=off)).date()


def local_date(ts: float, offset_min: int | None = None) -> dt.date:
    """Calendar date of a unix timestamp in the user's time zone."""
    off = max(-840, min(int(offset_min or 0), 840))
    return (dt.datetime.fromtimestamp(ts, dt.timezone.utc) - dt.timedelta(minutes=off)).date()


def parse_date(date_str: str | None) -> dt.date | None:
    try:
        return dt.date.fromisoformat(str(date_str)[:10]) if date_str else None
    except ValueError:
        return None


def interview_status(date_str: str | None, today: dt.date | None = None) -> str:
    """'none' (no date given), 'invalid', 'past', or 'ok'."""
    if not date_str:
        return "none"
    d = parse_date(date_str)
    if d is None:
        return "invalid"
    return "past" if d < (today or _today()) else "ok"


MAX_HORIZON = 90
DEFAULT_HORIZON = 21
REST_WEEKDAY_INDEX = 5   # one rest day a week (day 5, 12, 19, ... of the plan)


def days_until(date_str: str | None, default_days: int = DEFAULT_HORIZON, today: dt.date | None = None) -> int:
    """Days from today to the interview (0 = the interview is today). No, invalid or past date ->
    the default horizon (a maintenance plan). Capped at 90 days."""
    today = today or _today()
    d = parse_date(date_str)
    days = (d - today).days if d and d >= today else default_days
    return max(0, min(days, MAX_HORIZON))


def _drill_title(skill: str, level: int, sub: str | None, wanted: int) -> str:
    name = bank.SUBSKILLS.get(sub, (None, None))[1] if sub else None
    title = f"Drill: {bank.SKILLS[skill]}" + (f", {name}" if name else "") + f" (towards {bank.LEVELS[level]}"
    if level != wanted:
        title += f"; no {bank.LEVELS[wanted]} questions yet"
    return title + ")"


def build(intake: dict, levels: dict[str, int], weak_subskills: list[str], today: dt.date | None = None) -> dict:
    today = today or _today()
    group = intake.get("group") or "generalist"
    hours_week = max(1.0, min(float(intake.get("hours_per_week") or 5), 40.0))
    status = interview_status(intake.get("interview_date"), today)
    days = days_until(intake.get("interview_date"), today=today)
    d_int = parse_date(intake.get("interview_date"))
    horizon_capped = status == "ok" and d_int is not None and (d_int - today).days > MAX_HORIZON
    final_prep = days <= 2  # interview today, tomorrow or the day after: a short final-prep plan
    weeks = max(days, 1) / 7

    skills = [s for s in mastery.diagnostic_skills(group)]
    weights = bank.GROUP_WEIGHTS.get(group, {})
    rows, tasks = [], []
    for s in skills:
        avail = mastery.available_levels(group, s)
        if not avail:
            continue  # nothing to drill for this group
        cur = levels.get(s, 0)
        tgt = mastery.target_level(cur)
        steps = max(tgt - cur, 0)
        weak = [w for w in weak_subskills if bank.SUBSKILLS.get(w, ("",))[0] == s]
        drills = steps * DRILLS_PER_LEVEL + len(weak)
        if cur >= 3:
            drills = max(drills, math.ceil(weeks))  # maintenance at the top level
        # group emphasis: heavier-weighted skills get an extra drill, lighter ones may drop one
        wt = weights.get(s, 1.0)
        drills = max(1 if steps or weak or cur >= 3 else 0, round(drills * wt))
        priority = (cur, -len(weak), -wt)
        rows.append({"skill": s, "name": bank.SKILLS[s], "current": cur, "target": tgt,
                     "target_available": tgt in avail, "drills": 0,
                     "weak_subskills": [{"id": w, "name": bank.SUBSKILLS[w][1]} for w in weak], "priority": priority})
        for i in range(drills):
            sub = weak[i] if i < len(weak) else None
            want = min(cur + 1, 3) if i >= len(weak) else max(cur, 1)
            if sub:  # the sub-skill's own nearest level that has questions
                sub_levels = [L for L in avail if mastery.pool(group, skill=s, levels=(L,), subskill=sub)]
                lvl = min(sub_levels, key=lambda L: (abs(L - want), L)) if sub_levels else None
                if lvl is None:
                    sub = None
            if not sub:
                lvl = mastery.nearest_level(group, s, want)
            tasks.append({"type": "drill", "skill": s, "subskill": sub, "level": lvl, "level_wanted": want,
                          "minutes": DRILL_MIN, "priority": priority, "seq": i})
    tasks.sort(key=lambda t: (t["seq"], t["priority"]))  # round-robin across skills, weakest first

    # ---- mocks: one per full week (day 6, 13, ...) plus a final mock the day before the interview
    if final_prep:
        mock_days = [max(days - 1, 0)]
    else:
        mock_days = sorted({7 * (k + 1) - 1 for k in range(max(0, math.floor(days / 7)))} | {days - 1})
        mock_days = [d for d in mock_days if d <= days - 1]
    mocks = len(mock_days)
    need_min = round((sum(t["minutes"] for t in tasks) + mocks * MOCK_MIN) * (1 + REVIEW_SHARE))
    avail_min = round(hours_week * 60 * weeks)
    compressed = need_min > avail_min
    if final_prep:
        keep = 1 if days < 2 else 2
        compressed = len(tasks) > keep
        tasks = tasks[:keep]
    elif compressed:
        # keep the highest-priority drills (lowest level, most weak sub-skills, heaviest group weight)
        budget = avail_min / (1 + REVIEW_SHARE) - mocks * MOCK_MIN
        kept, used = [], 0
        for t in tasks:
            if used + t["minutes"] <= budget:
                kept.append(t)
                used += t["minutes"]
        tasks = kept

    # ---- calendar: spread drills evenly over the practice days before the interview.
    # Never on a mock day, a rest day, or on/after the interview day.
    if final_prep:
        drill_days = [0]
    else:
        drill_days = [d for d in range(days - 1) if d not in mock_days and d % 7 != REST_WEEKDAY_INDEX] or [0]
    n = len(tasks)
    for i, t in enumerate(tasks):
        t["date"] = (today + dt.timedelta(days=drill_days[i * len(drill_days) // n])).isoformat()
    for d in mock_days:
        tasks.append({"type": "mock", "skill": None, "subskill": None, "level": None, "minutes": MOCK_MIN,
                      "date": (today + dt.timedelta(days=d)).isoformat(), "final": d == mock_days[-1]})
    tasks.sort(key=lambda t: (t["date"], t["type"] != "drill"))
    for i, t in enumerate(tasks):
        t["id"] = i
        t["done"] = False
        t.pop("priority", None)
        t.pop("seq", None)
        if t["type"] == "drill":
            t["title"] = _drill_title(t["skill"], t["level"], t["subskill"], t.pop("level_wanted"))
        else:
            t["title"] = "Final mock interview" if t.get("final") else "Mock interview"

    tech = [levels.get(s, 0) for s in bank.TECHNICAL]
    overall = int(sum(tech) / len(tech) + 0.5) if tech else 0  # nearest level (4 of 5 skills at level 1 = level 1)
    per_skill = {}
    for t in tasks:
        if t["type"] == "drill":
            per_skill[t["skill"]] = per_skill.get(t["skill"], 0) + 1
    for r in rows:
        r.pop("priority", None)
        r["drills"] = per_skill.get(r["skill"], 0)  # what was actually scheduled, after compression
    n_drills = sum(1 for t in tasks if t["type"] == "drill")
    task_min = n_drills * DRILL_MIN + mocks * MOCK_MIN
    active_days = len({t["date"] for t in tasks})
    return {
        "created": today.isoformat(),
        "group": group, "group_name": bank.GROUPS.get(group, group), "stage": intake.get("stage"),
        "days_left": days, "hours_per_week": hours_week,
        "interview_status": status, "interview_passed": status == "past", "horizon_capped": horizon_capped,
        "final_prep": final_prep,
        "overall_level": overall, "overall_label": bank.LEVELS.get(overall, bank.LEVEL0_LABEL),
        "target_level": mastery.target_level(overall), "target_label": bank.LEVELS[mastery.target_level(overall)],
        "skills": rows,
        "drills": n_drills, "mocks": mocks, "questions": n_drills * DRILL_QUESTIONS + mocks * MOCK_QUESTIONS,
        "hours_needed": round(need_min / 60, 1),
        "hours_planned": round(task_min / 60, 1),                       # what is on the calendar
        "review_hours": round(task_min * REVIEW_SHARE / 60, 1),         # suggested extra review time
        "hours_available": round(avail_min / 60, 1), "compressed": compressed,
        "practice_days": active_days,
        "minutes_per_practice_day": round(task_min / max(active_days, 1)),  # equals the calendar average
        "tasks": tasks,
    }


def progress(plan: dict, today: dt.date | None = None) -> dict:
    """How the candidate is doing against the plan today (the user's today)."""
    today = (today or _today()).isoformat()
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


def mark_done(plan: dict, kind: str, skill: str | None, today: dt.date | None = None,
              task_id: int | None = None) -> dict | None:
    """Tick the task a session was started for (task_id), else the earliest open task that matches."""
    if task_id is not None:
        t = next((t for t in plan.get("tasks", []) if t.get("id") == task_id), None)
        if t and not t["done"] and t["type"] == kind:
            t["done"] = True
            t["completed"] = (today or _today()).isoformat()
            return t
    for t in plan.get("tasks", []):
        if t["done"] or t["type"] != kind:
            continue
        if kind == "drill" and skill and t["skill"] != skill:
            continue
        t["done"] = True
        t["completed"] = (today or _today()).isoformat()
        return t
    return None


def carry_over(new: dict, old: dict | None) -> dict:
    """Keep completed tasks (with their dates) when a plan is rebuilt; the new plan is the remaining work.

    Each completed task replaces one matching open task in the new plan (same skill for drills, a
    non-final mock for mocks), so rebuilding with unchanged inputs doesn't inflate the plan."""
    done = [t for t in (old or {}).get("tasks", []) if t.get("done")]
    if not done:
        return new
    remaining = list(new.get("tasks", []))
    for d in done:
        for i, t in enumerate(remaining):
            if t["type"] != d["type"]:
                continue
            if d["type"] == "drill" and t["skill"] != d["skill"]:
                continue
            if d["type"] == "mock" and t.get("final"):
                continue
            del remaining[i]
            break
    tasks = [dict(t) for t in done] + remaining
    tasks.sort(key=lambda t: (t["date"], not t.get("done"), t["type"] != "drill"))
    for i, t in enumerate(tasks):
        t["id"] = i
    new["tasks"] = tasks
    new["drills"] = sum(1 for t in tasks if t["type"] == "drill")
    new["mocks"] = sum(1 for t in tasks if t["type"] == "mock")
    new["questions"] = new["drills"] * DRILL_QUESTIONS + new["mocks"] * MOCK_QUESTIONS
    task_min = new["drills"] * DRILL_MIN + new["mocks"] * MOCK_MIN
    new["hours_planned"] = round(task_min / 60, 1)
    new["review_hours"] = round(task_min * REVIEW_SHARE / 60, 1)
    new["carried_over"] = len(done)
    return new
