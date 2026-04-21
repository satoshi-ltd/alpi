# Configuration reference

alf's settings live in `~/.alf/config.yaml` (or
`~/.alf/profiles/<name>/config.yaml` for non-default profiles). This
page lists every knob, its default, and what it controls.

## What ships in the YAML

On first install alf only writes the sections you're likely to tweak
— and where defaults are platform-dependent enough to deserve
visibility:

```yaml
model: openrouter/xiaomi/mimo-v2-flash
providers:
  custom: []
mcp:
  servers: {}
gateway:
  telegram:
    show_tool_trace: true
    typing_indicator: true
  email:
    poll_interval: 60
    mark_as_read: true
    show_tool_trace: false
    typing_indicator: false
```

Everything else (tool limits, TUI flags, fallback models, workspace)
falls back to the defaults below at load time. Add a key to the YAML
only when you want to override it.

## How to change settings

Three options, any of them works:

- **Chat**: ask alf. "change max_steps_per_turn to 60", "set the
  accent to Facebook blue". The `config` tool handles it.
- **CLI wizards**: `alf setup` covers model selection, gateway
  credentials, and MCP servers. The scalar knobs below go through
  the `config` tool instead.
- **Edit the YAML**: open `~/.alf/config.yaml` and change values
  manually. Restart whatever surface was affected.

## Reference

### Core

| Key | Default | Type | Takes effect |
|---|---|---|---|
| `model` | `openrouter/xiaomi/mimo-v2-flash` | string | next session |
| `workspace` | `""` (cwd at launch) | string | next session |
| `fallback_models` | `[]` | list of strings | next turn |
| `providers.custom` | `[]` | list of objects — `alf setup` only | next session |

### Tools

| Key | Default | Type | Takes effect |
|---|---|---|---|
| `tools.max_steps_per_turn` | `40` | int | next turn |
| `tools.web_extract.model` | `""` (use main) | string | next turn |
| `tools.terminal.sandbox` | `false` | bool | next turn |
| `tools.terminal.allow_network` | `false` | bool | next turn |

`tools.terminal.sandbox` enables OS-level isolation on shell commands
(macOS `sandbox-exec`, Linux `bubblewrap`). **Experimental** — see
[SECURITY.md](SECURITY.md) for details, platform requirements, and
what breaks when it's on. `allow_network` has no effect unless
`sandbox` is on.

### TUI

| Key | Default | Type | Takes effect |
|---|---|---|---|
| `tui.show_cost` | `true` | bool | next session |
| `tui.show_tokens` | `true` | bool | next session |
| `tui.show_reasoning` | `true` | bool | next session |
| `tui.accent` | `#ff8800` | CSS color (hex / named / rgb) | next session |

`tui.show_reasoning` controls two channels of model-thinking output:

1. **Inter-tool prose** — the dim `» …` line that appears above a
   tool card with whatever text the model emitted between tool
   calls.
2. **Streamed chain-of-thought** — for reasoning models
   (DeepSeek-R1, OpenAI o-series, Claude extended thinking), the
   tail of `reasoning_content` scrolls live inside the
   `thinking…` indicator.

When `false`, both are hidden from the screen. The reasoning is
**still persisted** to the session file (`sessions/*.json`) so that
re-enabling the flag later brings it back on replay, and so that
debug inspection (`cat sessions/<id>.json`) always has the full
context. Gateway surfaces (Telegram, Email) never rendered
reasoning, so this flag has no effect there.

### Gateway — Telegram

| Key | Default | Why |
|---|---|---|
| `gateway.telegram.show_tool_trace` | `true` | Interactive chat; seeing tool calls in real time makes progress legible. |
| `gateway.telegram.typing_indicator` | `true` | Shows "typing…" while alf is working; reassures the user something's happening. |

### Gateway — Email

| Key | Default | Why |
|---|---|---|
| `gateway.email.poll_interval` | `60` (seconds) | IMAP polling cadence. Hermes runs at 15s; 60s keeps CPU/network quiet for personal use. |
| `gateway.email.mark_as_read` | `true` | Processed messages marked `\Seen` so your mail client treats them as read. |
| `gateway.email.show_tool_trace` | `false` | Each trace would be its own email — spam if a turn touches many tools. Only the final reply goes out. |
| `gateway.email.typing_indicator` | `false` | No "typing…" concept over IMAP/SMTP. Kept explicit so the gateway loop doesn't spawn a no-op heartbeat. |

### MCP

| Key | Default | Notes |
|---|---|---|
| `mcp.servers` | `{}` | Map of `<name> → {command, args, env}`. Secrets in `env` use the `env:VAR_NAME` reference. Add via `alf setup → MCPs` — hand-editing is supported but the wizard is easier. |

## Takes-effect cheat sheet

- **next turn** — change is live on the agent's next response.
- **next session** — restart `alf` to pick it up.
- **next gateway restart** — `alf gateway stop && alf gateway start`
  (or reload the service if installed as a daemon).
