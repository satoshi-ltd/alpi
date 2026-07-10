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
| `service` | Per-profile daemon subsystem toggles. |
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
| `tools.attachments.max_text_tokens` | Per-attachment extracted-text cap (text files, digital-PDF text, scanned-PDF OCR), in tokens; engine converts to chars at ~4/token. **Default `0` = auto**: half the active model's context window (`litellm.get_model_info`), falling back to 100k when the model is unmapped. A positive value is a fixed override (bound cost, or force more text on a mis-sized model). Per-file byte caps (2 MiB text, 20 MiB PDF/image) only gate acceptance. Not the scan page cap (`SCAN_MAX_PAGES`). |

## Model examples

```yaml
model: openrouter/owl-alpha
```

```yaml
model: local/qwen3.6
providers:
  ollama:
    - name: local
      url: http://localhost:11434
```

## Change paths

- `alpi setup` (recommended): model, email, MCPs, sandbox, voice, peers, workgroups, devices, budget, cleanup, daemon/subsystem lifecycle.
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
| `service.*` | Next `alpi daemon restart`. |
| Email creds (`.env` `EMAIL__<ID>__PASSWORD` / shared `GMAIL_CLIENT_*`, `secrets/gmail_tokens/<id>.json`) | Next `email` tool call (read at call time, no restart). |
| Scheduler config/jobs | Scheduler reload or daemon restart depending on path. |
| `network.host`, `host.tcp_port`, `alp.tcp_port` | Daemon restart (listeners bind at boot). |
| `host.device_name` | Next pairing/status (read fresh per call, no restart). |

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

## Network (shared accessible address)

`network.host` (default `""`) is the address other machines and your devices reach this profile at. Empty = auto-detect (Tailscale first, then private LAN). Any reachable host works: Tailscale/WireGuard/VPN address, private hostname/MagicDNS name, LAN IP, `0.0.0.0`, or public IP. A public IP additionally needs `host.allow_public_bind: true`; that gate applies to the shared bind used by both planes (host plane + ALP listener), so without it neither binds TCP. One address shared by every listener, each on its own port.

## Common questions

- Workspace? -> `workspace`.
- Wrong model? -> active profile + `model`.
- Config edit ignored? -> restart the relevant daemon/service.
- Different work/personal models? -> use separate profiles.
- One address, two ports? -> `network.host` is the shared accessible address (empty = auto-detect Tailscale->LAN); `host.tcp_port` is device pairing, `alp.tcp_port` is the ALP peer listener. The `default` profile auto-exposes ALP TCP when a reachable address exists; named profiles are Unix-only unless they set their own unique `alp.tcp_port`. Unix sockets always work locally.
- Advertise vs bind? -> `network.host` is the *advertised* address clients and peers dial; the *bind* is derived from it, not used verbatim. A private/Tailscale IP binds itself; a hostname or an opted-in public IP binds `0.0.0.0`; a public IP without `host.allow_public_bind` refuses to bind (Unix-only); docker always binds `0.0.0.0`. `host.allow_public_bind` gates the public case for both planes (the address is shared).

## MCP servers

`mcp.servers`: map `<name> -> {command, args, env}`. Each is a **local stdio subprocess** the daemon spawns; alpi has NO native HTTP/SSE MCP transport. `env` values of the form `env:VAR` resolve from the profile `.env` at spawn and become the subprocess environment — the secret stays in `.env`, never in `config.yaml` or in `args`. Add via `alpi setup -> MCPs`. Takes effect on daemon restart / profile re-bootstrap (the MCP subprocess re-spawns).

- **stdio + env secret** (server reads creds from env): `command: npx`, `args: [-y, <pkg>]`, `env: {BITBUCKET_URL: env:BITBUCKET_URL, BITBUCKET_PASSWORD: env:BITBUCKET_PASSWORD, ...}`.
- **remote HTTP + header secret**: alpi is stdio-only, so bridge with `mcp-remote`. `env:VAR` only reaches the subprocess env, NOT `args`, so a header secret cannot be referenced in `--header` directly. Use mcp-remote's own `${VAR}` header expansion: `args: [-y, mcp-remote@latest, <url>, --transport, http-only, --header, 'x-mcp-secret: ${MCP_SECRET}']` + `env: {MCP_SECRET: env:MCP_SECRET}`. Do NOT hardcode the secret in the header and do NOT wrap in `sh -c` — mcp-remote expands `${VAR}` itself.

## Related topics

- Install/update path: `install`
- Model selection: `models`
- Daemon lifecycle: `operations`
- Host-plane pairing: `deployments`
