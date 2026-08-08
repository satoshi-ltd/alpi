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
5. Optional daemon layer serves schedules, host clients, ALP.

## Paths

| Path | Purpose |
|---|---|
| `alpi/engine.py` | Turn loop, tool loop, event emission, interrupt flag. |
| `alpi/llm.py` | LiteLLM transport. |
| `alpi/prompt_cache.py` | Stable cacheable system-prompt prefix assembly and platform/env hints. |
| `alpi/config.py` | Config load/save, defaults, model resolution. |
| `alpi/attachments.py` | Input/output attachment validation, mime/magic checks, text rendering for non-rich surfaces. |
| `alpi/tools/` | Tool registry + implementations (registered via `__init__.py`). |
| `alpi/tools/skill.py` | User skill management. |
| `alpi/scan.py` | Shared scanner library — skill/code danger patterns, prompt-injection detection, invisible-unicode; used by skills, memory writes, and the recalled-memory guard. |
| `alpi/tools/knowledge.py` | `alpi_knowledge` tool. |
| `alpi/knowledge/references/` | Packaged Markdown answer packs. |
| `alpi/memory.py` | `USER.md`, `MEMORY.md`, `AGENT.md`. |
| `alpi/promotion.py` | Compaction-to-memory promotion queue. |
| `alpi/compaction.py` | Auto-compact pipeline + logs. |
| `alpi/tools/knowledge_base.py` | `knowledge` tool for user/workspace OKF wiki. |
| `alpi/tools/workspace.py` | Document readers/chunker used by knowledge ingest. |
| `alpi/tui/` | Terminal UI. |
| `alpi/host/` | Host-plane JSON-RPC for desktop/mobile. |
| `alpi/mail/` | Multi-account email backing the on-demand `email` tool — `accounts.py` (account model, id = slug of address), IMAP/Gmail clients + OAuth. |
| `alpi/scheduler/` | Scheduled jobs. |
| `alpi/outputs.py` | Persistent native inbox rows for proactive messages and schedule results. |
| `alpi/ledger.py` | Daily spend ledger (`logs/ledger.json`): budget cap gate + 30-day per-day history. |
| `alpi/run_ledger.py` | Capped JSONL run evidence for agent/schedule/workgroup/terminal runs. |
| `alpi/ops_digest.py` | Human-readable operational digest over logs, runs, outputs, and stores. |
| `alpi/alp/` | Alpi Link Protocol peers/workgroups. |
| `alpi/mcp/` | MCP client support. |
| `desktop/`, `mobile/` | Companion apps, if present. |

Runtime state lives per profile under `~/.alpi/` (default) or
`~/.alpi/profiles/<name>/`; it does not ship with the package. User skills
live at `{home}/skills/<category>/<name>/`.

## Engine contracts

- `Engine.run_turn()` owns one turn: append input, call model, execute tools, record usage, save session.
- `assistant_done` may be pre-tool narration or final output. Consumers delivering a canonical reply must filter `final=True`.
- Chat history lives in `sessions/`. New files use `schema_version: 2`: large user/assistant/reasoning/tool payloads are stored as bounded previews plus byte/hash metadata, not raw unbounded blobs. Scheduler/workgroup/system turns must not appear as ordinary profile chats.
- Client-facing reads go through `host.session.read`, which normalizes legacy and v2 payloads back to the shape clients render. Code that needs a durable review should use that path instead of assuming `tools[].args`, `tools[].result`, or `reasoning` are raw strings on disk.
- Session listings are bounded: large files are summarized from stat/head data, while `host.profile.summaries` uses `count_sessions()` / `latest_chat_summary()` so sidebar and Settings do not parse huge histories.
- Live reconnect replay uses `sessions/_events_<id>.jsonl`; incremental deltas are preserved exactly, while oversized text frames are clipped. The sidecar is reconnect/backfill, not the full durable archive, so do not treat it as the canonical session log.
- Each turn runs on a fresh Engine that rehydrates the session from disk (`_hydrate_from_path`). Cross-turn context = a resume note + each **replayable** prior turn — one that ended in a final reply or produced a file; aborted/tool-only turns (no reply, no output files) are dropped so a resume never re-answers a dangling request. Each replayed turn contributes its user text (with an input marker `[attached: name (mime)]`) + assistant text (with a produced-file marker `[produced this turn … name → /abs/path]`). Tool calls and tool results are NOT replayed (context budget): an agent does not see its prior search/read/analyze output across turns — only its final text and the absolute paths of files it produced. A follow-up edit reuses the produced path from the marker, not a remembered tool result.
- A final assistant message with pending/in-progress todos is rejected; the model is re-prompted inside the same turn. The one exception is the max-steps wrap-up (below): it finalizes regardless of open todos, because no steps remain to re-prompt.
- Tool calls per turn are capped at `tools.max_steps_per_turn` (default 100). When left at the default, a free model (zero per-token OpenRouter pricing) or a local/ollama one raises the ceiling to 1000; an explicitly configured value is always respected (it also bounds loops / refusals / the TODO guard, not just cost). Hitting the cap doesn't fail the turn — the engine makes one tools-off wrap-up call so a best-effort final reply is still produced.

