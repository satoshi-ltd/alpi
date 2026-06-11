# Profiles

A **profile** is alpi's core isolation primitive: one directory on
disk, one identity, one set of credentials, one memory, one set of
skills, one peer list, one model choice. Everything else — the TUI,
the gateway, ALP, the scheduler — operates *inside* a profile.

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
| `config.yaml` | ✓ | Model, fallbacks, tool limits, gateway config, MCP servers. |
| `.env` | ✓ | API keys. A leak in one profile doesn't touch the other. |
| `memories/` (USER.md, MEMORY.md, AGENT.md) | ✓ | Your identity and what alpi remembers. |
| `sessions/<id>.json` | ✓ | Local human chat log (TUI / desktop / manual `chat --once`). |
| `mentions/<sender>.json` | ✓ | Per-sender `@`-mention threads (capped at 20 turns). Receiving side only. |
| `gateway/sessions/<id>.json` | ✓ | Telegram / email / webhook chat logs. Hidden from TUI/desktop listings on purpose. |
| `gateway/sessions/_map.json` | ✓ | `chat_id → session_id` pointer for per-chat threading. |
| `skills/` | ✓ | Installed skills (live under this profile's allowlist). |
| `alp/` (peers.yaml, socket, keypair) | ✓ | ALP identity + pinned peers. Two profiles on the same machine are two distinct peers. |
| `schedule/jobs.json` | ✓ | Cron + one-shot jobs. Scheduled runs use `chat --once --no-save` and do not create chat sessions. Jobs flagged `no_agent: true` exec `prompt` as a `python [flags] <skill_script>` invocation directly, bypassing the LLM (allowlist restricts the script to `skills/<category>/<name>/scripts/`). |
| `logs/` | ✓ | `gateway.log`, `schedule.log`, `alp.log`, `agent.log`, `approval.log`, plus JSONL telemetry `compaction.jsonl` and `runs.jsonl` (run ledger, surfaced by `alpi digest`). |
| `logs/ledger.json` | ✓ | Daily spending ledger — the profile's USD cap is enforced from here across every turn (interactive, gateway, scheduled, sub-agent, inbound ALP). Resets at UTC midnight. |
| `cache/` (tts, stt, inbound voice) | ✓ | Audio cache. |

Not isolated (shared globally by design):

- The `alpi` binary itself (`~/.local/bin/alpi`).
- Whisper model downloads (`~/.cache/huggingface/`).
- Chromium for the `browser` tool (Playwright's own cache).
- The user's shell, git config, workspace contents.

## Creating and removing profiles

```bash
alpi profile create work       # bootstraps the tree with defaults
alpi profile list              # shows all profiles, active one flagged
alpi profile remove work       # deletes after safety checks + confirm
```

`profile remove` archives the profile home under
`~/.alpi/.trash/<name>-<timestamp>/`. There's no per-profile
service to uninstall — the daemon is per-machine and picks up the
removal on its next restart. **`alpi -p <name> setup → Delete
profile`** is the same operation from the wizard.

Every command in alpi's CLI accepts `-p <name>` to scope to a
profile:

```bash
alpi -p work                   # launch TUI for the work profile
alpi -p work setup             # configure the work profile (services + gateways)
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
- **Different gateway identity.** Work uses a Telegram bot that
  only talks to work contacts; personal uses another.
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
sessions, rotated logs, schedule output, and RAG store freelist
bloat on demand.

On CPU / memory: a profile not in active use costs *nothing*.
Active surfaces collapse into two processes: the TUI instance
(when you launch it) and the alpi daemon — one process per
machine, hosting every profile's gateway / scheduler / ALP
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

Both profiles' gateways run simultaneously inside the single
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
~/.alpi/profiles/cron/        → runs scheduled jobs, no gateway
```

Each profile can have a completely different model, a different
sandbox posture, a different memory, and expose a different
capability surface in ALP. This is how a private network of alpis gets
built: granular identity per role, ALP as the coordination layer.
