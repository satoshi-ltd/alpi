---
name: brand-tokens
description: When a hotel has a real brand kit, recommend the site.json token overrides (accent, accent2, ink/paper/surface, font pair, logo) within the chosen theme. The 4 themes carry the design; this only personalises the brand — never layout or CSS.
category: creative
version: 0.1.0
origin: user
requires_env: []
tools: [read_file, search]
keywords: ['brand', 'tokens', 'theme', 'accent', 'typography']
created_at: 2026-06-01
---

## When to use
Only when the brief carries a real brand kit — logo, brand colours, licensed
fonts. With no kit, the theme defaults are right: reply
`brand tokens skipped · theme defaults apply`. A colour preference is a token,
never a reason to change theme.

## What you produce
A **recommendation** (posted in `proj-<slug>`, not a file) of the `tokens`
override block for `src/config/site.json`, which **scout folds in**
(single-writer — you don't edit site.json):
- `accent` / `accent2` — the brand's primary / secondary (hex).
- `ink` / `paper` / `surface` — only if the brand truly diverges from the
  theme's neutrals; otherwise leave them to the theme.
- `fontHead` / `fontBody` — a pair from the template's `fontOptions`
  (`factory/template-spec.json`), never a font outside the list.
- `brand.logo` — path under `public/img/` once pixel has the asset.

`accentSoft`, `line`, `muted` are **derived** (color-mix) — never set them.

## How
1. Read the brand kit + `factory/template-spec.json`
   (`tokenContract.editable`, `fontOptions`, `defaults[theme]`).
2. Check contrast (WCAG AA): accent-on-paper, ink-on-paper.
3. Post the override block + a one-line rationale; scout applies it.

## Voice
- Concrete values: "accent #a3623f, fontHead Playfair Display, fontBody
  Work Sans". Quote the theme contract when refusing bespoke layout.
