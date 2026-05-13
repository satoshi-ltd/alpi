---
name: primary-source
description: Research a question using primary sources — filings, transcripts, papers, original data — with explicit citation and confidence levels
category: research
version: 0.1.0
origin: user
requires_env: []
tools: [web_search, web_fetch, web_extract]
keywords: ['research', 'primary-source', 'citation', 'evidence', 'analysis']
created_at: 2026-05-05
---

## When to use
When a business decision requires factual grounding that goes beyond common knowledge, industry chatter, or secondary summaries. Also use when an existing claim in a report or presentation needs to be verified against its original source.

## Output format

**Question** — the specific question being answered. A vague question produces a vague answer regardless of source quality.

**Sources consulted** — for each:
- Source: [title, author/publisher, date, URL or document reference]
- Source type: primary (original filing, study, transcript, data release) / secondary (analysis of primary) / tertiary (summary of analysis)
- Relevance: [what specific claim this source supports or contradicts]

**Findings**

For each finding:
- Claim: [specific, falsifiable statement]
- Evidence: [direct quote or data point from primary source, with citation]
- Confidence: confirmed / pattern observed / single source / inferred
- Contradicting evidence: [any source that challenges this finding]

**Gaps** — questions that the available sources don't answer, and what source would fill the gap.

**What this research does not say** — conclusions that would require more evidence than was found.

## Approach
- Primary source first, always. If a finding is only available in a secondary source, go find the original before citing it. Secondary sources introduce errors and omit context.
- Label confidence on every claim. Confirmed (multiple primary sources agree) is different from pattern observed (directionally consistent but not definitive) which is different from single source (one primary source, not yet replicated).
- Cite specifically. "According to a study" is not a citation. "According to Smith et al. (2024), Figure 3, p.18" is.
- A trend you saw on Twitter is not a finding. A trend confirmed in SEC filings, earnings call transcripts, and industry association data is a finding.
- Gaps are findings. Acknowledging what the research couldn't answer prevents conclusions from overreaching the evidence.

## Web tools
Use `web_search` to locate the source. Use `web_fetch` to read the full document — filings, transcripts, papers. Use `web_extract` when you need one specific fact from a long document without reading the whole thing.
