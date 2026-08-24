# Architecture

Living technical reference for alpi at HEAD. Describes only what currently
ships — historical decisions live in commit messages, planned work lives
in [ROADMAP.md](ROADMAP.md).

Audience: any developer (or LLM) reading this codebase from cold.

## What alpi is

alpi is a local-first personal AI agent. It has a Textual TUI in the
terminal, a Tauri desktop app (and a planned mobile client) that
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
Knowledge, Digital Sovereignty). See the **Why alpi is built like
this** section in `README.md` for the mapping between principle and
code. The conventions below are the engineering expression of those
principles — not separate from them.

- **Focused.** Every feature earns its keep. No over-engineering. Maps to Satoshi's "constraint breeds coherence" heuristic.
- **Solid base.** Core loop, memory, tools, paths, scanner before surface features.
- **User in control.** No destructive action without explicit OK. No silent migrations. Expression of **User Sovereignty**.
- **Python stack.** No Go rewrite (loses LiteLLM, tests, no upside).
- **No legacy code.** When a schema or layout changes, it's a clean break — no compat shims, no auto-migration. Anything from yesterday's iteration is cleaned by hand, not by `ensure_home`.
- **Closed protocol, own transport.** ALP is not A2A / MCP-over-network / gRPC. Every verb we don't ship is an attack surface we don't own. Expression of **Privacy by Design** + **Security First**.

## Code conventions

**No human-facing comments in `alpi/` source.** The reader is an LLM. Narrative prose, banner dividers, section labels, restatement docstrings — token tax. See `feedback_no_human_comments.md` in agent memory for the full rule. Tests, docs, and tool `description` strings are out of scope (those serve other audiences).

**English only.** All text inside `alpi/` (code, docstrings, prompts, tool descriptions, error messages, seed comments) is English. The LLM reads these every turn; embedding Spanish nudges replies toward Spanish. User-facing runtime output follows the user's language.

**No comments without "why".** A comment survives only if removing it would mislead a future reader into a wrong edit or waste their time re-deriving an external fact. `or`-chains and try/except blocks are self-evidently intentional; documenting them is fluff.

## CLI surface

Stable verbs shared across groups so a user doesn't relearn per feature.

