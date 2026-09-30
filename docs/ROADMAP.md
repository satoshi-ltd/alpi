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
- **type** — `bug`, `feature`, `chore`, `verify` (evidence from a real device or
  environment), `deploy` (build, install or roll out outside the repository) or
  `decision`.
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

Every agent task also meets these, on top of its `accept`: a regression test that
fails before the fix; the relevant `pytest --integration` tests run for the exact
release SHA (`publish.yml` runs only `pytest -q`); no new runtime dependency, RPC
framework or persisted state unless the task names it; a large file is not a
defect, so a helper is extracted only when it removes evidenced duplication.

## Queue

- **SCOPE.4** — Device-scope privacy matrix
  `chore · alpi · agent · high`
  accept: one parametrised test writes as device A and then reads as device B through
  every host verb, tool and event path that returns session text (summaries, session
  read/list, search, recall, activity, events), under `session_scope: device`, and
  asserts B sees none of A's text; adding a new path means adding it to the matrix.
- **ACT.1** — Activity keeps pipelines a scoped caller can see
  `bug · alpi · agent · normal`
  note: [activity.py](../alpi/host/activity.py) dedupes a workgroup's rows preferring
  the hub before the server's profile-scope filter runs, so a caller scoped to a
  member profile loses the pipeline entirely.
  accept: dedupe happens among the rows the caller is allowed to see; a test with hub
  and member rows for one workgroup and a caller scoped to the member gets one row
  for the member profile.
- **SPAN.1** — A retried attempt leaves no reasoning span behind
  `bug · alpi · agent · normal`
  note: `_ReasoningSpans.discard_text()` in [engine.py](../alpi/engine.py) clears the
  open span but not spans the discarded attempt already closed by emitting text
  (reachable on replay-visible retries and the workgroup fallback).
  accept: spans are truncated to the attempt's start on `retry_reset` and on
  fallback; a test streams reasoning A, text, `retry_reset`, reasoning B, answer and
  the stored spans hold only B, matching `turn.reasoning`.
- **MEM.3** — Memory edits keep combining marks with their letter
  `bug · alpi · agent · normal`
  note: replacing a decomposed `Cafe\u0301` in [memory.py](../alpi/tools/memory.py)
  leaves the combining accent behind (`Teá`) on AGENT.md edits and inside multi-line
  entries.
  accept: a match extends past trailing combining marks (or text is compared in NFC);
  replace and remove tests with a decomposed accent produce the exact expected text.
- **MOB.ACT-REDETECT** — Activity comes back after a daemon upgrade
  `bug · mobile · agent · normal`
  note: a `-32601` from `host.activity.list` sets `supported=false` in
  [useActivity.js](../mobile/src/hooks/useActivity.js) for good; foreground and
  `activity.changed` never ask again.
  accept: the negative result resets on stream reconnect and on foreground; a test
  rejects with `-32601`, then resolves, triggers foreground and sees Activity
  supported; the tests that encode the permanent stop change accordingly.
- **MOB.REFRESH-ERR** — A failed refresh over stale data says so
  `bug · mobile · agent · low`
  note: `refresh()` in [useDaemonData.js](../mobile/src/hooks/useDaemonData.js)
  resolves `null` on failure, so the pull-to-refresh "Refresh failed" toast never
  fires for screens that already show data.
  accept: `refresh()` rejects (fire-and-forget callers handle it), and a
  pull-to-refresh test on a screen with data and a failing call shows the toast.

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

- **KB.11 + KB.13** — Ingest reports its cut and keeps Word tables (one commit)
  `bug · alpi · agent · high`
  note: [knowledge_base.py](../alpi/tools/knowledge_base.py) sends
  `source_text[:12000]` with no truncation metadata; the shared Word reader in
  [workspace.py](../alpi/tools/workspace.py) reads `doc.paragraphs` only, so a
  DOCX table is lost (reproduced locally).
  accept: the source budget stays; sources below, at and above it report
  truncated/available/used counts in preview and apply results, and the
  synthesizer prompt says so too. A paragraph/table/paragraph DOCX keeps its text
  in order through the shared reader and the ingest path, with explicit handling
  of empty and merged cells, using the existing `python-docx` (no new library, no
  chunked synthesis, vision or translation). Regressions cover the reader's other
  consumers and the existing protection of truncated related pages against
  overwrite.

