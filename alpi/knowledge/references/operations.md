# Operations answer pack

## Answer directly

- First diagnostic command: `alpi doctor` (exits non-zero on any failed live check; flags stale binary).
- Security posture command: `alpi audit` (whole install, every profile);
  use `alpi audit --offline` for local-only cron checks.
- Evidence rollup: `alpi digest` / `alpi -p <profile> digest`.
- Daemon control: `alpi daemon status|restart|stop` — one daemon supervises every profile on the machine.
- Durable memory promotion is CLI-only via `alpi memory promote`.

## Diagnostics

```bash
alpi doctor
alpi audit --offline
alpi audit
alpi audit-log
alpi digest
alpi digest --since 24h
alpi digest --json
alpi -p <profile> digest --since 7d
```

- `doctor`: live checks for common setup problems.
- `audit`: read-only security posture for the whole install. Offline checks:
  secret-file permissions, public/all-interface binds, terminal sandbox,
  LLM watchdog, and daily spend cap. Online check: OSV CVEs for installed
  Python packages. Exit code is non-zero only for `fail`, not warnings.
- `audit-log`: machine-wide, bounded host-RPC administrative trail attributed
  to the acting connection/device. Supports connection, device, result, limit
  and JSON filters; it contains no chat messages or credential/config values.
  Direct CLI/setup writes are not covered yet.
- `digest`: read-only evidence — tool availability, skill telemetry, memory promotion backlog/pressure, compaction rate.

## Daemon

```bash
alpi daemon start|status|restart|stop
```

One daemon supervises every profile on the machine. `restart` after `uv tool install --reinstall` (or when `doctor` flags a stale binary) to drop old in-memory code.

## Logs

Two scopes, do not conflate:

- **Daemon-wide (root):** `~/.alpi/logs/service.log` — ONE file per installation, never duplicated under a profile. `alpi logs --source service` always reads it regardless of `-p`.
- **Per profile:** `{home}/logs/` for the active profile (`~/.alpi/logs/` for default, `~/.alpi/profiles/<name>/logs/` otherwise). `alpi -p <name> logs ...` reads under that profile (`-p` belongs to the root `alpi` command, not to `logs`).

Rotated text caps at **1 MB** (`.log.1` = previous gen); `compaction.jsonl` does not rotate (read with `jq`).

| File | Scope | Content |
|---|---|---|
| `service.log` | root | daemon supervisor + per-profile services. `alpi logs --source service` always reads the root file regardless of `-p`. |
| `agent.log` | per profile | one line per engine turn on every surface (TUI, schedule, workgroup, inbound ALP, sub-agents). |
| `approval.log` | per profile | terminal approval decisions (audit trail with `agent.log`). |
| `admin-audit.jsonl` | root | administrative mutations, max ~20 MB across current + 3 rotations; query with `alpi audit-log`. |
| `compaction.jsonl` | per profile | compaction/truncation records. |
| `runs.jsonl` | per profile | run ledger: one line per long-running turn (agent/schedule/workgroup/terminal); surfaced by `alpi digest`. |
| `ledger.json` | per profile | daily budget gate (live counters, UTC reset) + 30-day per-day spend history (usd + input/output tokens, ALL spend incl. non-token costs like image generation); served by `host.usage.daily`. |

```bash
alpi logs --source agent -n 100              # active profile's agent.log
alpi -p mira logs --source agent             # mira's agent.log (note: -p before subcommand)
alpi logs --source service -f                # always reads ~/.alpi/logs/service.log
alpi audit-log --connection conn_customer -n 100
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

- One passphrase-encrypted archive of the whole `~/.alpi/` tree: all profiles, memories, sessions, skills, state, secrets, config, `.env`, ALP identity, peers, host state.
- Excluded recursively: `cache/`, `logs/`, `.trash/`, `*.sock`, `*.pid`.
- Stop daemon before restore; run `alpi doctor` and restart afterward.

## Common failure modes

| Symptom | Check |
|---|---|
| Wrong model | Active profile and `config.yaml` `model`. |
| Tool sees wrong files | Configured workspace. |
| Email tool fails | per-account creds in `.env` (`EMAIL__<ID>__PASSWORD`) / `secrets/gmail_tokens/<id>.json`, account config (`alpi setup → Email`), logs. |
| Scheduled job missing | Daemon/scheduler running for the right profile. |
| Env var missing in script | Skill `requires_env`, profile `.env`, skill opened. |
| ALP peer fails | Peer identity, socket/TCP reachability, budget, logs. |

## Related topics

- Config keys and restart behavior: `config`
- Deployment shapes: `deployments`
- Security and credentials: `security`
