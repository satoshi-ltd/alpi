---
name: project-lifecycle
description: Coordinate a cloned hotel project from setup through local QA; Mira alone records phase changes and routes failed gates back to their owner.
category: meta
version: 1.1.0
origin: user
requires_env: []
tools: [read_file, terminal, search, workgroup_post, write_file]
keywords: ['lifecycle', 'state-machine', 'testing', 'iteration', 'status']
created_at: 2026-05-29
---

# Project lifecycle

Use this lifecycle for every hotel clone:

`setup → intake → assets → content → translation → build → qa → test_ready`

Mira is the only agent that changes the recorded phase. This organization is
test-only: `test_ready` means the local artifact passed its gates, not that it
was deployed or approved for production.

## Required evidence

| Phase | Owner | Evidence |
|---|---|---|
| setup | mira | clone contains `factory/template-spec.json`; bootstrap completed |
| intake | scout | `src/config/site.json` and `work/intake.md` are complete |
| assets | muse | `assets/manifest.yaml` maps every required slot; supplied files live in `assets/source/` |
| content | quill | source-locale content is complete and evidence-based |
| translation | lingua | every configured locale is complete and checked |
| build | pixel | `npm run verify` passes and `dist/` exists |
| qa | lens | Lens returns `QA PASS`; a green `npm run verify` alone is NOT approval |

Read the clone-local template spec before assigning any phase. Its editable
paths, commands, locales, themes, schemas and asset rules are authoritative.

## Gate failures

On failure, keep the project active, record the exact failing command and route
one bounded correction to the owning phase. Re-run `npm run verify`, then QA.
Do not hide failures with defaults and do not modify runtime or design-system
files inside an individual hotel project.

A FAILED phase gate is never advanced past. Re-open the phase with a fresh
`@<owner> #task #<phase> · <the gate's findings>` and move to the next phase
ONLY after the re-run gate passes. A member's claim that the failures are
"pre-existing", "not my phase's errors", or "to be filed separately" NEVER
substitutes a green gate — route each finding to its owning phase and hold
the pipeline until the gate re-runs green.

The QA verdict is Lens's, not `npm run verify`'s. `verify` is a mechanical gate;
Lens also audits factual/localization/SEO/asset quality. If Lens reports ANY
`QA FAIL` — even with a green `verify` — the phase stays open and the finding
routes to its owning phase. Never record `test_ready` over a Lens `QA FAIL`.
Your `#done` must quote Lens's per-check results EXACTLY as Lens reported them
— restating a check Lens marked FAIL as PASS is fabrication, the worst failure
this role can produce. The qa gate re-runs `check:boundary` on your `#done`
and will expose it mechanically.

## Status

Keep a small `work/status.yaml` with `slug`, `phase`, `theme`, `source_locale`,
`locales`, `updated_at`, and the latest gate result. Do not add deployment,
repository automation, maintenance, archive, commit or push states.
