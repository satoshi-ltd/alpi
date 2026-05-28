# Architecture answer pack

Use this for internals, code layout, engine loop, tools, daemon,
host API, scheduler, MCP, logging, and where to edit.

## Answer directly

- "Where is X implemented?" -> use the directory table.
- Desktop/mobile never read `~/.alpi/` directly; they call `host.*`.
- ALP is not the app API; ALP is peer-to-peer between alpi profiles.
- alpi self-knowledge is native: `alpi_knowledge` reads `alpi/knowledge/references/`.

## Mental model

alpi is a local agent runtime:

1. Load profile config, memory, skill index, and system prompt.
2. Run an LLM turn with tool schemas.
3. Execute approved tools.
4. Persist session, logs, budget, and events.
5. Optional daemon layer serves gateways, schedules, host clients, and ALP.

## Important paths

| Path | Purpose |
|---|---|
| `alpi/engine.py` | Main turn loop and event emission. |
| `alpi/llm.py` | LiteLLM transport. |
| `alpi/config.py` | Config loading and model resolution. |
| `alpi/tools/` | Tool registry and tool implementations. |
| `alpi/tools/skill.py` | User skill management. |
| `alpi/tools/knowledge.py` | `alpi_knowledge` tool. |
| `alpi/knowledge/references/` | Packaged Markdown answer packs. |
| `alpi/memory.py` | `USER.md`, `MEMORY.md`, `AGENT.md`. |
| `alpi/promotion.py` | Compaction-to-memory promotion queue. |
| `alpi/compaction.py` | Auto-compact pipeline and logs. |
| `alpi/tools/workspace.py` | `search_workspace` and `index_workspace`. |
| `alpi/tui/` | Terminal UI. |
| `alpi/host/` | Host-plane JSON-RPC for desktop/mobile. |
| `alpi/gateway/` | Telegram, email, Matrix inbound gateways. |
| `alpi/scheduler/` | Scheduled jobs. |
| `alpi/alp/` | Alpi Link Protocol peers/workgroups. |
| `alpi/mcp/` | MCP client support. |
| `desktop/`, `mobile/` | Companion apps, if present. |

## Engine contracts

- `Engine.run_turn()` owns one turn: append input, call model, execute
  tools, record usage, save session.
- `assistant_done` can be pre-tool narration or final output. Consumers
  that deliver a canonical reply must filter `final=True`.
- Normal chat history lives in `sessions/`. Scheduler, gateway,
  workgroup, and system turns must not appear as ordinary profile chats.
- Open todos are enforced by the engine: a final assistant message with
  pending/in-progress todos is rejected and the model is re-prompted
  inside the same turn.

## Scheduler

- Agent jobs run through `alpi chat --once --emit-events --no-save`.
- Script jobs with `no_agent: true` run directly with `shell=False`.
- `schedule.done` / `schedule.failed` carry structured payloads:
  `profile`, `job_id`, `kind`, `message`, `reply`, `delivered_to`,
  `silent`. On `schedule.failed` the payload also carries
  `output_id` + `deep_link` (`/outputs/<profile>/<id>`) pointing at
  the persisted failure row.
- Successful schedules are not native-notified by default. A job that
  should notify the user calls `send_message(channel="alpi")`, which
  emits `agent.message` carrying `output_id` + `deep_link`.
- In schedule and gateway subprocesses the parent daemon is the
  single source of truth: the child's `send_message` is suppressed
  and the parent parses the `tool_end` args through the shared
  `alpi.outputs.record_child_send_message` helper to create the
  canonical output and re-emit `agent.message`. Gateway-only
  channels still produce an output (so the user can revisit what
  was pushed to Telegram/etc.) but skip the alpi-native notification.

## Host API

Desktop/mobile use `host.*` over:

- Unix socket: `~/.alpi/host/host.sock` for local same-user clients.
- WebSocket: paired remote clients over Tailscale/LAN with device token.

Important host contracts:

- `host.events.subscribe` streams `{event, data, at, seq}`.
- `host.events.history` is `seq`-based; clients should not use wall-clock
  timestamps as cursors.
