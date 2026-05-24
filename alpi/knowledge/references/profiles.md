# Profiles answer pack

Use this for "what is a profile?", "where is my data?", or "how do I
separate work/personal?"

## Answer directly

- Default profile lives at `~/.alpi/`.
- Named profiles live at `~/.alpi/profiles/<name>/`.
- Use profiles for separate identity, memory, credentials, ALP trust, or budget.
- Use workspace for project scope when identity/memory can be shared.

## Short answer

A profile is an isolated alpi identity and data directory. Use
profiles when config, memory, skills, sessions, cost tracking,
gateway settings, logs, or ALP identity should not mix.

## Locations

- Default profile: `~/.alpi/`
- Named profile: `~/.alpi/profiles/<name>/`

Important files/directories:

| Path | Purpose |
|---|---|
| `config.yaml` | Model, tools, gateway, scheduler, workspace, budget. |
| `.env` | Provider keys and static secrets. |
| `memory/` | Persistent user/project memory. |
| `sessions/` | Local human chat history only. Gateway, schedule, workgroup, and system-prefixed turns stay out of normal profile resume/history. |
| `skills/` | User-created skills. |
| `rag/` | Local RAG index over the workspace (`store.sqlite` with sqlite-vec). |
| `logs/` | Service and runtime logs. |
| `alp/` | ALP identity, peers, workgroups. |
| `run/` | Runtime state such as sockets/PIDs. |

## Commands

```bash
alpi
alpi -p work
alpi -p work setup
alpi -p work doctor
alpi -p work service start
```

## What is isolated

Profiles isolate:

- model/provider config,
- API keys in `.env`,
- memory,
- skills,
- local chat sessions,
- gateway and scheduler state,
- logs,
- ALP identity and peer list,
- budget ledger.

## When to create a profile

Use a new profile for:

- personal vs work,
- separate employers/clients,
- a service identity that runs continuously,
- different model/provider/cost posture,
- different ALP trust boundary.

Do not create a profile just for a single project if memory and
identity can safely be shared; use workspace config for project scope.

## ALP identity

Each profile has its own ALP identity. Peers trust the profile
identity, not the machine globally. If a user says "my work and
personal alpis should be separate", profiles are the answer.

## Service rule

Run one service process per profile. If a gateway or scheduler behaves
as if it is using the wrong identity, check which profile's service is
running.

## Related topics

- Config and `.env`: `config`
- Daemon lifecycle: `operations`
- ALP identity: `alp`
- Skills per profile: `skills`
