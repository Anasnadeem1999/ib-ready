# QA round 2: grading accuracy and content correctness (QA engineer B)

Branch `v2`, folder `app-v2`, run 2026-10-24. No app code edited. The live grader path matched `evals/run_eval.run_ticktie`: specialist agent, then `engine._adjudicate`. Isolated data dir (`qa2b_data` in the session scratchpad). Total API spend was about **$0.035**: $0.0075 for the 40 answers, about $0.023 for the three eval sets and about $0.0035 for the six sessions.

## Headline

| Metric (40 new realistic answers) | Result |
|---|---|
| Pass/fail verdict accuracy | **36/40 = 90%** |
| False alarms (correct answer marked wrong) | **2/16 = 12.5%** (N11, N18): both are interview-style rounding |
| False passes (wrong answer marked right) | **2/24 = 8.3%** (N23, N24): right numbers plus an explicit wrong conceptual claim |
| Exact misconception named (wrong answers with a known misconception) | **15/17 = 88%** (the 2 misses are the false passes) |
| Fit answers: unfair or harsh verdicts | **0/6** (all 4 good answers were `correct`; both weak answers were flagged fairly) |
| Basic group questions (FIG, TMT, HC, energy, RX, M&A) | **6/6** verdicts right |
| Existing eval sets (ticktie) | holdout 100% · behavioral 100% (fair 100%, unfair flags 0%) · industry 100% |

The existing sets are small (30, 10 and 8 items) and close to the training distribution. The fresh set shows the real failure modes, all in how the code decides the verdict around the model (`_adjudicate` and label tolerances), not in what the model reads.

## Summary of issues

| ID | Sev | Template / agent | Title |
|---|---|---|---|
| G-01 | **P1** | `engine._adjudicate` (numeric branch) | Right numbers + an explicit wrong concept passes as correct: the specialist flags the misconception, then code throws it away |
| G-02 | **P1** | `ma_stock`/`ma_cash`/`ma_debt`/`mkt_rates_ma` (accretion), `mkt_rates_wacc` (wacc_new, tv_change) | Label tolerances fail normal interview rounding. The grader then makes up an error to justify the verdict |
| G-03 | **P1** | `ev_equity_issue` + `EV_FINANCING_MOVES_EV` fix text | The teaching note contradicts the answer key: it tells the student equity value is unchanged when the key says +$200mm |
| G-04 | P2 | `bank.check_numbers` / `_adjudicate` | Optional (non-required) labels still fail the whole answer when stated "wrong", even under "Roughly ..." wording |
| G-05 | P2 | Coach debrief (`agents.coach`) | The debrief misstates what was wrong or right (S1: "EPS estimate was incorrect", but it was correct; S2: `went_well` empty though NI and cash were right) |
| G-06 | P2 | `_adjudicate` (conceptual) + specialist | A thin but correct partial answer gets a misconception tag, so `incorrect` instead of `incomplete` (C04 → `LBO_NO_LEVER_LOGIC`). A loose tag on G04 (`EN_EBITDA_ONLY` for "X = extra taxes") |
| G-07 | P2 | `hc_rnpv` | Ambiguous wording ("worth $1,500mm (NPV) if approved" could already be net of costs). The 270 trap is filed under the wrong misconception |
| G-08 | P3 | `ma_*` sign flip | "Accretive 10.3%" (should be dilutive) is caught but no misconception is named. `ACC_SIGN_FLIP` covers accounting only |
| G-09 | P3 | Specialist rationale | Correct answers get off-scope criticism in the rationale shown on resolve (N08: "you did not discount the TV", which the question never asked) |
| G-10 | P3 | `c_ma_sellside`, `c_ib_role` | Technical or knowledge questions sit in skill `fit` / kind `behavioral`, so they get fit leniency and the fit specialist |
| G-11 | P3 | `acc_defrev` | Gives a 25% tax rate but ignores cash tax on prepayments (US tax often taxes prepayments when received). A candidate could reasonably answer either way |
| G-12 | P3 | `evals/*_answers.json` | The eval sets are too small and in-distribution to catch G-01 and G-02. Suggest adding the 40 items below to holdout |

