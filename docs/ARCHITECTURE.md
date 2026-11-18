# Architecture

Living technical reference for alpi at HEAD. Describes only what currently
ships — historical decisions live in commit messages, planned work lives
in [ROADMAP.md](ROADMAP.md).

Audience: any developer (or LLM) reading this codebase from cold.

## What alpi is

alpi is a local-first personal AI agent. It has a Textual TUI in the
terminal, a Tauri desktop app and an Expo mobile app that
talk to the daemon over the host plane (Unix socket locally,
WebSocket remotely), an on-demand `email` tool (IMAP / Gmail) the
agent calls to read and send mail,
inline-learning memory, scanner-gated live skills, multi-provider LLM
support via LiteLLM, read-only research, write-capable delegation,
scheduling, MCP integration, and ALP for private agent-to-agent links.

The architectural constraint is sovereignty: state is local, identities
are per-profile, network trust is explicit, and operational surfaces
stay small enough to audit. The product is intentionally not a generic
agent suite, marketplace, or hosted router.

## Principles

alpi is published by [Satoshi Ltd.](https://www.satoshi-ltd.com/)
and inherits the company's six operating principles (Privacy by
Design, User Sovereignty, Security First, Open Source, Zero
Knowledge, Digital Sovereignty). See **Why alpi exists** in
`README.md` for the mapping between principle and code. The conventions below are the engineering expression of those
principles — not separate from them.

- **Focused.** Every feature earns its keep. No over-engineering. Maps to Satoshi's "constraint breeds coherence" heuristic.
- **Solid base.** Core loop, memory, tools, paths, scanner before surface features.
- **User in control.** No destructive action without explicit OK. No silent migrations. Expression of **User Sovereignty**.
- **Python stack.** No Go rewrite (loses LiteLLM, tests, no upside).
- **No legacy code.** When a schema or layout changes, it's a clean break — no compat shims, no auto-migration. Anything from yesterday's iteration is cleaned by hand, not by `ensure_home`.
- **Closed protocol, own transport.** ALP is not A2A / MCP-over-network / gRPC. Every verb we don't ship is an attack surface we don't own. Expression of **Privacy by Design** + **Security First**.

## Code conventions

Contributor rules — no human-facing comments inside `alpi/`, English only,
every comment must carry a "why" — live in `AGENTS.md` at the repo root.

## CLI surface

Stable verbs shared across groups so a user doesn't relearn per feature.

```
alpi                           launch the TUI
alpi -c / --continue           resume the last session in the TUI
alpi -p <name>                 profile flag, combinable with any command

alpi chat                      alias for `alpi`
alpi chat --once "<text>"      one-shot turn to stdout (pipe-friendly)
alpi chat --once ... -c | --session <id>   continue the last / a specific session (one-shot)
alpi chat --once ... --connection-id <id>  local-only delegated turn visible live to that connection
alpi chat --once ... --emit-events     INTERNAL — scheduler subprocess contract
alpi chat --once ... --no-save         INTERNAL — do not write a session file

alpi setup                     interactive menu: model / email / voice / MCPs /
                               peers / workgroups / sandbox / service /
                               health check / cleanup /
                               delete profile (non-default only)

alpi doctor                    live health check (IMAP login,
                               Gmail token refresh, MCP handshake, service PID);
                               exits 1 on any failure, 0 otherwise

alpi audit                     whole-install security posture scan
alpi audit-log                 bounded administrative activity by device

alpi logs                      tail every subsystem log merged by timestamp
  --source {service|schedule|agent|approval}  restrict to one subsystem
  -n N                                         last N lines (default 100)
  -f                                           follow mode (poll every 1s)

alpi profile list              list profiles, mark the active one with its shape glyph
alpi profile show [name]       draw the profile's object as half-block art with its model and path
alpi profile create <name>     bootstrap a new profile tree
alpi profile remove <name>     delete after safety checks + confirm

alpi daemon install|uninstall                  register / unregister the service unit
alpi daemon start|stop|restart|status          lifecycle of the single per-machine daemon
alpi schedule run-once|fire <id>               manual cron tick / ad-hoc job fire

alpi peers list                list pinned ALP peers for this profile
alpi peers key                 print this profile's ALP public key
alpi peers add <id> <pubkey>   pin a peer (prefer the wizard for capability selection)
alpi peers remove <id>         unpin a peer
alpi peers tools <id> [--allow …|--clear]  show or set the only tools an inbound turn from that peer may run
alpi peers ping <id>           live probe via link.ping

alpi workgroup list                                list workgroups (hub-of + member-of)
alpi workgroup show <wg_id>                        detail + decrypted transcript
alpi workgroup create <name> --member <id>         hub-side create, granting the invited peers
alpi workgroup join <hub_peer_id> <wg_id>          subscribe to a peer-hosted workgroup
alpi workgroup post <wg_id> <text>                 encrypt + post, declaring the turn's cost
alpi workgroup pull <wg_id>                        fetch new posts and decrypt; cursor advances
alpi workgroup pause|resume|leave <wg_id>          membership ops
alpi workgroup kick <wg_id> <member-id|pubkey>     hub-only; rotates the group key
```

**Shape rules:** containers (profile, peers, workgroups) get `list/create/remove` (or `add/remove`). The daemon gets `start/stop/restart/status/install/uninstall` under `alpi daemon`; the same lifecycle is also reachable from `alpi setup → Services → Daemon` (default profile only) so users have one canonical place. The first `alpi setup` auto-installs the daemon — no opt-in step. Scheduler, ALP, workgroups, and host are fixed daemon capabilities; their useful controls live with jobs, peers/workgroups, connections, and network settings. Interactive wizards live exclusively under `alpi setup`; never add a per-feature wizard command.

**Command ordering** in `--help` is frequency-first, not alphabetical: `chat → setup → doctor → logs → profile → peers → workgroup → schedule → daemon`. See `_OrderedGroup` in `cli.py`.

**`alpi/ui.py`** is the shared interactive layer. Raw `questionary.*` is forbidden outside it. Helpers: `banner`, `menu`, `text`, `password`, `confirm`, `row`, `ok/fail/warn/dim/saved/cancelled`. The close item is added automatically with value `None` (callers treat `None` as "out").

**Menu close wording**: top-level (`alpi setup`) → `Exit`. Sub-menus (`Email:`, `MCP servers:`, `Manage saved keys`) → `← Back`. Wizard aborted mid-flow → `cancelled`. Mixing `Exit/Back/Cancel` in one context is a bug.

## File layout

```
alpi/
├── __init__.py             __version__
├── cli.py                  entry point, --continue, --profile resolution
├── engine.py               turn runner, interrupt flag, tool loop
├── llm.py                  litellm stream() / complete() wrappers
├── session.py              Turn / ToolLog dataclasses, save/load
├── prefix_diag.py          hashed conversation affinity + request-shape diagnostics
├── memory.py               MemoryStore (3 files, two-tier dedup, .bak)
├── home.py                 profile path resolution
├── config.py               YAML load/save, defaults, deep merge
├── ui.py                   shared wizard/menu primitives
├── service.py              the one daemon: per-profile tasks, launchd / systemd unit
├── ledger.py               daily spend ledger + the profile cap gate
├── outputs.py              persistent inbox JSONL store (notify + schedule failures)
├── status.py               canonical /status rows (TUI + apps share this)
├── prompts/
│   ├── default_agent.md
│   └── system_prompt.md
├── providers/              metadata for the model picker
│   └── {anthropic,openai,google,groq,openrouter,ollama}.py + model catalogues
├── tools/
│   ├── base.py             Tool ABC + ToolResult
│   ├── _state.py           per-turn emit / interrupt / usage, isolated per thread
│   ├── _paths.py           resolve_path + sensitive-path denylist
│   ├── _guards.py          terminal denylist, SSRF, prompt-injection scan
│   ├── _budget.py          per-result char cap for LLM context (100K default, per-tool override)
│   ├── _osv.py             OSV malware query for PyPI/npm names before skill/MCP install
│   ├── _sandbox.py         OS-level sandbox wrapper (opt-in)
│   ├── skill.py            the skill tool: mutations, scanner, quota
│   ├── search.py           content + filename search (rg + stdlib fallback)
│   ├── research.py         read-only sub-agent (depth: fast/normal/deep)
│   ├── terminal.py         run/background/status/output/kill
│   ├── workflow.py         bounded tool DAGs routed through ToolExecutor
│   ├── notify.py           native push to the owner's apps
│   └── … (read_file, write_file, edit_file, delete_file, todo, web_*, schedule,
│         memory, session_search, email, config)
├── tui/                    Textual app, widgets, screens, theme
├── scheduler/              cron + once jobs, hosted by the alpi daemon
├── mail/                   multi-account email: accounts, IMAP+SMTP, Gmail + OAuth
├── mcp/                    MCP client (stdio JSON-RPC) + registry
├── alp/                    Alpi Link Protocol (spec: docs/ALP.md)
│   ├── keys.py            Ed25519 identity at {home}/alp/secrets/alp_key.{pem,pub}
│   ├── envelope.py        build/sign/verify JSON-RPC envelope + replay cache
│   ├── peers.py           {home}/alp/peers.yaml load/save + capability check
│   ├── server.py          Unix-socket listener, fail-closed dispatch
│   ├── client.py          one-shot call with typed errors (TargetOffline, RemoteError)
│   ├── handlers.py        link.ask / link.cancel — engine integration
│   ├── mention.py         @peer parser + executor (shared by TUI + host chat)
│   ├── pending.py         pending invites store (unpinned-sender capture)
│   └── setup.py           `alpi setup → Peers` wizard
├── host/                   control plane for desktop / mobile clients (default profile only)
│   ├── server.py          Unix-socket JSON-RPC server (no envelope, no Noise — fs perms = trust)
│   ├── handlers.py        read verbs (host.workgroup.transcript, host.sessions.*)
│   ├── read_pool.py       isolated executor for roster and pipeline-state reads
│   ├── chat.py            host.chat.send/delegate (streaming) + host.chat.cancel
│   ├── runs.py            host.runs.list + host.run.{read,cancel}
│   ├── config.py          config mutation verbs (providers, peers, mcp, email, …)
│   ├── connections.py     connection identities, device credentials, migration
│   ├── connection_context.py request-scoped connection/device attribution
│   ├── admin_audit.py     bounded audit trail for administrative mutations
│   ├── attachments_rpc.py stage uploads in, serve produced files out (scoped)
│   ├── network_rpc.py     bind status and the ordered WS/WSS pairing routes
│   ├── probes.py          host.email.probe, host.peers.ping, host.model.ctx_window
│   ├── schedule.py        host.schedule.{list,remove,set_paused,fire}
│   ├── outputs.py         host.outputs.{list,read,mark_read,mark_unread,mark_all_read,delete}
│   ├── daemon.py          host.daemon.{restart,update}
│   ├── device_state.py    device-facing profile state for the apps
│   ├── events.py          host.events.subscribe + thread-safe emit() for daemon-pushed updates
│   ├── workgroup.py       transcript decryption (hub + member shapes)
│   └── sessions.py        plaintext session list / read
└── knowledge/              `alpi_knowledge` answer packs (hand-maintained)
```

### Execution spine

Every engine turn creates one immutable `RunContext`, one `ToolExecutor`, and
one `ExecutionWorld`. Context variables bind those objects across nested tool
calls without adding parameters to every tool. The executor is the only
registry dispatch seam: direct model calls and `workflow` steps therefore use
the same denylist, member restrictions, availability checks, execution world,
and durable journal.

Tools are exclusive by default. Only classes that explicitly declare
`parallel_safe` can overlap, and the engine parallelizes a model batch only
when every call is safe. A mixed batch remains serial. Results and emitted
states are replayed in original call order, preserving provider transcript
determinism.

A call runs only with the arguments the model actually sent. The engine,
`delegate`, `research`, the workgroup wrap-up handoff and the memory reviewer
decode them through `alpi/tools/_args.py`: empty or `null` is `{}`, raw control
characters inside strings are accepted, and one JSON-encoded layer around an
object is unwrapped. Anything else never reaches the tool and answers one of:

- `arguments for <tool> are not valid JSON: <reason> (char <pos> of <len>); the call did not run.`
- `arguments for <tool> are not valid JSON: <reason>; the call did not run.` —
  a key given two different values, nesting deeper than 100 levels, a string
  holding an unpaired surrogate or a number out of range (`NaN`, `Infinity`,
  beyond ±1.8e308): values a tool, the logs or a strict JSON reader would
  mishandle. A key repeated with the same value is kept once.
- `arguments for <tool> are not a JSON object (got array); the call did not run.`
- `arguments for <tool> are missing (required: …); the call did not run.` — a
  tool with required parameters got empty or `null` arguments; an explicit
  `{}` still reaches the tool.

Only the last call of a reply cut at the output-token limit adds that the limit
cut it off. A batch holding a refused call runs serially. The assistant message
sent back to the provider carries the arguments as dispatched: the raw string
when it is already a strict JSON object without repeated keys equal to them,
canonical ASCII JSON otherwise, `{}` for a refused call, so a provider that
parses history never sees a broken payload.

Right after decoding, a top-level argument sent as a JSON string is decoded
when its schema admits objects or arrays and not strings (`type`, a type list
or `anyOf`/`oneOf` branches), so a stringified `knowledge` object or `workflow`
`steps` list reaches the tool, the events and the journal as the structure the
schema declares. A string whose JSON would be refused above stays a string.
`workflow` applies the same rule to each step's own arguments before
`${step.output}` references expand; an expanded value stays a string. A
parameter that admits strings, or one without a readable type, passes through
untouched.

Each turn writes `runs/<run_id>.jsonl` with bounded, redacted events (an unpaired surrogate in
any persisted text, journal or saved session, and in every frame the host sends a client over the Unix socket or a
WebSocket, becomes U+FFFD): the
start record (pid, model, input), tool starts / states / ends, `model_state`
when it changes, `usage`, every `assistant_done` (only the one closing the
turn carries `final=True`), errors and the finish outcome. Streaming deltas
are never journaled — the reconnect replay is the sessions sidecar — so
`alpi runs show` and `host.run.read` return an operational timeline, not the
stream. Terminal command text is omitted everywhere, including `workflow`
steps; `steps` or step arguments that are not structured are dropped from the
record. Local operators use `alpi runs list|show|cancel` or `/runs`; paired
clients use `host.runs.list`, `host.run.read`, `host.run.cancel`,
connection-scoped like sessions.

Cleanup offers completed journals older than 30 days plus the oldest beyond
200 MiB per profile, skipping anything completed within the last hour;
nothing is deleted on its own. A **run sweep** runs at profile start and
every 30 s from the daemon's maintenance loop, off the scheduler's thread
pool and wrapped so a failure in it never ends the loop. One scan of `runs/`
stats every journal and reopens only those whose size or mtime changed since
the last pass or that were running then (`_journal_status_cache`), so a
profile with thousands of closed journals costs one `stat` each. The scan
feeds two rules in order. `reconcile_stale` closes journals whose pid is gone
as `interrupted` (reason `dead`), so a dead child is reported within about a
minute. `reconcile_silent` judges a *scheduled* run that has written nothing
for longer than its timeout plus `SILENCE_GRACE_S`: the `timeout_s` the scheduler
recorded in `run.started` (from `ALPI_RUN_TIMEOUT_S`), else the job's current
timeout, else `MAX_RUN_TIMEOUT_SECONDS` for a deleted job or an invalid value; silence is wall-clock, but the sweep must
also have watched it hold for the grace on the monotonic clock before acting,
so a wedged child is reported roughly ten minutes past its timeout and a clock
step alone never fires it. A live pid is killed only when it is provably this
run's process — `run.started` records `pid_start` from `/proc/<pid>/stat`, the
sweep requires it to match, and never targets its own pid or its parent's.
Anything alive it cannot vouch for (a recycled pid, a pre-0.14.50 journal, a
host without `/proc`) is reported once and left untouched, journal included: a
`run.finished` written under a live writer would be followed by that writer's
own records and the run would read as running again. Runs without a job are
never judged by silence. The scheduler closes the journal of a child it ends
itself (it hands the child `ALPI_RUN_ID`), so its own timeout yields one alert
rather than one from the scheduler and one from the sweep. Each reported row
files an error output and raises `schedule.failed`, the path a live failure
already uses.

`ExecutionWorld` keeps filesystem resolution and terminal shell execution under one
run-scoped abstraction. `local` preserves the previous behavior. `docker`
wraps processes in an ephemeral container while bind-mounting the same
absolute workspace/profile paths, so file tools and subprocesses observe one
namespace. Foreground containers are force-removed on timeout; background
terminal jobs are refused so a detached container cannot outlive its run.
Dedicated workers such as skill scripts and speech transcription remain
host-side; this backend is not a whole-agent filesystem sandbox.

The `workflow` tool executes a bounded dependency graph of registered tools.
References such as `${step.output}` feed prior results into later arguments;
independent safe steps can overlap. Recursion is refused, failures stop the
graph unless explicitly marked `continue_on_error`, and every nested call
re-enters `ToolExecutor` rather than bypassing policy. Nested parallelism uses
the same `tools.max_parallel_tool_calls` limit as direct model batches.

Runtime state (skills, sessions, memories, logs, ALP peers, keys)
does not ship with the package — it's generated per profile under
`~/.alpi/`. The `alpi/knowledge/references/` directory holds the
answer packs the `alpi_knowledge` tool serves; there is no bundled
skill namespace.
See Profile home layout immediately below. The `skill` tool
(`alpi/tools/skill.py`) manages user-created skills
that live at `{home}/skills/<category>/<name>/`.

## Profile home layout (`~/.alpi/` or `~/.alpi/profiles/<name>/`)

```
~/.alpi/                     default profile root
├── .env                    API keys, IMAP/SMTP credentials, allowlists
├── config.yaml             model + tools + tui + mcp
├── memories/               USER.md, MEMORY.md, AGENT.md (+ .bak)
├── skills/<category>/<name>/    SKILL.md + scripts/ + references/ +
│                                 assets/ + secrets/ (0700) + state/ +
│                                 .gitignore
├── recipes/<id>.yaml        saved workgroup recipes owned by this hub profile
├── sessions/<id>.json      compact turn-based session log (TUI / desktop / `--once`)
├── knowledge.sqlite        sqlite-vec derived indexes for knowledge,
│                            session recall, and workgroup recall
├── mentions/<sender>@<conversation>.json  @-mention threads per sender and originating conversation (cap 20 turns), receiving side; <sender>.json for callers that send no conversation
├── run/                    background process registry, schedule pids
├── alp/                    ALP state — keypair, peer list, socket, pid
│   ├── peers.yaml         pinned peers (pubkey + allow + optional address)
│   ├── alp.sock           Unix-domain socket, 0600, only while listener runs
│   ├── alp.pid            listener pid
│   └── secrets/alp_key.{pem,pub}   Ed25519 identity (private 0600, public 0644)
├── host/                   control-plane state (default profile only)
│   └── host.sock          Unix socket the local desktop connects to (mobile uses the WebSocket)
├── outputs/                persistent inbox for proactive agent messages + schedule failures
│   └── outputs.jsonl       JSONL store (≤500 rows, atomic compaction)
└── logs/                   service.log (daemon-wide; lives only at the root, NOT
                            duplicated per profile), agent.log + approval.log
                            (per profile — only the default profile's pair is at
                            this level), ledger.json, compaction.jsonl, runs.jsonl

~/.alpi/profiles/<name>/     same layout MINUS service.log; agent.log + approval.log
                             are emitted under each profile's own logs/
```

## Core systems

### Engine loop (`alpi/engine.py`)

Per turn: append user message → loop {compaction check → LLM stream → emit deltas → exec tool calls → append tool results} until the LLM stops emitting tool calls OR `max_steps_per_turn` is hit. The configured value (default 100 model iterations) is literal for every provider and budget. Hitting it does not drop gathered work: normal chats get one tools-off best-effort wrap-up; detached workgroup turns get one `workgroup_post`-only handoff. `interrupt_requested` is polled at three checkpoints (between iterations, mid-stream, between tool calls). A turn lock serializes concurrent runs so a delayed `research` tool from the previous turn can't bleed into the next.

**Compaction runs before every model call of the turn**, not only at its start, so a long tool loop never grows the prompt until the provider rejects it. When the estimate passes `trigger_ratio` of the model's window, `alpi/compaction.py` first truncates oversized tool outputs, then prunes the tool outputs already behind the kept tail (`TOOL_PRUNE_*`: head and tail of each kept, the middle elided) and only summarizes the middle with the fast tier when those two passes leave the prompt above the trigger; when the kept head and tail alone exceed the trigger and the middle is too small to matter (under twice the summary floor), or the middle is only the previous summary plus a message or two, no summary is spent because none could help. The kept tail is aligned so it never opens on a tool reply whose calling assistant message was summarized away; when no calling message exists, one stub names every leading reply. Every pass that changed the prompt is one line in `logs/compaction.jsonl` and one `auto_compact` event.

**Repeated tool failures are a hint, not an escalation.** Consecutive failures are keyed by tool, arguments and error text: the same call failing three times in a row injects one `[engine]` user note that repeats the error and asks for different arguments or another route, and five identical failures mark that tool as exhausted for the turn (its calls are refused without running). One tool failing three times in a row with the same non-empty error while its arguments change gets its own note, once, asking the model to read what the error names before another variation; it is never exhausted (`terminal` is exempt, its error being an exit status rather than a cause). The one-way escalation (effort `high`, else the `deep` tier) stays for three consecutive failures with three different keys, which is what a model that does not understand the task produces, but such a same-error run holds it back until its fifth failure, so the note always goes first (also when one parallel batch jumps past five); a mixed streak does neither. Every note the engine injects into the turn (these, the time checks, the open-todo, relay and empty-reply nudges, the wrap-up instruction) is also emitted as an `engine_note` event and kept in the run journal as `agent.engine_note`; no client, gateway or `--once` consumer reads it.

**An empty final reply is fine when something was delivered.** A chat or scheduled turn that ends without text after a successful `notify`, `email(action=send)` or `attach_file`, or a silent scheduled job (`ALPI_SILENT_JOB=1` from the scheduler), closes as complete; a detached workgroup turn keeps its handoff nudge. Otherwise the model is re-prompted once; the effort escalation on that re-prompt applies only to attended chat, never under `ALPI_PLATFORM=cron` or in a workgroup dispatch.

