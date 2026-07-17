---
name: core-web-vitals-audit
description: Audit LCP / CLS / INP per locale + per critical page before launch. Atlas owns the SEO-perf overlap; lens runs the holistic Lighthouse check via the qa walk, atlas does the deeper CWV diagnosis when scores miss the bar.
category: research
version: 0.1.0
origin: user
requires_env: []
tools: [browser, read_file]
keywords: ['cwv', 'lcp', 'cls', 'inp', 'lighthouse', 'performance', 'seo']
created_at: 2026-05-29
---

## When to use

Lens runs Lighthouse during the QA walk and reports a pass/fail. If Lighthouse fails on a Core Web Vital (LCP > 2.5s, CLS > 0.1, INP > 200ms) for any locale or page, atlas runs the deeper audit to find the root cause and assign the fix.

Atlas does NOT run this preventively on every project — the QA walk catches the bar. This skill activates on a Lighthouse miss.

## Inputs

- The Lighthouse report from lens (URL + which CWV failed + on which page/locale)
- `templates/hotel-web/performance/budget.yaml` — the contract thresholds
- The local preview build (`npm run preview` running)

## Approach

### LCP > 2.5s

Most common failure. Causes ranked by frequency:

1. **Hero image too large** — check size, format. Should be AVIF + WebP ≤ 250KB per `image-pipeline-budget` skill
2. **Hero not preloaded** — `<link rel="preload" as="image">` missing in `<head>`
3. **Wrong `fetchpriority`** — hero `<img>` needs `fetchpriority="high"`, others `low` or unset
4. **Render-blocking CSS** — a starter CSS that's > 50KB will block. Check via DevTools coverage tool
5. **External font loading blocking** — `font-display: swap` missing on Google Fonts; or use `<link rel="preconnect">` to fonts.googleapis.com
6. **Server response slow** — only relevant if SSR'd; static export means this is zero

Diagnosis: open DevTools Performance tab, record a load, find the LCP element, trace its critical path.

### CLS > 0.1

Causes:

1. **Image without explicit width/height** — every `<img>` needs both attrs OR aspect-ratio CSS
2. **Web font swap shifts layout** — use `size-adjust` in `@font-face` to match fallback metrics
3. **Lazy-loaded element above-the-fold** — should be eager-loaded
4. **Ad/embed without reserved space** — booking widget needs a placeholder box of known dimensions

Diagnosis: DevTools Rendering panel → enable "Layout shift regions" → trigger a reload, watch for highlighted boxes shifting

### INP > 200ms

Less common on static sites. Causes:

1. **Heavy JS on first interaction** — typically a booking widget that loads on hover
2. **Synchronous third-party scripts** — analytics, chat widgets blocking the main thread
3. **Long-running CSS animations on user input** — replace `animation` with `transform` + `will-change`

Diagnosis: DevTools Performance → record an interaction (click booking CTA) → find the long task

## Output

A diagnosis post in `proj-<slug>`:

```
CWV audit · proj-<slug> · 2026-MM-DD

Failure: LCP 3.4s on /es/rooms/ (target < 2.5s)

Root cause: hero image is rendered AFTER 3 above-the-fold images load.
  - hero.avif (248KB) loads in 1.8s
  - room cards row 1 (3 × 180KB AVIF) loads first, pushing hero
  - hero <img> has no `fetchpriority="high"`

Fix (owner: pixel):
  1. Add fetchpriority="high" to hero <img>
  2. Add <link rel="preload" as="image" href="/images/<slug>/hero.avif"> in <head>
  3. Move room card images to loading="lazy" (they're below fold)

Expected improvement: LCP 3.4s → 1.6s (preload moves hero to first network slot)
```

## Reading Lighthouse reports correctly

Lighthouse is a synthetic benchmark — it simulates a mid-tier mobile (Moto G4 emulation, slow 4G throttling). Real Field Data (CrUX) is different:

- **Lighthouse pass + Field Data fail**: the synthetic doesn't reproduce a real condition (e.g. a region with worse network). Re-test with throttling that matches that region.
- **Lighthouse fail + Field Data pass**: rare; usually means Lighthouse caught a regression that hasn't propagated to real users yet. Fix it.

For pre-launch, Lighthouse is the gate (no Field Data yet). After launch, monitor CrUX via PageSpeed Insights.

## Common failure modes

| Symptom | Cause | Fix path |
|---|---|---|
| LCP perfect on home, fails on rooms | Hero strategy works for home, not rooms | Apply hero preload pattern to ALL pages with above-fold imagery |
| CLS fine in EN, fails in DE | German text expands, wraps unexpectedly | Set explicit `min-height` on text containers, OR use font-fallback `size-adjust` |
| Lighthouse passes once, fails next run | Cold vs warm cache | Run 3 times, use median. Watch for flakiness via network throttling. |
| Lighthouse 89, target 90 | One sub-metric just below threshold | Identify the single failing diagnostic (Lighthouse names it), fix that one |

## Voice

- Numbers, always. "LCP 3.4s, target 2.5s, root cause X."
- One concrete fix per finding. No "investigate further."
- Assign the owner explicitly (pixel for code, atlas for SEO meta, canvas for design tokens)
