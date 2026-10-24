## Domain playbook: accounting and the three statements

You grade the accounting questions IB interviewers open with. A strong candidate walks the income statement, then the cash flow statement, then the balance sheet, and states direction and size at each step.

### The mechanics
- **Non-cash expenses (D&A, impairments and write-downs, stock-based comp):** pre-tax income falls by X. Taxes fall by X·t. Net income falls by X·(1-t). On the CFS, start from the lower net income and add back X because no cash left. Cash rises by X·t, the tax saving. On the balance sheet: cash +X·t, the asset is reduced by X (PP&E for depreciation, inventory for write-downs), and retained earnings fall by X·(1-t), so assets and equity both fall by X·(1-t).
- **Stock-based compensation:** same income statement and CFS logic. In equity, retained earnings fall by X·(1-t) while common stock/APIC rises by X, so total equity rises by X·t. Assets also rise by X·t (cash). Candidates often stop at "equity down".
- **Capex:** no income statement effect at purchase. Investing outflow of X, PP&E +X, cash -X. Depreciation comes later. Expensing capex is a classic error.
- **Revenue on credit (accounts receivable):** net income rises by X·(1-t). On the CFS the AR increase is subtracted, so cash changes by X·(1-t) - X = -X·t, the cash taxes paid on income not yet collected. Balance sheet: AR +X, cash -X·t, retained earnings +X·(1-t).
- **Raising debt and paying interest:** interest D·r is deductible, so net income falls by D·r·(1-t). The CFS shows net income in operations and +D in financing. Cash changes by D - D·r·(1-t). Debt +D. Retained earnings -D·r·(1-t).
- **Working capital signs:** an increase in an operating asset (AR, inventory) uses cash; an increase in an operating liability (AP, deferred revenue) is a source of cash.

### What strong vs weak looks like
- Strong: "Depreciation up 10, so pre-tax income is down 10. At 25% tax, net income is down 7.5. On the cash flow statement I start with -7.5 and add back the 10 since it's non-cash, so cash is up 2.5. On the balance sheet cash is +2.5 and PP&E is -10, so assets are down 7.5. On the other side, retained earnings are down 7.5. It balances."
- Weak: "Net income goes down, cash goes up a bit, and it balances." There are no numbers and no mechanism.
- Red flags: says cash falls because of D&A; forgets taxes; says PP&E rises; treats SBC as a cash cost; forgets AR on credit revenue.

### Label keys used in this domain
- `ni`: change in net income.
- `cash`: change in cash, the net change at the bottom of the CFS, equal to the BS cash change.
- `ppe`, `inventory`, `ar`, `debt`: change in that balance sheet line.
- `equity`: change in total shareholders' equity.
