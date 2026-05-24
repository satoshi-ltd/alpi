# Quickstart

First-day walkthrough. Takes about 10 minutes end-to-end and leaves
you with a working alpi — model selected, workspace pinned, first
session running, and `alpi doctor` green. Profiles, gateways, apps,
and ALP come next.

For concepts behind any step, see [ARCHITECTURE.md](docs/ARCHITECTURE.md).
For the security posture, see [SECURITY.md](docs/SECURITY.md).
Why alpi is built the way it is: see
[README.md](README.md).

<!-- alpi-demo -->

## 1. Install

```bash
uv tool install alpi-agent     # install
alpi setup                     # use
```

PyPI package is `alpi-agent`; the binary is `alpi`. Alternatives
and update path → [INSTALL.md](docs/INSTALL.md).

Needs Python ≥ 3.10. The browser tool downloads Chromium
(~200 MB) the first time it runs — no separate install step.

Check it works:

```bash
alpi --version
```

## 2. Pick a model

The fresh profile ships **without** a default model — you choose
your provider and your model. Open the setup wizard:

```bash
alpi setup
```

Pick **Model / Provider**, choose a provider, paste the API key
when prompted, pick a model. For recommendations see
[docs/MODELS.md](docs/MODELS.md) — if you want a single sensible
choice, **Claude Sonnet 4.6** (`anthropic/claude-sonnet-4-6`)
is the pragmatic daily driver. If you want fully local (no cloud),
install [Ollama](https://ollama.com/) first and pick **Ollama** in
the wizard.

## 3. Pin a workspace

Same wizard, pick **Workspace**. Point it at the directory alpi is
allowed to read and write — typically the project you're working
on. Without a workspace, alpi falls back to the current working
directory at launch with a warning; that's fine for trying things,
not for real use.

## 4. Send your first message

```bash
alpi
```

Type `hola` and press Enter. The TUI streams the model's reply.
Useful first commands to try inside the TUI:

- `/help` — list every slash command.
- `/memory` — show what alpi remembers about you (`USER.md`,
  `MEMORY.md`, `AGENT.md`).
- `/skills` — list installed skills.
- `/status` — session snapshot (turns, tokens, cost).
- `/new` — start a fresh session.

And try asking alpi about itself — *"how do I configure the TUI
theme?"*, *"how does the ALP protocol work?"*. The
`alpi_knowledge` tool answers from the packaged docs without
leaving the terminal.

Leave it with Ctrl-C or `/exit`.

## 5. Resume where you left off

```bash
alpi -c
```

`-c` / `--continue` rehydrates the last session. To make this the
default behaviour without typing `-c` every time, enable
`tui.auto_resume` in `~/.alpi/config.yaml` (or set it via
`alpi setup`).

## 6. Optional: connect a gateway

If you want alpi to answer you on Telegram / IMAP / Gmail / Matrix, run the
wizard again:

```bash
alpi setup → Gateways
```

Pick the channel, follow the prompts, then make sure the unified
daemon is running so alpi answers 24/7:

```bash
alpi daemon status
alpi daemon start
```

Gateways are compatibility bridges for 24/7 reach. The primary
surfaces are the terminal, desktop app, and mobile app talking to
the daemon directly. The single `alpi daemon` process supervises
every profile on the machine and hosts gateways, scheduler ticks,
ALP listeners, workgroup pollers, and the host plane.

## 7. Add a second profile (optional)

If you want a work profile that's completely isolated from your
personal one (different API keys, different memory, different
Telegram bot):

```bash
alpi profile create work
alpi -p work setup
```

Everything is per-profile: home directory, sessions, memory,
skills, keys, peers. See [docs/PROFILES.md](docs/PROFILES.md) for
the full model.

## 8. Link to other alpis (optional)

If you plan to link profiles or machines with other alpis, the
daemon already exposes the [Alpi Link Protocol](docs/ALP.md)
listener when the profile's ALP subsystem is enabled. Then exchange
pubkeys with peers:

```bash
alpi daemon status
alpi setup → ALP → Peers
```

See [docs/DEPLOYMENTS.md](docs/DEPLOYMENTS.md) for topologies
(laptop + home server, multi-device, team, enterprise).

## 9. Check everything is healthy

```bash
alpi doctor
```

Runs live checks: model reachable, gateways logged in, MCP servers
handshaking, services alive, ALP socket listening, peers reachable.
Green = you're done.

## Next steps

- [docs/SKILLS.md](docs/SKILLS.md) — teach alpi reusable recipes
  (skills are live-by-default, scanner-gated, per-profile).
- [docs/OPERATIONS.md](docs/OPERATIONS.md) — logs, services,
  upgrades, backups.
- [docs/SECURITY.md](docs/SECURITY.md) — approval gate, sandbox,
  and how alpi protects you from the LLM.
- [docs/DEPLOYMENTS.md](docs/DEPLOYMENTS.md) — multi-alpi
  topologies from personal to enterprise.
