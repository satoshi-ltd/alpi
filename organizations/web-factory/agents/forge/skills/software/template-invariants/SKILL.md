---
name: template-invariants
description: Enforce what's locked vs configurable in the master template — five intentional handles only (accent, neutral mode, type pair, hero variant, photography treatment); all else stays consistent across projects
category: software
version: 0.1.0
origin: user
requires_env: []
tools: [read_file, search]
keywords: ['template', 'invariants', 'locked', 'design-system', 'architecture']
created_at: 2026-05-29
---

## When to use

When reviewing a template-change proposal (canvas wants a new component variant, atlas wants a new SEO meta strategy, lens wants a new QA item), or when a per-project request asks for something outside the locked set.

## The five handles

A hotel CAN customise (per starter + per project):

1. **Accent palette**: `--accent`, `--accent-2`, `--accent-ink` (3 values)
2. **Neutral mode**: light / dark / auto (driven by `prefers-color-scheme`)
3. **Typography pair**: `--font-display`, `--font-body` (2 fonts)
4. **Hero variant**: one of `editorial-still` / `price-forward` / `location-led` / `fullbleed-gallery`
5. **Photography treatment**: muse's house style (its AGENT.md: lighting, palette, framing) + the wireframes' photography slots (`library/wireframes/`)

## What's locked (never per-hotel)

- **Ink + bg neutrals** (`--ink-*`, `--bg-*`, `--line-*`) — system consistency
- **Type scale** (`--fs-*`, `--lh-*`) — vertical rhythm
- **Spacing scale** (`--space-*`) — layout integrity
- **Radius scale** (`--r-*`)
- **Container widths** (`--container`, `--container-narrow`)
- **Header height** (`--header-h`)
- **Grid breakpoints** (360 / 768 / 1024 / 1440 / 1920)
- **i18n strategy**: prefixed default locale, fallback chain to source language
- **Content schemas** (`src/content/config.ts` Zod definitions)
- **Schema.org Hotel JSON-LD structure** (atlas owns content, never structure)
- **Accessibility floor**: WCAG 2.1 AA
- **Performance budget**: Lighthouse mobile ≥ 90, LCP < 2.5s, CLS < 0.1, INP < 200ms

## Decision rule

When someone (canvas, atlas, lens, mira) wants to change something:

| Affects | Path |
|---|---|
| One of the 5 handles | Apply per-project via brand starter + tokens override. No template change. |
| A locked invariant, but pattern repeats across ≥3 projects | Bring to the `template` workgroup. Propose with rationale + ADR. |
| A locked invariant, one-off request | Decline. Push back to mira; mira pushes back to the client. |
| Performance budget or a11y floor | Never relax. Mira escalates to vera. |

## Output: ADR

When a template change is justified, write an ADR at `templates/hotel-web/decisions/<seq>-<slug>.md`:

```markdown
# <seq> · <title>

Status: proposed | accepted | superseded
Date: 2026-MM-DD
Authors: forge, <others>

## Context
What surfaced this. Which projects asked. Why the existing handle wasn't enough.

## Decision
What changed. Concrete diff if applicable.

## Consequences
What other agents need to adapt. What rolls back if this proves wrong.
```

## Voice

- "That's a handle" / "That's locked" — terse, clear
- Quote the locked invariant verbatim when refusing
- Always offer the path forward: per-project override OR template-wg proposal, never just "no"
