"""The action plan: computed by code, so its numbers must add up."""

import datetime as dt

from ticktie import bank, mastery, plan


def _intake(days=21, hours=6, group="tmt"):
    return {"group": group, "stage": "first_rounds", "hours_per_week": hours,
            "interview_date": (dt.date.today() + dt.timedelta(days=days)).isoformat()}


def test_plan_targets_one_level_up_and_counts_add_up():
    levels = {"accounting": 1, "ev": 2, "dcf": 0, "ma": 1, "lbo": 3, "industry": 1, "fit": 1}
    p = plan.build(_intake(), levels, ["accounting.noncash", "dcf.time_value"])
    rows = {r["skill"]: r for r in p["skills"]}
    assert rows["accounting"]["target"] == 2 and rows["lbo"]["target"] == 3 and rows["dcf"]["target"] == 1
    drills = [t for t in p["tasks"] if t["type"] == "drill"]
    mocks = [t for t in p["tasks"] if t["type"] == "mock"]
    assert len(drills) == p["drills"] and len(mocks) == p["mocks"]
    assert any(t["subskill"] == "accounting.noncash" for t in drills)
    assert p["tasks"][-1]["type"] == "mock"  # the final mock comes right before the interview
    assert max(t["date"] for t in p["tasks"]) < (dt.date.today() + dt.timedelta(days=21)).isoformat()


def test_plan_is_compressed_when_time_is_short():
    p = plan.build(_intake(days=4, hours=2), {s: 0 for s in bank.SKILLS}, [])
    assert p["compressed"]
    assert p["hours_planned"] <= p["hours_available"] + 1.0


def test_plan_progress_and_ticking():
    p = plan.build(_intake(), {s: 1 for s in bank.SKILLS}, [])
    before = plan.progress(p)["done"]
    first_drill = next(t for t in p["tasks"] if t["type"] == "drill")
    assert plan.mark_done(p, "drill", first_drill["skill"])["skill"] == first_drill["skill"]
    assert plan.progress(p)["done"] == before + 1


# ---------------------------------------------------------------- dates, calendar and honesty (QA-07..QA-12)
TODAY = dt.date(2026, 10, 24)


def _intake_on(days, hours=6, group="generalist"):
    return {"group": group, "stage": "first_rounds", "hours_per_week": hours,
            "interview_date": (TODAY + dt.timedelta(days=days)).isoformat()}


def test_past_date_gives_a_flagged_maintenance_plan():
    p = plan.build(_intake_on(-10), {s: 1 for s in bank.SKILLS}, [], today=TODAY)
    assert p["interview_passed"] and p["interview_status"] == "past" and p["days_left"] == plan.DEFAULT_HORIZON
    assert plan.days_until("not-a-date", today=TODAY) == plan.DEFAULT_HORIZON
    assert plan.interview_status("2026-13-45", TODAY) == "invalid"


def test_interview_today_or_tomorrow_gets_final_prep_before_the_interview():
    for days in (0, 1, 2):
        p = plan.build(_intake_on(days), {s: 0 for s in bank.SKILLS}, [], today=TODAY)
        drills = [t for t in p["tasks"] if t["type"] == "drill"]
        mocks = [t for t in p["tasks"] if t["type"] == "mock"]
        assert p["final_prep"] and len(drills) == {0: 0, 1: 1, 2: 2}[days] and len(mocks) == 1
        last_allowed = TODAY + dt.timedelta(days=max(days - 1, 0))
        assert all(dt.date.fromisoformat(t["date"]) <= last_allowed for t in p["tasks"])


def test_no_task_on_or_after_the_interview_day():
    for days in (3, 5, 8, 15, 60):
        p = plan.build(_intake_on(days, hours=10), {s: 1 for s in bank.SKILLS}, [], today=TODAY)
        interview = TODAY + dt.timedelta(days=days)
        assert all(dt.date.fromisoformat(t["date"]) < interview for t in p["tasks"]), days


def test_drills_are_spread_and_minutes_per_day_match_the_calendar():
    p = plan.build(_intake_on(60, hours=20), {s: 0 for s in bank.SKILLS}, [], today=TODAY)
    per_day: dict[str, int] = {}
    for t in p["tasks"]:
        per_day[t["date"]] = per_day.get(t["date"], 0) + t["minutes"]
    assert max(per_day.values()) <= 3 * plan.DRILL_MIN  # nothing crammed into the first days
    assert len(per_day) >= 20
    assert p["minutes_per_practice_day"] == round(sum(per_day.values()) / len(per_day))
    assert p["hours_planned"] == round(sum(per_day.values()) / 60, 1)


def test_skill_rows_match_scheduled_drills_after_compression():
    p = plan.build(_intake_on(21, hours=1), {s: 0 for s in bank.SKILLS}, [], today=TODAY)
    assert p["compressed"]
    scheduled = sum(1 for t in p["tasks"] if t["type"] == "drill")
    assert sum(r["drills"] for r in p["skills"]) == scheduled == p["drills"]


