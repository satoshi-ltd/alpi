# Configuration answer pack

## Answer directly

- Name the exact config key and profile config path.
- Say whether daemon/service restart is needed.
- Secrets go in profile `.env`, not `config.yaml` or skill files.
- Each profile has its own config and `.env`.

## Locations

- Default profile: `~/.alpi/config.yaml`
- Named profile: `~/.alpi/profiles/<name>/config.yaml`
- Static secrets: matching profile `.env`

## Core fields

| Field | Meaning |
|---|---|
| `model` | Primary LiteLLM model string. |
| `fallback_models` | Availability chain — retried in order when the active model fails before producing output. |
| `tiers` | Optional `fast` / `deep` `{model, effort}` slots for dynamic routing; unconfigured tiers resolve to `model`. |
| `workspace` | Default project root for file/terminal tools. |
| `budget` | Daily spend limit (USD or tokens, mutually exclusive). |
| `providers` | Provider-specific saved endpoints/choices. |
| `tools` | Sandbox, vision, TTS/STT, approvals, denylist, char budget. |
| `runtime` | Provider watchdog/retry settings and daemon asset prefetch mode. |
| `schedule` | Scheduler settings. |
| `alp` | ALP peer/workgroup settings. |
| `network` | Shared accessible address. |
| `host` | Control-plane port, device label, public-bind opt-in. |
| `tui` | TUI cosmetics. |
| `memory` | Reviewer cadence. |
| `model_reasoning.effort` | `"" \| low \| medium \| high` reasoning hint passed alongside `cfg.model`. Default model only; mid-chat overrides and tool sub-models ignore it. |
| `public_bio` | One-line public tag-line broadcast to every workgroup this profile joins (source of truth for `Member.bio`). Empty = no publication. |
| `paused` | Profile-level pause flag, surfaced to desktop / mobile via `host.device_state.profile_summary`. UI-only signal; the daemon does not gate turns on it. |
| `tools.browser.allow_local` | Let the `browser` tool navigate **loopback** only (`127.0.0.1`, `::1`, `localhost`). RFC1918 / CGNAT / Tailscale stay blocked; the exemption is loopback-only (`_guards._is_loopback`). |
| `tools.max_steps_per_turn` | Per-turn tool-call ceiling (default 100) — a runaway-loop backstop, **not** the cost guard (`budget.daily_usd` is). Hitting it triggers one tools-off wrap-up call so the turn still returns a best-effort reply instead of failing. Left at the default, a free/ollama model lifts the ceiling to 1000; an explicit value is always respected. |
| `tools.web_search.max_per_turn` | Per-turn `web_search` ceiling (default 25) — a runaway-loop backstop, not search discipline (the "cap at 3 per question" rule lives in the tool description). Searches are serialized and spaced ~1.5s apart regardless: one `ddgs` call fans out to 5+ upstream engines, so overlapping calls are what tips a shared IP into a rate limit that lasts ~17 minutes. |
| `tools.max_parallel_tool_calls` | Maximum concurrent calls in an all-parallel-safe batch (default 4). Mixed or exclusive batches stay serial. |
| `tools.execution.backend` | Terminal shell world: `local` (default) or `docker`. Docker preserves absolute workspace/profile paths through bind mounts; background jobs are refused because the containers are ephemeral. Dedicated workers remain host-side. |
| `tools.execution.docker_image` | Container image for the Docker execution world (default `python:3.12-slim`). |
| `tools.read_image.model` | Optional model route used by `read_image` and browser screenshot analysis. Empty means the profile model. It does not reroute chat attachments; those stay in the main turn. Configure it under `alpi setup → Routing models` or the Vision model row in the apps. |
| `tools.attachments.max_text_tokens` | Per-attachment extracted-text cap (text files, digital-PDF text, scanned-PDF OCR), in tokens; engine converts to chars at ~4/token. **Default `0` = auto**: half the active model's context window (`litellm.get_model_info`), falling back to 100k when the model is unmapped. A positive value is a fixed override (bound cost, or force more text on a mis-sized model). Per-file byte caps (2 MiB text, 20 MiB PDF/image) only gate acceptance. Not the scan page cap (`SCAN_MAX_PAGES`). |
| `runtime.{first_byte_timeout_s,stream_idle_timeout_s,stream_max_duration_s}` | Provider-stream watchdogs in seconds (`0` disables one): first output, silence between meaningful deltas, and absolute duration of one request. |
| `alp.link_idle_timeout_s` | Silence watchdog for `link.ask` (default 60s; `0` disables). Start/progress frames reset it, so it is not a total turn limit. Takes effect on the next peer call. |
| `alp.link_max_duration_s` | Optional absolute `link.ask` duration cap (default `0` = disabled). Takes effect on the next peer call. |

Removed `service.{schedule,alp,workgroups,host}` keys are ignored because these
daemon capabilities always start. Startup logs and `alpi doctor` warn while the
keys remain. Legacy `service.prefetch` migrates to `runtime.prefetch` on save.

## Model examples

```yaml
model: openrouter/~deepseek/deepseek-v4-flash-latest
```

