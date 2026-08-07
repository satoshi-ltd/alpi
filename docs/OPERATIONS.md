# Operations

Runbook for running alpi seriously — at home or inside an
organisation. Covers logs, services, upgrades, backup + restore,
identity rotation, and monitoring.

If you just installed alpi and want to chat, you don't need this
doc yet: [QUICKSTART.md](../QUICKSTART.md) covers everything. Come
back here when things break, or when you need to move a profile,
or when it's time to ship a new version.

## Logs — the files you'll actually read

Every profile writes to `{home}/logs/` with the same format so
`alpi logs` can merge them:

```
~/.alpi/logs/                     ← default profile
~/.alpi/profiles/<name>/logs/     ← named profile
```

Rotating text logs cap at **1 MB**; `.log.1` holds the previous
generation. JSONL telemetry feeds are append-only, read with `jq` (or
`alpi digest`) — `compaction.jsonl` is unbounded; `runs.jsonl` is capped
and rolling.

| File | Scope | Format | What it answers | Who writes it |
|---|---|---|---|---|
| `service.log` | **daemon-wide; ONE file at `~/.alpi/logs/service.log`, never duplicated per profile** | rotated text | Did the daemon start? Which services came up for which profile? Did a peer hit an ALP listener? Did a cron job fire? | the daemon supervisor + every per-profile service that logs through the root logger |
| `agent.log` | per profile | rotated text | What has the agent *been doing*? One line per **engine turn on every surface** (TUI, schedule, workgroup post, inbound ALP, research / delegate sub-agents): session id, elapsed, tools called, reply length, cost, user prompt preview. Cross-session grep index. | the engine (every turn on every surface) |
| `approval.log` | per profile | rotated text | Security audit of every non-safe shell command the LLM tried to run: caution (pending / once / session / always / deny) or dangerous (always denied). | the approval system |
| `compaction.jsonl` | per profile | append-only JSONL | Did auto-compact run this turn? Tokens before/after, summarized-message count, tool-truncation count, manual vs auto, `fired` (true when the LLM summarized; false when only oversized tool outputs were truncated). Use it as the evidence source before changing compaction/memory constants. | the engine (one line whenever compaction *or* tool truncation ran) |
| `runs.jsonl` | per profile | capped rolling JSONL | What ran and where it stopped: one record per long-running turn (agent, schedule, workgroup, terminal) — outcome, exit code, timeout reason, pid, backend, last tool, and a secret-redacted output tail. Surfaced by `alpi digest`. | the engine, scheduler, and terminal tool (one line per finished run) |
| `ledger.json` | per profile | JSON | Daily USD spend ledger; live counters for the daily cap + 30-day per-day history. Not a log; never cleaned by `Subsystem logs`. | every turn that records cost |

**Tail one or all:**

```bash
alpi logs                          # merged tail of every source under the active profile
alpi logs --source service         # always reads ~/.alpi/logs/service.log
                                   #   (root-scope; -p <name> doesn't change the source)
alpi logs --source agent -n 500    # last 500 lines of the active profile's agent.log
alpi -p mira logs --source agent   # mira's agent.log under ~/.alpi/profiles/mira/logs/
                                   #   NOTE: `-p` belongs to the root `alpi` command,
                                   #   not to `logs` — it must come before the subcommand
alpi logs -f                       # follow mode (poll every 1s)
```

`compaction.jsonl` is read with `jq`, not `alpi logs`:

```bash
jq -r '[.ts, .session_id[0:8], .trigger, .tokens_before, .tokens_after] | @tsv' \
  ~/.alpi/logs/compaction.jsonl
```

Per-record fields: `ts`, `trigger` (`auto`|`manual`), `session_id`,
`model`, `ctx_window`, `fired`, `tokens_before`, `tokens_after`,
`summarized_messages`, `tool_truncated`.

