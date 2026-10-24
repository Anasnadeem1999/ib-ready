# Learning design spec: content, calibration, beginner layer, coach voice, name

Owner: learning design (content). Status: review/spec only. No app code was changed.
Method: every numeric template in `ibready/bank.py` was instantiated with seeds 1-3 and read line by line, then each one was run 400 times to measure two things: (a) how often a misconception's wrong number falls inside the grading tolerance, which means a wrong answer gets marked correct, and (b) how often two misconceptions predict the same number, which makes the diagnosis ambiguous. The audit scripts are in the session scratchpad; the results are copied below.

---

## 0. Prioritized summary

| # | Pri | Area | Finding / change | Where |
|---|---|---|---|---|
| 1 | **P0** | Grading bug | `ev_tsm`: 22-27% of instances mark a **wrong** share count as correct (basic shares, or all options without the buyback), because the 1% relative tolerance is wider than the dilution itself. Fix: `tol_abs=0.05, tol_rel=0` on `diluted_shares`, `tol_abs=1, tol_rel=0` on `equity_value`, and gen `B ∈ {20,40,50,100}`. | §1.2 |
| 2 | **P0** | Grading bug | `mkt_rates_lbo`: a candidate who says "IRR unchanged" is graded correct 81% of the time, and the pre-tax error 100% of the time, because the shock moves IRR by less than the 1.0pp tolerance. Fix: make `lost_paydown` the required label, demote IRR to optional with `tol_abs=0.3`, and use `bp ∈ {200,300}`. | §1.2 |
| 3 | **P0** | Grading bug | `dcf_pv`: the simple-vs-compound discount misconception is undetectable 74% of the time, and the numbers aren't mental-math friendly ($100 / 1.157625). Fix: use paired parameters that give round answers, and set `tol_rel=0.003`. | §1.2 |
| 4 | **P0** | Grading bug | `dcf_ufcf`: UFCF can be negative, but the label is unsigned, so "+$20" is accepted when the truth is "-$20". Fix: `signed=True` on `ufcf`, and constrain gen so UFCF > 0. | §1.2 |
| 5 | **P0** | Grading bug | `ev_bridge`: the 1% tolerance on EV accepts a bridge that leaves out preferred stock or NCI 20% of the time, and a backwards bridge 3% of the time. All inputs are integers, so the answer is exact: use `tol_abs=0.5, tol_rel=0`. | §1.2 |
| 6 | **P0** | User feedback | Rewrite the coach voice to a warm, stress-aware mentor who is still always honest. Paste-ready `coach.md`, interviewer `reveal`/`nudge` lines, and 3 example debriefs. | §5 |
| 7 | **P0** | User feedback | Rename the app to **IB Ready** (user decision) in every user-facing string. Rename "Finance Club" to "For clubs" and move it out of the main tabs; rename "Agents & cost" to "Under the hood". | §6, §4.6 |
| 8 | **P0** | User feedback | Beginner layer: primer, glossary, "how levels work", "what's a misconception", empty states (all paste-ready). | §4 |
| 9 | **P0** | Calibration | Re-level 9 items so the coffee-chat/first-round experience is mostly Basic (for example `dcf_ufcf`, `c_dcf_wacc`, `c_lbo_leverage`, `b_why_firm` and `b_why_group` go to Basic; `acc_defrev`, `c_ev_negative` and `rx_waterfall` go to Intermediate). Add a level mix per interviewer. | §2 |
| 10 | P1 | Grading | `ma_stock`/`ma_cash`: the 1% tolerance on `pf_eps` accepts the "ignored premium" and "pre-tax interest" answers 10-26% of the time. Use `tol_abs=0.01, tol_rel=0` on all EPS labels. | §1.2 |
| 11 | P1 | Mental math | The M&A generator gives numbers like "net income $16.67mm, EPS $2.67". Swap in a generator that produces round EPS and target net income. | §1.2 |
| 12 | P1 | Grading | `mkt_rates_wacc`: the pre-tax-debt error is accepted 70% of the time (the gap is 0.04-0.16pp against a 0.1 tolerance). Use `tol_abs=0.02`. | §1.2 |
| 13 | P1 | Diagnosis | `dcf_ufcf`: "no tax" and "NWC sign" predict the same number 10% of the time. Fix: `NWC ∈ {12,18,24}`. | §1.2 |
| 14 | P1 | Coverage | Add 6 **Basic** templates: simple EV bridge, EV/EBITDA and P/E calc, EBITDA build, dividend walk, debt repayment walk, exit-multiple TV. | §3 |
| 15 | P1 | Prompt | `interviewer.md` says "Sound like a person in a Superday". That contradicts the coffee-chat calibration, so make it stage-aware. | §5.4 |
| 16 | P2 | Coverage | Add 6 **Intermediate** templates and 6 conceptual/behavioral items. | §3 |
| 17 | P2 | Copy nits | "a 8% cap rate"; LTV/CAC of 1.25 printed as "1.2x"; TV printed as "$1,373.30" after rounding to 1 dp; `c_lbo_what` grammar; misconception fix texts for inventory and preferred stock; `rx_waterfall` degenerate 100% case; `lbo_irr_rule` (1.5x, 3y) trap sits on the tolerance edge; `re_cap_rate` has no traps. | §1.3 |

Bottom line: the finance logic is sound. Every solve() and explain() matches standard IB interview conventions, and I found **no wrong answer keys**. The real problems are in grading tolerances (P0 1-5): in some templates a misconception's wrong answer is graded correct. That breaks the core promise that "code checks every number", so fix those before the demo.

---

## 1. Finance correctness audit

### 1.1 Template-by-template verdict (solve / traps / explain)

| Template | Math | Traps | Explain | Notes |
|---|---|---|---|---|
| acc_da | ✓ | ✓ | ✓ | Classic answer, correct: NI -X(1-t), cash +Xt, PP&E -X. |
| acc_writedown | ✓ | ✓ | ✓ | The deductibility assumption is stated in the question. Good. |
| acc_sbc | ✓ | ✓ | ✓ | Equity +Xt (RE -X(1-t), APIC +X) is correct. Simplification: the tax deduction is taken at book expense. Fine, because it's stated. |
| acc_capex | ✓ | ✓ | ✓ | The tax rate is a deliberate distractor. Good. |
| acc_ar | ✓ | ✓ | ✓ | "Taxes paid in cash" is stated, so cash = -Xt is correct. |
| acc_debt | ✓ | ✓ | ✓ | |
| acc_rev_cash / acc_opex_cash | ✓ | ✓ | ✓ | |
| acc_inventory | ✓ | ✓ | ✓ | `t` is generated but not shown, so the after-tax ACC_CAPEX_EXPENSED signature can't be produced by a candidate. Harmless. Either drop it, or add "Tax rate is X%" to the text as a distractor (preferred: same pattern as capex). |
| acc_ap | ✓ | ✓ | ✓ | |
| acc_defrev | ✓ | ✓ | ✓ | Trap signatures hard-code 4 tax rates because none is given. OK. Better: add "Tax rate is 25%" to the text and use one signature, X·(1-t). |
| ev_bridge | ✓ | tolerance bug (P0-5) | ✓ | |
| ev_implied_price | ✓ | naming | ✓ | The 2nd EV_BRIDGE_SIGN signature (price = EV / shares) is really "skips the bridge". Move it to the new id **EV_SKIP_BRIDGE** (§3.4). |
| ev_debt_cash | ✓ | ✓ | ✓ | |
| ev_tsm | ✓ | tolerance bug (P0-1) | ✓ | |
| dcf_ufcf | ✓ | signed + collision (P0-4, P1-13) | ✓ | |
| dcf_tv | ✓ | ✓ | format nit | `money(round(tv,1))` prints "$1,373.30mm". Use `money(round(v['tv']))`, giving "$1,373mm". |
| dcf_wacc / dcf_capm | ✓ | ✓ | ✓ | |
| ma_stock / ma_cash / ma_debt | ✓ | EPS tolerance (P1-10) | ✓ | Ugly numbers (P1-11). |
| ma_goodwill | ✓ | ✓ | ✓ | Standard simplified PPA (no existing goodwill written off). Fine at Advanced. |
| lbo_paper / lbo_basic / lbo_irr_rule | ✓ | ✓ (see nit) | ✓ | IRR anchors (2x/5y ≈ 15%, 3x/5y ≈ 25%, 2x/3y ≈ 26%) verified. |
| mkt_rates_wacc | ✓ | tolerance (P1-12) | ✓ | The TV ∝ 1/(WACC-g) reasoning is correct. |
| mkt_rates_lbo | ✓ | tolerance bug (P0-2) | ✓ | |
| mkt_rates_ma | ✓ | ✓ | ✓ | |
| fig_ptbv / re_ffo / tmt_ltv / hc_rnpv / en_ebitdax | ✓ | ✓ | ✓ (LTV nit) | |
| re_cap_rate | ✓ | none | grammar | "a 8%" should be "an 8%". There are no traps, so it can never diagnose anything (§1.3). |
| rx_waterfall | ✓ | 8% degenerate | ✓ | X=800, S=400, U=400 gives 100% recovery for everyone, so the question has no point. |

