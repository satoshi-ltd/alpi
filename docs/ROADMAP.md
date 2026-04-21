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
| C | OpenAI Codex provider (ChatGPT subscription auth) | 🔵 backlog — see below |
| D | Vision (`read_image`) | ✅ shipped (v0.2.4) |
| E | Multi-profile CLI | ✅ shipped (commit 630f97c) |
| F | Gateway workspace validation | ✅ shipped (commit 04bdaba) |
| G | Terminal + code execution OS sandbox | ✅ shipped opt-in/experimental (commit e78b428) |
| H | Home Assistant integration | ⏸ blocked on user confirmation |
| I | MCP client | ✅ shipped (commit 0d376ac) |
| J | Anti-bot browsing (camoufox) | 🔵 backlog — depends on B |
| K | Scroll resilience under heavy streaming | ✅ shipped (commit 9ed4139 — `VerticalScroll.anchor()`) |
| L | Reasoning-as-state (TUI) | ✅ shipped (commits 62f7fa7 + fd1fec4) |
| M | TTS / STT / voice-mode (local-first) | 🔵 backlog — opt-in, ⏸ pending user confirmation |
| N | Image generation | 🔵 backlog — no concrete use case yet |
| R.1 | Research step-counter in state label | ✅ shipped (v0.2.2) |
| R.2 | `delegate` — write-capable sub-agent | ✅ shipped (v0.2.3, named `delegate` not `delegate_task`) |
| R.3 | Batch parallel sub-agents (`tasks[]`) | ✅ shipped (v0.2.18) |
| T | Gmail API (OAuth2) gateway | 🔵 backlog — replaces IMAP as app-passwords sunset |
| U | Signal gateway (signal-cli) | 🔵 backlog — requires dedicated phone number |
| V | Anthropic subscription OAuth | 🔵 backlog — ToS-gray, wait for official |
| W | Approval system (dangerous cmd + session allowlist) | 🔵 backlog |
| X | Schedule prompt threat-scan | 🔵 backlog |
| Y | Tool result budget / truncation | 🔵 backlog |
| Z | OSV malware check (skills + MCP installers) | 🔵 backlog |
| Σ.1 | Mixture-of-agents tool (ensemble inference) | 🔵 bola extra — not planned, tracked for later |
| Σ.2 | RL training / fine-tuning hooks | 🔵 bola extra — not planned, tracked for later |

### What's left to call v0.2 done

The minimum-viable shape of v0.2 is what's already shipped. Anything
else listed under "🔵 backlog" can move to v0.3 without blocking
release. The bar for "ship v0.2" is **clean docs + version bump +
real-use validation across a few sessions** — not feature
exhaustiveness.

**Nothing open for v0.2.** Everything the original roadmap promised is shipped. Items still in the backlog — **C** (Codex OAuth), **H** (Home Assistant), **J** (camoufox), **M** (voice), **N** (image gen), **S** (read_image auto-resize), **T** (Gmail OAuth), **U** (Signal), **V** (Anthropic OAuth — ToS gray), **W** (approval system), **X** (schedule threat-scan), **Y** (tool budget), **Z** (OSV malware), **Σ.1/Σ.2** (bola extra) — roll forward to v0.3.

Once the v0.3 cycle picks up a few of those + a fresh CHANGELOG
entry summarises v0.2, bump to `v0.3.0` and reopen the table.

---

## Backlog — high value, on deck

### C. OpenAI Codex provider (ChatGPT subscription auth)

Today alf goes through LiteLLM with API keys → OpenAI is metered per token. Hermes supports a second path: OAuth device-code against the user's ChatGPT Plus/Pro account, using the same endpoints the official Codex CLI uses. Already-paid quota instead of metered tokens.

**Mechanics (reverse-engineered, not a public OpenAI API):**

