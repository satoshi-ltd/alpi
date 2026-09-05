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
```

Everything else (tool limits, TUI flags, fallback models, workspace)
falls back to the defaults below at load time. Add a key to the YAML
only when you want to override it.

## How to change settings

Three options:

- **CLI wizards**: `alpi setup` covers model selection, email
  credentials, MCP servers, sandbox posture, voice, peers,
  workgroups, disk cleanup, and the alpi daemon's lifecycle.
  `alpi setup → Cleanup` inspects the profile's heavy dirs (audio
  cache, old sessions, run journals older than 30 days, schedule
  output) and the knowledge index SQLite freelist (VACUUM-not-unlink),
  with one-shot confirmation per
  category. `alpi setup → Services` exposes daemon lifecycle (default
  profile), the shared accessible address, schedules, and client
  connections. The ALP section owns its peer TCP listener. Scheduler,
  ALP, workgroups, and the default host plane are daemon capabilities,
  not user-selectable services. The first `alpi setup` auto-installs
  the daemon, so the lifecycle row is mostly read-only after that.
- **Edit the YAML**: open `~/.alpi/config.yaml` (or
  `~/.alpi/profiles/<name>/config.yaml` for non-default profiles)
  and change values manually. Restart whatever surface was affected.
  Cosmetic knobs (`tui.*`, `tools.max_steps_per_turn`,
  `tools.stt.model`, `fallback_models`) live here.
- **Populate `.env` directly** (non-interactive, CI / devcontainers):
  alpi does not ship a `.env.example` — the Reference sections below
  (Core, Email — IMAP / Gmail) name every key with its
  default. Create `~/.alpi/.env` yourself with just the keys you use
  and alpi picks them up on next launch.

## Reference

### Core

| Key | Default | Type | Takes effect |
|---|---|---|---|
| `model` | `""` (empty; pick via `alpi setup → Model` — see `docs/MODELS.md`) | string | next session |
| `workspace` | `""` (cwd at launch) | string | next session |
| `fallback_models` | `[]` | list of strings — availability chain: when the active model fails before producing any output (provider down, credits exhausted) the turn retries down this list, sticking with the survivor for the rest of the turn | next turn |
| `tiers.fast.model` | `""` (use main) | string — cheap/fast model for routine work: compaction summaries, the memory reviewer, bio drafting, `research(depth=fast)`, and `delegate`/`schedule` runs that opt into `tier: fast` | next turn |
| `tiers.fast.effort` | `""` | `low` \| `medium` \| `high` — reasoning effort for the fast tier's own model (never inherits the profile effort) | next turn |
| `tiers.deep.model` | `""` (use main) | string — stronger model for hard reasoning: `research(depth=deep)`, `delegate(tier=deep)`, and the escalation target when a turn accumulates 3 consecutive tool failures or an empty reply (once per turn, skipped past 80% of `budget.daily_usd`) | next turn |
| `tiers.deep.effort` | `""` | `low` \| `medium` \| `high` — reasoning effort for the deep tier's own model | next turn |
| `providers.ollama` | `[]` | list of `{name, url}` — one per Ollama server | next session |
| `providers.openrouter.models` | `[]` | list of OpenRouter model ids the user has picked | next session |
| `public_bio` | `""` | string — one-line public tag-line broadcast to every workgroup this profile joins (source of truth for `Member.bio` on the hub). Empty = don't publish; peers see name only. `AGENT.md` stays private. | next `workgroup.join` |
| `paused` | `false` | bool — profile-level pause flag. Surfaced in the desktop / mobile profile summary so paired apps can show + respect the state; the daemon itself does not gate turns on this flag. Persisted only when `true`. | next host-plane read |

### Tools

| Key | Default | Type | Takes effect |
|---|---|---|---|
| `tools.max_steps_per_turn` | `100` | int | next turn |
| `tools.max_parallel_tool_calls` | `4` | int — maximum concurrent calls in an all-parallel-safe tool batch | next turn |
| `tools.deny` | `[]` | list of tool names | next turn |
| `tools.execution.backend` | `"local"` | `local` \| `docker` — terminal shell backend; background jobs are refused in Docker | next turn |
| `tools.execution.docker_image` | `"python:3.12-slim"` | Docker image used when the execution backend is `docker` | next turn |
| `tools.web_extract.model` | `""` (use main) | string — a model id, or the literal `fast` / `deep` to reference a tier | next turn |
| `tools.read_image.model` | `""` (use main) | string — a model id, or the literal `fast` / `deep` to reference a tier | next turn |
| `tools.terminal.sandbox` | `false` | bool | next turn |
| `tools.terminal.allow_network` | `false` | bool | next turn |
| `tools.terminal.approval.allowlist` | `[]` | list of pattern descriptions and/or command globs (see below) | next turn |
| `tools.browser.vision` | `false` | bool | next turn |
| `tools.web_search.max_per_turn` | `25` | int | next turn |
| `tools.browser.allow_local` | `false` | bool — let the `browser` tool navigate **loopback** only (`127.0.0.1`, `::1`, and hostnames that resolve to loopback such as `localhost`). RFC1918 / CGNAT / Tailscale stay blocked even when this is on; the exemption is loopback-only, matching `_guards._is_loopback`. Off blocks every local target; on is for hitting a local dev server you trust. | next turn |
| `tools.budget.per_result_chars` | `100_000` | int (-1 = unlimited) | next turn |
| `tools.tts.voice` | `"en-US-AriaNeural"` | Edge TTS voice id | next turn |
| `tools.tts.rate` | `""` | string (`"+10%"`, `"-20%"`) — speed | next turn |
| `tools.tts.pitch` | `""` | string (`"+5Hz"`, `"-10Hz"`) — pitch | next turn |
| `tools.tts.auto_read` | `false` | bool — apps auto-play each agent reply aloud | next turn |
| `tools.stt.model` | `"base"` | `tiny` \| `base` \| `small` \| `medium` \| `large-v3` | next turn |
| `tools.stt.language` | `""` (auto) | ISO code (`en`, `es`, ...) | next turn |
| `tools.attachments.max_text_tokens` | `0` (auto) | int (tokens) | next turn |
| `tools.<name>.max_result_chars` | `—` (unset) | int (-1 = unlimited) | next turn |

`tools.read_image.model` is a dedicated override for image inspection, not a
second conversational model. Set it from `alpi setup → Routing models`, or the
Vision model row in desktop/mobile. `read_image` and
`browser(screenshot, question=...)` use it; clearing it makes both fall back to
the profile's main model. It does **not** reroute image attachments sent directly
to chat: those remain part of the main model's turn.

`max_steps_per_turn` is a **runaway-loop backstop, not the cost guard** — the cost guard is `budget.daily_usd`. It counts model iterations, and the configured value (default 100) is literal for every provider and budget. Hitting the cap does not discard gathered work: normal chats get one tools-off best-effort wrap-up, while detached workgroup turns get one `workgroup_post`-only handoff. Raise it explicitly only for profiles whose skills legitimately need longer tool chains.

`tools.budget.per_result_chars` caps the size of any tool output the LLM
sees in-context, with a `… [N chars elided by tool budget]` suffix when
hit. Prevents a single `read_file` on a 5 MB log from blowing up a turn.
Per-tool overrides via `tools.<name>.max_result_chars` — set `-1` on
`read_file` if you want the LLM to get the whole source deliberately,
or lower a chatty tool's cap.

`tools.max_parallel_tool_calls` only applies when every call in the model's
batch declares itself parallel-safe. A mutation, terminal call, unknown tool,
or mixed batch is an exclusive barrier and retains serial ordering. Results
are appended to the conversation in the model's original call order.

`tools.execution.backend=docker` runs terminal shell processes in an ephemeral
`docker run --rm` world. The workspace, profile home, and explicit working
directory are mounted at their existing absolute paths so filesystem tools
and processes see the same namespace. Network is disabled unless
`tools.terminal.allow_network=true`. Background terminal jobs are refused in
this backend so a detached container cannot outlive its run. The `local` backend remains the default
and continues to compose with `tools.terminal.sandbox` as before. Dedicated
workers such as skill scripts and speech transcription remain host-side; this
setting is not a whole-agent filesystem sandbox.

Precedence: `tools.<name>.max_result_chars` (if set) → `tools.budget.per_result_chars` → hardcoded `100_000`.

Not implemented (tracked, not planned): per-turn aggregate cap and inline preview. Comparable agents carry both, but alpi only ships them if real turns start burning through several large tool results.

`tools.deny` is a per-profile denylist of tool names. Denied tools are
**absent from the schema the LLM sees** (it can't reach for what it
doesn't know about) AND **refused by the executor** as defence in
depth — if a stale context or a peer's `link.ask` names a denied tool,
the call returns `tool denied for this profile: <name>` instead of
running. Unknown names are no-ops, so typos are harmless. Denying
`alpi_knowledge` also drops the self-knowledge rule from the system
prompt, so the model is never told to call a tool it cannot reach.

Canonical names are the strings used at registration time —
`write_file`, `edit_file`, `terminal`, `email`,
`schedule`, `delegate`, `peer`, `knowledge`, `alpi_knowledge`,
`research`, `browser`, `workgroup`, etc. See `alpi/tools/__init__.py`
for the full registry. Note: `knowledge` is the user's workspace OKF
wiki; `alpi_knowledge` is the packaged docs tool for alpi itself.

Useful for tightening a profile that is exposed to less-trusted input
— e.g. a "librarian" profile that other peers reach via `link.ask`
and that has no business writing files, running shell, or sending
mail:

```yaml
# ~/.alpi/profiles/archi/config.yaml
tools:
  deny:
    - write_file
    - edit_file
    - terminal
    - email
    - schedule
    - delegate
