---
name: prd-writer
description: Write a Product Requirements Document that survives contact with engineering — problem-first, scope-bounded, testable
category: productivity
version: 0.1.0
origin: user
requires_env: []
tools: [write_file, db]
keywords: [prd, product, requirements, spec, feature]
created_at: 2026-05-05
---

## When to use
When a feature or product change needs to be specified before engineering picks it up. Also use to evaluate an existing spec for completeness before it enters the backlog.

## Output format

**Problem statement** — one to two sentences. What pain does the user have today, and what is the evidence for it? No solution language here.

**Who is this for** — specific user segment, not "all users". Include what they are trying to accomplish and what they currently do instead.

**Success metric** — one primary metric that moves when this feature works. Must be measurable within a defined time window after launch.

**Scope**
- In scope: bullet list of what this feature does
- Out of scope: bullet list of what this feature explicitly does not do. This section is as important as "in scope".

**User stories**
- As a [user type], I want to [action] so that [outcome]
Each story must have acceptance criteria: the minimum conditions under which this story is done.

**Non-functional requirements** — performance, security, accessibility, internationalisation. Only include what is actually constrained, not a boilerplate list.

**Open questions** — unresolved decisions that block implementation. Each must have an owner and a date by which it will be resolved.

**Kill criterion** — the observable condition that tells us this feature is not working and should be deprecated or changed.

## Approach
- Write the problem statement before anything else. If the problem is not clear, stop and do discovery first.
- "Out of scope" is the highest-leverage section. A spec without explicit exclusions will grow to fill the available engineering time.
- Acceptance criteria must be binary: either the condition is met or it is not. "Feels fast" is not an acceptance criterion. "P95 response time under 300ms" is.
- Open questions that are unowned or undated will not be resolved. Assign each one.

## State
Maintain the feature backlog as the canonical source of what's planned, in flight, and shipped.

Tables live under `state/db.sqlite` (per-skill). Schema is additive-only — `CREATE TABLE IF NOT EXISTS`, never `ALTER` destructively or `DROP`.

```sql
CREATE TABLE IF NOT EXISTS prds (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    feature         TEXT NOT NULL,
    problem         TEXT,
    success_metric  TEXT,
    kill_criterion  TEXT NOT NULL,
    status          TEXT NOT NULL DEFAULT 'draft',
    owner           TEXT,
    target_date     TEXT,
    date            TEXT NOT NULL
)
```

Insert when a PRD is written. Query `WHERE status IN ('in-flight','shipped') AND kill_criterion IS NULL` to surface PRDs that bypassed the kill rule. Update status as the feature progresses.
