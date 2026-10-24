"""The weakness map: per-skill mastery (Bayesian knowledge tracing) and per-misconception tracking.

All deterministic. The model never decides what to ask next or how well the
candidate is doing. That keeps the agent from 'teaching to the test' by
picking easy questions to make the scores look good.
"""

from __future__ import annotations

import random

from . import bank

P_INIT = 0.30
P_LEARN = 0.12
P_SLIP = 0.10
P_GUESS = {"numeric": 0.10, "conceptual": 0.25}

# How much each verdict counts as evidence of mastery (1 = clean correct).
EVIDENCE = {
    "correct": 1.0,
    "correct_unexplained": 0.5,  # right number, couldn't explain it: memorised, not mastered
    "incomplete": 0.4,
    "incorrect": 0.0,
}


def bkt_update(p: float, verdict: str, kind: str) -> float:
    """Bayesian knowledge tracing; partial evidence interpolates the two posteriors."""
    g = P_GUESS.get(kind, 0.15)
    s = P_SLIP
    post_right = p * (1 - s) / (p * (1 - s) + (1 - p) * g)
    post_wrong = p * s / (p * s + (1 - p) * (1 - g))
    w = EVIDENCE.get(verdict, 0.0)
    post = w * post_right + (1 - w) * post_wrong
    return round(post + (1 - post) * P_LEARN, 4)


MIN_EVIDENCE_FOR_READY = 3


def level(p: float, n: int = MIN_EVIDENCE_FOR_READY) -> str:
    """Label for a mastery estimate. 'Interview-ready' needs at least 3 graded questions,
    because one lucky answer shouldn't certify a skill."""
    if p >= 0.80 and n >= MIN_EVIDENCE_FOR_READY:
        return "interview-ready"
    if p >= 0.80:
        return "solid"
    if p >= 0.55:
        return "solid"
    if p >= 0.35:
        return "shaky"
    return "weak"


def target_difficulty(p: float) -> int:
    if p < 0.35:
        return 1
    if p < 0.65:
        return 2
    return 3


def pick_next(
    mode: str,
    mastery: dict[str, float],
    active_misconceptions: dict[str, int],
    asked: list[str],
    rng: random.Random,
    focus: str | None = None,
) -> str:
    """Choose the next template id.

    diagnostic: cover every skill once, easiest first, so the map fills in quickly.
    drill:      go after the weakest skill and the candidate's active misconceptions.
    mixed:      like drill, but with some exploration across skills.
    """
    skills = list(bank.SKILLS)
    if focus in skills:
        skills = [focus]

    if mode == "diagnostic":
        untested = [s for s in skills if not any(bank.TEMPLATES[a].skill == s for a in asked)]
        if untested:
            skill = untested[0]
            in_skill = [t for t in bank.TEMPLATES.values() if t.skill == skill]
            # Prefer an easy numeric question; some skills (markets) only have harder ones.
            pool = ([t for t in in_skill if t.kind == "numeric" and t.difficulty <= 2]
                    or [t for t in in_skill if t.kind == "numeric"] or in_skill)
            return min(pool, key=lambda t: (t.difficulty, rng.random())).id
        mode = "drill"

    # Rank skills from weakest up; mixed mode sometimes explores a random skill.
    ranked = sorted(skills, key=lambda s: mastery.get(s, P_INIT))
    skill = ranked[0]
    if mode == "mixed" and len(ranked) > 1 and rng.random() < 0.35:
        skill = rng.choice(ranked[1:])

    want = target_difficulty(mastery.get(skill, P_INIT))
    cands = [t for t in bank.TEMPLATES.values() if t.skill == skill]
    recent = set(asked[-4:])

    def score(t: bank.Template) -> tuple:
        hits = sum(active_misconceptions.get(m, 0) for m in t.misconceptions)
        return (
            -min(hits, 3),                 # templates that re-test an active misconception first
            t.id in recent,                # avoid immediate repeats (numbers change anyway)
            abs(t.difficulty - want),      # then the right difficulty
            asked.count(t.id),             # then least-asked
            rng.random(),
        )

    return min(cands, key=score).id
