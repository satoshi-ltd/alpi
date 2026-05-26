# Configuration reference

alpi's settings live in `~/.alpi/config.yaml` (or
`~/.alpi/profiles/<name>/config.yaml` for non-default profiles). This
page lists every knob, its default, and what it controls.

## What ships in the YAML

On first install alpi only writes the sections you're likely to tweak
— and where defaults are platform-dependent enough to deserve
visibility:

```yaml
model: ""                          # empty on a fresh scaffold; pick via `alpi setup → Model` (see docs/MODELS.md)
providers:
  ollama: []
mcp:
  servers: {}
gateway:
  telegram:
    show_tool_trace: true
  matrix:
    show_tool_trace: true
  imap:
    poll_interval: 60
    mark_as_read: true
```

Everything else (tool limits, TUI flags, fallback models, workspace)
falls back to the defaults below at load time. Add a key to the YAML
only when you want to override it.

## How to change settings

Three options:

- **CLI wizards**: `alpi setup` covers model selection, gateway
  credentials, MCP servers, sandbox posture, voice, peers,
  workgroups, disk cleanup, and the alpi daemon's lifecycle.
  `alpi setup → Cleanup` inspects the profile's heavy dirs (audio
  cache, old sessions, schedule output) and the RAG store's SQLite
  freelist (VACUUM-not-unlink), with one-shot confirmation per
  category. `alpi setup → Services` exposes two rows:
  **Daemon** (default profile only — install / uninstall / start /
  stop / restart of the per-machine launchd plist or systemd-user
  unit) and **Subsystems** (per-profile toggles for gateway /
  scheduler / ALP / workgroups / host, plus the inter-machine TCP
  port for ALP). The first `alpi setup` auto-installs the daemon,
  so the lifecycle row is mostly read-only after that.
- **Edit the YAML**: open `~/.alpi/config.yaml` (or
  `~/.alpi/profiles/<name>/config.yaml` for non-default profiles)
  and change values manually. Restart whatever surface was affected.
  Cosmetic knobs (`tui.*`, `tools.max_steps_per_turn`,
  `gateway.imap.poll_interval`, `fallback_models`) live here.
- **Populate `.env` directly** (non-interactive, CI / devcontainers):
  alpi does not ship a `.env.example` — the Reference tables below
  (Core, Gateway — Telegram / Matrix / IMAP / Gmail) list every key with its
  default. Create `~/.alpi/.env` yourself with just the keys you use
  and alpi picks them up on next launch.

## Reference

### Core

| Key | Default | Type | Takes effect |
|---|---|---|---|
| `model` | `""` (empty; pick via `alpi setup → Model` — see `docs/MODELS.md`) | string | next session |
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
| `tools.terminal.sandbox` | `false` | bool | next turn |
| `tools.terminal.allow_network` | `false` | bool | next turn |
| `tools.terminal.approval.allowlist` | `[]` | list of pattern descriptions and/or command globs (see below) | next turn |
| `tools.browser.vision` | `false` | bool | next turn |
| `tools.budget.per_result_chars` | `100_000` | int (-1 = unlimited) | next turn |
| `tools.tts.voice` | `"en-US-AriaNeural"` | Edge TTS voice id | next turn |
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

Not implemented (tracked, not planned): per-turn aggregate cap and inline preview. Comparable agents carry both, but alpi only ships them if real turns start burning through several large tool results.

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

`tools.terminal.approval` controls the **command approval system** — a
layer on top of the sandbox that gives the user a chance to approve
borderline destructive commands instead of blocking them outright.
Each `terminal` call is classified by a small pattern list into three
severities:

- **safe** (default, no match) — runs without prompting.
- **caution** — matches a pattern that's often legitimate but
  sometimes destructive. Examples: `rm -rf <dir>`, `chmod 777`,
  `sudo <cmd>`, `git push --force`, `git reset --hard`,
  `DROP TABLE`, `kill -9`. These pause for user approval in the TUI
  with four options: `Once` (this call only), `Session` (allowlist
  the pattern until restart), `Always` (persist the pattern
  description to `tools.terminal.approval.allowlist` in config), or
  `Deny` (abort the tool call). On non-interactive surfaces
  (gateway, schedule) these auto-deny with a clear error telling the
  user to rerun from the TUI or edit the config allowlist.
