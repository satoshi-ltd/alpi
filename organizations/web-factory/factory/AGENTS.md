# Hotel project authoring contract

Each hotel lives in `projects/<slug>/`, as an independent clone of the Astro
template repository. The cloned project's `factory/template-spec.json` is the
authoritative contract. Read it before changing project data.

## Required initialization

Immediately after cloning, run from the project directory:

```bash
python3 ../../tools/bootstrap_project.py .
```

This installs dependencies, runs `npm run site:init` to replace the Kivara demo
with neutral project data, restores client-supplied files into `assets/source/`,
and runs `npm run check:intake`.

## Allowed authoring surface

Agents may edit only:

- `src/config/site.json`
- `src/content/**`, except `src/content/config.js`
- `assets/manifest.yaml`
- `assets/source/**`
- project working documents such as `brief.md` and `intake.md`

Do not edit components, layouts, pages, styles, scripts, Astro configuration,
package files or content schemas inside a hotel project. Problems in the shared
runtime belong in the template repository, not in one hotel clone.

## Themes and content

- Available themes: `essential`, `signature`, `immersive`.
- An explicit client selection wins. Otherwise the AI may choose using the
  brief and the template rubric. If neither does, use `signature`.
- Enable only sections supported by real content.
- Never invent rooms, facilities, restaurant services, awards, claims, prices,
  offers or imagery.
- Booking is always configured. Mirai Club exists only when explicitly stated.
- Missing required media is declared as `kind: placeholder` with visible
  descriptive `text` and useful `alt`; it is not silently replaced with a fake
  representation of the hotel. Use `none: true` only when the visual itself is
  intentionally absent.

## Assets

Put original client files in `assets/source/`. Muse assigns each slot in
`assets/manifest.yaml` as `kind: supplied|created|placeholder`. Supplied media is
preferred. Missing required media defaults to a local descriptive placeholder.
Generated media requires explicit client or hub authorization even for safe,
non-factual ambience. `npm run assets:optimize` owns placeholder rendering,
resize, AVIF encoding and budgets.

## Commands

```bash
npm run check:intake
npm run check:content
npm run check:locales
npm run assets:optimize
npm run preview
npm run build
npm run verify
```

Use the phase gate that matches the artifact being produced: `check:intake`
after setup/intake, `check:content` after source-locale authoring, and
`check:locales` after translation. `check` remains the holistic final source
check and must not gate an intermediate phase.

`preview` builds the selected tier in draft mode. `build` creates the clean
single-tier deliverable. The workgroup is currently for testing only: do not
deploy, create repositories, commit or push unless the user explicitly asks.
