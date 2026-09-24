# Roadmap

Open work for alpi. Shipped work lives in
[CHANGELOG.md](../CHANGELOG.md) — this file never repeats it. For
technical reference of what currently ships, see
[ARCHITECTURE.md](ARCHITECTURE.md).

Audience: the creator ([@soyjavi](https://github.com/soyjavi)) and
any future contributor reading the repo cold.

Legend: 🟡 prioritized · 🔵 optional / demand-gated. Priority is impact,
not permission to start implementation. Remove completed items; do not replace
them with broader work unless a new, evidenced need exists.

---

## v0.16 — trustworthy accounting, bounded I/O, recoverable indexes

Reviewed against `31385983` (v0.15.6), 2026-09-22. This is a targeted source
audit with local reproductions, not a claim that every path or deployment was
verified. It covers the engine/tool boundary, shared persistence, MCP,
workgroup admission, and the Python/Docker release path. Client UI and live
infrastructure were not re-audited. No production data or external services
were used in the reproductions below.

The next cycle should repair observable failures, not add another orchestration
layer or reopen settled product decisions. The items below are bounded
fixes; each can ship independently as a patch before v0.16.

| Order | ID | Priority | Evidence | Outcome |
|---|---|---|---|---|
| 1 | TERM.3 | P3 · 🟡 | Observed in a Morpheus run on 2026-09-22: the agent could not find its JDK from `terminal` | A profile can hand `terminal` extra environment variables. |
| 2 | SCHED.4 | P2 · 🟡 | A 5400 s job died at 59:46 on 2026-09-22; a stored timeout above 3600 is clamped at run time without a word | The timeout a job carries is the one the scheduler enforces, or the clamp is shown before it bites. |
| 3 | UX.7 | P3 · 🟡 | The desktop Storage field on 2026-09-24: nine rows, two of them labelled `delete`, plus a `reclaim` row re-counting bytes already shown above it | Storage is one inventory; whatever can be reclaimed is offered on the row it belongs to. |

### TERM.3 — let a profile hand `terminal` extra environment variables

**Evidence.** [terminal.py](../alpi/tools/terminal.py) builds the subprocess
environment itself; [CONFIG.md](CONFIG.md#tools) exposes the backend, the
sandbox, network and the approval allowlist, but no way to add variables.
A skill runner that installs its own toolchain into the volume (the Java
`repo-task` keeps JDKs and Maven under `/data/toolchains`) exports
`JAVA_HOME` and a `PATH` prefix only to the subprocesses it spawns; the
agent's own targeted commands through `terminal` see neither. In a
2026-09-22 Morpheus run the agent tried to discover them and the sandbox refused the
command as `dangerous pattern: dump environment`; it recovered by spelling
absolute paths, which every future Java task would have to repeat.

**Smallest change.** A `tools.terminal.env` map in the profile config
(`JAVA_HOME`, `PATH` and the like), applied on top of the environment the
tool already builds, with `PATH` prepended rather than replaced. Values are
plain strings; no secret expansion, no reading of `.env` keys into the
shell, and the existing sandbox and allowlist apply unchanged.

**Acceptance.** A profile with the map runs `java -version` through
`terminal` and finds the volume JDK; a profile without it is byte-for-byte
unchanged; `PATH` keeps the original entries after the prefix; the map is
listed in the takes-effect table and the packaged config reference.

### SCHED.4 — stop clamping a stored job's timeout in silence

**Evidence.** The save path already validates: `schedule(add|update,
timeout=5400)` is refused with `'timeout' must be between 30 and 3600
seconds`. The run path does not tell anyone: [scheduler/run.py](../alpi/scheduler/run.py)
applies `max(30, min(MAX_RUN_TIMEOUT_SECONDS, secs))` to whatever the stored
job carries, so a `jobs.json` holding `5400` runs for 3600 seconds without a
word. That is how the fleet's values got in: the `neo` and `smith` weekend
jobs were written straight into `profiles/<p>/schedule/jobs.json` in the
fleet configuration repository, never through the tool. `write_file` and
`edit_file` accept the same out-of-range value in `jobs.json`, so an agent
can author one too. On 2026-09-22 a Morpheus pass on `mkto-worker` (a 510 MB
Maven repository) had merged a concurrent `main`, resolved the conflict and
was in its last verification when the subprocess was killed at 59:46 with
`agent timed out`; the branch and baseline survived and a manual chat turn
finished the pull request in 19 more minutes. The architecture reference
calls the cap "a stuck-process backstop, not a hint that jobs must be short",
yet the cap is what ended a healthy run.

**Smallest change.** Make the stored value and the enforced value the same
number. Either honour a declared timeout above 3600 for jobs everywhere it is
checked (the tool, the scheduler, the silence watchdog), keeping the soft
budget so the engine finalises first; or keep the ceiling and make the clamp
visible where the operator looks — `schedule list` shows the effective
timeout and marks a clamped job, and the clamp is logged when a run starts.
Do not add a second timeout knob.

**Acceptance.** A job stored with `timeout: 5400` either runs for 5400 s, or
is shown as clamped to 3600 before it ever runs and says so when it does;
`schedule list` shows the effective timeout; the existing `schedule.failed`
payload keeps naming the reason. The neo, smith and morpheus job files in the
fleet repository are corrected to whatever the scheduler will honour.

### UX.7 — make the desktop Storage field one inventory again

**Evidence.** [maintenance.jsx](../desktop/src/features/settings/fields/maintenance.jsx)
renders three unrelated lists under one heading: a usage row per group in
`STORAGE_GROUPS` (up to seven), then a `reclaim` row with a single **Clean**
button for every non-destructive member of `host.cleanup.plan`, then a
`delete` row per destructive member (old sessions, mentions, run journals,
workgroup history, generated files). Fully populated that is thirteen rows,
five of them labelled `delete`. On 2026-09-24 a small local profile showed
nine: six usage rows, `RECLAIM · Clean · 571 KB · 19 items · caches, logs and
knowledge — always safe`, and two `DELETE` rows (`chats older than 30 days`,
`all @-mention threads`). Three things make it unreadable:

- The row label is the verb, not the target, so consecutive rows read
  `DELETE / DELETE` and the target is demoted to a muted note.
- The reclaim row re-counts bytes already shown above it (the 571 KB is part
  of Logs and Knowledge) without saying which rows would shrink; the user sees
  the same storage twice and cannot map one to the other.
- The safe / destructive split is real (`destructive: true` marks user content
  with a retention cut: chats and generated files older than 30 days, run
  journals, every mention thread, every workgroup transcript; the rest is
  regenerable) but the UI expresses it as two different sections instead of a
  property of the row it belongs to. The daemon already tags every plan member
  with its group (`GROUP_OF` in [cleanup.py](../alpi/cleanup.py)) and the
  component already builds `planByGroup`; the data to fold them is there.

The console (`alpi setup → Cleanup`) shows the same plan as one menu: **Clean
all safe** plus one entry per destructive category marked ⚠. Mobile's
`CleanupSheet` is a separate sheet with one row per member. Three surfaces,
three shapes, one contract.

**Smallest change.** Desktop rendering only; `host.profile.storage`,
`host.cleanup.plan` and `host.cleanup.apply` stay as they are, so console and
mobile are untouched. Each group row keeps its size and file count and gains,
on the same row, its reclaim actions: one **Clean** chip totalling the group's
safe members, plus one **Delete** chip per destructive member, named after the
target ("chats older than 30 days", "run journals") and confirmed. Groups are
mixed, so actions are never merged across members: Logs shows Clean plus
Delete run journals; Conversations shows three named Deletes and no Clean;
Files shows Clean plus Delete generated files. The standalone `reclaim` and
`delete` rows go away; one **Clean everything safe** summary may stay as a
single line if a real user misses the one-click sweep. Drop the "always safe"
prose; the chip placement says it. No new component library, no new verb.

**Acceptance.** With every category populated the field renders no more rows
than there are non-empty storage groups plus at most one summary line; no two
rows share a label. Every plan member with something to reclaim stays
individually actionable, on the row of its group, and the per-row amounts sum
to the sweep total. Destructive actions still open `ConfirmDelete`; the safe
members of one group are one click; the admin-only gate (`canClean`) is
unchanged. `maintenance.test.jsx` covers the folded layout with a mixed group
and the desktop changelog entry pins no new alpi minimum.

### Optional: CAP.1 — show admission pressure without changing admission

The former ALP.9 alternative has already been chosen:
[CONFIG.md](CONFIG.md) and the packaged config reference explicitly say
**admission threshold, not a hard cap**. `_drain_pipeline_queue` recalculates
the active set; QA rewind, hub tasks and resume are not new FIFO admissions.
Do not silently queue resume, block QA recovery, or reinterpret a human task
to make the number look strict.

There is a narrower visibility gap: `workgroup list` prints the configured
threshold/origin and queue but not the active count;
[host.profile.detail](../alpi/host/device_state.py) exposes the threshold and
queue count but no active count. If selected, expose `active_workgroups` and
an advisory `over_threshold` in detail, the CLI, and the existing desktop
settings surface. Extract the counting rule from
[service._active_workgroup_ids](../alpi/service.py) into the workgroup domain
so every consumer uses one definition; do not make the CLI import the daemon
or add a persistent counter that can drift.

Acceptance: active/paused/between-phase/deliberation cases agree across
surfaces; `0` is unlimited and never over-threshold; inherited limits work;
an unreadable state is not presented as a verified zero. This is **🔵 optional
observability**, not a release gate and not a replacement hard-cap task.

### Verification required to close this cycle

- Add failing regressions for each item, then prove the fix. A green suite
  without the reproduced interleaving/failure is not closure.
- Run subprocess/pipe tests on Linux as well as macOS. Real `/proc` and pidfd
  acceptance must remain distinguishable from mocked decision tests.
- The current Python publish gate runs `pytest -q`; integration runs live in
  the PR/manual workflow. Ensure the relevant real-process tests pass for the
  exact release SHA before publishing, including direct-to-main releases.
  Reuse the existing workflows rather than create a parallel test system.
- No new runtime dependency, storage format, RPC framework or service is
  presumed necessary for the four fixes. Clients are only in scope if a
  selected item changes a user-visible contract.

### Simplification boundaries

Large files alone are not defects. `service.py`, `cli.py` and `engine.py`
coordinate many existing features; splitting them wholesale would create
review churn without proving an outcome. Extract a domain helper only when
it removes an evidenced duplication or inappropriate dependency (CAP.1), and
keep the indexers' atomicity rules consistent without generalizing their data
models.

Do not revive full config typing, a second orchestration framework, multi-root
knowledge storage, or nested Docker sandboxing just to populate a release.
A container and volume remain one trust scope; mutually untrusted scopes need
separate runtimes. Deployment acceptance is an operational responsibility, not
something this source audit certifies. Credential-loss procedures remain in
[OPERATIONS.md](OPERATIONS.md); enterprise audit is demand-gated below.

---

## Backlog — demand-gated

Only plausible next moves stay prominent. Everything here waits for observed
usage or a concrete blocker; standing maintenance belongs in
[OPERATIONS.md](OPERATIONS.md), not in the product backlog.

### Candidates

| ID | Candidate and promotion condition |
|---|---|
| BUILD.1 | Align the reproducible test environment with the managed image. Local verification uses `uv.lock`, while Python CI installs `.[dev]` and Docker runs `pip install .`; the smoke image and published multi-architecture image are separate builds. Inspect the resolved dependency sets and artifact digests before choosing lock export, constraints or promotion of the tested artifact. Promote on demonstrated drift or a requirement for reproducible image rebuilds; keep a separate unlocked compatibility check rather than freezing library consumers to one environment. |
| TERM.2 | SSH terminal backend for remote command execution. Promote when an unattended profile needs to operate on a remote machine. |
| AUDIT.2 | Enterprise audit and accountability: complete local mutation coverage, then add tamper-evident external records, provider policy, encryption, or RBAC only when a real fleet or compliance regime requires them. |
| ALP.7 | Pinned shared memory per workgroup (`wiki.md`). Promote when sustained workgroup use shows that the transcript is no longer enough. |
| SK.2 | Safe skill import (`alpi skill import <dir\|zip>` with preview, scan, and install). Promote when users repeatedly exchange skills outside their own profile. |
| SK.3 | Let a profile lock its own skills against its file tools. The denylist in [_paths.py](../alpi/tools/_paths.py) protects `config.yaml`, `.env` and skill `secrets/`, and keeps `skills/` away from members, but the profile itself can rewrite the scripts that enforce its own gates. On 2026-09-22 a scheduled Morpheus pass edited its `repo-task` runner mid-run, left a `run.py.bak`, fixed a real toolchain gap and broke one of the skill's tests; the live copy diverged from the fleet repository. Today the only guard is a sentence in `AGENT.md`. Opt-in only (inline skill updates are a product choice): a profile setting under which `write_file`, `edit_file` and the skill tool's write actions refuse the profile's own `skills/`. Promote when a second unattended profile edits its own skill, or when a fleet needs that guarantee enforced rather than asked for. |
| AI (3) | Structured entity memory with selective injection. Promote when keeping the markdown store coherent becomes a repeated source of defects or selective recall is required. |
| TTS.1 | Host-served local TTS and a single voice catalog. Promote when voice becomes a sustained client surface. |
| KB.9 | Spreadsheet (`.xlsx`) ingest into knowledge pages: one Markdown table per sheet, headers from the first row, `type: source`. The container ships neither `openpyxl` nor `pandas`, so this is either a stdlib zip+XML reader or a new image dependency. Promote when a real document set arrives as spreadsheets; the 2026-09 Confluence publishing skill covers Markdown, PDF and Word only. |
| ATT.1 | Keep an attachment when the user asks to. The host already stages every chat attachment under `<home>/host/attachments/tmp/<id>/<name>` and lists those absolute paths in the message for skills to read, but the staging area is swept after 6 hours, so a file the user wants to keep working with across days has to be re-attached. Add an explicit "keep this file" path (a tool or a `save_attachment` skill hook) that copies a staged attachment into `<workspace>/attachments/` and returns the durable path. Promote when a real flow needs a file to outlive the turn; on 2026-09-14 the Confluence publishing flow did not, because it publishes in the same turn. |
| KB.10 | A language policy for `knowledge(action="ingest"\|"maintain")`. `_MAINTAIN_PROMPT` in [knowledge_base.py](../alpi/tools/knowledge_base.py) says nothing about language, so a synthesized page follows its source; a profile whose knowledge must be English cannot get that from the tool. On 2026-09-24 agora's audit found 239 Spanish titles and 152 pages with Spanish lines, and the fleet now routes every agora write through a skill gate instead of the tool. A `knowledge.language` setting passed to the prompt and checked on the proposal would do. Promote when a second profile needs a fixed knowledge language, or agora goes back to the tool for curation. |
| KB.11 | Say when `maintain_knowledge` truncates its source. It sends `source_text[:12000]` to the model without a word, so a long PDF becomes a page about its first pages and the result never mentions the cut. Chunk the source, or at least return `truncated: true` with the characters used. Promote when a long document is ingested through the tool rather than a skill. |
| KB.12 | Vision in knowledge ingest. An image reaches `knowledge(action="ingest")` only with `ocr=true`, which keeps its text and loses everything a diagram or screenshot shows; `tools.read_image.model` is never used there. On 2026-09-24 agora needed a skill (read the image with `read_image`, store it as an asset, write an OKF page that embeds it) to keep diagrams. Promote when a second profile wants images kept as knowledge. |
| KB.13 | Keep Word tables in knowledge ingest. The daemon's `.docx` reader keeps paragraphs only, so every table is lost; agora's publishing skill converts the same files with their tables. Promote with the next change to the attachment readers. |
| KB.14 | Reindex by content, not by mtime. The index keys files on mtime and size, so a copy that truncates mtimes (a `tar` to another host) re-embeds every page it touched: 274 pages took 444 s on casa on 2026-09-24. Compare a content hash before re-embedding. Promote when a profile's knowledge moves between hosts routinely. |

### Watchlist

These ideas remain recorded without presenting them as likely next work.

| ID | Revisit only when |
|---|---|
| BROWSER.1 | A vetted lightweight backend passes real acceptance and the headless-shell footprint (344 MB since v0.14.9, down from 984 MB) still blocks a target host. |
| ALP.8 | Per-profile capacity (`alp.max_active_workgroups`) and a durable admission queue already ship; users need dynamic worker pools or cross-peer capacity negotiation on top of them. |
| ALP.3+ | Persistent workgroups demonstrate sustained parallel tasks that targeted tasks and pipeline continuation cannot cover. |
| AY / BF-8 | A real skill author or import community needs a federated marketplace, versioning, or update flows. |
| AQ | A real voice surface needs continuous push-to-talk or hotword loops on top of the read-aloud path that already ships (host-served synthesis, per-profile voice, auto-read). |
| UX.6 / External secrets | A masked, auditable editor for arbitrary `.env` keys (the RPC already writes any key; only provider keys are listed back), or central key rotation, becomes repeated friction. |

---

## Principles

alpi **respects the ToS of every provider it integrates with**. When
an LLM vendor offers a paid subscription tied to a specific first-party
client (the vendor's own chat app, IDE, or CLI), that subscription is
for THAT client. Reverse-engineering the private OAuth flow of the
official CLI to route a third-party agent against the same quota is:

- A clear ToS violation.
- Disrespectful to the vendor's product boundaries.
- Unsafe for users (accounts can be banned; the reversed flow can
  break any time).

Private subscription routing is not part of alpi's product shape. If
a vendor publishes an official
OAuth-for-third-parties flow in the future (documented, stable,
bindable), we adopt it then.

**Practical consequence:** users pay per-token API access through
their own keys. That cost is honest and visible. Subscription
routing is not on the roadmap.

See **Why alpi exists** in [README.md](../README.md) for how the
publisher's principles map to concrete choices in this repo.

---

## Decisions discarded — don't relitigate

| Decision | Reason |
|---|---|
| Vendor subscription OAuth | ToS violation and account-risk surface; users bring normal API keys. |
| Chat-app gateways (Telegram, Matrix, Signal, WhatsApp, Discord, …) | Retired in v0.10 — third-party chat bridges add attack surface and upkeep; the desktop/mobile/terminal apps are the surface, and email is an on-demand tool. |
| Smart-home orchestration | Device protocols and physical-world policy belong in Home Assistant / MCP / user skills, not core. |
| LangGraph / CrewAI / AutoGen as core | Graph frameworks do not match Alpi's profile/workgroup runtime and pull toward hosted observability. |
| Image generation as a core tool | Useful via MCP or user skills, but a built-in provider surface would turn Alpi into a creative-tool platform. |
| Mixture-of-agents runtime | Expensive research pattern; workgroups cover explicit multi-profile collaboration. |
| RL / fine-tuning hooks | Research infrastructure, not a personal-agent product surface. |
| Cost telemetry per skill / tool | Per-profile daily ledger is enough while skills are sparse and user-owned. |
| Browser anti-bot depth / camoufox | Cat-and-mouse and heavy dependencies; current Playwright posture is enough until a real user hits a wall. |
| Go / Bubbletea rewrite | No upside over the Python stack and LiteLLM ecosystem. |
| Heavy TUI chrome / rich.Live inline UI | Tried; Textual minimal TUI is the maintained shape. |
| SQLite `state.db` for sessions | Plain JSON remains fast and inspectable at current scale. |
| Separate conversation export schema | Host JSON-RPC session verbs are the contract; add export only for a second real consumer. |
| Pending approval files / skill approval gate | Removed; scanner + inline tool flows are lower friction. |
| Regex shell sandbox / workspace wall | False security without OS sandboxing; use real sandboxing and sensitive-path denylist. |
| `.bak` sibling on every `write_file` | Too much workspace clutter; backups stay limited to memory and skill files. |
| Profile identity wizard / starter packs | Profiles are shaped through chat and examples, not binary templates. Unrelated to the shipped `setup → Identity` screen, which only sets the ALP public bio. |
| Default skills bundle | Runtime capabilities are first-class tools; skills are user-owned. |
| `alpi run "<prompt>"` | Covered by `alpi chat --once "<prompt>"`. |
| Auto-reflect on Ctrl+C / post-session `/reflect` | Unsafe or redundant; inline memory/skill updates are the path. |
| TUI accessibility pass | Desktop is the right accessible surface; terminal APIs are weaker. |
| `duckduckgo-search` | Deprecated; migrated to `ddgs`. |
| True multi-root knowledge index | Partitioning the `knowledge.sqlite` tables by root is a large change for a use case nobody has; v0.14.44 made the single-root API honest instead: the index names the one bundle it holds, refuses to be replaced by another, and `force=true` retargets deliberately. |
| Renaming the `okf_*` SQLite tables | Internal and never rendered; the rename runs the drop and rebuild path, which v0.14.44 made transactional, so the only bar left is an observable benefit and there is none. |
| Hard-rejecting page shrinks in `maintain` | Consolidating is legitimate; `maintain` reports `bytes_before`/`bytes_after` per written page instead of blocking. |
| Root-relative fallback in the knowledge link resolver | Would pass lint while breaking the links in Obsidian, GitHub and VS Code; page-relative stays canonical (KB.5). |
| Renaming the `type` frontmatter key | Invalidates every existing page over a Hugo layout-key collision that will likely never matter; the docs note the collision instead (KB.7). |
| Defining what "OKF" stands for | The acronym was coined without a referent; writing an expansion now would invent a retroactive justification. It is gone from every model- and user-facing string; only the `okf_*` table names keep it. |
