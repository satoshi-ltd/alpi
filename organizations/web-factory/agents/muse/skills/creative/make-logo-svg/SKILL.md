---
name: make-logo-svg
description: Author a wordmark as SVG from brand tokens. NEVER for a client hotel's logo — requires explicit written authorization naming this skill, and a missing hotel logo is never a reason to run it.
category: creative
version: 0.2.0
origin: user
requires_env: []
tools: [read_file, write_file]
keywords: ['logo', 'wordmark', 'svg', 'brand', 'vector', 'mark']
created_at: 2026-06-05
---

## When NOT to use — read this first

**A client hotel having no logo is NOT a reason to run this skill.** That was
this skill's original trigger and it was wrong: in four consecutive runs it
produced invented brand identities that were then declared as client-supplied
media. A hotel's logo is its identity, and the factory does not author it.

When a project clone has no logo in `assets/source/`, the correct outcome is:
no `logo` slot in the manifest, no `brand.logo` in
`site.json`, the gap recorded in the handoff, and the template's typographic
brand lockup renders the hotel's name. That path is complete and intended — it
needs nothing from you.

`check:assets` reporting a missing slot reference is likewise never a reason to run this
skill. The fix there is removing the dangling reference, never creating the
asset to satisfy it.

## When to use

Only on **explicit written authorization that names this skill** — from the hub
relaying a client decision, or from the creator in direct chat. Authorization to
"handle the assets", a red gate, or a missing-logo warning are none of them.
Absent that sentence, this skill does not run.

Authorized output never poses as client material: in a project clone the result
is a manifest entry with `kind: created` plus its `generate` provenance, and the
file lands wherever the authorized generation step puts it — never written by
hand into `assets/source/`, which is the client's directory.

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
3. Write the SVG to `out/<descriptive-name>.svg` in your profile home — never
   into a project clone's `assets/source/`, and never a `projects/...` path.
   Provide a monochrome-safe version (single `currentColor` fill) so it works on
   light and dark headers.

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