The `agent.log` + `approval.log` pair is your **audit trail**.
Anyone who needs to answer "what did alpi do this week?" or "did
the agent run anything risky?" should be grepping those two
files. `compaction.jsonl` answers "did the context window pressure
get tight this week?" and "are my trigger ratios right for this
model?".

## Daemon — one process per machine, every profile inside

alpi runs a single `com.alpi.daemon` process (launchd plist on
macOS, systemd-user unit on Linux) that supervises every profile
under `~/.alpi/` — default plus each `profiles/<name>/`. Each
profile gets its own per-service supervised tasks named
`<profile>/<service>` (e.g. `doc/schedule`, `builder/alp`); a crash
in one profile's service leaves siblings untouched.

| What it does | Lifecycle | Install / config |
|---|---|---|
| Boots isolated tasks on one asyncio loop: scheduler tick, ALP socket (Unix + optional TCP/Noise_XK), workgroups poller, and the default host plane. These are fixed daemon capabilities; feature-level state lives with jobs, peers, workgroups, and connections. | `alpi daemon start\|stop\|restart\|status` | auto-installed on first `alpi setup`; manage from `alpi setup → Services → Daemon` (default profile only) |

There's exactly one daemon per machine, one plist / unit. Adding
a new profile just creates a directory under `~/.alpi/profiles/`;
the daemon picks it up on its next restart. Operational verbs
that aren't lifecycle survive on their own:

**File-descriptor limit.** One daemon hosts every profile's services
(schedule / alp / workgroups / host), so a machine with many
profiles holds a lot of sockets at once. The launchd/systemd unit — and the
Docker compose `ulimits` — raise the FD ceiling to **8192**; a low platform
default (256 on macOS launchd) is exhausted under load (symptom:
`OSError: [Errno 24] Too many open files` in `service.log`, operations failing
intermittently). The limit lives in the service definition, so **`alpi daemon
install` (re-run after upgrading) — or recreating the container — applies
it**; `launchctl limit maxfiles` shows the old default but the unit's own
`SoftResourceLimits` overrides it for the daemon process.

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

**CVEs.** `alpi audit` checks installed Python packages against OSV with exact
versions. Use `alpi audit --offline` on machines that must not make network
calls; use plain `alpi audit` before releases or after dependency changes.
Filter findings by surface: alpi uses the **SDK**, not the **Proxy** server.
CVEs scoped to LiteLLM Proxy (e.g. CVE-2026-30623, MCP stdio RCE) don't apply.
SDK CVEs do — bump promptly.

