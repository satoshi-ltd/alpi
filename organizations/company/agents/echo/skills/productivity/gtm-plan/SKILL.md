---
name: gtm-plan
description: Write a go-to-market plan structured as testable hypotheses with channels, metrics, and kill criteria
category: productivity
version: 0.1.0
origin: user
requires_env: []
tools: [write_file, db]
keywords: [gtm, go-to-market, launch, channel, positioning]
created_at: 2026-05-05
---

## When to use
When a product launch, new channel, or significant positioning change needs a structured plan. Also use to audit an existing GTM plan for missing hypotheses, vanity metrics, or untested assumptions.

## Output format

**What we are launching** — one sentence. Product, feature, or positioning change.

**ICP for this launch** — specific. Company size, role, pain, buying trigger. "SMBs" is not an ICP.

**Positioning statement** — "For [ICP], [product] is the [category] that [key benefit] unlike [alternative], because [proof point]."

**Channels** (list each channel being activated)
- Channel: [name]
- Hypothesis: "We believe this channel will deliver [X leads / signups / revenue] within [Y weeks] because [reason]"
- Spend: [time or money allocated]
- Primary metric: [the one number that validates or invalidates the hypothesis]
- Kill threshold: [the value below which we cut or pivot this channel]

**Launch sequence** — ordered list of what goes live when. Sequencing matters: soft launch before broad push.

**Success definition** — 30 / 60 / 90 day targets for the primary metric.

**What we are not doing** — at least two channels or tactics that were considered and rejected, with the reason.

## Approach
- An ICP that is not specific enough to reject someone is not an ICP — it is a market description.
- Every channel must have a kill threshold, not just a target. A channel without a kill threshold will never be cut.
- "We will try X and see" is not a hypothesis. Commit to a specific prediction with a specific timeframe.
- The launch sequence section prevents the common failure mode of doing everything at once and not knowing what worked.

## State
GTM is hypothesis-driven — every tactic is a bet with a kill criterion. Persist outcomes so the team learns.

Tables live under `state/db.sqlite` (per-skill). Schema is additive-only — `CREATE TABLE IF NOT EXISTS`, never `ALTER` destructively or `DROP`.

```sql
CREATE TABLE IF NOT EXISTS hypotheses (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    hypothesis      TEXT NOT NULL,
    channel         TEXT,
    target_metric   TEXT NOT NULL,
    target_value    REAL,
    actual_value    REAL,
    kill_criterion  TEXT NOT NULL,
    timeframe       TEXT,
    status          TEXT NOT NULL DEFAULT 'running',  -- running / hit / killed
    learned         TEXT,
    date            TEXT NOT NULL
)
```

Insert on plan write. Update `actual_value` and `status` when the timeframe closes. Query killed hypotheses to detect channel-level patterns ("paid social keeps killing — stop trying it").
