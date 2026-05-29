---
name: discovery-call
description: Prepare for or debrief a discovery call — surface the real problem, evaluate fit, and define the next step
category: communication
version: 0.1.0
origin: user
requires_env: []
tools: [db]
keywords: ['discovery', 'sales-call', 'qualification', 'fit', 'pipeline']
created_at: 2026-05-05
---

## When to use
Before a discovery call (preparation) or after one (debrief). Also use when reviewing a pipeline opportunity to determine whether discovery was actually done or just assumed.

## Output format

**Mode** — Pre-call preparation / Post-call debrief.

**For pre-call preparation:**

*Account context*
- Company: size, industry, known pain points from public sources
- Contact: role, likely priorities, any shared context
- Why now: what trigger event (funding, hiring, regulatory change, competitor move) makes this a good time to call?

*Research gaps* — what do you not know that you need to know before proposing anything?

*Primary questions* — five or fewer, focused on uncovering problem severity, not product fit:
1. [Question that reveals the pain]
2. [Question that quantifies the cost of the pain]
3. [Question that surfaces who owns the decision]
4. [Question that tests timeline and urgency]
5. [Question that surfaces what they've already tried]

*Disqualification criteria* — conditions under which you walk away without a follow-up.

**For post-call debrief:**

*What was confirmed*
- Pain: [specific, in their words]
- Quantified cost of the pain: [$ / time / risk — or "not established"]
- Decision process: [who decides, who influences, timeline]
- Current solution: [what they're using now and why it's not enough]

*Fit assessment*
- Strong fit: [which aspects of our solution match their problem precisely]
- Weak fit or risk: [what they need that we don't do well]
- Disqualifiers: [any signals this is not the right deal]

*Next step* — specific, time-bound, and owned by one person. "I'll follow up" is not a next step.

## Approach
- Discovery is diagnosis. A doctor who prescribes before diagnosing is malpractice. A seller who demos before discovering is the same.
- The goal of discovery is not to find reasons to sell — it is to find out whether selling is appropriate.
- "What have you already tried?" is the most under-asked discovery question. The answer tells you why previous solutions failed and what bar you're being held to.
- An honest disqualification on a bad-fit deal is more valuable than a slow loss. Bad-fit customers churn, complain, and consume support disproportionately.

## State
Discovery patterns repeat across prospects — persist call notes so fit signals and recurring problems surface.

Tables live under `state/db.sqlite` (per-skill). Schema is additive-only — `CREATE TABLE IF NOT EXISTS`, never `ALTER` destructively or `DROP`.

```sql
CREATE TABLE IF NOT EXISTS calls (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    prospect            TEXT NOT NULL,
    contact             TEXT,
    call_date           TEXT NOT NULL,
    problem_articulated TEXT,                  -- their actual stated problem
    fit_score           INTEGER,               -- 1..5
    objections_raised   TEXT,                  -- comma-separated tags
    next_step           TEXT,
    next_step_owner     TEXT,                  -- 'us' or 'them' (them is healthier)
    outcome             TEXT                   -- 'progressed' / 'no-fit' / 'ghosted' / 'stalled'
)
```

Group by `problem_articulated` to find recurring pain — it's product feedback. Track ratio of `next_step_owner = 'them'` over time as discovery quality signal.
