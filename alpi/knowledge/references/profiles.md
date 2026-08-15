# Profiles answer pack

## Answer directly

- Default profile: `~/.alpi/`. Named profile: `~/.alpi/profiles/<name>/`.
- A profile is one isolated alpi identity + data dir (config, `.env`, memory, skills, sessions, scheduler state, logs, ALP identity, budget ledger).
- Create a new profile for a separate identity/memory/credentials/ALP-trust/budget boundary. Use workspace (not a profile) when identity and memory can be shared across projects.
- Profile Git/versioning: recommend a separate profile-source repo + explicit allowlisted sync into `~/.alpi`; do not recommend `git init ~/.alpi` as the default. In containers/Kubernetes, use profile-source Git + init/entrypoint sync + persistent runtime volume/PVC + external secrets.

## Active profile resolution (first match wins)

1. `ALPI_HOME` env var — absolute override, bypasses everything.
2. `-p <name>` / `--profile <name>` CLI flag (propagates as `ALPI_PROFILE` to every subprocess).
3. `ALPI_PROFILE` env var.
4. Default `~/.alpi/`.

## Home layout (all isolated per profile)

| Path | Purpose |
|---|---|
| `config.yaml` | Model, fallbacks, tool limits, MCP servers, scheduler, workspace, budget. |
| `.env` | Provider keys / static secrets. A leak in one profile doesn't touch another. |
| `secrets/` | Per-profile non-ALP credential files (OAuth / Gmail tokens, etc.). `0o700`. The ALP keypair lives at `alp/secrets/alp_key.{pem,pub}`, not here. |
| `memories/` (USER.md, MEMORY.md, AGENT.md) | Persistent user/project memory + identity. |
| `sessions/<id>.json` | Local human chat log only (TUI / desktop / `chat --once`). Schedule, workgroup, system-prefixed turns stay out of resume/history. |
| `mentions/<sender>.json` | Per-sender `@`-mention threads, capped 20 turns, receiving side only. |
| `skills/` | Installed/user skills, under this profile's allowlist. |
| `recipes/` | Saved workgroup recipes owned by this profile when it acts as hub. The YAML filename stem is the recipe id. |
| `knowledge.sqlite` | Derived sqlite-vec indexes for workspace knowledge, session recall, and workgroup recall. |
| `alp/` (peers.yaml, socket, keypair under `alp/secrets/`) | ALP identity + pinned peers; two profiles = two distinct peers. The ALP private key lives at `alp/secrets/alp_key.{pem,pub}`, NOT under the profile-level `secrets/`. |
| `host/attachments/tmp/` | Uploaded chat attachments staged by the paired desktop / mobile apps. Per-profile — the rest of `host/` (`host.sock`, `connections.yaml`, `events.jsonl`, `device_id`) is root-only. |
| `run/bg/` | Background-terminal state: one combined `alpi-bg-*.log` (stdout+stderr capture) and one `<pid>.meta` file (key=value: `log=…`, `started=…`) per job spawned with `terminal(action="background")`. |
| `schedule/jobs.json` | Cron + one-shot jobs. Runs use `chat --once --no-save` (no session). Jobs with `no_agent: true` exec `prompt` as `python [flags] <skill_script>` directly, bypassing the LLM (allowlist restricts to `skills/<category>/<name>/scripts/`). |
| `outputs/outputs.jsonl` | Persistent inbox for proactive agent messages + schedule failures, capped 500 rows; served to paired apps via `host.outputs.*`. |
| `logs/` | `agent.log` (one line per engine turn on every surface — TUI, schedule, workgroup, inbound ALP, sub-agents), `llm.log` (provider request lifecycle breadcrumbs for idle-kill attribution) and `approval.log` (non-SAFE terminal classifications) — the only per-profile `.log` files actually emitted today. Daemon-wide events (schedule, ALP, workgroup) land in the root `~/.alpi/logs/service.log` — ONE per installation, not duplicated per profile; `alpi logs --source service` always reads the root file regardless of `-p`. `alpi logs --source` still accepts `schedule` as a filter value for any standalone or legacy file on disk. |
| `logs/ledger.json` | Daily USD/token spend cap, enforced across every turn (interactive, scheduled, sub-agent, inbound ALP). Resets at UTC midnight. |
| `cache/` (tts, stt, inbound voice) | Audio cache. |

