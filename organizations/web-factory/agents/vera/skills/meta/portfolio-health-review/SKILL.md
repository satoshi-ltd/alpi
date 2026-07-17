---
name: portfolio-health-review
description: Weekly walk across all proj-<slug> workgroups — surfaces stuck projects, capacity warnings, recurring failure modes. Vera's only proactive operational rhythm.
category: meta
version: 0.1.0
origin: user
requires_env: []
tools: [read_file, search, workgroup_post]
keywords: ['portfolio', 'weekly-review', 'health-check', 'capacity', 'bottleneck']
created_at: 2026-05-29
---

## When to use

Every Monday morning, or before an operator portfolio review. Vera runs this independently — mira's portfolio view is per-project; vera's is cross-project pattern detection.

## Inputs

- All `projects/<slug>/status.yaml` files (one per active project)
- The `proj-<slug>` workgroups (transcript scan for blockers, owner re-assignments, override requests)
- Mira's capacity statement (5-project hard ceiling)

## Approach

1. **Scan status.yaml across all active projects** (state != `archived`):
   - Days since last state change → flag if > 7 days
   - State distribution (how many in intake / design / content / build / qa / launched)
   - Imminent launch dates (next 14 days)
2. **Identify outliers**:
   - Any project stuck > 14 days in the same state → call out the owning agent
   - Any state queue depth > 3 (e.g. three projects waiting on canvas) → capacity warning
   - Any project with a granted override → expiry tracking
3. **Look for cross-project patterns**:
   - If three projects in a row need the same template change, push it to the `template` workgroup
   - If lens fails the same checklist item across two projects, push it to the `quality` workgroup
4. **Surface to the right workgroup**:
   - Capacity concerns → mira (in `quality` wg)
   - Pattern-level issues → relevant persistent wg (`template` / `quality` / `brand-library`)
   - Strategic concerns (factory overcommitted, customer concentration) → operator review in the `quality` workgroup

## Output format

A post in the `quality` workgroup every Monday:

```
Portfolio health · week of 2026-MM-DD

Active: <N> projects  (intake: X · design: X · content: X · build: X · qa: X)
Launched this week: <list>
Launching next 14 days: <list with owners>

Stuck (>14 days same state):
- proj-<slug>  state=<x>  owner=<agent>  age=<days>d
  → suggested next step

Capacity flags:
- <agent> has <N> projects in flight at <state> — may bottleneck on the next 3

Cross-project patterns:
- <pattern>  → propose to <workgroup>

Overrides expiring:
- proj-<slug>  criterion=<x>  expires=<date>
```

## What this is NOT

- Not a budget review (mira owns daily/wg budgets)
- Not a quality audit (lens + vera own that per-project)
- Not a roadmap (web-factory itself doesn't have one beyond the `template` wg)

## Voice

- Quantify everything: days, counts, percentages
- One actionable next step per outlier, not a problem description
- Escalate beyond the factory only when the issue genuinely needs operator input — not as a CYA reflex
