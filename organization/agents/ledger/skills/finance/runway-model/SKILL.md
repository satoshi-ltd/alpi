---
name: runway-model
description: Build a cash runway projection with multiple burn scenarios and decision triggers
category: finance
version: 0.1.0
origin: user
requires_env: []
tools: [terminal, db]
keywords: [runway, burn rate, cash, forecast, scenario]
created_at: 2026-05-05
---

## When to use
When a hiring decision, spending change, or fundraise timeline needs to be stress-tested against cash position. Also use when current burn rate hasn't been reviewed against assumptions in the last 60 days, or when the board or investors ask "how long do you have?"

## Output format

**Snapshot date** — the date this model reflects. Stale runway models mislead.

**Current state**
- Cash on hand: [amount, as of snapshot date]
- Monthly gross burn: [total cash out, not net]
- Monthly net burn: [gross burn minus revenue]
- Current runway at net burn: [months]

**Scenario table**

| Scenario | Monthly net burn | Runway (months) | Trigger assumption |
|---|---|---|---|
| Base | | | Current headcount + pipeline |
| Upside | | | X new customers by date |
| Downside | | | Revenue flat, headcount +N |
| Stress | | | Revenue -30%, headcount +N |

**Decision triggers** — specific cash-on-hand levels that should force a named decision:
- At $[X]: Begin fundraise or cut burn by Y%
- At $[Y]: Hard hiring freeze
- At $[Z]: Reduce headcount or sell

**Assumptions exposed**
- Revenue trajectory: [measured / estimated / assumed]
- Burn trajectory: [any planned hires or spend changes baked in?]
- Fundraise lead time assumption: [months assumed between start and close]

**Recommendation** — one sentence on whether current runway supports the plan under evaluation, and what changes the answer.

## Approach
- Use gross burn as the primary health metric. Net burn flatters the picture when revenue is lumpy.
- Runway is not a single number. It is a range bounded by your best and worst scenarios.
- Decision triggers must be specific cash amounts, not percentage thresholds. Nobody argues about whether cash is below $800k; they argue about whether "low cash" has been reached.
- Bake in fundraise lead time. Six months of runway when you need six months to raise is zero months of actual optionality.
- Update the model whenever headcount, revenue assumptions, or one-time spend changes. A model updated at last quarter's board meeting is fiction.

## State
Runway models are run repeatedly as inputs change — persist each snapshot to compare assumptions over time.

```sql
CREATE TABLE IF NOT EXISTS runway_snapshots (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    snapshot_date   TEXT NOT NULL,
    cash_on_hand    REAL NOT NULL,
    monthly_gross   REAL NOT NULL,
    monthly_revenue REAL NOT NULL,
    headcount       INTEGER,
    note            TEXT
);
CREATE TABLE IF NOT EXISTS runway_scenarios (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    snapshot_id   INTEGER NOT NULL REFERENCES runway_snapshots(id),
    scenario      TEXT NOT NULL,               -- base / upside / downside / stress
    net_burn      REAL NOT NULL,
    runway_months REAL NOT NULL,
    runs_out_on   TEXT NOT NULL                -- ISO date
)
```

Each `runway-model` execution writes one snapshot + 4 scenario rows. Compare snapshots month-over-month to see whether runway is improving or eroding. The script in `scripts/calculate.py` produces the numbers — `db` persists them.