Eager dirs at `ensure_home`: `memories/`, `secrets/`, `sessions/`, `skills/`, `recipes/`, `schedule/output/`, `logs/`, `host/`, `mentions/`, `outputs/` (all `0o700`). Lazy: `alp/`, `cache/`, `run/bg/`, `host/attachments/` and `knowledge.sqlite` (created on first use). `alpi audit` walks a fixed sensitive-path list and flags any group/other bits set (`st_mode & 0o077`) — fix is `chmod 700` for directories, `chmod 600` for files. The audited `secrets/` row is actually `alp/secrets/` (the ALP keypair directory) via `keys_mod.private_path(home).parent`; the profile-level OAuth `secrets/` is NOT audited today, and neither are the other lazy paths.

`alpi -p <name>` auto-bootstraps any not-yet-existing profile on first use; `alpi profile create <name>` is the explicit pre-bootstrap. Both go through `home.validate_profile_name`: the name must match `^[A-Za-z0-9][A-Za-z0-9._-]*$`, so `-p ../escape`, `-p .hidden`, `-p a/b`, `-p ..`, and any name containing `..` raise `InvalidProfileName` before the path is joined. `-p ""` is a no-op — empty falls through to the default profile (`~/.alpi/`), it does NOT resolve to `~/.alpi/profiles/`. Quote names containing zsh-glob characters (`*`, `?`, `[`); they're rejected by validation anyway but the shell expands them first.

Shared globally (NOT isolated): the `alpi` binary (`~/.local/bin/alpi`), Whisper downloads (`~/.cache/huggingface/`), Playwright Chromium, the user's shell / git config / workspace contents. **Host-plane root state** — `~/.alpi/host/host.sock` (control-plane socket), `~/.alpi/host/connections.yaml` (connection identities and device tokens), `~/.alpi/host/events.jsonl` (host event stream), and `~/.alpi/host/device_id` are root-only, ONE instance per installation. Named profiles still get their own `host/attachments/tmp/` (uploaded chat attachments), which IS per-profile and appears in the layout table above.

## Versioning / Git

Answer profile-versioning questions with this policy:

- `~/.alpi` is live runtime state, not clean source. It contains secrets, ALP private keys, device tokens, sessions, outputs, logs, cache, sockets, PIDs, temporary attachments, and derived indexes.
- Best practice: keep a separate Git repo such as `~/git/alpi-profiles/` containing profile source, then sync into the live profile with an allowlist.
- Commit source-like intent: `config.yaml` (reviewed for local paths/accounts), `memories/{AGENT,USER,MEMORY}.md`, `skills/**/SKILL.md`, skill scripts/references/non-secret assets, `recipes/*.yaml`, `schedule/jobs.json` when schedule behavior is intended, `README.md`, `env.example`.
- Never commit: `.env`, `secrets/`, `alp/secrets/`, skill `secrets/`, skill `state/`, `host/connections.yaml`, `host/devices.yaml.migrated`, `sessions/`, `mentions/`, `outputs/`, `logs/`, `cache/`, `run/`, `knowledge.sqlite`, sockets, pid files, temp attachments.
- `git init ~/.alpi` may be acceptable only for local inspection or a temporary migration on encrypted disk. If used, require deny-by-default `.gitignore` (`*` then opt in config/memories/skills/schedule docs) and inspect `git status --ignored` + `git diff --cached` before committing. Excluding only `.env` is unsafe.
- Docker: image is disposable; mount alpi home on a persistent volume, mount/bake profile-source separately/read-only, inject `.env`/credentials through runtime secrets, sync allowlisted files before `alpi daemon`.
- Kubernetes: prefer `StatefulSet` + `replicas: 1` for one live home writer; PVC at alpi home; init container or `git-sync` checks out profile source; init sync allowlisted files into PVC; secrets via Kubernetes Secret/SOPS/External Secrets/vault; annotate workload with source commit SHA.
- Do not make a Docker volume or Kubernetes PVC the Git repo for normal operation; the daemon writes live runtime state there.
- Git does not replace `alpi backup`: Git captures desired profile source; backup captures operational recovery (ALP identity, device pairings, OAuth tokens, sessions, outputs, ledgers, runtime state).