- **UX.7** — The desktop Storage field is one inventory
  `feature · desktop · agent · normal`
  note: [maintenance.jsx](../desktop/src/features/settings/fields/maintenance.jsx)
  renders a usage row per `STORAGE_GROUPS` entry, then a `reclaim` row, then a
  `delete` row per destructive `host.cleanup.plan` member (up to thirteen rows,
  five labelled `DELETE`), re-counting bytes already shown. Plan members carry
  their group (`GROUP_OF` in [cleanup.py](../alpi/cleanup.py)) and the component
  already builds `planByGroup`.
  accept: desktop rendering only; `host.profile.storage`, `host.cleanup.plan`,
  `host.cleanup.apply`, console and mobile untouched. Each group row keeps size
  and file count and carries its own actions: one **Clean** chip totalling its
  safe members and one confirmed **Delete** chip per destructive member, named
  after the target. The standalone reclaim/delete rows go (at most one **Clean
  everything safe** summary line); no "always safe" prose. With every category
  populated the field renders no more rows than non-empty groups plus one, no two
  rows share a label, per-row amounts sum to the sweep total, destructive actions
  still open `ConfirmDelete`, `canClean` is unchanged. `maintenance.test.jsx`
  covers a mixed group (Logs shows Clean plus Delete run journals; Conversations
  shows three named Deletes and no Clean; Files shows Clean plus Delete generated
  files); both client suites pass; the changelog entry pins no new alpi minimum.

- **KB.14** — Unchanged content is not embedded again
  `bug · alpi · agent · normal`
  note: [knowledge_base.py](../alpi/tools/knowledge_base.py) skips a file by mtime
  and size, so a metadata-only change pays for another embedding.
  accept: a content fingerprint covering everything that shapes the indexed page
  decides the skip; embedder change and explicit force keep their rebuild
  contract; single-root store and transactional rebuild stay. With a counting
  embedder and real SQLite: a touched unchanged page does not call the embedder;
  changed text with the same size and restored mtime is re-embedded; metadata
  changes update the index; an index without the fingerprint stays usable and
  gains it on indexing without dropping unrelated tables; a failure still rolls
  back the pass. Schema work is limited to that field.

- **ATT.2** — `host.attachments.fetch` scoped to the owning device
  `bug · alpi · agent · high`
  note: `_fetch` in [attachments_rpc.py](../alpi/host/attachments_rpc.py) checks
  `servable_roots` and the secrets denylist, never the caller, so any device of a
  `session_scope: device` connection can download another user's produced file by
  path.
  accept: for a remote caller on a `session_scope: device` connection, a path is
  served only if it appears in a session the device owns (`owns_session`) as a
  turn's `attachments`, `output_attachments`, tool result or assistant text, or if
  the device staged it (`_stage` records the `device_id` beside the file). A
  per-device index of offered paths is updated on session save and rebuilt
  lazily, never a transcript rescan per call. Roots and denylist stay the first
  barrier; a refusal returns the existing `-32001 forbidden` / `path not
  readable`. Over real WebSockets with two devices of one connection: A fetches
  its `out/report.md`, B gets `forbidden` for it and for A's staged upload; under
  `session_scope: connection` both fetch it; an image an assistant turn
  referenced stays fetchable for the session's device; sessions with no
  `device_id` stay fetchable for the whole connection; admin and the Unix socket
  are unaffected.

- **AUTH.1** — Auth-failure throttle per device, not per shared address
  `bug · alpi · agent · normal`
  note: `_handle_websocket` in [server.py](../alpi/host/server.py) closes a source
  with 1013 after `WS_AUTH_FAILURES_PER_MINUTE` (10); a multi-user front end
  reaches alpi from one address, so one revoked device retrying locks every user
  out. `authenticate` in [connections.py](../alpi/host/connections.py) skips
  devices with `status != "active"` and returns an anonymous failure.
  accept: `authenticate` matches revoked devices and returns
  `reason="device-revoked"` with the `device_id` (still a failure, logged in the
  audit trail); failures that name a device count against that device with the
  same limit and window and close it with `auth-rate-limited` without spending
  the address budget; anonymous failures stay per address;
  `ALPI_HOST_WS_TRUSTED_PROXIES` unchanged. Over real WebSockets from one address:
  a revoked device retried 30 times in a minute is throttled while a second valid
  device keeps connecting; ten unknown tokens still close the address;
  `token-expired` and `connection-disabled` count per device; the client still
  gets `auth-failed` with the existing reasons plus `device-revoked`.

