# alf — project context

Snapshot of where this project stands, what's been decided, and what's
pending. Audience: me (Claude in a future session) and Javi. Last
updated at the close of v0.1 — when the TUI, memory discipline, skill
pending gate, workspace sandbox, delegate sub-agent, and turn-based
session format all landed together.

**Currently on v0.1** (stable). **v0.2 roadmap** at the bottom.

## What alf is

A slim, personal AI agent inspired by Nous Research's **Hermes**
(`~/.hermes/hermes-agent`). Intended as Javi's everyday assistant in two
surfaces: terminal (Textual TUI) and Telegram bot (gateway). Not a generic
chatbot — learns about the user, keeps curated memory, and can grow skills.

Deliberately leaner than Hermes. Keeps the key ideas (tool-calling loop,
curated memory files, inline learning via `memory`, separate gateway
process, OpenRouter-first model selection) but drops the complexity (27
skill categories, 30+ tools, SQLite state, curses UIs). **Does NOT do
post-session reflect** — removed deliberately; the agent decides what to
save in the moment via the `memory` tool (Hermes-style).

## Principles (set by Javi)

- **Slim.** No over-engineering. Every feature must earn its keep.
- **Solid base.** Core loop, memory and tools must be rock-solid before
  adding surface features.
- **User is in control.** No destructive actions without explicit OK. No
  skills created autonomously. No memory deletions without approval.
- **Python stack.** No rewrite in Go — considered and rejected (loses
  litellm, tests, no real upside).
- **No migrations.** alf is in active development; we ship for the
  "market" (public use) only when Javi is proud of it. Until then:
  schema changes, renames, and disk-layout shifts go in as clean
  breaks — never with legacy-detection code, upgrade paths, or
  compatibility shims. Anything from yesterday's iteration that lives
  on disk gets cleaned up by hand, not by `ensure_home`. Keeps the
  codebase honest and free of dead branches.

---

## v0.1 — current state

### TL;DR of what ships

- **Textual TUI** (chat, streaming, tool cards, modals, slash commands,
  autocomplete, interrupt, accent color, atomic session persistence).
- **19 tools**, all with Hermes-style tool descriptions (positive use +
  explicit DO NOT / redirect-to-other-tool).
- **3-file memory** (USER/MEMORY/PERSONALITY) with two-tier dedup,
  Approach C (return state after mutation), `.bak` snapshots, strict
  hygiene rules, disambiguation rule for preferences.
- **Inline learning** (no post-session reflect): agent calls `memory` /
  `create_skill` during the conversation based on triggers.
- **Skills with pending gate**: agent-created skills land in
  `~/.alf/skills/_pending/`, user approves via `/skills` modal. Quota,
  security scanner, `origin: agent|user` field.
- **Workspace sandbox**: file tools limited to workspace + `~/.alf/`.
  `/workspace` slash to set; terminal soft-hardened with `cwd=workspace`
  + prompt discouragement (not hard isolation — see v0.2 §3).
- **Turn-based session format**: `turns: [{user, tools[], assistant}]`
  stored; resume rebuilds clean `system + user/assistant × N` messages.
  Small files (~5-10× smaller than the old message log).
- **Delegate tool** for deep research with its own context (12 LLM
  iterations, synthesis fallback, honors interrupts).
- **Gateway** (Telegram) — separate process, subprocess per message.
- **Interrupt on new input** via engine flag + turn lock.

### Surface

- **Interactive chat:** Textual 8.2.3 TUI (`alf/tui/app.py`), inspired by
  `mother.py`. Minimal layout: chat (VerticalScroll) + status/keys
  (`AlfHeader`) + bordered Input. **No Footer** — keybindings are
  implicit; `/help` lists them.
- **Streaming of LLM tokens** via litellm `stream=True`. Markdown widget
  updates incrementally.
- **Live tool cards (`ToolCard` in `alf/tui/widgets.py`):** single line,
  spinner + elapsed ticker that refreshes 4×/s (reduced from 10× for
  event-loop health). Shows **tool_state labels** while running, switches
  to final result line on completion. Accent color on diamond + name for
  `memory` and `create_skill` (learning tools) so the user sees when alf
  is growing.
- **Slash autocompletion** via Textual's built-in `SuggestFromList` — type
  `/he` → ghost `/help`, right arrow accepts.
- **`/model` native Textual screen** (`alf/tui/model_screen.py`): uses
  `OptionList`, not `suspend()` + questionary. Api-key prompt is its own
  `ModalScreen[str]`.
- **`/help`, `/memory`, `/tools`, `/cost`, `/skills`** are `ModalScreen`s
  (`alf/tui/screens.py`). `Esc` closes.
  - **`/skills`** lists live + pending skills. Keys: `a` approve, `r`
    reject, `v` view SKILL.md body.
- **Slash commands** also: `/clear`, `/compact`, `/exit`. **No
  `/reflect`** (removed — reflection is inline during conversation).
- **`/compact`** mounts a ToolCard of its own so the user sees the
  operation's progress like any tool.
- **Interrupt on new input:** typing a new message while a turn is still
  running cancels the current work and starts fresh. `engine.interrupt_requested`
  is polled at 3 points (between LLM iterations, mid-stream, between
  tool calls). Long-running tools (e.g. `delegate`) poll
  `tool_state.is_interrupted()` and abort early. Active ToolCards get
  `finish("[interrupted]")` immediately for visual feedback.
- **Accent color** from `tui.accent` in `config.yaml` (default `#ff8800`).
  Applies to input border, user message color, header model highlight,
  and learning-tool cards. Context bar shifts color: accent < 60% < yellow
  < 80% < red.
- **`Ctrl+Y`** copies last assistant reply. Tries `pbcopy`/`wl-copy`/
  `xclip`/`xsel` first, then OSC-52 as fallback (SSH-friendly).
  `Ctrl+L` clears. **`Ctrl+P` palette disabled** (was noise).
- **Text selection**: Textual 8.x has `ALLOW_SELECT=True` by default —
  click-drag should highlight. On macOS hold `⌥ Option` while dragging
  to bypass mouse capture and use native terminal copy.

### Core

- litellm multi-provider (Anthropic, OpenAI, OpenRouter, Google, Groq,
  custom OpenAI-compatible endpoints i.e. Ollama / LM Studio / vLLM).
