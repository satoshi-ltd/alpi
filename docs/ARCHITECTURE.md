# Architecture

Living technical reference for alpi at HEAD. Describes only what currently
ships — historical decisions live in commit messages, planned work lives
in [ROADMAP.md](ROADMAP.md).

Audience: any developer (or LLM) reading this codebase from cold.

## What alpi is

alpi is a local-first personal AI agent. It has a Textual TUI in the
terminal, a Tauri desktop app (and a planned mobile client) that
talk to the daemon over the host plane (Unix socket locally,
WebSocket remotely), Telegram/IMAP/Gmail/Matrix gateways hosted by
the alpi daemon,
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
alpi chat --once ... --emit-events     INTERNAL — gateway subprocess contract
alpi chat --once ... --no-save         INTERNAL — do not write a session file

alpi setup                     interactive menu: model / gateways / voice / MCPs /
                               peers / workgroups / sandbox / service /
                               health check / cleanup /
                               delete profile (non-default only)

alpi doctor                    live health check (Telegram getMe, IMAP login,
                               Gmail token refresh, MCP handshake, service PID);
                               exits 1 on any failure, 0 otherwise

alpi logs                      tail every subsystem log merged by timestamp
  --source {service|agent|approval}            restrict to one subsystem
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

**Shape rules:** containers (profile, peers, workgroups) get `list/create/remove` (or `add/remove`). The daemon gets `start/stop/restart/status/install/uninstall` under `alpi daemon`; the same lifecycle is also reachable from `alpi setup → Services → Daemon` (default profile only) so users have one canonical place. The first `alpi setup` auto-installs the daemon — no opt-in step. Per-profile services (gateway, schedule, alp, workgroups, host) toggle from `alpi setup → Services → Subsystems` or directly via the `service:` block in each profile's `config.yaml`. Interactive wizards live exclusively under `alpi setup`; never add a per-feature wizard command.

**Command ordering** in `--help` is frequency-first, not alphabetical: `chat → setup → doctor → logs → profile → peers → workgroup → schedule → daemon`. See `_OrderedGroup` in `cli.py`.

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
├── service.py              unified orchestrator — runs every enabled subsystem on one asyncio loop; install/uninstall launchd / systemd unit per profile
├── ledger.py               daily spend ledger (logs/ledger.json) + profile cap gate
├── status.py               canonical /status rows (TUI + Telegram share this)
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
│   ├── research.py         read-only sub-agent (depth: quick/normal/deep)
│   ├── terminal.py         run/background/status/output/kill
│   └── … (read_file, write_file, edit_file, todo, web_*, schedule,
│         memory, session_search, send_message, email, config)
├── tui/                    Textual app, widgets, screens, theme
├── gateway/                inbound platforms (Telegram / IMAP / Gmail), hosted by the alpi daemon
├── scheduler/              cron + once jobs, hosted by the alpi daemon
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
│   ├── pending.py         pending invites store (unpinned-sender capture)
│   └── setup.py           `alpi setup → Peers` wizard
├── host/                   control plane for desktop / mobile clients (default profile only)
│   ├── server.py          Unix-socket JSON-RPC server (no envelope, no Noise — fs perms = trust)
│   ├── handlers.py        read verbs (host.workgroup.transcript, host.sessions.*)
│   ├── chat.py            host.chat.send (streaming) + host.chat.cancel
│   ├── config.py          mutation verbs (host.providers.*, host.peers.*, host.profile.*, host.mcp.*, host.gateway.*, host.sandbox.*, host.voice.*)
│   ├── devices.py         host.devices.* pairing-token lifecycle
│   ├── probes.py          host.gateway.probe, host.peers.ping, host.model.ctx_window
│   ├── schedule.py        host.schedule.{list,remove,set_paused,fire}
│   ├── daemon.py          host.daemon.restart
│   ├── device_state.py    device-facing profile state (profiles, summaries, storage, gateways, skills, workgroups)
│   ├── events.py          host.events.subscribe + thread-safe emit() for daemon-pushed updates
│   ├── workgroup.py       transcript decryption (hub + member shapes)
│   └── sessions.py        plaintext session list / read
└── skills/                 bundled skill blueprints; read-only, resolved via `@alpi/<name>` (see docs/SKILLS.md)
```

Runtime state (user skills, sessions, memories, logs, ALP peers,
keys) does not ship with the package — it's generated per profile
under `~/.alpi/`. The `alpi/skills/` package directory holds only
bundled skill blueprints addressed as `@alpi/<name>`; bundled and
user skills coexist in the listing, kept apart by namespace.
See Profile home layout immediately below. The `skill` tool
(`alpi/tools/skill.py`) manages user-created skills
that live at `{home}/skills/<category>/<name>/`.

## Profile home layout (`~/.alpi/` or `~/.alpi/profiles/<name>/`)

```
~/.alpi/                     default profile root
├── .env                    API keys, gateway tokens, allowlists
├── config.yaml             model + tools + tui + mcp + gateway
├── memories/               USER.md, MEMORY.md, AGENT.md (+ .bak)
├── skills/<category>/<name>/    SKILL.md + scripts/ + references/ +
│                                 assets/ + secrets/ (0700) + state/ +
│                                 .gitignore
├── sessions/<id>.json      turn-based session log (TUI / desktop / `--once`)
├── rag/                    local RAG over the workspace (BA)
│   └── store.sqlite        sqlite-vec index — workspace_files / _chunks / _vec
├── mentions/<sender>.json  per-sender @-mention threads (cap 20 turns), receiving side
├── gateway/                inbound transport state + chat sessions
│   ├── telegram-state.json, imap-state.json, …   per-platform offsets, last-uid, etc.
│   └── sessions/<id>.json  Telegram / email / webhook chat logs (hidden from local listings)
│       └── _map.json       chat_id → session_id pointer
├── run/                    background process registry, gateway/schedule pids
├── alp/                    ALP state — keypair, peer list, socket, pid
│   ├── peers.yaml         pinned peers (pubkey + allow + optional address)
│   ├── alp.sock           Unix-domain socket, 0600, only while listener runs
│   ├── alp.pid            listener pid
│   └── secrets/alp_key.{pem,pub}   Ed25519 identity (private 0600, public 0644)
├── host/                   control-plane state (default profile only)
│   └── host.sock          Unix socket the desktop / mobile client connects to
└── logs/                   service.log, agent.log, approval.log, ledger.json,
                            plus subsystem logs such as gateway.log / schedule.log / alp.log