- **dangerous** — matches a pattern that's almost never legitimate.
  Examples: `mkfs`, `dd of=/dev/…`, fork bomb, pipe-to-interpreter
  from an unknown URL (`curl … | bash`), recursive chmod / chown on
  `/`, reading SSH private keys, writes into `/etc` or `/var`. These
  are **always blocked**. No override — if you genuinely need to run
  one of these, do it directly from your shell, not through the
  agent.

Allowlist entries come in two shapes, sharing the same list:

**Pattern descriptions** — the human label attached to one of the
built-in caution regexes (`recursive rm`, `sudo`, `git force-push`,
`git hard reset`, `chmod 777 / a+w`, `sql drop / truncate`,
`process kill -9`). A pattern-desc entry allows **every** command of
that severity-category. This is what the `Always` button writes.

**Command globs** — any other string is treated as an `fnmatch`
pattern matched against the literal command (whitespace-trimmed).
Use this for per-command exceptions when the category-level bypass
is too broad. Globs only override **caution** classification;
dangerous commands stay blocked. Globs also do **not** apply to
**compound** commands (containing `&&`, `||`, `;`, `|`, newline,
backticks, or `$(…)`) — otherwise `"sudo apt *"` would also approve
`sudo apt update && rm -rf build`. Compound commands fall back to
the prompt unless a category-desc bypass covers them.

```yaml
tools:
  terminal:
    approval:
      allowlist:
        - recursive rm                       # category: every rm -rf passes
        - sudo apt *                         # glob: any sudo apt subcommand
        - git reset --hard origin/main       # glob: this exact command only
        - git push --force origin my-branch  # glob: only this branch's force-push
```

Session approvals live in memory (a module-level set) and die with
the TUI process. Permanent approvals persist to `config.yaml` via the
`Always` button (which writes a pattern-desc) or by hand-editing the
list with globs. Dangerous commands never get an allowlist entry.

This layer composes with the sandbox (`tools.terminal.sandbox`): the
sandbox is an OS-level boundary (network, filesystem writes outside
workspace) that catches what the approval layer misses; approval is
user-in-loop for the subset of commands that are legitimately
destructive inside the allowed scope. Both can be on at once; the
approval check runs first so the user sees the prompt before the
sandbox has a chance to refuse.

`tools.browser.vision` lets the `browser(screenshot, question=…)` action auto-chain the screenshot into the vision model (`tools.read_image.model` or the active main model) and return the answer instead of the file path. When `false` (default), `screenshot` always returns the path and a hint pointing at `read_image` so the LLM can decide whether to pay for vision per call. Useful to turn on in an exploratory profile; keep off in watchdog/gateway profiles so the agent doesn't burn vision tokens silently.

