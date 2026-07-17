---
name: make-logo-svg
description: Author a hotel logo / wordmark directly as SVG from the brand tokens — vector, on-brand, no image model. First choice when the hotel has no logo.
category: creative
version: 0.1.1
origin: user
requires_env: []
tools: [read_file, write_file]
keywords: ['logo', 'wordmark', 'svg', 'brand', 'vector', 'mark']
created_at: 2026-06-05
---

## When to use

The hotel provided no logo (or an unusable one) and the site needs a mark. A
text LLM can't make a photo, but it writes clean SVG — perfect for a wordmark
or simple emblem, and it scales and recolours for free.

## Inputs
- Brand name + the 3 "feel" words from the brief.
- Brand tokens (accent / secondary, type feel) — from the brief or the
  workgroup's brand advice. If none, use the chosen theme's defaults.

## Procedure
1. Decide the mark type from the feel: a **wordmark** (styled hotel name) is the
   safe default; add a small emblem only if the brand clearly calls for one.
2. Compose the SVG by hand: a tidy `viewBox`, the accent token for fills, a
   generic `font-family` stack (or convert the wordmark to `<path>` so it renders
   without the font installed). Keep it to a handful of shapes — restraint reads
   as premium.
3. Write the SVG — **workgroup** (`#task` with a slug) → `projects/<slug>/assets/logo.svg`
   (+ a manifest entry); **direct chat** (no slug) → `out/<descriptive-name>.svg`
   (your profile home), never a `projects/...` path. Provide a monochrome-safe
   version (single `currentColor` fill) so it works on light and dark headers.

## Quality bar — self-contained, local-first
- **Every `<text>` MUST carry `textLength` (~90% of the viewBox width) +
  `lengthAdjust="spacingAndGlyphs"`** — you cannot measure font metrics, and
  without it a long name overflows the viewBox and the SVG clips it
  ("[ARLENE SUITE"). `textLength` pins the rendered width, always.
- Crisp at 24px and at 400px (it's vector — verify the geometry, not a raster).
- **NO remote anything**: never `@import`, never `url(https://…)`, no Google
  Fonts, no embedded raster, no `<image>` href. The SVG must render identically
  offline and inside `<img>`. Use a generic `font-family` stack (e.g.
  `Georgia, 'Times New Roman', serif`) **or** convert the wordmark to `<path>`.
- Recolourable: fills reference the token / `currentColor`, not hardcoded one-offs.

## Handoff
Report the path and the mark type (wordmark / emblem) and the tokens used. Never
`#done`/`#task`.
