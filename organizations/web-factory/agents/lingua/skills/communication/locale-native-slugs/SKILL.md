---
name: locale-native-slugs
description: Keep content-entry slugs (rooms, posts) clean, ASCII, and identical across locales so per-locale routes line up and hreflang stays consistent. Page route segments are fixed by the template.
category: communication
version: 0.2.0
origin: user
requires_env: []
tools: [read_file, search, write_file, edit_file]
keywords: ['i18n', 'slugs', 'urls', 'seo', 'hreflang']
created_at: 2026-05-29
---

## When to use
When lingua replicates content into target locales.

## What is fixed vs what you control
- **Page route segments are fixed by the template** — `/[lang]/rooms/`,
  `/[lang]/amenities/`, `/[lang]/dining/`, etc. The same segment appears
  under every locale (`/es/rooms/`, `/fr/rooms/`). You do NOT set these.
- **You control the slugs inside content entries** — `rooms/<slug>.<lang>.json`
  and `posts/<slug>.<lang>.md`.

## The rule
A room (or post) `slug` is **stable, ASCII, and identical across every
locale**: `sea-suite.es.json`, `sea-suite.en.json`, `sea-suite.fr.json` all
carry `"slug": "sea-suite"`. That alignment is what makes `/es/rooms/sea-suite/`
↔ `/en/rooms/sea-suite/` line up and lets the fixed `Seo.astro` emit correct
`hreflang` alternates.
- ASCII only — no accents: `sea-suite`, not `suite-del-már`.
- Do NOT translate the slug per locale — only the `name` + copy translate.
- Never rename a slug mid-translation — it breaks the hreflang chain.

> Locale-native page paths (`/es/habitaciones/` instead of `/es/rooms/`)
> would be a template change — forge's call, not a per-project one. Flag it
> to forge if a market needs it; don't fork the routing per project.

## Voice
- Slugs are stable identifiers, not copy. Keep them ASCII and shared across
  locales; translate the name, not the URL.