```

Today this is YAML-only. There is no `alpi setup` wizard for `deny`
and no surface for it in the desktop/mobile apps — the surface is
power-user enough that raw names beat any UI we'd build right now.

`tools.terminal.sandbox` enables OS-level isolation on shell commands
(macOS `sandbox-exec`, Linux `bubblewrap`). Toggle via `alpi setup →
Sandbox`, or directly in YAML. The TUI top bar shows the current
state (`sandbox on` / `off`). Most useful on profiles that run
unattended (schedule, sub-agents) — see
[SECURITY.md](SECURITY.md) for the recommended pattern + platform
requirements.

`allow_network` has no effect unless `sandbox` is on. When sandbox is
on and `allow_network=false`, the flag blocks ALL agent-initiated
network:

- The `terminal` subprocess is denied sockets (sandbox-exec / bwrap).
- Python-native tools (`web_fetch`, `web_search`, `web_extract`,
  `browser`, `tts`, `email`, `read_image` on URLs)
  refuse with a clear error.
- The LLM call itself (litellm) is exempt — it's the agent's brain,
  not an exfiltration vector.

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
  (schedule) these auto-deny with a clear error telling the
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

`tools.browser.vision` lets the `browser(screenshot, question=…)` action auto-chain the screenshot into the vision model (`tools.read_image.model` or the active main model) and return the answer instead of the file path. When `false` (default), `screenshot` always returns the path and a hint pointing at `read_image` so the LLM can decide whether to pay for vision per call. Useful to turn on in an exploratory profile; keep off in watchdog/unattended profiles so the agent doesn't burn vision tokens silently.

Image resizing is automatic: any image whose longer edge exceeds 1568 px (Anthropic's recommended bound) is downscaled before base64-encoding to the model. Vision-model cost scales with resolution — a 4K screenshot costs ~9× more tokens than its 1568-px version for the same content. Aspect ratio is preserved, PNG-with-alpha stays PNG, everything else rounds-trips through JPEG q=85. SVG (vector) is skipped. Not a knob — it is a fixed constant (`alpi.tools.read_image.MAX_EDGE`).

The `research` sub-agent's depth tiers (`fast` = 8 steps, `normal` = 15, `deep` = 30) are product definition, not user config. `fast` and `deep` share their names with the model tiers — a depth also picks the matching tier when configured, while `normal` runs on the main model. The agent picks the depth name from intent (`fast` = single-answer lookups, `normal` = comparative research, `deep` = exhaustive surveys); the step ceilings live in `alpi.tools.research.DEPTH_STEPS_DEFAULTS`.

`tools.tts.voice` selects the Edge TTS voice used by the `tts` tool. Any Microsoft Neural voice id is valid (`es-ES-AlvaroNeural`, `en-US-AriaNeural`, `fr-FR-DeniseNeural`, ...). Output is an MP3 cached under `~/.alpi/cache/tts/<hash>.mp3` — same text + voice reuses the cached file. Edge TTS runs against a free Microsoft endpoint (no API key), so there's no per-call cost. To use a different voice per call the agent can pass `voice=...` directly without touching config. `alpi setup → Voice` gives you a curated shortlist (10 common-language voices) plus a "custom" entry to type any voice id.

The daemon never plays audio itself — the `tts` tool returns the cached file path and stops. The alpi mobile / desktop apps stream playback on demand from a per-message button, and — when `tools.tts.auto_read` is on — auto-play each agent reply aloud as it arrives (your own messages are never read); they synthesize through the same Edge TTS path via `host.voice.preview`. To deliver the MP3 to a third party the agent chains `email(send, attachment=<path>)` as an audio attachment. Workgroups carry an analogous **hub-local** `auto_read` flag in the workgroup meta (set from the desktop/mobile workgroup settings) that auto-reads agents' messages — never your directives; it is not replicated to members.

`rate` and `pitch` are config-only (not per-call args) — persistent prosody defaults. Leave empty for neutral. Text is capped at 1000 chars (~1 minute); longer input is rejected. Output is always MP3.

`tools.attachments.max_text_tokens` caps how much **extracted text** from a
single attachment reaches the model — applied identically to text/source
files, digital-PDF text, and scanned-PDF OCR. Denominated in tokens; the
engine converts to characters at ~4 chars/token (`attachments.CHARS_PER_TOKEN`).

**Default `0` = auto**: the cap tracks the active model's context window —
half of it per attachment (`AUTO_TEXT_WINDOW_FRACTION`), resolved from
`litellm.get_model_info`. So a 200k-context model gives an attachment ~100k
tokens, a 1M model ~500k, a small local model proportionally less — no config
needed. When litellm can't resolve the model (some `openrouter/…` ids, custom
Ollama names) it falls back to `FALLBACK_TEXT_TOKENS` (100k). A **positive
value overrides auto** with a fixed per-attachment cap — set it to bound cost
on a large-context model, or to force more text on a model litellm mis-sizes.

This is the real content ceiling; the per-file byte caps (`MAX_TEXT_FILE_BYTES`
2 MiB for text, `MAX_FILE_BYTES` 20 MiB for PDF/image) only gate *acceptance*.
It does not change page rendering or OCR page count (that is the fixed
`SCAN_MAX_PAGES` scan cap); and to feed a text file larger than 2 MiB you would
also need a higher acceptance cap.

`tools.stt.{model,language}` control the `stt` tool backed by faster-whisper running on CPU. First call downloads the model weights (~40 MB for `tiny`, ~150 MB for `base`, ~500 MB for `small`, ~1.5 GB for `medium`, ~3 GB for `large-v3`) into `~/.cache/huggingface/` and keeps them forever. Pick the smallest model that meets your accuracy bar — `base` is the sweet spot for spoken messages/voice notes; `small` or above for podcasts/meetings. `language` defaults to `""` (auto-detect); set to an ISO code (`en`, `es`, `fr`, ...) only when auto-detect fails on short clips.

### Runtime

Provider stale-call hardening for LLM streaming turns: watchdogs that fail a
slow/stuck provider instead of hanging the turn, plus jittered retries before
any output reaches the consumer. A timeout of `0` disables that watchdog.

| Key | Default | Type | Takes effect |
|---|---|---|---|
| `runtime.first_byte_timeout_s` | `300` | seconds (`0` = off) | next turn |
| `runtime.stream_idle_timeout_s` | `120` | seconds (`0` = off) | next turn |
| `runtime.stream_max_duration_s` | `600` | seconds (`0` = off) | next turn |
| `runtime.max_retries` | `2` | int | next turn |
| `runtime.retry_backoff_s` | `1.5` | seconds (base; exponential + jitter) | next turn |
| `runtime.prefetch` | `""` | `"" \| auto \| all \| off` | next daemon start |

`first_byte_timeout_s` is generous so slow reasoning models aren't killed before
their first token; bump it for very slow local Ollama or long-thinking models.
`stream_max_duration_s` bounds one provider request even while it keeps emitting
deltas. The ten-minute default leaves room for long reasoning while preventing
one request from consuming an entire workgroup phase; set `0` to disable it.
Retries fire only for transient failures (timeouts, connection drops, 429/5xx)
and only before visible text reaches an interactive client. Detached workgroup
turns may replay a partial attempt because their streamed text is not exposed;
an enabled request-duration limit is treated as transient and can retry the same
model within the turn.

An empty `runtime.prefetch` selects `auto` outside Docker and `off` in Docker.
`all` forces Chromium and embedding weights to warm after daemon startup; `off`
keeps their existing first-use loading behavior.

### Model reasoning

Optional reasoning-effort hint passed alongside `cfg.model` to providers
that support it (Anthropic extended thinking, OpenAI o-series, DeepSeek
R1, etc.). Applied **only** to the profile's default model — mid-chat
`model` overrides and tool sub-models (`research`, `delegate`,
`web_extract`, `read_image`) ignore it. Models that don't recognise the
hint are unaffected.

| Key | Default | Type | Takes effect |
|---|---|---|---|
| `model_reasoning.effort` | `""` (no reasoning param sent) | `"" \| "low" \| "medium" \| "high"` — `"off"` written to disk normalises to `""` on load | next turn |

```yaml
model_reasoning:
  effort: medium
