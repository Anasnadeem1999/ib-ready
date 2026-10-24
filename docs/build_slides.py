"""Build docs/slides.html: a reveal.js deck (10 slides), fully self-contained, in the app's pastel colours.

    python docs/build_slides.py

reveal.js (MIT, docs/vendor/) and every image are inlined, so the file opens offline.
Every number comes from the same computation as the report (build_report.FACTS).
"""

from __future__ import annotations

import base64
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
    kind, b64 = R._image_data(p)
    return f'<img class="shot" src="data:image/{kind};base64,{b64}" style="{style}">'


def build() -> str:
    R.build()
    F = R.FACTS
    tt, base = F["tt"], F["base"]
    fa_lo, fa_hi = F["fa_lo"], F["fa_hi"]
    red = F["red"] or {"held": "?", "total": "?"}
    usd, pct, esc = R.usd, R.pct, R.esc
    people, p_answers = F["people"], F["p_answers"]
    story = F["story"] or {}
    fb = F["fb"]
    quotes = [f for f in fb if f.get("quote")][:2]
    quote_html = "".join(f'<blockquote>&ldquo;{esc(q["quote"])}&rdquo;<cite>{esc(q["person"])}, pilot user</cite></blockquote>' for q in quotes)
    if not quote_html:
        quote_html = '<div class="pending">PENDING pilot quote (with consent)</div>'
    v_drill = [a for a in people.get("Vishal", {}).get("answers", []) if a["session_mode"] != "diagnostic" and a["skill"] == "accounting"]

    css = (VENDOR / "reveal.css").read_text(encoding="utf-8")
    js = (VENDOR / "reveal.js").read_text(encoding="utf-8")
    arch = R.ARCH_SVG.replace('font-size="13"', 'font-size="13" style="background:#fff;border-radius:16px"')
    name = esc(R.NAME)

    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<title>{name} · slides</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>{css}</style>
