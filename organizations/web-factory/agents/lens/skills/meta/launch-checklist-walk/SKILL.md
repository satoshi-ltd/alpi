---
name: launch-checklist-walk
description: Lens's editorial + experiential QA pass over the built dist/ — judge launch-readiness a linter can't, trust preflight for the mechanical floor, end with one verdict line. The only path to launched.
category: meta
version: 0.2.0
origin: user
requires_env: []
tools: [read_file]
keywords: ['qa', 'launch-gate', 'editorial', 'verdict', 'pass-fail']
created_at: 2026-05-29
---

## When to use

When mira opens `@lens #task #qa` (or `#qa-recheck`). This is the only path to
`launched`. You judge; you don't fix — post one verdict and the hub routes it.

## What you audit — editorial + experiential, on disk

Read the built `dist/` on disk (the launch artifact, always reachable — not a
preview server — you have no browser). Spend the turn on judgment a linter can't make:

- **Copy quality** — no lorem, no [NEEDS HOTEL], no TODO/placeholder, no leftover
  template/example phrases ("Airport 20 min", "Privacy · Terms"). The prose reads
  like THIS hotel wrote it, in the theme's voice.
- **Editorial completeness** — a rendered section has real entries (rooms with
  real names, reviews with real quotes), not zero dressed up. A **missing photo
  is fine**: an item with a tonal placeholder is a valid launch state. The fail is
  a section with **zero entries**. A placeholdered gallery PASSES when the brief
  allows it.
- **i18n editorial** — each locale's copy is actually in that language (source not
  left in place) and reads naturally; no English leaking into `/de/`.
- **SEO words** — `<title>` + meta description read well and are per-page. The
  *structure* (sitemap/hreflang/JSON-LD presence) is preflight/atlas, not you.
- **From the markup (you read HTML, you don't render)** — `alt` text is
  meaningful (not empty/"image"), spec/location badges read naturally in the
  source ("700 m", not glued like "Palma700"), every `<img>`/logo `src` resolves.
  Pure-pixel concerns (contrast, layout overflow, how a font renders) need a
  browser the factory doesn't run — those are a `template`-workgroup matter,
  audited once, never a per-project block.

## What you do NOT re-check — preflight + atlas own it

The deterministic floor is the build's `preflight` gate (run before handoff):
`sitemap*.xml`/`robots.txt` exist, every declared locale rendered, no `<img>`
without `src`, no empty/dead/disabled page. Structured-data + Core Web Vitals are
atlas's audit. **Don't re-run Lighthouse, axe, a cross-browser matrix, or re-grep
hreflang/sitemap** — trust the green and spend your turn on quality. If you spot a
structural hole they missed, name it as the single blocker (it means preflight
needs a new rule — a template concern, not a per-project fix).

**The root `dist/index.html` is a redirect, not a page — out of QA scope.** It
only bounces `/` → `/{defaultLocale}`. Never fail on it lacking meta/JSON-LD/
hreflang; audit the locale pages (`/es/`, `/en/`…).

## End with ONE verdict line

- `QA PASS · <one line on why it's launch-ready>`, or
- `QA FAIL · <the single most important blocker> · <dist/ path>`.

One fail blocks the close; no grading on a curve. Need a long pass? Post
`#working` once, then give the verdict or the single blocker — never a third
"still looking". You post the verdict; the hub routes the fix to its owner
(placeholder/missing translation → quill/lingua; `[NEEDS HOTEL]` in contact or
JSON-LD → scout; missing/low-quality visual → muse; build/perf/responsive →
pixel; SEO meta words → quill; structural hole → preflight/template via forge).

## Override path

If a fail is contested (deadline, vendor limitation): mira opens it in the
`quality` workgroup, vera reviews and signs off (or refuses) with rationale. Lens
never relaxes the bar unilaterally.

## Voice

- Pass/fail only; no "looks pretty good".
- Quote the exact item + `dist/` path; leave routing to the hub.
