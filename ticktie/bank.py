"""Question bank: parameterised IB technical questions with calculators.

Every numeric template does three things deterministically:

* ``gen``   draws fresh numbers, so each question is new and answers can't be memorised;
* ``solve`` computes the correct answer for each graded line item ("label");
* ``traps`` computes the wrong answer each named misconception would produce.

The agents never compute the answer key. They only read what the candidate
said and map it to these labels.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Callable

Params = dict[str, float]
Values = dict[str, float]


# --------------------------------------------------------------------------- formatting
def money(v: float, unit: str = "") -> str:
    """$7.50, $1,250, -$40 (trailing .00 dropped)."""
    sign = "-" if v < 0 else ""
    v = abs(v)
    s = f"{v:,.2f}" if round(v, 2) != round(v) else f"{v:,.0f}"
    return f"{sign}${s}{unit}"


def _trim(s: str) -> str:
    """Drop trailing decimal zeros only: '7.50' -> '7.5', '20' stays '20'."""
    return s.rstrip("0").rstrip(".") if "." in s else s


def pct(v: float, dp: int = 1) -> str:
    """0.25 -> 25%, 0.075 -> 7.5%, 0.2 -> 20%."""
    return f"{_trim(f'{v * 100:.{dp}f}')}%"


def num(v: float, dp: int = 2) -> str:
    return _trim(f"{v:,.{dp}f}")


def chg(v: float) -> str:
    """Signed money change in words: 'up $7.50' / 'down $7.50' / 'unchanged'."""
    if abs(v) < 1e-9:
        return "unchanged"
    return f"{'up' if v > 0 else 'down'} {money(abs(v))}"


# --------------------------------------------------------------------------- data model
@dataclass(frozen=True)
class Label:
    key: str
    name: str
    unit: str  # "$" | "%" | "x" | "mm" | "$/sh"
    required: bool = True
    tol_abs: float = 0.05
    tol_rel: float = 0.01
    signed: bool | None = None  # None = infer: "Change in ..." / accretion labels are signed, levels aren't

    @property
    def is_signed(self) -> bool:
        if self.signed is not None:
            return self.signed
        n = self.name.lower()
        return n.startswith("change") or "accretion" in n

    def close(self, stated: float, truth: float) -> bool:
        if not self.is_signed:  # a level ("IRR", "lost paydown"): direction words don't change the size
            stated, truth = abs(stated), abs(truth)
        return abs(stated - truth) <= max(self.tol_abs, self.tol_rel * abs(truth))


@dataclass
class Template:
    id: str
    skill: str
    difficulty: int
    kind: str  # "numeric" | "conceptual"
    title: str
    text: Callable[[Params], str]
    key_points: list[str]
    misconceptions: list[str]
    gen: Callable[[random.Random], Params] = lambda r: {}
    solve: Callable[[Params], Values] = lambda p: {}
    labels: list[Label] = field(default_factory=list)
    traps: dict[str, Callable[[Params], list[Values]]] = field(default_factory=dict)
    explain: Callable[[Params, Values], str] = lambda p, v: ""
    vary: Callable[[Params, random.Random], tuple[Params, str]] | None = None
    target_seconds: int = 60


@dataclass
class Question:
    """One concrete instance the candidate sees."""

    template_id: str
    skill: str
    difficulty: int
    kind: str
    title: str
    text: str
    params: Params
    values: Values
    labels: list[Label]
    signatures: dict[str, list[Values]]
    key_points: list[str]
    misconceptions: list[str]
    solution: str
    target_seconds: int

    def to_public(self) -> dict:
        """What the browser may see before the answer is revealed: no answer key."""
        return {
            "template_id": self.template_id,
            "skill": self.skill,
            "difficulty": self.difficulty,
            "kind": self.kind,
            "title": self.title,
            "text": self.text,
            "target_seconds": self.target_seconds,
        }

    def to_state(self) -> dict:
        return {
            "template_id": self.template_id,
            "params": self.params,
            "text": self.text,
        }


def _a(x: float) -> float:
    return round(x, 6)


# --------------------------------------------------------------------------- helpers
TAXES = [0.20, 0.25, 0.30, 0.40]
AMTS = [10, 20, 40, 50, 100]


def _other(rng: random.Random, choices: list, current):
    opts = [c for c in choices if c != current]
    return rng.choice(opts)


def _vary_tax(p: Params, rng: random.Random) -> tuple[Params, str]:
    q = dict(p)
    q["t"] = _other(rng, TAXES, p["t"])
    return q, f"Same situation, but now the tax rate is {pct(q['t'])}. What changes?"


# =========================================================================== ACCOUNTING
def _noncash_template(tid: str, item: str, asset_label: str, asset_name: str,
                      text_fmt: str, extra_traps: dict | None = None,
                      equity_override: Callable[[Params], float] | None = None,
                      asset_sign: int = -1, explain_mid: str = "") -> Template:
    """D&A, inventory write-down and SBC all follow the same non-cash pattern."""

    def solve(p: Params) -> Values:
        X, t = p["X"], p["t"]
        v = {"ni": _a(-X * (1 - t)), "cash": _a(X * t)}
        if asset_label:
            v[asset_label] = _a(asset_sign * X)
        v["equity"] = _a(equity_override(p) if equity_override else -X * (1 - t))
        return v

    traps = {
        "ACC_NO_TAX": lambda p: [{"ni": -p["X"], "cash": 0.0}],
        "ACC_NONCASH_AS_CASH": lambda p: [{"cash": _a(-p["X"] * (1 - p["t"]))}, {"cash": -p["X"]}],
        "ACC_ADDBACK_NO_NI": lambda p: [{"cash": p["X"]}],
        "ACC_SIGN_FLIP": lambda p: [{"ni": _a(p["X"] * (1 - p["t"]))}, {"cash": _a(-p["X"] * p["t"])}],
    }
    if extra_traps:
        traps.update(extra_traps)

    labels = [
        Label("ni", "Change in net income", "$"),
        Label("cash", "Change in cash", "$"),
    ]
    if asset_label:
        labels.append(Label(asset_label, f"Change in {asset_name}", "$", required=False))
    labels.append(Label("equity", "Change in shareholders' equity", "$", required=False))

    def explain(p: Params, v: Values) -> str:
        X, t = p["X"], p["t"]
        return (
            f"Income statement: {item} of {money(X)} lowers pre-tax income by {money(X)}. "
            f"At a {pct(t)} tax rate, taxes fall by {money(X * t)}, so net income is {chg(v['ni'])}. "
            f"Cash flow statement: start from net income ({money(v['ni'])}) and add back the {money(X)} "
            f"because it is non-cash, so cash is {chg(v['cash'])}. {explain_mid}"
            f"Balance sheet: cash {chg(v['cash'])}"
            + (f", {asset_name} {chg(v[asset_label])}" if asset_label else "")
            + f"; shareholders' equity {chg(v['equity'])}. Both sides balance."
        )

    def vary(p: Params, rng: random.Random) -> tuple[Params, str]:
        if rng.random() < 0.5:
            return _vary_tax(p, rng)
        q = dict(p)
        q["X"] = _other(rng, AMTS, p["X"])
        return q, f"Now make it {money(q['X'])} instead of {money(p['X'])}, same {pct(p['t'])} tax rate. Walk me through it again, quickly."

    return Template(
        id=tid, skill="accounting", difficulty=1 if tid == "acc_da" else 2, kind="numeric",
        title=f"3-statement walk: {item}",
        text=lambda p: text_fmt.format(X=money(p["X"]), t=pct(p["t"])),
        gen=lambda r: {"X": float(r.choice(AMTS)), "t": r.choice(TAXES)},
        solve=solve, labels=labels, traps=traps, explain=explain, vary=vary,
        key_points=[
            "Net income falls by the after-tax amount",
            "It is added back on the cash flow statement because it is non-cash",
            "Cash rises by the tax saving",
            "The balance sheet balances through retained earnings",
        ],
        misconceptions=list(traps.keys()),
        target_seconds=60,
    )


ACC_DA = _noncash_template(
    "acc_da", "an increase in depreciation", "ppe", "net PP&E",
    "Walk me through the three statements if depreciation goes up by {X}. Assume a {t} tax rate.",
)
ACC_WRITEDOWN = _noncash_template(
    "acc_writedown", "an inventory write-down", "inventory", "inventory",
    "A company writes down {X} of inventory. Walk me through the three statements. "
    "Assume the write-down is tax-deductible and a {t} tax rate.",
)
ACC_SBC = _noncash_template(
    "acc_sbc", "stock-based compensation", "", "",
    "A company records {X} of stock-based compensation. Walk me through the three statements. "
    "Assume it is tax-deductible and a {t} tax rate.",
    extra_traps={"ACC_SBC_EQUITY": lambda p: [{"equity": _a(-p["X"] * (1 - p["t"]))}]},
    equity_override=lambda p: p["X"] * p["t"],
    explain_mid="Equity: retained earnings fall by the after-tax amount, but common stock/APIC rises by the full grant. ",
)


def _capex_solve(p: Params) -> Values:
    return {"ni": 0.0, "cash": -p["X"], "ppe": p["X"]}


ACC_CAPEX = Template(
    id="acc_capex", skill="accounting", difficulty=1, kind="numeric",
    title="3-statement walk: buying PP&E",
    text=lambda p: (f"On the last day of the year, a company buys {money(p['X'])} of PP&E with cash. "
                    f"Walk me through the three statements. Tax rate is {pct(p['t'])}."),
    gen=lambda r: {"X": float(r.choice([50, 100, 200, 500])), "t": r.choice(TAXES)},
    solve=_capex_solve,
    labels=[Label("ni", "Change in net income", "$"), Label("cash", "Change in cash", "$"),
            Label("ppe", "Change in PP&E", "$", required=False)],
    traps={
        "ACC_CAPEX_EXPENSED": lambda p: [{"ni": _a(-p["X"] * (1 - p["t"]))}, {"ni": -p["X"]}],
        "ACC_SIGN_FLIP": lambda p: [{"cash": p["X"]}],
    },
    explain=lambda p, v: (
        f"Income statement: nothing yet. Capex isn't an expense, and bought on the last day there is "
        f"no depreciation this year, so net income is unchanged. Cash flow statement: investing "
        f"activities show {money(-p['X'])} of capex, so cash is {chg(v['cash'])}. Balance sheet: cash "
        f"{chg(v['cash'])}, PP&E {chg(v['ppe'])}. Total assets are unchanged, and so is equity."
    ),
    key_points=["No income statement impact at purchase", "Capex is an investing cash outflow",
                "PP&E rises and cash falls by the same amount"],
    misconceptions=["ACC_CAPEX_EXPENSED", "ACC_SIGN_FLIP"],
    target_seconds=45,
)


def _ar_solve(p: Params) -> Values:
    X, t = p["X"], p["t"]
    return {"ni": _a(X * (1 - t)), "cash": _a(-X * t), "ar": X}


ACC_AR = Template(
    id="acc_ar", skill="accounting", difficulty=2, kind="numeric",
    title="3-statement walk: revenue on credit",
    text=lambda p: (f"A company records {money(p['X'])} of revenue, but the customer hasn't paid yet. "
                    f"There are no associated costs. Walk me through the three statements at a "
                    f"{pct(p['t'])} tax rate, assuming taxes are paid in cash."),
    gen=lambda r: {"X": float(r.choice(AMTS)), "t": r.choice(TAXES)},
    solve=_ar_solve,
    labels=[Label("ni", "Change in net income", "$"), Label("cash", "Change in cash", "$"),
            Label("ar", "Change in accounts receivable", "$", required=False)],
    traps={
        "ACC_AR_IGNORED": lambda p: [{"cash": _a(p["X"] * (1 - p["t"]))}, {"cash": p["X"]}],
        "ACC_NO_TAX": lambda p: [{"ni": p["X"], "cash": 0.0}],
    },
    explain=lambda p, v: (
        f"Income statement: revenue up {money(p['X'])}, taxes up {money(p['X'] * p['t'])}, so net income "
        f"is {chg(v['ni'])}. Cash flow statement: start with net income, then subtract the {money(p['X'])} "
        f"increase in accounts receivable because the cash hasn't been collected, so cash is {chg(v['cash'])} "
        f"(the taxes you paid). Balance sheet: AR {chg(v['ar'])} and cash {chg(v['cash'])}, so assets rise by "
        f"{money(v['ni'])}, matching the {money(v['ni'])} increase in retained earnings."
    ),
    vary=_vary_tax,
    key_points=["Net income rises by the after-tax revenue", "The AR increase is subtracted on the CFS",
                "Cash falls by the taxes paid", "AR rises on the balance sheet"],
    misconceptions=["ACC_AR_IGNORED", "ACC_NO_TAX"],
)


def _debt_solve(p: Params) -> Values:
    D, r, t = p["D"], p["r"], p["t"]
    return {"ni": _a(-D * r * (1 - t)), "cash": _a(D - D * r * (1 - t)), "debt": D}


ACC_DEBT = Template(
    id="acc_debt", skill="accounting", difficulty=2, kind="numeric",
    title="3-statement walk: raising debt and paying interest",
    text=lambda p: (f"A company borrows {money(p['D'])} at {pct(p['r'])} interest and pays one full year of "
                    f"interest in cash. Tax rate is {pct(p['t'])}. Walk me through the three statements "
                    f"after that year."),
    gen=lambda r: {"D": float(r.choice([100, 200, 500])), "r": r.choice([0.05, 0.06, 0.08, 0.10]), "t": r.choice(TAXES)},
    solve=_debt_solve,
    labels=[Label("ni", "Change in net income", "$"), Label("cash", "Change in cash", "$"),
            Label("debt", "Change in debt", "$", required=False)],
    traps={
        "ACC_INTEREST_NO_TAX": lambda p: [{"ni": -p["D"] * p["r"], "cash": _a(p["D"] - p["D"] * p["r"])}],
        "ACC_SIGN_FLIP": lambda p: [{"ni": _a(p["D"] * p["r"] * (1 - p["t"]))}],
    },
    explain=lambda p, v: (
        f"Income statement: interest expense of {money(p['D'] * p['r'])} lowers pre-tax income. After the "
        f"{pct(p['t'])} tax shield, net income is {chg(v['ni'])}. Cash flow statement: net income "
        f"{money(v['ni'])} in operations, plus {money(p['D'])} of debt raised in financing, so cash is "
        f"{chg(v['cash'])}. Balance sheet: cash {chg(v['cash'])}, debt {chg(v['debt'])}, retained earnings "
        f"{chg(v['ni'])}. It balances."
    ),
    vary=_vary_tax,
    key_points=["Interest expense is tax-deductible", "The debt raise is a financing inflow",
                "Net cash change = borrowing minus after-tax interest"],
    misconceptions=["ACC_INTEREST_NO_TAX", "ACC_SIGN_FLIP"],
)


# =========================================================================== EV / EQUITY
def _ev_gen(r: random.Random) -> Params:
    return {"S": float(r.choice([20, 25, 40, 50])), "Q": float(r.choice([10, 20, 50])),
            "D": float(r.choice([100, 200, 300, 400])), "C": float(r.choice([50, 80, 120, 150])),
            "P": float(r.choice([20, 40, 60])), "N": float(r.choice([10, 30, 50]))}


def _ev(p: Params) -> float:
    return p["S"] * p["Q"] + p["D"] + p["P"] + p["N"] - p["C"]


EV_BRIDGE = Template(
    id="ev_bridge", skill="ev", difficulty=1, kind="numeric",
    title="Equity value to enterprise value",
    text=lambda p: (f"A company's share price is {money(p['S'])} with {num(p['Q'])} million diluted shares. "
                    f"It has {money(p['D'])}mm of debt, {money(p['C'])}mm of cash, {money(p['P'])}mm of "
                    f"preferred stock and {money(p['N'])}mm of noncontrolling interest. What's its enterprise value?"),
    gen=_ev_gen,
    solve=lambda p: {"equity_value": p["S"] * p["Q"], "ev": _ev(p)},
    labels=[Label("ev", "Enterprise value ($mm)", "$"),
            Label("equity_value", "Equity value ($mm)", "$", required=False)],
    traps={
        "EV_ADD_CASH": lambda p: [{"ev": _ev(p) + 2 * p["C"]}],
        "EV_MISS_CLAIMS": lambda p: [{"ev": _ev(p) - p["P"] - p["N"]}, {"ev": _ev(p) - p["P"]}, {"ev": _ev(p) - p["N"]}],
        "EV_BRIDGE_SIGN": lambda p: [{"ev": p["S"] * p["Q"] - p["D"] + p["C"]}, {"ev": p["S"] * p["Q"] - p["D"] - p["P"] - p["N"] + p["C"]}],
    },
    explain=lambda p, v: (
        f"Equity value = {money(p['S'])} x {num(p['Q'])}mm = {money(v['equity_value'])}mm. "
        f"EV = equity value + debt + preferred + NCI - cash = {money(v['equity_value'])} + {money(p['D'])} + "
        f"{money(p['P'])} + {money(p['N'])} - {money(p['C'])} = {money(v['ev'])}mm."
    ),
    vary=lambda p, r: (lambda q: (q, f"Same company, but now it has {money(q['C'])}mm of cash. What's EV now?"))(
        {**p, "C": float(_other(r, [50, 80, 120, 150, 250], p["C"]))}),
    key_points=["Equity value = share price x diluted shares", "Add debt, preferred and NCI",
                "Subtract cash"],
    misconceptions=["EV_ADD_CASH", "EV_MISS_CLAIMS", "EV_BRIDGE_SIGN"],
    target_seconds=45,
)


def _ip_gen(r: random.Random) -> Params:
    return {"E": float(r.choice([50, 80, 100, 120])), "m": float(r.choice([8, 10, 12])),
            "D": float(r.choice([150, 200, 300])), "C": float(r.choice([50, 100])),
            "Q": float(r.choice([10, 20, 25, 50]))}


def _ip_price(p: Params) -> float:
    return (p["E"] * p["m"] - p["D"] + p["C"]) / p["Q"]


EV_IMPLIED_PRICE = Template(
    id="ev_implied_price", skill="ev", difficulty=2, kind="numeric",
    title="Implied share price from a multiple",
    text=lambda p: (f"Comparable companies trade at {num(p['m'])}x EBITDA. Our company has {money(p['E'])}mm "
                    f"of EBITDA, {money(p['D'])}mm of debt, {money(p['C'])}mm of cash and {num(p['Q'])} million "
                    f"diluted shares. What's the implied share price?"),
    gen=_ip_gen,
    solve=lambda p: {"ev": p["E"] * p["m"], "equity_value": p["E"] * p["m"] - p["D"] + p["C"], "price": _a(_ip_price(p))},
    labels=[Label("price", "Implied share price", "$/sh"),
            Label("ev", "Implied enterprise value ($mm)", "$", required=False),
            Label("equity_value", "Implied equity value ($mm)", "$", required=False)],
    traps={
        "EV_BRIDGE_SIGN": lambda p: [{"price": _a((p["E"] * p["m"] + p["D"] - p["C"]) / p["Q"]),
                                       "equity_value": p["E"] * p["m"] + p["D"] - p["C"]},
                                      {"price": _a(p["E"] * p["m"] / p["Q"]), "equity_value": p["E"] * p["m"]}],
    },
    explain=lambda p, v: (
        f"Implied EV = {num(p['m'])}x x {money(p['E'])} = {money(v['ev'])}mm. Equity value = EV - debt + cash = "
        f"{money(v['ev'])} - {money(p['D'])} + {money(p['C'])} = {money(v['equity_value'])}mm. Per share: "
        f"{money(v['equity_value'])} / {num(p['Q'])}mm = {money(v['price'])}."
    ),
    vary=lambda p, r: (lambda q: (q, f"What if comps trade at {num(q['m'])}x instead?"))(
        {**p, "m": float(_other(r, [8, 10, 12, 14], p["m"]))}),
    key_points=["Multiply EBITDA by the EV multiple to get EV", "Subtract debt and add cash to get equity value",
                "Divide by diluted shares"],
    misconceptions=["EV_BRIDGE_SIGN"],
)

EV_DEBT_CASH = Template(
    id="ev_debt_cash", skill="ev", difficulty=1, kind="numeric",
    title="Does financing change EV?",
    text=lambda p: (f"A company raises {money(p['X'])}mm of new debt and keeps all of it as cash on the balance "
                    f"sheet. What happens to its enterprise value and its equity value?"),
    gen=lambda r: {"X": float(r.choice([100, 200, 500]))},
    solve=lambda p: {"ev": 0.0, "equity_value": 0.0},
    labels=[Label("ev", "Change in enterprise value ($mm)", "$"),
            Label("equity_value", "Change in equity value ($mm)", "$")],
    traps={"EV_FINANCING_MOVES_EV": lambda p: [{"ev": p["X"]}, {"equity_value": -p["X"]}, {"ev": -p["X"]}]},
    explain=lambda p, v: (
        f"Debt rises {money(p['X'])}mm and cash rises {money(p['X'])}mm, so net debt is unchanged. "
        f"EV = equity value + debt - cash is unchanged, and so is equity value: nothing about the operating "
        f"business or the shareholders' claim changed."
    ),
    key_points=["Debt and cash rise by the same amount", "Net debt is unchanged, so EV is unchanged",
                "Equity value is unchanged"],
    misconceptions=["EV_FINANCING_MOVES_EV"],
    target_seconds=30,
)


# =========================================================================== DCF
def _ufcf(p: Params) -> float:
    return p["EBIT"] * (1 - p["t"]) + p["DA"] - p["CX"] - p["NWC"]


DCF_UFCF = Template(
    id="dcf_ufcf", skill="dcf", difficulty=2, kind="numeric",
    title="Unlevered free cash flow",
    text=lambda p: (f"A company has EBIT of {money(p['EBIT'])}, D&A of {money(p['DA'])}, capex of {money(p['CX'])}, "
                    f"interest expense of {money(p['I'])}, and net working capital increases by {money(p['NWC'])}. "
                    f"Tax rate is {pct(p['t'])}. What's unlevered free cash flow?"),
    gen=lambda r: {"EBIT": float(r.choice([100, 200, 400])), "DA": float(r.choice([20, 30, 50])),
                   "CX": float(r.choice([40, 60, 80])), "NWC": float(r.choice([10, 20])),
                   "I": float(r.choice([10, 20, 30])), "t": r.choice(TAXES)},
    solve=lambda p: {"ufcf": _a(_ufcf(p)), "nopat": _a(p["EBIT"] * (1 - p["t"]))},
    labels=[Label("ufcf", "Unlevered free cash flow", "$"),
            Label("nopat", "NOPAT (EBIT after tax)", "$", required=False)],
    traps={
        "DCF_LEVERED": lambda p: [{"ufcf": _a(_ufcf(p) - p["I"] * (1 - p["t"]))}, {"ufcf": _a(_ufcf(p) - p["I"])}],
        "DCF_NO_TAX": lambda p: [{"ufcf": _a(_ufcf(p) + p["EBIT"] * p["t"]), "nopat": p["EBIT"]}],
        "DCF_NWC_SIGN": lambda p: [{"ufcf": _a(_ufcf(p) + 2 * p["NWC"])}],
    },
    explain=lambda p, v: (
        f"NOPAT = EBIT x (1 - t) = {money(p['EBIT'])} x {num(1 - p['t'])} = {money(v['nopat'])}. "
        f"Add D&A {money(p['DA'])}, subtract capex {money(p['CX'])} and the NWC increase {money(p['NWC'])}: "
        f"UFCF = {money(v['ufcf'])}. Interest is ignored because unlevered FCF is before financing."
    ),
    vary=_vary_tax,
    key_points=["Start from EBIT after tax (NOPAT)", "Add back D&A", "Subtract capex",
                "Subtract the increase in NWC", "Ignore interest expense"],
    misconceptions=["DCF_LEVERED", "DCF_NO_TAX", "DCF_NWC_SIGN"],
)


def _tv(p: Params) -> float:
    return p["F"] * (1 + p["g"]) / (p["w"] - p["g"])


DCF_TV = Template(
    id="dcf_tv", skill="dcf", difficulty=2, kind="numeric",
    title="Terminal value (perpetuity growth)",
    text=lambda p: (f"Final-year unlevered FCF is {money(p['F'])}mm. WACC is {pct(p['w'])} and long-term growth is "
                    f"{pct(p['g'])}. What's the terminal value using the perpetuity growth method?"),
    gen=lambda r: {"F": float(r.choice([50, 80, 100, 120])), "w": r.choice([0.08, 0.09, 0.10, 0.12]),
                   "g": r.choice([0.02, 0.03])},
    solve=lambda p: {"tv": _a(_tv(p))},
    labels=[Label("tv", "Terminal value ($mm)", "$", tol_rel=0.015)],
    traps={
        "DCF_TV_NO_GROWTH_STEP": lambda p: [{"tv": _a(p["F"] / (p["w"] - p["g"]))}],
        "DCF_TV_PLUS_G": lambda p: [{"tv": _a(p["F"] * (1 + p["g"]) / (p["w"] + p["g"]))}, {"tv": _a(p["F"] / (p["w"] + p["g"]))}],
    },
    explain=lambda p, v: (
        f"TV = FCF x (1 + g) / (WACC - g) = {money(p['F'])} x {num(1 + p['g'], 3)} / ({pct(p['w'])} - {pct(p['g'])}) "
        f"= {money(p['F'] * (1 + p['g']))} / {pct(p['w'] - p['g'])} = {money(round(v['tv'], 1))}mm. "
        f"This is the value at the end of the forecast; discount it back to today."
    ),
    vary=lambda p, r: (lambda q: (q, f"What if WACC were {pct(q['w'])} instead?"))(
        {**p, "w": _other(r, [0.08, 0.09, 0.10, 0.12], p["w"])}),
    key_points=["Grow final-year FCF by one year: FCF x (1 + g)", "Divide by WACC - g",
                "Discount the TV back to the present"],
    misconceptions=["DCF_TV_NO_GROWTH_STEP", "DCF_TV_PLUS_G"],
)


def _wacc(p: Params) -> float:
    V = p["E"] + p["D"]
    return p["E"] / V * p["Re"] + p["D"] / V * p["Rd"] * (1 - p["t"])


DCF_WACC = Template(
    id="dcf_wacc", skill="dcf", difficulty=2, kind="numeric",
    title="WACC",
    text=lambda p: (f"A company has {money(p['E'])}mm of equity (market value) and {money(p['D'])}mm of debt. "
                    f"Cost of equity is {pct(p['Re'])}, pre-tax cost of debt is {pct(p['Rd'])}, and the tax rate is "
                    f"{pct(p['t'])}. What's the WACC?"),
    gen=lambda r: (lambda e: {"E": float(e), "D": float(1000 - e), "Re": r.choice([0.10, 0.11, 0.12]),
                              "Rd": r.choice([0.05, 0.06, 0.08]), "t": r.choice(TAXES)})(r.choice([600, 700, 800])),
    solve=lambda p: {"wacc": _a(_wacc(p) * 100)},
    labels=[Label("wacc", "WACC (%)", "%", tol_abs=0.1, tol_rel=0)],
    traps={"DCF_WACC_NO_SHIELD": lambda p: [{"wacc": _a((p["E"] * p["Re"] + p["D"] * p["Rd"]) / (p["E"] + p["D"]) * 100)}]},
    explain=lambda p, v: (
        f"Weights: equity {pct(p['E'] / (p['E'] + p['D']))}, debt {pct(p['D'] / (p['E'] + p['D']))}. After-tax cost of "
        f"debt = {pct(p['Rd'])} x (1 - {pct(p['t'])}) = {pct(p['Rd'] * (1 - p['t']), 2)}. WACC = "
        f"{pct(p['E'] / (p['E'] + p['D']))} x {pct(p['Re'])} + {pct(p['D'] / (p['E'] + p['D']))} x "
        f"{pct(p['Rd'] * (1 - p['t']), 2)} = {num(v['wacc'])}%."
    ),
    vary=_vary_tax,
    key_points=["Weight by market values", "Use the after-tax cost of debt", "WACC = E/V x Re + D/V x Rd x (1 - t)"],
    misconceptions=["DCF_WACC_NO_SHIELD"],
)

DCF_CAPM = Template(
    id="dcf_capm", skill="dcf", difficulty=1, kind="numeric",
    title="Cost of equity (CAPM)",
    text=lambda p: (f"The risk-free rate is {pct(p['rf'])}, the expected market return is {pct(p['Rm'])}, and the "
                    f"company's levered beta is {num(p['b'])}. What's its cost of equity?"),
    gen=lambda r: {"rf": r.choice([0.03, 0.04, 0.05]), "Rm": r.choice([0.08, 0.09, 0.10]), "b": r.choice([0.8, 1.2, 1.5])},
    solve=lambda p: {"re": _a((p["rf"] + p["b"] * (p["Rm"] - p["rf"])) * 100)},
    labels=[Label("re", "Cost of equity (%)", "%", tol_abs=0.1, tol_rel=0)],
    traps={"DCF_CAPM_MARKET_RETURN": lambda p: [{"re": _a((p["rf"] + p["b"] * p["Rm"]) * 100)}, {"re": _a(p["b"] * p["Rm"] * 100)}]},
    explain=lambda p, v: (
        f"Equity risk premium = market return - risk-free = {pct(p['Rm'])} - {pct(p['rf'])} = {pct(p['Rm'] - p['rf'])}. "
        f"Re = rf + beta x ERP = {pct(p['rf'])} + {num(p['b'])} x {pct(p['Rm'] - p['rf'])} = {num(v['re'])}%."
    ),
    vary=lambda p, r: (lambda q: (q, f"What if beta were {num(q['b'])}?"))({**p, "b": _other(r, [0.8, 1.2, 1.5], p["b"])}),
    key_points=["ERP = market return - risk-free rate", "Re = rf + beta x ERP"],
    misconceptions=["DCF_CAPM_MARKET_RETURN"],
    target_seconds=40,
)


# =========================================================================== M&A
def _ma_gen(r: random.Random) -> Params:
    return {"Pa": float(r.choice([40, 50, 80])), "Sa": float(r.choice([100, 200])),
            "PEa": float(r.choice([15, 20, 25])), "Mt": float(r.choice([500, 1000, 2000])),
            "prem": r.choice([0.20, 0.25, 0.50]), "PEt": float(r.choice([10, 12, 20, 30])),
            "r": r.choice([0.03, 0.04, 0.05]), "rd": r.choice([0.06, 0.08, 0.10]), "t": r.choice(TAXES)}


def _ma_base(p: Params) -> tuple[float, float, float, float]:
    NIa = p["Pa"] * p["Sa"] / p["PEa"]
    NIt = p["Mt"] / p["PEt"]
    price = p["Mt"] * (1 + p["prem"])
    eps = NIa / p["Sa"]
    return NIa, NIt, price, eps


def _ma_stock_vals(p: Params, price: float) -> Values:
    NIa, NIt, _, eps = _ma_base(p)
    new = price / p["Pa"]
    pf = (NIa + NIt) / (p["Sa"] + new)
    return {"new_shares": _a(new), "pf_eps": _a(pf), "accretion": _a((pf / eps - 1) * 100)}


def _ma_text_common(p: Params) -> str:
    NIa, NIt, price, eps = _ma_base(p)
    return (f"The acquirer's share price is {money(p['Pa'])} with {num(p['Sa'])}mm shares and net income of "
            f"{money(NIa)}mm (EPS {money(eps)}). The target has a market cap of {money(p['Mt'])}mm and net income "
            f"of {money(NIt)}mm. The acquirer pays a {pct(p['prem'], 0)} premium. Ignore synergies and fees.")


MA_STOCK = Template(
    id="ma_stock", skill="ma", difficulty=3, kind="numeric",
    title="Accretion / dilution: all-stock deal",
    text=lambda p: _ma_text_common(p) + " The deal is 100% stock. Is it accretive or dilutive, and by how much?",
    gen=_ma_gen,
    solve=lambda p: _ma_stock_vals(p, _ma_base(p)[2]),
    labels=[Label("accretion", "EPS accretion (+) / dilution (-) (%)", "%", tol_abs=0.3, tol_rel=0.02),
            Label("new_shares", "New shares issued (mm)", "mm", required=False),
            Label("pf_eps", "Pro forma EPS", "$/sh", required=False)],
    traps={"MA_IGNORE_PREMIUM": lambda p: [_ma_stock_vals(p, p["Mt"])]},
    explain=lambda p, v: (lambda NIa, NIt, price, eps: (
        f"Purchase price = {money(p['Mt'])} x {num(1 + p['prem'])} = {money(price)}mm, so new shares = {money(price)} / "
        f"{money(p['Pa'])} = {num(v['new_shares'])}mm. Pro forma EPS = ({money(NIa)} + {money(NIt)}) / ({num(p['Sa'])} + "
        f"{num(v['new_shares'])}) = {money(round(v['pf_eps'], 2))} vs {money(eps)} standalone, so "
        f"{num(abs(v['accretion']), 1)}% {'accretive' if v['accretion'] > 0 else 'dilutive'}. Shortcut: acquirer P/E "
        f"{num(p['PEa'])}x vs purchase P/E {num(price / NIt, 1)}x. The deal is accretive only if the acquirer's P/E is higher."
    ))(*_ma_base(p)),
    vary=lambda p, r: (lambda q: (q, f"What if the premium were {pct(q['prem'], 0)} instead?"))(
        {**p, "prem": _other(r, [0.20, 0.25, 0.50, 0.0], p["prem"])}),
    key_points=["Size new shares off the purchase price including the premium",
                "Pro forma EPS = combined net income / pro forma shares",
                "Compare acquirer P/E to purchase P/E as a shortcut"],
    misconceptions=["MA_IGNORE_PREMIUM", "MA_PE_RULE"],
    target_seconds=150,
)


def _ma_cash_vals(p: Params, after_tax: bool = True, issue_shares: bool = False) -> Values:
    NIa, NIt, price, eps = _ma_base(p)
    lost = price * p["r"] * ((1 - p["t"]) if after_tax else 1)
    shares = p["Sa"] + (price / p["Pa"] if issue_shares else 0)
    pf = (NIa + NIt - (0 if issue_shares else lost)) / shares
    return {"pf_eps": _a(pf), "accretion": _a((pf / eps - 1) * 100)}


MA_CASH = Template(
    id="ma_cash", skill="ma", difficulty=3, kind="numeric",
    title="Accretion / dilution: all-cash deal",
    text=lambda p: _ma_text_common(p) + (f" The deal is paid entirely with cash on hand, which currently earns "
                                         f"{pct(p['r'])} interest. Tax rate is {pct(p['t'])}. Accretive or dilutive, and by how much?"),
    gen=_ma_gen,
    solve=lambda p: _ma_cash_vals(p),
    labels=[Label("accretion", "EPS accretion (+) / dilution (-) (%)", "%", tol_abs=0.3, tol_rel=0.02),
            Label("pf_eps", "Pro forma EPS", "$/sh", required=False)],
    traps={"MA_FOREGONE_NO_TAX": lambda p: [_ma_cash_vals(p, after_tax=False)],
           "MA_SHARES_FOR_CASH": lambda p: [_ma_cash_vals(p, issue_shares=True)]},
    explain=lambda p, v: (lambda NIa, NIt, price, eps: (
        f"Purchase price = {money(price)}mm. Foregone after-tax interest = {money(price)} x {pct(p['r'])} x "
        f"(1 - {pct(p['t'])}) = {money(round(price * p['r'] * (1 - p['t']), 2))}mm. Pro forma net income = {money(NIa)} + "
        f"{money(NIt)} - {money(round(price * p['r'] * (1 - p['t']), 2))}; shares stay {num(p['Sa'])}mm. Pro forma EPS "
        f"{money(round(v['pf_eps'], 2))} vs {money(eps)}: {num(abs(v['accretion']), 1)}% "
        f"{'accretive' if v['accretion'] > 0 else 'dilutive'}. Shortcut: the target's earnings yield "
        f"({pct(NIt / price)}) vs the after-tax cost of cash ({pct(p['r'] * (1 - p['t']), 2)})."
    ))(*_ma_base(p)),
    vary=_vary_tax,
    key_points=["Cost of cash = foregone interest, after tax", "Share count doesn't change in a cash deal",
                "Compare the target's earnings yield to the after-tax cost of cash"],
    misconceptions=["MA_FOREGONE_NO_TAX", "MA_SHARES_FOR_CASH"],
    target_seconds=150,
)


def _ma_debt_vals(p: Params, rd: float | None = None, after_tax: bool = True) -> Values:
    NIa, NIt, price, eps = _ma_base(p)
    rd = p["rd"] if rd is None else rd
    cost = rd * ((1 - p["t"]) if after_tax else 1)
    pf = (NIa + NIt - price * cost) / p["Sa"]
    return {"accretion": _a((pf / eps - 1) * 100), "after_tax_cost": _a(cost * 100),
            "earnings_yield": _a(NIt / price * 100)}


MA_DEBT = Template(
    id="ma_debt", skill="ma", difficulty=3, kind="numeric",
    title="Accretion / dilution: debt-funded deal",
    text=lambda p: _ma_text_common(p) + (f" The deal is funded 100% with new debt at {pct(p['rd'])}. Tax rate is "
                                         f"{pct(p['t'])}. Is it accretive or dilutive, and by how much? What's the quick test?"),
    gen=_ma_gen,
    solve=lambda p: _ma_debt_vals(p),
    labels=[Label("accretion", "EPS accretion (+) / dilution (-) (%)", "%", tol_abs=0.3, tol_rel=0.02),
            Label("earnings_yield", "Target earnings yield at purchase price (%)", "%", required=False, tol_abs=0.15, tol_rel=0),
            Label("after_tax_cost", "After-tax cost of debt (%)", "%", required=False, tol_abs=0.1, tol_rel=0)],
    traps={"MA_FOREGONE_NO_TAX": lambda p: [_ma_debt_vals(p, after_tax=False)]},
    explain=lambda p, v: (lambda NIa, NIt, price, eps: (
        f"Purchase price {money(price)}mm, funded with debt at {pct(p['rd'])}, so the after-tax cost is "
        f"{num(v['after_tax_cost'])}%. Target earnings yield = {money(NIt)} / {money(price)} = {num(v['earnings_yield'])}%. "
        f"The deal is {'accretive' if v['accretion'] > 0 else 'dilutive'} by {num(abs(v['accretion']), 1)}%, "
        f"because the yield is {'above' if v['earnings_yield'] > v['after_tax_cost'] else 'below'} the after-tax cost of debt."
    ))(*_ma_base(p)),
    vary=_vary_tax,
    key_points=["After-tax cost of debt = rate x (1 - t)", "Target earnings yield = target net income / purchase price",
                "Accretive if earnings yield > after-tax cost of debt"],
    misconceptions=["MA_FOREGONE_NO_TAX"],
    target_seconds=150,
)


def _gw(p: Params) -> float:
    return p["P"] - (p["B"] + p["W"] - p["W"] * p["t"])


MA_GOODWILL = Template(
    id="ma_goodwill", skill="ma", difficulty=3, kind="numeric",
    title="Goodwill with a write-up and DTL",
    text=lambda p: (f"An acquirer buys 100% of a target's stock for {money(p['P'])}mm. The target's book equity is "
                    f"{money(p['B'])}mm, and its PP&E is written up by {money(p['W'])}mm. It's a stock deal, so the "
                    f"write-up isn't tax-deductible; tax rate is {pct(p['t'])}. How much goodwill is created?"),
    gen=lambda r: {"P": float(r.choice([1000, 1500, 2000])), "B": float(r.choice([400, 600, 800])),
                   "W": float(r.choice([100, 200])), "t": r.choice(TAXES)},
    solve=lambda p: {"goodwill": _a(_gw(p)), "dtl": _a(p["W"] * p["t"])},
    labels=[Label("goodwill", "Goodwill ($mm)", "$"), Label("dtl", "Deferred tax liability ($mm)", "$", required=False)],
    traps={"MA_GOODWILL_BOOK": lambda p: [{"goodwill": p["P"] - p["B"]}],
           "MA_GOODWILL_NO_DTL": lambda p: [{"goodwill": p["P"] - p["B"] - p["W"]}]},
    explain=lambda p, v: (
        f"Identifiable net assets = book equity {money(p['B'])} + write-up {money(p['W'])} - DTL ({money(p['W'])} x "
        f"{pct(p['t'])} = {money(v['dtl'])}) = {money(p['B'] + p['W'] - v['dtl'])}mm. Goodwill = {money(p['P'])} - "
        f"{money(p['B'] + p['W'] - v['dtl'])} = {money(v['goodwill'])}mm."
    ),
    vary=_vary_tax,
    key_points=["Goodwill = price - fair value of identifiable net assets", "The write-up raises net assets",
                "A DTL = write-up x tax rate lowers net assets"],
    misconceptions=["MA_GOODWILL_BOOK", "MA_GOODWILL_NO_DTL"],
    target_seconds=90,
)


# =========================================================================== LBO
def _lbo_gen(r: random.Random) -> Params:
    E0 = float(r.choice([50, 100]))
    m = float(r.choice([8, 10]))
    L = float(r.choice([4, 5, 6]))
    grow = r.choice([1.3, 1.5, 1.6, 2.0])
    pay = r.choice([0.2, 0.3, 0.4, 0.5])
    return {"E0": E0, "m": m, "L": L, "E5": round(E0 * grow, 2), "Dp": round(L * E0 * pay, 2), "n": 5.0,
            "t": r.choice(TAXES), "bp": float(r.choice([100, 200]))}


def _lbo_vals(p: Params, paydown: float | None = None) -> Values:
    entry_ev = p["E0"] * p["m"]
    debt = p["L"] * p["E0"]
    eq_in = entry_ev - debt
    exit_ev = p["E5"] * p["m"]
    Dp = p["Dp"] if paydown is None else paydown
    eq_out = exit_ev - (debt - Dp)
    moic = eq_out / eq_in
    return {"equity_in": _a(eq_in), "equity_out": _a(eq_out), "moic": _a(moic),
            "irr": _a((moic ** (1 / p["n"]) - 1) * 100)}


def _lbo_text(p: Params) -> str:
    return (f"A sponsor buys a company with {money(p['E0'])}mm of EBITDA at {num(p['m'])}x, funded with "
            f"{num(p['L'])}x EBITDA of debt and the rest equity. Over {num(p['n'])} years EBITDA grows to "
            f"{money(p['E5'])}mm, the company pays down {money(p['Dp'])}mm of debt, and the sponsor exits at the same "
            f"{num(p['m'])}x multiple. Ignore fees.")


LBO_PAPER = Template(
    id="lbo_paper", skill="lbo", difficulty=2, kind="numeric",
    title="Paper LBO",
    text=lambda p: _lbo_text(p) + " What are the MOIC and the approximate IRR?",
    gen=_lbo_gen,
    solve=lambda p: _lbo_vals(p),
    labels=[Label("moic", "MOIC (x)", "x", tol_abs=0.06, tol_rel=0),
            Label("irr", "IRR (%)", "%", tol_abs=1.5, tol_rel=0),
            Label("equity_in", "Sponsor equity at entry ($mm)", "$", required=False),
            Label("equity_out", "Sponsor equity at exit ($mm)", "$", required=False)],
    traps={
        "LBO_NO_PAYDOWN": lambda p: [_lbo_vals(p, paydown=0.0)],
        "LBO_MOIC_ON_EV": lambda p: [(lambda mo: {"moic": _a(mo), "irr": _a((mo ** (1 / p["n"]) - 1) * 100)})(p["E5"] / p["E0"])],
        "LBO_IRR_SIMPLE": lambda p: [{"irr": _a((_lbo_vals(p)["moic"] - 1) / p["n"] * 100)}],
    },
    explain=lambda p, v: (
        f"Entry EV = {num(p['m'])}x x {money(p['E0'])} = {money(p['E0'] * p['m'])}mm; debt = {num(p['L'])}x = "
        f"{money(p['L'] * p['E0'])}mm, so equity in = {money(v['equity_in'])}mm. Exit EV = {num(p['m'])}x x "
        f"{money(p['E5'])} = {money(p['E5'] * p['m'])}mm; remaining debt = {money(p['L'] * p['E0'])} - {money(p['Dp'])} = "
        f"{money(p['L'] * p['E0'] - p['Dp'])}mm, so equity out = {money(v['equity_out'])}mm. MOIC = "
        f"{num(v['moic'])}x; IRR = MOIC^(1/{num(p['n'])}) - 1 = about {num(v['irr'], 1)}%."
    ),
    key_points=["Equity in = entry EV - debt", "Equity out = exit EV - remaining debt (after paydown)",
                "MOIC = equity out / equity in", "IRR compounds: MOIC^(1/n) - 1"],
    misconceptions=["LBO_NO_PAYDOWN", "LBO_MOIC_ON_EV", "LBO_IRR_SIMPLE"],
    target_seconds=180,
)

_IRR_COMBOS = [(2.0, 5.0), (3.0, 5.0), (2.0, 3.0), (2.5, 5.0), (3.0, 3.0), (4.0, 5.0), (1.5, 3.0)]

LBO_IRR_RULE = Template(
    id="lbo_irr_rule", skill="lbo", difficulty=1, kind="numeric",
    title="IRR mental math",
    text=lambda p: (f"You invest {money(p['X'])}mm and get back {money(p['X'] * p['M'])}mm after {num(p['n'])} years, "
                    f"with no interim cash flows. Roughly what's the IRR?"),
    gen=lambda r: (lambda c: {"X": float(r.choice([100, 200, 500])), "M": c[0], "n": c[1]})(r.choice(_IRR_COMBOS)),
    solve=lambda p: {"irr": _a((p["M"] ** (1 / p["n"]) - 1) * 100), "moic": p["M"]},
    labels=[Label("irr", "IRR (%)", "%", tol_abs=2.0, tol_rel=0),
            Label("moic", "MOIC (x)", "x", required=False, tol_abs=0.05, tol_rel=0)],
    traps={"LBO_IRR_SIMPLE": lambda p: [{"irr": _a((p["M"] - 1) / p["n"] * 100)}]},
    explain=lambda p, v: (
        f"MOIC = {num(p['M'])}x over {num(p['n'])} years. IRR = {num(p['M'])}^(1/{num(p['n'])}) - 1 = about "
        f"{num(v['irr'], 1)}%. Anchors: 2x in 5 years is about 15%, 3x in 5 about 25%, 2x in 3 about 26%."
    ),
    key_points=["MOIC = proceeds / investment", "IRR compounds, so it isn't MOIC divided by years",
                "Use rules of thumb (2x in 5 years is about 15%)"],
    misconceptions=["LBO_IRR_SIMPLE"],
    target_seconds=30,
)


# =========================================================================== MARKETS / RATES
def _mw_gen(r: random.Random) -> Params:
    ev_ = r.choice([0.6, 0.7, 0.8])
    return {"we": ev_, "w0": r.choice([0.08, 0.09, 0.10]), "b": r.choice([0.8, 1.0, 1.2]),
            "t": r.choice(TAXES), "g": r.choice([0.02, 0.03]), "bp": 100.0}


def _mw_vals(p: Params, eq_leg: bool = True, tax: bool = True) -> Values:
    d = p["bp"] / 10000
    wd = 1 - p["we"]
    w1 = p["w0"] + (p["we"] * p["b"] * d if eq_leg else 0) + wd * d * ((1 - p["t"]) if tax else 1)
    return {"wacc_new": _a(w1 * 100), "tv_change": _a(((p["w0"] - p["g"]) / (w1 - p["g"]) - 1) * 100)}


MKT_RATES_WACC = Template(
    id="mkt_rates_wacc", skill="markets", difficulty=3, kind="numeric",
    title="Rates shock: WACC and terminal value",
    text=lambda p: (f"A company's WACC is {pct(p['w0'])}, with a capital structure of {pct(p['we'], 0)} equity and "
                    f"{pct(1 - p['we'], 0)} debt, a levered beta of {num(p['b'])} and a {pct(p['t'])} tax rate. The "
                    f"10-year Treasury rises {num(p['bp'], 0)}bp, and the company's pre-tax cost of debt rises by the "
                    f"same amount. Holding the equity risk premium constant, what's the new WACC? Roughly how much "
                    f"does a perpetuity-growth terminal value with {pct(p['g'])} growth change?"),
    gen=_mw_gen,
    solve=lambda p: _mw_vals(p),
    labels=[Label("wacc_new", "New WACC (%)", "%", tol_abs=0.1, tol_rel=0),
            Label("tv_change", "Change in terminal value (%)", "%", required=False, tol_abs=0.8, tol_rel=0)],
    traps={"MKT_RATES_DEBT_ONLY": lambda p: [_mw_vals(p, eq_leg=False)],
           "MKT_RATES_PRETAX": lambda p: [_mw_vals(p, tax=False)],
           "MKT_RATES_NO_EFFECT": lambda p: [{"wacc_new": _a(p["w0"] * 100), "tv_change": 0.0}]},
    explain=lambda p, v: (
        f"Cost of equity rises by beta x 100bp = {num(p['b'] * 100, 0)}bp (CAPM with a constant ERP). After-tax cost of "
        f"debt rises 100bp x (1 - {pct(p['t'])}) = {num(100 * (1 - p['t']), 0)}bp. WACC rises "
        f"{pct(p['we'], 0)} x {num(p['b'] * 100, 0)}bp + {pct(1 - p['we'], 0)} x {num(100 * (1 - p['t']), 0)}bp, "
        f"to {num(v['wacc_new'])}%. TV scales with 1 / (WACC - g): ({pct(p['w0'])} - {pct(p['g'])}) / "
        f"({num(v['wacc_new'])}% - {pct(p['g'])}) - 1 = {num(v['tv_change'], 1)}%."
    ),
    key_points=["Higher rf raises the cost of equity via CAPM (beta x change)",
                "Cost of debt rises; the after-tax change is smaller", "Both legs feed WACC by their weights",
                "TV falls more than proportionally because the denominator is WACC - g"],
    misconceptions=["MKT_RATES_DEBT_ONLY", "MKT_RATES_PRETAX", "MKT_RATES_NO_EFFECT"],
    target_seconds=150,
)


def _rl_vals(p: Params, tax: bool = True, effect: bool = True) -> Values:
    debt = p["L"] * p["E0"]
    lost = debt * p["bp"] / 10000 * p["n"] * ((1 - p["t"]) if tax else 1) if effect else 0.0
    v = _lbo_vals(p, paydown=p["Dp"] - lost)
    return {"lost_paydown": _a(lost), "irr_new": v["irr"], "moic_new": v["moic"]}


MKT_RATES_LBO = Template(
    id="mkt_rates_lbo", skill="markets", difficulty=3, kind="numeric",
    title="Rates shock: LBO returns",
    text=lambda p: (_lbo_text(p) + f" Base case: MOIC {num(_lbo_vals(p)['moic'])}x, IRR about "
                    f"{num(_lbo_vals(p)['irr'], 1)}%. Now the debt is floating, and rates are {num(p['bp'], 0)}bp higher "
                    f"for the whole hold. Assume extra interest is charged on the entry debt balance, is tax-deductible at "
                    f"{pct(p['t'])}, and reduces debt paydown one-for-one. What's the new IRR?"),
    gen=_lbo_gen,
    solve=lambda p: _rl_vals(p),
    labels=[Label("irr_new", "New IRR (%)", "%", tol_abs=1.0, tol_rel=0),
            Label("lost_paydown", "Lost debt paydown ($mm)", "$", required=False),
            Label("moic_new", "New MOIC (x)", "x", required=False, tol_abs=0.06, tol_rel=0)],
    traps={"MKT_RATES_PRETAX": lambda p: [_rl_vals(p, tax=False)],
           "MKT_RATES_NO_EFFECT": lambda p: [_rl_vals(p, effect=False)]},
    explain=lambda p, v: (
        f"Extra interest = {money(p['L'] * p['E0'])}mm x {num(p['bp'], 0)}bp x {num(p['n'])} years x (1 - {pct(p['t'])}) = "
        f"{money(v['lost_paydown'])}mm of paydown lost. Remaining debt at exit rises by that amount, equity out falls to "
        f"{money(_lbo_vals(p, paydown=p['Dp'] - v['lost_paydown'])['equity_out'])}mm, MOIC {num(v['moic_new'])}x, IRR "
        f"about {num(v['irr_new'], 1)}%."
    ),
    key_points=["Extra after-tax interest = debt x change in rate x (1 - t) per year",
                "It cuts paydown, so exit debt is higher", "Lower exit equity means lower MOIC and IRR"],
    misconceptions=["MKT_RATES_PRETAX", "MKT_RATES_NO_EFFECT"],
    target_seconds=180,
)


MKT_RATES_MA = Template(
    id="mkt_rates_ma", skill="markets", difficulty=3, kind="numeric",
    title="Rates shock: debt-funded M&A",
    text=lambda p: (_ma_text_common(p) + f" The deal is funded 100% with new debt. At a {pct(p['rd'])} rate it is "
                    f"{num(abs(_ma_debt_vals(p)['accretion']), 1)}% "
                    f"{'accretive' if _ma_debt_vals(p)['accretion'] > 0 else 'dilutive'}. Tax rate is {pct(p['t'])}. If "
                    f"financing costs rise 200bp before signing, what's the new accretion or dilution?"),
    gen=_ma_gen,
    solve=lambda p: {"accretion_new": _ma_debt_vals(p, rd=p["rd"] + 0.02)["accretion"]},
    labels=[Label("accretion_new", "New EPS accretion (+) / dilution (-) (%)", "%", tol_abs=0.3, tol_rel=0.02)],
    traps={"MKT_RATES_PRETAX": lambda p: [{"accretion_new": _ma_debt_vals(p, rd=p["rd"] + 0.02, after_tax=False)["accretion"]}],
           "MKT_RATES_NO_EFFECT": lambda p: [{"accretion_new": _ma_debt_vals(p)["accretion"]}]},
    explain=lambda p, v: (lambda NIa, NIt, price, eps: (
        f"New rate {pct(p['rd'] + 0.02)}, so the after-tax cost is {pct((p['rd'] + 0.02) * (1 - p['t']), 2)}. Extra after-tax "
        f"interest = {money(price)} x 2% x (1 - {pct(p['t'])}) = {money(round(price * 0.02 * (1 - p['t']), 2))}mm, which lowers "
        f"pro forma EPS. New result: {num(abs(v['accretion_new']), 1)}% "
        f"{'accretive' if v['accretion_new'] > 0 else 'dilutive'}."
    ))(*_ma_base(p)),
    key_points=["Higher rate raises the after-tax cost of debt", "Extra interest x (1 - t) lowers pro forma net income",
                "Compare against the target's earnings yield"],
    misconceptions=["MKT_RATES_PRETAX", "MKT_RATES_NO_EFFECT"],
    target_seconds=150,
)


# =========================================================================== CONCEPTUAL
def _concept(tid: str, skill: str, diff: int, title: str, question: str, key_points: list[str],
             mis: list[str], model_answer: str, secs: int = 90) -> Template:
    return Template(
        id=tid, skill=skill, difficulty=diff, kind="conceptual", title=title,
        text=lambda p, q=question: q, key_points=key_points, misconceptions=mis,
        explain=lambda p, v, a=model_answer: a, target_seconds=secs,
    )


CONCEPTUAL = [
    _concept("c_acc_link", "accounting", 1, "How the statements link",
             "Walk me through how the three financial statements link together.",
             ["Net income from the income statement is the top line of the cash flow statement",
              "The CFS adjusts for non-cash items and working capital, then adds investing and financing flows",
              "Ending cash from the CFS becomes cash on the balance sheet",
              "Net income (less dividends) flows into retained earnings, so the balance sheet balances"],
             ["ACC_NONCASH_AS_CASH"],
             "Net income at the bottom of the income statement starts the cash flow statement. The CFS adds back "
             "non-cash charges like D&A and SBC, adjusts for changes in working capital, then adds investing (capex) "
             "and financing (debt, equity, dividends) flows to get the net change in cash. That change updates cash "
             "on the balance sheet. Net income less dividends flows into retained earnings in equity, and PP&E, "
             "working capital and debt lines move with the CFS items, so the balance sheet balances."),
    _concept("c_acc_addback", "accounting", 1, "Why add back D&A",
             "Why do we add back depreciation on the cash flow statement?",
             ["Depreciation is a non-cash expense", "It reduced net income, so it is reversed",
              "The cash left when the asset was bought (capex)", "Its tax deductibility is a real cash saving"],
             ["ACC_NONCASH_AS_CASH"],
             "Depreciation lowers net income but no cash leaves the business that year. The cash went out earlier, "
             "as capex. Since the CFS starts from net income, we add depreciation back. The only real cash effect is "
             "the tax saving, because depreciation is deductible."),
    _concept("c_ev_cash", "ev", 1, "Why subtract cash in EV",
             "Why do we subtract cash when calculating enterprise value?",
             ["EV measures the value of the core operations to all capital providers", "Cash is a non-operating asset",
              "An acquirer effectively gets the cash back, which offsets the price",
              "It keeps EV consistent with EBITDA, which excludes interest income"],
             ["EV_ADD_CASH"],
             "Enterprise value is the value of the operating business to all capital providers. Cash isn't needed "
             "to run the operations, and an acquirer could use the target's cash to offset what it pays, so it is "
             "subtracted. It also keeps EV consistent with EBITDA, which excludes interest income on that cash."),
    _concept("c_ev_multiples", "ev", 2, "Matching multiples",
             "Why is EV/EBITDA a valid multiple but EV/Net Income isn't?",
             ["EBITDA is available to all capital providers (pre-interest)",
              "Net income is after interest, so it belongs to equity holders only",
              "Numerator and denominator must refer to the same capital providers",
              "Equity value pairs with net income or EPS (P/E)"],
             ["EV_MULTIPLE_MISMATCH"],
             "A multiple must match claim to metric. EV is the value to all capital providers, so it pairs with "
             "pre-interest metrics like EBITDA or EBIT. Net income is after interest has been paid to lenders, so it "
             "belongs only to equity holders and pairs with equity value, as in P/E. EV/Net Income mixes the two."),
    _concept("c_dcf_walk", "dcf", 1, "Walk me through a DCF",
             "Walk me through a DCF.",
             ["Project unlevered free cash flows for about 5-10 years", "Calculate the discount rate (WACC)",
              "Calculate a terminal value (perpetuity growth or exit multiple)",
              "Discount the cash flows and TV to present value to get enterprise value",
              "Bridge from EV to equity value and per-share value"],
             ["DCF_LEVERED"],
             "Project the company's unlevered free cash flows for 5-10 years. Estimate WACC as the discount rate. "
             "Compute a terminal value, either with perpetuity growth or an exit multiple. Discount the cash flows "
             "and the terminal value back to today and sum them to get enterprise value. Then subtract net debt and "
             "other claims to get equity value, and divide by diluted shares for a per-share value."),
    _concept("c_dcf_wacc", "dcf", 2, "WACC down, value?",
             "If a company's WACC goes down, what happens to its DCF value, and why?",
             ["Value goes up", "Future cash flows are discounted less", "Terminal value is most sensitive",
              "The TV denominator WACC - g shrinks"],
             ["DCF_TV_PLUS_G"],
             "Value goes up. A lower WACC discounts future cash flows less, so their present value rises. The terminal "
             "value is especially sensitive, because it divides by WACC - g, a small number that shrinks further, and "
             "TV is usually most of a DCF's value."),
    _concept("c_ma_pe", "ma", 2, "Quick accretion test",
             "In an all-stock deal, how can you tell quickly whether it's accretive or dilutive?",
             ["Compare the acquirer's P/E with the P/E paid for the target",
              "Acquirer P/E higher means accretive", "Acquirer P/E lower means dilutive",
              "Caveats: synergies, fees and purchase accounting change the answer"],
             ["MA_PE_RULE"],
             "Compare the acquirer's P/E with the P/E it is paying for the target (purchase price / target net income). "
             "If the acquirer's P/E is higher, it is using expensive stock to buy cheaper earnings, so the deal is "
             "accretive. If it is lower, the deal is dilutive. Synergies, fees and new D&A from write-ups can change "
             "the answer."),
    _concept("c_lbo_leverage", "lbo", 2, "Why leverage boosts returns",
             "Why does using more leverage increase returns in an LBO?",
             ["The sponsor contributes a smaller equity check", "EV gains accrue entirely to equity",
              "Debt paydown builds equity value", "Interest is tax-deductible",
              "Trade-off: more risk, interest burden and covenant pressure"],
             ["LBO_NO_LEVER_LOGIC"],
             "More debt means a smaller equity check for the same company. Any increase in EV goes entirely to equity "
             "holders, and cash flow that repays debt moves value from lenders to the sponsor. Interest is also "
             "tax-deductible. The trade-off is risk: higher interest burdens and covenants make distress more likely if "
             "performance slips."),
    _concept("c_lbo_candidate", "lbo", 1, "Good LBO candidate",
             "What makes a company a good LBO candidate?",
             ["Stable, predictable cash flows to service debt", "Low capex and working capital needs",
              "A strong market position or moat", "Room to improve operations or cut costs",
              "A reasonable entry valuation and clear exit options"],
             [],
             "Stable, predictable cash flows that can service debt; low capex and working capital needs; a strong market "
             "position; room for operational improvement; an unlevered or under-levered balance sheet; a reasonable "
             "purchase price; and a clear path to exit, through a sale to a strategic buyer, a secondary buyout or an IPO."),
    _concept("c_mkt_rates_deals", "markets", 2, "Rates and deal activity",
             "How do higher interest rates affect M&A and LBO activity?",
             ["Debt is more expensive, so sponsors can borrow less and IRRs fall",
              "Sponsors can pay less, so purchase prices and multiples compress",
              "Higher discount rates lower valuations across DCFs",
              "Strategics may shift to stock consideration; volumes fall as bid-ask spreads widen"],
             ["MKT_RATES_NO_EFFECT"],
             "Higher rates make debt more expensive, so sponsors support less leverage and earn lower IRRs at a given price. "
             "That caps what they can pay. Higher discount rates also lower DCF values and trading multiples. Buyers and "
             "sellers disagree more on price, so volumes fall. Strategic acquirers may lean on stock, or cash on hand, rather than debt."),
    _concept("c_mkt_duration", "markets", 3, "Growth stocks and rates",
             "Why do high-growth tech stocks often fall more than value stocks when rates rise?",
             ["Growth companies' value sits further in the future (terminal value)",
              "Higher discount rates cut the present value of distant cash flows the most",
              "This is equity 'duration': long-duration assets are more rate-sensitive",
              "Value stocks have more near-term cash flows, so they are less affected"],
             ["MKT_DURATION"],
             "A high-growth company earns most of its cash far in the future, so most of its value sits in the out-years "
             "and terminal value. A higher discount rate compounds over more years for distant cash, cutting its present "
             "value the most. Like long-dated bonds, these long-duration equities are more rate-sensitive than value "
             "stocks with near-term cash flows."),
]

NUMERIC = [ACC_DA, ACC_WRITEDOWN, ACC_SBC, ACC_CAPEX, ACC_AR, ACC_DEBT, EV_BRIDGE, EV_IMPLIED_PRICE,
           EV_DEBT_CASH, DCF_UFCF, DCF_TV, DCF_WACC, DCF_CAPM, MA_STOCK, MA_CASH, MA_DEBT, MA_GOODWILL,
           LBO_PAPER, LBO_IRR_RULE, MKT_RATES_WACC, MKT_RATES_LBO, MKT_RATES_MA]

TEMPLATES: dict[str, Template] = {t.id: t for t in NUMERIC + CONCEPTUAL}

SKILLS = {
    "accounting": "Accounting",
    "ev": "EV & equity value",
    "dcf": "DCF & WACC",
    "ma": "M&A",
    "lbo": "LBO",
    "markets": "Markets & rates",
}

SPECIALIST_FOR_SKILL = {
    "accounting": "accounting", "ev": "valuation", "dcf": "valuation",
    "ma": "deals", "lbo": "deals", "markets": "markets",
}


# --------------------------------------------------------------------------- instantiation
def build(template: Template, params: Params) -> Question:
    values = template.solve(params) if template.kind == "numeric" else {}
    sigs: dict[str, list[Values]] = {}
    label_map = {l.key: l for l in template.labels}
    for mid, fn in template.traps.items():
        kept = []
        for sig in fn(params):
            sig = {k: _a(v) for k, v in sig.items() if k in label_map}
            # A signature only counts if at least one of its numbers differs from the truth;
            # otherwise it can't be told apart from a correct answer.
            if any(not label_map[k].close(v, values[k]) for k, v in sig.items()):
                kept.append(sig)
        if kept:
            sigs[mid] = kept
    return Question(
        template_id=template.id, skill=template.skill, difficulty=template.difficulty,
        kind=template.kind, title=template.title, text=template.text(params), params=params,
        values=values, labels=template.labels, signatures=sigs, key_points=template.key_points,
        misconceptions=template.misconceptions, solution=template.explain(params, values),
        target_seconds=template.target_seconds,
    )


def instantiate(template_id: str, rng: random.Random) -> Question:
    t = TEMPLATES[template_id]
    return build(t, t.gen(rng))


def from_state(state: dict) -> Question:
    return build(TEMPLATES[state["template_id"]], state["params"])


def variation(q: Question, rng: random.Random) -> Question | None:
    """A 'what if' follow-up: same template, one parameter changed, recomputed by the calculator."""
    t = TEMPLATES[q.template_id]
    if t.vary is None:
        return None
    out = t.vary(q.params, rng)
    if out is None:
        return None
    new_params, prompt = out
    nq = build(t, new_params)
    nq.text = prompt
    nq.title = f"{t.title}: what-if"
    return nq


# --------------------------------------------------------------------------- deterministic checking
@dataclass
class LabelCheck:
    label: str
    name: str
    stated: float | None
    status: str  # correct | wrong | missing
    expected: float | None
    matches: list[str]  # misconception ids whose signature predicts the stated number
    sign_flip: bool = False
    slip: bool = False  # looks like a pure arithmetic slip (one digit off, transposed, decimal shift)

    def to_dict(self) -> dict:
        return self.__dict__.copy()


def looks_like_slip(stated: float, truth: float) -> bool:
    """True if the stated number is the truth with a classic arithmetic slip: one digit wrong,
    two adjacent digits swapped, or the decimal point shifted."""
    if truth == 0 or stated == 0 or (stated < 0) != (truth < 0):
        return False
    a, b = abs(stated), abs(truth)
    for k in (10.0, 0.1):
        if abs(a - b * k) <= 0.005 * b * k:
            return True
    sa, sb = f"{a:.2f}", f"{b:.2f}"
    if len(sa) != len(sb):
        return False
    diff = [i for i, (x, y) in enumerate(zip(sa, sb)) if x != y]
    if len(diff) == 1 and sa[diff[0]] != ".":
        return True
    if len(diff) == 2 and diff[1] == diff[0] + 1 and sa[diff[0]] == sb[diff[1]] and sa[diff[1]] == sb[diff[0]]:
        return True
    return False


def check_numbers(q: Question, stated: dict[str, float]) -> list[LabelCheck]:
    """Compare stated numbers to the answer key and to every misconception signature."""
    out: list[LabelCheck] = []
    for lab in q.labels:
        truth = q.values.get(lab.key)
        if lab.key not in stated:
            out.append(LabelCheck(lab.key, lab.name, None, "missing", truth, []))
            continue
        s = stated[lab.key]
        if truth is not None and lab.close(s, truth):
            out.append(LabelCheck(lab.key, lab.name, s, "correct", truth, []))
            continue
        matches = [mid for mid, sigs in q.signatures.items()
                   if any(lab.key in sig and lab.close(s, sig[lab.key]) for sig in sigs)]
        flip = lab.is_signed and truth is not None and abs(truth) > 1e-9 and lab.close(-s, truth)
        if flip and not matches and q.skill == "accounting":
            matches = ["ACC_SIGN_FLIP"]
        slip = not matches and not flip and truth is not None and looks_like_slip(s, truth)
        out.append(LabelCheck(lab.key, lab.name, s, "wrong", truth, matches, flip, slip))
    return out