### G-01 (P1): wrong side-claims pass when every number is right
- N23 `acc_asset_sale`: "net income up 15, cash up 95, PP&E down 80. **and the hundred of proceeds also counts as revenue**". Result: `correct_unexplained`. The specialist returned `ACC_PROCEEDS_AS_REVENUE` and its rationale says "you incorrectly treated the full sale proceeds as revenue".
- N24 `dcf_unlever_beta`: "0.9 ... **the unlevered beta is usually higher than the levered one**". Result: **`correct`**, which the interviewer acknowledges as right. The specialist returned `DCF_BETA_DIRECTION`.
- Cause: in `_adjudicate` the numeric branch returns `correct` / `correct_unexplained` once no label is wrong and nothing required is missing. `llm_mids` are used only when a number is wrong. The misconception never reaches the weakness map either.
- This breaks "never says wrong is right": the verdict says correct while the rationale on the same screen says incorrect. Suggested fix: if all numbers are right but `llm_mids` contains a misconception from this template's list, return `incomplete` and record the misconception.

### G-02 (P1): rounding false alarms, and the grader then makes up an error
- N11 `ma_stock`: "dilutive, about ten percent ... 45 million new shares, pro forma EPS about 3.59". Truth is -10.345%; the tolerance is `max(0.3, 2%) = 0.3pp`, so the answer is **incorrect** even though shares and EPS are right. The rationale says "Your dilution percentage does not follow from that EPS comparison". In session S1 the coach then said "**the earlier EPS estimate was incorrect**", which is false.
- N18 `mkt_rates_wacc`: "WACC is about 8.9%". Truth is 8.94, `tol_abs=0.02`. Result: **incorrect + `GEN_ARITHMETIC`**, with the made-up rationale "you applied the debt tax adjustment to the rate increase itself". The student did that step correctly.
- Seed sweep (200 instances, offline): `mkt_rates_wacc.wacc_new` fails **44%** of the time when the true answer is rounded to one decimal. The accretion labels fail 26–37% when rounded to a whole percent ("about 10% dilutive"). `tv_change` has `tol_abs=0.3` although the question says "Roughly".
- The diagnostician prompt says "Interview-standard approximations are fine", but code overrules it. The prompt also says "If the tool marked a number wrong, never describe that calculation as correct", which pushes the model to make up a reason.
- Suggested fix: widen `wacc_new` to about 0.06 and accretion labels to about 0.5pp (or 5% relative); `tv_change` about 1pp.

### G-03 (P1): `ev_equity_issue` gives a teaching note that contradicts the key
`check_numbers` on "equity value 0, EV 0" flags `equity_value` as wrong with match `EV_FINANCING_MOVES_EV`. That misconception's fix text is: "Raising debt and holding the cash ... **EV and equity value are unchanged**." It describes the debt case and tells the student equity value doesn't move, but the key is +$200mm. Its name ("Thinks financing changes enterprise value") is also wrong for this answer: the student said EV is unchanged, which is right. Suggested fix: add a misconception such as `EV_EQUITY_ISSUE_NO_CHANGE` ("New shares at market price raise equity value by the proceeds; EV is unchanged because cash rises equally").

### G-07 (P2): `hc_rnpv`
- The text says "would be worth $1,500mm (NPV) if approved" and "$150mm (PV) of trial costs must be spent either way". A careful student can read the approved-case NPV as already net of trial costs, which gives 300. Suggested wording: "the drug's cash flows if approved are worth $1,500mm, before trial costs".
- The trap `rnpv = p × (V − C)` (270) is tagged `HC_RNPV_UNWEIGHTED` ("Ignores the probability of approval"), but that answer *did* use the probability; the mistake is weighting the sunk-either-way costs. It should be a separate misconception, or the misconception should be renamed.

## Finance correctness spot-audit (25+ templates)
I instantiated all 50 numeric templates (seed 7) plus 15 new ones (seed 11, with what-ifs) and read the 57 conceptual and fit templates. I recomputed every key by hand for the templates below. A 300-seed sweep found **no trap signature equal to the true answer** in any numeric template.

| Template | Key, explanation, fix texts | Note |
|---|---|---|
| acc_da, acc_writedown, acc_sbc | OK | SBC equity +tax saving is correct |
| acc_ar, acc_ap, acc_defrev | OK | defrev: see G-11 |
| acc_debt, acc_debt_repay, acc_dividend | OK | the dividend's tax rate is a fair distractor |
| acc_ebitda_build, acc_asset_sale (+what-if) | OK | asset-sale cash = proceeds − tax on gain ✓ |
| ev_bridge, ev_bridge_basic (+what-if), ev_implied_price, ev_multiples_calc, ev_tsm | OK | |
| ev_equity_issue | **G-03** | key correct, fix text wrong |
| ev_debt_cash | OK | |
| dcf_ufcf, dcf_tv, dcf_wacc, dcf_capm, dcf_pv, dcf_exit_tv, dcf_unlever_beta | OK | |
| ma_premium, ma_stock, ma_cash, ma_debt, ma_goodwill, ma_synergies_breakeven | OK | tolerances: G-02 |
| lbo_paper, lbo_irr_rule, lbo_basic, lbo_levers | OK | levers decomposition adds up (12x exit seed checked) |
| mkt_rates_wacc, mkt_rates_lbo, mkt_rates_ma | OK | tolerances: G-02 / G-04 |
| fig_ptbv, re_ffo, re_cap_rate, tmt_ltv, rx_waterfall, en_ebitdax, lev_credit_stats | OK | |
| hc_rnpv | **G-07** | |
| c_fig_basics, c_tmt_arr, c_hc_basics, c_en_ebitdax, c_rx_role, c_ma_group_role | OK | key points accurate and gradeable |
| c_ma_consideration, c_ma_accretion_what, c_dcf_tv_methods, c_dcf_equity_cost, c_acc_most_important | OK | |
| c_ma_sellside, c_ib_role | G-10 | content fine, skill classification questionable |

