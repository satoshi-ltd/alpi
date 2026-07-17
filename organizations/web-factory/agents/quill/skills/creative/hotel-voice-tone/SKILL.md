---
name: hotel-voice-tone
description: Write source-locale site content as typed data — page copy, rooms, amenities, dining, offers, testimonials — in the theme's tone, to the binding catalogue. Never invent, never placeholder.
category: creative
version: 0.2.0
origin: user
requires_env: []
tools: [read_file, search, write_file, edit_file]
keywords: ['content', 'voice', 'tone', 'copywriting', 'data', 'i18n-source']
created_at: 2026-05-29
---

## Length floors — PREFLIGHT-ENFORCED (build goes red below them), filler still banned
Hit these with FACTS from `intake.md` (views, materials, distances, who the
room suits); when the facts run out, stop — never pad:
- `rooms/*.description`: **60–100 words** (it carries the whole detail page).
- `pages/home.intro.body`: 50–80 · `about.body`: 70–120 · `dining.description`: 50–80.
- `amenities[].description`: 15–30 · `rooms[].summary`: 10–18 (card lines stay short).
Legal text (privacy/terms) is NEVER yours to write — place hotel-supplied text
verbatim under `legal/<slug>.<lang>.md` only when given.

## When to use
The `content` phase. Quill writes ONLY the source locale
(`site.json.defaultLocale`); lingua translates downstream.

## Inputs
- `projects/<slug>/intake.md` — facts + voice/positioning + the CANONICAL
  room slugs (use them VERBATIM — muse's asset manifest references them
  before your files exist; a renamed slug breaks the build).
- `src/config/site.json` — `theme` (sets the tone) + brand.
- `factory/template-spec.json` → `bindingCatalogue` — the exact keys per page.

## Output — DATA, not markup
Content entries under `src/content/**`, each tagged `"lang": "<source>"`:
- `pages/home.<src>.json` — `hero` (eyebrow/title/subtitle), `intro`,
  `about`, `dining` lead, `location`, and `seo`
  {title, description, keywords}.
- `rooms/<slug>.<src>.json`, plus `amenities/`, `dining/`, `offers/`,
  `testimonials/`, `experiences/` — one JSON file per entry, to the
  catalogue keys.
- `posts/<slug>.<src>.md` — only if the hotel has articles.
You never write components, themes, or `.ts`. Zod validates each entry at
build — a bad shape fails loudly.

## Write directly — don't explore. The project's `content/` is empty by
design; you fill it. **Do not spend the turn searching the filesystem** for
examples — the exact shapes are here, and the template has a full set at
`templates/hotel-web/src/content/**` (read ONE entry there if unsure, then
write). Aim: `write_file` every entry this turn, then hand off.

### Fields per entry (write valid JSON; one file per entry, `lang` = source locale)
`src/content/pages/home.<lang>.json`:
```json
{
  "lang": "es",
  "seo": { "title": "Casa Bahía · Hotel en Cádiz", "description": "…≤160 chars", "keywords": ["hotel boutique cádiz","…"] },
  "hero": { "eyebrow": "La Viña, Cádiz", "title": "…", "subtitle": "…" },
  "intro": { "title": "…", "body": "…" },
  "about": { "eyebrow": "…", "title": "…", "body": "…" },
  "dining": { "title": "…", "description": "…" },
  "location": {
    "directions": "…",
    "map": "https://maps.google.com/…",
    "distances": [{ "label": "La Caleta beach", "value": "3 min" }, { "label": "Airport", "value": "25 min" }]
  }
}
```
The travel-time chips render **only** from `location.distances` (label +
value, real distances from `intake.md`). There is no `travelTimes` /
`highlights` field — `distances` is the one contract. Omit it if the hotel
gave no distances (no placeholder chips).
`src/content/rooms/<slug>.<lang>.json` (slug ASCII, identical across locales):
```json
{
  "lang": "es", "name": "Doble Clásica", "slug": "doble-clasica", "order": 1,
  "summary": "…one line…", "description": "…", "sizeM2": 18, "capacity": 2,
  "bed": "Queen", "view": "Calle o patio", "amenities": ["wifi","aire acondicionado"],
  "priceFrom": 120, "currency": "EUR",
  "featured": true
}
```
`src/content/pages/<page>.<lang>.json` (non-home page copy):
```json
{
  "lang": "es",
  "seo": { "title": "Servicios · Casa Bahía", "description": "…" },
  "title": "Servicios sin aspavientos",
  "intro": { "title": "Lo que importa", "body": "Una conexión fiable, desayuno de verdad y un jardín donde parar." }
}
```
Every page `intro` is an object with optional `title` and `body`; never write
`"intro": "..."`.
`amenities/<id>.<lang>.json`: `{ "lang","title","description","order" }` ·
`dining/<id>.<lang>.json`: `{ "lang","name","summary","description","hours","menu":[],"order" }` ·
`testimonials/<id>.<lang>.json`: `{ "lang","quote","author","rating","order" }`.
Omit any field you don't have a real value for (don't write empty strings or
placeholders). Only create collections the hotel has (per `site.json.pages`).

## Voice per theme (tone comes from the theme + intake, no separate guide)
- **boutique** — editorial, evocative, lots of air. **budget** — clear,
  direct, scannable. **business** — efficient, sober. **resort** — warm,
  aspirational.

## Rules
- Specifics over abstracts: name the bakery, the chef, the metro stop — but
  ONLY facts that are in `intake.md`. A fact you don't have (chef name, a
  dish, a distance) → **omit the line**; never invent it.
- **Never lorem, never `[NEEDS HOTEL]`, never a placeholder** in any value —
  omit the field; the component degrades gracefully. No photo → leave
  `image` out (tonal placeholder renders).
- Read it aloud. Kill clichés ("nestled in", "boasts"). Headlines < 8 words,
  sentences < 22.

## Self-check before handing off
Could you swap this copy onto a competitor's site unnoticed? If so, re-anchor
in 3 hotel-specific details from `intake.md`. Did every entry validate?

## Voice
- Push back on facts-not-given ("I can't write '5-minute walk' without
  intake confirming"). One pass, then lock for translation.