The conceptual model answers were all checked and are correct, apart from one grammar slip in `c_lbo_what`.

### 1.2 Exact fixes (copy into `bank.py`)

**P0-1 `ev_tsm`** (wrong answers accepted in 22-27% of instances. Example: basic 200 vs truth 200.8 is inside 1%):
```python
def _tsm_gen(r):
    S = float(r.choice([20, 25, 40, 50]))
    return {"S": S, "B": float(r.choice([20, 40, 50, 100])), "N": float(r.choice([2, 4, 5, 10])),
            "K": float(r.choice([k for k in (10, 15, 20, 30) if k < S]))}
labels=[Label("diluted_shares", "Diluted shares (mm)", "mm", tol_abs=0.05, tol_rel=0),
        Label("equity_value", "Equity value ($mm)", "$", required=False, tol_abs=1.0, tol_rel=0)]
```

**P0-2 `mkt_rates_lbo`** ("no effect" is accepted in 81% of instances. Example: trap 18.47% vs truth 18.06%):
```python
# in _lbo_gen keep everything, but bp for this template only:
gen=lambda r: {**_lbo_gen(r), "bp": float(r.choice([200, 300]))},
labels=[Label("lost_paydown", "Lost debt paydown ($mm)", "$", tol_abs=0.5, tol_rel=0),        # now required
        Label("irr_new", "New IRR (%)", "%", required=False, tol_abs=0.3, tol_rel=0),
        Label("moic_new", "New MOIC (x)", "x", required=False, tol_abs=0.02, tol_rel=0)],
```
Also change the question's last sentence to "How much debt paydown is lost, and what's the new IRR?". The lost paydown is the actual skill being tested. The IRR moves too little to grade on its own.

**P0-3 `dcf_pv`** (simple-discount trap undetectable 74% of the time):
```python
_PV_SETS = [(121, 0.10, 2), (242, 0.10, 2), (605, 0.10, 2), (144, 0.20, 2), (1331, 0.10, 3), (288, 0.20, 2)]
gen=lambda r: (lambda s: {"X": float(s[0]), "r": s[1], "n": float(s[2])})(r.choice(_PV_SETS)),
labels=[Label("pv", "Present value", "$", tol_abs=0.5, tol_rel=0.003)],
```
Answers: 100, 200, 500, 100, 1000, 200. The simple-interest trap gives 100.83 / 201.67 / 504.17 / 102.86 / 1023.62 / 205.71, which is now distinguishable every time.

**P0-4 `dcf_ufcf`** (negative truth accepted with the wrong sign):
```python
labels=[Label("ufcf", "Unlevered free cash flow", "$", signed=True, tol_abs=0.05, tol_rel=0), ...]
gen: "NWC": float(r.choice([12, 18, 24]))   # also removes the DCF_NO_TAX ~ DCF_NWC_SIGN collision (P1-13)
# and resample if _ufcf(p) <= 0 (or drop EBIT=100 with CX=80)
```

**P0-5 `ev_bridge`**: `Label("ev", "Enterprise value ($mm)", "$", tol_abs=0.5, tol_rel=0)`. Also, more generally: any "$" label whose inputs are all integers should use `tol_abs=0.5, tol_rel=0`, because the 1% default is too loose for big numbers. That covers ev_implied_price `ev`/`equity_value`, fig/re/rx, and lbo `equity_*`.

**P1-10 EPS labels** (`ma_stock`, `ma_cash` `pf_eps`): `tol_abs=0.01, tol_rel=0`.

**P1-11 M&A generator** (round EPS, round target NI, new shares mostly whole numbers):
```python
def _ma_gen(r):
    eps = float(r.choice([2, 4])); pea = float(r.choice([10, 15, 20]))
    return {"Pa": eps * pea, "Sa": 100.0, "PEa": pea, "Mt": float(r.choice([600, 1200])),
            "prem": r.choice([0.20, 0.25, 0.50]), "PEt": float(r.choice([10, 12, 15, 20, 30])),
            "r": r.choice([0.04, 0.05]), "rd": r.choice([0.06, 0.08, 0.10]), "t": r.choice([0.20, 0.25, 0.40])}
```
Every input is now a round number (acquirer NI $200mm or $400mm; target NI $20-120mm). Drop `t=0.30` from the M&A set so the after-tax rates stay friendly (8% × 0.75 = 6%).

**P1-12 `mkt_rates_wacc`**: `Label("wacc_new", ..., tol_abs=0.02, tol_rel=0)`, `Label("tv_change", ..., tol_abs=0.3, tol_rel=0)`.

### 1.3 Smaller fixes (P2)
- `re_cap_rate` text and explain: write the article correctly ("an 8% cap rate"). It has no traps, so it never diagnoses anything. Simplest fix: keep it numeric-only and add the key point "a lower cap rate means a higher price" so the grader can probe it conceptually.
- `tmt_ltv` explain: `num(v['ratio'], 2)`, so 1.25 doesn't print as "1.2x".
- `lbo_irr_rule`: remove the (1.5, 3) combo. The simple-math answer (16.7%) is 2.2pp from the truth, right on the 2.0 tolerance edge. Use (1.5, 2) instead: truth 22.5%, trap 25%. Better still, tighten to `tol_abs=1.5`.
- `rx_waterfall`: gen `X ∈ {500, 600, 700}` so value is always less than total claims.
- `c_lbo_what` key point: "The company's own cash flow pays the interest and pays down the debt".
- `misconceptions.py`:
  - `ACC_CAPEX_EXPENSED.fix`, append: "Inventory works the same way: it sits on the balance sheet and hits COGS only when it's sold."
  - `EV_MISS_CLAIMS.fix`, insert: "Preferred stock is a claim senior to common shareholders, so it's added like debt; NCI is added because EBITDA includes 100% of subsidiaries you only partly own."

---

## 2. Level calibration

**Working definitions.** Use these in code comments and in the UI, §4.3.
- **Basic = coffee chat / first round.** An Associate or VP would expect every candidate to answer it cleanly in under 60 seconds with no paper. These are the standard "walk me through" questions and single-step math.
- **Intermediate = Superday.** Two or three steps, with some judgement, or a well-known trap (working capital, TSM, accretion, paper LBO).
- **Advanced = specialist or stretch.** Purchase accounting, rate shocks, deferred taxes, edge cases, mostly for group-specific or very technical interviewers.