~/.alpi/profiles/<name>/     same layout, isolated per profile
```

## Core systems

### Engine loop (`alpi/engine.py`)

Per turn: append user message → loop {LLM stream → emit deltas → exec tool calls → append tool results} until the LLM stops emitting tool calls OR `max_steps_per_turn` is hit. `interrupt_requested` is polled at three checkpoints (between iterations, mid-stream, between tool calls). A turn lock serializes concurrent runs so a delayed `research` tool from the previous turn can't bleed into the next.

Events emitted to the UI sink: `user`, `reasoning_delta`, `assistant_delta`, `assistant_done`, `tool_start`, `tool_state`, `tool_end`, `usage`, `error`, `done`, `interrupted`. The TUI consumes them; the gateway subprocess consumes a subset via JSON-lines.

The system prompt for each turn is built from: `AGENT.md` (agent profile — voice, style, identity) → base prompt → environment block (workspace, profile home, path rule) → **platform hint** (`_platform_hint()` — injects per-surface guidance when `ALPI_PLATFORM` is set by the caller: `cron`, `telegram`, `email`, `gmail`; empty for TUI) → **skills index** (auto-injected by `alpi.tools.skill.skills_index_block`) → `USER.md` → `MEMORY.md`.

The gateway (`alpi/gateway/run.py`) sets `ALPI_PLATFORM=<msg.platform>` on every spawned subprocess so Telegram replies arrive Markdown-aware and email replies arrive plain-text-only. The scheduler (`alpi/scheduler/run.py`) sets `ALPI_PLATFORM=cron` so scheduled jobs run knowing no user is present and they cannot ask for clarification.

### LLM transport (`alpi/llm.py`)

Thin wrapper over `litellm.completion`. `stream()` is an async generator yielding `{text_delta, reasoning_delta, tool_calls_delta, finish_reason}` per chunk plus a final `{final, tool_calls, input_tokens, output_tokens, cost_usd}`. `complete()` is the non-streaming variant used by `research`. `_silence_litellm()` runs at import time to mute LiteLLM's startup banner via FD-level redirect (Textual is sensitive to stdout pollution).

### Memory (`alpi/memory.py`)

Three files: `USER.md` (facts about the user), `MEMORY.md` (env quirks, commands, incidents), `AGENT.md` (the agent's own profile — tone, style, identity, language). `§` entry delimiter, char limits `USER_CHAR_LIMIT = 3000` / `MEMORY_CHAR_LIMIT = 5000` (see `alpi/memory.py`; `AGENT.md` is free-form prose with no cap). Accent+case+punctuation-insensitive dedup, plus token-Jaccard dedup at 70% max-containment to catch paraphrases. `.bak` snapshot before every mutating write. Approach C: every mutating call returns the full current state of the target file so the agent sees its own write in the same turn.

**v2 quality metadata.** Each entry carries a trailing `<!-- alpi-meta conf=... captured=... reinforced=... -->` comment that is stripped before the entry reaches the system prompt. `conf` is `low` / `normal` / `high` (default `normal`). Near-duplicate writes reinforce the existing entry (bump `reinforced`, upgrade `low → normal` at ≥ 2) instead of appending a paraphrase. Low-confidence entries with zero reinforcements expire after `LOW_CONFIDENCE_MAX_AGE_DAYS = 30` (constant in `alpi/memory.py`; calibration is an evidence-gated v0.6 item, not a user knob). The memory tool's safety scanner reuses the skill scanner patterns and adds invisible/bidi unicode detection (U+200B–200F, 202A–202E, 2060, 2066–2069, FEFF) to block Trojan-Source vectors; `_operational_warning` surfaces non-blocking warnings when a write looks like session state (`chat_id`, `session_id`, ISO timestamps).

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

Denylist: `/etc/`, `/boot/`, `/sys/`, `/proc/`, `/usr/lib/systemd/`, `/System/`, `/private/etc/`, the docker sockets, `~/.ssh/id_*`, `*_key`, `*_ed25519`, `*.pem/.p12/.pfx`, `~/.aws/credentials`, `~/.gnupg/`. Both pre-resolve and post-resolve forms are checked (macOS `/var` → `/private/var` symlink case).

`suggest_similar_paths(target)` lists the parent directory and fuzzy-matches siblings by basename substring/prefix. Used by `read_file`, `edit_file`, and `search` to turn dead-end errors into actionable suggestions.

### Tool registry (`alpi/tools/__init__.py`)

`register(cls)` adds a `Tool` subclass to the dict, `schemas()` emits the OpenAI function-calling shape, `execute(name, args)` runs by name with full error capture. The registry is assembled from the sibling tool modules in `alpi/tools/__init__.py`, including the Playwright-backed `browser` tool. `search_workspace` and `index_workspace` register first so they appear at the top of the schema list (semantic recall is the right default for "what does my file say about X" questions).

### Local recall (`alpi/core/` + `alpi/tools/workspace.py`)

Per-profile semantic search over the user's local files (BA). Two agent tools:

- `index_workspace(path?, glob?, force?, ocr?)` — walks the workspace root, chunks supported files (30 lines / stride 25), embeds, upserts into a sqlite-vec virtual table. Incremental: mtime-skip avoids re-embedding unchanged files.
- `search_workspace(query, k=5)` — cosine similarity via sqlite-vec MATCH, returns `[{path, snippet, line_start, line_end, score}]` ordered ascending.

Supported formats: markdown / text / source / configs (stdlib read), HTML (`html2text`), PDF (`pypdf` for text-layer, RapidOCR fallback when `ocr=true` and pypdf extracts < 50 chars), DOCX (`python-docx`), EPUB (`ebooklib`), images (`PIL` + RapidOCR — only with `ocr=true`). OCR backend is `rapidocr-onnxruntime` (ONNX port of PaddleOCR, no torch dependency).

**Shared store primitive (`alpi/core/store.py`)**. `open_store(home)` returns a `sqlite3.Connection` with the sqlite-vec extension loaded. Designed to host other shapes later (ALP.6 workgroup search, future entity memory) — they bring their own table schemas.

**Embedder (`alpi/core/embed.py`)**. `Embedder` Protocol; default `FastembedEmbedder` wraps the ONNX export of `sentence-transformers/all-MiniLM-L6-v2` (384-dim, ~90 MB, no torch). Numerically equivalent to the original sentence-transformers checkpoint but ~10× lighter at runtime. Lazy-loaded under a `threading.Lock` so concurrent first-touch calls serialize on a single model instance instead of racing.

**Asset prefetch (`service.py::_prefetch_assets`)**. A daemon thread, scheduled 5 s into the event loop (after socket bind) by `_main_all`. Pre-loads the fastembed model into the ONNX runtime cache via `embed.ensure_weights_cached()` (~100 MB resident — vs ~600 MB the torch path would cost) and ensures the Chromium binary via `ensure_chromium()`. RapidOCR is skipped at startup because its constructor downloads-and-loads in one step; that cost lands on the first `ocr=true` call. Concurrent loaders use double-checked locking (`_load`, `_ocr_reader`, `ensure_chromium`) so a user-triggered call mid-prefetch waits on the same lock instead of racing the same network fetch.

### Skills

Live under `<home>/skills/<category>/<name>/`. Required `SKILL.md` plus optional `scripts/`, `references/`, `assets/`, `secrets/` (mode 0700, gitignored, scanner skipped), `state/` (gitignored, scanner skipped, runtime persistence). `.gitignore` auto-written on create with `secrets/\nstate/\n`.

**Live by default** — no `_pending/` approval stage (was tried in v0.1, removed in v0.2 as friction-without-benefit).

Frontmatter (auto-populated on `create`): `name`, `description`, `category`, `version`, `origin: agent|user`, `created_at`, `requires_env`, `tools`, `keywords`, optional `output_schema`. 13 fixed categories including `miscellaneous` as the fallback. `secrets/` is filesystem state, not frontmatter: it is created lazily when a skill writes a secret file. `output_schema` is one-line JSON and uses a deliberately small subset (`type`, `properties`, `required`, `items`, `enum`) so the runtime stays dependency-light.

**Security scanner** (~50 patterns, `_DANGER_PATTERNS` in `skill.py`): destructive shell, credential exfiltration, prompt injection, persistence (cron/launchd/systemd/authorized_keys/sudoers/shell rc), reverse shells, tunneling, obfuscation (base64/eval/exec/compile), process exec, hardcoded credentials (API keys, OpenAI sk-, GitHub ghp_, AWS AKIA), system-password-file paths, deep traversal. Runs on every `create`/`add_file`/`patch` for files NOT in `secrets/` or `state/`.

**Atomic writes** everywhere (tmp sibling + `os.replace`). `.bak` next to SKILL.md on every edit/patch. **Quota**: max 40 agent-owned skills, enforced at `create`.

**Auto-injected into the system prompt** (`skills_index_block(home)`): every session start, all installed skills are listed by category as `name: description` entries, prefixed by a directive that says "check this list before reaching for general tools". Without this nudge, mimo-class models routinely went straight to `web_search`/`terminal` even when a perfect skill existed.

**TUI integration**: when a `terminal` command's path matches `.alpi/(profiles/<p>/)?skills/<cat>/<name>/...`, `arg_hint` rewrites the ToolCard label as `skill: <name>` (or `skill: <name> · <script>` when the script is the full path). Tool name stays `terminal`; the rewrite is display-only.

**Execution: `skill(action="run", name=...)`**. Single canonical ad-hoc path. If `scripts/run.py` exists the action validates the skill, then spawns the script via `subprocess.run` with `cwd` = skill dir, `env += {ALPI_HOME, ALPI_SKILL_NAME, ALPI_SKILL_DIR}`, 600s timeout, and the skill's `requires_env` checked up-front. If the skill declares `output_schema`, stdout must be JSON and is validated before the call succeeds. Scripts are normal Python; built-in tools and MCP methods are not importable Python APIs. No script → SKILL.md is returned with a `[skill X has no scripts/run.py — follow these instructions]` prefix so the agent follows the prose and calls the real tools. Scheduled prompts should call this action instead of reimplementing the skill by hand; the scheduler still enters through `alpi chat --once --emit-events --no-save`.

**Structured composition: `skill(action="invoke", name=...)`**. Same subprocess/runtime path as `run`, but stricter: the callee must ship `scripts/run.py`, must declare `output_schema`, and stdout must satisfy it. This keeps skill-to-skill composition machine-readable and prevents prose-only skills from pretending to be callable subroutines.

**Scripted harness: `skill(action="test", name=...)`**. Thin validation layer over the same runtime path. It exists so chat/scheduler/desktop can exercise a scripted skill and verify its declared `output_schema` without inventing a second testing runtime. If a CLI wrapper lands later, it should call this action instead of duplicating logic.

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

### Daemon (`alpi/service.py`)

One alpi daemon per machine, every profile inside. A single
launchd plist (`com.alpi.daemon`) on macOS or systemd-user unit
(`alpi-daemon.service`) on Linux supervises one Python process
that hosts every profile under `~/.alpi/` (default plus each
`profiles/<name>/`) on the same asyncio loop. Per-(profile,
service) tasks are independently supervised — a crash in one
profile's gateway leaves siblings untouched. Tasks are named
`<profile>/<service>` (e.g. `mirai/gateway`, `ghost/alp`) so logs
+ `asyncio.all_tasks()` stay readable.

Per-profile services (`service.{gateway, schedule, alp,
workgroups, host}` in each profile's `config.yaml`):

- **gateway** — Telegram / IMAP / Gmail / webhook listeners.
- **schedule** — cron tick loop.
- **alp** — ALP **listener** (inbound). Serves the full protocol
  on a Unix socket plus optional Noise_XK on TCP: `link.ping`,
  `link.ask`, `link.cancel` (ALP.1/2) **and** every `workgroup.*`
  verb (ALP.3). When this is off, no peer can reach you, no hub
  can fan out workgroup posts to you, and no `@-mention` to this
  profile resolves.
- **workgroups** — ALP.3 **poller** (outbound). Periodically calls
  `workgroup.pull` against the hubs of every workgroup this profile
  subscribes to, decrypts new posts, and dispatches an autonomous
  agent turn when a post mentions this profile or opens a `#task`.
  Sibling preempt watcher ticks ~6× faster to abort in-flight
  responses when a new `#task` lands. Independent from `alp`
  because direction and lifecycle are different — outbound vs
  inbound, periodic vs reactive — so a poller crash (timeout
  against a dead hub, decrypt failure on a malformed post) doesn't
  take the listener down. The naming is a historical artefact:
  workgroups IS ALP, this service is its client half.
