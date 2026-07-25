---
name: project-build
description: Build and verify one cloned hotel project with the commands owned by the current Astro template.
category: software
version: 1.0.0
origin: user
requires_env: []
tools: [read_file, search, terminal]
keywords: ['build', 'astro', 'verify', 'dist']
created_at: 2026-05-29
---

## When to use

After intake, assets, content and translation are complete.

## Inputs

- `src/config/site.json`
- `src/content/**`, except the content schema
- `assets/manifest.yaml` and `assets/source/**`
- `factory/template-spec.json`

## Build flow

1. Install dependencies with `npm ci` when a lockfile is present, otherwise
   `npm install`.
2. Run `npm run verify`. This is the complete selected-tier verification path.
3. For interactive review, use `npm run preview` and then `npm run serve`.
4. For three-theme internal review only, use `npm run preview:all` and then
   `npm run serve:all`.

`npm run build` produces the clean selected-tier `dist/`. The multi-theme draft
artifact is never the project deliverable.

## Boundaries

Do not edit runtime, components, styles, schemas or build scripts to force a
project through. Route data, content, locale and asset failures to their owner.
Do not deploy, create repositories, stage, commit or push.

## Handoff

Report the selected theme, commands run, `dist/` path, and exact pass/fail output.