### 2.1 Proposed re-levelling (META changes)

| Template | Now | Proposed | Reason |
|---|---|---|---|
| dcf_ufcf | 2 | **1** | "How do you get to unlevered FCF?" is one of the most common first-round questions. It's a single formula. |
| c_dcf_wacc | 2 | **1** | "WACC down, value?" is a pure intuition question that comes straight after "walk me through a DCF". |
| c_lbo_leverage | 2 | **1** | "Why does leverage boost returns" is the natural follow-up to "what is an LBO" (already Basic). |
| b_why_firm | 2 | **1** | One of the "Big 5" that come up in every interview, including coffee chats. |
| b_why_group | 2 | **1** | Asked in the first 5 minutes of most coffee chats ("what group are you interested in?"). |
| acc_defrev | 3 | **2** | One-step walk (NI 0, cash +X). Hard only because it's unfamiliar. A classic Superday SaaS question. |
| c_ev_negative | 3 | **2** | Classic Superday curveball, not specialist material. |
| rx_waterfall | 3 | **2** | Simple arithmetic. For restructuring candidates it's the core group question. |
| ev_bridge | 1 | **2** | Including preferred stock and NCI makes it a Superday-level question. Replace the Basic slot with the new `ev_bridge_basic` (debt and cash only, §3.2 #1). |

Keep as is (checked): acc_da, acc_capex, acc_rev_cash, acc_opex_cash, acc_inventory and dcf_capm at 1. acc_ar, acc_ap, acc_debt, acc_sbc, ev_tsm, ev_implied_price, dcf_wacc, dcf_tv, ma_* accretion and lbo_paper at 2. ma_goodwill, mkt_rates_*, c_acc_dtl and c_mkt_duration at 3. (`ma_stock/cash/debt` are created with `difficulty=3` but META sets them to 2. Keep 2, but only once the P1-11 friendly numbers are in.)

### 2.2 Level mix per interviewer (for `mastery.pick_next` / mock composition)

| Interviewer | Typical setting | Technical : behavioral | Basic / Intermediate / Advanced (of technicals) |
|---|---|---|---|
| Associate | Coffee chat / first round | 70 : 30 | 70 / 25 / 5 |
| Vice President | First round / Superday technical | 80 : 20 | 45 / 45 / 10 |
| Director | Superday | 40 : 60 | 40 / 50 / 10 |
| Managing Director | Superday final | 15 : 85 | 70 / 30 / 0 (an MD asks one simple technical to check fundamentals) |

The placement interview should start every skill at Basic and step up only after a clean Basic answer. That way a nervous beginner's first three questions are ones they can win.

---

## 3. Coverage gaps and new templates

### 3.1 Highest-frequency gaps (by sub-skill)

| Sub-skill | Missing at Basic | Missing at Intermediate |
|---|---|---|
| ev.bridge | EV with debt and cash only | Issuing stock / paying dividends: EV vs equity value |
| ev.multiples | Calculating EV/EBITDA and P/E | (exists: implied price) |
| accounting.is_basics | Revenue → gross profit → EBITDA → EBIT → NI | n/a |
| accounting.links (equity) | Paying a dividend | Issuing stock |
| accounting.debt | Repaying principal | n/a |
| accounting.capex | n/a | Selling PP&E at a gain |
| dcf.terminal_value | Exit-multiple TV, discounted | n/a |
| dcf.discount_rate | Why equity costs more than debt (conceptual) | Unlevering beta |
| ma.accretion | n/a | Break-even synergies |
| lbo.returns | n/a | Returns attribution (the three levers) |
| industry.credit | Leverage and coverage ratios | n/a |
| fit / understanding banking | What an analyst does; a failure story | Sell-side M&A process |

### 3.2 Twelve new numeric templates (full specs)

All ranges were simulated 300 times: zero wrong answers inside tolerance and zero misconception collisions after the range fixes noted.

Conventions: amounts in $mm unless stated; `t` is the tax rate; every "$" label is `tol_abs=0.5, tol_rel=0` and every "x" label is `tol_abs=0.05, tol_rel=0`, unless noted.

---

**#1 `ev_bridge_basic`: "Equity value to EV (the basics)"**. Level 1 · `ev.bridge` · 40 s
- Text: "A company's shares trade at ${S} and it has {Q} million shares outstanding. It has ${D}mm of debt and ${C}mm of cash. What are its equity value and enterprise value?"
- Params: S ∈ {10, 20, 25, 50}; Q ∈ {10, 20, 40}; D ∈ {100, 200, 300}; C ∈ {20, 50, 80} (D > C always, so the backwards bridge never equals the truth).
- Labels: `equity_value` = S·Q (required); `ev` = S·Q + D - C (required).
- Traps: **EV_ADD_CASH** ev = S·Q + D + C; **EV_BRIDGE_SIGN** ev = S·Q - D + C; **EV_SKIP_BRIDGE** (new) ev = S·Q.
- Explain: "Equity value = ${S} × {Q}mm = ${EqV}mm: what the shares are worth. EV adds the lenders' claim and takes out the cash the buyer effectively gets back: ${EqV} + ${D} - ${C} = ${EV}mm."
- Key points: Equity value = share price × shares · EV = equity value + debt - cash · Cash is subtracted because it isn't part of the operating business.

**#2 `ev_multiples_calc`: "Calculating EV/EBITDA and P/E"**. Level 1 · `ev.multiples` · 60 s
- Text: "Share price ${S}, {Q} million shares, ${D}mm of debt, ${C}mm of cash. EBITDA is ${E}mm and net income is ${NI}mm. What are its EV/EBITDA and P/E multiples?"
- Params: (S, Q) ∈ {(50,20), (25,40), (20,50)} (equity value always $1,000mm); (D, C) ∈ {(300,100), (500,100), (600,200)}; E ∈ {100, 120, 200}; NI ∈ {40, 50, 80, 100}.
- Labels: `ev_ebitda` = (S·Q + D - C)/E; `pe` = S·Q/NI (equivalently price/EPS).
- Traps: **EV_MULTIPLE_MISMATCH** ev_ebitda = S·Q/E, or pe = (S·Q + D - C)/NI; **EV_ADD_CASH** ev_ebitda = (S·Q + D + C)/E.
- Explain: "EV = $1,000 + ${D} - ${C} = ${EV}mm, so EV/EBITDA = ${EV} / ${E} = {x}x. P/E uses equity value because net income is what's left for shareholders: $1,000 / ${NI} = {y}x."
- Key points: EV pairs with EBITDA (before interest, all investors) · Equity value pairs with net income (after interest, shareholders only).

**#3 `acc_ebitda_build`: "From revenue to net income"**. Level 1 · `accounting.is_basics` · 60 s
- Text: "Revenue is ${R}, cost of goods sold is ${COGS}, SG&A is ${SGA}, and D&A, shown on its own line, is ${DA}. Interest expense is ${I} and the tax rate is {t}. What are EBITDA, EBIT and net income?"
- Params: R ∈ {500, 1000}; COGS = R × {0.4, 0.5}; SGA ∈ {100, 150}; DA ∈ {20, 50}; I ∈ {10, 20}; t ∈ {20%, 25%}.
- Labels: `ebitda` = R - COGS - SGA (req); `ebit` = EBITDA - DA (req); `ni` = (EBIT - I)(1 - t) (optional).
- Traps: **ACC_EBITDA_AFTER_DA** (new) ebitda = EBITDA - DA; **ACC_INTEREST_IN_EBIT** (new) ebit = EBIT - I; **ACC_NO_TAX** ni = EBIT - I.
- Explain: "Gross profit = ${R} - ${COGS} = ${GP}. EBITDA = GP - SG&A = ${EBITDA}. EBIT subtracts D&A: ${EBIT}. Pre-tax income subtracts interest: ${EBT}; after {t} tax, net income is ${NI}. EBIT is before interest because it measures the business, not how it's financed."
- Key points: EBITDA is before D&A · EBIT is before interest · Net income is after interest and taxes.

**#4 `acc_dividend`: "3-statement walk: paying a dividend"**. Level 1 · `accounting.links` · 45 s
- Text: "A company pays a ${X} cash dividend to its shareholders. Tax rate is {t}. Walk me through the three statements."
- Params: X ∈ {10, 20, 40, 50, 100}; t ∈ {20%, 25%, 40%} (a distractor).
- Labels: `ni` = 0 (req); `cash` = -X (req); `equity` = -X (optional).
- Traps: **ACC_DIVIDEND_EXPENSED** (new) {ni: -X(1-t), cash: -X(1-t)} or {ni: -X}.
- Explain: "Nothing on the income statement: a dividend is a distribution of profit, not an expense, so it isn't tax-deductible. On the cash flow statement it's a financing outflow of ${X}. Balance sheet: cash down ${X}, retained earnings down ${X}."
- Key points: Dividends never hit the income statement · Financing cash outflow · Cash and retained earnings fall equally.

**#5 `acc_debt_repay`: "3-statement walk: repaying debt"**. Level 1 · `accounting.debt` · 40 s
- Text: "A company repays ${X} of debt principal with cash. Tax rate is {t}. Walk me through the three statements."
- Params: X ∈ {50, 100, 200}; t ∈ {20%, 25%, 40%}.
- Labels: `ni` = 0; `cash` = -X; `debt` = -X (optional).
- Traps: **ACC_PRINCIPAL_EXPENSED** (new) {ni: -X(1-t), cash: -X(1-t)} or {ni: -X}.
- Explain: "Repaying principal isn't an expense; only interest is. So nothing changes on the income statement. Financing cash flow shows -${X}. Balance sheet: cash down ${X}, debt down ${X}; both sides fall equally."
- Key points: Principal isn't an expense, interest is · Financing outflow · Cash and debt fall together.

**#6 `dcf_exit_tv`: "Terminal value with an exit multiple"**. Level 1 · `dcf.terminal_value` · 45 s
- Text: "In the final forecast year, year 5, EBITDA is ${E}mm. Similar companies trade at {m}x EBITDA. The year-5 discount factor is {df}, meaning $1 in year 5 is worth ${df} today. What's the terminal value, and what is it worth today?"
- Params: E ∈ {50, 80, 100, 120}; m ∈ {8, 10, 12}; df ∈ {0.5, 0.6, 0.75}.
- Labels: `tv` = E·m; `pv_tv` = E·m·df (both required).
- Traps: **DCF_TV_NOT_DISCOUNTED** (new) pv_tv = E·m; **DCF_DF_INVERTED** (new) pv_tv = E·m / df.
- Explain: "TV = {m}x × ${E} = ${TV}mm, the value at the end of year 5. Bring it back to today by multiplying by the discount factor: ${TV} × {df} = ${PV}mm."
- Key points: Exit multiple × final-year EBITDA · The TV is a future value, so discount it · Multiply by the discount factor (don't divide).

**#7 `ev_equity_issue`: "Does issuing stock change EV?"**. Level 2 · `ev.bridge` · 40 s
- Text: "A company issues ${X}mm of new shares at its current share price and keeps the cash. What happens to its equity value and its enterprise value?"
- Params: X ∈ {100, 200, 500}.
- Labels: `equity_value` = +X (signed); `ev` = 0.
- Traps: **EV_FINANCING_MOVES_EV** ev = +X, or equity_value = 0.
- Explain: "Equity value rises by ${X}mm: there are more shares at the same price. EV = equity value + debt - cash: equity value is up ${X} and cash is up ${X}, so EV doesn't change. The business itself is the same."
- Key points: Equity value rises by the amount raised · Cash rises by the same amount · EV is unchanged because operations are unchanged.

**#8 `acc_asset_sale`: "3-statement walk: selling an asset at a gain"**. Level 2 · `accounting.capex` · 75 s
- Text: "A company sells equipment with a book value of ${B} for ${P} in cash. The gain is taxed at {t}, paid in cash. Walk me through the three statements."
- Params: B ∈ {60, 80}; P ∈ {100, 120}; t ∈ {20%, 25%}.
- Labels: `ni` = (P - B)(1 - t); `cash` = P - (P - B)·t; `ppe` = -B (optional).
- Traps: **ACC_GAIN_DOUBLE_COUNT** (new) cash = P + (P - B)(1 - t); **ACC_NO_TAX** {ni: P - B, cash: P}; **ACC_PROCEEDS_AS_REVENUE** (new) ni = P(1 - t).
- Explain: "Income statement: a ${G} gain, taxed at {t}, raises net income by ${NI}. Cash flow statement: start with ${NI}, subtract the ${G} gain in operations (it's already counted in the proceeds), then add the ${P} proceeds in investing: cash is up ${Cash}, which is the proceeds minus the tax on the gain. Balance sheet: PP&E down ${B}, cash up ${Cash}; assets up ${NI}, matching retained earnings."
- Key points: Only the gain hits net income · Remove the gain from CFO and show full proceeds in CFI · Cash rises by proceeds minus tax.

**#9 `ma_synergies_breakeven`: "Synergies needed to break even"**. Level 2 · `ma.accretion` · 120 s
- Text: "An acquirer has 100mm shares at $20 and net income of $100mm (EPS $1.00). It buys a target with net income of ${NIt}mm for ${P}mm, paid entirely in new acquirer shares issued at $20. Tax rate is {t}. Ignore fees. Is the deal accretive or dilutive, and how much in pre-tax annual synergies would make it break even?"
- Params: P ∈ {400, 500, 600}; shortfall s ∈ {6, 9, 12, 15}; NIt = P/20 - s; t ∈ {25%, 40%}.
- Labels: `synergies` = (1.00 × (100 + P/20) - 100 - NIt)/(1 - t) = s/(1 - t) (req, `tol_abs=0.3`); `accretion` = ((100 + NIt)/(100 + P/20) - 1) × 100 (optional, %, `tol_abs=0.3`).
- Traps: **MA_SYNERGY_NO_GROSSUP** (new) synergies = s, or s·(1 - t); **MA_IGNORE_NEW_SHARES** (new) synergies = 0 / accretion computed on 100mm shares.
- Explain: "New shares = ${P} / $20 = {n}mm, so pro forma shares are {100+n}mm. To keep EPS at $1.00, combined net income must be ${100+n}mm; it's ${100+NIt}mm, a ${s}mm shortfall. Synergies are taxed, so pre-tax synergies = ${s} / (1 - {t}) = ${Syn}mm."
- Key points: Pro forma shares include the new shares · Break-even net income = standalone EPS × pro forma shares · Gross up the shortfall for taxes.

**#10 `dcf_unlever_beta`: "Unlevering beta"**. Level 2 · `dcf.discount_rate` · 60 s
- Text: "A comparable company has a levered beta of {bL}, a debt-to-equity ratio of {de} and a {t} tax rate. What's its unlevered beta?"
- Params: (t, D/E) ∈ {(20%, 0.25), (20%, 0.5), (25%, 0.4), (20%, 1.0)}, so the factor 1 + (1-t)·D/E ∈ {1.2, 1.4, 1.3, 1.8}; βu ∈ {0.8, 0.9, 1.0, 1.1, 1.2}; bL = βu × factor (rounded to 2 dp; the solver uses the shown bL).
- Labels: `beta_u` = bL / (1 + (1 - t)·D/E), `tol_abs=0.02, tol_rel=0`.
- Traps: **DCF_BETA_NO_TAX** (new) bL/(1 + D/E); **DCF_BETA_DIRECTION** (new) bL × (1 + (1 - t)·D/E).
- Explain: "Unlevering strips out financial risk: βu = βL / (1 + (1 - t) × D/E) = {bL} / (1 + {1-t} × {de}) = {bL} / {factor} = {βu}. The unlevered beta is always the smaller one, because debt adds risk for shareholders."
- Key points: Unlevered beta ≤ levered beta · Formula uses after-tax D/E · Unlever the peers, then relever at the target's structure.

**#11 `lbo_levers`: "Where did the LBO return come from?"**. Level 2 · `lbo.returns` · 120 s
- Text: "A sponsor buys a company with $100mm of EBITDA at {m0}x using ${D0}mm of debt. At exit, EBITDA is ${E1}mm, the exit multiple is {m1}x, and ${Dp}mm of debt has been repaid. How much equity value did the sponsor gain, and how much came from EBITDA growth (valued at the entry multiple), multiple expansion, and debt paydown?"
- Params: m0 ∈ {8, 10}; m1 = m0 + {0, 1, 2}; E1 ∈ {120, 150}; D0 ∈ {400, 500}; Dp ∈ {100, 200}.
- Labels: `equity_gain` = (E1·m1 - (D0 - Dp)) - (100·m0 - D0) (req); `ebitda_growth` = (E1 - 100)·m0; `multiple_exp` = (m1 - m0)·E1; `paydown` = Dp; `moic` (all optional; moic `tol_abs=0.05`).
- Traps: **LBO_NO_PAYDOWN** equity_gain = E1·m1 - 100·m0; **LBO_MOIC_ON_EV** moic = E1·m1/(100·m0).
- Explain: "Equity in = {m0}x × $100 - ${D0} = ${Ein}mm. Equity out = {m1}x × ${E1} - (${D0} - ${Dp}) = ${Eout}mm, a gain of ${G}mm: EBITDA growth ${E1-100} × {m0}x = ${g1}mm; multiple expansion {m1-m0}x × ${E1} = ${g2}mm; debt paydown ${Dp}mm. The three add up to the gain."
- Key points: Three levers: EBITDA growth, multiple expansion, debt paydown · They sum to the equity gain · Paydown is value moving from lenders to the sponsor.

**#12 `lev_credit_stats`: "Leverage and interest coverage"**. Level 1 · `industry.credit` · groups levfin, sponsors, restructuring · 40 s
- Text: "A company has ${E}mm of EBITDA and ${D}mm of debt at a {r} interest rate. What are its leverage ratio and interest coverage?"
- Params: E ∈ {100, 200}; (L, r) ∈ {(4, 5%), (5, 5%), (5, 8%), (4, 10%), (5, 10%), (2.5, 8%)}; D = L·E.
- Labels: `leverage` = D/E; `coverage` = E/(D·r).
- Traps: **CR_RATIO_INVERTED** (new) leverage = E/D, or coverage = D·r/E.
- Explain: "Leverage = debt / EBITDA = ${D} / ${E} = {L}x: years of EBITDA needed to repay the debt. Interest = ${D} × {r} = ${I}mm, so coverage = EBITDA / interest = {cov}x: how many times over the company can pay its interest."
- Key points: Leverage = debt / EBITDA (lower is safer) · Coverage = EBITDA / interest (higher is safer).

### 3.3 Conceptual and behavioral items (6)

| id | Level · sub-skill | Question | Key points | Mis. | Model answer (original) |
|---|---|---|---|---|---|
| `c_acc_most_important` | 1 · accounting.links | "If you could see only one financial statement, which would you pick, and why?" | Usually the cash flow statement · It shows real cash generation · Net income can hide working capital or capex · A solid alternative: BS + IS lets you rebuild the CFS | ACC_NONCASH_AS_CASH | "The cash flow statement, because cash is what pays debt, dividends and investment, and accounting profit can look healthy while cash drains through working capital or capex. If I could have two, I'd take the balance sheet and income statement, because together they let you rebuild the cash flow statement." |
| `c_dcf_tv_methods` | 1 · dcf.terminal_value | "What are the two ways to calculate terminal value, and when would you prefer each?" | Perpetuity growth: FCF × (1+g)/(WACC-g) · Exit multiple: EBITDA × multiple · Multiples are market-based; growth is more theoretical · Cross-check each with the other's implied number | DCF_TV_PLUS_G | "Perpetuity growth assumes cash flows grow at a modest rate forever; the exit multiple assumes the company is sold at a multiple like peers. Bankers often lead with the exit multiple because it's anchored in the market, then sanity-check the implied growth rate. The growth method suits stable businesses without good comps." |
| `c_dcf_equity_cost` | 1 · dcf.discount_rate | "Why is equity more expensive than debt?" | Equity holders are paid last · Their returns aren't fixed · Interest is tax-deductible | DCF_WACC_NO_SHIELD | "Shareholders are paid last and have no promised return, so they need a higher expected return for the extra risk. Lenders get fixed interest and are paid first, and interest is tax-deductible, so the after-tax cost of debt is lower still." |
| `c_ib_role` | 1 · fit.understanding_banking (new sub-skill) | "What do you think an investment banking analyst actually does day to day?" | Builds models and valuation analyses · Makes pitch books and client materials · Supports live deals (diligence, data rooms, process work) · Long hours, high attention to detail · Learns from Associates/VPs | FIT_GENERIC | "Most of the week goes into financial models, valuation work and presentation decks for pitches and live deals, plus process work like diligence lists and data rooms. The analyst is the team's engine: accuracy and turnaround matter most, and the payoff is a steep learning curve from seeing how senior bankers advise clients." |
| `b_failure` | 1 · fit.experiences | "Tell me about a time you failed." | A real failure you owned · What you did right after · A concrete lesson · Evidence you applied it later | FIT_FAKE_WEAKNESS, FIT_NO_EVIDENCE | "Pick a genuine setback where your choices mattered, own it in one sentence without blaming others, spend most of the answer on what you changed, and finish with a later example showing the lesson stuck." |
| `c_ma_sellside` | 2 · fit.understanding_banking | "Walk me through a sell-side M&A process." | Prep: teaser, CIM, buyer list · First round: NDAs, indications of interest · Second round: management meetings, data room, final bids · Negotiate the purchase agreement, sign, close | (none) | "The bank prepares marketing materials (a short teaser and a detailed information memorandum) and a buyer list. Interested buyers sign NDAs and submit non-binding first-round bids. A shortlist gets management meetings and data-room diligence, then submits final bids with a markup of the purchase agreement. The seller negotiates with the winner, signs, and closes after approvals." |

### 3.4 New misconceptions (append to `misconceptions.py`)

| id | skill | name | tell | fix |
|---|---|---|---|---|
| EV_SKIP_BRIDGE | ev | Treats equity value as enterprise value | "EV equals market cap" / divides EV by shares for the share price. | EV and equity value differ by the claims of other investors. Going up to EV: add debt (and preferred and NCI), subtract cash. Going down to equity value: the reverse, then divide by diluted shares. |
| ACC_EBITDA_AFTER_DA | accounting | Subtracts D&A to get EBITDA | EBITDA comes out equal to EBIT. | EBITDA is earnings *before* interest, taxes, depreciation and amortization, so D&A is not subtracted. EBIT = EBITDA - D&A. |
| ACC_INTEREST_IN_EBIT | accounting | Subtracts interest before EBIT | EBIT is reduced by interest expense. | EBIT measures the operating business before financing. Interest comes after EBIT, giving pre-tax income. |
| ACC_DIVIDEND_EXPENSED | accounting | Treats a dividend as an expense | Net income falls (often after tax) when a dividend is paid. | Dividends are a distribution of profit to owners, not a cost of running the business. They skip the income statement, aren't tax-deductible, and reduce cash and retained earnings directly. |
| ACC_PRINCIPAL_EXPENSED | accounting | Treats repaying debt as an expense | Net income falls when principal is repaid. | Only interest is an expense. Repaying principal just swaps cash for less debt: financing outflow, cash and debt both down. |
| ACC_GAIN_DOUBLE_COUNT | accounting | Counts an asset-sale gain twice in cash | Cash rises by the full proceeds plus the after-tax gain. | The gain is already inside the proceeds. On the cash flow statement subtract the gain from operating cash flow, then show the full proceeds in investing. |
| ACC_PROCEEDS_AS_REVENUE | accounting | Treats sale proceeds as revenue | Net income rises by the whole sale price after tax. | Selling an asset isn't revenue. Only the gain (price minus book value) hits the income statement. |
| DCF_TV_NOT_DISCOUNTED | dcf | Forgets to discount the terminal value | Adds the year-5 TV straight to today's value. | The terminal value is worth that amount at the end of the forecast. Multiply it by that year's discount factor (or divide by (1 + WACC)^n) before adding it up. |
| DCF_DF_INVERTED | dcf | Divides by a discount factor | Present value comes out bigger than the future value. | A discount factor is below 1 and you multiply by it. If your present value is larger than the future value, the operation is flipped. |
| DCF_BETA_NO_TAX | dcf | Unlevers beta without the tax shield | Uses 1 + D/E in the denominator. | Debt's risk to equity is softened by the interest tax shield: βu = βL / (1 + (1 - t) × D/E). |
| DCF_BETA_DIRECTION | dcf | Unlevers in the wrong direction | The unlevered beta comes out higher than the levered beta. | Removing debt removes financial risk, so the unlevered beta must be smaller. Divide by the leverage factor to unlever; multiply to relever. |
| MA_SYNERGY_NO_GROSSUP | ma | Forgets to gross synergies up for tax | Break-even synergies equal the after-tax EPS shortfall. | Synergies are taxed before they reach net income, so the pre-tax amount needed = net income shortfall / (1 - t). |
| MA_IGNORE_NEW_SHARES | ma | Forgets the new shares in a stock deal | Divides combined net income by the old share count. | In a stock deal the buyer issues new shares (purchase price / share price). Pro forma EPS divides combined net income by the old plus new shares. |
| CR_RATIO_INVERTED | industry | Flips a credit ratio | Leverage = EBITDA / debt or coverage = interest / EBITDA. | Leverage puts debt on top (how many years of EBITDA the debt equals); coverage puts EBITDA on top (how many times interest is covered). Lower leverage and higher coverage are safer. |

New sub-skill in `SUBSKILLS`: `"fit.understanding_banking": ("fit", "Understanding the job")`.

---

## 4. Beginner layer (paste-ready copy)

### 4.1 "What are IB technical interviews?" (120 words)
> **What are IB technical interviews?**
> Investment banks advise companies on big money decisions: buying another company, selling one, or raising money from investors. Before hiring you as an analyst, bankers check that you understand the basics of how companies are measured and valued. That's the "technical" part of the interview. Expect four families of questions: **accounting** (how a change ripples through the three financial statements), **valuation** (what a company is worth and why), **deals** (mergers and leveraged buyouts), and **you** (your story and why banking). Early conversations, such as coffee chats and first rounds, stick to the basics. Final rounds ("Superdays") go deeper. Nobody expects you to know everything. They want clear thinking, out loud, and honesty when you're unsure. That's exactly what you'll practise in IB Ready.

### 4.2 Glossary (one line each, plain English)
**The job and the process**
- **Investment banking (IB):** Advising companies on mergers, acquisitions and raising money.
- **Analyst / Associate / VP / Director / MD:** The ladder from entry level (Analyst) to senior (Managing Director). Juniors ask more technicals; seniors ask more about you.
- **Coffee chat:** An informal 15-30 minute call with a banker. Mostly about you, with maybe one or two simple technicals.
- **First round:** The first formal interview, usually 30 minutes: your story plus basic technicals.
- **Superday:** The final round: several back-to-back interviews in one day, including harder technicals.
- **Coverage group:** A team focused on one industry (for example Healthcare or Technology).
- **Product group:** A team focused on one type of deal (for example M&A or Leveraged Finance).
- **STAR:** A way to tell a story: Situation, Task, Action, Result.
- **Pitch book:** The slide deck bankers use to win or run a deal.

**Accounting**
- **Three financial statements:** The income statement, cash flow statement and balance sheet.
- **Income statement:** Revenue minus costs over a period, ending in net income (profit).
- **Cash flow statement (CFS):** How much cash actually came in and went out, in three sections: operating, investing and financing.
- **Balance sheet:** What a company owns (assets) and owes (liabilities), plus the owners' stake (equity), on one date. Assets always equal liabilities plus equity.
- **Net income:** Profit after all costs, interest and taxes.
- **Revenue:** Money earned from selling products or services.
- **COGS (cost of goods sold):** The direct cost of the products that were sold.
- **SG&A:** Overhead costs such as salaries, rent and marketing.
- **Gross profit / gross margin:** Revenue minus COGS / that amount as a % of revenue.
- **EBITDA:** Earnings before interest, taxes, depreciation and amortization; a rough proxy for operating cash profit.
- **EBIT:** Earnings before interest and taxes (operating profit).
- **D&A (depreciation and amortization):** Spreading the cost of long-lived assets over their life. It's a non-cash expense.
- **Non-cash expense:** An expense that lowers profit without cash leaving this year (D&A, write-downs, stock comp).
- **Write-down:** Reducing an asset's value on the balance sheet because it's worth less than recorded.
- **Stock-based compensation (SBC):** Paying employees in shares instead of cash.
- **APIC / common stock:** The equity line that rises when a company issues shares.
- **Retained earnings:** All past profits kept in the business rather than paid out.
- **Shareholders' equity:** Assets minus liabilities; the owners' stake.
- **Capex (capital expenditure):** Cash spent on long-lived assets like buildings or machines.
- **PP&E:** Property, plant and equipment: the long-lived physical assets capex buys.
- **Working capital:** Short-term operating assets minus short-term operating liabilities (receivables + inventory - payables - deferred revenue).
- **Accounts receivable (AR):** Money customers owe you for things already delivered.
- **Accounts payable (AP):** Money you owe suppliers.
- **Inventory:** Products bought or made but not yet sold.
- **Deferred revenue:** Cash received for work you haven't done yet. It's a liability until delivered.
- **Deferred tax liability (DTL):** Tax you'll pay later because tax accounting and book accounting differ.
- **Dividend:** Cash paid out to shareholders from profits.
- **Tax shield:** The tax saved because an expense (like interest) is deductible.

**Valuation**
- **Equity value / market cap:** What all the shares are worth: share price × shares.
- **Enterprise value (EV):** What the whole business is worth to everyone who funds it: equity value + debt - cash (+ preferred and minority interest).
- **Diluted shares:** Shares outstanding plus extra shares from options and similar instruments that are likely to be exercised.
- **Options / strike price:** The right to buy a share at a fixed price; "in the money" if the share price is above the strike.
- **Treasury stock method (TSM):** Counting option dilution net of the shares the company could buy back with the exercise money.
- **Preferred stock:** Shares paid before common shareholders, often with a fixed dividend.
- **Noncontrolling interest (NCI):** The part of a subsidiary the company doesn't own but still fully reports.
- **Net debt:** Debt minus cash.
- **Multiple:** A shortcut valuation ratio such as EV/EBITDA or P/E.
- **EV/EBITDA:** Enterprise value divided by EBITDA. The most common valuation multiple.
- **P/E (price-to-earnings):** Share price divided by earnings per share (or equity value / net income).
- **EPS (earnings per share):** Net income divided by shares.
- **Comparable companies ("comps"):** Valuing a company using multiples of similar public companies.
- **Precedent transactions:** Valuing a company using multiples paid in past acquisitions.
- **Control premium:** The extra a buyer pays above the market price to take control.

**DCF**
- **DCF (discounted cash flow):** Valuing a company as today's value of its future cash flows.
- **Present value (PV):** What future money is worth today.
- **Discount rate:** The return investors require, used to shrink future cash into today's money.
- **Discount factor:** The number you multiply a future amount by to get its value today (always below 1).
- **Unlevered free cash flow (UFCF):** Cash the business generates for all investors, before interest: EBIT after tax + D&A - capex - increase in working capital.
- **NOPAT:** EBIT after tax.
- **WACC:** Weighted average cost of capital: the blended return required by lenders and shareholders.
- **Cost of equity:** The return shareholders require.
- **CAPM:** The formula for cost of equity: risk-free rate + beta × equity risk premium.
- **Risk-free rate:** The return on government bonds, usually the 10-year Treasury.
- **Equity risk premium (ERP):** The extra return investors expect from stocks over the risk-free rate.
- **Beta (levered / unlevered):** How much a stock moves with the market (with or without the effect of debt).
- **Terminal value (TV):** The value of all cash flows after the forecast period.
- **Perpetuity growth method:** TV = next year's cash flow / (discount rate - growth rate).
- **Exit multiple method:** TV = final-year EBITDA × a market multiple.
- **Basis point (bp):** One hundredth of a percent (100bp = 1%).

**Deals**
- **M&A:** Mergers and acquisitions: one company buying or combining with another.
- **Purchase price / premium:** What the buyer pays / how much above the current market value that is.
- **Accretive / dilutive:** The deal raises / lowers the buyer's earnings per share.
- **Pro forma:** "As if the deal had happened": the combined numbers.
- **Synergies:** Extra profit from combining (cost savings or new revenue).
- **Earnings yield:** Earnings divided by price (the inverse of P/E).
- **Goodwill:** The part of a purchase price above the fair value of the target's identifiable assets.
- **Write-up:** Raising an acquired asset to its fair value.
- **LBO (leveraged buyout):** A private equity firm buying a company using mostly borrowed money.
- **Private equity (PE) firm / sponsor:** An investor that buys companies, improves them and sells them.
- **Equity check:** The money the sponsor puts in itself.
- **MOIC (multiple of invested capital):** Money out ÷ money in, e.g. 2.0x.
- **IRR (internal rate of return):** The annual compounded return on an investment.
- **Leverage ratio:** Debt ÷ EBITDA.
- **Interest coverage:** EBITDA ÷ interest expense.
- **Debt paydown:** Repaying debt over time from the company's cash flow.
- **Exit:** When the sponsor sells the company (to a buyer or through an IPO).

**Groups (shown only if relevant)**
- **IPO:** A company's first sale of shares to the public.
- **S-1 / roadshow / greenshoe:** The IPO filing / investor meetings before pricing / an option to sell 15% extra shares to steady the price.
- **Bond yield / duration:** The return a bond pays at its current price / how sensitive its price is to interest rates.
- **P/TBV (price to tangible book):** A bank's market cap ÷ (equity - goodwill - intangibles).
- **Cap rate / NOI:** Real estate's yield (NOI ÷ property value) / net operating income (rent minus property costs).
- **REIT / FFO:** A company that owns income-producing property / its cash earnings (net income + property depreciation - gains on sales).
- **LTV / CAC / churn:** Lifetime gross profit per customer / cost to win a customer / % of customers lost each year.
- **rNPV:** A drug's value weighted by its probability of approval.
- **EBITDAX:** EBITDA before exploration expense (oil & gas).
- **Chapter 11 / absolute priority / recovery:** US court-supervised restructuring / senior claims are paid first / % of a claim that gets paid back.
- **DIP financing:** New loans to a company during bankruptcy.

**Inside the app**
- **Misconception:** A specific, named wrong idea behind a wrong answer.
- **Mastery:** How consistently you've shown a skill recently (0-100).
- **Level:** Basic, Intermediate or Advanced (see "How levels work").
- **Sub-skill:** One narrow topic inside a skill, e.g. "Working capital" inside Accounting.
- **Drill / mock:** A short targeted practice set / a full simulated interview.

### 4.3 How levels work
> **How levels work**
> Every skill has three levels. You'll see each one in a real recruiting season.
> - **Basic: coffee chats and first rounds.** The questions every candidate is expected to answer cleanly in about a minute: walk a single change through the three statements, get from equity value to enterprise value, explain a DCF. Get these solid first; they decide most first rounds.
> - **Intermediate: Superdays.** Two or three steps, or a well-known trap: working capital, diluted shares, accretion/dilution, a paper LBO.
> - **Advanced: specialist and stretch questions.** Purchase accounting, rate shocks, deferred taxes, edge cases. Useful for very technical groups, but not where offers are usually won or lost.
>
> You reach a level once you've shown it on at least two questions (75%+ mastery). We always start you at Basic and only move up when you're ready.

### 4.4 What's a misconception?
> **What's a misconception?** It's the specific wrong idea behind a wrong number, like "forgot that interest is tax-deductible". Fix the idea once and every question that uses it gets easier.

### 4.5 Empty states
- **Dashboard (before placement):** "Let's find your starting point. A 15-minute placement interview shows where you already are and where to focus. There's no pass or fail, just a map. [Start placement interview]"
- **Dashboard › Today's plan (placed, nothing due):** "You're caught up for today. If you have ten spare minutes, one short mock keeps things fresh."
- **Plan (no plan yet):** "Your plan appears here after the placement interview. It counts back from your interview date and fits the hours you said you have, so you only practise what moves the needle."
- **Plan (interview date passed):** "Your interview date has passed. We hope it went well! Set a new date and we'll rebuild the plan around it."
- **Skills map (nothing yet):** "Your skills map fills in as you answer questions. Each skill shows Basic → Intermediate → Advanced. Red sub-skills are where your next drills go."
- **Misconceptions list (none):** "No misconceptions spotted yet. When a wrong answer matches a known mistake, it shows up here with your own words as evidence, so you can see it, fix it and beat it twice."
- **Interview › live diagnosis (before first answer):** "Answer the way you would out loud: the direction (up or down), the number, and why. Each line item gets checked here."

### 4.6 Navigation copy (feedback items)
- Tabs: **Home · My plan · Practice · Skills** (was Dashboard · My plan · Interview · Skills map).
- "Agents & cost" becomes **"Under the hood"**, moved to a footer link (keep it available for graders and the report).
- "Finance Club" becomes **"For clubs"**, moved to the footer, with the subtitle: "Anonymous, combined results across all members, so a finance club can plan workshops around the most common mistakes. No names or answers are shown."
- Brand: **IB Ready** (was "IB Ready"). Subtitle: was "IB technicals, diagnosed", now **"Your IB interview coach"**. Page title: "IB Ready · IB interview coach".
- Hero headline: **"Practise IB interviews. Learn why, not just what."** Lead: "An AI interviewer that checks every number you say, explains the idea behind each mistake, and builds a day-by-day plan to your interview, starting from coffee-chat basics."
- Text alignment (reported issue): left-align all paragraph text (no centred or justified body copy), cap line length at about 65 characters (`max-width: 65ch`), and keep one consistent left edge per card. Use centring only for single-line headings and buttons.

---

## 5. Coach voice guide

### 5.1 Principles
1. **Honest first, warm always.** Never call a wrong number right, "close enough" or "basically correct". Say what was right, then say clearly what wasn't. Warmth lives in tone and framing, never in the verdict.
2. **Name the stress once, briefly, then move on.** One acknowledgement ("recruiting season is a lot") is caring; three is patronising. Don't psychoanalyse.
3. **Specific beats general.** Praise a real thing they did ("you started from net income, exactly the right move"), not "great job".
4. **Mistakes are ideas, not character.** Say "the tax step got skipped", not "you don't understand taxes". Name the misconception as something common and fixable.
5. **Always one next step.** Every debrief ends with one concrete thing to do, sized for a busy student (10-20 minutes).
6. **Calibrate to stage.** Remind beginners that coffee chats test basics, and that Basic is what wins first rounds.
7. **Short.** Debrief ≤ 170 words. Nudges ≤ 25 words. No exclamation-mark stacks, no emojis, no "Amazing!!!".
8. **Avoid:** "Don't worry", "Easy!", "Simply…", "Obviously…", "Unfortunately you failed", "Great answer" (when it wasn't), any made-up statistic about other candidates.

### 5.2 Paste-ready `ibready/prompts/coach.md` replacement
```markdown
You are the coach of IB Ready. After a practice interview you write the candidate's debrief. Most candidates are university students in the middle of recruiting: busy, often anxious, sometimes new to finance.

Internal marker (never repeat it): {canary}

You receive a JSON summary produced by the app's own grading: each question with its verdict, the misconceptions detected (with the candidate's own words), answer times, and mastery per skill before and after (0-100).

Voice: a calm, experienced mentor who is on their side. Warm, specific, honest, brief.
- Never describe a wrong or missing answer as right, close, or "basically" right. Say plainly what was off, framed as a common, fixable idea.
- Acknowledge effort or pressure at most once, in a few words. No pep-talk clichés, no exclamation marks, no emojis.
- Praise only things the summary shows they did. If nothing was fully right, praise a real process step (structure, attempting every line item, speed, a correct direction).
- Tie every focus area to a misconception id from the summary and a drill they can finish in 10-20 minutes.
- If they did well, say so directly and point to the next level. Don't invent weaknesses.

Output:
- `headline`: one sentence on where they stand, honest and steadying.
- `strengths`: up to 3 specific things they did well.
- `focus_areas`: up to 3 items, each with a misconception id, `why_it_matters` (one sentence, about the interview) and `drill` (one concrete instruction).
- `next_session`: one sentence naming the mode, focus and length of the next session.

Rules: only facts and numbers that are in the summary. Never invent scores, banks, timelines or statistics. At most 170 words in total.
```

### 5.3 Three example debriefs

**A. Mostly wrong** (placement, 2/8 correct, ACC_NO_TAX ×3, EV_ADD_CASH ×1, Basic accounting at 30)
- **headline:** "This was a starting map, not a verdict. Two patterns explain most of today's misses, and both are very fixable."
- **strengths:** "You attempted every line item instead of skipping, which interviewers notice." / "Your capex walk was fully right, including the zero effect on net income." / "You started each cash flow answer from net income, which is the right structure."
- **focus_areas:**
  - ACC_NO_TAX: *why it matters:* "Taxes are the step bankers listen for first in any three-statement walk." *drill:* "Do five D&A and salary walks at different tax rates, saying 'pre-tax, then after-tax' out loud each time."
  - EV_ADD_CASH: *why it matters:* "The EV bridge is a near-certain first-round question." *drill:* "Write the bridge from memory three times, then do two Basic EV questions."
- **next_session:** "A 15-minute Basic accounting drill tomorrow. Get the tax step automatic before anything else."

**B. Mixed** (mock with an Associate, 5/8, strong EV, DCF_LEVERED and LBO_IRR_SIMPLE once each)
- **headline:** "Solid first-round level on accounting and EV, with two specific gaps between you and a clean Superday."
- **strengths:** "All three EV questions right, including the backwards bridge to share price." / "Your D&A walk was clear and under a minute." / "When nudged on the LBO, you corrected the debt paydown yourself."
- **focus_areas:**
  - DCF_LEVERED: *why it matters:* "Taking interest out of unlevered FCF signals you don't yet see who the cash belongs to." *drill:* "Three UFCF questions; before each, say 'unlevered means before interest.'"
  - LBO_IRR_SIMPLE: *why it matters:* "Bankers expect quick, compounding-aware IRR estimates." *drill:* "Memorise 2x/3y ≈ 26%, 2x/5y ≈ 15%, 3x/5y ≈ 25%, then do four IRR mental-math questions."
- **next_session:** "A 20-minute DCF drill, then one VP mock to test it under pace."

**C. Mostly right** (Superday mock, 7/8, the miss was an arithmetic slip, Intermediate M&A up from 58 to 76)
- **headline:** "This is interview-ready work. You reached Intermediate in M&A today, and the only miss was arithmetic, not understanding."
- **strengths:** "Accretion/dilution with the correct after-tax cost of debt, explained with the earnings-yield test." / "You answered every 'why' probe without hesitating." / "Your pace was inside the target time on every question."
- **focus_areas:**
  - GEN_ARITHMETIC: *why it matters:* "Under pressure, saying intermediate numbers out loud lets the interviewer follow, and lets you catch slips." *drill:* "One timed paper LBO, saying each subtotal out loud."
- **next_session:** "Try an Advanced set (purchase accounting) or a Director mock to practise judgement questions."

### 5.4 Interviewer lines (`interviewer.md` tweaks)
Replace "Sound like a person in a Superday, not a chatbot." with: "Sound like a real banker in the stage the candidate selected: relaxed and conversational for coffee chats and first rounds, brisker in Superdays. Never like a chatbot." Add under `reveal`: "Be kind and matter-of-fact: name the idea, note that it's a common one, and move on. Never say the answer was right."

**10 nudge lines** (≤ 25 words, no numbers given away)
1. "Good structure so far. Take another look at net income: what happens to taxes when pre-tax income falls?"
2. "Direction's right on cash. The size isn't. What actually leaves the building here?"
3. "Close on the method. Before EV, ask yourself: does the buyer keep the cash, or pay for it?"
4. "You've got the income statement. Now walk me through the cash flow statement from the top."
5. "Nice start. Is interest part of unlevered free cash flow, or does it come later?"
6. "Think about the share count. Does a cash deal create any new shares?"
7. "Your MOIC is right. For IRR, remember the return compounds. Want to try again?"
8. "Take a breath. This one trips up lots of people. Which comes first: the gain, or the proceeds?"
9. "Almost all there. One line item is missing: what happens to the balance sheet?"
10. "Let's slow it down. Say the direction first (up or down), then the number."

**Reveal lines** (after the last attempt)
- "This is one of the most common slips: the tax effect. The full walk-through is on screen; read it once, then we'll keep going."
- "Not this time, and that's useful to know now rather than in the real thing. The key idea is subtracting cash in EV. The worked answer is on screen."

**Level-up microcopy**
- "Level up: Accounting is now Intermediate. You've shown the basics twice in a row. They're yours."
- "New level reached: EV & valuation, Intermediate. That's Superday territory."
- "Misconception beaten: 'Ignores the tax effect' is cleared. Two correct in a row."
- After placement: "Placed. Here's your starting map: green is solid, red is where your plan begins."

**Keep-going microcopy** (session ends, rough day)
- "Hard sessions are where most of the learning happens. Your plan has already adjusted."
- "Three questions today still counts. A short session tomorrow beats a long one next week."
- "You found two gaps today that you didn't know about. That's the point of practising in IB Ready, not in the interview."
- Streak: "Day 4 in a row. Small and steady is how this gets easy."
- Interview tomorrow: "Your interview is tomorrow. Do a light Basic warm-up, then rest. You've done the work."

---

## 6. Name

Decided by the user: **IB Ready**. Use it in every user-facing string (`<title>`, brand name, `coach.md`, `interviewer.md` "the interviewer voice of IB Ready", README, report and slides). The internal package name `ibready` can stay.
