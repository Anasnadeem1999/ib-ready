## Domain playbook: group-specific technicals

You grade questions specific to coverage and product groups. Hold candidates to what a first-year analyst in that group would know, no more.

### Financial institutions (FIG)
- Banks' deposits and debt are the raw material of the business, and interest is an operating cost, so EV and EBITDA are not used.
- Valuation is on equity metrics: P/E, P/BV, and P/TBV, where tangible book = equity - goodwill - intangibles. ROE drives P/BV. Dividend discount models replace DCFs.
- Regulatory capital such as CET1 constrains growth and dividends.

### Real estate and REITs
- Property value = NOI / cap rate. A lower cap rate means a higher value, like a higher multiple.
- REITs use FFO = net income + real-estate depreciation - gains on property sales. AFFO also subtracts recurring capex and straight-line rent adjustments.
- NAV = properties at market cap rates - debt. REITs must distribute most of their taxable income, so dividend yield matters.

### TMT and software
- Unprofitable growth companies trade on EV/Revenue or EV/ARR, driven by growth and gross margin. The Rule of 40 is a common check.
- LTV = revenue per customer x gross margin / churn. LTV/CAC of about 3x or more is healthy. CAC payback and net revenue retention matter.

### Healthcare and biotech
- Pre-revenue biotechs are valued with risk-adjusted NPV: approved-case value x probability of success by phase - costs spent regardless.
- The total is a sum of the parts across the pipeline, cross-checked against peers by phase.

### Energy
- E&P: NAV of reserves under a commodity price deck, EV/EBITDAX (exploration expense added back), EV per flowing barrel and per proved reserve.
- Utilities: rate base x allowed return.

### Restructuring and credit
- Absolute priority: secured, then unsecured, then equity. Recoveries follow the waterfall, not pro rata.
- In Chapter 11 the company keeps operating under court protection, often with DIP financing. Chapter 7 is liquidation.
- Credit metrics: debt / EBITDA, EBITDA / interest, FCF / debt, covenants, collateral.

### Capital markets
- IPO: underwriters, due diligence, S-1, SEC review, roadshow and book-building, pricing and allocation, trading, greenshoe.
- Bonds: when rates rise, prices fall. Longer duration means bigger moves.

### Industrials and consumer
- Industrials: use mid-cycle or normalized earnings; capital intensity matters; backlog and orders.
- Consumer and retail: same-store sales, store count and productivity, gross margin, inventory turns, four-wall EBITDA.

### Label keys used in this domain
- `ptbv`, `pbv`, `multiple`: in x.
- `value`, `ffo`, `ltv`, `rnpv`: in $ millions or $ as stated in the question.
- `ratio`: in x.
- `unsecured_recovery`, `senior_recovery`: in percent.
