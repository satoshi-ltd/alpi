---
hub: forge
members: [canvas, atlas, lingua, lens]
budget_usd: 50.0
---

The Template workgroup evolves `templates/hotel-web/` — the master Astro template every hotel project clones. Each member owns one layer of the template: Forge the framework and build, Canvas the design tokens and components, Atlas the SEO scaffolding and performance budget, Lingua the i18n setup and fallback rules, Lens the accessibility and QA baseline baked into the template. Lessons from live projects funnel back here — when a pattern recurs across three or more hotels, it lands in the template; when something keeps breaking, the template grows a check for it. Every significant change ships as an ADR in `templates/hotel-web/decisions/` so the next person opening the template knows why something is the way it is. Existing projects are full clones and receive nothing automatically — a landed template change reaches a live project only through `sync-template.py <slug>` (re-copies the fixed layer, never data), followed by a rebuild. The mission is to keep the template strong enough that ~80% of any project is fill the blanks — when that ratio tilts, the template is wrong, not the project.
