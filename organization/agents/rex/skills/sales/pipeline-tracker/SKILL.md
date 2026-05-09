---
name: pipeline-tracker
description: Review a sales pipeline for deal health, stall signals, and forecast accuracy
category: sales
version: 0.1.0
origin: user
requires_env: []
tools: [terminal, db]
keywords: [pipeline, forecast, crm, deal review, sales]
created_at: 2026-05-05
---

## When to use
At weekly pipeline reviews, before a board or investor update with revenue projections, or when a quota is at risk and the team needs to triage which deals to prioritize. Also use when a deal has been sitting in the same stage for more than two weeks.

## Output format

**Pipeline snapshot** — date, total pipeline value, and weighted forecast.

**Deal review table**

| Deal | Stage | ARR | Close date | Last activity | Next step | Health |
|---|---|---|---|---|---|---|

Health: Green (on track) / Yellow (stalled or missing next step) / Red (no discovery done, close date past, or contact gone dark)

**Stall signals** — deals yellow or red with the specific reason:
- No next step defined
- Close date passed without update
- Last contact more than 14 days ago
- Discovery not completed (we're proposing to a problem we don't understand)
- Champion has left or gone quiet

**Forecast accuracy check**
- What closed last quarter vs. what was forecast at this point?
- Are there systematic biases (consistently optimistic on close dates, consistently overestimating deal size)?

**Actions required**
- [Deal]: [specific action, owner, by when]

**Forecast call** — what is likely to close this period, with a confidence level per deal.

## Approach
- A stale deal is not a pipeline — it is a list of wishes. Deals without a next step owned by the prospect (not the seller) are stuck.
- Close date accuracy is a leading indicator of forecast hygiene. A team that consistently pushes close dates by two weeks has a discipline problem, not a market problem.
- Discovery gap is the most common reason deals stall after demo. The prospect isn't convinced because the seller didn't understand their actual problem.
- Pipeline reviews should produce actions, not reports. A review that ends with "the pipeline looks solid" without anyone being held to a specific next step is a meeting, not a review.

## State
Pipeline is a system — tracking deals over time reveals stage-conversion rates, forecast accuracy, and stall patterns.

```sql
CREATE TABLE IF NOT EXISTS deals (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    prospect        TEXT NOT NULL,
    stage           TEXT NOT NULL,             -- discovery / demo / proposal / negotiation / closed-won / closed-lost
    arr             REAL NOT NULL,
    close_date      TEXT NOT NULL,
    last_activity   TEXT NOT NULL,
    next_step       TEXT,
    health          TEXT NOT NULL,             -- green / yellow / red (computed by scripts/score.py)
    health_reason   TEXT,
    created_at      TEXT NOT NULL,
    last_reviewed   TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS deal_history (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    deal_id     INTEGER NOT NULL REFERENCES deals(id),
    field       TEXT NOT NULL,                 -- 'stage' / 'close_date' / 'arr'
    old_value   TEXT,
    new_value   TEXT,
    changed_at  TEXT NOT NULL
)
```

Track `deal_history` on stage and close-date changes — repeated close-date pushes are the strongest stall signal. The scoring script in `scripts/score.py` computes `health`; pipeline-tracker writes the row, the script feeds it numbers.
