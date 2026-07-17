# Design library

The design source of the 4 hotel templates (boutique · budget · business ·
resort). This is what the `brand-library` workgroup curates.

## Provenance

Exported from a Claude Design (claude.ai/design) handoff bundle
(`mirai-web-factory`, 2026-05-31) — the session where the whole factory was
designed. Original share: `https://api.anthropic.com/v1/design/h/8kxK_U4Ejz0wfsBCGl-ZJA`.
The design chat transcript lives in that bundle, not in this repo.

## Contents

- `starters.md` — the 4 starter passports (who / look / voice / signature
  structure / photography). The judgement half of the definition; the
  machine half is `factory/template-spec.json`.
- `wireframes/Hotel Wireframes.html` — navigable low-fi canvas: 4 styles × 11
  pages, token tweaks panel, bindings toggle. Open directly in a browser.
- `wireframes/wireframe-kit.jsx` — the shared kit: per-style token sets
  (accent, radius, gap, pad, type), primitives (Nav, BookingBar, Footer, …)
  and the bindings layer.
- `wireframes/pages-core.jsx` — landing, rooms list, room detail (×4 styles).
- `wireframes/pages-content.jsx` — amenities, dining, gallery.
- `wireframes/pages-convert.jsx` — offers, booking, location, about.
- `wireframes/pages-blog.jsx` — blog list + post.
- `wireframes/pages-mobile.jsx` — phone shell, hamburger nav, mobile landing.
- `wireframes/design-canvas.jsx`, `wireframes/tweaks-panel.jsx` — canvas/editor
  infra the HTML needs to render; design-phase tools, not product features.

Wireframe annotations and placeholder copy are in Spanish — they are design
content (hotel-facing placeholder text), same class as the template's example
content fixtures.

## How the pieces relate

- These wireframes are the **structural source of truth** for the template's
  components and per-style variations.
- `factory/visual-reference.html` is the packaged offline render of the same
  design (bindings toggle included).
- `templates/hotel-web/src/styles/themes/*.css` + `factory/template-spec.json`
  (`defaults`, `fontOptions`, `decisionRubric`) are the **production** form of
  the 4 starters.

Design changes flow: wireframes → `template` workgroup decision (ADR when
significant) → `templates/hotel-web/`. The wireframes are reference, not
build input — nothing imports them at build time.
