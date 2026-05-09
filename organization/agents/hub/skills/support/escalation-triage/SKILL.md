---
name: escalation-triage
description: Decide whether to escalate a support issue, to whom, and with what context — without over-escalating or under-escalating
category: support
version: 0.1.0
origin: user
requires_env: []
tools: []
keywords: [escalation, triage, support, priority, routing]
created_at: 2026-05-05
---

## When to use
When a support ticket arrives that may need to go beyond frontline support — to engineering, customer success, product, or leadership. Also use to build or audit an escalation matrix for a support team.

## Output format

**Ticket** — one-sentence description of the issue.

**Escalation decision** — Resolve at frontline / Escalate to [team] / Immediate escalation.

**Decision criteria**

Escalate when any of the following is true:
- Data loss or corruption is possible or has occurred
- A security or privacy concern is raised (explicit or inferred)
- The issue is reproducible and engineering hasn't confirmed it as a known bug
- The customer has been unresolved for more than [X] business hours (define SLA)
- The customer is in a high-risk segment (enterprise, renewal imminent, at-risk flag)
- The customer's tone indicates a risk of public complaint or churn

Resolve at frontline when:
- A documented resolution exists in the knowledge base
- The issue is user error with a clear explanation
- The issue is a known limitation with an honest answer

**Escalation package** — what goes to the next team:
- Customer account and plan
- Full ticket history and any prior escalations
- Reproduction steps if it's a bug
- Customer sentiment assessment
- Proposed resolution or response already drafted

**SLA status** — is this ticket within or outside of the response SLA?

**Expected next step** — who owns this now, what action they take, and when customer should hear back.

## Approach
- The cost of under-escalation is a churned customer. The cost of over-escalation is engineering time. Both are real.
- The escalation package is what distinguishes a useful escalation from a hand-off. Escalating without context forces the next person to start over.
- "Escalated to the team" is not a resolution for the customer. Always tell the customer what happens next and when.
- Patterns in escalation are more valuable than the individual escalations. If the same issue escalates three times in a week, it should surface to product as a bug or to CS as a known issue.