- `host.events.*` is transport, not durable history. `host/events.jsonl`
  is a bounded reconnect replay buffer (`HISTORY_MAX = 500`) and can
  drop rows under load. UIs that need browseable history must query the
  durable stores: outputs, sessions, or workgroup transcripts.
- `host.chat.send` has a replay sidecar; clients recover missed frames
  with `host.chat.events_since(after_seq)`.
- `host.profile.summaries` is the lightweight sidebar shape.
- `host.profile.detail` is the heavier settings/profile shape.
- `host.skills.list` is metadata-only; `host.skill.read` returns a skill body.
- `host.network.*` controls companion app pairing/network config and is
  local-only.
- `host.outputs.{list,read,mark_read,mark_all_read,delete}` exposes the
  persistent inbox (proactive agent messages + schedule results).
  Backed by `<home>/outputs/outputs.jsonl`, capped at 500 rows.
  Producers: `send_message` (every channel — alpi / both /
  gateway-only with non-empty text) and the scheduler on
  `schedule.failed` (always) and `schedule.done` when the reply
  was delivered to a real gateway channel (telegram / email /
  matrix / …). Stdout-only maintenance scripts and silent jobs
  file nothing. Each row
  has `{id, profile, created_at, source (send_message|schedule),
  source_id, body, severity, kind, status (unread|read),
  session_id, delivered_to}`. No archive flow — the cap handles
  retention so clients only render a two-state inbox. The daemon
  also emits `output.created` so inbox surfaces can refresh
  without polling.
- `host.sessions.delete` bulk-deletes chat sessions by id. It is
  admin-only, refuses active/busy sessions, and removes both
  `sessions/<id>.json` and `_events_<id>.jsonl`.
- Device records carry `role` + optional `profile_scope`. The
  dispatcher gates non-scope-free verbs on
  `params.profile in device.profile_scope or role == "admin"`,
  returning `-32001 forbidden` otherwise. `host.devices.generate`
  takes `profiles=[…]` for scoped tokens; `host.devices.set_profiles`
  retunes scope without re-pairing. See `security` for the scope-free
  verb allowlist and list-payload filtering rules.

## Doctor and cleanup

- `alpi doctor` is read-only health. It may warn about outsized
  per-profile stores (sessions, TTS cache, workgroup transcripts) but
  never deletes.
- `alpi setup -> Cleanup` is the manual cleanup surface for caches,
  logs, mentions, gateway sessions, schedule output, workgroup files,
  and RAG freelist vacuum.
- Desktop Manage Sessions is the richer UI for pruning chat sessions.

## Tools

Tools live in `alpi/tools/` and register through `alpi/tools/__init__.py`.
Each tool exposes `name`, `description`, JSON schema `parameters`, and
`run(...) -> ToolResult`.

Important tool helpers:

- `write_file` / `edit_file` run syntax linting before writing supported
  formats.
- `safe_write_secret(...)` is the canonical path for credential files.
- `search_workspace` is semantic local RAG over the user's workspace.
- `index_workspace(path?, glob?, force?, ocr?)` is incremental by
  default (mtime-skip, deleted files purged); auto-rebuilds on a
  workspace-root or embedder change; `force=true` drops + vacuums.

## Skills and knowledge

Skills are user-owned directories under
`<home>/skills/<category>/<name>/`. Runtime self-knowledge is not a
skill; `alpi_knowledge` reads packaged Markdown from
`alpi/knowledge/references/`.

## Memory

- `USER.md`: stable facts about the human, capped at 3000 chars.
- `MEMORY.md`: durable user world/context, capped at 5000 chars.
- `AGENT.md`: profile voice/persona, uncapped.
- Low-confidence memories with no reinforcement expire after 30 days.
- Compaction produces promotion candidates; only `alpi memory promote`
  applies them to durable memory.

## Daemon and env

- One daemon supervises every profile on the machine.
- One Telegram bot token per profile.
- Profile `.env` is loaded through `effective_profile_env`; the daemon
  does not mutate global `os.environ`.
- Gateway adapters snapshot env at construction, so credential edits
  usually require daemon/gateway restart.

## Security boundary

File tools and terminal commands are guarded by application-level
checks. Optional OS sandboxing provides stronger isolation where
supported. See `security`.

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
