# alpi roadmap

Updated 2026-10-06. Current versions live in the changelogs. v0.17 takes the tasks in Queue (the
workgroup and profile boards); the rest of the pool targets v0.18.

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

_None._

## In progress

_None._

## Needs creator

### Builds and deployments

- **BUILD-MOBILE** — EAS build of mobile 0.7.0
  `deploy · mobile · creator · high`
  accept: an EAS build of mobile 0.7.0 or later installed on the Fold and on an
  iPhone.
- **OPS-CRED-SWEEP** — Credential hygiene on every daemon
  `deploy · alpi · creator · normal`
  accept: the credential hygiene checklist in the creator's operations runbook
  has been run on every deployed daemon and `alpi doctor` reports no credential
  findings on each.

### Device checks

- **VERIFY-MOBILE-070** — Mobile 0.7.0 on device
  `verify · mobile · creator · high · depends: BUILD-MOBILE`
  accept: on device, the process block sits at 12 pt flush with the answer; the
  Fold sidebar slides; expand/collapse and the Latest button animate; a long
  press pulses only after 350 ms and a tap never moves a bubble; the notification
  count shows its number at large text sizes; approval notification actions
  answer on the right connection from a cold start. Pairing from a fresh install:
  Scan QR opens the camera at once, a reachable host walks the three steps to
  Paired with its name and role, Open inbox leaves no way Back to onboarding, an
  unreachable host keeps the link with Try again, a used link is cleared; with the
  daemon stopped the header goes offline and the roster unfolds within seconds,
  and comes back on its own; a member with nothing shared sees whom to ask.

- **VERIFY-DESKTOP-FIRSTRUN** — Desktop 0.8.0 first run on a Mac
  `verify · desktop · creator · high`
  accept: on a Mac without alpi, the window opens on Set up alpi with the install
  commands and the link field, and installing alpi and pressing Check again lands
  on the roster with the one-time phone card; with alpi installed and stopped, it
  starts on its own (Starting alpi…) and lands on the roster; a broken config shows
  alpi didn't start with the log tail, the command and Retry; stopping the daemon
  mid-session keeps the open view under the banner and Retry starts it again;
  connecting with a used link names the failure and clears the field.

- **VERIFY-DESK-DICTATION** — Dictation in the composer on a Mac
  `verify · desktop · creator · high`
  accept: on a Mac with desktop 0.8.3 or later (the composer holds its auto-size and mention work while text is composed; if Dictation still closes at once, the cause is elsewhere and this becomes a bug), the Dictation shortcut set in System Settings
  › Keyboard › Dictation (pressing 🌐 twice by default; a further press ends it, as in every app) opens
  Dictation in the composer and it stays open while you speak, the words land in the field, and the same
  holds while a reply streams and in a workgroup's composer.

- **VERIFY-BRAND-GLYPHS** — One-cell glyphs in the terminals alpi supports
  `verify · alpi · creator · low · `
  accept: the twelve one-cell glyphs of the console (⌂ ♥ ➤ ⬟ ⌃ ★ ♣ ▣ ♛ ✒ ☼ and the diamond) were
  seen in Terminal, iTerm2 and one Linux terminal; any that fails is replaced or falls back to the
  diamond.

- **VERIFY-BRAND-ICONS** — The new icons on a Mac, an iPhone and an Android
  `verify · desktop, mobile · creator · low`
  accept: the Tauri app's dock and window icon, an EAS iOS build in light, dark and tinted home
  screens, and an Android build with the adaptive mask all show the flat ink alpaca without clipping,
  and the splash and adaptive background are neutral grey (no blue tint) in light and dark.

