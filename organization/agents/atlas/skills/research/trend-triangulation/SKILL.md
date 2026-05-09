---
name: trend-triangulation
description: Identify and validate an emerging trend by triangulating across multiple independent source types before claiming it's real
category: research
version: 0.1.0
origin: user
requires_env: []
tools: [web_search, web_fetch, web_extract]
keywords: [trend, signal, market, research, triangulation]
created_at: 2026-05-05
---

## When to use
When evaluating whether a pattern observed in one or two sources reflects a real market shift or is noise. Also use when a strategic decision depends on an emerging trend being durable — not when it's already in the mainstream press (at that point it's priced in and may already be peaking).

## Output format

**Trend hypothesis** — the specific, falsifiable claim being evaluated: "X is happening in Y market, driven by Z." Not "AI is changing everything."

**Source matrix** — triangulate across at least three source types:

| Source type | Specific source | Signal found | Confidence |
|---|---|---|---|
| Regulatory / policy | [filing, agency guidance, legislation] | | |
| Financial / capital flow | [IPO filings, VC investment data, M&A activity] | | |
| Talent / hiring | [job posting patterns, LinkedIn, conference speaker lineups] | | |
| Customer behavior | [search trends, product usage data, survey research] | | |
| Operator statements | [earnings call transcripts, investor day remarks] | | |
| Academic / research | [papers, preprints, research institution output] | | |

**Triangulation result**
- How many independent source types confirm the trend?
- Do the sources agree on timing, direction, and magnitude — or only on direction?
- Are there contradicting signals? From what source types?

**Confidence rating**
- Strong signal: 4+ source types confirm, directionally consistent
- Pattern: 2–3 source types confirm, timing uncertain
- Early signal: 1–2 confirming sources, others neutral or absent
- Noise: single anecdote or viral content only

**Strategic implications** — if this trend is real and durable, what changes for us in 12 and 24 months?

**What would change this assessment** — specific observable events that would upgrade or downgrade confidence.

## Approach
- A trend you saw in three Twitter threads is a social media event. A trend confirmed in regulatory filings, VC allocation shifts, and earnings call transcripts is a market signal.
- Timing uncertainty is not the same as signal uncertainty. "This is happening" and "this will peak in 18 months" are independent claims — you can be confident about one and uncertain about the other.
- Contradiction is information. If one source type confirms and another contradicts, investigate the contradiction rather than averaging the signals.
- "Everyone knows this is the future" is the death of triangulation. Consensus means the signal is late, not that it's strong.

## Web tools
Use `web_search` to locate sources across different source types. Use `web_fetch` to read the full source. Use `web_extract` to pull the specific claim from each source for comparison. Triangulation requires reading three independent sources — do not summarise from `web_search` snippets alone.
