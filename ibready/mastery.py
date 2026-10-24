"""The weakness map and question selection: all deterministic.

Three layers of mastery, each a Bayesian-knowledge-tracing estimate:
* skill               e.g. "accounting"            the headline bar
* level within skill  e.g. "lvl:accounting:2"      decides Coffee-chat / First-round / Superday ready
* sub-skill           e.g. "sub:accounting.noncash" what drills target

The model never decides what to ask next or how well the candidate is doing,
so it can't choose easy questions to make the numbers look good.
"""

from __future__ import annotations

import random

from . import bank

P_INIT = 0.30
P_LEARN = 0.12
P_SLIP = 0.10
P_GUESS = {"numeric": 0.10, "conceptual": 0.25, "behavioral": 0.30}
READY = 0.75             # a level counts as "achieved" at or above this
MIN_EVIDENCE_FOR_READY = 3

EVIDENCE = {"correct": 1.0, "correct_unexplained": 0.5, "incomplete": 0.4, "incorrect": 0.0}

# How often each interviewer seniority asks fit/behavioral questions in a mock.
FIT_SHARE = {"associate": 0.10, "vp": 0.25, "director": 0.50, "md": 0.70}


def bkt_update(p: float, verdict: str, kind: str) -> float:
    """Bayesian knowledge tracing; partial evidence interpolates the two posteriors."""
    g = P_GUESS.get(kind, 0.15)
    s = P_SLIP
    post_right = p * (1 - s) / (p * (1 - s) + (1 - p) * g)
    post_wrong = p * s / (p * s + (1 - p) * (1 - g))
    w = EVIDENCE.get(verdict, 0.0)
    post = w * post_right + (1 - w) * post_wrong
    return round(post + (1 - post) * P_LEARN, 4)


def level(p: float, n: int = MIN_EVIDENCE_FOR_READY) -> str:
    """Label for a mastery estimate. 'Interview-ready' needs at least 3 graded questions."""
    if p >= 0.80 and n >= MIN_EVIDENCE_FOR_READY:
        return "interview-ready"
    if p >= 0.80:
        return "solid"
    if p >= 0.55:
        return "solid"
    if p >= 0.35:
        return "shaky"
    return "weak"


def current_level(skill: str, placed: int, keys: dict[str, dict]) -> int:
    """Highest level achieved: the placement, raised once a level's mastery is demonstrated (>= READY, n >= 2)."""
    lvl = placed
    for L in (1, 2, 3):
        k = keys.get(f"lvl:{skill}:{L}")
        if k and k["p"] >= READY and k["n"] >= 2 and L == lvl + 1:
            lvl = L
    return lvl


def target_level(current: int) -> int:
    return min(max(current, 0) + 1, 3)


# --------------------------------------------------------------------------- selection
def pool(group: str | None, skill: str | None = None, levels: tuple[int, ...] | None = None,
         subskill: str | None = None, kinds: tuple[str, ...] | None = None) -> list[bank.Template]:
    """Strict filter: only questions that match every constraint the candidate set."""
    out = []
    for t in bank.TEMPLATES.values():
        if not bank.eligible(t, group):
            continue
        if skill and t.skill != skill:
            continue
        if levels and t.difficulty not in levels:
            continue
        if subskill and t.subskill != subskill:
            continue
        if kinds and t.kind not in kinds:
            continue
        if t.skill == "industry" and (not group or group == "generalist"):
            continue
        out.append(t)
    return out


def choose(cands: list[bank.Template], asked: list[str], active: dict[str, int], rng: random.Random) -> bank.Template:
    recent = set(asked[-6:])

    def score(t: bank.Template) -> tuple:
        hits = sum(active.get(m, 0) for m in t.misconceptions)
        return (t.id in recent, -min(hits, 3), asked.count(t.id), rng.random())

    return min(cands, key=score)


def pick_targeted(group: str | None, skill: str, lvl: int, subskill: str | None, asked: list[str],
                  active: dict[str, int], rng: random.Random) -> bank.Template:
    """Best question for a (skill, level, sub-skill) target, relaxing constraints only if nothing fresh matches.

    Numeric questions may repeat (the calculator draws new numbers each time); conceptual and
    behavioral questions are never repeated within the last few questions, so the selector widens
    the sub-skill or level before it would ask the same words twice."""
    for attempt in (
        dict(skill=skill, levels=(lvl,), subskill=subskill),
        dict(skill=skill, levels=(lvl,)),
        dict(skill=skill, levels=(max(lvl - 1, 1), min(lvl + 1, 3))),
        dict(skill=skill),
    ):
        fresh = _fresh(pool(group, **attempt), asked)
        if fresh:
            return choose(fresh, asked, active, rng)
    cands = pool(group, skill=skill) or list(bank.TEMPLATES.values())
    return choose(cands, asked, active, rng)


