# Profiles

A **profile** is alpi's core isolation primitive: one directory on
disk, one identity, one set of credentials, one memory, one set of
skills, one peer list, one model choice. Everything else — the TUI,
the apps, ALP, the scheduler — operates *inside* a profile.

If you only ever use alpi for yourself on one machine, the default
profile is enough. Profiles become important as soon as identity,
cost, memory, trust, or unattended execution need a boundary: personal
vs work, laptop vs home server, daily driver vs cron, or one shared
service per team.

## Where a profile lives

- **Default profile:** `~/.alpi/`
- **Named profile:** `~/.alpi/profiles/<name>/`

The active profile is resolved in this order:

1. `ALPI_HOME` env var — absolute override, bypasses everything.
2. `-p <name>` / `--profile <name>` CLI flag (propagates via
   `ALPI_PROFILE` env var to every subprocess).
3. `ALPI_PROFILE` env var.
4. Default (`~/.alpi/`).

`alpi profile list` shows all profiles with their model, size on
disk, and active marker.

## What's isolated per profile

Everything that represents state, identity, or cost:

| Under `{home}/` | Isolated per profile | Why it matters |
|---|---|---|
| `config.yaml` | ✓ | Model, fallbacks, tool limits, MCP servers. |
| `.env` | ✓ | API keys. A leak in one profile doesn't touch the other. |
| `secrets/` | ✓ | Per-profile non-ALP credential files (OAuth tokens, Gmail tokens, etc.). Created `0o700` on bootstrap. The ALP keypair lives separately at `alp/secrets/alp_key.{pem,pub}`. |
| `memories/` (USER.md, MEMORY.md, AGENT.md) | ✓ | Your identity and what alpi remembers. |
| `sessions/<id>.json` | ✓ | Local human chat log (TUI / desktop / manual `chat --once`). |
| `mentions/<sender>.json` | ✓ | Per-sender `@`-mention threads (capped at 20 turns). Receiving side only. |
| `skills/` | ✓ | Installed skills (live under this profile's allowlist). |
| `recipes/` | ✓ | Saved workgroup recipes owned by this profile when it acts as hub. The YAML filename stem is the recipe id. |
| `alp/` (peers.yaml, socket, keypair under `alp/secrets/`) | ✓ | ALP identity + pinned peers. Two profiles on the same machine are two distinct peers. The ALP private key lives here, NOT under `secrets/`. |
| `host/attachments/tmp/` | ✓ | Staged chat-attachment uploads from the paired apps. Per profile — the rest of `host/` (`host.sock`, `connections.yaml`, `events.jsonl`, `device_id`) is root-only (see below). |
| `run/bg/` | ✓ | Background-terminal state — one combined `alpi-bg-*.log` (stdout+stderr capture) and one `<pid>.meta` file (key=value pairs: `log=…`, `started=…`) per job spawned with `terminal(action="background")`. |
| `schedule/jobs.json` | ✓ | Cron + one-shot jobs. Scheduled runs use `chat --once --no-save` and do not create chat sessions. Jobs flagged `no_agent: true` exec `prompt` as a `python [flags] <skill_script>` invocation directly, bypassing the LLM (allowlist restricts the script to `skills/<category>/<name>/scripts/`). |
| `outputs/outputs.jsonl` | ✓ | Persistent inbox for proactive agent messages + schedule failures, capped at 500 rows. Surfaced by `host.outputs.*` to paired apps. |
| `knowledge.sqlite` | ✓ | Derived sqlite-vec indexes for workspace knowledge, session recall, and workgroup recall. |
| `logs/` | ✓ | `agent.log` (one line per engine turn on every surface — TUI, schedule, workgroup, inbound ALP, research / delegate sub-agents — written by `engine.py::run_turn`), `llm.log` (provider request start / first delta / stream end-or-error breadcrumbs written by `llm.py` — the attribution record for idle-killed turns) and `approval.log` (one line per non-SAFE `terminal` classification, written by `tools/_approval.py`), plus JSONL telemetry `compaction.jsonl` and `runs.jsonl` (run ledger, surfaced by `alpi digest`). The daemon's root log lives outside the per-profile tree at `~/.alpi/logs/service.log` — there is ONE per installation, not one per profile, and `alpi logs --source service` always reads the root file regardless of `-p`. `alpi logs --source` still accepts `schedule` as a filter value for any standalone or legacy file on disk. |
| `logs/ledger.json` | ✓ | Daily spending ledger — the profile's USD cap is enforced from here across every turn (interactive, scheduled, sub-agent, inbound ALP). Resets at UTC midnight. |
| `cache/` (tts, stt, inbound voice) | ✓ | Audio cache. |

**Eager vs lazy.** `home.ensure_home()` creates 10 subdirs eagerly with `0o700` permissions on first bootstrap: `memories/`, `secrets/`, `sessions/`, `skills/`, `recipes/`, `schedule/output/`, `logs/`, `host/`, `mentions/`, `outputs/`. The rest (`alp/`, `cache/`, `run/bg/`, `host/attachments/`) and `knowledge.sqlite` are created lazily on first use. `alpi audit` walks a fixed sensitive-path list and flags any group/other bits set (`st_mode & 0o077`); the fix is `chmod 700` for directories and `chmod 600` for files. The list: the profile home itself, `.env`, the ALP private key (`alp/secrets/alp_key.pem`), `alp/secrets/` (the ALP keypair directory — **not** the profile-level OAuth `secrets/`, which is not audited today), `config.yaml`, `peers.yaml`, `memories/`, `sessions/`, `skills/`, `schedule/output/`, `logs/`, `host/`, `mentions/`, `outputs/`. Lazily-created paths outside this list (`alp/` itself, `cache/`, `run/bg/`, `host/attachments/`) and the profile-level `secrets/` OAuth folder are not audited today.

**Profile creation.** `alpi -p <name>` auto-bootstraps any not-yet-existing profile on first use; `alpi profile create <name>` is the explicit pre-bootstrap. Both paths go through the same central validator (`home.validate_profile_name`): the name must match `^[A-Za-z0-9][A-Za-z0-9._-]*$`, so `-p ../escape`, `-p .hidden`, `-p a/b`, `-p ..`, and any name containing `..` are rejected with `InvalidProfileName` before the path is joined. `-p ""` is a no-op — empty falls through to the default profile (`~/.alpi/`), it does **not** resolve to `~/.alpi/profiles/`. Quote names containing zsh-glob characters (`*`, `?`, `[`); they're rejected by validation anyway but the shell expands them first.

Not isolated (shared globally by design):

- The `alpi` binary itself (`~/.local/bin/alpi`).
- Whisper model downloads (`~/.cache/huggingface/`).
- Chromium for the `browser` tool (Playwright's own cache).
- The user's shell, git config, workspace contents.
- **Host-plane root state.** `~/.alpi/host/host.sock` (control-plane socket), `~/.alpi/host/connections.yaml` (connection identities and device tokens), `~/.alpi/host/events.jsonl` (host event stream), and `~/.alpi/host/device_id` are root-only — ONE instance per installation, not duplicated per profile. The desktop / mobile client always pairs against the root and reaches sibling profiles via the `profile` parameter on each verb. Named profiles still get their own `host/attachments/tmp/` (uploaded chat attachments) — that IS per profile and appears in the table above.

## Creating and removing profiles

```bash
alpi profile create work       # bootstraps the tree with defaults
alpi profile list              # shows all profiles, active one flagged
alpi profile remove work       # deletes after safety checks + confirm
```

## Versioning

Treat `~/.alpi/` as the live runtime tree. It contains reviewable
profile intent, but also secrets, identity material, logs, sessions,
outputs, sockets, cache, and other state the daemon owns while it is
running.

### Source repository

The preferred workflow is a separate Git repository for profile source,
then an explicit sync into the live profile:

```text
~/git/alpi-profiles/
  profiles/
    support/
      config.yaml
      memories/
        AGENT.md
        USER.md
        MEMORY.md
      skills/
      schedule/
        jobs.json
      env.example
      README.md
```

```bash
rsync -a --delete \
  --include='config.yaml' \
  --include='memories/***' \
  --include='skills/***' \
  --include='schedule/' \
  --include='schedule/jobs.json' \
  --exclude='*' \
  ~/git/alpi-profiles/profiles/support/ \
  ~/.alpi/profiles/support/

alpi -p support doctor
```

This keeps Git diffs focused on intended behavior: model/config
choices, memory, skills, schedules, and profile notes. It avoids
reviewing transient runtime files and avoids accidentally pushing
secrets or private chat history.

Good candidates for Git:

- `config.yaml`, after checking for local-only hostnames, paths, and
  account ids.
- `memories/AGENT.md`, `memories/USER.md`, `memories/MEMORY.md`.
- `skills/**/SKILL.md`, scripts, references, tests, and non-secret
  assets.
- `recipes/*.yaml` when saved workgroup launch contracts are intended profile behavior.
- `schedule/jobs.json` when schedules are part of the intended profile
  behavior.
- `README.md` files that explain the profile purpose, owner, rollout
  notes, and workspace expectation.
- `env.example`, never the real `.env`.

Do not commit:

- `.env`, `secrets/`, `alp/secrets/`, or any skill `secrets/`.
- `host/connections.yaml`, `host/devices.yaml.migrated`, or host pairing state.
- `sessions/`, `mentions/`, `outputs/`, `logs/`, `cache/`, `run/`.
- `knowledge.sqlite` or other derived indexes.
- sockets, PID files, temporary attachments, skill `state/`.

### Local live home

Running `git init ~/.alpi` can be useful as a local inspection tool, but
it is not the recommended collaboration model. If you do it, use a
deny-by-default `.gitignore` and opt files back in:

```gitignore
*

!config.yaml
!memories/
!memories/AGENT.md
!memories/USER.md
!memories/MEMORY.md
!skills/
!skills/**/
!skills/**/SKILL.md
!skills/**/scripts/
!skills/**/scripts/**
!skills/**/references/
!skills/**/references/**
!skills/**/assets/
!skills/**/assets/**
!schedule/
!schedule/jobs.json
!README.md
!.gitignore
!env.example

.env
**/.env
secrets/
**/secrets/
**/state/
alp/secrets/
host/
sessions/
mentions/
outputs/
logs/
cache/
run/
knowledge.sqlite
*.sock
*.pid
```

Even with that ignore file, inspect `git status --ignored` and
`git diff --cached` before every commit. A future alpi release can add a
new runtime path, so a separate source repo plus allowlisted sync stays
safer than committing the live home.

### Docker

For containers, keep the same split:

- Mount the alpi home on a persistent volume, for example
  `/home/alpi/.alpi`.
- Mount or bake the profile-source repository separately and read-only,
  for example `/profile-source`.
- Inject `.env` and provider credentials through the container runtime,
  not through the profile-source repository.
- Run an entrypoint step that syncs allowlisted source files into the
  live profile before starting the daemon.

```bash
rsync -a --delete \
  --include='config.yaml' \
  --include='memories/***' \
  --include='skills/***' \
  --include='schedule/' \
  --include='schedule/jobs.json' \
  --exclude='*' \
  /profile-source/profiles/support/ \
  /home/alpi/.alpi/profiles/support/

exec alpi daemon
```

The container image should be disposable. The volume is operational
state. The Git repository is desired profile source.

### Kubernetes

Use a `StatefulSet` with `replicas: 1` unless the daemon explicitly
supports multi-writer operation for the same home. Mount a PVC at the
alpi home and treat it as live runtime state.

A typical layout:

- Init container, or a `git-sync`-style checkout step, checks out the
  profile-source repository into a read-only mount before the daemon
  starts.
- Init container copies allowlisted files from profile source into the
  PVC before the daemon starts.
- Secrets arrive through Kubernetes `Secret`, SOPS, External Secrets, or
  a vault integration, not through Git.
- ConfigMaps are fine for tiny deployment values, but profile trees with
  skills, references, and assets should stay in Git.
- Annotate the Pod or StatefulSet with the profile-source commit SHA so
  runtime state can be traced back to reviewed source.

```text
profile-source Git
  -> init checkout
  -> allowlisted sync
  -> PVC /home/alpi/.alpi
  -> alpi daemon
```

Do not make the PVC itself the Git repository for normal operation. The
daemon writes sessions, outputs, logs, ledgers, sockets, cache, and
other runtime files there while Kubernetes keeps the process alive.

### Backups

Git does not replace `alpi backup`. Git captures desired profile source;
backup captures operational recovery: ALP private identity, device
pairings, OAuth tokens, sessions, outputs, ledgers, and other runtime
state.

`profile remove` archives the profile home under
`~/.alpi/.trash/<name>-<timestamp>/`. There's no per-profile
service to uninstall — the daemon is per-machine and picks up the
removal on its next restart. **`alpi -p <name> setup → Delete
profile`** is the same operation from the wizard.

Every command in alpi's CLI accepts `-p <name>` to scope to a
profile:

```bash
alpi -p work                   # launch TUI for the work profile
alpi -p work setup             # configure the work profile (services + email)
alpi -p work peers list        # list peers pinned by the work profile
```

## Profile identity in ALP

Each profile has its own Ed25519 keypair at
`{home}/alp/secrets/alp_key.{pem,pub}`. The base64-encoded public
key is the **profile's cryptographic identity** on the ALP network
— it's what other profiles (on this or other machines) pin when
they add you to their `peers.yaml`.

Consequence: two profiles on the same machine (`default` and
`work`) are **not** the same peer. They have distinct pubkeys and
distinct socket paths. They can talk to each other over ALP.1
exactly like they'd talk to a profile on a different machine over
ALP.2.

Rotation is deliberate: delete `alp/secrets/` and the next
`alpi daemon restart` generates a fresh pair when the ALP
service boots for this profile. Every peer who pinned the old pubkey must update
their entry — rotation is an *outage* for the peer mesh, not a
silent operation. Treat it the way you'd treat rotating an SSH
key.

## When to create a new profile

The axis is **identity + stakes**, not "I want different chats".
Create a new profile when:

- **Different cost / compliance boundary.** Work charges tokens to
  the company API key; personal pays out of pocket. Per-profile
  `.env` + `config.yaml` prevents mixing, and a per-profile
  `budget.daily_usd` caps the spend independently — the work profile can
  be aggressive while the personal one runs on a $1/day leash.
- **Different memory.** You don't want work context (calendar,
  colleagues, ongoing projects) bleeding into a personal chat
  about weekend plans. MEMORY.md is profile-scoped.
- **Different email identity.** Work uses a work mailbox the
  `email` tool reads and sends from; personal uses another.
- **Different ALP role.** You want this alpi to be a peer that
  other machines/people talk to (`home-server`, `laptop`), with
  its own pubkey and peer list.

Not a reason:
- "I want to try a different model" — `/model` or
  `alpi setup → Model` does this in the same profile, keeping
  memory and skills.
- "I want a scratch session" — `/new` inside the TUI starts a
  fresh session in the same profile.

## Cost of a profile

On disk: a fresh profile is ~10 KB (config + memory seeds + empty
directory tree). After a few weeks of use, expect 5–50 MB
depending on voice-cache and session-history retention. The TUI
top bar surfaces the live size next to the profile name; the
cleanup wizard (`alpi setup → Cleanup`) reclaims audio cache, old
sessions, rotated logs, schedule output, and knowledge index freelist
bloat on demand.

On CPU / memory: a profile not in active use costs *nothing*.
Active surfaces collapse into two processes: the TUI instance
(when you launch it) and the alpi daemon — one process per
machine, hosting every profile's scheduler / ALP
listener / workgroups poller as supervised tasks named
`<profile>/<service>` on a single asyncio loop. The daemon is
auto-installed on the first `alpi setup` and managed from `alpi
setup → Services → Daemon` thereafter.

## Common patterns

### Personal + work on one machine

```
~/.alpi/                     → personal (default)
~/.alpi/profiles/work/       → work
```

Both profiles' services run simultaneously inside the single
machine-wide alpi daemon (one launchd plist / systemd unit
total). Both can be ALP peers of each other if you want
cross-profile handoffs (`@work ...` from personal).

### Per-employee in an organisation

```
~/.alpi/profiles/jane/
~/.alpi/profiles/raj/
~/.alpi/profiles/mia/
```

Each user's profile holds their own identity, their own API key
(or the org's shared one via `.env`), their own memory. Discovery
happens via `peers.yaml` at onboarding — the IT admin seeds each
new profile with the pinned pubkeys of the shared services
(`home-server`, `tools-bot`). See
[DEPLOYMENTS.md](DEPLOYMENTS.md) for the enterprise topology in
full.

### One machine, many service identities

```
~/.alpi/profiles/assistant/   → personal daily driver
~/.alpi/profiles/researcher/  → read-only research agent for the family
~/.alpi/profiles/cron/        → runs scheduled jobs, ALP off
```

Each profile can have a completely different model, a different
sandbox posture, a different memory, and expose a different
capability surface in ALP. This is how a private network of alpis gets
built: granular identity per role, ALP as the coordination layer.