1. **Auth** — OAuth2 device code against `auth.openai.com` with the Codex CLI's public `client_id` (`app_EMoamEEZ73f0CkXaXp7hrann`). User opens URL + types code → poll → `access_token` + `refresh_token`. Reference: `~/git/hermes-agent/hermes_cli/auth.py:2999-3119` (`_codex_device_code_login`) and `:1615-1675` (`resolve_codex_runtime_credentials`).
2. **Storage** — `~/.alpi/auth.json` with `fcntl` file lock (gateway + TUI + schedule daemon must not race on refresh). Refresh 120s before expiry; on 401 force-refresh + retry once.
3. **Endpoint** — `https://chatgpt.com/backend-api/codex` (NOT `api.openai.com`).
4. **Wire protocol** — Responses API with event streaming (`client.responses.stream(...)`), not chat/completions. **LiteLLM does not cover this cleanly** → bypass LiteLLM, use the OpenAI SDK directly. Reference: `~/git/hermes-agent/run_agent.py:4592` (`_run_codex_stream`).

**Implementation shape:**

- `alpi/auth/codex.py` — port from Hermes: `device_code_login()`, `resolve_runtime_credentials(force_refresh, refresh_skew)`, locked R/W of `auth.json`.
- `alpi/providers/openai_codex.py` — new `Provider` subclass with `auth_type = "oauth_external"`, lists gpt-5 family.
- `alpi/llm.py` — add a transport dispatch: when model id prefix is `openai-codex/`, resolve credentials and call `openai.OpenAI(...).responses.stream(...)` instead of `litellm.completion`. Normalise the event stream (`response.output_item.added` with `type=function_call`, etc.) into the same `{text_delta, tool_calls_delta, finish_reason}` shape `stream()` already yields.
- CLI: `alpi auth openai-codex [login|logout|status]`.

**Effort.** 1-2 days. Auth module is almost a literal port. The unknown is event-stream normalisation — Responses API emits a richer set of events than chat/completions.

**Risks.**

- **ToS grey area.** `chatgpt.com/backend-api/codex` is not a public, bindable-by-third-parties API. OpenAI can rotate the `client_id`, filter by User-Agent, or tighten the device flow at any moment. Acceptable for personal use; NOT acceptable for hosted/shared deployment.
- **Two transports.** `engine.py` gets a second code path; contain it behind a `Transport` protocol so dispatch happens once in `llm.py`, not sprinkled.
- **Token liveness across processes.** Gateway / TUI / schedule each open `auth.json` independently. The lock prevents torn writes but not stale reads — every transport call must re-resolve credentials.

**Ship order.** Auth + CLI first (testable standalone). Then provider + transport dispatch. Then end-to-end smoke with real `gpt-5` through the agent loop.

### H. Home Assistant integration

Only if Javi runs HA. Hermes has `homeassistant_tool` as reference. Requires `HA_URL` + long-lived token in `.env`. Typical uses: read sensors, toggle lights/scenes, query occupancy. **Waiting on Javi confirming.**

### J. Anti-bot browsing (camoufox)

Firefox fork with C++ fingerprint patches for sites that block plain Chromium even with `playwright-stealth` (Cloudflare Turnstile, DataDome, PerimeterX). Free but heavy: +230MB Firefox binary aside from Playwright's own Chromium, separate Python wrapper, and camoufox periodically breaks when the anti-bot vendors update.

v0.2.16 shipped `playwright-stealth` on by default, which beats ~80% of basic detection (navigator.webdriver, plugins, UA-CH, WebGL vendor overrides). Activate camoufox only when a concrete site breaks through that. Alternatives to consider at that point, in order of effort: manual cookie import (user logs in on their real browser, exports cookies, imports into alpi), `patchright` (newer Chromium-based stealth fork), Browserbase cloud (paid, residential IPs), camoufox.

### N. Image generation

`generate_image(prompt, style)` using the active vision model or a dedicated endpoint (DALL-E, SD). Useful for "hazme un logo rápido". Low priority unless a concrete use case appears.

### M. TTS / STT / voice-mode (local-first, opt-in)

