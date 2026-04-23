# Architecture

Living technical reference for alpi at HEAD. Describes only what currently
ships — historical decisions live in commit messages, planned work lives
in [ROADMAP.md](ROADMAP.md).

Audience: any developer (or LLM) reading this codebase from cold.

## What alpi is

A slim personal AI agent. Two surfaces — a Textual TUI in the terminal
and a Telegram/IMAP gateway as a separate process. Inline-learning
memory (no post-session reflect), live-by-default skills with a security
scanner and a quota, multi-provider LLM via LiteLLM (plus a planned
direct-Codex transport for the ChatGPT subscription path).

**Positioned as a lighter, improved version of
[Hermes](https://github.com/NousResearch/hermes-agent).** The Hermes
working tree is already on disk at **`~/git/hermes-agent/`** — alpi's
canonical reference codebase, read directly with `Read`/`Grep`/`Glob`
(no clone, no fetch). When designing a non-trivial feature, read
Hermes first — they've usually solved the problem. Then evaluate critically (Hermes covers a broader
audience than alpi and many of its solutions are over-engineered for
personal-use scope) and propose a leaner adaptation. The bar is "the
smallest design that captures the value Hermes provides," not "port it
verbatim." Things alpi borrowed lean: skill scanner patterns
(skills_guard.py), auto-injected skills index in the system prompt
(prompt_builder.py:589), depth-tiered research budget. Things alpi
deliberately skipped: skill hub/sync, sub-agent mesh, SQLite state, 28
skill categories, post-session reflect, broad cross-platform support.

## Principles

alpi is published by [Satoshi Ltd.](https://www.satoshi-ltd.com/)
and inherits the company's six operating principles (Privacy by
Design, User Sovereignty, Security First, Open Source, Zero
Knowledge, Digital Sovereignty). See the **Why alpi is built like
this** section in `README.md` for the mapping between principle and
code. The conventions below are the engineering expression of those
principles — not separate from them.

- **Slim.** Every feature earns its keep. No over-engineering. Maps to Satoshi's "constraint breeds coherence" heuristic.
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
alpi chat --once ... --emit-events     INTERNAL — gateway subprocess contract

alpi setup                     interactive menu: model / gateways / voice / MCPs /
                               peers / sandbox / gateway service / schedule service /
                               alp service / health check / cleanup

alpi doctor                    live health check (Telegram getMe, IMAP login,
                               Gmail token refresh, MCP handshake, service PIDs);
                               exits 1 on any failure, 0 otherwise

alpi logs                      tail every subsystem log merged by timestamp
  --source {gateway|schedule|agent|approval}   restrict to one subsystem
  -n N                                         last N lines (default 100)
  -f                                           follow mode (poll every 1s)

alpi profile list              list profiles, mark the active one
alpi profile create <name>     bootstrap a new profile tree
alpi profile remove <name>     delete after safety checks + confirm

alpi gateway   start|stop|restart               manual control for debug; service runs via `alpi setup → Gateway service`
alpi schedule  start|stop|restart|run-once      manual control; service auto-installs on first run
alpi alp       start|stop|restart               ALP Unix-socket listener; service via `alpi setup → ALP service`

