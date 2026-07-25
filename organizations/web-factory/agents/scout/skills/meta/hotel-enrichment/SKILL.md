---
name: hotel-enrichment
description: Research ONE prospect hotel from a CLOSED allowlist of public sources — its own site, Booking, Expedia, Tripadvisor, Google — corroborate every fact across ≥2 independent sources, and write only the verified static facts to work/enrichment.md as prose for the intake to consume. Never a price, availability, or personal datum. This is the ONLY place web research happens in the factory.
category: meta
version: 0.1.0
origin: agent
requires_env: []
tools: ['web_search', 'web_extract', 'web_fetch', 'terminal', 'notify']
keywords: ['enrichment', 'research', 'hotel', 'prospect', 'corroborate', 'rooms', 'amenities', 'dining', 'places', 'facts']
---

# Hotel enrichment (prospect research)

Turn a thin brief into a corroborated fact sheet for a hotel that may not yet
exist in Mirai. Research its public footprint, corroborate every fact across
independent sources, and write ONLY verified static facts to `work/enrichment.md`
as prose. This runs BEFORE intake; intake then reads `brief.md` + this file and
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

## Sources & corroboration (no single source wins)
- **Closed allowlist of exactly THREE**: the hotel's official site (when it
  exists), Booking, and Google Places (via `scripts/google_place.py`).
  Nothing else — no Tripadvisor, no Expedia/Hotels.com, no aggregators
  (ReservationDesk, Trivago, Kayak, Agoda, …), even when they rank first.
  Three sources keep the sweep fast; corroboration still requires two.
- **Corroboration gate**: state a fact as verified ONLY when **≥2 independent
  sources on DISTINCT hostnames agree**, the evidence carries a **date**, and the
  source type fits the fact. An OTA that mirrors the official text is NOT a
  second independent source. The official site can be stale — it never wins
  alone.
- Single-source / undated / conflicting / a correction of the brief → it goes to
  **Needs human**, never into the verified section. Never guess a winner.

## google_place.py
The only permitted `terminal` use in this skill is
`python3 scripts/google_place.py "<hotel name> <city>"`. It needs a
`GOOGLE_PLACES_API_KEY` (env or `../secrets/google_places.key`) — if absent, skip
Google and corroborate from the remaining sources. Do not build or transform any
object via other scripts; write the prose yourself.

## Output — work/enrichment.md (prose)
Additive context for the intake, in the brief's source language. Two parts:

```
# Enrichment — <hotel> (<date>)

## Verified facts
Only facts corroborated by ≥2 distinct sources. Write them as clear prose,
grouped by topic (rooms, amenities, dining, location, nearby places, policies).
Each fact names the sources that agreed, e.g.:
- Rooftop pool, adults-only, open 10:00–20:00 (official site + Booking).
- Nearby: Ángel de la Independencia, ~1.2 km (Google + Tripadvisor).

## Needs human
Anything single-source, undated, conflicting, or that contradicts the brief —
with the disagreeing values and where each came from. A person resolves these;
never fold them into Verified.
```

## Testimonials (auto-selected)
When the allowlist sources carry clearly positive guest reviews, add a final
section `## Testimonials (auto-selected)` (header in the brief's language)
with AT MOST 3 entries. Select the ones most beneficial to the hotel:
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
omit the section and say so in the gaps list.

## Self-check gate (mandatory before handoff)
Run `python3 scripts/validate_enrichment.py work/enrichment.md`. It fails on
prices/amounts, off-allowlist sources and volatile ratings. A red validator
means you edit the file and re-run — never hand off over a red check.

## Rules
- **Additive only.** The brief is the client-authorized source of truth. This
  enrichment ADDS public context the brief lacks; it never overrides or
  contradicts a brief fact — a contradiction goes to Needs human.
- Write `work/enrichment.md` and nothing else. Do not touch `site.json`,
  `src/content/**`, or template files.
- If no hotel is named, or the brief already covers everything, write a short
  enrichment noting there were no verified additions.
