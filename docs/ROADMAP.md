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
| B | Interactive browser (Playwright) | 🔵 backlog — see below |
| C | OpenAI Codex provider (ChatGPT subscription auth) | 🔵 backlog — see below |
| D | Vision (`read_image`) | 🔵 backlog — see below |
| E | Multi-profile CLI | ✅ shipped (commit 630f97c) |
| F | Gateway workspace validation | ✅ shipped (commit 04bdaba) |
| G | Terminal + code execution OS sandbox | ✅ shipped opt-in/experimental (commit e78b428) |
| H | Home Assistant integration | ⏸ blocked on user confirmation |
| I | MCP client | ✅ shipped (commit 0d376ac) |
| J | Anti-bot browsing (camoufox) | 🔵 backlog — depends on B |
| K | Scroll resilience under heavy streaming | 🔵 backlog — watch for regressions |
| L | Reasoning-as-state (TUI) | ✅ shipped (commits 62f7fa7 + fd1fec4) |
| M | TTS / STT / voice-mode | ❌ out of scope for core agent |
| N | Image generation | 🔵 backlog — no concrete use case yet |
| R | Research tool follow-ups (R.1 / R.2 / R.3) | 🔵 backlog — see below |

### What's left to call v0.2 done

The minimum-viable shape of v0.2 is what's already shipped. Anything
else listed under "🔵 backlog" can move to v0.3 without blocking
release. The bar for "ship v0.2" is **clean docs + version bump +
real-use validation across a few sessions** — not feature
exhaustiveness.

**Open work that would make sense to land before closing v0.2:**

- **R.1** (research step-counter in state label) — 2-4h, low risk, very visible UX win.
- **D** (vision `read_image`) — ~50 LOC, unblocks "lee este screenshot".
- Anything else: defer to v0.3.

Once those land + a fresh CHANGELOG entry summarises v0.2, bump to
`v0.3.0` and reopen the table for the next cycle.

---

## Backlog — high value, on deck

### B. Interactive browser (Playwright)

`alf/tools/browser.py` is a stub; not registered. To ship:

1. Replace `Browser.run` with a Playwright impl: headless Chrome, persistent context under `~/.alf/browser/`, actions `text | screenshot | click | fill | navigate`.
2. Add `playwright` to `pyproject.toml` (+ one-time `playwright install chromium`).
3. Re-register `browser` in `alf/tools/__init__.py`.

Unlocks online shopping, logins, form-filling — things `web_fetch` (read-only) can't do.

### C. OpenAI Codex provider (ChatGPT subscription auth)

Today alf goes through LiteLLM with API keys → OpenAI is metered per token. Hermes supports a second path: OAuth device-code against the user's ChatGPT Plus/Pro account, using the same endpoints the official Codex CLI uses. Already-paid quota instead of metered tokens.

**Mechanics (reverse-engineered, not a public OpenAI API):**

1. **Auth** — OAuth2 device code against `auth.openai.com` with the Codex CLI's public `client_id` (`app_EMoamEEZ73f0CkXaXp7hrann`). User opens URL + types code → poll → `access_token` + `refresh_token`. Reference: `~/git/hermes-agent/hermes_cli/auth.py:2999-3119` (`_codex_device_code_login`) and `:1615-1675` (`resolve_codex_runtime_credentials`).
2. **Storage** — `~/.alf/auth.json` with `fcntl` file lock (gateway + TUI + schedule daemon must not race on refresh). Refresh 120s before expiry; on 401 force-refresh + retry once.
3. **Endpoint** — `https://chatgpt.com/backend-api/codex` (NOT `api.openai.com`).
4. **Wire protocol** — Responses API with event streaming (`client.responses.stream(...)`), not chat/completions. **LiteLLM does not cover this cleanly** → bypass LiteLLM, use the OpenAI SDK directly. Reference: `~/git/hermes-agent/run_agent.py:4592` (`_run_codex_stream`).

**Implementation shape:**

- `alf/auth/codex.py` — port from Hermes: `device_code_login()`, `resolve_runtime_credentials(force_refresh, refresh_skew)`, locked R/W of `auth.json`.
- `alf/providers/openai_codex.py` — new `Provider` subclass with `auth_type = "oauth_external"`, lists gpt-5 family.
- `alf/llm.py` — add a transport dispatch: when model id prefix is `openai-codex/`, resolve credentials and call `openai.OpenAI(...).responses.stream(...)` instead of `litellm.completion`. Normalise the event stream (`response.output_item.added` with `type=function_call`, etc.) into the same `{text_delta, tool_calls_delta, finish_reason}` shape `stream()` already yields.
- CLI: `alf auth openai-codex [login|logout|status]`.

