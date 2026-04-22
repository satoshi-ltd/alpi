# Roadmap

Status of in-progress work, plans for the next cycle, and a brief log of
what's already shipped. For technical reference of what's currently in
the codebase see [ARCHITECTURE.md](ARCHITECTURE.md).

Audience: Javi (product) + me (Claude across sessions).

---

## Now — v0.2 in progress

| ID | Item | Status |
|---|---|---|
| A | `send_message` outbound messaging | ✅ shipped (commit 6e31ace) |
| B | Interactive browser (Playwright) | ✅ shipped (v0.2.16) |
| C | OpenAI Codex provider (ChatGPT subscription auth) | ❌ rejected — ToS violation, see "Principles" |
| D | Vision (`read_image`) | ✅ shipped (v0.2.4) |
| E | Multi-profile CLI | ✅ shipped (commit 630f97c) |
| F | Gateway workspace validation | ✅ shipped (commit 04bdaba) |
| G | Terminal + code execution OS sandbox | ✅ shipped opt-in/experimental (commit e78b428) |
| H | Home Assistant integration | ⏸ blocked on user confirmation |
| I | MCP client | ✅ shipped (commit 0d376ac) |
| J | Anti-bot browsing (camoufox) | 🔵 backlog — depends on B |
| K | Scroll resilience under heavy streaming | ✅ shipped (commit 9ed4139 — `VerticalScroll.anchor()`) |
| L | Reasoning-as-state (TUI) | ✅ shipped (commits 62f7fa7 + fd1fec4) |
| M | TTS / STT / voice-mode (local-first) | ✅ shipped (v0.2.25, 2 tools + Telegram voice inbound/outbound, no continuous voice mode) |
| N | Image generation | 🔵 backlog — no concrete use case yet |
| R.1 | Research step-counter in state label | ✅ shipped (v0.2.2) |
| R.2 | `delegate` — write-capable sub-agent | ✅ shipped (v0.2.3, named `delegate` not `delegate_task`) |
| R.3 | Batch parallel sub-agents (`tasks[]`) | ✅ shipped (v0.2.18) |
| S | `read_image` auto-resize (cost saver) | ✅ shipped (v0.2.21) |
| T | Gmail API (OAuth2) gateway | ✅ shipped (v0.2.23, 2 commits: T.1 rename + T.2 full Gmail) |
| U | Signal gateway (signal-cli) | 🔵 backlog — requires dedicated phone number |
| V | Anthropic subscription OAuth | ❌ rejected — ToS violation, see "Principles" |
| W | Approval system (dangerous cmd + session allowlist) | 🔵 backlog |
| X | Schedule prompt threat-scan | ✅ shipped (v0.2.20) |
| Y | Tool result budget / truncation | ✅ shipped (v0.2.20) |
| Z | OSV malware check (skills + MCP installers) | ✅ shipped (v0.2.20) |
| Σ.1 | Mixture-of-agents tool (ensemble inference) | 🔵 bola extra — not planned, tracked for later |
| Σ.2 | RL training / fine-tuning hooks | 🔵 bola extra — not planned, tracked for later |

### What's left to call v0.2 done

The minimum-viable shape of v0.2 is what's already shipped. Anything
else listed under "🔵 backlog" can move to v0.3 without blocking
release. The bar for "ship v0.2" is **clean docs + version bump +
real-use validation across a few sessions** — not feature
exhaustiveness.

**Nothing open for v0.2.** Everything the original roadmap promised is shipped. Items still in the backlog — **H** (Home Assistant), **J** (camoufox), **N** (image gen), **U** (Signal), **W** (approval system), **Σ.1/Σ.2** (bola extra) — roll forward to v0.3. **C** (OpenAI Codex OAuth) and **V** (Anthropic OAuth) were rejected on ToS grounds — see Principles section.

Once the v0.3 cycle picks up a few of those + a fresh CHANGELOG
entry summarises v0.2, bump to `v0.3.0` and reopen the table.

---

## Principles

alpi **respects the ToS of every provider it integrates with**. When an LLM vendor (OpenAI, Anthropic, …) offers a paid subscription for a first-party client (ChatGPT Plus/Pro, Claude Pro/Max, Claude Code), that subscription is for THAT client. Reverse-engineering the private OAuth flow of the official CLI to route a third-party agent against the same quota is:

