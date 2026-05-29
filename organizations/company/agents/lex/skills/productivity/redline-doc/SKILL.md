---
name: redline-doc
description: Produce a redlined version of a contract with tracked changes and a negotiation rationale for each redline
category: productivity
version: 0.1.0
origin: user
requires_env: []
tools: [read_file, write_file, edit_file, web_fetch]
keywords: [redline, contract, negotiation, markup, legal]
created_at: 2026-05-05
---

## When to use
When responding to a counterparty's contract draft, when the company is the drafting party and wants to anticipate pushback, or when redlines have been received and the team needs to evaluate them. Redlining without a business rationale produces a negotiation, not a contract.

## Output format

**Contract** — name, version, and which party drafted it.

**Redline table**

| Section | Original text | Proposed text | Rationale | Priority |
|---|---|---|---|---|
| §X.X | "[verbatim original]" | "[proposed revision]" | [business reason for the change] | Must-have / Nice-to-have / Fallback |

Priority:
- Must-have: walk away if this isn't accepted
- Nice-to-have: push for it; accept a partial solution
- Fallback: low priority; drop if counterparty pushes back

**Deletions** — clauses proposed for removal with the reason.

**Additions** — clauses proposed to add that are absent from the original, with the reason and suggested language.

**Counterparty considerations** — for each must-have redline, what is the counterparty likely to object to and why? What is an acceptable compromise?

**Negotiation sequence** — which redlines to lead with and which to hold back. Presenting all redlines simultaneously invites rejection of all of them.

## Approach
- Every redline needs a business rationale, not just a legal one. "This is standard market language" is not a rationale — it's an appeal to convention. State the actual risk the redline addresses.
- Priority classification is mandatory. A counterparty that sees 20 undifferentiated redlines will negotiate them all equally. Signaling must-haves from nice-to-haves shapes the negotiation.
- Counterparty considerations are often omitted and are often decisive. Knowing why a counterparty will resist a redline lets you frame it in terms of their interest, not yours.
- Plain English strengthens, not weakens, contracts. Legalese obscures intent and creates interpretation disputes. Where clarity and convention conflict, choose clarity.

## Web tools
Use `web_fetch` to retrieve the source contract from a URL if one is provided rather than a pasted document.