## The 40 realistic answers
Expected verdict and misconception were written before running. Numerics use `bank.instantiate(tid, Random(7))`; fit uses `{"group": "investment banking"}`. Full outputs, with checks, rationale and model ids, are in the scratchpad (`qa2b_results.json`).

| ID | Template | Answer (truncated) | Expected | Got | Result |
|---|---|---|---|---|---|
| N01 | acc_da | "um ok so depreciation goes up forty, that's an expense so pre-tax income drops forty, taxes go down ten so ..." | PASS  | correct  | OK |
| N02 | acc_da | "so net income's down thirty after tax, and um cash is down ten I think, PP&E down forty" | FAIL ACC_SIGN_FLIP | incorrect ACC_SIGN_FLIP | OK |
| N03 | acc_sbc | "NI falls 30 after tax, cash goes up 10 from the tax savings because SBC is non-cash, and equity... falls by..." | FAIL ACC_SBC_EQUITY | incorrect ACC_SBC_EQUITY | OK |
| N04 | acc_ar | "revenue up 40 so net income's up thirty after taxes, and cash goes up thirty too" | FAIL ACC_AR_IGNORED | incorrect ACC_AR_IGNORED | OK |
| N05 | ev_bridge | "ok equity value is 40 times 10 so 400 million, then plus the 400 of debt, plus pref 20, plus the NCI 50, mi..." | PASS  | correct  | OK |
| N06 | ev_implied_price | "8 times 100 is 800, divide by the 10 million shares, so like 80 bucks a share" | FAIL EV_SKIP_BRIDGE | incorrect EV_SKIP_BRIDGE | OK |
| N07 | dcf_ufcf | "EBIT 200 times .8 is 160, plus 20 of D&A, minus 60 capex, minus 24 for NWC, and minus the 10 of interest, s..." | FAIL DCF_LEVERED | incorrect DCF_LEVERED | OK |
| N08 | dcf_tv | "TV is a hundred times 1.03 over 6 percent, so roughly 1.7 billion" | PASS  | correct  | OK |
| N09 | dcf_wacc | "70% times 10 is 7, debt is 6% times point 8 so 4.8, times 30% is like 1.44, so WACC is around 8.4%" | PASS  | correct  | OK |
| N10 | dcf_capm | "it's four plus 1.2 times eight, so 13.6%" | FAIL DCF_CAPM_MARKET_RETURN | incorrect DCF_CAPM_MARKET_RETURN | OK |
| N11 | ma_stock | "um it's dilutive, about ten percent. purchase price is 1.8 billion, so 45 million new shares, pro forma EPS..." | PASS  | incorrect  | **FALSE ALARM** |
| N12 | ma_stock | "45 million new shares, pro forma EPS 3.59, so it's accretive by about 10.3%" (wrong sign word) | FAIL  | incorrect  | OK (no mid, G-08) |
| N13 | ma_cash | "cash deal so no new shares. lost interest is 1800 times 4% which is 72, so net income is 520 minus 72, 448,..." | FAIL MA_FOREGONE_NO_TAX | incorrect MA_FOREGONE_NO_TAX | OK |
| N14 | ma_goodwill | "goodwill is purchase price minus the fair value of net assets, so 1500 minus 400 minus the 200 write-up, wh..." | FAIL MA_GOODWILL_NO_DTL | incorrect MA_GOODWILL_NO_DTL | OK |
| N15 | lbo_paper | "equity in is 800 minus 500 so 300, equity out is 1040 minus 400 so 640, so a bit over 2.1x, IRR around 16 p..." | PASS  | correct  | OK |
| N16 | lbo_irr_rule | "2x in three years, so like 33% a year" | FAIL LBO_IRR_SIMPLE | incorrect LBO_IRR_SIMPLE | OK |
| N17 | lbo_irr_rule | "doubling your money in three years is roughly twenty-six percent IRR" | PASS  | correct_unexplained  | OK |
| N18 | mkt_rates_wacc | "cost of equity goes up 100 bps since beta is 1, cost of debt goes up 80 after tax, so WACC is about 8.9%, a..." | PASS  | incorrect GEN_ARITHMETIC | **FALSE ALARM** |
| N19 | ma_premium | "the premium is 10 over 50 so 20%, and purchase equity value is 50 times 20 million so a billion" | FAIL MA_PREMIUM_ON_OFFER | incorrect MA_PREMIUM_ON_OFFER | OK |
| N20 | ev_bridge_basic | "equity value is two fifty, then EV is 250 plus 200 plus the 80 of cash, so 530" | FAIL EV_ADD_CASH | incorrect EV_ADD_CASH | OK |
| N21 | acc_dividend | "the dividend reduces net income by 40, so after tax it's 32, and cash is down 32" | FAIL ACC_DIVIDEND_EXPENSED | incorrect ACC_DIVIDEND_EXPENSED | OK |
| N22 | dcf_exit_tv | "TV is 800 million, and today it's 800 divided by point 6, so like 1333" | FAIL DCF_DF_INVERTED | incorrect DCF_DF_INVERTED | OK |
| N23 | acc_asset_sale | "net income up 15, cash up 95, PP&E down 80. and the hundred of proceeds also counts as revenue on the incom..." | FAIL ACC_PROCEEDS_AS_REVENUE | correct_unexplained  | **FALSE PASS** |
| N24 | dcf_unlever_beta | "it's 1.17 over 1 plus .75 times .4, so 0.9. and the unlevered beta is usually higher than the levered one" | FAIL DCF_BETA_DIRECTION | correct  | **FALSE PASS** |
| C01 | c_ev_cash | "because cash isn't really part of the operating business, like if you buy the company you basically get the..." | PASS  | correct  | OK |
| C02 | c_dcf_wacc | "if WACC goes down the value goes down too, because the company is earning a lower return" | FAIL  | incorrect  | OK |
| C03 | c_ma_pe | "you compare P/Es, if the target's P/E is higher than the acquirer's then it's accretive" | FAIL MA_PE_RULE | incorrect MA_PE_RULE | OK |
| C04 | c_lbo_leverage | "um because you put in less equity so your returns are bigger?" | FAIL (incomplete) | incorrect LBO_NO_LEVER_LOGIC | OK (tag harsh, G-06) |
| G01 | c_fig_basics (FIG) | "banks are different cuz the balance sheet basically is the business, deposits come in and they lend them ou..." | PASS  | correct  | OK |
| G02 | c_tmt_arr (TMT) | "ARR is like average revenue rate I think? and software companies are valued on revenue because for them rev..." | FAIL  | incorrect  | OK |
| G03 | c_hc_basics (HC) | "mostly the drug pipeline and how likely each drug is to get approved, then patents and when they expire cau..." | PASS  | correct  | OK |
| G04 | c_en_ebitdax (energy) | "EBITDAX is EBITDA plus extra taxes, the X is the extra taxes, they use it because oil companies pay a lot o..." | FAIL  | incorrect EN_EBITDA_ONLY | OK (tag loose, G-06) |
| G05 | c_rx_role (RX) | "they help companies that are going bankrupt, like in chapter 11" | FAIL (incomplete) | incorrect  | OK |
| G06 | c_ma_group_role (M&A) | "so the M&A group does the actual buying and selling advice, the valuation, running the sale process, negoti..." | PASS  | correct  | OK |
| F01 | b_why_ib | "um so honestly I got into it through my finance club, we did a mock sell-side pitch on a regional bank and ..." | PASS  | correct  | OK |
| F02 | b_weakness | "my greatest weakness is probably that I'm a perfectionist and I just work too hard sometimes" | FAIL FIT_FAKE_WEAKNESS | incorrect FIT_FAKE_WEAKNESS/FIT_NO_EVIDENCE | OK |
| F03 | b_team | "so in my econ capstone we had a 48 hour deadline and one teammate dropped out. we split up his part, um, I ..." | PASS  | correct  | OK |
| F04 | b_resume | "sure, uh, I'm a junior at state studying econ. freshman year I joined the investment club which got me into..." | PASS  | correct  | OK |
| F05 | b_deal | "I've been following the Cisco Splunk deal, Cisco bought Splunk for like 28 billion in cash. I think it made..." | PASS  | correct  | OK |
| F06 | b_failure | "honestly I can't really think of a time I failed, I've always managed to pull things off in the end" | FAIL  | incorrect FIT_NO_EVIDENCE | OK |

