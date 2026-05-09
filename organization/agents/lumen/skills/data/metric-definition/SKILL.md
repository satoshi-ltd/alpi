---
name: metric-definition
description: Define a metric precisely — calculation, source, interpretation, and the decisions it informs — so it means the same thing to everyone
category: data
version: 0.1.0
origin: user
requires_env: []
tools: [db]
keywords: [metric, definition, kpi, measurement, analytics]
created_at: 2026-05-05
---

## When to use
When a new metric is being added to a dashboard or report, when two people use the same metric name but produce different numbers, or when a business question needs a new metric defined before it can be answered. A badly defined metric is worse than no metric — it produces confident wrong answers.

## Output format

**Metric name** — exact name as it will appear in dashboards and reports.

**Plain language definition** — one sentence. What does this metric count or measure?

**Formula**
```
[Metric] = [Numerator] / [Denominator]
```
Or if not a ratio, describe the calculation explicitly.

**Data source** — which table(s), which column(s), which system. A metric without a data source is a concept, not a metric.

**Inclusion and exclusion rules**
- Include: [what qualifies for the numerator/denominator]
- Exclude: [what is explicitly excluded and why — test accounts, internal users, cancelled accounts, etc.]
- Null handling: [how are nulls treated]
- Deduplication: [if a user/account can appear multiple times, how is that resolved]

**Calculation period** — daily / weekly / monthly / rolling 28-day / cohort-based. If time-windowed, specify how the window is defined.

**Interpretation guidance**
- What does a higher value indicate?
- What does a lower value indicate?
- What is the expected range (benchmarks or historical baseline)?
- What changes in the metric should trigger a review or investigation?

**What this metric does not measure** — the adjacent thing someone might think this captures that it actually doesn't.

**Decisions informed by this metric** — at least one specific decision that changes based on the value of this metric. If no decision changes, the metric is vanity.

## Approach
- A metric defined as "number of active users" is not a definition. "Active" must be operationalized: what event, in what time window, with what exclusions.
- Two people producing different numbers from the same metric name means the definition is ambiguous. Fix the definition, not the people.
- The "decisions informed" section is a litmus test for vanity metrics. If the metric goes up 20% and the team's behavior doesn't change, it's not a decision metric.
- Metric definitions must be versioned. When the definition changes, historical comparisons become invalid unless the change is documented.

## State
This skill is the org's metric catalog — the single place every other agent consults to know what NRR, ARR, CAC, etc. actually mean here.

```sql
CREATE TABLE IF NOT EXISTS metrics (
    name         TEXT PRIMARY KEY,             -- 'nrr', 'cac-payback', 'mau'
    description  TEXT NOT NULL,
    formula      TEXT NOT NULL,
    source_table TEXT,
    granularity  TEXT NOT NULL,                -- 'monthly' / 'quarterly' / 'rolling-30d' / 'daily'
    unit         TEXT,                         -- 'USD' / '%' / 'count' / 'days'
    primary_use  TEXT NOT NULL,                -- which decision this metric informs
    owner        TEXT NOT NULL,                -- agent name
    defined_at   TEXT NOT NULL,
    last_revised TEXT
)
```

Other agents query this before reporting numbers — Fern reading NRR, Ledger reading runway-burn, Echo reading CAC. A metric not in this table doesn't have a definition yet; refuse to report on it until defined.
