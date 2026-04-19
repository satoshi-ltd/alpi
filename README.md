# alf

A slim personal AI agent. Terminal + Telegram. Inline-learning memory,
pending-gate skills, workspace-sandboxed tools.

Built as a simpler alternative to Nous Research's
[Hermes](https://github.com/NousResearch/hermes-agent) — keeps the key
ideas (tool-calling loop, curated memory, separate gateway process,
multi-provider LLM via litellm) and drops the complexity (30+ tools →
17, no post-session reflect, no sub-agent mesh, no SQLite state). Full
context in [`docs/CONTEXT.md`](docs/CONTEXT.md).

## Status

**v0.1** — first usable cut. TUI, memory discipline, skill pending gate,
workspace sandbox, delegate sub-agent for research, turn-based session
format, interrupt-on-new-input. Not production; personal use.

## Install

```bash
# One-time tool install from source
uv tool install /path/to/alf
# After any code change
uv tool install /path/to/alf --reinstall --no-cache
```

## Run

```bash
alf                         # interactive TUI in the current directory
alf --continue              # resume the last session
alf --profile <name>        # use a named profile (multi-profile)
alf gateway setup           # configure the Telegram gateway
alf gateway start           # run the gateway process
```

## Key concepts

**Workspace** — the directory alf's file tools can touch. Defaults to
`cwd` at launch if no `workspace` is set in the profile's
`config.yaml`; `/workspace <path>` pins it explicitly. Paths outside
the workspace (and `~/.alf/`) are rejected. Terminal is
soft-hardened; see `docs/CONTEXT.md` for the sandbox caveats.

**Memory** — three files under `~/.alf/memories/`:

- `USER.md` — who the user is (name, location, preferences).
- `MEMORY.md` — alf's own notes (env quirks, commands, incidents).
- `PERSONALITY.md` — how alf should respond (tone, length, language).

Updated inline during conversations via the `memory` tool. No
post-session reflect. Snapshot is frozen per session (prefix cache).

**Skills** — reusable recipes under `~/.alf/skills/<category>/<name>/`.
Agent-created skills land in `~/.alf/skills/_pending/` and need user
approval via `/skills` before going live. Each carries an `origin:
agent | user` field.

**Sessions** — JSON under `~/.alf/sessions/<id>.json`. Stored as a list
of `turns` (`{user, tools, assistant}`); no raw OpenAI message thread
to keep disk usage small and `session_search` clean.

## Providers

Any LiteLLM-supported provider — set the relevant key in `~/.alf/.env`:

```bash
ANTHROPIC_API_KEY=...
OPENAI_API_KEY=...
OPENROUTER_API_KEY=...
GOOGLE_API_KEY=...
GROQ_API_KEY=...
OLLAMA_BASE_URL=http://localhost:11434     # local
# Gateway (optional) — single source of truth for bot + allowlist:
TELEGRAM_BOT_TOKEN=...
TELEGRAM_ALLOWED_CHAT_IDS=12345,67890      # comma-separated, fail-closed
```

Switch model any time with `/model` inside the TUI.

## Gateway

Relays Telegram messages to alf. Tool activity streams to the chat
(`◆ memory · ...`) and a typing indicator stays on while alf works.
Both are toggleable in `config.yaml`:

```yaml
gateway:
  show_tool_trace: true
  typing_indicator: true
```

The allowlist lives **only** in `~/.alf/.env` as `TELEGRAM_ALLOWED_CHAT_IDS`
(fail-closed if unset). Run `alf gateway setup` to configure both
interactively.

## Layout

```
alf/                       Python package
  cli.py                   entry point, bootstrap, --continue logic
  engine.py                turn runner, interrupt flag, tool loop
  llm.py                   litellm stream + complete wrappers
  session.py               Turn / ToolLog dataclasses, persistence
  memory.py                MemoryStore with two-tier dedup + .bak
  home.py                  profile resolution, PERSONALITY migration
  config.py                YAML + workspace handling
  prompts/                 system prompt + skill templates
  tools/                   18 registered tools (incl. send_message)
  tui/                     Textual app, widgets, screens, theme
  gateway/                 Telegram gateway (separate process)
  skills/                  bundled skills (only `consolidate-memory`)
docs/
  CONTEXT.md               full snapshot + v0.2 roadmap
tests/                     pytest, ~70 tests, 2s
```

See `docs/CONTEXT.md` for:
- every key design decision and the rationale behind it
- what's been tried and discarded (don't relitigate)
- the v0.2 roadmap (browser/Playwright, send_message, MCP, multimodal,
  OS-level sandbox, multi-profile CLI, …)

## Tests

```bash
uv run --with pytest pytest -q
uv run --with pytest pytest --llm    # also run real-LLM integration tests
```

## License

MIT.
