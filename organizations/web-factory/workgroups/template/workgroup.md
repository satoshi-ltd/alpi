---
hub: forge
members: [canvas, atlas, lingua, lens]
budget_usd: 50.0
---

The Template workgroup evolves the master Astro template — the git base repo `satoshi-ltd/alpi-mirai-web-factory` that every hotel project clones into `projects/<slug>`. Members work on a checkout of that repo. Each member owns one layer of the template: Forge the framework and build, Canvas the design tokens and components, Atlas the SEO scaffolding and performance budget, Lingua the i18n setup and fallback rules, Lens the accessibility and QA baseline baked into the template. Lessons from live projects funnel back here — when a pattern recurs across three or more hotels, it lands in the template; when something keeps breaking, the template grows a check for it. Every significant change ships as an ADR under the repo's `decisions/` (which travels into every clone at `projects/<slug>/decisions/`) so the next person opening the template knows why something is the way it is. Existing projects are full clones and receive nothing automatically — a landed template change reaches a live project by pulling and merging the base repo inside `projects/<slug>`, followed by a rebuild. The mission is to keep the template strong enough that ~80% of any project is fill the blanks — when that ratio tilts, the template is wrong, not the project.