Image resizing is automatic: any image whose longer edge exceeds 1568 px (Anthropic's recommended bound) is downscaled before base64-encoding to the model. Vision-model cost scales with resolution — a 4K screenshot costs ~9× more tokens than its 1568-px version for the same content. Aspect ratio is preserved, PNG-with-alpha stays PNG, everything else rounds-trips through JPEG q=85. SVG (vector) is skipped. Not a knob — it is a fixed constant (`alpi.tools.read_image.MAX_EDGE`).

The `research` sub-agent's depth tiers (`quick` = 8 steps, `normal` = 15, `deep` = 30) are product definition, not user config. The agent picks the depth name from intent (`quick` = single-answer lookups, `normal` = comparative research, `deep` = exhaustive surveys); the step ceilings live in `alpi.tools.research.DEPTH_STEPS_DEFAULTS`.

`tools.tts.voice` selects the Edge TTS voice used by the `tts` tool. Any Microsoft Neural voice id is valid (`es-ES-AlvaroNeural`, `en-US-AriaNeural`, `fr-FR-DeniseNeural`, ...). Output is an MP3 cached under `~/.alpi/cache/tts/<hash>.mp3` — same text + voice reuses the cached file. Edge TTS runs against a free Microsoft endpoint (no API key), so there's no per-call cost. To use a different voice per call the agent can pass `voice=...` directly without touching config. `alpi setup → Voice` gives you a curated shortlist (10 common-language voices) plus a "custom" entry to type any voice id.

The daemon never plays audio itself — the `tts` tool returns the cached file path and stops. The alpi mobile / desktop apps stream playback on demand from a per-message button; for an external chat (e.g. Telegram) the agent chains `send_message(attachment=<path>)` to deliver the MP3 as an audio attachment.

`rate` and `pitch` are config-only (not per-call args) — persistent prosody defaults. Leave empty for neutral. Text is capped at 1000 chars (~1 minute); longer input is rejected. Output is always MP3.

`tools.stt.{model,language}` control the `stt` tool backed by faster-whisper running on CPU. First call downloads the model weights (~40 MB for `tiny`, ~150 MB for `base`, ~500 MB for `small`, ~1.5 GB for `medium`, ~3 GB for `large-v3`) into `~/.cache/huggingface/` and keeps them forever. Pick the smallest model that meets your accuracy bar — `base` is the sweet spot for spoken messages/voice notes; `small` or above for podcasts/meetings. `language` defaults to `""` (auto-detect); set to an ISO code (`en`, `es`, `fr`, ...) only when auto-detect fails on short clips.

The Telegram gateway auto-transcribes inbound voice notes and audio files through the same `stt` pipeline: when a user sends a voice message, the gateway downloads it via `getFile`, caches under `~/.alpi/cache/inbound/`, runs `stt`, and feeds the transcript to the agent as text (`[voice note] <transcription>`). The agent sees a normal text turn — nothing surface-specific to handle.

### Memory

| Field | Default | Notes |
|---|---|---|
| `memory.review_interval` | `0` (off) | Post-turn reviewer cadence. `N > 0` fires a daemon-thread reviewer every `N` user turns that snapshots the conversation and writes durable facts via `memory(action="add")`. Append-only — the reviewer cannot `replace`/`remove`. Opt-in by design. |

Internal-only constants (in `alpi/memory.py` and `alpi/compaction.py`, not user knobs):

- `USER_CHAR_LIMIT = 3000`, `MEMORY_CHAR_LIMIT = 5000` — file-level caps.
- Jaccard `0.7` max-containment — near-duplicate threshold.
- `LOW_CONFIDENCE_MAX_AGE_DAYS = 30` — low-conf pruning age.
- `trigger_ratio = 0.75`, `target_ratio = 0.40`, `keep_head = 2`, `keep_tail = 8` — auto-compaction policy.

Calibration of these is an evidence-gated v0.6 item (`AI(1.c)` + `CM.1` reading `logs/compaction.jsonl`); they stay fixed until real session data justifies tuning.

### TUI

alpi's TUI is built on [Textual](https://textual.textualize.io/) — a
full widget-based framework with streaming, focus management, scroll
anchoring, and responsive layout. It's the **primary surface** (not a
fallback); gateway and schedule processes inherit the same engine
behind the scenes but render through their own channel (chat message,
log file).

Design choices worth knowing before tweaking config:

- **Single cohesive UI.** No separate "legacy CLI" to maintain. alpi has
  one Textual app that covers every interactive use case.
- **Streaming is the default.** Assistant text streams into a Markdown
  widget char-by-char. No full-message reload; the widget knows how to
  append deltas. On `assistant_done` the final text replaces the
  streamed buffer so any post-processing (e.g. `_strip_cache_noise`)
  takes effect without a flash.
- **Tool cards, not log lines.** Each tool call gets a compact card
  with an args preview on the left, a live state in the middle
  (`synthesizing…`, `playing…`, `transcribing…` — tools push these
  via `tool_state_mod.emit_state`), a result hint on the right, and a
  duration badge. Cards are scroll-anchored so the chat follows new
  activity without stealing focus from what you're reading above.
- **Reasoning is inline, not modal.** For reasoning models
  (DeepSeek-R1, OpenAI o-series, Claude extended thinking) the tail
  of `reasoning_content` scrolls live inside the `thinking…`
  indicator. Full history is persisted to `sessions/*.json` even when
  `tui.show_reasoning=false`, so you can re-enable later and replay
  gets the reasoning back.
- **Slash commands auto-suggest.** `/help`, `/memory`, `/tools`,
  `/mcps`, `/cost`, `/clear`, `/new`, `/compact`, `/skills`, `/model`,
  `/exit`, `/quit`. Typing `/` opens a fuzzy prefix
  suggester over that list.
- **Responsive.** The top bar collapses labels when the terminal is
  narrower than 60 columns; long paths are home-dir-abbreviated to
  `~/…`. Nothing clips, nothing wraps weirdly.
- **Theming.** Pick a `tui.accent` colour (CSS hex/name/rgb) and
  `tui.theme: dark|light`. The accent recolours interactive
  highlights and the profile name in the top bar.
