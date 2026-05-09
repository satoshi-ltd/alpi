---
name: bug-report
description: Write a structured bug report with exact reproduction steps, environment, severity, and expected vs actual behavior
category: software
version: 0.1.0
origin: user
requires_env: []
tools: [write_file, db]
keywords: [bug report, defect, issue, reproduction, severity]
created_at: 2026-05-05
---

## When to use
When a defect has been observed and needs to be communicated to engineering for investigation and fix. A good bug report cuts the time to resolution by half. A bad one results in "cannot reproduce" and round-trips that delay fixes.

## Output format

**Title** — [Component/Area] Short description of what's wrong. Avoid generic titles ("Something is broken"). Example: "[Checkout] Order total is wrong when coupon is applied to a cart with a free item."

**Severity** — P0 (data loss, security, system down) / P1 (core feature broken, no workaround) / P2 (degraded behavior, workaround exists) / P3 (cosmetic, low frequency)

**Environment**
- Platform / OS / browser version
- App version or commit hash (if available)
- Account type or user state (e.g., "free plan, no payment method on file")

**Steps to reproduce**
1. [Exact starting state]
2. [Exact action]
3. [Next exact action]
…

**Expected behavior** — what should happen.

**Actual behavior** — what actually happens. Be specific; include error messages verbatim.

**Evidence** — screenshot, screen recording, log excerpt, or network trace. Attach or link.

**Frequency** — always / intermittent (X% of attempts) / once observed.

**Workaround** — if one exists, describe it so affected users can be unblocked while the fix lands.

## Approach
- Reproduce the bug yourself before writing the report. "User says it's broken" is not a bug report.
- The steps to reproduce are the most important section. If engineering can't follow them and hit the bug, the report is incomplete.
- Severity is not urgency. Urgency is a business decision. Severity is a technical one. Don't conflate them.
- Include the environment section even when it seems obvious. Bugs that only appear in specific environments take days longer to diagnose without this.
- "Sometimes it doesn't work" is a description of intermittent bugs. Log a timestamp, session ID, or any other correlation signal that engineering can query.

## State
Persist every bug in the skill db. On first use, initialise the schema:

```sql
CREATE TABLE IF NOT EXISTS bugs (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    title    TEXT NOT NULL,
    severity TEXT NOT NULL,
    status   TEXT NOT NULL DEFAULT 'open',
    steps    TEXT,
    env      TEXT,
    created  TEXT NOT NULL
)
```

Insert each new report. Query with `SELECT * FROM bugs WHERE status = 'open' ORDER BY severity, created` to produce a live bug register. Update `status` to `fixed` or `wont-fix` as issues are resolved.