- **VERIFY-NOTIF-PHONE** — Notifications on the phone, on device
  `verify · mobile · creator · normal`
  accept: on an iPhone and an Android build, a row swipes left to Unread/Read and Delete and back; the
  Undo toast after a delete leaves the list scrollable and tappable and Back working for its 5 s (it is
  a transparent Modal: if it blocks touches, the toast becomes an overlay); up and down on a
  notification page step through the list across connections; Reply opens a new session with the
  quote in the composer; large text keeps rows and the bottom bar readable, on the phone and the Fold.

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
- **BRAND.D1** — Brand choices still open
  `decision · alpi · creator · normal`
  note: decided by the creator: the brand accent is ink (cream on dark, black on light); the alpaca is
  one flat ink and only its name carries tones (T3 crease); objects are established origami models (the
  gate); object and colour are two stored values and every new profile takes the next pair of the roulette; the honeycomb
  marks a workgroup; the default profile is the alpaca. Still open, none blocking: the unit's name
  ("profile", with "fold" only the look); whether the box stays or becomes a paper hat.
  accept: a written answer to each; a different answer becomes an edit to the task it touches
  before that task ships.

## Proposed

- **WG.FLOW-LATENCY** — The pipeline strip appears as soon as a workgroup opens
  `bug · desktop, mobile · agent · normal`
  note: opening a pipeline workgroup shows "Loading flow…" for seconds, yet `fold_task_state` takes about 5 ms
  on a 37-post transcript in process (decrypt plus fold, cold). The wait is elsewhere: the three calls the view
  fires at once (`workgroup_members`, `workgroup_tasks`, the transcript), the Tauri bridge and its socket, or a
  busy daemon loop. Board UI-LOADING covers drawing the chain before the run arrives; this task is the latency.
  accept: a measurement of each hop (client call, bridge, socket, handler) on a pipeline workgroup names where the
  time goes; the fix brings the run state on screen without waiting for the transcript, and a test proves
  `workgroup_tasks` is not queued behind it.

- **BRAND.EMPTY** — A blank chat that introduces the profile
  `decision · desktop, mobile · creator · normal`
  note: today an empty chat is the profile's origami at 72 px, "Start a new thread" and the model. Ideas to
  weigh with the copy pass: the profile's own one-line bio under the origami, the pair name ("blue shield")
  beside the model as the Brand board shows, up to three starter chips drawn from the profile's skills or
  its recent sessions (one tap fills the composer), and a short fold-in of the origami on first paint that
  stops under reduced motion. Needs a board before any code, and the copy of every empty state decided together.
  accept: the creator picks which of these ideas ship and the copy of the empty states; the answer becomes a
  `ui` task with its board.

- **BRAND.SPLASH** — Mount the boot splash with the crease wordmark
  `feature · desktop · creator · low`
  note: `BootSplash` in [desktop/src/primitives](../desktop/src/primitives/) is exported but nothing renders
  it; startup shows only the connecting banner. Decide where a splash belongs (first paint before the
  daemon answers) before drawing the alpaca beside the crease "alpi" there.

- **TERM.3** — Profile environment for `terminal`
  `feature · alpi · agent · low`
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
- **REDACT.1** — The URL-credentials pattern in `redact` is quadratic
  `bug · alpi · agent · normal`
  note: found while reviewing RUN.1. `(?P<scheme>[a-zA-Z][a-zA-Z0-9+.-]*://)[^/\s:@]+:[^/\s@]+@` in
  [_redact.py](../alpi/_redact.py) takes 2.2 s on 50 KB of `a` and a 5 MB string did not finish in 120 s; `redact`
  runs on every journal event, saved turn and tool result, so one large alphanumeric output can stall a turn.
  accept: the scheme length is bounded; a test redacts 1 MB of `a` within a second and the URL, userinfo and
  credential cases still redact as before.
- **FRAME.1** — A lone surrogate in a live frame breaks the client's stream
  `bug · alpi · agent · low`
  note: found while reviewing RUN.1. [host/server.py](../alpi/host/server.py) sends frames with
  `json.dumps(..., ensure_ascii=False).encode("utf-8")` on the Unix socket and the websocket; a `tool_end` or
  `assistant` frame that carries tool output with an unpaired surrogate raises inside `send` (the Unix path logs
  `host unix connection crashed`). The same pattern appears in `outputs.py`, `run_ledger.py`, `admin_audit.py` and
  `workgroup.py`; whether each receives text derived from tool output is not traced.
  accept: a turn whose tool output holds a lone surrogate streams to a client and finishes, the frame carrying
  U+FFFD; each writer named above either scrubs or is shown not to receive tool text; tests drive the socket and
  the websocket.