```

### Memory

| Field | Default | Notes |
|---|---|---|
| `memory.review_interval` | `0` (off) | Post-turn reviewer cadence. `N > 0` fires a daemon-thread reviewer every `N` user turns that snapshots the conversation and writes durable facts via `memory(action="add")`. Append-only — the reviewer cannot `replace`/`remove`. Opt-in by design. |

Internal-only constants (in `alpi/memory.py` and `alpi/compaction.py`, not user knobs):

- `USER_CHAR_LIMIT = 3000`, `MEMORY_CHAR_LIMIT = 5000` — file-level caps.
- Jaccard `0.7` max-containment — near-duplicate threshold.
- `LOW_CONFIDENCE_MAX_AGE_DAYS = 30` — low-conf pruning age.
- `trigger_ratio = 0.75`, `target_ratio = 0.40`, `keep_head = 2`, `keep_tail = 8` — auto-compaction policy.

Calibration stays evidence-gated: these constants should not become user knobs unless real `logs/compaction.jsonl` / memory-review traces show repeated failures that a fixed default cannot solve.

### TUI

alpi's TUI is built on [Textual](https://textual.textualize.io/) — a
full widget-based framework with streaming, focus management, scroll
anchoring, and responsive layout. It's the **primary surface** (not a
fallback); schedule processes inherit the same engine
behind the scenes but render through their own channel (log file).

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
not affect `alpi chat --once` (scripts and scheduled jobs always start
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
context. Non-interactive surfaces (scheduled jobs) never rendered
reasoning, so this flag has no effect there.

### Email — IMAP / Gmail

Email is an on-demand integration, not a listener: the agent reads,
searches, and sends mail through the `email` tool when a chat or a
scheduled job calls for it — nothing polls your inbox.

A profile holds **as many email accounts as you want**, any mix of
IMAP and Gmail. Each account is keyed by its address (its id is a slug
of that address), so adding a second Gmail or a third IMAP mailbox is
just another entry. The `email` tool's `account` parameter selects
which one by address or id.

Accounts are declared in `config.yaml` under `email.accounts`, which
carries no secrets — only the non-sensitive shape of each account:

```yaml
email:
  accounts:
    you-at-work-com:
      type: imap
      address: you@work.com
      imap_host: imap.work.com
      imap_port: 993
      smtp_host: smtp.work.com
      smtp_port: 465
    you-at-gmail-com:
      type: gmail
      address: you@gmail.com
