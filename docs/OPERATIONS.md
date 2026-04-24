# Operations

Runbook for running alpi seriously — at home or inside an
organisation. Covers logs, services, upgrades, backup + restore,
identity rotation, and monitoring.

If you just installed alpi and want to chat, you don't need this
doc yet: [QUICKSTART.md](../QUICKSTART.md) covers everything. Come
back here when things break, or when you need to move a profile,
or when it's time to ship a new version.

## Logs — the five files you'll actually read

Every profile writes to `{home}/logs/` with the same format so
`alpi logs` can merge them:

```
~/.alpi/logs/                     ← default profile
~/.alpi/profiles/<name>/logs/     ← named profile
```

Each file rotates at **1 MB**; `.log.1` holds the previous
generation. One file per subsystem:

| File | What it answers | Who writes it |
|---|---|---|
| `gateway.log` | Did my Telegram / IMAP / Gmail daemon actually start? Did it accept this inbound? Which chat id? | `alpi gateway start` |
| `schedule.log` | Did my cron job fire? What did it output? Is it stuck in a loop? | `alpi schedule start` |
| `alp.log` | Did my ALP listener come up? Which peer asked what and when? Which were rejected by capability? | `alpi alp start` |
| `agent.log` | What has the agent *been doing*? One line per turn: session id, elapsed, tools called, reply length, cost, user prompt preview. Cross-session grep index. | the engine (every turn on every surface) |
| `approval.log` | Security audit of every non-safe shell command the LLM tried to run: caution (pending / once / session / always / deny) or dangerous (always denied). | the approval system |

**Tail one or all:**

```bash
alpi logs                          # merged tail of every subsystem
alpi logs --source gateway         # just gateway.log
alpi logs --source agent -n 500    # last 500 lines of agent.log
alpi logs -f                       # follow mode (poll every 1s)
```

The `agent.log` + `approval.log` pair is your **audit trail**.
Anyone who needs to answer "what did alpi do this week?" or "did
the agent run anything risky?" should be grepping those two
files.

## Services — which daemon is which

alpi has three daemons, each installable as a launchd (macOS) or
systemd --user (Linux) unit:

| Daemon | What it does | CLI | Service install |
|---|---|---|---|
| `gateway` | Listens on Telegram / IMAP / Gmail, spawns a one-shot `alpi chat` per inbound. | `alpi gateway start\|stop\|restart` | `alpi setup → Gateway service` |
| `schedule` | Fires cron + one-shot jobs. Auto-installs on first run. | `alpi schedule start\|stop\|restart` | `alpi setup → Schedule service` |
| `alp` | Listens on the Unix-domain socket for ALP requests. | `alpi alp start\|stop\|restart` | `alpi setup → ALP service` |

Every service is per-profile. Installing the `gateway` service
for `work` doesn't install it for `default`.

### When `stop` doesn't stop

If you run `alpi gateway stop` on a service-managed daemon,
launchd / systemd will respawn it within seconds (the plist
declares `KeepAlive=true`). The CLI warns when this is about to
happen. To permanently stop a daemon:

```bash
alpi setup → Gateway service → Uninstall
```

### When `restart` is really what you want

After `uv tool install --reinstall`, the long-running service
still holds the old binary's code. Use:

```bash
alpi gateway restart      # stop + wait up to 15s for service to respawn
```

`alpi doctor` will warn with "stale binary — run `alpi X restart`
to reload" when the binary on disk is newer than the running
process.

## Upgrades

alpi doesn't ship silent migrations. When the on-disk schema
changes, the release notes say so and ask you to move files by
hand. Today's upgrade rule of thumb:

1. `git pull` + `uv tool install --reinstall .` (or the equivalent
   with `uv tool install <version>`).
2. `alpi doctor` — the Services section flags any stale daemon.
3. `alpi gateway restart` / `alpi schedule restart` /
   `alpi alp restart` as needed.
4. If the CHANGELOG entry calls for file moves (e.g. the ALP
   layout change in v0.2.68), follow them for **every profile**.
5. Re-run `alpi doctor` — should be clean.

## Backup + restore

A profile is a single directory. Back up the directory, restore
the directory, you have the profile back.

**What's in the backup.** Treat the whole `{home}/` as atomic.
The pieces worth knowing:

- `config.yaml` + `.env` — reproducible config. Keep `.env` in a
  password manager, not in plain-text backup storage, if you
  treat API keys as secret.
- `memories/` — your USER.md + MEMORY.md + AGENT.md. The
  `.bak` siblings hold the previous generation.
- `sessions/` — every chat history. Growing monotonically unless
  you run `alpi setup → Cleanup`.
- `alp/secrets/alp_key.{pem,pub}` — your ALP identity. Losing
  this = every peer has to re-pin you. Treat like an SSH key.
