# Quickstart answer pack

## Answer directly

- New-user path: `uv tool install alpi-agent` → `alpi setup` → `alpi`.
- Project work: pin `workspace` in setup/config so file/terminal tools default there.
- Second identity: `alpi profile create <name>`, then setup + run with `-p <name>`.
- Schedules, desktop, mobile all require the daemon.

## Commands

| Goal | Command |
| --- | --- |
| Install (recommended) | `uv tool install alpi-agent` |
| Install uv first | `curl -LsSf https://astral.sh/uv/install.sh \| sh` |
| First setup wizard | `alpi setup` |
| Start / send first message | `alpi` |
| Resume latest session | `alpi -c` |
| Run named profile | `alpi -p work` |
| Create profile | `alpi profile create work` |
| Health check | `alpi doctor` |
| Daemon | `alpi daemon {status,start,restart}` |

PyPI package is `alpi-agent`; binary/import/home dir is `alpi`. Install details → see install.

## Setup wizard

`alpi setup` collects: model/provider, API key or local endpoint, workspace path, optional email/daemon settings. Writes config to `~/.alpi/` (default profile) or `~/.alpi/profiles/<name>/` (named). Config keys → see config.

## Profiles

`alpi -p <name>` selects a profile. Each isolates config, memory, sessions, skills, logs, and ALP identity.

## Resume

Sessions persist per profile. `alpi -c` reopens the latest; set `tui.auto_resume` so bare `alpi` does the same. `alpi chat --once` resumes too — `-c` for the last session, `--session <id>` for a specific one — so a script can drive a multi-turn chat where each turn keeps the prior context.

## Daemon

One per-machine daemon supervises every profile; required for schedules, desktop, mobile. `alpi setup` auto-installs and starts it.

## doctor

Run `alpi doctor` when setup succeeds but messages, tools, service, or provider auth misbehave; output names the missing piece and the wizard step that fixes it.

## Related topics

- install — install paths, daemon backends, updating, troubleshooting
- config — config keys, workspace, profiles layout