```

Secrets live in `~/.alpi/<profile>/.env`, namespaced per account by
its id: an IMAP account's password is `EMAIL__<ID>__PASSWORD` (e.g.
`EMAIL__YOU_AT_WORK_COM__PASSWORD`). Gmail accounts use OAuth — the
client credentials `GMAIL_CLIENT_ID` / `GMAIL_CLIENT_SECRET` are
**shared across every Gmail account** on the profile, while each
account's refreshable token is stored per account at
`~/.alpi/<profile>/secrets/gmail_tokens/<id>.json` after a one-off
consent.

Add and manage accounts with `alpi setup → Email` (CLI) or the
**Email** settings section in the desktop / mobile apps — its own
section, where you add and remove accounts like MCP servers. Operate on
a single account by id from the CLI with `alpi email probe <id>` and
`alpi email remove <id>`.

`email.accounts` is intentionally absent from the key tables above: it
is a per-account map, not a fixed knob.

### Budget

One daily spending ceiling per profile, in dollars — or unlimited.

- `daily_usd` caps real spend (LiteLLM reports a cost per turn for
  paid APIs; local/free paths report zero and so never hit the cap).
- Leave it unset for no ceiling.

A token-denominated cap is intentionally not offered: tokens are not a
meaningful business constraint (their cost varies by model), so the only
caps that mean anything are dollars or nothing.

The cap covers **every** turn this profile runs: interactive TUI
replies, scheduled jobs,
sub-agent spawns (`research`, `delegate`, `read_image`), and inbound
ALP calls from pinned peers. It is re-checked **before each step**
within a turn, so a long multi-step turn aborts as soon as it crosses
the ceiling rather than running to completion. Counters reset at UTC
midnight; no carry-over. The ledger lives at `~/.alpi/<profile>/logs/ledger.json` and
also records a per-peer breakdown for the `/cost` panel, though only
the profile total gates new turns.

| Key | Default | Notes |
|---|---|---|
| `budget.daily_usd` | unset | Hard daily USD cap. Exceeding it surfaces `budget-exceeded` (interactive) or JSON-RPC `-32005 budget-exceeded` (ALP). Unset = unlimited. |

```yaml
budget:
  daily_usd: 5.00