alpi peers list                list pinned ALP peers for this profile
alpi peers key                 print this profile's ALP public key
alpi peers add <id> <pubkey>   pin a peer (prefer the wizard for capability selection)
alpi peers remove <id>         unpin a peer
alpi peers ping <id>           live probe via link.ping
```

**Shape rules:** containers (profile, peers) get `list/create/remove` (or `add/remove`). Daemons (gateway, schedule, alp) get `start/stop/restart` for manual/debug use — install/uninstall lives only in the wizard (`alpi setup → {Gateway,Schedule,ALP} service`), so users don't need to memorise two ways of doing the same thing. The scheduler auto-installs as a service on first run; a marker at `{home}/schedule/.bootstrapped` prevents re-installing after the user uninstalls from the wizard. Interactive wizards live exclusively under `alpi setup`; never add a per-feature wizard command.

**Command ordering** in `--help` is frequency-first, not alphabetical: `chat → setup → doctor → logs → profile → peers → alp → gateway → schedule`. See `_OrderedGroup` in `cli.py`.

**`alpi/ui.py`** is the shared interactive layer. Raw `questionary.*` is forbidden outside it. Helpers: `banner`, `menu`, `text`, `password`, `confirm`, `row`, `ok/fail/warn/dim/saved/cancelled`. The close item is added automatically with value `None` (callers treat `None` as "out").

**Menu close wording**: top-level (`alpi setup`) → `Exit`. Sub-menus (`Gateways:`, `MCP servers:`, `Manage saved keys`) → `← Back`. Wizard aborted mid-flow → `cancelled`. Mixing `Exit/Back/Cancel` in one context is a bug.

## File layout

```
alpi/
├── __init__.py             __version__
├── cli.py                  entry point, --continue, --profile resolution
├── engine.py               turn runner, interrupt flag, tool loop
├── llm.py                  litellm stream() / complete() wrappers
├── session.py              Turn / ToolLog dataclasses, save/load
├── memory.py               MemoryStore (3 files, two-tier dedup, .bak)
├── home.py                 profile path resolution
├── config.py               YAML load/save, defaults, deep merge
├── ui.py                   shared wizard/menu primitives
├── service.py              install/uninstall launchd/systemd units
├── prompts/
│   ├── default_personality.md
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
│   ├── research.py         read-only sub-agent (depth: quick/normal/deep)
│   ├── terminal.py         run/background/status/output/kill
│   └── … (read_file, write_file, edit_file, todo, web_*, schedule,
│         memory, session_search, send_message, email, config)
├── tui/                    Textual app, widgets, screens, theme
├── gateway/                separate process (Telegram / IMAP)
├── scheduler/              schedule daemon (cron + once jobs)
├── mail/                   mail backends (imap.py — IMAP+SMTP; gmail.py coming in T)
├── mcp/                    MCP client (stdio JSON-RPC) + registry
├── alp/                    Alpi Link Protocol (spec: docs/ALP.md)
│   ├── keys.py            Ed25519 identity at {home}/alp/secrets/alp_key.{pem,pub}
│   ├── envelope.py        build/sign/verify JSON-RPC envelope + replay cache
│   ├── peers.py           {home}/alp/peers.yaml load/save + capability check
│   ├── server.py          Unix-socket listener, fail-closed dispatch
│   ├── client.py          one-shot call with typed errors (TargetOffline, RemoteError)
│   ├── handlers.py        link.ask / link.cancel — engine integration
│   ├── mention.py         @peer parser + executor (shared by TUI + gateway)
│   └── setup.py           `alpi setup → Peers` wizard
└── skills/                 bundled skills (only `meta/consolidate-memory`)
```

## Profile home layout (`~/.alpi/` or `~/.alpi/profiles/<name>/`)

```
~/.alpi/                     default profile root
├── .env                    API keys, gateway tokens, allowlists
├── config.yaml             model + tools + tui + mcp + gateway
├── memory/                 USER.md, MEMORY.md, PERSONALITY.md (+ .bak)
├── skills/<category>/<name>/    SKILL.md + scripts/ + references/ +
│                                 assets/ + secrets/ (0700) + state/ +
│                                 .gitignore
├── sessions/<id>.json      turn-based session log
├── run/                    background process registry, gateway/schedule pids
├── alp/                    ALP state — keypair, peer list, socket, pid
│   ├── peers.yaml         pinned peers (pubkey + allow + optional address)
│   ├── alp.sock           Unix-domain socket, 0600, only while listener runs
│   ├── alp.pid            listener pid
│   └── secrets/alp_key.{pem,pub}   Ed25519 identity (private 0600, public 0644)
└── logs/                   gateway.log, schedule.log, alp.log (rotated at 1MB)

