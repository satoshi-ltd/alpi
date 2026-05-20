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

`AgentEvent(kind="assistant_done")` can fire for pre-tool narration as
well as the final answer. Consumers that build a canonical reply
(`chat --once`, host chat, ALP, scheduler delivery, tests) must use
only events with `final=True`. The TUI may consume every
`assistant_done` because it rewrites the live assistant bubble.

`sessions/` is local human chat history. TUI resume, desktop profile
history, and host `latest_session` use only sessions classified as
`chat`; scheduled, gateway, workgroup, and system-prefixed turns must
not appear as normal profile chats.

Scheduled jobs run through `alpi chat --once --emit-events --no-save`
with `ALPI_PLATFORM=cron`. The scheduler reads stdout events and
delivers the final reply, but no session file is saved. `run_job()`
returns `JobOutcome`: `ok`, operational `message`, clean `reply`,
`delivered_to`, and `silent`. `schedule.done` / `schedule.failed`
events carry those fields so clients render notifications from
explicit data rather than parsing `message`. `reply` is capped at
2000 chars in host events. `serve()` runs each `tick()` in a dedicated
`ThreadPoolExecutor`, and `host.schedule.fire` wraps `fire_by_id` in
`run_in_executor`, so a long `subprocess.run` job can't starve
sibling-profile coroutines on the daemon loop.

Jobs with `no_agent: true` skip the LLM entirely. The `prompt` is
shlex-tokenized and exec'd directly (`shell=False`); `${ALPI_HOME}`
expands to the profile home and the profile's `.env` is merged into
the subprocess env so skills find their declared `requires_env`.
Empty stdout = silent ok. Non-empty stdout = delivered if `platform`
is set, otherwise summarized in the daemon log. Use this for
deterministic skills (data sync, file processors) — saves both
tokens and ~30s of agent boot latency per fire.

`host.chat.send` persists every emitted frame to a per-turn JSONL
sidecar (`sessions/_events_<session_id>.jsonl`); the desktop calls
`host.chat.events_since(after_seq)` to replay missed frames when the
stream socket dies mid-turn. A 5s `heartbeat` frame keeps the
client's stall watchdog alive on long tool calls.

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

`alpi/tools/_lint.py::lint_content(path, content)` runs a parser-based
syntax check before every `write_file` / `edit_file` lands on disk
(`.py` → `ast.parse`, `.json` → `json.loads`, `.yaml`/`.yml` →
`yaml.safe_load`, `.toml` → `tomllib` on 3.11+ / `tomli` conditional
dep on 3.10). On failure the write is refused and the original file
(if any) is untouched — malformed configs never reach downstream
consumers.

`alpi/secrets_io.py::safe_write_secret(path, content, mode=0o600)`
is the canonical write path for credential files. Uses
`tempfile.mkstemp` (O_EXCL + 0o600 at creation, random unique
name) + `os.replace` — no TOCTOU window, and a stale
`<target>.tmp` at looser perms cannot compromise the write.
Used by `model_selector` (.env), `mail/gmail_auth` (gmail token),
`alp/pending` (yaml), and `alp/keys` (ALP private key).

### Local RAG (BA)