- **19 tools** registered: `read_file`, `write_file`, `edit_file`,
  `terminal`, `grep`, `glob`, `todo`, `web_search`, `web_fetch`,
  `web_extract`, `schedule`, `memory`, `session_search`, `create_skill`,
  `edit_skill`, `delete_skill`, `delegate`, `send_message`, `email`.
  - **`browser`** file exists but is **not registered** (stub). See
    "Open questions / pending" section 6 for the Playwright roadmap.
- **Curated memory** (`memories/USER.md`, `memories/MEMORY.md`) with §
  entry delimiter, char limits (1375 / 2200), **accent+case insensitive
  dedup** plus **token-overlap dedup** (70% max-containment — catches
  paraphrases like "Vivo en Hua Hin" vs "Javi vive en Hua Hin"), no
  silent deletions. `.bak` snapshot before every mutating write.
- **`PERSONALITY.md`** at home root. Edited by user or via `memory`
  tool (target="PERSONALITY.md").
- **Skills** under `~/.alf/skills/<category>/<name>/`. Agent-created
  skills land in `~/.alf/skills/_pending/<name>/` with `origin: agent`
  frontmatter — the user reviews with `/skills` (approve → moves to
  live category dir; reject → deletes). User-owned skills carry
  `origin: user` and require `confirm_user_skill=true` on `edit_skill`
  or `delete_skill`. Quota: max 5 pending at a time. Security scanner
  (regex) blocks obvious foot-guns (rm -rf, fork bomb, curl|sh, eval,
  hardcoded keys) before writing.
- **Inline learning, not post-session reflect.** The system prompt tells
  the agent to call `memory(add, ...)` and `create_skill(...)` during
  the conversation whenever the triggers apply. The `/reflect` post-
  session pass was removed — it added complexity and Hermes doesn't do
  it either.
