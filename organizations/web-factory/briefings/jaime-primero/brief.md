# Client brief · Hotel Jaime I

**Source**: facts extracted from the hotel's official site
(hoteljaimeprimero.com), 2026-06. Real client rebuild.
**Outcome**: kickoff to factory authorised.

Raw client brief — agents read it, never edit. Facts not stated here are
omitted (never invented); pricing is dynamic via Mirai, so no `priceFrom`.

---

## Project metadata

- **Project slug**: `hotel-jaime-primero`
- **Legal/display name**: Hotel Jaime I
- **Domain**: `hoteljaimeprimero.com`
- **Site URL**: `https://www.hoteljaimeprimero.com`
- **Tourism licence**: HB-004160
- **Booking provider**: Mirai
- **Booking property ID**: `100033800`
- **Booking fields**: check-in, check-out, guests, rooms

## Identity and positioning

- 3-star family resort in Salou, Costa Daurada (Tarragona), Spain.
- More than 700 rooms, all exterior, some with central-pool views.
- The pitch is family holidays with children: "Hotel with children in
  Salou", motto **#FunForAll**. Warm, fun, generous, value-for-family —
  never quiet-luxury, never corporate.
- Brand keywords: family, fun, sunny.
- Tagline: `Family holidays in Salou, where the fun never stops.`
- Reception open 24h, Monday to Sunday.
- Club Jaime I (direct-booking perks): 5% discount, free heated-pool hour
  per day, welcome pack.

## Theme

This is a `resort`. (Family destination, beach/Costa Daurada, pools, splash
park, activities, all-inclusive — the resort rubric signals all fire.)

## Target market and languages

The official site serves **Spanish, Catalan, English, French and Russian** —
a Costa Daurada family resort drawing domestic Spanish + local Catalan guests
plus French and Russian tour markets and UK/international families. Decide
`locales` from this market.

## Contact

- **Address**: Logronyo 16, 43840 Salou, Tarragona, Spain.
- **Phone**: +34 977 38 83 92.
- **Email**: reserves@hoteljaimeprimero.com.
- **Facebook**: `https://www.facebook.com/hoteljaimeprimero`
- **Instagram**: `https://www.instagram.com/hoteljaimeprimero`

## Pages

Enable: `landing`, `rooms`, `roomDetail`, `amenities`, `dining`, `gallery`,
`location`, `about`. Disable: `offers` (perks live in Club Jaime I, no fixed
packages confirmed), `blog` (no articles).

## Room inventory

Currency: EUR. All rooms exterior; pool view optional (chargeable). Standard
in-room services across all types: full bathroom, telephone, satellite TV,
air-conditioning, safe (chargeable), hair dryer, amenities, daily towel
change, daily room cleaning. Sizes and per-type prices are not published —
omit them; Mirai serves live rates.

1. **Family Room** — slug `family-room`
   - Capacity: 4. Beds: 2 double beds. Balcony.
   - Summary: spacious rooms designed for families or groups of friends.
   - Description: the hotel's signature room — two double beds in a roomy,
     cosy space for up to four, ideal for a family holiday in Salou.

2. **Triple Room** — slug `triple-room`
   - Capacity: 3. Balcony.
   - Summary: a very spacious room with every comfort for three guests.
   - Description: room for three with all the comforts for a relaxed family
     stay on the Costa Daurada.

3. **Double Room** — slug `double-room`
   - Capacity: 2. Beds: one double or two singles. Balcony.
   - Summary: the ideal room for a couple's getaway.
   - Description: a comfortable double with a balcony, your choice of one
     double or two single beds.

4. **Single Room** — slug `single-room`
   - Capacity: 1. Beds: one double or two singles. Balcony (most rooms).
   - Summary: every comfort for an individual stay in Salou.
   - Description: a comfortable single-occupancy room, most with a balcony.

## Amenities and services

1. **Pools** — several pools including a heated pool (heated pool free 1h/day
   for Club Jaime I members).
2. **Splash Park** — water slides and splash zone for children (minimum
   height 1.20 m on the slides).
3. **Children's play areas and game room** — indoor and outdoor play spaces.
4. **Animation team** — daytime and night-time entertainment programme for
   the whole family, run by the hotel's own team.
5. **Sports facilities** — on-site sports areas.
6. **Free Wi-Fi** — in common areas.
7. **Transfer service** — airport/train transfer on request (chargeable, via
   Shuttle2Sun).
8. **Pre-check-in** — complete it before arrival to save time at reception.

## Dining

- **Main Restaurant** — buffet dining for families.
- **Show Cooking Restaurant** — live cooking stations.
- **Palm Corner** — outdoor gastro-terrace (opened 2021).
- **Bar and snacks** — poolside bar and snacks.
- All-inclusive available in Standard and Premium options.
- Tone: family buffet, generous and fun — not fine dining.

## Location

- Salou, Costa Daurada — beach resort town in Tarragona.
- Close to PortAventura World (theme park) and the beaches of Salou.
- Directions copy: Hotel Jaime I sits in Salou on the Costa Daurada, minutes
  from the beach and a short hop from PortAventura World — the heart of a
  family holiday on Spain's golden coast.

## Visual policy

Real photos are supplied in `assets/` — **restore them, never regenerate from
scratch**. Muse triages each with its eyes and wires it to its slot
(`kind: restored`): `hero.jpg`/`resort.jpg` → `home.hero.image`; pool, splash
park, slides, water-games, restaurant, show-cooking, Palm Corner, bar and play
areas → the relevant amenity/dining slots and the home gallery. `logo.png`
already exists — use it as `brand.logo`, no SVG needed. No real room photo was
supplied, so the four room types keep tonal placeholders (honest launch
state — never fabricate a room).

## Content guardrails

- Write Spanish first, then the other locales scout selects.
- Keep room names as given. Do not invent sizes, prices or facts not above.
- No lorem, no `[NEEDS HOTEL]` in shipped data.
- Do not edit components, styles, themes, schemas, or TypeScript files.
- Legal pages (privacy/cookies) are hotel-supplied verbatim — do not draft.
