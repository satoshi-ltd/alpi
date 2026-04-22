# Configuration reference

alf's settings live in `~/.alpi/config.yaml` (or
`~/.alpi/profiles/<name>/config.yaml` for non-default profiles). This
page lists every knob, its default, and what it controls.

## What ships in the YAML

On first install alf only writes the sections you're likely to tweak
— and where defaults are platform-dependent enough to deserve
visibility:

```yaml
model: openrouter/xiaomi/mimo-v2-flash
providers:
  ollama: []
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

Two options:

- **CLI wizards**: `alpi setup` covers model selection, gateway
  credentials, MCP servers, and sandbox posture — the settings that
  benefit from structured flows or secret handling.
- **Edit the YAML**: open `~/.alpi/config.yaml` (or
  `~/.alpi/profiles/<name>/config.yaml` for non-default profiles)
  and change values manually. Restart whatever surface was affected.
  Cosmetic knobs (`tui.*`, `tools.max_steps_per_turn`,
  `gateway.email.poll_interval`, `fallback_models`) live here.

## Reference

### Core

| Key | Default | Type | Takes effect |
|---|---|---|---|
| `model` | `openrouter/xiaomi/mimo-v2-flash` | string | next session |
| `workspace` | `""` (cwd at launch) | string | next session |
| `fallback_models` | `[]` | list of strings | next turn |
| `providers.ollama` | `[]` | list of `{name, url}` — one per Ollama server | next session |
| `providers.openrouter.models` | `[]` | list of OpenRouter model ids the user has picked | next session |

### Tools

| Key | Default | Type | Takes effect |
|---|---|---|---|
| `tools.max_steps_per_turn` | `40` | int | next turn |
| `tools.web_extract.model` | `""` (use main) | string | next turn |
| `tools.read_image.model` | `""` (use main) | string | next turn |
| `tools.read_image.auto_resize` | `true` | bool | next turn |
| `tools.read_image.max_edge` | `1568` | int (pixels; `0` disables) | next turn |
| `tools.terminal.sandbox` | `false` | bool | next turn |
| `tools.terminal.allow_network` | `false` | bool | next turn |
| `tools.browser.vision` | `false` | bool | next turn |
| `tools.research.quick_steps` | `8` | int | next turn |
| `tools.research.normal_steps` | `15` | int | next turn |
| `tools.research.deep_steps` | `30` | int | next turn |
| `tools.budget.per_result_chars` | `100_000` | int (-1 = unlimited) | next turn |
| `tools.<name>.max_result_chars` | `—` (unset) | int (-1 = unlimited) | next turn |

`tools.budget.per_result_chars` caps the size of any tool output the LLM
sees in-context, with a `… [N chars elided by tool budget]` suffix when
hit. Prevents a single `read_file` on a 5 MB log from blowing up a turn.
Per-tool overrides via `tools.<name>.max_result_chars` — set `-1` on
`read_file` if you want the LLM to get the whole source deliberately,
or lower a chatty tool's cap.

Precedence: `tools.<name>.max_result_chars` (if set) → `tools.budget.per_result_chars` → hardcoded `100_000`.

Not implemented (tracked, not planned): per-turn aggregate cap and inline preview. Hermes has both (200K aggregate with spill-to-disk, 1.5K preview in the tool card). Ship if and when a real turn actually burns through several large tool results.

`tools.terminal.sandbox` enables OS-level isolation on shell commands
(macOS `sandbox-exec`, Linux `bubblewrap`). Toggle via `alf setup →
Sandbox`, or directly in YAML. The TUI top bar shows the current
state (`sandbox on` / `off`). Most useful on profiles that run
unattended (gateway, schedule, sub-agents) — see
[SECURITY.md](SECURITY.md) for the recommended pattern + platform
requirements. `allow_network` has no effect unless `sandbox` is on.

`tools.browser.vision` lets the `browser(screenshot, question=…)` action auto-chain the screenshot into the vision model (`tools.read_image.model` or the active main model) and return the answer instead of the file path. When `false` (default), `screenshot` always returns the path and a hint pointing at `read_image` so the LLM can decide whether to pay for vision per call. Useful to turn on in an exploratory profile; keep off in watchdog/gateway profiles so the agent doesn't burn vision tokens silently.

`tools.read_image.auto_resize` downscales any image whose longer edge exceeds `max_edge` (default 1568 px, matches Anthropic's recommendation) before base64-encoding to the model. Vision-model cost scales with resolution — a 4K screenshot costs ~9× more tokens than its 1568-px version for the same content. Aspect ratio is preserved, PNG-with-alpha stays PNG, everything else rounds-trips through JPEG q=85. SVG (vector) is skipped. Set `max_edge: 0` to disable entirely, or bump it if you work with detail-heavy images (charts, fine text) where the default is too aggressive.

`tools.research.{quick,normal,deep}_steps` control the iteration
budget of the `research` sub-agent. The agent picks the depth tier
based on the user's intent (`quick` for single-answer lookups,
`normal` for comparative research, `deep` for exhaustive surveys);
the integer per tier is your knob. Bumping `deep_steps` to 60 if
you want even deeper investigations is fine; dropping `quick_steps`
to 3 if you mainly use a tier-A model and want minimum latency on
trivial questions is also fine. Default tiers are tuned for
mimo-class models on read-only research.

### TUI

| Key | Default | Type | Takes effect |
|---|---|---|---|
| `tui.show_cost` | `true` | bool | next session |
| `tui.show_tokens` | `true` | bool | next session |
| `tui.show_reasoning` | `true` | bool | next session |
| `tui.accent` | `#ff8800` | CSS color (hex / named / rgb) | next session |
| `tui.theme` | `dark` | `dark` \| `light` | next session |

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

### Ollama

Ollama is a first-class provider. One entry per server — local, remote, different ports — each with its own user-chosen `name` that becomes the model prefix (`home/gemma4:e4b`, `gpu-box/qwen3:14b`). On every request against an Ollama server, `num_ctx` is auto-resolved from `/api/show` and injected so the model sees the full prompt instead of being truncated to Ollama's 2K default.

```yaml
providers:
  ollama:
    - name: home
      url: http://localhost:11434
    - name: gpu-box
      url: http://192.168.1.50:11434
```

Add via `alpi setup → Model → Add Ollama`. Remove via `alpi setup → Model → Remove keys`.

### MCP

| Key | Default | Notes |
|---|---|---|
| `mcp.servers` | `{}` | Map of `<name> → {command, args, env}`. Secrets in `env` use the `env:VAR_NAME` reference. Add via `alpi setup → MCPs` — hand-editing is supported but the wizard is easier. |

## Takes-effect cheat sheet

- **next turn** — change is live on the agent's next response.
- **next session** — restart `alf` to pick it up.
- **next gateway restart** — `alpi gateway stop && alf gateway start`
  (or reload the service if installed as a daemon).
