# Profiles answer pack

## Answer directly

- Default profile: `~/.alpi/`. Named profile: `~/.alpi/profiles/<name>/`.
- A profile is one isolated alpi identity + data dir (config, `.env`, memory, skills, sessions, gateway/scheduler state, logs, ALP identity, budget ledger).
- Create a new profile for a separate identity/memory/credentials/ALP-trust/budget boundary. Use workspace (not a profile) when identity and memory can be shared across projects.

## Active profile resolution (first match wins)

1. `ALPI_HOME` env var — absolute override, bypasses everything.
2. `-p <name>` / `--profile <name>` CLI flag (propagates as `ALPI_PROFILE` to every subprocess).
3. `ALPI_PROFILE` env var.
4. Default `~/.alpi/`.

## Home layout (all isolated per profile)

| Path | Purpose |
|---|---|
| `config.yaml` | Model, fallbacks, tool limits, gateway, MCP servers, scheduler, workspace, budget. |
| `.env` | Provider keys / static secrets. A leak in one profile doesn't touch another. |
| `memory/` (USER.md, MEMORY.md, AGENT.md) | Persistent user/project memory + identity. |
| `sessions/<id>.json` | Local human chat log only (TUI / desktop / `chat --once`). Gateway, schedule, workgroup, system-prefixed turns stay out of resume/history. |
| `mentions/<sender>.json` | Per-sender `@`-mention threads, capped 20 turns, receiving side only. |
| `gateway/sessions/<id>.json` | Telegram / email / webhook logs. Hidden from TUI/desktop listings on purpose. |
| `gateway/sessions/_map.json` | `chat_id → session_id` pointer for per-chat threading. |
| `skills/` | Installed/user skills, under this profile's allowlist. |
| `rag/store.sqlite` | Local RAG index over the workspace (sqlite-vec). |
| `alp/` (peers.yaml, socket, keypair) | ALP identity + pinned peers; two profiles = two distinct peers. |
| `schedule/jobs.json` | Cron + one-shot jobs. Runs use `chat --once --no-save` (no session). Jobs with `no_agent: true` exec `prompt` as `python [flags] <skill_script>` directly, bypassing the LLM (allowlist restricts to `skills/<category>/<name>/scripts/`). |
| `logs/` | `gateway.log`, `schedule.log`, `alp.log`, `agent.log`, `approval.log`. |
| `logs/ledger.json` | Daily USD/token spend cap, enforced across every turn (interactive, gateway, scheduled, sub-agent, inbound ALP). Resets at UTC midnight. |
| `cache/` (tts, stt, inbound voice) | Audio cache. |
| `run/` | Runtime sockets / PIDs. |

Shared globally (NOT isolated): the `alpi` binary (`~/.local/bin/alpi`), Whisper downloads (`~/.cache/huggingface/`), Playwright Chromium, the user's shell / git config / workspace contents.

## Commands

```bash
alpi profile create work   # bootstrap tree with defaults
alpi profile list          # all profiles + model, disk size, active marker
alpi profile remove work   # archives home to ~/.alpi/.trash/<name>-<timestamp>/ after confirm
alpi -p work               # launch TUI for the work profile
alpi -p work setup         # configure (services + gateways); setup → Delete profile = remove
alpi -p work peers list    # peers pinned by the work profile
```

Every CLI command accepts `-p <name>`. No per-profile service to uninstall — the daemon is per-machine and picks up a removal on next restart.

## Common questions

- "Where is my data?" → see layout table; default `~/.alpi/`, named `~/.alpi/profiles/<name>/`.
- "Separate work/personal?" → two profiles (e.g. `~/.alpi/` personal + `~/.alpi/profiles/work/`); both gateways run in the one machine-wide daemon and can be ALP peers of each other (`@work ...`).
- "Different model only?" → NOT a new profile; use `/model` or `setup → Model` in the same profile (keeps memory/skills). Scratch chat → `/new`.

## When to create a profile (axis = identity + stakes)

- Different cost/compliance boundary — per-profile `.env` + `config.yaml`; `budget.daily_usd` (paid) **or** `daily_tokens` (local models, mutually exclusive) caps spend independently.
- Different memory — MEMORY.md is profile-scoped; work context shouldn't bleed into personal.
- Different gateway identity — e.g. separate Telegram bots.
- Different ALP role — a peer others talk to (`home-server`, `laptop`) with its own pubkey + peer list.
- Service identities: e.g. `assistant` (daily driver), `researcher` (read-only), `cron` (scheduled, no gateway) — each its own model/sandbox/memory/ALP surface.
- Per-employee org: `~/.alpi/profiles/<user>/` each with own identity/key/memory; IT seeds `peers.yaml` with shared-service pubkeys. See DEPLOYMENTS.md.

## ALP identity

- Each profile has its own Ed25519 keypair at `{home}/alp/secrets/alp_key.{pem,pub}`; the base64 pubkey is the profile's cryptographic identity that peers pin in `peers.yaml`.
- Two profiles on one machine are distinct peers (distinct pubkeys + socket paths), talking over ALP.1 just as a remote profile would over ALP.2.
- Rotation = outage: delete `alp/secrets/`, next `alpi daemon restart` regenerates the pair; every peer that pinned the old key must update. Treat like rotating an SSH key.

## Cost & service rules

- Disk: fresh ~10 KB; after weeks 5–50 MB (voice cache + session retention). TUI top bar shows live size; `setup → Cleanup` reclaims audio cache, old sessions, rotated logs, schedule output, RAG freelist bloat.
- CPU/mem: an idle profile costs nothing. One alpi daemon per machine hosts every profile's gateway/scheduler/ALP/workgroups poller as supervised `<profile>/<service>` asyncio tasks. Auto-installed on first `alpi setup`, managed from `setup → Services → Daemon`.
- Wrong-identity gateway/scheduler symptom → check which profile's service is running.

## Related topics

- Config and `.env`: `config`
- Daemon lifecycle: `operations`
- ALP identity: `alp`
- Skills per profile: `skills`
