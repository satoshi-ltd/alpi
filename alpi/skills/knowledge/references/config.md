# Configuration answer pack

Use this for `config.yaml`, `.env`, model/provider settings, tools,
gateway, budget, service, and "when does a setting take effect?"

## Locations

- Default profile config: `~/.alpi/config.yaml`
- Named profile config: `~/.alpi/profiles/<name>/config.yaml`
- Static secrets: matching `.env` file in the same profile home.

## Core fields

| Field | Meaning |
|---|---|
| `model` | Primary LiteLLM model string. Empty on fresh setup. |
| `fallback_models` | Stored list of fallback model strings. Do not promise automatic runtime escalation unless the installed version implements it. |
| `workspace` | Default project root for relative file/terminal work. |
| `budget` | Daily/monthly spend limits for paid providers. |
| `providers` | Provider-specific saved choices/endpoints. |
| `tools` | Tool-specific settings such as sandbox, vision model, TTS/STT. |
| `gateway` | Telegram/IMAP/Gmail inbound settings. |
| `schedule` | Scheduler/service settings. |
| `service` | Local daemon toggles and host options. |
| `alp` | ALP peer/workgroup configuration. |
| `host` | Host-plane companion endpoint (`host.tcp_port`, `host.tcp_host`, `host.device_name`). Empty `host.tcp_host` = auto-detect Tailscale then LAN; explicit value advertises a stable host to paired desktop/mobile clients. `host.device_name` sets the pairing label shown in `Devices`. |

## Model examples

OpenRouter:

```yaml
model: openrouter/xiaomi/mimo-v2-pro
```

Anthropic:

```yaml
model: anthropic/claude-sonnet-4.6
```

Ollama endpoint configured under providers:

```yaml
model: local/qwen3.6
providers:
  ollama:
    - name: local
      url: http://localhost:11434
```

## How to change settings

Recommended:

```bash
alpi setup
```

Also valid:

- `/model` inside the TUI for model switching.
- Edit `config.yaml` directly for advanced fields.

## Takes effect when

| Setting | Takes effect |
|---|---|
| `model` | Next turn/session depending on caller. |
| `workspace` | Next tool call after reload. |
| `budget` | Next turn; engine rereads budget. |
| `tools.terminal.sandbox` | Next terminal call. |
| Gateway config | Service restart usually required. |
| Scheduler config/jobs | Scheduler/service reload or restart depending on path. |

## `.env`

Use `.env` for provider keys and static secrets. Skills declare needed
variables with `requires_env`; values stay in `.env` and are only
passed to subprocesses after the skill is opened.

Do not store secret values inside `SKILL.md`, docs, or scripts.

## Terminal approval allowlist

`tools.terminal.approval.allowlist` skips the interactive prompt for entries that match. Two shapes share the list:

- Pattern desc (e.g. `recursive rm`, `sudo`, `git force-push`) → bypass entire severity-category. Persisted by the TUI `Always` button.
- Anything else → command glob, `fnmatch` against trimmed command.

```yaml
tools:
  terminal:
    approval:
      allowlist:
        - recursive rm                       # category
        - sudo apt *                         # glob
        - git reset --hard origin/main       # glob
```

Invariants:

- DANGEROUS classifications (`mkfs`, `dd of=/dev/…`, pipe-to-interpreter, ssh-key reads, system-dir writes, fork bombs) are always blocked — allowlist has no effect.
- Globs do not apply to compound commands (`&&`, `||`, `;`, `|`, newline, backtick, `$( … )`). Falls back to prompt. Category-desc bypass still applies on compound.
- `classify()` returns the worst severity across the entire command, not the first match. `rm -rf build && mkfs.ext4 /dev/sda` → DANGEROUS even with `recursive rm` in allowlist.

## Common questions

- "Where do I set the workspace?" -> `workspace` in config or setup.
- "Why is alpi using the wrong model?" -> check active profile and
  `model` field.
- "Why does service ignore my config edit?" -> restart the profile's
  service.
- "Can work and personal use different models?" -> yes, use profiles.
- "What's the difference between `Devices -> Network` and `Peer TCP listener`?" -> `Devices` configures the host-plane companion endpoint (`host.*`); `Peer TCP listener` configures ALP peer traffic (`link.*`, `workgroup.*`).
