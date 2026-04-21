# alpi

A slim personal AI agent. Terminal + Telegram + email. Inline-learning
memory, live skills with a security scanner and a quota, and a read-only
research sub-agent.

**Positioned as a lighter, improved version of Nous Research's
[Hermes](https://github.com/NousResearch/hermes-agent).** Hermes is
the canonical reference codebase — kept locally at
**`~/git/hermes-agent/`** so alpi development can read it directly when
designing a feature. Workflow: read Hermes, evaluate critically, port
a leaner version. Kept: the ideas that earn their keep (tool-calling
loop, curated memory, separate gateway process, multi-provider LLM via
litellm, read-only research sub-agent, security scanner on skills).
Dropped: the complexity that doesn't (30+ tools → ~17, post-session
reflect, sub-agent mesh, SQLite state, 28 skill categories, hub/sync).

## Status

**v0.2** — in active development. Core systems stable; surface features
landing. See [docs/ROADMAP.md](docs/ROADMAP.md) for what's shipped and
what's planned.

## Install

```bash
# One-time tool install from source
uv tool install /path/to/alf
# After any code change
uv tool install /path/to/alf --reinstall --no-cache

# One-time — Chromium for the `browser` tool (~200MB)
playwright install chromium
```

## Run

```bash
alpi                         # interactive TUI in the current directory
alpi --continue              # resume the last session
alpi -p <name>               # use a named profile (multi-profile)
alpi chat --once "text"      # one-shot turn to stdout (pipe-friendly)

alpi profile list            # show profiles, mark the active one
alpi profile create <name>   # bootstrap a new profile tree
alpi profile remove <name>   # delete after safety checks + confirm

alpi setup                   # interactive menu: model, gateways, MCPs

alpi gateway start           # run the Telegram/email gateway process
alpi schedule start          # run the schedule daemon
alpi mcp list                # list configured MCP servers (read-only)

# Persist across reboots (launchd on macOS, systemd --user on Linux):
alpi gateway install         # one-time, auto-starts at login
alpi schedule install
alpi gateway uninstall
alpi schedule uninstall
```

`gateway` and `schedule` are independent processes with the same
lifecycle. Install only what you want surviving a reboot — otherwise
`start`/`stop` covers day-to-day.

## Key concepts

**Workspace** — the default root for relative paths in tools. Pinned in
the profile's `config.yaml`, or `cwd` at launch as fallback. **Not a
wall**: absolute paths reach anywhere except a sensitive-path denylist
(`/etc`, SSH keys, AWS creds, docker sockets, …). Real workspace-only
isolation is the opt-in OS sandbox (`tools.terminal.sandbox: true`).
Full security model in [docs/SECURITY.md](docs/SECURITY.md).

**Memory** — three files under `~/.alpi/memory/`:

- `USER.md` — who the user is.
- `MEMORY.md` — alpi's own notes (env quirks, commands, incidents).
- `PERSONALITY.md` — how alpi should respond.

Updated inline during conversations via the `memory` tool. No
post-session reflect. Snapshot frozen per session for prefix cache.

**Skills** — reusable recipes under `~/.alpi/skills/<category>/<name>/`.
Each skill is a directory with `SKILL.md` plus optional `scripts/`,
`references/`, `assets/`, `secrets/` (mode 0700, gitignored), `state/`
(gitignored runtime persistence). Live by default — no approval gate;
the security scanner is the gate. Auto-injected into the system prompt
so the agent sees its toolbox without having to discover it. Full
contract in [docs/SKILLS.md](docs/SKILLS.md).

**Sessions** — JSON under `~/.alpi/sessions/<id>.json` as a list of
turns. `--continue` resumes the most recent.

**Research** — `research(brief, depth)` spawns a read-only sub-agent
with its own context. `depth` is `quick` / `normal` / `deep`; the
integer per tier is a knob in `config.yaml`. Returns a synthesised
report; the main agent never sees the intermediate trace.

## Providers

Any LiteLLM-supported provider — set the relevant key in `~/.alpi/.env`:

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

# Email (optional) — generic IMAP/SMTP:
EMAIL_ADDRESS=you@yourprovider.com
EMAIL_PASSWORD=...
EMAIL_IMAP_HOST=imap.yourprovider.com
EMAIL_SMTP_HOST=smtp.yourprovider.com
EMAIL_ALLOWED_SENDERS=pepe@x.com,ana@y.com  # gateway inbound (fail-closed)
```

Switch model any time with `/model` inside the TUI. Tier guidance in
[docs/MODELS.md](docs/MODELS.md).

## Gateway

Relays Telegram and email messages to alpi. Tool activity streams to the
chat (`◆ memory · ...`) and a typing indicator stays on while alpi works.
Both toggleable in `config.yaml` per platform:

```yaml
gateway:
  telegram:
    show_tool_trace: true
    typing_indicator: true
  email:
    poll_interval: 60
    mark_as_read: true
    show_tool_trace: false
```

Allowlists live in `~/.alpi/.env` (fail-closed if unset). Run
`alpi setup` for interactive configuration.

## Documentation

Each doc has a focused job:

- [ARCHITECTURE.md](docs/ARCHITECTURE.md) — technical reference of what's currently in the codebase. File layout, core systems, invariants. Living document.
- [ROADMAP.md](docs/ROADMAP.md) — what's shipped, in progress, planned, and discarded.
- [CONFIG.md](docs/CONFIG.md) — every config key with default + when it takes effect.
- [SECURITY.md](docs/SECURITY.md) — threat model + Layer 1 (always-on guards) + Layer 2 (opt-in OS sandbox).
- [SKILLS.md](docs/SKILLS.md) — skill authoring guide: structure, conventions, secrets/state, scanner.
- [MODELS.md](docs/MODELS.md) — tiered model recommendations from real OpenRouter data.

## Tests

```bash
uv run --with pytest pytest -q
uv run --with pytest pytest --llm    # also real-LLM integration tests
```

## License

MIT.
