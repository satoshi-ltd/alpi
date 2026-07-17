# Pre-launch quality checklist

Owned by the `quality` workgroup. Lens enforces. A single fail blocks
`#done launched`. Mira can override only with vera's signoff; overrides
log back to the `quality` wg.

## Accessibility (WCAG AA)
- [ ] Color contrast pass: text 4.5:1, large text 3:1, UI 3:1
- [ ] Semantic HTML: one `<h1>` per page, landmarks (`<header>`, `<main>`, `<footer>`, `<nav>`)
- [ ] Keyboard-only navigation: every interactive element reachable + visible focus
- [ ] Skip-to-content link present and functional
- [ ] All images have meaningful `alt` text (or `alt=""` if decorative)
- [ ] Forms: every input has a `<label>`, errors are programmatically associated
- [ ] No keyboard traps; modal focus returns to trigger on close
- [ ] Touch targets ≥ 44×44 px

## Responsive
- [ ] 360 / 768 / 1024 / 1440 / 1920 all render correctly
- [ ] No horizontal scroll at any width
- [ ] Hero, nav, gallery all degrade gracefully on mobile
- [ ] Typography legible without zoom on mobile

## Performance
- [ ] Lighthouse mobile ≥ 90 (perf / a11y / best-practices / SEO)
- [ ] LCP < 2.5s on a mid-tier mobile (Moto G4 throttle profile)
- [ ] CLS < 0.1
- [ ] INP < 200ms
- [ ] Total JS < 200kb gzipped
- [ ] Total CSS < 50kb gzipped
- [ ] Images served as WebP (apply-assets-manifest output); eager only on LCP image

## SEO
- [ ] Meta title + description set per page per locale
- [ ] Schema.org Hotel JSON-LD valid (validator.schema.org green)
- [ ] Sitemap per locale, listed in robots.txt
- [ ] Canonical URLs correct (per-locale, no cross-locale duplicates)
- [ ] hreflang alternates declared for every page in every locale shipped
- [ ] robots.txt allows crawling, points to sitemap
- [ ] OG and Twitter cards render in debuggers

## Rendered spot-check (headless Chromium — the factory's only real browser)
- [ ] Landing screenshot per locale reviewed with eyes: layout intact, hero/logo render, CTA readable
- [ ] One content page (rooms or dining) spot-checked at 360 and 1440 px

## Content
- [ ] No lorem ipsum anywhere
- [ ] No raw i18n key rendered as text (e.g. `cta.book` shown literally — preflight 4f catches it)
- [ ] No broken images (`<img>` without `src`) — tonal placeholders are valid when assets are missing and the brief allows it
- [ ] Every translation reviewed by lingua (no auto-MT untouched)
- [ ] No "Hotel Placeholder" or template fallback strings
- [ ] Contact details verified against intake (phone, email, address)
- [ ] Geo coordinates verified against intake

## Booking integration
- [ ] Booking engine present per intake (external URL, widget, or N/A)
- [ ] CTA in header + hero + footer all route to booking
- [ ] If widget: renders correctly at 360 and 1440 px (spot-check)

## Final
- [ ] 404 page styled and useful
- [ ] No console errors in production build

## Client handoff (informative — the factory does NOT deploy; nothing here gates launch)
- DNS + SSL on the production domain are the client's to set up; ship a one-page handoff note.
- Legal pages: the template renders `src/content/legal/*.md` (footer links + sitemap appear automatically) — but the TEXT is hotel-supplied verbatim. Hotel sent none → note it in the handoff; agents never draft legal copy. A legal entry with an empty/placeholder body builds NO page (template filters it) — a legal page that ships with placeholder or stub text is a FAIL, never a valid launch state.
- Cookie banner / GDPR consent tooling remains client-side.