- **host** — *default profile only*. The control-plane Unix socket
  (`~/.alpi/host/host.sock`) the desktop / mobile client uses to
  drive the daemon. Refused on non-default profiles fast — the
  client always targets default's socket and reaches sibling
  profiles via the `profile` param on each verb.

### Host plane (`alpi/host/`)

The host plane is the local device API. It is JSON-RPC-shaped over
`~/.alpi/host/host.sock` with filesystem permissions as the trust
boundary. It is not ALP: there is no peer identity, no envelope, no
Noise handshake, and no remote transport. Desktop and future mobile
clients talk to this API; they do not read profile files directly.

`host.device_state` owns the device-facing profile state contract:
profile lists/summaries, bounded profile file reads, storage stats,
gateway status/config previews, skill lists, workgroup lists, workgroup
member rosters, config field edits, and local Ollama model discovery.
The desktop Tauri layer keeps its existing `invoke(...)` command names
for UI stability, but those commands proxy to `host.*` verbs instead of
parsing `~/.alpi` themselves. Mobile should use the same verb shapes
rather than inventing a separate state API.

Default if a key is missing: every service on (so the desktop
"just works" after install).

`alpi.service.serve_all(root)` is the foreground entry point
called from `alpi daemon start` and from the supervising unit's
ExecStart. It:

1. Walks `~/.alpi/` (default + every `profiles/<name>/`) to
   discover profiles.
2. For each profile reads `service.*` toggles; missing block →
   every service on.
3. Configures the root logger at `~/.alpi/logs/service.log` (stderr
   only when it's a TTY, to avoid double-writes under launchd).
4. Sets the process title to `alpi (daemon, N profiles)` via
   `setproctitle`.
5. Writes `~/.alpi/service.pid`.
6. Spawns one supervised asyncio task per (profile, service) and
   waits. `_supervise` wraps each one so a crash leaves siblings
   running.
7. SIGTERM / SIGINT cancels every task cooperatively; PID file
   removed on exit.

**Active home isolation.** Because N profiles share one process,
tools that resolve their home via `home.get_home()` would all see
the same env vars and write to default's home. The engine wraps
each `run_turn` in a `home.set_active_home(self.home)` contextvar
binding (per-thread); `get_home()` consults this binding before
the env. Without it, mirai's memory tool would write to default's
`USER.md`. See `tests/core/test_home.py` for the isolation tests.

`daemon_status(root)` is the snapshot used by `alpi daemon status`
and by `alpi setup → Services → Daemon`: PID, uptime (via `ps -o
etime`), install backend (launchd / systemd / none), and the
per-profile services map.

### Host plane (`alpi/host/`)

Control-plane for the desktop / mobile client. **Not** ALP — the
two share a profile but live on different sockets, with different
auth models. ALP is peer-to-peer (Noise on TCP, envelope-signed,
peers pinned in `peers.yaml`); host is client-to-daemon.

Only the `default` profile hosts this subsystem — the client
always targets default's socket and reaches sibling profiles via
the `profile` parameter on each verb. `_run_host` refuses to bind
on any other profile even if the toggle leaks via manual config
edit.

Two transports, one dispatcher:

1. **Unix socket** (`~/.alpi/host/host.sock`, mode 0600). Local
   trust = filesystem perms. Used by desktop on the same machine.
   No token required.
2. **WebSocket on Tailscale or LAN** (`ws://<bind>:49200` by
   default). Used by mobile and any remote desktop. Bind address
   is auto-detected: Tailscale CGNAT (`100.64.0.0/10`) first, else
   first private RFC1918 LAN address. The listener never binds to
   `0.0.0.0`, loopback, or public IPs — that would leak the pairing
   token over plaintext on any sniffed path. **Per-device pairing
   token required** in every request's `params.auth_token`.

Bind and advertised endpoint are intentionally separate concerns.
The daemon chooses where the host-plane server listens; `Devices →
Network` chooses what the paired client should dial. On a normal Mac or
Linux install those often collapse to the same Tailscale or LAN address.
On Umbrel they do not: the daemon can bind inside Docker while the QR
advertises `umbrel.local`, a Tailscale `100.x` address, or a MagicDNS
hostname that resolves to the host machine outside the container.

Wire shape (both transports):

```
{"id": "<reqid>", "method": "host.<noun>.<verb>", "params": {…, "auth_token": "<token>"}}
```

Unix socket payload omits `auth_token`. WS payload requires it once
at least one device has been paired — empty store stays open as a
migration window for setups that predate v0.5.

The daemon writes either a single response line or, for streaming
verbs (`host.chat.send`, `host.events.subscribe`), multiple frames
followed by a `done` frame and connection close.

This is distinct from ALP peer transport. `Devices` / host-plane remote
access configures how paired desktop and mobile clients reach their own
daemon (`host.*`). `Peer TCP listener` configures the optional ALP TCP
listener other alpis use for `link.*` and `workgroup.*`.

#### Pairing tokens (`alpi/host/devices.py`)

Each remote device holds its own opaque token. The store lives at
`~/.alpi/host/devices.yaml` (mode 0600) as a list of
`{token, label, created, last_seen}`. The daemon validates the
token in `_check_token` (`alpi/host/server.py`); a hit also bumps
`last_seen` so the user sees who's active.

Token lifecycle:

- **Generate**: `host.devices.generate(label?)` returns a fresh
  `secrets.token_urlsafe(24)` (192 bits, 32 chars). The token is
  embedded in the QR shown by `alpi setup → Devices → + Add
  device`. Mobile / desktop save it to their secure store.
- **Use**: every WS request carries `auth_token`. Fail =
  JSON-RPC `{code: -32000, message: "auth-failed"}` and the
  connection closes; the mobile app's auth-failed handler wipes
  its endpoint and bounces back to the pair screen.
- **Revoke**: `host.devices.revoke(token_id)` (last 8 chars of
  the token). The TUI lists devices with `Last seen` and a
  Revoke action; revoked devices fail the next request.

`host.devices.list` redacts the full token to a `token_id` (last
8 chars) so the TUI can show paired devices without leaking
secrets. The full token only escapes the daemon once, at
`generate` time, into the one-shot QR.

Verb namespaces in current shape:

- **`host.sessions.list`**, **`host.session.read`**,
  **`host.workgroup.transcript`** — read-only.
- **`host.chat.send`** (stream), **`host.chat.cancel`** — run an
  engine turn for a profile, stream tool / reasoning / assistant
  events back; cancel via a separate connection that targets the
  in-flight `request_id`.
- **`host.providers.*`** (set_key, unset_key, add_ollama,
  remove_ollama, add_openrouter_model, remove_openrouter_model),
  **`host.peers.{add,remove,pending_list,pending_accept,pending_discard}`**,
  **`host.profile.{create,delete}`**,
  **`host.mcp.{add,remove}`**, **`host.gateway.remove`**,
  **`host.sandbox.{set,network}`**, **`host.voice.{set_voice,autoplay}`**
  — config mutations. Each is a thin wrapper around the same
  internal helper the matching CLI subcommand calls. The
  `host.peers.pending_*` verbs surface unpinned-sender entries
  recorded by the ALP server (see [ALP.md → Pending invites](ALP.md#pending-invites));
  `pending_list` enriches each row with `local_profile` when the
  pubkey resolves to a profile on this machine, so the desktop /
  TUI can pre-fill the peer id without prompting.
- **`host.workgroup.{create,update,add_member,kick,remove,action,post}`**
  — workgroup CRUD, hub-only for create/update/add_member/kick/remove,
  member-side for action (pause/resume/leave) and post. The desktop
  Tauri layer used to shell out to `alpi workgroup …` for these;
  v0.5 routes them through the host plane so mobile reuses the same
  contract.
- **`host.devices.{list,generate,revoke,rename}`** — pairing-token
  management for the WebSocket transport. `list` redacts the full
  token to `token_id` (last 8 chars); `generate` returns the fresh
  full token exactly once.
- **`host.gateway.probe`**, **`host.peers.ping`**,
  **`host.model.ctx_window`** — diagnostic probes the desktop / TUI
  used to invoke via `alpi gateway probe`, `alpi peers ping`, and
  `alpi ctx`. Same logic, host-plane entry point.
- **`host.events.subscribe`** — long-lived push channel. Daemon
  emits `{event, data}` frames as state changes. Sources call
  `alpi.host.events.emit(kind, data)`; loop is captured at first
  subscription and broadcasts via `call_soon_threadsafe` (safe to
  call from worker threads). Filter optional via `params.kinds`.
  Currently wired source: `Engine.save_session` → `session_changed`.
  Pending sources tracked in [ROADMAP.md](ROADMAP.md).

Adding a new verb: create the handler in the matching `host/*.py`
module, register on `host_server.Server.register` (or
`register_stream` for multi-frame), and call from the desktop /
mobile client via the platform's host-client helper. Never expose
a verb outside `host.*` — the namespace check in `register` enforces it.

### Gateway (`alpi/gateway/`)

Inbound platform listeners (Telegram long-poll, IMAP polling,
Gmail OAuth, webhook stub) hosted by the alpi daemon. Each
platform iterates `async for msg in platform.listen()`; per
incoming message the gateway spawns `alpi chat --once --emit-events`,
streaming tool traces as `◆ {tool} · {arg_hint}` with the typing
indicator on while the subprocess works.

Allowlist: `TELEGRAM_ALLOWED_CHAT_IDS` and `IMAP_ALLOWED_SENDERS`
in `.env`, fail-closed if unset. Per-platform user config under
`gateway.*` in `config.yaml`: chat platforms (Telegram, Matrix)
expose `show_tool_trace`, IMAP/Gmail expose `poll_interval` and
`mark_as_read`. Typing indicators are hardcoded by platform (chat
on, email off — email has no typing concept); email tool traces
are hardcoded off because each trace would be its own message.

Disable for a profile via `alpi setup → Services → Daemon →
Gateway · off` (writes `service.gateway: false`).

### Schedule (`alpi/scheduler/`)

Tick loop (default 30s) hosted inside the alpi daemon. `add`
schedules a job (`kind: cron|once`, expression or `after_hours`).
`run-once` ticks manually for testing. LLM time grounding: when
the agent calls `schedule(action='add', kind='once',
after_hours=N)`, the engine resolves `now` from a single source so
the agent doesn't drift.

**Duplicate guard + in-place edits.** `add` rejects a job whose (`kind` + cron / `run_at` / `after_hours`) matches an existing one AND whose prompt fingerprint (lowercase + whitespace-collapsed first 80 chars) collides. Pass `force=true` to bypass when the second job is genuinely intentional. Use `update` to change prompt, cron, target, or pause state without remove/recreate churn. Schedule prompts must not tell the agent to send/post to Telegram when `platform=telegram`; delivery is automatic after the scheduled reply is produced.

Scheduled jobs execute through `alpi chat --once --emit-events
--no-save` with `ALPI_PLATFORM=cron`. The scheduler consumes stdout
events to detect tool traces, final reply text, delivery, and failure.
It does not write `sessions/<id>.json`: cron output belongs to
schedule delivery/logging, not to local TUI / desktop chat history.

**Timezone.** Cron expressions evaluate against the **machine's system timezone** (`datetime.now().astimezone()` in `scheduler/run.py`). Jobs are stored with UTC `last_run_at` but fire according to local wall-clock time. Practical consequence: if you specify `10 12 * * *` because you want a 12:10 reminder in Bangkok, the Mac must be set to `Asia/Bangkok`. Move the machine to a different timezone and the cron fires at 12:10 there, not in Bangkok. No in-job timezone override today — add it via `TZ=…` in the launchd plist / systemd unit if cross-timezone stability is required.

### MCP client (`alpi/mcp/`)

Spawns user-configured MCP servers (stdio JSON-RPC, SSE planned). Their tools are wrapped and registered as alpi tools. Servers configured in `config.yaml` under `mcp.servers.<name>` (command, args, env). Management lives in `alpi setup → MCPs`; `alpi mcp` itself is not exposed on the CLI surface.

### Logging (`alpi/_log.py`, `alpi/logs.py`)

Every subsystem writes to a single flat folder: `~/.alpi/logs/<subsystem>.log`, rotated at 1 MB with no backups. Same format everywhere (`%(asctime)s %(levelname)s %(name)s %(message)s`) so `alpi logs` can merge them by timestamp prefix. The source tag on display comes from the filename.

Four sources today:

- **`service`** — the unified orchestrator's root log: subsystem
  start/stop, gateway listener events (Telegram / IMAP / Gmail),
  scheduler ticks, ALP listener traffic, delivery errors. Written
  by `alpi.service` and every subsystem that logs through the
  root logger.
- **`agent`** — one line per TUI/gateway/schedule-triggered turn: session id, elapsed, tool names, reply size, cumulative cost, truncated user prompt. This is the **cross-session grep index** — `sessions/<id>.json` carry the full detail; `agent.log` lets you answer "what has alpi been doing this week?" without iterating JSONs.
- **`approval`** — one line per non-SAFE terminal command classification (ALLOW / DENY with severity, pattern, reason). **Security audit trail**; complements the per-turn detail in `sessions/`.

Why logs are NOT inside `sessions/`: `sessions/` is a structured store (one JSON per conversation, indexed by id, consumed by `session_search` and the resume flow). Mixing freeform logs would break the glob pattern and the cleanup semantics. Logs are the **index and audit trail**; sessions are the **content**. Peers, not nested.

Why one flat folder (`logs/`) instead of per-subsystem dirs: tiny `<subsystem>/logs/` folders with a single file each is pure noise. The service keeps non-log state in its own places (`schedule/jobs.json`, `alp/alp.sock`, `service.pid` at the profile root) — only the `.log` files consolidate.

Adding a new source is two lines: `from alpi._log import get_subsystem_logger; logger = get_subsystem_logger(home, "my-sub")`. `alpi logs` picks it up without changes; add the tag to the `--source` choice list in `cli.py::logs_cmd` if you want it filterable.

### Doctor (`alpi/doctor.py`)

`alpi doctor` — live health check. Verifies each subsystem actually **responds**, not just that it's configured. Same entry point from the CLI and from `alpi setup → Health check`; the status in the setup menu row (`all green` / `N warning(s)` / `N failing`) runs the full check too.

Checks:

- **Model** — `cfg.model` set + provider's API key present in `.env` or env.
- **Workspace** — configured + exists + writable.
- **Gateways** (live) — Telegram `getMe` over HTTPS, IMAP login+SMTP handshake, Gmail OAuth token refresh.
- **Service** — `service.installed(profile)` + `service.running_pid(home)` to distinguish "installed but dead" from "running" from "not installed". A second info row lists which subsystems the config has enabled.
- **MCPs** (live) — spawn each configured server, `list_tools`, stop. Parallelised; per-server timeout 8 s.
- **Security** — sandbox backend binary on PATH (if `tools.terminal.sandbox: true`), approval allowlist count.

Parallelism: the four network-bound tasks (Telegram/IMAP/Gmail/MCPs) submit to a `ThreadPoolExecutor(max_workers=8)`. Sync checks (model, workspace, services, security) run on the main thread while the pool works. Total wall time ≈ slowest single task, not sum — ~5-10 s on a healthy profile.

Progressive rendering: `run_and_render()` uses `rich.live.Live` — every row appears immediately with a cyan spinner, each resolves to `✓`/`✗`/`!` as its future completes. Animation at 10 fps via a manual frame cycler (rich's `Spinner` objects can't be appended to `Text`). Layout is stable (same rows, same column widths) so the eye doesn't jump.

Exit codes: `1` if any check returns `fail`, `0` for warn/info/ok. Warnings don't break cron. The wizard entry ignores the exit code — it press-enter-waits so the user can read.

### Sessions (`alpi/session.py`, `alpi/session_map.py`)

Turn-based JSON: `turns: [{at, user, tools[], assistant}]` plus cumulative metrics. `ToolLog` carries `at, name, args, result (truncated hint), ok, duration_s, reasoning (non-empty only on first tool of a batch)`. Empty sessions (no user message) are NOT saved.

`sessions/` is local human chat history: TUI, desktop, and manual
`alpi chat --once` runs that should be resumable. `--continue`,
`tui.auto_resume`, host `latest_session`, and desktop profile opening
all treat only `kind == "chat"` as resumable local history. Historical
files whose first user message starts with `[SCHEDULED:]`, `[INBOUND
...]`, `[workgroup-poller]`, or another system bracket are ignored by
resume/profile history.

**TUI resume.** Bare `alpi` resumes the most recent session when `tui.auto_resume: true`; `-c` / `--continue` is the manual override.

**Gateway per-chat threading.** Each inbound message carries `external_chat_id` (a Telegram chat id, or the sender email for IMAP/Gmail). `alpi/session_map.py` holds a pointer map at `~/.alpi/<profile>/gateway/sessions/_map.json`: `{chat_id: session_id}`. When the gateway spawns `alpi chat --once --resume-chat <chat_id>`, the CLI sets `engine.session.subdir = "gateway/sessions"` and consults the map — if there's a pointer, that session is loaded and continued; otherwise a fresh session starts and the pointer gets bound after save. Same mechanism across every platform; the natural semantics fall out of what each puts in `chat_id`: per-chat threading for Telegram, per-sender threading for IMAP / Gmail.

Gateway sessions live in their own subdir (`gateway/sessions/`) so they don't pollute the local TUI/desktop session list (which scans `sessions/` only) and so the `Cleanup → Gateway` category never collides with transport state files in `gateway/` itself (Telegram offsets, IMAP last-uid, …).

Scheduled jobs do not persist session files. The scheduler uses
`--no-save` because it only needs emitted final reply/tool events for
delivery and audit; keeping a resumable transcript would make
background jobs appear as user chats.

`/new` (wired up in AK) calls `session_map.forget(chat_id)` — the pointer drops but the underlying session file stays on disk. Historical threads remain searchable via `session_search` against the local `sessions/` dir; gateway transcripts are intentionally excluded from local search.

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
- `croniter` — cron expression parsing for the scheduler subsystem.
- `setproctitle` — makes `ps aux` show ``alpi (<profile>)`` instead of identical ``alpi`` lines for every profile's service.
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
- Gateway subprocess uses `alpi chat --once --emit-events --resume-chat <chat_id>` — separate codepath from the TUI, simpler, non-streaming, and persisted under `gateway/sessions`.
- Schedule subprocess uses `alpi chat --once --emit-events --no-save` — same event stream, no resumable session file.
- `ALPI_HOME` env var routes daemons + tests to a specific profile root.
- `ALPI_SKIP_UPDATE_CHECK=1` short-circuits the background PyPI version check (`alpi/updater.py`); the autouse fixture in `tests/conftest.py` sets it so the unit suite never reaches PyPI. `ALPI_UPDATE_INDEX` overrides the JSON URL the updater hits when you need a staging or local mirror.