What worked well: numbers spoken in words ("eight hundred twenty million", "twenty-six percent"), filler words, "like 80 bucks", and rounding inside a wide tolerance (TV "roughly 1.7 billion", WACC "around 8.4%", IRR "around 16 percent") all parsed and graded correctly. Every one of the 13 classic numeric traps was named exactly. Fit grading was fair: hesitant, "we"-heavy and lightly quantified answers were not penalised.

## Existing eval sets (run today; results written to `evals/results/`)

| Set | System | Verdict acc. | Caught | Named | False alarms | Fair verdict / unfair flags | $/answer |
|---|---|---|---|---|---|---|---|
| holdout (30) | ticktie | 100% | 100% | 100% | 0% | – | $0.00024 |
| | ticktie_lite | 100% | 100% | 100% | 0% | – | $0.00024 |
| | baseline (plain model) | 83% | 93% | 93% | 27% | – | $0.00011 |
| behavioral (10) | ticktie | 100% | 100% | 100% | 0% | 100% / 0% | $0.00018 |
| | baseline | 70% | 100% | 100% | 100% | 50% / 30% | $0.00010 |
| industry (8) | ticktie | 100% | 100% | 100% | 0% | – | $0.00024 |
| | baseline | 100% | 100% | 83% | 0% | – | $0.00009 |

