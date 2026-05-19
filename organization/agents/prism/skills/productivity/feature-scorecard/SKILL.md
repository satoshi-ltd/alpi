---
name: feature-scorecard
description: Score a feature candidate on user value, build cost, strategic fit, and confidence to produce a prioritization recommendation
category: productivity
version: 0.1.0
origin: user
requires_env: []
tools: [db]
keywords: [feature, prioritization, score, roadmap, backlog]
created_at: 2026-05-05
---

## When to use
When the Roadmap workgroup needs to compare feature candidates for prioritization, or when a single feature needs a clear recommendation on whether to build it now, later, or not at all.

## Output format

**Feature** — name and one-sentence description.

**Scores** (1 = low, 2 = medium, 3 = high)

| Dimension | Score | Evidence |
|---|---|---|
| User value | | What user problem does this solve and how severely? |
| Reach | | How many users are affected? |
| Build cost | | Estimated engineering effort (invert: 3 = cheap, 1 = expensive) |
| Strategic fit | | How directly does this serve the current strategy? |
| Confidence | | How well do we understand the problem and solution? |

**Weighted score** — (User value × 2) + Reach + (Build cost × 1.5) + Strategic fit + Confidence. Show the arithmetic.

**Recommendation** — build now / build next quarter / defer / kill, with a one-sentence reason.

**The case against** — the strongest argument for not building this. If you cannot make a case against it, you have not thought about it hard enough.

**Dependencies** — what must be true before this can be built (other features, team capacity, data, third-party APIs).

## Approach
- Evidence beats intuition. If a score is based on a hunch, label it as such and weight it accordingly.
- The "confidence" dimension is underused. A high-value, low-confidence feature is a research task, not a build task.
- The case against is mandatory. Features that look obviously good on a scorecard are usually missing a hidden cost or assumption.
- Do not let the score override judgment. The scorecard surfaces tradeoffs; the PM makes the call.

## State
Persist every score so feature priority can be compared and re-evaluated.

Tables live under `state/db.sqlite` (per-skill). Schema is additive-only — `CREATE TABLE IF NOT EXISTS`, never `ALTER` destructively or `DROP`.

```sql
CREATE TABLE IF NOT EXISTS scorecards (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    feature         TEXT NOT NULL,
    user_value      INTEGER NOT NULL,   -- 1..5
    build_cost      INTEGER NOT NULL,   -- 1..5 (5 = expensive)
    strategic_fit   INTEGER NOT NULL,   -- 1..5
    confidence      INTEGER NOT NULL,   -- 1..5
    weighted_score  REAL,               -- (user_value * strategic_fit * confidence) / build_cost
    decision        TEXT,
    date            TEXT NOT NULL
)
```

Compute `weighted_score` on insert. Sort the backlog with `ORDER BY weighted_score DESC` to produce the next-up list. Re-score when assumptions change rather than overwriting — track score drift.
