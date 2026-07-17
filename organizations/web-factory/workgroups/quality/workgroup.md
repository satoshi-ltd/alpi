---
hub: vera
members: [mira, lens, atlas]
budget_usd: 50.0
---

The Quality workgroup defines and maintains the single pre-launch checklist every hotel project must clear before going live. Accessibility (WCAG AA), Core Web Vitals (LCP < 2.5s, CLS < 0.1, INP < 200ms), responsive breakpoints (360 / 768 / 1024 / 1440 / 1920), SEO minimums (meta, schema.org Hotel JSON-LD, sitemap per locale, canonicals + hreflang), a rendered spot-check in headless Chromium (atlas runs it — the only QA-circuit profile with `browser`; lens stays an editorial gate on the HTML. No device farm, no deploys; DNS/SSL/legal are client handoff, never launch gates), content completeness (no lorem ipsum, no broken images — tonal placeholders are valid when assets are missing and the brief allows it, every translation reviewed). A single fail blocks `#done` — Lens enforces, Mira can override only with Vera's signoff, overrides log back here. The checklist lives at `templates/hotel-web/quality/checklist.md` and evolves only by decisions taken in this workgroup. The goal is not exhaustive QA — it is a barrier consistent enough that "factory-built" means something the client can trust on first launch.
