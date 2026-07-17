# Restore brief · Casa del Patio

**Source**: synthetic confirmed data pack for web-factory acceptance testing
**Outcome**: hotel signed. Kickoff to factory authorised.
**Purpose**: fixture for `proj-casa-patio-restore` — exercises the
hotel-supplied-photos path: muse must TRIAGE and RESTORE the photos in
`assets/` into their specific inventory slots, never regenerate from scratch.

This file is intentionally complete. Agents should not ask follow-up
questions or invent facts.

---

## Restore acceptance

- Expected theme: `boutique`.
- `assets/` ships 3 hotel photos: `patio-room.jpg` (the Patio Room),
  `master-suite.jpg` (the Master Suite), `courtyard.jpg` (the central
  courtyard — hero material).
- Muse restores each to professional standard and wires them via
  `assets.yaml`: the room photos to `rooms.patio-room.image` /
  `rooms.master-suite.image` (**kind: restored**, slugs verbatim from the
  intake inventory), the courtyard as `home.hero.image` (restored).
- No logo exists → muse authors the wordmark SVG.
- Expected outcome: `launched` without fix loops or `#done BLOCKED`; the
  built home and both room pages ship real `/img/` photos.

## Project metadata

- **Project slug**: `casa-patio-restore`
- **Legal/display name**: Casa del Patio
- **Domain**: `casadelpatio.es`
- **Site URL**: `https://casadelpatio.es`
- **Default locale**: `es`
- **Locales**: `es`, `en`
- **CMS**: none
- **Booking provider**: Mirai
- **Booking property ID**: `100379008` (Mirai demo — no real id for a test hotel)
- **Booking fields**: check-in, check-out, guests, rooms

## Identity and positioning

- Family-run boutique guesthouse in Seville's Santa Cruz quarter, Spain.
- 9 rooms in a restored 18th-century patio house around a central courtyard.
- Independent, design/editorial story, gastronomy nearby (no own restaurant).
- Star rating: 3. Price level: upper-mid.
- Brand keywords: warm, handmade, unhurried.
- Tagline: `A courtyard house in the heart of Seville.`

## Contact and booking

- **Address**: Calle del Agua 12, Barrio de Santa Cruz, 41004 Sevilla, Spain.
- **Coordinates**: 37.3851, -5.9905.
- **Phone**: +34 954 11 22 33.
- **Email**: hola@casadelpatio.es.

## Pages

Enable: `landing`, `rooms`, `roomDetail`, `amenities`, `gallery`,
`location`, `about`. Disable: `dining` (no restaurant), `offers`, `blog`.

## Room inventory

Currency: EUR. Slugs below are canonical — quill's files and muse's asset
slots use them verbatim.

1. **Patio Room** — slug `patio-room`
   - Count: 6 rooms. Size: 17 m². Capacity: 2. Bed: 1 queen.
   - View: central courtyard. Price from: 132.
   - Amenities: walk-in shower, air conditioning, fast Wi-Fi, handmade tiles.
   - Summary: bright rooms with wooden shutters opening onto the courtyard.
   - Photo supplied: `assets/patio-room.jpg` — restore it.

2. **Master Suite** — slug `master-suite`
   - Count: 3 rooms. Size: 29 m². Capacity: 2. Bed: 1 king.
   - View: rooftop terrace side. Price from: 219.
   - Amenities: sitting area, beamed ceiling, bathtub, fast Wi-Fi.
   - Summary: the top-floor suites under the original wooden beams.
   - Photo supplied: `assets/master-suite.jpg` — restore it.

## Amenities

1. **Central courtyard** — the 18th-century patio with plants and a fountain;
   breakfast is served here in summer. Photo: `assets/courtyard.jpg` doubles
   as hero material.
2. **Honesty bar** — self-service bar in the old kitchen, on trust.
3. **Roof terrace** — small terrace with views over Santa Cruz rooftops.

## Location

- Real Alcázar: 250 m, 4 minutes on foot.
- Seville Cathedral: 400 m, 6 minutes on foot.
- Plaza de España: 1.1 km, 14 minutes on foot.
- Santa Justa station: 2.3 km, 10 minutes by taxi.

## Visual policy

**Photos supplied in `assets/` — restore them, do not regenerate from
scratch.** Muse triages each photo with its eyes, restores it (relight,
declutter, professional framing — preserving every real element) and wires
it to its slot with `kind: restored`. Logo: none exists — author the
wordmark SVG. No extra gallery needed.

## Content guardrails

- Write Spanish first, then English. Keep room names in English as given
  (proper names) with Spanish descriptions.
- No lorem, no `[NEEDS HOTEL]` — this fixture has all required facts.
- Do not edit components, styles, themes, schemas, or TypeScript files.
