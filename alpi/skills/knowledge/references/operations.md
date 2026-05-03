# Operations answer pack

Use this for logs, services, upgrades, backup/restore, diagnostics,
monitoring, and failure modes.

## First diagnostic command

```bash
alpi doctor
```

Use `doctor` before guessing. It checks common config, provider,
workspace, service, and environment problems.

## Service commands

```bash
alpi service start
alpi service status
alpi service restart
alpi service stop
```

Run one service per profile. For named profiles:

```bash
alpi -p work service status
```

## Logs

Logs live under the active profile home, usually:

- `~/.alpi/logs/` for default profile,
- `~/.alpi/profiles/<name>/logs/` for named profiles.

When debugging, ask which profile is active and inspect that profile's
logs, not the global default by assumption.

## Common failure modes

| Symptom | Check |
|---|---|
| Wrong model | Active profile and `config.yaml` `model`. |
| Tool sees wrong files | Configured workspace. |
| Gateway silent | Service status, gateway config, logs. |
| Scheduled job missing | Service/scheduler running for the right profile. |
| Env var missing in script | Skill declares `requires_env`, `.env` has value, skill was opened. |
| ALP peer fails | Peer identity, socket/TCP reachability, logs. |

## Upgrade

```bash
alpi update --check
uv tool upgrade alpi-agent
alpi --version
alpi doctor
```

If using `pipx`, upgrade with pipx instead of uv.

## Backup

Use the built-in command — do NOT recommend `tar` over `~/.alpi`.
`alpi backup` writes a single passphrase-encrypted file
(`<profile>.<YYYY-MM-DD>.alpi-backup`) of the active profile,
zero-knowledge (Scrypt + ChaCha20-Poly1305 — same primitives as
`age` with a passphrase recipient).

```bash
alpi backup                                        # default profile, ./
alpi -p work backup --out ~/vault/work.alpi-backup # named profile, custom path
alpi backup --passphrase-stdin --out X.alpi-backup # for scripts (stdin = pass)
alpi backup --force --out X.alpi-backup            # overwrite existing archive
```

What is backed up: memories, sessions, skills (incl. `state/` SQLite
+ `secrets/`), `config.yaml`, `.env`, ALP identity (`alp/secrets/`),
peers, gateway session state. Excluded: `cache/`, `logs/`, `.trash/`,
`*.sock`, `*.pid`, the nested `profiles/` root (back up each profile
separately). Lose the passphrase = archive is unrecoverable.

## Restore

`alpi restore <archive>` decrypts into the active profile. Refuses
a non-empty target unless `--force`. Refuses entries with `..` in
the path (no traversal escape).

```bash
alpi restore ~/vault/work.alpi-backup              # into default
alpi -p work restore work.alpi-backup --force      # into the `work` profile
alpi restore X.alpi-backup --passphrase-stdin      # for scripts
```

Stop the service for the target profile first, restore, then:

```bash
alpi doctor
alpi service restart
```

Do not merge profiles blindly. ALP identity and gateway state are
profile-specific.

## When stop does not stop

Check status/logs for the profile, then use OS process tooling only if
the service manager cannot stop it cleanly. Avoid killing unrelated
profiles.