- **UPD.1** — Clients know before the click whether a daemon can self-update
  `bug · alpi, common, desktop, mobile · agent · normal`
  note: `_detect_installer()` in [updater.py](../alpi/updater.py) returns `uv`/`pipx`
  or `dev`; a Docker image (`pip install .` as root, daemon as uid 1000) always
  lands on `dev` → `reason: "manual"`, while `host.version`
  ([device_state.py](../alpi/host/device_state.py)) advertises `update_available`
  and desktop shows **Update alpi**. The hint `docker compose pull` is wrong for a
  pinned tag; desktop [DaemonField.jsx](../desktop/src/features/settings/fields/DaemonField.jsx),
  mobile [daemonUpdate.js](../mobile/src/features/settings/daemonUpdate.js) and
  [ConnectionSheet.jsx](../mobile/src/features/sheets/ConnectionSheet.jsx) carry
  three texts; the comment in `_daemon_update` wrongly implies an in-container
  upgrade.
  accept: the updater names the install kind `uv | pipx | docker | source`
  (`docker` from `ALPI_PLATFORM`) and `host.version` adds `installer` and
  `self_update: bool`. A Docker daemon reports `self_update: false`,
  `installer: docker`; desktop and mobile hide the button and the badge tooltip
  shows one shared `common/` step with the latest version filled in ("set the
  image tag to `X.Y.Z` in docker-compose.yml, then `docker compose up -d`";
  `source`: "git pull and restart the daemon"); `alpi update` prints the same
  text. uv/pipx keep the one-click flow; a daemon without `self_update` keeps
  today's behaviour. Updater tests stub environment and subprocess per kind; both
  client suites cover the one hint string. No in-container upgrade, no compose
  editing.

- **UX.8** — Usage bars by cost when the profile pays
  `feature · desktop · agent · normal`
  note: [Usage.jsx](../desktop/src/features/settings/Usage.jsx) sizes bars by
  tokens (`maxTok`) while the headline and the daily cap are dollars; with prompt
  caching they diverge. [ledger.py](../alpi/ledger.py) already keeps both per day.
  accept: a window with any cost draws bars proportional to dollars and the
  tooltip shows both numbers; an all-free window draws tokens as today; no new
  verb; a component test renders a mixed window; both client suites pass; the
  changelog entry pins no new alpi minimum.

- **SCHED.6** — Each fired job is stamped when it finishes
  `bug · alpi · agent · normal`
  note: `tick` in [scheduler/run.py](../alpi/scheduler/run.py) writes
  `last_run_at` / `last_run_status` for every fired job in one
  `jobs_store.update` after the pass, with the pass's start time; a fire may now
  run up to 86400 s, so a restart mid-pass fires finished jobs again.
  accept: each job is stamped right after its `run_job` returns, with the same
  update rules (first-seen, one-shot removal on success, stamp on failure); the
  pass stays serial with no new state. With two due jobs and the second still
  running, the first is already stamped in `jobs.json`; a simulated restart after
  the first does not fire it again; one-shot and failure semantics unchanged.

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

- **OPS-CONN-POLICY** — Connection policy for the fleet
  `decision · alpi · creator · normal`
  accept: a written connection policy (one connection per person with an exact
  `profile_scope`, one device per physical device, the old row revoked on
  re-pairing, a profile's tools reviewed before granting scope) is confirmed and
  applied to every deployed daemon; any code it needs becomes an agent task.

## Proposed

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
- **WG.STATUS** — Compound workgroup list status
  `feature · alpi, desktop · agent · low`
  note: one observation only, cosmetic.
  accept: the workgroup list shows a compound status ("setup done · media queued
  #N") instead of `queued` hiding `completed`, in the CLI and desktop.
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