~/.alpi/profiles/<name>/     same layout, isolated per profile
```

## Core systems

### Engine loop (`alpi/engine.py`)

Per turn: append user message → loop {LLM stream → emit deltas → exec tool calls → append tool results} until the LLM stops emitting tool calls OR `max_steps_per_turn` is hit. `interrupt_requested` is polled at three checkpoints (between iterations, mid-stream, between tool calls). A turn lock serializes concurrent runs so a delayed `research` tool from the previous turn can't bleed into the next.

Events emitted to the UI sink: `user`, `reasoning_delta`, `assistant_delta`, `assistant_done`, `tool_start`, `tool_state`, `tool_end`, `usage`, `error`, `done`, `interrupted`. The TUI consumes them; the gateway subprocess consumes a subset via JSON-lines.

The system prompt for each turn is built from: personality file → base prompt → environment block (workspace, profile home, path rule) → **skills index** (auto-injected by `alpi.tools.skill.skills_index_block`) → USER.md → MEMORY.md.

### LLM transport (`alpi/llm.py`)

Thin wrapper over `litellm.completion`. `stream()` is an async generator yielding `{text_delta, reasoning_delta, tool_calls_delta, finish_reason}` per chunk plus a final `{final, tool_calls, input_tokens, output_tokens, cost_usd}`. `complete()` is the non-streaming variant used by `research`. `_silence_litellm()` runs at import time to mute LiteLLM's startup banner via FD-level redirect (Textual is sensitive to stdout pollution).

### Memory (`alpi/memory.py`)

Three files: `USER.md` (facts about the user), `MEMORY.md` (env quirks, commands, incidents), `PERSONALITY.md` (tone / language / behaviour). `§` entry delimiter, char limits (1375 / 2200), accent+case+punctuation-insensitive dedup, plus token-Jaccard dedup at 70% max-containment to catch paraphrases. `.bak` snapshot before every mutating write. Approach C: every mutating call returns the full current state of the target file so the agent sees its own write in the same turn.

### Path resolution (`alpi/tools/_paths.py`)

Single entry point `resolve_path(path)`:

1. `expanduser()`.
2. Relative paths root at the active workspace (`cfg.workspace` or `cwd` fallback).
3. Resolve symlinks.
4. Reject if the resulting path matches any sensitive-path entry (denylist below) — `ValueError`.

Denylist: `/etc/`, `/boot/`, `/sys/`, `/proc/`, `/usr/lib/systemd/`, `/System/`, `/private/etc/`, the docker sockets, `~/.ssh/id_*`, `*_key`, `*_ed25519`, `*.pem/.p12/.pfx`, `~/.aws/credentials`, `~/.gnupg/`. Both pre-resolve and post-resolve forms are checked (macOS `/var` → `/private/var` symlink case).

`suggest_similar_paths(target)` lists the parent directory and fuzzy-matches siblings by basename substring/prefix. Used by `read_file`, `edit_file`, and `search` to turn dead-end errors into actionable suggestions.

### Tool registry (`alpi/tools/__init__.py`)

`register(cls)` adds a `Tool` subclass to the dict, `schemas()` emits the OpenAI function-calling shape, `execute(name, args)` runs by name with full error capture. Currently 17 tools registered; `browser` exists as a stub but is not registered (Playwright work pending).

### Skills

Live under `<home>/skills/<category>/<name>/`. Required `SKILL.md` plus optional `scripts/`, `references/`, `assets/`, `secrets/` (mode 0700, gitignored, scanner skipped), `state/` (gitignored, scanner skipped, runtime persistence). `.gitignore` auto-written on create with `secrets/\nstate/\n`.

**Live by default** — no `_pending/` approval stage (was tried in v0.1, removed in v0.2 as friction-without-benefit).

Frontmatter (auto-populated on `create`): `name`, `description`, `category`, `version`, `origin: agent|user`, `created_at`, `requires_env`, `tools`, `stores_secrets`. 13 fixed categories including `miscellaneous` as the fallback.

**Security scanner** (~50 patterns, `_DANGER_PATTERNS` in `skill.py`): destructive shell, credential exfiltration, prompt injection, persistence (cron/launchd/systemd/authorized_keys/sudoers/shell rc), reverse shells, tunneling, obfuscation (base64/eval/exec/compile), process exec, hardcoded credentials (API keys, OpenAI sk-, GitHub ghp_, AWS AKIA), system-password-file paths, deep traversal. Runs on every `create`/`add_file`/`patch` for files NOT in `secrets/` or `state/`.

**Atomic writes** everywhere (tmp sibling + `os.replace`). `.bak` next to SKILL.md on every edit/patch. **Quota**: max 40 agent-owned skills, enforced at `create`.

**Auto-injected into the system prompt** (`skills_index_block(home)`): every session start, all installed skills are listed by category as `name: description` entries, prefixed by a directive that says "check this list before reaching for general tools". Without this nudge, mimo-class models routinely went straight to `web_search`/`terminal` even when a perfect skill existed.

**TUI integration**: when a `terminal` command's path matches `.alpi/(profiles/<p>/)?skills/<cat>/<name>/...`, `arg_hint` rewrites the ToolCard label as `skill: <name>` (or `skill: <name> · <script>` when the script is the full path). Tool name stays `terminal`; the rewrite is display-only.

### Research (read-only sub-agent, `alpi/tools/research.py`)

Spawns a sub-agent with a read-only toolset (`web_search`, `web_fetch`, `web_extract`, `read_file`, `search`). Returns a single synthesised report; the main agent never sees the intermediate tool trace.

**Depth tiers** instead of a numeric `max_steps`: `depth="quick"|"normal"|"deep"`. The integer per tier comes from `tools.research.{quick,normal,deep}_steps` in `config.yaml` (defaults 8 / 15 / 30). Locks the model to three buckets (quick = single-answer, normal = comparative, deep = exhaustive) while letting the user re-tune all three from one place.

**Synthesis fallback**: when the budget runs out, research forces one final no-tools `llm.complete()` with "stop investigating, report now". Avoids the "[research gave up]" footgun where the main agent retries the whole thing.

**Interrupt**: polls `tool_state.is_interrupted()` between iterations and between tools; returns `[research: interrupted]` on the first hit. **State label** during execution: `<depth> · step N/M`; while an inner tool runs its own `emit_state` label gets auto-prefixed with `step N/M · …` via a wrapped `_emit` installed for the duration of each tool-call batch (restored in a `finally`).

**Batch mode** (v0.2.18): `tasks: [{brief, depth}]` up to 3 runs concurrently — see the Delegate section below for the shared ThreadPoolExecutor design (same pattern applies here).

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

**Blocked for sub-agents**: `delegate` (no recursion), `memory`, `skill`, `schedule`, `send_message`, `email`, `session_search`, `todo` (shared global state). `research` is not in any preset either — if you need deep investigation inside a delegate task today, do it in the main agent first and pass findings via `context`.

**Budget**: hardcoded `MAX_STEPS = 30`. No config knob — it's a ceiling, not a target (sub-agent stops when done). If a real case needs more, bump the constant.

**System prompt** is built from a single template plus the workspace root (when set): relative paths resolve under workspace, absolute paths go where the goal says, and the sub-agent is explicitly warned not to invent `/workspace/...` style roots.

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

**Slash commands**: `/help`, `/memory`, `/tools`, `/mcps`, `/status`, `/skills`, `/clear`, `/new`, `/compact`, `/model`, `/exit`. All surface-panels are `FloatingPanel`s on the overlay layer docked above the input strip, dismissed by Esc or click-outside. Header (`$surface-lighten-1` tint) shows the command name; body scrolls with `max-height: 18`. The info panels (`screens.py`) are read-only; `/help` and `/model` (`model_panel.py`) are interactive — subclasses focus an `OptionList` / `Input` in `on_mount` via `call_after_refresh` so selection and navigation work while the panel floats. Configuration verbs (workspace, gateways, sandbox, …) live exclusively in `alpi setup` — the TUI is for chat and inspection, not for editing the profile.

**Interrupt on new input**: typing while a turn runs cancels it. `engine.interrupt_requested` polled at 3 points; long-running tools (`research`) poll `tool_state.is_interrupted()`. Skipped tool calls get a `[skipped — user interrupted]` tool message to preserve OpenAI's pairing invariant.

**`Ctrl+Y`** copies last assistant reply (pbcopy/wl-copy/xclip/xsel/OSC-52 fallback chain). `Ctrl+L` clears.

### Gateway (`alpi/gateway/`)

Separate process from the TUI. `alpi gateway start` runs an event loop that listens to platforms (Telegram long-poll, IMAP polling) and spawns `alpi chat --once --emit-events` per incoming message. Tool traces stream as `◆ {tool} · {arg_hint}` messages; typing indicator stays on while the subprocess works.

Allowlist: `TELEGRAM_ALLOWED_CHAT_IDS` and `IMAP_ALLOWED_SENDERS` in `.env`, fail-closed if unset. Per-platform config under `gateway.{telegram,imap}` in `config.yaml` (`show_tool_trace`, `typing_indicator`, etc.).

The gateway is registered as a launchd (macOS) or systemd-user (Linux) unit via `alpi setup → Gateway service` so it survives reboot.

### Schedule (`alpi/scheduler/`)

Long-running daemon with a tick loop (default 30s). `add` schedules a job (`kind: cron|once`, expression or `after_hours`). `run-once` ticks manually for testing. LLM time grounding: when the agent calls `schedule(action='add', kind='once', after_hours=N)`, the engine resolves `now` from a single source so the agent doesn't drift.

**Timezone.** Cron expressions evaluate against the **machine's system timezone** (`datetime.now().astimezone()` in `scheduler/run.py`). Jobs are stored with UTC `last_run_at` but fire according to local wall-clock time. Practical consequence: if you specify `10 12 * * *` because you want a 12:10 reminder in Bangkok, the Mac must be set to `Asia/Bangkok`. Move the machine to a different timezone and the cron fires at 12:10 there, not in Bangkok. No in-job timezone override today — add it via `TZ=…` in the launchd plist / systemd unit if cross-timezone stability is required.

### MCP client (`alpi/mcp/`)

Spawns user-configured MCP servers (stdio JSON-RPC, SSE planned). Their tools are wrapped and registered as alpi tools. Servers configured in `config.yaml` under `mcp.servers.<name>` (command, args, env). Management lives in `alpi setup → MCPs`; `alpi mcp` itself is not exposed on the CLI surface.

### Logging (`alpi/_log.py`, `alpi/logs.py`)

Every subsystem writes to a single flat folder: `~/.alpi/logs/<subsystem>.log`, rotated at 1 MB with no backups. Same format everywhere (`%(asctime)s %(levelname)s %(name)s %(message)s`) so `alpi logs` can merge them by timestamp prefix. The source tag on display comes from the filename.

Four sources today:

- **`gateway`** — inbound platform traffic (Telegram/IMAP/Gmail), agent spawns triggered by incoming messages, delivery errors. Written by the gateway daemon.
- **`schedule`** — cron tick loop, job fires, job create/delete. Written by the schedule daemon.
- **`agent`** — one line per TUI/gateway/schedule-triggered turn: session id, elapsed, tool names, reply size, cumulative cost, truncated user prompt. This is the **cross-session grep index** — `sessions/<id>.json` carry the full detail; `agent.log` lets you answer "what has alpi been doing this week?" without iterating JSONs.
- **`approval`** — one line per non-SAFE terminal command classification (ALLOW / DENY with severity, pattern, reason). **Security audit trail**; complements the per-turn detail in `sessions/`.

Why logs are NOT inside `sessions/`: `sessions/` is a structured store (one JSON per conversation, indexed by id, consumed by `session_search` and the resume flow). Mixing freeform logs would break the glob pattern and the cleanup semantics. Logs are the **index and audit trail**; sessions are the **content**. Peers, not nested.

Why one flat folder (`logs/`) instead of per-subsystem dirs: four tiny `<subsystem>/logs/` folders with a single file each is pure noise. Daemons still keep their own dirs for non-log state (`gateway/gateway.pid`, `schedule/jobs.json`) — only the `.log` files consolidate.

Adding a new source is two lines: `from alpi._log import get_subsystem_logger; logger = get_subsystem_logger(home, "my-sub")`. `alpi logs` picks it up without changes; add the tag to the `--source` choice list in `cli.py::logs_cmd` if you want it filterable.

### Doctor (`alpi/doctor.py`)

`alpi doctor` — live health check. Verifies each subsystem actually **responds**, not just that it's configured. Same entry point from the CLI and from `alpi setup → Health check`; the status in the setup menu row (`all green` / `N warning(s)` / `N failing`) runs the full check too.

Checks:

- **Model** — `cfg.model` set + provider's API key present in `.env` or env.
- **Workspace** — configured + exists + writable.
- **Gateways** (live) — Telegram `getMe` over HTTPS, IMAP login+SMTP handshake, Gmail OAuth token refresh.
- **Services** — `service.installed()` + `kill -0 <pid>` to distinguish "installed but dead" from "installed and running".
- **MCPs** (live) — spawn each configured server, `list_tools`, stop. Parallelised; per-server timeout 8 s.
- **Security** — sandbox backend binary on PATH (if `tools.terminal.sandbox: true`), approval allowlist count.

Parallelism: the four network-bound tasks (Telegram/IMAP/Gmail/MCPs) submit to a `ThreadPoolExecutor(max_workers=8)`. Sync checks (model, workspace, services, security) run on the main thread while the pool works. Total wall time ≈ slowest single task, not sum — ~5-10 s on a healthy profile.

Progressive rendering: `run_and_render()` uses `rich.live.Live` — every row appears immediately with a cyan spinner, each resolves to `✓`/`✗`/`!` as its future completes. Animation at 10 fps via a manual frame cycler (rich's `Spinner` objects can't be appended to `Text`). Layout is stable (same rows, same column widths) so the eye doesn't jump.

Exit codes: `1` if any check returns `fail`, `0` for warn/info/ok. Warnings don't break cron. The wizard entry ignores the exit code — it press-enter-waits so the user can read.

### Sessions (`alpi/session.py`, `alpi/session_map.py`)

Turn-based JSON: `turns: [{at, user, tools[], assistant}]` plus cumulative metrics. `ToolLog` carries `at, name, args, result (truncated hint), ok, duration_s, reasoning (non-empty only on first tool of a batch)`. Empty sessions (no user message) are NOT saved.

**TUI resume.** Bare `alpi` resumes the most recent session when `tui.auto_resume: true`; `-c` / `--continue` is the manual override.

**Gateway per-chat threading (v0.2.54).** Each inbound message carries `external_chat_id` (a Telegram chat id, or the sender email for IMAP/Gmail). `alpi/session_map.py` holds a pointer map at `~/.alpi/sessions/_gateway_map.json`: `{chat_id: session_id}`. When the gateway spawns `alpi chat --once --resume-chat <chat_id>`, the CLI consults the map — if there's a pointer, that session is loaded and continued; otherwise a fresh session starts and the pointer gets bound after save. Same mechanism across every platform; the natural semantics fall out of what each puts in `chat_id`: per-chat threading for Telegram, per-sender threading for IMAP / Gmail.

`/new` (wired up in AK) calls `session_map.forget(chat_id)` — the pointer drops but the underlying session file stays on disk. Historical threads remain searchable via `session_search`.

### Security model

Two layers:

- **Layer 1 — application guards (always on).** `_guards._DANGEROUS` denylist on terminal (rm -rf, pipe-to-interpreter, fork bomb, ...). SSRF block on web_fetch/web_extract (RFC 1918, link-local, cloud metadata). Prompt-injection scan on email + web content. Sensitive-path denylist on file tools (`_paths.py`).
- **Layer 2 — OS sandbox (opt-in, experimental).** `tools.terminal.sandbox: true` wraps shell commands in `sandbox-exec` (macOS) or `bubblewrap` (Linux). Read/write limited to workspace + `~/.alpi/` + `/tmp`; network denied by default. Off by default until validated against the long tail of common commands.

Threat model: prompt injection via email/web content + direct user input (trusted) + network adversaries (out of scope, personal-use posture). Full discussion in [SECURITY.md](SECURITY.md).

## Cross-cutting concerns

### Profiles

`alpi -p <name>` resolves home to `~/.alpi/profiles/<name>/`. `ALPI_PROFILE` env var is the same. No sticky "current profile" file — resolution is fully explicit. Daemons (gateway, schedule) carry the profile name in their launchd/systemd label so multiple profiles coexist without colliding.

### Workspace

`cfg.workspace` (or `cwd` fallback if unset) is the **default root for relative paths** — not a wall. File tools and terminal can reach absolute paths anywhere except the sensitive denylist. Real workspace-only isolation is the opt-in OS sandbox (Layer 2). Configure it via `alpi setup → Workspace`; the TUI top bar read-outs the resolved path but does not edit it.

### `_state.py` — global tool state callbacks

Three module-level globals: `_emit`, `_interrupt_getter`, `_usage_sink`. The engine sets them around each tool call (`_emit` → updates the active ToolCard, `_interrupt_getter` → propagates Ctrl+C, `_usage_sink` → records sub-agent token counts). Tools call `emit_state(label)`, `is_interrupted()`, `record_usage(in, out, cost)` to bubble info up.

These are GLOBALS — concurrent tool calls would race. The current design is single-threaded; batch parallel research (ROADMAP §R.3) requires moving to `contextvars` or thread-locals.

## Dependencies

Hard runtime deps are kept tight — every line in `pyproject.toml`'s `dependencies` is actually imported by `alpi/`. The audited set, with one-liner for why each earns its place:

- `litellm` — multi-provider LLM client; the one primitive the agent is built around.
- `rich` — Text formatting primitives used across the CLI wizards, TUI rendering pipeline, and tool output.
- `textual` — TUI framework.
- `prompt_toolkit` — CLI wizard input (menus, text, password). Replaced `questionary` in v0.2.10.
- `httpx` — async HTTP; Telegram long-poll, Gmail API, web_fetch, setMyCommands, OAuth dance.
- `click` — CLI command dispatch.
- `pyyaml` — config.yaml + skill frontmatter.
- `python-dotenv` — `.env` loader.
- `croniter` — cron expression parsing for the schedule daemon.
- `playwright` + `playwright-stealth` — interactive browser tool.
- `pillow` — image pre-processing for `read_image` (auto-resize).
- `html2text` — strip HTML to markdown in `web_fetch` / `web_extract`.
- `ddgs` — DuckDuckGo search backend (replaced `duckduckgo-search` when that package was deprecated).
- `edge-tts` — TTS tool (local-first, no API key).
- `faster-whisper` — STT tool (local-first, no API key).

Optional `dev` extra: `pytest` + `pytest-asyncio` for the test suite, `ruff` for lint, `pip-audit` for CVE scans.

**No `gateway` extra.** Prior to v0.2.66 there was one bundling `python-telegram-bot`, `fastapi`, `uvicorn` for an HTTP webhook server that never materialised. A dependency audit confirmed zero imports from the codebase; dropped. If a FastAPI webhook ever lands, the extra comes back.

Security posture: `uv run --with pip-audit pip-audit` ran clean against the full lockfile at the time of the v0.2.66 audit. Re-run before each release. Known-CVE deps are not allowed to accumulate — drop or upgrade.

## Testing

`tests/` runs via `pytest`. ~340 tests, ~2s. `--llm` flag enables real-LLM integration tests (a few cents on free models).

Key fixtures (`tests/conftest.py`):
- `tmp_home_no_env` — isolated `~/.alpi/` rooted at a tmp dir, no `.env` (safe for unit tests).
- `tmp_home` — same with the user's `.env` copied (for LLM tests).

## Non-obvious things to know

- `rich.markup.escape()` any user-controlled substring before passing to `Text.from_markup()`. Several past crashes from `[exit 0]`-style tokens in tool output.
- Tool results are capped at 10,000 chars in `engine.py` before going into the LLM message thread.
- `last_ctx_tokens` (current prompt size) ≠ cumulative `input_tokens`. Header shows the former.
- `call_from_thread` + Python built-in methods (e.g. `dict.pop`) crashes Textual; always wrap in a regular function.
- `cfg` must be loaded BEFORE `super().__init__()` on `AlpiApp`. The theme is then registered immediately after, in `__init__` rather than `on_mount`, because child widgets read `self.app.theme_variables` during their own mount (which fires first). `self.get_css_variables()` is called explicitly to rebuild the var dict synchronously — setting `self.theme` alone schedules the refresh for the next event-loop tick.
- `browser.py` exists but is intentionally NOT in the registry. Reactivate when Playwright lands (ROADMAP §B).
- Gateway subprocess uses `alpi chat --once --emit-events` — separate codepath from the TUI, simpler, non-streaming. Changes to TUI feel don't affect gateway.
- `ALPI_HOME` env var routes daemons + tests to a specific profile root.
