# alpi roadmap

Updated 2026-10-09. Current versions live in the changelogs. The Queue runs top to bottom; the creator
approves the next tasks from Proposed.

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

- **REDACT.1** — The URL-credentials pattern in `redact` is quadratic
  `bug · alpi · agent · high`
  note: found while reviewing RUN.1. `(?P<scheme>[a-zA-Z][a-zA-Z0-9+.-]*://)[^/\s:@]+:[^/\s@]+@` in
  [_redact.py](../alpi/_redact.py) takes 2.2 s on 50 KB of `a` and a 5 MB string did not finish in 120 s; `redact`
  runs on every journal event, saved turn and tool result, so one large alphanumeric output can stall a turn.
  accept: the scheme length is bounded; a test redacts 1 MB of `a` within a second and the URL, userinfo and
  credential cases still redact as before.

- **RES.1** — One `research` call has no cost cap of its own
  `bug · alpi · agent · high`
  note: [research.py](../alpi/tools/research.py) already limits each sub-agent to 8/15/30 iterations
  and a batch to three briefs. It checks the daily budget, but has no per-call monetary budget;
  reaching the daily cap returns an error before synthesis and can leave the main turn unable to answer.
  accept: a configurable per-call cap bounds the whole batch, shared across workers, with explicit
  headroom for synthesis and the parent answer. Exhaustion returns partial findings and a truncation
  note; no new provider calls start after exhaustion, and already in-flight calls have documented
  overshoot semantics. Fake-provider tests cover single and parallel calls, exhausted daily headroom
  and the parent still answering. Document the cap's default and takes-effect behavior in CONFIG and
  its knowledge reference; preserve the existing depth constants unless separately approved.

- **FRAME.1** — A lone surrogate in a live frame breaks the client's stream
  `bug · alpi · agent · normal`
  note: found while reviewing RUN.1. [host/server.py](../alpi/host/server.py) sends frames with
  `json.dumps(..., ensure_ascii=False)` followed by UTF-8 encoding directly on Unix or by the websocket library; a `tool_end` or
  `assistant` frame that carries tool output with an unpaired surrogate raises inside `send` (the Unix path logs
  `host unix connection crashed`). The same pattern appears in `outputs.py`, `run_ledger.py`, `admin_audit.py` and
  `workgroup.py`; whether each receives text derived from tool output is not traced.
  accept: a turn whose tool output holds a lone surrogate streams to a client and finishes, the frame carrying
  U+FFFD; each writer named above either scrubs or is shown not to receive tool text; tests drive the socket and
  the websocket.

- **SCOPE.5** — Profile session counts respect scope
  `bug · alpi · agent · normal`
  note: `counts.sessions` in `host.profile.summaries` counts every session file of the
  profile, so a member or a device-scoped device learns how many sessions other
  connections and sibling devices hold (a count only, no text).
  accept: the count includes only sessions `owns_session_row` lets the caller see; a
  test with sessions from two devices under `session_scope: device` counts one each.

- **ACT.2** — Jobs fired from the console never show as running
  `bug · alpi · agent · normal`
  note: found while reviewing ACT.1. `alpi schedule fire`, `alpi setup → Fire now` and the TUI's
  in-process `schedule(action="fire")` run `scheduled_run` in their own process, where the activity
  registry is off, so `host.activity.list` never lists the run and the apps never show it working.
  The apps' Fire button (`host.schedule.fire`) and cron fires are listed.
  accept: a job fired from the CLI or the TUI appears as a running row with its `job_id` while it
  runs (handed to the daemon when one answers); a test fires through the CLI path against a daemon.

