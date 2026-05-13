---
name: unit-economics
description: Calculate and interpret unit economics — CAC, LTV, payback period, gross margin — for a business or channel
category: finance
version: 0.1.0
origin: user
requires_env: []
tools: []
keywords: ['unit-economics', 'cac', 'ltv', 'payback', 'gross-margin', 'churn']
created_at: 2026-05-05
---

## When to use
When evaluating a channel, pricing change, or growth initiative for financial viability. Also use when a decision looks strategically good but the unit economics have not been checked.

## Output format

**What we are evaluating** — one sentence.

**Inputs** (state the source of each number: measured / estimated / assumed)
- Average Revenue Per Account (ARPA): [monthly or annual]
- Gross margin: [%]
- Monthly churn rate: [%]
- CAC: [total sales + marketing spend / new customers in period]

**Derived metrics**

| Metric | Value | Formula |
|---|---|---|
| LTV | | ARPA × Gross margin / Monthly churn |
| LTV:CAC ratio | | LTV / CAC |
| CAC payback period | | CAC / (ARPA × Gross margin) in months |

**Interpretation**
- LTV:CAC < 1: spending more to acquire than you will ever recover. Stop the channel.
- LTV:CAC 1–3: marginal. Acceptable only if payback period is short and churn is improving.
- LTV:CAC 3+: healthy. Scale if payback period is under 18 months.
- Payback > 24 months: cash flow risk regardless of LTV:CAC.

**Sensitivity** — how do the metrics change if churn increases by 50%? If CAC increases by 30%? Show the stressed scenario.

**Recommendation** — one sentence on whether the economics support the decision under evaluation.

## Approach
- Label every input as measured, estimated, or assumed. Assumed inputs must be validated before committing spend.
- LTV:CAC is a ratio, not a target. 5:1 with a 36-month payback is worse than 3:1 with a 6-month payback for a capital-constrained company.
- Run the stressed scenario first, not last. Optimistic base cases mislead; stress cases reveal whether the model is robust.
- Gross margin, not revenue, is what matters. A high-revenue, low-margin product has worse unit economics than it appears.