```

Edit interactively via `alpi setup → Budget` or the desktop app's
profile detail.

### Network (shared accessible address)

One address, shared by every network listener this profile runs — the
device-pairing host plane and the ALP peer listener both bind/advertise on it,
each on its own port. Configure it once.

| Key | Default | Effect |
|---|---|---|
| `network.host` | `""` | Shared bind/ALP address. Empty = auto-detect a reachable private address. A private IP literal also produces the automatic direct `ws://` client route. Hostnames require an explicit certificate-validated `wss://` entry in `host.endpoints`; they never produce a plaintext route. A public IP additionally needs `host.allow_public_bind: true`; that gate applies to the shared bind used by **both** planes (host control plane + ALP listener), so without it neither binds TCP. |

```yaml
network:
  host: ""        # empty = auto-detect a private address
```

The detected address is shown read-only in `alpi setup → Connections → Network`
and Desktop (`Settings → profile → Service`). Set an explicit address in
`config.yaml`, or with `ALPI_NETWORK_HOST` in Docker. Ports stay per-plane
(`host.tcp_port`, `alp.tcp_port`). A public IP also requires
`host.allow_public_bind: true`; set both keys by hand.

### ALP

ALP always serves the per-profile Unix socket for same-machine peers. The
Noise_XK TCP listener is auto-exposed only for the `default` profile, whenever
the machine has a reachable address — bound to the shared `network.host`
(above), or an auto-detected overlay/LAN address, or `0.0.0.0` in Docker.
**Named profiles stay Unix-only** unless they set their own explicit, unique
`alp.tcp_port` (otherwise every profile would fight over the shared port). With
no reachable address (no `network.host`, no Tailscale/LAN, not Docker) even
`default` stays Unix-only.

