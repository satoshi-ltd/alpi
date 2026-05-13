---
name: objection-handler
description: Diagnose and respond to a sales objection — distinguish real objections from smokescreens, and respond without pressure
category: communication
version: 0.1.0
origin: user
requires_env: []
tools: [db]
keywords: [objection, sales, negotiation, pushback, close]
created_at: 2026-05-05
---

## When to use
When a prospect raises an objection during or after a sales conversation, or when a deal has stalled and the blocker is unclear. Also use to build a reusable objection library from patterns in lost deals.

## Output format

**Objection stated** — the exact words the prospect used. Do not paraphrase — the phrasing contains signal.

**Objection type**
- Real: a genuine concern that, if resolved, moves the deal forward
- Smokescreen: a proxy for a concern the prospect isn't naming (price objection often masks budget authority; "need to think about it" often masks fear of change)
- Disqualifier: a fundamental mismatch that should end the deal honestly

**Underlying concern** — if smokescreen, what is it most likely hiding?

**Clarifying question** — one question that confirms whether this is the real objection before responding. Responding to the stated objection before confirming it's the real one is a common failure.

**Response** — direct, non-pressuring:
- Acknowledge the concern (not "great question" — acknowledge the substance)
- Address the root, not the surface
- Offer evidence, alternative framing, or a next step that reduces the perceived risk

**What not to say** — the pressure move or dismissive response that would make this objection worse.

**Pattern note** — if this objection type recurs, what does it reveal about positioning, onboarding, or product?

## Approach
- An objection is information. Treating it as an obstacle to overcome misses the signal it contains.
- Never answer an objection before confirming it's the real one. "Is price the only thing holding you back?" is more valuable than a polished price response that doesn't address the actual hesitation.
- Discount is not a response to a price objection. Discount is a response to a budget mismatch. They're different. One is solved with ROI; the other may not be solvable at all.
- A recurring objection is a product or positioning problem, not a sales skill problem. Track them and surface them to product and marketing.

## State
The objection library is the highest-leverage sales asset — patterns of objections reveal positioning gaps and the responses that work.

```sql
CREATE TABLE IF NOT EXISTS objections (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    raw               TEXT NOT NULL,           -- prospect's actual words
    category          TEXT NOT NULL,           -- price / feature / timing / authority / trust / fit
    real_concern      TEXT,                    -- the underlying concern (often different from raw)
    response_used     TEXT,
    outcome           TEXT,                    -- 'resolved' / 'still-blocking' / 'walked-away'
    deal_size         REAL,
    raised_at         TEXT NOT NULL
)
```

Group `WHERE outcome = 'still-blocking' GROUP BY category` to detect systemic objections that need product or positioning changes — those go to Roadmap or Growth, not handled at the call level.