<style>
  :root {{ --p:#6a56c9; --p2:#5e4cc2; --bg:#f6f4fb; --panel:#ffffff; --line:#e4dff0; --ink:#2b2840; --muted:#5f5a75;
           --mint:#e7f8ef; --mint-ink:#237e5b; --rose:#fdeef2; --rose-ink:#b83d62; --butter:#fff8de; --sky:#e3f1fc; }}
  html, body, .reveal {{ background: radial-gradient(1000px 560px at 88% -8%, #ece8fb, transparent 60%), var(--bg); }}
  .reveal {{ font-family: Inter, "Segoe UI", system-ui, sans-serif; font-size: 30px; color: var(--ink); }}
  .reveal .slides {{ text-align: left; }}
  .reveal h1, .reveal h2 {{ font-family: inherit; color: var(--ink); text-transform: none; letter-spacing: -0.5px; font-weight: 800; }}
  .reveal h1 {{ font-size: 2.1em; line-height: 1.05; }}
  .reveal h2 {{ font-size: 1.3em; margin-bottom: .5em; }}
  .reveal h2::before {{ content: ""; display: inline-block; width: 10px; height: .9em; background: var(--p); margin-right: 14px; border-radius: 3px; vertical-align: -0.1em; }}
  .reveal em, .accent {{ color: var(--p); font-style: normal; font-weight: 700; }}
  .reveal p, .reveal li {{ line-height: 1.35; }}
  .reveal ul {{ display: block; margin-left: 1em; }}
  .reveal li {{ margin: .28em 0; }}
  .muted {{ color: var(--muted); }}
  .small {{ font-size: .62em; }}
  .grid2 {{ display: grid; grid-template-columns: 1fr 1fr; gap: 26px; align-items: start; }}
  .card {{ background: var(--panel); border: 1px solid var(--line); border-radius: 18px; padding: 18px 22px; box-shadow: 0 6px 24px rgba(76,60,140,.08); }}
  .kpis {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; margin: .4em 0; }}
  .kpis div {{ background: var(--panel); border: 1px solid var(--line); border-radius: 18px; padding: 14px 16px; box-shadow: 0 6px 24px rgba(76,60,140,.06); }}
  .kpis b {{ display: block; font-size: 1.4em; color: var(--p); }}
  .kpis span {{ font-size: .52em; color: var(--muted); }}
  .big {{ font-size: 2.5em; font-weight: 800; color: var(--p); line-height: 1; }}
  table {{ font-size: .62em; border-collapse: collapse; width: 100%; background: #fff; border-radius: 14px; overflow: hidden; }}
  .reveal table th, .reveal table td {{ border-bottom: 1px solid var(--line); padding: 6px 10px; text-align: left; }}
  .reveal table th {{ color: var(--muted); font-weight: 650; background: #f1eef9; }}
  td.y {{ color: var(--mint-ink); font-weight: 700; }} td.n {{ color: var(--rose-ink); }}
  img.shot {{ border-radius: 14px; border: 1px solid var(--line); box-shadow: 0 12px 40px rgba(76,60,140,.15); }}
  blockquote {{ background: #fff; border-left: 5px solid var(--p); border-radius: 0 14px 14px 0; padding: 12px 18px;
               font-size: .62em; font-style: italic; margin: .4em 0; width: auto; box-shadow: none; }}
  blockquote cite {{ display: block; font-style: normal; color: var(--muted); font-size: .8em; margin-top: 4px; }}
  .pending {{ border: 3px dashed var(--rose-ink); color: var(--rose-ink); padding: 14px; border-radius: 12px; font-weight: 700; font-size: .6em; }}
  .pill {{ display: inline-block; background: #ece8fb; color: var(--p2); border-radius: 99px; padding: 3px 14px; font-size: .5em; font-weight: 700; margin-right: 6px; }}
  .reveal .progress, .reveal .controls {{ color: var(--p); }}
  .logo {{ display: inline-grid; place-items: center; width: 70px; height: 70px; border-radius: 20px; font-size: 40px; font-weight: 800;
           background: linear-gradient(135deg, #a596ec, #6a56c9); box-shadow: 0 10px 40px rgba(106,86,201,.35); color: #fff; }}
</style></head><body>
<div class="reveal"><div class="slides">

<section>
  <div class="logo">✓</div>
  <h1 style="margin-top:.4em">{name}</h1>
  <p style="font-size:1.12em">Practice IB interviews. Learn <em>why</em> you got it wrong. Get a plan.</p>
  <p><span class="pill">code-checked math</span><span class="pill">named mistakes</span><span class="pill">concise-answer coaching</span><span class="pill">day-by-day plan</span></p>
  <p class="muted small">Anas Nadeem · MGT 409 AI Foundations for Managers · Yale SOM · Final project<br>{R.REPO_URL.replace('https://', '')}{(' · ' + R.APP_URL) if R.APP_URL else ''}</p>
</section>

<section>
  <h2>The problem: practice is easy, diagnosis isn't</h2>
  <div class="grid2">
    <div><ul style="font-size:.78em">
      <li>Every banking recruit must pass <b>technicals</b>: accounting, EV, DCF, M&amp;A, LBO, said out loud</li>
      <li>About <b>10&ndash;14%</b> of each Yale SOM class goes into banking, and many more recruit</li>
      <li>Anas preps <b>15 hours a week</b> with six free resources, yet finding weak spots took <b>about 2 hours</b>, and nothing flagged the real one: <em>answers too long</em></li>
    </ul></div>
    <table><tr><th>Today</th><th>Cost</th><th>Diagnoses <i>your</i> mistake?</th></tr>
      <tr><td>Guides (BIWS, WSP, 400 Qs)</td><td>$99&ndash;$197</td><td class="n">No</td></tr>
      <tr><td>Peer and second-year mocks</td><td>Free, scarce</td><td class="n">Sometimes</td></tr>
      <tr><td>Coaches</td><td>$100&ndash;$300/hr</td><td class="y">Yes</td></tr>
      <tr><td>ChatGPT</td><td>$0&ndash;$20/mo</td><td class="n">Calls {pct(fa_lo)}&ndash;{pct(fa_hi)} of right answers wrong</td></tr></table>
  </div>
</section>

<section>
  <h2>What's new: "tick and tie" every number</h2>
  <div class="grid2">
    <div><ul style="font-size:.74em">
      <li><b>Code checks the math</b>: a calculator computes the right answer <em>and</em> the wrong number each of {len(R.LIBRARY)} misconceptions produces</li>
      <li><b>Placement → plan → drill</b>, re-planned after every session</li>
      <li><b>Concise-answer coaching</b>, tracked over time</li>
      <li>Associate, VP, Director or MD; 13 coverage groups; voice</li>
    </ul>
    <p class="small muted">Superday AI, IB IQ and HARDO grade with an AI rubric. None says how it checks math or publishes its accuracy.</p></div>
    <div class="card" style="text-align:center">
      <div class="muted small">Correct answers wrongly marked wrong</div>
      <div class="big">{pct(tt.get('false_alarms_on_correct', 0))}</div><div class="small">{name}</div>
      <div class="big" style="color:#b83d62;margin-top:.3em">{pct(fa_lo)}&ndash;{pct(fa_hi)}</div>
      <div class="small">plain gpt-6-luna, across 3 runs</div>
      <div class="small muted" style="margin-top:.6em">{tt.get('n', '?')} held-out answers · {pct(tt.get('exact_misconception_named', 0))} of mistakes named exactly</div>
    </div>
  </div>
</section>

<section>
  <h2>How the agents work</h2>
  <div style="width:80%;margin:0 auto">{arch}</div>
  <p class="small muted">Code is the boss: it picks questions and makes the grade, so no answer can talk its way to "correct" (Goodhart). Six gpt-6-luna
  specialists read answers and call the calculator tool; the interviewer speaks; coach and planner write. The same calculators are an MCP server.</p>
</section>

<section>
  <h2>Demo: one real run</h2>
  <div class="grid2" style="gap:18px">
    {pic("07_wrong_first_try", "width:100%")}
    {pic("05_plan", "width:100%;max-height:430px;object-fit:cover;object-position:top")}
  </div>
  <p class="small muted">Left: a long answer with a classic mistake. The calculator names it, the interviewer nudges without giving the answer, and the length is flagged. Right: the plan computed to the interview date.</p>
</section>

<section>
  <h2>Cost to run</h2>
  <div class="kpis">
    <div><b>{usd(F['per_answer_cost'], 5)}</b><span>per graded answer</span></div>
    <div><b>{usd(F['per_session_cost'], 4)}</b><span>per practice session</span></div>
    <div><b>{pct(F['cached_share'])}</b><span>input served from cache</span></div>
    <div><b>{usd(F['user_month'], 2)}</b><span>per user per month</span></div>
  </div>
  <table><tr><th>Users</th><th>AI / month</th><th>Hosting / month</th><th>Total / month</th></tr>
    <tr><td>100</td><td>{usd(100 * F['user_month'], 2)}</td><td>$7.25</td><td><b>{usd(100 * F['user_month'] + 7.25, 2)}</b></td></tr>
    <tr><td>10,000</td><td>{usd(10000 * F['user_month'], 2)}</td><td>about $120</td><td><b>{usd(10000 * F['user_month'] + 120, 2)}</b></td></tr></table>
  <p class="small">Measured from real runs. The cheapest design (one plain LLM call) costs {usd(base.get('cost_per_answer_usd', 0), 5)} per answer, but false alarms jump to {pct(fa_lo)}&ndash;{pct(fa_hi)}: <em>rejected</em>.
  Cache, code-side math and caps keep a 100-member club under {usd(F['club_total_year'], 0)} a year, hosting included.</p>
</section>

<section>
  <h2>Safety: {red['held']}/{red['total']} attacks stopped</h2>
  <div class="grid2">
    <div><ul style="font-size:.6em">
      <li><b>Grader lock</b>: code grades from calculator checks</li>
      <li><b>Input filter</b>: injection, hidden text, fake tags, links</li>
      <li><b>Output filter</b>: answer leaks, invented numbers, prompt leaks (canary)</li>
      <li><b>Budgets</b>: one answer at a time, rate and length caps, session, daily and global token caps</li>
      <li><b>Least privilege</b>: no agent can browse, email or write files</li>
      <li>Independent QA: <b>20 more attacks</b> held; 2 real flaws found and fixed with tests</li>
    </ul></div>
    {pic("09_injection_blocked", "width:100%")}
  </div>
</section>

<section>
  <h2>Impact: real users</h2>
  <div class="kpis">
    <div><b>{len(people)}</b><span>pilot users recruiting for IB</span></div>
    <div><b>{sum(a['verdict'] == 'correct' for a in v_drill)}/{len(v_drill)}</b><span>right in the drill after the placement named the mistake</span></div>
    <div><b>{F['n_long_correct']}/{len(F['long_correct'])}</b><span>correct answers that were too long: now flagged</span></div>
    <div><b>2 h → 1 answer</b><span>to find a weak spot (pilot notes; logs)</span></div>
  </div>
  {quote_html}
  <p class="small">For a finance club: unlimited diagnosed mocks for 100 recruiters at about {usd(F['club_total_year'], 0)} a year, and an anonymized view of the most common mistakes to target workshops.</p>
</section>

<section>
  <h2>What's next</h2>
  <ul>
    <li>Four-week Finance Club pilot: re-test accuracy and answer length, before and after</li>
    <li>Grade a <b>photographed paper LBO</b> with a vision tool</li>
    <li>Spaced repetition; more Superday-level questions</li>
    <li>Postgres + Render deploy; students' own agents plan their week via the <b>MCP server</b></li>
  </ul>
  <p class="muted small" style="margin-top:1.2em">Try it: {R.APP_URL or R.REPO_URL.replace('https://', '')} · runs locally in about 3 minutes</p>
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
