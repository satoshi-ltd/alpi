---
name: tech-debt-assessment
description: Assess a piece of technical debt with business impact, remediation cost, and a prioritization recommendation
category: software
version: 0.1.0
origin: user
requires_env: []
tools: [read_file, search, db]
keywords: ['tech-debt', 'refactor', 'remediation', 'cost', 'risk']
created_at: 2026-05-05
---

## When to use
When a codebase area, system component, or architectural pattern needs to be evaluated for debt remediation — either because it is causing incidents, slowing delivery, or blocking a planned feature.

## Output format

**Component / area** — name it precisely.

**Debt type** — choose one: design debt / code debt / test debt / infrastructure debt / documentation debt. Mixed is allowed but name the primary type.

**Business impact** — what this debt is costing today in measurable terms:
- Delivery slowdown: estimate in developer-days per quarter lost to working around this
- Incident rate: recent incidents attributable to this area (count, severity)
- Feature blocker: features currently blocked or made risky by this debt

**Remediation options**
- Option A (incremental): [what, estimated cost in dev-days, risk of approach]
- Option B (full rewrite): [what, estimated cost, risk]
Choose at least two options. "Do nothing" counts as an option and must appear if it is viable.

**Recommendation** — which option, and why, given current business priorities.

**Priority** — critical / high / medium / low, with reasoning:
- Critical: causing incidents now or will block a committed roadmap item
- High: meaningful delivery slowdown, fixable in a sprint
- Medium: annoying but not urgent
- Low: clean code preference, not business-driven

**Prerequisite** — what needs to be true before remediation starts (test coverage, feature freeze, new team member onboarded, etc.)

## Approach
- Technical debt is a business decision, not a moral one. Frame the assessment in terms of business impact, not code aesthetics.
- The "do nothing" option is valid. Name it honestly, including its compounding cost over time.
- Cost estimates are rough; label them as such. A ±50% range is more honest than a false-precision day count.
- Do not recommend full rewrites without a very clear and very costly business case. Most rewrites cost 3x what the estimate says.

## State
Tech debt accumulates. A queryable log makes prioritization and progress visible.

Tables live under `state/db.sqlite` (per-skill). Schema is additive-only — `CREATE TABLE IF NOT EXISTS`, never `ALTER` destructively or `DROP`.

```sql
CREATE TABLE IF NOT EXISTS tech_debt (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    item              TEXT NOT NULL,
    business_impact   TEXT NOT NULL,             -- high / medium / low
    remediation_cost  TEXT NOT NULL,             -- high / medium / low
    priority          INTEGER,                   -- 1..5 (computed: impact / cost)
    status            TEXT NOT NULL DEFAULT 'open',  -- open / scheduled / resolved
    related_files     TEXT,
    date              TEXT NOT NULL
)
```

Sort `WHERE status = 'open' ORDER BY priority DESC` for the next-up list. Mark `resolved` with the date so historical debt-paydown rate is measurable.
