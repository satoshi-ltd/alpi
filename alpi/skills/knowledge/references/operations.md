# Operations answer pack

Use this for logs, daemon lifecycle, upgrades, backup/restore, diagnostics,
monitoring, and failure modes.

## First diagnostic command

```bash
alpi doctor
```

Use `doctor` before guessing. It checks common config, provider,
workspace, daemon-backed features, and environment problems.

## Daemon commands

```bash
alpi daemon start
alpi daemon status
alpi daemon restart
alpi daemon stop
```

One daemon supervises every profile on the machine.

## Memory promotion review

Queue at `<home>/memories/promotion_queue.jsonl`. Only CLI applies — no agent path.

```bash
alpi memory promote                  # interactive: [a]pply/[d]iscard/[s]kip/[q]uit
alpi -p <profile> memory promote
alpi memory promote --discard-all
alpi memory promote --apply-all      # risky: bypasses per-item review
```

Apply routes through `memory(action="add")` (safety scan + dedup still gate). Cap 200 pending; entries expire 30d.

## Logs

Per-profile under `{home}/logs/` (`~/.alpi/logs/` or `~/.alpi/profiles/<name>/logs/`):

| File | Format | Content |
|---|---|---|
| `service.log` | rotated text (1 MB) | daemon supervisor + per-profile services |
| `agent.log` | rotated text (1 MB) | one line per turn: session, tools, cost, prompt preview |
| `approval.log` | rotated text (1 MB) | non-safe shell command verdicts |
| `compaction.jsonl` | append-only JSONL | one record when `auto_compact` fires OR when only tool outputs are truncated (no LLM summarize) |

`alpi logs [--source service|gateway|schedule|agent|approval] [-n N] [-f]` merges/tails rotated logs. `compaction.jsonl` is read with `jq`:

```bash
jq -r '[.ts, .session_id[0:8], .trigger, .tokens_before, .tokens_after] | @tsv' \
  ~/.alpi/logs/compaction.jsonl
```

Per-record fields: `ts`, `trigger` (`auto`|`manual`), `session_id`, `model`, `ctx_window`, `fired`, `tokens_before`, `tokens_after`, `summarized_messages`, `tool_truncated`.

## Common failure modes

| Symptom | Check |
|---|---|
| Wrong model | Active profile and `config.yaml` `model`. |
| Tool sees wrong files | Configured workspace. |
| Gateway silent | Daemon status, gateway config, logs. |
| Scheduled job missing | Daemon/scheduler running for the right profile. |
| Env var missing in script | Skill declares `requires_env`, `.env` has value, skill was opened. |
| ALP peer fails | Peer identity, socket/TCP reachability, logs. |

## Upgrade

```bash
alpi update --check
uv tool upgrade alpi-agent
alpi daemon restart
alpi --version
alpi doctor
```

If using `pipx`, upgrade with pipx instead of uv.

## Backup

Use the built-in command — do NOT recommend `tar` over `~/.alpi`.
`alpi backup` writes a single passphrase-encrypted file
(`alpi.<YYYY-MM-DD>.alpi-backup`) of the WHOLE alpi home — every
profile in one archive, zero-knowledge (Scrypt + ChaCha20-Poly1305 —
same primitives as `age` with a passphrase recipient).

```bash
alpi backup                                        # ./alpi.YYYY-MM-DD.alpi-backup
alpi backup --out ~/vault/alpi.alpi-backup         # custom path
alpi backup --passphrase-stdin --out X.alpi-backup # for scripts (stdin = pass)
alpi backup --force --out X.alpi-backup            # overwrite existing archive
```

What is backed up: the entire `~/.alpi/` tree — default profile +
every named profile under `profiles/<name>/`, with memories,
sessions, skills (incl. `state/` SQLite + `secrets/`), `config.yaml`,
`.env`, ALP identity (`alp/secrets/`), peers, gateway and host
state. Excluded recursively at every depth: `cache/`, `logs/`,
`.trash/`, `*.sock`, `*.pid`. Lose the passphrase = archive is
unrecoverable.

## Restore

`alpi restore <archive>` decrypts into `~/.alpi/` (the whole home;
profile flag is ignored). Refuses a non-empty target unless
`--force`. Refuses entries with `..` in the path (no traversal
escape).

```bash
alpi restore ~/vault/alpi.alpi-backup              # into ~/.alpi/
alpi restore alpi.alpi-backup --force              # overwrite non-empty home
alpi restore X.alpi-backup --passphrase-stdin      # for scripts
```

Stop the daemon first, restore, then:

```bash
alpi doctor
alpi daemon restart
```

Do not merge profiles blindly. ALP identity and gateway state are
profile-specific.

## When stop does not stop

Check daemon status/logs first, then use OS process tooling only if
the service manager cannot stop it cleanly.