- A clear ToS violation.
- Disrespectful to the vendor's product boundaries.
- Unsafe for users (accounts can be banned; the reversed flow can break any time).

The competitor landscape (hermes, similar third-party agents) routinely ships "Codex OAuth" / "Claude Code OAuth" features. **alpi does not, and will not.** If a vendor publishes an official OAuth-for-third-parties flow in the future (documented, stable, bindable), we adopt it then.

**Practical consequence:** users pay per-token API access through their own keys. That cost is honest and visible. Subscription routing is not on the roadmap.

## Backlog — high value, on deck

### H. Home Assistant integration

Only if Javi runs HA. Hermes has `homeassistant_tool` as reference. Requires `HA_URL` + long-lived token in `.env`. Typical uses: read sensors, toggle lights/scenes, query occupancy. **Waiting on Javi confirming.**

### J. Anti-bot browsing (camoufox)

Firefox fork with C++ fingerprint patches for sites that block plain Chromium even with `playwright-stealth` (Cloudflare Turnstile, DataDome, PerimeterX). Free but heavy: +230MB Firefox binary aside from Playwright's own Chromium, separate Python wrapper, and camoufox periodically breaks when the anti-bot vendors update.

v0.2.16 shipped `playwright-stealth` on by default, which beats ~80% of basic detection (navigator.webdriver, plugins, UA-CH, WebGL vendor overrides). Activate camoufox only when a concrete site breaks through that. Alternatives to consider at that point, in order of effort: manual cookie import (user logs in on their real browser, exports cookies, imports into alpi), `patchright` (newer Chromium-based stealth fork), Browserbase cloud (paid, residential IPs), camoufox.

### N. Image generation

`generate_image(prompt, style)` using the active vision model or a dedicated endpoint (DALL-E, SD). Useful for "hazme un logo rápido". Low priority unless a concrete use case appears.

## Next — v0.3 planned



### U. Signal gateway (signal-cli)

Signal has the best security posture of any consumer messenger, but integration requires a **dedicated phone number for the bot** (you can't bot your own number — Signal won't allow two sessions simultaneously in a useful way). signal-cli runs as a local daemon exposing an HTTP/JSON-RPC endpoint; we just POST/GET messages.

**Scope.** `alpi/gateway/platforms/signal.py` talking to a locally-running `signal-cli daemon --http 127.0.0.1:…`. First-run: user registers a bot number, follows signal-cli's captcha + SMS verify flow once (`signal-cli -u <num> register`), then `alpi setup → Gateways → Signal` stores the daemon URL + allowlist of sender numbers.

**Estimated LOC:** ~200 (HTTP client + polling loop + send).

**Blocker:** requires extra SIM / VoIP number. Real cost: ~$5/mo (Twilio / JustCall). Nicho unless you want E2EE + self-hosted.

### W. Approval system (dangerous cmd + session allowlist)

Today the `terminal` tool has a static denylist (`_guards.py`) that blocks known-destructive patterns. It's binary: allowed or blocked. Real-world agent runs hit a middle ground — commands that *look* dangerous but are legitimate (`rm -rf node_modules` inside the workspace, `sudo systemctl restart X` on a dev VM). Today those get blocked forever; users would want "yes, approve once for this session."

**Scope.**
- A pattern-based scanner classifies each terminal call as `safe` | `caution` | `dangerous` (reuse patterns from existing `_guards.py`, extend with the hermes list).
- `caution` commands pause with a prompt: `[approve once] [approve for this session] [block]`. Session allowlist stored in-memory, discarded on restart.
- `dangerous` blocked by default; bypassable only with an explicit `--yolo` flag or per-pattern config entry.
- Works consistently in TUI (interactive) and gateway (auto-block if unattended, never auto-approve `dangerous`).

**Estimated LOC:** ~150. Fits naturally alongside the existing sandbox (P — layer 2).

