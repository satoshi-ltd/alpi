# Configuration answer pack

Use this for `config.yaml`, `.env`, model/provider settings, tools,
gateways, budget, service, and "when does this setting take effect?"

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
| `budget` | Daily/monthly spend limits. |
| `providers` | Provider-specific saved endpoints/choices. |
| `tools` | Tool settings: sandbox, vision, TTS/STT, approvals. |
| `gateway` | Telegram, Matrix, IMAP, Gmail inbound settings. |
| `schedule` | Scheduler/service settings. |
| `alp` | ALP peer/workgroup settings. |
| `host` | Desktop/mobile companion endpoint and device label. |

## Model examples

```yaml
model: openrouter/xiaomi/mimo-v2-pro
```

```yaml
model: anthropic/claude-sonnet-4.6
```

```yaml
model: local/qwen3.6
providers:
  ollama:
    - name: local
      url: http://localhost:11434
```

## Change paths

Recommended:

```bash
alpi setup
```

Also valid:

- `/model` inside the TUI.
- Direct `config.yaml` edit for advanced fields.
- Desktop/mobile settings through `host.*` where available.

## Takes effect when

| Setting | Takes effect |
|---|---|
| `model` | Next turn/session depending on caller. |
| `workspace` | Next tool call after reload. |
| `budget` | Next turn. |
| `tools.terminal.sandbox` | Next terminal call. |
| Gateway config | Usually daemon/gateway restart. |
| Scheduler config/jobs | Scheduler reload or daemon restart depending on path. |
| `host.tcp_host`, `host.device_name` | Daemon restart. |

## TTS / voice

Config keys:

- `tools.tts.voice`
- `tools.tts.rate`
- `tools.tts.pitch`

The `tts` tool only synthesizes and returns a cached MP3 path. The
daemon does not play audio, there is no `tools.tts.autoplay`, and
there is no `host.voice.autoplay` host verb. Desktop/mobile playback is
an explicit per-message action; external chats receive audio only when
the agent chains `send_message(attachment=<mp3 path>)`.

## `.env`

Use profile `.env` for provider keys and static secrets. Skills declare
needed variables with `requires_env`; runtime credentials belong in a
skill's `secrets/` directory.

The daemon supervises many profiles in one process and does not mutate
global `os.environ`. Profile-scoped lookups go through
`effective_profile_env(home)`: process env overlaid with the profile's
`.env`. Gateway adapters snapshot env at construction, so credential
edits normally need restart.

## Memory knobs

`memory.review_interval` defaults to `0` (off). `N > 0` enables the
daemon-thread reviewer every N user turns.

These are constants, not config knobs: memory char limits, low-confidence
expiry, dedup threshold, and compaction ratios.

## Terminal approval allowlist

`tools.terminal.approval.allowlist` skips prompts for approved command
globs or severity-category descriptions.

```yaml
tools:
  terminal:
    approval:
      allowlist:
        - recursive rm
        - sudo apt *
        - git reset --hard origin/main
```

Dangerous classifications are always blocked. Globs do not apply to
compound commands with pipes, `&&`, `;`, backticks, or command
substitution.

## Common questions

- Workspace? -> `workspace`.
- Wrong model? -> active profile + `model`.
- Config edit ignored? -> restart the relevant daemon/service.
- Different work/personal models? -> use separate profiles.
- Devices vs Peer TCP? -> `host.*` is app pairing; ALP peer listener is
  for profile-to-profile traffic.

## Related topics

- Install/update path: `install`
- Model selection: `models`
- Daemon lifecycle: `operations`
- Host-plane pairing: `deployments`
