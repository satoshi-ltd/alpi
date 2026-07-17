# mirai-hotel-templates (Astro)

One codebase, **4 themes** (boutique · budget · business · resort). An AI
picks the theme from the brief and fills the content — **without touching
components or CSS**. It edits data only: `src/config/site.json` + the
`src/content/` collections.

## Run
```bash
npm install
npm run build     # static dist/  ·  npm run dev for the dev server
```

## How the AI generates a hotel (data only — never `.ts`)
1. **Pick the theme** → `site.json.theme` (`boutique|budget|business|resort`).
   Rubric in `../factory/template-spec.json`.
2. **Brand tokens** → `site.json.tokens` (accent, accent2, ink, paper,
   surface, fontHead, fontBody). Omit to use the theme defaults; `muted`,
   `line`, `accent-soft` derive themselves.
3. **Fill content** → files under `src/content/**`; run `npm run content-check`
   before translation, then Zod validates the complete set at build.
4. **Configure** → locales, contact, `booking` (plugin), `nav`, `pages` on/off.

## Structure
```
src/
  config/site.json        ← the ONLY config file the AI edits (pure data)
  config/site.ts          ← CODE: loads + Zod-validates site.json (do not edit)
  config/site-schema.ts   ← CODE: types + Zod + tokenStyle (do not edit)
  config/examples/        ready site.json configs for other themes — copy over site.json
  styles/
    base.css              shared + derived tokens (do not edit)
    themes/*.css          one file per theme (do not edit)
  content/
    config.ts             Zod schemas (the safety gate — do not edit)
    pages/ rooms/ amenities/ dining/ offers/
    testimonials/ experiences/ posts/   ← content, one file per locale (lang field)
  i18n/*.json                   UI strings (NOT editorial content)
  layouts/BaseLayout.astro      sets data-theme + tokens + fonts; mounts <Seo>
  components/
    primitives/           Button, Image, Badge, Eyebrow, Stars
    blocks/               Header, Footer, Hero, BookingWidget, RoomCard,
                          AmenityGrid, DiningTeaser, GalleryStrip, Reviews,
                          LocationTeaser, Newsletter, OfferCards, ExperienceTiles
    Seo.astro             canonical + hreflang + OG + JSON-LD Hotel + robots
  pages/[lang]/           landing + rooms + roomDetail + amenities + dining +
                          gallery + offers + location + about + blog
  pages/sitemap.xml.ts    self-owned sitemap endpoint (no @astrojs/sitemap)
```

## How the themes work
- **Tokens**: each theme defines the same CSS custom properties with
  different values. `BaseLayout` sets `data-theme` on `<html>` and inlines
  the `site.json.tokens` overrides.
- **Structural variants**: blocks that change shape per theme (`Hero`,
  `Header`, `RoomCard`, the landing section order) branch on
  `const v = site.theme`. The rest is token-driven and reskins itself.

## Booking & language
- `BookingWidget` is a **plugin mount**: fill `site.json.booking` (provider +
  propertyId + fields); the real embed (Cloudbeds, Mirai, SiteMinder…)
  replaces the inner markup. No booking page — the selector lives in landing
  + room detail.
- `LangSwitcher` reads `site.json.locales`. Routes are `/[lang]/…`.

## Images
Paths (`/img/...`) are placeholders: if the file is missing, `<Image>` renders
a tonal wash in the theme accent (no broken icons). pixel optimises the
hotel's real photos from `projects/<slug>/assets/` into `public/img/`.

> AI kit + spec in `../factory/` (AGENTS.md, template-spec.json,
> briefing.template.md, visual-reference.html).