**Alternatives evaluated.** Raw SDKs (rejected: maintenance cost,
see above). [chuk-llm](https://github.com/chrishayuk/chuk-llm) on
the radar but immature for our provider matrix at audit time.

## Backup + restore

`alpi backup` writes a single passphrase-encrypted file of the
whole alpi home (`~/.alpi/`) — every profile in one shot;
`alpi restore <file>` reverses it. Zero-knowledge — the passphrase
derives the key locally and never leaves the machine. Lose the
passphrase and the archive is unrecoverable.

```bash
alpi backup                                # ./alpi.YYYY-MM-DD.alpi-backup
alpi backup --out ~/vault/alpi.alpi-backup
alpi restore ~/vault/alpi.alpi-backup      # into ~/.alpi/
alpi restore alpi.alpi-backup --force      # overwrite a non-empty home
```

**What's in the backup.** The entire `~/.alpi/` tree: default
profile (memories, sessions, skills with `state/` SQLite +
`secrets/`), every named profile under `profiles/<name>/`,
`config.yaml`, `.env`, ALP identity (`alp/secrets/alp_key.{pem,pub}`),
peers, and host state. Excluded recursively at every depth:
`cache/`, `logs/`, `.trash/`, sockets (`*.sock`), PIDs (`*.pid`).

**Crypto.** Scrypt KDF (n=2¹⁷, r=8, p=1) → ChaCha20-Poly1305 over
a gzipped tar. Same primitives as `age` with a passphrase
recipient. The header (KDF params, salt, nonce, scope, timestamp,
file count) is bound as AAD, so any tamper flips the AEAD tag with
the same error a wrong passphrase produces.

**Scripting.** Both commands accept `--passphrase-stdin` to read
the passphrase from stdin without a prompt. Pair with a password
manager or systemd credential — never embed it in the cron line:

```bash
pass show alpi/backup | alpi backup --passphrase-stdin --out /backup/alpi.$(date +%F).alpi-backup
```

After restoring on a new machine, run `alpi doctor` — it surfaces
peers whose counterpart rotated their key since the backup, and
any missing optional dependency the restored skills declare.

Backups are operational snapshots. They are not a review workflow for
profile changes. For Git-based profile source, promotion, and secrets
boundaries, see [Profiles → Versioning](PROFILES.md#versioning).

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
- **Security posture.** `alpi audit --offline` in cron gives a local-only
  posture scan of every profile: secret file permissions, public binds,
  disabled hardening, and uncapped budgets. Run `alpi audit` manually when
  network is allowed to include OSV CVEs. Its exit code is non-zero only on
  `fail` findings; warnings are for review.
- **Log tail error rate.** `grep ERROR ~/.alpi/logs/*.log | wc -l`
  over a window — spike = misconfig, broken credentials, LLM API
  outage.
- **Cost ceiling.** Set `budget.daily_usd` in the profile's
  `config.yaml` (or leave it unset for unlimited) —
  see [CONFIG.md → Budget](CONFIG.md#budget). The ledger at
  `~/.alpi/<profile>/logs/ledger.json` is the in-process gate;
  every interactive turn, scheduled job, sub-agent
  spawn, and inbound ALP call admits against it before running and
  records its actual spend after. The same file keeps a 30-day
  `history` map of per-day totals (usd + input/output tokens) — the
  authoritative spend record, including non-token costs like image
  generation that session files never see; `host.usage.daily`
  (admin-only) serves the last 14 days of it to clients, plus a `total30`
  aggregate over the full 30-day retention.
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

What it covers: memory edits (which file, when), local sessions
(count, turns, tool calls, cost, tokens, agent time),
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

## Operator evidence digest

`alpi digest [--since 7d]` answers a different question from
`alpi diff`: not "what changed?", but "what parts of this profile need
operator attention?" It is a read-only aggregation over state Alpi
already writes:

```bash
alpi digest                 # last 7 days, human output
alpi digest --since 24h
alpi digest --since 30m
alpi digest --json          # machine-readable report
alpi -p work digest --json
```

The report covers unavailable tools, skill usage
telemetry, memory promotion backlog / pressure, compaction rate over the
window, and a **Runs** section folding the run ledger (`runs.jsonl`) — totals
by kind/outcome, recent failures and timeouts, and the slowest recent runs. It
does not run an LLM, write new state, make recommendations, or send telemetry
anywhere.

Use it before roadmap or ops decisions: if a proposed improvement has no
evidence in the digest, it probably belongs in "listening first" until a
real profile starts showing the pain.

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
6. `alpi` → test a turn; verify the reply lands.
7. Tail `service.log` and `agent.log` for 24 h to confirm every
   profile's scheduler and ALP listener are firing normally.

If you had no backup: you've lost the profile. Start from
quickstart, re-pair your ALP peers, re-install your skills. The
conversation history is gone. This is by design — alpi doesn't
phone home, so there's no "recover from the cloud" path.

## Common failure modes

**"Listener not running"** when calling `@peer …`. The peer's
daemon is down, its address is unreachable, or its ALP listener failed.
Check `alpi daemon status`, `alpi doctor`, and `service.log` on the
peer's machine.

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

**The `email` tool fails.** `alpi email probe <id>` exercises the live
login for that account. A failure means revoked or wrong credentials
in `<profile>/.env`, or an expired Gmail OAuth token. `alpi doctor`
flags credential problems explicitly.

**Stale binary.** After `uv tool install --reinstall`, the
daemon still runs the old code. `alpi doctor` warns; fix with
`alpi daemon restart`.
