---
name: ticket-response
description: Draft a support ticket response that resolves the issue clearly, confirms understanding, and leaves the customer better off than when they wrote in
category: communication
version: 0.1.0
origin: user
requires_env: []
tools: [read_file, write_file, db]
keywords: ['support', 'ticket', 'response', 'customer-service', 'resolution']
created_at: 2026-05-05
---

## When to use
When drafting a response to a customer support ticket — bug report, how-to question, billing inquiry, or complaint. Also use to audit a response draft for tone, completeness, and accuracy before sending.

## Output format

**Ticket summary** — the customer's actual problem in one sentence. If unclear, stop and ask the clarifying question before drafting the response.

**Response draft**

---
[Greeting — use the customer's name if available]

[Confirm understanding — one sentence restating the problem in the customer's language, not ours]

[Resolution or next step — what happens next and when]

[If a workaround is needed while a fix is pending — describe it clearly]

[If the issue requires escalation — tell the customer exactly what will happen and the expected timeline]

[Close — specific, not generic]

---

**Internal note** — not sent to the customer:
- Root cause (if known)
- Whether this is a known issue, a product bug, or user error
- Whether this ticket should be flagged for the product team as a pattern
- Any context that a different agent would need to handle a follow-up

## Approach
- Confirm understanding before resolving. Solving the wrong problem confidently is worse than asking one clarifying question.
- Skip the canned opener. "Thank you for reaching out to us!" tells the customer nothing and wastes the first sentence.
- If the answer is "we can't do that," say so immediately and explain why. Don't bury the answer in paragraph three.
- Escalation is not a resolution. Tell the customer what will happen next and when they can expect to hear back. "I've escalated this to our team" with no timeline is a non-answer.
- The internal note is as important as the customer response. Patterns discovered in support that never reach the product team are organizational waste.

## State
Tickets reveal product patterns. Persist every handled ticket so recurring issues surface to product (`pattern_tag`) and resolution templates emerge.

Tables live under `state/db.sqlite` (per-skill). Schema is additive-only — `CREATE TABLE IF NOT EXISTS`, never `ALTER` destructively or `DROP`.

```sql
CREATE TABLE IF NOT EXISTS tickets (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    customer    TEXT,
    subject     TEXT NOT NULL,
    category    TEXT,
    resolution  TEXT NOT NULL,
    pattern_tag TEXT,
    csat        INTEGER,
    handled_at  TEXT NOT NULL
)
```

Group by `pattern_tag` to find recurring issues that should escalate to product or generate a knowledge-base article. Aggregate by `category` for trend analysis.
