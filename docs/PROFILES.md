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
| `sessions/<id>.json` | ✓ | Local human chat log (TUI / desktop / manual `chat --once`), each with a `_events_<id>.jsonl` sidecar used to replay a turn after a dropped connection. |
| `mentions/<sender>.json` | ✓ | Per-sender `@`-mention threads (capped at 20 turns). Receiving side only. |
| `skills/` | ✓ | Installed skills (live under this profile's allowlist). |
| `recipes/` | ✓ | Saved workgroup recipes owned by this profile when it acts as hub. The YAML filename stem is the recipe id. |
| `alp/` | ✓ | ALP identity and pinned peers (`peers.yaml`, socket, keypair under `alp/secrets/` — **not** under the profile's `secrets/`), plus the workgroups this profile hubs: transcripts, files and member state under `alp/workgroups/<id>/`. Two profiles on the same machine are two distinct peers. |
| `host/attachments/tmp/` | ✓ | Staged chat-attachment uploads from the paired apps. The rest of `host/` is root-only (see below). |
| `run/bg/` | ✓ | Output capture and metadata for background terminal jobs. |
| `runs/<run_id>.jsonl` | ✓ | Bounded, redacted durable event journal for each engine turn; surfaced by `alpi runs`, `/runs`, `host.runs.list` and `host.run.read`. |
| `schedule/jobs.json` | ✓ | Cron + one-shot jobs. Scheduled runs never create chat sessions; a job flagged `no_agent: true` runs one of this profile's skill scripts directly, without the LLM. |
| `outputs/outputs.jsonl` | ✓ | Persistent inbox for proactive agent messages + schedule failures, capped at 500 rows. Surfaced by `host.outputs.*` to paired apps. |
| `out/` | ✓ | Files the agent produces for you and the apps serve back. Kept ~30 days, then offered by the cleanup wizard; excluded from `alpi backup`. |
| `knowledge.sqlite` | ✓ | Derived sqlite-vec indexes for workspace knowledge, session recall, and workgroup recall. |
| `logs/` | ✓ | `agent.log` (one line per engine turn, on every surface), `llm.log` (provider request breadcrumbs — the record of what a stalled turn was waiting on), `approval.log` (every non-safe `terminal` classification), plus `compaction.jsonl` and `runs.jsonl` telemetry read by `alpi digest`. The daemon's own `service.log` is root-only at `~/.alpi/logs/` — one per installation, and `alpi logs --source service` always reads it regardless of `-p`. |
| `logs/ledger.json` | ✓ | Daily spending ledger — the profile's USD cap is enforced from here across every turn (interactive, scheduled, sub-agent, inbound ALP). Resets at UTC midnight. |
| `cache/` | ✓ | Audio cache — synthesised speech and inbound voice notes. Speech-to-text model weights are shared, not per profile. |

**Permissions.** The directories alpi creates at bootstrap are mode `0700`
and the credential files it writes are `0600`. `alpi audit` then checks a
fixed list for any group or other bit — the profile home, `.env`,
`config.yaml`, `peers.yaml`, `alp/secrets/` and the ALP private key,
`memories/`, `sessions/`, `skills/`, `logs/`, `host/`, `mentions/`,
`outputs/`, `schedule/output/` — and the fix is `chmod 700` for directories,
`chmod 600` for files. Paths created lazily on first use (caches, `run/bg/`,
staged attachments) inherit your umask and are not on that list, so a
hardened setup should check them too.

**Names.** A profile name starts with a letter or digit and may contain
letters, digits, `.`, `_` and `-`; anything else (`../escape`, `a/b`, a
leading dot, any name containing `..`) is rejected before any path is
touched, as are the reserved names `default` and `alpi`. `alpi -p <name>`
bootstraps a missing profile on first use; `alpi profile create <name>` does
it explicitly. Quote names that contain shell-glob characters.

Not isolated (shared globally by design):

- The `alpi` binary itself (`~/.local/bin/alpi`).
- Whisper model downloads (`~/.cache/huggingface/`) and the embedding
  models and update-check cache under `~/.alpi/cache/`.
- Chromium for the `browser` tool (Playwright's own cache).
- The user's shell, git config, workspace contents.
- **Host-plane root state.** The control-plane socket, `connections.yaml` (connection identities and hashed device tokens), the host event stream and the device id live once under `~/.alpi/host/`. Paired apps always talk to the root and reach sibling profiles through the `profile` parameter on each call.

## Creating and removing profiles

```bash
alpi profile create work       # bootstraps the tree with defaults
alpi profile list              # shows all profiles, active one flagged
alpi profile remove work       # archives to .trash after confirmation
```

`profile remove` archives the home under `~/.alpi/.trash/<name>-<timestamp>/`.
There is no per-profile service to uninstall — the daemon is per-machine and
picks up the removal on its next restart. `alpi -p <name> setup → Delete
profile` is the same operation from the wizard.

Every CLI command accepts `-p <name>` to scope to a profile:

```bash
alpi -p work                   # launch the TUI for the work profile
alpi -p work setup             # configure the work profile
alpi -p work peers list        # list the peers pinned by the work profile
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
- `host/connections.yaml` or any other host pairing state.
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

### Containers

Keep the same split in Docker or Kubernetes: the alpi home on a persistent
volume, the profile-source checkout mounted read-only, secrets injected by
the runtime rather than committed, and an entrypoint or init step that syncs
the allowlisted files into the live profile before `alpi daemon` starts. On
Kubernetes that is a `StatefulSet` with `replicas: 1` and a PVC at the alpi
home; annotate the pod with the profile-source commit so runtime state traces
back to reviewed source. Never make the volume itself the Git repository —
the daemon writes sessions, ledgers, sockets and caches there while it runs.
Container shapes and ports are in [DEPLOYMENTS.md](DEPLOYMENTS.md).

### Backups

Git does not replace `alpi backup`. Git captures desired profile source;
backup captures operational recovery: ALP private identity, device
pairings, OAuth tokens, sessions, outputs, ledgers, and other runtime
state.

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

On disk: a fresh profile is about a kilobyte (a seed `config.yaml`, an
`AGENT.md`, empty memory files and an empty directory tree). After a few
weeks of use, expect 5–50 MB depending on voice-cache and session-history
retention. The TUI
top bar surfaces the live size next to the profile name; the
cleanup wizard (`alpi setup → Cleanup`) reclaims audio cache, old
sessions, rotated logs, schedule output, and knowledge index freelist
bloat on demand.

On CPU / memory: adding a profile does not add a process. Everything
collapses into the TUI instance you launch and the one alpi daemon per
machine, which supervises each profile's scheduler, ALP listener, workgroup
poller and preempt watcher as tasks named `<profile>/<service>`; the host
plane exists once, on `default`. An idle profile is close to free but not
free — its ALP listener holds a socket and its poller wakes on a timer — so
dozens of profiles on one machine is a real cost, while a handful is not.
The daemon is auto-installed on the first `alpi setup` and managed from
`alpi setup → Services → Daemon`.

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
