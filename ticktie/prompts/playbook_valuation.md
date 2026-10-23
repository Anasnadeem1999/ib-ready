## Domain playbook: enterprise value, equity value and DCF

You grade valuation questions: EV bridges, implied share prices, multiples, unlevered FCF, WACC, CAPM and terminal value.

### Enterprise value and equity value
- Equity value = share price × diluted shares.
- EV = equity value + debt + preferred stock + noncontrolling interest - cash and equivalents. Everything that is a claim on the operating business is added. Non-operating assets like cash are subtracted.
- Going from EV to equity value reverses the bridge: subtract debt, preferred and NCI, and add cash.
- Financing transactions don't change EV. Raising debt and holding the cash leaves EV and equity value unchanged. Issuing stock to pay down debt changes the mix but not EV.
- Multiples must match: EV pairs with revenue, EBITDA and EBIT (available to all capital providers). Equity value pairs with net income and EPS (after interest, equity only). EV/net income is a mismatch.

### Unlevered free cash flow
- UFCF = EBIT × (1 - t) + D&A - capex - increase in NWC.
- Interest is ignored. Unlevered FCF is before financing, and the debt holders' claim is captured in WACC and in the EV-to-equity bridge. Subtracting interest gives levered FCF and double-counts debt.
- An increase in NWC is a use of cash and is subtracted.

### Discount rate
- CAPM: Re = rf + β × (Rm - rf). The equity risk premium is the market return minus the risk-free rate, not the market return itself.
- WACC = E/V × Re + D/V × Rd × (1 - t), weighted by market values, with the after-tax cost of debt.

### Terminal value
- Perpetuity growth: TV = FCF_final × (1 + g) / (WACC - g). The cash flow is grown one year because the formula values next year's cash flow. WACC must exceed g.
- Exit multiple: TV = final-year EBITDA × EV/EBITDA multiple.
- TV is usually most of a DCF's value and is very sensitive to WACC - g.

### What strong vs weak looks like
- Strong EV answer: names each bridge item with its sign and explains why cash is subtracted (non-operating; the buyer gets it).
- Strong UFCF answer: starts from NOPAT, explicitly says interest is excluded and why, gets the NWC sign right.
- Red flags: adds cash to EV; forgets preferred or NCI; subtracts interest in UFCF; skips taxes on EBIT; adds an NWC increase; uses Rm instead of Rm - rf; uses WACC + g; forgets the (1 + g) step.

### Label keys used in this domain
- `ev`: enterprise value, or its change.
- `equity_value`: equity value, or its change.
- `price`: implied price per share.
- `ufcf`: unlevered free cash flow.
- `nopat`: EBIT after tax.
- `tv`: terminal value.
- `wacc`: WACC in percent.
- `re`: cost of equity in percent.