**Effort.** 1-2 days. Auth module is almost a literal port. The unknown is event-stream normalisation — Responses API emits a richer set of events than chat/completions.

**Risks.**

- **ToS grey area.** `chatgpt.com/backend-api/codex` is not a public, bindable-by-third-parties API. OpenAI can rotate the `client_id`, filter by User-Agent, or tighten the device flow at any moment. Acceptable for personal use; NOT acceptable for hosted/shared deployment.
- **Two transports.** `engine.py` gets a second code path; contain it behind a `Transport` protocol so dispatch happens once in `llm.py`, not sprinkled.
- **Token liveness across processes.** Gateway / TUI / schedule each open `auth.json` independently. The lock prevents torn writes but not stale reads — every transport call must re-resolve credentials.

**Ship order.** Auth + CLI first (testable standalone). Then provider + transport dispatch. Then end-to-end smoke with real `gpt-5` through the agent loop.

### D. Vision (`read_image`)

~50 LOC. LiteLLM already supports vision models. A `read_image(path, question)` tool sends image + prompt to whichever model is active (if vision-capable). Falls back to "model is text-only" error. Useful for "lee el screenshot que he guardado".

### R.1. Research step-counter in live state label

The `research` ToolCard currently shows whatever inner tool is running (`searching the web…`) with no sense of progress. Wrap the `emit_state` callback inside the research subloop so every inner label is prefixed with `step N/M · <inner>`. Capture the engine-set callback, install a wrapping closure for the duration of each tool call, restore after.

Cost: 2-4h. Risk: low. Tests: 2-3 cases. **Ship first among the three R follow-ups.**

### R.2. `delegate_task` — write-capable sub-agents

Sibling to `research`. Schema: `brief` + `toolsets: ["file", "terminal", "web"]`. Map toolset names → concrete tool sets (`"file"` → read_file + write_file + edit_file + search, `"terminal"` → terminal). Reuses research subloop infra; different system prompt allowing mutations.

Use case: "refactor module X", "generate project scaffold from template Y". Only ship if a concrete need materialises.

**Gotchas:**

1. **Security posture.** Sub-agent with `write_file` + prompt injection can mutate FS without user-in-the-loop. Layer 1 sensitive-path denylist is the only wall today. Decision before implementing: (a) trust the denylist (consistent with the main agent), or (b) add first-write confirmation per sub-agent invocation. For personal-agent scope (a) is probably sufficient.
2. **Testing.** Sub-agent writes need isolated FS fixtures + LLM mocks. ~3-4h test budget.

Cost: 1-2 days. Risk: medium. Backlog until a use case lands.

### R.3. Batch parallel research (`tasks[]`)

Hermes-style: `tasks: [{brief, depth}]` up to 3 concurrent via `ThreadPoolExecutor(max_workers=3)`. Aggregate reports, propagate interrupt to all children on cancel.

**The real cost is the refactor of `alf/tools/_state.py`.** `set_emit`, `set_interrupt_getter`, `set_usage_sink` are module-level globals — three subagents in parallel race on them. Move to `contextvars` (preferred) or thread-locals. Touches ~15 sites that call `emit_state` (web_search, web_fetch, web_extract, search, research, schedule, ...). Mechanical, non-destructive, but real.

The refactor is also useful on its own: cleaner tests, better observability when nested tools run.

Cost: 1-2 days + 1 day refactor. Risk: medium-high. Lowest priority of the three R follow-ups — niche for personal use.

### H. Home Assistant integration

Only if Javi runs HA. Hermes has `homeassistant_tool` as reference. Requires `HA_URL` + long-lived token in `.env`. Typical uses: read sensors, toggle lights/scenes, query occupancy. **Waiting on Javi confirming.**

### J. Anti-bot browsing (camoufox)

Stealth Firefox fork for Cloudflare-protected sites. Hold until B (Playwright) is proven useful. Free but heavy (+200MB binary).

### K. Scroll resilience under heavy streaming

`call_after_refresh` + dual timers cover most cases today. Watch for regressions when streaming is fast + tool cards animate concurrently.

### N. Image generation

`generate_image(prompt, style)` using the active vision model or a dedicated endpoint (DALL-E, SD). Useful for "hazme un logo rápido". Low priority unless a concrete use case appears.

---

## Next — v0.3 planned

### O. Drop `questionary` in favour of direct `prompt_toolkit`