`search_workspace` (semantic search over the user's local files) and
`index_workspace` (build/refresh the index). Per-profile index at
`<profile>/rag/store.sqlite` using `sqlite-vec`. `index_workspace`
with `force=true` drops + rebuilds the schema and `VACUUM`s after the
rebuild commits — DROP TABLE leaves pages in the SQLite freelist
and never shrinks the file otherwise, which bloated `store.sqlite`
across past force reindexes. Manual repair lives in `setup → Cleanup
→ RAG store bloat` (vacuum action, not unlink). Embeddings via
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
- **One Telegram bot per profile** — Telegram allows only one poller
  per token; two profiles sharing a token 409 each other forever. The
  contract is enforced at write time (TUI setup + host RPC reject
  duplicates) and listeners read their token from `<home>/.env`, not
  the global env.
- **Per-profile env isolation** — `alpi.home.effective_profile_env(home,
  *, base=None, extra=None)` is the canonical helper: `base`
  (defaults to `os.environ`) overlaid with `<home>/.env` overlaid
  with `extra`. The daemon never mutates `os.environ`. Every
  `Platform` snapshots this into `self.env` at construction;
  Telegram token, IMAP (`from_env_map`), Matrix `_build_client`,
  inbound `delivery.is_allowed(env=…)` all read from it. Agent
  tools (`tools/{skill,terminal,email,web_extract,read_image}`),
  the model selector / TUI gating (`Provider.has_key(env=…)`),
  identity drafting (`config.resolve_model(cfg)`), and the gateway
  child agent extend the contract. Snapshot is frozen at
  construction; credential edits write the file atomically but
  live listeners pick up the change on next daemon/gateway restart.

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
management, pairing-network config, probes, schedule verbs, and daemon
restart.

Pairing-network config is exposed as:

- `host.network.status` — returns the live advertised endpoint plus
  candidates (`tailscale`, `lan`, `configured`), `port`, `device_name`,
  `diagnosis`, and `is_override`. `scope_in_use` is the host's network
  character (`tailscale`, `lan`, `custom`, `umbrel`, or `None`), not the
  raw resolution path.
- `host.network.set_advertised({host?, device_name?})` — writes
  `cfg.host.tcp_host` and/or `cfg.host.device_name`. Missing key =
  preserve; explicit `""` = unset that field. Public IPs, loopback,
  multicast/link-local/reserved addresses, and malformed hostnames are
  rejected.
- `host.network.restart_host_server` — idempotently restarts the daemon
  so the TCP listener uses the fresh config.

All three `host.network.*` verbs are local-only: desktop over the Unix
socket can call them, but a paired remote client over WebSocket gets
`forbidden`.

`host.events.subscribe` emits live `{event, data, at, seq}` frames
and a `{event: "subscribed", next_seq}` handshake on connect.
`host.events.history({after_seq?, kinds?, limit?})` returns
`{events, next_seq}` from a bounded in-memory ring backed by
compacted `<server.home>/host/events.jsonl`. The contract is
**seq-only**: clients pivot on monotonic `seq`, never wall-clock
`at` (clock skew + suspend-resume scramble that). The legacy
`since` param is silently ignored. **Subscribe FIRST**, then on the
`subscribed` handshake backfill from the previous cursor — doing
history-then-subscribe leaves a race window where frames fired
between the two calls are counted in the daemon's seq but never
delivered. Wired event kinds beyond chat/sessions/wg.post/wg.done:
`schedule.{done,failed,changed}`, `config_changed`,
`gateway_changed`, `peers_changed`, `profile_changed`,
`workgroup_changed`, `workgroup_members`, `budget.threshold`.

Host model/device helpers are additive and tolerant of partial failure:
`host.providers.ollama_models` returns `{models, errors}` so one
unreachable local Ollama endpoint does not hide the rest, and
`host.voice.preview` returns a short daemon-synthesized MP3 preview
as base64 with controlled errors for missing TTS dependencies.

**Lite/detail split on the hot path** (v0.4.52). `host.profile.summaries`
ships only the inbox/sidebar shape (name, model, accent,
latest_session, counts, budget_*, pubkey_b64, has_any_provider,
subsystems). The heavy companion lives in `host.profile.detail`
(workspace, tcp_*, provider_keys, provider_ollama, sandbox*,
voice_*, mcps, peers, models) — fetched lazily by settings/profile
screens, cached per `(connectionId, profile)` so two daemons with
the same profile name never bleed state. `host.skills.list` is
also lightweight: no SKILL.md body by default (`~32KB/skill`);
`host.skill.read({name, category?})` returns one skill's body on
demand. `_counts.skills` counts SKILL.md directories without reading
bodies. `host.workgroup.transcript({after_seq?, limit?, tail?})`
returns `{posts, next_seq, limit}`; without `after_seq` the default
is `tail=true` so first-paint of a long-lived workgroup ships the
recent window, not the oldest. `decrypt_transcript` opens the hub
sealed group key once outside the per-post loop.

**WebSocket transport** negotiates `permessage-deflate` by default
(`ws_serve(compression="deflate")`), which trims JSON-RPC payloads
50–80% on Tailscale. Desktop and mobile maintain a persistent
multiplexed WS pool per `(ip, port, token)` so chatty RPCs amortize
the TCP+WS handshake. Streams (`host.chat.send`,
`host.events.subscribe`) open their own dedicated socket.

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
