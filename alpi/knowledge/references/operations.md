# Operations answer pack

## Answer directly

- First diagnostic command: `alpi doctor` (exits non-zero on any failed live check; flags stale binary).
- Evidence rollup: `alpi digest` / `alpi -p <profile> digest`.
- Daemon control: `alpi daemon status|restart|stop` — one daemon supervises every profile on the machine.
- Durable memory promotion is CLI-only via `alpi memory promote`.

## Diagnostics

```bash
alpi doctor
alpi digest
alpi digest --since 24h
alpi digest --json
alpi -p <profile> digest --since 7d
```

- `doctor`: live checks for common setup problems.
- `digest`: read-only evidence — tool availability, gateway breaker state, skill telemetry, memory promotion backlog/pressure, compaction rate.

## Daemon

```bash
alpi daemon start|status|restart|stop
```

One daemon supervises every profile on the machine. `restart` after `uv tool install --reinstall` (or when `doctor` flags a stale binary) to drop old in-memory code.

## Logs

Per-profile under `{home}/logs/`. Rotated text caps at **1 MB** (`.log.1` = previous gen); `compaction.jsonl` does not rotate (read with `jq`).

| File | Content |
|---|---|
| `service.log` | daemon supervisor + per-profile services |
| `agent.log` | one line per turn |
| `approval.log` | terminal approval decisions (audit trail with `agent.log`) |
| `compaction.jsonl` | compaction/truncation records |
| `runs.jsonl` | run ledger: one line per long-running turn (agent/schedule/workgroup/terminal); surfaced by `alpi digest` |

```bash
alpi logs --source agent -n 100
alpi logs --source service -f
jq -r '[.ts, .session_id[0:8], .trigger, .tokens_before, .tokens_after] | @tsv' \
  ~/.alpi/logs/compaction.jsonl
```

## Memory promotion

Queue: `<home>/memories/promotion_queue.jsonl`.

```bash
alpi memory promote
alpi -p <profile> memory promote
alpi memory promote --discard-all
alpi memory promote --apply-all
```

Apply routes through `memory(action="add")`, so safety scan and dedup still apply.

## Upgrade

```bash
alpi update --check
uv tool upgrade alpi-agent
alpi daemon restart
alpi --version
alpi doctor
```

- Use the same installer family as the original install (`uv`, `pipx`, …).
- No silent migrations: if a CHANGELOG entry calls for file moves, apply them for **every profile**.

## Backup / restore

```bash
alpi backup
alpi backup --out ~/vault/alpi.alpi-backup
alpi restore ~/vault/alpi.alpi-backup
alpi restore ~/vault/alpi.alpi-backup --force
```

- One passphrase-encrypted archive of the whole `~/.alpi/` tree: all profiles, memories, sessions, skills, state, secrets, config, `.env`, ALP identity, peers, gateway + host state.
- Excluded recursively: `cache/`, `logs/`, `.trash/`, `*.sock`, `*.pid`.
- Stop daemon before restore; run `alpi doctor` and restart afterward.

## Common failure modes

| Symptom | Check |
|---|---|
| Wrong model | Active profile and `config.yaml` `model`. |
| Tool sees wrong files | Configured workspace. |
| Gateway silent | Daemon status, gateway config, logs. |
| Scheduled job missing | Daemon/scheduler running for the right profile. |
| Env var missing in script | Skill `requires_env`, profile `.env`, skill opened. |
| ALP peer fails | Peer identity, socket/TCP reachability, budget, logs. |

## Related topics

- Config keys and restart behavior: `config`
- Deployment shapes: `deployments`
- Security and credentials: `security`
