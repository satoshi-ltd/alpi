# Architecture answer pack

## Answer directly

- "Where is X implemented?" -> use the paths table.
- Desktop/mobile never read `~/.alpi/` directly; they call `host.*`.
- ALP is not the app API; ALP is peer-to-peer between alpi profiles. Host plane is client-to-daemon. Different sockets, different auth.
- alpi self-knowledge is native: `alpi_knowledge` reads `alpi/knowledge/references/`, not a skill.

## Mental model

Local agent runtime, per turn:

1. Load profile config, memory, skill index, system prompt.
2. Run LLM turn with tool schemas.
3. Execute approved tools.
4. Persist session, logs, budget, events.
5. Optional daemon layer serves gateways, schedules, host clients, ALP.

## Paths

| Path | Purpose |
|---|---|
| `alpi/engine.py` | Turn loop, tool loop, event emission, interrupt flag. |
| `alpi/llm.py` | LiteLLM transport. |
| `alpi/config.py` | Config load/save, defaults, model resolution. |
| `alpi/tools/` | Tool registry + implementations (registered via `__init__.py`). |
| `alpi/tools/skill.py` | User skill management. |
| `alpi/tools/knowledge.py` | `alpi_knowledge` tool. |
| `alpi/knowledge/references/` | Packaged Markdown answer packs. |
| `alpi/memory.py` | `USER.md`, `MEMORY.md`, `AGENT.md`. |
| `alpi/promotion.py` | Compaction-to-memory promotion queue. |
| `alpi/compaction.py` | Auto-compact pipeline + logs. |
| `alpi/tools/workspace.py` | `search_workspace`, `index_workspace`. |
| `alpi/tui/` | Terminal UI. |
| `alpi/host/` | Host-plane JSON-RPC for desktop/mobile. |
| `alpi/gateway/` | Telegram, email, Matrix inbound gateways. |
| `alpi/scheduler/` | Scheduled jobs. |
| `alpi/alp/` | Alpi Link Protocol peers/workgroups. |
| `alpi/mcp/` | MCP client support. |
| `desktop/`, `mobile/` | Companion apps, if present. |

Runtime state lives per profile under `~/.alpi/` (default) or
`~/.alpi/profiles/<name>/`; it does not ship with the package. User skills
live at `{home}/skills/<category>/<name>/`.

## Engine contracts

- `Engine.run_turn()` owns one turn: append input, call model, execute tools, record usage, save session.
- `assistant_done` may be pre-tool narration or final output. Consumers delivering a canonical reply must filter `final=True`.
- Chat history lives in `sessions/`. Scheduler/gateway/workgroup/system turns must not appear as ordinary profile chats.
- A final assistant message with pending/in-progress todos is rejected; the model is re-prompted inside the same turn.

## Scheduler

- Agent jobs run via `alpi chat --once --emit-events --no-save`.
- Script jobs (`no_agent: true`) run directly, `shell=False`.
- `schedule.done` / `schedule.failed` payload: `profile`, `job_id`, `kind`, `message`, `reply`, `delivered_to`, `silent`. `schedule.failed` adds `output_id` + `deep_link` (`/outputs/<profile>/<id>`) for the persisted failure row.
- Successful schedules are not native-notified by default. To notify, a job calls `send_message(channel="alpi")`, emitting `agent.message` with `output_id` + `deep_link`.
- In schedule/gateway subprocesses the parent daemon is the single source of truth: the child's `send_message` is suppressed; the parent parses `tool_end` args via `alpi.outputs.record_child_send_message` to create the canonical output and re-emit `agent.message`. Gateway-only channels still produce an output but skip the alpi-native notification.

## Host API

Transport (see `deployments`):

- Unix socket `~/.alpi/host/host.sock` — local same-user clients, no token.
- WebSocket — paired remote clients reach the shared advertised address (`network.host`: Tailscale/LAN/VPN/hostname) with a per-device token.

Contracts:

