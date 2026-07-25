---
name: intake-interview
description: Convert a hotel brief into validated site configuration and an evidence-led intake document for the cloned Astro template.
category: meta
version: 1.0.0
origin: user
requires_env: []
tools: [read_file, search, write_file, browser, web_fetch, web_search, research]
keywords: ['intake', 'discovery', 'theme', 'site-config', 'hotel']
created_at: 2026-05-29
---

# Intake interview

Read `brief.md`, `factory/template-spec.json`, the current site config and the
incoming asset inventory. Write only `src/config/site.json` and `work/intake.md`.

Capture verified identity, location, contacts, source locale, target locales,
rooms, services, dining, offers, club, legal gaps and enabled sections. Never
invent a facility, claim, award, price, policy or image.

Target locales must come from the clone's supported set — the `src/i18n/*.json`
dictionaries, mirrored by `src/config/route-slugs.js`. Never inline a locale
list from memory; read what the clone actually ships.

Theme selection order:

1. explicit client choice;
2. documented AI recommendation from evidence;
3. `signature` fallback.

Use only `essential`, `signature` or `immersive`, and choose a makeup valid for
that theme. Run `npm run check:config` before handoff. Report warnings separately from
blocking errors.
