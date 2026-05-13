---
name: process-map
description: Map a cross-functional process to surface handoff gaps, bottlenecks, and steps that don't add value
category: productivity
version: 0.1.0
origin: user
requires_env: []
tools: [write_file]
keywords: ['process-map', 'workflow', 'operations', 'bottleneck', 'handoff']
created_at: 2026-05-05
---

## When to use
When a process involves multiple teams and no one has a clear picture of the full flow, when a process is taking longer than expected and the bottleneck is undiagnosed, or when a recurring operational problem has an unclear root cause that might be structural.

## Output format

**Process name** — what is being mapped.

**Scope** — where the process starts and where it ends. Out-of-scope steps should be listed but not mapped.

**Swimlane map** — present as a table, with rows as roles/teams and columns as time sequence:

| Step | Owner | Input | Output | System/Tool | Avg time |
|---|---|---|---|---|---|
| 1. [Action] | [Role] | [What arrives] | [What's produced] | | |

For decision points, note:
- Decision: [question]
- Yes path → Step X
- No path → Step Y

**Handoff analysis** — every place where output from one team becomes input for another:
- Handoff: [from → to]
- Handoff mechanism: [email / ticket / Slack / system event]
- Where things drop: [what can go wrong at this handoff]

**Bottleneck candidates** — steps with the longest average time, highest error rate, or highest re-work rate.

**Value-add vs. non-value-add** — classify each step:
- Value-add: the customer or next team needs this output
- Necessary non-value-add: required but doesn't produce value (compliance step, audit log)
- Non-value-add: could be eliminated without degrading output

**Recommendation** — the one or two process changes that would have the highest impact on cycle time or error rate.

## Approach
- Map the current state first, then the desired state. Mapping a hypothetical process you haven't observed is fiction.
- Handoffs are where processes break. Most process failures are not in the steps themselves — they're in the gaps between teams.
- Non-value-add steps are politically sensitive but operationally important. Name them clearly; don't soften the label.
- Cycle time is the metric that matters. Activity measures effort; cycle time measures throughput. A process full of busy steps can still be slow.
