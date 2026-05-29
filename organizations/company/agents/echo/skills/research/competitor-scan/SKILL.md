---
name: competitor-scan
description: Produce a structured competitive positioning scan with pricing, messaging, and strategic gaps
category: research
version: 0.1.0
origin: user
requires_env: []
tools: [web_search, web_fetch]
keywords: [competitor, competitive, positioning, market, scan]
created_at: 2026-05-05
---

## When to use
When the Growth workgroup needs a current picture of competitor positioning before a pricing change, a launch, or a positioning revision. Also use when a sales objection pattern suggests a competitor is gaining ground.

## Output format

**Market framing** — one sentence on how the category is contested today and what the dominant positioning axes are.

For each competitor:

**[Competitor name]**
- Positioning: how they describe themselves (use their own words, not ours)
- ICP signal: who their marketing targets (infer from case studies, copy, pricing tiers)
- Pricing: tiers and public prices if available; "not public" if not
- Strengths: what they do genuinely well that customers choose them for
- Weaknesses: real gaps, not wishful thinking — source from reviews or sales call patterns if available
- Recent moves: any pricing, product, or positioning change in the last 6 months

**Gap analysis** — where do competitors leave a real opening?
- Underserved segments: ICPs no competitor is targeting well
- Pricing gap: tiers or models nobody offers
- Messaging gap: a true benefit nobody is claiming

**Implication for us** — one to three sentences on what this competitive picture means for our positioning right now.

## Approach
- Use competitors' own words for their positioning. Do not paraphrase them into something easier to dismiss.
- Distinguish between "they are weak here" (evidence-based) and "we think they are weak here" (assumption). Label both.
- Gaps are only real if there is a customer willing to pay for what is missing. An unclaimed position nobody wants is not an opportunity.
- Update quarterly at minimum. Competitive intelligence that is six months old is often worse than no intelligence.

## Web tools
Use `web_search` to find competitor pages, review sites, and press. Use `web_fetch` to read pricing pages and landing pages in full rather than relying on snippets.
