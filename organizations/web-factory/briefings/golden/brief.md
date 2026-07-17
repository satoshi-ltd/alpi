# Golden brief · Casa Bahía

**Source**: synthetic confirmed data pack for web-factory acceptance testing
**Commercial (Mirai)**: María Ruiz
**Outcome**: hotel signed. Kickoff to factory authorised.
**Purpose**: happy-path one-shot fixture for `proj-casa-bahia-golden`.

This file is intentionally complete. It is not rough sales discovery. Agents
should not ask follow-up questions, invent missing facts, or mark anything as
unknown. Use it to prove the project workgroup can move from intake to launch
without fix loops.

---

## Golden acceptance

- Expected theme: `boutique`.
- Expected default locale: `es`.
- Expected locales: `es`, `en`, `fr`, `de`.
- Expected pages: rooms, room detail, amenities, dining, gallery, location,
  about, landing.
- Expected disabled pages: offers, blog.
- Expected outcome: `launched` without `#done BLOCKED`, `#intake-fix`,
  `#content-fix`, `#translation-fix`, `#build-fix`, or `#qa-recheck`.
- Missing photos are acceptable. If `projects/casa-bahia-golden/assets/` is
  empty, tonal placeholders are a valid launch state.

## Project metadata

- **Project slug**: `casa-bahia-golden`
- **Legal/display name**: Casa Bahía
- **Domain**: `casabahia.es`
- **Site URL**: `https://casabahia.es`
- **Default locale**: `es`
- **Locales**: `es`, `en`, `fr`, `de`
- **Launch target**: 2026-08-31
- **CMS**: none
- **Booking provider**: Mirai
- **Booking property ID**: `100379008` (Mirai demo — no real id for a test hotel)
- **Booking fields**: check-in, check-out, guests, rooms

## Identity and positioning

- Family-run boutique hotel in Cádiz, Andalucía, Spain.
- 18 rooms across two restored 19th-century buildings.
- Founded in 1947 by Carmen González; now run by third-generation owner María
  González.
- Reopened after a full restoration in May 2022.
- Located in Barrio de La Viña, 180 m from La Caleta beach.
- Star rating: 4.
- Price level: upper-mid, not luxury.
- Target guests: Spanish couples year-round, French families in summer,
  German couples in shoulder season, and English-speaking winter travellers.
- Competitive edge: character, family hospitality, local food, walkable Cádiz.
- Brand keywords: warm, considered, lived-in.
- Voice: editorial, people-led, specific, never resort-like.
- Tagline: `A Cádiz house with the sea around the corner.`

## Theme decision data

Casa Bahía should use the boutique theme.

- Independent family hotel.
- Under 40 rooms.
- Design/editorial story around restored houses and neighbourhood life.
- Gastronomy is a real selling point.
- Tone is warm and considered, not budget, corporate, or resort.

## Contact and booking

- **Address**: Calle Venezuela 8, Barrio de La Viña, 11002 Cádiz, Spain.
- **Coordinates**: 36.5306, -6.3011.
- **Phone**: +34 956 22 18 47.
- **Reception hours**: 08:00-22:00.
- **Email**: reservas@casabahia.es.
- **Group sales**: same phone/email, ask for Tomás González.
- **Instagram**: `https://instagram.com/casabahia.cadiz`
- **Facebook**: `https://facebook.com/casabahiacadiz`
- **Pets**: allowed in 4 ground-floor rooms, EUR 15/night.
- **Wi-Fi**: 600 Mbps fibre, free in all rooms and common areas.
- **Parking**: no private parking; paid public parking at Parking Campo del
  Sur, 9 minutes on foot.

## Pages

Enable:

- `landing`
- `rooms`
- `roomDetail`
- `amenities`
- `dining`
- `gallery`
- `location`
- `about`

Disable:

- `offers` — no packages or discounts confirmed.
- `blog` — no articles requested.

## Room inventory

Currency: EUR.

1. **Doble Clásica**
   - Count: 9 rooms.
   - Size: 18 m².
   - Capacity: 2 guests.
   - Bed: 1 queen.
   - View: street or interior patio.
   - Price from: 145.
   - Amenities: walk-in shower, 600 Mbps Wi-Fi, air conditioning, handmade
     ceramic tiles, writing desk, local toiletries.
   - Summary: compact restored rooms for short Cádiz stays.
   - Description: warm doubles with original shutters, quiet colours, and the
     choice of street or patio views.

2. **Familiar**
   - Count: 4 rooms.
   - Size: 26 m².
   - Capacity: 4 guests.
   - Bed: 1 queen + 2 singles.
   - View: interior patio.
   - Price from: 198.
   - Amenities: family layout, 600 Mbps Wi-Fi, air conditioning, walk-in
     shower, extra storage, children amenities on request.
   - Summary: flexible family rooms around the quieter patio side.
   - Description: practical rooms for families who want the centre of Cádiz
     without giving up space or quiet.

3. **Doble Superior**
   - Count: 3 rooms.
   - Size: 22 m².
   - Capacity: 2 guests.
   - Bed: 1 king.
   - View: balcony over La Viña streets.
   - Price from: 176.
   - Amenities: private balcony, 600 Mbps Wi-Fi, air conditioning, sitting
     chair, walk-in shower, local toiletries.
   - Summary: brighter doubles with balcony light and more room to settle in.
   - Description: rooms made for longer weekends, with a balcony for morning
     coffee and the sound of the neighbourhood below.

