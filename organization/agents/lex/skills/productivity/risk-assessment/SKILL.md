---
name: risk-assessment
description: Assess the legal risk of a proposed action — with severity, likelihood, triggers, and mitigation options stated plainly
category: productivity
version: 0.1.0
origin: user
requires_env: []
tools: [read_file, write_file]
keywords: ['legal-risk', 'compliance', 'liability', 'assessment', 'mitigation']
created_at: 2026-05-05
---

## When to use
When a business decision has potential legal consequences that need to be evaluated before proceeding — product launch, new market entry, data handling change, pricing change, partnership structure, or user-facing policy change. Also use when the team asks "can we do this?" and the honest answer is "it depends."

## Output format

**Action under review** — what the company is proposing to do. Be specific about the mechanism, not just the outcome.

**Jurisdiction(s)** — the legal systems that apply. Many risk assessments fail because jurisdiction is assumed, not stated.

**Risk table**

| Risk | Legal basis | Likelihood | Severity | Trigger | Mitigation |
|---|---|---|---|---|---|
| [e.g., GDPR violation] | [Regulation/statute] | Low/Med/High | Low/Med/High | [What would actualize this risk] | [What reduces it] |

Likelihood: probability of the risk materializing if no action is taken.  
Severity: business impact if it does materialize (fine size, operational disruption, reputational damage).

**What changes the risk level** — specific conditions or decisions that move the risk from the current level to higher or lower.

**Recommended mitigations** — specific, actionable steps that reduce the highest-severity risks:
- [Mitigation]: [what it does, who does it, by when]

**Residual risk** — the risk that remains after recommended mitigations are applied.

**Verdict** — Proceed / Proceed with mitigations / Do not proceed without legal counsel / Do not proceed.

## Approach
- Distinguish probability from severity. A low-probability, high-severity risk (e.g., a class action) warrants different treatment than a high-probability, low-severity risk (e.g., a user complaint).
- "It depends" is honest, but specificity about what it depends on is what makes it useful. Name the conditions.
- Residual risk is always non-zero. A risk assessment that concludes "no risk if we do X" is overconfident.
- Do not opine on jurisdictions you cannot specify the statute or relevant authority for. "This may violate EU law" without citing a regulation is not a legal assessment.
- The trigger column is often omitted and is often the most useful. Knowing what activates a risk helps the business decide whether to accept it.

## State
Append every assessment to `state/risks.jsonl`. Volume is low (~20/year) and the only query is "have we ruled on something similar?" — flat JSONL with grep is the right shape.

Each line:
```json
{"date":"2026-05-12","action":"sign data-processing addendum with EU vendor","severity":"medium","likelihood":"low","triggers":"GDPR Art. 28","mitigation":"require SCCs","decision":"proceed-with-mitigation"}
```

Before assessing a new action, read the file and grep by action keyword to surface precedents. Append the new assessment after deciding.
