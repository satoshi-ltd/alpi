---
name: pricing-model
description: Analyze pricing strategy options — tiers, anchoring, packaging — with revenue and unit-economics impact
category: finance
version: 0.1.0
origin: user
requires_env: []
tools: []
keywords: [pricing, tiers, packaging, revenue, arpa]
created_at: 2026-05-05
---

## When to use
When evaluating a new pricing structure, a tier change, or a price increase. Also use when current pricing was set more than 12 months ago and hasn't been validated against actual customer segments and willingness to pay.

## Output format

**What is being priced** — product, feature, or tier being evaluated.

**Current state** (skip if new product)
- Existing tiers and prices
- Revenue distribution across tiers (% of customers and % of revenue per tier)
- Estimated price sensitivity signal: [from sales objections / churn interviews / surveys / none]

**Proposed pricing structure**

| Tier | Price | What's included | Target ICP | Expected conversion |
|---|---|---|---|---|

**Revenue model**

| Scenario | Customers | ARPA | MRR | Assumptions |
|---|---|---|---|---|
| Conservative | | | | |
| Base | | | | |
| Upside | | | | |

**Unit economics impact** — how does the proposed pricing change LTV, LTV:CAC, and payback period? (Reference the unit-economics skill if needed.)

**Risks**
- Downgrade risk: which customers are likely to move to a lower tier?
- Churn risk: which segments are most price-sensitive?
- Competitive exposure: does this pricing open or close a gap vs competitors?

**Recommendation** — one sentence. Price to move or price to hold, and why.

## Approach
- Distinguish between what customers pay and what they would pay. Current price is not evidence of ceiling.
- Packaging matters as much as price. Customers compare tiers to each other, not to competitors. Anchor pricing deliberately.
- Price increases on existing customers carry different risk from new customer pricing. Model them separately.
- Revenue distribution across tiers reveals where value is actually perceived. A tier with 60% of customers and 20% of revenue is a pricing problem.
- Validate assumptions with at least one customer segment before a price increase. Surveys are imperfect; cancelled churned interviews are better.
