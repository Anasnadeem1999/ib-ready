"""Export the pilot (real users) to docs/pilot_summary.json for the report, without anyone's answer text.

    python docs/export_pilot.py [path/to/ticktie.db ...]

Default source: the v1 pilot database next to this worktree (../tick-and-tie/data/ticktie.db), opened read-only.
Profiles are mapped to people with PEOPLE below (one person may have signed up twice); test profiles are dropped.
What is kept: per-answer skill, verdict, misconception ids, seconds and word count; per-call token counts; survey
rows (quotes only with the consent box ticked). No answer or question text leaves the database.
"""

from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = ROOT.parent / "tick-and-tie" / "data" / "ticktie.db"
OUT = ROOT / "docs" / "pilot_summary.json"

# profile name -> pilot person (first names only; both agreed to be named)
PEOPLE = {"anas": "Anas", "anas.nadeem@hotmail.com": "Anas", "vishal": "Vishal", "vish": "Vishal"}


def export(paths: list[Path]) -> dict:
    people: dict[str, dict] = {}
    calls: list[dict] = []
    feedback: list[dict] = []
    for path in paths:
        c = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)
        c.row_factory = sqlite3.Row
        prof = {r["id"]: PEOPLE.get(r["name"].strip().lower()) for r in c.execute("SELECT id, name FROM profiles")}
        for s in c.execute("SELECT * FROM sessions ORDER BY started"):
            who = prof.get(s["profile_id"])
            if not who:
                continue
            p = people.setdefault(who, {"sessions": [], "answers": []})
            turns = [dict(t) for t in c.execute("SELECT * FROM turns WHERE session_id=? ORDER BY id", (s["id"],))]
            graded = [t for t in turns if t["verdict"]]
            p["sessions"].append({"mode": s["mode"], "persona": s["persona"], "started": s["started"],
                                  "ended": s["ended"], "graded": len(graded)})
            for t in graded:
                p["answers"].append({"session_mode": s["mode"], "template_id": t["template_id"],
                                     "skill": t["skill"], "kind": t["kind"],
                                     "verdict": t["verdict"], "error_type": t["error_type"],
                                     "misconceptions": json.loads(t["misconceptions"] or "[]"),
                                     "seconds": round(t["seconds"]) if t["seconds"] else None,
                                     "words": len((t["answer"] or "").split()), "ts": t["ts"]})
            for e in c.execute("SELECT actor, input_tokens, cached_tokens, output_tokens, cost_usd FROM events "
                               "WHERE session_id=? AND kind='llm'", (s["id"],)):
                calls.append({"person": who, **dict(e)})
        for f in c.execute("SELECT * FROM feedback"):
            who = prof.get(f["profile_id"])
            if who:
                row = {k: f[k] for k in f.keys() if k not in ("id", "profile_id", "session_id", "quote")}
                if f["consent"] and f["quote"]:
                    row["quote"] = f["quote"]
                feedback.append({"person": who, **row})
        c.close()
    return {"source": [str(p.name) for p in paths], "people": people, "llm_calls": calls, "feedback": feedback}


if __name__ == "__main__":
    srcs = [Path(a) for a in sys.argv[1:]] or [DEFAULT_DB]
    data = export([p for p in srcs if p.exists()])
    OUT.write_text(json.dumps(data, indent=1), encoding="utf-8")
    n = sum(len(p["answers"]) for p in data["people"].values())
    print(f"wrote {OUT}: {len(data['people'])} people, {n} graded answers, {len(data['llm_calls'])} model calls, "
          f"{len(data['feedback'])} survey rows")
