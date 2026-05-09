---
name: adr-writer
description: Write an Architecture Decision Record capturing context, decision, alternatives, and consequences
category: software
version: 0.1.0
origin: user
requires_env: []
tools: [write_file, db]
keywords: [adr, architecture, decision, record, technical]
created_at: 2026-05-05
---

## When to use
Any time a significant technical decision is made in the Architecture workgroup: technology choice, system boundary change, infrastructure direction, data model change, or security posture decision. "Significant" means hard to reverse or with broad impact across services.

## Output format

**ADR-[number]: [short title]**
Date: [ISO]
Status: proposed / accepted / deprecated / superseded by ADR-[N]

**Context**
The forces at play — technical constraints, operational requirements, team capabilities, current system state. Two to four sentences. This is the "why now" for the technical decision.

**Decision**
One to two sentences. What we will do. Active voice: "We will use X" not "X was chosen".

**Alternatives considered**
- [Option A] — [one sentence on what it is and why we did not choose it]
- [Option B] — ...
At least two alternatives. If only one option was considered, the decision was not made — it was assumed.

**Consequences**
- Positive: [what this decision enables or improves]
- Negative: [what this decision makes harder or more expensive]
- Neutral: [changes that are neither good nor bad but the team needs to know]

**Validation**
How we will know this decision is working. Specific observable signal, not "we'll monitor it".

**Rollback**
If the decision proves wrong, what is the path to reverse or mitigate? "We can't" is a valid answer but it must be stated explicitly.

## Approach
- The context section is the most important. A future engineer reading this ADR needs to understand the world as it was when the decision was made, not the world as it is now.
- Name the rejected alternatives honestly. Do not write them as strawmen — give each a fair hearing and explain specifically why it lost.
- Consequences must include negatives. An ADR with only upsides is marketing, not engineering.
- Write for Forge and Sentinel: the people who will implement and test this decision, not for a conference talk.

## State
Maintain the ADR index in the skill db. On first use, initialise:

```sql
CREATE TABLE IF NOT EXISTS adrs (
    number  INTEGER PRIMARY KEY,
    title   TEXT NOT NULL,
    status  TEXT NOT NULL DEFAULT 'proposed',
    date    TEXT NOT NULL
)
```

Before writing a new ADR, query `SELECT COALESCE(MAX(number), 0) + 1 FROM adrs` to get the next sequential number. Insert a row after writing the file. Update `status` when the Architecture workgroup closes the task.
