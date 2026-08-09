# alpi answer pack

## Short answer

alpi is a profile-based personal AI agent for the terminal and private peer-to-peer agent networks. It keeps persistent memory, uses tools, builds reusable skills, and runs a per-machine daemon for the scheduler/host plane/ALP. Email is an on-demand tool (IMAP/Gmail), not a polled inbox. Goal: a lighter, tighter personal-agent system. Not a hosted SaaS, not browser-only; it does not make weak models reliable (tool discipline still tracks model quality).

- Package `alpi-agent`. Import path / binary / home dir: `alpi` / `alpi` / `~/.alpi`.
- Surfaces: TUI/CLI, daemon-hosted scheduler/host plane, ALP peer links, tools, memory, skills.

## Common commands

```bash
alpi setup           # model, email, MCPs, sandbox, daemon
alpi                 # interactive TUI
alpi -p work         # named profile
alpi doctor          # live health checks
alpi audit           # whole-install security posture scan
alpi audit-log       # bounded device-attributed administrative activity
alpi daemon status | restart
alpi update --check
alpi --version
```

## Core concepts

- **Profile**: isolation unit — one config, memory, sessions, skills, ALP identity, logs, service state. Default `~/.alpi/`; named `~/.alpi/profiles/<name>/`.
- **Memory**: plain Markdown written inline via `memory` tool, no post-session reflection. `USER.md` (user facts), `MEMORY.md` (env/operational), `AGENT.md` (response shaping).
- **Skills**: reusable workflows under `~/.alpi/skills/<category>/<name>/`, user-owned; mutations pass validation + security scanner; secrets in `.env` or per-skill `secrets/`. see skills
- **Workspace**: default root for relative paths, not a security wall. Absolute paths allowed except a sensitive-path denylist; real isolation is the opt-in OS sandbox.
- **Email**: on-demand `email` tool over IMAP/Gmail (list/search/read/send/reply/forward/move/delete); nothing polls the inbox.
- **Schedule**: cron + one-shot jobs through the same agent loop.

## ALP vs host plane

- **ALP** (Alpi Link Protocol): each profile owns an Ed25519 keypair; peers pin pubkeys out of band and grant explicit capabilities (`link.ping`, `link.ask`, `workgroup.post`). Fail-closed; no discovery service, shared account, or central broker.
  - ALP.1: same-machine profiles over Unix sockets.
  - ALP.2: inter-machine over Noise_XK TCP, per-peer budget + rate limits.
  - ALP.3: hub-anchored shared workgroups (multiple alpis + optional humans).
- **Host plane** (separate from ALP): control surface for paired desktop/mobile clients to reach their own daemon — `host.*` over local Unix socket or remote WebSocket. A connection groups role/profile scope, sessions and usage with multiple per-device credentials. `Connections` sets the companion endpoint; `Peer TCP listener` sets ALP peer traffic.

## What ships today

- Tool-calling agent loop over LiteLLM-compatible providers (first-class Ollama); fresh profiles ship no default model.
- TUI: streaming, slash commands, live tool cards, interrupt, session resume, model switching, cost/token display.
- Multimodal input: attach images/PDFs/text+source files per turn (TUI `/attach`, desktop/mobile paperclip); `knowledge(action="ingest")` makes the content durable by synthesizing OKF Markdown under the workspace `knowledge/` directory. The raw source is not copied.
- Tools: file, terminal, browser/search, memory, schedule, MCP client, plus:
  - `knowledge`: user/workspace OKF wiki search, ingest, maintenance, lint, and index actions.
  - `recall_sessions` / `index_sessions`: semantic recall over past conversations (`session_search` is the lexical layer, `session_read` opens the exact turn window — no model call); opt-in, forgettable, no auto-injection.
  - `workgroup_search` / `index_workgroups`: semantic search over hub-owned workgroup transcripts; profile-local, no cross-peer search, opt-in, forgettable.
  - `research(brief, depth)`: read-only sub-agent, tiers `fast`/`normal`/`deep`.
  - `delegate`: write-capable sub-agent for focused file/web/terminal tasks.
  - `alpi_knowledge`: packaged references (shipped behavior, not roadmap).
- Profile isolation; optional macOS/Linux OS sandbox per profile.
- Unified per-machine daemon (scheduler + ALP + workgroups + host plane); one launchd/systemd user unit.
- ALP identity + peer/workgroup features; desktop/mobile companion state behind `host.*`.
- Docker image `satoshiltd/alpi`, persistent storage under `/data/.alpi`.

## Security posture

LLM is treated as powerful, fallible, next to user credentials. Layered local guardrails:

- safe / caution / dangerous command classification; dangerous blocked with no config escape hatch; caution needs interactive approval or configured allowlist;
- sensitive-path denylist shared across file + terminal;
- SSRF protection on web tools; prompt-injection warnings on fetched web/email content;
- OSV malware checks before skill or MCP install;
- `alpi audit` scans every profile for loose secret permissions, public binds,
  disabled hardening, uncapped budgets, and installed-package CVEs; `--offline`
  skips the OSV lookup;
- agent/tool audit via `approval.log` and `agent.log`; administrative changes
  via `admin-audit.jsonl` / `alpi audit-log`. see security

## Related topics

quickstart (first setup) · install (install/update/uninstall) · config (fields) · profiles · tools · skills · security · operations
