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
| `fallback_models` | Stored fallback model strings. |
| `workspace` | Default project root for file/terminal tools. |
| `budget` | Daily spend limit (USD or tokens, mutually exclusive). |
| `providers` | Provider-specific saved endpoints/choices. |
| `tools` | Sandbox, vision, TTS/STT, approvals, denylist, char budget. |
| `gateway` | Telegram, Matrix, IMAP, Gmail inbound. |
| `service` | Per-profile daemon subsystem toggles. |
| `schedule` | Scheduler settings. |
| `alp` | ALP peer/workgroup settings. |
| `network` | Shared accessible address. |
| `host` | Control-plane port, device label, public-bind opt-in. |
| `tui` | TUI cosmetics. |
| `memory` | Reviewer cadence. |

## Model examples

```yaml
model: openrouter/xiaomi/mimo-v2-pro
```

```yaml
model: local/qwen3.6
providers:
  ollama:
    - name: local
      url: http://localhost:11434
```

## Change paths

- `alpi setup` (recommended): model, gateways, MCPs, sandbox, voice, peers, workgroups, devices, budget, cleanup, daemon/subsystem lifecycle.
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
| `tui.*` | Next session (`tui.auto_resume`: next launch). |
| `service.*` | Next `alpi daemon restart`. |
| Gateway config | Usually daemon/gateway restart. |
| Scheduler config/jobs | Scheduler reload or daemon restart depending on path. |
| `network.host`, `host.tcp_port`, `alp.tcp_port` | Daemon restart (listeners bind at boot). |
| `host.device_name` | Next pairing/status (read fresh per call, no restart). |

## TTS / voice

Config keys: `tools.tts.voice` (Edge TTS id), `tools.tts.rate`, `tools.tts.pitch` (prosody, config-only defaults), `tools.tts.auto_read` (bool; set via `host.voice.set_auto_read`).

The `tts` tool only synthesizes and returns a cached MP3 path — the daemon never plays audio. Desktop/mobile play on demand from a per-message button, and when `tools.tts.auto_read` is on they auto-play each agent reply (synthesizing via `host.voice.preview`); your own messages are never read. Workgroups carry an analogous hub-local `auto_read` flag in the workgroup meta (`host.workgroup.update`), not replicated to members. External chats receive audio only when the agent chains `send_message(attachment=<mp3 path>)`.

## STT

`tools.stt.{model,language}` drive the `stt` tool (faster-whisper on CPU). The Telegram gateway auto-transcribes inbound voice/audio through it and feeds the agent `[voice note] <transcription>` as a normal text turn.

## `.env`

Profile `.env` holds provider keys and static secrets. Skills declare needs with `requires_env`; runtime credentials belong in a skill's `secrets/` directory.

The daemon supervises many profiles in one process and does not mutate global `os.environ`. Profile-scoped lookups go through `effective_profile_env(home)`: process env overlaid with the profile's `.env`. Gateway adapters snapshot env at construction, so credential edits normally need restart.

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
    - send_message
    - schedule
    - delegate
```

Use the canonical registered name — `alpi_knowledge`, not `knowledge`; `search_workspace`, not `workspace_search`. Unknown names are no-ops (typos are harmless). A bare string (`deny: terminal`) collapses to `[]`, not a per-char iteration.

## Network (shared accessible address)

`network.host` (default `""`) is the address other machines and your devices reach this profile at. Empty = auto-detect (Tailscale first, then private LAN). Any reachable host works: Tailscale/WireGuard/VPN address, private hostname/MagicDNS name, LAN IP, `0.0.0.0`, or public IP. A public IP additionally needs `host.allow_public_bind: true`; that gate applies to the shared bind used by both planes (host plane + ALP listener), so without it neither binds TCP. One address shared by every listener, each on its own port.

## Common questions

- Workspace? -> `workspace`.
- Wrong model? -> active profile + `model`.
- Config edit ignored? -> restart the relevant daemon/service.
- Different work/personal models? -> use separate profiles.
- One address, two ports? -> `network.host` is the shared accessible address (empty = auto-detect Tailscale->LAN); `host.tcp_port` is device pairing, `alp.tcp_port` is the ALP peer listener. The `default` profile auto-exposes ALP TCP when a reachable address exists; named profiles are Unix-only unless they set their own unique `alp.tcp_port`. Unix sockets always work locally.
- Advertise vs bind? -> `network.host` is the *advertised* address clients and peers dial; the *bind* is derived from it, not used verbatim. A private/Tailscale IP binds itself; a hostname or an opted-in public IP binds `0.0.0.0`; a public IP without `host.allow_public_bind` refuses to bind (Unix-only); docker always binds `0.0.0.0`. `host.allow_public_bind` gates the public case for both planes (the address is shared).

## Related topics

- Install/update path: `install`
- Model selection: `models`
- Daemon lifecycle: `operations`
- Host-plane pairing: `deployments`
