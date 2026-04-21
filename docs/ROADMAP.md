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
| M | TTS / STT / voice-mode | ❌ out of scope for core agent |
| N | Image generation | 🔵 backlog — no concrete use case yet |
| R.1 | Research step-counter in state label | ✅ shipped (v0.2.2) |
| R.2 | `delegate` — write-capable sub-agent | ✅ shipped (v0.2.3, named `delegate` not `delegate_task`) |
| R.3 | Batch parallel sub-agents (`tasks[]`) | 🔵 backlog — see below |

### What's left to call v0.2 done

The minimum-viable shape of v0.2 is what's already shipped. Anything
else listed under "🔵 backlog" can move to v0.3 without blocking
release. The bar for "ship v0.2" is **clean docs + version bump +
real-use validation across a few sessions** — not feature
exhaustiveness.

**Nothing open for v0.2.** Everything the roadmap promised is in. Backlog items (B, C, H, J, N, O, P, Q, R.3) all roll forward to v0.3.

Once those land + a fresh CHANGELOG entry summarises v0.2, bump to
`v0.3.0` and reopen the table for the next cycle.

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

### R.3. Batch parallel sub-agents (`tasks[]`)

Applies to both `research` and `delegate` once shipped. `tasks: [{brief, depth}]` (or `{goal, toolsets}` for delegate) up to 3 concurrent via `ThreadPoolExecutor(max_workers=3)`. Aggregate results, propagate interrupt to all children on cancel.

**The real cost is the refactor of `alpi/tools/_state.py`.** `_emit`, `_interrupt_getter`, `_usage_sink` are module-level globals — multiple subagents in parallel race on them. Move to `contextvars.ContextVar` (preferred) so each thread gets its own view. Touches ~15 sites that call `emit_state` (web_search, web_fetch, web_extract, search, research, delegate, schedule, ...). Mechanical, non-destructive.

The refactor is also useful on its own: cleaner tests, better observability when nested tools run.

Both `research.py` and `delegate.py` have the single-task loop structured so `tasks[]` can layer on top with no structural change once state is context-local. See the module docstring in `alpi/tools/delegate.py` for the exact handoff point.

Cost: 1-2 days + 1 day refactor. Risk: medium-high. Niche for personal use.

### H. Home Assistant integration

Only if Javi runs HA. Hermes has `homeassistant_tool` as reference. Requires `HA_URL` + long-lived token in `.env`. Typical uses: read sensors, toggle lights/scenes, query occupancy. **Waiting on Javi confirming.**

### J. Anti-bot browsing (camoufox)

Firefox fork with C++ fingerprint patches for sites that block plain Chromium even with `playwright-stealth` (Cloudflare Turnstile, DataDome, PerimeterX). Free but heavy: +230MB Firefox binary aside from Playwright's own Chromium, separate Python wrapper, and camoufox periodically breaks when the anti-bot vendors update.

v0.2.16 shipped `playwright-stealth` on by default, which beats ~80% of basic detection (navigator.webdriver, plugins, UA-CH, WebGL vendor overrides). Activate camoufox only when a concrete site breaks through that. Alternatives to consider at that point, in order of effort: manual cookie import (user logs in on their real browser, exports cookies, imports into alpi), `patchright` (newer Chromium-based stealth fork), Browserbase cloud (paid, residential IPs), camoufox.

### N. Image generation

`generate_image(prompt, style)` using the active vision model or a dedicated endpoint (DALL-E, SD). Useful for "hazme un logo rápido". Low priority unless a concrete use case appears.

---

## Next — v0.3 planned

### Q. Skill self-review / validation

Tier B models happily publish skills with real bugs: threading races (opening browser before the local callback server is listening), undeclared third-party imports (`import requests` when only stdlib is acceptable), incorrect setup instructions that contradict the docs the agent just fetched (e.g. "Authorization Callback Domain: localhost:8765" when the provider rejects port numbers in that field).

Current mitigations — stdlib-preferred rule + security scanner + structured layout — catch the crude cases but miss the subtle ones. v0.3 idea: a `skill(action="validate", name=...)` that runs a battery of cheap checks:

- `python -c "import <every top-level import in scripts/*.py>"` — surface missing third-party deps.
- `python -m py_compile scripts/*.py` — syntax.
- `ast.parse` + walk for common foot-guns (race patterns in OAuth: `webbrowser.open(...)` before `.serve_forever()` / `.handle_request()` on the same script).
- Cross-check setup instructions in SKILL.md against the endpoints scripts actually hit (if SKILL.md mentions `localhost:8765` and scripts bind to a different port, flag it).

**Even more ambitious:** `skill(action="review", name=...)` that spawns a `research()` sub-agent with a pre-canned prompt — "You are reviewing skill X. Read its SKILL.md and scripts/. Return a bulleted list of bugs, race conditions, security issues, or setup instructions that contradict the code." — and reports back. One research call per review; catches real issues.

### S. `read_image` auto-resize (cost saver)

Vision-model cost scales with image resolution: a 4K screenshot costs ~9× more tokens than its 1K version for the same content. Right now `read_image` sends the original bytes to the LLM, so a photo of a receipt at phone-native resolution burns tokens that contribute nothing to the answer.

**Scope.** Add Pillow as a main dependency (~3 MB). Add `tools.read_image.auto_resize: true` to config (default on). When set, downscale any image whose longer edge exceeds a target (Anthropic recommends ~1568px, which also matches OpenAI's 512/768/2048 tile grid well) before base64-encoding. Preserve aspect ratio, reuse format where possible (RGBA→RGB for JPEG), JPEG quality 85.

**Why not in v0.2.** Adding Pillow as a required dep + config knob + resize logic + tests is a non-trivial chunk for what is an optimisation, not a correctness fix. Users with 4K screenshots pay more tokens; that's it. Ship when we have a real "this is getting expensive" signal from usage.

**Reference.** Hermes' `_resize_image_for_vision` in `tools/vision_tools.py` does a reactive version (resize only after the API rejects with "too large"); our take would be proactive (resize any time we could).

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