| Key | Default | Notes |
|---|---|---|
| `alp.tcp_port` | `7423` (default profile only) | The ALP peer TCP port. Auto-exposed for the `default` profile; a named profile binds TCP only if it sets its own unique port here. The address is `network.host`. |
| `alp.link_idle_timeout_s` | `60` | Cancel `link.ask` after this many seconds without a signed response or progress frame. `0` disables the idle watchdog. |
| `alp.link_max_duration_s` | `0` | Optional absolute cap for one `link.ask`; `0` allows an active turn to run without a fixed wall-clock limit. |
| `alp.max_active_workgroups` | `5` on the default profile | How many workgroups may be active at once: a running pipeline or a deliberation with an open task each hold a slot. Enforced at pipeline admission: excess pipeline launches and triggers wait in a persistent FIFO queue, while deliberation launches always open and count against the cap. Read from the hub's own `config.yaml` when set there, else from the default profile's (the daemon-wide setting, seeded at `5` on new installs), else unlimited; `0` is unlimited. Set it with `alpi workgroup limit N` (on the default profile for every hub, on a hub to override), remove a hub override with `alpi workgroup limit --inherit`, or edit it from any profile's settings in the desktop app; `workgroup list` shows the cap, its origin and the queue. |
| `alp.working_after_s` | `30` | Post an automatic `#working` heartbeat when a member turn remains silent for this many seconds. `0` disables it. |

```yaml
alp:
  tcp_port: 7423
  link_idle_timeout_s: 60
  link_max_duration_s: 0
  max_active_workgroups: 5
  working_after_s: 30
```

`link.ask` uses streaming internally even when the caller only needs the final
reply. The target sends a start frame and periodic progress frames, so an active
review can run longer than `link_idle_timeout_s`; the watchdog measures silence,
not total duration. Set `link_max_duration_s` only when the operator wants a
hard cap as well. A timed-out caller requests `link.cancel` and reports the
reason explicitly instead of returning an empty transport error.

Pipeline admission is local to each hub profile. The queue limits whole active
pipelines, not agent turns: admitted workgroups retain normal parallel phase
execution, while excess launches and manual triggers wait FIFO on disk and
survive daemon restarts. `running` and between-phase pipelines occupy a slot;
completed or blocked pipelines release it. Both settings take effect after a
configuration reload; a daemon that predates this feature still needs the
updated process before it can enforce them.

### Relay

Turns a profile into a **read-only front door** to one designated peer. When set, the engine offers the profile **only the `peer` tool** and hard-gates every turn: the agent MUST consult that pinned peer via `peer` before it can produce a final answer — a call to any other peer id is rejected before it runs, an empty reply does not count, and if the turn ends (or hits the step/time limit) without a valid reply it fails closed with a fixed message rather than answer from the model's own knowledge. The peer's reply is surfaced as the answer. So you only pin that peer in `peers.yaml` with `link.ask` — no separate `tools.deny` needed.

This makes the **relay side** read-only, structurally. It does **not** make the target agent immutable: an inbound `link.ask` runs a full turn on the target with the target's own tools, so keeping the knowledge source unwritable is the target profile's responsibility — deny its mutating tools there, and restrict which paired devices may address it via a member connection's `profile_scope` (see *Host* below). The relay does not police the peer.

| Key | Default | Notes |
|---|---|---|
| `relay.peer` | unset | The pinned `peer_id` this profile must consult before answering. Unset = no relay gate (normal profile). |

