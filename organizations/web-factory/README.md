# Web Factory

Agent organization that turns a client hotel brief into a locally verified,
multi-locale hotel website. Each hotel is an independent git clone of the
[Astro hotel template](https://github.com/satoshi-ltd/alpi-mirai-web-factory);
the factory's output is a `dist/` ready for internal review — it does not
deploy.

Open factory work is tracked in [`../../web-factory-tasks.md`](../../web-factory-tasks.md);
core workgroup work lives in [`../../alpi-tasks.md`](../../alpi-tasks.md).

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
itself: every normal owner delivery closes through a mechanical gate, and the
daemon opens the declared successor only after a green result. An explicit
`#done skipped · <reason>` is the visible bypass for a deliberately skipped phase.

## Pipeline

| Phase | Owner | Deliverable | Gate |
| --- | --- | --- | --- |
| setup | pixel | initialized clone, demo neutralized | `npm run check:setup` |
| enrich | scout | `work/enrichment.md` (web research) | `npm run check:enrichment` |
| intake | scout | `work/intake.md`, `src/config/site.json` | `npm run check:intake` |
| assets | muse | `assets/manifest.yaml` slot decisions | `npm run check:assets` |
| content | quill | source-locale content in `src/content/**` | `npm run check:content` |
| translation | lingua | every declared locale at parity | `npm run check:locales` |
| build | pixel | selected-tier production `dist/` | `npm run check:build` |
| qa | lens | one PASS/FAIL audit verdict | verdict-owned · self-check `npm run check:audit` |

Recipe tasks are thin triggers (≤120 characters, test-enforced): the *how*
lives in each agent's contract file (`agents/*/agent.md`), never in the task text. Workgroup posts are
English unless the hub opens in Spanish; the hotel's content keeps its own
locales.

## The brief

`BRIEFING.md` (next to this file) is the client-facing checklist: what to ask
the hotel for, what merely helps, and what to avoid. Its core finding, measured
across eight runs: a 500-word commercial sheet carrying the operational data
(engine id, category, rates, corporate details) produces a BETTER site than a
4,600-word dump of the hotel's current website — input volume degrades data
fidelity, so the brief should be short and dense, never long and narrative.
Multi-property briefs are split into one project per property.

## Driving a workgroup (after launch)

Everything is a post in the workgroup chat, always shaped
`@<owner> #task #<slug> · <text>`. The slug is CONSTANT per task type (ids
and details travel in the text, never as extra hashtags); a post without
`@owner` becomes a collective task and stalls waiting for every member.

Every post-launch protocol is a **declared pipeline**, so it is started by key
rather than by remembering the right opener. The daemon publishes the recipe's
own owner and task, verbatim:

```bash
alpi -p mira workgroup trigger <wg_id> media-update
alpi -p mira workgroup trigger <wg_id> content-update
alpi -p mira workgroup trigger <wg_id> review
```

Desktop and mobile expose the same action in the workgroup **chat**, next to the
phase strip. The workgroup's settings only list the declared chains: pipelines
come from the recipe, so nothing edits them after launch — changing one means
editing `recipes/hotel.yaml` and launching again.

| Pipeline | Phases | Consumes |
|---|---|---|
| `media-update` | muse maps + optimizes → scout wires config → pixel rebuilds → lens audits | client media already staged in `assets/source/` |
| `content-update` | scout folds into `site.json` + `work/intake.md` → quill → lingua → pixel → lens | verified update material already staged in `work/` |
| `review` | mira materializes + triages → scout → quill → lingua → muse → pixel → lens → mira closes note by note | unclosed `work/review/REV-*.md` files |

The first phase's task is static and self-contained: stage the input in the
project first, then trigger. There is no free-text suffix on a trigger. An
inline review order (pasted rather than staged) still goes through the
lower-level `@mira #task #review · <document>` post.

Direct posts remain available for recovery:

| Post | What runs |
|---|---|
| `@<owner> #task #<phase>` | Re-opens a stalled phase (the standard recovery when a gate failed and the pipeline stopped) |
| `@<owner> #task #<phase>-fix` / `#<phase>-recheck` | Repair attempt inside the same phase — the only two suffixes that map back to it |

Pause/resume and remove live in the workgroup detail view (or
`alpi -p mira workgroup pause|resume|remove`). Launching is the recipe form
(hub `mira`, param `slug`, the brief pasted as the text input).

Open daemon investigations, including hub self-dispatch, are tracked in
[`../../alpi-tasks.md`](../../alpi-tasks.md); do not encode temporary recovery
procedures in this operating guide.

The brief can pin aesthetics for deterministic reruns: an explicit
`theme: <essential|signature|immersive>`, `makeup: <id>` or a brand colour in
the brief always wins over the AI's choice. Without a pin, two runs of the
same brief may legitimately pick different makeups.

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
volatile rating, contradictions go to "Needs human", and the mechanical
`npm run check:enrichment` gate polices the phase. Brand colour is the
single-source exception and carries an explicit machine-readable tag.

## Roster

Seven agents, one team: **mira** (hub) · **scout** · **muse** · **quill** ·
**lingua** · **pixel** · **lens**. Each agent directory carries a
human-facing `README.md` and the operative AI contract in its agent file.
