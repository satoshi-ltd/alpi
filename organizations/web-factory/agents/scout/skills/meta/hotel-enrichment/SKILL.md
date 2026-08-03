---
name: hotel-enrichment
description: Research ONE prospect hotel to fill the gaps its brief leaves, from a CLOSED allowlist of exactly three sources — its own site, Booking, Google Places — corroborating every fact across ≥2 of them, and write only the verified static facts to work/enrichment.md as prose for the intake to consume. Never a price, availability, or personal datum. This is the ONLY place web research happens in the factory.
category: meta
version: 0.3.0
origin: agent
requires_env: []
tools: ['web_search', 'web_extract', 'web_fetch', 'terminal', 'notify']
keywords: ['enrichment', 'research', 'hotel', 'prospect', 'corroborate', 'rooms', 'amenities', 'dining', 'places', 'facts']
---

# Hotel enrichment (prospect research)

Fill the gaps a brief leaves, for a hotel that may not yet exist in Mirai.
Answer the questions the brief leaves open, corroborate each answer across the
allowlist, and write ONLY verified static facts to `work/enrichment.md` as prose. This runs BEFORE intake; intake then reads `brief.md` + this file and
writes `site.json` with no further web access.

This is the ONLY task in which you use the web. In intake you do not research —
you convert the brief and this enrichment into config.

## The hard exclusions (read first)
Record that something EXISTS and WHAT IT INCLUDES — never a number that moves or
a person's data:
- **NEVER write**: a room's price/rate/tariff, date availability, a guest's
  booking or loyalty balance. A prospect has no live rates; once it's a Mirai
  client, price is served live — not our job. "Desde X MXN/noche" IS a price.
  A deposit's AMOUNT is a price too — record that a deposit policy exists,
  never the figure. Review ratings/counts (4.8/5, 9.0/10) are volatile — skip
  them.
- **DO write** the static facts: room types (name, size, beds, occupancy, view,
  in-room amenities), what an amenity/board plan INCLUDES (a yes/no, never an
  amount), hours, location, policies (a deposit *policy*, not the amount),
  nearby places.
- **DO write the hotel's brand colour** when its own site states one you can
  read — a CSS custom property, a declared `theme-color`, or the dominant fill
  of the logo. Write it as a hex under a `Brand colour` line with WHERE it came
  from, in the one shape the gate accepts — the hex first, then the provenance,
  then the tag: `- Brand colour: #b89055 (--color-accent in the official site's
  stylesheet). [src: official-site; exception: brand-colour]`.
  One accent, optionally a darker second. Read it, never
  eyeball it from a screenshot, and never average or invent a palette. This is
  the ONE fact exempt from the two-source gate below, for the reason given
  there.

## The procedure — three steps, in order, and no exploration

Enrichment fills what the brief did NOT say. It is not a survey of the hotel and
it never confirms the client.

**Step 0 — list the gaps.** Read `brief.md` and write down the fields it leaves
empty. That list IS your question set, and it bounds the work: a complete brief
produces one or two questions, a thin one produces eight. You do not decide how
much to research; the brief decides.

**If the brief states it, do not look it up and do not write it.** Re-confirming
a briefed fact costs a lookup and does real damage: it re-attributes the
client's own datum to whatever page you found it on, so the intake ends up
reading a reseller as the authority for the hotel's check-in time.

**Space descriptions are ALWAYS on the list.** For every amenity that is a
space — salones/event rooms, meeting room, bar/lounge, spa, pool, gym, a
described parking — AND for every dining venue (restaurant, buffet, bar,
cafeteria), the official-site extract asks for its description, even
when the brief names the space. Naming is not developing: the description is a
gap by definition, and those corroborated one-liners are what lets the intake
mark the space `summary` and the services page render it as a card instead of
a bare list.

Then, for the questions on your list only:

1. **`python3 scripts/google_place.py "<hotel name> <city>"`** — structured
   address, phone, site and hours in one call, no page reading. Always first.
2. **One `web_extract` per remaining question against the official site**, with
   the question written out. Never a sweep, never following links.
3. **One `web_extract` against the Booking property page** for whatever is still
   open after 1 and 2 — and ALWAYS with guest reviews as one of its questions,
   because Booking is the only source that can supply them. Google cannot: Place
   Details returns `userRatingCount` and omits `reviews` with this API key, and it
   omits them silently rather than failing, so an empty `reviews` array is not
   evidence that the hotel has none. Testimonials are a deliverable of this
   phase, not a bonus — a run that ends with no `## Testimonials` section and no
   stated reason is incomplete.

Stop when the list is answered. An empty list is a valid outcome: hand off a
short enrichment whose `## Verified facts` section contains the exact marker
`[no-verified-additions]`, then optionally explain under `## Notes` that the
brief covered everything.

`web_fetch` has exactly one job here — the brand colour, with `raw=True`,
because the hex lives in a stylesheet or a `theme-color` meta tag that a
Markdown conversion drops. Everything else is `web_extract`.

Measured on a complete brief before this procedure existed: 30 web calls and
2.3M input tokens to produce 753 words, of which the check-in time, check-out
time, parking price and room service were already in the brief. Nine of those
calls were searches — nine decisions, each replaying the whole context. That is
the cost of exploring instead of asking.