- **Scroll resilience under heavy streaming.** `VerticalScroll.anchor()`
  is used during long tool outputs or streamed responses so the view
  tracks the bottom without the user losing scroll position when they
  were reading history.

**What the top bar shows (left to right):**

```
alpi <version>  │  profile <name> <size>  │  [sandbox|offline]  │  workspace <path>
```

- `<size>` is the total disk footprint of the active profile home dir
  (`~/.alpi/` for default, `~/.alpi/profiles/<name>/` otherwise).
  Cached for 30 s; refreshed when you change profile, workspace, or
  model. For the default profile the `profiles/` subtree is excluded
  so it doesn't conflate with sibling profiles. Hidden in narrow mode
  (< 60 columns).
- The sandbox segment shows `sandbox` when
  `tools.terminal.sandbox=true` and `tools.terminal.allow_network=true`;
  it switches to `offline` when the network is locked (see sandbox
  knobs above). Hidden when sandbox is off.
- Workspace shows the resolved workspace path, or `not set` in error
  colour when no workspace is configured and alpi falls back to cwd.

**Config knobs (`tui.*`):**

| Key | Default | Type | Takes effect |
|---|---|---|---|
| `tui.show_cost` | `true` | bool | next session |
| `tui.show_tokens` | `true` | bool | next session |
| `tui.show_reasoning` | `true` | bool | next session |
| `tui.accent` | `#c8a24e` | CSS color (hex / named / rgb) | next session |
| `tui.theme` | `dark` | `dark` \| `light` | next session |
| `tui.auto_resume` | `false` | bool | next launch |

`tui.auto_resume` makes bare `alpi` behave as if `-c` / `--continue` was
passed — the last session is loaded automatically. Use `/new` inside the
TUI to start a fresh thread without changing the config. The flag does
not affect `alpi chat --once` (scripts and the gateway always start
clean) or explicit `-c` usage (still an override).

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

### Gateway — Matrix

| Key | Default | Why |
|---|---|---|
| `gateway.matrix.show_tool_trace` | `true` | Same rationale as Telegram — Matrix is an interactive chat surface. |

### Gateway — IMAP

| Key | Default | Why |
|---|---|---|
| `gateway.imap.poll_interval` | `60` (seconds) | IMAP polling cadence. Keeps CPU/network quiet for personal use. |
| `gateway.imap.mark_as_read` | `true` | Processed messages marked `\Seen` so your mail client treats them as read. |

### Gateway — Gmail

Same knobs as IMAP, different backend. Polling uses Gmail's `users.history.list` with the last-seen `historyId` so we only fetch deltas (cheaper than rescanning INBOX). Credentials live in `~/.alpi/<profile>/gmail_token.json` after the one-off OAuth consent via `alpi setup → Gateways → Gmail`.

| Key | Default | Why |
|---|---|---|
| `gateway.gmail.poll_interval` | `60` (seconds) | Same rationale as IMAP. |
| `gateway.gmail.mark_as_read` | `true` | Removes the `UNREAD` label on processed messages. |

Configure both if you want: `imap` polls your primary mailbox via password, `gmail` polls another account via OAuth, each with its own allowlist (`IMAP_ALLOWED_SENDERS` vs `GMAIL_ALLOWED_SENDERS`).

### Budget

One daily spending ceiling per profile. Pick **either** USD or tokens
— they are mutually exclusive, matching the profile's provider:

- `daily_usd` for paid APIs (Claude, OpenAI, Gemini, OpenRouter) where
  LiteLLM reports a real cost per turn.
- `daily_tokens` for local Ollama and other free inference paths where
  cost is always zero.
- Leave both unset for no ceiling.

The setup flows (`alpi setup → Budget` and the desktop app) enforce
the mutex by clearing the other key when you save one. If you
hand-edit `config.yaml` and end up with both, `daily_usd` takes
precedence at runtime.

The cap covers **every** turn this profile runs: interactive TUI
replies, gateway responses (Telegram / IMAP / Gmail), scheduled jobs,
sub-agent spawns (`research`, `delegate`, `read_image`), and inbound
ALP calls from pinned peers. Counters reset at UTC midnight; no
carry-over. The ledger lives at `~/.alpi/<profile>/logs/ledger.json` and
also records a per-peer breakdown for the `/cost` panel, though only
the profile total gates new turns.

