---
name: scope-bend-decision
description: Decide when a client request bends the master template vs fits within the existing handle space. Mira's escalation gate — keeps the factory model intact while honouring real client needs.
category: meta
version: 0.1.0
origin: user
requires_env: []
tools: [read_file, workgroup_post, search]
keywords: ['scope', 'template-fit', 'escalation', 'factory-discipline', 'change-control']
created_at: 2026-05-29
---

## When to use

Whenever a client (via mira directly, or surfaced through scout's intake) asks for something that doesn't obviously fit the template. The decision is binary and mira's:

- **Fits the template**: express it as data — `site.json` (theme + tokens) + `content/**`. Project moves on.
- **Bends the template**: requires a template change. Project pauses; mira escalates to `template` workgroup; forge writes an ADR.

This is the single skill that keeps the factory factory. Without it, every client ask becomes a fork.

## The decision tree

For each ask, walk in order:

### 1. Is the request inside the theme + token space?

The theme (1 of 4) sets the structure; within it the AI overrides only data:
- brand tokens — accent, accent2, ink/paper/surface, font pair (from `fontOptions`)
- logo, brand name, tagline
- locales, nav, which pages are on (`site.json.pages`)

If yes → FITS. It's a `site.json` edit, no escalation.

### 2. Is the request a content / config parameter the model already covers?

Things the data model already accepts:
- Room name strategy (own-name / categorical / hybrid)
- Locale set
- Per-room facts, amenity selection, dining, offers, testimonials
- Page copy + per-page `seo` meta

If yes → FITS. Capture in intake, fill during content.

### 3. Is the request a page already in the inventory?

The template ships 11 pages (landing · rooms · roomDetail · amenities ·
dining · gallery · offers · location · about · blog). Want one that's off?

If yes → FITS. Turn it on in `site.json.pages` and have quill write its
content. A page **outside** the inventory (e.g. a bespoke `/menu/` with a
PDF) is a template change → `template-adr`, only if ≥ 3 projects ask.

### 4. Does the request require changing a locked invariant?

Locked invariants:
- Content schemas (`config.ts` Zod)
- i18n routing strategy
- Performance budget
- Accessibility floor (AA)
- Component contracts (RoomCard structure, AmenityGrid layout, etc.)
- JSON-LD structure

If yes → BENDS. Mira escalates to template workgroup.

### 5. Does the request break a starter's voice/visual contract?

E.g. budget hotel wants editorial photography + serif type. Boutique wants neon accents.

If yes → wrong starter, not a template bend. Mira either:
- Re-evaluates the starter choice with scout
- Or: in genuine cases, accepts that this hotel is "boutique with budget-pricing positioning" (rare) and customises within the boutique starter

### 6. Is the request driven by a third-party constraint?

E.g. booking widget vendor requires a specific HTML structure. Booking.com requires specific schema.org fields.

If yes → mira coordinates with atlas / forge to find the integration shape. Vendor-driven constraints are not "client wants" — they're external requirements that factor into the build.

## Output format

A short post in `proj-<slug>` (and parallel in `template` wg if escalating):

```
Scope decision · proj-<slug> · 2026-MM-DD

Request: "We want our menu page to use a custom layout with full-width food photography and a downloadable PDF version of the menu."

Walk:
  1. Inside the 5 handles? No (custom layout, not just photography treatment)
  2. Brand starter parameter? No (menu page exists for resort but not with PDF download)
  3. Routine addition? Yes, /menu/ is a resort extra — fits url-conventions-extension
  4. Locked invariant? PDF download is new — schemas allow it, but no Astro pattern exists
  5. Voice/visual contract? Fits resort
  6. Vendor? No

Decision: SPLIT
  - "Add /menu/ page" → FITS (atlas adds slug, quill writes content, pixel wires it)
  - "Custom layout with full-width photography" → FITS (variant of hero-fullbleed-gallery, no new component needed)
  - "Downloadable PDF" → BENDS (no Astro pattern in template for downloadable assets per page)

Action: proj continues for FITS items. PDF download escalates to template wg as a candidate ADR. Mira posts in template wg.
```

## Failure modes (the discipline traps)

| Trap | Symptom | Mitigation |
|---|---|---|
| **One-off accommodation** | "Just for this client, we'll handcode it" | Refuse. Either it's a handle or it's a template change. No middle. |
| **Premature template change** | One client asks → ADR drafted → template bent | Wait for evidence: ≥ 3 projects ask, or single high-strategic-value client + explicit vera signoff |
| **Hidden bend in design phase** | Canvas accommodates "just this once" without flagging | Mira reads design-lock posts; flags drift if visible |
| **Cumulative drift** | 10 projects, each with 5% custom = 50% bent template | Quarterly: vera reviews recent projects for cumulative deviation; surfaces patterns |

## When to GRANT a custom one-off (rare)

Only if all three:
1. The client signs a non-template-fit acknowledgement (cost premium, no future support guarantee)
2. The custom work is encapsulated in `projects/<slug>/custom/` (doesn't touch shared template)
3. Vera signs off in `quality` workgroup (logged for portfolio review)

This path exists for the strategic exception, not the routine convenience.

## Voice

- "Fits" / "Bends" — no "kind of fits"
- Always walk the decision tree publicly in the workgroup post — shows the reasoning, sets precedent
- Default to FIT. Errs on the side of factory discipline.
- When you escalate, you escalate to template wg, not directly to forge — the workgroup is the deliberation surface
