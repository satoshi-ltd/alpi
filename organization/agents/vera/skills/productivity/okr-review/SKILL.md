---
name: okr-review
description: Review OKR progress, surface misalignment between objectives and current work, and recommend corrections
category: productivity
version: 0.1.0
origin: user
requires_env: []
tools: [read_file, db]
keywords: [okr, objectives, review, alignment, quarterly]
created_at: 2026-05-05
---

## When to use
When reviewing quarterly OKR progress — at mid-quarter check-ins, end-of-quarter reviews, or when there is a suspicion that current priorities have drifted from stated objectives.

## Output format

For each Objective:

**Objective** — restate it as written.

**Status** — on track / at risk / off track. No "in progress" — that is not a status.

**Key Results progress**
- KR1: [target] → [current] — [on track / at risk / off track]
- KR2: ...

**Gap analysis** — what is the delta between where we are and where we said we would be. Be specific: name the KR, the number, the shortfall.

**Root cause** — one sentence per KR that is at risk or off track. Distinguish between "we chose to deprioritize this" (a decision) and "we underestimated the work" (a planning error) and "the assumption was wrong" (a hypothesis failure).

**Recommendation** — for each at-risk or off-track item: (a) adjust the target, (b) reallocate effort, or (c) drop the KR and explain why. No "we will work harder".

## Approach
- OKR reviews are diagnostic tools, not performance reviews. The goal is to update the plan, not to assign blame.
- Treat a KR at 70% with a clear path to 100% differently from one at 70% with no path.
- Surface misalignment explicitly: if the team's actual work does not map to any stated OKR, name it. Either the OKRs are wrong or the work is wrong.
- Never smooth numbers. A KR at 45% is not "almost halfway".

## State
Track objectives and key results across periods so review is genuinely longitudinal.

Tables live under `state/db.sqlite` (per-skill). Schema is additive-only — `CREATE TABLE IF NOT EXISTS`, never `ALTER` destructively or `DROP`.

```sql
CREATE TABLE IF NOT EXISTS objectives (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    period    TEXT NOT NULL,
    objective TEXT NOT NULL,
    owner     TEXT,
    status    TEXT NOT NULL DEFAULT 'active'
);
CREATE TABLE IF NOT EXISTS key_results (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    objective_id  INTEGER NOT NULL REFERENCES objectives(id),
    description   TEXT NOT NULL,
    target        REAL,
    current       REAL,
    last_updated  TEXT
)
```

On review, query progress per period; flag KRs with no `last_updated` in 14+ days as stale.