## Commands

```bash
alpi profile create work   # bootstrap tree with defaults
alpi profile list          # all profiles + model, disk size, active marker
alpi profile remove work   # archives home to ~/.alpi/.trash/<name>-<timestamp>/ after confirm
alpi -p work               # launch TUI for the work profile
alpi -p work setup         # configure (services + email); setup → Delete profile = remove
alpi -p work peers list    # peers pinned by the work profile
```

Every CLI command accepts `-p <name>`. No per-profile service to uninstall — the daemon is per-machine and picks up a removal on next restart.

## Common questions

- "Where is my data?" → see layout table; default `~/.alpi/`, named `~/.alpi/profiles/<name>/`.
- "Separate work/personal?" → two profiles (e.g. `~/.alpi/` personal + `~/.alpi/profiles/work/`); both run in the one machine-wide daemon and can be ALP peers of each other (`@work ...`).
- "Different model only?" → NOT a new profile; use `/model` or `setup → Model` in the same profile (keeps memory/skills). Scratch chat → `/new`.

## When to create a profile (axis = identity + stakes)

- Different cost/compliance boundary — per-profile `.env` + `config.yaml`; `budget.daily_usd` caps spend independently (USD or unlimited — no token cap).
- Different memory — MEMORY.md is profile-scoped; work context shouldn't bleed into personal.
- Different email identity — e.g. separate IMAP/Gmail accounts per profile.
- Different ALP role — a peer others talk to (`home-server`, `laptop`) with its own pubkey + peer list.
- Service identities: e.g. `assistant` (daily driver), `researcher` (read-only), `cron` (scheduled) — each its own model/sandbox/memory/ALP surface.
- Per-employee org: `~/.alpi/profiles/<user>/` each with own identity/key/memory; IT seeds `peers.yaml` with shared-service pubkeys. See DEPLOYMENTS.md.

## ALP identity

- Each profile has its own Ed25519 keypair at `{home}/alp/secrets/alp_key.{pem,pub}`; the base64 pubkey is the profile's cryptographic identity that peers pin in `peers.yaml`.
- Two profiles on one machine are distinct peers (distinct pubkeys + socket paths), talking over ALP.1 just as a remote profile would over ALP.2.
- Rotation = outage: delete `alp/secrets/`, next `alpi daemon restart` regenerates the pair; every peer that pinned the old key must update. Treat like rotating an SSH key.

## Cost & service rules

- Disk: fresh ~10 KB; after weeks 5–50 MB (voice cache + session retention). TUI top bar shows live size; `setup → Cleanup` reclaims audio cache, old sessions, rotated logs, schedule output, and knowledge index freelist bloat.
- CPU/mem: an idle profile costs nothing. One alpi daemon per machine hosts every profile's scheduler/ALP/workgroups poller as supervised `<profile>/<service>` asyncio tasks. Auto-installed on first `alpi setup`, managed from `setup → Services → Daemon`.
- Wrong-identity scheduler symptom → check which profile's service is running.

## Related topics

- Config and `.env`: `config`
- Daemon lifecycle: `operations`
- ALP identity: `alp`
- Skills per profile: `skills`
