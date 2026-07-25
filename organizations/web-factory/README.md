# Web Factory

Agent organization that turns a client hotel brief into a locally verified,
multi-locale hotel website. Each hotel is an independent git clone of the
[Astro hotel template](https://github.com/satoshi-ltd/alpi-mirai-web-factory);
the factory's output is a `dist/` ready for internal review — it does not
deploy.

Field history, proven principles and the operational playbook live in the repo
root's `../../workgroup-notes.md`. Daemon recovery findings live in
`../../workgroup-crash-recovery.md`.

## Launching a hotel

A launch carries **text only** — the client brief as markdown. Binary media
never travels at launch.

```bash
ALPI_PROFILE=mira alpi workgroup launch \
  --recipe organizations/web-factory/recipes/hotel.yaml \
  --param slug=<hotel-slug> \
  --input brief=./brief.md
```

The recipe clones the template into `projects/<slug>/`, seeds
`work/intake.md`, writes the brief to `brief.md`, creates the workgroup
(`site-<slug>`) and posts the kickoff task. From there the pipeline drives
itself: every phase closes through a mechanical gate the daemon runs on the
hub's `#done` — a false report cannot advance a phase.

## Pipeline

| Phase | Owner | Deliverable | Gate |
| --- | --- | --- | --- |
| setup | pixel | initialized clone, demo neutralized | `npm run check:setup` |
| intake | scout | `work/enrichment.md` (web research), `work/intake.md`, `src/config/site.json` | `npm run check:config` |
| assets | muse | `assets/manifest.yaml` slot decisions | `npm run assets:optimize` |
| content | quill | source-locale content in `src/content/**` | `npm run check:content` |
| translation | lingua | every declared locale at parity | `npm run check:content:all` |
| build | pixel | selected-tier production `dist/` | `npm run check:dist` |
| qa | lens | one PASS/FAIL audit verdict | `npm run check:boundary` |

Recipe tasks are thin triggers (≤120 characters, test-enforced): the *how*
lives in each agent's contract file (`agents/*/agent.md`), never in the task text. Workgroup posts are
English unless the hub opens in Spanish; the hotel's content keeps its own
locales.

## Driving a workgroup (after launch)

Everything is a post in the workgroup chat, always shaped
`@<owner> #task #<slug> · <text>`. The slug is CONSTANT per task type (ids
and details travel in the text, never as extra hashtags); a post without
`@owner` becomes a collective task and stalls waiting for every member.

| Post | What runs |
|---|---|
| `@mira #task #review` + the work order pasted below (or `· REV-X (see work/review/REV-X.md)`, or a one-line manual request) | The `review-orders` skill: materialize to `work/review/`, triage per owner, fix, rebuild, close note by note (`applied` / `rejected` / `template-gap`) |
| `@muse #task #media-update · new client media in assets/source/` | After photos/logos land in the project's `assets/source/` via git: muse re-inventories the manifest, pixel optimizes and rebuilds |
| `@scout #task #content-update · <reason>` | New verified facts (fresh enrichment, client mail): scout folds into `site.json` + `work/intake.md`, then quill → lingua → pixel → lens |
| `@<owner> #task #<phase>` | Re-opens a stalled phase (the standard recovery when a gate failed and the pipeline stopped) |
| `@<owner> #task #<anything>-fix · <what>` | Ad-hoc targeted fix for one phase owner |

Pause/resume and remove live in the workgroup detail view (or
`alpi -p mira workgroup pause|resume|remove`). Launching is the recipe form
(hub `mira`, param `slug`, the brief pasted as the text input).

## Authoring boundary

Agents may write only: `src/config/site.json`, `src/content/**` (except
`config.js`), `assets/manifest.yaml`, `assets/source/**` and `work/**`.
Everything else — components, styles, scripts, schemas, `src/i18n/*`
dictionaries — is runtime; touching it fails `check:boundary` mechanically.
A demo string baked into runtime is a template gap to report, never to patch.

## Content contract (short form)

The clone's `src/config/content-system.js` is authoritative. The layout adapts
to available content; content is never inflated to fill a layout. `summary` is
the floor of every rendered entry; `body` only where the brief has real
material; numbers live in structured `facts`. Word ranges select components —
they are never minimums. The brief (plus scout's corroborated enrichment) is
the only source of facts; testimonials are auto-selected verbatim quotes,
published without OTA attribution.

## Web research

Scout's `hotel-enrichment` skill is the ONLY place web access happens: closed
source allowlist, ≥2 independent hostnames per fact, never a price, amount or
volatile rating, contradictions go to "Needs human", and a mechanical
validator (`validate_enrichment.py`) must pass before handoff.

## Roster

Seven agents, one team: **mira** (hub) · **scout** · **muse** · **quill** ·
**lingua** · **pixel** · **lens**. Each agent directory carries a
human-facing `README.md` and the operative AI contract in its agent file.
