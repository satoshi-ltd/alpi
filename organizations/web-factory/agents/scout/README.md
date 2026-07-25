# Scout — intake producer

Turns `brief.md` into the factory's two factual inputs: `work/intake.md` and
`src/config/site.json`. Works in two phases: first the `hotel-enrichment`
skill (the ONLY web access in the factory: closed allowlist, corroboration,
never prices, mechanical validator), then the intake itself. Publishes the
canonical slug table every other agent follows, decides theme/makeup, maps
booking id and category, legal identity, navigation (header = commercial
pages; footer = three groups incl. the brand group), tagline in the source
locale, and `brand.logo` when the client supplied one.

- Writes: `work/enrichment.md`, `work/intake.md`, `src/config/site.json`.
- Skills: `intake-interview`, `hotel-enrichment`.
- Operative contract: `agent.md`.
