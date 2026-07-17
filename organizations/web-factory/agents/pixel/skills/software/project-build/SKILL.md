---
name: project-build
description: Take a project from `translation complete` to `build green` — run `npm run ship` (apply-assets-manifest → build → preflight), set SITE_URL, hand the dist/ to lens. The manifest owns public/img; no image, component or schema editing.
category: software
version: 0.2.0
origin: user
requires_env: []
tools: [read_file, search, write_file, edit_file, terminal]
keywords: ['build', 'astro', 'npm', 'assets', 'dist']
created_at: 2026-05-29
---

## When to use
When mira opens the `build` task — scout's `site.json` is on disk and quill +
lingua have filled `src/content/**` for every locale in `site.json.locales`.
You turn data into a green static build with real assets.

## Inputs
- `projects/<slug>/src/config/site.json` (theme + config) and
  `src/content/**` (the content the build renders).
- `projects/<slug>/assets/` — source photos + logo the hotel provided
  (local-first; may be empty).

## What you do NOT touch
`src/components/`, `src/styles/themes/`, `src/config/*.ts`,
`src/content/config.ts`. That is the fixed design layer. You touch
`public/img/` and run the build — nothing else.

## Approach
1. **Build** — `npm install`, then `SITE_URL=https://<domain> npm run ship`
   (domain from `site.json` / the brief). **`ship` is the only valid build
   path** — it runs `apply-assets-manifest` (materialises every `assets.yaml`
   asset into `public/img/` and wires its slot deterministically — you never
   optimise or wire images by hand), then the **Zod** build, then **preflight**.
   A missing photo is fine: the `<Image>` component renders a tonal placeholder,
   never a broken layout. Never fetch from a URL; never invent or stock images.
2. **Triage** — if `ship` fails on data, it is the **owner's** fix, not
   yours: tag scout (site.json / contact), quill (content/copy), or lingua
   (a locale's entries). Never edit content to force a pass; never disable a
   check. Your job is a green `ship`.
3. **Hand off** — `dist/` is the launch artifact. Post:
   `@mira · build complete · npm run ship green · dist/ at projects/<slug>/dist/`.

## Common failure modes
| Symptom | Cause | Fix |
|---|---|---|
| Zod error on `site.json` | bad/missing field | tag scout — it's the config |
| Zod error on a content entry | missing required field | tag quill/lingua |
| locale page empty | a declared locale has no content | block on lingua |
| build times out | oversized image in `public/img/` | compress to budget |

## Voice
- Numbers in the handoff: page count, locales, bundle size.
- Surface + block data issues to the owner; never guess-fix content.
- Never disable a check to make a build pass.