- **ACT.2** — Jobs fired from the console never show as running
  `bug · alpi · agent · low`
  note: found while reviewing ACT.1. `alpi schedule fire`, `alpi setup → Fire now` and the TUI's
  in-process `schedule(action="fire")` run `scheduled_run` in their own process, where the activity
  registry is off, so `host.activity.list` never lists the run and the apps never show it working.
  The apps' Fire button (`host.schedule.fire`) and cron fires are listed.
  accept: a job fired from the CLI or the TUI appears as a running row with its `job_id` while it
  runs (handed to the daemon when one answers); a test fires through the CLI path against a daemon.
- **SCOPE.12** — The `db` tool and `out/` sit outside the member fence
  `bug · alpi · agent · low`
  note: found while reviewing SCOPE.8. The `db` tool runs arbitrary SQL on any skill's `state/db.sqlite`,
  around the `skills/` file fence and the rule that fenced turns change no skill, and the fenced file tools
  still read `<home>/out/`, where every session's produced files land.
  accept: a fenced turn (member device or peer without `tools.allow`) gets only read queries on the active
  skill's database, or none, and cannot read another connection's files under `out/`; tests cover both.
- **POL.2** — A member connection can carry the tool policy a peer carries
  `feature · alpi · agent · low`
  note: a member device runs and invokes the profile's skills since v0.17.1 and is otherwise fenced; an ALP peer can already carry `tools.allow` (names, `*` patterns, `tool:action`) that replaces the fence with an exact list, but a member connection cannot. A profile that untrusted members drive has no way to open one skill and close another.
  promote when: a profile is driven by members who are not trusted with every mode of its skills.
  accept: a connection record takes the same `tools.allow` grammar as a peer and replaces the member fence with exactly that list, nested execution included; a connection without it behaves as today; the setting is in the takes-effect table of [CONFIG.md](CONFIG.md) and next to the member fence in [SECURITY.md](SECURITY.md); tests drive a member through a granted and an ungranted tool.
- **RES.1** — One `research` call has no cost cap of its own
  `bug · alpi · agent · normal`
  note: [research.py](../alpi/tools/research.py) fans a brief into sub-agents that search and fetch on their own. On casa on 2026-09-29 two calls of a biography profile spent $2.35 and $2.74 and ended at the daily budget ($2.00, then $5.00) without an answer: the budget stops the turn after the damage, and the next message of the day failed too. Nothing bounds one call's spend, the number of sub-agents' steps or the retries on dead URLs (DNS failures).
  accept: a `research` call stops at a configurable fraction of the remaining daily budget (or a fixed amount) and returns what it has with a note saying it was cut; the cap and the sub-agent step limit are in the takes-effect table of [CONFIG.md](CONFIG.md); a test with a fake provider that spends past the cap shows the call ending early and the turn still answering.
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
- **ATT.3** — `host.attachments.fetch` ignores the caller's connection
  `bug · alpi · agent · low`
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

- **SCOPE.11** — Turns a workgroup post wakes run unfenced
  `bug · alpi · agent · low`
  note: found while reviewing SCOPE.9. `_dispatch_workgroup_turn` in [service.py](../alpi/service.py) runs a
  `chat --once` child as the profile (admin) for every member or hub turn a post wakes; the session history
  tools are denied there since v0.17.0, but `read_file`, `search` and `terminal` still read `sessions/`,
  `runs/` and `host/`, so a member device or a peer without `tools.allow` driving any profile of the
  workgroup can `workgroup_post` a request for another conversation and get it posted back.
  promote when: a profile that member devices or peers without `tools.allow` drive joins a workgroup.
  accept: a turn woken by a post whose author is a member device or a peer without `tools.allow` gets the
  member fence (file tools and `search` out of the private areas, `terminal` only in Linux bubblewrap and
  refused elsewhere, no skill scripts or skill/memory/job changes); a test posts as a member asking for
  another session's text and the turn gets none of it; a pipeline of local profiles with admin posts keeps
  terminal and skill scripts.
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
