"""The answer key must be right. These tests pin the calculators to hand-worked answers."""

import random

import pytest

from ticktie import bank
from ticktie.misconceptions import LIBRARY


def q(tid, **params):
    return bank.build(bank.TEMPLATES[tid], params)


def test_formatting_keeps_whole_number_zeros():
    assert bank.pct(0.2, 0) == "20%"
    assert bank.pct(0.075) == "7.5%"
    assert bank.num(100, 0) == "100"
    assert bank.num(2.50) == "2.5"
    assert bank.money(1250) == "$1,250"
    assert bank.money(7.5) == "$7.50"
    assert bank.money(-40) == "-$40"


def test_question_text_shows_true_parameters():
    qq = bank.build(bank.TEMPLATES["mkt_rates_wacc"], {"we": 0.6, "w0": 0.09, "b": 0.8, "t": 0.2, "g": 0.03, "bp": 100.0})
    assert "60% equity" in qq.text and "40% debt" in qq.text and "100bp" in qq.text


def test_depreciation_walk():
    v = q("acc_da", X=10.0, t=0.25).values
    assert v["ni"] == pytest.approx(-7.5)
    assert v["cash"] == pytest.approx(2.5)
    assert v["ppe"] == pytest.approx(-10)
    assert v["equity"] == pytest.approx(-7.5)


def test_sbc_equity_rises_by_tax_saving():
    v = q("acc_sbc", X=100.0, t=0.4).values
    assert v["ni"] == pytest.approx(-60)
    assert v["cash"] == pytest.approx(40)
    assert v["equity"] == pytest.approx(40)


def test_revenue_on_credit():
    v = q("acc_ar", X=100.0, t=0.25).values
    assert v == {"ni": 75.0, "cash": -25.0, "ar": 100.0}


def test_ev_bridge():
    v = q("ev_bridge", S=20.0, Q=10.0, D=100.0, C=50.0, P=20.0, N=10.0).values
    assert v["ev"] == pytest.approx(200 + 100 + 20 + 10 - 50)


def test_ufcf_ignores_interest():
    v = q("dcf_ufcf", EBIT=100.0, DA=20.0, CX=40.0, NWC=10.0, I=30.0, t=0.25).values
    assert v["ufcf"] == pytest.approx(75 + 20 - 40 - 10)


def test_terminal_value():
    v = q("dcf_tv", F=100.0, w=0.10, g=0.02).values
    assert v["tv"] == pytest.approx(102 / 0.08)


def test_wacc_after_tax_debt():
    v = q("dcf_wacc", E=700.0, D=300.0, Re=0.10, Rd=0.06, t=0.25).values
    assert v["wacc"] == pytest.approx((0.7 * 0.10 + 0.3 * 0.045) * 100)


def test_paper_lbo():
    # 100 EBITDA, 10x, 5x debt -> 1000 EV, 500 debt, 500 equity.
    # Exit 150 x 10 = 1500; debt 500 - 250 = 250 -> equity 1250 -> 2.5x, IRR ~20.1%.
    v = q("lbo_paper", E0=100.0, m=10.0, L=5.0, E5=150.0, Dp=250.0, n=5.0, t=0.25, bp=100.0).values
    assert v["moic"] == pytest.approx(2.5)
    assert v["irr"] == pytest.approx((2.5 ** 0.2 - 1) * 100)


def test_all_stock_pe_rule_agrees_with_math():
    rng = random.Random(7)
    for _ in range(200):
        qq = bank.instantiate("ma_stock", rng)
        _, nit, price, _ = bank._ma_base(qq.params)
        purchase_pe = price / nit
        if abs(purchase_pe - qq.params["PEa"]) < 1e-6:
            continue
        assert (qq.values["accretion"] > 0) == (qq.params["PEa"] > purchase_pe)


def test_misconception_signature_is_detected():
    qq = q("acc_da", X=10.0, t=0.25)
    checks = {c.label: c for c in bank.check_numbers(qq, {"ni": -10.0, "cash": 0.0})}
    assert "ACC_NO_TAX" in checks["ni"].matches
    assert "ACC_NO_TAX" in checks["cash"].matches


