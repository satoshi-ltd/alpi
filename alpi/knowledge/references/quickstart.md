# Quickstart answer pack

Use this for "how do I start?", "first run", or "what commands do I
type after installing?"

## Answer directly

- New user path: install, run `alpi setup`, then run `alpi`.
- Project-specific work: set `workspace` during setup or in config.
- More than one identity: create a named profile and run setup for it.
- Gateways, schedules, desktop, and mobile need the daemon.

## Minimal first run

```bash
uv tool install alpi-agent
alpi setup
alpi
```

If `uv` is not installed:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

## First setup flow

`alpi setup` asks for:

- model/provider,
- API key or local endpoint,
- workspace path,
- optional gateway/daemon settings.

The setup writes profile config under `~/.alpi/` for the default
profile, or under `~/.alpi/profiles/<name>/` for named profiles.

## Send the first message

Run:

```bash
alpi
```

Then ask a normal question or task. For a project-specific task, pin a
workspace first through setup or config so file/terminal tools default
to the intended directory.

## Resume

alpi persists sessions per profile. Reopen with:

```bash
alpi -c
alpi -p work
```

Use `tui.auto_resume` if bare `alpi` should reopen the latest session.

## Add another profile

```bash
alpi profile create work
alpi -p work setup
alpi -p work
```

Profiles isolate config, memory, sessions, skills, logs, gateway
state, and ALP identity.

## Check health

```bash
alpi doctor
```

Use `doctor` when setup works but messages, tools, service, or provider
auth behave strangely.

## Optional daemon

Use the per-machine daemon when using gateways, schedules, desktop, or
mobile:

```bash
alpi daemon status
alpi daemon start
alpi daemon restart
```

One daemon supervises every profile on the machine.