- `alp/peers.yaml` — the list of peers who can reach this
  profile.
- `skills/` — your installed skills, including any
  `skills/<category>/<skill>/secrets/` folders (these have OAuth
  tokens — 0700 by default).

**Minimal backup script** (cron nightly, whatever you prefer):

```bash
#!/bin/sh
# tar + gpg; drop the result somewhere that isn't the same machine
tar czf - ~/.alpi | gpg -c -o "/backups/alpi-$(date +%F).tar.gz.gpg"
```

**Restore** is `tar xzf … -C ~`. After restore, run
`alpi doctor` — you'll catch any peer whose counterpart rotated
their key since the backup.

## ALP identity rotation

Rotating the Ed25519 keypair is a deliberate, disruptive act.
Every peer who pinned your old pubkey must update their
`peers.yaml` before you can reach them again.

```bash
alpi alp stop                          # or: alpi setup → ALP service → Uninstall
rm ~/.alpi/alp/secrets/alp_key.{pem,pub}
alpi alp start                         # generates a fresh pair
alpi peers key                         # print the new pubkey; send OOB to every peer
```

Every peer on the other end:

```bash
alpi peers remove <old-id>
alpi peers add <new-id> <new-pubkey> --allow link.ping --allow link.ask
```

Treat rotation as planned downtime. Coordinate with your mesh.

## Monitoring + alerting

alpi has no built-in metrics endpoint by design (**Zero Knowledge**
principle — no telemetry, no phone-home). For in-house
observability, the signals to watch:

- **Daemon liveness.** `alpi doctor` in a cron; exits non-zero if
  any live check fails. Alert on non-zero.
- **Log tail error rate.** `grep ERROR ~/.alpi/logs/*.log | wc -l`
  over a window — spike = misconfig, broken credentials, LLM API
  outage.
- **Cost ceiling.** `jq '.cost_usd' ~/.alpi/sessions/*.json` sums
  the spend per profile. Bound this in a cron job and alert if a
  threshold is crossed. Budget enforcement *inside* alpi for ALP
  peer traffic lands in ALP.2.
- **`approval.log` triggers.** Any line with a
  `caution always-approved` entry means the allowlist grew — a
  new command pattern is now auto-permitted for this profile. Put
  a trigger on `approval.log` modifications; review before
  accepting a new always-allowed pattern into steady state.
- **Disk.** `alpi profile list` shows the per-profile footprint.
  In a managed environment, bound it — a profile quietly growing
  past 1 GB usually means voice-cache or session-log retention
  that the user didn't know was on.

For enterprise setups, ship the log dir through a forwarder
(rsyslog / Vector / fluentd) to whatever SIEM you already have.
The log format is standard Python logging with ISO timestamps;
there's no parser to write.

## Disaster recovery checklist

You've lost a machine. Here's the order of operations to restore.

1. Reinstall alpi on the replacement machine (`uv tool install`).
2. Restore `~/.alpi/` from backup.
3. `alpi doctor` — note which services are "not installed".
4. Re-install the services you actually want
   (`alpi setup → Gateway service → Install` etc.).
5. If your ALP identity is intact (backup included
   `alp/secrets/`), your peers still reach you. If you had to
   regenerate, see **ALP identity rotation** above.
6. `alpi` → test a turn. `alpi gateway start` → send a message
   from Telegram; verify the reply lands.
7. Tail `agent.log` for 24 h to confirm the gateway and schedule
   are firing normally.

If you had no backup: you've lost the profile. Start from
quickstart, re-pair your ALP peers, re-install your skills. The
conversation history is gone. This is by design — alpi doesn't
phone home, so there's no "recover from the cloud" path.

## Common failure modes

**"Listener not running"** when calling `@peer …`. The peer's
`alpi alp start` isn't up. Check `alpi doctor` on the peer's
machine.

**Two gateways running simultaneously.** `ps aux | grep "alpi
gateway"` shows more than one pid. Happens after a failed
reinstall. Fix:
`alpi gateway stop && pkill -f "alpi gateway start" && sleep 1 &&
alpi gateway start`.

**Message didn't save to memory.** Check the session file:
`jq '.turns[-1].tools' ~/.alpi/sessions/*.json` — if no `memory`
tool call landed, the model decided the signal wasn't worth a
write. Inline-learning is LLM-driven; if you want a guaranteed
capture, tell alpi explicitly ("remember that…").

**Telegram is silent.** `alpi logs --source gateway -n 100`.
Expected to see inbound lines with `[telegram]` prefix. If
nothing: bot token revoked, offset corrupted, or the daemon
crashed. `alpi doctor` flags credential problems explicitly.

**Stale binary.** After `uv tool install --reinstall`, the
daemon still runs the old code. `alpi doctor` warns; fix with
`alpi {gateway,schedule,alp} restart`.
