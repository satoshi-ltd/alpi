---
name: automation-script
description: Specify and plan an automation for a manual process — with scope, trigger, error handling, and rollback defined before writing code
category: productivity
version: 0.1.0
origin: user
requires_env: []
tools: [terminal, read_file, search, write_file, edit_file, db]
keywords: [automation, script, workflow, integration, ops]
created_at: 2026-05-05
---

## When to use
When a manual process is being considered for automation — before any code is written. Also use to audit an existing automation that is brittle, failing silently, or poorly documented. A poorly specified automation is worse than the manual process it replaces.

## Output format

**Process being automated** — name of the manual process and why it's a candidate for automation (frequency, error rate, time cost).

**Automation trigger**
- Scheduled: [cron expression or frequency]
- Event-driven: [what event fires it]
- Manual: [who initiates and how]

**Inputs** — what data or state does the automation depend on? Where does it come from?

**Steps** — what the automation does, in order:
1. [Action]
2. [Decision point: if X, do Y; if not, do Z]
3. ...

**Outputs and side effects** — what does the automation produce? What external systems does it write to or affect?

**Error handling**
- For each step where failure is likely: what does the automation do when it fails?
- Does it retry? How many times and with what backoff?
- Does it alert a human? How and who?
- Does it fail silently? (This is almost never correct.)

**Rollback** — if the automation runs partially and fails, what state is left behind? Can it be undone?

**Idempotency** — if the automation runs twice on the same input, is the result the same as running it once? If not, why not?

**Monitoring** — how will a human know the automation is running correctly? (Not just "it didn't error" — does it produce the expected output?)

**Human override** — what is the procedure to skip the automation and do the step manually if it breaks in production?

## Approach
- Automate only after the manual process is stable and well-understood. Automating a process you don't fully understand produces automated mistakes.
- Silent failure is the most dangerous failure mode in automation. An automation that fails without alerting anyone is worse than no automation.
- Idempotency is not optional for automations that write to external systems. Double-processing a payment or duplicate-sending an email is a reliability failure.
- Rollback must be thought through before the automation runs in production, not after the first failure.

## State
Track every automation written so failures surface and dead automations are pruned.

```sql
CREATE TABLE IF NOT EXISTS automations (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    name          TEXT NOT NULL UNIQUE,
    trigger       TEXT NOT NULL,
    script_path   TEXT NOT NULL,
    last_run      TEXT,
    last_failure  TEXT,
    failure_count INTEGER NOT NULL DEFAULT 0,
    status        TEXT NOT NULL DEFAULT 'active'
)
```

Insert when an automation is written. Update `last_run` / `last_failure` from observability. Query `WHERE status = 'active' AND (last_run IS NULL OR last_run < date('now', '-30 days'))` to find dead automations.