def test_correct_answer_matches_no_misconception():
    qq = q("acc_da", X=10.0, t=0.25)
    checks = bank.check_numbers(qq, {"ni": -7.5, "cash": 2.5})
    assert [c.status for c in checks if c.label in ("ni", "cash")] == ["correct", "correct"]


@pytest.mark.parametrize("tid", list(bank.TEMPLATES))
def test_every_template_builds_and_explains(tid):
    rng = random.Random(tid)
    for _ in range(150):
        qq = bank.instantiate(tid, rng)
        assert qq.text and qq.solution
        for mid in qq.signatures:
            assert mid in LIBRARY, mid
        for mid in qq.misconceptions:
            assert mid in LIBRARY, mid
        if qq.kind == "numeric":
            assert set(l.key for l in qq.labels) == set(qq.values)
            assert any(l.required for l in qq.labels)
            # The truth itself must never be flagged as a misconception.
            checks = bank.check_numbers(qq, dict(qq.values))
            assert all(c.status == "correct" for c in checks)
        v = bank.variation(qq, rng)
        if v is not None:
            assert v.text and v.values


def test_slip_detector():
    assert bank.looks_like_slip(182.5, 192.5)      # one digit wrong
    assert bank.looks_like_slip(2.8, 28.0)         # decimal shift
    assert bank.looks_like_slip(1243.0, 1234.0)    # transposed digits
    assert not bank.looks_like_slip(73.0, 80.0)    # a real conceptual miss
    assert not bank.looks_like_slip(-16.0, 16.0)   # sign errors are not slips


def test_levels_ignore_direction_words():
    qq = q("mkt_rates_lbo", E0=100.0, m=10.0, L=5.0, E5=160.0, Dp=100.0, n=5.0, t=0.2, bp=200.0)
    checks = {c.label: c for c in bank.check_numbers(qq, {"lost_paydown": -40.0, "irr_new": 18.3})}
    assert checks["lost_paydown"].status == "correct"
    # ...but direction still matters for changes
    qd = q("acc_da", X=10.0, t=0.25)
    assert {c.label: c for c in bank.check_numbers(qd, {"ni": 7.5})}["ni"].status == "wrong"


# --------------------------------------------------------------------------- grading-band properties
# QA-02 found templates where a misconception's wrong number sat inside the grading tolerance, so the wrong
# answer was marked correct (mkt_rates_lbo, dcf_pv, mkt_rates_wacc, ev_tsm, ev_bridge). These tests check
# the raw trap formulas (before build() filters anything) over 300 random instances of every template.
NUMERIC_IDS = [tid for tid, t in bank.TEMPLATES.items() if t.kind == "numeric"]


def _wrong_parts(sig, truth):
    """Entries equal to the truth are the parts of a fingerprint the candidate still gets right."""
    return {k: x for k, x in sig.items() if abs(x - truth[k]) > 1e-9}


@pytest.mark.parametrize("tid", NUMERIC_IDS)
def test_no_misconception_is_graded_correct(tid):
    t = bank.TEMPLATES[tid]
    labels = {l.key: l for l in t.labels}
    for seed in range(300):
        p = t.gen(random.Random(seed))
        truth = t.solve(p)
        for mid, fn in t.traps.items():
            for sig in fn(p):
                assert set(sig) <= set(labels), (tid, mid, sig)
                wrong = _wrong_parts(sig, truth)
                assert wrong, f"{tid} seed {seed}: {mid} predicts exactly the right answer"
                for key, x in wrong.items():
                    assert not labels[key].close(x, truth[key]), (
                        f"{tid} seed {seed}: {mid} predicts {key}={x}, inside the band around the truth {truth[key]}")


