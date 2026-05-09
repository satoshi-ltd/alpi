---
name: cohort-analysis
description: Build or interpret a cohort analysis — retention, revenue, or behavior curves — with correct cohort definition and honest interpretation
category: data
version: 0.1.0
origin: user
requires_env: []
tools: [db, terminal]
keywords: [cohort, retention, analysis, lifecycle, behavior]
created_at: 2026-05-05
---

## When to use
When evaluating whether retention is improving over time, when comparing behavior across acquisition channels or plan types, or when a blended metric (average retention, average revenue) is hiding important segment differences. The cohort is the unit; the blended average is the lie.

## Output format

**Cohort definition** — what event marks cohort entry? (signup date, first purchase, first active session). A cohort analysis is only as good as its entry definition.

**Cohort table** — month-by-month retention or revenue per cohort:

| Cohort | Month 0 | Month 1 | Month 2 | Month 3 | Month 6 | Month 12 |
|---|---|---|---|---|---|---|
| Jan 2025 | 100% | X% | X% | X% | X% | X% |
| Feb 2025 | 100% | X% | X% | X% | X% | X% |

**Trend line** — is Month 3 retention improving, declining, or flat across successive cohorts?

**Key observations**
- At what month does the retention curve flatten? (This is the "retained" baseline — customers who reach it tend to stay.)
- Which cohort behaved best and what was different about it (acquisition channel, onboarding, product changes)?
- Which cohort churned fastest and what might explain it?

**Segmented view** — if data allows, split by plan tier, acquisition source, or company size. Blended cohorts hide the story.

**Metric interpretation** — distinguish:
- Retention cohort: % of users still active
- Revenue cohort: % of MRR retained (different from users — a smaller number of high-value accounts can produce misleading user retention)

**Caveats** — what this cohort view doesn't show (e.g., reactivations counted as retained, multi-seat accounts counted as one).

## Approach
- Cohort analysis answers "is the business getting better at retaining customers?" not "how many customers do we have?"
- Define "active" before building the analysis. Login once in 30 days is not the same as performing a value-generating action once in 30 days.
- A retention curve that never flattens is a churn-to-zero business. A curve that flattens at 30% at month 3 means one in three acquired customers will stay indefinitely — that is what you're building for.
- Improving month-over-month cohort retention is the most important product and CS signal available. If each new cohort retains better than the last, the flywheel is working.

## Data
Load cohort data into the skill db for persistent analysis. Use `terminal` + `sqlite3` for complex aggregations or when working with CSV files the user provides. Store cohort results in db so trends are visible across periods.

## Scripts
`scripts/cohort_table.py` pivots long-format cohort data (cohort, period_offset, value) into a cohort × period grid. It accepts CSV via `--input` or stdin and outputs either raw values (`--mode raw`) or retention % vs each cohort's M0 baseline (`--mode pct`).

```
python <absolute_path> --input cohorts.csv --mode pct
```

Use this when the data warehouse exports cohort events in long format — pivoting by hand introduces transcription errors. The script is schema-agnostic: any (cohort, period_offset, value) triples work, whether the metric is retention, revenue, sessions, or feature usage.