```
alpi                           launch the TUI
alpi -c / --continue           resume the last session in the TUI
alpi -p <name>                 profile flag, combinable with any command

alpi chat                      alias for `alpi`
alpi chat --once "<text>"      one-shot turn to stdout (pipe-friendly)
alpi chat --once ... -c | --session <id>   continue the last / a specific session (one-shot)
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

alpi profile list              list profiles, mark the active one
alpi profile create <name>     bootstrap a new profile tree
alpi profile remove <name>     delete after safety checks + confirm

alpi daemon install|uninstall                  register / unregister the launchd plist / systemd unit
alpi daemon start|stop|restart|status          lifecycle of the single per-machine daemon
alpi schedule run-once|fire <id>                manual cron tick / ad-hoc job fire (operational, not lifecycle)

alpi peers list                list pinned ALP peers for this profile
alpi peers key                 print this profile's ALP public key
alpi peers add <id> <pubkey>   pin a peer (prefer the wizard for capability selection)
alpi peers remove <id>         unpin a peer
alpi peers ping <id>           live probe via link.ping

alpi workgroup list                                list workgroups (hub-of + member-of)
alpi workgroup show <wg_id>                        detail + decrypted transcript
alpi workgroup create <name> --member <id|pubkey>  hub-side create (auto-grants verbs to invited peers)
alpi workgroup join <hub_peer_id> <wg_id>          subscribe to a peer-hosted workgroup
alpi workgroup post <wg_id> <text>                 encrypt + post; cost is auto-declared in PR 5
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
├── service.py              unified orchestrator — runs isolated daemon tasks on one asyncio loop; installs one launchd / systemd unit per machine
├── ledger.py               daily spend ledger (logs/ledger.json: live counters + 30-day per-day history) + profile cap gate
├── outputs.py              persistent inbox JSONL store (notify + schedule failures)
├── status.py               canonical /status rows (TUI + apps share this)
├── prompts/
│   ├── default_agent.md
│   └── system_prompt.md
├── providers/              metadata for the model picker
│   └── {anthropic,openai,google,groq,openrouter,custom}.py
├── tools/
│   ├── base.py             Tool ABC + ToolResult
│   ├── _state.py           ContextVar-backed emit / interrupt / usage (per-thread isolated for batch sub-agents)
│   ├── _paths.py           resolve_path + sensitive-path denylist
│   ├── _guards.py          terminal denylist, SSRF, prompt-injection scan
│   ├── _budget.py          per-result char cap for LLM context (100K default, per-tool override)
│   ├── _osv.py             OSV malware query for PyPI/npm names before skill/MCP install
│   ├── _sandbox.py         OS-level sandbox wrapper (opt-in)
│   ├── skill.py            create/edit/patch/add_file/remove_file/delete/list/view + scanner + quota
│   ├── search.py           content + filename search (rg + stdlib fallback)
│   ├── research.py         read-only sub-agent (depth: fast/normal/deep)
│   ├── terminal.py         run/background/status/output/kill
│   ├── workflow.py         bounded tool DAGs routed through ToolExecutor
│   ├── notify.py           native push to the owner's apps
│   └── … (read_file, write_file, edit_file, delete_file, todo, web_*, schedule,
│         memory, session_search, email, config)
├── tui/                    Textual app, widgets, screens, theme
├── scheduler/              cron + once jobs, hosted by the alpi daemon
├── mail/                   multi-account email — accounts.py (account model + per-account env/token resolution); imap.py (IMAP+SMTP); gmail.py (Gmail API + OAuth)
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
│   ├── chat.py            host.chat.send (streaming) + host.chat.cancel
│   ├── runs.py            host.runs.list + host.run.{read,cancel}
│   ├── config.py          mutation verbs (host.providers.*, host.peers.*, host.profile.*, host.mcp.*, host.email.*, host.sandbox.*, host.voice.*)
│   ├── connections.py     host.connections.* identities, device credentials and devices.yaml migration
│   ├── connection_context.py request-scoped connection/device attribution
│   ├── admin_audit.py     bounded JSONL trail for attributable administrative mutations + host.audit.list
│   ├── attachments_rpc.py host.attachments.{stage,fetch} — stage uploads in, fetch serves a tool-produced output attachment's bytes out (scoped to the profile's workspace/home/temp) so rich clients render images inline + other files as a metadata chip; text surfaces get a shared listing
│   ├── network_rpc.py     host.network.{status,set_advertised,restart_host_server} — bind status plus ordered WS/WSS pairing-route configuration (parity with `alpi setup → Connections → Network`)
│   ├── probes.py          host.email.probe, host.peers.ping, host.model.ctx_window
│   ├── schedule.py        host.schedule.{list,remove,set_paused,fire}
│   ├── outputs.py         host.outputs.{list,read,mark_read,mark_all_read,delete}
│   ├── daemon.py          host.daemon.{restart,update}
│   ├── device_state.py    device-facing profile state (profiles, summaries, storage, email, skills, workgroups)
│   ├── events.py          host.events.subscribe + thread-safe emit() for daemon-pushed updates
│   ├── workgroup.py       transcript decryption (hub + member shapes)
│   └── sessions.py        plaintext session list / read
└── knowledge/              `alpi_knowledge` answer packs — Markdown the tool reads (see docs/SKILLS.md)
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

Each turn writes `runs/<run_id>.jsonl` with bounded, redacted events. The
`run_id` is carried by host chat stream frames and the existing run ledger.
Local operators use `alpi runs list|show|cancel` or `/runs`; paired clients use
`host.runs.list`, `host.run.read`, and `host.run.cancel`. Reads and cancellation
are connection-scoped like sessions, while the sovereign local socket can stop
any active run. Terminal command text is omitted from the journal, saved turn
metadata, and chat replay sidecar, including terminal steps nested in a
workflow. Listing reads the first and last journal records rather than replaying
the event stream; Cleanup offers inactive journals older than 30 days.

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
├── mentions/<sender>.json  per-sender @-mention threads (cap 20 turns), receiving side
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

Per turn: append user message → loop {LLM stream → emit deltas → exec tool calls → append tool results} until the LLM stops emitting tool calls OR the effective step ceiling is hit — `max_steps_per_turn` (default 100), raised to 1000 for free (zero-priced) or local/ollama models **when left at the default**; an explicit value is always respected. Hitting the ceiling does not drop the turn: the engine makes one tools-off wrap-up call so the model still returns a best-effort final reply. `interrupt_requested` is polled at three checkpoints (between iterations, mid-stream, between tool calls). A turn lock serializes concurrent runs so a delayed `research` tool from the previous turn can't bleed into the next.

Events emitted to the UI sink: `user`, `reasoning_delta`, `assistant_delta`, `assistant_done`, `tool_start`, `tool_state`, `tool_end`, `usage`, `error`, `done`, `interrupted`. The TUI consumes them; the scheduler subprocess consumes a subset via JSON-lines.

**Cross-turn resume.** A chat is not a long-lived object: each turn spins up a fresh `Engine` and rehydrates the session from disk (`_hydrate_from_path` in `cli.py`, shared by TUI `--continue` and the host chat; the desktop "edit message" rewrite path mirrors it in `host/chat.py`). The model context is rebuilt from the prior **replayable** turns — those that ended in a final reply or produced a file; a turn aborted before its reply (no assistant text, no output files) is dropped, so a resumed session never re-answers a dangling request. Each replayed turn contributes its user text (plus an input-attachment marker `[attached: name (mime)]`) and assistant text (plus a produced-file marker `[produced this turn — reuse the absolute path…: name → /abs/path]`). Tool calls and tool results are deliberately **not** replayed — they would blow the context budget — so an agent does not remember what it searched, read, or analyzed last turn, only its final reply and the absolute paths of the files it produced. A multi-turn edit ("now relight it at sunset") reuses the produced path surfaced by the marker, not a remembered tool output; an agent that needs an earlier tool's result across turns must re-run the tool or rely on a produced file.

The system prompt for each turn is built from: `AGENT.md` (agent profile — voice, style, identity) → base prompt → environment block (workspace, profile home, path rule) → **platform hint** (`_platform_hint()` — injects per-surface guidance when `ALPI_PLATFORM` is set by the caller: `cron`; empty for TUI and the apps) → **skills index** (auto-injected by `alpi.tools.skill.skills_index_block`) → `USER.md` → `MEMORY.md`.

The scheduler (`alpi/scheduler/run.py`) sets `ALPI_PLATFORM=cron` so scheduled jobs run knowing no user is present and they cannot ask for clarification. Each fire runs as a subprocess capped at `job_run_timeout(job)` seconds — `job.timeout` if set, else `DEFAULT_RUN_TIMEOUT_SECONDS` (900), clamped to `[30, MAX_RUN_TIMEOUT_SECONDS]` (3600). The cap is a stuck-process backstop for unattended runs, not the cost guard (`budget.daily_usd` is) and not a hint that jobs must be short; heavy jobs (deep research, multi-step publishing) opt into a longer budget via `schedule(add|update, timeout=…)`. The scheduler passes the child a soft budget via `ALPI_TURN_BUDGET_S` (the cap minus a ~10% reserve, floor 60s); when the engine crosses it mid-turn it makes one tools-off wrap-up call and returns a best-effort final reply instead of being killed with nothing — the same graceful close the max-step ceiling gets. The hard `subprocess` timeout remains as the last-resort kill if the wrap-up itself stalls.

Cron jobs with `no_agent: true` skip the LLM entirely. The `prompt` is shlex-tokenized and exec'd directly (`shell=False`); `${ALPI_HOME}` expands to the profile home and the profile's `.env` overrides inherited env keys so skills find their declared `requires_env`. A form-based allowlist enforces that the command is `python[3] [flags] <script>` or `<script>` invoked directly, where `<script>` resolves to `<home>/skills/<category>/<name>/scripts/…`; non-python executables and `-c`/`-m` inline-code flags are rejected at both `schedule(add)` time and inside the scheduler before exec. Use this for deterministic skills (sync, file processors) — saves both tokens and the agent boot latency per fire.

### LLM transport (`alpi/llm.py`)

Thin wrapper over `litellm.completion`. `stream()` is an async generator yielding `{text_delta, reasoning_delta, tool_calls_delta, finish_reason}` per chunk plus a final `{final, tool_calls, input_tokens, output_tokens, cost_usd}`. `complete()` is the non-streaming variant used by `research`. `_silence_litellm()` runs at import time to mute LiteLLM's startup banner via FD-level redirect (Textual is sensitive to stdout pollution).

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

`suggest_similar_paths(target)` lists the parent directory and fuzzy-matches siblings by basename substring/prefix. Used by `read_file`, `edit_file`, and `search` to turn dead-end errors into actionable suggestions.

`alpi/tools/_lint.py::lint_content(path, content)` runs a parser-based syntax check before every `write_file` / `edit_file` lands on disk. Parsers by suffix: `.py` → `ast.parse` (stdlib), `.json` → `json.loads` (stdlib), `.yaml`/`.yml` → `yaml.safe_load` (PyYAML, already a dep), `.toml` → `tomllib.loads` (stdlib on 3.11+, with `tomli` declared as a conditional dep for 3.10). Other suffixes pass through. Failures return a one-line error with the source line/col and the write is refused — the original file (if any) is untouched. Catches the class of bug where a malformed `jobs.json`, `config.yaml`, or skill script silently breaks a downstream consumer.

`alpi/secrets_io.py::safe_write_secret(path, content, mode=0o600)` is the canonical write path for any credential file. It uses `tempfile.mkstemp` (O_EXCL + 0o600 at creation, random unique name in the target dir), then `os.replace` onto the target — no TOCTOU window where the file exists at umask perms, and a stale `<target>.tmp` lingering at looser perms cannot compromise the write because the helper picks a fresh random name. Used by `model_selector._atomic_write_env` (.env writes), `mail/gmail_auth._save` (gmail token), `alp/pending.save` (pending-peers yaml), and `alp/keys.create` (ALP private key).

### Tool registry (`alpi/tools/__init__.py`)

`register(cls)` adds a `Tool` subclass to the dict, `schemas()` emits the OpenAI function-calling shape, `execute(name, args)` runs by name with full error capture. The registry is assembled from the sibling tool modules in `alpi/tools/__init__.py`, including the Playwright-backed `browser` tool. `knowledge` registers first so durable user/workspace recall has one canonical surface.

A tool's `check()` is what keeps `schemas()` honest: an unavailable tool is never offered to the model, so the probe has to test the thing that actually fails at call time, not a proxy for it. `browser` is the cautionary case — probing only `import playwright` advertised the tool on every slim Linux image, where playwright downloads the browser on demand and then cannot launch it because the distro never installed Chromium's load-time libraries. It now `dlopen`s one soname per Debian package family (`_CHROMIUM_SONAMES`, Linux-only, ~2 ms when they are absent) and reports the missing set plus `CHROMIUM_DEPS_COMMAND` — a `uvx --from playwright …` invocation, because `uv tool install` links only alpi-agent's own entry points and a bare `playwright` is not on `PATH`.

The image cannot be held to that list by a unit test: `pip install .` ignores `uv.lock`, so the playwright inside the image outruns the one the suite imports (observed: 1.62 vs 1.58). So `docker/Dockerfile` derives the packages from its own playwright (`playwright install-deps chromium-headless-shell`) instead of carrying a hand-written copy, and `publish-docker.yml` launches the real headless shell in the built image before anything is pushed. `ensure_chromium()` installs with `--only-shell` because `chromium.launch(headless=True)` runs `chrome-headless-shell`; the full Chromium build was never used, and `_wanted_chromium_dirs()` now tracks only the shell so an existing profile's stale full build is pruned (~640 MB reclaimed per profile).

### Knowledge recall (`alpi/core/` + `alpi/tools/knowledge_base.py`)

Per-profile semantic search over synthesized user/workspace knowledge. The
source of truth is Markdown under `<workspace>/knowledge/`; SQLite under
`<home>/knowledge.sqlite` is only a rebuildable derived index. Raw source files
and attachments are read only as inputs for synthesis; alpi does not copy them
into a durable documents store.

- `knowledge(action="search", query, k=5)` — hybrid sqlite-vec + FTS search over OKF pages, returning page-level results (`path`, `title`, `type`, `tags`, `snippet`, `score`, `links`). Use `alpi_knowledge`, not this tool, for questions about alpi itself.
- `knowledge(action="ingest", source_path?|name?, topic?, apply=true, ocr=false)` — explicit learn path. Resolves an existing file or current-turn attachment, validates it with the same attachment allowlist/caps, extracts text (PDF/DOCX/EPUB/HTML/text, OCR for scanned PDF/images when requested), asks the LLM to synthesize durable Markdown pages, updates `index.md` and `log.md`, lints, and refreshes the derived OKF index. The raw file is not copied.
- `knowledge(action="maintain", source_path?, topic?, apply=true, ocr=false)` — explicit LLM-wiki maintenance for reorganizing or updating pages.
- `knowledge(action="lint", path?)` — validates required `index.md` / `log.md`, minimal YAML frontmatter (`type`, `title`, `tags`, `updated_at`, `sources`), relative Markdown links, and orphan pages.
- `knowledge(action="index", path?, force?)` — chunks valid pages, writes `okf_*` tables, sqlite-vec rows, FTS rows, metadata, and outgoing links. Incremental by `mtime` + `size`; `force=true`, root drift, or embedder drift rebuilds only the OKF table family.

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

The bundle uses minimal OKF-style YAML frontmatter, relative Markdown links,
and required `index.md` / `log.md`. It is never auto-injected into the system
prompt; access happens only through `knowledge` tool output.

### Session recall (`alpi/tools/recall.py`)

Recall over **past conversations**, the conversational-memory peer of knowledge recall, in three layers: lexical find (`session_search`, term counts over `sessions/*.json`), exact browse (`session_read`, no model call), and opt-in semantic search (`index_sessions` / `recall_sessions`) for fuzzy "when did we discuss X / what did we decide about Y".

- `session_search(query)` — lexical first layer; returns the tail thread of matching sessions, active session excluded.
- `session_read(session?, phrase?, start?)` — browse layer, no embedding/LLM call: lists recent sessions, or opens a windowed turn slice around an exact phrase or `start` index (paged). Pairs with `session_search` (find → open the window).
- `index_sessions(force?)` — **opt-in** (sessions are never auto-indexed): walks `<home>/sessions/*.json`, builds a per-turn transcript (`user:`/`alpi:` lines), chunks + embeds with the same `core/embed.py` + sqlite-vec primitives as the knowledge index, into a **separate table family** (`session_files` / `session_chunks` / `session_vec` / `session_meta`) in the same `knowledge.sqlite`. Incremental (mtime/size skip); the active session is excluded.
- `recall_sessions(query, k=5)` — cosine MATCH → `[{session_id, when, snippet, score}]`, active session excluded.

**Forgettable.** Recall is a derived view, so forgetting is real: deleting a session (`host.sessions.delete` → `host/sessions.py::delete_session`) purges its rows via `recall.forget_session`, and `index_sessions` orphan-sweeps any tracked session whose file is gone. No auto per-turn injection — retrieval is explicit, like the workspace tools.

### Workgroup transcript search (`alpi/tools/workgroup_search.py`)

The third retrieval surface on the same store: semantic search over **hub-owned** workgroup transcripts. Workgroups are hub-owned by design, so this is **profile-local and hub-only** — the hub decrypts its own transcript and indexes it; there is no cross-peer / federated search and no global "search all my peers' workgroups". Two tools:

- `index_workgroups(workgroup_id?, force?)` — **opt-in**: decrypts each hub-owned transcript via `host/workgroup.py::decrypt_transcript` (key-history aware, so posts written before a rekey still index), groups consecutive posts into ~2 KB chunks tagged `[seq · ts · author]`, embeds, into a **separate table family** (`workgroup_files` / `workgroup_chunks` / `workgroup_vec` / `workgroup_meta`) in the same `knowledge.sqlite`. Posts that don't decrypt (rotated-out key, AEAD failure) are skipped. Incremental (transcript mtime/size); empty `workgroup_id` indexes all hub-owned workgroups on the profile.
- `workgroup_search(workgroup_id, query, k=5)` — search is scoped to one workgroup (brute-force cosine over that workgroup's chunks, so per-workgroup ranking is exact rather than a filtered global KNN). Returns `[{workgroup_id, seq_start, seq_end, when, authors, snippet, score}]`; never returns group keys, ciphertext, or filesystem paths.

**Forgettable.** Removing a workgroup purges its index in both delete paths — the host RPC (`host/workgroup_admin.py::_remove`) and the CLI (`alpi workgroup remove`) call `workgroup_search.forget_workgroup`; `index_workgroups` orphan-sweeps any tracked workgroup whose directory is gone. No auto-injection into workgroup turns. ALP encryption/transcript behaviour is untouched — this only reads through the existing decrypt path.

**Asset prefetch (`service.py::_prefetch_assets`)**. Scheduled by `_main_all` at boot+600 s — deliberately past the client-reconnection rush (at boot+5 s the Chromium unzip + ONNX load starved small Docker hosts, which read as "the machine is blocked"). Gated by `runtime.prefetch` on the root profile: `auto` (default) fetches the fastembed weights only when some profile has `knowledge.sqlite`, and Chromium only when some profile leaves the `browser` tool un-denied; `all` forces both; `off` — the default under `ALPI_PLATFORM=docker` — skips prefetch entirely. Every asset still fetches lazily on first use, so `off` costs latency, never functionality. `ensure_weights_cached()` downloads through a throwaway embedder and releases the ONNX session instead of leaving ~150 MB resident in every daemon; the first real `embed()` lazy-loads from the disk cache. `ensure_chromium()` warns and stays retryable when the install fails, and after a successful install prunes stale `chromium*` builds (each playwright bump orphans ~520 MB; firefox/webkit are never touched, and nothing is pruned unless the wanted build exists on disk). RapidOCR remains first-use. Concurrent loaders keep the double-checked locking (`_load`, `_ocr_reader`, `ensure_chromium`).

### Skills

Live under `<home>/skills/<category>/<name>/`. Required `SKILL.md` plus optional `scripts/`, `references/`, `assets/`, `secrets/` (mode 0700, gitignored, scanner skipped), `state/` (gitignored, scanner skipped, runtime persistence). `.gitignore` auto-written on create with `secrets/\nstate/\n`.

**Live by default** — no `_pending/` approval stage (was tried in v0.1, removed in v0.2 as friction-without-benefit).

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

**Interrupt**: polls `tool_state.is_interrupted()` between iterations and between tools; returns `[research: interrupted]` on the first hit. **State label** during execution: `<depth> · step N/M`; while an inner tool runs its own `emit_state` label gets auto-prefixed with `step N/M · …` via a wrapped `_emit` installed for the duration of each tool-call batch (restored in a `finally`).

**Batch mode** (v0.2.18): `tasks: [{brief, depth}]` up to 3 runs concurrently — see the Delegate section below for the shared ThreadPoolExecutor design (same pattern applies here).

### Attachments (`alpi/attachments.py`)

`host.chat.send` accepts `attachments: [{path, mime?, name?}]`. The engine validates them (`att.validate` — magic-byte sniff for image/PDF, NUL/control-ratio guard for binary-as-text, per-type size caps, allowlist: images `png`/`jpeg`/`webp`, PDF, and text/source incl. `py`/`js`/`ts`/`tsx`/`go`/`rs`/`sh`/`sql`) and turns them into OpenAI content-parts (`build_content_parts`): images → base64 `image_url` data parts, text/source → inline text parts, PDFs → text extraction (bounded by `tools.attachments.max_text_tokens` → chars at ~4/token; default auto = half the active model's context window, no page cap). A **scanned** PDF (extractable text below `SCANNED_PDF_TEXT_FLOOR`) falls back by model capability: vision-capable → rendered page images; text-only → **RapidOCR** text (capped at `SCAN_MAX_PAGES`), so a profile with no knowledge base and no vision can still summarize a scan. PDF text/render/OCR mechanics are shared with the knowledge tool via `alpi/extract.py`. Images on a text-only model are **not** OCR'd — they degrade to a path note telling the model it can't see them. A guidance text-part tells the model the files are inline so it doesn't reflexively call filesystem or knowledge tools to "find" them.

**Per-turn only.** Bytes live only in the in-memory message. `session_metadata` is itself bytes- and **path-free** (`{name, mime, size}`), but the engine re-adds a **best-effort local `path`** to each persisted chat-turn attachment so clients can thumbnail history — the path may be unfetchable from another client (outside `host.attachments.fetch` roots) or after a staged file's TTL, so this is preview replay, not durable storage. The validated turn attachments (`{name, path, mime}`) are also published to a runtime-only `ContextVar` (`tools/_state.set_turn_attachments`) so a tool can resolve a turn's files. Remote clients (mobile, or desktop pointed at a remote daemon) can't hand the daemon a local path, so they upload bytes via the `host.attachments.stage` RPC (type-aware caps, content validated 1:1 with send) which writes to a TTL-swept temp dir and returns a daemon-side path.

**Durable.** `knowledge(action="ingest")` is the bridge from per-turn input to permanent knowledge. It reads an attachment or source file, synthesizes OKF Markdown under `<workspace>/knowledge/`, updates `index.md` / `log.md`, and refreshes the profile-local derived index in `knowledge.sqlite`. The raw source is not copied into a durable documents directory. There is **no auto-learn**: attachments stay one-turn unless the user explicitly asks to learn/remember/save/index/compile one.

### Vision (`alpi/tools/read_image.py`)

`read_image(path, question)` runs the current (or override) model in multimodal mode on an image and returns a text answer. `path` can be a local file OR an `http(s)` URL — URLs go through `check_url()` for SSRF (metadata hosts + private IPs blocked, redirects re-validated via httpx `event_hooks`).

Magic-bytes sniff accepts PNG / JPEG / GIF / WebP / BMP plus SVG (text-sniff for `<svg`); rejects bytes that don't match a known header even if the extension agrees. 20 MB cap on file and on download payload.

No pre-flight vision-capability check — LiteLLM's `supports_vision()` is wrong for `openrouter/...` prefixes and would bounce real vision models. If the call fails we surface the error with a hint pointing at `/model` when the message mentions image / vision / multimodal.

**Model override** via `tools.read_image.model` in config (same pattern as `web_extract`). When set, the tool tries the override first; on failure it retries with the main model and prefixes the answer with `[fallback: <override> unavailable, used main model]`. Useful for "main agent on a cheap text model, keep an expensive vision model just for images".

Same usage / cost plumbing as research and delegate (`record_usage`). Auto-resize to cut tokens is tracked in [ROADMAP §S](ROADMAP.md) for v0.3.

### Delegate (write-capable sub-agent, `alpi/tools/delegate.py`)

Sibling to `research`, but can mutate: spawn a focused sub-agent with a chosen toolset, get back a summary. Used when a task would otherwise flood the parent context (multi-file refactors, fetch+parse+write pipelines, skills that generate several output files, iterative debug loops).

**Toolsets** (callable presets via the `toolsets` param, default `["file", "web"]`):
- `file` → `read_file`, `write_file`, `edit_file`, `search`
- `terminal` → `terminal`
- `web` → `web_search`, `web_fetch`, `web_extract`

**Blocked for sub-agents**: `delegate` (no recursion), `memory`, `skill`, `schedule`, `notify`, `email`, `session_search`, `session_read`, `todo` (shared global state). `research` is not in any preset either — if you need deep investigation inside a delegate task today, do it in the main agent first and pass findings via `context`.

**Budget**: hardcoded `MAX_STEPS = 30`. No config knob — it's a ceiling, not a target (sub-agent stops when done). If a real case needs more, bump the constant.

**System prompt** is built from a single template plus the workspace root (when set): relative paths resolve under workspace, absolute paths go where the goal says, and the sub-agent is explicitly warned not to invent `/workspace/...` style roots.

**Prompt-cache contract.** `messages[0]` is the stable system prefix and tool
schemas are sorted by name. Volatile `# NOW`, workgroup, skill-hint, and relay
state is composed once into the user turn's persisted `host_context` suffix,
so normal history growth is append-only across live calls and every rehydrator.
OpenRouter calls carry a hashed affinity for the logical conversation; other
providers receive no OpenRouter-only fields. `prefix_diag.py` compares bounded
request-shape hashes per conversation and records causes, never prompt text.
Caching and diagnostics are best-effort and cannot fail a provider call.

**Batch parallel mode** (v0.2.18). Both `research` and `delegate` accept `tasks: [...]` (up to 3) and run them concurrently via `ThreadPoolExecutor(max_workers=3)`. Isolation is provided by `_state.py`: `_emit`, `_interrupt_getter`, `_usage_sink` are `contextvars.ContextVar`, so each worker thread sees its own values without racing on module globals. Workers re-seed `interrupt_getter` + `usage_sink` from the parent context (Python's `ThreadPoolExecutor` doesn't propagate ContextVars automatically) and install a per-task prefixed `emit` so TUI progress lines read `[i/N] <tag> · <msg>`. Results aggregate into one markdown report with per-task sections; per-task failures are captured inline as `[failed: <error>]` instead of aborting the batch. Cap is hardcoded at 3 — bumping would need a config knob *and* would multiply LLM cost linearly; not a default worth moving.

### TUI (`alpi/tui/`)

Textual 8.2.x. Layout: `AlpiTopBar` (identity) + chat scroll (`VerticalScroll.anchor()` auto-follows new content) + `AlpiHeader` (status: model · ctx · cost) + `#chat-input` (flat slab, accent-tinted bg on focus).

**Theme** (`themes.py`): `build_theme(accent, dark)` factory returns a Textual `Theme` from a single accent hex + dark/light flag. Registered in `AlpiApp.__init__` (not `on_mount` — child widgets read `theme_variables` during their own mount). Widgets read `self.app.theme_variables` at render time instead of taking colors as params, so `tui.accent` or `tui.theme` changes propagate without rewiring.

**Live tool cards** (`ToolCard` in `widgets.py`): single line, spinner + elapsed at 6 Hz, `tool_state` labels while running, switches to result line on completion. `◆` uses `$accent-darken-1` for non-error, `$error` for failures.

**Assistant streaming**: `AssistantMessage` uses Textual's native `Markdown.get_stream()` — async queue that coalesces fragments when deltas arrive faster than the widget can render. Parser runs on new fragments only, not the full buffer.

**Reasoning surface**:
- Inter-tool prose is demoted to a `ReasoningLine` (`» …`) above the next tool card in `$text-muted`. Persisted in `ToolLog.reasoning` (first tool of each batch carries the text); replayed on `--continue`.
- For models emitting `reasoning_content` separately (R1, o-series, Claude extended thinking), the tail (last 80 chars) replaces `thinking…` inside the live spinner. Dropped when the first content token or tool call arrives.
- `tui.show_reasoning` (default `true`) hides both channels when `false`; data is still persisted, the engine still emits.

**Persistence contract** (cross-surface). The engine consolidates the whole turn's reasoning — `reasoning_delta` thinking + the inter-tool prose — into **`Turn.reasoning`** (str), and records **`Turn.reasoned_s`** (float) = the reasoning span from turn start to the first tool boundary, or to the first final-answer text token when there are no tools; it **excludes both tool execution and final-answer streaming** so the duration isn't inflated by a long-running tool or a long reply. Desktop/mobile render a collapsible "Reasoned for Ns" block from `Turn.reasoning`, falling back to joining `ToolLog.reasoning` for turns logged before the field existed; the TUI renders the per-tool `ToolLog.reasoning` interleaved. `ToolLog.reasoning` (first tool of each batch) remains the legacy per-tool fallback.

**Slash commands**: `/help`, `/memory`, `/tools`, `/mcps`, `/status`, `/skills`, `/clear`, `/new`, `/compact`, `/model`, `/exit`. All surface-panels are `FloatingPanel`s on the overlay layer docked above the input strip, dismissed by Esc or click-outside. Header (`$surface-lighten-1` tint) shows the command name; body scrolls with `max-height: 18`. The info panels (`screens.py`) are read-only; `/help` and `/model` (`model_panel.py`) are interactive — subclasses focus an `OptionList` / `Input` in `on_mount` via `call_after_refresh` so selection and navigation work while the panel floats. Configuration verbs (workspace, email, sandbox, …) live exclusively in `alpi setup` — the TUI is for chat and inspection, not for editing the profile.

**Interrupt on new input**: typing while a turn runs cancels it. `engine.interrupt_requested` polled at 3 points; long-running tools (`research`) poll `tool_state.is_interrupted()`. Skipped tool calls get a `[skipped — user interrupted]` tool message to preserve OpenAI's pairing invariant.

**`Ctrl+Y`** copies last assistant reply (pbcopy/wl-copy/xclip/xsel/OSC-52 fallback chain). `Ctrl+L` clears.

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
  `link.ask`, `link.cancel` **and** every `workgroup.*`
  verb.
- **workgroups** — the **poller** (outbound). Periodically calls
  `workgroup.pull` against the hubs of every workgroup this profile
  subscribes to, decrypts new posts, and dispatches an autonomous
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
and future mobile clients talk to this API; they do not read profile
files directly.

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
`devices[]` each hold a separate opaque token plus self-reported client/name/
version metadata and `last_seen`. Desktop and mobile may therefore share one
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
  workgroup post/read, voice preview. Admin verbs reject with
  `-32001 forbidden / "admin role required"`.

The admin set lives in `_ADMIN_METHODS`; the strictly-local set
in `_LOCAL_ONLY_METHODS` (network admin only — no role unlocks
those over WS).

Lifecycle:

- **Create connection**: `host.connections.create(label, role, profiles)`
  creates the parent identity and a ten-minute one-time grant. The grant is
  embedded in the QR/link shown by `alpi setup → Connections → New connection`.
  The default role is `member`.
- **Add device**: `host.connections.add_device(connection_id)` creates another
  one-time grant under the same parent identity.
- **Exchange**: the client sends `host.connections.exchange_pairing` as its
  first unauthenticated WS message. The daemon atomically consumes the grant,
  creates the permanent device credential with its client/name/version
  metadata, returns it once and closes the bootstrap socket. Reuse returns
  `-32011 pairing-used`; expiry returns `-32011 pairing-expired`.
- **Observe / cancel**: local/admin callers use
  `host.connections.pairing_status` and `host.connections.cancel_pairing`.
- **Update / disable**: `host.connections.update` changes label, role or
  profile scope. `host.connections.set_status` disables or enables every
  linked credential without deleting sessions or usage.
- **Use**: every WS request carries `auth_token`. Fail =
  JSON-RPC `{code: -32000, message: "auth-failed"}` and the
  connection closes; the mobile app's auth-failed handler wipes
  its endpoint and bounces back to the pair screen.
- **Revoke / delete**: `host.connections.revoke_device` invalidates one
  device. `host.connections.delete` tombstones the parent and clears every
  linked token while retaining historical session/ledger attribution.

On startup, when `connections.yaml` is absent and `devices.yaml` exists, each
legacy device row is migrated to one connection with one device. Tokens,
roles and profile scopes are preserved; the source becomes
`devices.yaml.migrated`. No rows are merged because the old schema has no
reliable grouping key. Sessions written before this contract lack an owner
and remain under the synthetic `host` connection.

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
- **`host.profile.summaries`** — lightweight inbox/sidebar shape:
  `name`, `model`, `accent`, `latest_session`, `counts`, `budget_*`,
  `pubkey_b64`, `has_any_provider`. No peers/models/
  mcps/provider_keys/sandbox/voice — those live in **`host.profile.detail`**
  (`{workspace, tcp_port, advertise_host, provider_keys, provider_ollama,
  sandbox*, voice_*, mcps, peers, models}`), fetched lazily by
  settings/profile screens. The summaries verb is the hot poll; the
  detail verb is on-demand.
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
  Tauri layer used to shell out to `alpi workgroup …` for these;
  v0.5 routes them through the host plane so mobile reuses the same
  contract.
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
- **`host.outputs.{list,read,mark_read,mark_all_read,delete}`** —
  durable inbox for proactive agent messages and schedule
  results. Backed by `<home>/outputs/outputs.jsonl` (capped at
  500 rows, atomic compaction). `notify` pushes to the OWNER's own
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
  `{id, profile, created_at, title?, body,
  type: info|warning|error, status: unread|read, session_id, delivered_to}`
  (`title` present when a `notify` caller set one, or on scheduler
  failure rows — the job's title).
  No `archive` action — the 500-row cap handles retention so
  clients only render a two-state inbox. `agent.message`,
  `schedule.done` and `schedule.failed` events ship `output_id`
  + `deep_link: /outputs/<profile>/<id>` whenever an output was
  filed so clients can deep-link straight to the row.

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
    interrupt — it adds the job `title` and an enriched `body`
    (reason + timeout/exit) plus `output_id` + `deep_link`
    (`/outputs/<profile>/<id>`), and is itself the failure
    notification (clients raise it; failures are NOT re-emitted as
    `agent.message`).
  - `agent.message` — emitted by `notify` (the owner-push tool). In
    daemon turns it fires from the tool process; for scheduled jobs
    the parent re-emits after parsing the child subprocess events.
    Always carries `output_id` + `deep_link`
    (`/outputs/<profile>/<id>`) so clients land on the canonical
    output instead of the chat window.
  - `output.created` — companion event for every new outputs row
    (`{profile, id, type}`). Lets inbox surfaces refresh without
    polling `host.outputs.list`.
  - `schedule.changed` (`action: removed|paused|resumed`) —
    schedule mutators on the host plane.
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

**Per-profile env snapshot (v0.4.52).** `alpi.home.effective_profile_env(home)`
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

Tick loop (default 30s) hosted inside the alpi daemon. `add`
schedules a job (`kind: cron|once`, expression or `after_hours`).
`run-once` ticks manually for testing. LLM time grounding: when
the agent calls `schedule(action='add', kind='once',
after_hours=N)`, the engine resolves `now` from a single source so
the agent doesn't drift.

**Duplicate guard + in-place edits.** `add` rejects a job whose (`kind` + cron / `run_at` / `after_hours`) matches an existing one AND whose prompt fingerprint (lowercase + whitespace-collapsed first 80 chars) collides. Pass `force=true` to bypass when the second job is genuinely intentional. Use `update` to change prompt, cron, `notify`, or pause state without remove/recreate churn. A job carries a single delivery axis, `notify: bool` (default `false` = silent): `true` pushes the reply to the owner's apps. Legacy jobs with a `platform` field are migrated to `notify` on load (`platform` set → `notify: true`). Reaching a THIRD PARTY is an explicit `email` call in the prompt — that's now allowed (the old auto-delivery guard that rejected such prompts is gone).

Scheduled jobs execute through `alpi chat --once --emit-events
--no-save` with `ALPI_PLATFORM=cron`. The scheduler consumes stdout
events to detect tool traces, final reply text, delivery, and failure.
It does not write `sessions/<id>.json`: cron output belongs to
schedule delivery/logging, not to local TUI / desktop chat history.

**Loop isolation.** `serve()` runs `tick()` in a dedicated
`ThreadPoolExecutor(max_workers=2)`, and `host.schedule.fire` wraps
`fire_by_id` in `run_in_executor` before awaiting. Both paths
ultimately call `subprocess.run(timeout=job_run_timeout(job))` (default 900s, per-job up to 3600s); running them inline
would block every other coroutine on the daemon's asyncio loop —
ALP responders and `host.chat.send` streams in
sibling profiles all stall for the duration of the scheduled job.
The dedicated executor also means the scheduler can't starve chat's
default-executor turns. A regression test in
`tests/core/test_schedule.py::test_serve_runs_tick_off_loop_so_chat_can_progress`
pins the contract.

**Timezone.** Cron expressions evaluate against the **machine's system timezone** (`datetime.now().astimezone()` in `scheduler/run.py`). Jobs are stored with UTC `last_run_at` but fire according to local wall-clock time. Practical consequence: if you specify `10 12 * * *` because you want a 12:10 reminder in Bangkok, the Mac must be set to `Asia/Bangkok`. Move the machine to a different timezone and the cron fires at 12:10 there, not in Bangkok. No in-job timezone override today — add it via `TZ=…` in the launchd plist / systemd unit if cross-timezone stability is required.

### MCP client (`alpi/mcp/`)

Spawns user-configured MCP servers (stdio JSON-RPC, SSE planned). Their tools are wrapped and registered as alpi tools. Servers configured in `config.yaml` under `mcp.servers.<name>` (command, args, env). Management lives in `alpi setup → MCPs`; `alpi mcp` itself is not exposed on the CLI surface.

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

Listings are bounded. `host.sessions.list` fully parses normal files but uses a cheap summary path for files above the large-session threshold; `host.profile.summaries` uses `count_sessions()` and `latest_chat_summary()` so profile/sidebar RPCs never parse 50 MB histories just to show a count or latest row.

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

**`@`-mention threads (`alpi/alp/mention_thread.py`).** When peer A `@`-mentions peer B over ALP (`link.ask`), the receiving side runs a fresh `Engine` per turn — but B persists a small per-sender thread at `<B-home>/mentions/<A>.json`, capped at 20 turns. Successive mentions from the same A→B pair carry conversational memory ("what I said before" resolves) without polluting B's local `--continue` (which only reads `sessions/`). Threads are isolated per remitente. Wipe via `setup → Cleanup → Mentions`.

### Security model

Two layers:

- **Layer 1 — application guards (always on).** `_guards._DANGEROUS` denylist on terminal (rm -rf, pipe-to-interpreter, fork bomb, ...). SSRF block on web_fetch/web_extract (RFC 1918, link-local, cloud metadata). Prompt-injection scan on email + web content. Sensitive-path denylist on file tools (`_paths.py`).
- **Layer 2 — OS sandbox (opt-in, per profile).** `tools.terminal.sandbox: true` wraps shell commands in `sandbox-exec` (macOS) or `bubblewrap` (Linux). Read/write limited to workspace + `~/.alpi/` + `/tmp`; network denied by default. Off by default because interactive development workflows vary; recommended for unattended profiles.

Threat model: prompt injection via email/web content, LLM-issued tool calls on the user's machine, direct user input (trusted), and network adversaries for ALP links. Full discussion in [SECURITY.md](SECURITY.md).

## Cross-cutting concerns

### Profiles

`alpi -p <name>` resolves home to `~/.alpi/profiles/<name>/`. `ALPI_PROFILE` env var is the same. No sticky "current profile" file — resolution is fully explicit. The single daemon (`com.alpi.daemon` / `alpi-daemon.service`) supervises every profile from one process; tasks are namespaced `<profile>/<service>` so they stay distinguishable in logs and `asyncio.all_tasks()`. Inside a turn, `home.set_active_home(home)` binds the per-thread contextvar consulted by `home.get_home()` so tools resolve to the right profile even though every concurrent turn shares the daemon's env.

### Workspace

`cfg.workspace` (or `cwd` fallback if unset) is the **default root for relative paths** — not a wall. File tools and terminal can reach absolute paths anywhere except the sensitive denylist. Real workspace-only isolation is the opt-in OS sandbox (Layer 2). Configure it via `alpi setup → Workspace`; the TUI top bar read-outs the resolved path but does not edit it.

## Dependencies

Hard runtime deps are kept tight — every line in `pyproject.toml`'s `dependencies` is actually imported by `alpi/`. The audited set, with one-liner for why each earns its place:

- `litellm` — multi-provider LLM client; the one primitive the agent is built around.
- `rich` — Text formatting primitives used across the CLI wizards, TUI rendering pipeline, and tool output.
- `textual` — TUI framework.
- `prompt_toolkit` — CLI wizard input (menus, text, password). Replaced `questionary` in v0.2.10.
- `httpx` — async HTTP; Gmail API, web_fetch, OAuth dance.
- `click` — CLI command dispatch.
- `pyyaml` — config.yaml + skill frontmatter.
- `python-dotenv` — `.env` loader.
- `croniter` — cron expression parsing for the scheduler subsystem.
- `setproctitle` — makes `ps aux` show ``alpi (<profile>)`` instead of identical ``alpi`` lines for every profile's service.
- `playwright` + `playwright-stealth` — interactive browser tool.
- `pillow` — image pre-processing for `read_image` (auto-resize).
- `html2text` — strip HTML to markdown in `web_fetch` / `web_extract`.
- `ddgs` — DuckDuckGo search backend (replaced `duckduckgo-search` when that package was deprecated).
- `edge-tts` — TTS tool (local-first, no API key).
- `faster-whisper` — STT tool (local-first, no API key).

Optional `dev` extra: `pytest` + `pytest-asyncio` for the test suite, `ruff` for lint, `pip-audit` for CVE scans.

Security posture: `uv run --with pip-audit pip-audit` ran clean against the full lockfile at the time of the v0.2.66 audit. Re-run before each release. Known-CVE deps are not allowed to accumulate — drop or upgrade.

## Testing

Run via `uv run pytest tests/`. The `--llm` flag enables real-LLM integration tests (a few cents on free models).

Key fixtures (`tests/conftest.py`):
- `tmp_home_no_env` — isolated `~/.alpi/` rooted at a tmp dir, no `.env` (safe for unit tests).
- `tmp_home` — same with the user's `.env` copied (for LLM tests).

## Non-obvious things to know

- `rich.markup.escape()` any user-controlled substring before passing to `Text.from_markup()`. Several past crashes from `[exit 0]`-style tokens in tool output.
- Tool results are capped per-tool by `alpi/tools/_budget.py` (default 100,000 chars; override via `tools.<name>.max_result_chars`).
- `last_ctx_tokens` (current prompt size) ≠ cumulative `input_tokens`. Header shows the former.
- `call_from_thread` + Python built-in methods (e.g. `dict.pop`) crashes Textual; always wrap in a regular function.
- `cfg` must be loaded BEFORE `super().__init__()` on `AlpiApp`. The theme is then registered immediately after, in `__init__` rather than `on_mount`, because child widgets read `self.app.theme_variables` during their own mount (which fires first). `self.get_css_variables()` is called explicitly to rebuild the var dict synchronously — setting `self.theme` alone schedules the refresh for the next event-loop tick.
- Schedule subprocess uses `alpi chat --once --emit-events --no-save` — same event stream, no resumable session file.
- `ALPI_HOME` env var routes daemons + tests to a specific profile root.
- `ALPI_SKIP_UPDATE_CHECK=1` short-circuits the background PyPI version check (`alpi/updater.py`); the autouse fixture in `tests/conftest.py` sets it so the unit suite never reaches PyPI. `ALPI_UPDATE_INDEX` overrides the JSON URL the updater hits when you need a staging or local mirror.
