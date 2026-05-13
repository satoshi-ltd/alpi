# Architecture answer pack

Use this for internals, code layout, engine loop, tools, daemon,
gateway, scheduler, MCP, logging, and where to edit.

## Mental model

alpi is a local agent runtime:

1. Load profile config, memory, skills index, and system prompt.
2. Run an LLM turn with tool schemas.
3. Execute approved tools.
4. Persist session/log/budget state.
5. Optionally run under the daemon for gateways, schedules, workgroups,
   and host verbs.

## Important directories

| Path | Purpose |
|---|---|
| `alpi/engine.py` | Main turn loop. |
| `alpi/llm.py` | LiteLLM transport. |
| `alpi/config.py` | Config loading and model resolution. |
| `alpi/tools/` | Tool registry and tool implementations. |
| `alpi/tools/workspace.py` | `search_workspace` + `index_workspace` (BA local RAG). |
| `alpi/tools/skill.py` | User/bundled skill management. |
| `alpi/skills/` | Bundled skills packaged with alpi. |
| `alpi/memory.py` | Memory file management (USER.md, MEMORY.md, AGENT.md). |
| `alpi/promotion.py` | Promotion queue — staging area between compaction and durable memory. |
| `alpi/compaction.py` | Auto-compact pipeline + event log + candidate extraction. |
| `alpi/core/` | Shared primitives: sqlite-vec store, embedder, locked Chromium installer. |
| `alpi/tui/` | Terminal UI. |
| `alpi/gateway/` | Telegram/IMAP/Gmail/Matrix inbound gateways. |
| `alpi/scheduler/` | Scheduled jobs. |
| `alpi/service.py` | Background daemon/service management. |
| `alpi/alp/` | Alpi Link Protocol. |
| `alpi/mcp/` | MCP client support. |
| `desktop/` | Tauri desktop app, if present. |

## Engine loop

`Engine.run_turn()` binds the active home/profile, serializes turns,
checks budget, injects transient context, appends user input, streams
LLM output, executes tool calls, records usage, and saves the session.

`sessions/` is local human chat history. TUI resume, desktop profile
history, and host `latest_session` use only sessions classified as
`chat`; scheduled, gateway, workgroup, and system-prefixed turns must
not appear as normal profile chats.

Scheduled jobs run through `alpi chat --once --emit-events --no-save`
with `ALPI_PLATFORM=cron`. The scheduler reads stdout events and
delivers the final reply, but no session file is saved.

Skills are exposed through a compact index in the system prompt.
Keyword hints can add a one-turn system message nudging toward matching
skills.

## Tools

Tools live under `alpi/tools/` and register through
`alpi/tools/__init__.py`. Each tool exposes:

- `name`,
- `description`,
- JSON schema `parameters`,
- `run(...) -> ToolResult`.

Use existing tool patterns before adding abstractions.

### Local RAG (BA)

