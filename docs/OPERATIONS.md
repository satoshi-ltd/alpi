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
generation.

| File | What it answers | Who writes it |
|---|---|---|
| `service.log` | Did the daemon start? Which services came up for which profile? Did a gateway accept this inbound? Did a peer hit an ALP listener? Did a cron job fire? | the daemon supervisor + every per-profile service that logs through the root logger |
| `agent.log` | What has the agent *been doing*? One line per turn: session id, elapsed, tools called, reply length, cost, user prompt preview. Cross-session grep index. | the engine (every turn on every surface) |
| `approval.log` | Security audit of every non-safe shell command the LLM tried to run: caution (pending / once / session / always / deny) or dangerous (always denied). | the approval system |

**Tail one or all:**

```bash
alpi logs                          # merged tail of every source
alpi logs --source service         # just service.log
alpi logs --source agent -n 500    # last 500 lines of agent.log
alpi logs -f                       # follow mode (poll every 1s)
```

The `agent.log` + `approval.log` pair is your **audit trail**.
Anyone who needs to answer "what did alpi do this week?" or "did
the agent run anything risky?" should be grepping those two
files.

## Daemon — one process per machine, every profile inside

alpi runs a single `com.alpi.daemon` process (launchd plist on
macOS, systemd-user unit on Linux) that supervises every profile
under `~/.alpi/` — default plus each `profiles/<name>/`. Each
profile gets its own per-service supervised tasks named
`<profile>/<service>` (e.g. `mirai/gateway`, `ghost/alp`); a crash
in one profile's service leaves siblings untouched.

| What it does | Lifecycle | Install / config |
|---|---|---|
| Boots one task per (profile, service) on a single asyncio loop: gateway (Telegram / IMAP / Gmail / webhook), scheduler tick, ALP socket (Unix + optional TCP/Noise_XK), workgroups poller, host plane. Toggle which services run for a profile via `service.{gateway,schedule,alp,workgroups,host}: bool` in that profile's `config.yaml`. | `alpi daemon start\|stop\|restart\|status` | auto-installed on first `alpi setup`; manage from `alpi setup → Services → Daemon` (default profile only) |

There's exactly one daemon per machine, one plist / unit. Adding
a new profile just creates a directory under `~/.alpi/profiles/`;
the daemon picks it up on its next restart. Operational verbs
that aren't lifecycle survive on their own:

```bash
alpi schedule run-once          # tick the scheduler once, in-process
alpi schedule fire <job-id>     # ad-hoc run of a specific job
```

### Linux: lingering

`systemctl --user` services die when you log out unless lingering
is enabled. `alpi daemon install` runs `loginctl enable-linger
$USER` automatically; on restricted environments (WSL without
`systemd=true` in `/etc/wsl.conf`, minimal containers) `loginctl`
may not exist — the install logs a warning and you'll need to
keep the daemon foregrounded under `tmux` / `screen`, or fix the
linger setup manually.

### When `stop` doesn't stop

If you run `alpi daemon stop` while the unit is installed, the
supervisor will respawn it within seconds (the plist declares
`KeepAlive=true`). To permanently stop:

```bash
alpi setup → Services → Daemon → Uninstall
```

### When `restart` is really what you want

After `uv tool install --reinstall`, the long-running daemon
still holds the old binary's code. Use:

```bash
alpi daemon restart      # stop + wait for the supervisor to respawn
```

`alpi doctor` flags "stale binary — `alpi daemon restart` to
reload" when the binary on disk is newer than the running
process.

## Upgrades

alpi doesn't ship silent migrations. When the on-disk schema
changes, the release notes say so and ask you to move files by
hand. Today's upgrade rule of thumb:

1. `git pull` + `uv tool install --reinstall .` (or the equivalent
   with `uv tool install <version>`).
2. `alpi doctor` — the Daemon row flags a stale binary.
3. `alpi daemon restart` — one daemon supervises every profile,
   so a single restart picks up the new code for all of them.
   (`launchctl list | grep com.alpi.daemon` confirms the unit.)
4. If the CHANGELOG entry calls for file moves (e.g. the ALP
   layout change in v0.2.68), follow them for **every profile**.
5. Re-run `alpi doctor` — should be clean.

## Dependencies — cadence + LiteLLM

alpi pins a tight range on its hot-path deps so a silent SDK release
can't break tool-calling, streaming, or cost reporting. The one to
watch is **LiteLLM** — every provider (OpenAI, Anthropic, Ollama,
OpenRouter, Gemini, Groq, Mistral, DeepSeek…) flows through it.

**Why LiteLLM and not raw provider SDKs.** alpi is single-maintainer.
Writing and maintaining one adapter per provider is a maintenance
trap. LiteLLM costs one dep + a quarterly changelog read; raw SDKs
cost N adapters forever.

**Re-audit cadence — quarterly.** When the calendar hits the next
review:

