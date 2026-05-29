---
name: decision-record
description: Capture a strategic decision with full context, alternatives considered, and rationale so it is never relitigated
category: productivity
version: 0.1.0
origin: user
requires_env: []
tools: [write_file]
keywords: [decision, record, rationale, alternatives, context]
created_at: 2026-05-05
---
## Scope
This skill is for **strategic decisions Vera makes** — direction-setting at the company or council level. Write the record at the moment of decision, while context is fresh, before the workgroup closes.

**Use this skill** when:
- Vera is making the call (or hub of an ad-hoc strategic workgroup she created)
- The decision is strategic: positioning, focus, kill-or-keep, prioritization across functions, organizational changes
- The decision needs Vera's specific frame (tradeoffs, what we're not doing, why now)

**Do NOT use this for** workgroup-level decisions where Vera is just a peer. Those go through `archive/decision-capture` at `#done` time, captured by Archive as the canonical org-wide record. Architectural decisions go through `zeta/adr-writer`.

The output of this skill flows into `archive/decision-capture` as one of many sources — Archive is the searchable index across all decisions; this skill is Vera's working artifact.

## When to use
At the close of any workgroup task or Council discussion where a direction was chosen. The record exists so future agents — or a future version of this org — can understand not just what was decided but why, and what was considered and rejected.

## Output format

**Decision** — one sentence.

**Date** — ISO format.

**Context** — two to four sentences. The situation that forced a choice. Include constraints, deadlines, and stakeholder pressures that shaped the options.

**Options considered**
- Option A: [description] — [reason it was rejected or not chosen]
- Option B: [description] — [reason it was rejected or not chosen]
- Chosen: [description] — [why this one]

**Rationale** — the reasoning behind the chosen option. Reference data or evidence where it exists. Label opinions as opinions.

**Dissent** — if any agent or stakeholder disagreed, capture their position and why it was overruled. Burying dissent produces decisions that get relitigated.

**Follow-up** — owner and date for the next checkpoint.

## Approach
- Write this at the moment of decision, not after the fact. Memory degrades; rationale invented later is rationalization.
- The "options considered" section is the most important part. A decision record with only one option is a rubber stamp, not a record.
- Be specific about who disagreed and why. "Some concern was raised" is useless.
- If the decision was made under uncertainty, say so explicitly and name the assumption being bet on.
