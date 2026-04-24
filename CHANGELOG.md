# Changelog

## v0.2.75 — 2026-04-24

### wizard / cli — profile lifecycle + polish

- New setup entry `alpi -p <name> setup → Delete profile` (non-default
  profiles only). One-shot teardown: summary → warn about installed
  services → typed-name confirmation → uninstall gateway / schedule /
  alp services → `rmtree` the profile home → exit. Collapses what
  used to be "uninstall each service manually, then run `alpi profile
  remove X`" into a single guided action.
- `alpi profile remove <name>` CLI now redirects to the wizard when
  services are installed, instead of listing per-service uninstall
  hints. CLI remains for the happy path (empty profiles, scripting).
- "Did you mean…?" suggestions in CLI when the target id doesn't
  exist: `alpi profile remove` (closest profile name), `alpi peers
  remove` / `alpi peers ping` (closest peer id), `alpi schedule fire`
  (closest job id). Shared `_suggest()` helper using `difflib`.
- Fixed the misleading "→ Gateway service" hint in `profile remove`
  error — it now names the actually-installed service(s) and points
  at the wizard.
- Dropped `.githooks/` (pre-push CHANGELOG regen). We've been
  running `alpi release notes` manually at release time; the hook
  was opt-in and unused.

### docs
- `docs/PROFILES.md` — documents the wizard-redirect flow.
- `docs/ARCHITECTURE.md` — setup menu outline lists "delete profile".

## v0.2.74 — 2026-04-24

### schedule — ad-hoc job fire (BA closed)

Closes the tightest feedback loop in the schedule lifecycle: add a
cron, verify it works, without waiting for the cron window.

- `alpi/scheduler/run.py::fire_by_id(home, job_id)` — loads
  `jobs.json`, looks up the id, runs the job through the same path
  the daemon tick uses (`run_job` — threat scan + `alpi chat --once`
  subprocess + delivery). Updates `last_run_at`; does **not**
  consume `once` jobs (ad-hoc fire is deliberate testing, not the
  natural trigger).
- CLI: `alpi schedule fire <job_id>`. Exit code 1 on failure.
- Tool: `schedule(action="fire", id=...)` so the LLM can self-test
  a job right after adding it.
- Description updated to list the new action + caveat about
  once-jobs not being consumed.

5 new regression tests in `tests/test_schedule.py`; 675 green.

## v0.2.73 — 2026-04-24

### skills / memory / docs — stop shipping what we don't use

- Deleted the `alpi/skills/` package directory. The only blueprint
  there (`meta/consolidate-memory/SKILL.md`) never reached profiles
  — the `skill` tool only searches `{home}/skills/` and nothing
  seeds the bundle. Keeping dead literature shipped with the binary
  violated the "ship what you use" posture. Runtime skills system
  is untouched — `~/.alpi/skills/<category>/<name>/` still works,
  the `skill` tool still creates / edits / runs user skills, and
  the `/skills` TUI panel still lists them.
- `pyproject.toml` package-data no longer includes `skills/**/*.md`.
- `alpi/tools/memory.py` — the ≥80% hint now says *"consider
  consolidating old entries before adding more"* (generic,
  actionable) instead of pointing at a skill that doesn't exist.
- `alpi/prompts/system_prompt.md` — same substitution: at ≥80%,
  prefer `replace` / `remove` over `add`.
- `alpi/prompts/create_skill_guide.md` — drops the "search the
  bundled `alpi/skills/`" step, since there's nothing to search.
- `docs/ARCHITECTURE.md` — package tree no longer lists `skills/`
  under `alpi/`. Added a bridge paragraph pointing at the Profile
  home layout where runtime skills / sessions / memories / logs /
  ALP state actually live. Skills core-systems section unchanged.
- `docs/ROADMAP.md` — **BE** reframed as "bundled skills
  infrastructure (loader; no content yet)" rather than a loader
  pinned to a specific blueprint. **AO** no longer claims
  consolidate-memory is bundled.
- Two regression tests in `tests/test_memory_tool_v2.py` now
  assert the new generic "consolidating" wording.

## v0.2.72 — 2026-04-24

### memory — v2 rules (AI partial)

Renames PERSONALITY.md → **AGENT.md** across the codebase, prompts,
tests, and docs. The user/agent pair (`USER.md` vs `AGENT.md`) is now
symmetric and readable. The `memory` tool enum, template file
(`alpi/prompts/default_agent.md`), home helper, and tool descriptions
that list memory files are all updated. File migration on existing
profiles is manual — no auto-migration per project policy.

- **A** — AGENT.md now uses paragraph-level fold + Jaccard dedup
  (`is_duplicate_stanza` in `alpi/memory.py`) instead of raw substring
  match. Paraphrased voice blocks no longer accumulate. Error text
  nudges toward `replace` when the user is refining an existing rule.
- **B** — `alpi/prompts/default_agent.md` "Edit me" footer rewritten
  to teach the correct `replace` vs `add` pattern (append new
  sections; replace existing lines; never replace unrelated rules
  to "make room").
- **C** — cross-file duplicate check: `add` to USER.md (or MEMORY.md)
  rejects when the content is already in the other file, pointing
  the caller at the correct target. Prevents the common failure
  where a fact (e.g. vehicle list) lands in both files.
- **E** — operational-state warning: `add` returns a ⚠ line in the
  tool output when the entry matches a session/chat/interaction log
  pattern (`chat_id`, `session_id`, `first interaction`, 5+-digit id
  combined with a date). Non-blocking — the LLM sees the hint; it
  decides whether to honour the user's explicit target.
- **F** — memory char limits bumped: `USER.md` 1375 → **3000**,
  `MEMORY.md` 2200 → **5000**. When either target reaches ≥ 80%
  usage, the tool response carries a `— run the consolidate-memory
  skill` hint so the model can escalate to consolidation before
  adding more.

**D deferred** — the "≤1-token entry dedup" idea (lower Jaccard
guard from 2 → 1) produced false positives on entries that shared
one generic content token (`Dato A` vs `Dato B` both reduced to
`{dato}`). Kept the guard at 2.

**G deferred** — periodic self-consolidation trigger stays out:
explicit over-engineering per the "no fails, no over-engineering"
directive. The user or the model can run the `consolidate-memory`
skill on demand.

11 new regression tests in `tests/test_memory_tool_v2.py`.

## v0.2.71 — 2026-04-24

### engine / prompts (AT partial — 4 of 5 candidate edits applied)
- new per-surface platform hint in the system prompt: `_platform_hint()` in `alpi/engine.py` reads `ALPI_PLATFORM` env and injects a matching block (`cron`, `telegram`, `email`, `gmail`). Gateway (`alpi/gateway/run.py`) sets it to `msg.platform` on every spawn; scheduler (`alpi/scheduler/run.py`) sets it to `cron`. TUI gets no hint (baseline). Concrete wins: cron jobs stop asking phantom users for clarification; Telegram replies arrive Markdown-aware; email replies arrive plain-text-only. 6 regression tests.
- `memory` tool description now enforces declarative phrasing with ✓/✗ examples ("User prefers concise replies" ✓ — "Always reply concisely" ✗). Imperative memory entries were being re-read as directives across sessions.
- `skill` tool description leads with "use when" purpose instead of directory layout.
- `email` tool description leads with "Read, search, send, or move email. Use when…" instead of "Manage the mailbox".
- `alpi/prompts/system_prompt.md` — dropped the "Past conversations" section; `session_search` tool description already carries the same rule. Net: ~10 fewer tokens injected on every turn.

### roadmap
- new **BD** item added for v0.3: model-aware tool-use-enforcement guidance (Claude/MiMo brevity, GPT/Codex/Gemini full block) — requires an A/B measurement on `agent.log` before applying.

### docs
- `docs/ARCHITECTURE.md` — system-prompt assembly section now documents the `ALPI_PLATFORM` contract between callers (gateway, scheduler) and the engine.

## v0.2.70 — 2026-04-23

### license
- repo re-licensed under **Business Source Licence 1.1** (`LICENSE`). Licensor: Satoshi Ltd. Change Date 2030-04-23 → Apache 2.0. Additional Use Grant lets individuals run alpi freely on machines they control for personal / research / non-commercial purposes; commercial production deployment by a legal entity requires a licence from `info@satoshi-ltd.com`. `pyproject.toml` license field updated to `BUSL-1.1`; README License section rewritten to explain the split.

### docs
- repo rooted in Satoshi Ltd.'s six operating principles (Privacy by Design, User Sovereignty, Security First, Open Source, Zero Knowledge, Digital Sovereignty) across `README.md`, `docs/ARCHITECTURE.md`, `docs/SECURITY.md`, `docs/ALP.md`. Each doc now explicitly maps its content to the principle it expresses.
- new [`QUICKSTART.md`](QUICKSTART.md) at repo root — first-day walkthrough: install → model → workspace → first chat → resume → gateway → second profile → ALP → doctor.
- new [`docs/PROFILES.md`](docs/PROFILES.md) — canonical reference for alpi's core isolation primitive (home resolution, what's isolated per profile, identity in ALP, creation patterns, cost).
- new [`docs/DEPLOYMENTS.md`](docs/DEPLOYMENTS.md) — six topologies from laptop-only to enterprise "army of alpis", each with ASCII diagram, trade-offs, and BSL licence boundary.
- new [`docs/OPERATIONS.md`](docs/OPERATIONS.md) — runbook: the five logs, service lifecycle, upgrades, backup + restore, ALP identity rotation, monitoring, disaster recovery, common failure modes.
- `docs/ROADMAP.md` sanitised — 64 shipped-item rows + the "Done — v0.1 + shipped v0.2 items" commit table dropped (they duplicated CHANGELOG which already reconstructs them from `git log`). New top table lists only open items with target version + status.

## v0.2.69 — 2026-04-23

### models
- `docs/MODELS.md` rebuilt around a neutral 3-tier recommendation sourced from a standalone deep-research pass (Tier 1 quality, Tier 2 cost/service, Tier 3 Ollama) with production-setup suggestions. Personal-usage section and deliberately-left-out list dropped to keep the doc unbiased.
- fresh profile scaffold (`config.seed_defaults`) no longer pins a default model — `config.yaml` ships with `model: ""` so the setup wizard is the canonical picker.
- `docs/CONFIG.md` updated to reflect the empty default.

## v0.2.68 — 2026-04-23

### alp (Alpi Link Protocol — ALP.1 closed)
- new `alpi/alp/` package: Ed25519 identity, signed JSON-RPC envelope with replay cache, fail-closed peer list, Unix-socket server + client. `link.ping`, `link.ask` (reject-fast reentrancy), `link.cancel` (idempotent interrupt).
- `peer` tool for LLM-driven cross-profile calls. TUI `@peer rest…` gesture with strict leading-`@` rule and `/peers` panel. Telegram / email / webhook gateway inbound interception hits the same code path without firing the local LLM.
- `alpi alp start|stop|restart` + service install via `alpi setup → ALP service` (launchd / systemd). Doctor granular sub-checks: Identity (key loadable), Socket (listening), Peers (reachable).
- `alpi setup → Peers` wizard: identity page with clipboard copy, probe-based ●/○/? status list, add/remove/inspect flows.
- `alpi peers key|list|add|remove|ping` CLI group for scripting.
- docs: `docs/ALP.md` spec v1 (envelope, verbs, errors, security), `docs/ROADMAP.md` ALP.1 shipped / ALP.2 + ALP.3 both v0.4, `docs/ARCHITECTURE.md` layout + commands.

### setup
- health-check row no longer blocks menu render on 5–10s of live network probes — status reads "open to run checks", actual checks run on-demand when the user opens the page.

## v0.2.54 — 2026-04-23

### gateway
- per-chat session threading (AN closed) + AU backlog entry (`e0f093d`)

## v0.2.53 — 2026-04-23

### config
- drop .env.example scaffold (AP closed) (`e707983`)

## v0.2.52 — 2026-04-23

### skill
- tighten `tools:` field description + document scheduler TZ (`27765b0`)

## v0.2.51 — 2026-04-23

### tui
- unified list row shape for selectable panels + /help palette (AH closed) (`f0f9052`)

## v0.2.50 — 2026-04-23

### config
- tui.auto_resume flag for bare alpi (AL closed) (`8404526`)

## v0.2.49 — 2026-04-23

### roadmap
- expand v0.3 backlog (AH–AT) + pre-push CHANGELOG hook (`543834d`)

## v0.2.47 — 2026-04-23

### setup
- first-time help text in gateway/MCP wizards (AG closed) (`88e4086`)

## v0.2.46 — 2026-04-23

### cli
- shrink surface, unify logs, add live doctor (AD/AE/AF) (`b110569`)

## v0.2.41 — 2026-04-23

### setup
- normalise wizard UX across the board (`b46929f`)

## v0.2.40 — 2026-04-23

### gateway
- service install/uninstall wizard (AB closed) (`f372ec0`)

## v0.2.39 — 2026-04-22

### cleanup
- `alpi setup → Cleanup` wizard (AA closed) (`5825e87`)

## v0.2.38 — 2026-04-22

### approval
- panel styled like /model, YOLO removed (`6be95ca`)

## v0.2.37 — 2026-04-22

### approval
- three-severity command gate for terminal (W closed) (`2064d10`)

## v0.2.36 — 2026-04-22

### browser
- humanised typing, dismiss camoufox (`a54425f`)

## v0.2.35 — 2026-04-22

### tidy
- move PERSONALITY.md under memories/, gmail_token under secrets/ (`2914fe0`)

## v0.2.34 — 2026-04-22

### gateway
- persist telegram offset, log backlog catch-up (`418d2fb`)

## v0.2.33 — 2026-04-22

### misc
- profile list: accent diamond + model + size + abbreviated path (`4a832b6`)

## v0.2.32 — 2026-04-22

### setup
- reorder Model wizard — Ollama first, cloud second (`1e4b119`)

## v0.2.31 — 2026-04-22

### tui
- profile disk size in top bar + document TUI features (`416f203`)

## v0.2.30 — 2026-04-22

### sandbox
- allow_network=off now blocks Python-native network tools (`83f9d00`)

## v0.2.29 — 2026-04-22

### tos
- remove C (Codex OAuth) and V (Anthropic OAuth) from backlog (`5e77f17`)

## v0.2.28 — 2026-04-22

### misc
- tts + send_message: autoplay off on gateway, terse outputs (`5e80755`)

## v0.2.27 — 2026-04-22

### brand
- nickname → alpi across ~130 files (`00722a9`)

## v0.2.26 — 2026-04-22

### misc
- mcp + providers: OpenAI-compat tool names, curated lists, ctx window (`6ddf316`)

## v0.2.25 — 2026-04-22

### voice
- tts + stt + telegram voice inbound/outbound (M closed) (`1af86d6`)

## v0.2.23 — 2026-04-22

### gmail
- OAuth2 gateway + mail tool dispatch (T closed) (`d8b644e`)

## v0.2.22 — 2026-04-22

### refactor
- email → mail/imap rename for upcoming Gmail backend (T commit 1/3) (`d9cd7de`)

## v0.2.21 — 2026-04-22

### read_image
- auto-resize oversized images before vision (S closed) (`2823b4b`)

## v0.2.20 — 2026-04-22

### misc
- security pack: tool budget + OSV malware + schedule threat-scan (`8d79faf`)

## v0.2.19 — 2026-04-22

### roadmap
- extend backlog with TTS/STT, Gmail/Signal, approval, OSV (`2e504f3`)

## v0.2.18 — 2026-04-22

### research/delegate
- batch parallel tasks (R.3 closed) (`5eec824`)

## v0.2.17 — 2026-04-22

### skill
- add validate action for correctness checks (Q closed) (`88e2721`)

## v0.2.16 — 2026-04-22

### browser
- Playwright tool with stealth-by-default and optional vision (`9710574`)

## v0.2.15 — 2026-04-21

### ollama
- first-class provider + kill the generic custom slot (`9a3b4e1`)

### todo
- add in_progress status to match the prompt promise (`664e184`)

## v0.2.14 — 2026-04-21

### tui
- /tools skips MCP-registered tools (`836f28a`)

## v0.2.13 — 2026-04-21

### misc
- remove the config tool — config is user-owned (`ba7ce49`)

## v0.2.12 — 2026-04-21

### rename
- alf → alpi across the entire codebase (`85384c3`)

## v0.2.11 — 2026-04-21

### misc
- sandbox polish: promote from "experimental" to per-profile opt-in (`679fca8`)

## v0.2.10 — 2026-04-21

### ui
- drop questionary, build menu()+text() directly on prompt_toolkit (`1063bf2`)

## v0.2.9 — 2026-04-21

### tui
- AlfTopBar drops labels in narrow mode (`a5fd740`)

## v0.2.8 — 2026-04-21

### tui
- AlfHeader adapts to available width (`c065e14`)

## v0.2.7 — 2026-04-21

### tui
- panel header elevation flips in light mode (`6c02eeb`)

## v0.2.6 — 2026-04-21

### tui
- /mcps panel listing running MCP servers (`b13ed62`)

## v0.2.5 — 2026-04-21

### tui+setup
- /model as panel, user-driven openrouter, live anthropic/openai fetch (`f64bebf`)

## v0.2.4 — 2026-04-21

### read_image
- vision tool with URL, SVG, and model-override (D) (`b71ce2f`)

## v0.2.3 — 2026-04-21

### delegate
- write-capable sub-agent with file/terminal/web toolsets (R.2) (`fdf999a`)

## v0.2.2 — 2026-04-21

### research
- prefix inner emit_state with step counter (R.1) (`1722fab`)

## v0.2.1 — 2026-04-21

### tui
- theme system + floating panels + scaffold polish (`9ed4139`)

## v0.2.0 — 2026-04-21

### docs
- add MODELS.md — tiered model recommendations for agent use (`df29cfc`)
- record identity-wizard decision as rejected (`60122b7`)
- split CONTEXT into ARCHITECTURE + ROADMAP, position alf as lighter Hermes, bump to v0.2.0 (`6b946e4`)

### fix
- propagate active profile to tool context + sharpen memory prompt (`1470bdb`)

### gateway
- stream tool traces + typing indicator; simplify allowlist (`fe3a3d4`)

### gateway/schedule
- fail fast if the profile has no usable workspace (`04bdaba`)

### schedule
- fix immediate-fire, UTC vs local tz, duplicate delivery (`3dd4522`)
- kind=once and LLM time grounding (`1fc3610`)

### skills
- unified tool, subdir contract, live-by-default, path guards (`2e67830`)
- auto-inject index into system prompt + render skill name in tool cards (`4035327`)

### tooling
- level-2 comment cleanup across alf/ (`a07e40a`)

### tools
- rename delegate → research, depth tiers driven by config (`d2ceb74`)

### tui
- surface inter-tool prose + reasoning tokens in live indicator (`62f7fa7`)
- reasoning persists across sessions, show_reasoning toggle, tighter layout (`fd1fec4`)

### web_search
- dedup by domain + lean description (`b04b394`)

### misc
- remove stray test artifacts and fix layout in README (`56d1711`)
- send_message tool + delivery refactor (`6e31ace`)
- schedule daemon: tool + CLI + rename from cron (`2245e42`)
- install/uninstall for gateway + schedule (launchd + systemd) (`cd62da0`)
- profile CLI + drop all migration/legacy code (`630f97c`)
- email subsystem + alf setup UX polish (`c67e618`)
- email gateway channel + per-platform config namespace (`4691df8`)
- mcp client — user-configured MCP servers as alf tools (`0d376ac`)
- setup UX: shared ui primitives, profile-scoped status, CLI polish (`7a81770`)
- memory tool: compress description to Hermes-style, keep all invariants (`b214ce6`)
- tool descriptions: compress terminal/email/schedule/send_message/session_search (`19f1287`)
- config polish: minimal seed, config tool, /new session, accent spinners (`2dadc09`)
- tool descriptions: restore CALL directives + English-only language rule (`6be1685`)
- security phase 1: terminal denylist, SSRF block, tool-output injection scan (`a54d99d`)
- security phase 2: opt-in OS sandbox (sandbox-exec / bubblewrap) (`e78b428`)
- merge glob + grep into search; fix relative-path resolution (`2b73091`)
- file tools: drop workspace wall, match terminal's denylist posture (`3e2dc29`)
- skill tool: patch/view actions, state/ subdir, scanner beef-up (`211c022`)

## v0.1.0 — 2026-04-19

### misc
- initial commit — alf v0.1 (`a0c7630`)