- **WG.FLOW-LATENCY** — Remove the measured delay before pipeline state appears
  `bug · alpi, desktop, mobile · agent · normal`
  note: the clients already request tasks and transcript independently; the desktop bridge uses
  `off_main` and both daemon handlers use `asyncio.to_thread`. A fast isolated fold does not identify
  the source of the reported multi-second delay.
  accept: reproduce with a defined transcript size and local/remote connection, measure request,
  bridge/transport, handler and render time, then fix the measured bottleneck. A regression test
  reproduces that bottleneck and proves state can render while transcript loading is held pending;
  record before/after timings under the same conditions. Narrow the release products to the layers
  actually changed. Preserve the existing visual design and regenerate affected design views.

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

## In progress

_None._

## Needs creator

### Decisions

- **SCOPE.D1** — Does `session_scope: device` bind an admin connection?
  `decision · alpi · creator · high`
  note: found by the SCOPE.4 inventory. `can_read_session` and `can_handle_prompt` return
  true for `role == admin`, and the member-only event filters never run for an admin, so a
  remote admin device with `session_scope: device` sees device A's sessions through
  `session_search`, `session_read`, `recall_sessions`, `host.activity.list`, prompts and
  every event, while `host.sessions.*`, `host.chat.*` and `host.runs.*` hide them. Today the
  scope is a partition for admins, not a privacy boundary.
  accept: decide whether remote admins are bound for session text, and whether that applies
  within their connection or across connections. Create a separate agent task for consistent
  enforcement, documentation and matrix tests; preserve the local socket owner semantics.
  Member-only isolation fixes in Queue do not wait on this decision.

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
  `decision · desktop · creator · low`
  note: `BootSplash` in [desktop/src/primitives](../desktop/src/primitives/) is exported but nothing renders
  it; startup shows only the connecting banner. Decide where a splash belongs (first paint before the
  daemon answers) before drawing the alpaca beside the crease "alpi" there.
  accept: decide whether a splash belongs before first connection; if yes, approve its board
  and create the implementation task.

### Builds and deployments

- **OPS-CRED-SWEEP** — Credential hygiene on every daemon
  `deploy · alpi · creator · normal`
  accept: the credential hygiene checklist in the creator's operations runbook
  has been run on every deployed daemon and `alpi doctor` reports no credential
  findings on each.

## Proposed

### Requires a design board

- **CHART.1** — The mobile Usage chart follows the cost too
  `feature · desktop, mobile, common · agent · normal`
  note: found while reviewing UX.8. Desktop sizes bars by dollars when any day cost something, with the
  input/output split drawn inside each bar (the creator confirmed this design), but
  [UsageChart.jsx](../mobile/src/components/UsageChart.jsx) still scales by tokens through `usageScale` in
  [usage.mjs](../common/usage.mjs), so one profile draws a different tallest bar on each client. The split is
  price-weighted from fixed constants because the ledger keeps one cost per day.
  accept: `byCost` and `sizeOf` live in `common/usage.mjs` and both clients use them; mobile gets the same
  thin-bar minimum, split and a "bars by" footer; a window with no cost on any day (a local model) sizes bars by
  total tokens; a component test renders a mixed window and a free window on each client.
  The interface follows board UI-CHART.1, matching the existing desktop cost-based chart;
  draw and approve that board before moving this task to Queue.

### Demand-gated

Each names the condition that promotes it; none is worked on before.

- **OUT.OWN** — A member rereads and edits its own earlier outputs
  `feature · alpi · agent · low`
  note: since SCOPE.12 a fenced turn (member device, peer without `tools.allow`) reaches `out/` only for files it creates in that turn or its skill produces; the next turn cannot reread, edit or attach them, because `out/` carries no owner and the only ownership records are the sessions' offered paths, which cost a session scan per file check.
  promote when: members ask the agent to revise or resend a document it made for them earlier.
  accept: a fenced turn reads, edits and attaches the files its own connection produced in earlier turns (its device too under `session_scope: device`) and still none another connection produced; no new persisted state beyond what ownership needs, named in the change; tests cover two connections on one profile.

