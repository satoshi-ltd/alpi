# alpi

**Your private agent network.**

alpi starts as the agent in your terminal, then grows with you:
profiles for work, cron, home servers, research, and rooms with other
alpis. Each profile owns its memory, keys, model, skills, gateways,
approvals, and trust boundary. ALP links them across machines without
a registry, hub, account, or mandatory cloud.

Bring any model. Keep every key. Run one alpi, or a network that stays
yours.

## Why alpi exists

Most useful agents eventually become infrastructure: they hold memory,
touch files, run commands, answer from a phone, wake up on schedules,
and coordinate work across machines. alpi treats the **profile** as
the unit of that infrastructure, not the chat.

The design goal is sovereignty:

- **Local-first by default.** State lives under `~/.alpi/` or a named
  profile. Memory, sessions, skills, keys, logs, and peer lists are
  files on your machine.
- **User-owned models.** Fresh profiles ship with no default model.
  You pick the provider, model, API key, or Ollama server per profile.
- **Security as product shape.** Shell commands pass a three-tier
  approval system. Dangerous commands are blocked with no override.
  Web and email content is treated as hostile data. Skills and MCPs
  are scanned before install.
- **Operational UX.** One setup wizard, a live `doctor`, per-profile
  services, merged logs, gateway daemons, scheduling, and cleanup.
- **Private coordination.** ALP.1 links local profiles, ALP.2 links
  machines over Noise_XK, and ALP.3 adds shared rooms. Peers are
  pinned by Ed25519 identity and governed by fail-closed capabilities.
  No discovery service, no shared account, no central broker.
- **Honest provider boundaries.** alpi does not reverse-engineer
  ChatGPT Plus, Claude Pro, Claude Code, or other first-party
  subscription clients. If a vendor publishes an official third-party
  OAuth flow, alpi can adopt it. Until then, users pay per-token API
  access through their own keys.

## What ships today

The current release ships the full local-to-network shape:

- Textual TUI with streaming replies, slash commands, live tool cards,
  interrupt, session resume, model switching, and cost/token display.
- Telegram, IMAP, and Gmail gateways as separate per-profile daemons.
- Inline-learning memory: `USER.md`, `MEMORY.md`, and `AGENT.md`.
- Live skills under `~/.alpi/skills/<category>/<name>/`, scanner-gated
  and auto-injected into the system prompt.
- Multi-provider LLM support through LiteLLM, plus first-class Ollama.
- Read-only `research(brief, depth)` sub-agent with `quick`, `normal`,
  and `deep` tiers.
- Write-capable `delegate` sub-agent for focused file/web/terminal
  tasks.
- Schedule daemon for cron and one-shot jobs.
- MCP client for user-configured local MCP servers.
- ALP.1: intra-machine agent-to-agent links over Unix sockets.
- ALP.2: inter-machine links over Noise_XK TCP, with per-peer budget
  and rate-limit enforcement.
- ALP.3: hub-anchored shared rooms for multiple alpis and optional
  human participants.
- `alpi doctor`, `alpi logs`, per-profile launchd/systemd services,
  backup-friendly file layout, and security audit logs.

## Quickstart

```bash
uv tool install alpi
alpi setup
alpi
alpi doctor
```

Optional browser support:

```bash
playwright install chromium
```

During setup, pick a model, paste the relevant key, and pin a
workspace. For local-only inference, install Ollama first and add it in
`alpi setup -> Model`.

Common commands:

```bash
alpi                         # interactive TUI
alpi -c                      # resume last session
alpi -p work                 # use named profile
alpi chat --once "status?"   # one-shot stdout turn

alpi setup                   # model, gateways, MCPs, sandbox, services
alpi doctor                  # live health checks
alpi logs                    # merged profile logs

alpi profile list
alpi profile create work
alpi profile remove work

alpi gateway start|stop|restart
alpi schedule start|stop|restart|run-once
alpi alp start|stop|restart

alpi peers key
alpi peers list
alpi peers add <id> <pubkey>
alpi peers ping <id>
```

For the first-day walkthrough, see [QUICKSTART.md](QUICKSTART.md).

