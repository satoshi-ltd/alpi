# Visual brief · Marlene Suites

**Source**: synthetic confirmed data pack for web-factory acceptance testing
**Outcome**: hotel signed. Kickoff to factory authorised.
**Purpose**: exercise the Muse↔Quill↔Pixel asset contract end-to-end.

This file is intentionally complete — agents should not ask follow-ups or
invent facts. Unlike the golden brief, this one **requires visuals**: the hotel
has **no logo and no hero photo**, and the site needs a strong first impression.
So Mira must open `#assets @muse` **between intake and content**, and the asset
manifest must flow through to the built site.

---

## Visual policy

**Muse required. No hotel photos supplied. Generate logo + hero before content.**
Scout must emit `visual_assets: required before content` in its intake handoff.

## Visual acceptance

- Mira opens `#assets @muse` **before** `#content` (Muse participates).
- Muse produces at least `assets/hero-main.png` (brand ambience / mood, not a
  fabricated documentary room) and `assets/logo.svg`.
- Muse writes `projects/marlene-suites-visual/assets/assets.yaml` with entries
  carrying `file`, `slot`, and `alt` (e.g. `slot: home.hero.image`,
  `slot: brand.logo`).
- `npm run ship` applies the manifest deterministically (apply-assets-manifest):
  materialises each file to `/img/<basename>.webp` and wires `home.json`
  `hero.image`. Quill writes NO image paths; Pixel runs ship, nothing by hand.
- `npm run ship` is green (build + preflight; no `<img>` without `src`).
- The launched `dist/` home shows the hero image, not only a tonal placeholder.
- Reached without `#content-fix` / `#build-fix` (no fix loops from missing assets).

## Project metadata

- **Project slug**: `marlene-suites-visual`
- **Legal/display name**: Marlene Suites
- **Domain**: `marlenesuites.com`
- **Site URL**: `https://marlenesuites.com`
- **Default locale**: `es`
- **Locales**: `es`, `en`
- **CMS**: none
- **Booking provider**: Mirai
- **Booking property ID**: `100379008` (Mirai demo — no real id for a test hotel)
- **Booking fields**: check-in, check-out, guests, rooms

## Identity and positioning

- Independent design hotel in Palma de Mallorca, Spain.
- 12 rooms, each themed around a 20th-century film icon (the flagship is the
  "Marlene Dietrich 1957" room with a hand-painted mural).
- Reopened after a design-led refurbishment in 2024.
- Star rating: 4. Price level: upper-mid, design-forward, not luxury.
- Brand keywords: cinematic, warm, characterful.
- Voice: editorial, playful-but-considered, never resort-like.
- Tagline: `Stay inside the picture.`

## Theme decision data

Marlene Suites should use the `boutique` theme — independent, under 40 rooms,
strong design/editorial story, character over scale.

## Pages

Enable: `landing`, `rooms`, `roomDetail`, `amenities`, `gallery`, `location`, `about`.
Disable: `offers` (none confirmed), `dining` (no venue), `blog` (no articles).

## Contact and booking

- **Address**: Carrer de la Mar 14, 07012 Palma de Mallorca, Spain.
- **Coordinates**: 39.5696, 2.6502.
- **Phone**: +34 971 22 00 14.
- **Reception hours**: 08:00-22:00.
- **Email**: hola@marlenesuites.com.
- **Wi-Fi**: 600 Mbps fibre, free throughout.
- **Parking**: paid public parking 5 minutes on foot.
- **Pets**: not allowed.

## Room inventory

Currency: EUR.

1. **Marlene Dietrich 1957**
   - Count: 1. Size: 24 m². Capacity: 2. Bed: 2 singles (convertible to king).
   - View: balcony over a quiet garden.
   - Price from: 210.
   - Amenities: hand-painted mural, terrazzo headboard, private balcony,
     600 Mbps Wi-Fi, air conditioning, walk-in shower, local toiletries.
   - Summary: the flagship room, built around its cinematic mural.
   - Description: a design room with a hand-painted Marlene Dietrich mural,
     warm terrazzo, orange accents, and a balcony onto the garden.

2. **Doble Cine**
   - Count: 8. Size: 18 m². Capacity: 2. Bed: 1 queen.
   - View: street or garden.
   - Price from: 165.
   - Amenities: themed décor, 600 Mbps Wi-Fi, air conditioning, walk-in shower,
     writing desk, local toiletries.
   - Summary: compact design doubles, each themed around a film.
   - Description: characterful doubles with cinematic touches and quiet colours.

3. **Suite Estudio**
   - Count: 3. Size: 30 m². Capacity: 2. Bed: 1 king.
   - View: balcony over the garden.
   - Price from: 245.
   - Amenities: sitting area, balcony, 600 Mbps Wi-Fi, air conditioning, larger
     bathroom, local toiletries.
   - Summary: the larger suites for slower, design-led stays.
   - Description: roomier studios with a sitting area and a garden balcony.

## Amenities

1. **Garden patio** — a planted patio with shade and evening lighting.
2. **Fast Wi-Fi** — 600 Mbps fibre throughout, suitable for remote work.
3. **Design library** — a small lounge of film and design books.

## Location

- Palma Cathedral: 700 m, about 10 minutes on foot.
- Passeig del Born: 500 m, about 7 minutes on foot.
- Playa de Can Pere Antoni: 1.2 km, about 16 minutes on foot.
- Palma Airport: 9 km, about 15 minutes by taxi.

Directions copy: Marlene Suites sits just off Passeig del Born in central Palma,
a short walk from the cathedral and the seafront.

## About and story

Marlene Suites is an independent design hotel in central Palma, refurbished in
2024 with a room-per-film-icon concept. It should feel cinematic and warm — a
characterful base for exploring the old town, not a generic boutique concept.

## Gallery and assets

- **No logo and no hero photo were provided.** The hotel has no usable imagery
  beyond what Muse creates.
- The site needs a strong first impression, so Muse must supply a logo (SVG) and
  a brand-ambience hero and write the `assets.yaml` manifest; `npm run ship`
  applies it deterministically. Generated imagery is on-brand ambience — **not** a
  fabricated documentary photo of a specific real room. Room images stay tonal
  placeholders (no real photos supplied) — that is the correct launch state.
- Do not fetch or stock-source imagery.

## SEO intent

- Home: Marlene Suites · design hotel in Palma de Mallorca.
- Rooms: design rooms in Palma · cinematic suites.
- Location: hotel near Passeig del Born, central Palma.

Primary keywords: design hotel Palma, boutique hotel Palma de Mallorca,
hotel Passeig del Born.

## Content guardrails

- Write in Spanish first, then adapt to English.
- Do not write lorem, TODO, or `[NEEDS HOTEL]`.
- Do not enable pages without content.
- Do not edit components, styles, themes, schemas, or TypeScript files.
