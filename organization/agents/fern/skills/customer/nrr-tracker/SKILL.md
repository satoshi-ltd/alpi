---
name: nrr-tracker
description: Calculate and interpret Net Revenue Retention — expansion vs. contraction vs. churn — as a health metric
category: customer
version: 0.1.0
origin: user
requires_env: []
tools: [db]
keywords: [nrr, net revenue retention, expansion, contraction, arr]
created_at: 2026-05-05
---

## When to use
At the end of each month or quarter to track cohort revenue health, before a board update that includes retention metrics, or when an investor or board member asks "what is your NRR?" and the team needs to know the answer is accurate.

## Output format

**Period** — month or quarter being measured.

**Starting cohort** — MRR or ARR of the cohort at the start of the period (existing customers only; no new logo revenue).

**Revenue movements in period**

| Movement type | Amount | % of starting cohort |
|---|---|---|
| Expansion (upsell, seat adds, plan upgrades) | | |
| Contraction (downgrades, seat reductions) | | |
| Churn (cancellations) | | |
| **Ending cohort MRR** | | |
| **NRR** | | (ending / starting × 100) |

**NRR interpretation**
- NRR > 120%: strong expansion motion — existing customers are funding growth
- NRR 100–120%: healthy — churn is offset by expansion
- NRR 90–100%: watch — growth depends entirely on new logos
- NRR < 90%: at risk — existing base is shrinking; new logos plug a leaking bucket

**Segment breakdown** — NRR by plan tier or segment if available. Blended NRR can hide a healthy enterprise base masking SMB collapse, or vice versa.

**Leading indicators**
- QBR completion rate (for enterprise): [%]
- Accounts with no expansion in 90+ days: [count and % of base]
- Accounts flagged as at-risk: [count and expected churn MRR]

**Trend** — NRR for the prior three periods to show direction.

## Approach
- NRR is the most honest health metric in a SaaS business. It cannot be inflated by adding logos; it measures whether the base is growing on its own.
- NRR above 100% is not automatic — it requires active expansion motion. Customers don't expand without a reason and a path to do so.
- Segmented NRR is more useful than blended NRR. A 110% blended NRR built on 140% enterprise and 85% SMB is a very different business than a uniform 110%.
- NPS measures feelings. NRR measures behavior. When they diverge, trust NRR.

## State
NRR is a longitudinal metric — the trend across periods is the signal, not any single number.

```sql
CREATE TABLE IF NOT EXISTS nrr_periods (
    period           TEXT PRIMARY KEY,         -- '2026-05', '2026-Q1'
    starting_mrr     REAL NOT NULL,
    expansion        REAL NOT NULL,
    contraction      REAL NOT NULL,
    churn            REAL NOT NULL,
    ending_mrr       REAL NOT NULL,
    nrr_pct          REAL NOT NULL,            -- ending / starting * 100
    computed_at      TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS nrr_segments (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    period           TEXT NOT NULL REFERENCES nrr_periods(period),
    segment          TEXT NOT NULL,            -- 'enterprise' / 'smb' / 'pro'
    starting_mrr     REAL NOT NULL,
    nrr_pct          REAL NOT NULL
)
```

Query the last 4-6 periods to show NRR trend. Segment breakdown surfaces blended NRR hiding a healthy enterprise base masking SMB collapse.
