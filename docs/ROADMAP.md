# alpi roadmap

Updated 2026-09-30. Current versions live in the changelogs.

This is the task pool. [ARCHITECTURE.md](ARCHITECTURE.md) owns current state and
contracts; [CHANGELOG.md](../CHANGELOG.md), [desktop/CHANGELOG.md](../desktop/CHANGELOG.md)
and [mobile/CHANGELOG.md](../mobile/CHANGELOG.md) record what each version shipped;
[AGENTS.md](../AGENTS.md) defines the workflow that consumes this file.

## How this file works

Every task is one entry that one commit per product it releases can finish, with fixed fields
(decisions only need their question):

- **ID** — stable, never reused. Keep an existing ID when ARCHITECTURE, a
  changelog, a test or a sibling repository cites it.
- **type** — `bug`, `feature`, `chore`, `ui` (a visual change drawn as a board in
  [design/](../design/)), `verify` (evidence from a real device or environment),
  `deploy` (build, install or roll out outside the repository) or `decision`.
- **product** — `alpi`, `desktop`, `mobile`, `common` or `design`, one or more. A
  task that releases several products ships one commit per product, daemon first;
  a `common/` change releases both clients.
- **owner** — `agent` (finished in the repository and proved with tests) or
  `creator` (@soyjavi: an EAS build, a device check, a fleet deploy, credentials
  or a product choice).
- **priority** — `high`, `normal` or `low`. The Queue runs top to bottom in the
  creator's order; in the other lanes, order is priority, then position.
- **depends** — IDs that must finish first.
- **accept** — what proves it done. Agent tasks need evidence a test or command
  can show.

Lanes:

- **Queue** — approved agent tasks, in the order they will be done. Only the
  creator moves a task here, with two exceptions that enter at the top: a bug the
  creator reports, and a red pipeline on `main`.
- **In progress** — at most one agent task.
- **Needs creator** — `verify`, `deploy` and `decision` tasks, and agent work
  waiting on one of them.
- **Proposed** — ideas not yet approved, from the creator or from the agent.
  Never worked on until approved.

When a task ships, delete it and record it in the product's changelog and in the
ARCHITECTURE section it changes. When a feature needs device evidence, split it:
the implementation is an agent task; the device check is a creator `verify` task
that depends on it.

A purely visual idea is not filed here: its board on the `design/` Proposals page is the
proposal. Once the creator approves it, it becomes one `ui` entry in Queue that names the
board ID, with the board as its accept; shipping it deletes the board and regenerates
`design/`. A task that mixes logic and a screen is split: the screen is board `UI-<TASKID>`, and the
logic stays under its ID with the line "the interface follows board UI-<TASKID>" in its accept; board
IDs never equal a non-`ui` task ID. Tasks with no visual component never get a board.

Every agent task also meets these, on top of its `accept`: a regression test that
fails before the fix; the relevant `pytest --integration` tests run for the exact
release SHA (`publish.yml` runs only `pytest -q`); no new runtime dependency, RPC
framework or persisted state unless the task names it; a large file is not a
defect, so a helper is extracted only when it removes evidenced duplication.

## Queue