```yaml
model: local/qwen3.6
providers:
  ollama:
    - name: local
      url: http://localhost:11434
```

## Change paths

- `alpi setup` (recommended): model, email, MCPs, sandbox, voice, peers, workgroups, connections, network, budget, cleanup (including run journals older than 30 days), and daemon lifecycle.
- `/model` inside the TUI.
- Direct `config.yaml` edit for advanced/cosmetic fields.
- Desktop/mobile settings through `host.*` where available.

## Takes effect when

| Setting | Takes effect |
|---|---|
| `model` | Next turn/session depending on caller. |
| `workspace` | Next tool call after reload. |
| `budget` | Next turn. |
| `tools.terminal.sandbox` | Next terminal call. |
| `tools.deny` | Next turn (re-read from disk per turn, same as `budget`). |
| `tools.max_steps_per_turn` | Next turn. |
| `tui.*` | Next session (`tui.auto_resume`: next launch). |
| Email creds (`.env` `EMAIL__<ID>__PASSWORD` / shared `GMAIL_CLIENT_*`, `secrets/gmail_tokens/<id>.json`) | Next `email` tool call (read at call time, no restart). |
| Scheduler config/jobs | Scheduler reload or daemon restart depending on path. |
| `network.host`, `host.tcp_port`, `alp.tcp_port` | Daemon restart (listeners bind at boot). |
| `host.device_name` | Next pairing/status (read fresh per call, no restart). |
| `host.endpoints` | Next pairing code (read fresh per call, no restart). |

## TTS / voice

Config keys: `tools.tts.voice` (Edge TTS id), `tools.tts.rate`, `tools.tts.pitch` (prosody, config-only defaults), `tools.tts.auto_read` (bool; set via `host.voice.set_auto_read`).

The `tts` tool only synthesizes and returns a cached MP3 path — the daemon never plays audio. Desktop/mobile play on demand from a per-message button, and when `tools.tts.auto_read` is on they auto-play each agent reply (synthesizing via `host.voice.preview`); your own messages are never read. Workgroups carry an analogous hub-local `auto_read` flag in the workgroup meta (`host.workgroup.update`), not replicated to members. To send synthesized audio to a third party, attach the cached MP3 to an `email` send.

## STT

`tools.stt.{model,language}` drive the `stt` tool (faster-whisper on CPU) for on-demand transcription of audio attachments.

## `.env`

Profile `.env` holds provider keys and static secrets. Skills declare needs with `requires_env`; runtime credentials belong in a skill's `secrets/` directory.

The daemon supervises many profiles in one process and does not mutate global `os.environ`. Profile-scoped lookups go through `effective_profile_env(home)`: process env overlaid with the profile's `.env`. The `email` tool reads creds via this lookup at call time, so credential edits take effect on the next call with no restart.

Email is multi-account: a profile holds N accounts (any mix of IMAP and Gmail), declared under `email.accounts` in `config.yaml` (non-secret shape only; id = slug of the address). Per-account secrets in `.env`: IMAP `EMAIL__<ID>__PASSWORD`; Gmail OAuth client `GMAIL_CLIENT_ID` / `GMAIL_CLIENT_SECRET` shared across all Gmail accounts, per-account token at `secrets/gmail_tokens/<id>.json`. Manage via `alpi setup → Email` or the apps' Email section; `alpi email probe <id>` / `alpi email remove <id>` operate by id. The `email` tool's `account` param selects by address or id.

## Memory knobs

`memory.review_interval` defaults to `0` (off). `N > 0` enables the daemon-thread reviewer every N user turns (append-only via `memory(action="add")`).

These are constants, not config knobs: memory char limits, low-confidence expiry, dedup threshold, and compaction ratios.

## Terminal approval allowlist

`tools.terminal.approval.allowlist` skips prompts for approved command globs or severity-category descriptions.

```yaml
tools:
  terminal:
    approval:
      allowlist:
        - recursive rm
        - sudo apt *
        - git reset --hard origin/main
```

Dangerous classifications are always blocked. Globs do not apply to compound commands with pipes, `&&`, `;`, backticks, or command substitution.

## Tool denylist

`tools.deny` is a per-profile list of tool names hidden from the LLM's schema and refused by the executor as defence in depth. Used to tighten profiles exposed to less-trusted input (e.g. a librarian profile reachable via `link.ask`). Denying `alpi_knowledge` also drops the self-knowledge rule from the system prompt.

```yaml
tools:
  deny:
    - write_file
    - edit_file
    - terminal
    - email
    - schedule
    - delegate
```

Use the canonical registered name. `knowledge` is the user/workspace OKF wiki;
`alpi_knowledge` is packaged docs about alpi itself. Unknown names are no-ops
(typos are harmless). A bare string (`deny: terminal`) collapses to `[]`, not a
per-char iteration.

## Relay (read-only front door to one peer)

`relay.peer` makes a profile a pure conduit to one pinned peer. The engine then offers only the `peer` tool and hard-gates every turn: it must consult that exact peer via `link.ask` before answering; a wrong peer id is rejected pre-execute, an empty reply doesn't count, and a turn that ends (or hits the step/time limit) with no valid reply fails closed with a fixed message instead of answering from the model's own knowledge. The peer's reply is surfaced verbatim. Just pin the peer in `peers.yaml` with `link.ask` — no separate `tools.deny` needed.

