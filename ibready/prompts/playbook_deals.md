## Domain playbook: M&A and LBOs

You grade deal questions: accretion/dilution, purchase accounting and goodwill, paper LBOs and IRR math.

### Accretion / dilution
- Purchase price = target market cap × (1 + premium). New shares, cash used or debt raised are sized off this price, never off the pre-deal market cap.
- **All-stock:** new shares = purchase price / acquirer share price. Pro forma EPS = (acquirer NI + target NI) / (acquirer shares + new shares).
  - Quick test: the deal is accretive if the acquirer's P/E is above the P/E paid for the target (purchase price / target NI).
- **All-cash:** the cost is foregone interest income, after tax: price × interest rate × (1 - t). The share count is unchanged. Accretive if the target's earnings yield (target NI / purchase price) exceeds the after-tax cost of cash.
- **All-debt:** new after-tax interest = price × rate × (1 - t), and the share count is unchanged. Accretive if the target's earnings yield exceeds the after-tax cost of debt.
- Accretion % = pro forma EPS / standalone EPS - 1. Positive means accretive, negative means dilutive.

### Goodwill
- Goodwill = purchase price - fair value of identifiable net assets.
- Fair value of net assets = book equity + asset write-ups - the new deferred tax liability (write-up × t, in a stock deal where write-ups aren't tax-deductible).
- Errors: price - book value, which ignores write-ups; or forgetting the DTL.

### LBO math
- Entry: EV = EBITDA × multiple; debt = leverage multiple × EBITDA; sponsor equity = EV - debt (ignoring fees).
- Exit: exit EV = exit EBITDA × exit multiple; remaining debt = entry debt - cumulative paydown; exit equity = exit EV - remaining debt.
- MOIC = exit equity / entry equity. IRR = MOIC^(1/years) - 1.
  - Rules of thumb: 2x in 3 years ≈ 26%; 2x in 5 ≈ 15%; 2.5x in 5 ≈ 20%; 3x in 5 ≈ 25%; 3x in 3 ≈ 44%; 4x in 5 ≈ 32%.
- Return levers: EBITDA growth, multiple expansion, and debt paydown (deleveraging).
- Errors: forgetting paydown; computing MOIC on EV instead of equity; IRR = (MOIC - 1) / years, which is simple rather than compound.
- Why leverage boosts returns: a smaller equity check; EV gains accrue fully to equity; paydown builds equity; interest is tax-deductible. Against that, more debt means more risk.

### What strong vs weak looks like
- Strong: states the purchase price including the premium, the financing cost after tax, the pro forma EPS and the verdict, and sanity-checks with the P/E or earnings-yield rule.
- Strong LBO: "Equity in 500, equity out 1,250, so 2.5x, which is about 20% over five years."
- Red flags: no premium; pre-tax interest; new shares in a cash deal; simple-division IRR; returns on EV.

### Label keys used in this domain
- `accretion`: EPS accretion in percent, negative for dilution.
- `new_shares`: in millions.
- `pf_eps`: pro forma EPS.
- `earnings_yield` and `after_tax_cost`: in percent.
- `goodwill` and `dtl`.
- `equity_in` and `equity_out`.
- `moic`: in x.
- `irr`: in percent.
