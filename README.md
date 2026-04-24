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

## Principles

alpi respects the Terms of Service of every LLM vendor it integrates
with. Users pay per-token API access through their own keys — that cost
is honest and visible. **Subscription routing is not on the roadmap**:
we do not reverse-engineer the private OAuth flows that ChatGPT Plus /
Claude Pro / Claude Code use to talk to their official clients.
Competitor agents ship these features; we consider that disrespectful
to the vendor's product boundaries and unsafe for users (accounts get
banned, reversed flows break). If a vendor publishes an official OAuth
for third-party agents, we adopt it then.

## Why alpi is built like this

alpi is published by **[Satoshi Ltd.](https://www.satoshi-ltd.com/)**
and inherits its six operating principles. They are not aspirational
copy — every non-obvious design choice in this repo traces back to one:

- **Privacy by Design.** ALP is a closed, purpose-built protocol, not
  an adoption of A2A or similar open standards — every exposed knob
  is a potential attack vector. No discovery, no registry, no
  telemetry. LiteLLM's default telemetry is audited off at release
  (`alpi/llm.py::_silence_litellm`, regression-tested).
- **User Sovereignty.** Per-profile isolation under
  `~/.alpi/profiles/<name>/`. Fresh profiles ship with no default
  model — you pick your provider, your model, your memory. Skills
  and memory live on your disk, not ours.
- **Security First.** Threat-modeled from the spec (see
  [docs/ALP.md](docs/ALP.md)): Ed25519 signing on every ALP
  envelope, fail-closed capability model, reject-fast reentrancy,
  approval gate on shell, OSV check before installing skills or
  MCPs, `pip-audit` in the release checklist.
- **Open Source.** Source-available under BSL 1.1; reproducible via `uv.lock`; no hidden binaries. See [License](#license) for the split between personal / non-production use (free) and commercial production deployment (separate licence from Satoshi). Converts to Apache 2.0 on the Change Date.
- **Zero Knowledge.** No trust-on-first-use. Peers exchange pubkeys
  out-of-band and pin them. ALP.2's Noise_XK handshake produces
  forward-secret session keys — losing a long-term key doesn't unlock
  past traffic.
- **Digital Sovereignty.** Ollama is a first-class provider. Skills
  and sub-agents run locally. You can wire alpi up on a laptop, a
  home server, and a remote box, link them via ALP, and never depend
  on a centralised service.

The design heuristic that pulls these together — borrowed from
Satoshi's Clonara — is **"constraint breeds coherence"**. Closed
scope, small verb set, one transport per environment, no generic
framework.

## Install

```bash
# One-time tool install from source
uv tool install /path/to/alpi
# After any code change
uv tool install /path/to/alpi --reinstall --no-cache

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

alpi gateway start           # run the Telegram/IMAP gateway process
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
- `AGENT.md` — how alpi should respond.

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

# Email (optional, pick ONE or BOTH).
# IMAP/SMTP — generic provider (password or app-password):
IMAP_ADDRESS=you@yourprovider.com
IMAP_PASSWORD=...
IMAP_HOST=imap.yourprovider.com
SMTP_HOST=smtp.yourprovider.com
IMAP_ALLOWED_SENDERS=pepe@x.com,ana@y.com    # fail-closed inbound allowlist

# Gmail API (OAuth2) — scoped, no password stored:
GMAIL_CLIENT_ID=...apps.googleusercontent.com
GMAIL_CLIENT_SECRET=GOCSPX-...
GMAIL_ALLOWED_SENDERS=pepe@x.com,ana@y.com   # fail-closed inbound allowlist
# The refresh token is stored per profile under ~/.alpi/.../gmail_token.json
# after a one-off browser consent via `alpi setup → Gateways → Gmail`.
```

Switch model any time with `/model` inside the TUI. Tier guidance in
[docs/MODELS.md](docs/MODELS.md).

## Gateway

Relays Telegram and IMAP messages to alpi. Tool activity streams to the
chat (`◆ memory · ...`) and a typing indicator stays on while alpi works.
Both toggleable in `config.yaml` per platform:

```yaml
gateway:
  telegram:
    show_tool_trace: true
    typing_indicator: true
  imap:
    poll_interval: 60
    mark_as_read: true
    show_tool_trace: false
```

Allowlists live in `~/.alpi/.env` (fail-closed if unset). Run
`alpi setup` for interactive configuration.

## Documentation

Each doc has a focused job:

- [QUICKSTART.md](QUICKSTART.md) — first-day walkthrough. Pick a model, pin a workspace, send your first message, connect a gateway, install services.
- [ALP.md](docs/ALP.md) — Alpi Link Protocol spec — paper-style normative reference for agent↔agent communication.
- [PROFILES.md](docs/PROFILES.md) — the core isolation primitive. Per-profile identity, state, memory, skills, peers.
- [DEPLOYMENTS.md](docs/DEPLOYMENTS.md) — six topologies from laptop-only to enterprise "army of alpis", with the licence boundary for each.
- [OPERATIONS.md](docs/OPERATIONS.md) — runbook: logs, services, upgrades, backup + restore, identity rotation, monitoring, disaster recovery.
- [ARCHITECTURE.md](docs/ARCHITECTURE.md) — technical reference of what's currently in the codebase. File layout, core systems, invariants.
- [CONFIG.md](docs/CONFIG.md) — every config key with default + when it takes effect.
- [SECURITY.md](docs/SECURITY.md) — threat model + Layer 1 (always-on guards) + Layer 2 (opt-in OS sandbox).
- [SKILLS.md](docs/SKILLS.md) — skill authoring guide: structure, conventions, secrets/state, scanner.
- [MODELS.md](docs/MODELS.md) — tiered model recommendations.
- [ROADMAP.md](docs/ROADMAP.md) — open work; shipped work lives in the CHANGELOG.

## Tests

```bash
uv run --with pytest pytest -q
uv run --with pytest pytest --llm    # also real-LLM integration tests
```

## License

alpi is published under the **[Business Source Licence 1.1](LICENSE)**
by [Satoshi Ltd.](https://www.satoshi-ltd.com/) — source-available,
not OSI "open source" *today*, but it converts to **Apache 2.0 on the
Change Date** (2030-04-23, or four years after each version's first
public release, whichever comes first).

### What you can do without a commercial licence

- **Anyone** can read, copy, modify, redistribute, and make
  non-production use of alpi — no paperwork, no contact needed.
- **Individuals** can run alpi in production on machines they
  personally control, for personal, research, and non-commercial
  purposes.
- **Companies and other legal entities** can run alpi internally
  for **evaluation, development, and experimentation**.

### What requires a commercial licence

- Production deployment by a company or other legal entity
  (e.g. rolling alpi out to staff, automating internal workflows
  with it, running it against a production dataset).
- Offering alpi — or a derivative — to third parties as a hosted,
  embedded, or managed service.

Commercial enquiries: **info@satoshi-ltd.com**.

This model — free for individuals and non-production use, paid for
commercial production — reflects Satoshi's consulting-first business
model and keeps alpi honest about its funding. See
[docs/ROADMAP.md](docs/ROADMAP.md) under "Principles" for why
subscription-routing and OAuth-reversal are also off the table.
