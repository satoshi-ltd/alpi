---
name: sop-writer
description: Write a Standard Operating Procedure that someone can follow without asking questions — with decision points explicit, not assumed
category: operations
version: 0.1.0
origin: user
requires_env: []
tools: [read_file, write_file, db]
keywords: [sop, procedure, operations, documentation, process]
created_at: 2026-05-05
---

## When to use
When a process is done repeatedly by different people and the result varies based on who does it, when a new team member needs to be onboarded to a recurring task, or when a process needs to be automated and must be documented before it can be scripted.

## Output format

**SOP name** — descriptive, verb-first: "Process monthly payroll" not "Payroll SOP."

**Purpose** — one sentence. What outcome does this procedure produce?

**Owner** — who is responsible for this SOP being current and followed?

**Trigger** — what event starts this procedure? (scheduled time, incoming request, system event)

**Prerequisites** — what must be true or ready before starting?
- Access requirements
- Tools or systems required
- Data or inputs needed
- Prior steps that must be complete

**Steps**

Numbered, imperative:
1. [Exact action] — [where to do it / what to click / what to enter]
2. ...

For decision points:
- If [condition A]: go to step X
- If [condition B]: go to step Y

**Verification** — how does the person doing the procedure know it was completed correctly?

**What to do when it goes wrong** — for the most common failure modes:
- [Failure mode]: [what to do, who to escalate to]

**Version and last reviewed** — date and reviewer. An SOP with no review date is a SOP that has drifted from reality.

## Approach
- Write for the person doing it for the first time. If the procedure requires judgment that isn't documented, it will produce inconsistent results.
- Decision points must be explicit. "Handle exceptions appropriately" is not a step — it is where the SOP breaks.
- The verification step is what converts a procedure into a closed loop. Without it, there's no way to know if the procedure worked.
- SOPs that are too long won't be read. If a procedure genuinely requires 30 steps, it's two procedures. Split it.
- The "what to do when it goes wrong" section is the most valuable part and the most commonly omitted. Failure modes are predictable — document them before they happen.

## State
SOPs go stale. Track ownership and review schedule so staleness surfaces automatically.

```sql
CREATE TABLE IF NOT EXISTS sops (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    title         TEXT NOT NULL UNIQUE,
    path          TEXT NOT NULL,
    owner         TEXT NOT NULL,
    version       INTEGER NOT NULL DEFAULT 1,
    last_reviewed TEXT NOT NULL,
    next_review   TEXT NOT NULL,
    status        TEXT NOT NULL DEFAULT 'active'  -- active / deprecated
)
```

Insert on write. Run `WHERE next_review <= date('now') AND status = 'active'` periodically to surface SOPs needing review. Bump `version` and reset `last_reviewed` on each revision.
