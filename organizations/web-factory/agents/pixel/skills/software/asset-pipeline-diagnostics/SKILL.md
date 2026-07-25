---
name: asset-pipeline-diagnostics
description: Diagnose the template-owned asset optimizer and manifest checks without manually creating derivatives.
category: software
version: 1.0.0
origin: user
requires_env: []
tools: [read_file, terminal]
keywords: ['assets', 'manifest', 'optimizer', 'budget', 'diagnostics']
created_at: 2026-05-29
---

## When to use

During the assets phase or when `npm run assets:optimize` or `npm run check`
fails.

## Contract

- Client originals live in `assets/source/**`.
- `assets/manifest.yaml` records each required slot as `kind: supplied`,
  `kind: created`, or `kind: placeholder`; `none: true` means the visual is
  intentionally absent. Placeholders require visible descriptive `text` and
  useful `alt`.
- `factory/budget.yaml` owns dimensions and byte budgets.
- The optimizer owns local placeholder rendering and `public/img/**`. Never
  hand-edit optimized derivatives or fetch an external placeholder URL.

## Flow

1. Run `npm run assets:optimize`.
2. Run `npm run check`.
3. On failure, quote the exact slot, source file, format, dimensions or budget
   reported by the tool.
4. Route manifest/source issues to Muse and configuration or optimizer defects
   to the template workgroup.

Never bypass a budget, substitute an unconfirmed image, or run a separate
image pipeline.
