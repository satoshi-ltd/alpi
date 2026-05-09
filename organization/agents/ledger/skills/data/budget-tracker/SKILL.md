---
name: budget-tracker
description: Compare actuals against budget assumptions to surface variance, drift, and re-forecast triggers
category: data
version: 0.1.0
origin: user
requires_env: []
tools: [db]
keywords: [budget, actuals, variance, forecast, spend]
created_at: 2026-05-05
---

## When to use
At the close of each month, when a spend category has exceeded its budget by more than 10%, or when the team asks "are we on budget?" and no one has checked recently. Also use when a new hire or vendor contract was added since the last budget review.

## Output format

**Period** — month and year this review covers.

**Variance table**

| Category | Budget | Actual | Variance ($) | Variance (%) | Status |
|---|---|---|---|---|---|
| Payroll | | | | | On track / Over / Under |
| Infrastructure | | | | | |
| Marketing | | | | | |
| Tools & SaaS | | | | | |
| Other | | | | | |
| **Total** | | | | | |

Status: On track (< 5% variance), Watch (5–15%), Over budget (> 15%).

**Assumption drift** — which budget categories were built on assumptions that have since changed?
- [Category]: budgeted assuming X, actual driver is Y

**Re-forecast triggers** — any category where current trajectory changes 3-month outlook by more than 10%:
- [Category]: at current run rate, end-of-quarter actual will be $X vs budget of $Y

**Actions required**
- [Item]: who owns it, by when

**Recommendation** — one sentence on whether the budget is on track and the most important line item to address.

## Approach
- Track actuals against the assumptions behind the budget, not just the totals. A category on budget for the wrong reasons is still a problem.
- Distinguish one-time variances (a vendor invoice paid early) from structural drift (a new recurring cost that wasn't budgeted). Only structural drift needs a re-forecast.
- The re-forecast trigger is the output that matters most. Budget reviews that end with "we're 3% over" but no decision are ceremonies.
- Variance percentages lie when the base is small. A $200 overage on a $1,000 line item is noise. A $200 overage on an $800 item is a signal.

## State
Budget tracking is variance over time — single-period variance is noise; structural drift is signal.

```sql
CREATE TABLE IF NOT EXISTS budget_lines (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    period       TEXT NOT NULL,                -- '2026-05'
    category     TEXT NOT NULL,                -- 'engineering-headcount' / 'cloud' / 'sales' / etc.
    budgeted     REAL NOT NULL,
    actual       REAL NOT NULL,
    variance_pct REAL NOT NULL,                -- (actual - budgeted) / budgeted * 100
    status       TEXT NOT NULL,                -- ok (<5%) / watch (5-15%) / alert (>15%)
    note         TEXT,
    recorded_at  TEXT NOT NULL
)
```

Query `WHERE category = ? ORDER BY period` to see whether a variance is one-time (single period) or structural (3+ periods). Trigger re-forecast when 3+ consecutive `alert` periods on the same category.
