---
name: media-update
description: Trigger the declared media-update pipeline and handle explicit skips or red gates while the daemon sequences its verified phases.
category: meta
version: 2.0.0
origin: user
requires_env: []
tools: [read_file, terminal, search, workgroup_post, write_file]
keywords: ['media', 'photos', 'logo', 'assets', 'chain', 'phase-2']
created_at: 2026-07-29
---

# Media update

Client photography arrives after the site exists. Trigger the chain once:
`alpi -p mira workgroup trigger <wg_id> media-update` (or the Run action in the
app). The daemon authors the opener from the recipe and owns the order below:
after each green gate it closes that phase and opens the next one. Never write
that opener yourself and never re-state the order in a post.

| Phase | Owner | Gate |
|---|---|---|
| 1. manifest — map every supplied file to its slot | muse | `npm run check:assets` |
| 2. config — logo and gallery keys, only if step 1 changed either | scout | `npm run check:intake` |
| 3. rebuild | pixel | `npm run check:build` |
| 4. audit | lens | verdict-owned close · self-check `npm run check:audit` |

A phase whose owner has nothing to do posts `#skip`; close it explicitly with
`#done skipped · <reason>` — it renders as skipped, not completed, and the chain
still advances. A red gate re-tasks the SAME phase with its findings, never the
next one.

## Phase 2 is conditional, not disposable

Real media is worthless until something references it. Measured across a
seven-hotel fleet, this chain died at `media-config` in every project that supplied a
logo: the files were optimized into `dist/img/` and no page pointed at them, so
each site published without the hotel's own mark while every gate stayed green
except one orphan-asset error that blames the image rather than the missing
reference.

So `media-config` is NOT optional when `media-update` declared the `logo` slot or
any `gallery-*` slot. Its task must leave the config pointing at those slots:
`brand.logo` must be the bare slot name (`"logo"`), never a path and never the
client's filename. There is one logo slot and it renders on ink.

## The chain is complete when Lens says so

`#done media-update complete` after the first phase is a false claim: the
manifest names files, it does not publish them. The run is complete only after
`media-config`, `media-build` and `media-qa` close through their gates — the
console and both apps show it as `completed` when that happens, and not before.
