---
name: competitor-analysis
description: Deep-dive analysis of a single competitor — strategy, product trajectory, financial health, and the specific threat they pose
category: research
version: 0.1.0
origin: user
requires_env: []
tools: [web_search, web_fetch, web_extract, db]
keywords: [competitor, analysis, strategy, threat, market]
created_at: 2026-05-05
---

## When to use
When a competitor is gaining ground and a shallow competitive scan isn't enough, when evaluating whether a competitor's recent move changes our strategy, or when preparing for a board conversation about competitive dynamics. This is a deep-dive on one company, not a market scan across many.

## Output format

**Competitor** — name, founding year, estimated headcount and ARR (state source and confidence).

**Strategic intent** — what is this company trying to become? Use their own communications (fundraise memos, founder interviews, investor letters) not our interpretation.

**Product trajectory**
- What they launched in the last 12 months
- Where they are investing (hiring signals, job postings, conference talks)
- What they have publicly roadmapped
- Product weaknesses that persist despite investment

**Go-to-market**
- ICP: who they target and who they convert (infer from case studies and review sites)
- Positioning: their current message in their own words
- Channels: primary acquisition vectors (infer from ad spend, content, partner activity)
- Pricing: public tiers; if not public, infer from positioning and available intelligence

**Financial health** (for funded companies)
- Last round: amount, date, valuation (if disclosed), lead investor
- Burn signals: hiring pace, office changes, leadership departures
- Revenue signals: any public ARR claims, analyst estimates, customer count

**Threat assessment**
- Direct overlap: where do they compete head-to-head with us for the same customer?
- Expansion risk: where could they credibly expand into our core territory in 12–18 months?
- Competitive advantage: what do they do genuinely better that customers choose them for?

**Intelligence gaps** — what don't we know that would change this assessment?

## Approach
- Use their own words. Paraphrasing competitor positioning into something easier to dismiss is self-deception.
- Distinguish confirmed intelligence (primary source) from inferred intelligence (pattern across signals) from speculation (single anecdote). Label all three.
- Financial health matters. A competitor with 18 months of runway is a different threat than one that just raised a $100M Series C.
- Threat assessment must name specific deals we've lost to them or specific customer segments they're winning. "They're a threat in the enterprise" is not a threat assessment.

## Web tools
Use `web_search` when you need to find sources. Use `web_fetch` to read the full content of a page once you have the URL. Use `web_extract` to pull a specific answer from a page (e.g. current pricing, last funding round) without reading the whole document. For primary sources (SEC filings, earnings transcripts), `web_fetch` the direct URL. Persist findings in `db` across sessions so competitor intelligence accumulates over time.

## State
Competitor intelligence accumulates over time — single snapshots are misleading. Persist findings so trajectory is queryable.

Tables live under `state/db.sqlite` (per-skill). Schema is additive-only — `CREATE TABLE IF NOT EXISTS`, never `ALTER` destructively or `DROP`.

```sql
CREATE TABLE IF NOT EXISTS competitors (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    name         TEXT NOT NULL UNIQUE,
    founded      TEXT,
    headcount    INTEGER,
    arr_estimate TEXT,
    last_round   TEXT,
    last_analyzed TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS intel (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    competitor_id INTEGER NOT NULL REFERENCES competitors(id),
    category      TEXT NOT NULL,               -- product / gtm / financial / hiring / pricing
    claim         TEXT NOT NULL,
    source        TEXT NOT NULL,
    confidence    TEXT NOT NULL,               -- confirmed / pattern / single-anecdote
    observed_at   TEXT NOT NULL
)
```

On each scan, `INSERT` rather than `UPDATE` intel rows — older claims show how positioning evolved. Query `WHERE category = 'pricing' ORDER BY observed_at DESC` to see pricing trajectory.
