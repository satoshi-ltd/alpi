# Configuration reference

alpi's settings live in `~/.alpi/config.yaml` (or
`~/.alpi/profiles/<name>/config.yaml` for non-default profiles). This
page lists every knob, its default, and what it controls.

## What ships in the YAML

On first install alpi only writes the sections you're likely to tweak
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
  imap:
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
  `gateway.imap.poll_interval`, `fallback_models`) live here.

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
| `tools.tts.voice` | `"en-US-AriaNeural"` | Edge TTS voice id | next turn |
| `tools.tts.autoplay` | `true` | bool (plays audio after synthesis) | next turn |
| `tools.tts.rate` | `""` | string (`"+10%"`, `"-20%"`) — speed | next turn |
| `tools.tts.pitch` | `""` | string (`"+5Hz"`, `"-10Hz"`) — pitch | next turn |
| `tools.stt.model` | `"base"` | `tiny` \| `base` \| `small` \| `medium` \| `large-v3` | next turn |
| `tools.stt.language` | `""` (auto) | ISO code (`en`, `es`, ...) | next turn |
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
(macOS `sandbox-exec`, Linux `bubblewrap`). Toggle via `alpi setup →
Sandbox`, or directly in YAML. The TUI top bar shows the current
state (`sandbox on` / `off`). Most useful on profiles that run
unattended (gateway, schedule, sub-agents) — see
[SECURITY.md](SECURITY.md) for the recommended pattern + platform
requirements.

`allow_network` has no effect unless `sandbox` is on. When sandbox is
on and `allow_network=false`, the flag blocks ALL agent-initiated
network:

- The `terminal` subprocess is denied sockets (sandbox-exec / bwrap).
- Python-native tools (`web_fetch`, `web_search`, `web_extract`,
  `browser`, `tts`, `send_message`, `email`, `read_image` on URLs)
  refuse with a clear error.
- The LLM call itself (litellm) is exempt — it's the agent's brain,
  not an exfiltration vector. The gateway inbound listener is also
  exempt (receiving is not exfiltrating).

The TUI top bar shows `offline` instead of `sandbox` when network is
locked, so unattended profiles can be audited at a glance.

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

`tools.tts.voice` selects the Edge TTS voice used by the `tts` tool. Any Microsoft Neural voice id is valid (`es-ES-AlvaroNeural`, `en-US-AriaNeural`, `fr-FR-DeniseNeural`, ...). Output is an MP3 cached under `~/.alpi/cache/tts/<hash>.mp3` — same text + voice reuses the cached file. Edge TTS runs against a free Microsoft endpoint (no API key), so there's no per-call cost. To use a different voice per call the agent can pass `voice=...` directly without touching config. `alpi setup → Voice` gives you a curated shortlist (10 common-language voices) plus a "custom" entry to type any voice id, and toggles autoplay in one place.

`tools.tts.autoplay` (default `true`) controls whether the generated MP3 plays through the system speakers immediately after synthesis. Uses `afplay` on macOS, `paplay`/`aplay`/`ffplay` on Linux (first one found), and PowerShell `Media.SoundPlayer` on Windows. Headless servers with no audio device: playback fails silently, the tool still returns the file path. Gateway processes: leave off or accept that the daemon machine plays sound — there's no per-surface override for now. The agent can also pass `play: false` per call when it just wants the file.

`rate` and `pitch` are config-only (not per-call args) — persistent prosody defaults. Leave empty for neutral. Text is capped at 1000 chars (~1 minute); longer input is rejected. Output format is auto-picked: MP3 in TUI, OGG (Opus) on gateway surfaces for Telegram voice-note compatibility. OGG requires `ffmpeg`.

`tools.stt.{model,language}` control the `stt` tool backed by faster-whisper running on CPU. First call downloads the model weights (~40 MB for `tiny`, ~150 MB for `base`, ~500 MB for `small`, ~1.5 GB for `medium`, ~3 GB for `large-v3`) into `~/.cache/huggingface/` and keeps them forever. Pick the smallest model that meets your accuracy bar — `base` is the sweet spot for spoken messages/voice notes; `small` or above for podcasts/meetings. `language` defaults to `""` (auto-detect); set to an ISO code (`en`, `es`, `fr`, ...) only when auto-detect fails on short clips.

The Telegram gateway auto-transcribes inbound voice notes and audio files through the same `stt` pipeline: when a user sends a voice message, the gateway downloads it via `getFile`, caches under `~/.alpi/cache/inbound/`, runs `stt`, and feeds the transcript to the agent as text (`[voice note] <transcription>`). The agent sees a normal text turn — nothing surface-specific to handle.

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
| `gateway.telegram.typing_indicator` | `true` | Shows "typing…" while alpi is working; reassures the user something's happening. |

### Gateway — IMAP

| Key | Default | Why |
|---|---|---|
| `gateway.imap.poll_interval` | `60` (seconds) | IMAP polling cadence. Hermes runs at 15s; 60s keeps CPU/network quiet for personal use. |
| `gateway.imap.mark_as_read` | `true` | Processed messages marked `\Seen` so your mail client treats them as read. |
| `gateway.imap.show_tool_trace` | `false` | Each trace would be its own email — spam if a turn touches many tools. Only the final reply goes out. |
| `gateway.imap.typing_indicator` | `false` | No "typing…" concept over IMAP/SMTP. Kept explicit so the gateway loop doesn't spawn a no-op heartbeat. |

### Gateway — Gmail

Same knobs as IMAP, different backend. Polling uses Gmail's `users.history.list` with the last-seen `historyId` so we only fetch deltas (cheaper than rescanning INBOX). Credentials live in `~/.alpi/<profile>/gmail_token.json` after the one-off OAuth consent via `alpi setup → Gateways → Gmail`.

| Key | Default | Why |
|---|---|---|
| `gateway.gmail.poll_interval` | `60` (seconds) | Same rationale as IMAP. |
| `gateway.gmail.mark_as_read` | `true` | Removes the `UNREAD` label on processed messages. |
| `gateway.gmail.show_tool_trace` | `false` | Same reason as IMAP. |
| `gateway.gmail.typing_indicator` | `false` | Same reason as IMAP. |

Configure both if you want: `imap` polls your primary mailbox via password, `gmail` polls another account via OAuth, each with its own allowlist (`IMAP_ALLOWED_SENDERS` vs `GMAIL_ALLOWED_SENDERS`).

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
- **next session** — restart `alpi` to pick it up.
- **next gateway restart** — `alpi gateway stop && alpi gateway start`
  (or reload the service if installed as a daemon).