Hermes ships ~3000 LOC of voice (7 TTS providers, 3 STT tiers, full voice-mode). Too thick for alpi. Scope for us:

- **TTS:** two providers only — Edge TTS (free online, zero setup) and NeuTTS (local, subprocess isolation so the 500MB model doesn't bloat alpi's RAM, supports voice cloning from a reference audio). Config knob `tools.voice.tts_provider: edge|neutts`.
- **STT:** `faster-whisper` local, no cloud. Small model (base) by default, configurable. No Groq/OpenAI fallback — if local fails we fail explicitly.
- **Voice mode:** push-to-talk only (no wake-word). Activated with `alpi --voice` or `/voice` slash in TUI. Mic → STT → LLM → TTS → speaker. Never always-listening.

**Real-world applications** (why ship this at all):
- Cooking, driving, DIY, walking — hands-busy scenarios where the TUI is unusable.
- Dictating quick thoughts to memory while multitasking.
- Sick-in-bed / accessibility.

**Out of scope:** wake-word, continuous ambient listening, multi-voice synthesis, phone-mode (mic+speaker on separate hardware). Keep it simple.

**Estimated LOC:** ~250 for the full pipeline (TTS dispatcher + STT wrapper + voice-mode loop + config).

---

## Next — v0.3 planned

### S. `read_image` auto-resize (cost saver)

Vision-model cost scales with image resolution: a 4K screenshot costs ~9× more tokens than its 1K version for the same content. Right now `read_image` sends the original bytes to the LLM, so a photo of a receipt at phone-native resolution burns tokens that contribute nothing to the answer.

