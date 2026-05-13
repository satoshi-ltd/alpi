---
name: contract-review
description: Review a contract for material risks, missing protections, and terms that require negotiation — with jurisdiction and business context stated
category: productivity
version: 0.1.0
origin: user
requires_env: []
tools: [read_file, web_fetch, db]
keywords: [contract, review, legal, terms, negotiation]
created_at: 2026-05-05
---

## When to use
When evaluating a vendor agreement, customer contract, partnership agreement, or employment document before signing. Not a substitute for a licensed attorney in the relevant jurisdiction — flag when that is needed.

## Output format

**Contract type and parties** — what kind of agreement, who are the parties, and what jurisdiction governs it.

**Business context** — why is this contract being signed and what outcome does the signing party want? A contract review without business context over-weights legal risk and under-weights commercial reality.

**High-risk clauses** — terms that could expose the company to material harm:

| Clause | Location | Risk | Severity | Recommended action |
|---|---|---|---|---|
| [e.g., unlimited liability] | §X.X | [explains the exposure] | High / Medium / Low | Negotiate / Accept / Reject |

Severity: High (material financial or operational exposure) / Medium (manageable with controls) / Low (standard market risk).

**Missing protections** — clauses that are absent but should be included:
- [What's missing]: why it matters and standard market language

**Terms to negotiate** — specific redlines recommended, with the business rationale:
- Current: "[verbatim problematic text]"
- Proposed: "[suggested revision]"
- Reason: [why this is better for the signing party]

**Jurisdiction note** — any terms that may be unenforceable or interpreted differently in the governing jurisdiction.

**Summary** — Sign as-is / Sign with listed redlines / Do not sign without legal counsel review.

## Approach
- Contracts allocate risk. Every clause is a decision about who bears a specific risk. Evaluate each against who is better positioned to bear it.
- Flag clauses you don't understand as missing context rather than accepting them as standard. "Standard industry terms" are still negotiable.
- The absence of a clause can be as dangerous as a bad clause. Missing IP ownership, missing data breach notification obligations, and missing limitation of liability are common omissions.
- Jurisdiction matters. An arbitration clause in California has different implications than one in Delaware. Do not generalize across jurisdictions.
- Never invent case citations or statutory references. If a legal argument requires precedent that you cannot cite with certainty, label it as interpretation rather than settled law.

## Web tools
Use `web_fetch` to retrieve contracts provided as URLs. Consult `references/review-checklist.md` for the section-by-section review order.

## State
Track every contract reviewed so renewals, expirations, and risk patterns are visible.

```sql
CREATE TABLE IF NOT EXISTS contracts (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    counterparty  TEXT NOT NULL,
    type          TEXT NOT NULL,                 -- msa / nda / vendor / employment / sow
    risk_level    TEXT NOT NULL,                 -- high / medium / low
    redline_count INTEGER NOT NULL DEFAULT 0,
    status        TEXT NOT NULL DEFAULT 'in-review',
    review_date   TEXT NOT NULL,
    expiry_date   TEXT
)
```

Query `WHERE expiry_date <= date('now', '+90 days')` to flag renewals. Aggregate by `counterparty` to detect repeat negotiation patterns.
