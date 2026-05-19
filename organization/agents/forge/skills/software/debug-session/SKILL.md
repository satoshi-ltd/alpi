---
name: debug-session
description: Diagnose a bug systematically — reproduce, isolate, hypothesize, verify — without guessing
category: software
version: 0.1.0
origin: user
requires_env: []
tools: [read_file, search, terminal, db]
keywords: ['debug', 'bug', 'reproduce', 'root-cause', 'diagnosis']
created_at: 2026-05-05
---

## When to use
When a bug has been reported or observed and the root cause is not immediately clear. Also use when a fix has been applied but the bug persists or recurs, suggesting the wrong cause was addressed.

## Output format

**Bug description** — what is happening vs. what should be happening. Be precise about the symptom, not the assumed cause.

**Reproduction steps**
1. Exact preconditions (data state, environment, inputs)
2. Exact steps
3. Observed result
4. Expected result

Can this be reproduced? [Yes / No / Intermittent]. If intermittent, note frequency and any correlation (time, load, user type).

**Isolation**
- What is the smallest input or code path that triggers the bug?
- What has been ruled out? (List what was tried and what it confirmed or denied.)
- Is the bug in: [input handling / business logic / data layer / external dependency / environment]?

**Hypotheses** (ordered by probability)
1. [Most likely cause] — evidence: [what supports this]
2. [Alternative] — evidence: [what supports this]

**Verification plan** — for the top hypothesis, what is the specific test or log output that would confirm or deny it?

**Fix** — once root cause is confirmed:
- What changed and why
- What edge cases the fix does not cover (be honest)
- Whether a regression test was added

## Approach
- Reproduce before diagnosing. "I think I know what's wrong" without a reproducible case leads to fixing the wrong thing.
- Distinguish symptoms from causes. The error message is a symptom. The unchecked null two frames up is the cause.
- Rule things out explicitly. "X is not the cause because I verified Y" is as valuable as finding the cause.
- The fix is only complete when a regression test prevents the same bug from returning silently.
- If a fix takes more than 30 minutes to verify, the hypothesis was probably wrong. Go back to isolation.

## State
Bug patterns repeat. A queryable debug log turns one-off fixes into compounding knowledge.

Tables live under `state/db.sqlite` (per-skill). Schema is additive-only — `CREATE TABLE IF NOT EXISTS`, never `ALTER` destructively or `DROP`.

```sql
CREATE TABLE IF NOT EXISTS debug_log (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    symptom       TEXT NOT NULL,
    root_cause    TEXT NOT NULL,
    fix           TEXT NOT NULL,
    files_touched TEXT,
    pattern_tag   TEXT,                    -- e.g. 'race-condition', 'null-deref', 'config-drift'
    date          TEXT NOT NULL
)
```

Before diagnosing, query `WHERE pattern_tag = ? OR symptom LIKE ?` to check for prior incidents with similar signatures. Insert after every resolved session — symptom + cause + fix in plain language.
