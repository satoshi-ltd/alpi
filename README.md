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
alf chat --once "text"      # one-shot turn to stdout (pipe-friendly)
alf profile list            # show profiles; marks the one this command resolved to
alf profile create <name>   # bootstrap a new profile tree (same as first `alf -p <name>`)
alf profile remove <name>   # delete a profile (safety checks + confirm)
alf gateway setup           # configure the Telegram gateway
alf gateway start           # run the gateway process
alf schedule start          # run the schedule daemon (manual, like the gateway)
alf schedule status         # check the daemon + list jobs
alf setup                   # interactive menu: model, gateways, MCPs
alf mcp list                # show configured MCP servers (read-only)
alf mcp test <name>         # spawn + list tools of one server (read-only)

# Persist across reboots (launchd on macOS, systemd --user on Linux):
alf gateway install         # one-time, auto-starts + reanima al login
alf schedule install
alf gateway uninstall       # clean stop + unregister
alf schedule uninstall
```

> `gateway` and `schedule` are independent processes with identical
> lifecycle rules. Install each one only if you want it to survive a
> reboot — otherwise `start`/`stop` covers day-to-day use.

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
Each skill is a directory with `SKILL.md` plus up to four optional
subdirs: `scripts/` (executable code), `references/` (markdown docs),
`assets/` (templates / data), and `secrets/` (credentials, mode 0700,
gitignored). Agent-created skills land in `~/.alf/skills/_pending/`
and need user approval via `/skills` before going live. Full contract
in [`docs/SKILLS.md`](docs/SKILLS.md).

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
# Email (optional) — generic IMAP/SMTP, any provider:
EMAIL_ADDRESS=you@yourprovider.com
EMAIL_PASSWORD=...
EMAIL_IMAP_HOST=imap.yourprovider.com
EMAIL_SMTP_HOST=smtp.yourprovider.com
EMAIL_ALLOWED_SENDERS=pepe@x.com,ana@y.com  # gateway inbound (fail-closed)
```

Switch model any time with `/model` inside the TUI.

Not every model is a good agent — tool-calling fluency and
system-prompt adherence vary a lot across providers. See
[`docs/MODELS.md`](docs/MODELS.md) for a tiered recommendation based
on real OpenRouter usage data and hands-on testing.

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
  home.py                  profile resolution
  config.py                YAML + workspace handling
  prompts/                 system prompt + skill templates
  tools/                   19 registered tools (incl. send_message, email)
  scheduler/               schedule daemon (tick loop, PID, run_job)
  email/                   IMAP+SMTP client (shared by tool + gateway)
  mcp/                     MCP client (stdio JSON-RPC) + registry + setup
  service.py               install/uninstall launchd/systemd units
  ui.py                    shared wizard/menu primitives (banner, row,
                           menu, text, password, ok/fail/saved)
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

## Security

Two layers, layered by trust:

- **Always on**: command denylist on `terminal`, SSRF block on
  `web_fetch` / `web_extract`, prompt-injection scanner on email /
  web content, path sandbox on file tools.
- **Opt-in, experimental**: OS-level sandbox for `terminal`
  (`sandbox-exec` on macOS, `bubblewrap` on Linux). Default **off**
  — turn it on with `config(set, tools.terminal.sandbox, true)` once
  you've checked your usual commands still work.

Full model + platform notes in [`docs/SECURITY.md`](docs/SECURITY.md).

## Tests

```bash
uv run --with pytest pytest -q
uv run --with pytest pytest --llm    # also run real-LLM integration tests
```

## License

MIT.