```yaml
relay:
  peer: agora
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
| `mcp.servers` | `{}` | Map of `<name> → {command, args, env}`. Each server is a **local stdio subprocess** the daemon spawns — alpi has no native HTTP/SSE MCP transport. Secrets in `env` use the `env:VAR_NAME` reference (resolved from the profile `.env` at spawn). Add via `alpi setup → MCPs`; hand-editing is supported. |

An entry is `command` + `args` + `env`. alpi launches it as a local subprocess
and speaks MCP over stdio, so a **remote HTTP endpoint must be bridged** (below).
Each `env` value of the form `env:VAR_NAME` is resolved from the profile `.env`
at spawn and passed as the subprocess's environment — the secret lives in `.env`,
never in `config.yaml`.

**Pattern A — stdio server, secret via environment** (server reads its
credentials from env vars, e.g. a Bitbucket MCP):

```yaml
mcp:
  servers:
    bitbucket:
      command: npx
      args: [-y, bitbucket-mcp@5.0.6]
      env:
        BITBUCKET_URL: env:BITBUCKET_URL
        BITBUCKET_WORKSPACE: env:BITBUCKET_WORKSPACE
        BITBUCKET_USERNAME: env:BITBUCKET_USERNAME
        BITBUCKET_PASSWORD: env:BITBUCKET_PASSWORD
```
`.env`: `BITBUCKET_PASSWORD=…` (etc.). The server reads them from its environment.

**Pattern B — remote HTTP endpoint, secret in an auth header.** Because alpi is
stdio-only, bridge the HTTP MCP with `mcp-remote`. The catch: `env:VAR` injects
into the subprocess **environment only, not into `args`**, so a secret that must
travel as an HTTP header cannot be referenced directly in the `--header` arg.
Use `mcp-remote`'s own `${VAR}` expansion — it substitutes `${VAR}` in a
`--header` value from its environment, which you populate via the `env:` map:

```yaml
mcp:
  servers:
    lobby:
      command: npx
      args:
        - -y
        - mcp-remote@latest
        - https://api.example.com/mcp
        - --transport
        - http-only
        - --header
        - 'x-mcp-secret: ${MCP_SECRET}'   # mcp-remote expands ${...} from its env
      env:
        MCP_SECRET: env:MCP_SECRET   # alpi injects it from the profile .env
```
`.env`: `MCP_SECRET=…`. Do **not** hardcode the secret in `--header`, and do
**not** wrap the command in `sh -c` to expand it — `mcp-remote` expands `${VAR}`
in headers itself.

**Takes effect:** MCP servers are spawned by the profile's engine; a config
change is picked up when that profile's MCP subprocess is next (re)started —
restart the daemon or re-bootstrap the profile.

### Daemon capabilities

The one-per-machine daemon starts the scheduler, ALP listener, and workgroup
poller for every profile, plus the host control plane for `default`. They are
fixed internal tasks rather than configuration switches. Control behavior at
the owning boundary instead: enable/remove jobs, pause/leave workgroups,
grant/revoke peers, and scope/revoke client connections.

Legacy `service.schedule`, `service.alp`, `service.workgroups`, and
`service.host` keys are ignored. The daemon logs a warning at startup and
`alpi doctor` reports them until the block is removed; all capabilities still
start. A legacy `service.prefetch` value migrates to `runtime.prefetch` on save.

`host` is meaningful only on the ``default`` profile; on any other
profile the toggle is honoured but the runner refuses to bind a
socket (the desktop / mobile client always targets default's
socket and reaches sibling profiles via the ``profile`` parameter
on each verb).

### Host (control plane)

The host plane serves `host.*` verbs over a Unix socket (always)
and a WebSocket on the shared `network.host` (see Network above);
mobile / remote desktop use this path.

| Key | Default | Effect |
|---|---|---|
| `host.tcp_port` | `49200` | WebSocket port for device pairing (the host plane's own port). |
| `host.device_name` | `""` | Optional pairing name shown in `Devices`. Empty = auto, otherwise embedded in the pairing QR and device list. |
| `host.endpoints` | `[]` | Ordered explicit routes advertised in new pairing codes. Each row is `{url, label}` for wire compatibility. Desktop and setup manage one optional public `wss://` route. When no explicit `ws://` row exists, Alpi appends the private route derived from `network.host` and `host.tcp_port`; unsafe or unavailable addresses produce no private route. Explicit WS rows remain supported for compatibility. |
| `host.allow_public_bind` | `false` | Opt-in to let the shared network bind use a **public IP**. Affects **both** the host control plane and the ALP listener — both derive their bind from `network.host`, so without it neither binds TCP on a public address. A private or hostname address needs no opt-in; only a public IP does. |

```yaml
host:
  tcp_port: 49200
  device_name: ""
  endpoints:
    - url: wss://your.domain.com
      label: Secure Internet
    - url: ws://100.64.10.2:49200
      label: Direct
```