1. Read [LiteLLM release notes](https://docs.litellm.ai/release_notes)
   from our current pin to latest.
2. Diff the surface alpi uses (5 entry points): ``litellm.completion``,
   ``litellm.completion_cost``, ``litellm.model_cost``,
   ``litellm.get_llm_provider``, the suppress/telemetry flags.
3. Run the LLM-in-loop probe (``pytest tests/llm --llm``) against the
   model matrix on the candidate version.
4. Bump the floor in ``pyproject.toml`` to the new tested version,
   keep the upper bound one minor ahead (``>=1.83,<1.85`` shape).
5. ``uv lock``, commit.

**CVEs.** Filter by surface: alpi uses the **SDK**, not the **Proxy**
server. CVEs scoped to LiteLLM Proxy (e.g. CVE-2026-30623, MCP stdio
RCE) don't apply. SDK CVEs do — bump promptly.

**Alternatives evaluated.** Raw SDKs (rejected: maintenance cost,
see above). [chuk-llm](https://github.com/chrishayuk/chuk-llm) on
the radar but immature for our provider matrix at audit time.

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
alpi daemon stop                       # or: alpi setup → Services → Daemon → Stop
rm ~/.alpi/alp/secrets/alp_key.{pem,pub}
alpi daemon start                      # generates a fresh pair when the ALP listener boots
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
  any live check fails. Alert on non-zero. The Daemon row covers
  the supervisor's PID + install backend.
- **Log tail error rate.** `grep ERROR ~/.alpi/logs/*.log | wc -l`
  over a window — spike = misconfig, broken credentials, LLM API
  outage.
- **Cost ceiling.** Set `budget.daily_usd` (paid models) or
  `budget.daily_tokens` (local) in the profile's `config.yaml` —
  see [CONFIG.md → Budget](CONFIG.md#budget). The ledger at
  `~/.alpi/<profile>/logs/ledger.json` is the in-process gate;
  every interactive turn, gateway reply, scheduled job, sub-agent
  spawn, and inbound ALP call admits against it before running and
  records its actual spend after. For external alerting that
  catches provider-side drift, `jq '.cost_usd' ~/.alpi/sessions/*.json`
  still sums historical session spend.
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

## What changed in this profile?

`alpi diff [--since 24h]` summarises profile-level activity since
the cutoff. mtime-driven, side-effect free; safe to run from cron
or a remote SSH session.

```bash
alpi diff                       # last 24h, default profile
alpi diff --since 7d            # weekly digest
alpi diff --since 2026-04-25    # since an explicit date
alpi -p personal diff --since 1h
alpi diff --since 7d --json     # machine-readable for scripts / dashboards
```

What it covers: memory edits (which file, when), local + gateway
sessions (count, turns, tool calls, cost, tokens, agent time),
mention threads touched, skill installs, peer-list mutations,
fired schedule jobs grouped by job id, and today's budget usage.

The same primitive is exposed in the TUI as `/diff [since]`
(default `24h`). One implementation — three surfaces (CLI, TUI,
host-plane verb when the desktop catches up).

Use cases:
- **Came back from holiday** — `alpi diff --since 7d` answers
  "what did my service do?".
- **Pre-backup smoke check** — `alpi diff --since <last-backup>`
  before `alpi backup` so you know what's about to be archived.
- **Cron snapshot** — `alpi diff --since 24h --json` piped into
  whatever dashboard collects per-profile activity.

## Disaster recovery checklist

You've lost a machine. Here's the order of operations to restore.

1. Reinstall alpi on the replacement machine (`uv tool install`).
2. Restore `~/.alpi/` from backup.
3. Run `alpi setup` once — it auto-installs the daemon if the
   plist / unit isn't already in place. (Or manually:
   `alpi daemon install`.)
4. `alpi doctor` — the Daemon row should read "running".
5. If your ALP identity is intact (backup included
   `alp/secrets/`), your peers still reach you. If you had to
   regenerate, see **ALP identity rotation** above.
6. `alpi` → test a turn. Send a message from Telegram; verify the
   reply lands.
7. Tail `service.log` and `agent.log` for 24 h to confirm every
   profile's gateway and scheduler are firing normally.

If you had no backup: you've lost the profile. Start from
quickstart, re-pair your ALP peers, re-install your skills. The
conversation history is gone. This is by design — alpi doesn't
phone home, so there's no "recover from the cloud" path.

## Common failure modes

**"Listener not running"** when calling `@peer …`. The peer's
daemon is down or its `alp` service is disabled for that profile.
Check `alpi daemon status` on the peer's machine and the
`service.alp` flag in the peer profile's `config.yaml`.

**Two daemons running simultaneously.** `ps aux | grep "alpi ("`
shows more than one `alpi (daemon, …)` entry. Usually after a
failed reinstall, or after running `alpi daemon start` foreground
while the supervisor was already running. Fix:
`pkill -f "alpi (daemon" && alpi daemon restart`.

**Message didn't save to memory.** Check the session file:
`jq '.turns[-1].tools' ~/.alpi/sessions/*.json` — if no `memory`
tool call landed, the model decided the signal wasn't worth a
write. Inline-learning is LLM-driven; if you want a guaranteed
capture, tell alpi explicitly ("remember that…").

**Telegram is silent.** `alpi logs --source service -n 100`.
Expected to see inbound lines with `[telegram]` prefix. If
nothing: bot token revoked, offset corrupted, or the daemon
crashed. `alpi doctor` flags credential problems explicitly.

**Stale binary.** After `uv tool install --reinstall`, the
daemon still runs the old code. `alpi doctor` warns; fix with
`alpi daemon restart`.