@pytest.mark.parametrize("tid", NUMERIC_IDS)
def test_misconceptions_are_distinguishable(tid):
    t = bank.TEMPLATES[tid]
    labels = {l.key: l for l in t.labels}
    for seed in range(300):
        p = t.gen(random.Random(seed))
        truth = t.solve(p)
        preds = [(mid, k, x) for mid, fn in t.traps.items() for sig in fn(p) for k, x in _wrong_parts(sig, truth).items()]
        for i, (m1, k1, x1) in enumerate(preds):
            for m2, k2, x2 in preds[i + 1:]:
                assert not (m1 != m2 and k1 == k2 and labels[k1].close(x1, x2)), (
                    f"{tid} seed {seed}: {m1} and {m2} both predict {k1}={x1}")


def test_generators_rarely_need_resampling():
    """The resampling guard is a safety net, not the design: ranges themselves should be clean."""
    for tid in NUMERIC_IDS:
        t = bank.TEMPLATES[tid]
        base = getattr(t, "raw_gen", None)
        if base is None:
            continue
        bad = sum(not bank._diagnosable(t, base(random.Random(s))) for s in range(300))
        assert bad / 300 <= 0.10, f"{tid}: {bad}/300 raw instances undiagnosable"


def test_every_group_has_basic_material():
    for g in bank.GROUPS:
        if g == "generalist":
            continue
        assert any(g in t.groups and t.difficulty == 1 for t in bank.TEMPLATES.values()), g


def test_new_templates_hand_worked():
    assert q("ev_bridge_basic", S=25.0, Q=10.0, D=200.0, C=80.0).values == {"equity_value": 250.0, "ev": 370.0}
    v = q("acc_asset_sale", B=80.0, P=100.0, t=0.25).values
    assert v["ni"] == pytest.approx(15) and v["cash"] == pytest.approx(95) and v["ppe"] == -80
    assert q("ma_synergies_breakeven", P=500.0, NIt=16.0, t=0.4).values["synergies"] == pytest.approx(15)
    assert q("dcf_unlever_beta", t=0.25, de=0.4, bL=1.04).values["beta_u"] == pytest.approx(0.8)
    v = q("lbo_levers", m0=10.0, m1=11.0, E1=120.0, D0=400.0, Dp=100.0).values
    assert v["equity_gain"] == pytest.approx(v["ebitda_growth"] + v["multiple_exp"] + v["paydown"]) == pytest.approx(420)
    assert q("dcf_pv", X=121.0, r=0.10, n=2.0).values["pv"] == pytest.approx(100)


def test_tsm_basic_shares_now_graded_wrong():
    qq = q("ev_tsm", S=25.0, B=100.0, N=2.0, K=15.0)   # truth 100.8
    c = {x.label: x for x in bank.check_numbers(qq, {"diluted_shares": 100.0})}["diluted_shares"]
    assert c.status == "wrong" and "EV_TSM_BASIC" in c.matches


def test_offer_premium():
    v = q("ma_premium", P0=25.0, Offer=30.0, Q=20.0).values
    assert v["premium"] == pytest.approx(20) and v["purchase_equity"] == pytest.approx(600)
    c = {x.label: x for x in bank.check_numbers(q("ma_premium", P0=25.0, Offer=30.0, Q=20.0), {"premium": 16.67})}["premium"]
    assert c.status == "wrong" and "MA_PREMIUM_ON_OFFER" in c.matches


def _as_said(label, x):
    """The truth the way a person rounds it out loud (QA G-02)."""
    if label.unit == "%":
        return round(x, 1)
    if label.unit == "$":
        return float(round(x)) if abs(x) >= 20 else round(x, 2)
    return round(x, 2)   # $/sh to the cent; multiples and share counts to 2dp


@pytest.mark.parametrize("tid", NUMERIC_IDS)
def test_interview_rounding_is_accepted(tid):
    t = bank.TEMPLATES[tid]
    for seed in range(300):
        qq = bank.build(t, t.gen(random.Random(seed)))
        said = {l.key: _as_said(l, qq.values[l.key]) for l in qq.labels}
        bad = [(c.label, c.stated, c.expected) for c in bank.check_numbers(qq, said) if c.status != "correct"]
        assert not bad, f"{tid} seed {seed}: rounded answer marked wrong {bad}"


