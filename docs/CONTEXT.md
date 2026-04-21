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

## Language

**All text inside the `alf/` source tree is written in English.** That
includes code, docstrings, tool descriptions, system prompts, commit
messages, CLI help, error messages, seed config comments — everything
except actual user-facing output that the LLM generates at runtime
(which follows the user's language).

Why: `alf` is open-source, the LLM reads these strings at every turn,
and examples embedded in tool descriptions bias the agent toward that
language. A tool description with "saying \"lo recordaré\" without a
tool call" nudges the model toward Spanish replies; the English
equivalent keeps it neutral.

This rule is load-bearing for tool descriptions (which ship to the
LLM each turn) and for any prose the LLM reads. It's also the
enforcement path for code readers who aren't native Spanish speakers.

Sessions that accidentally seed Spanish strings into source get
caught by grep at review time; fix with a direct English rewrite, no
translation layer.

## Code conventions

**No human-facing comments in `alf/` source.** The reader of this code is
an LLM — this Claude Code session, a future one, or a delegated
sub-agent. Narrative prose, banner dividers, section labels, and
"rationale" docstring essays are token tax with no corresponding
benefit. Well-named identifiers carry the WHAT; commit messages and
`docs/CONTEXT.md` carry the WHY that outlives a single change.

Applies across `alf/`. Out of scope: `tests/` (executable spec), `docs/`
(human-facing by design), tool `description` strings inside `Tool`
subclasses (those ARE read by the LLM at every turn and deserve care).

Allowed, rarely:
- Class docstrings that document a contract the signature can't (often
  `Tool` subclasses where `description` + `parameters` shape LLM behaviour).
