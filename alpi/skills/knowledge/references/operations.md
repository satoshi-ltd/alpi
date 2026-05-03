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

Back up the profile directory:

```bash
tar -czf alpi-profile.tgz ~/.alpi
```

For named profiles, include `~/.alpi/profiles/<name>/`. Protect the
archive; it can contain memory, sessions, config, keys, skills, and
secrets.

## Restore

Stop services first, restore files, then run:

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
