---
name: customer-signal
description: Synthesize qualitative customer signals — conversations, tickets, surveys, reviews — into actionable product and business insights
category: communication
version: 0.1.0
origin: user
requires_env: []
tools: [db]
keywords: ['customer-signal', 'voice-of-customer', 'feedback', 'insight', 'pattern']
created_at: 2026-05-05
---

## When to use
After a set of customer conversations, QBRs, support ticket analysis, or review mining. Also use when product asks "what are customers actually saying?" and the answer should come from evidence, not from the loudest recent conversation.

## Output format

**Signal sources** — what was collected, how many inputs, over what period. Signal from 3 conversations is anecdote; signal from 30 is a pattern.

**Signal themes** — grouped by type:

*Friction signals* — things customers can't do, find confusing, or work around:
- Theme: [description]
- Frequency: [how many signals / what % of inputs]
- Representative quote: [verbatim, with attribution stripped]
- Severity: blocking / degrading / minor

*Value signals* — things customers specifically praise or report as the reason they stay:
- Theme: [description]
- Frequency
- Representative quote

*Expansion signals* — requests, use cases, or adjacent problems customers raise unprompted:
- Theme: [description]
- Frequency
- Potential surface area: [is this a missing feature, a new segment, or a pricing opportunity?]

*Churn signals* — language or patterns that indicate at-risk sentiment:
- Theme
- Frequency
- Accounts affected (without PII in shared docs)

**Prioritized implications** — the top three things this signal says the company should change, stop doing, or pay attention to.

**What this signal does not say** — signal gaps. If no one mentioned pricing, that's notable. If all signal came from power users, it may not represent the median customer.

## Approach
- A single vocal customer is not a signal. Three customers saying the same thing in different words is a weak pattern. Ten is a strong one.
- The most important signals are often the ones customers don't know how to articulate. "I'm not sure how to use X" is a signal about discovery and onboarding, not about X.
- Distinguish between what customers ask for and what they need. Customers rarely ask for the right solution — they ask for relief from the symptom.
- Surface to product the frequency, not just the existence, of each theme. "Several customers mentioned" is less useful than "11 of 40 conversations touched this."

## State
Single signals are noise; aggregated signals are pattern. Persist every customer signal so themes emerge across sources.

```sql
CREATE TABLE IF NOT EXISTS signals (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    source       TEXT NOT NULL,                -- call / ticket / survey / review / churn-exit
    customer_ref TEXT,
    raw          TEXT NOT NULL,                -- the actual quote or summary
    theme        TEXT,                         -- normalised tag, e.g. 'onboarding-friction'
    sentiment    TEXT,                         -- positive / neutral / negative
    captured_at  TEXT NOT NULL,
    promoted_to  TEXT                          -- 'roadmap' / 'growth' / null if not promoted
)
```

Group by `theme` to find patterns reaching the 3-customer floor before promoting to Roadmap. `promoted_to` tracks which signals turned into action.