`search_workspace` (semantic search over the user's local files) and
`index_workspace` (build/refresh the index). Per-profile index at
`<profile>/rag/store.sqlite` using `sqlite-vec`. Embeddings via
`fastembed` running the ONNX export of
`sentence-transformers/all-MiniLM-L6-v2` (384-dim, no torch).
Supports markdown, text, source, configs, HTML, PDF (`pypdf` for
text-layer), DOCX, EPUB, and images. OCR uses `rapidocr-onnxruntime`
+ `pypdfium2`; opt-in via `ocr=true`, scanned PDFs without it land
in `failed_files`. The daemon pre-loads the fastembed ONNX model
into runtime cache in a background thread 5 s into the event loop
(after socket bind). RapidOCR is downloaded lazily on first
`ocr=true` use. Concurrent loaders are serialized by per-asset
locks.

For workspace-content questions ("what does my file say about X"),
the agent reaches `search_workspace` first; `search` (grep) stays
for code / literal-string matches.

## Skills

User skills live in profile home. Bundled skills live in
`alpi/skills/` package resources and are addressed as `@alpi/<name>`.
The desktop/mobile client should talk to daemon host verbs, not read
profile files directly.

## Memory + promotion queue

Files at `<home>/memories/`:

| File | Cap | Purpose |
|---|---|---|
| `USER.md` | 3000 | Stable facts about the human |
| `MEMORY.md` | 5000 | World the user operates in |
| `AGENT.md` | — | Agent's own voice/style/persona |

Entry shape: `<!-- alpi-meta conf={low\|normal\|high} captured=ISO reinforced=N -->` trailer, stripped before reaching the system prompt. Low-conf + 0 reinforcements expire at `LOW_CONFIDENCE_MAX_AGE_DAYS = 30` (constant in `alpi/memory.py`, not user-configurable). Near-duplicate writes reinforce existing entry (Jaccard ≥ 0.7) instead of appending. Scanner blocks Trojan-Source unicode, prompt-injection patterns, secret leakage.

**Compaction** (`alpi/compaction.py`): fires when projected prompt > 0.75 × `ctx_window`. Cheap pass truncates oversized tool outputs first. LLM summarizes the middle; preserves system + first 2 + last 8 non-system messages. Targets 0.4 × `ctx_window` post-compact. One JSONL line appended per fired compaction to `<home>/logs/compaction.jsonl`.

**Promotion queue** (`alpi/promotion.py`): after each fired compaction the engine runs a second LLM call against the summary and pushes candidates to `<home>/memories/promotion_queue.jsonl`. Per-record shape: `id` (8-char hex), `created_at` (unix ts), `source` (`compaction`|`reviewer`|`manual`), `session_id`, `model`, `target` (`USER.md`|`MEMORY.md`|`AGENT.md`), `text`, `confidence` (`low`|`normal`|`high`), `warnings` (list of strings — operational-state, cross-file duplicate, safety scan hits computed at enqueue). Cap 200 pending; entries expire 30d.

Tool actions: `memory(action="promotion_list")` read-only, `memory(action="promotion_discard", id=…)` drops without writing. **No agent apply path.** `promotion_apply` rejects with a pointer to the CLI. Only `alpi memory promote` writes — interactive `[a]pply/[d]iscard/[s]kip/[q]uit`, plus `--apply-all` / `--discard-all`. Apply routes through `memory(action="add")` so safety scan + dedup still gate. If add rejects, candidate stays in queue.

## Daemon and gateways

- `alpi daemon ...` manages the per-machine daemon.
- Gateways receive inbound messages and hand them to the engine.
- Scheduler jobs also run through the agent loop.
- One daemon supervises every profile on the machine.

## Host/API boundary

Desktop/mobile clients use `host.*` verbs in `alpi/host/`. Two
transports: Unix socket (`~/.alpi/host/host.sock`, local, no token)
and WebSocket on Tailscale or RFC1918 LAN (per-device token in
`params.auth_token`). Desktop should support multiple host-plane
connections: local socket plus paired remote daemons. Bind never goes
to `0.0.0.0`/public on normal hosts. `Devices -> Network` controls the
advertised companion endpoint; it can differ from the bind address
(notably on Umbrel, where the daemon binds inside Docker but the QR
advertises the host's external name or Tailscale IP). Tokens at
`~/.alpi/host/devices.yaml`, generated from `alpi setup → Devices`.
The host surface includes chat, sessions, workgroups, pairing-token
management, probes, schedule verbs, and daemon restart.

Clients must not read `~/.alpi/` directly or spawn `alpi` as a
subprocess. ALP (`alpi/alp/`) is separate (peer-to-peer). `Peer TCP
listener` configures ALP's optional TCP listener; it is not the same
as the host-plane companion endpoint.

## Security boundary

File tools and terminal commands are guarded by application-level
checks. Optional OS sandboxing can restrict filesystem/network access
for stronger isolation. See `security.md`.

## Tests

Common commands:

```bash
pytest -q
pytest --integration -q
pytest --llm
```

Fast tests cover unit/filesystem behavior. Integration tests cover
sockets and sandbox paths. LLM tests make real provider calls.
