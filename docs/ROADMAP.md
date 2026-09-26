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

## Next cycle — isolated conversations, explicit limits, faithful ingest

Priorities reviewed against the local v0.15.17 code on 2026-09-24. Local
reproductions confirmed the timeout clamp, Word-table loss and history reuse
within one peer; the other findings below are source inspection. Fleet
incidents are operator-reported evidence, not independently replayed here.
No production data or external services were used in this review.

The next cycle should repair observable failures, not add another orchestration
layer or reopen settled product decisions. The items below are bounded
fixes; each can ship independently. The order below is also the commit plan:
five commits, with only KB.11 and KB.13 grouped. Each implementation includes
its tests, relevant docs, bump and changelog. UX.7 releases desktop; the other
groups release alpi unless their implementation also changes a client.
Do not bundle unrelated work just because it is ready at the same time.

| Order | ID | Priority | Evidence | Outcome |
|---|---|---|---|---|
| 1 | SCHED.4 | P2 · 🟡 | A stored timeout of 5400 resolves to 3600 | The declared valid timeout is honoured consistently, including above one hour. |
| 2 | TERM.3 | P3 · 🟡 | A Morpheus terminal command could not find the skill's volume JDK | Explicit profile environment reaches foreground, background and Docker commands. |
| 3 | KB.11 + KB.13 | P2 · 🟡 | Source text is silently cut at 12000 characters; Word tables are discarded | Ingest reports its cut and preserves ordinary Word tables in document order. |
| 4 | UX.7 | P3 · 🟡 | Storage repeats inventory bytes under separate reclaim/delete rows | One inventory with safe and individually confirmed destructive actions on each group. |
| 5 | KB.14 | P3 · 🟡 | The index uses mtime/size to decide whether to embed again | Unchanged content does not cause another paid embedding. |

### SCHED.4 — honour the timeout a job declares

**Evidence.** `schedule(add|update, timeout=5400)` rejects the value, while
[scheduler/run.py](../alpi/scheduler/run.py) silently clamps a directly stored
5400 to 3600. The fleet reported a healthy Maven run killed near one hour,
then completed manually. The local reproduction confirms the clamp, not the
production timing.

**Decision.** Honour valid declared durations above 3600. Keep the current
default, minimum and soft-budget reserve; do not add a second knob or another
arbitrary one-hour ceiling. Use one duration contract for add/update,
execution, listing and the silence watchdog. Validate malformed, boolean,
non-finite and unrepresentable durations explicitly; a bad stored value must
not silently become an apparently valid timeout or crash the scheduler.

**Acceptance.** A stored or tool-created 5400 s job reports and enforces 5400
in agent and script paths; the watchdog uses the same duration and the engine
receives the corresponding soft budget. Exercise the boundary with a fake
clock rather than an actual 90-minute test. Existing timeout failure details
and process cleanup survive. Updating neo/smith/morpheus jobs in the fleet is
a separate operational change, not permission to edit that repository here.

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
Do not let the map override Alpi's internal execution/ownership markers.
Docker has an explicit environment forwarding list: changing only the parent
`Popen` environment is not sufficient for that backend.

**Acceptance.** A profile with the map runs `java -version` through
`terminal` and finds the volume JDK; a profile without it is byte-for-byte
unchanged; `PATH` keeps the original entries after the prefix; the map is
listed in the takes-effect table and the packaged config reference. Test
foreground/background, native sandbox and Docker forwarding, invalid map
values, and protected internal variables. Preserve the backend's own PATH
when adding its prefix, not a host PATH that may not exist inside the image.

### KB.11 + KB.13 — preserve source content and report deliberate cuts

**Evidence.** [knowledge_base.py](../alpi/tools/knowledge_base.py) sends
`source_text[:12000]` without truncation metadata. The shared Word reader in
[workspace.py](../alpi/tools/workspace.py) reads `doc.paragraphs` only; a local
DOCX with a paragraph and a table loses the table. These are two small source
fidelity fixes, not new knowledge capabilities, and belong in one commit.

**Smallest change.** Keep the existing source budget, but tell both the
synthesizer and the tool caller whether it was cut, how many characters were
available and how many were used. Preserve ordinary Word tables and their
order relative to paragraphs using the existing `python-docx` dependency.
Do not add chunked synthesis, vision, translation or another document library.

**Acceptance.** Sources below, at and above the limit report accurate counts
in preview and apply results; the model sees the cut too. A paragraph/table/
paragraph fixture retains text in order, with explicit handling of empty and
merged cells and no claim of full Word layout fidelity. Exercise the shared
reader and the ingest path, plus regressions for its other consumers. The
existing protection of truncated related pages against overwrite remains.

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
rows share a label. Every destructive plan member with something to reclaim
stays individually actionable; safe members are grouped per inventory row.
The per-row amounts sum
to the sweep total. Destructive actions still open `ConfirmDelete`; the safe
members of one group are one click; the admin-only gate (`canClean`) is
unchanged. `maintenance.test.jsx` covers the folded layout with a mixed group
and the desktop changelog entry pins no new alpi minimum.

### KB.14 — avoid re-embedding unchanged content

**Evidence.** [knowledge_base.py](../alpi/tools/knowledge_base.py) compares
mtime and size before deciding to skip a file. A metadata-only change therefore
re-embeds unchanged text. The fleet reports 274 pages taking 444 seconds after
a move; that timing was not independently reproduced.

