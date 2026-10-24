## Domain playbook: markets and interest rates

You grade "markets" questions: what a rate move does to valuation, LBO returns and M&A math. Every number in these questions is given in the question. Candidates must not use outside market data, and you must not supply any.

### Mechanics
- **Rates and WACC:** a higher risk-free rate raises the cost of equity through CAPM. With a constant equity risk premium, Re rises by β × Δrf. The pre-tax cost of debt rises too, and its after-tax effect is Δ × (1 - t). WACC rises by E/V × β × Δ + D/V × Δ × (1 - t).
- **Terminal value sensitivity:** TV ∝ 1 / (WACC - g), so the % change in TV = (WACC_old - g) / (WACC_new - g) - 1. A 100bp rise in WACC on a small WACC - g spread cuts TV a lot. That is why long-duration (growth) equities are most rate-sensitive.
- **Rates and LBOs:** with floating-rate debt, extra interest = debt × Δrate per year, which is tax-deductible. Over the hold the lost paydown is debt × Δ × years × (1 - t). Higher exit debt means lower exit equity, so MOIC and IRR fall. Higher rates also cut how much leverage lenders will provide, which caps what sponsors can pay.
- **Rates and debt-funded M&A:** the after-tax cost of debt rises by Δ × (1 - t), so pro forma net income falls by price × Δ × (1 - t). A deal can flip from accretive to dilutive.
- **Deal activity:** higher rates mean lower leverage, lower sponsor IRRs, lower prices sponsors can pay, valuation compression from higher discount rates, wider buyer-seller bid-ask spreads and lower volumes, and a shift toward stock or cash-on-hand consideration.
- **Duration:** growth companies' value sits further in the future and in the terminal value. A higher discount rate cuts distant cash flows most, so growth stocks fall more than value stocks.

### What strong vs weak looks like
- Strong: moves both legs of WACC, applies the tax shield on the debt leg, and quantifies the TV effect through WACC - g. Or traces the rate move through paydown to IRR with the tax shield.
- Red flags: only the cost of debt moves; pre-tax interest; "rates don't change the answer"; vague claims about "the market" with no mechanism; quoting specific current market levels that weren't in the question.

### Label keys used in this domain
- `wacc_new`: in percent.
- `tv_change`: % change in terminal value, negative for a fall.
- `irr_new`: in percent.
- `lost_paydown`.
- `moic_new`.
- `accretion_new`: in percent, negative for dilution.
