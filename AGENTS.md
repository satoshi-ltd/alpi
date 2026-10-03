# AGENTS.md

Rules for any AI agent (Claude Code, Cursor, Codex, Aider, …) working on
this repository. Hard constraints, not suggestions.

> Behavioural rules the maintainer applies to every project (commit
> hygiene, test discipline, comment style, no AI-attribution lines) live
> in his personal agent config. They apply here too. If your harness
> doesn't load that file, the short version is: **no commits / pushes /
> tags without explicit permission in the current turn; every functional
> change ships with a test; default to no comments — when needed, one-line
> and aimed at the next LLM, not at humans.**

## Project

- **Name:** Alpi. Package `alpi`, binary `alpi`, home directory `~/.alpi`.
  Open-source, solo-maintained.
- **Positioning:** "a lighter, better Hermes." Hermes
  (`~/git/hermes-agent` on the maintainer's machine) is the canonical
  reference codebase. Before designing a non-trivial feature, look there
  first — but evaluate critically: Hermes is feature-rich for a broad
  audience while Alpi is scoped tight. The bar is "the smallest design
  that captures the value", not "port verbatim".

## Documents

Each document answers one question. Put information in the one that owns it
and nowhere else, and update it in the same change as the code.

| File | Question | Never contains |
| --- | --- | --- |
| `README.md` | What is alpi, and how do I install and run it? (humans) | Status, history, tasks |
| `AGENTS.md` | Which rules apply when working here? | Status, tasks, contracts, history |
| `docs/ROADMAP.md` | What is left to do? The task pool; its header defines fields and lanes | Shipped work |
| `docs/ARCHITECTURE.md` | How does alpi work today? Layout, systems and the contracts clients and consumers rely on | Dates, statuses, test counts, investigation logs |
| `docs/*.md` (CONFIG, PROFILES, WORKGROUPS, …) | How does one area work, in depth? | Tasks, history |
| `CHANGELOG.md`, `desktop/CHANGELOG.md`, `mobile/CHANGELOG.md` | What did each version ship? | Implementation detail, test counts, review narrative, customers or infrastructure |

- Start from `README.md`, `docs/ROADMAP.md` and the `docs/ARCHITECTURE.md`
  section the task touches.
- `docs/ARCHITECTURE.md` is present tense and edited in place: when behaviour
  changes, rewrite the section that owns it. History lives in git and the
  changelogs.
- Changelog entries: `## vX.Y.Z — YYYY-MM-DD — short title`, at most five
  bullets of what changed for someone using or running the product, then why
  when it is not obvious. Client entries end with the minimum alpi version
  they need.
- `alpi/knowledge/references/` is what the alpi agent itself reads to know
  alpi: hand-tuned AI-facing documentation, not a copy of `docs/`. Any change
  to `docs/`, a contract or a user-visible behaviour updates the matching
  reference in the same change, written for an agent (`scripts/sync_knowledge.py`
  only validates the file set).
- `design/` is the design kit, not a document (rules below). `reports/` holds
  the creator's internal decision reports in Spanish; it is excluded from git,
  never committed and never a task list.

## Workflow

The creator runs the project as an autonomous loop with the user-level
`next-task` skill (usually `/loop /next-task`) and the `adversarial-reviewer`
agent in `~/.claude/`. Each iteration takes one approved task, implements and
tests it, bumps the version and changelog, has the reviewer try to break it,
applies the findings, validates, commits, pushes and watches CI.

Project wiring for those tools:

- **Task pool:** `docs/ROADMAP.md`. Only `owner: agent` tasks in Queue are
  worked on; only the creator approves a task into Queue.
- **Products:** a task names the products it releases (`alpi`, `desktop`,
  `mobile`; `common/` releases both clients, `design/` releases none). A task
  that releases several products ships one commit per product, daemon first,
  each with its own bump and changelog; `design/` and `common/` ride with the
  first client commit.
- **Version:** `python3 scripts/bump.py <alpi|desktop|mobile> [patch|minor|major]`
  (patch by default) updates every version location, including the lock files
  and the mobile build counters; then write the changelog entry. Every commit
  to `main` that changes a product bumps it; docs-only, design-only and
  build-tooling commits that leave the shipped artefact unchanged do not. `python3 scripts/check_release.py` proves manifests, locks and
  changelog headings agree.
- **Validation:** `python3 scripts/validate.py` runs the release check, then
  every suite the working tree touches against `HEAD` (`--base REF` for another
  base, `--all` for everything, `--dry-run` for the plan), stopping at the first
  failure. Report it separately from the GitHub pipeline results.
- **CI:** `gh run list --commit <sha>`: `publish` (alpi: PyPI, then
  `publish-docker` and `publish-site`), `clients` (both JS suites on every push
  that touches a client), `publish-desktop` (the desktop release). Mobile has
  no pipeline; EAS builds are the creator's. A red pipeline on `main` is the
  next task.

Rules of the loop:

- Invoking `/next-task` or `/loop /next-task` is the creator's explicit request
  to commit and push each finished task once review and validation pass.
  Outside the loop, commit only when asked in the current turn. When the
  creator says not to commit, prepare and validate, leave the change staged
  and report.
- Adversarial review before every commit; a second pass on the deltas when the
  fixes were substantive.
- Interruptions: triage before continuing and say where each item went. A bug
  the creator reports goes to the top of Queue; a requested feature goes to
  Queue; ideas, including your own, go to Proposed; questions get answered.
- Anything needing an EAS build, a physical device, the fleet, credentials or
  a product choice becomes a `Needs creator` task. When a feature needs device
  evidence, split it: the implementation is an agent task, the device check a
  creator `verify` task that depends on it.
- Stop and report when Queue is empty or everything is blocked on the creator.

### Review checklist

On top of the reviewer's generic checklist, and against every rule in the
"Contracts clients and consumers rely on" section of `docs/ARCHITECTURE.md`
(clients talk to the daemon over `host.*` only, never `~/.alpi` from Rust or a
spawned `alpi`; `notify` for the owner vs `send_message` for third parties;
clients surface every `agent.message`; `schedule.*` fields instead of parsing
`message`; `host.network.*`, `host.activity.list` and session ownership):

- **Ownership:** every `host.*` verb that lists, reads or acts on sessions,
  prompts, runs or schedules filters by connection, device (`session_scope`)
  and profile scope, and the local socket's owner semantics hold. Members
  never see another connection's data.
- **Console parity:** a new host verb with app UI ships its CLI or TUI
  equivalent.
- **Older daemons:** clients hide a feature when a verb answers
  `-32601 method-not-found` (or `forbidden` for a scoped device) and ignore
  unknown frame kinds; a new stream field is optional on the client.
- **Event consumers:** anything that builds a reply from `AgentEvent`s filters
  on `final=True`; a new event kind is ignored by the scheduler, gateways, ALP
  and `--once` unless they need it.
- **Redaction and caps:** anything persisted (sessions, run journals, replay
  sidecars, outputs) is redacted and capped; no secret reaches a log.
- **Desktop:** Tauri commands that touch the daemon run off the main thread
  (`off_main()` / `spawn_blocking`); the Rust bridge forwards new fields.
- **Mobile:** nothing needs a device to prove it; native config (app.json,
  config plugins) survives `expo prebuild`; touch targets, reduce motion and
  large text sizes hold.
- **Design:** every board the change affects is regenerated and matches what
  ships, in light and dark.
- **Knowledge:** every `docs/` or behaviour change has its matching
  `alpi/knowledge/references/` update, so the agent does not answer from stale
  knowledge.

## Code style

- **All source text in English.** No Spanish anywhere in `alpi/` — code,
  docstrings, prompts, tool descriptions, CLI help, error messages,
  commit messages. Only runtime user-facing output (which follows the
  user's language) is exempt. Examples in tool descriptions bias the
  LLM's reply language; English keeps it neutral.
- **Plain JavaScript only — no TypeScript.** Frontend is always `.js` /
  `.jsx`. Do not propose adding TS "later" or scaffold projects with TS
  templates.
- **Minimize dependencies.** Every runtime or build dep needs explicit
  justification. Defaults: CSS Modules over Tailwind, hand-rolled over UI
  kits, vanilla over opinionated state libraries. Solo-maintained — every
  dep is maintenance tax forever.
- **No AI-maker attribution in the repo.** No "powered by Claude",
  "Co-Authored-By: Claude", or analogous Anthropic / OpenAI / Google /
  Mistral credits in commit messages, PR descriptions, code comments,
  marketing copy, README, or user-visible UI. Functional API identifiers
  (model strings like `anthropic/claude-sonnet-5`, env var names like
  `ANTHROPIC_API_KEY` / `OPENAI_API_KEY` / `GEMINI_API_KEY`, provider
  class names, LiteLLM routing prefixes) are exempt — they're protocol
  contracts, not branding. The line: if removing the mention would break
  auth, routing, or interop, it stays; if it's brag/credit/decorative,
  it goes.

- **`design/` is the visual reference, generated.** `python3 design/build.py`
  rewrites `design/*.html` and the canvas artboards under `design/canvas/` from
  the repo's tokens, components and screens; never edit the HTML by hand. **Any
  change to what desktop or mobile shows or how it behaves regenerates `design/`
  in the same change**: a UI change is not done while `design/` still shows the old
  look. `tests/test_design_kit.py` and `design/drift.py` fail until you do. The
  design-kit contract, board format and lifecycle live in `design/AGENTS.md`.
  - **Views in sync.** The views (System and every interface tab) show what ships; Proposals shows what is proposed.
    Shipping a proposal is one change: the code, the views regenerated so they show the new design, the board deleted,
    its `ui` line deleted, and the changelog and the spec updated. A board left standing after its change shipped, or
    a view that still draws the old look, fails the adversarial review before the commit.

- **App icons are generated.** `python3 scripts/gen_icons.py` rewrites every icon under `desktop/src-tauri/icons/` and
  `mobile/assets/` from `common/folds.mjs` (the alpaca in one flat ink); never edit those PNGs, ICNS or ICO by hand, and
  `tests/test_icons.py` fails when they drift. The iOS tinted icon and the tray templates stay single-ink.
- **Console parity is mandatory.** The console (`alpi setup`, the TUI,
  the CLI) is the core product; desktop/mobile are siblings, not the
  primary surface. Any new host verb that gets UI in the apps ships its
  console equivalent (slash command, CLI command, or setup section) in
  the same change — features must never be reachable only through the
  apps.

## Releases & versioning

Three products ship from this repo, on independent cadences with
independent version schemes. Don't conflate them. `scripts/bump.py` owns
every version location listed below; never edit them by hand.

- **alpi (CLI / Python package).** Tags ``vX.Y.Z`` (no prefix).
  Versioned in ``pyproject.toml`` + ``alpi/__init__.py``.
  Changelog: [CHANGELOG.md](CHANGELOG.md). Pipeline:
  [.github/workflows/publish.yml](.github/workflows/publish.yml)
  (PyPI + GitHub release).
- **Desktop app (Tauri).** Tags ``desktop-vX.Y.Z``. Versioned in
  ``desktop/package.json`` + ``desktop/src-tauri/tauri.conf.json`` +
  ``desktop/src-tauri/Cargo.toml`` + its ``Cargo.lock`` entry (all must agree,
  or the release workflow aborts). Changelog:
  [desktop/CHANGELOG.md](desktop/CHANGELOG.md). Pipeline:
  [.github/workflows/publish-desktop.yml](.github/workflows/publish-desktop.yml)
  (GitHub release only — no PyPI). The Tauri updater reads
  ``releases/download/desktop-latest/latest.json``; the workflow
  re-points the rolling ``desktop-latest`` tag on every release
  so that URL stays stable.

- **Mobile app (Expo).** Tags ``mobile-vX.Y.Z``. Versioned in
  ``mobile/package.json`` + ``mobile/app.json`` (``expo.version``), and both
  build counters must advance: ``ios.buildNumber`` and ``android.versionCode``,
  or the store upload is rejected. ``mobile/package-lock.json`` carries the
  version twice; a dependency change regenerates the lock with ``npm install``
  and ``npm ci --dry-run`` must pass. Changelog:
  [mobile/CHANGELOG.md](mobile/CHANGELOG.md). Built by EAS; no GitHub workflow.

- **Shared client source.** ``common/`` is a third source directory, not a
  package: no ``package.json``, consumed by relative import from both trees.
  Nothing above it declares a module type, so **logic is ``.mjs``** (bare Node
  reparses ``.js`` there only by accident) and **shared components are
  ``.jsx``** (JSX cannot live in ``.mjs``). Metro reaches it through
  ``mobile/metro.config.js``'s explicit ``watchFolders``; Vite needs nothing.
  ``common/`` carries no version — a change there releases both clients.

A change to ``common/``, ``desktop/`` or ``mobile/`` runs both JS suites, locally
via the hook and in ``clients.yml`` — which owns client testing on every PR *and*
on pushes to main, because ``publish.yml`` path-filters on ``alpi/**`` and
``publish-desktop.yml`` goes straight to build with no test gate.

Neither client reads the other's source. ``desktop/src/styles/tokens.css`` stays
a separate file — CSS custom properties cannot be imported by React Native — so
each side carries a parity test against ``common/tokens.mjs`` instead
(``desktop/src/styles/tokenParity.test.js`` reads the CSS beside it). The four
palette values that deliberately differ are declared in the mobile test
independently of the override table that implements them, so the table cannot
vouch for itself.

A desktop release pins a minimum compatible alpi version in its
changelog entry — clients require a daemon recent enough to serve
every ``host.*`` verb the UI calls.

## Testing

`python3 scripts/validate.py` is the one command before claiming done. The
suites it composes:

```bash
pytest -q                # fast suite (unit + filesystem)
pytest --integration -q  # adds tests that open sockets / use sandbox-exec
pytest --llm             # adds tests that make real LLM calls
```

CI (`.github/workflows/pull-request.yml`) runs `unit` and `integration` jobs
on every PR and on manual dispatch — not on push. The push-to-main gate is
`publish.yml`, and it only fires for `alpi/**`, `tests/**`, `pyproject.toml`,
`uv.lock` and `CHANGELOG.md`. Backstop only, not a substitute for running the
suite locally before declaring done.

`prune-actions.yml` runs weekly and on manual dispatch (`dry_run` only lists):
`scripts/prune_actions.py --apply` deletes the runs beyond the newest 10 per
workflow that are also older than 7 days, and the artifacts older than 7 days.
Without `--apply` the script only lists. CI caches are left to GitHub's eviction.

A repo-versioned `pre-commit` hook (`.githooks/pre-commit`) runs only
the suites touched by the staged diff — alpi (pytest), desktop
(`pnpm test` + `cargo test`), mobile (`npm test`). Enable once per
clone:

```bash
git config core.hooksPath .githooks
```

Override with `git commit --no-verify` only when you know what you're
doing (half-merge in progress, etc.).

## Live environment boundaries

- The creator's deployed daemons are theirs: never deploy, update, restart or
  edit their state unless asked in the turn; read-only RPCs are fine. Their
  config repositories take manual commits only, and a mounted copy of a remote
  daemon's data is stale and read-only, never evidence of live state.
- `~/.alpi` on this machine is the creator's live daemon. Tests use isolated
  temporary homes and never point at a real daemon.
- EAS builds, installs and device checks are the creator's. A running
  `pnpm tauri dev` is the creator's too; never restart it.
- Keep implemented, released and verified apart in reports: a green suite is
  not a device check and a pushed commit is not a deployed daemon.