def _fresh(cands: list[bank.Template], asked: list[str]) -> list[bank.Template]:
    """Numeric questions may come back (new numbers each time) but never back to back; word questions
    (conceptual, behavioral) are not repeated within the last 8 questions, and a question's twin (one that
    asks nearly the same thing, bank.TWINS) is not asked in the same session."""
    recent = set(asked[-8:])
    seen = set(asked)
    return [t for t in cands if ((t.kind == "numeric" and asked[-1:] != [t.id]) or t.id not in recent)
            and not (bank.TWINS.get(t.id, set()) & seen)]


def available_levels(group: str | None, skill: str) -> list[int]:
    """Levels that have at least one question for this group."""
    return [L for L in (1, 2, 3) if pool(group, skill=skill, levels=(L,))]


def nearest_level(group: str | None, skill: str, lvl: int) -> int | None:
    """The level closest to `lvl` that has questions (ties go to the lower level); None if the skill has none."""
    avail = available_levels(group, skill)
    if not avail:
        return None
    return min(avail, key=lambda L: (abs(L - lvl), L))


def pick_practice(group: str | None, skill: str, lvl: int, asked: list[str], active: dict[str, int],
                  rng: random.Random) -> tuple[bank.Template, int | None]:
    """Free practice at the level the candidate chose. Returns (question, served_level or None if exact).

    The chosen level is strict while it has a fresh question. When it has none (or no questions at all
    for this group), the nearest level with a fresh question is used and reported, so the trace and
    the UI can say so truthfully instead of quietly serving another level."""
    exact = _fresh(pool(group, skill=skill, levels=(lvl,)), asked)
    if exact:
        return choose(exact, asked, active, rng), None
    for L in sorted((1, 2, 3), key=lambda L: (abs(L - lvl), L)):
        if L == lvl:
            continue
        fresh = _fresh(pool(group, skill=skill, levels=(L,)), asked)
        if fresh:
            return choose(fresh, asked, active, rng), L
    cands = pool(group, skill=skill)
    if cands:  # every question of this skill was asked recently: repeat the least-recent one
        t = choose(cands, asked, active, rng)
        return t, (t.difficulty if t.difficulty != lvl else None)
    t = choose(_fresh(pool(group, skill="accounting"), asked) or pool(group, skill="accounting"), asked, active, rng)
    return t, t.difficulty


def pick_mock(group: str | None, persona: str, levels: dict[str, int], weights: dict[str, float],
              asked: list[str], active: dict[str, int], rng: random.Random, focus: str | None = None) -> bank.Template:
    """A mock interview: the interviewer's seniority sets the fit/technical mix; the group sets the technical mix."""
    if focus:
        lvl = target_level(levels.get(focus, 0))
        return pick_targeted(group, focus, lvl, None, asked, active, rng)
    if rng.random() < FIT_SHARE.get(persona, 0.2):
        lvl = 1 if persona in ("associate", "vp") else rng.choice([1, 2, 2, 3])
        return pick_targeted(group, "fit", lvl, None, asked, active, rng)
    skills = list(bank.TECHNICAL)
    if group and group != "generalist" and pool(group, skill="industry"):
        skills.append("industry")
    w = [weights.get(s, 1.0) * (1.4 if s == "industry" else 1.0) for s in skills]
    skill = rng.choices(skills, weights=w)[0]
    return pick_targeted(group, skill, target_level(levels.get(skill, 0)), None, asked, active, rng)


# --------------------------------------------------------------------------- placement (diagnostic)
def diagnostic_skills(group: str | None) -> list[str]:
    order = ["accounting", "ev", "dcf", "ma", "lbo"]
    if group and group != "generalist" and pool(group, skill="industry"):
        order.append("industry")
    order.append("fit")
    return order


def first_level(group: str | None, skill: str) -> int:
    for L in (1, 2, 3):
        if pool(group, skill=skill, levels=(L,)):
            return L
    return 1
