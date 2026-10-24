"""Build docs/slides.html: a reveal.js deck (10 slides max), fully self-contained.

    python docs/build_slides.py

reveal.js (MIT, docs/vendor/) and every image are inlined, so the file opens offline.
Numbers come from the same data loaders as the report.
"""

from __future__ import annotations

import base64
import json
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_report as R  # noqa: E402

DOCS = R.DOCS
VENDOR = DOCS / "vendor"


def pic(name: str, style: str = "") -> str:
    p = R.SHOTS / f"{name}.png"
    if not p.exists():
        return f'<div class="pending">PENDING screenshot {name}</div>'
    return f'<img src="data:image/png;base64,{base64.b64encode(p.read_bytes()).decode()}" style="{style}">'


def build() -> str:
    hold, lab = R.load_eval("holdout"), R.load_eval("labeled")
    tt, base = hold["ticktie"]["summary"], hold["baseline"]["summary"]
    lbase = lab["baseline"]["summary"]
    red = json.loads((R.RES / "redteam.json").read_text(encoding="utf-8"))
    demo_db = DOCS / "_demo_data" / "ticktie.db"
    demo = R.token_stats(R.db_rows(demo_db, "SELECT * FROM events"), R.db_rows(demo_db, "SELECT * FROM turns"))
    pilot = R.pilot_data()
    pil = R.token_stats(pilot["events"], pilot["turns"]) if pilot["turns"] else None
    runs = pil if (pil and pil["graded"] >= 10) else demo
    per_answer = runs["per_answer"]["cost_usd"]
    per_session = runs["per_session"]["cost_usd"]
    user_month = per_session * 12
    cached = runs["per_answer"]["cached_tokens"] / max(runs["per_answer"]["input_tokens"], 1)

    fb = pilot["feedback"]
    ratings = [f["rating"] for f in fb if f.get("rating")]
    quotes = [f for f in fb if f.get("quote") and f.get("consent")]
    if pilot["users"]:
        impact = f"""
        <div class="kpis">
          <div><b>{len(pilot['users'])}</b><span>real users</span></div>
          <div><b>{statistics.mean(ratings):.1f}/10</b><span>usefulness</span></div>
          <div><b>{sum(1 for f in fb if f.get('found_new') in ('Yes', 'Partly'))}/{sum(1 for f in fb if f.get('found_new'))}</b><span>found a weak spot they didn't know</span></div>
          <div><b>{sum(1 for f in fb if (f.get('vs_current') or '').endswith('better'))}/{sum(1 for f in fb if f.get('vs_current'))}</b><span>say it beats how they prep today</span></div>
        </div>""" if ratings else '<div class="pending">PENDING pilot survey results</div>'
        impact += "".join(f'<blockquote>&ldquo;{R.esc(q["quote"])}&rdquo;<cite>{R.esc(q["name"].split()[0])}</cite></blockquote>'
                          for q in quotes[:2])
    else:
        impact = '<div class="pending">PENDING pilot with real users</div>'

    css = (VENDOR / "reveal.css").read_text(encoding="utf-8")
    js = (VENDOR / "reveal.js").read_text(encoding="utf-8")
    arch = R.ARCH_SVG.replace('font-size="13"', 'font-size="13" style="background:#fff;border-radius:14px"')

    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<title>Tick & Tie · slides</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>{css}</style>