## Scheduler

- Agent jobs run via `alpi chat --once --emit-events --no-save`.
- Script jobs (`no_agent: true`) run directly, `shell=False`.
- Each fire is capped at `job.timeout` seconds (default 900, max 3600) — a stuck-process backstop for unattended runs, not the cost guard (`budget.daily_usd` is) and not a hint that jobs must be short. Heavy jobs (deep research, multi-step publishing) raise it via `schedule(add|update, timeout=…)`. The scheduler hands the child a soft budget (`ALPI_TURN_BUDGET_S`, ~10% reserved) so the engine wraps up gracefully — one tools-off final reply — before the hard `subprocess` kill, instead of dying with no answer; the hard cap stays as the last-resort backstop if the wrap-up itself stalls.
- `schedule.done` / `schedule.failed` payload: `profile`, `job_id`, `title`, `kind`, `message`, `reply`, `delivered_to`, `silent`. `schedule.failed` adds an enriched `body` (failure reason + timeout/exit), plus `output_id` + `deep_link` (`/outputs/<profile>/<id>`) for the persisted failure row (which carries the same `title`). `schedule.failed` is itself a client notification — failures are NOT re-emitted as `agent.message`.
- Jobs are silent by default (`notify: false`). Set `notify: true` and the reply is pushed to the owner's apps — the scheduler re-emits `agent.message` (`delivered_to="alpi"`) with `output_id` + `deep_link`. A job that wants to reach a THIRD PARTY uses the `email` tool in its prompt; that does not count as notifying the owner.
- In schedule subprocesses the parent daemon is the single source of truth: the child's `notify` is suppressed; the parent parses `tool_end` args to create the canonical output and re-emit `agent.message`. If the agent already notified itself, the scheduler skips the auto-notify (`delivered_to="external"`).

## Host API

Transport (see `deployments`):

- Unix socket `~/.alpi/host/host.sock` — local same-user clients, no token.
- WebSocket — paired remote clients reach the shared advertised address (`network.host`: Tailscale/LAN/VPN/hostname) with a per-device token.

Contracts:

