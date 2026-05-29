---
name: vendor-eval
description: Evaluate a vendor or technology against operational, security, cost, and lock-in criteria
category: research
version: 0.1.0
origin: user
requires_env: []
tools: [read_file, write_file]
keywords: ['vendor', 'evaluation', 'technology', 'comparison', 'buy-vs-build']
created_at: 2026-05-05
---

## When to use
When the Architecture workgroup needs to choose between vendors, managed services, or a build-vs-buy decision for a platform component.

## Output format

**What we are evaluating** — one sentence on the capability or problem this addresses.

**Evaluation criteria** (score each 1–3: 1 = poor, 2 = acceptable, 3 = good)

| Criterion | [Vendor A] | [Vendor B] | [Build] | Weight |
|---|---|---|---|---|
| Operational simplicity | | | | High |
| Security posture | | | | High |
| Cost at current scale | | | | Medium |
| Cost at 10x scale | | | | Medium |
| Lock-in risk | | | | Medium |
| Team familiarity | | | | Low |
| Community / support | | | | Low |

**Weighted summary** — one sentence per option summarising the score and the strongest argument for and against.

**Recommendation** — one option, stated clearly. If genuinely too close to call, name the single deciding factor that would break the tie.

**Risks of recommended option** — two to three bullet points. Be specific; "vendor goes bankrupt" is not actionable. "Vendor's pricing model has no cap at high volume — we need a contractual ceiling" is.

**Migration path** — if we choose this and later regret it, how hard is the exit? Score: easy / painful / extremely painful, with a one-sentence explanation.

## Approach
- Boring technology that the team can operate is worth more than impressive technology that requires a specialist.
- Evaluate at actual current scale and at 10x. A solution that breaks at 10x is acceptable if 10x is years away and we can re-evaluate.
- Lock-in is underweighted in most evaluations. Make it explicit.
- "Build" is a valid option that is almost always undercosted. Include realistic maintenance overhead, not just initial build time.

## State
Append each evaluation to `state/vendors.jsonl`. Volume is low (10-20 vendors lifetime) and lookups are "what did we decide about category X" — flat JSONL is enough.

Each line:
```json
{"date":"2026-05-12","name":"Postgres","category":"database","operational":5,"security":4,"cost":4,"lock_in":"low","decision":"adopt","rationale":"boring tech, deep ecosystem, team has ops experience"}
```

To compare options in a category: read the file, filter by `category`. To revisit a past decision: grep by name. Append a fresh entry rather than mutating old ones — historical scores show how thinking evolved.