def test_whole_percent_dilution_and_one_decimal_wacc_pass():
    # QA N11 / N18: "about ten percent dilutive", "WACC about 8.9%"
    qq = q("ma_stock", Pa=40.0, Sa=100.0, PEa=10.0, Mt=1200.0, prem=0.5, PEt=15.0, r=0.04, rd=0.06, t=0.25)
    truth = qq.values["accretion"]
    c = {x.label: x for x in bank.check_numbers(qq, {"accretion": float(round(truth))})}
    assert c["accretion"].status == "correct", truth
    qw = q("mkt_rates_wacc", we=0.6, w0=0.08, b=1.0, t=0.2, g=0.02, bp=100.0)   # truth 8.94
    assert bank.check_numbers(qw, {"wacc_new": 8.9})[0].status == "correct"


def test_equity_issue_mistake_has_its_own_teaching_note():
    qq = q("ev_equity_issue", X=200.0)
    c = {x.label: x for x in bank.check_numbers(qq, {"equity_value": 0.0, "ev": 0.0})}
    assert c["equity_value"].matches == ["EV_EQUITY_ISSUE_NO_CHANGE"] and c["ev"].status == "correct"
    assert "rises by the cash raised" in LIBRARY["EV_EQUITY_ISSUE_NO_CHANGE"].fix


def test_rnpv_traps_are_named_for_what_went_wrong():
    qq = q("hc_rnpv", V=1500.0, pr=0.3, Cd=150.0)   # truth 300
    m = lambda x: bank.check_numbers(qq, {"rnpv": x})[0].matches
    assert m(405.0) == ["HC_RNPV_WEIGHTS_COSTS"] and m(1350.0) == ["HC_RNPV_UNWEIGHTED"]
    assert "before any trial costs" in qq.text


def test_accretion_direction_flip_is_named():
    qq = q("ma_stock", Pa=40.0, Sa=100.0, PEa=10.0, Mt=1200.0, prem=0.5, PEt=15.0, r=0.04, rd=0.06, t=0.25)
    c = bank.check_numbers(qq, {"accretion": -qq.values["accretion"]})[0]
    assert c.status == "wrong" and c.matches == ["MA_ACCRETION_SIGN"]


_STOP = set("""the a an and or of to in on for with is are be it its this that as by at from than then so not no into
their them they you your what when which who how why more most less can does do about each per very also just only
over under up down out usually often like such will would should may every while because""".split())


def _terms(text):
    import re
    return {w[:5] for w in re.findall(r"[a-z0-9/&\-]+", text.lower()) if len(w) >= 3 and w not in _STOP}


@pytest.mark.parametrize("tid", [tid for tid, t in bank.TEMPLATES.items() if t.kind != "numeric"])
def test_model_answer_covers_its_own_key_points(tid):
    """QA F-02: the worked answer shown to a student must pass its own rubric, so each key point's main
    terms have to appear in it (at least half of them; paraphrase covers the rest)."""
    t = bank.TEMPLATES[tid]
    answer = _terms(t.explain({"group": "investment banking"}, {}))
    for kp in t.key_points:
        terms = _terms(kp)
        assert len(terms & answer) / len(terms) >= 0.5, f"{tid}: model answer misses key point '{kp}'"


# ---------------------------------------------------------------- UX QA round 2, D-08: no "why banking" twice
def test_why_team_question_reads_well_for_generalists():
    t = bank.TEMPLATES["b_why_group"]
    assert t.title == "Why this team"
    assert t.text({"group": "investment banking", "generalist": True}) == "Why banking, and what kind of team interests you?"
    assert t.text({"group": "Healthcare"}) == "Why do you want to work in Healthcare?"


def test_why_ib_and_why_team_are_never_asked_in_one_session():
    from ticktie import mastery
    for first, twin in (("b_why_ib", "b_why_group"), ("b_why_group", "b_why_ib")):
        for seed in range(30):
            rng = random.Random(seed)
            for lvl in (1, 2):
                t = mastery.pick_targeted("generalist", "fit", lvl, None, [first], {}, rng)
                assert t.id != twin