No item errored. The headline story still holds: IB Ready beats the plain model mainly on false alarms and fit fairness. But a perfect score on 48 in-distribution items overstates real accuracy; the 40 fresh answers give **90%** (G-12).

## Feedback tone review (6 full engine sessions, ended with the coach debrief)

| S | Question / persona | Turns | Interviewer | Coach debrief | Verdict on tone |
|---|---|---|---|---|---|
| S1 | ma_stock / Associate | "about ten percent dilutive" → nudge; "10.3%" → probe_why | Nudge: "You've got the new shares and pro forma EPS. Revisit the percentage dilution..." Warm and specific, but it **tells a right answer to change** (G-02) | "the earlier **EPS estimate was incorrect**". **False**: EPS was right; only the rounding was off | Warm, short. **Not honest-accurate** (G-05) |
| S2 | acc_sbc / VP | wrong equity → nudge; repeated → reveal | "Net income and cash are accounted for. Revisit shareholders' equity: what happens to APIC...". Reveal: "retained earnings falls after tax, while common stock and APIC rise by the full grant value". Brisk but kind, no numbers before reveal | Precise misconception and a good try_this. **`went_well` empty** although NI and cash were right | Honest. Slightly cold for a nurturing coach (G-05) |
| S3 | acc_asset_sale / Associate | right numbers + "proceeds count as revenue" → probe_why | "Your net income, cash, and PP&E changes are right. Why does only the gain, not the full sale proceeds, flow through net income?" A good save: the interviewer challenges the wrong claim | "the gain is not revenue": honest. `went_well` says "recognized the sale brings in $100 of cash" (the student said 95) | Good tone. The engine still never records the misconception (G-01) |
| S4 | c_lbo_leverage / Associate | thin → nudge; full → correct (final `incomplete`) | "Using less equity is part of it, but what happens to equity value as EV grows and debt is paid down?" Encouraging and specific | Credits the second answer; work_on LBO_NO_LEVER_LOGIC, with a fair try_this | Meets the standard |
| S5 | b_weakness / Director | "perfectionist" → nudge; real weakness → correct | "That can sound like a disguised strength. What's a genuine, manageable weakness...?" Honest without shaming | Names the cliché, credits the fix, gives 2 actionable items | Meets the standard |
| S6 | b_team / Associate | good STAR → correct | "You stepped in on the regression work and kept the team coordinated..." | Praise is specific; the suggestion to "make the result explicit" is a bit generic, since the result was given | Meets the standard |

Across 10 interviewer messages, **no answer-key number leaked before a reveal** (output filter plus checks) and no message called a wrong answer right. Every message was 1–2 sentences, warm and specific. The tone problems all come from the grading layer underneath: G-02 makes the coach invent an error, and G-01 means a wrong claim is never recorded. The coach's `went_well` can come back empty or slightly off on partly right answers (G-05).

## Reproduce
Scripts are in the session scratchpad: `qa2b_answers.py` (40 answers through `agents.specialist` + `engine._adjudicate`) and `qa2b_sessions.py` (six sessions through `engine.start_session/answer/end_session`, with `state["current"]` pinned to the chosen question). Run both with `TICKTIE_DATA_DIR` set to a scratch dir.
