# Web Factory

An org that ships ~120 hotel websites a year off **one** master template.
Eleven agents, three standing workgroups for meta-work, and one `proj-<slug>`
workgroup per hotel — each driven by an ordered pipeline the hub runs to the
launch gate.

The thesis: a hotel site is **~80% configuration, ~20% bespoke**. The product
is the template (the `alpi-mirai-web-factory` git base repo, a 4-theme Astro
kit cloned per project) plus the machine-readable contract (`factory/template-spec.json`). Agents produce
**data only** — a site config + typed content — validated at build by Zod.
Invalid data fails the build with a clear error; it never breaks the design.

## Roster

Every profile runs the org's model palette (`org.yaml models:`): main
`deepseek-v4-flash`/medium, routing tiers `fast` (flash/low —
delegate/research fast paths, engine plumbing) and `deep`
(`deepseek-v4-pro`/medium — the engine's automatic escalation target).
Agents inherit the org's medium effort; only deviations declare
`reasoning_effort`: mira runs `high` (flash/medium flipped the
assets-gate twice; flash/high is the calibrated hub — a pro/high trial
on 2026-07-16 overrode a correct `not_required` signal, so raw model
power is NOT the hub lever) and pixel runs `low`.

| Agent | Reasoning | Role |
|---|---|---|
| **vera** | medium | Strategic lead — owns the *system* that runs projects, not the projects |
| **mira** | high (pro) | Project manager — hub of every `proj-<slug>`, intake → launch |
| **forge** | medium | Tech lead — ships the template that ships the sites |
| **canvas** | medium | Brand steward — owns the 4 themes; no per-project CSS |
| **scout** | medium | Intake — turns a hotel into a site config + prose intake |
| **quill** | medium | Copywriter — words as data the components render |
| **lingua** | medium | Localization — translates *and* adapts per locale |
| **muse** | medium | Visual producer — logo (SVG) + generated/restored imagery; owns the `assets` phase (closed trivially when intake signals `not_required`) |
| **pixel** | low | Implementation — data → green build with real assets (deterministic gates) |
| **atlas** | medium | SEO + performance — baked into the template, not artisanal |
| **lens** | medium | QA + launch gate — nothing ships until green |

Souls carry identity + craft only. The workgroup protocol (markers, rounds,
closure) is runtime knowledge from [`docs/ALP.md`](../../docs/ALP.md), never
re-explained in a soul. Each agent's briefing — not its soul — tells it the
mission, the pipeline, and the handoff expected.

Profiles also work as independent chat agents. A direct chat with `@quill`,
`@muse`, `@pixel`, `@lens`, etc. is not a simulated workgroup turn: the profile
answers, advises, or produces explicit requested artifacts through normal tools,
without `#task`/`#done`/`#working` markers or `workgroup_post`. Workgroups add
shared context, ownership, and sequencing for a specific project; they are not
the only way a profile can be useful.

## The producer contract

Every agent, every project, obeys the same boundary:

- Produce **data**: `src/config/site.json` (theme + brand tokens + contact +
  booking + nav + pages) and `src/content/**` (rooms, amenities, dining,
  offers, testimonials, experiences, page copy).
- **Never** edit components, `styles/themes`, or any `*.ts` — that is the
  fixed design layer. The 4 themes ARE the design.
- The contract — theme rubric, token defaults, binding catalogue, guardrails
  — is `factory/template-spec.json`. Read it; don't reinvent it.

> **TypeScript exception (scoped, conscious).** The repo rule is JS-only for
> alpi's own surfaces (`alpi/`, `desktop/`, `mobile/`). The base-repo kit
> (`alpi-mirai-web-factory`) is the factory's PRODUCT, an idiomatic Astro app where `.ts` is
> load-bearing: the Zod schemas in `src/config/site-schema.ts` +
> `src/content/config.ts` ARE the build-time validation gate (the safety model),
> `env.d.ts` is Astro-generated, and the `.ts` route endpoints (sitemap/robots)
> are Astro convention. Converting to `.js` would drop the typed Zod gate and
> fight the framework. TS lives ONLY here, in the shipped template; never in
> alpi code.
- The raw client brief (`projects/<slug>/brief.md`) is **immutable**: agents
  read it, never edit it.
- Assets are **local-first** (`projects/<slug>/assets/`). Missing → template
  tonal fallbacks. When the hotel sent bad/no photos or no logo, the hub may
  task **muse** (on-demand) to supply a logo (SVG), brand/ambience imagery, or
  restored photos into `assets/` — never fabricated real rooms or stock imagery.

## The per-project pipeline

`alpi -p mira workgroup launch --recipe organizations/web-factory/recipes/hotel.yaml --param slug=<slug> --input brief=<file>`
clones the base repo (`satoshi-ltd/alpi-mirai-web-factory`) into
`projects/<slug>`, seeds the brief and a neutral `site.json` skeleton, creates
the `proj-<slug>` workgroup (hub **mira**, members scout/quill/lingua/muse/
pixel/lens — one per phase; budget from `org.yaml`
`budgets.project_workgroup`) and posts the kickoff, with the pipeline:

```
intake → assets → content → translation → build → qa
```

| Phase | Owner | Deliverable |
|---|---|---|
| **intake** | scout | theme pick (rubric) + `site.json` + prose `intake.md` + the `visual_assets:` signal |
| **assets** | muse | logo + hero + `assets.yaml` when the signal requires it; mira closes it trivially on `not_required` |
| **content** | quill | source-locale copy as typed content |
| **translation** | lingua | every required locale, adapted not swapped |
| **build** | pixel | real assets wired, green Zod build |
| **qa** | lens | the pre-launch checklist; a single fail blocks `#done` |

The per-project briefing carries **project facts + the pipeline map only** —
how each agent operates lives in its soul/skills, and the hub's phase
procedure lives in mira's `project-lifecycle` skill. Operating prose in the
briefing proved noisy for members and unenforceable for the hub; structure
(a real phase) replaced it.

The hub opens one phase at a time; when a phase closes with `#done`, core
opens the next automatically. A phase that closes `#done BLOCKED` halts the
pipeline cleanly (mira re-scopes rather than the watchdog churning). The
workgroup is **persistent** — it stays open through launch and into
maintenance iterations.

## Parallel project runs

Web Factory can run multiple `proj-<slug>` workgroups at once, but a single
roster is shared capacity, not a stateless worker pool. The daemon may dispatch
different workgroups concurrently, yet `mira`, `quill`, `muse`, `pixel`, and
the rest still share their profile home, tools, logs, budgets, model limits,
and provider rate limits. With one roster, 1–2 active hotel projects is the
normal operating shape; 3–4 is a stress test and will often bunch up around the
same producer phases. For real throughput, add more producer profiles or run
separate rosters per batch. Do not model throughput as another pipeline phase.

## Standing workgroups (meta-work)

- **brand-library** (hub canvas) — curates the 4 starters (boutique, budget,
  business, resort). Keep each strong enough that a hotel customises 4–6
  tokens, not 40. Luxury intentionally stays out.
- **template** (hub forge) — evolves the `alpi-mirai-web-factory` base repo.
  Lessons from ≥3 live projects land in the base repo; each significant change
  ships an ADR under its `decisions/`.
- **quality** (hub vera) — owns the single pre-launch checklist (WCAG AA,
  Core Web Vitals, responsive breakpoints, SEO minimums, content
  completeness). Lens enforces; the checklist lives at
  `projects/<slug>/quality/checklist.md`.

## Growing the library — more variety without more templates

The pressure for "more designs" is real at 120 sites/year, but a fifth
starter or free-form agent styling is the wrong lever. Variety grows on
two sanctioned axes, both of which stay inside the data-only contract:

- **Tokens + copy + photography** are already per-hotel — most perceived
  sameness is actually default tokens plus thin briefs, not template
  limits.
- **Schema variants**: when a structural wish repeats (hero layouts,
  section order, an alternate rooms presentation), it lands as a new
  *validated field* in `site.json` — designed in `brand-library`,
  ADR'd and built by `template`, then available to every project as
  data. Never per-project CSS, never an agent "deciding the style".

A **new starter** needs what `brand-library`'s charter demands: intake
data showing a recurring segment the four don't serve. Luxury stays out.

## Changing the org (souls, skills, models, workgroup charters)

The source of truth is this folder in the repo — **never** the live
profiles and never a workgroup `#task`. A `#task` edits a project;
bootstrap builds the org. Live-editing `~/.alpi/profiles/<name>/` is
overwritten by the next bootstrap, and workgroup members can't rewrite
their own souls. The loop is: edit here → `setup.py web-factory --check`
→ re-bootstrap → the acceptance fixtures below must pass before the
change is considered landed. Post-launch *project* changes are the
opposite: they always flow through mira's `maintenance-intake` as a
`#task` in the project's workgroup.

Deploys and per-project git history are designed (not yet wired) in
[`deployment.md`](deployment.md).

## Bootstrap

```bash
uv run python organizations/setup.py web-factory          # nuke + rebuild
uv run python organizations/setup.py web-factory --check  # validate only
```

Builds the 11 profiles, the 3 standing workgroups, syncs the `factory/`
contract + `library/` into the workspace (`~/git/web-factory`), and scaffolds
`projects/`, `archive/`.

## Spinning up a hotel

Every hotel is one launch of the **`recipes/hotel.yaml`** recipe. The recipe is
the constant shape of a `proj-<slug>` workgroup (hub mira, the six phase owners,
the gated pipeline, the base-repo clone); a launch only supplies what changes
per hotel:

- **`slug`** (param) — the project id, `^[a-z0-9][a-z0-9-]{0,63}$`. Becomes the
  workgroup name `proj-<slug>` and the clone `projects/<slug>`.
- **`brief`** (input) — the raw client brief, seeded verbatim to
  `projects/<slug>/brief.md`. Immutable source of truth for the whole build.
- **`--assets <dir>`** (optional) — hotel-supplied photos copied into the
  project's `assets/` before kickoff; muse restores them into inventory slots.

### From the desktop

New workgroup → **Import recipe…** → pick
`organizations/web-factory/recipes/hotel.yaml`. The form fixes the hub (mira)
from the recipe and shows a **RECIPE INPUTS** section: a `SLUG` field and a
`HOTEL BRIEF` textarea. Fill both, optionally edit the workgroup briefing, and
hit **Launch**.

### From the CLI

```bash
alpi -p mira workgroup launch \
  --recipe organizations/web-factory/recipes/hotel.yaml \
  --param slug=villa-marisol \
  --input brief=organizations/web-factory/briefings/boutique/brief.md
```

Either path clones the base repo into `projects/villa-marisol`, seeds `brief.md`
+ a neutral `site.json` skeleton, creates the workgroup, and posts the kickoff.
mira then drives the pipeline to the launch gate — a clean run reaches QA PASS
with `dist/` on disk (HTML per locale + sitemap + robots), no human in the loop.

A brief is free-form prose — give scout the facts a site needs (name, location,
category, rooms, amenities, tone, audience, languages, domain, contact):

```
Villa Marisol — boutique adults-only beachfront hotel in Jávea, Alicante, Spain.
14 rooms + 2 suites, sea-view terraces. Rooftop infinity pool, farm-to-table
restaurant, small spa, 200 m from Playa del Arenal. Understated, calm luxury;
couples 35–55. Languages: Spanish (default), English, German.
Domain: https://villamarisol.es · hola@villamarisol.es · +34 966 123 456.
Rooms: Doble Estándar (garden), Deluxe Vista Mar (sea view),
Suite Marisol (terrace + hydromassage).
```

### Fixtures

Every fixture brief lives in `briefings/<name>/brief.md`, with any
hotel-supplied photos beside it in `briefings/<name>/assets/` (real-client
photos are gitignored via a local `.gitignore`; tiny fixtures are tracked).

- `briefings/golden/` — happy-path acceptance: reaches `launched` without fix
  loops or `#done BLOCKED`.
- `briefings/visual/` — assets-path acceptance: muse produces logo + hero
  BEFORE content; the built home ships the generated hero.
- `briefings/restore/` — restore-path acceptance: muse restores the supplied
  photos into their inventory slots (`kind: restored`).
- `briefings/{boutique,budget,business,resort}/` — one rough sales-note brief
  per theme, for manual theme testing.
- `briefings/jaime-primero/` — a real hotel (Hotel Jaime I, Salou).

## Acceptance — "perfect" as a command

```bash
uv run python organizations/web-factory/tools/acceptance.py golden   # trivial-close path (no muse)
uv run python organizations/web-factory/tools/acceptance.py visual   # assets path (muse before content)
uv run python organizations/web-factory/tools/acceptance.py restore  # hotel-supplied photos restored into inventory slots
```

Each run recreates the fixture project, lets the org build it unattended, and
asserts the criteria mechanically: `launched` with `iterations: 0`, no
`BLOCKED`, the brief's domain in `site.json` AND the built canonical, muse
involvement matching scout's signal (including `#assets` opening before
`#content` and the generated hero shipping), a complete `dist/`, cost under
budget. Any change to souls, skills, briefing, or pipeline lands only if both
fixtures pass. `--no-recreate` asserts against an existing run.

Happy-path smoke:

```bash
alpi -p mira workgroup launch \
  --recipe organizations/web-factory/recipes/hotel.yaml \
  --param slug=casa-bahia-golden \
  --input brief=organizations/web-factory/briefings/golden/brief.md
```

To tear a project down, remove its clone under `projects/`:

```bash
rm -rf projects/casa-bahia
```
