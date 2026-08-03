---
name: multi-locale-translation-pass
description: Produce complete locale variants for every locale declared by the hotel project without changing content structure or facts.
category: communication
version: 1.0.0
origin: user
requires_env: []
tools: [read_file, search, write_file, edit_file]
keywords: ['translation', 'i18n', 'localisation', 'multi-locale']
created_at: 2026-05-29
---

## When to use

After the source-locale content is approved and before the project build.

## Inputs

- `src/config/site.json` for source locale and target locales.
- `src/content/**` for the approved source content.
- The clone's i18n files and route-slug contract.

## Rules

1. Create complete content for every locale in `site.json.locales`.
2. Preserve keys, arrays, image references, IDs, prices, contacts and stable
   entity slugs. Translate only human-facing language.
3. Never invent hotel facts or translate legal text without supplied legal
   source material.
4. Use natural locale-specific copy, not word-for-word output. Check for source
   language leakage on every rendered page.
5. Run `npm run check:locales` and resolve missing locale files, structure mismatches,
   route collisions and untranslated prose before handoff.

## Handoff

Report source locale, completed target locales, warnings for proper nouns, and
the result of `npm run check:locales`.