```yaml
relay:
  peer: agora
```

This locks down the relay side only. It does NOT make the target immutable — an inbound `link.ask` runs a full turn on the target with the target's own tools. Keep the source unwritable via the target profile's own tool denies, and restrict which paired devices can address it with a member connection's `profile_scope`. The `default` host socket serves sibling profiles, and admin/local access ignore scoping.

## Network (shared accessible address)

`network.host` (default `""`) is the shared bind/ALP address. Empty = auto-detect a reachable private address. A private IP literal also produces the automatic direct `ws://` client route. A hostname remains usable for ALP but requires an explicit certificate-validated `wss://` entry in `host.endpoints` for desktop/mobile; it never produces plaintext client access. A public IP additionally needs `host.allow_public_bind: true`; that gate applies to both planes, so without it neither binds TCP.

## Common questions

- Workspace? -> `workspace`.
- Wrong model? -> active profile + `model`.
- Listener config edit ignored? -> restart the daemon.
- Docker host port edit ignored? -> `ALPI_HOST_TCP_PORT` overrides `host.tcp_port`; change the environment value and matching 1:1 port mapping, then recreate the container. Several Alpi containers on one host use distinct effective ports.
- Different work/personal models? -> use separate profiles.
- One address, two ports? -> `network.host` is the shared accessible address (empty = auto-detect a private address); `host.tcp_port` is device pairing, `alp.tcp_port` is the ALP peer listener. The `default` profile auto-exposes ALP TCP when a reachable address exists; named profiles are Unix-only unless they set their own unique `alp.tcp_port`. Unix sockets always work locally.
- WS or WSS route? -> `ws://` requires a private IP literal. Any hostname requires certificate-validated `wss://`; an unsafe automatic WS fallback is not advertised.
- Private and public routes? -> the private WS route is derived from the current address and `host.tcp_port`. `host.endpoints` normally stores the optional public WSS route; when it has no explicit WS entry, resolution appends the safe private route. Removing public WSS does not disable private access.
- Docker WSS custom port? -> set `ALPI_HOST_TCP_PORT` once. The supplied compose files use it for the daemon listener, direct private mapping and Caddy upstream; the WSS URL still omits the port because it uses 443. The WSS overlay removes direct host mappings.
- Advertise vs bind? -> `network.host` is the *advertised* address clients and peers dial; the *bind* is derived from it, not used verbatim. A private IP binds itself; a hostname or an opted-in public IP binds `0.0.0.0`; a public IP without `host.allow_public_bind` refuses to bind (Unix-only); docker always binds `0.0.0.0`. `host.allow_public_bind` gates the public case for both planes (the address is shared).
- WebSocket limits? -> daemon-wide `ALPI_HOST_WS_MAX_CONNECTIONS`, `ALPI_HOST_WS_MAX_CONNECTIONS_PER_DEVICE`, `ALPI_HOST_WS_MAX_RPCS_PER_DEVICE`, `ALPI_HOST_WS_AUTH_TIMEOUT`, `ALPI_HOST_WS_AUTH_RECHECK`, `ALPI_HOST_WS_CLOSE_TIMEOUT`, and `ALPI_HOST_WS_REVOCATION_RETRY` override the safe defaults and require restart. There is no global handshake-per-minute budget, but the global concurrent-socket cap is checked pre-auth and an anonymous socket occupies a slot until the auth timeout. Per-IP limits belong at the trusted public edge.

## MCP servers

`mcp.servers`: map `<name> -> {command, args, env}`. Each is a **local stdio subprocess** the daemon spawns; alpi has NO native HTTP/SSE MCP transport. `env` values of the form `env:VAR` resolve from the profile `.env` at spawn and become the subprocess environment — the secret stays in `.env`, never in `config.yaml` or in `args`. Add via `alpi setup -> MCPs`. Takes effect on daemon restart / profile re-bootstrap (the MCP subprocess re-spawns).

- **stdio + env secret** (server reads creds from env): `command: npx`, `args: [-y, <pkg>]`, `env: {BITBUCKET_URL: env:BITBUCKET_URL, BITBUCKET_PASSWORD: env:BITBUCKET_PASSWORD, ...}`.
- **remote HTTP + header secret**: alpi is stdio-only, so bridge with `mcp-remote`. `env:VAR` only reaches the subprocess env, NOT `args`, so a header secret cannot be referenced in `--header` directly. Use mcp-remote's own `${VAR}` header expansion: `args: [-y, mcp-remote@latest, <url>, --transport, http-only, --header, 'x-mcp-secret: ${MCP_SECRET}']` + `env: {MCP_SECRET: env:MCP_SECRET}`. Do NOT hardcode the secret in the header and do NOT wrap in `sh -c` — mcp-remote expands `${VAR}` itself.

## Related topics

- Install/update path: `install`
- Model selection: `models`
- Daemon lifecycle: `operations`
- Host-plane pairing: `deployments`
