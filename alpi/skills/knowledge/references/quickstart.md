# Quickstart answer pack

Use this for "how do I start?", "first run", or "what commands do I
type after installing?"

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
- optional gateway/service settings.

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
alpi
alpi -p work
```

Use the TUI/session commands to continue or inspect previous turns.

## Add another profile

```bash
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

## Optional service

Start a background service when using gateways or scheduled jobs:

```bash
alpi service start
alpi service status
alpi service stop
```

Use one service process per profile.