**Smallest change.** Compare a content fingerprint before paying for another
embedding. Cover all content that affects the indexed page, not just its body;
an embedder change or explicit force still follows its existing rebuild
contract. Keep the single-root store and transactional rebuild. Limit schema
work to the metadata needed for this decision; no generalized index framework.

**Acceptance.** A touched unchanged page does not call the embedder; changed
text with the same size and restored mtime is not silently skipped. Metadata
changes update the index correctly. Existing indexes without a fingerprint
remain usable and acquire it on indexing without dropping unrelated tables.
Failure still rolls back the pass. Test with a counting embedder and real
SQLite, not timing or external API calls. Keep this separate from ingest fixes.

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
- No new runtime dependency, RPC framework or service is presumed necessary.
  KB.14 may need an index metadata field; that does not authorize a general
  persistence redesign. Run both client suites
  for UX.7 and verify destructive confirmations in the rendered desktop UI.

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
| KB.12 | Vision in knowledge ingest. An image reaches `knowledge(action="ingest")` only with `ocr=true`, which keeps its text and loses everything a diagram or screenshot shows; `tools.read_image.model` is never used there. On 2026-09-24 agora needed a skill (read the image with `read_image`, store it as an asset, write an OKF page that embeds it) to keep diagrams. Promote when a second profile wants images kept as knowledge. |
| TIER.1 | A model tier per task, not only per job. A job's `tier` sets `ALPI_TIER` for its whole turn ([scheduler/run.py](../alpi/scheduler/run.py), read in `engine.py`), but a chat turn always runs on the main model. agora's nightly Confluence ingest runs on `deep` (`:nitro`, effort high), while the same writes asked from chat (a PDF, "add", "fix", "remove" through the `okf` and `confluence-ingest` skills) run on the default model. A skill-level `tier` that raises the rest of the turn once that skill runs would separate knowledge writes from questions. Promote when a second profile mixes cheap questions with quality-sensitive writes in chat. |
| SCHED.5 | A cron job fires on the first tick after it appears, whatever its expression. `is_due` in [scheduler/run.py](../alpi/scheduler/run.py) returns true for a cron job with no `last_run_at` "so the user sees activity right after adding a job". On 2026-09-24 two jobs written into Curator's `jobs.json` on the AWS box (`booking-cache` at `35 3 * * *`, `weekly-report` at `25 17 * * 0`) both ran within a minute on a Thursday afternoon, and the weekly report landed three days early. A fleet that deploys jobs by file has to seed `schedule/runs.json` with `last_run_at` to avoid it. Anchoring a first run on the next occurrence of the expression, for jobs that did not come from the `schedule` tool or chat, would keep the immediate feedback where a person is watching. Promote when another fleet deploys schedules by file, or when an early run of an expensive job costs real money. |
| UX.8 | Chart usage by money when the profile pays for it. The desktop Usage panel ([Usage.jsx](../desktop/src/features/settings/Usage.jsx)) sizes each day's bar by tokens (`maxTok`) and shows the cost only in the tooltip, while the headline and the daily cap are in dollars. With prompt caching the two diverge: on 2026-09-25 curator's day was 276M input tokens for $24.88 of a $40 cap, so the bars say nothing about the number the owner watches. The ledger already keeps cost and tokens per day ([ledger.py](../alpi/ledger.py)). Scale the bars by cost when the window has any cost, and by tokens when every day costs nothing (free or local models); two charts or a toggle are the alternatives. Requested by the creator on 2026-09-26. |
| KB.15 | The embedder reads only part of each chunk. fastembed's `all-MiniLM-L6-v2` ([core/embed.py](../alpi/core/embed.py)) truncates its input at 128 tokens, while `_chunk_lines` ([tools/workspace.py](../alpi/tools/workspace.py)) cuts pages into 30-line chunks with a 25-line stride; on agora's base (13.5k chunks) the median chunk is about 1,000 characters, so each vector sees roughly its first half and the rest is found only by full-text search (`okf_fts`, bm25). Shorter chunks (about 12 lines or 500 characters) or a model with a longer window would close it. Promote when semantic search misses content that full-text search finds, or before indexing long documents at scale. |
| ATT.2 | A produced file under `/tmp` is listed but cannot be downloaded. The engine records an `attach_file` or `skill` output as an attachment when it lies under the home, the workspace or the temp directory (the `_roots` list in [engine.py](../alpi/engine.py)), but the host serves non-image attachments only from `host/attachments/tmp`, `out/` and the workspace (`_fetch_nonimage_allowed` in [host/attachments_rpc.py](../alpi/host/attachments_rpc.py)). On 2026-09-25 Alexandra's documents written to `/tmp` appeared as attachments in the CLI and would have failed in the app; writing them to `out/` fixed it. Align the two lists (drop `/tmp` from the produced roots, or serve it) and name `out/` in the `attach_file` description. A bug; small. |
| FILE.1 | Member file tools can read other profiles' run journals and ALP threads. `_MEMBER_HOME_AREA` in [_paths.py](../alpi/tools/_paths.py) fences `host`, `secrets`, `gateway`, `cache`, `logs`, `outputs`, `sessions`, `memories`, `schedule`, `skills` and `alp`, but not `runs/` (every tool input and output of every run) or `mentions/` (conversations relayed over ALP), and not other profiles' workspaces. A member-facing profile with `read_file` (Alexandra, since 2026-09-25) is kept off them only by its persona. Add `runs` and `mentions` to the member areas. Worth doing now: Alexandra has `read_file` on both instances of the Mirai fleet. |

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