| Key | Default | Notes |
|---|---|---|
| `budget.daily_usd` | unset | Hard daily USD cap. Exceeding it surfaces `budget-exceeded` (interactive) or JSON-RPC `-32005 budget-exceeded` (ALP). |
| `budget.daily_tokens` | unset | Hard daily token cap. Same behaviour; use instead of `daily_usd` for local / free providers. |

```yaml
# Paid-API profile
budget:
  daily_usd: 5.00

# Local Ollama profile
budget:
  daily_tokens: 500000
```

Edit interactively via `alpi setup → Budget` or the desktop app's
profile detail.

### ALP

ALP always serves the per-profile Unix socket for same-machine peers.
Inter-machine ALP.2 is opt-in per profile: set a TCP port in YAML or
pass `--port` when starting the listener. Bind the port to a Tailscale
/ WireGuard address where possible; `0.0.0.0` is supported, but public
internet exposure is not the recommended shape.

| Key | Default | Notes |
|---|---|---|
| `alp.tcp_port` | unset | Enables ALP.2 Noise_XK-over-TCP for this profile. The daemon's `alp` service picks it up when it boots this profile's listener. |
| `alp.tcp_host` | `127.0.0.1` when `tcp_port` is set | TCP bind host. Use a VPN IP or `0.0.0.0` when remote peers need to dial in. |

Example:

```yaml
alp:
  tcp_host: 100.64.12.34
  tcp_port: 7423
```

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

### Services (per profile)

Which services the alpi daemon spawns for THIS profile. The
daemon itself is one-per-machine (see [OPERATIONS.md →
Daemon](OPERATIONS.md)); these flags only decide what it
activates here.

```yaml
service:
  gateway: true     # Telegram / IMAP / Gmail / webhook listeners
  schedule: true    # cron tick loop
  alp: true         # peer-to-peer ALP listener
  workgroups: true  # ALP.3 outbound poller for joined workgroups
  host: true        # control-plane socket for desktop / mobile clients (default profile only)
```

The block name remains `service:` for back-compat; conceptually
each entry is a service the daemon runs for this profile. Missing
keys default to ``True``. Toggling takes effect at the next
``alpi daemon restart``.

`host` is meaningful only on the ``default`` profile; on any other
profile the toggle is honoured but the runner refuses to bind a
socket (the desktop / mobile client always targets default's
socket and reaches sibling profiles via the ``profile`` parameter
on each verb).

### Host (control plane)

The host plane serves `host.*` verbs over a Unix socket (always)
and a WebSocket on a Tailscale or RFC1918 LAN address (when one is
detected; mobile / remote desktop use this path).

| Key | Default | Effect |
|---|---|---|
| `host.tcp_port` | `49200` | WebSocket port for the remote transport. |
| `host.tcp_host` | `""` | Optional advertised host for `Devices`. Empty = auto-detect Tailscale CGNAT first, then first private LAN address. Set explicitly when clients should dial a stable hostname, MagicDNS name, VPN IP, or Umbrel hostname. |
| `host.device_name` | `""` | Optional pairing name shown in `Devices`. Empty = auto, otherwise this value is embedded in the pairing QR and device list. |

```yaml
host:
  tcp_port: 49200
  tcp_host: ""
  device_name: ""
```

`host.tcp_host` controls the **companion endpoint** shown in `alpi setup
→ Devices → Network` and embedded in pairing QRs. It does not configure
ALP peer transport. `Peer TCP listener` under `alpi setup → Services`
controls the separate `alp.tcp_host` / `alp.tcp_port` listener used by
other alpis (`link.*`, `workgroup.*`).

`host.device_name` controls the visible pairing label for new devices.
It is optional; when empty, alpi falls back to the platform hostname.

On regular macOS/Linux installs, leaving `host.tcp_host` empty keeps the
old auto mode: Tailscale first, then LAN. On Umbrel the daemon may bind
inside Docker while advertising a different host externally, such as
`umbrel.local`, a `100.x` Tailscale IP, or a MagicDNS hostname.

Pairing tokens for the WS transport live at
``~/.alpi/host/devices.yaml`` (mode 0600). Manage them through
``alpi setup → Devices`` — generate, label, revoke. The full token
appears once inside the pairing QR; the listing redacts to a
`token_id` (last 8 chars).

## Takes-effect cheat sheet

- **next turn** — change is live on the agent's next response.
- **next session** — restart `alpi` to pick it up.
- **next daemon restart** — `alpi daemon restart` (or reload
  through launchd / systemd if installed as an autorun).
