# Operations answer pack

Use this for logs, daemon lifecycle, upgrades, backup/restore,
diagnostics, monitoring, and failure modes.

## Answer directly

- First diagnostic command: `alpi doctor`.
- Evidence rollup: `alpi digest` or `alpi -p <profile> digest`.
- Daemon control: `alpi daemon status|restart|stop`.
- Durable memory promotion is CLI-only through `alpi memory promote`.

## Diagnostics

```bash
alpi doctor
alpi digest
alpi digest --since 24h
alpi digest --json
alpi -p <profile> digest --since 7d
```

`doctor` checks common setup problems. `digest` is read-only evidence:
tool availability, gateway breaker state, skill telemetry, memory
promotion backlog/pressure, and compaction rate.

## Daemon

```bash
alpi daemon start
alpi daemon status
alpi daemon restart
alpi daemon stop
```

One daemon supervises every profile on the machine.

## Logs

Per-profile under `{home}/logs/`:

| File | Content |
|---|---|
| `service.log` | daemon supervisor + per-profile services |
| `agent.log` | one line per turn |
| `approval.log` | terminal approval decisions |
| `compaction.jsonl` | compaction/truncation records |

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

Apply routes through `memory(action="add")`, so safety scan and dedup
still apply.

## Upgrade

```bash
alpi update --check
uv tool upgrade alpi-agent
alpi daemon restart
alpi --version
alpi doctor
```

Use the same installer family originally used for install (`uv`, `pipx`,
etc.).

## Backup / restore

```bash
alpi backup
alpi backup --out ~/vault/alpi.alpi-backup
alpi restore ~/vault/alpi.alpi-backup
alpi restore ~/vault/alpi.alpi-backup --force
```

`alpi backup` writes one passphrase-encrypted archive for the whole
`~/.alpi/` tree: all profiles, memories, sessions, skills, state,
secrets, config, `.env`, ALP identity, peers, gateway state, and host
state. Excluded recursively: `cache/`, `logs/`, `.trash/`, `*.sock`,
`*.pid`.

Stop daemon before restore; run `alpi doctor` and restart afterward.

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