- **WG.ORIGIN-WIRE** — A post that arrives over the wire without a claim counts as admin's
  `bug · alpi · agent · normal`
  note: SCOPE.11 stamps the fence of every post a caller on this daemon makes and lets another daemon's profile claim one, but a peer that posts to the hub directly (not through a turn here) carries no claim, and the hub cannot verify what authority that profile's turn ran under. Its post wakes turns as admin. The same claim lets any member of a workgroup degrade the turns its post wakes: a `peer` claim takes `terminal` away from a pipeline owner, and an empty `allow` leaves only `workgroup_post`.
  promote when: a hub takes posts from profiles on daemons the creator does not run, or the creator asks for it.
  accept: the hub derives the origin of a wire post from the posting peer's record (`tools.allow` absent means fenced) instead of trusting the claim alone, with a per-member way to trust a profile fully so local multi-profile pipelines keep working; tests cover a local trusted member, an untrusted one and a forged claim.

- **ALP.READ** — Fenced turns read every workgroup transcript under `alp/`
  `bug · alpi · agent · low`
  note: the member fence leaves `alp/` readable (peer mentions, workgroup transcripts) except `alp/secrets`, so a fenced turn reads the decrypted posts cached in `alp/subscriptions.yaml` and the transcripts of every workgroup of the profile, not only the one it serves.
  promote when: a profile is in workgroups that members or untrusted peers of one must not see.
  accept: a fenced turn reads `alp/` only for the workgroup its turn serves, or none; tests cover a second workgroup's transcript and the subscriptions file.

- **POL.2** — A member connection can carry the tool policy a peer carries
  `feature · alpi · agent · low`
  note: a member device runs and invokes the profile's skills since v0.17.1 and is otherwise fenced; an ALP peer can already carry `tools.allow` (names, `*` patterns, `tool:action`) that replaces the fence with an exact list, but a member connection cannot. A profile that untrusted members drive has no way to open one skill and close another.
  promote when: a profile is driven by members who are not trusted with every mode of its skills.
  accept: a connection record takes the same `tools.allow` grammar as a peer and replaces the member fence with exactly that list, nested execution included; a connection without it behaves as today; the setting is in the takes-effect table of [CONFIG.md](CONFIG.md) and next to the member fence in [SECURITY.md](SECURITY.md); tests drive a member through a granted and an ungranted tool.

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
  ([scheduler/run.py](../alpi/scheduler/run.py), read in `engine.py`); chat has no skill-declared
  tier, even for quality-sensitive knowledge writes; the engine already has a separate automatic
  escalation path.
  promote when: a second profile mixes cheap questions with quality-sensitive
  writes in chat.
  accept: a skill-level `tier` raises the rest of the turn once that skill runs.

- **ALP.ADMIT** — Admission that adapts to provider latency
  `feature · alpi · agent · low`
  note: ALP.9 (shipped) settled `alp.max_active_workgroups` as an admission threshold, not
  a cap; revisit on top of that contract.
  promote when: measured provider saturation repeatedly delays useful workgroup progress and
  a fixed admission threshold is insufficient.
  accept: admission drops to 1 while the per-call provider median exceeds a
  configured threshold and returns to the configured value when it recovers.

## Discarded — don't relitigate

| Decision | Reason |
|---|---|
| Vendor subscription OAuth | alpi respects every provider's ToS: a subscription tied to a vendor's own client is for that client, and reversing its private OAuth flow is a ToS violation and an account-ban risk. Users pay per token with their own keys; an official, documented third-party OAuth flow would be adopted. |
| Remote push to a closed phone (Live Activity, approval pushes; MOB.LIVE-ACTIVITY) | alpi puts no relay or third-party service between a daemon and its apps. APNs and FCM only take messages signed with the app's own keys, so reaching a closed phone needs a relay (Expo's push service or one the creator runs) between every daemon and every phone. The phone hears from its daemons through its own stream and poll, while the app runs and when the OS wakes it. |
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