**Design notes (post-hermes research, 2026-04-22).** Hermes' approval (`tools/approval.py`) is our reference: 39 hardcoded regex with human-readable descriptions, 3 scopes (`once`/`session`/`always`), permanent allowlist in config, per-surface defaults. Steal the pattern list + description strings + 3-scope model. Drop hermes' smart-mode LLM approver (unnecessary complexity), dual legacy/new pattern keys (back-compat we don't need — ship clean), triple scanner stack (regex + Tirith + skills-guard; one capa is enough), and activity-heartbeat during blocking (no inactivity watchdog to fight). Design split with sandbox (P): sandbox is automatic boundary (network/FS); approval is user-in-loop for destruction *inside* the allowed scope — complementary, not redundant. Surface defaults: TUI blocking modal with 60s timeout, schedule auto-deny (second layer over existing threat-scan), gateway auto-deny + notify-user-with-blocked-command (no interactive `/approve` flow over Telegram/email in v1 — reply correlation is not worth the LOC; revisit if users ask). YOLO escape: `--yolo` flag or `ALPI_YOLO=1`. Scope v1: only `terminal` tool (biggest blast radius); revisit `write_file` / other tools only if real incidents warrant. Module: single `alpi/tools/_approval.py`, patterns hardcoded, session state in a module-level dict keyed by session id, `always` persisted to `tools.terminal.approval.allowlist: []` in config.yaml.

### Σ.1. Mixture-of-agents (bola extra)

Spawn multiple LLMs on the same prompt, aggregate answers with a final synthesizer. Hermes has this as `mixture_of_agents_tool.py`. Use case: hard decisions where one model is weak and you want "wisdom of crowds" at 3× cost.

Not planned — tracked here because it's a known technique and might become useful if we hit a ceiling on single-model research quality.

### Σ.2. RL training / fine-tuning hooks (bola extra)

Hermes has `rl_training_tool.py` for recording agent runs and building training datasets. If we ever want to fine-tune a smaller local model on your actual conversation patterns, the dataset-collection scaffold would live here.

Not planned. Research-grade, irrelevant for everyday personal use.

---

## Decisions discarded — don't relitigate

- **Go + Bubbletea rewrite.** Rejected.
- **rich.Live + prompt_toolkit inline UI.** Worked but had ceiling (no modals, suspend races). Replaced by Textual.
- **Full Textual app with sidebar + modals + fullscreen chrome** (first attempt). Rolled back as too heavy. Current is mother.py-style minimal.
- **Pending-approval gate for skills.** Tried in v0.1, removed in v0.2 commit 2e67830 ("live-by-default"). Friction outweighed benefit; security scanner is the gate.
- **Workspace wall on file tools.** Removed in v0.2 commit 3e2dc29. Without Layer 2 OS sandbox active, the wall was friction without isolation (terminal escaped it in one tool call). Now file tools follow terminal's posture: shared sensitive-path denylist, no workspace restriction.
- **Pending-approval files** (`pending_skills.md`, `pending_personality.md`). Replaced inline.
- **SQLite state.db.** Plain JSON files scan fast for <1000 sessions.
- **Auto-reflect on Ctrl+C.** Dangerous.
- **duckduckgo-search.** Deprecated → migrated to `ddgs`.
- **Post-session `/reflect` loop.** Tried it — `/reflect` slash + auto-trigger + `alpi/reflect.py` + 2 tests. Removed because Hermes doesn't do post-session reflection either, and the TUI implementation was broken (silenced Console output + `Prompt.ask` blocking the worker). Replaced by hardened system prompt + tool-description rules for inline `memory(add)` + `skill(create)`.
- **Regex-gating shell commands** to enforce sandbox. Too many false positives (legitimate `..`, env-var expansion, command substitution). Real enforcement needs OS-level sandbox (G).
- **`.bak` sibling on every `write_file`.** Tried it, rejected — clutters every directory alpi writes in. Kept only on memory files where it pays off.
- **`alpi setup → Identity` wizard for editing PERSONALITY.md.** Rejected after consideration. The `memory` tool already mutates `PERSONALITY.md` from inside chat, and the LLM captures nuance ("less formal but not jokey; respect my code-switching") that a form can't.
- **WhatsApp gateway.** Meta Business API requires company verification + is expensive; `whatsapp-web.js` / Baileys are reverse-engineered with frequent bans, and the attack surface is catastrophic (a compromised bot leaks every chat). Not worth shipping for a personal agent.
- **Discord gateway.** Bot tokens grant full server access — same blast-radius profile as Telegram with no added value, since Telegram covers the "messaging gateway" role already.
- **Slack gateway.** Enterprise-focused, per-workspace tokens with broad scopes, operationally heavy. No real personal-agent use case.

---

## Done — v0.1 + shipped v0.2 items

### v0.1 (released)

First usable cut. Textual TUI, 3-file memory with two-tier dedup, skill system with pending gate (later removed), workspace sandbox (later removed), `delegate` sub-agent (renamed `research` in v0.2), turn-based session format, interrupt-on-new-input, gateway (Telegram), schedule daemon (cron + once jobs), email tool + gateway channel, MCP client, multi-profile CLI, send_message tool, OS sandbox phase 1 + 2 (terminal denylist + opt-in OS sandbox), config tool + `/new` session.

### v0.2 (in progress — shipped so far)

| Commit | What landed |
|---|---|
| 2e67830 | Skills: unified `skill` tool, subdir contract, live-by-default, path guards |
| 2b73091 | Merge `glob` + `grep` into `search`; fix relative-path resolution |
| 62f7fa7 | TUI: surface inter-tool prose + reasoning tokens in live indicator |
| 3e2dc29 | File tools: drop workspace wall, match terminal's denylist posture |
| 211c022 | Skill tool: `patch`/`view` actions, `state/` subdir, scanner beef-up (~50 patterns) |
| fd1fec4 | TUI: reasoning persists across sessions, `show_reasoning` toggle, tighter layout |
| d2ceb74 | Tools: rename `delegate` → `research`, depth tiers driven by config |
| 4035327 | Skills: auto-inject index into system prompt + render skill name in tool cards |
| 9ed4139 | TUI: theme system + floating panels + anchored scroll + MarkdownStream (v0.2.1) |
| (next)  | Research: prefix inner `emit_state` with `step N/M · …` during tool loop (v0.2.2, R.1) |
| (next)  | `delegate` tool: write-capable sub-agent with file/terminal/web toolsets (v0.2.3, R.2) |
| (next)  | `read_image` tool: vision-capable image analysis, local path + http(s) URL with SSRF guard, SVG, model override (v0.2.4, D) |
| (next)  | `/model` as FloatingPanel (was ModalScreen); startup warn when no usable model; session-only model switch with reload on `/new`; OpenRouter user-driven model history (no catalog fetch); Anthropic/OpenAI fetch live with hardcoded fallback; setup flow polish — custom providers above "add new", active entry in accent, provider order, 3s fetch timeout (v0.2.5) |
| (next)  | `/mcps` panel listing running MCP servers with status and exposed tools (v0.2.6) |
| (next)  | Panel header elevation flips direction in light mode — `$surface-lighten-1` in dark, `$surface-darken-1` in light, so the header always contrasts with the body (v0.2.7) |
| (next)  | `AlpiHeader` responsive — 3 width tiers: wide (≥100) shows full `provider/model` path, medium keeps the short name, narrow (<60) drops the `ctx` label and halves the bar to 5 cells; `│` separators preserved across all tiers (v0.2.8) |
| (next)  | `AlpiTopBar` responsive — narrow (<60) drops `profile` / `workspace` labels, keeps values + `│` separators; matches `AlpiHeader` policy (v0.2.9) |
| (next)  | Drop `questionary`; `menu()` reimplemented directly on `prompt_toolkit` (O). Removes 5 workarounds in `ui.py` (empty qmark, FormattedText close hack, ANSI wipe, close sentinel, style overrides). Dependency gone from `pyproject.toml` (v0.2.10) |
| (next)  | Sandbox polish (P closed): `alpi setup → Sandbox` to toggle per profile, TUI top bar shows `sandbox on/off` next to workspace, `TerminalToolConfig` dataclass for clean `save()` delta, SECURITY.md + CONFIG.md drop "experimental" wording and reposition as "recommended for unattended profiles" (v0.2.11). Default stays `false` — dev workflows vary too much to pick a universal profile; the kill scenario is unattended runs, not interactive chat. |
| (next)  | Rename `alpi` → `alpi` across the codebase: package dir, CLI entrypoint, `~/.alpi` home, `ALPI_*` env vars, TUI brand, prompts, docs, tests. 357 tests green (v0.2.12) |
| (next)  | Remove the `config` tool (199 LOC + 112 LOC of tests). Config surface is now two-channel: `alpi setup` for structured settings (model, gateways, MCP, sandbox) + direct YAML edits for cosmetic knobs (`tui.*`, `max_steps_per_turn`, `poll_interval`, `fallback_models`). The conversational "change the accent to Facebook blue" case wasn't worth the tool-attention budget (v0.2.13) |
| (next)  | `/tools` panel filters out MCP-registered tools (`<server>:<tool>` shape) — they live in `/mcps`. Keeps `/tools` focused on alpi's own surface (v0.2.14) |
| (next)  | `todo` tool: `done: bool` → `status: pending\|in_progress\|completed` with a new `start` action. The description already promised "only ONE in_progress at a time" but the tool had no way to mark it — now the invariant is tool-enforced. Deliberately did not port hermes' IDs, merge mode, dedup, or /compact re-injection (v0.2.15) |
| (next)  | Ollama as a first-class provider (replaces the generic "Custom OpenAI-compatible endpoint" slot). Multiple named servers per profile (`home`, `gpu-box`, remote…), each with its own URL; model id becomes `<server-name>/<model>`. Live listing via `/api/tags` at setup time. Auto-resolves `num_ctx` from `/api/show` on every request so the model sees the full prompt instead of Ollama's 2K default — was the root cause of "never replies" with large system prompts. TUI header reads the resolved ctx as `ctx_window`; cost line hidden when `<= 0` for local models. `providers.custom` deleted entirely — no backwards-compat, no migration. ⚠ known limitation: small Ollama models (<7B) still hallucinate tool names regardless of transport (v0.2.15) |
| (next)  | `browser` tool shipped (B closed). Playwright + Chromium, 9 actions: `navigate`, `snapshot`, `click`, `type`, `scroll`, `press`, `screenshot`, `close`, `logout`. Uses Playwright's native `aria_snapshot()` for LLM-friendly page representation; targets elements by `role` + accessible `name` (or by visible `text`) — robust across re-renders, no fragile CSS selectors. `playwright-stealth` patches applied by default (navigator.webdriver hidden, plugins populated, etc.) so Cloudflare-lite protection doesn't block us. `screenshot` saves a PNG and returns the path; when `tools.browser.vision=true` in the profile's config, passing a `question` auto-chains the screenshot to `read_image` — otherwise path-only with a hint. Per-profile storage at `~/.alpi/profiles/<name>/browser/state.json` so cookies stay isolated across profiles. Single dedicated worker thread (`ThreadPoolExecutor(1)`) funnels every call to Playwright's sync API — sidesteps the "Cannot switch to a different thread" greenlet restriction in the TUI where each turn runs in a fresh Textual worker. SSRF via existing `check_url()`. ~400 LOC vs hermes' 2984 — deliberately dropped multi-provider abstraction, daemon process, `@e1` refs, LLM summarization, JS/console eval, Browserbase/BrowserUse cloud, orphan reaper (v0.2.16) |
| (next)  | `skill(action="validate")` shipped (Q closed). Four cheap correctness checks on a skill's `scripts/*.py`: `py_compile` for syntax, AST-walk + `find_spec` for missing third-party imports, OAuth race pattern (`webbrowser.open` before `serve_forever`/`handle_request`), and port coherence between `localhost:NNNN` mentioned in `SKILL.md` and `bind()` calls in code. Non-blocking — reports findings so the LLM decides what to do. ~150 LOC in `_skill_validate.py`. Did not port the 65-regex security scanner from hermes (we already had our own), nor the LLM-as-reviewer pattern (overlaps with asking alpi in chat "revisa esta skill") (v0.2.17) |
| (next)  | Batch parallel sub-agents shipped (R.3 closed). `research` and `delegate` now accept `tasks: [...]` (up to 3) and run them concurrently via `ThreadPoolExecutor(max_workers=3)`. Results aggregate into one report with per-task sections; failures are captured inline instead of short-circuiting the batch. Prerequisite: `alpi/tools/_state.py` refactored from module-global `_emit`/`_interrupt_getter`/`_usage_sink` to `contextvars.ContextVar`, so two workers can have distinct emit callbacks without racing. Worker threads re-seed `interrupt_getter` + `usage_sink` from the parent context (Python's `ThreadPoolExecutor` does not auto-propagate ContextVars) and install a per-task prefixed `emit`. Existing callers unchanged — the public API is identical; only `research.py` and `delegate.py` added `get_emit()` instead of reading `_emit` directly (v0.2.18) |
| (next)  | Roadmap sweep: extended backlog with 9 new items (TTS/STT local, Gmail OAuth, Signal, Anthropic OAuth as ToS-gray, approval system, schedule threat-scan, tool budget, OSV malware, bola extra). Discarded WhatsApp/Discord/Slack with rationale (v0.2.19) |
| (next)  | Security hardening pack — three items shipped together (Y + Z + X, ~200 LOC): (1) **Tool result budget** in `alpi/tools/_budget.py` — `tools.budget.per_result_chars: 100_000` default, per-tool override via `tools.<name>.max_result_chars` (e.g. `-1` for unlimited on `read_file`), replaces the three hardcoded `[:10_000]` sites across engine/research/delegate with a clean elided suffix; (2) **OSV malware check** in `alpi/tools/_osv.py` — `api.osv.dev` query on skill `scripts/*.py` imports and MCP `npx` args at save time, blocks on MAL-* findings, fails open on network errors; (3) **Schedule prompt threat-scan** — reuses `scan_skill_body` patterns at both save and fire time so prompt-injected cron jobs don't escape into unattended runs. 17 new tests, 402 green total (v0.2.20) |
| (next)  | `read_image` auto-resize shipped (S closed). Pillow added as main dep (~3 MB). When `tools.read_image.auto_resize` (default `true`), any input image with a longer edge over `tools.read_image.max_edge` (default 1568 px — matches Anthropic's recommendation) is downscaled before base64-encoding. Aspect ratio preserved; PNGs with alpha stay PNG; everything else round-trips through JPEG q=85; SVG passthrough. Proactive (vs hermes' reactive "resize after API rejects too-large"). Typical saving: ~9× input-token cost on a 4K screenshot. 7 new tests, 409 green (v0.2.21) |
| (next)  | T.1 — rename `email` → `mail/imap` in preparation for a second backend. Pure refactor, no behaviour change. Classes `EmailClient`/`EmailError` → `ImapClient`/`ImapError`; gateway platform class `Email` → `Imap`; config `gateway.email.*` → `gateway.imap.*`; env vars `EMAIL_*` → `IMAP_*`/`SMTP_*`. Setup menu: "Email" → "IMAP". Tool name `email` kept (user-facing concept, backend-agnostic) (v0.2.22) |
| (next)  | T.2 — Gmail API (OAuth2) as a first-class parallel backend (T closed). `alpi/mail/gmail.py` implements the same 9 operations as `ImapClient` (list/search/read/send/reply/forward/move/delete/download_attachment) against `gmail.googleapis.com` with scopes `gmail.modify` + `gmail.send`. OAuth2 Authorization Code + PKCE with loopback callback server; refresh tokens stored per profile under `~/.alpi/<profile>/gmail_token.json` (0600, `fcntl`-locked). New `alpi/gateway/platforms/gmail.py` polls via `users.history.list` for delta-only fetches (no inbox rescans). Tool `email` gains an `account` param: auto-picks the only configured backend, demands explicit choice when both IMAP and Gmail are set. `send_message` platform enum grows `gmail`; delivery `_allowlist_env` maps gmail → `GMAIL_ALLOWED_SENDERS`. Setup wizard "Gateways → Gmail" walks through the GCP OAuth setup in 4 compact steps. Seed `.env.example` gains `GMAIL_CLIENT_ID` / `GMAIL_CLIENT_SECRET` / `GMAIL_ALLOWED_SENDERS`. Two post-landing correctness fixes: (a) `_list_history` no longer filters by `labelId: INBOX` — Gmail filter rules can route mail straight to custom labels (skipping INBOX), and those must still trigger alpi; SPAM/TRASH/DRAFT/CHAT/SENT excluded at processing time instead (matches IMAP's "only skip Junk" semantics); (b) `mark_as_read` moved from platform `listen()` to `run.py` post-allowlist via a new `IncomingMessage.ack` callback — previously automated/bulk and disallowed senders got `\Seen` / UNREAD removed without being processed, touching unrelated inbox traffic. 16 new tests (10 Gmail client + 6 dispatch). 425 green total (v0.2.23) |
| (next)  | M — voice shipped as two tools + Telegram inbound/outbound, no continuous voice mode. **tts** (`alpi/tools/tts.py`) wraps Edge TTS (Microsoft Neural voices, free, no API key); autoplays locally when `tools.tts.autoplay` on (default). Format auto-picked: MP3 in TUI, OGG/Opus on gateway (`ALPI_GATEWAY=1` subprocess env) for Telegram voice-note compatibility — MP3 is synthesised first and autoplayed (afplay decodes Opus badly), then ffmpeg-converted to OGG. Tool params: `text`, `voice`; `rate`/`pitch` are config-only (`tools.tts.{rate,pitch}`) to keep the LLM from fiddling with prosody every turn. 1000-char hard cap. Cache keyed by hash-of(voice, rate, pitch, format, text) under `~/.alpi/cache/tts/`. **stt** (`alpi/tools/stt.py`) wraps faster-whisper on CPU; spawns a subprocess per call to avoid `bad value(s) in fds_to_keep` when ctranslate2 forks under the Textual TUI's fd-munged event loop. Model (`tiny`/`base`/`small`/`medium`/`large-v3`) downloaded on first call into `~/.cache/huggingface/`. **send_message** grew an `attachment` param; Telegram platform picks the right endpoint by extension (`sendVoice` for `.ogg`, `sendAudio` for `.mp3`, etc.). **Telegram inbound voice notes** auto-transcribe: gateway downloads via `getFile`, caches under `~/.alpi/cache/inbound/`, runs `stt`, feeds `[voice note] <transcript>` as a normal text turn. Surface tag `[INBOUND TELEGRAM from <id>]` prepended so the LLM knows to chain `send_message(attachment=…)` when asked to deliver audio back. Engine post-processor `_strip_cache_noise` in `alpi/engine.py` filters lines containing `.alpi/cache/(tts|stt)/` from the assistant's final text so weak models (mimo-v2-flash parrots + hallucinates paths) can't leak the cache path into replies; TUI re-renders the `AssistantMessage` markdown with the cleaned buffer on `assistant_done`. Deliberately dropped vs hermes's 3050 LOC voice stack: continuous voice mode, streaming TTS, silence/VAD state machine, whisper-hallucination regex filter, 6 extra TTS providers, auxiliary LLM smart approval. 31 new tests (tts, stt, send_message attachment, telegram voice inbound, engine strip-cache). 458 green total (v0.2.25) |

| (next)  | Three tidy-ups bundled. (1) MCP tool-name OpenAI compatibility: MCP-exposed tools were named `<server>:<tool>` (e.g. `github:create_issue`), but OpenAI rejects any function name outside `^[a-zA-Z0-9_-]+$` — every OpenAI turn with MCP servers loaded crashed with `Invalid tools[N].function.name`. Anthropic/OpenRouter silently accepted the colon so the bug hid until an OpenAI model was picked. Switched separator to `__` (`github__create_issue`), sanitise server + tool names to collapse any other illegal char to `_`. (2) OpenAI + Anthropic provider lists curated manually instead of live-fetched from `/models` — raw catalogs include dozens of embeddings, TTS, moderation, and legacy variants that were never going to work as an agent brain, and the wizard scrolled forever. Dropped `_fetch()` + `_EXCLUDE_PREFIXES` in favour of a 5-model OpenAI list (`gpt-5.4` flagship, `gpt-5.4-mini` balanced, `gpt-5.4-nano` cheap, `gpt-5.3-codex` coding, `o3` heavy reasoning) and 4-model Anthropic list (`claude-opus-4-7` flagship, `claude-opus-4-6` 1M ctx, `claude-sonnet-4-6` balanced, `claude-haiku-4-5` fast). Each entry carries a short role tag rendered in the two-column setup wizard. Custom model id is still one click away for previews or anything not in the shortlist. Groq + Google were already curated. (3) Context window resolution: the TUI's header used to hardcode 200k for any non-Ollama model, which both under-reports (`gpt-5.4` is 1.05M, Claude 4.7 is 1M) and over-reports (`gpt-4o` is 128k). `_resolve_ctx_window` now probes `litellm.model_cost` after the Ollama branch — litellm ships an up-to-date cost/context DB for every mainstream provider, so we get accurate bars without maintaining a map in-repo. Ollama stays on its own `/api/show` path (local-only). Tests updated (v0.2.26) |

| (next)  | Brand cleanup across ~130 files. The Python package, binary, and home dir were already `alpi`, but the old nickname leaked everywhere — CLI help text, wizard banner titles, logger names, systemd/launchd service labels, User-Agent headers, tempfile prefixes, widget class names (`AlpiApp`, `AlpiHeader`, `AlpiTopBar`), function locals (`_locate_*`, `*_bin`, `*_home`), env vars (`ALPI_HOME`, `ALPI_PROFILE`, `ALPI_BIN`), shell aliases, docstrings, and docs. Rename staged in three regex passes: word-boundary, punctuated (`-`, `.`, `/`, `:`), and identifier-fragment (`_X_`, uppercase `X_`, capitalised `X`). Local git dir `~/git/alf/` kept intact (personal convention). 458 tests green (v0.2.27) |

| (next)  | tts autoplay skipped on gateway. Before, autoplay fired on every call — fine in TUI where the speaker is right there, but in gateway context the agent usually replies to a user who is on their phone, not sitting next to the Mac. Audio played through the server speakers reaches nobody and can interrupt anyone else in earshot. Autoplay now runs only when `ALPI_GATEWAY` is unset. Voice-note delivery to Telegram via `send_message(attachment=…)` is the real channel; the user taps play on their device. Also simplified the synthesis flow: MP3 for TUI (afplay-native) or OGG via ffmpeg for gateway (Telegram `sendVoice` needs Opus). Dropped the previous "synthesise MP3 first so autoplay has something afplay can decode, then convert to OGG for delivery" gymnastics — no longer needed now that gateway never autoplays. 458 tests green (v0.2.28) |

| (next)  | ToS stance codified. Removed **C** (OpenAI Codex OAuth against the private ChatGPT backend) and **V** (Anthropic Claude Pro/Code OAuth) from the backlog, marked both as rejected in the table. Added a "Principles" section to ROADMAP + README: alpi does not reverse-engineer the private OAuth flows that ChatGPT / Claude Code use for their official clients. Competitor agents (hermes, similar) ship these features; we do not. Users pay per-token API access through their own keys — honest + visible. If a vendor publishes an official OAuth-for-third-parties flow, we adopt it then. (v0.2.29) |

| (next)  | `allow_network=false` now blocks Python-native network tools too, not just the terminal subprocess. Before, toggling off `allow_network` only denied sockets to the shell sandbox (sandbox-exec / bwrap); `web_fetch`, `web_search`, `web_extract`, `browser`, `tts`, `send_message`, `email`, and URL-mode `read_image` all still reached out freely. That was semantically confusing — "network off" is meant to mean off, not "off for shell, on for everything else". Added `require_network(tool_name)` helper in `alpi/tools/_sandbox.py` that reads `tools.terminal.{sandbox,allow_network}` directly from `config.yaml` (no `load_dotenv` side effects that poisoned test env). Each network-using tool checks at entry and refuses with a clear error citing the config key. LLM transport (litellm) and gateway inbound listeners stay exempt — the LLM is the agent's brain and inbound is not exfiltration. TUI top bar now renders `offline` instead of `sandbox` when network is locked (muted style, no icons) so unattended profiles are auditable at a glance. 458 tests green (v0.2.30) |

| (next)  | TopBar shows the active profile's disk footprint next to its name (e.g. `profile default 2.8MB`). `~/.alpi/` for the default profile (with the `profiles/` subtree excluded so it doesn't double-count sibling profiles); `~/.alpi/profiles/<name>/` otherwise. `rglob`-based walk with 30 s cache; recomputed on profile / workspace / model changes. Hidden in narrow mode (< 60 columns). Useful hook for the planned cleanup wizard (reveal which profile has ballooned). Also documented alpi TUI's features/design choices in CONFIG.md — Textual vs hermes's prompt_toolkit CLI + separate Ink.js TUI, streaming markdown, tool cards with live state, inline reasoning tail, auto-suggest slash commands, responsive collapse, scroll anchoring. 458 tests green (v0.2.31) |
