# Client brief · Hotel Kivir

**Source**: facts extracted from the hotel's official site
(hotelkivir.com), 2026-07. Real client rebuild — a live Mirai property.
**Outcome**: kickoff to factory authorised.

Raw client brief — agents read it, never edit. Facts not stated here are
omitted (never invented); pricing is dynamic via Mirai, so no `priceFrom`.

---

## Project metadata

- **Project slug**: `hotel-kivir`
- **Legal/display name**: Hotel Kivir
- **Domain**: `hotelkivir.com`
- **Site URL**: `https://www.hotelkivir.com`
- **Booking provider**: Mirai
- **Booking property ID**: `100376355`
- **Booking fields**: check-in, check-out, guests, rooms

## Identity and positioning

- Boutique hotel in the heart of Seville, on the banks of the
  Guadalquivir — Paseo de Cristóbal Colón, facing the Mercado del Arenal,
  across the river from Triana.
- 31 rooms. Design-led restoration by Cruz y Ortiz Arquitectos; the pitch
  is light, minimalism, sustainability and exclusivity.
- Taglines: **"Live the light"** · "A orillas del Guadalquivir" · "A city
  full of joy. Of light. Of color."
- Sustainability: Bioscore certification level A, A-grade energy
  certification.
- Kivir Club (direct-booking perks): best online price guaranteed, free
  wellness pack, free bicycles, welcome drink, free minibar, 10% discount
  at the Skyline terrace.
- Never budget, never corporate, never family-resort: quiet luxury with
  Sevillian warmth.

## Theme

Use `signature`. The independent editorial story, 31-room scale,
gastronomy and quiet-luxury positioning match the default signature system.

## Target market and languages

The official site serves **Spanish, English, French, German, Italian and
Portuguese**. Seville draws domestic Spanish guests plus strong French,
Italian, Portuguese, German and Anglophone city-break markets. Decide
`locales` from this market. Source language: Spanish.

## Contact

- **Address**: Paseo de Cristóbal Colón 3, 41001 Sevilla, Spain.
- **Phone**: +34 954 59 13 43.
- **WhatsApp**: +34 689 127 168.
- **Email**: kivir@hotelkivir.com.
- **Instagram**: `https://www.instagram.com/hotelkivir`
- **Facebook**: `https://www.facebook.com/hotelkivir`
- **TikTok**: `https://www.tiktok.com/@hotelkivir`

## Pages

Enable: `landing`, `rooms`, `roomDetail`, `amenities`, `dining`,
`gallery`, `offers`, `location`, `about`. Disable: `blog` (the hotel has
one but no article content is supplied).

## Room inventory

Currency: EUR. Sizes and per-type prices are not published — omit them;
Mirai serves live rates. Standard in-room comfort across types: safe,
Wi-Fi, free minibar, TV, air-conditioning, wooden floors, rainfall
shower.

1. **Deluxe** — slug `deluxe`
   - Capacity: 2. Beds: 1 or 2 beds.
   - View: facing the Mercado del Arenal.
   - Summary: comfortable deluxe rooms with soul and Sevillian light.
   - Description: the entry point to Kivir's quiet luxury — calm,
     light-filled rooms in the heart of Seville, looking onto the
     traditional Arenal market.

2. **Premium** — slug `premium`
   - Capacity: 2. Beds: 1 or 2 beds.
   - View: panoramic Guadalquivir river views toward Triana.
   - Summary: spacious, light-filled rooms over the river.
   - Description: designed for slow mornings — natural light and
     panoramic views of the Guadalquivir and the Triana quarter.

3. **Junior Suite** — slug `junior-suite`
   - Capacity: 2. Beds: double (matrimonial).
   - View: over the Guadalquivir river and the Arenal market.
   - Summary: spacious, welcoming suites bathed in natural light.
   - Description: the generous middle ground — a wide, serene suite
     where the river light does the decorating.

4. **Premium with Terrace** — slug `premium-terrace`
   - Capacity: 2. Beds: 1 or 2 beds. Top floor, exclusive access.
   - Private terrace: 15 m², over the Guadalquivir and the Triana
     bridge.
   - Summary: top-floor rooms with a 15 m² private terrace over the
     river.
   - Description: the house signature — your own terrace above the
     Guadalquivir, the Triana bridge as a backdrop.

## Amenities and services

1. **Rooftop pool and solarium** — plunge pool with skyline views.
2. **Kivir Skyline** — 360° rooftop terrace over the river, Triana and
   the city; premium cocktails, wines and gourmet tapas.
3. **Free bicycles** — explore Seville on two wheels, on the house.
4. **Wellness pack** — free with direct booking.
5. **Free minibar** — in every room.
6. **Coffee Corner** — specialty coffees, select teas, juices and
   canapés in a casual space.
7. **360° virtual tour / 3D booking** — explore the hotel before
   arriving.
8. **Sustainability** — Bioscore level A certification, A-grade energy
   rating.

## Dining

- **Doña Emilia Restaurant** — at the foot of the hotel on the Paseo de
  Cristóbal Colón; Mediterranean cuisine with avant-garde touches built
  on local products; exclusive tasting menu for hotel guests
  (reservation required); Andalusian wineries lead the wine list.
- **Breakfast** — buffet, 8:00–11:00: fresh seasonal fruit, artisan
  breads, top-quality cold cuts and cheeses, made-to-order eggs — with
  panoramic views of the Guadalquivir and Triana.
- **Kivir Skyline** — rooftop bar: premium cocktails, wine selections,
  gourmet tapas over the best views of Seville.
- Tone: refined but warm — Andalusian produce, editorial voice, no
  fine-dining stiffness.

## Location

- Paseo de Cristóbal Colón 3, Seville — riverside, facing the Mercado
  del Arenal, opposite Triana across the Puente de Triana.
- Torre del Oro and the bullring a short stroll along the river; the
  Cathedral and Giralda minutes away on foot.
- Directions copy: Hotel Kivir sits on Seville's riverside promenade,
  where the old city meets the Guadalquivir — Triana across the bridge,
  the Torre del Oro down the promenade, and the Giralda a short walk
  behind.

## Visual policy

Real photos are supplied in `assets/source/` — **reuse them, never regenerate
them from scratch**. Muse inspects each file and maps it to its slot
(`kind: supplied`): `hero-guadalquivir.webp` → `home.hero.image`;
`ambience-seville-*.webp` → home gallery; `restaurant-dona-emilia-*.webp`
→ dining slots; `room-deluxe.jpg`, `room-premium.jpg`,
`room-junior-suite.jpg`, `room-premium-terrace.jpg` → their room slugs.
`logo-kivir.webp` already exists — use it as `brand.logo`, no SVG needed.

## Content guardrails

- Write Spanish first, then the other locales scout selects.
- Keep room names as given. Do not invent sizes, prices or facts not
  above.
- No lorem, no `[NEEDS HOTEL]` in generated project data.
- Do not edit runtime code, components, styles, themes, schemas or scripts.
- Legal pages (privacy/cookies) are hotel-supplied verbatim — do not
  draft.