`questionary` was the right choice when setup was 3 menus and 0 wizards. Now that `alf/ui.py` is the shared layer for every setup flow, we're fighting its defaults more than using them.

Concrete hacks in `alf/ui.py` as of v0.2:

1. `qmark=""` + empty `message` to suppress its prompt header.
2. List-tuple titles `[(style, text)]` so it skips its own `class:highlighted` wrap.
3. Style override for `class:close` / `class:highlighted close` / `class:selected close` to keep the close row from flashing accent.
4. ANSI escape (`\033[1A\033[2K\r\n`) after every menu to wipe questionary's post-selection echo.
5. `_CLOSE_SENTINEL = object()` because `Choice.value=None` collapses into "unset" and falls back to the title string.

What `questionary` still gives us after those hacks: arrow-key nav, ENTER/ESC, cursor rendering, scroll-if-long. All ~150 LOC on top of `prompt_toolkit` (which we keep transitively).

**Scope.** Reimplement `menu()` directly against `prompt_toolkit`. Remove the 5 hacks. Rewrite the 5 monkeypatched UI tests. Drop `questionary` from `pyproject.toml`. Leave `text/password/confirm` on `rich.Prompt`.

**Risk budget.** Half-day to a day. ESC handling on macOS Terminal sometimes delays behind escape-sequence timeout — exactly the edge questionary abstracts. Budget 1-3h for surprises.

**Trigger.** v0.3 UI polish, or earlier if we hit hack #6.

### P. Graduate the OS sandbox out of experimental

`tools.terminal.sandbox` ships in v0.1 as opt-in + experimental. Default-on was rejected because the `sandbox-exec` profile (macOS) and `bubblewrap` invocation (Linux) haven't been validated against the long tail of real commands: `git push` with SSH keys outside the workspace, `docker` touching `/var/run/docker.sock`, Homebrew Intel vs Apple Silicon, `npm install` cache in `~/.npm`, `code --install-extension` writing `~/.vscode/`, etc.

**For v0.3, revisit with data.** Goal: move default to `true` without a regression wave.

Scope:

- Collect a "golden set" of 30-50 real commands the agent runs in a normal week. Exercise each under sandbox. Anything that breaks gets a profile fix or an explicit carve-out in docs.
- Extend macOS profile to cover Homebrew Apple Silicon (`/opt/homebrew`) and Intel (`/usr/local`); allow reads on `~/.gitconfig` and `~/.git-credentials` without opening the rest of `$HOME`.
- Extend Linux `bwrap` similarly — bind-mount `~/.gitconfig` + `~/.npm` + `~/.cache` as RO so package managers work.
- Smoke-test on Ubuntu LTS and Fedora stable (not just the Docker test image).
- First-run check: with sandbox on, run `echo ok` through the sandboxed path. If it fails, warn loudly with a pointer to SECURITY.md and fall back to disabled.

Once the golden set passes cleanly, flip `DEFAULT_CONFIG` to `sandbox: true`, drop "experimental" wording in SECURITY.md / CONFIG.md, mention in v0.3 CHANGELOG as "tightened by default".

Don't graduate it silently — the security posture change deserves visibility.

### Q. Skill self-review / validation

Tier B models happily publish skills with real bugs: threading races (opening browser before the local callback server is listening), undeclared third-party imports (`import requests` when only stdlib is acceptable), incorrect setup instructions that contradict the docs the agent just fetched (e.g. "Authorization Callback Domain: localhost:8765" when the provider rejects port numbers in that field).

Current mitigations — stdlib-preferred rule + security scanner + structured layout — catch the crude cases but miss the subtle ones. v0.3 idea: a `skill(action="validate", name=...)` that runs a battery of cheap checks:

- `python -c "import <every top-level import in scripts/*.py>"` — surface missing third-party deps.
- `python -m py_compile scripts/*.py` — syntax.
- `ast.parse` + walk for common foot-guns (race patterns in OAuth: `webbrowser.open(...)` before `.serve_forever()` / `.handle_request()` on the same script).
- Cross-check setup instructions in SKILL.md against the endpoints scripts actually hit (if SKILL.md mentions `localhost:8765` and scripts bind to a different port, flag it).

**Even more ambitious:** `skill(action="review", name=...)` that spawns a `research()` sub-agent with a pre-canned prompt — "You are reviewing skill X. Read its SKILL.md and scripts/. Return a bulleted list of bugs, race conditions, security issues, or setup instructions that contradict the code." — and reports back. One research call per review; catches real issues.

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
