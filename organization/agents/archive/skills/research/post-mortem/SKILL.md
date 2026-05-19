---
name: post-mortem
description: Write a blameless post-mortem that identifies root causes, systemic factors, and follow-up actions — not individuals to fault
category: research
version: 0.1.0
origin: user
requires_env: []
tools: [write_file, search, db]
keywords: [post-mortem, incident, retrospective, root-cause, learning]
created_at: 2026-05-05
---

## When to use
After an incident, outage, significant bug, failed launch, or missed objective — any event where the outcome was materially worse than expected and the team needs to learn from it. The goal is to extract the learning, not assign the blame.

## Output format

**Incident title** — descriptive, without blame: "Checkout service outage — 2026-04-12" not "Dev pushed broken code."

**Summary** — two sentences: what happened and what the impact was.

**Timeline** — chronological sequence of events:

| Time | Event | Who noticed / who acted |
|---|---|---|
| HH:MM | [What happened] | |

**Impact**
- Duration: [from first symptom to resolution]
- Scope: [who / what was affected, quantified where possible]
- Customer impact: [number of users, revenue affected, SLA breach]

**Root cause analysis** — use "5 Whys" or equivalent:
1. Why did [symptom] occur? → [cause 1]
2. Why did [cause 1] occur? → [cause 2]
…until a systemic or process-level cause is reached.

Do not stop at the first human action. "An engineer pushed a bad deploy" is not a root cause — it is a symptom of a deploy process without adequate safeguards.

**Contributing factors** — systemic conditions that made this incident more likely or more severe:
- [Factor]: [how it contributed]

**What went well** — responses or safeguards that limited the impact.

**Follow-up actions**

| Action | Owner | Due date | Priority |
|---|---|---|---|
| | | | P0 / P1 / P2 |

P0: prevents recurrence. P1: reduces likelihood or impact. P2: improves detection or response.

## Approach
- Blameless means blaming the system, not the person. The question is not "who made the mistake" but "what conditions made this mistake likely?"
- The timeline is the foundation. Reconstruct it from logs, not from memory. Memory compresses and rearranges events.
- Root cause analysis must reach a systemic level. If every root cause is "human error," the post-mortem is just a record of what happened — not a learning document.
- Follow-up actions with no owner and no due date are wishes, not commitments.
- "What went well" is mandatory. It identifies the safeguards worth keeping and signals that the review is diagnostic, not punitive.

## State
Persist post-mortems so patterns and recurrence become visible.

Tables live under `state/db.sqlite` (per-skill). Schema is additive-only — `CREATE TABLE IF NOT EXISTS`, never `ALTER` destructively or `DROP`.

```sql
CREATE TABLE IF NOT EXISTS post_mortems (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    incident_title  TEXT NOT NULL,
    severity        TEXT NOT NULL,             -- sev1 / sev2 / sev3 / sev4
    incident_date   TEXT NOT NULL,
    duration_min    INTEGER,
    root_cause      TEXT NOT NULL,
    pattern_tag     TEXT,                      -- e.g. 'config-drift', 'capacity', 'human-error'
    detection_min   INTEGER                    -- minutes from incident start to detection
);
CREATE TABLE IF NOT EXISTS action_items (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    post_mortem_id  INTEGER NOT NULL REFERENCES post_mortems(id),
    action          TEXT NOT NULL,
    owner           TEXT NOT NULL,
    due_date        TEXT,
    status          TEXT NOT NULL DEFAULT 'open'   -- open / done / abandoned
)
```

Aggregate by `pattern_tag` to detect recurring root-cause families. Query open `action_items` with past-due `due_date` for accountability.