- `host.events.subscribe` streams `{event, data, at, seq}`; `host.events.history` is `seq`-based (don't cursor on wall-clock).
- `host.events.*` is transport, not durable history. `host/events.jsonl` is a bounded reconnect replay buffer (`HISTORY_MAX = 500`) and may drop rows under load. Browseable history must query durable stores: outputs, sessions, workgroup transcripts.
- `host.chat.send` has a replay sidecar; recover missed frames via `host.chat.events_since(after_seq)`.
- `host.profile.summaries` = lightweight sidebar shape. `host.profile.detail` = heavier settings shape; its payload field is `advertise_host` (not `tcp_host`).
- `host.skills.list` returns per-skill `status`/`reason`/`size`/`keywords` + metadata; `host.skill.read` returns structured detail (frontmatter, resolved `requires[]`, file `tree`, body ≤32K); `host.skill.file` reads one file ≤256K and refuses `secrets/`/symlinks (`name`/`category` must be `[A-Za-z0-9_-]+`).
- `host.attachments.{stage,fetch}`: `stage` uploads a file in; `fetch` serves a tool-produced output attachment's bytes (base64) out by path, so rich clients render images inline and other files as a metadata chip; text surfaces (CLI/TUI/ALP) get a shared textual listing instead. `fetch` reads are scoped to the profile's workspace/home/temp (see `security`).
- `host.network.*` controls companion pairing/network config; local-only.
- `host.usage.daily` / `host.usage.workgroup.daily` (admin-only) = a 14-day per-day series of token usage + cost; the profile payload also carries a `total30` aggregate over the 30-day retention and is identical to the profile snapshot's `usage` section. Profile usage reads the `ledger.json` 30-day history (authoritative for ALL spend, incl. non-token costs like image generation); workgroup usage reads the hub transcript's per-post declared cost. Both bucket by UTC day, so today matches the budget gate.
- `host.outputs.{list,read,mark_read,mark_all_read,delete}` = persistent inbox (proactive messages + schedule results). Backed by `<home>/outputs/outputs.jsonl`, capped 500 rows, no archive (cap handles retention → two-state inbox). Row: `{id, profile, created_at, title?, body, type (info|warning|error), status (unread|read), session_id, delivered_to}` (`title` set by `notify` callers and on scheduler failure rows — the job's title; omitted otherwise). `notify` sets `type`; scheduler failures are `error`. Producers: `notify` (owner push) and scheduler on `schedule.failed` (always) + `schedule.done` when the job notified the owner (`notify: true` → `delivered_to="alpi"`). Jobs whose agent notified itself (`delivered_to="external"`) don't duplicate; silent jobs (`notify: false`) and stdout-only summaries file nothing. Daemon emits `output.created` (`{profile, id, type}`) for poll-free refresh.
- `host.sessions.delete` bulk-deletes chat sessions by id; admin-only, refuses active/busy sessions, removes `sessions/<id>.json` + `_events_<id>.jsonl`.
- `~/.alpi/host/connections.yaml` groups a connection identity (`label`, `role`, `profile_scope`) with independently revocable device credentials and hashed one-time pairing grants. Grants expire after ten minutes and `host.connections.exchange_pairing` consumes one atomically before returning the permanent device token once. Terminal grant metadata is kept for seven days, capped at 50 rows per connection and omitted from connection-list responses. Dispatcher resolves each permanent token to connection/device IDs and gates scoped members on `params.profile in connection.profile_scope`, else `-32001 forbidden`. Sessions and daily ledger usage are attributed to the connection; local Unix/TUI/CLI activity uses synthetic `host`. `host.connections.*` is canonical and `host.devices.*` remains a management compatibility alias. See `security` for the bootstrap exception, scope-free allowlist and migration behavior.

## Doctor and cleanup

- `alpi doctor` — read-only health; may warn about outsized stores (sessions, TTS cache, workgroup transcripts), never deletes.
- `alpi audit` — read-only security posture for the whole install; scans every
  profile, checks permissions/network/hardening offline, and optionally queries
  OSV for installed-package CVEs unless `--offline` is set.
- `alpi setup -> Cleanup` — manual cleanup for caches, logs, mentions, schedule output, workgroup files, knowledge index freelist vacuum.
- Desktop Manage Sessions — richer chat-session pruning UI.

## Tools

Each tool exposes `name`, `description`, JSON schema `parameters`, `run(...) -> ToolResult`.

- `write_file` / `edit_file` — syntax-lint before writing supported formats.
- `safe_write_secret(...)` — canonical path for credential files.
- `knowledge(action="search", query, k=5)` — semantic + lexical recall over synthesized OKF pages in `<workspace>/knowledge/`.
- `knowledge(action="ingest", source_path?|name?, topic?, ocr?)` — explicit learning from a source file or current-turn attachment. The source is read and summarized into Markdown; the raw file is not copied.
- `knowledge(action="maintain", source_path?, topic?, apply=true, ocr=false)` — explicit LLM-wiki workflow: write/update pages, update index/log, lint, then refresh the derived index.
- `knowledge(action="lint", path?)` / `knowledge(action="index", path?, force?)` — validate the bundle or rebuild the `okf_*` derived tables in `knowledge.sqlite`.
- `recall_sessions(query, k=5)` / `index_sessions(force?)` — semantic recall over past conversations. `session_search` stays the lexical first layer and `session_read` is the exact-browse layer (lists recent sessions or opens a windowed turn slice around a phrase/index, no model call); the semantic layer runs on the same embed/sqlite-vec store, separate `session_*` table family. Opt-in indexing (never automatic), active session excluded, no per-turn injection. Forgettable: deleting a session purges its index rows (`recall.forget_session`), reindex orphan-sweeps gone sessions.
- `workgroup_search(workgroup_id, query, k=5)` / `index_workgroups(workgroup_id?, force?)` — semantic search over hub-owned workgroup transcripts, same store, separate `workgroup_*` family. Hub-owned + profile-local only: no cross-peer/federated search. Decrypts via the existing key-history-aware path; opt-in, search scoped per-workgroup, no auto-injection. Forgettable: removing a workgroup (host RPC or CLI) purges its index (`workgroup_search.forget_workgroup`), reindex orphan-sweeps gone workgroups. ALP wire/crypto untouched.

## Attachments

- `host.chat.send` takes `attachments: [{path, mime?, name?}]`; the engine validates (magic bytes, binary-as-text guard, allowlist: images/PDF/text+source) and builds multimodal content-parts. Allowed text/source incl. `py`/`js`/`ts`/`tsx`/`go`/`rs`/`sh`/`sql`.
- Per-turn only: bytes live in the in-memory message. `session_metadata` is path-free (`{name, mime, size}`), but the engine re-adds a best-effort local `path` to each persisted chat-turn attachment so clients can thumbnail history — the path may be unfetchable cross-client (outside `fetch` roots) or after a staged file's TTL, so it's preview replay, not durable storage. Validated turn attachments also go to a runtime-only ContextVar (`tools/_state`) so tools resolve them.
- Remote clients upload via `host.attachments.stage` (caps + validation), getting a daemon-side path.
- Storage contract: synthesized Markdown lives in the **workspace** (`knowledge/`, source of truth); the derived SQLite index lives in the **profile** (`knowledge.sqlite`). Raw source documents used for ingest are not copied into alpi-managed durable storage.

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
- Profile `.env` loaded via `effective_profile_env`; the daemon does not mutate global `os.environ`.
- Email is multi-account (N accounts, any IMAP/Gmail mix; `email.accounts` in `config.yaml`, id = slug of address). The `email` tool's `account` param selects by address/id; per-account creds from `.env` (`EMAIL__<ID>__PASSWORD`, shared `GMAIL_CLIENT_*`) + `secrets/gmail_tokens/<id>.json` at call time; nothing polls the inbox.

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
