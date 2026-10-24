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
    subskill: str = ""              # e.g. "accounting.noncash"; set from META below
    groups: list[str] = field(default_factory=list)  # empty = core question for every group
    specialist: str | None = None   # override which specialist grades it


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
    subskill: str = ""

    def to_public(self) -> dict:
        """What the browser may see before the answer is revealed: no answer key."""
        return {
            "template_id": self.template_id,
            "skill": self.skill,
            "difficulty": self.difficulty,
            "level": LEVELS.get(self.difficulty, ""),
            "subskill": self.subskill,
            "subskill_name": SUBSKILLS.get(self.subskill, ("", ""))[1],
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

# =========================================================================== BASIC-LEVEL NUMERIC (coffee-chat / first-round level)
def _num(tid, skill, title, text, gen, solve, labels, traps, explain, key_points, secs=45, vary=None) -> Template:
    return Template(id=tid, skill=skill, difficulty=1, kind="numeric", title=title, text=text, gen=gen, solve=solve,
                    labels=labels, traps=traps, explain=explain, key_points=key_points,
                    misconceptions=list(traps.keys()), target_seconds=secs, vary=vary)


ACC_REV_CASH = _num(
    "acc_rev_cash", "accounting", "3-statement walk: a cash sale",
    lambda p: f"A company sells {money(p['X'])} of product for cash, with no associated costs. Tax rate is {pct(p['t'])}. Walk me through the three statements.",
    lambda r: {"X": float(r.choice(AMTS)), "t": r.choice(TAXES)},
    lambda p: {"ni": _a(p["X"] * (1 - p["t"])), "cash": _a(p["X"] * (1 - p["t"]))},
    [Label("ni", "Change in net income", "$"), Label("cash", "Change in cash", "$")],
    {"ACC_NO_TAX": lambda p: [{"ni": p["X"], "cash": p["X"]}]},
    lambda p, v: (f"Revenue up {money(p['X'])}, taxes up {money(p['X'] * p['t'])}, so net income is {chg(v['ni'])}. The CFS starts "
                  f"with that net income and there are no adjustments, so cash is {chg(v['cash'])}. On the balance sheet cash and "
                  f"retained earnings both rise {money(v['ni'])}."),
    ["Net income rises by the after-tax amount", "Cash rises by the same amount (it was a cash sale)",
     "Cash and retained earnings both rise, so the balance sheet balances"],
    vary=_vary_tax,
)

ACC_OPEX_CASH = _num(
    "acc_opex_cash", "accounting", "3-statement walk: hiring an employee",
    lambda p: f"A company hires an employee and pays {money(p['X'])} of salary in cash this year. Tax rate is {pct(p['t'])}. Walk me through the three statements.",
    lambda r: {"X": float(r.choice([50, 100, 200])), "t": r.choice(TAXES)},
    lambda p: {"ni": _a(-p["X"] * (1 - p["t"])), "cash": _a(-p["X"] * (1 - p["t"]))},
    [Label("ni", "Change in net income", "$"), Label("cash", "Change in cash", "$")],
    {"ACC_NO_TAX": lambda p: [{"ni": -p["X"], "cash": -p["X"]}]},
    lambda p, v: (f"Operating expenses up {money(p['X'])}; taxes fall {money(p['X'] * p['t'])}, so net income is {chg(v['ni'])}. "
                  f"It's a cash expense, so nothing to add back: cash is {chg(v['cash'])}. Cash and retained earnings both fall "
                  f"{money(abs(v['ni']))}."),
    ["Pre-tax income falls by the salary", "Taxes fall, so net income falls by the after-tax amount",
     "No add-back because salary is a cash expense", "Cash and retained earnings fall equally"],
    vary=_vary_tax,
)

ACC_INVENTORY = _num(
    "acc_inventory", "accounting", "3-statement walk: buying inventory",
    lambda p: f"A company buys {money(p['X'])} of inventory with cash. It hasn't sold any of it yet. Walk me through the three statements.",
    lambda r: {"X": float(r.choice([50, 100, 200])), "t": r.choice(TAXES)},
    lambda p: {"ni": 0.0, "cash": -p["X"], "inventory": p["X"]},
    [Label("ni", "Change in net income", "$"), Label("cash", "Change in cash", "$"),
     Label("inventory", "Change in inventory", "$", required=False)],
    {"ACC_CAPEX_EXPENSED": lambda p: [{"ni": _a(-p["X"] * (1 - p["t"]))}, {"ni": -p["X"]}]},
    lambda p, v: (f"No income statement effect: inventory only hits COGS when it's sold. On the CFS the {money(p['X'])} increase in "
                  f"inventory is a use of cash in working capital, so cash is {chg(v['cash'])}. Balance sheet: inventory up "
                  f"{money(p['X'])}, cash down {money(p['X'])}; total assets unchanged."),
    ["No income statement impact until the inventory is sold", "The inventory increase is a use of cash in working capital",
     "Cash down and inventory up by the same amount"],
)

ACC_AP = Template(
    id="acc_ap", skill="accounting", difficulty=2, kind="numeric", title="3-statement walk: an unpaid expense",
    text=lambda p: (f"A company records {money(p['X'])} of operating expenses but hasn't paid the supplier yet. "
                    f"Tax rate is {pct(p['t'])}. Walk me through the three statements."),
    gen=lambda r: {"X": float(r.choice(AMTS)), "t": r.choice(TAXES)},
    solve=lambda p: {"ni": _a(-p["X"] * (1 - p["t"])), "cash": _a(p["X"] * p["t"]), "ap": p["X"]},
    labels=[Label("ni", "Change in net income", "$"), Label("cash", "Change in cash", "$"),
            Label("ap", "Change in accounts payable", "$", required=False)],
    traps={"ACC_AP_IGNORED": lambda p: [{"cash": _a(-p["X"] * (1 - p["t"]))}, {"cash": -p["X"]}],
           "ACC_NO_TAX": lambda p: [{"ni": -p["X"], "cash": 0.0}]},
    explain=lambda p, v: (f"Net income falls {money(abs(v['ni']))} after the tax saving. On the CFS, start from that and add back the "
                          f"{money(p['X'])} increase in accounts payable (cash hasn't gone out yet), so cash is {chg(v['cash'])}, which "
                          f"is the tax saving. Balance sheet: cash up {money(v['cash'])}; AP up {money(p['X'])}, retained earnings down "
                          f"{money(abs(v['ni']))}."),
    key_points=["Net income falls by the after-tax expense", "The AP increase is added back on the CFS",
                "Cash rises by the tax saving", "AP up, retained earnings down"],
    misconceptions=["ACC_AP_IGNORED", "ACC_NO_TAX"], vary=_vary_tax,
)

ACC_DEFREV = Template(
    id="acc_defrev", skill="accounting", difficulty=3, kind="numeric", title="3-statement walk: customer prepays",
    text=lambda p: (f"A software customer pays {money(p['X'])} in cash today for a service that will be delivered next year. "
                    f"Walk me through the three statements today."),
    gen=lambda r: {"X": float(r.choice([50, 100, 120, 200]))},
    solve=lambda p: {"ni": 0.0, "cash": p["X"], "deferred_revenue": p["X"]},
    labels=[Label("ni", "Change in net income", "$"), Label("cash", "Change in cash", "$"),
            Label("deferred_revenue", "Change in deferred revenue", "$", required=False)],
    traps={"ACC_DEFREV_AS_REVENUE": lambda p: [{"ni": _a(p["X"] * 0.75)}, {"ni": _a(p["X"] * 0.8)}, {"ni": _a(p["X"] * 0.7)},
                                               {"ni": _a(p["X"] * 0.6)}, {"ni": p["X"]}]},
    explain=lambda p, v: (f"No revenue yet: the service hasn't been delivered, so net income is unchanged. On the CFS, the {money(p['X'])} "
                          f"increase in deferred revenue (a liability) is a source of cash, so cash is up {money(p['X'])}. Balance sheet: "
                          f"cash up {money(p['X'])}, deferred revenue up {money(p['X'])}."),
    key_points=["No revenue until the service is delivered", "Deferred revenue is a liability",
                "The deferred revenue increase is a source of cash on the CFS"],
    misconceptions=["ACC_DEFREV_AS_REVENUE"], target_seconds=60,
)


def _tsm(p: Params) -> float:
    return p["B"] + p["N"] - p["N"] * p["K"] / p["S"]


def _tsm_gen(r: random.Random) -> Params:
    S = float(r.choice([20, 25, 40, 50]))
    return {"S": S, "B": float(r.choice([50, 100, 200])), "N": float(r.choice([2, 4, 5, 10])),
            "K": float(r.choice([k for k in (10, 15, 20, 30) if k < S]))}


EV_TSM = Template(
    id="ev_tsm", skill="ev", difficulty=2, kind="numeric", title="Diluted shares (treasury stock method)",
    text=lambda p: (f"A company's share price is {money(p['S'])}. It has {num(p['B'])} million basic shares and {num(p['N'])} million "
                    f"options with an exercise price of {money(p['K'])}. What's the diluted share count, and its equity value?"),
    gen=_tsm_gen,
    solve=lambda p: {"diluted_shares": _a(_tsm(p)), "equity_value": _a(_tsm(p) * p["S"])},
    labels=[Label("diluted_shares", "Diluted shares (mm)", "mm"),
            Label("equity_value", "Equity value ($mm)", "$", required=False)],
    traps={"EV_TSM_BASIC": lambda p: [{"diluted_shares": p["B"], "equity_value": p["B"] * p["S"]}],
           "EV_TSM_ALL_OPTIONS": lambda p: [{"diluted_shares": p["B"] + p["N"], "equity_value": (p["B"] + p["N"]) * p["S"]}]},
    explain=lambda p, v: (f"The options are in the money ({money(p['K'])} strike vs {money(p['S'])} price), so all {num(p['N'])}mm are "
                          f"exercised, raising {money(p['N'] * p['K'])}mm. That buys back {money(p['N'] * p['K'])} / {money(p['S'])} = "
                          f"{num(p['N'] * p['K'] / p['S'])}mm shares. Net new shares {num(p['N'] - p['N'] * p['K'] / p['S'])}mm, so diluted "
                          f"shares = {num(v['diluted_shares'])}mm and equity value = {money(round(v['equity_value'], 2))}mm."),
    key_points=["Only in-the-money options count", "Exercise proceeds are used to buy back shares at the current price",
                "Diluted shares = basic + options - buyback shares"],
    misconceptions=["EV_TSM_BASIC", "EV_TSM_ALL_OPTIONS"], target_seconds=75,
)


def _pv(p: Params) -> float:
    return p["X"] / (1 + p["r"]) ** p["n"]


DCF_PV = _num(
    "dcf_pv", "dcf", "Present value",
    lambda p: f"What's the present value of {money(p['X'])} received {num(p['n'])} years from now, at a {pct(p['r'])} discount rate?",
    lambda r: {"X": float(r.choice([100, 121, 1000])), "r": r.choice([0.05, 0.10]), "n": float(r.choice([2, 3]))},
    lambda p: {"pv": _a(_pv(p))},
    [Label("pv", "Present value", "$", tol_rel=0.015)],
    {"DCF_SIMPLE_DISCOUNT": lambda p: [{"pv": _a(p["X"] / (1 + p["r"] * p["n"]))}]},
    lambda p, v: (f"PV = {money(p['X'])} / (1 + {pct(p['r'])})^{num(p['n'])} = {money(p['X'])} / {num((1 + p['r']) ** p['n'], 4)} = "
                  f"{money(round(v['pv'], 2))}. A dollar later is worth less than a dollar today, and the discount compounds each year."),
    ["Discount compounds: divide by (1 + r)^n", "Money in the future is worth less than money today"],
)

LBO_BASIC = _num(
    "lbo_basic", "lbo", "Simple LBO returns",
    lambda p: (f"A private equity firm buys a company for {money(p['EV'])}mm, using {money(p['D'])}mm of debt and the rest equity. "
               f"Five years later it sells the company for {money(p['EV2'])}mm, with the debt still at {money(p['D'])}mm. "
               f"What's the money-on-money multiple?"),
    lambda r: (lambda ev: {"EV": ev, "D": ev * r.choice([0.5, 0.6]), "EV2": ev * r.choice([1.3, 1.5])})(float(r.choice([500, 1000]))),
    lambda p: {"moic": _a((p["EV2"] - p["D"]) / (p["EV"] - p["D"])), "equity_in": p["EV"] - p["D"], "equity_out": p["EV2"] - p["D"]},
    [Label("moic", "MOIC (x)", "x", tol_abs=0.06, tol_rel=0), Label("equity_in", "Equity in ($mm)", "$", required=False),
     Label("equity_out", "Equity out ($mm)", "$", required=False)],
    {"LBO_MOIC_ON_EV": lambda p: [{"moic": _a(p["EV2"] / p["EV"])}]},
    lambda p, v: (f"Equity in = {money(p['EV'])} - {money(p['D'])} = {money(v['equity_in'])}mm. Equity out = {money(p['EV2'])} - "
                  f"{money(p['D'])} = {money(v['equity_out'])}mm. MOIC = {num(v['moic'])}x, higher than the "
                  f"{num(p['EV2'] / p['EV'])}x rise in the company's value because the debt amplifies the equity return."),
    ["Equity in = purchase price - debt", "Equity out = sale price - debt", "MOIC is on equity, not on the company's value",
     "Leverage makes the equity return bigger than the value increase"],
    secs=60,
)

# =========================================================================== GROUP-SPECIFIC NUMERIC
FIG_PTBV = Template(
    id="fig_ptbv", skill="industry", difficulty=2, kind="numeric", title="Bank valuation: P/TBV",
    text=lambda p: (f"A bank has a market cap of {money(p['M'])}mm, shareholders' equity of {money(p['E'])}mm, and {money(p['G'])}mm "
                    f"of goodwill and intangibles. What's its price-to-tangible-book multiple?"),
    gen=lambda r: {"M": float(r.choice([1200, 1500, 1800])), "E": float(r.choice([1000, 1200])), "G": float(r.choice([200, 300]))},
    solve=lambda p: {"ptbv": _a(p["M"] / (p["E"] - p["G"])), "pbv": _a(p["M"] / p["E"])},
    labels=[Label("ptbv", "P/TBV (x)", "x", tol_abs=0.03, tol_rel=0), Label("pbv", "P/BV (x)", "x", required=False, tol_abs=0.03, tol_rel=0)],
    traps={"FIG_PTBV_NO_GW": lambda p: [{"ptbv": _a(p["M"] / p["E"])}]},
    explain=lambda p, v: (f"Tangible book = {money(p['E'])} - {money(p['G'])} = {money(p['E'] - p['G'])}mm. P/TBV = {money(p['M'])} / "
                          f"{money(p['E'] - p['G'])} = {num(v['ptbv'])}x (P/BV is {num(v['pbv'])}x). Banks are valued on equity metrics "
                          f"because debt and interest are part of the business, not financing."),
    key_points=["Tangible book = equity - goodwill - intangibles", "P/TBV = market cap / tangible book",
                "Banks use equity-value metrics, not EV"],
    misconceptions=["FIG_PTBV_NO_GW", "FIG_USES_EV"], groups=["fig"], target_seconds=60,
)

RE_CAP_RATE = _num(
    "re_cap_rate", "industry", "Property value from a cap rate",
    lambda p: f"An office building produces {money(p['NOI'])}mm of net operating income a year. Comparable buildings trade at a {pct(p['c'])} cap rate. What's it worth?",
    lambda r: {"NOI": float(r.choice([5, 8, 10, 12])), "c": r.choice([0.05, 0.06, 0.08])},
    lambda p: {"value": _a(p["NOI"] / p["c"])},
    [Label("value", "Property value ($mm)", "$")],
    {},
    lambda p, v: (f"Value = NOI / cap rate = {money(p['NOI'])} / {pct(p['c'])} = {money(round(v['value'], 1))}mm. A cap rate is like an "
                  f"inverted EV/EBITDA multiple: a {pct(p['c'])} cap rate is about {num(1 / p['c'], 1)}x NOI."),
    ["Value = NOI / cap rate", "A lower cap rate means a higher value (like a higher multiple)"],
)

RE_FFO = Template(
    id="re_ffo", skill="industry", difficulty=2, kind="numeric", title="REIT funds from operations (FFO)",
    text=lambda p: (f"A REIT reports net income of {money(p['NI'])}mm, real-estate depreciation of {money(p['DA'])}mm, and a "
                    f"{money(p['G'])}mm gain on selling a property. What's its FFO?"),
    gen=lambda r: {"NI": float(r.choice([100, 150, 200])), "DA": float(r.choice([60, 80, 100])), "G": float(r.choice([20, 30]))},
    solve=lambda p: {"ffo": p["NI"] + p["DA"] - p["G"]},
    labels=[Label("ffo", "FFO ($mm)", "$")],
    traps={"RE_FFO_GAIN": lambda p: [{"ffo": p["NI"] + p["DA"]}]},
    explain=lambda p, v: (f"FFO = net income + real-estate depreciation - gains on property sales = {money(p['NI'])} + {money(p['DA'])} - "
                          f"{money(p['G'])} = {money(v['ffo'])}mm. Depreciation is added back because buildings often hold their value; "
                          f"gains are removed because they don't recur."),
    key_points=["Add back real-estate depreciation", "Subtract gains on property sales", "FFO approximates recurring cash earnings"],
    misconceptions=["RE_FFO_GAIN"], groups=["real_estate"], target_seconds=50,
)

TMT_LTV = Template(
    id="tmt_ltv", skill="industry", difficulty=2, kind="numeric", title="SaaS unit economics: LTV/CAC",
    text=lambda p: (f"A SaaS customer pays {money(p['A'])} a year. Gross margin is {pct(p['gm'], 0)}, annual churn is {pct(p['ch'], 0)}, "
                    f"and it costs {money(p['C'])} to acquire a customer. What are the lifetime value and the LTV/CAC ratio?"),
    gen=lambda r: {"A": float(r.choice([1000, 1200, 2000])), "gm": r.choice([0.75, 0.8]), "ch": r.choice([0.1, 0.2]),
                   "C": float(r.choice([1500, 2000, 3000]))},
    solve=lambda p: {"ltv": _a(p["A"] * p["gm"] / p["ch"]), "ratio": _a(p["A"] * p["gm"] / p["ch"] / p["C"])},
    labels=[Label("ltv", "Customer lifetime value", "$"), Label("ratio", "LTV/CAC (x)", "x", required=False, tol_abs=0.05, tol_rel=0)],
    traps={"TMT_LTV_NO_MARGIN": lambda p: [{"ltv": _a(p["A"] / p["ch"]), "ratio": _a(p["A"] / p["ch"] / p["C"])}]},
    explain=lambda p, v: (f"Gross profit per year = {money(p['A'])} x {pct(p['gm'], 0)} = {money(p['A'] * p['gm'])}. Average lifetime = 1 / "
                          f"{pct(p['ch'], 0)} = {num(1 / p['ch'])} years. LTV = {money(round(v['ltv']))}; LTV/CAC = {num(v['ratio'], 1)}x "
                          f"(3x+ is usually considered healthy)."),
    key_points=["LTV uses gross profit, not revenue", "Customer lifetime = 1 / churn", "LTV/CAC above about 3x is healthy"],
    misconceptions=["TMT_LTV_NO_MARGIN"], groups=["tmt"], target_seconds=75,
)

HC_RNPV = Template(
    id="hc_rnpv", skill="industry", difficulty=2, kind="numeric", title="Biotech: risk-adjusted NPV",
    text=lambda p: (f"A biotech's only drug would be worth {money(p['V'])}mm (NPV) if approved. It has a {pct(p['pr'], 0)} chance of "
                    f"approval, and {money(p['Cd'])}mm (present value) of trial costs must be spent either way. What's the risk-adjusted NPV?"),
    gen=lambda r: {"V": float(r.choice([1000, 1500, 2000])), "pr": r.choice([0.2, 0.3, 0.5]), "Cd": float(r.choice([100, 150, 200]))},
    solve=lambda p: {"rnpv": _a(p["pr"] * p["V"] - p["Cd"])},
    labels=[Label("rnpv", "Risk-adjusted NPV ($mm)", "$")],
    traps={"HC_RNPV_UNWEIGHTED": lambda p: [{"rnpv": p["V"] - p["Cd"]}, {"rnpv": _a(p["pr"] * (p["V"] - p["Cd"]))}]},
    explain=lambda p, v: (f"Weight the approved-case value by the probability: {pct(p['pr'], 0)} x {money(p['V'])} = "
                          f"{money(p['pr'] * p['V'])}mm, then subtract the {money(p['Cd'])}mm of costs that are spent regardless: "
                          f"rNPV = {money(v['rnpv'])}mm."),
    key_points=["Weight the success-case value by the probability of approval", "Costs spent regardless are not probability-weighted"],
    misconceptions=["HC_RNPV_UNWEIGHTED"], groups=["healthcare"], target_seconds=60,
)


def _rx(p: Params) -> tuple[float, float]:
    senior = min(p["S"], p["X"])
    unsec = max(min(p["U"], p["X"] - senior), 0)
    return senior / p["S"] * 100, unsec / p["U"] * 100


RX_WATERFALL = Template(
    id="rx_waterfall", skill="industry", difficulty=3, kind="numeric", title="Restructuring: recovery waterfall",
    text=lambda p: (f"A bankrupt company is worth {money(p['X'])}mm. It has {money(p['S'])}mm of senior secured debt and "
                    f"{money(p['U'])}mm of unsecured bonds. Under absolute priority, what percentage do the unsecured bondholders recover?"),
    gen=lambda r: {"X": float(r.choice([600, 700, 800])), "S": float(r.choice([400, 500])), "U": float(r.choice([400, 600]))},
    solve=lambda p: {"unsecured_recovery": _a(_rx(p)[1]), "senior_recovery": _a(_rx(p)[0])},
    labels=[Label("unsecured_recovery", "Unsecured recovery (%)", "%", tol_abs=1.0, tol_rel=0),
            Label("senior_recovery", "Senior recovery (%)", "%", required=False, tol_abs=1.0, tol_rel=0)],
    traps={"RX_PRO_RATA": lambda p: [{"unsecured_recovery": _a(min(p["X"] / (p["S"] + p["U"]), 1) * 100),
                                      "senior_recovery": _a(min(p["X"] / (p["S"] + p["U"]), 1) * 100)}]},
    explain=lambda p, v: (f"Senior secured is paid first: {money(min(p['S'], p['X']))}mm, a {num(v['senior_recovery'], 0)}% recovery. "
                          f"What's left, {money(max(p['X'] - p['S'], 0))}mm, goes to the {money(p['U'])}mm of unsecured bonds: "
                          f"{num(v['unsecured_recovery'], 1)}%. Equity gets nothing."),
    key_points=["Absolute priority: secured claims are paid first", "Unsecured creditors get only the remaining value",
                "Equity is wiped out if creditors aren't paid in full"],
    misconceptions=["RX_PRO_RATA"], groups=["restructuring", "levfin"], target_seconds=75,
)

EN_EBITDAX = Template(
    id="en_ebitdax", skill="industry", difficulty=2, kind="numeric", title="E&P valuation: EV/EBITDAX",
    text=lambda p: (f"An oil & gas producer has an enterprise value of {money(p['V'])}mm, EBITDA of {money(p['E'])}mm and "
                    f"{money(p['X'])}mm of exploration expense. Peers are quoted on EV/EBITDAX. What's its multiple?"),
    gen=lambda r: {"V": float(r.choice([3000, 4000, 6000])), "E": float(r.choice([400, 500, 600])), "X": float(r.choice([50, 100]))},
    solve=lambda p: {"multiple": _a(p["V"] / (p["E"] + p["X"]))},
    labels=[Label("multiple", "EV/EBITDAX (x)", "x", tol_abs=0.1, tol_rel=0)],
    traps={"EN_EBITDA_ONLY": lambda p: [{"multiple": _a(p["V"] / p["E"])}]},
    explain=lambda p, v: (f"EBITDAX = EBITDA + exploration expense = {money(p['E'] + p['X'])}mm. EV/EBITDAX = {money(p['V'])} / "
                          f"{money(p['E'] + p['X'])} = {num(v['multiple'], 1)}x. Adding back exploration makes successful-efforts and "
                          f"full-cost companies comparable."),
    key_points=["EBITDAX adds exploration expense back to EBITDA", "It makes companies with different accounting methods comparable"],
    misconceptions=["EN_EBITDA_ONLY"], groups=["energy"], target_seconds=50,
)

# =========================================================================== MORE CONCEPTUAL (incl. basics + groups)
MORE_CONCEPTUAL = [
    _concept("c_ev_vs_equity", "ev", 1, "EV vs equity value",
             "What's the difference between enterprise value and equity value?",
             ["Equity value is the value of the shareholders' claim (market cap)", "Enterprise value is the value of the whole operating business to all investors",
              "Bridge: EV = equity value + debt + preferred + NCI - cash", "A house analogy: the house price (EV) vs the owner's equity after the mortgage"],
             ["EV_ADD_CASH"],
             "Equity value is what the company's shares are worth: the shareholders' claim. Enterprise value is what the core business is worth to "
             "everyone with a claim on it, lenders as well as shareholders. You get from equity value to EV by adding debt, preferred stock and "
             "noncontrolling interest and subtracting cash. Like a house: EV is the price of the house; equity value is what the owner keeps after the mortgage."),
    _concept("c_val_methods", "ev", 1, "The three valuation methods",
             "What are the main ways to value a company, and which usually gives the highest value?",
             ["Comparable companies (trading multiples)", "Precedent transactions (multiples paid in past deals)",
              "DCF (intrinsic value of future cash flows)", "Precedents are often highest because they include a control premium"],
             [],
             "Comparable companies apply peers' trading multiples; precedent transactions apply multiples paid in past acquisitions; a DCF values the "
             "company's future cash flows. Precedents often give the highest value because acquirers pay a control premium; a DCF can be highest "
             "or lowest depending on its assumptions."),
    _concept("c_wacc_what", "dcf", 1, "What WACC is",
             "What is WACC, and why do we use it in a DCF?",
             ["The blended required return of all capital providers (debt and equity)", "Weights by market value, with the after-tax cost of debt",
              "It discounts unlevered free cash flow, which belongs to all capital providers"],
             ["DCF_WACC_NO_SHIELD"],
             "WACC is the weighted average cost of capital: the blended return that debt and equity investors require, weighted by market values, "
             "with debt on an after-tax basis. It's the discount rate for unlevered free cash flow because that cash flow is available to all "
             "capital providers."),
    _concept("c_wc_what", "accounting", 1, "Working capital",
             "What is working capital, and what does an increase in it do to cash flow?",
             ["Operating current assets minus operating current liabilities", "Examples: receivables, inventory, payables, deferred revenue",
              "An increase uses cash (money tied up in the business)", "A decrease is a source of cash"],
             ["ACC_AR_IGNORED"],
             "Working capital is operating current assets (receivables, inventory) minus operating current liabilities (payables, deferred revenue). "
             "An increase means more cash is tied up in the business, so it reduces cash flow; a decrease frees cash up."),
    _concept("c_ma_why", "ma", 1, "Why companies acquire",
             "Why would one company want to acquire another?",
             ["Growth: new markets, products or customers", "Synergies: cost savings and revenue opportunities",
              "Capabilities: technology, talent or IP faster than building it", "Strategic or defensive reasons (consolidation, blocking competitors)"],
             [],
             "To grow faster than it could organically (new markets, products or customers), to capture synergies (cost savings or cross-selling), "
             "to buy capabilities like technology, talent or IP, or for strategic reasons such as consolidating an industry or keeping an asset away "
             "from a competitor."),
    _concept("c_ma_synergies", "ma", 2, "Revenue vs cost synergies",
             "What's the difference between revenue and cost synergies, and which do bankers trust more?",
             ["Cost synergies: overlapping costs removed (headcount, facilities, procurement)", "Revenue synergies: cross-selling, pricing, new markets",
              "Cost synergies are more reliable because they're more within management's control", "Synergies are often overestimated, so they're usually haircut"],
             [],
             "Cost synergies come from removing overlapping costs: headcount, facilities, procurement. Revenue synergies come from cross-selling, "
             "pricing or new markets. Cost synergies are trusted more because management controls them; revenue synergies depend on customers and are "
             "often overestimated, so they're usually haircut."),
    _concept("c_lbo_what", "lbo", 1, "What an LBO is",
             "What is a leveraged buyout?",
             ["A private equity firm buys a company using a lot of debt", "The company's own cash flow pays the interest and down the debt",
              "The sponsor sells after about 3-7 years", "Returns come from paydown, EBITDA growth and multiple expansion"],
             ["LBO_NO_LEVER_LOGIC"],
             "A private equity firm buys a company using mostly borrowed money, with the company's own cash flows servicing and paying down the debt. "
             "After a few years it sells, and the equity return comes from debt paydown, EBITDA growth and any multiple expansion. The debt "
             "magnifies the return on the sponsor's smaller equity check."),
    _concept("c_acc_dtl", "accounting", 3, "Deferred tax liabilities",
             "Where does a deferred tax liability come from, for example with accelerated depreciation?",
             ["Book and tax depreciation differ", "More tax depreciation now means lower cash taxes now than book taxes",
              "The difference reverses later, so a liability is recorded", "On the CFS the DTL increase is added back (a non-cash expense)"],
             [],
             "If tax depreciation is faster than book depreciation, the company pays less cash tax today than its book tax expense. That difference "
             "will reverse later, so it records a deferred tax liability. The increase in the DTL is a non-cash part of tax expense, so it's added "
             "back on the cash flow statement."),
    _concept("c_ev_negative", "ev", 3, "Negative enterprise value",
             "Can a company's enterprise value be negative? What would that mean?",
             ["Yes, when cash exceeds market cap plus debt", "The market values the operating business below zero",
              "Often signals expected cash burn, liabilities or distrust of management", "Can be a value opportunity or a warning sign"],
             [],
             "Yes. If a company holds more cash than its market cap plus debt, EV is negative: the market is valuing the operating business below zero, "
             "usually because it expects cash burn, hidden liabilities or poor capital allocation. It can be a bargain or a warning sign."),
    # group-specific conceptual
    _concept("c_fig_no_ev", "industry", 2, "Why banks aren't valued on EV",
             "Why don't we use enterprise value or EBITDA to value a bank?",
             ["Debt and deposits are the raw material of a bank's business, not financing", "Interest is an operating cost, so EBITDA is meaningless",
              "Use equity metrics: P/E, P/BV, P/TBV, ROE", "Dividend discount models replace DCFs"],
             ["FIG_USES_EV"],
             "For a bank, deposits and debt are the inputs it lends out, and interest is its main operating cost, so EV and EBITDA don't separate "
             "operations from financing. Banks are valued on equity metrics: P/E, P/BV and P/TBV (linked to ROE), with dividend discount models in place of DCFs."),
    _concept("c_re_reit", "industry", 2, "Valuing a REIT",
             "What metrics would you use to value a REIT?",
             ["FFO and AFFO instead of net income (P/FFO multiples)", "NAV: properties valued at cap rates, less debt",
              "Cap rates and NOI", "Dividend yield matters because REITs must distribute most income"],
             ["RE_FFO_GAIN"],
             "REITs are valued on FFO and AFFO (price/FFO) rather than net income, because real-estate depreciation distorts earnings. Analysts also build a "
             "NAV by valuing the properties at market cap rates on NOI and subtracting debt, and they watch dividend yield because REITs must pay out most income."),
    _concept("c_tmt_saas", "industry", 2, "Valuing high-growth software",
             "How would you value an unprofitable, high-growth software company?",
             ["EV/Revenue or EV/ARR multiples instead of earnings multiples", "Growth rate and gross margin drive the multiple",
              "Unit economics: LTV/CAC, net revenue retention, churn", "DCF with a long horizon until margins mature"],
             ["TMT_LTV_NO_MARGIN"],
             "With no earnings, use EV/Revenue or EV/ARR, where the multiple depends on growth and gross margin (the Rule of 40 is a common check). "
             "Unit economics like LTV/CAC, net revenue retention and churn show whether growth is profitable, and a long-horizon DCF can show value "
             "once margins mature."),
    _concept("c_hc_biotech", "industry", 2, "Valuing a pre-revenue biotech",
             "How would you value a biotech that has no revenue yet?",
             ["Risk-adjusted NPV (rNPV) by drug", "Probability of success by clinical phase", "Sum-of-the-parts across the pipeline",
              "Comparable deals and peer valuations by phase"],
             ["HC_RNPV_UNWEIGHTED"],
             "Value each drug with a risk-adjusted NPV: forecast its cash flows if approved and weight them by the probability of success at its clinical "
             "phase, then sum across the pipeline. Cross-check with peer and transaction valuations for companies at the same phase."),
    _concept("c_en_ep", "industry", 2, "Valuing oil & gas producers",
             "What's different about valuing an oil & gas exploration and production company?",
             ["NAV based on proved reserves and commodity price decks", "EV/EBITDAX multiples", "Production and reserves multiples (EV per flowing barrel, per proved reserve)",
              "Commodity prices drive everything"],
             ["EN_EBITDA_ONLY"],
             "E&P companies are valued with a NAV model of their reserves under commodity price assumptions, plus EV/EBITDAX (to neutralise exploration "
             "accounting) and operating multiples like EV per flowing barrel or per proved reserve. Commodity price assumptions drive the answer."),
    _concept("c_rx_ch11", "industry", 3, "Chapter 11",
             "What happens to a company in a Chapter 11 restructuring?",
             ["The company keeps operating under court protection", "Creditors are paid by priority (absolute priority rule)",
              "DIP financing funds operations during the case", "A plan of reorganization swaps debt for equity or new debt; Chapter 7 is liquidation"],
             ["RX_PRO_RATA"],
             "In Chapter 11 the company keeps operating under court protection, often funded by DIP financing, while it negotiates a plan of reorganization. "
             "Claims are settled by priority: secured creditors first, then unsecured, then equity, often by swapping debt for new debt or equity. "
             "Chapter 7, by contrast, is liquidation."),
    _concept("c_ind_cyclical", "industry", 2, "Cyclical industrials",
             "How do you value a cyclical industrial company?",
             ["Use normalized or mid-cycle earnings, not peak or trough", "EV/EBITDA on mid-cycle numbers", "Backlog and order trends matter",
              "Capital intensity: look at EV/EBIT or FCF as well as EBITDA"],
             [],
             "Use mid-cycle or normalized earnings rather than a peak or trough year, and apply EV/EBITDA, plus EV/EBIT or free cash flow because these "
             "businesses are capital-intensive. Backlog and order trends signal where the cycle is heading."),
    _concept("c_consumer_metrics", "industry", 2, "Consumer and retail metrics",
             "What operating metrics matter most for a retail company?",
             ["Same-store sales growth", "Store count and new-store productivity", "Gross margin and inventory turns",
              "Store-level (four-wall) EBITDA"],
             [],
             "Same-store (comparable) sales growth, store count and new-store productivity, gross margin, inventory turns, and store-level or "
             "four-wall EBITDA, which show whether growth is coming from healthy existing stores or just from opening new ones."),
    _concept("c_levfin_credit", "industry", 2, "Credit metrics",
             "What credit metrics would a lender look at before financing a company?",
             ["Leverage: debt / EBITDA", "Interest coverage: EBITDA / interest", "Free cash flow to debt and ability to repay",
              "Covenants, collateral and the business's stability"],
             [],
             "Leverage (total and senior debt / EBITDA), interest coverage (EBITDA / interest), and free cash flow relative to debt to see how fast it "
             "can repay, plus covenants, collateral and how stable and cyclical the business is."),
    _concept("c_ecm_ipo", "industry", 1, "The IPO process",
             "Walk me through the IPO process.",
             ["Pick banks and do due diligence", "File the registration statement (S-1) with the SEC", "Roadshow to investors and build the order book",
              "Price the offering, allocate shares and start trading (with a greenshoe)"],
             [],
             "The company picks underwriters, they do due diligence and draft the S-1 registration statement, which the SEC reviews. Then management "
             "runs a roadshow to investors while the banks build the order book, the deal is priced and allocated, and the shares start trading, "
             "often with a greenshoe option to stabilise the price."),
    _concept("c_dcm_rates", "industry", 1, "Bond prices and rates",
             "What happens to a bond's price when interest rates rise, and why?",
             ["Price falls", "Its fixed coupon is now less attractive than new bonds", "The yield rises to match the market",
              "Longer-maturity bonds move more (duration)"],
             ["MKT_RATES_NO_EFFECT"],
             "The price falls. Its fixed coupon is now less attractive than new bonds paying higher rates, so the price drops until its yield matches "
             "the market. Longer-dated bonds fall more because more of their cash flows are discounted at the higher rate (duration)."),
]

# =========================================================================== FIT & BEHAVIORAL
def _fit(tid: str, diff: int, title: str, question: str, key_points: list[str], mis: list[str], model: str, secs: int = 120) -> Template:
    return Template(id=tid, skill="fit", difficulty=diff, kind="behavioral", title=title,
                    text=lambda p, q=question: q.replace("{group}", str(p.get("group", "this group"))),
                    key_points=key_points, misconceptions=mis, explain=lambda p, v, a=model: a, target_seconds=secs)


BEHAVIORAL = [
    _fit("b_resume", 1, "Walk me through your resume", "Walk me through your resume.",
         ["Clear structure: past, then present, then future", "Connects the steps with the reasons behind each choice",
          "Builds to why investment banking now", "About two minutes, without reading the resume line by line"],
         ["FIT_NO_STRUCTURE", "FIT_GENERIC"],
         "A strong answer is a two-minute story, not a list: where you started and what drew you to business, the key steps and why you took each one, "
         "what you learned that points to banking, and why this role is the logical next step now."),
    _fit("b_why_ib", 1, "Why investment banking", "Why investment banking?",
         ["Specific reasons (deal exposure, learning curve, working on strategic decisions)", "Evidence from your own experience",
          "Realistic view of the job (hours, analytical work)", "Not mainly about money or prestige", "Link to longer-term goals"],
         ["FIT_GENERIC", "FIT_MONEY_PRESTIGE"],
         "Give two or three specific reasons, each backed by something you've done: a project where you enjoyed financial analysis, a deal you followed "
         "closely, conversations with bankers. Show you understand the job's demands, and connect it to where you want to be in the long run."),
    _fit("b_why_group", 2, "Why this group", "Why do you want to work in {group}?",
         ["Knowledge of the group's sector or product", "A specific trend or recent deal in the space", "A personal connection or prior experience",
          "How your skills fit the group's work"],
         ["FIT_GENERIC", "FIT_NO_EVIDENCE"],
         "Show you know what the group does and what's happening in its space (a trend or recent deal), why it genuinely interests you (a personal link or "
         "prior experience), and how your background fits the work."),
    _fit("b_why_firm", 2, "Why our firm", "Why our firm over the other banks you're talking to?",
         ["Specific differentiators (deal flow, group strengths, culture)", "People you've met and what you learned from them",
          "Fit between you and the firm", "Not generic praise"],
         ["FIT_GENERIC"],
         "Name concrete differentiators (group strengths, recent deals, culture), mention people you've spoken with and what stood out, and explain why that "
         "fits you specifically. Avoid praise that could apply to any bank."),
    _fit("b_deal", 2, "Tell me about a deal", "Tell me about a recent deal you've followed.",
         ["Who, what and size (parties, value, consideration)", "Strategic rationale", "Valuation (multiple or premium paid)",
          "Your own view: good deal or not, and why", "Key risks"],
         ["FIT_NO_VIEW", "FIT_NO_EVIDENCE"],
         "Cover the parties, size and consideration; the strategic rationale; the valuation (multiple or premium); then take a view on whether it creates "
         "value and name the biggest risk. The view is what interviewers are really testing."),
    _fit("b_team", 1, "Teamwork under pressure", "Tell me about a time you worked on a team under pressure.",
         ["STAR structure: situation, task, action, result", "Your specific role and actions (\"I\", not just \"we\")",
          "A concrete, ideally quantified result", "What you learned"],
         ["FIT_NO_STRUCTURE", "FIT_NO_EVIDENCE"],
         "Use STAR: set the situation and stakes briefly, explain your task, spend most of the time on what you personally did, give a concrete result, "
         "and close with what you learned."),
    _fit("b_weakness", 1, "Greatest weakness", "What's your greatest weakness?",
         ["A real weakness, not a disguised strength", "Not disqualifying for the job", "A concrete example",
          "Specific steps you're taking, with evidence of progress"],
         ["FIT_FAKE_WEAKNESS", "FIT_NO_EVIDENCE"],
         "Pick a genuine, non-fatal weakness, illustrate it with a real example, and spend most of the answer on what you're doing about it and the progress so far."),
    _fit("b_leadership", 2, "Leading without authority", "Tell me about a time you had to lead or influence people without formal authority.",
         ["STAR structure", "How you persuaded or aligned people", "A concrete result", "Reflection on your leadership style"],
         ["FIT_NO_STRUCTURE", "FIT_NO_EVIDENCE"],
         "Use STAR, focus on how you built buy-in (listening, data, small wins), give the outcome, and reflect on what it taught you about leading."),
    _fit("b_pitch", 3, "Pitch me a stock", "Pitch me a stock you'd buy today.",
         ["A clear thesis in one sentence", "Two or three supporting points with numbers", "Valuation: why it's mispriced",
          "Catalysts and key risks"],
         ["FIT_NO_VIEW", "FIT_NO_EVIDENCE"],
         "State the thesis up front, support it with two or three data-backed points, show why the valuation is attractive versus peers or history, "
         "and finish with catalysts and the main risk."),
]

NEW_NUMERIC = [ACC_REV_CASH, ACC_OPEX_CASH, ACC_INVENTORY, ACC_AP, ACC_DEFREV, EV_TSM, DCF_PV, LBO_BASIC,
               FIG_PTBV, RE_CAP_RATE, RE_FFO, TMT_LTV, HC_RNPV, RX_WATERFALL, EN_EBITDAX]

NUMERIC = [ACC_DA, ACC_WRITEDOWN, ACC_SBC, ACC_CAPEX, ACC_AR, ACC_DEBT, EV_BRIDGE, EV_IMPLIED_PRICE,
           EV_DEBT_CASH, DCF_UFCF, DCF_TV, DCF_WACC, DCF_CAPM, MA_STOCK, MA_CASH, MA_DEBT, MA_GOODWILL,
           LBO_PAPER, LBO_IRR_RULE, MKT_RATES_WACC, MKT_RATES_LBO, MKT_RATES_MA] + NEW_NUMERIC

TEMPLATES: dict[str, Template] = {t.id: t for t in NUMERIC + CONCEPTUAL + MORE_CONCEPTUAL + BEHAVIORAL}

SKILLS = {
    "accounting": "Accounting",
    "ev": "EV & valuation",
    "dcf": "DCF & WACC",
    "ma": "M&A",
    "lbo": "LBO",
    "industry": "Group specifics",
    "fit": "Fit & behavioral",
}
TECHNICAL = ["accounting", "ev", "dcf", "ma", "lbo"]
LEVELS = {1: "Basic", 2: "Intermediate", 3: "Advanced"}

SPECIALIST_FOR_SKILL = {
    "accounting": "accounting", "ev": "valuation", "dcf": "valuation",
    "ma": "deals", "lbo": "deals", "markets": "markets", "industry": "industry", "fit": "fit",
}

# --------------------------------------------------------------------------- groups the candidate can target
GROUPS = {
    # coverage
    "tmt": "Technology, Media & Telecom", "healthcare": "Healthcare", "fig": "Financial Institutions (FIG)",
    "industrials": "Industrials", "consumer": "Consumer & Retail", "energy": "Energy, Power & Infrastructure",
    "real_estate": "Real Estate & REITs",
    # product
    "ma": "M&A", "levfin": "Leveraged Finance / DCM", "ecm": "Equity Capital Markets", "restructuring": "Restructuring",
    "sponsors": "Financial Sponsors", "generalist": "Generalist / not sure yet",
}
GROUP_KIND = {g: ("coverage" if g in ("tmt", "healthcare", "fig", "industrials", "consumer", "energy", "real_estate") else "product")
              for g in GROUPS}
# How much each technical area weighs in practice for each group (1 = normal). FIG de-emphasises EV/LBO.
GROUP_WEIGHTS = {
    "fig": {"ev": 0.6, "lbo": 0.4, "accounting": 1.4},
    "levfin": {"lbo": 1.8, "dcf": 1.1, "ma": 0.7}, "sponsors": {"lbo": 2.0, "ma": 0.8},
    "ma": {"ma": 1.8, "ev": 1.2}, "ecm": {"ma": 0.6, "lbo": 0.5, "ev": 1.3, "dcf": 1.2},
    "restructuring": {"accounting": 1.3, "lbo": 1.2, "ma": 0.6}, "real_estate": {"lbo": 0.8},
}

# --------------------------------------------------------------------------- level, sub-skill and groups for every question
# (level 1 Basic / 2 Intermediate / 3 Advanced, calibrated against how foundational each topic is in standard IB guides)
SUBSKILLS: dict[str, tuple[str, str]] = {
    "accounting.links": ("accounting", "How the statements link"),
    "accounting.is_basics": ("accounting", "Simple income-statement items"),
    "accounting.noncash": ("accounting", "Non-cash items (D&A, write-downs, SBC)"),
    "accounting.working_capital": ("accounting", "Working capital (AR, AP, inventory, deferred revenue)"),
    "accounting.capex": ("accounting", "Capex and PP&E"),
    "accounting.debt": ("accounting", "Debt and interest"),
    "accounting.taxes": ("accounting", "Deferred taxes"),
    "ev.concepts": ("ev", "EV vs equity value"),
    "ev.bridge": ("ev", "EV bridge"),
    "ev.diluted_shares": ("ev", "Diluted shares (TSM)"),
    "ev.multiples": ("ev", "Multiples and valuation methods"),
    "dcf.time_value": ("dcf", "Time value of money"),
    "dcf.process": ("dcf", "DCF walkthrough"),
    "dcf.fcf": ("dcf", "Unlevered free cash flow"),
    "dcf.discount_rate": ("dcf", "WACC and cost of equity"),
    "dcf.terminal_value": ("dcf", "Terminal value"),
    "dcf.rates": ("dcf", "Interest-rate sensitivity"),
    "ma.rationale": ("ma", "Deal rationale and synergies"),
    "ma.accretion": ("ma", "Accretion / dilution"),
    "ma.purchase_accounting": ("ma", "Purchase accounting and goodwill"),
    "ma.rates": ("ma", "Financing costs and rates"),
    "lbo.concepts": ("lbo", "LBO concepts and candidates"),
    "lbo.returns": ("lbo", "Returns math (MOIC, IRR)"),
    "lbo.paper": ("lbo", "Paper LBO"),
    "lbo.rates": ("lbo", "Rates and leverage"),
    "industry.fig": ("industry", "Banks and FIG"), "industry.real_estate": ("industry", "Real estate and REITs"),
    "industry.tmt": ("industry", "Software and TMT"), "industry.healthcare": ("industry", "Healthcare and biotech"),
    "industry.energy": ("industry", "Energy"), "industry.restructuring": ("industry", "Restructuring"),
    "industry.industrials": ("industry", "Industrials"), "industry.consumer": ("industry", "Consumer and retail"),
    "industry.credit": ("industry", "Credit and leveraged finance"), "industry.capital_markets": ("industry", "Capital markets"),
    "fit.story": ("fit", "Your story"), "fit.motivation": ("fit", "Why banking, group and firm"),
    "fit.deal": ("fit", "Deal discussion"), "fit.experiences": ("fit", "Teamwork and leadership stories"),
    "fit.self_awareness": ("fit", "Strengths and weaknesses"), "fit.markets_view": ("fit", "Market views and pitches"),
}

META: dict[str, tuple[int, str, list[str]]] = {
    # accounting
    "acc_rev_cash": (1, "accounting.is_basics", []), "acc_opex_cash": (1, "accounting.is_basics", []),
    "acc_da": (1, "accounting.noncash", []), "acc_capex": (1, "accounting.capex", []),
    "acc_inventory": (1, "accounting.working_capital", []), "c_acc_link": (1, "accounting.links", []),
    "c_acc_addback": (1, "accounting.noncash", []), "c_wc_what": (1, "accounting.working_capital", []),
    "acc_writedown": (2, "accounting.noncash", []), "acc_sbc": (2, "accounting.noncash", []),
    "acc_ar": (2, "accounting.working_capital", []), "acc_ap": (2, "accounting.working_capital", []),
    "acc_debt": (2, "accounting.debt", []),
    "acc_defrev": (3, "accounting.working_capital", []), "c_acc_dtl": (3, "accounting.taxes", []),
    # EV & valuation
    "c_ev_vs_equity": (1, "ev.concepts", []), "c_val_methods": (1, "ev.multiples", []), "ev_bridge": (1, "ev.bridge", []),
    "ev_debt_cash": (1, "ev.bridge", []), "c_ev_cash": (1, "ev.bridge", []),
    "ev_implied_price": (2, "ev.multiples", []), "ev_tsm": (2, "ev.diluted_shares", []), "c_ev_multiples": (2, "ev.multiples", []),
    "c_ev_negative": (3, "ev.concepts", []),
    # DCF
    "dcf_pv": (1, "dcf.time_value", []), "c_dcf_walk": (1, "dcf.process", []), "c_wacc_what": (1, "dcf.discount_rate", []),
    "dcf_capm": (1, "dcf.discount_rate", []),
    "dcf_ufcf": (2, "dcf.fcf", []), "dcf_wacc": (2, "dcf.discount_rate", []), "dcf_tv": (2, "dcf.terminal_value", []),
    "c_dcf_wacc": (2, "dcf.terminal_value", []),
    "mkt_rates_wacc": (3, "dcf.rates", []), "c_mkt_duration": (3, "dcf.rates", []),
    # M&A
    "c_ma_why": (1, "ma.rationale", []), "c_ma_synergies": (2, "ma.rationale", []), "c_ma_pe": (2, "ma.accretion", []),
    "ma_stock": (2, "ma.accretion", []), "ma_cash": (2, "ma.accretion", []), "ma_debt": (2, "ma.accretion", []),
    "c_mkt_rates_deals": (2, "ma.rates", []),
    "ma_goodwill": (3, "ma.purchase_accounting", []), "mkt_rates_ma": (3, "ma.rates", []),
    # LBO
    "c_lbo_what": (1, "lbo.concepts", []), "c_lbo_candidate": (1, "lbo.concepts", []), "lbo_irr_rule": (1, "lbo.returns", []),
    "lbo_basic": (1, "lbo.returns", []),
    "c_lbo_leverage": (2, "lbo.concepts", []), "lbo_paper": (2, "lbo.paper", []),
    "mkt_rates_lbo": (3, "lbo.rates", []),
    # group specifics
    "fig_ptbv": (2, "industry.fig", ["fig"]), "c_fig_no_ev": (2, "industry.fig", ["fig"]),
    "re_cap_rate": (1, "industry.real_estate", ["real_estate"]), "re_ffo": (2, "industry.real_estate", ["real_estate"]),
    "c_re_reit": (2, "industry.real_estate", ["real_estate"]),
    "tmt_ltv": (2, "industry.tmt", ["tmt"]), "c_tmt_saas": (2, "industry.tmt", ["tmt"]),
    "hc_rnpv": (2, "industry.healthcare", ["healthcare"]), "c_hc_biotech": (2, "industry.healthcare", ["healthcare"]),
    "en_ebitdax": (2, "industry.energy", ["energy"]), "c_en_ep": (2, "industry.energy", ["energy"]),
    "rx_waterfall": (3, "industry.restructuring", ["restructuring", "levfin"]), "c_rx_ch11": (3, "industry.restructuring", ["restructuring"]),
    "c_ind_cyclical": (2, "industry.industrials", ["industrials"]), "c_consumer_metrics": (2, "industry.consumer", ["consumer"]),
    "c_levfin_credit": (2, "industry.credit", ["levfin", "sponsors", "restructuring"]),
    "c_ecm_ipo": (1, "industry.capital_markets", ["ecm"]), "c_dcm_rates": (1, "industry.capital_markets", ["levfin", "ecm"]),
    # fit
    "b_resume": (1, "fit.story", []), "b_why_ib": (1, "fit.motivation", []), "b_team": (1, "fit.experiences", []),
    "b_weakness": (1, "fit.self_awareness", []), "b_why_group": (2, "fit.motivation", []), "b_why_firm": (2, "fit.motivation", []),
    "b_deal": (2, "fit.deal", []), "b_leadership": (2, "fit.experiences", []), "b_pitch": (3, "fit.markets_view", []),
}

_SKILL_FOR_PREFIX = {"accounting": "accounting", "ev": "ev", "dcf": "dcf", "ma": "ma", "lbo": "lbo", "industry": "industry", "fit": "fit"}
for _tid, (_lvl, _sub, _groups) in META.items():
    _t = TEMPLATES[_tid]
    if _t.skill == "markets":  # rate-shock questions keep the markets specialist but count toward their parent skill
        _t.specialist = "markets"
    _t.skill = SUBSKILLS[_sub][0]
    _t.difficulty = _lvl
    _t.subskill = _sub
    _t.groups = _groups
assert set(META) == set(TEMPLATES), sorted(set(TEMPLATES) ^ set(META))


def eligible(t: Template, group: str | None) -> bool:
    """A question is relevant if it's core (no group tag) or tagged with the candidate's group."""
    return not t.groups or (group in t.groups)


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
        target_seconds=template.target_seconds, subskill=template.subskill,
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