The address itself lives in `network.host` (shared with the ALP listener),
not here. `host.endpoints` is advertisement only: it does not open listeners,
terminate TLS, or change authentication. A `wss://` route normally points at a
TLS front-end — a reverse proxy such as Caddy, or a managed edge like a cloud
load balancer / CDN — which forwards to the daemon's `tcp_port`.
The Service UI shows that derived WS endpoint as **Private route** and the
configured WSS endpoint as **Public route**. Removing the public route removes
only WSS advertisement; private access continues whenever a safe private
address exists.
The listen port is editable in Desktop and `alpi setup` and requires a daemon
restart. `ALPI_HOST_TCP_PORT` takes precedence over `host.tcp_port`; when set by
a Docker deployment, change both that environment value and the matching 1:1
port mapping, then recreate the container. Multiple containers on one host use
distinct effective ports such as `49200`, `49201`, and `49202`.
`host.device_name` controls the visible pairing label for new devices.
It is optional; when empty, alpi falls back to the platform hostname.
Plaintext hostname routes are rejected because DNS may resolve them to a public
address (including alternate numeric IPv4 forms). Use a private IP literal for
direct WS or a certificate-validated hostname with WSS.

WebSocket safety limits are daemon-wide environment settings. Defaults should
fit Desktop and Mobile; changing them requires a daemon restart.

| Environment | Default | Effect |
|---|---:|---|
| `ALPI_HOST_WS_MAX_CONNECTIONS` | `128` | Maximum simultaneous WebSockets. |
| `ALPI_HOST_WS_MAX_CONNECTIONS_PER_DEVICE` | `8` | Maximum sockets sharing one device credential. |
| `ALPI_HOST_WS_MAX_RPCS_PER_DEVICE` | `8` | Maximum concurrent RPC handlers or streams for one device. |
| `ALPI_HOST_WS_AUTH_TIMEOUT` | `10` | Seconds allowed for the first authenticated request. |
| `ALPI_HOST_WS_AUTH_RECHECK` | `1` | Seconds between active-socket authorization checks. |
| `ALPI_HOST_WS_CLOSE_TIMEOUT` | `1` | Maximum graceful WebSocket close wait in seconds. |
| `ALPI_HOST_WS_REVOCATION_RETRY` | `5` | Minimum seconds before retrying cancellation of a revoked stream. |

These can be set in the daemon process environment or the root `~/.alpi/.env`.
There is intentionally no global handshake-per-minute setting: before
authentication, Alpi cannot distinguish a paired client from an attacker, and
a shared budget would let cheap HTTP requests lock out legitimate devices.
Per-IP limits belong in the public reverse proxy, firewall or WAF where the
original client address is trustworthy.

The host plane lives with the `default` profile and its single socket serves
every sibling profile. **Admin** connections plus direct local socket access
reach any profile. To limit which profiles a paired **member** connection may
address, scope that connection with `profile_scope`; daemon task configuration
is not an access-control boundary.

On regular macOS/Linux installs, leaving `network.host` empty keeps auto
mode: Tailscale first, then LAN, used as both the advertised address and the
bind. Setting it advertises that address to clients/peers; the bind is
derived separately — a private/Tailscale IP binds itself, a hostname or an
opted-in public IP binds `0.0.0.0`, and a public IP without
`host.allow_public_bind` refuses to bind at all. In Docker the daemon binds
`0.0.0.0` inside the container. A LAN or `100.x` Tailscale IP in
`ALPI_NETWORK_HOST` can produce the direct client route. A hostname, including
MagicDNS, is still valid for ALP but desktop/mobile need an explicit `wss://`
entry in `host.endpoints` (see
[`docker/README.md`](../docker/README.md#secure-internet-access-wss)).

Connection identities and per-device WS credentials live at
``~/.alpi/host/connections.yaml`` (mode 0600). Manage them through
``alpi setup → Connections``. A connection owns its label, role and profile
scope; every linked desktop/mobile device receives a different token and can
be revoked independently. A new QR/link contains a one-time pairing grant,
never that permanent token. The grant is stored only as a hash, expires after
ten minutes and is consumed atomically by the first client. Desktop and Mobile
still accept legacy `token=` links generated by older daemons.

On first startup after upgrading, an existing ``devices.yaml`` is migrated
automatically. Every legacy row becomes one connection with one device, its
token and access preserved, and the source is renamed to
``devices.yaml.migrated``. The old schema has no grouping key, so migration
cannot safely merge rows that may belong to the same person or workload.

## Takes-effect cheat sheet

- **next turn** — change is live on the agent's next response.
- **next session** — restart `alpi` to pick it up.
- **next daemon restart** — `alpi daemon restart` (or reload
  through launchd / systemd if installed as an autorun).