4. **Habitación de la Esquina**
   - Count: 1 room.
   - Size: 24 m².
   - Capacity: 2 guests.
   - Bed: 1 king.
   - View: corner views to the street and inner patio.
   - Price from: 220.
   - Amenities: dual-aspect windows, 600 Mbps Wi-Fi, air conditioning, reading
     chair, walk-in shower, local toiletries.
   - Summary: the most requested room, with light from both sides of the house.
   - Description: María's favourite room, balanced between street life and the
     calm of the interior patio.

5. **Suite Carmen**
   - Count: 1 room.
   - Size: 34 m².
   - Capacity: 2 guests.
   - Bed: 1 king.
   - View: top-floor sea glimpse.
   - Price from: 260.
   - Amenities: sitting area, sea glimpse, 600 Mbps Wi-Fi, air conditioning,
     larger bathroom, local toiletries, welcome tray.
   - Summary: the quiet top-floor suite named for the founder.
   - Description: a generous room for slower stays, with a sitting area and a
     small glimpse of the Atlantic above the rooftops.

## Dining

- **Dining concept**: breakfast and light evening plates rooted in La Viña.
- **Venue name**: La Mesa de Carmen.
- **Breakfast hours**: 08:00-11:00.
- **Evening plates**: 19:00-22:00, Thursday to Monday.
- **Signature detail**: breakfast bread comes from Panadería Salinas across
  the street, run by Pedro Salinas.
- **Tone**: local, home-like, precise; avoid fine-dining language.

Sample menu:

- Toast with Panadería Salinas sourdough, olive oil, and grated tomato.
- Seasonal fruit with sheep yoghurt and orange blossom honey.
- Cádiz cheese board with membrillo.
- Tortillita de camarones with lemon.
- Small plate of tuna with roasted peppers.

## Amenities

1. **Interior garden**
   - Small patio garden with a fountain, tiled benches, shade, and evening
     lanterns.

2. **Breakfast by local producers**
   - Bread from Panadería Salinas, local olive oil, seasonal fruit, and Cádiz
     cheeses.

3. **Fast Wi-Fi**
   - 600 Mbps fibre throughout the hotel, suitable for calls and remote work.

4. **Pet-friendly ground-floor rooms**
   - Four rooms accept pets, with a EUR 15/night supplement and a simple house
     guide for nearby walks.

5. **Neighbourhood recommendations**
   - María's team keeps a short list of family-run restaurants, beaches, and
     flamenco spots within walking distance.

## Gallery and assets

- Real assets may exist in `projects/casa-bahia-golden/assets/`.
- If that folder is empty, the template's tonal placeholders are accepted.
- Do not fetch, invent, or stock-source imagery.
- **Do not task Muse for this fixture** — tonal placeholders are accepted for
  every missing image and logo. This brief validates the pipeline without the
  image API (no generation, no `OPENROUTER_API_KEY` dependency, deterministic).
- Desired image direction if assets exist: moody available light, restored
  shutters, tiled patio, breakfast table, La Viña street corners, and the
  walk to La Caleta.

## Location

- La Caleta beach: 180 m, about 3 minutes on foot.
- Cádiz Cathedral: 900 m, about 12 minutes on foot.
- Mercado Central: 650 m, about 8 minutes on foot.
- Gran Teatro Falla: 350 m, about 5 minutes on foot.
- Cádiz train station: 1.6 km, about 20 minutes on foot or 8 minutes by taxi.
- Jerez Airport: 45 km, about 35 minutes by taxi.
- Public parking: Parking Campo del Sur, 700 m, about 9 minutes on foot.

Directions copy:

Casa Bahía sits on Calle Venezuela in La Viña, the old fishing quarter between
the Atlantic and the historic centre. Guests can walk to La Caleta for a swim,
to the market for lunch, and back through quiet side streets after dinner.

## About and story

Casa Bahía began as Carmen González's family guesthouse in 1947. The two
houses were restored in 2021 and reopened in 2022, keeping shutters, tiles,
and the interior patio while modernising the rooms. María González now runs
the hotel with her brother Tomás. The hotel should feel like a Cádiz home
opened carefully to guests, not like a generic boutique concept.

## SEO intent

Use specific, localized SEO. Do not use generic luxury claims.

- Home: Casa Bahía · boutique hotel in Cádiz near La Caleta.
- Rooms: boutique rooms in Cádiz · family rooms and Suite Carmen.
- Location: hotel in La Viña Cádiz · 180 m from La Caleta beach.
- Dining: breakfast with local Cádiz producers · Panadería Salinas.
- Amenities: interior garden, fast Wi-Fi, pet-friendly rooms.

Primary keywords:

- hotel boutique Cádiz
- hotel La Caleta Cádiz
- hotel La Viña Cádiz
- family hotel Cádiz
- boutique hotel Cadiz

## Content guardrails

- Write in Spanish first, then translate/adapt to English, French, and German.
- Keep room names in Spanish where they are proper names.
- Do not write lorem, TODO, or placeholder copy.
- Do not write `[NEEDS HOTEL]`; this golden fixture has all required facts.
- Do not enable pages without content.
- Do not edit components, styles, themes, schemas, or TypeScript files.
- Missing photos are not a blocker. Use template placeholders.
