"""The misconception library.

Each entry is one specific, named way candidates get IB technicals wrong.
Numeric templates in `bank.py` compute the exact wrong numbers each
misconception produces, so a matching answer is diagnosed with certainty.
Conceptual questions are matched by the specialist agents against the
`tell` text below.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Misconception:
    id: str
    skill: str
    name: str
    tell: str  # what the wrong answer sounds like
    fix: str  # the one-paragraph teaching note shown to the candidate


_ALL = [
    # ---------------- Accounting ----------------
    Misconception(
        "ACC_NO_TAX", "accounting", "Ignores the tax effect",
        "Net income moves by the full pre-tax amount; cash is unchanged.",
        "Any pre-tax expense change hits net income after tax: a $10 expense at 25% "
        "tax lowers net income by $7.50, because taxes fall by $2.50. If the expense is "
        "non-cash, that $2.50 tax saving is the only cash effect.",
    ),
    Misconception(
        "ACC_NONCASH_AS_CASH", "accounting", "Treats a non-cash expense as cash",
        "Cash falls because of D&A, a write-down or stock comp.",
        "D&A, write-downs and stock-based compensation reduce net income but no cash "
        "leaves the business, so they are added back on the cash flow statement. Net "
        "effect on cash = the tax saving only.",
    ),
    Misconception(
        "ACC_ADDBACK_NO_NI", "accounting", "Adds back the expense but forgets the net income hit",
        "Cash goes up by the full expense amount.",
        "Start the cash flow statement from the lower net income, then add back the "
        "non-cash expense. Cash rises by amount minus the after-tax net income drop, "
        "which is just the tax saving.",
    ),
    Misconception(
        "ACC_CAPEX_EXPENSED", "accounting", "Expenses a purchase right away (capex or inventory)",
        "Buying PP&E or inventory lowers net income right away.",
        "Capex is capitalised: it shows up in investing cash flow and as PP&E on the "
        "balance sheet. It reaches the income statement only over time, through "
        "depreciation. Inventory works the same way: it sits on the balance sheet and "
        "hits COGS only when it's sold.",
    ),
    Misconception(
        "ACC_AR_IGNORED", "accounting", "Forgets the working-capital (AR) adjustment",
        "Credit revenue raises cash as if it were collected.",
        "Revenue on credit raises accounts receivable, not cash. On the cash flow "
        "statement the AR increase is subtracted, so cash actually falls by the taxes "
        "paid on income not yet collected.",
    ),
    Misconception(
        "ACC_SBC_EQUITY", "accounting", "Misses the APIC increase from stock comp",
        "Shareholders' equity falls with the net income drop.",
        "SBC lowers retained earnings by the after-tax amount but raises common "
        "stock/APIC by the full grant value, so total equity rises by the tax saving.",
    ),
    Misconception(
        "ACC_INTEREST_NO_TAX", "accounting", "Forgets interest is tax-deductible",
        "Net income falls by the full interest expense.",
        "Interest is deductible, so net income falls by interest x (1 - tax rate). This "
        "interest tax shield is why debt is cheaper than its coupon.",
    ),
    Misconception(
        "ACC_SIGN_FLIP", "accounting", "Right size, wrong direction",
        "The amount is correct but the sign is backwards.",
        "Write the direction down before the size. Expenses lower net income; non-cash "
        "add-backs raise operating cash flow; asset increases use cash.",
    ),
    # ---------------- EV / equity ----------------
    Misconception(
        "EV_ADD_CASH", "ev", "Adds cash to enterprise value",
        "EV = equity + debt + cash.",
        "EV is the value of the operating business to all capital providers. Cash is "
        "non-operating and a buyer effectively gets it back, so it is subtracted: "
        "EV = equity + debt + preferred + NCI - cash.",
    ),
    Misconception(
        "EV_MISS_CLAIMS", "ev", "Leaves out preferred stock or minority interest",
        "Only debt and cash appear in the bridge.",
        "Every claim on the operating business belongs in EV. Preferred stock is a claim "
        "senior to common shareholders, so it's added like debt; noncontrolling interest "
        "is added because EBITDA includes 100% of subsidiaries you only partly own.",
    ),
    Misconception(
        "EV_BRIDGE_SIGN", "ev", "Runs the bridge the wrong way",
        "Debt is subtracted or cash added when moving between EV and equity value.",
        "Going from EV to equity value: subtract debt and other claims, add cash. Going "
        "from equity value to EV: the reverse.",
    ),
    Misconception(
        "EV_FINANCING_MOVES_EV", "ev", "Thinks financing changes enterprise value",
        "Raising debt and holding the cash increases EV.",
        "Raising debt and holding the cash adds debt and cash in equal amounts, so EV "
        "and equity value are unchanged. Only changes to the operating business move EV.",
    ),
    Misconception(
        "EV_MULTIPLE_MISMATCH", "ev", "Mismatches numerator and denominator in multiples",
        "Pairs EV with net income, or equity value with EBITDA.",
        "Match the claim to the metric: EV pairs with pre-interest metrics (revenue, "
        "EBITDA, EBIT) that belong to all capital providers; equity value pairs with "
        "post-interest metrics (net income, EPS).",
    ),
    # ---------------- DCF ----------------
    Misconception(
        "DCF_LEVERED", "dcf", "Subtracts interest in unlevered FCF",
        "Interest expense is deducted when building unlevered FCF.",
        "Unlevered FCF is cash available to all capital providers, before financing. "
        "Start from EBIT (pre-interest), tax it, add D&A, subtract capex and the "
        "increase in NWC. Interest belongs in levered FCF.",
    ),
    Misconception(
        "DCF_NO_TAX", "dcf", "Skips taxes on EBIT",
        "Uses EBIT instead of NOPAT.",
        "Unlevered FCF starts from NOPAT = EBIT x (1 - t). Skipping the tax overstates "
        "cash flow to all capital providers.",
    ),
    Misconception(
        "DCF_NWC_SIGN", "dcf", "Adds an increase in working capital",
        "An NWC increase raises free cash flow.",
        "An increase in net working capital ties up cash (more receivables or "
        "inventory), so it is subtracted. A decrease releases cash.",
    ),
    Misconception(
        "DCF_TV_NO_GROWTH_STEP", "dcf", "Forgets to grow FCF one year in the Gordon model",
        "TV = FCF / (WACC - g).",
        "The perpetuity growth formula values next year's cash flow: "
        "TV = FCF_n x (1 + g) / (WACC - g).",
    ),
    Misconception(
        "DCF_TV_PLUS_G", "dcf", "Adds growth to the discount rate",
        "Uses WACC + g in the denominator.",
        "Growth raises value, so it is subtracted from the discount rate: the "
        "denominator is WACC - g, which must be positive.",
    ),
    Misconception(
        "DCF_WACC_NO_SHIELD", "dcf", "Leaves out the debt tax shield in WACC",
        "Cost of debt enters WACC pre-tax.",
        "Interest is deductible, so the cost of debt in WACC is Rd x (1 - t).",
    ),
    Misconception(
        "DCF_CAPM_MARKET_RETURN", "dcf", "Uses the market return as the risk premium",
        "Cost of equity = rf + beta x market return.",
        "CAPM uses the equity risk premium, which is the market return minus the "
        "risk-free rate: Re = rf + beta x (Rm - rf).",
    ),
    # ---------------- M&A ----------------
    Misconception(
        "MA_IGNORE_PREMIUM", "ma", "Uses the target's market cap instead of the purchase price",
        "New shares are sized off the current market cap.",
        "The buyer pays the offer price including the control premium. Size new shares, "
        "or the cash and debt needed, off the purchase price.",
    ),
    Misconception(
        "MA_FOREGONE_NO_TAX", "ma", "Forgets taxes on foregone interest or new interest",
        "Uses the pre-tax interest rate in the pro forma net income.",
        "Lost interest income on cash, or new interest on debt, flows through net "
        "income after tax: amount x rate x (1 - t). The after-tax cost of cash or debt "
        "is what you compare to the target's earnings yield.",
    ),
    Misconception(
        "MA_SHARES_FOR_CASH", "ma", "Issues shares in a cash deal",
        "Adds new shares even though the deal is paid in cash.",
        "Only stock consideration creates new shares. In a cash or debt deal the share "
        "count is unchanged and the cost shows up as lost interest income or new "
        "interest expense.",
    ),
    Misconception(
        "MA_GOODWILL_BOOK", "ma", "Calculates goodwill off book value only",
        "Goodwill = purchase price - book equity.",
        "Goodwill = purchase price - fair value of identifiable net assets. Write-ups "
        "raise the net assets, which lowers goodwill, and the deferred tax liability on "
        "the write-up raises it back partly.",
    ),
    Misconception(
        "MA_GOODWILL_NO_DTL", "ma", "Forgets the deferred tax liability on write-ups",
        "Goodwill = price - book equity - write-up.",
        "In a stock deal the write-up is not tax-deductible, so a deferred tax "
        "liability of write-up x t is created. It lowers net assets and so raises "
        "goodwill.",
    ),
    Misconception(
        "MA_PE_RULE", "ma", "Gets the P/E rule for stock deals backwards",
        "A deal is accretive when the target's P/E is higher than the acquirer's.",
        "In an all-stock deal, the deal is accretive when the acquirer's P/E is higher "
        "than the P/E paid for the target. The buyer is using expensive currency to buy "
        "cheaper earnings.",
    ),
    # ---------------- LBO ----------------
    Misconception(
        "LBO_NO_PAYDOWN", "lbo", "Forgets debt paydown at exit",
        "Exit equity = exit EV - the original debt.",
        "Free cash flow repays debt during the hold. At exit, subtract the remaining "
        "debt, which is entry debt minus cumulative paydown. Paydown is one of the "
        "three return levers.",
    ),
    Misconception(
        "LBO_MOIC_ON_EV", "lbo", "Computes returns on enterprise value",
        "MOIC = exit EV / entry EV.",
        "The sponsor's return is on its equity check: MOIC = exit equity / entry equity. "
        "Leverage is exactly why equity returns exceed EV growth.",
    ),
    Misconception(
        "LBO_IRR_SIMPLE", "lbo", "Turns MOIC into IRR with simple division",
        "IRR = (MOIC - 1) / years.",
        "IRR compounds: IRR = MOIC^(1/n) - 1. Rules of thumb: 2x in 5 years is about "
        "15%, 3x in 5 years about 25%, 2x in 3 years about 26%.",
    ),
    Misconception(
        "LBO_NO_LEVER_LOGIC", "lbo", "Can't explain why leverage boosts returns",
        "Says debt is 'cheaper' without the mechanism.",
        "With debt, the sponsor puts in less equity for the same asset. EV gains go "
        "entirely to equity, and debt paydown moves value from lenders to equity, while "
        "after-tax interest is cheaper than the equity return.",
    ),
    # ---------------- Markets / rates ----------------
    Misconception(
        "MKT_RATES_DEBT_ONLY", "markets", "Thinks higher rates only affect cost of debt",
        "WACC moves only through Rd.",
        "A higher risk-free rate raises the cost of equity through CAPM as well as the "
        "cost of debt, so both legs of WACC move.",
    ),
    Misconception(
        "MKT_RATES_PRETAX", "markets", "Ignores the tax shield when rates move",
        "Extra interest hits cash flow and earnings pre-tax.",
        "Extra interest is deductible: the cash and earnings cost of +X bp on debt D is "
        "D x X x (1 - t).",
    ),
    Misconception(
        "MKT_RATES_NO_EFFECT", "markets", "Says rates don't change the deal math",
        "Returns or accretion stay the same after a rate shock.",
        "Rates feed straight into the numbers: higher interest cuts debt paydown and "
        "sponsor IRR, raises the after-tax cost of debt in M&A, and lifts the WACC that "
        "discounts DCF cash flows.",
    ),
    Misconception(
        "MKT_DURATION", "markets", "Misses why long-duration (growth) assets react more to rates",
        "Treats all stocks as equally rate-sensitive.",
        "More of a growth company's value sits in distant cash flows and the terminal "
        "value. A higher discount rate cuts the present value of far-off cash much more, "
        "so long-duration equities fall more when rates rise.",
    ),
    # ---------------- Accounting: working capital ----------------
    Misconception(
        "ACC_AP_IGNORED", "accounting", "Forgets the accounts payable adjustment",
        "An expense that hasn't been paid yet is treated as if it reduced cash.",
        "An unpaid expense raises accounts payable. On the cash flow statement the AP increase is added back, "
        "so cash rises by the tax saving even though net income falls.",
    ),
    Misconception(
        "ACC_DEFREV_AS_REVENUE", "accounting", "Books a customer prepayment as revenue",
        "Cash received in advance shows up as revenue right away.",
        "A prepayment for future service is a liability (deferred revenue), not revenue. Net income is unchanged "
        "until the service is delivered; cash and deferred revenue both rise.",
    ),
    # ---------------- EV: diluted shares ----------------
    Misconception(
        "EV_TSM_BASIC", "ev", "Uses basic shares instead of diluted shares",
        "Equity value uses only basic shares outstanding.",
        "In-the-money options add shares. Use the treasury stock method: add the options, then subtract the "
        "shares the company could buy back with the exercise proceeds.",
    ),
    Misconception(
        "EV_TSM_ALL_OPTIONS", "ev", "Counts every option without the buyback",
        "Adds all options to the share count.",
        "The treasury stock method assumes exercise proceeds (options x strike) buy back shares at the current price, "
        "so the net new shares are options - (options x strike / price).",
    ),
    # ---------------- DCF: time value ----------------
    Misconception(
        "DCF_SIMPLE_DISCOUNT", "dcf", "Discounts with simple instead of compound interest",
        "PV = cash / (1 + rate x years).",
        "Discounting compounds: PV = cash / (1 + r)^n. Each year's discount builds on the last.",
    ),
    # ---------------- Group specifics ----------------
    Misconception(
        "FIG_PTBV_NO_GW", "industry", "Uses book value instead of tangible book value",
        "P/TBV is calculated on total book value, with goodwill still in.",
        "Tangible book value strips out goodwill and intangibles, because a bank's loss-absorbing capital is tangible. "
        "P/TBV = market cap / (book equity - goodwill - intangibles).",
    ),
    Misconception(
        "FIG_USES_EV", "industry", "Values a bank on EV/EBITDA",
        "Applies EV and EBITDA to a bank.",
        "For banks, debt and interest are the raw material of the business, not financing, so EV and EBITDA are "
        "meaningless. Use equity-value metrics: P/E, P/BV, P/TBV, and dividend discount models.",
    ),
    Misconception(
        "RE_FFO_GAIN", "industry", "Leaves gains on property sales in FFO",
        "FFO = net income + real-estate depreciation.",
        "FFO adds back real-estate depreciation and removes gains on property sales, because those gains aren't "
        "recurring operating cash flow.",
    ),
    Misconception(
        "TMT_LTV_NO_MARGIN", "industry", "Calculates LTV on revenue instead of gross profit",
        "LTV = annual revenue per customer / churn.",
        "Customer lifetime value should use gross profit, not revenue: LTV = revenue per customer x gross margin / churn.",
    ),
    Misconception(
        "HC_RNPV_UNWEIGHTED", "industry", "Ignores the probability of approval",
        "Values a pipeline drug at its full approved-case NPV.",
        "Risk-adjusted NPV weights the approved-case value by the probability of approval; costs that are spent "
        "regardless stay unweighted.",
    ),
    Misconception(
        "RX_PRO_RATA", "industry", "Splits value pro rata, ignoring priority",
        "All creditors recover the same percentage.",
        "Recoveries follow the absolute priority waterfall: secured claims are paid in full first, and only the value "
        "that's left flows to unsecured creditors, then to equity.",
    ),
    Misconception(
        "EN_EBITDA_ONLY", "industry", "Uses EBITDA instead of EBITDAX for E&P",
        "Values an oil & gas producer on EV/EBITDA.",
        "E&P companies using successful-efforts accounting expense exploration, so peers use EBITDAX (adding "
        "exploration expense back) to compare like with like.",
    ),
    # ---------------- Fit & behavioral ----------------
    Misconception(
        "FIT_NO_STRUCTURE", "fit", "No clear structure",
        "Rambles chronologically without a beginning, middle and end.",
        "Use a structure the listener can follow: past to present to future for your story, and STAR (situation, task, "
        "action, result) for experiences. Keep it to about two minutes.",
    ),
    Misconception(
        "FIT_GENERIC", "fit", "Generic answer that could apply to anyone",
        "\"I like fast-paced environments and working with smart people.\"",
        "Interviewers have heard the generic version hundreds of times. Anchor every claim in something only you can "
        "say: a specific experience, a person you spoke with, a deal you followed.",
    ),
    Misconception(
        "FIT_NO_EVIDENCE", "fit", "Claims without evidence or results",
        "States strengths or actions without a concrete example or outcome.",
        "Back each claim with a concrete example and a result, ideally quantified, so the interviewer can believe it.",
    ),
    Misconception(
        "FIT_MONEY_PRESTIGE", "fit", "Money or prestige as the main reason",
        "The motivation sounds like pay, exit options or brand.",
        "Lead with what you want to learn and do (deal exposure, the steep learning curve, working on strategic "
        "decisions) and tie it to your own past experiences.",
    ),
    Misconception(
        "FIT_NO_VIEW", "fit", "Describes a deal without taking a view",
        "Summarises the news but never says whether it was a good deal.",
        "Bankers want judgement: give the rationale, the valuation (multiple or premium), and a clear view of whether it "
        "creates value and the key risk.",
    ),
    Misconception(
        "FIT_FAKE_WEAKNESS", "fit", "Disguises a strength as a weakness",
        "\"I work too hard\" or \"I'm a perfectionist.\"",
        "Pick a real, non-disqualifying weakness, show a concrete example, and explain the specific steps you're taking "
        "and the progress you've made.",
    ),
    # ---------------- Learning-design additions (Oct 2026) ----------------
    Misconception(
        "EV_SKIP_BRIDGE", "ev", "Treats equity value as enterprise value",
        "\"EV equals market cap\", or divides EV by shares to get the share price.",
        "EV and equity value differ by the claims of other investors. Going up to EV: add debt (and preferred and NCI), "
        "subtract cash. Going down to equity value: the reverse, then divide by diluted shares.",
    ),
    Misconception(
        "ACC_EBITDA_AFTER_DA", "accounting", "Subtracts D&A to get EBITDA",
        "EBITDA comes out equal to EBIT.",
        "EBITDA is earnings before interest, taxes, depreciation and amortization, so D&A is not subtracted. "
        "EBIT = EBITDA - D&A.",
    ),
    Misconception(
        "ACC_INTEREST_IN_EBIT", "accounting", "Subtracts interest before EBIT",
        "EBIT is reduced by interest expense.",
        "EBIT measures the operating business before financing. Interest comes after EBIT, giving pre-tax income.",
    ),
    Misconception(
        "ACC_DIVIDEND_EXPENSED", "accounting", "Treats a dividend as an expense",
        "Net income falls (often after tax) when a dividend is paid.",
        "Dividends are a distribution of profit to owners, not a cost of running the business. They skip the income "
        "statement, aren't tax-deductible, and reduce cash and retained earnings directly.",
    ),
    Misconception(
        "ACC_PRINCIPAL_EXPENSED", "accounting", "Treats repaying debt as an expense",
        "Net income falls when debt principal is repaid.",
        "Only interest is an expense. Repaying principal just swaps cash for less debt: a financing outflow, with cash "
        "and debt both down.",
    ),
    Misconception(
        "ACC_GAIN_DOUBLE_COUNT", "accounting", "Counts an asset-sale gain twice in cash",
        "Cash rises by the full proceeds plus the after-tax gain.",
        "The gain is already inside the proceeds. On the cash flow statement subtract the gain from operating cash flow, "
        "then show the full proceeds in investing.",
    ),
    Misconception(
        "ACC_PROCEEDS_AS_REVENUE", "accounting", "Treats sale proceeds as revenue",
        "Net income rises by the whole sale price after tax.",
        "Selling an asset isn't revenue. Only the gain (price minus book value) hits the income statement.",
    ),
    Misconception(
        "DCF_TV_NOT_DISCOUNTED", "dcf", "Forgets to discount the terminal value",
        "Adds the year-5 terminal value straight to today's value.",
        "The terminal value is worth that amount at the end of the forecast. Multiply it by that year's discount factor "
        "(or divide by (1 + WACC)^n) before adding it up.",
    ),
    Misconception(
        "DCF_DF_INVERTED", "dcf", "Divides by a discount factor",
        "The present value comes out bigger than the future value.",
        "A discount factor is below 1 and you multiply by it. If your present value is larger than the future value, the "
        "operation is flipped.",
    ),
    Misconception(
        "DCF_BETA_NO_TAX", "dcf", "Unlevers beta without the tax shield",
        "Uses 1 + D/E in the denominator.",
        "Debt's extra risk for shareholders is softened by the interest tax shield: "
        "unlevered beta = levered beta / (1 + (1 - t) x D/E).",
    ),
    Misconception(
        "DCF_BETA_DIRECTION", "dcf", "Unlevers beta in the wrong direction",
        "The unlevered beta comes out higher than the levered beta.",
        "Removing debt removes financial risk, so the unlevered beta must be smaller. Divide by the leverage factor to "
        "unlever; multiply to relever.",
    ),
    Misconception(
        "MA_SYNERGY_NO_GROSSUP", "ma", "Forgets to gross synergies up for tax",
        "Break-even synergies equal the after-tax EPS shortfall.",
        "Synergies are taxed before they reach net income, so the pre-tax amount needed = net income shortfall / (1 - t).",
    ),
    Misconception(
        "MA_IGNORE_NEW_SHARES", "ma", "Forgets the new shares in a stock deal",
        "Divides combined net income by the old share count.",
        "In a stock deal the buyer issues new shares (purchase price / share price). Pro forma EPS divides combined net "
        "income by the old plus new shares.",
    ),
    Misconception(
        "MA_PREMIUM_ON_OFFER", "ma", "Measures the premium against the offer price",
        "Premium = (offer - current price) / offer.",
        "A premium is measured against the target's current, undisturbed share price, what shareholders would have "
        "without the deal: premium = offer / current price - 1. A $30 offer for a $25 stock is a 20% premium, not 16.7%.",
    ),
    Misconception(
        "CR_RATIO_INVERTED", "industry", "Flips a credit ratio",
        "Leverage = EBITDA / debt, or coverage = interest / EBITDA.",
        "Leverage puts debt on top (how many years of EBITDA the debt equals); coverage puts EBITDA on top (how many "
        "times interest is covered). Lower leverage and higher coverage are safer.",
    ),
    # ---------------- Generic ----------------
    Misconception(
        "GEN_ARITHMETIC", "any", "Arithmetic slip",
        "The logic is right but the number is off.",
        "Your method was right; the arithmetic slipped. Say each intermediate number out "
        "loud in interviews so the interviewer can follow, and catch, the slip.",
    ),
    Misconception(
        "GEN_MEMORISED", "any", "Correct answer, can't explain why",
        "Gets the number right but can't justify it when probed.",
        "Interviewers probe to separate memorisation from understanding. For every "
        "answer, be ready to say why each step happens, not just what the number is.",
    ),
]

LIBRARY: dict[str, Misconception] = {m.id: m for m in _ALL}


def for_skill(skill: str) -> list[Misconception]:
    return [m for m in _ALL if m.skill in (skill, "any")]
