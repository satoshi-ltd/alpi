---
name: asset-pipeline-diagnostics
description: Pixel's build-phase diagnostics — run `npm run ship` and, on red, report the EXACT blocker (apply-assets-manifest manifest/source/slot · Zod schema · preflight rule). Pixel never edits images, never runs sharp by hand, never touches public/img.
category: software
version: 0.3.0
origin: user
requires_env: []
tools: [read_file, terminal]
keywords: ['build', 'ship', 'diagnostics', 'manifest', 'preflight', 'assets']
created_at: 2026-05-29
---

## When to use
The `build` phase, and whenever `npm run ship` goes red. You run the
deterministic pipeline and diagnose what broke — you do NOT optimise anything.

## The contract — who does what (you only execute + report)
- **muse** produces assets into `projects/<slug>/assets/` + `assets.yaml`.
- **`apply-assets-manifest`** (first step of `npm run ship`) materialises each
  manifest entry → `public/img/<basename>.webp` and wires its slot — it owns
  `public/img` entirely.
- **preflight** (last step) is the gate (structure, copy floors, image byte
  budget, …).
- **you (pixel)** run `npm run ship` and report. You NEVER hand-edit an image,
  run `sharp` yourself, emit AVIF/WebP by hand, or write into `public/img`.

## The single flow
1. `npm install` (first run), then **`npm run ship`**: `apply-assets-manifest`
   → `astro build` (Zod) → `preflight`.
2. **Green** → hand off, counts from your own `dist/`.
3. **Red** → quote the EXACT blocker the tool named, route it, stop:
   - **apply-assets-manifest** → a missing source file or a slot with no content
     file (`slot X: no content files at …`) is muse's manifest — re-task muse for
     the manifest only, never hand-fix it.
   - **astro build (Zod)** → quote the schema error + the offending
     `site.json`/content entry; route to its author (scout/quill).
   - **preflight** → quote the rule + artifact (`content thin: …`,
     `image over budget: /img/x.webp 410KB`, `raw i18n key …`); route to the
     owner (quill copy · muse assets · scout facts · forge template).
4. Never edit data/images to force a pass, never disable a check, never skip
   preflight — the fix is the author's, routed by the hub.

## Voice
- Quote the exact tool line + artifact path; name the owner. Counts in the green
  handoff. Never "build broken" without the named blocker.