def test_only_levels_with_questions_are_scheduled():
    for g in bank.GROUPS:
        p = plan.build(_intake_on(30, group=g), {s: 2 for s in bank.SKILLS}, [], today=TODAY)
        for t in (t for t in p["tasks"] if t["type"] == "drill"):
            assert mastery.pool(g, skill=t["skill"], levels=(t["level"],)), (g, t["title"])


def test_user_today_uses_the_client_offset():
    east, west = plan.user_today(-840), plan.user_today(720)
    assert east - west == dt.timedelta(days=1)
    assert plan.local_date(0, 300) == dt.date(1969, 12, 31)  # midnight UTC = 7 PM the day before in New York


def test_carry_over_keeps_done_tasks_without_inflating():
    old = plan.build(_intake_on(21), {s: 1 for s in bank.SKILLS}, [], today=TODAY)
    first = next(t for t in old["tasks"] if t["type"] == "drill")
    plan.mark_done(old, "drill", first["skill"], today=TODAY)
    new = plan.carry_over(plan.build(_intake_on(21), {s: 1 for s in bank.SKILLS}, [], today=TODAY + dt.timedelta(days=2)), old)
    assert sum(t["done"] for t in new["tasks"]) == 1 and len(new["tasks"]) == len(old["tasks"])
    assert sorted(t["id"] for t in new["tasks"]) == list(range(len(new["tasks"])))


def test_mark_done_prefers_the_task_id():
    p = plan.build(_intake_on(21), {s: 1 for s in bank.SKILLS}, [], today=TODAY)
    last = [t for t in p["tasks"] if t["type"] == "drill"][-1]
    assert plan.mark_done(p, "drill", last["skill"], today=TODAY, task_id=last["id"])["id"] == last["id"]


# ---------------------------------------------------------------- .env discovery
def test_empty_repo_env_does_not_mask_parent_key(tmp_path, monkeypatch):
    from ticktie import config
    (tmp_path / "repo").mkdir()
    (tmp_path / "repo" / ".env").write_text("PORTKEY_API_KEY=\n", encoding="utf-8")
    (tmp_path / ".env").write_text("PORTKEY_API_KEY=parent-key\n", encoding="utf-8")
    monkeypatch.setenv("PORTKEY_API_KEY", "")  # restored after the test
    config.load_env([tmp_path / "repo" / ".env", tmp_path / ".env"])
    import os
    assert os.environ["PORTKEY_API_KEY"] == "parent-key"


def test_requirements_are_pinned():
    from ticktie import config
    lines = [l.strip() for l in (config.REPO_ROOT / "requirements.txt").read_text().splitlines()
             if l.strip() and not l.startswith("#")]
    assert lines and all("==" in l for l in lines)


def test_interview_today_has_no_drill_on_the_day():
    p = plan.build(_intake_on(0), {s: 0 for s in bank.SKILLS}, [], today=TODAY)
    assert [t["type"] for t in p["tasks"]] == ["mock"] and p["tasks"][0]["title"].startswith("Warm-up")


def test_carry_over_dates_done_tasks_on_completion_and_keeps_one_final_mock():
    old = plan.build(_intake_on(10), {s: 1 for s in bank.SKILLS}, [], today=TODAY)
    final = next(t for t in old["tasks"] if t.get("final"))
    final["done"], final["completed"] = True, (TODAY + dt.timedelta(days=12)).isoformat()  # after the interview
    drill = next(t for t in old["tasks"] if t["type"] == "drill")
    drill["done"], drill["completed"] = True, (TODAY + dt.timedelta(days=1)).isoformat()
    new = plan.carry_over(plan.build(_intake_on(9), {s: 1 for s in bank.SKILLS}, [], today=TODAY + dt.timedelta(days=1)), old)
    interview = TODAY + dt.timedelta(days=10)
    assert all(dt.date.fromisoformat(t["date"]) < interview for t in new["tasks"])
    done_drill = next(t for t in new["tasks"] if t["done"] and t["type"] == "drill")
    assert done_drill["date"] == drill["completed"]
    assert sum(1 for t in new["tasks"] if t.get("final")) == 1
    assert sum(1 for t in new["tasks"] if t["title"] == "Final mock interview") == 1


def test_rebuilt_plan_totals_match_its_tasks():
    old = plan.build(_intake_on(21), {s: 1 for s in bank.SKILLS}, [], today=TODAY)
    for t in [t for t in old["tasks"] if t["type"] == "drill"][:2]:
        plan.mark_done(old, "drill", t["skill"], today=TODAY)
    new = plan.carry_over(plan.build(_intake_on(20), {s: 2 for s in bank.SKILLS}, [], today=TODAY + dt.timedelta(days=1)), old)
    days = {t["date"] for t in new["tasks"]}
    minutes = sum(t["minutes"] for t in new["tasks"])
    assert new["practice_days"] == len(days) and new["minutes_per_practice_day"] == round(minutes / len(days))
    assert sum(r["drills"] for r in new["skills"]) == new["drills"] == sum(t["type"] == "drill" for t in new["tasks"])
