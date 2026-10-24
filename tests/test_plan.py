"""The action plan: computed by code, so its numbers must add up."""

import datetime as dt

from ticktie import bank, plan


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