- `host.events.subscribe` streams `{event, data, at, seq}`; `host.events.history` is `seq`-based (don't cursor on wall-clock).
- `host.events.*` is transport, not durable history. `host/events.jsonl` is a bounded reconnect replay buffer (`HISTORY_MAX = 500`) and may drop rows under load. Browseable history must query durable stores: outputs, sessions, workgroup transcripts.
- `host.chat.send` has a replay sidecar; recover missed frames via `host.chat.events_since(after_seq)`.
- `host.profile.summaries` = lightweight sidebar shape. `host.profile.detail` = heavier settings shape; its payload field is `advertise_host` (not `tcp_host`).
- `host.skills.list` is metadata-only; `host.skill.read` returns a skill body.
- `host.attachments.{stage,fetch}`: `stage` uploads a file in; `fetch` serves a tool-produced output attachment's bytes (base64) out by path, so rich clients render images inline and other files as a metadata chip; text surfaces (CLI/TUI/gateway/ALP) get a shared textual listing instead (MM.2). `fetch` reads are scoped to the profile's workspace/home/temp (see `security`).
- `host.network.*` controls companion pairing/network config; local-only.
- `host.outputs.{list,read,mark_read,mark_all_read,delete}` = persistent inbox (proactive messages + schedule results). Backed by `<home>/outputs/outputs.jsonl`, capped 500 rows, no archive (cap handles retention → two-state inbox). Row: `{id, profile, created_at, source (send_message|schedule), source_id, body, severity, kind, status (unread|read), session_id, delivered_to}`. Producers: `send_message` (alpi/both/gateway-only, non-empty text) and scheduler on `schedule.failed` (always) + `schedule.done` when delivered to a real gateway channel. Silent/stdout-only jobs file nothing. Daemon emits `output.created` for poll-free refresh.
- `host.sessions.delete` bulk-deletes chat sessions by id; admin-only, refuses active/busy sessions, removes `sessions/<id>.json` + `_events_<id>.jsonl`.
- Device records carry `role` + optional `profile_scope`. Dispatcher gates non-scope-free verbs on `params.profile in device.profile_scope or role == "admin"`, else `-32001 forbidden`. `host.devices.generate(profiles=[…])` mints scoped tokens; `host.devices.set_profiles` retunes scope without re-pairing. See `security` for scope-free allowlist + list-payload filtering.

## Doctor and cleanup

- `alpi doctor` — read-only health; may warn about outsized stores (sessions, TTS cache, workgroup transcripts), never deletes.
- `alpi setup -> Cleanup` — manual cleanup for caches, logs, mentions, gateway sessions, schedule output, workgroup files, RAG freelist vacuum.
- Desktop Manage Sessions — richer chat-session pruning UI.

## Tools

Each tool exposes `name`, `description`, JSON schema `parameters`, `run(...) -> ToolResult`.

- `write_file` / `edit_file` — syntax-lint before writing supported formats.
- `safe_write_secret(...)` — canonical path for credential files.
- `search_workspace` — semantic local RAG over the user's workspace.
- `index_workspace(path?, glob?, force?, ocr?)` — incremental by default (mtime-skip, deleted files purged); auto-rebuilds on workspace-root or embedder change; `force=true` drops + vacuums.
- `learn_file(name?, source_path?, folder?, ocr?)` (RAG.2) — promote a file to durable workspace knowledge: copy under `<workspace>/.alpi/documents/YYYY/MM/`, never overwriting; append a `manifest.jsonl` line (metadata only); index just that file via `workspace.index_files()`. Source resolves from `source_path`, a current-turn attachment by `name`, or the single current-turn attachment. Explicit user intent only — no auto-learn. Images need `ocr=true`.
- `recall_sessions(query, k=5)` / `index_sessions(force?)` (CM.4) — semantic recall over past conversations. `session_search` stays the lexical first layer; CM.4 adds the semantic layer on the same embed/sqlite-vec store, separate `session_*` table family. Opt-in indexing (never automatic), active session excluded, no per-turn injection. Forgettable: deleting a session purges its index rows (`recall.forget_session`), reindex orphan-sweeps gone sessions.
- `workgroup_search(workgroup_id, query, k=5)` / `index_workgroups(workgroup_id?, force?)` (ALP.6) — semantic search over hub-owned workgroup transcripts, same store, separate `workgroup_*` family. Hub-owned + profile-local only: no cross-peer/federated search. Decrypts via the existing key-history-aware path; opt-in, search scoped per-workgroup, no auto-injection. Forgettable: removing a workgroup (host RPC or CLI) purges its index (`workgroup_search.forget_workgroup`), reindex orphan-sweeps gone workgroups. ALP wire/crypto untouched.

## Attachments (MM.1 + RAG.2)

- `host.chat.send` takes `attachments: [{path, mime?, name?}]`; the engine validates (magic bytes, binary-as-text guard, allowlist: images/PDF/text+source) and builds multimodal content-parts. Allowed text/source incl. `py`/`js`/`ts`/`tsx`/`go`/`rs`/`sh`/`sql`.
- Per-turn only: bytes live in the in-memory message; the session persists `{name, mime, size}` — **no paths**. Validated turn attachments go to a runtime-only ContextVar (`tools/_state`) so tools resolve them without persisting paths.
- Remote clients upload via `host.attachments.stage` (caps + validation), getting a daemon-side path.
- Storage contract: documents live in the **workspace** (`.alpi/documents/`, source of truth); the RAG index lives in the **profile** (`rag/store.sqlite`); `manifest.jsonl` is metadata only. `.alpi/documents/` is the one `.alpi` subtree `index_workspace` does NOT skip, so learned docs survive a full reindex.

## Skills and knowledge

User-owned dirs under `{home}/skills/<category>/<name>/`. Runtime self-knowledge is not a skill: `alpi_knowledge` reads packaged Markdown from `alpi/knowledge/references/`.

## Memory

- `USER.md` — stable facts about the human, cap 3000 chars.
- `MEMORY.md` — durable user world/context, cap 5000 chars.
- `AGENT.md` — profile voice/persona, uncapped.
- Low-confidence memories with no reinforcement expire after 30 days.
- Compaction yields promotion candidates; only `alpi memory promote` applies them.

## Daemon and env

- One daemon supervises every profile on the machine.
- One Telegram bot token per profile.
- Profile `.env` loaded via `effective_profile_env`; the daemon does not mutate global `os.environ`.
- Gateway adapters snapshot env at construction → credential edits usually need a daemon/gateway restart.

## Security boundary

File tools and terminal commands are guarded by application-level checks; optional OS sandboxing adds isolation where supported. See `security`.

## Tests

```bash
pytest -q
pytest --integration -q
pytest --llm
```

## Related topics

- Host-plane deployment shape: `deployments`
- Config keys and restart behavior: `config`
- Security boundaries: `security`
- ALP peer protocol: `alp`