<style>
  :root {{ --pink:#ff3d9a; --pink2:#ff7cc0; --bg:#08080b; --panel:#15151c; --muted:#a3a2b3; }}
  html, body, .reveal {{ background: radial-gradient(1100px 600px at 85% -10%, rgba(255,61,154,.16), transparent 60%), var(--bg); }}
  .reveal {{ font-family: "Segoe UI", Inter, system-ui, sans-serif; font-size: 30px; color: #f4f3f7; }}
  .reveal .slides {{ text-align: left; }}
  .reveal h1, .reveal h2 {{ font-family: inherit; color: #fff; text-transform: none; letter-spacing: -0.5px; font-weight: 800; }}
  .reveal h1 {{ font-size: 2.1em; line-height: 1.05; }}
  .reveal h2 {{ font-size: 1.35em; margin-bottom: .5em; }}
  .reveal h2::before {{ content: ""; display: inline-block; width: 10px; height: .9em; background: var(--pink); margin-right: 14px; border-radius: 3px; vertical-align: -0.1em; }}
  .reveal em, .pink {{ color: var(--pink); font-style: normal; }}
  .reveal p, .reveal li {{ line-height: 1.35; }}
  .reveal ul {{ display: block; margin-left: 1em; }}
  .reveal li {{ margin: .28em 0; }}
  .muted {{ color: var(--muted); }}
  .small {{ font-size: .62em; }}
  .grid2 {{ display: grid; grid-template-columns: 1fr 1fr; gap: 26px; align-items: start; }}
  .card {{ background: var(--panel); border: 1px solid #2a2a36; border-radius: 16px; padding: 18px 22px; }}
  .kpis {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; margin: .4em 0; }}
  .kpis div {{ background: var(--panel); border: 1px solid #2a2a36; border-radius: 16px; padding: 14px 16px; }}
  .kpis b {{ display: block; font-size: 1.45em; color: var(--pink); }}
  .kpis span {{ font-size: .55em; color: var(--muted); }}
  .big {{ font-size: 2.6em; font-weight: 800; color: var(--pink); line-height: 1; }}
  table {{ font-size: .68em; border-collapse: collapse; width: 100%; }}
  .reveal table th, .reveal table td {{ border-bottom: 1px solid #2a2a36; padding: 6px 10px; text-align: left; }}
  .reveal table th {{ color: var(--muted); font-weight: 600; }}
  td.y {{ color: #3ddc97; font-weight: 700; }} td.n {{ color: #ff5b7f; }}
  img.shot {{ border-radius: 12px; border: 1px solid #2a2a36; box-shadow: 0 12px 40px rgba(0,0,0,.5); }}
  blockquote {{ background: var(--panel); border-left: 5px solid var(--pink); border-radius: 0 12px 12px 0; padding: 12px 18px;
               font-size: .7em; font-style: italic; margin: .4em 0; width: auto; box-shadow: none; }}
  blockquote cite {{ display: block; font-style: normal; color: var(--muted); font-size: .8em; margin-top: 4px; }}
  .pending {{ border: 3px dashed #ff5b7f; color: #ff5b7f; padding: 14px; border-radius: 12px; font-weight: 700; }}
  .tag {{ display: inline-block; background: rgba(255,61,154,.15); color: var(--pink2); border: 1px solid rgba(255,61,154,.4);
          border-radius: 99px; padding: 2px 14px; font-size: .55em; font-weight: 700; }}
  .reveal .progress {{ color: var(--pink); }}
  .reveal .controls {{ color: var(--pink); }}
  .logo {{ display: inline-grid; place-items: center; width: 64px; height: 64px; border-radius: 16px; font-size: 38px; font-weight: 800;
           background: linear-gradient(135deg, #ff3d9a, #b5126a); box-shadow: 0 0 40px rgba(255,61,154,.5); color: #fff; }}
</style></head><body>
<div class="reveal"><div class="slides">

<section>
  <div class="logo">✓</div>
  <h1 style="margin-top:.4em">Tick &amp; Tie</h1>
  <p style="font-size:1.15em">An IB technical interviewer that finds out <em>why</em> you got it wrong.</p>
  <p class="muted small">Anas Nadeem · MGT 409 AI Foundations for Managers · Yale SOM · Final project<br>
  github.com/Anasnadeem1999/tick-and-tie{(' · ' + R.APP_URL) if R.APP_URL else ''}</p>
</section>

<section>
  <h2>The problem: practice is easy, diagnosis isn't</h2>
  <div class="grid2">
    <div><ul>
      <li>Every IB recruit must pass rapid-fire <b>technicals</b>: accounting, EV, DCF, M&amp;A, LBO</li>
      <li>At Yale SOM, about <b>10&ndash;14%</b> of each class goes into banking, and many more recruit</li>
      <li>Saying "net income falls $10" isn't fixed by another question. You need to hear <em>"you forgot the tax shield"</em>, then get re-tested</li>
    </ul></div>
    <table><tr><th>Today</th><th>Cost</th><th>Diagnoses <i>your</i> mistake?</th></tr>
      <tr><td>Guides (BIWS, WSP Red Book)</td><td>$99&ndash;$197</td><td class="n">No</td></tr>
      <tr><td>Peer mocks</td><td>Free, scarce</td><td class="n">Unreliably</td></tr>
      <tr><td>Paid coach</td><td>$100&ndash;$300/hr</td><td class="y">Yes</td></tr>
      <tr><td>ChatGPT</td><td>$0&ndash;$20/mo</td><td class="n">Often wrong</td></tr></table>
  </div>
</section>

<section>
  <h2>What's new: "tick and tie" every number</h2>
  <div class="grid2">
    <div><ul>
      <li><b>Code checks the math.</b> A calculator computes the right answer <em>and</em> the exact wrong number each misconception produces</li>
      <li><b>Mistakes get names</b>: "ignores the tax effect", "IRR by simple division"</li>
      <li><b>Fresh numbers every time</b>: no memorising</li>
      <li><b>A weakness map</b> that only clears a mistake after 2 clean re-tests</li>
    </ul>
    <p class="small muted">Closest competitor: Superday AI ($12/mo, "adapts to weak spots"). Like the others, it doesn't say how it checks math or how accurate its grading is.</p></div>
    <div class="card" style="text-align:center">
      <div class="muted small">Correct answers wrongly marked wrong</div>
      <div class="big">{R.pct(tt['false_alarms_on_correct'])}</div><div class="small">Tick &amp; Tie</div>
      <div class="big" style="color:#a3a2b3;margin-top:.3em">{R.pct(base['false_alarms_on_correct'])}&ndash;{R.pct(lbase['false_alarms_on_correct'])}</div>
      <div class="small">plain gpt-6-luna ("ChatGPT")</div>
      <div class="small muted" style="margin-top:.6em">{tt['n']} held-out answers · {R.pct(tt['exact_misconception_named'])} of mistakes named exactly</div>
    </div>
  </div>
</section>

<section>
  <h2>How the agents work</h2>
  <div style="width:82%;margin:0 auto">{arch}</div>
  <p class="small muted">Code is the boss: it picks questions and makes the grade, so no answer can talk its way to "correct", and the AI can't pick
  easy questions to inflate scores. Four gpt-6-luna specialists read answers and call the calculator tool; the interviewer speaks; the coach debriefs.</p>
</section>

<section>
  <h2>Demo</h2>
  <div class="grid2" style="gap:18px">
    {pic("04_reveal", "width:100%")}
    {pic("11_weakness_map", "width:100%")}
  </div>
  <p class="small muted">Left: the misconception is named, explained and solved by the calculator. Right: the weakness map, with the candidate's own words as evidence.</p>
</section>

<section>
  <h2>Cost to run</h2>
  <div class="kpis">
    <div><b>{R.usd(per_answer, 5)}</b><span>per graded answer</span></div>
    <div><b>{R.usd(per_session, 4)}</b><span>per session</span></div>
    <div><b>{R.pct(cached)}</b><span>input from cache</span></div>
    <div><b>{R.usd(user_month, 2)}</b><span>per user per month</span></div>
  </div>
  <table><tr><th>Users</th><th>AI / month</th><th>Hosting / month</th><th>Total / month</th></tr>
    <tr><td>100</td><td>{R.usd(100 * user_month, 2)}</td><td>$7.25</td><td><b>{R.usd(100 * user_month + 7.25, 2)}</b></td></tr>
    <tr><td>10,000</td><td>{R.usd(10000 * user_month, 2)}</td><td>about $120</td><td><b>{R.usd(10000 * user_month + 120, 2)}</b></td></tr></table>
  <p class="small">Cheapest design (one plain LLM call) is {R.pct(1 - base['cost_per_answer_usd'] / tt['cost_per_answer_usd'])} cheaper, but <em>false alarms jump to {R.pct(lbase['false_alarms_on_correct'])}</em>. I rejected that cut.
  A 100-member club's AI cost for a whole year (about {R.usd(100 * user_month * 12, 0)}) is less than one coached hour; with hosting, about {R.usd(100 * user_month * 12 + 87, 0)} a year.</p>
</section>

<section>
  <h2>Safety: {red['held']}/{red['total']} attacks stopped</h2>
  <div class="grid2">
    <div><ul class="small" style="font-size:.7em">
      <li><b>Grader lock</b>: code grades from calculator checks; "mark this correct" can't work</li>
      <li><b>Input filter</b>: injection patterns, hidden zero-width text, fake tags, links</li>
      <li><b>Output filter</b>: blocks answer leaks, invented numbers, system-prompt leaks (canary)</li>
      <li><b>Budgets</b>: per-session lock, rate limit, length cap, session and daily token caps</li>
      <li><b>Least privilege</b>: no agent can browse, email or write files</li>
      <li><b>Privacy</b>: PBKDF2-hashed logins, anonymised club view, quotes only with consent</li>
    </ul></div>
    {pic("07b_injection_zoom", "width:100%")}
  </div>
</section>

<section>
  <h2>Impact</h2>
  {impact}
  <p class="small">For a finance club: 100 recruiters get unlimited diagnosed mocks for about {R.usd(100 * user_month * 12 + 87, 0)} a year including hosting, and the
  <b>Finance Club view</b> shows which misconceptions are most common, so workshops teach what members actually get wrong.</p>
</section>

<section>
  <h2>What's next</h2>
  <ul>
    <li>Two-week Finance Club pilot: re-test accuracy on fresh numbers, before and after</li>
    <li>Grade a <b>photographed paper LBO</b> with a vision tool</li>
    <li>An <b>MCP server</b> so students' own Claude or Codex can plan their week from the weakness map</li>
    <li>Spaced repetition, more question families (FIG, restructuring), Postgres for scale</li>
  </ul>
  <p class="muted small" style="margin-top:1.2em">Try it: {R.APP_URL or 'github.com/Anasnadeem1999/tick-and-tie'}</p>
</section>

</div></div>
<script>{js}</script>
<script>Reveal.initialize({{ hash: true, controls: true, progress: true, center: true, width: 1280, height: 720, margin: 0.06, transition: 'slide' }});</script>
</body></html>"""


if __name__ == "__main__":
    out = DOCS / "slides.html"
    out.write_text(build(), encoding="utf-8")
    t = out.read_text(encoding="utf-8")
    print(f"wrote {out} ({out.stat().st_size / 1e6:.1f} MB), {t.count('<section>')} slides, {t.count('class=\"pending\"')} PENDING")