**One tool call is bounded.** `ToolExecutor` runs a call under a deadline of `tools.call_timeout_s` (default 600 s, `0` disables), shortened to the soft turn budget left when the scheduler or a workgroup dispatch set one and more than 30 s of it remain (closer to the deadline, and past it, the plain cap applies so wrap-up calls are not cut to nothing). A call past it returns a transient failure (the engine moves on; the tool's thread is left to finish or die with the process) and is journaled as such. Tools that bound themselves declare `call_timeout_exempt` (`ask_user`, `peer`, `research`, `delegate`, `workflow`, `terminal`, `workgroup_post`).

Events emitted to the UI sink: `user`, `reasoning_delta`, `assistant_delta`, `assistant_done`, `tool_start`, `tool_state`, `tool_end`, `usage`, `error`, `done`, `interrupted`. The TUI consumes them; the scheduler subprocess consumes a subset via JSON-lines.

A model-provider failure reaches every surface as one plain sentence, never as the provider's
exception text. `alpi/llm_errors.py` classifies the exception chain (litellm class, HTTP status,
text) into `context_length`, `insufficient_credit`, `auth`, `forbidden`, `model_unavailable`,
`content_policy`, `rate_limited`, `timeout`, `provider_unavailable`, `bad_request` or `unknown`.
The `error` event carries `text` (the sentence), `code` (the class) and `detail` (the redacted,
500-character technical text, also logged and kept in the run journal). `host.chat.send` frames
carry `text` and `code`; `detail` reaches the TUI, `--once` (`[error] text (detail)`, or the
`detail` key of the JSON event) and the scheduler, whose failed-job message reads `agent error:
text (detail)`. ALP peer replies carry only the sentence. Chat-level codes such as `busy` share
the `code` field.

The apps put the daemon's own protocol errors in plain words through one shared map,
`common/plainError.mjs` (fixtures in `common/plainError.fixtures.mjs`, exercised by both clients):
`too-many-connections`, `too-many-requests`, `forbidden`, `method-not-found` and the close reasons
`Authorization changed`, `Device authorization revoked`, `WebSocket capacity reached`, plus the
transport failures, become a sentence; anything else is shown unchanged. Both clients retry a call
or a stream refused with `-32029 too-many-connections` once after 1.5 s before showing it.

Host chat forwards `usage` with `context_tokens`; it is non-zero only for the
main completion whose input becomes `Session.last_ctx_tokens`. Side-model usage
still carries accounting fields but cannot move a client's conversation meter.

**Cross-turn resume.** A chat is not a long-lived object: each turn spins up a fresh `Engine` and rehydrates the session from disk (`_hydrate_from_path` in `cli.py`, shared by TUI `--continue` and the host chat; the desktop "edit message" rewrite path mirrors it in `host/chat.py`). The model context is rebuilt from the prior **replayable** turns — those that ended in a final reply or produced a file; a turn aborted before its reply (no assistant text, no output files) is dropped, so a resumed session never re-answers a dangling request. Each replayed turn contributes its user text (plus an input-attachment marker `[attached: name (mime)]`) and assistant text (plus a produced-file marker `[produced this turn — reuse the absolute path…: name → /abs/path]`). Tool calls and tool results are deliberately **not** replayed — they would blow the context budget — so an agent does not remember what it searched, read, or analyzed last turn, only its final reply and the absolute paths of the files it produced. A multi-turn edit ("now relight it at sunset") reuses the produced path surfaced by the marker, not a remembered tool output; an agent that needs an earlier tool's result across turns must re-run the tool or rely on a produced file.

The system prompt for each turn is assembled in a fixed order (`PART_ORDER` in `alpi/prompt_cache.py`): `AGENT.md` (agent profile — voice, style, identity) → base prompt → environment block (workspace, profile home, path rule) → system time → **platform hint** (per-surface guidance when `ALPI_PLATFORM` is set: `cron`; empty for TUI and the apps) → turn guidance → the self-knowledge rule pointing the model at `alpi_knowledge` (dropped when that tool is denied) → **skills index** → `USER.md` → `MEMORY.md`. Providers that need an explicit marker (Anthropic, including through OpenRouter) get LiteLLM's `cache_control_injection_points` on `messages[0]` from `cache_kwargs_for_model`; an `openai`-prefixed model at OpenAI's own endpoint never does (the host is judged as LiteLLM judges it, from `api_base`, `litellm.api_base` or `OPENAI_BASE_URL`), because LiteLLM would turn the marker into OpenAI's explicit mode, which switches off its automatic prefix cache (and the `/v1/responses` bridge drops the breakpoint anyway), so an OpenAI model reads its cache with no marker at all; a gateway behind the same prefix keeps it.

The scheduler (`alpi/scheduler/run.py`) sets `ALPI_PLATFORM=cron` so scheduled jobs run knowing no user is present and they cannot ask for clarification. That overwrite would otherwise erase the deployment runtime, so it also carries `ALPI_DEPLOY_RUNTIME`, which `alpi/runtime.py` prefers: `ALPI_PLATFORM` is the turn origin, `platform_id()` is the runtime, and a job inside a container still reads as Docker. Each fire runs as a subprocess capped at `job_run_timeout(job)` seconds — `job.timeout` if set, else `DEFAULT_RUN_TIMEOUT_SECONDS` (900). `parse_run_timeout` is the one duration contract for `schedule(add|update)`, execution, `schedule list` / `host.schedule.list` (`run_timeout`, or `null` plus `timeout_error`) and the silence watchdog: a whole number of seconds in `[30, 86400]`; booleans, fractions, non-finite and out-of-range values are refused, and a bad stored value fails the fire with `invalid stored timeout` instead of being clamped. Fires of one profile run serially, so a long timeout also delays that profile's other due jobs. The cap is a stuck-process backstop for unattended runs, not the cost guard (`budget.daily_usd` is) and not a hint that jobs must be short; heavy jobs (deep research, multi-step publishing) opt into a longer budget via `schedule(add|update, timeout=…)`. The scheduler passes the child a soft budget via `ALPI_TURN_BUDGET_S` (the cap minus a ~10% reserve, floor 60s); when the engine crosses it, normal jobs get one tools-off best-effort reply and detached workgroup turns get one `workgroup_post`-only handoff. The hard subprocess timeout remains the last-resort kill if finalization itself stalls.

Cron jobs with `no_agent: true` skip the LLM entirely. The `prompt` is shlex-tokenized and exec'd directly (`shell=False`); `${ALPI_HOME}` expands to the profile home and the profile's `.env` overrides inherited env keys so skills find their declared `requires_env`. A form-based allowlist enforces that the command is `python[3] [flags] <script>` or `<script>` invoked directly, where `<script>` resolves to `<home>/skills/<category>/<name>/scripts/…`; the script must exist as a regular file (not a symlink), the only interpreter flags accepted are `-u -B -I -E -s -O` (alone or joined, as `-uB`), so no inline code (`-c`, `-m`, `-Bc`…) can ride in a job, the interpreter is `python`, `python3` or `python3.N` (a bare name, or an absolute path outside the profile home, the workspace and temp folders), and other executables are rejected, at `schedule(add)` and `schedule(update)` time and again inside the scheduler before every exec, so a job stored with a refused shape stops running. Use this for deterministic skills (sync, file processors) — saves both tokens and the agent boot latency per fire.

### LLM transport (`alpi/llm.py`)

Thin wrapper over `litellm.completion`. alpi only ever imports the package (`import litellm`, then `litellm.utils.X`): a thread that does `from litellm.utils import X` while another is inside the first `import litellm` leaves it half-initialised and the CLI dies with a circular-import error. `stream()` is a generator yielding `{text_delta, reasoning_delta, tool_calls_delta, finish_reason}` per chunk plus a final `{final, tool_calls, input_tokens, output_tokens, cost_usd, finish_reason}` whose `finish_reason` is the last one the provider reported (litellm reports `stop` when a stream closes early, so only `length` proves a cut); the `stream end` breadcrumb logs it. `complete()` is the non-streaming variant (`research`, `delegate` and the background passes); its `Completion.finish_reason` carries the same signal. `_silence_litellm()` runs at import time to mute LiteLLM's startup banner via FD-level redirect (Textual is sensitive to stdout pollution).

### Memory (`alpi/memory.py`)

Three files: `USER.md` (facts about the user), `MEMORY.md` (env quirks, commands, incidents), `AGENT.md` (the agent's own profile — tone, style, identity, language). `§` entry delimiter, char limits `USER_CHAR_LIMIT = 3000` / `MEMORY_CHAR_LIMIT = 5000` (see `alpi/memory.py`; `AGENT.md` is free-form prose with no cap). Accent+case+punctuation-insensitive dedup, plus token-Jaccard dedup at 70% max-containment to catch paraphrases. `.bak` snapshot before every mutating write. Approach C: every mutating call returns the full current state of the target file so the agent sees its own write in the same turn.

**v2 quality metadata.** Each entry carries a trailing `<!-- alpi-meta conf=... captured=... reinforced=... -->` comment that is stripped before the entry reaches the system prompt. `conf` is `low` / `normal` / `high` (default `normal`). Near-duplicate writes reinforce the existing entry (bump `reinforced`, upgrade `low → normal` at ≥ 2) instead of appending a paraphrase. Low-confidence entries with zero reinforcements expire after `LOW_CONFIDENCE_MAX_AGE_DAYS = 30` (constant in `alpi/memory.py`; keep it fixed unless operational traces justify tuning). The memory tool's safety scanner reuses the skill scanner patterns and adds invisible/bidi unicode detection (U+200B–200F, 202A–202E, 2060, 2066–2069, FEFF) to block Trojan-Source vectors; `_operational_warning` surfaces non-blocking warnings when a write looks like session state (`chat_id`, `session_id`, ISO timestamps).

**Batch writes.** `memory(action="add", entries=[...])` accepts a list of entries for the same target in a single call. Each entry runs through cross-file and same-target dup checks independently; entries that collide are skipped with a per-line note, the rest land in one write. Replaces the pathological pattern of one `add` call per fact (16 calls in a single turn observed in real sessions).

**Post-turn reviewer.** When `memory.review_interval > 0` (default 0 = off), `alpi/review.py` spawns a daemon thread after each turn that snapshots the user/assistant text and asks the LLM whether anything durable should be added. The reviewer is constrained to `memory(action="add", ...)` — never `replace`/`remove` — to prevent it from deleting unrelated entries on a bad pass.

**Promotion queue (`alpi/promotion.py`).** Auto-compaction never writes to `USER.md` / `MEMORY.md` / `AGENT.md` directly. After every fired compaction the engine runs a second short LLM call against the summary (system prompt `CANDIDATE_PROMPT`) and pushes any durable facts as **candidates** into `<home>/memories/promotion_queue.jsonl`. On enqueue, each candidate is annotated with the same preview warnings the memory tool computes at write time — operational-state heuristic, cross-file duplicate check, safety scan. The queue is bounded (`MAX_PENDING = 200` per profile) and pending entries expire after `MAX_AGE_DAYS = 30`. Per-record fields in the JSONL: `id` (8-char hex), `created_at` (unix ts), `source` (`compaction` | `reviewer` | `manual`), `session_id`, `model`, `target` (`USER.md` | `MEMORY.md` | `AGENT.md`), `text`, `confidence` (`low` | `normal` | `high`), `warnings` (list of strings).

Two memory tool actions surface the queue, both safe for the agent to call: `promotion_list` (read-only) and `promotion_discard(id)` (drops a candidate without writing). **There is no agent-callable apply.** The only path that writes to durable memory from the queue is the CLI `alpi memory promote` — interactive review with `[a]pply / [d]iscard / [s]kip / [q]uit` per candidate, plus `--apply-all` / `--discard-all` for unattended sweeps. This keeps the human-in-the-loop gate genuine: the agent cannot promote facts on its own regardless of how the prompt is framed. If the underlying memory add fails (safety scan, duplicate), the candidate stays in the queue so the operator can fix and retry.

### Path resolution (`alpi/tools/_paths.py`)

Single entry point `resolve_path(path)`:

1. `expanduser()`.
2. Relative paths root at the active workspace (`cfg.workspace` or `cwd` fallback).
3. Resolve symlinks.
4. Reject if the resulting path matches any sensitive-path entry (denylist below) — `ValueError`.

Denylist: `/etc/`, `/boot/`, `/sys/`, `/proc/`, `/usr/lib/systemd/`, `/System/`, `/private/etc/`, the docker sockets, `~/.ssh/id_*`, `~/.ssh/authorized_keys`, `*_key`, `*_ed25519`, `*.pem/.p12/.pfx`, `~/.aws/{credentials,config}`, `~/.gnupg/`, `~/.netrc`, `~/.npmrc`, `~/.pypirc`, `~/.pgpass`, `~/.config/{gh,gcloud}/`, shell rc/login files (`.bashrc`/`.zshrc`/`.zprofile`/…), `~/Library/Launch{Agents,Daemons}/`, profile `.env`/`config.yaml`, and skill `secrets/` dirs. Both pre-resolve and post-resolve forms are checked (macOS `/var` → `/private/var` symlink case).

On top of that denylist, `_always_private_area` applies to every caller, admin turns included: read and write are refused under a profile's `secrets/`, `alp/secrets/` and `host/` (except reads under `host/attachments/`, where staged chat uploads live), and write is refused under `schedule/`, `memories/`, `logs/`, `runs/`, `sessions/`, `recipes/` and `alp/peers.yaml`. The error for `memories/` and `schedule/` names the owning tool (`memory`, `schedule`). The member fence (`private_areas_fenced`) runs first and keeps its wider list and its own message. `is_read_denied` applies the read half, so `search` never returns those files.

`suggest_similar_paths(target)` lists the parent directory and fuzzy-matches siblings by basename substring/prefix. Used by `read_file`, `edit_file`, and `search` to turn dead-end errors into actionable suggestions.

`alpi/tools/_lint.py::lint_content(path, content)` runs a parser-based syntax check before every `write_file` / `edit_file` lands on disk. Parsers by suffix: `.py` → `ast.parse` (stdlib), `.json` → `json.loads` (stdlib), `.yaml`/`.yml` → `yaml.safe_load_all` (PyYAML, already a dep; every `---` document is parsed, so Spring and Kubernetes multi-document files pass and a broken later document is reported at its line in the file), `.toml` → `tomllib.loads` (stdlib on every supported Python version). Other suffixes pass through. Failures return a one-line error with the source line/col and the write is refused — the original file (if any) is untouched. Catches the class of bug where a malformed `jobs.json`, `config.yaml`, or skill script silently breaks a downstream consumer.

`alpi/secrets_io.py::safe_write_secret(path, content, mode=0o600)` is the canonical write path for any credential file. It uses `tempfile.mkstemp` (O_EXCL + 0o600 at creation, random unique name in the target dir), then `os.replace` onto the target — no TOCTOU window where the file exists at umask perms, and a stale `<target>.tmp` lingering at looser perms cannot compromise the write because the helper picks a fresh random name. Used by `model_selector._atomic_write_env` (.env writes), `mail/gmail_auth._save` (gmail token), `alp/pending.save` (pending-peers yaml), and `alp/keys.create` (ALP private key). `open_private(path, truncate=False)` is the append (or truncate) counterpart for logs and JSONL stores: it opens 0600 and tightens an existing looser file. The subsystem and daemon loggers (`_log.PrivateRotatingFileHandler` + `RedactingFormatter`), the replay sidecar, `outputs.jsonl`, `host/events.jsonl` and `alp/turns.jsonl` write through it after `redact()`.

### Tool registry (`alpi/tools/__init__.py`)

`register(cls)` adds a `Tool` subclass to the dict, `schemas()` emits the OpenAI function-calling shape, `execute(name, args)` runs by name with full error capture. The registry is assembled from the sibling tool modules in `alpi/tools/__init__.py`, including the Playwright-backed `browser` tool. `knowledge` registers first so durable user/workspace recall has one canonical surface.

`tools.deny` takes whole tools (`terminal`, `github__*`) and single actions (`knowledge:ingest`, `knowledge:*`). A denied action leaves the tool's `action` enum, and the parameters only that action reads leave with it when the tool declares `action_parameters` (`knowledge` does: a search-only profile sees `action`, `query` and `k`); a tool whose every action is denied is dropped. The executor refuses a denied action, and any spelling of `action` outside the trimmed enum, naming the ones still allowed, so a stale context cannot reach it. Denying `write_file` or `terminal` also denies every `skill` action that writes skill files (`create`, `edit`, `patch`, `add_file`, `remove_file`, `delete`, `reset_state`, `set_meta`): a skill's scripts run through `skill run`, so authoring one would write and run code past the deny. `run`, `view`, `list`, `validate`, `test` and `invoke` stay, so a profile keeps the skills its operator installed, and the refusal says why. Schemas are paid on every cold prefix, so a tool description carries its operating rules and points manuals (layout, conventions, examples) at `alpi_knowledge`; `tests/test_tool_schemas_cacheable.py` caps the total.

The interactive `browser` can record its own context with `trace_start` before navigating and `trace_stop` after the workflow. Navigation, form fills and clicks keep the same cookies and recording; capture does not replay the workflow in a separate browser. Trace files under the workspace's `.browser-traces/` contain bounded request/response metadata, sanitised JSON projections and action outcomes, with checkpoints after actions. No headers, cookies, form values or query values are stored; URL path segments that contain a digit or a symbol are masked, plain-word segments are kept. Financial values and enumerated states survive; other body values use per-recording keyed references. Unknown or excessive response lengths omit bodies explicitly. A complete trace requires successful navigation, no failed actions, no pending, failed or error-status (4xx/5xx) document/API requests, no trace truncation or write error and a visible confirmation checked by exact accessible role/name on stop. This proves those observations, not hidden server correctness. Closing the browser during recording saves an incomplete trace. Existing browser network and workspace guards still apply.

A tool's `check()` is what keeps `schemas()` honest: an unavailable tool is never offered to the model, so the probe has to test the thing that actually fails at call time, not a proxy for it. `browser` is the cautionary case — probing only `import playwright` advertised the tool on every slim Linux image, where playwright downloads the browser on demand and then cannot launch it because the distro never installed Chromium's load-time libraries. It now `dlopen`s one soname per Debian package family (`_CHROMIUM_SONAMES`, Linux-only, ~2 ms when they are absent) and reports the missing set plus `CHROMIUM_DEPS_COMMAND` — a `uvx --from playwright …` invocation, because `uv tool install` links only alpi-agent's own entry points and a bare `playwright` is not on `PATH`.

The image cannot be held to that list by a unit test: `pip install .` ignores `uv.lock`, so the playwright inside the image outruns the one the suite imports (observed: 1.62 vs 1.58). So `docker/Dockerfile` derives the packages from its own playwright (`playwright install-deps chromium-headless-shell`) instead of carrying a hand-written copy, and `publish-docker.yml` launches the real headless shell in the built image before anything is pushed. `pyproject.toml` keeps playwright below 1.65: from that release the driver's own `node` needs `libatomic.so.1`, which the base image lacks, so `install-deps` cannot even start. `ensure_chromium()` installs with `--only-shell` because `chromium.launch(headless=True)` runs `chrome-headless-shell`; the full Chromium build was never used, and `_wanted_chromium_dirs()` now tracks only the shell so an existing profile's stale full build is pruned (~640 MB reclaimed per profile).

### Knowledge recall (`alpi/core/` + `alpi/tools/knowledge_base.py`)

Per-profile semantic search over synthesized user/workspace knowledge. The
source of truth is Markdown under `<workspace>/knowledge/`; SQLite under
`<home>/knowledge.sqlite` is only a rebuildable derived index. Raw source files
and attachments are read only as inputs for synthesis; alpi does not copy them
into a durable documents store.

- `knowledge(action="search", query, k=5)` — hybrid sqlite-vec + FTS search over knowledge pages; page-level results with `path`, `title`, `type`, `tags`, `snippet`, `score`, `links`. The index holds one bundle and says which. Only `query` is searched: a search without it is refused with the call to resend, even when text arrived in another parameter, so a misplaced argument never runs as a guessed search. The ingest-only flags (`force`, `apply`, `ocr`) carry no schema default. Use `alpi_knowledge` for questions about alpi itself.
- `knowledge(action="ingest", …)` — the explicit learn path: resolve a file or a current-turn attachment, extract text (PDF / DOCX / EPUB / HTML / text, OCR on request), have the LLM synthesise durable Markdown pages, update `index.md` and `log.md`, lint, refresh the index. The raw file is not copied. The synthesiser reads the first 12,000 characters of the source; ingest and maintain results carry `source_budget {available, used, truncated}`, and the same object is in the prompt so a cut source is not presented as whole. A DOCX keeps its tables in document order, one line per row with cells joined by ` | `, empty rows skipped and a merged cell read once.
- `knowledge(action="maintain", …)` — LLM-wiki maintenance: every proposed page is validated before any is written, an existing page is replaced only when the synthesiser saw its full body, and the result reports `bytes_before` / `bytes_after` so a legitimate shrink is visible.
- `knowledge(action="lint", path?)` — required `index.md` / `log.md`, minimal frontmatter (`type`, `title`, `tags`, `updated_at`, `sources`), relative links, orphan pages.
- `knowledge(action="index", path?, force?)` — incremental by a sha256 fingerprint of each page's text (stored in `okf_files.fingerprint`, added in place to an older index): a page whose fingerprint is unchanged is skipped even when its mtime moved, a page whose text changed is re-embedded even when its size and mtime did not, and a page whose chunks are unchanged but whose metadata moved (tags, type, `updated_at`, `sources`) is refreshed without calling the embedder (`refreshed_pages`); `force=true` rebuilds the `okf_*` table family inside one transaction and is the only way to retarget the index at another bundle.

Supported ingest formats: markdown / text / source / configs (stdlib read),
HTML (`html2text`), PDF (`pypdf` for text-layer, RapidOCR fallback when
`ocr=true` and pypdf extracts < 50 chars), DOCX (`python-docx`), EPUB
(`ebooklib`), images (`PIL` + RapidOCR — only with `ocr=true`). OCR backend is
`rapidocr-onnxruntime` (ONNX port of PaddleOCR, no torch dependency). The
PDF/image/OCR extraction primitives live in `alpi/extract.py` and are shared
verbatim with the chat-attachment path (`alpi/attachments.py`); the DOCX/EPUB/
HTML readers and the chunker live in `alpi/tools/workspace.py`, a support
library, not an agent-facing recall surface.

**Shared store primitive (`alpi/core/store.py`)**. `open_store(home)` returns a `sqlite3.Connection` with the sqlite-vec extension loaded. Designed to host other shapes later (workgroup search, future entity memory) — they bring their own table schemas.

**Embedder (`alpi/core/embed.py`)**. `Embedder` Protocol; default `FastembedEmbedder` wraps the ONNX export of `sentence-transformers/all-MiniLM-L6-v2` (384-dim, ~90 MB, no torch). Numerically equivalent to the original sentence-transformers checkpoint but ~10× lighter at runtime. Lazy-loaded under a `threading.Lock` so concurrent first-touch calls serialize on a single model instance instead of racing.

The bundle uses minimal YAML frontmatter, relative Markdown links,
and required `index.md` / `log.md`. It is never auto-injected into the system
prompt; access happens only through `knowledge` tool output.

Links resolve relative to the page holding them, the way GitHub, Obsidian and VS
Code resolve them, and that is the only form alpi writes. The link graph reads
more than it writes: bare, angle-bracketed and percent-encoded destinations,
`[[wikilinks]]` (by path, or by page name when it is unambiguous) and CommonMark
reference links, while links inside fenced blocks or code spans are examples, not
edges. `maintain` also repoints a proposed link that is written from the bundle
root onto the page it plainly means. Two rules are alpi's own rather than
Markdown's, and are the usual reasons an imported vault fails `lint`: every page
needs an inbound link, and the `type` frontmatter key collides with Hugo's
reserved layout key if the same tree is published with Hugo.

### Session recall (`alpi/tools/recall.py`)

Recall over **past conversations**, the conversational-memory peer of knowledge recall, in three layers: lexical find (`session_search`, term counts over `sessions/*.json`), exact browse (`session_read`, no model call), and opt-in semantic search (`index_sessions` / `recall_sessions`) for fuzzy "when did we discuss X / what did we decide about Y".

- `session_search(query)` — lexical first layer; returns the tail thread of matching sessions, active session excluded.
- `session_read(session?, phrase?, start?)` — browse layer, no embedding/LLM call: lists recent sessions, or opens a windowed turn slice around an exact phrase or `start` index (paged). Pairs with `session_search` (find → open the window).
- `index_sessions(force?)` — **opt-in** (sessions are never auto-indexed): walks `<home>/sessions/*.json`, builds a per-turn transcript (`user:`/`alpi:` lines), chunks + embeds with the same `core/embed.py` + sqlite-vec primitives as the knowledge index, into a **separate table family** (`session_files` / `session_chunks` / `session_vec` / `session_meta`) in the same `knowledge.sqlite`. Incremental (mtime/size skip); the active session is excluded. A pass — incremental, `force`, or the rebuild an embedder change triggers — runs in one write transaction, so a failure part-way leaves the previous index searchable, and readers keep seeing it until the new one commits. A session file that cannot be read stops a forced or embedder-change rebuild, keeping the previous index; an incremental pass skips it and keeps its old rows.
- `recall_sessions(query, k=5)` — cosine MATCH → `[{session_id, when, snippet, score}]`, active session excluded. Index rows carry the session's `connection_id` and `device_id` (an index built before either column is migrated in place, device ids backfilled from the session files before the first query; a versioned `device_backfill` count of device-less rows in `session_meta` commits with the backfill, so an interrupted pass, a completed legacy backfill or rows written by an older alpi rerun it without rebuilding embeddings; a session whose file cannot be read is stored as `?unverified`, which no device matches under `session_scope: device`, and is retried on every query, without writing while it stays unreadable, until the file reads; a query that cannot migrate fails instead of answering unfiltered), and results pass the same `can_read_session` check as `session_search` (the widening search stops at sqlite-vec's k limit of 4096), so a member sees its connection and a device under `session_scope: device` its own and deviceless sessions.

**Forgettable.** Recall is a derived view, so forgetting is real: deleting a session (`host.sessions.delete` → `host/sessions.py::delete_session`) purges its rows via `recall.forget_session`, and `index_sessions` orphan-sweeps any tracked session whose file is gone. No auto per-turn injection — retrieval is explicit, like the workspace tools.

### Workgroup transcript search (`alpi/tools/workgroup_search.py`)

The third retrieval surface on the same store: semantic search over **hub-owned** workgroup transcripts. Workgroups are hub-owned by design, so this is **profile-local and hub-only** — the hub decrypts its own transcript and indexes it; there is no cross-peer / federated search and no global "search all my peers' workgroups". Two tools:

- `index_workgroups(workgroup_id?, force?)` — **opt-in**: decrypts each hub-owned transcript via `host/workgroup.py::decrypt_transcript` (key-history aware, so posts written before a rekey still index), groups consecutive posts into ~2 KB chunks tagged `[seq · ts · author]`, embeds, into a **separate table family** (`workgroup_files` / `workgroup_chunks` / `workgroup_vec` / `workgroup_meta`) in the same `knowledge.sqlite`. Posts that don't decrypt (rotated-out key, AEAD failure) are skipped. Incremental (transcript mtime/size); empty `workgroup_id` indexes all hub-owned workgroups on the profile. Like the session index, each pass (scoped or global `force`, or an embedder-change rebuild) is one write transaction: a failure leaves the previous rows searchable. A workgroup that fails to decrypt stops a global `force` or embedder-change rebuild, keeping the previous index; incremental and scoped passes list it under `failed_workgroups` and keep its old rows.
- `workgroup_search(workgroup_id, query, k=5)` — search is scoped to one workgroup (brute-force cosine over that workgroup's chunks, so per-workgroup ranking is exact rather than a filtered global KNN). Returns `[{workgroup_id, seq_start, seq_end, when, authors, snippet, score}]`; never returns group keys, ciphertext, or filesystem paths.

**Forgettable.** Removing a workgroup purges its index in both delete paths — the host RPC (`host/workgroup_admin.py::_remove`) and the CLI (`alpi workgroup remove`) call `workgroup_search.forget_workgroup`; `index_workgroups` orphan-sweeps any tracked workgroup whose directory is gone. No auto-injection into workgroup turns. ALP encryption/transcript behaviour is untouched — this only reads through the existing decrypt path.

**Removal tombstones (`alp/secrets/subscriptions.removed.d/`).** Removing a
workgroup writes an empty marker named by its id in every local home, so a
stale in-memory copy or a hub-side auto-join heal cannot resurrect it.
Markers never cross machines and expire after `TOMBSTONES_KEEP_DAYS` (2) once
the id is gone from `subscriptions.yaml` and `alp/workgroups/`; `setup →
Cleanup` offers the expired set under *Workgroup tombstones*.

**Asset prefetch (`service.py::_prefetch_assets`).** Scheduled at boot + 600 s,
past the client-reconnection rush. Gated by `runtime.prefetch` on the root
profile: `auto` (default) fetches the embedding weights only when some
profile has `knowledge.sqlite` and Chromium only when some profile leaves
`browser` un-denied; `all` forces both; `off` — the default in Docker —
skips it. Every asset still loads lazily on first use, so `off` costs
latency, never functionality. A successful Chromium install prunes stale
builds of the headless shell.

### Skills

Live under `<home>/skills/<category>/<name>/`. Required `SKILL.md` plus optional `scripts/`, `references/`, `assets/`, `secrets/` (mode 0700, gitignored, scanner skipped), `state/` (gitignored, scanner skipped, runtime persistence). `.gitignore` auto-written on create with `secrets/\nstate/\n`.

**Live by default** — there is no pending-approval stage; the scanner and the sandbox are the guarantees.

Frontmatter (auto-populated on `create`): `name`, `description`, `category`, `version`, `origin: agent|user`, `created_at`, `requires_env`, `tools`, `keywords`, optional `output_schema`. 13 fixed categories including `miscellaneous` as the fallback. `secrets/` is filesystem state, not frontmatter: it is created lazily when a skill writes a secret file. `output_schema` is one-line JSON and uses a deliberately small subset (`type`, `properties`, `required`, `items`, `enum`) so the runtime stays dependency-light.

**Security scanner** (~50 patterns, `_DANGER_PATTERNS` in `alpi/scan.py` — the shared scanner library used by skills, memory writes, and the recalled-memory guard): destructive shell, credential exfiltration, prompt injection, persistence (cron/launchd/systemd/authorized_keys/sudoers/shell rc), reverse shells, tunneling, obfuscation (base64/eval/exec/compile), process exec, hardcoded credentials (API keys, OpenAI sk-, GitHub ghp_, AWS AKIA), system-password-file paths, deep traversal. Runs on every `create`/`add_file`/`patch` for files NOT in `secrets/` or `state/`.

**Atomic writes** everywhere (tmp sibling + `os.replace`). `.bak` next to SKILL.md on every edit/patch. **Quota**: max 40 agent-owned skills, enforced at `create`.

**Auto-injected into the system prompt** (`skills_index_block(home)`): every session start, all installed skills are listed by category as `name: description` entries, prefixed by a directive that says "check this list before reaching for general tools". Without this nudge, mimo-class models routinely went straight to `web_search`/`terminal` even when a perfect skill existed.

**TUI integration**: when a `terminal` command's path matches `.alpi/(profiles/<p>/)?skills/<cat>/<name>/...`, `arg_hint` rewrites the ToolCard label as `skill: <name>` (or `skill: <name> · <script>` when the script is the full path). Tool name stays `terminal`; the rewrite is display-only.

**Execution: `skill(action="run", name=...)`**. Single canonical ad-hoc path. If `scripts/run.py` exists the action validates the skill, then spawns the script via `subprocess.run` with `cwd` = skill dir, `env += {ALPI_HOME, ALPI_SKILL_NAME, ALPI_SKILL_DIR}`, 600s timeout, and the skill's `requires_env` checked up-front. If the skill declares `output_schema`, stdout must be JSON and is validated before the call succeeds. Scripts are normal Python; built-in tools and MCP methods are not importable Python APIs. No script → SKILL.md is returned with a `[skill X has no scripts/run.py — follow these instructions]` prefix so the agent follows the prose and calls the real tools. Scheduled prompts should call this action instead of reimplementing the skill by hand; the scheduler still enters through `alpi chat --once --emit-events --no-save`.

**Structured composition: `skill(action="invoke", name=...)`**. Same subprocess/runtime path as `run`, but stricter: the callee must ship `scripts/run.py`, must declare `output_schema`, and stdout must satisfy it. This keeps skill-to-skill composition machine-readable and prevents prose-only skills from pretending to be callable subroutines.

**Scripted harness: `skill(action="test", name=...)`**. Thin validation layer over the same runtime path. It exists so chat/scheduler/desktop can exercise a scripted skill and verify its declared `output_schema` without inventing a second testing runtime. If a CLI wrapper lands later, it should call this action instead of duplicating logic.

### Research (read-only sub-agent, `alpi/tools/research.py`)

Spawns a sub-agent with a read-only toolset (`web_search`, `web_fetch`, `web_extract`, `read_file`, `search`). Returns a single synthesised report; the main agent never sees the intermediate tool trace.

**Depth tiers** instead of a numeric `max_steps`: `depth="fast"|"normal"|"deep"`. The step ceilings are product constants (`DEPTH_STEPS_DEFAULTS`, 8 / 15 / 30). Locks the model to three buckets (fast = single-answer, normal = comparative, deep = exhaustive); `fast` and `deep` double as the model-tier names, so a depth also picks the matching tier when the profile configures one.

**Synthesis fallback**: when the budget runs out, research forces one final no-tools `llm.complete()` with "stop investigating, report now". Avoids the "[research gave up]" footgun where the main agent retries the whole thing.

**Cost cap**: `tools.research.max_usd` (default 1.0 USD, `0` = none) bounds one call, a whole `tasks` batch included, through one `_CallBudget` that every worker charges through a wrapper of the usage sink, so it counts the research model's completions and the model calls its own tools make (`web_extract`); a model that reports no cost is bounded by the step ceilings only. Before each investigation step, and before each tool call of a step's batch, the sub-agent stops once spend reaches 75% of the cap (the rest is the synthesis reserve; the calls skipped answer the model with an error), and before the synthesis once it reaches the cap; it also stops when today's spend reaches 90% of `budget.daily_usd`, so the main turn can still answer. A stop with something gathered returns the report (or, when the reserve is gone, the notes the model wrote and bounded excerpts of what its tools returned, each with its source) with a one-line truncation note; a stop before the first call is an error. The cap is checked before a call and charged after it, so calls already in flight finish: the overshoot is at most one call per running worker (three).

**Interrupt**: polls `tool_state.is_interrupted()` between iterations and between tools; returns `[research: interrupted]` on the first hit. **State label** during execution: `<depth> · step N/M`; while an inner tool runs its own `emit_state` label gets auto-prefixed with `step N/M · …` via a wrapped `_emit` installed for the duration of each tool-call batch (restored in a `finally`).

**Batch mode**: `tasks: [{brief, depth}]` up to 3 runs concurrently — see the Delegate section below for the shared ThreadPoolExecutor design (same pattern applies here).

### Attachments (`alpi/attachments.py`)

`host.chat.send` accepts `attachments: [{path, mime?, name?}]`. The engine validates them (`att.validate` — magic-byte sniff for image/PDF, NUL/control-ratio guard for binary-as-text, per-type size caps, allowlist: images `png`/`jpeg`/`webp`, PDF, and text/source incl. `py`/`js`/`ts`/`tsx`/`go`/`rs`/`sh`/`sql`) and turns them into OpenAI content-parts (`build_content_parts`): images → base64 `image_url` data parts, text/source → inline text parts, PDFs → text extraction (bounded by `tools.attachments.max_text_tokens` → chars at ~4/token; default auto = half the active model's context window, no page cap). A **scanned** PDF (extractable text below `SCANNED_PDF_TEXT_FLOOR`) falls back by model capability: vision-capable → rendered page images; text-only → **RapidOCR** text (capped at `SCAN_MAX_PAGES`), so a profile with no knowledge base and no vision can still summarize a scan. PDF text/render/OCR mechanics are shared with the knowledge tool via `alpi/extract.py`. Images on a text-only model are **not** OCR'd — they degrade to a path note telling the model it can't see them. A guidance text-part tells the model the files are inline so it doesn't reflexively call filesystem or knowledge tools to "find" them.

**Per-turn only.** Bytes live only in the in-memory message. `session_metadata` is itself bytes- and **path-free** (`{name, mime, size}`), but the engine re-adds a **best-effort local `path`** to each persisted chat-turn attachment so clients can thumbnail history — the path may be unfetchable from another client (outside `host.attachments.fetch` roots) or after a staged file's TTL, so this is preview replay, not durable storage. The validated turn attachments (`{name, path, mime}`) are also published to a runtime-only `ContextVar` (`tools/_state.set_turn_attachments`) so a tool can resolve a turn's files. Remote clients (mobile, or desktop pointed at a remote daemon) can't hand the daemon a local path, so they upload bytes via the `host.attachments.stage` RPC (type-aware caps, content validated 1:1 with send) which writes to a TTL-swept temp dir and returns a daemon-side path. `host.attachments.fetch` serves a remote member only what its connection staged (a `.owner` marker beside the upload; a missing, unreadable or malformed marker refuses access) or a path that appears in a session its connection owns, and under `session_scope: device` only its own device's: a turn's `attachments` or `output_attachments`, a tool's args or result, or the assistant's text, never a path the user typed (a path the user also wrote is not offered even if the agent repeats it), and only exact paths: a file named only in the assistant's text with a space or a parenthesis in its name is not offered, and one the agent lists or reads on its own becomes offered. `alpi/host/offered_paths.py` keeps that set per session and rebuilds it only when the session file changes. Admins and the Unix socket are not narrowed, and the roots and the secrets denylist still apply first. `host.chat.send` applies the same owner rule to a remote member's attachments: only an upload its connection staged (its device too under `session_scope: device`) can be attached, and a missing, unreadable or malformed marker refuses it; a remote admin is checked against the staging area only.

**Durable.** `knowledge(action="ingest")` is the bridge from per-turn input to permanent knowledge. It reads an attachment or source file, synthesizes Markdown pages under `<workspace>/knowledge/`, updates `index.md` / `log.md`, and refreshes the profile-local derived index in `knowledge.sqlite`. The raw source is not copied into a durable documents directory. There is **no auto-learn**: attachments stay one-turn unless the user explicitly asks to learn/remember/save/index/compile one.

### Vision (`alpi/tools/read_image.py`)

`read_image(path, question)` runs the current (or override) model in multimodal mode on an image and returns a text answer. `path` can be a local file OR an `http(s)` URL — URLs go through `check_url()` for SSRF (metadata hosts + private IPs blocked, redirects re-validated via httpx `event_hooks`).

Magic-bytes sniff accepts PNG / JPEG / GIF / WebP / BMP plus SVG (text-sniff for `<svg`); rejects bytes that don't match a known header even if the extension agrees. 20 MB cap on file and on download payload.

No pre-flight vision-capability check — LiteLLM's `supports_vision()` is wrong for `openrouter/...` prefixes and would bounce real vision models. If the call fails we surface the error with a hint pointing at `/model` when the message mentions image / vision / multimodal.

**Model override** via `tools.read_image.model` in config (surfaced as Vision
model by `alpi setup`, desktop and mobile). When set, `read_image` and browser's
opt-in screenshot analysis try the override first; on failure the tool retries
with the main model and prefixes the answer with `[fallback: <override>
unavailable, used main model]`. Clearing it restores main-model fallback. This
route is deliberately tool-scoped: chat image attachments are multimodal parts
of the main turn and are not silently moved to the override.

Same usage / cost plumbing as research and delegate. Images are auto-resized before upload (see CONFIG.md → `tools.browser.vision`).

### Delegate (write-capable sub-agent, `alpi/tools/delegate.py`)

Sibling to `research`, but can mutate: spawn a focused sub-agent with a chosen toolset, get back a summary. Used when a task would otherwise flood the parent context (multi-file refactors, fetch+parse+write pipelines, skills that generate several output files, iterative debug loops).

**Toolsets** (callable presets via the `toolsets` param, default `["file", "web"]`):
- `file` → `read_file`, `write_file`, `edit_file`, `search`
- `terminal` → `terminal`
- `web` → `web_search`, `web_fetch`, `web_extract`

**Blocked for sub-agents**: `delegate` (no recursion), `memory`, `skill`, `schedule`, `notify`, `email`, `session_search`, `session_read`, `todo` (shared global state). `research` is not in any preset either — if you need deep investigation inside a delegate task today, do it in the main agent first and pass findings via `context`.

**Budget**: `max_steps` is a per-call tool parameter, defaulting to 30 and clamped to `MAX_STEPS_CAP = 100`; a non-positive or unparseable value falls back to the default. It's a ceiling, not a target — the sub-agent stops when done.

**System prompt** is built from a single template plus the workspace root (when set): relative paths resolve under workspace, absolute paths go where the goal says, and the sub-agent is explicitly warned not to invent `/workspace/...` style roots.

**Prompt-cache contract.** `messages[0]` is the stable system prefix and tool
schemas are sorted by name. Volatile `# NOW`, workgroup, skill-hint, and relay
state is composed once into the user turn's persisted `host_context` suffix,
so normal history growth is append-only across live calls and every rehydrator.
OpenRouter calls carry a hashed affinity for the logical conversation; other
providers receive no OpenRouter-only fields. `prefix_diag.py` compares bounded
request-shape hashes per conversation and records causes, never prompt text.
Caching and diagnostics are best-effort and cannot fail a provider call.

**Batch parallel mode.** Both `research` and `delegate` accept `tasks: [...]` (up to 3) and run them concurrently via `ThreadPoolExecutor(max_workers=3)`. Isolation is provided by `_state.py`: `_emit`, `_interrupt_getter`, `_usage_sink` are `contextvars.ContextVar`, so each worker thread sees its own values without racing on module globals. Workers re-seed `interrupt_getter` + `usage_sink` from the parent context (Python's `ThreadPoolExecutor` doesn't propagate ContextVars automatically) and install a per-task prefixed `emit` so TUI progress lines read `[i/N] <tag> · <msg>`. Results aggregate into one markdown report with per-task sections; per-task failures are captured inline as `[failed: <error>]` instead of aborting the batch. Cap is hardcoded at 3 — bumping would need a config knob *and* would multiply LLM cost linearly; not a default worth moving.

### TUI (`alpi/tui/`)

Textual 8.2.x. Layout: `AlpiTopBar` (identity: version, profile, workspace) + chat scroll (`VerticalScroll.anchor()` auto-follows new content) + a bottom dock holding the completion popup, the multi-line composer (`ChatInput`, a `TextArea`) and the `StatusLine` (model · ctx % · cost · budget · sandbox · unread inbox · prompts waiting, then context-aware key hints).

**Theme** (`themes.py`): `build_theme(accent, dark)` returns a Textual `Theme` whose background, surfaces, ink and status colours come from `alpi/palette.py`, a mirror of `common/tokens.mjs` kept honest by a parity test. `surface` (the chat input, floating panels, code fences and table heads) is the `fill` tone, `#262626` dark and `#f2f2f2` light, so it never equals the background; `panel` is `bgElev` in dark and `fill` in light, where `bgElev` is the background itself. Every grey of both themes, in the console and in the apps, is an equal-channel neutral, so the only colour on any surface is a profile's. `palette.resolve_accent` maps an unset or legacy brand accent (`#c8a24e`, `#8a5a0a`) to the mode's token (`#f3efe6` dark, `#14110c` light, the brand ink); a chosen colour, amber included, is kept. The console (`ui.py`, `alpi profile list`) goes through the same resolver. Registered in `AlpiApp.__init__` (not `on_mount` — child widgets read `theme_variables` during their own mount).

**Marks in the console**: the console wears the same identity as the apps. `python3 scripts/sync_marks.py` generates `alpi/mark_shapes.py` from `common/agentMarks.mjs` and `common/workgroupMark.mjs` (outlines flattened to polygons, eye positions, expressions, the still pose per state, the honeycomb cells) plus `LEGACY_SHAPE` from `design/src/agent_marks.py`; `--check` fails when the generated file is stale, and the pre-commit hook runs it whenever one of those sources changes. `alpi/fold_art.py` rasterises a mark into half-block cells (`▀ ▄ █`, two pixels per cell) in one flat colour with the two eyes of the idle still pose filled in the paper ink of the console theme (`palette.EYE_INK`, white on light, black on dark, parity-tested against `markEye`; the eye cells are a half block with that background): a profile's mark is its `tui.shape`, in its accent's body tone (`fold_art.body_colour`, the same `markTone` as the apps: a pale accent a step deeper on light so the white eyes hold 3:1, the accent itself on dark); the default profile is Twin (`alpi-twin`, `alpi-twin-small` below 24 px) in the brand ink of the theme (`palette.BRAND_INK`, parity-tested against `common/shapes.mjs`), never an accent; the workgroup honeycomb draws its three cells. The art sits beside the title of the `alpi setup` menu and beside `alpi profile show`, whose name line uses `name_colour` (the same `nameTone` as the apps: the accent one step darker on light, lighter on dark, at least 4.5:1). A one-cell marker in the accent marks the active entry in `alpi profile list`, the TUI list rows and the status line, picked from a glyph map (round `⬤`, squircle `⯀`, drop `⧫`, dome `⯊`, pill `⬮`, clover `✤`, cloud `ɷ`, bean `◗`, pebble `⬬`, arch `⋂`, heart `❥`, bell `⍾`, honeycomb `⬢`, Twin `⍥`). Only a UTF-8, truecolor TTY without `NO_COLOR` draws marks; anywhere else every mark falls back to the single-colour `◆` (and `◇` for an inactive profile). Menu cursors (`ui.POINTER`) and the tool-hint chip are status marks and stay diamonds. `alpi/appearance.py` names a pair by colour and shape (`blue bell`; the default profile is `twin (brand mark)`); `/shape [shape] [colour]` accepts the shape names only (`/shape bell blue` saves `bell`; `/shape shield` is refused), `alpi setup → Appearance` lists the shapes by name, both save the shape name in `tui.shape`, and both refuse the default profile ("the default profile always wears the alpi brand mark in the brand ink").

**Steps** (`StepsGroup` / `ToolCard` in `widgets.py`): each turn's tool calls collapse into one `▸ N steps · Xs` row that shows the live step while running. It expands to one card per call: a family glyph (file, terminal, globe, search, link, memory, chip — `tool_hints.tool_family`), the argument summary, the result hint and the duration; a card opens to the pretty-printed arguments and an output excerpt. A failed call stays closed like any other; the group head counts it (`N failed`). `ask_user` answers render as their own line, not as steps. `Ctrl+O` toggles the last turn's reasoning and steps.

**Assistant streaming**: `AssistantMessage` streams into a cheap `Static` (flushed every 150 ms) and swaps to a `Markdown` widget once when the reply lands. Very long user messages render as plain text instead of Markdown.

**Reasoning surface**:
- While the model thinks, the spinner reads `Thinking…` with elapsed seconds (`Preparing a step…` while tool calls stream).
- When the first tool call or answer token arrives, reasoning deltas and any pre-tool prose collapse into one `▸ Thought for Xs` row per turn (`ReasoningBlock`), expandable to the text. Live turns time it in-process from turn start; replays use `Turn.reasoned_s` and the consolidated `Turn.reasoning` (same segment dedupe as `common/reasoningSteps.mjs`).
- `tui.show_reasoning` (default `true`) hides the block when `false`; data is still persisted, the engine still emits.

**Persistence contract** (cross-surface). The engine consolidates the whole turn's reasoning — `reasoning_delta` thinking + the inter-tool prose — into **`Turn.reasoning`** (str), and records **`Turn.reasoned_s`** (float) = the reasoning span from turn start to the first tool boundary, or to the first final-answer text token when there are no tools; it **excludes both tool execution and final-answer streaming** so the duration isn't inflated by a long-running tool or a long reply. Desktop, mobile and the TUI render a collapsible "Thought for Ns" block from `Turn.reasoning`, falling back to joining `ToolLog.reasoning` for turns logged before the field existed. `ToolLog.reasoning` (first tool of each batch) remains the legacy per-tool fallback.

**Slash commands** come from one registry (`alpi/tui/commands.py`) that drives `/help` and the completion popup (`/` or `@peer`, with descriptions): `/help`, `/activity`, `/status`, `/model`, `/new`, `/clear`, `/compact`, `/sessions`, `/outputs`, `/runs`, `/memory`, `/skills`, `/tools`, `/mcps`, `/peers`, `/diff [since]`, `/shape [shape] [colour]`, `/attach <path>`, `/attachments`, `/clear-attachments`, `/quit` (alias `/exit`). Panels are `FloatingPanel`s on the overlay layer docked above the composer, dismissed by Esc or click-outside. `/activity` calls `host.activity.list` over `host.sock` (needs you / running / scheduled) and answers listed approvals and questions via `host.approval.respond` / `host.clarification.respond`; without a daemon it says so. Configuration verbs (workspace, email, sandbox, …) live in `alpi setup` — the TUI is for chat and inspection.

**Approvals and questions** raised by the in-process engine are prompt panels that cannot be dismissed by a click or by opening another panel. They queue (the first shows `+N queued`), show a live countdown to the engine deadline (60 s approval, 300 s question), and Esc answers deny / cancel immediately. A prompt that times out, shown or still queued, leaves a line in the transcript.

**Interrupt**: sending a new message, Esc, or Ctrl+C stops the running turn; each also resolves any open prompt so the tool thread never blocks. `engine.interrupt_requested` is polled at 3 points; long-running tools (`research`) poll `tool_state.is_interrupted()`. Skipped tool calls get a `[skipped — user interrupted]` tool message to preserve OpenAI's pairing invariant. `/quit` interrupts first, then exits. `/clear`, `/new` and `Ctrl+L` refuse while a turn runs.

**Keys**: Enter sends; Ctrl+J (or a trailing `\` then Enter) adds a line — Shift+Enter too on terminals that report it (CSI-u); pasted newlines are kept; ↑/↓ recall sent messages from an empty composer; Tab completes. Esc answers a prompt, closes the popup or a panel, or stops the turn. Ctrl+C stops the turn, and quits on a second press within 2 s. Ctrl+O toggles details, Ctrl+L starts a new session (same as `/clear`), Ctrl+Y copies the last reply (pbcopy/wl-copy/xclip/xsel/OSC-52 fallback chain).

### Daemon (`alpi/service.py`)

One alpi daemon per machine, every profile inside. A single
launchd plist (`com.alpi.daemon`) on macOS or systemd-user unit
(`alpi-daemon.service`) on Linux supervises one Python process
that hosts every profile under `~/.alpi/` (default plus each
`profiles/<name>/`) on the same asyncio loop. Per-profile tasks are
independently guarded — a crash in one profile's scheduler leaves
siblings untouched. Tasks are named `<profile>/<capability>` (e.g.
`doc/schedule`, `builder/alp`) so logs + `asyncio.all_tasks()` stay
readable. These are internal capabilities, not configurable services:

- **schedule** — cron tick loop.
- **alp** — ALP **listener** (inbound). Serves the full protocol
  on a Unix socket plus optional Noise_XK on TCP: `link.ping`,
  `link.ask`, `link.cancel`, `link.put_blob` / `link.get_blob`
  **and** every `workgroup.*` verb.
- **workgroups** — the **poller** (outbound). Holds `workgroup.pull` open
  for active subscriptions, uses staggered nonblocking probes for idle
  or paused mirrors and 15-minute probes for subscriptions with no post
  in a day (the hub poller on the same daemon wakes them through
  `alp/wakes.py` when it sees the transcript move; a remote hub's members
  wait for the next sample), decrypts new posts, and dispatches an autonomous
  agent turn when a post mentions this profile or opens a `#task`.
  Sibling preempt watcher ticks ~6× faster to abort in-flight
  responses when a new `#task` lands. Independent from `alp`
  because direction and lifecycle are different — outbound vs
  inbound, periodic vs reactive — so a poller crash (timeout
  against a dead hub, decrypt failure on a malformed post) doesn't
  take the listener down. Workgroups is ALP; this task is its client half.
- **host** — *default profile only*. The control-plane Unix socket
  (`~/.alpi/host/host.sock`) the desktop / mobile client uses to
  drive the daemon. Refused on non-default profiles fast — the
  client always targets default's socket and reaches sibling
  profiles via the `profile` param on each verb.

Before starting a profile's capabilities, the daemon binds legacy QA rewind counters
and retained checklists to that workgroup's latest pipeline trigger. Workgroups without
a `meta.yaml` are pruned from these tables. Trigger admission also migrates before opening
a new run, including when the daemon is stopped. A workgroup whose run cannot be read keeps
its state untouched without holding back the profile, and a trigger on it is refused.
Hub post validation, baseline hashing and transcript admission run in a worker thread
under one transcript lock. Peer post admission and cost settlement also wait for that
lock outside the event loop, and a peer post re-checks membership and pause under the
lock. Baselines include generated output files the phase's globs own, excluding Git
internals, `.astro` operational logs and non-regular files.

All capabilities start for every profile; the host plane is default-only.
Jobs and workgroups retain their own enabled/paused state, and access control
lives in peer grants and connection roles/scopes.

`alpi.service.serve_all(root)` is the foreground entry point
called from `alpi daemon start` and from the supervising unit's
ExecStart. It:

1. Walks `~/.alpi/` (default + every `profiles/<name>/`) to
   discover profiles.
2. Configures the root logger at `~/.alpi/logs/service.log` (stderr
   only when it's a TTY, to avoid double-writes under launchd).
3. Sets the process title to `alpi (daemon, N profiles)` via
   `setproctitle`.
4. Writes `~/.alpi/service.pid`.
5. Spawns the fixed task set for every profile and waits. `_guard_task`
   wraps each one so a crash leaves siblings
   running.
6. SIGTERM / SIGINT cancels every task cooperatively; PID file
   removed on exit.

**PID 1 (`alpi/pid1.py`).** Inside the image `alpi daemon start` is PID 1
(`ENTRYPOINT ["alpi-docker"]`, no init). Before anything else it forks: PID 1
stays a minimal init — `waitpid(-1)` in a loop, SIGTERM / SIGINT / SIGHUP /
SIGQUIT / SIGUSR1 / SIGUSR2 forwarded to its only child, exit code mirrored
(128 + signal on a signal death) — and `serve_all` runs in the child, which
owns `service.pid` and `service.lock` as before. Every orphan in the container
(an exited `npx` wrapper chain, a `docker exec` session, the grandchildren of a
hard-killed turn) reparents to PID 1 and is reaped there, each one logged to
stderr. The reaper is deliberately not inside the daemon: a `waitpid(-1)` in
that process would steal exit statuses from `Popen.poll()` / `wait()` and from
asyncio's child watcher, which then report 0 or 255 for a child they never
saw exit. Outside a container `os.getpid() != 1` and the fork is skipped.
`pytest` covers the fork, the forwarding and the exit-code mirror; the PID 1
case itself runs in `publish-docker.yml`, which starts the built image,
leaves an orphan through `docker exec`, asserts no zombie remains and that
`docker stop` returns the daemon's exit code.

**Operational invariants of `serve_all`** (each one is the root cause of a real production incident; do not regress):

- `~/.alpi/service.lock` is held under an OS-level non-blocking lock (`fcntl.flock` on Unix, `msvcrt.locking` on Windows) for the daemon's lifetime; this guarantees one daemon per installation. A second `alpi daemon start` exits with a warning instead of racing the existing one.
- `~/.alpi/host/host.sock` is published BEFORE the TCP plane is resolved or enabled. TCP bind work (`resolve_host_tcp_bind`, `server.enable_tcp`) runs off-loop via `asyncio.to_thread` and is non-fatal — a TCP failure leaves the Unix socket up, so the local desktop (which talks to the daemon over `host.sock`) keeps working when network detection (Tailscale, LAN) is slow or blocked. Mobile and any remote desktop go through the WebSocket transport and *do* need TCP to come up.
- ALP TCP is auto-bound only on `default`, or on a profile with its own explicit `alp.tcp_port`. Other profiles stay Unix-only — otherwise every named profile would fight `default` for the same port.

**Active home isolation.** Because N profiles share one process,
tools that resolve their home via `home.get_home()` would all see
the same env vars and write to default's home. The engine wraps
each `run_turn` in a `home.set_active_home(self.home)` contextvar
binding (per-thread); `get_home()` consults this binding before
the env. Without it, another profile's memory tool would write to default's
`USER.md`. See `tests/core/test_home.py` for the isolation tests.

`daemon_status(root)` is the snapshot used by `alpi daemon status`
and by `alpi setup → Services → Daemon`: PID, uptime (via `ps -o
etime`), install backend (launchd / systemd / none), and the
per-profile services map.

### Host plane (`alpi/host/`)

Control-plane for the desktop / mobile client. **Not** ALP — the
two share a profile but live on different sockets, with different
auth models. ALP is peer-to-peer (Noise on TCP, envelope-signed,
peers pinned in `peers.yaml`); host is client-to-daemon. JSON-RPC-shaped
over `~/.alpi/host/host.sock` with filesystem permissions as the trust
boundary; no peer identity, no envelope, no Noise handshake. Desktop
and mobile talk to this API; they do not read profile files directly.

Only the `default` profile hosts this plane — the client
always targets default's socket and reaches sibling profiles via
the `profile` parameter on each verb. `_run_host` refuses to bind
on any other profile even if the toggle leaks via manual config
edit.

`host.device_state` owns the device-facing profile state contract:
profile lists/summaries, bounded profile file reads, storage stats,
email status/config previews, skill lists, workgroup lists, workgroup
member rosters, config field edits, and local Ollama model discovery.
The desktop Tauri layer keeps its existing `invoke(...)` command names
for UI stability, but those commands proxy to `host.*` verbs instead of
parsing `~/.alpi` themselves. Mobile should use the same verb shapes
rather than inventing a separate state API.

Two transports, one dispatcher:

1. **Unix socket** (`~/.alpi/host/host.sock`, mode 0600). Local
   trust = filesystem perms. Used by desktop on the same machine.
   No token required.
2. **WebSocket** (`ws://<bind>:49200` by default). Used by mobile
   and any remote desktop. `network.host` drives the direct bind/address;
   the *bind* is derived from it (see `config` / `security`): empty →
   auto-detected Tailscale CGNAT (`100.64.0.0/10`) then private RFC1918
   LAN; a private/Tailscale IP → that IP; a hostname or an opted-in
   public IP → `0.0.0.0` (all interfaces); a public IP without
   `host.allow_public_bind` → refused (no TCP); Docker → `0.0.0.0`.
   Loopback is never a bind target. A `0.0.0.0` bind leans on the
   device token (and a firewall/NAT) for access control, so `alpi
   doctor` warns whenever the listener binds `0.0.0.0`. **Per-device token
   required** in every authenticated request's `params.auth_token`.
   `permessage-deflate` is negotiated by default
   (`ws_serve(compression="deflate")`); JSON-RPC payloads drop
   50–80% on the wire. Clients that don't negotiate fall back to
   raw. Mobile and desktop keep a persistent multiplexed WS pool
   per `(URL, token)` so RPCs don't pay a TCP+WS handshake
   every call — the dominant cost of "remote alpi feels slow" on
   Tailscale. Streams (`host.chat.send`, `host.events.subscribe`)
   open their own dedicated socket.

Bind and advertised routes are intentionally separate concerns.
The daemon chooses where the host-plane server listens; `Connections →
Network` stores an ordered `host.endpoints` list of complete `ws://` or
`wss://` URLs and chooses what the paired client should dial. Plain WS requires
a private IP literal; hostnames require WSS, and synthesized routes
pass through the same validator. WSS terminates
at a certificate-validating reverse proxy and forwards to the same daemon
listener; it does not create another authorization plane. On a normal Mac or
Linux install those often collapse to the same private address.
In Docker they do not: the daemon binds `0.0.0.0` inside the container
while the QR advertises a configured `host.endpoints` route or a safe private
IP derived from `ALPI_NETWORK_HOST`.

Wire shape (both transports):

```
{"id": "<reqid>", "method": "host.<noun>.<verb>", "params": {…, "auth_token": "<token>"}}
```

Unix socket payload omits `auth_token` — the local transport is
sovereign and bypasses token validation entirely. WS requires a valid token
except for one exact bootstrap verb: `host.connections.exchange_pairing` may
redeem a locally-created, high-entropy grant once and then the daemon closes
that socket. An empty or missing `connections.yaml` rejects every ordinary WS
request (fail-closed). The connection, role, profile scope and grant are
created locally over the Unix socket; remote bootstrap cannot choose them.

The daemon writes either a single response line or, for streaming
verbs (`host.chat.send`, `host.events.subscribe`), multiple frames
followed by a `done` frame and connection close.

This is distinct from ALP peer transport. `Connections` / host-plane remote
access configures how paired desktop and mobile clients reach their own
daemon (`host.*`). `Peer TCP listener` configures the optional ALP TCP
listener other alpis use for `link.*` and `workgroup.*`.

#### Connections and device credentials (`alpi/host/connections.py`)

The store lives at `~/.alpi/host/connections.yaml` (mode 0600). A connection
is the operational identity: `{id, label, role, profile_scope, status}`. Its
`devices[]` each hold the SHA-256 digest of a separate opaque token
(`token_hash`; the cleartext exists only on the client) plus self-reported
client/name/version metadata and `last_seen`. Auth hashes the presented token
before the constant-time compare, so a copy of the file is not a credential.
Desktop and mobile may therefore share one
connection, its sessions and accounting, without sharing a credential.
`pairings[]` holds only hashed temporary grants and lifecycle metadata. A
pending grant expires after ten minutes; the first exchange marks it consumed
and appends exactly one device under the same file lock. Terminal metadata is
kept for seven days, capped at 50 entries per connection, and omitted from
`host.connections.list`.

The daemon resolves each token to `{connection_id, device_id, role,
profile_scope}` and binds that identity to the request context. A hit bumps
the device's `last_seen` at most once per minute. The engine persists
`connection_id` on new sessions; session list, read, continue, cancel and
delete reject sessions owned by another connection. The daily ledger records
input/output tokens and USD under `by_connection`; the run ledger records both
IDs. Local Unix/TUI/CLI activity uses the synthetic `host` connection.

Sessions also persist `device_id`. A connection's `session_scope` decides
whether that matters: `connection` (the default) shares every session among the
connection's devices; `device` lets a remote device list, read, continue,
cancel and delete only the sessions it created, drops other devices'
`session_changed` frames from its event stream and history, serves each device
its own `latest_session` preview in `host.profile.summaries` (the summary cache
is keyed by connection, device and profile), and narrows the agent's
`session_read` / `session_search` / `recall_sessions` tools the same way. Every session
records its device whatever the scope, so switching to `device` also hides a
device's earlier sessions from its siblings; sessions without a `device_id`
(saved by alpi before 0.15.20, or started by the daemon itself through the
scheduler or `host.chat.delegate`) stay visible to every device of the
connection. `ask_user` clarifications and command approvals carry the owner of
the turn that raised them: `host.clarification.pending` / `host.approval.pending`,
their `respond` verbs and the `clarification.*` / `approval.*` events follow the
same rule for member devices. Remote admins also receive, list and answer prompts
only from their own connection, but share them across its devices regardless of
`session_scope`. Prompts without an owner are hidden from remote event streams and
history. The local socket can still handle every connection's prompts. Other
admin-role session reads are unaffected. A device
flagged `provisioner` (minted from a pairing grant that carried the flag) may
call `add_device`, `pairing_status`, `cancel_pairing` and `revoke_device` for
its own connection without the admin role; it cannot grant provisioning, revoke
itself, or reach any other admin verb.

Sensitive mutations pass through one dispatcher audit boundary after their
handler returns. `admin_audit.py` writes only allowlisted identifiers and the
stable error envelope; it never serializes request params or handler results.
The bootstrap pairing exchange replaces its temporary context with the newly
created connection/device identity before writing. Authenticated admin denials
are recorded at most once per device/method/minute; invalid unauthenticated
traffic stays in operational metrics/logging so it cannot churn durable audit
history. `host.audit.list` is local/admin-only, cursor-paginated and filters an
identity whether it acted or was the target.

This boundary covers calls through `host.sock` and authenticated WebSockets.
Direct CLI/setup code paths still mutate their stores without crossing the
dispatcher and are explicitly tracked as remaining AUDIT.2 coverage rather
than being represented as synthetic host-RPC events.

Three trust tiers gate every WS call:

- **Unix socket** — sovereign. Used by the local CLI and the
  desktop running on the same machine; bypasses every role check.
- **WS admin** — full app-level CRUD + connection/device management
  (`host.connections.*`).
- **WS member** — chat, events, read-only views, schedule listing,
  workgroup post/read, voice preview, deleting its own chats
  (`host.sessions.delete` only removes sessions owned by the calling
  connection; any other id answers `not-found`). Admin verbs reject with
  `-32001 forbidden / "admin role required"`. A member's turn runs on the
  profile's model: `host.chat.send` answers a `model` override from a member
  with an `error` frame (`code: forbidden`), and `host.profile.detail` keeps
  only `voice_id` and `voice_auto_read` for a member (`models` is admin
  detail, as is `host.providers.ollama_models`), so the model, its reasoning effort, the budget and the skills are
  changed only by an admin; a member uses the skills the profile has.

The admin set lives in `_ADMIN_METHODS`; the strictly-local set
in `_LOCAL_ONLY_METHODS` (network admin only — no role unlocks
those over WS).

Lifecycle:

- **Create connection**: `host.connections.create(label, role, profiles,
  session_scope?)` creates the parent identity and a ten-minute one-time grant.
  The grant is embedded in the QR/link shown by `alpi setup → Connections → New
  connection`. The default role is `member`; the default scope is `connection`.
- **Add device**: `host.connections.add_device(connection_id, provisioner?)`
  creates another one-time grant under the same parent identity. `provisioner:
  true` needs the admin role and marks the device the grant mints; a
  provisioner device may call this verb, `pairing_status`, `cancel_pairing`
  and `revoke_device` for its own connection.
- **Exchange**: the client sends `host.connections.exchange_pairing` as its
  first unauthenticated WS message. The daemon atomically consumes the grant,
  creates the permanent device credential with its client/name/version
  metadata, returns it once and closes the bootstrap socket. Reuse returns
  `-32011 pairing-used`; expiry returns `-32011 pairing-expired`.
- **Observe / cancel**: local/admin callers use
  `host.connections.pairing_status` and `host.connections.cancel_pairing`.
- **Update / disable**: `host.connections.update` changes label, role,
  profile scope or session scope. `host.connections.set_status` disables or enables every
  linked credential without deleting sessions or usage.
- **Use**: every WS request carries `auth_token`. Fail =
  JSON-RPC `{code: -32000, message: "auth-failed"}` and the
  connection closes; the mobile app's auth-failed handler wipes
  its endpoint and bounces back to the pair screen.
- **Revoke / delete**: `host.connections.revoke_device` invalidates one
  device. `host.connections.delete` tombstones the parent and clears every
  linked token while retaining historical session/ledger attribution.
- **Policy change**: every WebSocket remembers the `role`, `profile_scope` and
  `session_scope` it authenticated under, and the authorization watcher closes it with `1008
  "Authorization changed"` on its next pass (`ALPI_HOST_WS_AUTH_RECHECK`) once the stored
  connection differs, whoever edited it: `host.connections.update`, the legacy `host.devices.*`
  verbs or `alpi setup connections`. An open stream, `host.events.subscribe` included, never
  outlives the policy it was opened under; clients reconnect and get the new one. A running chat
  turn on the closed socket is interrupted like on a revocation. A label-only or same-value
  update leaves sockets open. The one exception is the socket that carries the policy-changing request itself (`host.connections.update`, `host.devices.promote|demote|set_profiles`): it stays open for at most two seconds so its own response goes out first; every other socket of the connection, streams and pending calls included, closes on the next pass.
- **Per-device socket limit**: a device credential may hold `ALPI_HOST_WS_MAX_CONNECTIONS_PER_DEVICE`
  sockets. A socket that would exceed it pings the device's existing ones first and evicts those
  that do not answer within two seconds (ping and pong share one deadline; the transport is
  aborted, no close handshake; `stale_connections_evicted` in `websocket_status()`), because a
  client that lost its network leaves half-open sockets registered until the keepalive fails.
  A device whose sockets all answer is refused with `-32029 too-many-connections`.

The daemon migrates the credential store at startup, before it opens the
WebSocket listener: a legacy `devices.yaml` becomes one connection per row
with hashed tokens, a pre-0.14.39 `connections.yaml` is rewritten once with
`token_hash`, and the source is deleted only after the destination has been
re-read and verified. A corrupt or empty store is an explicit error, never
zero connections, and a failed migration keeps the WebSocket listener down.
Rolling back below 0.14.39 is not supported. Leftover copies are listed by
`alpi doctor`; [OPERATIONS.md](OPERATIONS.md) has the removal procedure.

`host.devices.*` remains as a compatibility RPC alias for older management
clients; generated payloads use the new one-time grant contract. Desktop and
Mobile continue to consume old QR/link payloads that contain a final `token`.
All new management uses `host.connections.*`.

Verb namespaces in current shape:

- **`host.sessions.list`**, **`host.session.read`** — read-only.
- **`host.audit.list`** — local/admin-only paginated administrative activity;
  never returns credentials, values, payloads or chat content.
- **`host.workgroup.transcript`** — read-only,
  `{after_seq?, limit?, tail?}` → `{posts, next_seq, limit}`.
  Without `after_seq` the default is `tail=true` so first-paint of a
  long-lived workgroup ships the recent window, not the oldest 200.
  `decrypt_transcript` opens the hub sealed group key once outside
  the per-post loop (was O(N) Curve25519 unseals per fetch).
- **`host.workgroup.tasks`** — canonical task and pipeline state. Its fold runs through
  `host.read_pool.run_read`, on the same four-worker executor as roster reads, with the
  caller's context variables preserved. Engine turns, gates and transcript loads use the default
  executor and cannot occupy those workers. Desktop and mobile request task state independently
  of the transcript and can render the pipeline while transcript loading remains pending.
- **`host.profile.summaries`** — lightweight inbox/sidebar shape:
  `name`, `model`, `accent`, `shape`, `latest_session`, `counts`, `budget_*`,
  `pubkey_b64`, `has_any_provider`. `counts.sessions` uses the same `owns_session_row` filter as the
  session list and `latest_session`, including remote admins: connection ownership always applies,
  and `session_scope: device` narrows remote devices while retaining deviceless sessions of that
  connection. Local requests count host-owned and legacy ownerless sessions without a device clause.
  Detail and settings snapshots do not carry a session count. A profile's identity is its `shape` in its `accent`, and the apps
  draw it wherever a profile is identified (status marks stay diamonds). `shape` is the stored and transmitted value, one of the
  twelve names in `SHAPE_ORDER` (round, squircle, drop, dome, pill, clover, cloud, bean, pebble, arch, heart, bell; a missing or
  unknown one is `round`), saved as `tui.shape` in the profile's `config.yaml`. Input takes shape names only:
  `host.config.set_field` takes `tui.shape` with one of the twelve names and stores it; any other value (an old origami id
  included) is `-32602 invalid-params`, and the old key `tui.fold` is refused with `-32602` by `set_field` and `unset_field`.
  The only legacy handling is on read: a config that still stores `tui.fold` is translated and never rewritten by loading it
  (`config.translate_shape` and `appearance.stored_shape`, through `palette.legacy_shape` and the `LEGACY_SHAPE` map in
  `alpi/mark_shapes.py`: `round` when unknown, `twin` on the default profile, a `tui.shape` already set wins); saving the
  shape (`set_field`, `/shape`, setup) writes `tui.shape` and drops `tui.fold`, and unsetting `tui.shape` drops both,
  keeping every other key. The summaries send `shape` and never `fold`; the clients read `shape` only and draw `round` for a
  missing or unknown value (`profileShape` in `common/shapes.mjs`). The UI names a profile by colour and shape
  (`pairName` in `common/accents.mjs`: bell in blue reads "blue bell"). The twelve colours (all hues, no grey, so no profile
  reads as the ink of Twin; the `nearestAccent` map from any stored colour, with the retired grey `#7e8792` read as sky) and
  `ACCENT_SHAPES`, the shape each colour is seeded with, live in `common/accents.mjs`. A new
  profile (`host.profile.create`, `alpi profile create`, or any first bootstrap of a home under `profiles/`)
  is seeded with the next pair of a fixed roulette (`appearance.ROULETTE`): the least worn colour among the
  existing profiles, in roulette order, with its own shape, so no pair repeats until all twelve are worn. The default profile (the host-plane one, never one under `profiles/`) is not one of the twelve: its
  summary always reports `shape: "twin"` and no `accent`; the apps draw Twin for it in
  the brand ink of the theme (`defaultAsTwin` in `common/shapes.mjs` gives it that shape whatever the daemon reports), show its
  appearance read-only, and `host.config.set_field` refuses `tui.shape` and `tui.accent` for it. A roster mark carries the
  row's state (see Mark states below): paused draws the dashed neutral outline with no fill and a profile without a provider reads
  needs; on the phone the whole roster reads offline (the flat still mark at 30 % opacity) while the active
  connection is offline, disabled, auth-failed or rate-limited; the desktop leaves the marks alone for an outage, because its
  banner owns the offline state. Such rows stay openable, a paused name in a header reads in grey, and a stale working state is dropped. From `host.activity.list` a row reads needs you over failed (a job whose last run failed in the last day) over working, and a failed job whose `job_id` has a running turn again reads working. The daemon lists the default profile first, and both clients keep it there: `common/rosterOrder.mjs` splits it
  (`is_default` or the name `default`) out of the list, and the desktop sidebar, the phone roster and the Fold draw it as the
  unlabelled first row above Pinned, dimmed when paused or without a provider, never pinnable (a stored `default` pin is
  ignored), never behind *Show N more*, kept under a filter only when it matches like any other row (the desktop checks its
  name and the `alpi` label, the phone also its last message), and absent when the
  connection does not list it; ⌘1 on the desktop opens it. The desktop has no start screen: startup, a connection
  switch and a deleted open profile land on the first profile row's latest session once the live roster has answered
  (on the cached one only while the connection is offline; with no profiles, the empty roster state), and closing
  Settings returns to its profile or the previous view only when the active connection still serves it; a new session starts from a profile (its row menu, the Sessions menu, or ⌘N, which outside a profile uses the
  last profile seen on the connection or the first row), and ⌘K opens on New session, highlighted, with the recent sessions across profiles below it. No peers/models/
  mcps/provider_keys/sandbox/voice — those live in **`host.profile.detail`**
  (`{workspace, tcp_port, advertise_host, provider_keys, provider_ollama,
  sandbox*, voice_*, mcps, peers, models, vision_model, fallback_models, tiers, …}`), fetched lazily by
  settings/profile screens. The summaries verb is the hot poll; the
  detail verb is on-demand.
- **Profile settings save optimistically in both apps.** A discrete choice (model, reasoning effort, tier model and
  effort, vision model, shape, colour, budget, pause) shows at once everywhere the profile is drawn (settings, roster,
  chat header, notifications) through one overlay store, `common/optimisticProfiles.mjs`, keyed by connection, profile and
  field path; a failed save rolls back to the previous value with an error toast. Typed fields on the desktop (workspace and
  the like) debounce instead and save about 600 ms after the last keystroke. Saves of one field are sent in order, each after the
  previous one settles, so the daemon ends at the last choice; a choice replaces any pending one on an enclosing or enclosed
  path (clearing a tier, then picking its model). A confirmed choice stays overlaid until a read started after the
  confirmation lands (summaries for roster fields, detail or the settings snapshot for `tiers`, `vision_model` and
  `model_reasoning_effort`); when a newer choice fails over an older confirmed one, the client refreshes and then shows
  what the daemon has.
- **Workgroup pipeline display** — Phase chips on desktop and mobile show completed on an 18% success tint and blocked on a 14% danger tint over the pane. Running uses the selected ground, a semibold slug and the worker's mark in the working state (still under reduced motion); pending uses hover and skipped is struck through. Checks and state words stay out of the chips; accessible names and hover/tap details retain the state. The desktop chat strip starts with the literal `pipeline`, followed by phase chips and separators; mobile shows just the chips and separators. Neither repeats the pipeline's name or adds a pinned label or run-status suffix; the header keeps the run's progress and status.
- **`host.skills.list`** — one row per skill: `category, name,
  description, path, size, status` (active | inactive | invalid),
  `reason` (why, when not active) and `keywords`. Pass
  `include_body=true` to also embed each SKILL.md body.
- **`host.skill.read({name, category?})`** — full structured detail:
  frontmatter (`version, origin, created_at, platforms, tools,
  keywords`), `status`/`reason`, `requires[]` (env/bin/config, each
  resolved or not), the `tree` of files (`secrets/` reports count +
  mode only, never names), and the SKILL.md `body` (capped 32K).
- **`host.skill.file({name, category?, path})`** — read one file
  under a skill (`SKILL.md` or `<subdir>/<file>`, capped 256K, binary
  flagged not decoded). `secrets/` and symlinks are refused; `name`
  and `category` must match `[A-Za-z0-9_-]+`.
- **`host.chat.send`** (stream), **`host.chat.cancel`**,
  **`host.chat.events_since`** — run an engine turn for a profile,
  stream tool / reasoning / assistant events back; cancel via a
  separate connection that targets the in-flight `request_id`. Every
  emitted frame is also appended to a per-turn JSONL sidecar under
  `sessions/_events_<session_id>.jsonl`; `events_since(profile,
  session_id, after_seq)` lets a desktop client whose stream socket
  died mid-turn replay the missed frames and reconstruct the turn
  without losing the model's reply. A 5-second `heartbeat` frame is
  woven into the same stream so a long-running tool with no deltas
  doesn't fool the client's stall watchdog. The daemon-side emit
  path catches `send_frame` failures and switches to "drain + persist
  only" so the sidecar still captures `reply` + `done` after the
  socket dies.
- **`host.providers.*`** (set_key, unset_key, add_ollama,
  remove_ollama, add_openrouter_model, remove_openrouter_model),
  **`host.peers.{add,remove,pending_list,pending_accept,pending_discard}`**,
  **`host.profile.{create,delete}`**,
  **`host.mcp.{add,remove}`**, **`host.email.remove`**,
  **`host.sandbox.{set,network}`**, **`host.voice.set_voice`**
  — config mutations. Each is a thin wrapper around the same
  internal helper the matching CLI subcommand calls. The
  `host.peers.pending_*` verbs surface unpinned-sender entries
  recorded by the ALP server (see [ALP.md → Pending invites](ALP.md#pending-invites));
  `pending_list` enriches each row with `local_profile` when the
  pubkey resolves to a profile on this machine, so the desktop /
  TUI can pre-fill the peer id without prompting. `host.peers.remove`
  and `host.peers.pending_discard` are **idempotent**: they return
  `{ok: true, existed: <bool>}` instead of raising `-32004 not-found`
  when the row is already gone, so a stale UI click or a parallel
  retry never blocks the user's intent.
- **`host.workgroup.{create,update,add_member,kick,remove,action,post}`**
  — workgroup CRUD, hub-only for create/update/add_member/kick/remove,
  member-side for action (pause/resume/leave) and post. The desktop
  Tauri layer routes them through the host plane so mobile reuses the
  same contract.
- **`host.connections.{list,create,add_device,exchange_pairing,pairing_status,cancel_pairing,update,set_status,delete,revoke_device,register_device,summary,usage_daily}`**
  — connection/device management and 14-day aggregate usage for the
  WebSocket transport. The server requires
  scoped members to pass `params.profile` explicitly on every
  profile-aware RPC (a small allowlist of profile-agnostic verbs is
  exempt) and returns `-32001 forbidden` if missing or out of scope;
  admin role bypasses by design. `host.devices.*` aliases preserve the old
  client contract during migration. List-style RPCs
  that aggregate across profiles (`host.profiles.list`,
  `host.profile.summaries`, `host.workgroups.list`,
  `host.approval.pending`, `host.clarification.pending`,
  `host.events.history`) are filtered to the device's scope before
  delivery; the event-subscribe stream drops out-of-scope frames
  the same way.
- **Roster reads stay responsive during agent turns.** `host.profile.summaries`
  and `host.workgroups.list` run their filesystem aggregation on a dedicated four-worker
  executor in `host.read_pool`, preserving the caller's context variables and scope. Agent turns and pipeline gates
  use the default executor and cannot occupy the roster's workers. The desktop gives both reads
  a 60-second deadline. It applies each successful half independently and persists only that half;
  a failed or unapplied response retains memory and marks the workgroups page as potentially out
  of date, with Retry. Only applied responses count as synchronized.
  Retries back off through 1.5, 5, 15, 30 and 60 seconds, then keep the 60-second ceiling until
  recovery. Reloads run one at a time per connection, coalescing events during a pending read into
  one follow-up refresh; replies from a previous connection or switch are ignored. Online desktop
  windows also reconcile every minute while visible. Terminal task events (`wg.done`, `wg.blocked`)
  request a coalesced roster refresh for pipeline state and spend; ordinary `wg.post`
  frames only touch recency, avoiding a full-list request per post. The daemon emits no separate
  task or skip event: those posts arrive as `wg.post`.
  The phone keeps the same reads current per resource (profile summaries, the workgroups list, an
  open workgroup's transcript and its task fold), each in its own cache entry keyed by connection,
  so a reply from a previous connection never lands in the active one. A plain refresh (mount,
  focus, pull) joins the read in flight; an event (`wg.post`, `wg.done`, `wg.blocked`,
  `workgroup_changed`, `workgroup_members`, or the stream's reconnect) invalidates, which adds at
  most one read after the one in flight. A read that fails in transport (timeout, dropped socket,
  `too-many-connections`) retries after 2, 4, 8, 16, 32 and 60 seconds while the app is in front;
  any answer from the daemon is final and stops retries and reconciliation for that screen. In the
  foreground those four reads re-check every minute without showing the loading state; nothing
  runs in the background, and a return from the background reads at once (an inactive blip does
  not). Each read exposes `stale` (cached rows plus an error) and `updatedAt`. An auth failure
  still clears the cached rows.

- **CLI workgroup mutations notify through the daemon.** `workgroup launch` and
  `workgroup remove` use the existing host verbs when its socket exists, so the daemon emits
  lifecycle events to subscribed clients. Without a socket they retain their standalone behavior.
  An RPC error is reported without repeating the mutation locally: a timeout can mean the daemon
  already performed it.

- **`host.email.probe`**, **`host.peers.ping`**,
  **`host.model.ctx_window`** — diagnostic probes the desktop / TUI
  used to invoke via `alpi email probe`, `alpi peers ping`, and
  `alpi ctx`. Same logic, host-plane entry point. `host.peers.ping`
  resolves intra-machine targets by `pubkey` (not by the peer's
  local `id`), so a co-located peer pinned under any alias still
  finds the right `alp.sock` — the alias never has to match the
  remote profile's name.
- **`host.usage.daily`** / **`host.usage.workgroup.daily`** (admin-only) —
  a 14-day per-day series of token usage + cost; the profile payload also
  carries a `total30` aggregate over the ledger's 30-day retention (the same
  payload feeds the profile snapshot's `usage` section). Profile usage reads the
  `ledger.json` 30-day history (authoritative for ALL spend, including
  non-token costs like image generation); workgroup usage reads the hub
  transcript (per-post declared cost). Both bucket by UTC day, so the
  today figure matches the budget gate / `budget_used_usd`.
- **`host.outputs.{list,read,mark_read,mark_unread,mark_all_read,delete}`** —
  durable inbox for proactive agent messages and schedule
  results. Backed by `<home>/outputs/outputs.jsonl` (capped at
  500 rows, atomic compaction). Rows the scheduler files (a notified
  reply, a failure, a child agent's own notification) carry the
  `job_id` and `run_id` behind them, so a client can open the job or its
  run; `mark_unread` flips a row back and emits `output.updated` like
  `mark_read`, and `alpi outputs unread <id>` does the same from the
  console (`alpi outputs show` prints the source). `notify` pushes to the OWNER's own
  apps (native, via the shared
  `outputs.create_output_and_emit_message` helper) and carries the
  row's single `type` axis (`info` | `warning` | `error`, default
  `info`). To reach a THIRD PARTY the agent uses the `email` tool,
  which sends over IMAP/SMTP or Gmail directly. Producers:
  - `notify` files an output for every successful owner push.
    Attachment-only deliveries with no text body skip the row —
    nothing to revisit.
  - `scheduler/run.py` files an output on `schedule.failed`
    (always) AND on `schedule.done` when the job notified the
    owner (`notify: true` → `delivered_to="alpi"`). Jobs where the
    agent notified itself (`delivered_to="external"`) don't get a
    duplicate row. Silent jobs (`notify: false`, the default) and
    stdout-only summaries write nothing — operational noise the
    user never saw.
  In schedule subprocesses the parent daemon is the single source
  of truth: the child's `notify` is suppressed and the parent
  parses the `tool_end` args to file one canonical output with the
  full `delivered_to` list. Each row carries
  `{id, profile, created_at, title?, summary?, body,
  type: info|warning|error, status: unread|read, session_id, job_id?, run_id?, delivered_to}`
  (`title` present when a `notify` caller set one, or on scheduler
  failure rows — "<job> failed", whose body opens with `**Reason:**`, then
  `**Exit:**` / `**Timeout:**` when they apply and any trace in a fenced
  `text` block, capped at 2000 characters). A notification is read in three
  parts, in this order on every surface: the title (markdown stripped), the
  summary and the body. A row stores `summary` only when the `notify` caller
  gave one (flattened to plain text, at most 200 characters); every reader
  derives one otherwise with the same rule (`outputs.derive_summary`, mirrored
  by `common/notificationSummary.mjs` and tested against the shared corpus in
  `common/notificationSummary.fixtures.mjs`): the first prose paragraph,
  skipping headings, short labels, tables and code, joined with the next block
  while it ends on a colon, cut at a sentence, never ending on a colon. A stored
  summary equal to the derived one counts as derived, so readers draw it once.
  The apps lead the list row with the title over a two-line summary, open the
  reader with the title, the summary and the body (a derived summary is the
  body's first paragraph, drawn as the deck), carry a given summary into Reply,
  Copy, Download and Read aloud, and raise the banner and the phone push as
  `@handle · title` over the summary, opened with "Warning · " or "Failed · "
  for those types, or "Open it to read the detail." when the body has no prose.
  `alpi outputs show` and the TUI print a given summary between the header and
  the body.
  No `archive` action — the 500-row cap handles retention so
  clients only render a two-state inbox. `agent.message`,
  `schedule.done` and `schedule.failed` events ship `output_id`
  + `deep_link: /outputs/<profile>/<id>` whenever an output was
  filed so clients can deep-link straight to the row.
  Deleting is client-side until it lands: both clients hide the row
  at once and hold every delete of one run in a single 5 s window
  (`common/undoBatch.mjs`), so a run of deletes raises one toast that
  counts them and one Undo that brings all of them back. Each delete
  restarts that one window, and on desktop hovering the toast pauses
  it, so `host.outputs.delete` is sent only for the rows the window
  outlived. Desktop shows at most three toasts; a fourth retires the
  oldest. Errors carry a Dismiss button, an optional Retry and the alert role: one that
  offers Retry persists until dismissed and any other lasts 6 s (or its own duration),
  on both clients; a persistent toast is evicted last when the stack is full.

**Contract.** ``host.events.*`` is transport, not durable history.
The replay window (``HISTORY_MAX = 500``) is sized for reconnect
catch-up within a session of activity — it can drop old rows under
load and must never be the source of truth for anything a user can
browse. Durable user-visible state lives in the per-profile stores
that ``host.outputs.*`` / ``host.sessions.*`` / workgroup transcripts
read from. If a UI needs history older than the replay window, it
queries those stores, not ``host.events.history``.

- **`host.events.subscribe`** — long-lived push channel. Daemon
  emits `{event, data, at, seq}` frames as state changes. Sources
  call `alpi.host.events.emit(kind, data)`; loop is captured at
  first subscription and broadcasts via `call_soon_threadsafe` (safe
  to call from worker threads). Filter optional via `params.kinds`.
  On connect the daemon sends a `{event: "subscribed", next_seq}`
  handshake — clients anchor their cursor here and (if they had a
  previous one) backfill the gap with `host.events.history` AFTER
  subscribing, deduping by `seq`. Subscribe-then-backfill is
  mandatory: history-then-subscribe leaves a race window where a
  frame fired between the two calls is counted in the daemon's
  `seq` but never reaches the client.
- **`host.events.history`** — bounded backfill, seq-only contract:
  `{after_seq?, limit?, kinds?}` → `{events, next_seq}`. Recent
  events are kept in memory and in `<server.home>/host/events.jsonl`;
  the JSONL sidecar is periodically compacted so offline clients can
  catch up without unbounded growth. `_load_history` preserves JSONL
  append order rather than resorting by `at` — clock skew /
  suspend-resume would otherwise scramble the replay window. The
  legacy wall-clock `since` param is silently ignored; every
  in-repo client (CLI/TUI, desktop, mobile) advances on `seq`.
  Wired kinds:
  - `session_changed` — `Engine.save_session` (id + subdir).
  - `wg.post` / `wg.done` — `workgroup_client.post()` (hub-only;
    `wg.done` is detected via `tasks_mod.is_done`, honouring handle
    prefixes + line-anchored grammar). Carry `wg_id`, `seq`, and a
    200-char summary.
  - `workgroup_changed` (`action: created|updated|removed|paused|
    resumed|left`) — workgroup lifecycle from
    `host.workgroup.{create,update,remove,action}`.
  - `workgroup_members` — `host.workgroup.{add_member,kick}`.
  - `schedule.done` / `schedule.failed` — `scheduler/run.py::tick`
    after each job dispatch. Carries `job_id`, `title`, `kind`,
    `message`, `reply`, `delivered_to`, and `silent`; clients use the
    explicit fields instead of parsing the operational `message`. Silent
    jobs (`notify: false`) are activity/history only; a job with
    `notify: true` (or one whose agent called `notify` itself) has
    its reply re-emitted as `agent.message` from the scheduler
    daemon so it wakes the owner's apps. `schedule.failed` remains an
    interrupt — it adds the job `title` and a plain one-line `body`
    ("reason; exit N; timeout: …", no markdown) plus `output_id` + `deep_link`
    (`/outputs/<profile>/<id>`), and is itself the failure
    notification (clients raise it; failures are NOT re-emitted as
    `agent.message`).
  - `agent.message` — emitted by `notify` (the owner-push tool). In
    daemon turns it fires from the tool process; for scheduled jobs
    the parent re-emits after parsing the child subprocess events.
    Carries `{profile, title, summary, body, type}`: `summary` is the given
    one or the derived one, empty only when the body has no prose, and
    `title` falls back to the profile name on an untitled row. Always carries `output_id` + `deep_link`
    (`/outputs/<profile>/<id>`) so clients land on the canonical
    output instead of the chat window.
  - `output.created` — companion event for every new outputs row
    (`{profile, id, type}`). Lets inbox surfaces refresh without
    polling `host.outputs.list`.

  Desktop and mobile stream only the active connection. Every other
  daemon is polled through `host.events.history` (desktop every 25 s,
  mobile on its catch-up and background wakes) with the notifiable kinds
  plus `output.created` / `output.updated`: the first raise native
  notifications, the output kinds only refresh that connection's inbox.
  Each client keeps one cursor per daemon, shared by its stream and its
  poll (desktop shares it only between admin routes; a member route sees
  a filtered stream and keeps its own), so switching the active connection
  neither drops nor replays an event; a daemon whose `next_seq` falls below
  the cursor its request carried restarts it from zero (a late answer below a
  cursor that moved on since is not a reset). Its replay page then takes only
  frames whose `at` is later than the last one the client saw, since a plain
  restart can restore a counter below the cursor too (`history=False` emits
  take a seq that is never persisted), while a frame above the head reported
  at the reset is always new whatever its clock; with no `at` seen yet it
  re-anchors at the head instead. A client's first poll of a daemon
  anchors without banners but still refreshes that inbox when the page changed
  it. A polled or replayed request past `ts + timeout_s` raises no banner.
  - `schedule.changed` (`action: removed|paused|resumed`) —
    schedule mutators on the host plane.
  - `attention.changed` (`{profile, counts, total}`) — the set of
    flagged items of `host.profile.attention` changed; refetch it.
    Dropped from a member's stream like `schedule.*`.
  - `config_changed` (`scope: providers|mcp|sandbox|voice|env|<dotted-key-head>`)
    — every cfg.save in `alpi/host/config.py` plus
    `host.config.set_field` / `unset_field`.
  - `email_changed` (`name`, `action: configured|cleared|authorized|removed`)
    — IMAP/SMTP env writes, gmail OAuth success, credential removal.
  - `peers_changed` (`action: added|removed|accepted|discarded`)
    — peer add/remove/pending verbs.
  - `profile_changed` (`action: created|deleted`) — profile
    lifecycle.
  - `budget.threshold` — `ledger.record()` when a USD spend
    crosses 80% or 100% of the daily cap (highest threshold wins
    when a single record vaults past both). Engine passes
    `cfg_budget` into the record callsite.

`host.profile.attention` (admin) answers what needs the owner in one profile
without opening each panel: `memory` (USER.md or MEMORY.md at 95 % of its
limit or over it, and kept listed until it drops under 90 %; AGENT.md has no
enforced limit and is never listed: `file`, `used`, `limit`, `pct`, `over`), `skills` (a skill that fails
lint, or is inactive because what it requires is missing: `name`, `category`,
`problem` = `lint|missing`, `message`), `schedules` (a job whose last run
failed and is not paused: `id`, `title`, `message`, `at`, `last_ok_at`), plus
`counts` and `total`. `alpi/attention.py` computes it; the scheduler's tick and
`host.profile.memory_write` reconcile it against `<home>/attention.json`, emit
`attention.changed` when the set changes and file one `warning` output for each
memory or skill item the first time it is flagged, and again only after it
was resolved (a memory file under 90 %) and broke again; a listed file that
crosses its cap changes `over` and emits `attention.changed`, not a warning. A failed job already files its own `error` row.
`alpi profile show` and the TUI `/status` print the same list.

Adding a new verb: create the handler in the matching `host/*.py`
module, register on `host_server.Server.register` (or
`register_stream` for multi-frame), and call from the desktop /
mobile client via the platform's host-client helper. Never expose
a verb outside `host.*` — the namespace check in `register` enforces it.

### Email (`alpi/tools/email.py`, `alpi/mail/`)

Email is an **on-demand tool, not a listener** — nothing polls the
inbox and nothing auto-replies. The agent calls `email` (actions:
`list`, `search`, `read`, `send`, `reply`, `forward`, `move`,
`delete`, `download_attachment`) whenever a chat or a scheduled job
needs to read or send mail; the tool drives the IMAP/SMTP backend
(`mail/imap.py::ImapClient`) or the Gmail backend (`mail/gmail.py::
GmailClient` + OAuth). Bodies pulled by `email(read)` pass through
the prompt-injection scanner behind an untrusted-content envelope
before the model sees them.

**Multi-account.** A profile holds N accounts — any mix of IMAP and
Gmail — modelled in `alpi/mail/accounts.py`; each account's identity is
its address and its id is a slug of that address. The `email` tool's
`account` parameter picks which one (by address or id); with one
account it defaults to that account. Accounts are declared in
`config.yaml` under `email.accounts` (non-secret shape only). Secrets
live in `<home>/.env` namespaced per account — an IMAP account's
password is `EMAIL__<ID>__PASSWORD`; Gmail OAuth client creds
(`GMAIL_CLIENT_ID` / `GMAIL_CLIENT_SECRET`) are shared across all Gmail
accounts, while each account's token sits at
`<home>/secrets/gmail_tokens/<id>.json` after a one-off OAuth consent.
Add and manage accounts via `alpi setup → Email` or the apps' Email
section; probe / remove a single account by id from the CLI with
`alpi email probe <id>` and `alpi email remove <id>`. There are no
`email.*` scalar `config.yaml` knobs beyond the `email.accounts` map.

**Per-profile env snapshot.** `alpi.home.effective_profile_env(home)`
overlays `os.environ` (process-level vars: PATH, HOME, TZ,
ALPI_PLATFORM…) with `<home>/.env` (per-profile secrets, quotes
stripped) and is the source of truth for **all credentials**:
the per-account `EMAIL__<ID>__PASSWORD` keys and the shared
`GMAIL_CLIENT_ID` / `GMAIL_CLIENT_SECRET`. The daemon never mutates `os.environ`
— under multi-profile supervision a global mutation would
cross-contaminate every profile. The contract holds across the agent
toolchain: `tools/email` (IMAP's `ImapClient.from_env_map`), the
LLM-override paths in `tools/web_extract` / `tools/read_image`,
`alpi/identity.py`, and the model selector / TUI provider gating.
Credential edits via the host plane write the file atomically; a
running engine reads the current `.env` on its next turn.

### Schedule (`alpi/scheduler/`)

Ad-hoc fires from `alpi schedule fire`, setup's Fire now and the schedule tool use
`fire_from_console`: when the local host socket exists they request `host.schedule.fire`,
and success means accepted, not completed. A missing socket or failed connection before any
request is sent keeps local execution, including an orphaned socket. `HostNotConnected` is
a `HostUnavailable` subtype raised only before the connection opens. After it opens, an RPC
error, response timeout or malformed acknowledgment never triggers a second local run.
The daemon retains `fire_by_id` as its execution path, registering the job in
Activity until completion and emitting `schedule.done` or `schedule.failed` afterward.

Tick loop (default 30s) hosted inside the alpi daemon. `add`
schedules a job (`kind: cron|once`, expression or `after_hours`).
`run-once` ticks manually for testing. LLM time grounding: when
the agent calls `schedule(action='add', kind='once',
after_hours=N)`, the engine resolves `now` from a single source so
the agent doesn't drift.

**Provider pause.** `alpi/provider_pause.py` keeps one in-memory breaker per profile in the daemon. Two consecutive failures of an account class (`insufficient_credit`, `auth`, `model_unavailable`, as `llm_errors` classifies them) pause the profile's provider for 15 minutes; two of a transport class (`provider_unavailable`, `timeout`) for 5 minutes. While paused, the scheduler skips the profile's agent jobs without stamping them (they stay due and fire on the first tick after the pause; script jobs run), the workgroup poller skips its dispatches (`skipped-provider-paused` in `alp/turns.jsonl`) and chat is not blocked. When the window lapses exactly one probe is let through (the others stay paused until it reports, or for `PROBE_TTL_S` = 15 minutes if it never does): a success closes the pause, a provider-class failure doubles the window (up to 4 hours for account errors, 1 hour for transport) without a second notification, and any other outcome (timeout, kill, an error of another class) frees the probe slot. Status surfaces read the state without taking the slot. Failures and successes are reported by the scheduler from the child's `error` event (`code`), by the poller from the dispatch's events and by the engine for the chat turns the daemon runs itself. Opening files one `error` output and raises `schedule.failed` with `kind: provider`; closing files an `info` output and `schedule.done`. The breaker is active only in the daemon process (`provider_pause.activate()` in `serve_all`): a TUI or CLI engine records nothing, so it never files a "jobs paused" alert from its own memory. `host.profile.summaries` carries `provider_pause` (`code`, `since`, `until`, `failures`, or null) and `alpi daemon status` prints it per profile; the apps do not render the field yet.

**Duplicate guard + in-place edits.** `add` rejects a job whose (`kind` + cron / `run_at` / `after_hours`) matches an existing one AND whose prompt fingerprint (lowercase + whitespace-collapsed first 80 chars) collides. Pass `force=true` to bypass when the second job is genuinely intentional. Use `update` to change prompt, cron, `notify`, or pause state without remove/recreate churn. A job carries a single delivery axis, `notify: bool` (default `false` = silent): `true` pushes the reply to the owner's apps. Failure is not on that axis: a failed job always files an error output and raises `schedule.failed` regardless of `notify`, and a run the scheduler could not end does too — killed with the daemon (0.14.49), or wedged past its timeout inside a live one (0.14.50) — through the run sweep described under Runs: a dead child within about a minute, a wedged one roughly ten minutes past its timeout. Legacy jobs with a `platform` field are migrated to `notify` on load (`platform` set → `notify: true`). Reaching a THIRD PARTY is an explicit `email` call in the prompt — that's now allowed (the old auto-delivery guard that rejected such prompts is gone).

Scheduled jobs execute through `alpi chat --once --emit-events
--no-save` with `ALPI_PLATFORM=cron`. The scheduler consumes stdout
events to detect tool traces, final reply text, delivery, and failure.
It does not write `sessions/<id>.json`: cron output belongs to
schedule delivery/logging, not to local TUI / desktop chat history.

**Loop isolation.** `serve()` runs `tick()` in a dedicated
`ThreadPoolExecutor(max_workers=2)`, and `host.schedule.fire` wraps
`fire_by_id` in `run_in_executor` before awaiting. Both paths
ultimately call `subprocess.run(timeout=job_run_timeout(job))` (default 900s, per-job up to 86400s); running them inline
would block every other coroutine on the daemon's asyncio loop —
ALP responders and `host.chat.send` streams in
sibling profiles all stall for the duration of the scheduled job.
The dedicated executor also means the scheduler can't starve chat's
default-executor turns. A regression test in
`tests/core/test_schedule.py::test_serve_runs_tick_off_loop_so_chat_can_progress`
pins the contract.

**First run.** A cron job runs at its next occurrence, never on the tick it appears. The `schedule` tool records `last_run_at` when it adds a job; a job that arrives without run state (written into `jobs.json` by hand or by a deploy, or whose `schedule/runs.json` entry was lost) gets `first_seen_at` in `runs.json` from the first tick that sees it, or, if it arrives paused, from the first tick after it is resumed. A fired job is stamped (`last_run_at`, `last_run_status`; a one-shot that succeeded is removed) the moment its run returns, before its outputs and events are written and not at the end of the pass, so a daemon restart in the middle of a long pass does not fire a job that already finished. A run that raises (the agent subprocess cannot start, a file is missing) is a failed outcome stamped and reported like any other failure, and the pass goes on with the next job. Each job is re-read from `jobs.json` just before it fires and skipped if it was removed, paused, fired by hand or no longer due meanwhile, and fires from the fresh copy; a due check that raises skips that job with a logged reason; a stamp that cannot be written is logged and kept in memory, laid over the job on every later tick while the job's kind and `run_at` are the ones that ran (so it is not fired again, and a one-shot stays gone, but a job edited into something else in the meantime is left alone) and retried first thing on each tick until it lands, without overwriting a newer stamp on disk (a daemon restart while the disk keeps failing loses it); an unreadable `jobs.json` mid-pass ends the pass. `fire_by_id` stamps the outcome (a failed stamp is logged, not raised) before it emits `schedule.done`, so the first `host.activity.list` after `activity.changed` already reads it. `schedule(action="fire")` requests a job now.

**Job fields.** A job carries an optional one-line `description` (at most 160 characters, set through `schedule(add|update, description=…)` and listed by `host.schedule.list`), and its run state keeps `last_run_message` (the redacted failure, 300 characters, cleared by the next success) and `last_ok_at`.

**Timezone.** Cron expressions evaluate against the **machine's system timezone** (`datetime.now().astimezone()` in `scheduler/run.py`). Jobs are stored with UTC `last_run_at` but fire according to local wall-clock time. Practical consequence: if you specify `10 12 * * *` because you want a 12:10 reminder in Bangkok, the Mac must be set to `Asia/Bangkok`. Move the machine to a different timezone and the cron fires at 12:10 there, not in Bangkok. No in-job timezone override today — add it via `TZ=…` in the launchd plist / systemd unit if cross-timezone stability is required.

### MCP client (`alpi/mcp/`)

Spawns user-configured MCP servers (stdio JSON-RPC, SSE planned). Their tools are wrapped and registered as alpi tools. Servers configured in `config.yaml` under `mcp.servers.<name>` (command, args, env). Management lives in `alpi setup → MCPs` and in the `alpi mcp` command group (`add`, `remove`).

**External orchestration frameworks.** Alpi does not embed LangGraph,
CrewAI, AutoGen, or similar graph/supervisor runtimes in core. They
overlap with Alpi's own agent loop and bring a heavier dependency,
state, and observability model than the local-first runtime needs.
Interop belongs at the edge: expose the external workflow as an MCP
server and let Alpi call it as a tool, or wrap a local workflow in a
scripted skill. ALP is not the adapter layer for these frameworks; ALP
is reserved for sovereign profile-to-profile collaboration across
machines, while MCP is the interop layer for external runtimes and
tools.

### Logging (`alpi/_log.py`, `alpi/logs.py`)

Every subsystem writes to a single flat folder: `~/.alpi/logs/<subsystem>.log`, rotated at 1 MB with 3 backups (`MAX_BYTES` / `BACKUP_COUNT` in `_log.py`). Same format everywhere (`%(asctime)s %(levelname)s %(name)s %(message)s`) so `alpi logs` can merge them by timestamp prefix. The source tag on display comes from the filename.

Three sources today (file on disk + the writer that produces it):

- **`service`** — the unified orchestrator's root log: subsystem
  start/stop, scheduler ticks, ALP listener traffic, delivery
  errors. Written by `alpi.service` and every subsystem that logs
  through the root logger.
- **`agent`** — one line per TUI/schedule-triggered turn: session id, elapsed, tool names, reply size, cumulative cost, truncated user prompt. Written by `engine.py::run_turn` via `get_subsystem_logger(home, "agent")`. This is the **cross-session grep index** — `sessions/<id>.json` carry the full detail; `agent.log` lets you answer "what has alpi been doing this week?" without iterating JSONs.
- **`approval`** — one line per non-SAFE terminal command classification (ALLOW / DENY with severity, pattern, reason). Written by `tools/_approval.py`. **Security audit trail**; complements the per-turn detail in `sessions/`.

The machine-wide structured administrative trail is separate:
`~/.alpi/logs/admin-audit.jsonl`, 5 MB plus three rotated generations, mode
0600. Each row is capped at 4 KB, bootstrap/auth failures have their own
one-row-per-minute budget, and target fields are allowlisted per method. It is
JSONL because Desktop and `host.audit.list` filter by actor,
target and result. `alpi audit-log` renders it for the console. It is not
included in `alpi logs`: those commands merge human-readable `.log` streams,
while this trail has its own bounded query contract. Chat turns are not copied
into it; sessions already carry their owning `connection_id`.

The `alpi logs --source` CLI choice list also accepts `schedule`. Inside the unified daemon, scheduler events route through the root logger and land in `service.log` — the filter value is kept so that any standalone or legacy `schedule.log` (e.g. from an older `scheduler.run.ensure_running()` invocation that ran out-of-process) stays selectable.

Why logs are NOT inside `sessions/`: `sessions/` is a structured store (one JSON per conversation, indexed by id, consumed by `session_search` and the resume flow). Mixing freeform logs would break the glob pattern and the cleanup semantics. Logs are the **index and audit trail**; sessions are the **content**. Peers, not nested.

Why one flat folder (`logs/`) instead of per-subsystem dirs: tiny `<subsystem>/logs/` folders with a single file each is pure noise. The service keeps non-log state in its own places (`schedule/jobs.json`, `alp/alp.sock`, `service.pid` at the profile root) — only the `.log` files consolidate.

Adding a new source is two lines: `from alpi._log import get_subsystem_logger; logger = get_subsystem_logger(home, "my-sub")`. `alpi logs` picks it up without changes; add the tag to the `--source` choice list in `cli.py::logs_cmd` if you want it filterable.

### Doctor (`alpi/doctor.py`)

`alpi doctor` — live health check. Verifies external capabilities actually **respond**, not just that they're configured. Same entry point from the CLI and from `alpi setup → Health check`; the status in the setup menu row (`all green` / `N warning(s)` / `N failing`) runs the full check too.

Checks:

- **Model** — `cfg.model` set + provider's API key present in `.env` or env.
- **Workspace** — configured + exists + writable.
- **Email** (live) — IMAP login + SMTP handshake, Gmail OAuth token refresh.
- **Service** — daemon installation + PID checks distinguish "installed but dead" from "running" from "not installed".
- **MCPs** (live) — spawn each configured server, `list_tools`, stop. Parallelised; per-server timeout 8 s.
- **Security** — sandbox backend binary on PATH (if `tools.terminal.sandbox: true`), approval allowlist count.
- **Dependencies** — the installed LiteLLM against the pin alpi's own metadata records, and every file of the distribution against the sha256 digests its installer wrote to `RECORD`. Catches a local swap or edit of the one dependency every provider call routes through. The pin row is sync; the file hashing runs in the pool with the network checks, so it never delays the first frame. An absent `RECORD` warns rather than fails — the check reports what it could not verify instead of claiming it did.

Parallelism: the network-bound tasks (IMAP/Gmail/MCPs) submit to a `ThreadPoolExecutor(max_workers=8)`. Sync checks (model, workspace, services, security) run on the main thread while the pool works. Total wall time ≈ slowest single task, not sum — ~5-10 s on a healthy profile.

Progressive rendering: `run_and_render()` uses `rich.live.Live` — every row appears immediately with a cyan spinner, each resolves to `✓`/`✗`/`!` as its future completes. Animation at 10 fps via a manual frame cycler (rich's `Spinner` objects can't be appended to `Text`). Layout is stable (same rows, same column widths) so the eye doesn't jump.

Exit codes: `1` if any check returns `fail`, `0` for warn/info/ok. Warnings don't break cron. The wizard entry ignores the exit code — it press-enter-waits so the user can read.

### Ops digest (`alpi/ops_digest.py`)

`alpi digest [--since 7d]` is the read-only evidence rollup for
operator decisions. It deliberately does not own new state: each section
reads the primitive owned by another subsystem.

- **Tools** — current availability report from `alpi.tools`.
- **Skills** — summary from `skills_usage`.
- **Memory** — promotion queue counts plus memory-file pressure.
- **Compaction** — event count and after/before ratios from
  `logs/compaction.jsonl` over the requested window.

The command has two renderers: a compact Rich view for humans and
`--json` for scripts. The JSON is a dataclass dump of the report shape.
It is not an observability daemon, dashboard, recommendation engine, or
telemetry channel. Tests pin the read-only contract by snapshotting the
profile tree before and after a digest run.

### Sessions (`alpi/session.py`)

Turn-based JSON: `schema_version: 2`, `turns: [{at, user, tools[], assistant}]`, and cumulative metrics. `ToolLog` carries `at, name, args, result, ok, duration_s, reasoning`; large `user` / `assistant` / `reasoning` / tool payloads are persisted as bounded previews plus `{bytes, sha256, truncated}` metadata, not raw unbounded blobs. `host.session.read` normalizes both legacy and v2 payloads back to the client-facing shape, so desktop/mobile can render old and new sessions the same way. Empty sessions (no user message) are NOT saved.

Resumed chats and host rewrites retain successful human `ask_user` answers as user clarifications alongside their questions, before the final assistant reply. Ordinary tool results remain excluded. Answers are redacted on save, capped at 4 KiB each and 8 KiB per replayed turn; failed, fallback and clipped answers, or questions over 1 KiB, are excluded. A completed human clarification keeps an otherwise interrupted turn replayable.

Listings are bounded. `host.sessions.list` fully parses normal files but uses a cheap summary path for files above the large-session threshold; `host.profile.summaries` uses `count_sessions()` and `latest_chat_summary()` so profile/sidebar RPCs never parse 50 MB histories just to show a count or latest row.
Scoped counts reuse the same cached session rows and bounded large-file metadata path as listings;
an unfiltered internal count enumerates session files without parsing them.

Live replay is a separate sidecar (`sessions/_events_<id>.jsonl`). It is append-only within the active turn, sequence-numbered, and bounded: incremental `assistant_delta` / `reasoning_delta` frames are preserved exactly, while very large text fields are clipped. The canonical durable review remains `sessions/<id>.json`; the sidecar is for reconnect/backfill, not long-term full-fidelity storage.

`sessions/` is local human chat history: TUI, desktop, and manual
`alpi chat --once` runs that should be resumable. `--continue`,
`tui.auto_resume`, host `latest_session`, and desktop profile opening
all treat only `kind == "chat"` as resumable local history. Historical
files whose first user message starts with `[SCHEDULED:]`,
`[workgroup-poller]`, or another system bracket are ignored by
resume/profile history.

**TUI resume.** Bare `alpi` resumes the most recent session when `tui.auto_resume: true`; `-c` / `--continue` is the manual override.

Scheduled jobs do not persist session files. The scheduler uses
`--no-save` because it only needs emitted final reply/tool events for
delivery and audit; keeping a resumable transcript would make
background jobs appear as user chats.

**`@`-mention threads (`alpi/alp/mention_thread.py`).** When peer A `@`-mentions peer B over ALP (`link.ask`), the receiving side runs a fresh `Engine` per turn — but B persists a small thread at `<B-home>/mentions/<A>@<conversation>.json`, capped at 20 turns, where `conversation` is an opaque id A derives from its own source session (the `peer` tool reads it from the run context; the host chat, TUI and `--once` pass their session explicitly). Successive mentions from the same A conversation carry conversational memory ("what I said before" resolves) without polluting B's local `--continue` (which only reads `sessions/`); a new A conversation starts clean, and the same `conversation` value from peer C selects nothing. A request whose conversation cannot be established runs with no history and writes none; a caller that sends no `conversation` at all predates the identity and keeps the legacy `<A>.json` thread, which is never imported into conversation threads. The result's `history` field says which applied, so a sender can tell when a target ignored the identity. Wipe via `setup → Cleanup → Mentions`.

### Security model

Two layers:

- **Layer 1 — application guards (always on).** `_approval` classifier on terminal (rm -rf, pipe-to-interpreter, downloaded code run, credential paths after resolving `~`, `~+`, `$ALPI_HOME`, `${VAR:-default}`, `$'…'`, globs and `..`, fork bomb, ...). It strips `#` comments before tokenizing, re-classifies the string of `sh -c` / `bash -c` / `eval` and every command substitution up to three levels deep, expands `${VAR…}` forms and treats an unset variable as empty. A command it cannot read (it fails to tokenize, or has an ambiguous `$'…\''`, a `case` inside `$( )`, `${!name}`, an `eval` with arguments, an unquoted heredoc with a substitution, more than eight nested bodies or nesting beyond three levels; a nested body that cannot be read counts for its parent) is `caution` with the fixed reason `command could not be checked`: it asks once, and neither the session allowlist, the config allowlist nor "always" applies to it. A real dangerous match found anywhere still wins. Heredoc bodies are never set aside: a body that breaks the tokenizer makes the command ask. SSRF block on web_fetch/web_extract (RFC 1918, link-local, cloud metadata). Prompt-injection scan on email + web content. Sensitive-path denylist on file tools (`_paths.py`).
- **Layer 2 — OS sandbox (normally opt-in, mandatory for scoped bare-metal pipeline turns).** `tools.terminal.sandbox: true` wraps shell commands in `sandbox-exec` (macOS) or `bubblewrap` (Linux). Ordinary sandboxed turns can write workspace + `~/.alpi/` + temp storage; network is denied by default. A bare-metal workgroup phase carrying `paths` forces the wrapper even when the profile setting is off: workspace and `~/.alpi/` become read-only, only exact literal paths and trailing `/**` subtrees are writable, ambiguous globs fail closed, and temp writes use isolated storage. A scope-only wrapper preserves the network access of a profile whose sandbox is disabled. In the official Docker runtime, scoped turns omit `terminal` entirely; native file tools enforce `paths` and daemon gates run outside the agent tool surface. `tools.terminal.docker_scoped: true` returns an unsandboxed `terminal` to the profile that owns the phase, leaving the gate's source-file audit as attribution only. Unscoped interactive turns keep the profile's configured behavior.

Threat model: prompt injection via email/web content, LLM-issued tool calls on the user's machine, direct user input (trusted), and network adversaries for ALP links. Full discussion in [SECURITY.md](SECURITY.md).

## Cross-cutting concerns

### Profiles

`alpi -p <name>` resolves home to `~/.alpi/profiles/<name>/`. `ALPI_PROFILE` env var is the same. No sticky "current profile" file — resolution is fully explicit. The single daemon (`com.alpi.daemon` / `alpi-daemon.service`) supervises every profile from one process; tasks are namespaced `<profile>/<service>` so they stay distinguishable in logs and `asyncio.all_tasks()`. Inside a turn, `home.set_active_home(home)` binds the per-thread contextvar consulted by `home.get_home()` so tools resolve to the right profile even though every concurrent turn shares the daemon's env.

### Workspace

`cfg.workspace` (or `cwd` fallback if unset) is the **default root for relative paths** — not a wall. File tools and terminal can reach absolute paths anywhere except the sensitive denylist. Real workspace-only isolation is the opt-in OS sandbox (Layer 2). Configure it via `alpi setup → Workspace`; the TUI top bar read-outs the resolved path but does not edit it.

### Marks (`common/agentMarks.mjs`, `common/workgroupMark.mjs`)

alpi's identity is a set of flat soft marks with two filled eyes, drawn from data that `python3 design/build.py` writes into
`common/agentMarks.mjs` and `common/workgroupMark.mjs` from the design modules (`design/src/marks_export.py`; never edit them by
hand, `design/drift.py` fails when they drift). Both clients, the site and the icon generator import them.

- **Twin** (`alpi-twin`, and `alpi-twin-small` under 24 px) is alpi's own mark, a robot head with two antenna balls. It is always
  neutral: `BRAND_INK` ink `#14110c` on light, cream `#f3efe6` on dark, never an accent. The default profile (shape `twin`)
  renders as Twin, and so do the busy mark (`Busy`, turning busy), the first-run screens, the empty states and the error boundary.
- **Profile shapes**: twelve shapes (`SHAPE_ORDER`: round, squircle, drop, dome, pill, clover, cloud, bean, pebble, arch, heart,
  bell) of equal area and a shared optical centre, one flat fill in the profile's accent, with two eyes drawn over it in the theme's `markEye` token
  (`common/tokens.mjs`: white `#ffffff` on light, black `#000000` on dark; the paused outline keeps its eyes in ink-3). The app
  icon, the menu-bar template and the favicon are one-ink assets and keep the eyes cut out.
- **Body tone**: the body is filled with `markTone(accent, theme)` from `common/markTone.mjs`, never the raw accent in light. In
  dark it is the accent itself; in light a pale accent is deepened in OKLab lightness by the smallest 0.01 step
  (`shiftLightness`) until the white eyes reach 3:1 on the body (`MARK_EYE_FLOOR`), so amber, orange, rose, sky, teal, green and
  lime draw `#c08915`, `#dd7a28`, `#ec6a88`, `#10a1c7`, `#20a2a4`, `#2aa961`, `#799f08`, and the other five draw as stored. The
  stored hex never changes: the tone is derived where a mark is painted (desktop `Fold` with `--mark-light` / `--mark-dark` on the
  mark, mobile `markFill` by theme mode, the site's `.mark-toned` with `--mark-paper`, the console's `fold_art.body_colour`
  mirrored in Python and parity-tested, the design kit's `body_fill` as `light-dark()`). Names, the workgroup lit cell and every
  swatch keep their own tones; Twin and the one-ink icons are untouched.
  The twelve colours times the twelve shapes are the 144 pairs a profile can wear. `LEGACY_SHAPE` (diamond → round, shield → bell,
  house → arch, heart → heart, plane → drop, rocket → pill, star → clover, box → squircle, bulb → bean, tree → pebble, crown → dome,
  feather → cloud) lives only in `design/src/agent_marks.py` and the generated `alpi/mark_shapes.py`, for the daemon reading an old
  `tui.fold`; it is not exported to `common/`, and no client knows the old ids.
- **Eyes and states**: each eye is a 48-point outline that morphs between expressions (`EXPRESSIONS`: rest, wide, squint, happy,
  sleepy, sad, look, blink). Eight states (idle, busy, working, needs, done, failed, paused, offline) each have a
  `SEQUENCE` of expressions and a `STILL` form; paused draws a dashed neutral outline with no fill, offline the still
  mark faded. Motion starts at `MOTION_MIN` (20 px) and never runs under reduce motion, where the still form shows.
- **Mark states**: a profile row (desktop sidebar, phone roster) reads paused when the profile is paused, needs when it has no
  model (needs a provider) or a question or approval is pending, failed after a recent failed job, working while a turn runs or a
  sent prompt still waits for output, done for an unread reply, otherwise idle. `busy` is never a row state: it is only the loading
  indicator (`BusyMark` on desktop, `Busy` on the phone, Twin waiting). In the sidebar and the roster only the active row (the
  selected profile or workgroup) animates; every other row draws the still pose and expression of its state (`TURN.still`,
  `STILL`) with no animation loop, and still updates live. The chat header mark is animated and follows the open session:
  working from send until the turn ends (thinking, streaming or tools), needs while an `ask_user` question or a permission
  request waits, failed when the turn ends in an error (until the next send), done for 2.4 s after a successful turn and then
  idle (a turn the user stops goes straight back to idle, never done), paused when the profile is paused. Moving to another session, profile or connection starts the header from idle (a new
  thread keeps the done of its first turn once the turn names its session). The selected sidebar row and the selected phone row
  merge it with the roster: paused first, then a missing provider, then needs you, then the session state when it is not idle, then
  failed, working and unread; on the phone the shared session store counts every mounted chat of a profile, so closing the top
  one of a stack hands the row to the one below. The big profile mark of an empty thread
  ("Start a new thread", "needs a model") wears the same state, so a paused profile draws it paused. Under "Start a new thread" both
  clients show the profile's `bio` from `host.profile.summaries` (cut at three lines on desktop, with the full text on hover,
  and five on the phone) and a Continue row into its `latest_session` titled by its first message (the user's own title on
  desktop) and its age; each is hidden when there is none, and `common/threadIntro.mjs` picks both. An empty workgroup's
  honeycomb wears the workgroup's state. A workgroup has no disabled look: its states are those of
  `common/workgroupMarkState.mjs`.
- **Motion policy**: only the hero-size profile mark of an empty thread follows the pointer on desktop (`watch` on `Fold`, which
  refuses it below `MARK_SIZES.hero`, for a paused or offline mark and under reduce motion; `common/gaze.mjs` runs one shared
  listener; a focused text field draws the look down until the mouse moves, and a keystroke, focusing a field or 2.6 s of a
  resting mouse give it back), and on the site Twin in the landing hero cast follows it the same way (the same `common/gaze.mjs`,
  copied to `dist/`; only with a fine pointer, motion allowed and the hero on screen). A following mark faces front and drops
  its own turn, so only the pointer turns it; the site does this with `is-following` on `.cast-gaze` while it follows. Rows, the chat header and every other mark never follow the pointer.
  Marks are alive (SMIL eyes, CSS turn and body loops, pointer following) only while the app is in front: desktop reads window
  focus and visibility once (`lib/windowFocus.js`, focus, blur and `visibilitychange`), mobile reads `AppState`
  (`lib/appActive.js`, live only while `active`); otherwise every mark draws the still pose of its real state and resumes when
  the window or app comes back.
- **The turn**: a mark turns in 3D (CSS perspective with rotateY/X/Z, `TURN_CSS`, `TURN` per state) with the eyes sliding for
  parallax; at rest it holds a pose (`TURN.still`), smaller at row size (`TURN.smallTurn`); reduce motion keeps the still pose.
- **Sizes**: `MARK_SIZES` inline 16 (in text), row 24 (sidebar rows, menus, the palette), header 28 (beside a title), list 40
  (phone rows, the inbox, pickers), tile 48 (pinned profiles in the sidebar and the roster), hero 72 (empty and first-run pages).
- **Workgroups** wear the soft honeycomb (`WG_CELLS`, three cells in `WG_ORDER` left, top, right) that turns like the profile
  marks. A workgroup is neutral and lights up only when something happens, in the accent of the profile that owns the live phase
  (else its hub's): idle, done and queued are
  neutral ink-3 (queued as an outline, `WG_RING`); running fills the current phase cell (`currentCell`) in that accent, the
  finished cells a faint neutral fill (`WG_ALPHA.faint`) and the pending ones a neutral outline (a run without phase counts chases
  the hub's accent around the cells); needs draws the other cells in solid neutral ink-3 and the waiting cell in that
  accent, popped out of the honeycomb above row size (`MARK_SIZES.row`: the header and larger pop, rows and inline marks fill it
  flat); failed fills the failed cell in the danger colour; paused is the dashed neutral outline and offline a faint neutral
  fill. The lit colour (running cell, chase, waiting cell) is `nameTone(accent, ground)`, toned for the theme ground so a pale
  accent still reads (desktop `--wg-lit-light` / `--wg-lit-dark` on the mark, mobile against the theme `bg`). The accent is
  `workgroupMarkAccent(mark, hub, accentOf)`: the owner of the running or waiting phase when that owner is a profile on this
  device, else the hub's accent, else the brand ink (a hub that is not a profile on this device). The desktop sidebar, workgroups
  page, chat header and settings hero and the phone roster, chat header and settings hero all use it; the Activity rows carry no
  phase owner and light in the accent of their `hub_id`, never of the local member profile.
  `common/workgroupMarkState.mjs` maps a workgroup, its run and its task to that state (paused, offline, needs, queued, running,
  failed, idle), the phase counts, the phase slug (`step`) and the owner's name (`phaseOwnerName`), both from the same phase,
  which the meta says in words: `workgroupStatusLine` gives "Working · translate · @lingo" and "Needs you · approval · @yuri"
  (desktop chat header meta, workgroups page status, the sidebar tip; the phone's workgroup header meta). The workgroup list
  (`host.workgroups.list` with `include_pipeline_status`) sends `pipeline_phase` for `running`, `between` and `blocked`, so the
  workgroups page reads "Needs you · <phase> · @owner" on a blocked row, with its own warning dot; a failed task keeps the
  danger dot and "Needs attention".
- **Names**: a profile name is solid Bricolage Grotesque 800 at -0.04em in `nameTone(accent, ground)` from `common/name.mjs`: the
  accent one OKLCH step darker on a light ground and lighter on a dark one, nudged until it reads at 4.5:1 (desktop `.ds-name`
  with `lib/nameVars.js`, mobile `theme/name.js`). A workgroup's name in a title (the chat header and the settings hero on
  desktop, the chat and settings headers on the phone) is the same solid Bricolage in neutral ink, cream in dark, never the hub's
  tone, and ink-3 when paused; in rows (sidebar, workgroups page, phone roster, activity) it keeps the plain row type of any
  other row. The desktop sidebar's phase count of a running workgroup ("2/4") is meta text in the lit accent's `nameTone` (the
  phase owner's, else the hub's) on the sidebar ground (`nameVars(accent, "bgSide")`), never the raw accent.
- `common/markEyes.mjs` places the eyes of a still mark; the exported PDF footer (`common/messageExport.mjs`) signs with Twin.
- **Site**: `site/scripts/brand.mjs` builds the site's lockup, favicon, social card, profile marks and names from the same modules;
  the hero's flowing "agents" word wears the same `markTone` per theme, and `heroTone` is `toneAgainst` at 3:1 on a given ground.

`common/shapes.mjs` keeps the shape vocabulary (`SHAPE_IDS`, `DEFAULT_SHAPE` `round`, `TWIN_SHAPE` `twin`, `WORKGROUP_SHAPE`
`honeycomb`), `shapeOf` / `profileShape` (a known shape name passes through, anything else, a missing `shape` included, is
`round`; `profileShape` reads only the `shape` field), `defaultAsTwin`, `BRAND_INK`, `FALLBACK_ACCENT`, `isHexColour` and the OKLCH colour helpers
(`toOklab`, `shiftLightness`) the names and the accents use. No shape geometry lives there; marks come from `common/agentMarks.mjs`.

### App icon (`scripts/gen_icons.py`)

Run it to rewrite every icon under `desktop/src-tauri/icons/` and `mobile/assets/` and the site marks `site/assets/alpi-black.svg`
and `alpi-white.svg`; `tests/test_icons.py` fails on drift (`--check` exits 1). Every icon is Twin read from
`common/agentMarks.mjs`, projected in its held turn (22°) with the eyes' parallax, one flat ink, no gradient or outline. The desktop
tile (the PNGs, `icon.icns`, `icon.ico`) is a white superellipse with a soft shadow and a light top edge; from 128 px it shows Twin
close up, cropped by the tile, and below it the full turned mark. The iOS light and dark icons, the store icon, the iOS tinted icon
(white on black) and the splash marks use the close-up or the fitted mark in the brand ink of their theme; the adaptive
foreground stays inside the 0.306 safe radius. The favicon is Twin at half turn in `#7a7468`. The tray icons (`icons/tray/`) are
Twin at half turn, one ink with binary alpha, per size and state (see the tray bullet under the contracts). Rendering is
deterministic: a second run writes the same bytes.

## Dependencies

Hard runtime deps are kept tight — every line in `pyproject.toml`'s `dependencies` is actually imported by `alpi/`. The audited set, with one-liner for why each earns its place:

- `litellm` — multi-provider LLM client; the one primitive the agent is built around.
- `rich` — Text formatting primitives used across the CLI wizards, TUI rendering pipeline, and tool output.
- `textual` — TUI framework.
- `prompt_toolkit` — CLI wizard input (menus, text, password).
- `httpx` — async HTTP; Gmail API, web_fetch, OAuth dance.
- `click` — CLI command dispatch.
- `pyyaml` — config.yaml + skill frontmatter.
- `python-dotenv` — `.env` loader.
- `croniter` — cron expression parsing for the scheduler subsystem.
- `setproctitle` — makes `ps aux` show ``alpi (<profile>)`` instead of identical ``alpi`` lines for every profile's service.
- `playwright` + `playwright-stealth` — interactive browser tool.
- `pillow` — image pre-processing for `read_image` (auto-resize).
- `html2text` — strip HTML to markdown in `web_fetch` / `web_extract`.
- `ddgs` — keyless search across public engines; `web_search` asks one engine at a time in a configured order (replaced `duckduckgo-search` when that package was deprecated).
- `edge-tts` — TTS tool (local-first, no API key).
- `faster-whisper` — STT tool (local-first, no API key).
- `cryptography` — ChaCha20-Poly1305 for encrypted backups.
- `websockets` — the host plane's WSS server.
- `httpcore` — pinned-DNS transport, so a resolved address cannot be swapped under an in-flight request.
- `sqlite-vec` — vector search inside the knowledge SQLite store.
- `fastembed` — local embeddings for that store; no embedding API key.
- `pypdf` + `pypdfium2` — PDF text extraction, then page rasterisation when a page carries no text layer.
- `rapidocr-onnxruntime` — OCR for those rasterised pages, local.
- `python-docx` + `ebooklib` — Word and EPUB readers for the workspace tools.
- `python-gnupg` — PGP sign/encrypt in the email tool.
- `qrcode` — renders the pairing link as a scannable code in the terminal.

Optional `dev` extra: `pytest` + `pytest-asyncio` for the test suite, `ruff` for lint, `pip-audit` for CVE scans.

Project dependencies and Python build/check tools use a seven-day PyPI artifact cooldown in
uv resolution, Docker pip installs and CI, including twine and wheel smoke installs. Bootstrap
pip is pinned; user installs resolve the published dependency ranges without this cooldown.
The policy and exclusions live in [SECURITY.md](SECURITY.md#policy).

Security posture: `uv run --with pip-audit pip-audit` must run clean against the full lockfile before each release. Known-CVE deps are not allowed to accumulate — drop or upgrade.

## Testing

`python3 scripts/validate.py` is the one command before claiming done: it runs the release check and every suite the working tree touches (see `AGENTS.md`). Directly, `uv run pytest -q` is the fast suite, `--integration` adds sockets and sandbox-exec, and `--llm` enables real-LLM tests (a few cents on free models).

Key fixtures (`tests/conftest.py`):
- `tmp_home_no_env` — isolated `~/.alpi/` rooted at a tmp dir, no `.env` (safe for unit tests).
- `tmp_home` — same with the user's `.env` copied (for LLM tests).

## Contracts clients and consumers rely on

Breaking one of these breaks a client, a gateway or a peer. Change the contract, its consumers and this section in the same change.

- **The desktop / mobile client talks to the daemon, not the filesystem.**
  Verbs in the `host.*` namespace (in `alpi/host/`) are served over
  `~/.alpi/host/host.sock` (Unix socket, 0600 + same-user trust boundary;
  no Noise, no pairing). When adding a desktop feature, add a `host.*`
  verb — never read `~/.alpi/` directly from Rust, never spawn `alpi` as
  a subprocess. ALP (`alpi/alp/`) is a separate plane for cross-machine
  peer-to-peer (`link.*`, `workgroup.*`) and is **not** what the client
  calls. The one exception is the local daemon's lifecycle, which no
  `host.*` verb can serve while the daemon is down: `local_daemon_state`
  classifies this machine as `running` (`host.version` answers on the
  local socket), `stopped` (an `alpi` binary on `PATH` or the usual install
  dirs, or a launchd / systemd unit exists; `~/.alpi` alone does not count,
  the app creates it), `absent` or `unsupported` (Windows), checking
  existence only; `local_daemon_start` kickstarts the supervisor unit, or
  without one runs `alpi daemon start` detached in its own process group
  (with the install dirs on its `PATH`, stderr to `logs/desktop-start.log`,
  reaped when it exits, and not spawned again while a previous one lives),
  waits up to 45 s of wall clock for `host.version` on the local socket and
  on failure returns the tail of the launcher's stderr and of
  `logs/service.log`. It does not register a login service. `local_daemon_install` is a second
  off-main lifecycle exception, called only from the welcome button: it reuses
  an existing alpi, otherwise finds uv or downloads its official HTTPS installer
  with curl, installs uv into `~/.local/bin` without changing shell files, then
  runs `uv tool install --python 3.12 alpi-agent` with `UV_TOOL_BIN_DIR` set to
  that directory. uv downloads Python when needed. Install steps have a ten-minute
  deadline and concurrent installs are refused. The client then uses the same
  start/readiness flow; failures offer a separate installation retry.

- **A `host.*` verb that takes a `profile` never creates it.** `handlers._resolve_home` (and the usage verbs) answer `-32004 not-found`
  for a name with no directory under `profiles/`; only `host.profile.create` makes one. Reading jobs (`jobs_store.read`) does not create
  `schedule/`. A client that asks about a profile another connection owns learns it is absent and the roster never grows. The mobile app
  guards every `/profile/<id>` screen (`ProfileGuard`) so it does not ask at all.

- **First run is one welcome, not an error.** On a local connection that
  has not answered yet in this session, the desktop draws one Welcome by
  state in place of the main pane (once it has answered, an outage keeps the
  open view under the reconnecting banner, whose Retry runs this flow again
  and never replaces the window). It reads as a console screen: one
  left-aligned column of `--modal-md` (520 px) under the 38 px drag strip, the
  Twin in the theme's ink on the column edge (72 px, turning busy while
  installing or starting), a title, one sentence, facts in
  Mono, then one primary Button lg (176 px) per state with ghosts after it,
  never two primaries; the primary holds first focus. `stopped` starts alpi
  once on its own, then offers Start alpi; a launch that returned keeps the
  starting state for 15 s so the window never flashes the offline banner;
  while starting it shows the steps (start requested, waiting for alpi to
  answer); a failed start shows the error log (capped at 12 lines, scrolled to
  its tail, a focusable region), `alpi daemon start` to run by hand and Retry as
  the primary; `absent` offers one Install and start alpi primary (installation
  progress, and Retry on failure) with Check again (also re-detected when the
  window gains focus) and Connect to another computer as ghosts;
  `unsupported` offers only the link form. The form is a labelled `alpi://
  link` field (40 px), the link sources as a two-row list (`LINK_SOURCE_ROWS`
  in `common/onboarding.mjs`), the three pairing steps in place of the list
  while connecting, one failure line and one action row (Connect, then Back
  except where alpi cannot run).
  The full-window frame, with no Sidebar, exists only on a true first run:
  the local daemon has never been online on this machine (a persisted flag,
  read and written like the first-run hint) and at most one connection is
  saved. Until the local connection has a status (no connections yet, unknown,
  probing, offline and detecting) that frame is held, empty but for the
  drag strip, rather than flashing the Sidebar and the offline banner, and
  every shortcut that changes the view or opens a panel is off while it
  shows. It resolves straight to the Sidebar when the daemon answers. In every other
  case the Sidebar stays and the same Welcome fills the main pane beside it.
  Once alpi answers, one Mono line under the main pane says "This is alpi on
  this computer · To use it from a phone: Settings → Connections"; it has no
  button, shows once per machine (a persisted flag) and goes away when the
  first message is accepted. A chat opened with nothing holding focus (the
  document body) focuses its composer; a focused sidebar search, modal or
  other control keeps focus.
- **The desktop window outlives its close.** Closing the window hides it and
  keeps the process, so the tray, its notifications and the global shortcut
  (⌘⇧A, which only brings the window to the front) keep working; ⌘Q quits.
  Clicking the Dock icon while no window is visible shows the main window
  again (`RunEvent::Reopen`, macOS only), as the tray, the shortcut and a
  second launch do.
- **The tray is a popover that triages.** A second webview window, `tray`
  (`tray.html`, `src/tray/`), opens under the menu bar icon and closes on Esc or when it loses focus. On
  macOS any click opens it and the status item carries no native menu: macOS
  shows an attached menu on every click, which would hide the popover. On
  Windows a left click opens it and a right click shows the native menu (Open
  Alpi, Settings…, Notifications (N) when unread, the update header and
  Restart to update, Quit); Linux keeps that menu on every click. The icon click is decided on press and executed on release,
  with a guard so the click that blurs the popover does not reopen it. Every
  route to the main window goes through one `show_main_window`: it hides the
  popover, drops the pending banner, shows, unminimizes and focuses.
  - *Snapshot.* The popover never calls `host.*` and never reads `~/.alpi`. The
    main window pushes one snapshot (`tray_announce_state`, versioned, debounced
    250 ms, an identical snapshot is not resent) already filtered by connection
    and profile scope, over every online connection: the active one from the
    main window's own activity, each other one read with `host.activity.list` and
    profile summaries (on its `activity.changed` events after a short wait, and
    every five minutes as a backstop; a member connection counts for needs you
    and running, never for schedules or failing). The snapshot holds state, counts
    summed over the connections, the first four needs-you rows (profile, shape,
    accent, a deeplink for an approval or a clarification on its own connection),
    failing jobs, the first four running turns (profile, shape, accent, title,
    start time and a deeplink: `chat` to the session, `workgroup` to a pipeline,
    `profile` for a scheduled run), the next three scheduled jobs merged by time
    (each with a `settings/schedules` deeplink), unread, update and
    offline facts. Titles are cut to 200 characters; when the invoke fails a
    reduced `{v, state, counts}` is sent instead; Rust refuses a snapshot over
    64 KB and caps each deeplink field. The popover reads it with `tray_state`
    when it opens and on the `tray-state` event, and follows the app theme
    (System, Light or Dark) through the shared `storage` event and on show.
  - *States.* Heading and rows come from `trayModel.js`. The state, the icon
    and the counts follow the sum over every connection read, while the active
    connection's own link (offline, starting, connecting) still wins. The header is
    Twin at 40 px wearing the state (needs you → needs, running → working, failing →
    failed, offline → offline, starting and connecting → busy, else idle), a 20 px
    title (`Abby needs you` or `N need you`, `Sentinel is working` or `N working`,
    `N jobs failing`, `All quiet`) and a 14 px summary of what the title does not
    say: the running count or the kinds of request when something needs you, else
    `Nothing needs you`, then `next in 2h` (under six hours, `next due now` when it is
    under a minute away or overdue), `next at <clock>`, `next tomorrow` or
    `next <weekday>` from the first scheduled job; an admin with
    nothing scheduled reads `Nothing needs you, nothing scheduled`, a member never
    gets that claim. Sections come in a fixed order, each always labelled, within a
    budget of five lines (rows, the failing banner and every `N more` line count):
    `Needs you` (up to four rows with Review), the failing jobs
    as a danger-tinted banner (`N jobs failed in 24 h` over the profiles, opening
    alpi), `Running` (a row per turn opening the session, workgroup or profile), then
    the next scheduled jobs grouped by day (`Later today`, `Tomorrow`, the short
    weekday), up to three, two beside running, each opening its schedule. A row is
    the profile's 24 px mark (animated for needs-you and running rows, still for
    scheduled ones), its name in Bricolage toned with `nameVars`, the connection
    only while several are read, the kind and age of a request, and the elapsed time
    or `in 2h`/the clock on that line in tabular figures, with the job title alone on
    the second line. Once needs you has three rows, running collapses to a count line
    and the schedule is hidden. Needs-you or running rows that do not fit end in
    `N more · Open alpi` (four rows and the line at most). A snapshot without rows
    (the reduced one the main window falls back to) draws its counts as count lines
    and a needs-you summary of `Open alpi to review`. Also: an update ready (a success-tinted banner with Restart
    above the footer in every state), daemon stopped (`alpi isn’t running` with a
    full-width Start alpi), starting, connecting (activity still loading: it never
    claims all quiet) and `alpi · online` when the daemon has no
    `host.activity.list`. The footer is Open alpi, the bell, Settings and Quit.
  - *Window.* 340 px wide inside a 342 px transparent, undecorated,
    always-on-top window that skips the taskbar (`macos-private-api` makes the
    transparency possible on macOS); the page reports its height with
    `resize_tray` (48 to 640 px). The container takes focus when it opens and
    shows no ring until Tab. App commands: `show_main(deeplink)`,
    `open_settings`, `open_notifications`, `restart_to_update`, `start_alpi`,
    `quit_app`, `resize_tray`, `hide_tray`, `tray_state`. The `tray` capability
    only grants event listening; app commands are not restricted by
    capabilities, so the popover relies on loading nothing but app assets under
    the default CSP and does not get defence in depth.
  - *Icon.* `scripts/gen_icons.py` writes pixel-exact assets
    `icons/tray/tray-{quiet,dot,needs,offline}-{size}.png` for 16, 20, 22, 24,
    32 and 36 px: Twin at half turn in one ink with binary alpha, and a
    knock-out around a badge in the lower right (a dot, a ring for needs you,
    a slash across the mark for offline). macOS uses 36 px (18 pt);
    Windows 16, 20, 24 or 32 px at scale 1.0, 1.25, 1.5 or 2.0 and up; Linux 22
    px, 24 above 1.0. The state is needs you, then offline, then unread or
    update, then quiet; `refresh_icon` makes one `set_icon_with_as_template`
    call, and only when the state or the size changed. On Windows and Linux the
    size is re-read on a state change only, so moving between displays of
    different scale keeps the old size until then. The tooltip names the heading
    state (`alpi · 2 need you`).
  - *Standard behaviour stays.* Closing the window hides it, ⌘Q quits, Hide and
    Hide Others are the predefined items, a second launch re-shows the window and
    ⌘⇧A shows, unminimizes and focuses it.
- **The phone's first run is the same console.** `/onboarding`, `/pair` and
  `/paired` are one column on a single left edge (16 pt, 24 pt on a fold,
  where these routes render full-bleed; `lib/firstRun.js`): Twin in the
  theme's ink on the edge, a terse title, one sentence, facts in mono and one primary
  Button hero anchored above the safe area, with ghosts under it and never two
  primaries. The welcome adds the link sources under Where do I get a link?;
  the scan screen has one Paste link button; with the camera not allowed the
  page offers Continue, or Open settings when the system will not ask
  again (the permission is read again when the app returns). The paste page
  hides the mark and the sources while the keyboard is open; pairing shows the
  three steps and one wait (the busy mark, no button spinner) and names a
  failure in the same slot. The pairing fact is the host and its URL, a long
  host name cut at 40 characters, and a second scan in the same tick starts one
  exchange. A spent deep link opens the link-used state instead of the inbox.
  With a connection already saved, `/pair` also offers Open inbox as a second
  ghost; a failure that left the connection saved keeps Open inbox as the
  primary. Paired names the host and the role and lists two optional rows,
  Face ID unlock (hidden without hardware or enrolment) and Notifications:
  Enable asks the system and records the primer flag only after the answer
  (`accepted` when granted, `declined` when denied, nothing otherwise), a
  denial shows Open settings and a grant the on pill; Open inbox never waits
  for them. The notifications primer sheet stays closed on these routes and is
  evaluated again when the user leaves them, so skipping Enable still shows it
  on the first inbox.
- **An empty roster is the first-profile page.** One condition,
  `isFirstProfile` in `lib/roster.js` (empty roster after the first load,
  paired, no filter, daemon not down, no error), drives both panes. The list
  shows the mark at 72 pt, the title, one sentence and New profile as the one
  primary for an admin; a member sees the role line `member · nothing shared
  yet`, naming the device in the sentence, and no action. On a fold the detail
  pane then says only Their chats open here; with the list folded an admin
  keeps New profile in the pane. The fold's sidebar is 280 pt.

- **`host.version` says whether a daemon can update itself.** It returns
  `installer` (`uv` | `pipx` | `docker` | `source`, cached after a successful probe by
  `updater.install_kind`; `docker` comes from the deploy runtime) and
  `self_update`, true only for `uv` and `pipx`. A client shows its update
  button only when `self_update` is not false (a daemon that omits it keeps
  today's behaviour) and otherwise shows the manual step from
  `common/updateHint.mjs`, which `alpi update` prints too: for Docker the image
  tag to set in `docker-compose.yml`, for a source install `git pull` and a
  restart. `host.daemon.update` on such a daemon answers `reason: "manual"`
  and runs nothing.

- **Engine `assistant_done` events: `final=True` marks the deliverable.**
  The engine emits `AgentEvent(kind="assistant_done", ...)` for **every**
  assistant message, including preamble narration that comes *before*
  tool calls ("Let me check things first.", etc.). Only the event that
  closes the turn carries `final=True`. Consumers that build the
  canonical reply (scheduler delivery, gateway, ALP) **must** filter on
  `ev.final`; otherwise preamble leaks into the message users receive.
  The TUI is the exception — it consumes every `assistant_done` to
  rewrite the active bubble, which is correct for live streaming.

- **A banner opens what it announces; a link lands where it says.** The
  desktop raises each banner with a deeplink `{kind, profile, id,
  connection_id}`. The desktop notification plugin reports no click, so the
  app opens the latest banner raised while the window was unfocused when the
  window gains focus within 20 s: only the latest, an approval or question
  outranks a later notice, connection and budget notices are never opened, and
  opening the app from the tray, the shortcut, the Dock icon or a menu drops
  it. Coming back to the window cannot be told apart from a click, so only a
  banner from the connection open when it was raised is held, a later banner
  from another connection drops a held notice (not a held approval or
  question), and the activation is marked `inferred`: the client never
  switches connection for it and drops it if the open connection has changed. `chat`, `profile` and
  `workgroup` open that view, `output` opens the notification, `approval` and
  `clarification` bring that request to the front, and `settings` with id
  `schedules` opens the profile's Schedule panel (an admin connection only,
  decided on the connection the banner came from). An explicit activation (a
  tray row) switches to the originating connection first, applies a request or
  a schedule once the switch has landed, and never leaves unsaved settings.
  On the phone a tap follows `deepLinkFor`: `schedule.failed` opens its output
  row (`deep_link`) or, on a daemon without one, the job page; a link from
  another app never carries a `draft`, and a pairing link the system hands over
  again after its token was used opens the link-used state of `/pair`.

- **A chat send is accepted when the stream starts.** The desktop keeps what
  was typed until the first frame of `host.chat.send` (`session_start`); an
  `error` before `session_start` (a busy session, an unstaged attachment, a
  session that is not found) ends the stream, removes the pending turn and
  returns the text to the composer, while an `error` after it is the engine's
  and is followed by `reply` and `done`. A stream that closes without `done` is
  reported as an error, never as a finished turn. A connections file the
  client cannot decode is set aside as `connections.corrupt-<time>.json` and an
  unreadable one is never overwritten.

- **A chart is a ```` ```chart ```` block of JSON inside the text.** Every profile learns the syntax, with a
  worked example, from the system prompt's environment block (`prompt_cache.CHART_LINE`) and when to draw one
  from the base prompt's "Showing numbers" section: three or more values over time or three or more categories
  measured the same way, in a reply, a notification, a scheduled report or a workgroup post, led by a sentence on
  what the chart shows, aggregated to fit the limits, never one or two numbers or values in different units, never in
  `email` or a `peer` message. The `notify` and `workgroup_post` descriptions and the scheduled-job surface hint point
  to the same rule; there is no chart tool.
  The spec is `{type: line|bar, stacked?, title?, unit?, x: [labels], series: [{name?, values: [numbers or
  null]}]}` with one value per label, at most four series, 2 to 60 points for a line and up to 24 bars;
  `stacked` refuses negative values and only stacks a bar with two series or more. `alpi/charts.py` (`parse_chart`, `render_text`, `textify`)
  and `common/chartSpec.mjs` (`parseChart`, `chartLayout`, `chartSvg`, `describeChart`) validate the
  same way, tested against `common/chartSpec.fixtures.mjs`. Desktop draws a valid block as SVG in chat,
  workgroup and notification Markdown, the phone with `react-native-svg`, both with the first series in
  the speaking profile's accent and the rest in ink (a comparison line dashed), bars lying down when a
  label is longer than 8 characters or there are more than 8 and no value is negative; the TUI and `alpi outputs show` draw a
  sparkline or block bars. An invalid block, and every block on an older client, stays a code block;
  banners and inbox rows never show charts, since the summary derivation skips code.
- **A link in a notification body opens outside the app.** The daemon keeps `[text](https://…)` and bare URLs when
  it normalises a body (`alpi/outputs.py`: `<https://…>` becomes the bare URL, a link to anything but http(s) becomes
  its text). `inlineSegments` in `common/notificationBody.mjs` yields a `link` segment for both forms (closing
  punctuation and quotes stay text, a URL inside code stays code, a URL inside bold is text); desktop draws it as an
  anchor that the opener plugin sends to the system browser through the one guard every external anchor in the
  window goes through (`desktop/src/lib/openExternal.js`; the chat sanitizer keeps `<a href>` for web links), and the
  phone as a pressable text that calls `Linking.openURL`. The Markdown and PDF exports keep it as an anchor.
- **Any agent message downloads as Markdown or exports to a PDF, charts included.** The same two actions sit on a
  notification (desktop More menu, phone overflow), on an assistant reply and on a workgroup post (a Download menu
  in the desktop footer, the phone's long-press sheet). `common/messageExport.mjs` is the one renderer: it turns
  `{title?, profile, server, at, body}` into the Markdown file (title, `@profile · server · date`, body with the raw
  chart block) or into a light-palette document (the body parsed by `parseNotificationBody`, charts as `chartSvg`,
  ordered lists keeping their own numbers, one block per table row so a chart or a table row never splits across
  pages) closing with a footer row carrying the alpi mark, the profile, the server and the date — the last row
  of the same table, not a `tfoot`: WebKit's print engine (desktop on macOS/Linux, `expo-print` on iOS) silently
  drops a `display: table-footer-group` footer instead of repeating it, so it never reached a printed page; a
  footer that is ordinary table content prints once, reliably, everywhere.
  Desktop does not print that table as is: the WKWebView print operation on macOS repeats neither a `thead` nor a
  `position: fixed` element and WebKit has no page-margin boxes or page counters, so `desktop/src/lib/printPages.js`
  lays out the pages itself. It first lays the article out in an off-screen probe and waits for the fonts (at most
  2 s), then cuts it into blocks (title, paragraph, quote, heading, chart, list, table, code) and measures each in a
  probe at the page width, under the same `.alpi-export` wrap rules as the page, before anything is mounted: a list by
  item, a table by row, code by line and text by line box (each word, as `Intl.Segmenter` cuts it so CJK splits too,
  wrapped in a span; a new line where a word starts below the previous line), from the distance between their tops. The pure
  `paginate(blocks, pageHeight)` packs them into fixed-height pages 8 px short of the body: a chart or row never
  splits; lists and tables split at an item or row boundary, a table piece repeating its header row and the full
  table's column widths (`table-layout: fixed`); text and code move whole when they fit a page and otherwise split
  by line; a heading, or a chain of them, goes with the first piece of what follows unless that is scaled, and
  is never left behind once placed; a
  single unsplittable block taller than a page (a chart, a row) gets a page of its own, scaled to fit. Long words
  wrap anywhere instead of being clipped. Each page carries a running header (mark,
  profile, server, title) and footer (profile, date, `n / m`) in place of the meta line and the end footer. The
  paper is chosen in the print sheet after pagination, so pages are sized for the smaller of A4 and Letter inside
  the 16 mm margins (672 × 928 CSS px). The phone keeps the single end footer: `expo-print` gives no measured layout.
  Desktop mounts those pages in a hidden print root and calls `window.print()` (the system print sheet;
  `core:webview:allow-print` is granted to the main window only), naming the document after the file. The root
  and the title stay until `afterprint` or ten minutes, never removed when the call returns, because macOS answers
  before the sheet has paginated; the next export replaces it. The phone writes it with `expo-print` and shares it,
  giving each export a cache folder of its own (the readable file name inside it) that the next export clears once
  it is ten minutes old. The file name is the title, slugged; an untitled export has no message id to key on, so
  it is named `alpi-<profile>-<fingerprint>-<day>`, an 8-hex FNV-1a hash of profile, server, timestamp and body —
  two untitled messages from the same profile in the same second with the same body still collide, but same-day
  collisions from the old `<profile>-<day>` name are otherwise gone. Only the desktop numbers its pages.
- **Two messaging intents: `notify` (owner) vs `send_message` (third party).**
  `notify(text, title?, summary?, type?)` pushes to the OWNER's own paired Alpi apps —
  it files an inbox row in `~/.alpi/outputs/` and emits the `agent.message`
  host event (the only native push). `type` is the single presentation axis:
  `info` (default) | `warning` | `error`. `send_message(text, channel,
  chat_id?, attachment?)` reaches a THIRD PARTY through a gateway
  (telegram / imap / gmail / matrix / webhook) — `channel` is required, there
  is no owner channel, and it carries no `type` (its inbox rows are always
  `info`). The shared native-emit helpers live in `alpi/outputs.py`
  (`create_output_and_emit_message`, `_suppress_native_emit`). Clients must
  surface every `agent.message` — do not suppress it (e.g. for the active
  chat).

- **`schedule.done` / `schedule.failed` events carry structured output.**
  The scheduler tick emits `{profile, job_id, title, kind, message, reply,
  delivered_to, silent}` on the host event bus. `message` is the
  operational status for daemon logs and ops UIs. `reply` is the clean
  agent/script output, capped at 2000 chars in the event, intended for native
  notification bodies; the archived inbox row keeps the whole reply up to
  8000 chars and, past that, ends with a line saying where it was cut. A job has one delivery axis, `notify: bool` (default
  `false`). `delivered_to` is `""` (silent, `notify:false`) | `"alpi"`
  (`notify:true` → the daemon re-emits the reply as `agent.message`) |
  `"external"` (the agent called `notify` itself → no duplicate). Failures
  always file an `error` inbox row and emit `schedule.failed`, regardless of
  `notify`; the failed event carries the job `title` and a plain one-line
  summary, the row is titled "<job> failed" with a markdown `body` (the reason —
  the exception line of a traceback — then exit and timeout; a timeout also says which tool was in flight
  and for how long, how many tool calls ran, and the agent's last message), and
  `schedule.failed` is the single failure
  notification — it is NOT also re-emitted as `agent.message`. `silent` means a
  successful job produced no user-facing output.
  Do not parse `message` in clients when an explicit field exists. When
  changing the contract, update desktop/mobile consumers and bump the docs
  here.

- **`host.network.*` is the canonical network config surface for
  desktop/mobile.** `host.network.status` returns
  `{scope_in_use, host_in_use, is_override, port, device_name, endpoints,
  is_endpoints_override,
  candidates: {tailscale, lan, configured, docker}, diagnosis}` so clients
  can show the live pairing endpoint AND let the user pick a different one
  without dropping to `alpi setup`. `scope_in_use` is the network
  character of the host (`tailscale | lan | custom | docker`) computed
  via `network.classify_scope` — NOT the resolution path. `is_override`
  carries the "this came from `cfg.network.host`" bit separately.
  `host.network.set_advertised({host, device_name, endpoints})` persists
  `cfg.network.host`, `cfg.host.device_name`, and the ordered
  `cfg.host.endpoints`; empty values unset their override. Endpoint URLs accept
  only `ws://` / `wss://`, reject credentials/paths and public plaintext WS,
  and are advertisement metadata — they do not change the daemon bind.
  Empty `host` unsets the
  override (back to auto-detect). Validation rejects public IPs (token
  leak), loopback, multicast/link-local/reserved, and malformed
  hostnames — accepts RFC1918, Tailscale CGNAT (100.64/10), and any
  valid hostname. `host.network.restart_host_server` ends the current
  daemon process (supervisor respawns with fresh config) and is the
  explicit handshake clients use after writing. **Known gotcha:** a
  stale override (e.g. Tailscale IP saved in config but Tailscale now
  off) still classifies as `tailscale` because the IP literally is one,
  but the daemon won't be listening on it — clients should compare
  `host_in_use` against `candidates` to detect this and warn.

- **`host.activity.list` is the one "what needs me / what is running" read.**
  Schedule list/detail views identify a running job by `(profile, job_id)`, show `running`
  and the elapsed time, and disable another Run now while it runs. Desktop holds a just-accepted
  request briefly while canonical activity arrives; terminal schedule events clear that local
  pending state. Reopening a job reads current activity, and a job row in Activity opens its
  schedule detail rather than an empty chat. Older daemons without Activity retain schedule controls.
  Both clients draw Activity with `common/activityGroups.mjs`, the one grouping: counts and filters
  (All, Needs you, Failing, Running, Upcoming), where a chip shows only while its count is above zero
  or it is the current filter and the whole row is absent when at most one kind has entries; when
  nothing needs you or fails, one quiet line says so and names the next run; failing jobs (an error
  in the last 24 hours, not re-running) grouped per profile with the first group open; Upcoming lists
  only future runs, grouped under the viewer's local day (`groupByDay`), the first ten showing and
  the rest behind Show more (`capDays`), and on desktop each run is one 32 px line with the clock
  first and the profile as a trailing tag;
  section eyebrows stay sticky; red marks only the failed time and `last ok` shows when the daemon
  sends `last_ok_at`. Retry and Retry all (confirmed) fire `host.schedule.fire`, are admin-only and
  hide for members, `forbidden` and `-32601`. Desktop shows it as a 500 px float (Open and Retry
  on row hover and focus); the phone as a full page and the fold as the detail pane (Retry per job).
  The phone's Home band keeps its own list of recent failures with Run again.
  `host.activity.list` aggregates `needs_you` (pending approvals + clarifications, each with
  `session_id`), `running` (`turn` rows from the in-process registry in
  `alpi/host/activity.py` — engine turns, workgroup dispatch in
  `service._dispatch_workgroup_turn`, scheduler fires via `scheduled_run` — plus
  `workgroup` pipeline rows from the cached fold, each with `hub_id`, while the pipeline is running or between phases; a blocked
  pipeline is not a running row) and `scheduled` (admin-only; each row carries `next_fire`, `last_run_at`, `last_run_status` and `last_ok_at`).
  A workgroup seen from both its hub and a member profile is one row, the hub's, chosen among the
  profiles the caller's `ConnectionContext.profile_scope` allows, so a caller limited to the
  member profile keeps the member's row. It reads memory and stat-keyed caches only, because
  clients call it on every `activity.changed {profile}`; never add a per-call scan of `runs/` or
  transcripts. A new long-running source registers with
  `activity.start_run/end_run` (or `tracked_run`), and a new event that changes
  what the verb returns joins `activity._TRIGGERS`. `activity.changed` is
  live-only (`emit(..., history=False)`) so it never evicts replay rows; the read
  path never writes the phase-change baseline. Running turns use the
  `can_handle_prompt` rule, the same check as `needs_you`: remote admins and members
  see their own connection's chat turns and prompts; member devices also apply
  `session_scope`. Local callers see all connections; scheduled and workgroup runs
  keep their separate visibility rules. Chat frames:
  `tool_start.started_at`, `tool_end.duration_s`, and one `reasoning_done
  {seconds}` per reasoning span (consecutive deltas closed by the next tool
  call, text delta or step end); `seconds` is time spent reasoning — the first
  span of a step counts from the model call (equal to the stored `reasoned_s`
  when step 0 streams no prose first), later spans in the same step from their
  own first delta; reasoning a retry or fallback discards never reaches a span,
  and all span texts of a turn share the turn's reasoning cap. The
  engine measures spans once (`_ReasoningSpans` emits `reasoning_done`
  AgentEvents; `host.chat` only forwards them) and stores them on the turn as
  ordered `reasoning_spans: [{seconds, before_tool, text?}]`, `before_tool`
  being the index in the turn's `tools` of the first call after the span
  (`len(tools)` when it precedes the answer) and `text` that span's own
  reasoning (clients place replayed text by span, never by splitting the joined
  `reasoning`; `tools[].reasoning` is only the inter-tool prose); absent on
  turns without reasoning and on pre-field sessions, where clients fall back to
  `reasoned_s`. Each step restarts the span clock at its model call.
  `session_changed.in_flight` is true only for the in-flight stub save; a
  crashed chat turn still closes with `in_flight: false`.

- **Session ownership is `(connection_id, device_id)`, gated by the
  connection's `session_scope`.** `Session` persists both ids; every host verb
  that lists, reads, continues, cancels or deletes a session goes through
  `connection_context.owns_session(connection_id, device_id)` (row form:
  `owns_session_row`; agent tools use `can_read_session`, which keeps the admin
  bypass). Under `session_scope: connection` (default) the device clause is a
  no-op; under `device` a remote device sees only sessions carrying its own
  `device_id`, and sessions with no `device_id` (pre-flag, scheduler,
  `host.chat.delegate`) stay visible to the whole connection. The local socket
  never applies the device clause. The events that carry session text, `session_changed`,
  `chat.turn_done` (the first 200 characters of the reply), `file_mutations` (a diff
  preview) and the `approval.*` and `clarification.*` prompts, carry both ids, and
  `server._filter_session_events` (`_OWNED_EVENTS`) drops foreign ones for members, next to the
  role redaction. `_PROMPT_EVENTS` also filters questions and approvals by connection
  for remote admins, without narrowing their other session events or sharing within
  the connection. Ownerless prompts are hidden from all remote clients. A new event
  that carries session text joins the owned set. Never filter by
  `owns_connection` alone in a new session verb. Those two
  events recorded without an owner are hidden from members altogether. `tests/host/test_device_scope_matrix.py`
  writes as device A and reads as device B through each path it lists (the session verbs, replay,
  runs, activity, prompts, summaries, events and the session tools); a new path is one more row.
  Profile-wide data is shared by design: workgroup posts, memory and the files an admin may read.
  The remaining scope gaps are tracked in `docs/ROADMAP.md`. A device with `provisioner: true` may call the `_SELF_SERVICE_METHODS`
  (`add_device`, `pairing_status`, `cancel_pairing`, `revoke_device`) on its own
  `connection_id` without the admin role; those verbs are `_SCOPE_FREE_METHODS`
  because they carry no profile.
- **A workgroup post carries the fence of whoever made it, and the turns it wakes keep it.**
  `workgroup_client.post` and `send_file` (the `#file` marker, `workgroup.file_put`) stamp `origin` (`alpi/authority.py::current`: `member`, `peer`, or
  `allow` with the list; absent means admin) on the transcript entry, locally or as the
  optional `origin` param of `workgroup.post`, which the hub normalises with
  `authority.sanitize` (what it does not understand becomes `peer`). Each of the four
  `_dispatch_workgroup_turn` call sites folds the origins of the posts the turn will see
  (`service._wake_authority`: the last `_RECENT_POSTS`, the open task's opener and every post past the
  turn's cursor) with
  `authority.fold` (the strictest fence wins, peer over member, and the tool lists intersect, so a list mixed with a fence keeps both: `{"fence": "member", "allow": [...]}`) and
  passes it as `ALPI_WORKGROUP_AUTHORITY`; `cli._run_once` applies it with `authority.apply`
  before the `Engine` is built, so the child's tools, nested execution and posts see the same
  fence; `authority.environ()` puts it in the environment of the skill scripts and shell commands a
  fenced turn starts, and `authority.current` falls back to it, so a CLI they run stamps its posts too. A child with an unreadable value is fenced as `peer`, and the daemon clears
  an inherited value when a turn is not fenced. A new dispatch site passes `authority=`
  (`tests/alp/test_workgroup_authority.py` fails otherwise).

- **Shared look and interaction rules of the apps.** `common/tokens.mjs` is the one value source;
  `desktop/src/styles/tokens.css` restates it for CSS and `mobile/src/theme/tokens.js` re-exports it, each held equal by a
  parity test, with no per-client override. **Surfaces**: four, identical on both clients (`surfaces`): `side` (sidebar,
  `#f6f6f6` / `#121212`), `pane` (content and the phone's ground, `#ffffff` / `#1a1a1a`), `fill` (bubbles, fields, the
  composer, cards, row groups, chips, `#f2f2f2` / `#262626`) and `raised` (menus, popovers, dialogs, sheets, toasts:
  `#ffffff` with a soft float shadow in light, `#2c2c2c` with a 1 px `rgba(237,237,237,.09)` edge and a shadow in dark,
  `floatShadow`); the older names `bg`, `bgInput`, `card` and `field` are `pane` and `fill`. Inks `ink`, `ink2`, `ink3`
  (`#6b6b6b` / `#969696`, 4.5:1 on every surface), `edge` (about 3:1, the off track of a switch, an unchecked box) and
  `accent` (alpi's ink, cream in dark). Surfaces part by tone and space, never by a grey rule: no hairlines between rows,
  headers or pickers on either client, and none anywhere on the phone; the chat header and the composer fade into the stream
  with a gradient. **Type**: six sizes (`typeLadder`, `--text-*`): meta 12 (times, counts, hints: the floor, nothing smaller
  ships), small 14 (descriptions, previews, section labels, chips), ui 15 (rows, buttons, menus, fields, settings labels),
  read 16 (messages and the composer), title 20 (screen, dialog and sheet titles, names in headers), display 28 (first run,
  empty states, the phone's large titles); the old names in `fontSizes` alias onto these six. Geist 400/500/600 for every
  word; Geist Mono only for machine text (code, paths, commands, model ids, tool ids) at 0.92 of its role and never under
  12 (`monoScale`; desktop `--text-mono*` and `.mono` at `max(var(--text-meta), 0.92em)`, mobile `theme/code.js`; the phone's
  Small text size clamps every scaled size at 12 too); Bricolage 800 in `nameTone` only where a name stands
  alone (tile, header, hero). Section labels (`eyebrow`) are 14 px sans 500 in `ink3`, sentence case, no tracking.
  **Space** is one 4-pt grid, 4·8·12·16·24·32·48 (`spaceScale`, `--sp-*`; the `space.s*` names alias onto it), with the
  1, 2 and 3 px micro nudges. **Heights** 32 compact (dense rows, chips, in-row buttons), 40 every desktop control, 48
  every phone control (`controlHeight`, `--ctl-*`); phone targets are at least 44 pt (`touchTarget`). **Icons** 16 / 20 / 24
  (`iconSizes`) at a rendered stroke of 1.5. **Corners** say what a thing does (`radii`, `--r-*`): `xs` 6 (checkbox, key
  cap, inline code, tooltip), `control` 12 (what you type in, list rows, menu items, the selection fill), `surface` 20
  (cards, row groups, bubbles, menus, popovers, toasts, approvals, tiles), `sheet` 28 (dialogs, sheets, the palette, the
  composer) and `pill` (everything you press: buttons, icon buttons, chips, selects, segments, switches); `chip` and the
  older names are retired and both `paperDirection` scanners flag them and any literal corner; a surface that meets its
  container's edge is square there (panes, the sidebar, headers, banners, the bottom of a phone sheet). **States**: one
  neutral ladder per mode (`stateFills`): hover ink 4 % / 5 %, selected 8 % / 9 %, pressed 12 % / 13 %; hover is colour
  only, fading in over `fast` (120 ms, enter curve) and out over `exit` (130 ms, exit curve) (`stateMotion`,
  `--state-in` / `--state-out`), pressed is instant and reduced motion drops the transition; there is one selection look,
  the neutral fill at `control` (never an outline, stripe, accent or ink chip on a row), and a highlighted menu or palette
  item takes the fill without a ring; disabled is `alpha.disabled` 0.45 everywhere. **Work line** (desktop `features/ToolSteps.jsx` and mobile `features/chat/ProcessBlock.jsx`, words in `common/workLine.mjs`): a turn's reasoning and tool calls are one closed line above the answer, the clients' counterpart of the console's steps row: the profile's mark at `MARK_SIZES.row` (24, working while the turn runs, idle once done), then `Working` with the newest step in plain words (`stepPhrase`: Reading deploy.log, Running npm test, Thinking) and a clock, or `Worked for 34s · 6 steps · 1 failed` (the wall span of the tools plus any thinking before the first or after the last; steps count tools and thoughts); it stays Working until the turn closes, between rounds too (Writing while text streams before the next step), the clock restarts with each new turn, and the step is announced to screen readers; it opens into every step in order, indented under the mark with no rule, each step keeping its own open state (on the phone a step still opens its sheet); 32 px high on desktop, 36 pt with a 44 pt target on the phone. **Unsaved drafts**: desktop Settings never drops a dirty field (`lib/settingsDirty.js`): App's `setView`, `setSettingsTarget` and the connection switch refuse to leave Settings while a field is dirty and say "Save or discard your settings changes first", so ⌘,, the menu's Settings… (which also closes Settings), the tray, Back to chat, ⌘1–9 and every other route behave alike; on the phone every form asks before back drops what was typed (`useDirtyBack`, whose `.leave()` exits after a save). An open workgroup that leaves the roster falls back to the workgroups list with a notice, like a removed profile falls back to the landing. **Settings rows** (desktop, `primitives/SettingsLayout`): a sentence-case label on the left and a 340 px control column on the right whose content ends on one edge: a wrapper that is the control's only child is right-justified, and the ghost button that really ends the row (or each line; popovers and confirms beside it do not count) is marked `data-trailing` by `Field` and lends its padding to the gutter (12 px at sm, 16 at md) so its label meets the edge chips reach; a top-aligned row keeps its content left; a row with two lines is `stacked` (`FieldLine` per line, right-aligned, the label on the first line), and a note about the row is its helper under the label. **Surface motion** (desktop, `design-system.css`, on the shipped `motionTokens` and nothing new): a dialog rises 8 px and settles from 0.98 over `enter` (the veil only fades), a menu, popover or dropdown drifts 4 px out of its anchor and settles from 0.98 over `fast` from the anchor corner (`.anim-menu`, `--menu-dy`, `transform-origin` from the placement), a toast rises 8 px; every exit runs over `exit` on the exit curve at half the entrance travel (a dialog and a toast sink 4 px, a menu only settles to 0.98), and a leaving menu is `inert` and out of the overlay stack so focus returns at once (`useExit` keeps it mounted for the exit and drops it at once under reduced motion); the same applies to every window that opens over the app: the launcher panels (palette, Activity, shortcuts, connections) rise in under a fading scrim, and the browse windows (notifications, skills, memory, tools, schedule), the sessions manager and the image preview do too, each kept mounted by `useExit` for its exit; the settings detail popovers of a device or a peer enter the same way but are removed by their owner without an exit, and only the usage tooltip keeps the plain fade. **Focus**: a pressable shows a 2 px
  ring of ink at 60 % offset 2 only on keyboard focus (`focusRing`; desktop `:focus-visible`, the phone through
  `components/focusRing.js` on hardware-keyboard focus, so touch never draws it), at 3:1 or more on side, pane and fill; a
  field shows focus as a 1.5 px inset `ink3` line (`fieldFocus`, `--field-focus`) and an invalid one a 1.5 px `dangerText`
  line, keeping its fill; the composer shows no ring (the caret is its focus). **Controls** follow `common/button.mjs` and
  `common/well.mjs`: buttons are pills (desktop sm 32 / md 40 / hero 48, phone 44 / 48), labels medium, the primary fills
  with `accent` and steps 86 / 78 % toward the pane on hover and press, secondary and ghost take the state fills, and a
  loading button keeps its label beside the spinner; icon buttons are round (32 / 40 on desktop, 44 on the phone); fields
  are 40 / 48 tall on the `fill` at `control`; selects are pills on the fill; the segmented control is a pill track with
  the chosen cell `raised` and semibold, edged in dark with a 1 px `line2` ring (`--shadow-cell`) where raised and fill
  sit too close; a well that sits on another fill recesses: inside a desktop float (`--well-float`, the pane in dark like the
  phone's `recess()`), inside an inline request card (its fields and secondary choices, `--well-nested`), code in your
  bubble, and a phone `Pill` on a card all take the pane; chips are 32 px pills at 14 px with the chosen filter in ink. A desktop `Field` carries an
  optional helper or error line linked by `aria-describedby`.
  **Shell (desktop)**: the sidebar is 272 px of `side`: the connection switcher alone on top (its "Connection" label for
  screen readers only), with no icon buttons beside it and no general new-session button (a session starts from a
  profile's row menu or ⌘N); pinned profiles as tiles (`MARK_SIZES.tile` 48 px mark with the name under it in
  Bricolage and `nameTone`, a needs or failed pip, selection by the fill, three to a row on the 12 px nav gutter the rows and
  the switcher use, evenly spaced and wrapping in rows of three, a long name truncated with the full name in its label;
  never following the pointer), the default profile the first tile; then 40 px
  rows with 24 px marks and 15 px names under 14 px sentence-case section labels; the footer holds Settings, notifications,
  Activity, Search (it opens the palette, ⌘K in its tooltip), the theme button and the version, all 32 px round icon
  buttons, the bell and Activity showing a plain 8 px danger dot. The chat header is
  56 px under the 38 px titlebar band (`--titlebar-h`), level with the connection switcher, its items centred on one line
  from the pane's 32 px edge (`--pane-pad-x`): the mark at 28, the name in Bricolage at 20 (an `h1` outside the menu button,
  which it names through `aria-labelledby`) and a chevron; the pill opens the profile menu holding Model, the full model id,
  Context and Cost today (a workgroup's holds hub, members, status and budget); there is no meta line under the name. A
  passive 8 px dot beside the name (warning, danger at 100 %, spoken by its label) shows when the context or the daily
  budget reaches 80 %, and for a workgroup while its pipeline needs the user or failed; the phone header carries the same
  dot beside the chip, and its popover speaks the full model id. The settings pages (profile, workgroup, connections) wear the same
  56 px bar: the mark, the name, a 20 px sentence-case "Settings" or "Connections" in `ink3`, the chevron opening their
  details, and the page's actions ending in Back to chat. The workgroups list wears that bar too: the honeycomb, the name
  "Workgroups" and its counts behind the chevron. Connections and its audit log put the bar, the search and the table in
  one centred column the width of the table (`--stream-max` + 200 px; the settings forms keep the left edge beside their
  rail); each paired connection reads its access first (`common/connectionAccess.mjs`): "All profiles" for an admin or an
  empty scope, otherwise up to three profiles in scope as their 16 px mark and their name in its `nameTone`, then +N with
  the rest in the tooltip and every name in the accessible label, and a name the roster no longer has struck in ink 3
  with no mark; the role and the devices follow in ink 3. The phone's connection list and the Profiles row of its
  connection detail draw the same access line, and on the fold the list's and the detail's column is centred. The stream is
  a 760 px column (`--stream-max`) with 24 px between turns; your message sits in a `fill` bubble at `surface`, an answer is
  plain 16 px prose; a turn's time sits on its outer edge (the bubble's right edge for yours, the text's left edge for an
  answer) with its actions inside it, so actions hidden at rest never move it. The composer is one pill on the `fill` at `sheet`, at least 56 px: a leading + (attach; its tooltip
  names @ mentions), the 16 px input, the model picker (it opens the effort choice, which applies on pick; the label is
  truncated before its effort) and a round send whose tooltip names ⌘↵; there is no hint row, and a composer error or
  paused reason shows on its status line. **Shell (phone)**: the roster leads with the default profile and pinned profiles
  as 48 px tiles with names under them (three equal columns, as on desktop), then 64 px rows with 40 px marks, a 15 px name and a 14 px preview; the chat header of a ready profile
  is one 56 pt row: Back at the left, the profile chip centred between two 88 pt side columns (the mark at 28, the name at 20
  and a chevron, 44 pt high, pill radius), Sessions and More at the right (a read-aloud wave sits beside the chip), and no model line; a tap on the chip opens a popover
  with Model (mono, the full id beneath), Context and Cost today meters (a row is left out when the daemon sent no value, and with none the chip has no popover), closed by a tap outside or Back, and the profile
  menu's subtitle carries model, context and cost; the composer is the 56 px pill with + (attach, mention, model and effort; the menu floats in a modal layer and a tap
  outside closes it) and a round send; two panes
  (the Fold) keep the 24 px sidebar rows. Settings rows on both clients are a 15 px label over a 14 px sans description
  with the control on the right, at least 56 px tall; phone groups are one `fill` card at `surface`. **Floating**: menus,
  popovers and toasts sit on `raised` at `surface` with an 8 px inset, 40 px rows, 20 px icons and 15 px items, groups
  parted by 8 px of space; one menu primitive serves every desktop menu (Dropdown, header menu, context menu: check slot,
  danger variant, roles `menu`, `menuitemradio`, `menuitemcheckbox`); dialogs, the palette and phone sheets are `sheet`
  with 20 px titles over a dim veil (`veils`: ink 22 % in light, black 55 % in dark), sheets square at the bottom edge;
  the palette has a 56 px search at 16 px and 48 px rows; the tooltip is an ink fill at `xs`, 12 px medium, no tracking. Count
  badges are sans 600 (`common/countBadge.mjs`). One confirm dialog
  (optional typed field) replaces every destructive native alert on the phone. Toasts stack at the bottom right on desktop
  and are for failures and undo windows: info lasts 2.8 s; an error has Dismiss and an optional Retry and persists only
  when it offers Retry (6 s otherwise); a copy confirms in place (the desktop button label flips for about 1.5 s, the
  phone toasts). **Banners**: every status banner (`Banner`) and alert banner (`AlertBanner`) on both clients is one flat,
  square tint of its kind's hue mixed into the pane (warning, danger and success 10 % light / 14 % dark, `--banner-tint`;
  info a neutral ink at 5 % / 6 %, `--banner-tint-quiet`; on the phone `components/bannerTones.js`) with no rule, ring,
  radius or shadow and 14 px text: warning and danger lead with the alert glyph in their text colour, info with the `ink3`
  dot and success with its text-colour dot, the message is `ink2` and the action is plain text in the kind's text colour
  (44 pt on the phone), every text at 4.5:1 or more. A paused composer dims only the input and keeps its reason readable;
  the paused banner holds the one Resume; an offline reason stays visible, and the connection banner (with Manage on the
  phone) owns the outage, so the Connection sheet never opens by itself. Statuses collapse to active, paused, attention and
  failed (`lib/statusVocab.js`); a row's state word (needs you, failed, working) takes the trailing slot in its kind's text
  colour; muted roster rows keep `ink3` with a micro-label (`paused`, needs provider) instead of fading. The four profile panels (Memories, Skills, Tools, Schedules) share one list row on both clients (desktop `BrowseRow` in
  `primitives/BrowseModal.jsx`, phone `components/PanelRow.jsx`): a 15 px medium title with an ellipsis, a 14 px `ink3` second
  line clamped to two lines (for a tool, the first sentence of its description), one 12 px tabular meta at the right (a
  job's next run, a skill's size such as `4.2 KB`, a memory file's share such as `64%`, or nothing) that a state word
  replaces (inactive, paused, failed, denied, over, full; failed, invalid, lint, missing, over and full in the danger text
  colour), and Memories' 3 px meter as a third line; padding 8 × 12 (12 × 16 in a phone tile), neutral hover and selected
  fills, no dots, pills or fading (an off item keeps an `ink2` title), group labels in sentence case, and the selected row
  lifts the second line and the meta to `ink2`, because `ink3` on the selected fill is under 4.5:1. A phone job row has no
  last-result line. Every detail opens on one header (`BrowseDetailHead`, phone `components/DetailHead.jsx`): a 20 px
  semibold title with the state as a 14 px `ink3` word, the id or path (`research/hotel-intake`, `web_fetch`,
  `MEMORY.md`, the job id) in mono with a copy button, and the actions at the right (a job's Run now, Pause and Delete on
  desktop; Edit on a memory file), then one facts table (`FactTable`; 84 px labels on desktop, 72 on the phone, 14 px
  sentence-case `ink3` labels, 14 px `ink2` values, mono only for ids): a skill's About, Requires, Tools, Platforms,
  Keywords (plain text) and Version (version, origin and date); a tool's About and Category above its parameters; a memory
  file's About, Usage, Entries and Updated; a job's About, When (the cron in mono), Next, Last run, Runs, Timeout and
  Notify. The size, first-sentence and meta rules live in `common/panelRow.mjs`. `EmptyState` takes
  an `action`; a chat approval card has one primary action; usage bars under 1 % are hidden and one chevron marks every
  disclosure; the count badge follows `common/countBadge.mjs`. Theme (System, Light, Dark) and text size (four steps) are
  `Segmented` controls in the phone's Settings; on desktop the theme is a control in the default profile's settings, the
  sidebar footer's theme button and the palette's Switch theme. In two panes (a tablet or an unfolded phone) the mobile
  sidebar footer is the desktop one: Settings, notifications, Activity, the profile filter (it leaves the connection
  header) and the theme button cycling Light, Dark and System, as 40 pt icons with 44 pt targets, then the version; the
  one-pane phone footer stays Settings, Notifications and Activity with labels. Panels and sheets are dialogs with a label. A loading
  state draws the silhouette of what is loading in the `line` ink, with real titles and labels kept as text and no slab
  for a composite widget (the usage widget loads as its four tiles and fourteen day bars): flat bones with no gradient or
  shimmer share one breathing animation (opacity 0.55 to 1 over 1.6 s, 90 ms stagger per row; static under reduced
  motion), appear after 150 ms, stay at least 400 ms once shown (the whole-list and reader skeletons keep only the 150 ms
  delay), and give way to the content with a 120 ms fade when bones were shown.

## Non-obvious things to know

- `rich.markup.escape()` any user-controlled substring before passing to `Text.from_markup()`. Several past crashes from `[exit 0]`-style tokens in tool output.
- Tool results are capped per-tool by `alpi/tools/_budget.py` (default 100,000 chars; override via `tools.<name>.max_result_chars`).
- `last_ctx_tokens` (current prompt size) ≠ cumulative `input_tokens`. Header shows the former.
- `call_from_thread` + Python built-in methods (e.g. `dict.pop`) crashes Textual; always wrap in a regular function.
- `cfg` must be loaded BEFORE `super().__init__()` on `AlpiApp`. The theme is then registered immediately after, in `__init__` rather than `on_mount`, because child widgets read `self.app.theme_variables` during their own mount (which fires first). `self.get_css_variables()` is called explicitly to rebuild the var dict synchronously — setting `self.theme` alone schedules the refresh for the next event-loop tick.
- Schedule subprocess uses `alpi chat --once --emit-events --no-save` — same event stream, no resumable session file.
- `ALPI_HOME` env var routes daemons + tests to a specific profile root.
- `ALPI_SKIP_UPDATE_CHECK=1` short-circuits the background PyPI version check (`alpi/updater.py`); the autouse fixture in `tests/conftest.py` sets it so the unit suite never reaches PyPI. `ALPI_UPDATE_INDEX` overrides the JSON URL the updater hits when you need a staging or local mirror.
