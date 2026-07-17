---
name: intake-interview
description: Turn the raw client brief into the site config (src/config/site.json — theme picked via the rubric) plus a prose intake.md the content phase builds on. Data only, never TypeScript.
category: meta
version: 0.2.0
origin: user
requires_env: []
tools: [read_file, search, write_file, browser, web_fetch, web_search, research]
keywords: ['intake', 'discovery', 'theme', 'site-config', 'hotel']
created_at: 2026-05-29
---

## When to use
When mira opens the `intake` task on a new hotel. You read `brief.md` and the
contract, pick the theme, and produce the two things the factory runs on.

## Inputs
- `projects/<slug>/brief.md` — the raw client brief (immutable; your one
  required read; never edit).
- `factory/template-spec.json` — the contract: `decisionRubric` (theme
  choice), `defaults[theme]` (token defaults), `fontOptions`, the page list.
- the optional `--launch-date` from the kickoff.

Do NOT read components, themes, or any `.ts`. The look is fixed by the theme;
you choose the theme, you don't build it.

## Output artifacts (under `projects/<slug>/`)
1. **`src/config/site.json`** — PURE DATA, validated by Zod at build:
   `theme` (rubric call), `tokens` (brand colours/fonts only if the brief
   gives them, else omit → theme defaults), `brand` {name, tagline},
   `url` (the hotel's real domain, e.g. `"https://casabahia.com"` — drives
   canonical/sitemap/robots; if the brief truly lacks it, OMIT it and note
   `[NEEDS HOTEL] domain` in `intake.md` — never invent a domain, and know
   preflight will block launch until a real one is set), `locales` +
   `defaultLocale`, `contact` {phone, email, address, coords},
   `booking` {provider, propertyId, fields}, `nav` {primary, cta,
   showLangSwitcher}, `pages` {…on/off},
   `social` as an **array** `[{ "label": "Instagram", "href": "https://…" }]`
   (NOT an object) — omit if none.
2. **`intake.md`** — prose: theme rationale (cite the rubric signal), voice/
   positioning, and the facts the content phase needs — room inventory
   (name, size, beds, view, price), amenities, dining, location + distances.
3. **Handoff** to `@mira`: theme + signal, source + target locales + evidence,
   suggested launch date, any open gaps.

## Approach
1. Read `brief.md` (twice). Mark facts, voice, audience, photography.
2. Decide from the brief: **source locale** (country + brief's language),
   **target locales** (the real guest mix, not aspiration), **theme** (score
   the 4 with `decisionRubric`, pick the highest, cite the signal).
   **Locales are constrained to the template's supported set, defined in
   `factory/template-spec.json → i18n.supportedLocales` — read it and declare
   ONLY locales from that list.** The UI chrome (nav, buttons, booking
   labels) is translated exactly for that set; declaring a locale outside it
   leaks another language into the chrome and fails QA. If the market
   genuinely needs another (e.g. Japanese), note it in `intake.md` and flag a
   template i18n addition — never ship a project with a locale not in
   `supportedLocales`.
3. Write `site.json`: take `defaults[theme]` for tokens, override only what
   the brand truly justifies (real hex, or a `fontOptions` pair). **Only set a
   `pages` flag `true` when the brief gives real content for it** — empty
   sections are hidden by the template, but don't declare a page the hotel
   can't fill (no articles → `blog: false`; no testimonials → leave them out;
   no offers → `offers: false`).
   **A fact the brief lacks is omitted (leave the key out), never the string
   `"[NEEDS HOTEL]"`** — that marker is prose, it lives only in `intake.md`.
4. Write `intake.md` (the facts + rationale).
5. Verify: `site.json` parses, has a valid `theme` + `brand.name` + `locales`;
   `intake.md` has the room/amenity/dining facts. A bad `site.json` fails the
   build with a clear Zod error — keep it to the schema.
6. Hand off to `@mira`.
7. Optional, only after handing off: `competitive-research` confirms the
   theme; it never decides it and never delays steps 3–6.

## Theme rubric (factory/template-spec.json · decisionRubric)
| Signal | Theme |
|---|---|
| independent · design/editorial · <40 rooms · gastronomy · quiet luxury | boutique |
| competitive price · 2–3★/hostel · competes with OTAs · no frills | budget |
| city/airport · corporate · meetings · business traveler | business |
| destination · beach/mountain/island · families · spa · activities | resort |

Score all four, pick the strongest, cite it. Tie or thin brief → ask. A
colour preference is a token override, not a theme change.

## Voice
- Specific over abstract; quote the client where it sharpens the brief.
- Gaps: `[NEEDS HOTEL]` in `intake.md` prose, omitted in `site.json`.