## Sources — a closed allowlist of three

The hotel's official site, Booking, and Google Places via `google_place.py`.
**Nothing else.** Not Google Hotels, not a tourism portal, not a local guide,
and above all no reseller or aggregator — Trip.com, GuestReservations, Trivago,
Tripadvisor, Expedia, Hotels.com and the rest are excluded whether or not they
rank first. The validator enforces this as an allowlist, so a citation naming
any other host fails the check.

**Corroboration gate**: state a fact as verified ONLY when ≥2 of those three
agree, the evidence carries a date, and the source type fits the fact. An OTA
mirroring the official text was never a second source, and now it is not a
source at all.

Single-source / undated / conflicting / a correction of the brief → it goes to
**Needs human**, never into the verified section. Never guess a winner.

**The brand colour is the one exception, and only it.** A hotel's own site is
definitionally authoritative for its own visual identity, and no second source
exists — Booking and Google publish no hex. Corroboration exists because
sources disagree about facts; nobody disagrees with a hotel about its own
accent. So the official site alone verifies it. If the site is unreadable or
states no colour, write nothing: absent is a valid answer and the makeup
default is a good one.

## google_place.py
The only permitted `terminal` use in this skill is
`python3 scripts/google_place.py "<hotel name> <city>"`. It needs a
`GOOGLE_PLACES_API_KEY` (env or `../secrets/google_places.key`) — if absent, skip
Google and corroborate from the remaining sources. Do not build or transform any
object via other scripts; write the prose yourself.

## Output — work/enrichment.md (prose)
Additive context for the intake, in the brief's source language. Keep the two
control headings below in English so the gate can validate them; localize their
contents, not their names.

```
# Enrichment — <hotel> (<date>)

## Verified facts
Only facts corroborated by ≥2 distinct sources. Write them as clear prose,
grouped by topic (rooms, amenities, dining, location, nearby places, policies).
Every fact ENDS with a canonical evidence tag — `[src: …]` naming two or more
of `official-site`, `booking`, `google-places`, joined with `+`. A regular fact
needs at least two distinct names. The validator reads that tag and nothing
else, so a fact without one fails and an invented name fails. Prose about
sources is not evidence:
- Rooftop pool, adults-only, open 10:00–20:00. [src: official-site + booking]
- Address and phone match. [src: official-site + google-places]

Those three names are the whole vocabulary. Never write another platform's name
anywhere in the file, tag or prose — the validator rejects the name on sight.
The brand colour is the sole single-source exception and uses its explicit tag.
The line must OPEN with `Brand colour: #RRGGBB`; provenance goes between the hex
and the tag, and the tag still closes the line:
- Brand colour: #123456 (--color-accent in the stylesheet). [src: official-site; exception: brand-colour]

## Needs human
Anything single-source, undated, conflicting, or that contradicts the brief —
with the disagreeing values and where each came from. A person resolves these;
never fold them into Verified.
```

## Testimonials (auto-selected) — required, not conditional
Step 3 asked Booking for reviews, so this section is part of the handoff. Add
`## Testimonials (auto-selected)` (header in the brief's language) with AT MOST
3 entries. If Booking genuinely carries no usable quote, keep the header and
write one line saying which property you checked and why nothing qualified —
an absent section reads as "not attempted", and one run shipped with zero
testimonials for exactly that reason. Select the ones most beneficial to the hotel:
strictly positive, CONCRETE (they name a specific virtue — location, rooms,
service, breakfast — not generic praise), and covering different aspects
rather than three variations of one. Recency is the tie-breaker: among equally
strong quotes ALWAYS pick the newest; nothing older than 18 months, and favour
the last 6 months when available. Prefer quotes in the
site's locales when available. Format: short verbatim quote (≤30 words, no
edits beyond truncation), attribution `— <FirstName> <Initial>., <Platform>,
<month year>`, never a rating number. Record each quote's ORIGINAL LANGUAGE
next to the attribution — Quill writes the source-locale translation and
Lingua reuses the verbatim for the matching locale. Multi-property briefs are
NOT exempt: check each property's Booking/Google reviews, still AT MOST 3
total across the whole brief, and note the property internally in the
attribution. Quill folds these into the `testimonials` collection
automatically — the end-of-pipeline internal review is the human gate, not
this section. No usable reviews after actually checking every property →
keep the header, state which properties you checked and why nothing
qualified, and say so in the gaps list.

## Self-check gate (mandatory before handoff)
From the project directory, run
`npm run check:enrichment` — that exact command is
what the phase gate runs, so its verdict is the phase's verdict. It fails on
prices/amounts, off-allowlist or missing evidence tags, uncorroborated facts and
volatile ratings. A red validator means you edit the file and re-run — never
hand off over a red check.

## Rules
- **Additive only.** The brief is the client-authorized source of truth. This
  enrichment ADDS public context the brief lacks; it never overrides or
  contradicts a brief fact — a contradiction goes to Needs human.
- Write `work/enrichment.md` and nothing else. Do not touch `site.json`,
  `src/content/**`, or template files.
- If no hotel is named, or the brief already covers everything, write a short
  enrichment with `[no-verified-additions]` under `## Verified facts` and the
  reason under `## Notes`.
