---
name: locale-native-slugs
description: Keep localized page routes canonical while preserving stable entity slugs across locales.
category: communication
version: 1.0.0
origin: user
requires_env: []
tools: [read_file, search, write_file, edit_file]
keywords: ['i18n', 'slugs', 'urls', 'seo', 'hreflang']
created_at: 2026-05-29
---

## When to use

When translating a project or checking localized routes.

## Contract

- Page paths come from the clone's `routeSlugs` configuration. Use exactly one
  canonical localized URL per page and locale.
- Room and post slugs are stable identifiers. Keep them ASCII and identical
  across locales; translate names and copy, not entity slugs.
- Every canonical page must expose a self-referential canonical URL and
  `hreflang` alternates for every configured locale.
- Do not create a second full HTML page for an alias. Route aliases are an
  upstream template concern.

## Validation

Run `npm run check:content:all` after locale changes. Treat route collisions, missing
alternates, duplicate canonical pages, and untranslated prose as failures.

## Handoff

Report the locales checked, the stable entity slugs, and any route collision.