- A single-line module docstring for orientation.
- An inline note pinning a concrete workaround to a concrete bug
  ("questionary's `class:highlighted` flashes the accent tint — use
  the list-title path to bypass it").

Never:
- `# ---- Section ----` banners.
- `# Bootstrap` / `# Helpers` / `# Foo` section labels before a def.
- Docstrings on private functions (names starting with `_`).
- Multi-paragraph docstrings on public functions.
- Restatement docstrings (`"""Return the workspace path."""` on a
  function already named `workspace_path()`).
- `# do the thing` above `do_the_thing()`.

This policy was enforced repo-wide in commit `a07e40a` (–1,431 lines of
comments). Future changes that add comments of the "banned" categories
should be removed before merging — no exceptions for "this one is
important", because every previous session made that same argument and
we ended up with a 1,630-char `memory` tool description and 161 banner
lines.

## CLI + UI conventions

The CLI surface is small and stable. Verbs are shared across groups
so the user doesn't relearn per feature.

**Commands** (user-facing, hidden plumbing marked internal):

    alf                              → launch the TUI
    alf -c / alf --continue          → launch the TUI, resume last session
    alf -p <name>                    → profile flag, combinable with any command

    alf chat                         → alias for `alf`
    alf chat --once "<text>"         → one-shot turn to stdout (pipe-friendly)
    alf chat --once ... --emit-events   (INTERNAL, hidden) gateway subprocess
                                        contract: stdout becomes JSON-lines

    alf setup                        → single interactive entry for per-profile
                                        config: Model / Gateways / MCPs

    alf profile list                 → list profiles, mark the active one
    alf profile create <name>        → bootstrap a new profile tree
    alf profile remove <name>        → delete after safety checks + confirm

    alf gateway   start|stop|status|logs|install|uninstall
    alf schedule  start|stop|status|logs|install|uninstall|run-once
    alf mcp       list|test              (read-only; mutations live in `alf setup`)

**Shape rules:**

- Containers (profile) get ``list / create / remove`` verbs.
- Daemons (gateway, schedule) get ``start / stop / status / logs /
  install / uninstall``. Schedule adds ``run-once`` for manual ticks.
- MCP gets ``list / test / remove`` — it has no daemon of its own
  (servers spawn as children of the Engine) so no ``start/stop``.
- Interactive wizards live under ``alf setup``. There is NO
  duplicate per-feature wizard command — don't add ``alf model``
  or ``alf gateway setup`` back; always ``alf setup → ...``.

**UI module: ``alf/ui.py``.** Every interactive prompt and menu passes
through it. Raw ``questionary.*`` is forbidden outside this module —
enforced by convention. Helpers:

- ``banner(title, subtitle, hint)`` — the wizard/menu header block.
- ``menu(message, items, home, close)`` — questionary.select with our
  ``◆`` pointer tinted by ``tui.accent`` and the standard
  ``↑↓ / ENTER / ESC`` instruction line. The close item is added
  automatically with value ``None``; callers treat ``None`` as "out".
- ``text / password / confirm`` — input prompts with hydration semantics.
  ``password(label, current=...)`` is "ENTER keeps the existing value";
  everyone else uses ``default=current`` so empty input clears.
- ``row(label, status)`` — left-pads the label to ``LABEL_WIDTH`` and
  joins with ``·``. Menus across the app align columns because they
  use this to build titles.
- ``ok / fail / warn / dim / saved / cancelled`` — feedback lines with
  the same Rich styling everywhere.

**Menu close wording:**

- Top-level menu (``alf setup``) → ``Exit`` (closes the program path).
- Sub-menus (``Gateways:``, ``MCP servers:``, ``Manage saved keys``) →
  ``← Back`` (returns to the parent).
- Wizard aborted mid-flow (ESC, blank required field) → ``cancelled``.

Mixing ``Exit`` / ``Back`` / ``Cancel`` within one context is a bug.

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
  `skill(create)` during the conversation based on triggers.
- **Skills — live by default**: agent-created skills land directly
  under `~/.alf/skills/<category>/<name>/` with `origin: agent`
  frontmatter, a security scanner checks on every write, and a quota
  caps how many agent-owned skills coexist.
- **File tools follow terminal's posture**: shared sensitive-path
  denylist (`/etc`, SSH keys, creds, …); no workspace wall. Real
  workspace-only isolation is available via the opt-in OS sandbox
  (Layer 2 in `docs/SECURITY.md`).
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
  `memory` and `skill` (learning tools) so the user sees when alf
  is growing.
- **Slash autocompletion** via Textual's built-in `SuggestFromList` — type
  `/he` → ghost `/help`, right arrow accepts.
- **`/model` native Textual screen** (`alf/tui/model_screen.py`): uses
  `OptionList`, not `suspend()` + questionary. Api-key prompt is its own
  `ModalScreen[str]`.
- **`/help`, `/memory`, `/tools`, `/cost`, `/skills`** are `ModalScreen`s
  (`alf/tui/screens.py`). `Esc` closes.
  - **`/skills`** lists every installed skill grouped by category,
    with a `v` key to view SKILL.md body.
- **Slash commands** also: `/clear`, `/compact`, `/exit`. **No
  `/reflect`** (removed — reflection is inline during conversation).
- **`/compact`** mounts a ToolCard of its own so the user sees the
  operation's progress like any tool.
- **Interrupt on new input:** typing a new message while a turn is still
  running cancels the current work and starts fresh. `engine.interrupt_requested`
  is polled at 3 points (between LLM iterations, mid-stream, between
  tool calls). Long-running tools (e.g. `research`) poll
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
- **17 tools** registered: `read_file`, `write_file`, `edit_file`,
  `terminal`, `search`, `todo`, `web_search`, `web_fetch`,
  `web_extract`, `schedule`, `memory`, `session_search`, `skill`,
  `research`, `send_message`, `email`, `config`.
  - **`browser`** file exists but is **not registered** (stub). See
    "Open questions / pending" section 6 for the Playwright roadmap.
- **Curated memory** (`memories/USER.md`, `memories/MEMORY.md`) with §
  entry delimiter, char limits (1375 / 2200), **accent+case insensitive
  dedup** plus **token-overlap dedup** (70% max-containment — catches
  paraphrases like "Vivo en Hua Hin" vs "Javi vive en Hua Hin"), no
  silent deletions. `.bak` snapshot before every mutating write.
- **`PERSONALITY.md`** at home root. Edited by user or via `memory`
  tool (target="PERSONALITY.md").
- **Skills** under `~/.alf/skills/<category>/<name>/`. All skills are
  live — no pending/approval state. The `origin` field in the
  frontmatter distinguishes `agent` (self-created) from `user` (hand-
  authored); modifications to user skills require
  `confirm_user_skill=true`. Subdirs: `scripts/`, `references/`,
  `assets/`, `secrets/` (mode 0700, gitignored, scan skipped),
  `state/` (gitignored, scan skipped, runtime persistence). Security
  scanner runs on every `create`/`add_file`/`patch`. Quota caps
  agent-owned skills.
- **Inline learning, not post-session reflect.** The system prompt tells
  the agent to call `memory(add, ...)` and `skill(action='create', ...)`
  during the conversation whenever the triggers apply. The `/reflect`
  post-session pass was removed — it added complexity and Hermes doesn't
  do it either.
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

### Skills

One unified `skill` tool ([alf/tools/skill.py](alf/tools/skill.py))
covers the full lifecycle: `create`, `edit` (SKILL.md body), `patch`
(targeted find-and-replace inside any skill file), `add_file`,
`remove_file`, `delete`, `list`, `view`. Skills live under
`~/.alf/skills/<category>/<name>/` and are live-by-default — no
pending/approval state (that design existed briefly in early v0.1
and was removed; the friction outweighed the benefit).

**Frontmatter** auto-populated on `create`:

- `name`, `description`, `category` (required, from a fixed enum
  plus `miscellaneous` as fallback).
- `version: 0.1.0`, `origin: agent|user`, `created_at`.
- `requires_env: []`, `tools: []`, `stores_secrets: bool`.

**Subdirectory contract**:

- `scripts/` — executable (python/bash). Scanned.
- `references/` — docs/data the LLM reads as context. Scanned.
- `assets/` — static files (templates, images, seed data). Scanned.
- `secrets/` — credentials, mode `0o700`, gitignored, scanner
  **skipped by design** (opaque to detect creds-as-values).
- `state/` — runtime persistence (caches, counters, histories),
  gitignored, scanner skipped. **No enforced schema** — the skill
  author picks the shape. Convention (recommendation, not
  validated): `.jsonl` for append-only logs, `.json` for
  structured snapshots, `.db` for SQLite. The authoritative schema
  lives in the scripts that touch state/. A `## State` section in
  SKILL.md is the canonical place to describe what lives there,
  what's regenerable, and what rotation the skill expects — so
  the LLM sees it on context load without reading the scripts.

A `.gitignore` inside the skill dir lists `secrets/` and `state/`
so `git add` of the skills tree never drags creds or runtime state.

**Provenance & guards**:

- `origin: agent` skills may be edited/deleted freely by the agent.
- `origin: user` (default for manually-authored skills) require
  explicit `confirm_user_skill=true` on every mutating action.
- `MAX_AGENT_SKILLS = 40` quota enforced at `create` time.
- Anti-duplication by name across every category.

**Security scanner** ([alf/tools/skill.py:_SCANNER](alf/tools/skill.py))
runs on `create`, `add_file`, `patch` for every file NOT in
`secrets/` or `state/`. Covers (~50 patterns): destructive shell
(`rm -rf`, mkfs, dd, chmod 777, etc.), credential exfiltration
(curl/wget piping env vars or `~/.ssh`/`~/.aws`), prompt injection
("ignore previous instructions", role hijack), persistence (crontab,
shell rc, authorized_keys, systemd, launchd), reverse shells (nc,
socat, bash /dev/tcp), obfuscation (base64 decode pipes, `eval`/
`exec`, `__import__`), process execution (subprocess, os.system),
and hardcoded credentials.

**Atomic writes**: every mutating operation writes to a temp file
in the same directory and `os.replace`s onto the target, so a crash
or interruption leaves the original file untouched.

**Size limits**: 1 MiB per supporting file, 100k chars for SKILL.md
body. Larger payloads go to `assets/` + reference from SKILL.md.

**`view` action** lets the LLM load SKILL.md or any single skill
file into context on demand (progressive disclosure) — cheaper than
`read_file` because the tool handles path resolution from
`name` + optional `file` argument.

**System prompt** tells the agent it doesn't need to ask before
calling `skill(action='create')` — the scanner + quota + `origin:
agent` convention are the safety net.

### Interrupt

- **One mode only** — new input always cancels the current turn (no
  queue mode, unlike Hermes which has both).
- **Engine flag** `interrupt_requested` polled at 3 check-points:
  before each LLM iteration, mid-stream (`llm.stream` loop breaks on
  flag), and between tool calls within a step.
- **Long-running tools** (`research`) poll
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
- **Sensitive-path denylist**: `download_attachment` dest + `send`
  attachment paths go through `tools._paths.resolve_path` — same
  denylist as the other file tools. No workspace restriction; blocks
  `/etc`, SSH keys, credentials, etc.
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
- **CLI**: `alf mcp list` and `alf mcp test <name>` — read-only
  inspection from a shell. Mutations (add / edit / remove) live in
  ``alf setup → MCPs`` so there's one place where configuration
  changes, not two.
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

### Research (read-only sub-agent)

- **When to use** (per system prompt): open-ended research needing
  multiple searches + fetches ("investigate X", "compare Y vs Z",
  "haz un estudio profundo sobre Z").
- **Scope**: read-only toolset `{web_search, web_fetch, web_extract,
  read_file, search}`. No memory/terminal/write. Enforced by
  `SUB_AGENT_TOOLS` allowlist.
- **Depth tiers**: model picks `depth="quick" | "normal" | "deep"`;
  the integer per tier comes from
  `tools.research.{quick,normal,deep}_steps` in `config.yaml`
  (defaults 8 / 15 / 30). One iteration = one LLM round-trip
  (a `search + 3 extracts` parallel call inside one assistant
  message still counts as 1).
- **Synthesis fallback**: when the budget runs out, research forces
  one final no-tools `llm.complete()` with "stop investigating,
  report now with what you have". Avoids the "[research gave up]"
  footgun where the main agent retries the whole thing.
- **Interrupt**: polls `tool_state.is_interrupted()` between
  iterations and between tools; returns "[research: interrupted]"
  on the first hit.
- **State label** during execution: `"<depth> · step N/M"` emitted
  at the start of every iteration. Inner tools (`web_search` etc.)
  override it briefly with their own labels — that's a known UX
  rough edge tracked in the v0.2 R.1 follow-up.

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

### Filesystem access

File tools (``read_file``, ``write_file``, ``edit_file``, ``search``,
email attachment download) go through
``alf/tools/_paths.py :: resolve_path``:

1. **Relative paths root at the workspace** — ``cfg.workspace`` from
   the profile's ``config.yaml`` if set (e.g. ``workspace: ~/git``);
   otherwise ``os.getcwd()`` at the time of the call.
2. **Absolute paths go anywhere** except a sensitive-path denylist:
   ``/etc``, ``/boot``, ``/sys``, ``/proc``, ``/usr/lib/systemd``,
   ``/System``, ``/private/etc``, docker sockets, SSH private keys
   (``~/.ssh/id_*``, ``*_key``, ``*_ed25519``), ``*.pem /.p12 /.pfx``,
   ``~/.aws/credentials``, ``~/.gnupg/``.
3. **Profile home** (``~/.alf/``) is reached directly by
   ``skill``/``config``/``memory`` via ``alf.home.get_home()``, not via
   ``resolve_path``. These tools always see their own data regardless
   of workspace.

This matches terminal's posture: any path the shell would let you
touch, file tools let you touch. The workspace is a starting point for
relative paths, not a wall. Real workspace-only isolation lives in the
opt-in OS sandbox (Layer 2 in ``docs/SECURITY.md``).

**Error ergonomics** — when a path doesn't exist, ``read_file``,
``edit_file``, and ``search`` list the parent directory and suggest
siblings by fuzzy basename match ("Similar: …"). Ported from Hermes's
``file_operations.py``. Turns dead-ends into next steps instead of
pushing the agent into ``terminal ls``.

**`/workspace` slash** (TUI):
- ``/workspace`` → show the effective root.
- ``/workspace <path>`` → persist ``workspace: <path>`` to config.yaml
  and reload. Takes effect on the next tool call.
- ``/workspace clear`` → remove the pin; fall back to cwd.

**Warning on launch**: if ``workspace`` is unset in the config, an
``ErrorLine`` appears at the top of the chat telling the user cwd is
the scope. Forces a conscious choice.

**Gateway**: today, the gateway subprocess inherits cwd from the
service (launchd/systemd) — non-deterministic. ``alf gateway start``
validates every paired profile has a ``workspace`` configured and
refuses to start otherwise.

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
│   ├── skill.py                 create/edit/patch/add_file/view/delete/list — scanner + origin + quota
│   ├── search.py                content + filename search (ripgrep + stdlib fallback)
│   ├── research.py              read-only sub-agent (depth: quick/normal/deep)
│   ├── terminal.py              run/background/status/output/kill
│   ├── browser.py               STUB, not registered (v0.2 Playwright)
│   └── <other>.py               read_file, write_file, edit_file, todo, memory,
│                                web_*, schedule, send_message, session_search,
│                                email, config
├── skills/meta/consolidate-memory/SKILL.md    only bundled skill
├── prompts/
│   ├── default_personality.md   seed for ~/.alf/PERSONALITY.md
│   ├── system_prompt.md         tool-use + inline memory/skill triggers +
│                                research guidance
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
- **`alf setup → Identity` wizard (or `$EDITOR` shortcut) for editing
  `PERSONALITY.md`.** Rejected after considering. The `memory` tool
  already mutates `PERSONALITY.md` from inside the chat, and the LLM
  captures nuance ("less formal but not jokey; respect my code-switching")
  that a form can't. A wizard would duplicate the tool's mutation path
  and double our surface for bugs when the file format evolves. Users
  rename their agent conversationally — same mental model as the rest
  of the product. The real bug that motivated this proposal (Lucía
  identity silently lost) was the `ALF_PROFILE` propagation gap — fixed
  in commit 1470bdb, not by adding UI.

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

#### C. OpenAI Codex provider (ChatGPT subscription auth)
Today alf speaks to every provider via LiteLLM with an API key. That
means OpenAI is only usable by paying per-token against
`api.openai.com`. Hermes supports a second path — auth against the
user's **ChatGPT Plus/Pro subscription** using the same endpoints the
official Codex CLI uses. For a personal agent this is a big deal:
already-paid-for quota instead of metered tokens.

**How it works (reverse-engineered, not a public OpenAI API).**

1. **Auth — OAuth2 device code** against `auth.openai.com` using the
   Codex CLI's public `client_id` (`app_EMoamEEZ73f0CkXaXp7hrann`).
   User opens a URL + types a code → we poll → we get
   `access_token` + `refresh_token`. Reference:
   `/Users/javi/.hermes/hermes-agent/hermes_cli/auth.py` lines 2999–3119
   (`_codex_device_code_login`) and 1615–1675
   (`resolve_codex_runtime_credentials`).
2. **Token storage** — `~/.alf/auth.json` with `fcntl` file lock so
   gateway + TUI + schedule daemon don't race on refresh. Refresh 120s
   before expiry; on 401 force-refresh + retry once.
3. **Inference endpoint** — `https://chatgpt.com/backend-api/codex`
   (NOT `api.openai.com`). That's the backend your ChatGPT
   subscription actually consumes.
4. **Wire protocol** — **Responses API with event streaming**
   (`client.responses.stream(...)`), not `chat/completions`. This is
   the part LiteLLM does NOT cover cleanly, so this provider has to
   bypass LiteLLM and use the OpenAI SDK directly. Reference:
   `/Users/javi/.hermes/hermes-agent/run_agent.py:4592`
   (`_run_codex_stream`).

**Config schema** (new provider entry):
```yaml
model: openai-codex/gpt-5
# api_key field is ignored for this provider — tokens live in auth.json
```
`alf auth openai-codex` triggers the device-code flow and writes
`auth.json`; after that it's transparent.

**Implementation shape in alf.**

- `alf/auth/codex.py` — port of Hermes's auth module:
  `device_code_login()`, `resolve_runtime_credentials(force_refresh,
  refresh_skew)`, locked read/write of `~/.alf/auth.json`.
- `alf/providers/openai_codex.py` — new `Provider` subclass with
  `auth_type = "oauth_external"`, lists gpt-5 family models.
- `alf/llm.py` — today a thin LiteLLM wrapper. Add a transport
  dispatch: when the model id prefix is `openai-codex/`, resolve
  credentials from the auth store and call
  `openai.OpenAI(api_key=access_token,
  base_url="https://chatgpt.com/backend-api/codex").responses.stream(...)`
  instead of `litellm.completion`. Normalize the event stream
  (`response.output_item.added` with `type=function_call`, etc.) into
  the same `{text_delta, tool_calls_delta, finish_reason}` shape that
  `stream()` already yields, so `engine.py` doesn't need to care which
  transport ran.
- CLI: `alf auth openai-codex [login|logout|status]`.

**Effort.** 1–2 days. Auth module is almost a literal port from
Hermes. The unknown is event-stream normalization — the Responses API
emits a richer set of events than chat/completions, and we need to
map function-call streaming precisely so tool use survives the
round-trip.

**Risks (document them — don't discover them later).**

- **ToS grey area.** `chatgpt.com/backend-api/codex` is not a public,
  bindable-by-third-parties API. OpenAI can rotate the Codex `client_id`,
  start filtering by User-Agent, or tighten the device flow at any
  moment. If that happens the provider breaks and the user falls back
  to pay-per-token OpenAI or another provider. Acceptable for a
  personal agent; NOT acceptable to recommend for a hosted / shared
  deployment.
- **Two transports to maintain.** `engine.py` gets a second code path
  for streaming (LiteLLM vs OpenAI Responses). Contain it behind a
  `Transport` protocol so the dispatch happens once, in `llm.py`, not
  sprinkled across the codebase.
- **Token liveness across processes.** Gateway, TUI, and schedule
  daemon each open `auth.json` independently. The file lock prevents
  torn writes but not stale reads — every transport call must
  re-resolve credentials (or accept that it's cheap to re-read on
  each call).

**Ship order.** Auth module + CLI first (can be tested standalone:
run `alf auth openai-codex`, verify `auth.json` is written, verify
refresh works). Then provider + transport dispatch. Then end-to-end
smoke test with a real `gpt-5` call through the agent loop.

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

#### L. Reasoning-as-state ✅ shipped
Two channels of model thinking are now surfaced in the TUI instead
of being discarded:

1. **Inter-tool prose** — text the model emits between tool calls
   (`assistant_delta` chunks) is demoted from a full Markdown
   `AssistantMessage` to a compact dim `ReasoningLine` as soon as
   the next `tool_start` arrives. One `»` line per agent step,
   truncated to 400 chars. Multi-step turns get one preamble per
   step (correct — each reflects a real LLM iteration).
2. **Chain-of-thought tokens** — for models that emit
   `reasoning_content` separately (OpenAI o-series, DeepSeek-R1,
   Claude extended thinking), the latest 80 chars of that stream
   replace the literal `thinking…` label inside the live spinner.
   Tail view, so the indicator stays single-height regardless of how
   verbose the CoT gets. Dropped the moment the first `content`
   token or tool call arrives.

Plumbing: `alf/llm.py` captures `reasoning_content` / `reasoning`
into a new `reasoning_delta` field in the stream dict;
`alf/engine.py` emits it as `AgentEvent(kind="reasoning_delta")`;
`alf/tui/app.py` routes it to `ThinkingIndicator.append_reasoning()`
without stopping the indicator; `alf/tui/widgets.py` hosts the new
`ReasoningLine` widget and the tail-view logic.

**Persistence + resume.** The inter-tool prose is stored on
`ToolLog.reasoning` (the first tool of each batch carries the
reasoning text, subsequent tools in the same batch store `""`).
`session.save()` writes it only when non-empty. On `alf --continue`
the TUI replays it as a `ReasoningLine` before the corresponding
tool card. Old session files without the field load with
`reasoning=""` and simply don't render any preamble.

**Toggle.** `tui.show_reasoning` (default `true`) hides both
channels from the UI when `false`. Data is still persisted and the
event still fires — only the render is skipped. Re-enabling on a
past session brings the `»` back on the next replay. Gateway
surfaces never rendered reasoning, so the flag is a pure-TUI
concern.

#### M. TTS / STT / voice-mode
Out of scope for core agent. If added, lives in a separate surface
(voice gateway) — don't pollute the TUI.

### Multimodal output

#### N. Image generation
A `generate_image(prompt, style)` tool using the active vision model
or a dedicated endpoint (DALL-E, SD). Useful for "hazme un logo
rápido". Low priority unless a concrete use case appears.

#### R. Research tool — follow-ups

The v0.2 launch of `research` (renamed from `delegate`) shipped with
a read-only sub-agent, `depth` enum (`quick` / `normal` / `deep`)
driving iteration count via `tools.research.{quick,normal,deep}_steps`
in `config.yaml`, fixed system-prompt bug (was naming `grep`/`glob`
which no longer exist), and a narrow scope — single sub-agent, read
only, no batch. Three follow-ups intentionally deferred:

**R.1 — Step-counter in live state label.** Cost: 2-4h. Risk: low.

Today the research ToolCard shows whatever the innermost tool emits
(e.g. `"searching the web…"`) with no sense of how deep into the
budget we are. Wrap the `emit_state` callback inside the research
subloop so every inner label is prefixed with `step N/M · <inner>`.
Implementation sits in `alf/tools/research.py` — capture the engine-
set emit callback, install a wrapper that prefixes with the current
step counter before delegating, restore after the tool call.
Testable with 2-3 cases. Ship first among the three follow-ups.

**R.2 — `delegate_task` — write-capable sub-agents.** Cost: 1-2 days.
Risk: medium.

A second tool alongside `research`, write-capable. Schema:
`brief` + `toolsets: ["file", "terminal", "web"]` enum. Map internal
toolset names → concrete tool sets (`"file"` → read_file + write_file
+ edit_file + search, `"terminal"` → terminal, etc.). Reuses the
research subloop infrastructure; different system prompt allowing
mutations. Use-case: "refactor module X", "generate project scaffold
following template Y".

Two real gotchas:

1. **Security posture**: a sub-agent with `write_file` plus prompt
   injection can mutate the FS without user-in-the-loop. alf's Layer 1
   sensitive-path denylist is the only wall; no per-write confirmation
   today. Decision point before implementing: (a) trust the denylist,
   consistent with how the main agent operates, or (b) add first-write
   confirmation gate per sub-agent invocation. For personal-agent
   scope (a) is probably sufficient — align with the rest of alf's
   threat model.
2. **Testing surface**: subagent writes need isolated FS fixtures +
   LLM mocks. Adds test complexity; budget 3-4 hours for coverage.

Only ship if a concrete use-case materialises ("I need alf to delegate
a multi-file refactor"). Absent that, this stays backlog.

**R.3 — Batch parallel (`tasks[]`).** Cost: 1-2 days + 1 day refactor.
Risk: medium-high.

Hermes-style: `tasks: [{brief, depth}]` up to 3 running concurrently
via `ThreadPoolExecutor(max_workers=3)`. Aggregates the reports,
propagates interrupts to all children on cancel.

**The real bill is the refactor of `alf/tools/_state.py`.** Today
`set_emit`, `set_interrupt_getter`, `set_usage_sink` are module-level
globals — three subagents running in parallel race on them: one
subagent's `emit_state` pisa the callback the other is using, usage
gets attributed to the wrong card. Fix: move to `contextvars`
(preferred, per-coroutine/thread isolation) or thread-locals. That
refactor touches every tool that calls `emit_state` — ~15 sites
across web_search, web_fetch, web_extract, search, research,
schedule, etc. Not destructive (same API, different storage) but
mechanical.

The refactor is also useful on its own: cleaner tests, better
observability when nested tools run. Worth doing when either (a)
we genuinely need batch parallel, or (b) we hit a bug traceable to
the current globals. Don't do it in isolation; bundle with the use
case.

Lowest-priority of the three follow-ups — niche for a personal
agent, highest cost, most fragile.

---

## v0.3 — planned

### O. Drop `questionary` in favour of direct `prompt_toolkit`

**Why revisit.** `questionary` was the right choice when setup was 3
menus and 0 wizards. Now that `alf/ui.py` is the shared layer for
every `setup` flow, we're fighting its defaults more than using them.
Concrete hacks in `alf/ui.py` as of v0.2:

1. `qmark=""` + empty `message` to suppress its prompt header.
2. List-tuple titles `[(style, text)]` so it skips its own
   `class:highlighted` wrap (see `common.py:459` in the questionary
   source) — that's how muted Back/Exit titles survive the pointer.
3. Style override for `class:close` / `class:highlighted close` /
   `class:selected close` in `accent_style()`, just to keep the
   close row from flashing accent.
4. ANSI escape (`\033[1A\033[2K\r\n`) after every menu to wipe
   questionary's post-selection echo — which our `qmark/message=""`
   setup reduces to an orphan line with zero information.
5. `_CLOSE_SENTINEL = object()` because `Choice.value=None` collapses
   into "unset" and falls back to the title string.

What `questionary` still gives us after those hacks: arrow-key
navigation, ENTER/ESC bindings, cursor rendering, and scroll-if-long
behaviour. All of that is ~150 LOC on top of `prompt_toolkit` (which
we keep anyway — it's transitive via `rich` and questionary itself).

**Scope.**

- Reimplement `menu()` in `alf/ui.py` against `prompt_toolkit`
  directly: `Application` + `Layout` with a single
  `FormattedTextControl`, key bindings for ↑/↓/ENTER/ESC, render
  that knows about pointer + styled titles. ~150 LOC.
- Remove the 5 hacks listed above — they all evaporate.
- Rewrite the 5 monkeypatched tests in `tests/test_ui.py` against
  the new internal API. The current mocks pretend to be
  `questionary.select`; the new ones mock our own menu loop, which
  is simpler.
- Drop `questionary` from `pyproject.toml`.
- Leave `text() / password() / confirm()` on `rich.Prompt` — those
  work well, no hacks, not in scope.

**Risk budget.** Half-day to day of work.

- Core rewrite + unit tests: 2-3h.
- Manual testing across macOS Terminal, iTerm2, and one Linux
  terminal (gnome-terminal or alacritty): 1-2h.
- ESC handling on macOS default Terminal sometimes delays behind
  the escape-sequence timeout — the exact sort of edge case
  questionary abstracts away today. Budget 1-3h for surprises like
  that.

**Trigger.** Ship as part of v0.3 UI polish, or earlier if we hit
hack #6 (e.g. we need disabled rows, separators, async-rendered
rows). Don't split across versions — migration should land in one
commit with all the hack-removals bundled, so the diff tells the
story.

### P. Graduate the OS sandbox out of experimental

`tools.terminal.sandbox` ships in v0.1 as opt-in + experimental
(default `false`). Shipping on by default was rejected for v0.1
because the `sandbox-exec` profile (macOS) and the `bubblewrap`
invocation (Linux) haven't been validated against the long tail of
real commands users actually run: `git push` with SSH keys outside
the workspace, `docker` touching `/var/run/docker.sock`, Homebrew
Intel vs Apple Silicon paths, `npm install` with caches in
`~/.npm`, `code --install-extension` writing to `~/.vscode/`, and
so on. Each of these would break silently when someone flips the
flag and erode trust in the agent faster than the security gain is
worth.

**For v0.3, revisit with data.** Goal: move the default to `true`
without a regression wave.

Scope when we attack it:

- Collect a "golden set" of 30–50 real commands the agent runs in
  a normal week (read from session history) and exercise each under
  the sandbox. Anything that breaks gets a profile fix or an
  explicit carve-out in docs.
- Extend the macOS profile to cover Homebrew Apple Silicon
  (`/opt/homebrew`) and Intel (`/usr/local`) paths and to allow
  reads on the user's git config (`~/.gitconfig`, `~/.git-credentials`)
  without opening the rest of `$HOME`.
- Extend the Linux `bwrap` invocation similarly — bind-mount the
  user's `.gitconfig` + `~/.npm` + `~/.cache` as RO so package
  managers work.
- Smoke-test on two real Linux distros (not just the Docker image
  in `docs/sandbox-linux-test.md`): Ubuntu LTS and Fedora stable.
- Add a first-run check: on `alf` boot with sandbox on, run a
  trivial `echo ok` through the sandboxed path. If it fails, warn
  loudly with a pointer to SECURITY.md and fall back to disabled.

Once the golden set passes cleanly, flip `DEFAULT_CONFIG` to
`sandbox: true`, drop the "experimental" wording from SECURITY.md
and CONFIG.md, mention it in the v0.3 CHANGELOG as "tightened by
default".

Don't graduate it silently — the security posture change deserves
visibility.

### Q. Skill self-review / validation

Tier B models (mimo-v2-flash) happily publish skills with real bugs:
threading race conditions (opening browser before the local callback
server is listening), undeclared third-party imports (`import requests`
when only stdlib is acceptable), incorrect setup instructions that
contradict the docs the agent just fetched (e.g. "Authorization
Callback Domain: localhost:8765" when the provider rejects port
numbers in that field). The current mitigations — stdlib-preferred
rule + security scanner + structured layout — catch the crude cases
but not these.

**For v0.3**, add a `skill(action="validate", name=...)` action and
wire it into the `/skills` UI (`V` binding). The validator runs a
battery of cheap checks:

- `python -c "import <every top-level import in scripts/*.py>"` to
  surface missing third-party deps.
- `python -m py_compile scripts/*.py` for syntax.
- `ast.parse` + walk looking for common foot-guns (race patterns in
  OAuth: `webbrowser.open(...)` before a `.serve_forever()` /
  `.handle_request()` on the same script).
- Cross-check setup instructions in SKILL.md against the endpoints
  the scripts actually hit (if SKILL.md mentions `localhost:8765` and
  scripts bind to a different port, flag it).

**Even more ambitious**: an optional `skill(action="review", name=...)`
that spawns a `research()` sub-agent with a pre-canned prompt — *"You
are reviewing this skill directory. Read SKILL.md and every file in
scripts/. Return a bulleted list of bugs, race conditions, security
issues, or setup instructions that contradict the code."* — and
reports back. Costs one research call but catches real issues.

Deliberately NOT for v0.1/v0.2:

- Adding per-library OAuth/threading/etc guidance to the skill tool
  description. That's feature creep — we'd end up with pages of
  domain-specific rules. The stdlib-first line is the one exception
  because it's a single, universally-applicable rule.
- Blocking skill creation on validation failure. Users may
  legitimately want to publish work-in-progress skills. Validation
  reports should be advisory.

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
30. **`research` tool** for deep investigation (renamed from
    `delegate` in v0.2). Read-only sub-toolset, depth-tiered budget
    (`quick` / `normal` / `deep` driven by
    `tools.research.{tier}_steps` config), synthesis fallback when
    budget runs out. Honors engine interrupt via
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