**Scope.** Add Pillow as a main dependency (~3 MB). Add `tools.read_image.auto_resize: true` to config (default on). When set, downscale any image whose longer edge exceeds a target (Anthropic recommends ~1568px, which also matches OpenAI's 512/768/2048 tile grid well) before base64-encoding. Preserve aspect ratio, reuse format where possible (RGBA→RGB for JPEG), JPEG quality 85.

**Why not in v0.2.** Adding Pillow as a required dep + config knob + resize logic + tests is a non-trivial chunk for what is an optimisation, not a correctness fix. Users with 4K screenshots pay more tokens; that's it. Ship when we have a real "this is getting expensive" signal from usage.

**Reference.** Hermes' `_resize_image_for_vision` in `tools/vision_tools.py` does a reactive version (resize only after the API rejects with "too large"); our take would be proactive (resize any time we could).

### T. Gmail API (OAuth2) gateway

IMAP + app-specific-passwords is deprecated on Google (new tenants can't generate them; existing ones get pressure to migrate). A Gmail API channel gives us scoped OAuth (`gmail.send` alone, or `gmail.readonly`), no password storage, revocable per-app from the user's Google account settings.

**Scope.** Parallel channel to the existing IMAP/SMTP gateway — does not replace it. New `alpi/gateway/platforms/gmail.py` + OAuth callback server (ephemeral localhost port) for the install flow, refresh token stored in `~/.alpi/profiles/<name>/auth/gmail.json` with `fcntl` lock. First-run: `alpi setup → Gateways → Gmail` opens a browser for consent. Inbound polling via `users.messages.list` with `is:unread` filter. Outbound via `users.messages.send`.

**Estimated LOC:** ~300. Dep: `google-api-python-client` + `google-auth-oauthlib` (~2 MB combined).

### U. Signal gateway (signal-cli)

Signal has the best security posture of any consumer messenger, but integration requires a **dedicated phone number for the bot** (you can't bot your own number — Signal won't allow two sessions simultaneously in a useful way). signal-cli runs as a local daemon exposing an HTTP/JSON-RPC endpoint; we just POST/GET messages.

**Scope.** `alpi/gateway/platforms/signal.py` talking to a locally-running `signal-cli daemon --http 127.0.0.1:…`. First-run: user registers a bot number, follows signal-cli's captcha + SMS verify flow once (`signal-cli -u <num> register`), then `alpi setup → Gateways → Signal` stores the daemon URL + allowlist of sender numbers.

**Estimated LOC:** ~200 (HTTP client + polling loop + send).

**Blocker:** requires extra SIM / VoIP number. Real cost: ~$5/mo (Twilio / JustCall). Nicho unless you want E2EE + self-hosted.

### V. Anthropic subscription OAuth (ToS-gray)

Anthropic does not offer a public OAuth flow against Claude Pro/Max/Team quotas. Claude Code CLI uses a private OAuth against `claude.ai` but it's baked into the official client — not advertised as a bindable API. Reverse-engineering the flow is technically feasible (client_id discovery, device-code poll, session token) but:

- **ToS grey**: Anthropic can (and will, if pattern detected) revoke the reverse-engineered client_id. Same category as hermes' Codex path.
- **Value only if you already pay Pro/Max**: otherwise you still pay API tokens, just via a different endpoint.
- **Breakage risk is permanent**: every Anthropic update can invalidate the flow.

**Do not ship until Anthropic offers an official OAuth.** Documented here so nobody spends a sprint on it without reading this warning first. If it ever becomes officially supported, the implementation mirrors C (OpenAI Codex): `alpi/auth/anthropic.py` with device-code login, `alpi/providers/anthropic_oauth.py` as a second provider subclass, transport dispatch in `llm.py` when model prefix is `anthropic-oauth/…`.

### W. Approval system (dangerous cmd + session allowlist)

Today the `terminal` tool has a static denylist (`_guards.py`) that blocks known-destructive patterns. It's binary: allowed or blocked. Real-world agent runs hit a middle ground — commands that *look* dangerous but are legitimate (`rm -rf node_modules` inside the workspace, `sudo systemctl restart X` on a dev VM). Today those get blocked forever; users would want "yes, approve once for this session."

**Scope.**
- A pattern-based scanner classifies each terminal call as `safe` | `caution` | `dangerous` (reuse patterns from existing `_guards.py`, extend with the hermes list).
- `caution` commands pause with a prompt: `[approve once] [approve for this session] [block]`. Session allowlist stored in-memory, discarded on restart.
- `dangerous` blocked by default; bypassable only with an explicit `--yolo` flag or per-pattern config entry.
- Works consistently in TUI (interactive) and gateway (auto-block if unattended, never auto-approve `dangerous`).

**Estimated LOC:** ~150. Fits naturally alongside the existing sandbox (P — layer 2).

### X. Schedule prompt threat-scan

Cron jobs run unattended with full tool access. A prompt-injected email or a skill that silently mutates its trigger could insert exfiltration instructions that nobody sees until after the fact. Scan the scheduled prompt at save time AND at fire time for:

- Known injection patterns (ignore previous / override system / disregard rules).
- Exfil markers (URL with `?data=`, `$ENV_VAR` referencing secrets).
- Invisible Unicode.

Refuse to save if found; on fire-time hit, log + skip. ~50 LOC — reuses the existing `scan_skill_body` patterns.

### Y. Tool result budget / truncation

Today a `read_file` on a 5 MB log, or a `web_fetch` on a giant HTML page, dumps the raw payload into context and can single-handedly blow up a turn. Hermes has a 3-tier budget (per-result char cap, per-turn budget, inline preview of N chars) that prevents this.

**Scope.**
- `tools.budget.per_result_chars: 100_000` (default). If exceeded, truncate with `… [N chars elided]` suffix.
- `tools.budget.per_turn_chars: 200_000` (default). Summed across all tool returns in one turn; if exceeded, subsequent calls get shorter truncation.
- Per-tool override via `tools.<name>.max_result_chars`: e.g. set `read_file` to `∞` (no cap) so the LLM can pull the raw source when it explicitly wants to.
- Inline preview in the TUI tool card (first 1.5K chars) — already mostly there, formalise it.

~100 LOC in a new `alpi/tools/_budget.py`, wired into `execute()` in `tools/__init__.py`.

### Z. OSV malware check (skills + MCP installers)

When a skill's `scripts/*.py` imports a third-party package, or an MCP server spec runs `npx -y <pkg>` / `uvx <pkg>`, we're one typo away from installing a name-squatted malicious package. Google's OSV database has an up-to-date MAL-* feed (confirmed malicious packages, not just CVEs).

**Scope.** At the moment a skill is `create`d or an MCP server is added, scan: extract package names from `scripts/*.py` imports, from MCP `args` (`-y @foo/bar`), and from `requirements.txt` if present. POST to `https://api.osv.dev/v1/query` for each with ecosystem=`PyPI|npm`. If any response contains `id` starting with `MAL-`, refuse to save (or refuse to install) and surface the advisory URL.

Fail-open: if OSV is unreachable, proceed with a warning. Don't block on network issues — that's a worse UX than the risk the check covers.

**Estimated LOC:** ~50. Dep: none (just httpx which is already present).

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
- **Post-session `/reflect` loop.** Tried it — `/reflect` slash + auto-trigger + `alf/reflect.py` + 2 tests. Removed because Hermes doesn't do post-session reflection either, and the TUI implementation was broken (silenced Console output + `Prompt.ask` blocking the worker). Replaced by hardened system prompt + tool-description rules for inline `memory(add)` + `skill(create)`.
- **Regex-gating shell commands** to enforce sandbox. Too many false positives (legitimate `..`, env-var expansion, command substitution). Real enforcement needs OS-level sandbox (G).
- **`.bak` sibling on every `write_file`.** Tried it, rejected — clutters every directory alf writes in. Kept only on memory files where it pays off.
- **`alf setup → Identity` wizard for editing PERSONALITY.md.** Rejected after consideration. The `memory` tool already mutates `PERSONALITY.md` from inside chat, and the LLM captures nuance ("less formal but not jokey; respect my code-switching") that a form can't.
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
| (next)  | `AlfHeader` responsive — 3 width tiers: wide (≥100) shows full `provider/model` path, medium keeps the short name, narrow (<60) drops the `ctx` label and halves the bar to 5 cells; `│` separators preserved across all tiers (v0.2.8) |
| (next)  | `AlfTopBar` responsive — narrow (<60) drops `profile` / `workspace` labels, keeps values + `│` separators; matches `AlfHeader` policy (v0.2.9) |
| (next)  | Drop `questionary`; `menu()` reimplemented directly on `prompt_toolkit` (O). Removes 5 workarounds in `ui.py` (empty qmark, FormattedText close hack, ANSI wipe, close sentinel, style overrides). Dependency gone from `pyproject.toml` (v0.2.10) |
| (next)  | Sandbox polish (P closed): `alf setup → Sandbox` to toggle per profile, TUI top bar shows `sandbox on/off` next to workspace, `TerminalToolConfig` dataclass for clean `save()` delta, SECURITY.md + CONFIG.md drop "experimental" wording and reposition as "recommended for unattended profiles" (v0.2.11). Default stays `false` — dev workflows vary too much to pick a universal profile; the kill scenario is unattended runs, not interactive chat. |
| (next)  | Rename `alf` → `alpi` across the codebase: package dir, CLI entrypoint, `~/.alpi` home, `ALPI_*` env vars, TUI brand, prompts, docs, tests. 357 tests green (v0.2.12) |
| (next)  | Remove the `config` tool (199 LOC + 112 LOC of tests). Config surface is now two-channel: `alpi setup` for structured settings (model, gateways, MCP, sandbox) + direct YAML edits for cosmetic knobs (`tui.*`, `max_steps_per_turn`, `poll_interval`, `fallback_models`). The conversational "change the accent to Facebook blue" case wasn't worth the tool-attention budget (v0.2.13) |
| (next)  | `/tools` panel filters out MCP-registered tools (`<server>:<tool>` shape) — they live in `/mcps`. Keeps `/tools` focused on alpi's own surface (v0.2.14) |
| (next)  | `todo` tool: `done: bool` → `status: pending\|in_progress\|completed` with a new `start` action. The description already promised "only ONE in_progress at a time" but the tool had no way to mark it — now the invariant is tool-enforced. Deliberately did not port hermes' IDs, merge mode, dedup, or /compact re-injection (v0.2.15) |
| (next)  | Ollama as a first-class provider (replaces the generic "Custom OpenAI-compatible endpoint" slot). Multiple named servers per profile (`home`, `gpu-box`, remote…), each with its own URL; model id becomes `<server-name>/<model>`. Live listing via `/api/tags` at setup time. Auto-resolves `num_ctx` from `/api/show` on every request so the model sees the full prompt instead of Ollama's 2K default — was the root cause of "never replies" with large system prompts. TUI header reads the resolved ctx as `ctx_window`; cost line hidden when `<= 0` for local models. `providers.custom` deleted entirely — no backwards-compat, no migration. ⚠ known limitation: small Ollama models (<7B) still hallucinate tool names regardless of transport (v0.2.15) |
| (next)  | `browser` tool shipped (B closed). Playwright + Chromium, 9 actions: `navigate`, `snapshot`, `click`, `type`, `scroll`, `press`, `screenshot`, `close`, `logout`. Uses Playwright's native `aria_snapshot()` for LLM-friendly page representation; targets elements by `role` + accessible `name` (or by visible `text`) — robust across re-renders, no fragile CSS selectors. `playwright-stealth` patches applied by default (navigator.webdriver hidden, plugins populated, etc.) so Cloudflare-lite protection doesn't block us. `screenshot` saves a PNG and returns the path; when `tools.browser.vision=true` in the profile's config, passing a `question` auto-chains the screenshot to `read_image` — otherwise path-only with a hint. Per-profile storage at `~/.alpi/profiles/<name>/browser/state.json` so cookies stay isolated across profiles. Single dedicated worker thread (`ThreadPoolExecutor(1)`) funnels every call to Playwright's sync API — sidesteps the "Cannot switch to a different thread" greenlet restriction in the TUI where each turn runs in a fresh Textual worker. SSRF via existing `check_url()`. ~400 LOC vs hermes' 2984 — deliberately dropped multi-provider abstraction, daemon process, `@e1` refs, LLM summarization, JS/console eval, Browserbase/BrowserUse cloud, orphan reaper (v0.2.16) |
| (next)  | `skill(action="validate")` shipped (Q closed). Four cheap correctness checks on a skill's `scripts/*.py`: `py_compile` for syntax, AST-walk + `find_spec` for missing third-party imports, OAuth race pattern (`webbrowser.open` before `serve_forever`/`handle_request`), and port coherence between `localhost:NNNN` mentioned in `SKILL.md` and `bind()` calls in code. Non-blocking — reports findings so the LLM decides what to do. ~150 LOC in `_skill_validate.py`. Did not port the 65-regex security scanner from hermes (we already had our own), nor the LLM-as-reviewer pattern (overlaps with asking alpi in chat "revisa esta skill") (v0.2.17) |
| (next)  | Batch parallel sub-agents shipped (R.3 closed). `research` and `delegate` now accept `tasks: [...]` (up to 3) and run them concurrently via `ThreadPoolExecutor(max_workers=3)`. Results aggregate into one report with per-task sections; failures are captured inline instead of short-circuiting the batch. Prerequisite: `alpi/tools/_state.py` refactored from module-global `_emit`/`_interrupt_getter`/`_usage_sink` to `contextvars.ContextVar`, so two workers can have distinct emit callbacks without racing. Worker threads re-seed `interrupt_getter` + `usage_sink` from the parent context (Python's `ThreadPoolExecutor` does not auto-propagate ContextVars) and install a per-task prefixed `emit`. Existing callers unchanged — the public API is identical; only `research.py` and `delegate.py` added `get_emit()` instead of reading `_emit` directly (v0.2.18) |