- **TERM.3** — Profile environment for `terminal`
  `feature · alpi · agent · normal`
  note: a skill toolchain installed in the volume (JDK and Maven under
  `/data/toolchains`) is exported only to the skill runner's own subprocesses;
  [terminal.py](../alpi/tools/terminal.py) builds its environment itself and the
  sandbox refuses discovery as `dangerous pattern: dump environment`.
  accept: a `tools.terminal.env` map of plain strings in the profile config is
  applied on top of the environment the tool builds, with `PATH` prepended to the
  backend's own PATH (not a host PATH absent from the image); no secret
  expansion, no `.env` keys, internal execution/ownership markers cannot be
  overridden, sandbox and allowlist unchanged. A profile with the map runs
  `java -version` through `terminal` and finds the volume JDK; a profile without
  it is byte-for-byte unchanged. Tests cover foreground, background, the native
  sandbox, the Docker backend's explicit forwarding list, invalid values and
  protected variables. The map is listed in the takes-effect table of
  [CONFIG.md](CONFIG.md#tools) and in the packaged config reference.

- **UI-EMPTY-VOICE** — Empty states speak in one voice on both clients
  `ui · desktop, mobile, common · agent · normal`
  note: empty copy mixes lowercase headings, "none", a middle dot or em dash joining title and hint, and hints
  with or without a full stop; [emptyCopy.mjs](../common/emptyCopy.mjs) already holds the shared entries.
  accept: the board UI-EMPTY-VOICE. Every empty state on both clients follows the rule; the copy lives in
  `common/` and a test fails on a title that is not sentence case or a hint without a full stop; both client
  suites pass.

## In progress

_None._

## Needs creator

### Builds and deployments

- **BUILD-MOBILE** — EAS build of mobile 0.6.1
  `deploy · mobile · creator · high`
  accept: an EAS build of mobile 0.6.1 or later installed on the Fold and on an
  iPhone.
- **OPS-CRED-SWEEP** — Credential hygiene on every daemon
  `deploy · alpi · creator · normal`
  accept: the credential hygiene checklist in the creator's operations runbook
  has been run on every deployed daemon and `alpi doctor` reports no credential
  findings on each.

### Device checks

- **VERIFY-MOBILE-061** — Mobile 0.6.1 on device
  `verify · mobile · creator · high · depends: BUILD-MOBILE`
  accept: on device, the process block sits at 12 pt flush with the answer; the
  Fold sidebar slides; expand/collapse and the Latest button animate; a long
  press pulses only after 350 ms and a tap never moves a bubble; the notification
  count shows its number at large text sizes; approval notification actions
  answer on the right connection from a cold start.

### Decisions

- **SCOPE.D1** — Does `session_scope: device` bind an admin connection?
  `decision · alpi · creator · high`
  note: found by the SCOPE.4 inventory. `can_read_session` and `can_handle_prompt` return
  true for `role == admin`, and the member-only event filters never run for an admin, so a
  remote admin device with `session_scope: device` sees device A's sessions through
  `session_search`, `session_read`, `recall_sessions`, `host.activity.list`, prompts and
  every event, while `host.sessions.*`, `host.chat.*` and `host.runs.*` hide them. Today the
  scope is a partition for admins, not a privacy boundary.
  accept: a written decision, one of "admins are never bound" (documented as such) or "admins
  are bound for session text", with the matrix rows added for the chosen reading.
- **OPS-CONN-POLICY** — Connection policy for the fleet
  `decision · alpi · creator · normal`
  accept: a written connection policy (one connection per person with an exact
  `profile_scope`, one device per physical device, the old row revoked on
  re-pairing, a profile's tools reviewed before granting scope) is confirmed and
  applied to every deployed daemon; any code it needs becomes an agent task.

## Proposed

- **SCHED.7** — A job whose run raises is never stamped and starves the rest of the pass
  `bug · alpi · agent · normal`
  note: found while reviewing SCHED.6. `tick` in [scheduler/run.py](../alpi/scheduler/run.py)
  does not catch an exception from `run_job` or `scheduled_run` (a `PermissionError` or
  `FileNotFoundError` from the agent subprocess; only the timeout is caught): the job gets no
  `last_run_at`, the pass aborts and the jobs after it never run, and it fires again every tick.
  accept: an exception from `run_job` becomes a failed outcome stamped like any failure, the pass
  goes on with the next job, and a test with three jobs where the second raises shows all three
  handled and the second not re-fired on the next tick.
- **SCHED.8** — A long pass fires jobs from a stale snapshot
  `bug · alpi · agent · low`
  note: found while reviewing SCHED.6. `tick` iterates the jobs read at the start of the pass; a
  job removed, edited, paused or fired by hand during an earlier run of up to 86400 s is still
  fired from the old copy.
  accept: each job is re-read from `jobs.json` just before it fires and skipped if it is gone,
  paused or no longer due; a test removes the second job during the first run and it does not fire.
- **CHART.1** — The mobile Usage chart follows the cost too
  `feature · mobile, common · agent · normal`
  note: found while reviewing UX.8. Desktop sizes bars by dollars when any day cost something, with the
  input/output split drawn inside each bar (the creator confirmed this design), but
  [UsageChart.jsx](../mobile/src/components/UsageChart.jsx) still scales by tokens through `usageScale` in
  [usage.mjs](../common/usage.mjs), so one profile draws a different tallest bar on each client. The split is
  price-weighted from fixed constants because the ledger keeps one cost per day.
  accept: `byCost` and `sizeOf` live in `common/usage.mjs` and both clients use them; mobile gets the same
  thin-bar minimum, split and a "bars by" footer; a window with no cost on any day (a local model) sizes bars by
  total tokens; a component test renders a mixed window and a free window on each client.
- **SCOPE.8** — A member device's `terminal` reads every session of the profile
  `bug · alpi · agent · high`
  note: found by the SCOPE.4 inventory. Members keep the `terminal` tool, it exports
  `ALPI_HOME` and `_approval.classify` rates `cat $ALPI_HOME/sessions/*.json`,
  `grep -r … $ALPI_HOME/sessions` and `cat $ALPI_HOME/runs/*.jsonl` safe, so a turn run
  from device B can read device A's sessions, run journals and replay sidecars, and other
  connections' too. The file tools are fenced by `_member_home_area` in
  [_paths.py](../alpi/tools/_paths.py); `terminal` is not.
  accept: a member's `terminal` cannot read the profile's `sessions/`, `runs/` and `host/`
  areas; a matrix row in `tests/host/test_device_scope_matrix.py` runs `cat` on A's session
  file as device B and gets no text, with the owner or admin control reading it.
- **SCOPE.9** — Peer and host-context turns can search every session
  `bug · alpi · agent · high`
  note: found by the SCOPE.4 inventory. A turn answering an ALP peer runs as `peer:<id>`
  with the default admin role and no tool allow-list unless the peer has `tools.allow`, so
  `session_search`, `session_read` and `recall_sessions` see every session of every
  connection; a workgroup post that mentions the agent can paste that text into the shared
  transcript. Only the workgroup pipeline denies them (`PIPELINE_HISTORY_TOOLS`).
  accept: peer turns deny the history tools unless the peer's config allows them; a test
  asks as a peer and gets none of a member's session text.
- **ATT.3** — `host.attachments.fetch` ignores the caller's connection
  `bug · alpi · agent · normal`
  note: found while reviewing ATT.2. `_fetch` in [attachments_rpc.py](../alpi/host/attachments_rpc.py)
  checks roots, the denylist and, since ATT.2, the device under `session_scope: device`; under
  `session_scope: connection` and for any non-admin member it never compares the path with the
  caller's connection, so a member of one connection can fetch another connection's produced
  file or staged upload by path.
  accept: a remote non-admin caller is served only what its own connection staged or what appears
  in a session its connection owns (`owns_session` without the device clause); a test with two
  connections fetches across them and is refused, with the owner control; admin and the Unix
  socket are unaffected.
- **SCOPE.10** — A device can attach another device's staged upload to its own turn
  `bug · alpi · agent · low`
  note: found by the SCOPE.4 inventory. `host.chat.send` accepts any path under the staging
  root from a remote device, so a device that knows the path of another device's staged upload
  (`host/attachments/tmp/<hex8>/`) can attach it to its own turn and read it through the model.
  `host.attachments.fetch` is already scoped (ATT.2, v0.16.16).
  accept: `host.chat.send` refuses a staged path whose `.owner` marker names another device of a
  `session_scope: device` connection; a test stages as A and sends as B.
- **SCOPE.5** — Profile session counts respect scope
  `bug · alpi · agent · low`
  note: `counts.sessions` in `host.profile.summaries` counts every session file of the
  profile, so a member or a device-scoped device learns how many sessions other
  connections and sibling devices hold (a count only, no text).
  accept: the count includes only sessions `owns_session_row` lets the caller see; a
  test with sessions from two devices under `session_scope: device` counts one each.

Demand-gated entries name the condition that promotes them.

- **SK.2** — Safe skill import
  `feature · alpi · agent · low`
  promote when: users repeatedly exchange skills outside their own profile.
  accept: `alpi skill import <dir|zip>` previews, scans and installs; a skill
  that fails the scan is not installed.
- **SK.3** — A profile can lock its own skills against its file tools
  `feature · alpi · agent · low`
  note: the denylist in [_paths.py](../alpi/tools/_paths.py) protects
  `config.yaml`, `.env` and skill `secrets/` and keeps `skills/` from members, but
  an unattended profile rewrote its own runner mid-run and broke the skill's tests;
  the only guard is a sentence in `AGENT.md`.
  promote when: a second unattended profile edits its own skill, or a fleet needs
  the guarantee enforced.
  accept: an opt-in profile setting under which `write_file`, `edit_file` and the
  skill tool's write actions refuse the profile's own `skills/`; off by default,
  inline skill updates unchanged.
- **KB.10** — Language policy for knowledge ingest and maintain
  `feature · alpi · agent · low`
  note: `_MAINTAIN_PROMPT` in [knowledge_base.py](../alpi/tools/knowledge_base.py)
  says nothing about language, so a synthesized page follows its source.
  promote when: a second profile needs a fixed knowledge language, or a profile
  goes back to the tool (instead of a skill gate) for curation.
  accept: a `knowledge.language` setting reaches the prompt and is checked on the
  proposal; unset keeps today's behaviour.
- **KB.12** — Vision in knowledge ingest
  `feature · alpi · agent · low`
  note: an image reaches `knowledge(action="ingest")` only with `ocr=true`, which
  loses what a diagram shows; `tools.read_image.model` is unused there.
  promote when: a second profile wants images kept as knowledge.
  accept: an ingested image produces a page that embeds it as an asset with a
  description from the configured vision model.
- **TIER.1** — Model tier per task, not only per job
  `feature · alpi · agent · low`
  note: a job's `tier` sets `ALPI_TIER` for its turn
  ([scheduler/run.py](../alpi/scheduler/run.py), read in `engine.py`); a chat turn
  always runs the main model, even for quality-sensitive knowledge writes.
  promote when: a second profile mixes cheap questions with quality-sensitive
  writes in chat.
  accept: a skill-level `tier` raises the rest of the turn once that skill runs.
- **ALP.ADMIT** — Admission that adapts to provider latency
  `feature · alpi · agent · low`
  note: ALP.9 (shipped) settled `alp.max_active_workgroups` as an admission threshold, not
  a cap; revisit on top of that contract.
  accept: admission drops to 1 while the per-call provider median exceeds a
  configured threshold and returns to the configured value when it recovers.
- **MOB.LIVE-ACTIVITY** — Live Activity and closed-app approval pushes
  `feature · mobile, alpi · agent · low`
  note: needs a remote push relay (APNs/FCM) the daemon does not have.
  accept: a running workgroup shows as a Live Activity, and an approval reaches
  the phone as a push with the app closed.
  the interface follows board UI-MOB.LIVE-ACTIVITY.

## Discarded — don't relitigate

| Decision | Reason |
|---|---|
| Vendor subscription OAuth | alpi respects every provider's ToS: a subscription tied to a vendor's own client is for that client, and reversing its private OAuth flow is a ToS violation and an account-ban risk. Users pay per token with their own keys; an official, documented third-party OAuth flow would be adopted. |
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
| True multi-root knowledge index | Partitioning the `knowledge.sqlite` tables by root is a large change for a use case nobody has; the single-root index names the one bundle it holds, refuses to be replaced by another, and `force=true` retargets deliberately. |
| Renaming the `okf_*` SQLite tables | Internal and never rendered; the rename runs the transactional drop and rebuild path, so the only bar left is an observable benefit and there is none. |
| Hard-rejecting page shrinks in `maintain` | Consolidating is legitimate; `maintain` reports `bytes_before`/`bytes_after` per written page instead of blocking. |
| Root-relative fallback in the knowledge link resolver | Would pass lint while breaking the links in Obsidian, GitHub and VS Code; page-relative stays canonical (KB.5). |
| Renaming the `type` frontmatter key | Invalidates every existing page over a Hugo layout-key collision that will likely never matter; the docs note the collision instead (KB.7). |
| Defining what "OKF" stands for | The acronym was coined without a referent; writing an expansion now would invent a retroactive justification. It is gone from every model- and user-facing string; only the `okf_*` table names keep it. |
| Longer-context embedder or smaller chunks (KB.15) | Measured on a 13.5K-chunk bundle with 81 queries: all-MiniLM-L6-v2's 128-token cut loses no answers because hybrid search (bm25 over the full chunk) finds the page and the agent reads the file; 12-line chunks cost +39% index size, bge-small 10x indexing CPU. |
