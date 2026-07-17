# The 4 starters — one passport per template

Curated by the `brand-library` workgroup. Each starter exists because a hotel
TYPE exists; everything below is the definition agents reason from. The
machine half (rubric, defaults, fonts, binding fields) lives in
`factory/template-spec.json`; this file is the judgement half. If they ever
disagree, the spec wins and this file gets fixed here.

---

## boutique

- **Who**: independent, design/editorial story, <40 rooms, gastronomy as a
  selling point, quiet luxury — never a chain feel.
- **Look**: Cormorant Garamond + Jost, warm earth accent `#9c6a45`, zero
  radius, generous air, hairline borders. Editorial, not decorated.
- **Voice**: editorial and evocative; people and place over features;
  headlines that read like a sentence, not a label. Never "luxury",
  never superlatives.
- **Signature structure**: centered header; overlay hero with discreet
  booking below; about strip on landing; rooms as 2-col editorial cards;
  reviews bordered, not filled; about page may carry a 3-value manifesto
  (`about.values[]`).
- **Photography**: photography-heavy — warm natural light, lived-in rooms,
  texture details (linen, tiles, daylight). Muse leans editorial: one
  striking hero beats a complete gallery.

## budget

- **Who**: price-competitive, 2–3★/hostel, competes with OTAs head-on,
  high volume, no frills.
- **Look**: Archivo everywhere, OTA blue `#1f6feb`, green price accents,
  dense spacing, small radii. Information first.
- **Voice**: clear, direct, factual; price and inclusions up front; short
  sentences; "free" is a feature, say it.
- **Signature structure**: compact hero with price hook; rooms LIST (image
  left, price right) on the listing page; amenities as a dense grouped
  checklist (`amenities[].category`: most popular / in your room / good to
  know); offers carry `discountPct` badges and a promo `code` box.
- **Photography**: functional and honest — bright, sharp, true-to-size
  rooms; no moody editorial. Show the bed, the bathroom, the breakfast.

## business

- **Who**: city/airport, corporate guest, meetings & events, work stays,
  location-led.
- **Look**: Libre Franklin, navy `#1e3a5f`, utility bar above the header,
  ordered grid, small radii. Efficiency reads as competence.
- **Voice**: efficient and sober; numbers and logistics (minutes, capacity,
  Mbps); no warmth theater. Bullet beats paragraph.
- **Signature structure**: utility bar (phone + lang); meeting rooms TABLE
  on amenities (`meetings[]`: name, capacity, AV); location page renders
  distances as a transit-time table; offers read as programs (corporate
  rate / long stay / loyalty).
- **Photography**: clean, daylight, desk-and-workspace forward; meeting
  rooms set up and empty; the city out the window.

## resort

- **Who**: holiday destination, beach/mountain/island, families, spa &
  activities, the getaway.
- **Look**: Quicksand, lagoon teal `#0d8a8a` with a warm second accent,
  large radii, full-bleed imagery, shadow cards.
- **Voice**: warm and aspirational; experiences over specs; days described,
  not rooms listed. Playful is fine, childish is not.
- **Signature structure**: tall overlay hero with prominent CTAs;
  experiences tiles ARE the amenities page (`experiences[]`); villas as
  shadow cards; offers as escape packages with included-items lists.
- **Photography**: immersive and saturated-but-real — water, horizons,
  families mid-activity; golden hour welcome. The pool shot is the hero
  until a better one exists.

---

**Shared rules**: luxury intentionally stays out (one-off if a client
lands). A hotel customises 4–6 tokens, never 40 — if a brief needs more,
the starter is wrong or the request is a new starter (only when intake
data shows a recurring unserved segment). Structure differences above are
TEMPLATE features, not per-project work: agents fill data, the template
carries the layout.
