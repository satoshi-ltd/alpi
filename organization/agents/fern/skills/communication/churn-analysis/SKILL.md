---
name: churn-analysis
description: Diagnose churn — identify when it starts, what triggers it, and which interventions are supported by evidence
category: communication
version: 0.1.0
origin: user
requires_env: []
tools: [db, terminal]
keywords: ['churn', 'retention', 'cancellation', 'offboarding', 'customer-success']
created_at: 2026-05-05
---

## When to use
When churn rate has increased or is above benchmark, when a cohort of customers has churned unexpectedly, or when the team needs to understand where in the lifecycle customers are leaving. Also use before building a retention playbook — diagnose before prescribing.

## Output format

**Period under analysis** — cohort or date range.

**Churn metrics**
- Gross logo churn: % of customers who cancelled in period
- Gross revenue churn: % of MRR lost from cancellations
- Net revenue churn: gross revenue churn minus expansion in period
- Where is churn concentrated? (segment, cohort, plan, use case)

**When churn happens** — median time to cancel from signup, broken down by segment if possible. Churn that happens in month 1 is an onboarding problem. Churn in month 6 is a value problem. Churn in month 18 is a competitive or contract problem.

**Exit signal analysis** — from exit surveys, cancellation flows, or customer conversations:
- Stated reasons (caution: these are post-rationalization — note frequency but treat as weak signal)
- Behavioral signals that preceded churn (login frequency drop, support ticket volume, feature abandonment)

**Early warning indicators** — which behaviors in the first 30–60 days predict churn with measurable correlation?

**Cohort comparison** — do customers who churned behave differently from retained customers in their first 30 days? What's the earliest divergence point?

**Intervention hypotheses** — one or two specific interventions supported by the data above, with a measurable success criterion.

## Approach
- Churn starts at onboarding, not at cancellation. The cancellation date is when the customer formalized a decision they made weeks or months earlier.
- Exit surveys measure why customers say they left, not why they actually left. Treat them as one signal among many, weighted less than behavioral data.
- Segment before concluding. A blended churn rate obscures that SMBs are churning fast while enterprise is retained. These are different problems with different solutions.
- Proposed interventions must be testable. "Improve onboarding" is not an intervention. "Send a video walkthrough at day 3 to accounts that haven't completed setup" is.

## State
Churn analysis requires cohorts tracked over time — the diagnostic value is in the curve, not the snapshot.

```sql
CREATE TABLE IF NOT EXISTS cohorts (
    cohort_label    TEXT PRIMARY KEY,          -- '2026-Q1', '2026-05', etc.
    starting_count  INTEGER NOT NULL,
    started_at      TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS churn_events (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_ref   TEXT NOT NULL,
    cohort_label   TEXT NOT NULL REFERENCES cohorts(cohort_label),
    churn_date     TEXT NOT NULL,
    months_active  INTEGER,
    mrr_lost       REAL,
    reason         TEXT,                       -- price / fit / competitor / outcome / unknown
    onboarding_completed INTEGER                -- 0 or 1 — leading indicator
)
```

Group by `reason` to surface dominant churn drivers. Cohort retention curves: count `churn_events` per `months_active` bucket per cohort.

## Scripts
`scripts/cohort_curve.py` produces the retention curve across all cohorts in the db. Doing this manually across N cohorts × 12 months is error-prone — use the script as the canonical calculation. View the file with `skill(action='view', file='scripts/cohort_curve.py')` to get the absolute path, then run via `terminal`:

```
python3 <absolute_path> --db <skill state path>/db.sqlite --max-months 12
```

The output is a markdown-friendly table showing % retained at each month per cohort. Use the curve shape — not single-number retention — to diagnose where churn happens.