## Core concepts

**Profiles** are the isolation primitive. A profile is one directory,
one identity, one model choice, one memory, one skill set, one gateway
configuration, one schedule surface, and one ALP peer list. The
default profile lives at `~/.alpi/`; named profiles live under
`~/.alpi/profiles/<name>/`.

**Memory** is plain Markdown. `USER.md` captures facts about the user,
`MEMORY.md` captures environment quirks and durable operational facts,
and `AGENT.md` shapes how alpi should respond. Memory is updated inline
during conversations; there is no post-session reflection loop.

**Skills** are reusable recipes with a strict directory contract. They
can include instructions, scripts, references, assets, secrets, and
state. Mutations go through validation and a security scanner; secrets
live in either `.env` or a per-skill `secrets/` directory.

**Workspace** is the default root for relative paths, not a fake
security wall. File tools and terminal can use absolute paths except
for a sensitive-path denylist. Real workspace-only isolation is the
opt-in OS sandbox.

**ALP** is the Alpi Link Protocol. Each profile owns an Ed25519 keypair.
Peers pin pubkeys out of band and grant explicit capabilities such as
`link.ping`, `link.ask`, and `room.post`. ALP.1 handles same-machine
profiles over Unix sockets. ALP.2 handles inter-machine links with
Noise_XK over TCP plus budgets and rate limits. ALP.3 adds
hub-anchored rooms.

## Security posture

alpi assumes the LLM is powerful, fallible, and sitting next to user
credentials. The guardrails are local and layered:

- safe / caution / dangerous command classification;
- dangerous commands blocked with no config escape hatch;
- caution commands require interactive approval or configured allowlist;
- sensitive-path denylist shared across file and terminal posture;
- SSRF protection on web tools;
- prompt-injection warnings on fetched web/email content;
- OSV malware checks before skill or MCP install;
- optional macOS/Linux OS sandbox per profile;
- `approval.log` and `agent.log` for audit.

See [docs/SECURITY.md](docs/SECURITY.md) for the full model.

## Documentation

- [QUICKSTART.md](QUICKSTART.md) — install, model, workspace, first chat,
  gateways, profiles, ALP, doctor.
- [docs/PROFILES.md](docs/PROFILES.md) — per-profile identity,
  isolation, state, memory, skills, peers, services.
- [docs/ALP.md](docs/ALP.md) — wire protocol, identity, signatures,
  transports, methods, errors, rooms.
- [docs/SECURITY.md](docs/SECURITY.md) — threat model, approval gate,
  sandbox, injection/SSRF/path guards, dependency posture.
- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) — implementation
  reference for contributors and agents reading the codebase.
- [docs/CONFIG.md](docs/CONFIG.md) — every YAML key and when it takes
  effect.
- [docs/SKILLS.md](docs/SKILLS.md) — skill directory contract,
  frontmatter, secrets, scanner, validation.
- [docs/MODELS.md](docs/MODELS.md) — model recommendations for
  tool-heavy agent use.
- [docs/DEPLOYMENTS.md](docs/DEPLOYMENTS.md) — laptop, home server,
  multi-profile, multi-device, family/team, enterprise shapes.
- [docs/OPERATIONS.md](docs/OPERATIONS.md) — services, logs, upgrades,
  backup/restore, monitoring, disaster recovery.
- [docs/ROADMAP.md](docs/ROADMAP.md) — open work and rejected ideas.

## Tests

```bash
uv run --with pytest pytest -q
uv run --with pytest pytest --llm
```

## License

alpi is source-available from day one. The agent core is published by
[Satoshi Ltd.](https://www.satoshi-ltd.com/) under the
[Business Source Licence 1.1](LICENSE), with a scheduled conversion to
Apache 2.0 on 2030-04-23, or four years after each version's first
public release, whichever comes first.

Personal use, research, evaluation, and non-production deployments are
free. Commercial production deployments, or offering alpi as a hosted,
embedded, or managed service, are covered by a Satoshi Ltd. commercial
licence.

Commercial enquiries: **info@satoshi-ltd.com**.
