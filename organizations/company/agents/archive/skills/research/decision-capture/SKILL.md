---
name: decision-capture
description: Record a decision with context, options, rationale, and dissent so it can be understood and challenged later
category: research
version: 0.1.0
origin: user
requires_env: []
tools: [db, write_file]
keywords: [decision, record, rationale, history, documentation]
created_at: 2026-05-05
---
## Scope
This skill is the **canonical decision archive** for the org. Every workgroup `#done` produces an entry here, regardless of which agent or workgroup made the call.

**Use this skill** when:
- A workgroup task closes with a decision (any of the four: roadmap / architecture / growth / customers — or ad-hoc)
- An agent has written a decision artifact (`vera/decision-record`, `zeta/adr-writer`, etc.) and it needs to enter the org-wide index
- Querying past decisions across domains: "what did we decide about X", "what's been overturned"

**Do NOT use this for** writing the decision in the first place — that's the job of the originating skill (`vera/decision-record` for strategy, `zeta/adr-writer` for architecture, etc.). This skill captures the record in the canonical index, links it to the workgroup, and makes it queryable. It is downstream of the writing skills, not a substitute for them.

The `decisions` table is the single source of truth across the org. Other skills' output flows here.

## When to use
When any significant decision is made — product, strategic, technical, organizational — that will affect how people work or what the company builds. Decisions that take more than 30 minutes to make or that affect more than one team warrant a capture. Also use retroactively when a past decision is being re-litigated and no one can remember what was decided or why.

## Output format

**Decision** — a specific, binary statement of what was decided. "We will use Postgres" not "We discussed database options."

**Date** — when the decision was made.

**Decision maker** — who made it. Group decisions produce no accountability.

**Context** — what made this decision necessary now? What would have happened if it were deferred?

**Options considered**

For each option:
- What it was
- Why it was a credible choice
- Why it was not selected

**Rationale** — the specific reasoning that led to the decision made. Not a list of virtues of the chosen option — the reasoning that made it better than the alternatives.

**Dissent recorded** — who disagreed and what their argument was. This is not for judgment — it's for the future reader who may discover the dissenting view was correct. Capturing disagreement prevents the org from pretending there was consensus when there wasn't.

**Assumptions** — what must be true for this decision to remain correct? If one of these changes, the decision should be revisited.

**Trigger for revisit** — the specific condition that would make this decision worth reconsidering.

## Approach
- A decision capture is not meeting minutes. It captures the why, not the discussion.
- "We decided to do X because it's best" is not a rationale. "We decided X over Y because Y would have required a 6-month migration we cannot afford this quarter, and X gives us the same capability for the current problem" is.
- Dissent captured honestly is a competitive advantage. Teams that suppress disagreement in documentation are surprised by the same arguments in the next planning cycle.
- Assumptions are what make decisions time-bound. A decision made when the team was 5 people may not be right at 50 people. Write down the assumptions; they become the trigger for revisit.

## State
The canonical decision archive. Every workgroup `#done` produces an entry here.

Tables live under `state/db.sqlite` (per-skill). Schema is additive-only — `CREATE TABLE IF NOT EXISTS`, never `ALTER` destructively or `DROP`.

```sql
CREATE TABLE IF NOT EXISTS decisions (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    title           TEXT NOT NULL,
    decision        TEXT NOT NULL,
    rationale       TEXT NOT NULL,
    workgroup       TEXT NOT NULL,             -- roadmap / architecture / growth / customers / ad-hoc
    alternatives    TEXT,                      -- rejected options + why
    dissent         TEXT,                      -- minority view if any
    status          TEXT NOT NULL DEFAULT 'active',  -- active / superseded
    superseded_by   INTEGER REFERENCES decisions(id),
    captured_at     TEXT NOT NULL
)
```

Insert on `#done`. Query `WHERE workgroup = ? AND status = 'active' ORDER BY captured_at DESC` to surface recent decisions in a domain. Set `superseded_by` rather than deleting — the old decision and why it was overturned are both knowledge.