- **Sessions** auto-saved under `sessions/*.json`; empty sessions (no
  user message) are NOT saved. `alf -c` / `--continue` resumes the last
  one (adopts its id, doesn't fork). Replays user/assistant turns
  visually on resume; ctx tokens restored from `last_ctx_tokens` field
  (or estimated from chars/4 for old sessions).
- **Gateway** — separate process (`alf gateway start`). Telegram
  long-poll real. `alf gateway setup/start/stop/status/logs` for
  lifecycle. Log file auto-rotates at 1MB (single file, no backups).
- **Config** structured with sections in `~/.alf/config.yaml`:
  `model`, `providers.custom[]`, `tools.{max_steps_per_turn,
  web_extract.model}`, `tui.{accent, show_cost, show_tokens}`.
  **No `reflect` section** (removed with post-session reflect).
- **`max_steps_per_turn: 40`** (Hermes uses 90). If the agent loops,
  bump it. System prompt also caps consecutive `web_search` to 3.
- **Interrupt mechanism** (`Engine.interrupt_requested`): flag polled
  between loop iterations, mid-stream, and between tool calls. Long-
  running tools read `alf.tools._state.is_interrupted()` to abort.
  On interrupt, skipped tool calls get a `"[skipped — user interrupted]"`
  message appended to preserve OpenAI-style message pairing.

### Testing

`tests/` has 11 files. **pytest-based** with a `--llm` flag.

- `pytest` (no LLM): **68 tests**, ~2s.
- `pytest --llm` (real LLM calls): adds a handful of integration tests
  (web_fetch, llm_chat), ~30-50s, costs a few cents on mimo-free.

Removed since v0.1 start: `test_reflect_unit.py`, `test_llm_reflect.py`
(reflect feature deleted).

---

## Key design decisions (and rationale)

### Memory files

- **3 files:** `USER.md` (facts about user), `MEMORY.md` (env/tool
  notes), `PERSONALITY.md` (behavior/style). Hermes has 2 (user +
  memory) — we split personality because it's edited by user, not agent.
- **UPPERCASE names** — follows `README.md` / `LICENSE` / `SKILL.md`
  convention.
- **Char limits, not token counts.** Model-independent.
- **`§` delimiter.** Multiline-safe.
- **Frozen snapshot in system prompt** (for prefix cache). Writes update
  disk immediately but NOT the in-context snapshot.
- **Memory tool returns full current state after mutation** — "approach C"
  vs Hermes. The agent sees its own write result in the next turn without
  needing `memory(read)`. Trade-off: +50-100 chars per mutation response.
- **Dedup is accent/case/punctuation insensitive.** `"Hua Hin"` and
  `"hua hin."` are the same entry.

### Tool output display

- **Single-line card per tool call.** No `rich.Panel` boxes.
- **Format:** `◆ tool_name  arg_hint  spinner  elapsed` → `◆ tool_name
   arg_hint  →  result_hint  duration`.
- **State streaming (`alf/tools/_state.py`):** Tools import `emit_state`
  and call it during execution. Engine wires a `set_emit(callback)`
  around each tool call. Callback emits `tool_state` AgentEvent →
  UI updates the card's label. Supports `error=True` flag → red state.
- **Rich markup escape:** tool outputs may contain `[` / `]` (e.g.
  `[USER.md: 17%]`). Any user-controlled substring going into
  `Text.from_markup()` MUST be `rich.markup.escape()`-wrapped or built
  with `Text()` directly. Several crashes fixed around this.

### Web tools

- `web_search` uses **`ddgs`** (the maintained successor of
  `duckduckgo-search` — the old package returns empty arrays silently).
  No API key. Tool rate-limits to 15 results max.
- `web_fetch` tries **Jina Reader** (`https://r.jina.ai/<url>`) first —
  free proxy that returns clean Markdown for sites with anti-bot
  protection. Falls back to direct `httpx.get` + html2text on failure.
  `emit_state("Jina unreachable — retrying direct", error=True)` makes
  the fallback visible.
- `web_extract` = `web_fetch` + summarization via LLM. Uses
  `cfg.tools.web_extract.model` if set (e.g.
  `openrouter/google/gemma-4-31b-it:free`) else falls back to the main
  model. Fallback chain handles deprecated model IDs gracefully.
- System prompt has a decision table: `web_search` for "find", `web_extract`
  for "answer about URL", `web_fetch` for "show full page". **Hard rule**:
  never `bash curl` for HTTP(S).

### Skills — pending gate + origin (our main differentiation vs Hermes)

Hermes' `skill_manager_tool` writes skills directly to the live dir.
Users have complained the agent creates them unilaterally. alf does it
differently:

- **`create_skill`** writes to `~/.alf/skills/_pending/<name>/` (NOT
  live) with `origin: agent` frontmatter.
- **`/skills` modal** lists pending at top (yellow) and installed below
  (with `origin: agent` cyan or `origin: user` green). Keys: `a`
  approve → moves dir to `<category>/<name>/`; `r` reject → deletes;
  `v` view SKILL.md.
- **Quota**: max 5 pending at once. The agent gets an error if it tries
  to exceed.
- **Anti-duplication** across live + pending — no collision by name.
- **Security scanner** ([create_skill.py:scan_skill_body](alf/tools/create_skill.py))
  rejects obvious foot-guns before writing: `rm -rf`, fork bomb,
  `curl|sh`, `eval()`, `exec()`, `__import__()`, hardcoded API keys.
- **`edit_skill` / `delete_skill`**: agent-owned skills edit/delete
  directly; user-owned (`origin: user` or unknown) require
  `confirm_user_skill=true`. `edit_skill` keeps frontmatter intact,
  replaces body only, and writes a `.bak` next to `SKILL.md`.
- The system prompt tells the agent it **doesn't need to ask** before
  calling `create_skill` — the pending gate is the ask.

### Interrupt

- **One mode only** — new input always cancels the current turn (no
  queue mode, unlike Hermes which has both).
- **Engine flag** `interrupt_requested` polled at 3 check-points:
  before each LLM iteration, mid-stream (`llm.stream` loop breaks on
  flag), and between tool calls within a step.
- **Long-running tools** (`delegate`) poll
  `alf.tools._state.is_interrupted()` between internal LLM iterations
  and between sub-tool executions. The engine sets the getter around
  the outer tool call so the flag propagates automatically.
- **Session coherence on interrupt**: any skipped tool calls get a
  `"[skipped — user interrupted]"` tool message appended so OpenAI's
  "every assistant tool_call must be followed by a tool message with
  matching id" invariant holds for the next turn.
- **Visual feedback**: `DimLine("↯ interrupted previous turn")` mounts
  immediately when the new input arrives, active ToolCards are marked
  `finish("[interrupted]", ok=False)` right away (don't wait for the
  engine's tool_end events).

### Gateway

- **Separate process.** PID file at `gateway/gateway.pid`.
- **Subprocess per message, streamed.** Each message spawns
  `alf chat --once --emit-events "..."`. stdout is a JSON-lines stream
  (`tool_start`, `tool_end`, `error`, `reply`) — the gateway reads it
  line-by-line and relays tool activity to the chat as it happens.
- **Tool trace in chat.** Each `tool_start` becomes a short Telegram
  message (`◆ name · preview`). Muteable via `gateway.show_tool_trace`
  in `config.yaml` (default `true`).
- **Typing indicator.** While a turn is running, a background task
  re-pings `sendChatAction` every 4s (Telegram's indicator drops after
  ~5s). Muteable via `gateway.typing_indicator` (default `true`).
- **Allowlist = env only.** `TELEGRAM_ALLOWED_CHAT_IDS` (and
  `WEBHOOK_ALLOWED_CHAT_IDS`) in `~/.alf/.env`, comma-separated. No
  `pairing.json`, no per-chat state file — `.env` is the single source
  of truth for both the bot token and the allowlist. Fail-closed:
  unset/empty var rejects every chat. When a dynamic pairing flow ever
  lands (owner approves codes from CLI), reintroduce a store then.
- **Env var `ALF_HOME`** passed to subprocesses to isolate profiles.

### Proactive outreach (`send_message` tool)

- **Tool `send_message(text, platform=telegram, chat_id=…)`** — sends a
  message out to a paired chat. Used by the agent for long-running tool
  completions ("your research is done") and by the schedule daemon for
  reminders + inactivity check-ins.
- **Autosuficiente.** The tool posts to the platform API directly using
  the bot credentials in `.env`. Does NOT depend on the gateway
  listener being up — outbound posting adds zero inbound attack
  surface, so there's no reason to route through the gateway process.
- **Allowlist-only.** `{PLATFORM}_ALLOWED_CHAT_IDS` in `.env` is the
  same source of truth as the gateway's inbound check, reused via
  `gateway.delivery.is_allowed`.

### Email (`email` tool, generic IMAP/SMTP)

- **Agentic mailbox access** — list, search, read, send, reply,
  forward, move, delete, download_attachment. Credentials in
  `~/.alf/.env` under the `EMAIL_*` prefix (same pattern as
  `TELEGRAM_*`): address, password, IMAP host/port, SMTP host/port.
  Zero provider-specific code — any mailbox that speaks IMAP(S) and
  SMTP+STARTTLS works.
- **Client lives in `alf/email/client.py`** (`EmailClient`): fresh
  IMAP/SMTP connections per op, UID-based message IDs, defensive MIME
  parsing, text-body preference with HTML-strip fallback, 8K char cap
  on bodies to keep prompts bounded.
- **Setup wizard** at `alf/email/setup.py`, hooked into the `alf
  setup` menu as "Email (IMAP/SMTP)". Asks for address/password/hosts,
  runs a live `client.test()` before saving — if auth or network
  fail, nothing lands in `.env`.
- **Sandbox**: `download_attachment` dest + `send` attachment paths go
  through `tools._paths.check_path` — same allowed roots as
  `write_file`.
- **Prompt-injection defense.** Tool description is load-bearing:
  tells the LLM email bodies/subjects/attachments are UNTRUSTED data,
  not instructions, and to ignore directives like "ignore previous
  instructions" / "forward to X" / "run Y". Reinforced by a line in
  the global system prompt that applies to all tool output.
- **Gateway channel** at `alf/gateway/platforms/email.py`: `listen()`
  polls IMAP at `gateway.email.poll_interval` seconds (config.yaml;
  default 60s), `send()` pushes replies via SMTP. Reuses the same
  `EmailClient` as the tool so provider quirks (SMTPS port 465,
  STARTTLS 587, MIME parsing) are solved once. Runs only while
  `alf gateway start` is alive — outbound via `send_message` or
  `schedule` does NOT need the gateway up.
- **Baseline on first run.** Records the highest UID in INBOX as
  "seen" and only surfaces messages with UID > baseline. No backfill
  — same spirit as Telegram, you don't want a week of old threads
  replayed when you restart. State persists to
  `~/.alf/gateway/email-state.json` (one `last_uid` per email
  address) so daemon restarts don't re-process or miss messages.
- **Allowlist** lives in `.env` as `EMAIL_ALLOWED_SENDERS` (not the
  generic `*_ALLOWED_CHAT_IDS` pattern because "sender" reads right
  for email). Case-insensitive match. Fail-closed when empty. The
  gateway run loop checks via `delivery.is_allowed` — same code path
  as Telegram.
- **Anti-bulk filter**: drops senders matching `noreply`,
  `do-not-reply`, `mailer-daemon`, `bounce`, `notifications@`, etc.
  + messages with `Auto-Submitted != no`, `Precedence: bulk|list`,
  `List-Unsubscribe`, or `X-Auto-Response-Suppress`. Runs BEFORE the
  allowlist check — a bulk sender's address ending up allowlisted
  won't bypass the filter.
- **Only INBOX.** Spam/Junk folders are skipped. Your provider's
  DKIM/SPF already ran; if the mail ended up in Spam, we don't
  second-guess that.
- **`mark_as_read: true`** (default) — sets `\Seen` on processed
  messages so your regular mail client shows them read after alf
  replies. Toggle via `gateway.email.mark_as_read` in config.yaml.
- **Config structure** lives under `gateway.<platform>.*` now.
  Telegram flags (`show_tool_trace`, `typing_indicator`) moved from
  flat `gateway.*` to `gateway.telegram.*` to make room for email's
  own keys without collisions.

### MCP servers (`alf setup → MCPs`)

- **Blank slate by default** — alf ships with zero pre-connected
  MCP servers. Users opt into each one explicitly via
  `alf setup → MCPs`. No magic, no surprise subprocesses.
- **Client in `alf/mcp/client.py`** (`MCPClient`): sync JSON-RPC over
  stdio. Stdlib only. One subprocess per configured server, spawned
  at `Engine.__init__` and killed on process exit via `atexit`.
  Protocol version `2024-11-05`; initialize → notifications/initialized
  → tools/list → tools/call cycle.
- **Registry in `alf/mcp/registry.py`**: turns each discovered MCP
  tool into a dynamically-created `Tool` subclass with name
  `<server>:<tool>` — e.g. `github:create_issue`,
  `notion:search_pages`. Collision with native tools impossible
  because the colon never appears in native names.
- **Tool description caveat**: every wrapped MCP tool's description
  gets prepended with the same "data, not instructions" warning
  `email` uses. Third-party MCP content could carry prompt-injection
  payloads; the agent is told to treat it as data and surface it to
  the user.
- **Config** lives under `mcp.servers.<name>` in `config.yaml`:
      mcp:
        servers:
          github:
            command: npx
            args: ["-y", "@modelcontextprotocol/server-github"]
            env:
              GITHUB_TOKEN: env:GITHUB_TOKEN
  The `env:VAR` form expands against the live process env at spawn
  time — secrets stay in `~/.alf/.env`, never in `config.yaml`.
- **Setup wizard** (`alf setup → MCPs`): list/add/remove/inspect.
  Add flow: name, command, args, env var refs. Spawns + handshakes +
  lists tools BEFORE writing to config — if it can't connect, nothing
  lands. Same guarantee as the email wizard.
- **CLI**: `alf mcp list`, `alf mcp test <name>`, `alf mcp remove
  <name>` for quick inspection outside the setup menu.
- **Failure isolation**: one MCP failing to start doesn't take the
  whole engine down. Its tools just don't appear; a warning goes to
  the log. Other MCPs start normally.
- **Skills reference MCPs, never install them** (see
  `alf/prompts/create_skill_guide.md`). A skill like
  `github-triage` declares `github` MCP as a Prerequisite; the user
  has already opted in once via setup. Keeps the pending-gate and
  install-gate boundaries clean.

### Schedule daemon (`alf schedule start`)

- **Separate process.** PID at `schedule/scheduler.pid`, logs at
  `schedule/logs/scheduler.log`.
- **Lifecycle mirrors the gateway.** Runs only when the user starts it
  (`alf schedule start`) or installs it as a service (v0.3). No
  auto-spawn from TUI, gateway, or tools. Adding a job writes the file
  but delivery waits until the daemon is up — the `add` response tells
  the user exactly how to activate.
- **Independent of the gateway.** Killing the gateway doesn't kill the
  daemon, and vice versa. Proactive outreach (`send_message`) doesn't
  need the gateway listener up.
- **CLI:** `alf schedule [start|stop|status|logs|run-once]`.
- **`ensure_running(home)`** lives in `scheduler.run` as a helper for
  the future `alf schedule install` flow; nothing calls it at runtime
  today.
- **Tick every 30s.** Reads `schedule/jobs.json`, fires due jobs, updates
  `last_run_at` (even on failure, to avoid tight re-fire loops). Uses
  `croniter` for expressions.
- **Two job kinds:**
  - `cron` — standard expression (`0 9 * * *`). First run fires on the
    first tick after creation (nice feedback); subsequent runs anchor
    off `last_run_at`.
  - `inactivity` — fires once the newest `sessions/*.json` mtime is
    older than `after_hours`. Per-job cooldown: won't re-fire within
    `after_hours` of its own last fire.
- **Execution model.** Shells out to `alf chat --once <wrapped prompt>`
  so a crashing job can't take the daemon down. The prompt gets a tiny
  `[SCHEDULED: …]` preamble so the agent knows the reply will be pushed
  rather than displayed live.
- **Delivery** goes through `gateway.delivery.send_to(platform,
  chat_id, text)` — same path as the `send_message` tool. Default
  `chat_id` is the first entry in `{PLATFORM}_ALLOWED_CHAT_IDS`.
- **Persistence across reboot.** `alf gateway install` and
  `alf schedule install` register the daemon as a system service —
  launchd on macOS (`~/Library/LaunchAgents/com.alf.<name>.<profile>.plist`,
  `RunAtLoad=true` + `KeepAlive=true`) or systemd --user on Linux
  (`~/.config/systemd/user/alf-<name>-<profile>.service`,
  `Restart=on-failure`). Auto-starts immediately and at every login.
  Per-profile: the service label includes the profile so `alf -p work`
  and `alf -p personal` coexist. Install refuses if the daemon is
  already running manually (avoids orphan-PID races); `alf <name> stop`
  first. Uninstall does the reverse — `launchctl bootout` /
  `systemctl --user disable --now` + deletes the unit file. All the
  logic lives in `alf/service.py`; the CLI glue is in
  `_install_daemon` / `_uninstall_daemon` in `alf/cli.py`.

### `/compact`

- Mounts a `ToolCard` (name="compact") for visual consistency with other
  tools.
- Runs in `@work(thread=True)`. Uses `call_from_thread` for UI updates.
- **Gotcha:** don't pass built-in methods (`dict.pop`, etc.) to
  `call_from_thread` — Textual inspects signatures and built-ins trip it.
  Wrap in a regular method (see `_drop_active_tool`).

### Delegate (research sub-agent)

- **When to use** (per system prompt): open-ended research needing
  multiple searches + fetches ("investigate X", "compare Y vs Z").
- **Scope**: read-only toolset `{web_search, web_fetch, web_extract,
  read_file, grep, glob}`. No memory/terminal/write. Enforced by
  `SUB_AGENT_TOOLS` allowlist.
- **Budget**: 12 iterations *of LLM round-trips* (not tool calls — a
  parallel `search + 3 extracts` in one turn still counts as 1).
- **Synthesis fallback**: when budget runs out, delegate forces one
  final no-tools `llm.complete()` with "stop researching, report now
  with what you have". Avoids the "[delegate gave up]" footgun where
  the main agent retries the whole thing.
- **Interrupt**: polls `tool_state.is_interrupted()` between iterations
  and between tools; returns "[delegate: interrupted]" on the first hit.

### Terminal tool

- Replaces the old `bash` tool (renamed). Actions:
  - `run` (default): blocking, up to `timeout=120s`.
  - `background`: spawns detached with `start_new_session=True`, writes
    a `.meta` file under `~/.alf/run/bg/<pid>.meta` and a log file
    under the same dir. Returns `pid=`.
  - `status` / `output` / `kill` (requires `pid=`): query or stop a bg
    job. Uses `os.kill(pid, 0)` for liveness.
- **ANSI stripped** from stdout/stderr before returning to the LLM so
  color codes don't pollute reasoning.
- Background output capped to last 8000 chars on read.

### File tools

- **`read_file`** sniffs first 8KB for binaries: null byte OR >30%
  non-text bytes → refuses with size (avoids dumping PNG/ZIP bytes
  into the LLM context).
- **`write_file`** uses atomic overwrite — writes to `path.tmp`, then
  `os.replace` onto target. If the process crashes mid-write, the
  original is untouched. **No `.bak` sibling** — git (or user's own
  backups) handles version recovery; `.bak` clutter was rejected.
- **`glob` / `grep`** skip noise dirs by default (`.git`, `node_modules`,
  `.venv`, `__pycache__`, `.pytest_cache`, `dist`, `build`, `.next`,
  `.cache`). Pass `include_noise=true` to recurse into them.

### Memory tool — Approach C + .bak

- **Approach C** (post-mutation state): `memory(add)` / `replace` /
  `remove` return the full current snapshot of the target file after
  mutation. The agent sees its own write in the same turn.
- **Two-tier dedup** on `add`:
  1. Substring match after case/accent/punctuation fold.
  2. Token Jaccard-ish: if ≥70% of the shorter entry's content tokens
     are in the other, treat as duplicate. Stopwords filtered (tiny
     Spanish/English list).
- **`.bak` snapshot** in `backup_file(path)` before every write. Only
  for memory files — not for general `write_file`.
- System prompt includes: **"Read before add when unsure"** — the agent
  is nudged to call `memory(read)` first if uncertainty about dup.

### Filesystem sandbox

alf can only operate on files inside approved roots:

1. **Primary root** — one of:
   * ``cfg.workspace`` from the profile's ``config.yaml`` if set
     (e.g. ``workspace: ~/git``). Overrides cwd entirely.
   * Otherwise ``os.getcwd()`` at the time of the call (whatever
     directory alf was launched from).
2. **Profile home** — ``~/.alf/`` (or ``~/.alf/profiles/<name>/``).
   alf must be able to inspect its own skills, memories and sessions.

File tools (``read_file``, ``write_file``, ``edit_file``, ``glob``,
``grep``) validate via ``alf/tools/_paths.py :: check_path``. Anything
outside both roots is rejected with a clear message.

**`/workspace` slash** (TUI):
- ``/workspace`` → show the effective root.
- ``/workspace <path>`` → persist ``workspace: <path>`` to config.yaml
  and reload. Takes effect on the next tool call.
- ``/workspace clear`` → remove the pin; fall back to cwd.

**Warning on launch**: if ``workspace`` is unset in the config, an
``ErrorLine`` appears at the top of the chat telling the user cwd is
the scope. Forces a conscious choice.

**Caveat — terminal tool is NOT sandboxed.** The shell can reach
anywhere via ``cat ../foo``, ``$HOME``, command substitution, etc.
Regex-gating shell commands would be false security. The system prompt
tells alf not to use ``terminal`` to bypass a blocked file tool, but
that's prompt-level only.

**Gateway**: today, the gateway subprocess inherits cwd from the
service (launchd/systemd) — non-deterministic. If you paired a profile
without a workspace, alf will sandbox to whatever cwd the service got.
Set ``workspace`` on any gateway-paired profile. A future change may
force validation at ``alf gateway start``.

### Status bar

- Shows `⚡ <model> │ ctx <tokens>/200K ▓░░░ <pct>% │ $<cost>`.
- **ctx uses `session.last_ctx_tokens`** (input tokens of the last LLM
  call), NOT cumulative input+output. After `/compact`, re-estimates
  `last_ctx_tokens` from total chars / 4. Persisted to `session.json`
  so resume shows the real value.
- **Color threshold** on the bar: accent below 60%, yellow 60-80%, red
  ≥ 80% (prompt to `/compact`). Model name and ⚡ icon always use the
  accent color.

### Reinstall workflow

```bash
cd /Users/javi/git/alf
uv tool install . --reinstall --no-cache
```

- `--reinstall --no-cache` needed when deps change.
- **Gotcha:** `uv tool install` wipes pytest from the tool venv. To run
  tests:
  ```bash
  /Users/javi/.local/share/uv/tools/alf/bin/python -m ensurepip
  /Users/javi/.local/share/uv/tools/alf/bin/python -m pip install -q pytest
  /Users/javi/.local/share/uv/tools/alf/bin/python -m pytest -q
  ```

### Textual gotchas we've hit

- **Widget naming:** don't override `_render` on a Widget subclass — it
  collides with Textual's internal render. Use `_refresh_display` or
  similar.
- **Widget attribute `name`** is read-only on Widget. If you need a
  custom `name` attr (e.g. on `ToolCard`), call it `tool_name`.
- **`set_interval(period, callback)`** where callback does `self.refresh()`
  works fine. The timer auto-stops when widget is removed if stored.
- **`rich.Live` breaks prompt_toolkit's terminal state.** Don't mix Live
  contexts with prompt_toolkit prompts. We removed all rich.Live code
  when migrating to Textual.
- **Don't FD-redirect `/dev/null` during LLM calls inside Textual.**
  Textual renders via stdout; an FD redirect freezes the UI. We removed
  the redirect from `llm.complete()` (only left in `_silence_litellm()`
  which runs at import time).
- **`uv tool install`** pins `textual==8.2.3`. `ALLOW_SELECT=True` is
  default in this version, enabling click-drag text selection.
- **On exit, restore terminal manually.** Textual sometimes leaves mouse
  reporting on after crash → every mouse movement prints escape codes.
  `_restore_terminal()` in cli.py sends the right sequences in a
  `finally` block around `app.run()`.

---

## Code layout (`/Users/javi/git/alf/`)

```
alf/
├── __main__.py                  entry point: python -m alf
├── cli.py                       click CLI + bootstrap + `chat --once` for gateway
├── home.py                      HOME_DIR resolution + profile paths
├── config.py                    YAML loader; ReflectConfig, ToolsConfig,
│                                WebExtractToolConfig; resolve_model()
├── memory.py                    MemoryStore with dedup (two-tier), .bak,
│                                backup_file(), fuzzy_contains, _content_tokens
├── session.py                   Session dataclass; last_ctx_tokens persisted
├── engine.py                    LLM streaming loop; interrupt flag + checks;
│                                tool_state wiring (emit + interrupt getter)
├── llm.py                       stream() + complete() litellm wrappers
├── model_selector.py            OLD questionary-based picker (only used by
│                                `alf model` CLI subcommand and `alf setup`)
├── providers/                   metadata for the picker
│   └── …                        anthropic/openai/google/groq/openrouter/custom
├── tools/
│   ├── base.py                  Tool ABC + ToolResult
│   ├── _state.py                set_emit / emit_state / set_interrupt_getter
│   ├── create_skill.py          pending gate + origin + quota + scanner
│   ├── edit_skill.py            rewrite body with origin-gate + .bak
│   ├── delete_skill.py          rm dir with origin-gate
│   ├── delegate.py              research sub-agent (read-only toolset)
│   ├── terminal.py              run/background/status/output/kill
│   ├── browser.py               STUB, not registered (v0.2 Playwright)
│   └── <other>.py               read_file, write_file, edit_file, grep, glob,
│                                todo, memory, web_*, schedule, send_message,
│                                session_search
├── skills/meta/consolidate-memory/SKILL.md    only bundled skill
├── prompts/
│   ├── default_personality.md   seed for ~/.alf/PERSONALITY.md
│   ├── system_prompt.md         tool-use + inline memory/skill triggers +
│                                delegate guidance
│   ├── create_skill_guide.md    rules for create_skill
│   └── skill_template.md
├── tui/
│   ├── __init__.py              re-exports AlfApp
│   ├── app.py                   main App, event handlers, slash routing
│   ├── widgets.py               UserMessage, AssistantMessage, ToolCard,
│                                DimLine, ErrorLine, AlfHeader
│   ├── screens.py               HelpScreen, MemoryScreen, ToolsScreen, CostScreen
│   ├── model_screen.py          ProviderScreen + ModelListScreen + _ApiKeyScreen
│   ├── formatting.py            arg_hint, result_hint, truncate, shorten_*
│   └── theme.tcss               CSS for layout + OptionList + modals
├── gateway/
│   ├── run.py                   asyncio loop; loads .env; subprocess per msg
│   ├── setup.py                 interactive Telegram config (questionary)
│   ├── base.py, delivery.py
│   └── platforms/
│       ├── telegram.py          real long-poll via getUpdates
│       └── webhook.py           stub
├── scheduler/
│   ├── __init__.py
│   └── run.py                   tick loop, run_job, ensure_running (auto-spawn)
├── email/
│   ├── __init__.py
│   ├── client.py                IMAP+SMTP EmailClient (stdlib-only)
│   └── setup.py                 interactive wizard (hooked into alf setup)
└── mcp/
    ├── __init__.py
    ├── client.py                MCPClient (stdio JSON-RPC)
    ├── registry.py              load + register MCP tools
    └── setup.py                 interactive wizard

tests/                           13 files, 69 unit + 6 LLM-tagged
docs/CONTEXT.md                  this file
pyproject.toml                   deps: litellm, rich, prompt_toolkit, click,
                                 questionary, html2text, ddgs, textual>=0.86
```

## Home layout (`~/.alf/`)

```
PERSONALITY.md                   agent identity (user-edited, optionally reflected)
config.yaml                      model, providers, reflect, tools, tui
.env                             API keys (OPENROUTER_*, TELEGRAM_*, ...)
.env.example                     template
.history                         prompt_toolkit history (legacy — not used in TUI)
memories/
├── USER.md                      facts about user
└── MEMORY.md                    agent notes on env/tools
skills/<category>/<name>/        user skills (override bundled)
sessions/*.json                  chat history, one per session
cache/openrouter_models.json     24h TTL
schedule/{jobs.json, scheduler.pid, logs/scheduler.log, output/}
gateway/{gateway.pid, logs/gateway.log}
```

---

## Decisions discarded (don't relitigate)

- **Go + Bubbletea rewrite.** Rejected.
- **rich.Live + prompt_toolkit inline UI.** Worked but had ceiling (no
  modals, weird suspend races). Replaced by Textual.
- **Full Textual app with sidebar + modals + fullscreen chrome** (first
  attempt). Rolled back as too heavy. Current is mother.py-style minimal.
- **Pending-approval files** (`pending_skills.md`, `pending_personality.md`).
  Replaced with inline `y`/`n` prompts in reflect.
- **SQLite state.db.** Plain JSON files scan fast for <1000 sessions.
- **Auto-reflect on Ctrl+C.** Dangerous.
- **duckduckgo-search.** Deprecated → migrated to `ddgs`.
- **Textual 0.80 < 0.86.** Upgraded to 8.2.3 for `ALLOW_SELECT`.
- **Post-session `/reflect` loop.** Tried it — `/reflect` slash +
  auto-trigger + `alf/reflect.py` + 2 tests. Removed because Hermes
  doesn't do post-session reflection either (their model is also
  inline-only via `memory_tool`), and our TUI implementation was broken
  (silenced Console output + `Prompt.ask` blocking the worker thread).
  Replaced by hardened system prompt + tool description rules for
  inline `memory(add)` + `create_skill` calls.
- **Regex-gating shell commands** to enforce sandbox. Too many false
  positives (user having a `/documents` dir in workspace, legitimate
  `..` usage, env-var expansion, command substitution). `cwd=workspace`
  + prompt discouragement covers 90%; real enforcement needs OS-level
  sandbox (v0.2 §G).
- **`.bak` sibling on every `write_file`.** Tried it, rejected —
  clutters every directory alf writes in. Kept `.bak` only on memory
  files (USER/MEMORY/PERSONALITY) where it actually pays off.

---

## v0.2 — roadmap

Everything that's *not* shipped. Consolidated in a single bucket — no
v0.3 / v0.4 labels here; priorities shift, and small features can
piggyback on bigger ones. Picked loosely by value × ease.

### High value, cheap

#### A. `send_message` — outbound messaging
alf currently RECEIVES from Telegram via the gateway but cannot send
unsolicited. Add a `send_message(channel, text)` tool where channels
are declared in `config.yaml`:
```yaml
notifications:
  - {kind: telegram, chat_id: 12345}
  - {kind: email, to: foo@bar.com}
```
Unlocks "ping me when this long task finishes", "notify me at 9am
about X" (combined with `schedule`). Reuses the `TELEGRAM_BOT_TOKEN` you
already have.

#### B. Interactive browser (Playwright)
`alf/tools/browser.py` is a stub and NOT registered today (kept out of
the registry import list). To ship:
1. Replace `Browser.run` with a Playwright-backed impl: headless
   Chrome, persistent context under `~/.alf/browser/`, actions
   `text | screenshot | click | fill | navigate`.
2. Add `playwright` to `pyproject.toml` (+ one-time
   `playwright install chromium`).
3. Re-register `browser` in `alf/tools/__init__.py`.

Enables online shopping, logins, form-filling — things that today
fail because `web_fetch` is read-only.

#### C. web_search quality (Tavily / Brave)
DDG via `ddgs` works but quality is variable (bad queries → TikToks).
Drop in Tavily (1000/mo free) or Brave Search as a fallback provider:
if DDG returns <3 results, retry via Tavily. API-key optional in
`.env`.

#### D. Vision (`read_image`)
~50 lines. LiteLLM already supports vision models. A `read_image(path,
question)` tool that sends the image + prompt to whichever model is
active (if vision-capable). Falls back to "model is text-only" error.
Useful for "lee el screenshot que he guardado".

#### E. Multi-profile CLI ✅ shipped
`alf profile list` and `alf profile create <name>` cover profile
management. Resolution is fully explicit (``-p`` flag, ``ALF_PROFILE``
env, or the default ``~/.alf``) — no sticky "current profile" file,
no hidden state. Users who want persistence wire a shell alias
(``alias alfw='alf -p work'``) or export ``ALF_PROFILE``. All the
daemons (gateway, schedule) and their installed services already
carry the profile in their label, so profiles truly coexist.

### Medium value

#### F. Gateway workspace validation
When `alf gateway start` runs, verify every paired profile has a
`workspace` set in its config. If not → refuse to start with clear
message. Prevents "headless alf inherits launchd cwd" silent bad
scope.

#### G. Terminal + code execution sandbox (OS-level)
Today: file tools hard-gated to workspace + `~/.alf/`. Terminal is
only soft-hardened (`cwd=workspace` + prompt discouragement). A
motivated agent or explicit user request still reaches `~/Documents`
via shell. Real isolation needs OS-level sandboxing:

- **macOS**: `sandbox-exec -f profile.sb` (native, zero install).
- **Linux**: `bubblewrap` or `firejail`.
- Write a profile whitelisting workspace + `~/.alf/` + network (for
  HTTP tools) + git tooling paths.
- Wrap `subprocess.run/Popen` in `terminal._run_fg/_run_bg` to go
  through the sandboxed launcher when available; fall back to bare
  subprocess if not installed.

Docker / E2B / Modal also work but are heavier; `sandbox-exec` is the
right first cut on macOS.

**Scope includes MCP subprocesses.** Each MCP server alf spawns today
inherits the user's full privileges (filesystem, env, network). When
this task lands the same `Popen` wrapper must apply to
`alf/mcp/client.py`'s spawn path, and each server's config gets a
`sandbox:` subkey declaring its required paths and hosts — e.g.
`filesystem` MCP gets only its declared directories, `github` MCP
gets only `api.github.com`. Mitigations today: tokens with narrow
scopes + opt-in-only MCPs (no auto-install). Good enough for a
personal setup, but not for a shared / untrusted-MCP world.

#### H. Home Assistant integration
Only worth building if Javi runs HA. Hermes has `homeassistant_tool`
as a reference. Requires `HA_URL` + long-lived token in `.env`.
Typical uses: read sensors, toggle lights/scenes, query occupancy.
**Waiting on Javi confirming he has HA.**

#### I. MCP client
High-leverage: connect to arbitrary MCP servers without writing alf
tools. Adds a transport layer (stdio + SSE). Good once the basics are
stable and the ecosystem grows.

#### J. Anti-bot browsing (camoufox)
Stealth Firefox fork for Cloudflare-protected sites. Hold until
`browser` (Playwright) is proven useful — then consider adding
camoufox on top for hard sites. Free but heavy (+200MB binary).

### UX polish (lower priority, but easy wins)

#### K. Scroll resilience under heavy streaming
Current scroll logic is good for normal use but may need tuning if
streaming is very fast + tool cards animate simultaneously.
`call_after_refresh` + dual timers cover most cases; watch for
regressions.

#### L. Reasoning-as-state
The LLM often emits text between tool calls ("let me try X
instead…"). Currently discarded. Could be surfaced as the state
label of the NEXT tool card. Adds personality. Javi said "pensamos
luego".

#### M. TTS / STT / voice-mode
Out of scope for core agent. If added, lives in a separate surface
(voice gateway) — don't pollute the TUI.

### Multimodal output

#### N. Image generation
A `generate_image(prompt, style)` tool using the active vision model
or a dedicated endpoint (DALL-E, SD). Useful for "hazme un logo
rápido". Low priority unless a concrete use case appears.

---

## Non-obvious things future-me should know

- **`rich.markup.escape()`** — wrap any user-controlled substring you put
  into `Text.from_markup()`. Many crashes came from this.
- **Tool results are capped at 10,000 chars** in engine.py. For large
  outputs (web_fetch raw HTML), the model sees a truncated view.
- **`last_ctx_tokens` vs `input_tokens`.** `last_ctx_tokens` is the
  current context size; `input_tokens` is cumulative across the
  session. Header shows the former.
- **`call_from_thread` + built-in methods = crash.** Always wrap
  `dict.pop` / similar in a Python function.
- **Gateway subprocess uses `alf chat --once`.** It's a separate
  codepath from the TUI — simpler, non-streaming, just prints final
  assistant text. Changes to how conversations feel in TUI don't
  affect the gateway.
- **`ALF_HOME` env var** — set by gateway subprocess to route to the
  correct profile. Also used by tests for isolation.
- **Tool_id tracking dict (`_active_tools`) lives on AlfApp instance.**
  Indexed by tool_call id from the LLM.
- **The old `alf/model_selector.py` (questionary) is still used** by
  `alf model` CLI subcommand and `alf setup`. The TUI uses
  `alf/tui/model_screen.py` instead.
- **`browser.py` is NOT registered.** File exists, tool class exists,
  but it's intentionally absent from the `alf/tools/__init__.py` import
  + registry loop. Don't be confused if the LLM doesn't mention it —
  reactivate it when Playwright lands.
- **`cfg` must be loaded BEFORE `super().__init__()` on `AlfApp`** —
  Textual calls `get_css_variables()` from its constructor, and that
  reads `self.cfg.tui.accent`. Race condition otherwise.
- **Delegate tool budget is LLM iterations, NOT tool calls.** One turn
  can have N parallel tools and still counts as 1 iteration. 12 is
  plenty for most research tasks.
- **Engine calls `tool_state.set_interrupt_getter(None)` after the tool
  loop** to clear the closure. If you forget, the getter from a past
  turn will keep firing on the next unrelated tool call.
- **Accent color for learning tools** (`memory`, `create_skill`) lives
  in `LEARNING_TOOLS = {"memory", "create_skill"}` in
  `alf/tui/widgets.py`. Add new learning-style tools there.
- **`/skills` is a separate modal from `/memory` and `/tools`.**
  `/memory` shows USER/MEMORY/PERSONALITY files. `/tools` shows the
  registered tool list with descriptions. `/skills` shows the skill
  dirs and is the only one with interactive actions (approve/reject/view).

## Recent changes (since first CONTEXT.md)

1. Migrated UI from `rich.Live + prompt_toolkit` to Textual 8.2.3.
2. Native `/model` via Textual OptionList screens (no suspend).
3. `ddgs` replaces dead `duckduckgo-search`.
4. `web_fetch` → Jina Reader first, direct fallback.
5. `web_search` new tool.
6. Tool state streaming (`_state.py` + `emit_state`).
7. Memory files uppercase (USER.md / MEMORY.md / PERSONALITY.md).
8. Memory mutations return full current state (approach C).
9. Rich markup escape on user-controlled content (crash fix).
10. Status bar moved to bottom, above Input.
11. `Ctrl+Y` copies last response.
12. `max_steps_per_turn` bumped from 12 → 40, configurable.
13. Scroll lag fix (`call_after_refresh` + `immediate=True`).
14. `last_ctx_tokens` separated from cumulative `input_tokens`.
15. Sessions without user messages no longer saved.
16. Gateway log rotation (1MB, single file).
17. `/compact` shown as a ToolCard (visual consistency).
18. Textual crash fix: FD redirect removed from `llm.complete()`.
19. Terminal restore on exit (`_restore_terminal()`).
20. **Reflect (post-session) removed.** `/reflect` slash, auto-trigger,
    `reflect.py`, `ReflectConfig`, `session.reflected`,
    `test_reflect_unit.py`, `test_llm_reflect.py` — all deleted.
    Replaced by stronger inline prompting.
21. **Skills: pending gate + origin field**. Agent-created skills land
    in `~/.alf/skills/_pending/<name>/` with `origin: agent`; user
    reviews with `/skills` (approve/reject/view). Quota 5 pending,
    anti-dup across live+pending, regex security scanner.
    New tools: `edit_skill`, `delete_skill` (origin-gated).
22. **`/skills` modal** with keys `a/r/v`. Auto-moves approved skills
    into the right category dir (from frontmatter).
23. **`create_skill` + `memory`** rendered in accent color on ToolCard
    (learning tools) so the user sees in-flight learning.
24. **Inline `memory(read)` hint** added to system prompt: "Read
    before add when unsure" — avoids semantic duplicate writes.
25. **Two-tier memory dedup**: substring + token-overlap (70%
    max-containment). Catches paraphrases like
    "Javi vive en Hua Hin" vs "Me llamo Javi. Vivo en Hua Hin.".
26. **`bash` → `terminal`** with actions `run`/`background`/`status`/
    `output`/`kill`. Background jobs tracked under `~/.alf/run/bg/`.
    ANSI codes stripped from output before sending to LLM.
27. **`read_file` binary detection**: sniffs 8KB for null byte / >30%
    non-text bytes, refuses early with size.
28. **`write_file` atomic overwrite** (`tmp + os.replace`, no `.bak`).
29. **`glob` / `grep` default excludes** (`.git`, `node_modules`,
    `.venv`, etc.); `include_noise=true` to opt in.
30. **`delegate` tool** for deep research. Read-only sub-toolset,
    12-iteration budget (counted by LLM round-trips), synthesis
    fallback when budget runs out. Honors engine interrupt via
    `tool_state.is_interrupted()`.
31. **Interrupt on new input**: flag polled at 3 points in engine,
    immediate visual feedback (DimLine + cards marked `[interrupted]`),
    session stays coherent (`[skipped — user interrupted]` tool
    messages preserve OpenAI-style pairing).
32. **`browser` unregistered** (still stub). Path to v0.2 documented.
33. **Slash autocompletion** via `SuggestFromList` (built-in Textual).
34. **Accent color configurable** via `tui.accent` in `config.yaml`
    (default `#ff8800`). Context bar shifts color by % usage
    (accent→yellow at 60%→red at 80%).
35. **Copy with pbcopy/xclip/wl-copy/xsel fallback** + OSC-52; safer
    across terminals and SSH.
36. **AssistantMessage accepts initial content** so resume paints
    assistant replies correctly (fixed "respuesta no aparece en
    --continue").
37. **ToolCard spinner reduced to 4 Hz** from 10 Hz — less refresh
    pressure on the event loop when multiple cards run concurrently.
38. **`last_ctx_tokens` persisted** to `session.json`; resume shows
    real context size (not 0).
