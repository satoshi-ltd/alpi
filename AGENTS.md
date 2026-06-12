# AGENTS.md

Rules for any AI agent (Claude Code, Cursor, Codex, Aider, …) working on
this repository. Hard constraints, not suggestions.

> Behavioural rules the maintainer applies to every project (commit
> hygiene, test discipline, comment style, no AI-attribution lines) live
> in his personal agent config. They apply here too. If your harness
> doesn't load that file, the short version is: **no commits / pushes /
> tags without explicit permission in the current turn; every functional
> change ships with a test; default to no comments — when needed, one-line
> and aimed at the next LLM, not at humans.**

## Project

- **Name:** Alpi. Package `alpi`, binary `alpi`, home directory `~/.alpi`.
  Open-source, solo-maintained.
- **Positioning:** "a lighter, better Hermes." Hermes
  (`~/git/hermes-agent` on the maintainer's machine) is the canonical
  reference codebase. Before designing a non-trivial feature, look there
  first — but evaluate critically: Hermes is feature-rich for a broad
  audience while Alpi is scoped tight. The bar is "the smallest design
  that captures the value", not "port verbatim".

## Code style

- **All source text in English.** No Spanish anywhere in `alpi/` — code,
  docstrings, prompts, tool descriptions, CLI help, error messages,
  commit messages. Only runtime user-facing output (which follows the
  user's language) is exempt. Examples in tool descriptions bias the
  LLM's reply language; English keeps it neutral.
- **Plain JavaScript only — no TypeScript.** Frontend is always `.js` /
  `.jsx`. Do not propose adding TS "later" or scaffold projects with TS
  templates.
- **Minimize dependencies.** Every runtime or build dep needs explicit
  justification. Defaults: CSS Modules over Tailwind, hand-rolled over UI
  kits, vanilla over opinionated state libraries. Solo-maintained — every
  dep is maintenance tax forever.
- **No AI-maker attribution in the repo.** No "powered by Claude",
  "Co-Authored-By: Claude", or analogous Anthropic / OpenAI / Google /
  Mistral credits in commit messages, PR descriptions, code comments,
  marketing copy, README, or user-visible UI. Functional API identifiers
  (model strings like `anthropic/claude-sonnet-4-6`, env var names like
  `ANTHROPIC_API_KEY` / `OPENAI_API_KEY` / `GEMINI_API_KEY`, provider
  class names, LiteLLM routing prefixes) are exempt — they're protocol
  contracts, not branding. The line: if removing the mention would break
  auth, routing, or interop, it stays; if it's brag/credit/decorative,
  it goes.

## Releases & versioning

Two products ship from this repo, on independent cadences with
independent version schemes. Don't conflate them.

- **alpi (CLI / Python package).** Tags ``vX.Y.Z`` (no prefix).
  Versioned in ``pyproject.toml`` + ``alpi/__init__.py``.
  Changelog: [CHANGELOG.md](CHANGELOG.md). Pipeline:
  [.github/workflows/publish.yml](.github/workflows/publish.yml)
  (PyPI + GitHub release).
- **Desktop app (Tauri).** Tags ``desktop-vX.Y.Z``. Versioned in
  ``desktop/package.json`` + ``desktop/src-tauri/tauri.conf.json``
  (both must agree, or the release workflow aborts). Changelog:
  [desktop/CHANGELOG.md](desktop/CHANGELOG.md). Pipeline:
  [.github/workflows/desktop-release.yml](.github/workflows/desktop-release.yml)
  (GitHub release only — no PyPI). The Tauri updater reads
  ``releases/download/desktop-latest/latest.json``; the workflow
  re-points the rolling ``desktop-latest`` tag on every release
  so that URL stays stable.

A desktop release pins a minimum compatible alpi version in its
changelog entry — clients require a daemon recent enough to serve
every ``host.*`` verb the UI calls.

## Architecture

- **The desktop / mobile client talks to the daemon, not the filesystem.**
  Verbs in the `host.*` namespace (in `alpi/host/`) are served over
  `~/.alpi/host/host.sock` (Unix socket, 0600 + same-user trust boundary;
  no Noise, no pairing). When adding a desktop feature, add a `host.*`
  verb — never read `~/.alpi/` directly from Rust, never spawn `alpi` as
  a subprocess. ALP (`alpi/alp/`) is a separate plane for cross-machine
  peer-to-peer (`link.*`, `workgroup.*`) and is **not** what the client
  calls.

- **Engine `assistant_done` events: `final=True` marks the deliverable.**
  The engine emits `AgentEvent(kind="assistant_done", ...)` for **every**
  assistant message, including preamble narration that comes *before*
  tool calls ("Let me check things first.", etc.). Only the event that
  closes the turn carries `final=True`. Consumers that build the
  canonical reply (scheduler delivery, gateway, ALP) **must** filter on
  `ev.final`; otherwise preamble leaks into the message users receive.
  The TUI is the exception — it consumes every `assistant_done` to
  rewrite the active bubble, which is correct for live streaming.

- **Two messaging intents: `notify` (owner) vs `send_message` (third party).**
  `notify(text, title?, type?)` pushes to the OWNER's own paired Alpi apps —
  it files an inbox row in `~/.alpi/outputs/` and emits the `agent.message`
  host event (the only native push). `type` is the single presentation axis:
  `info` (default) | `warning` | `error`. `send_message(text, channel,
  chat_id?, attachment?)` reaches a THIRD PARTY through a gateway
  (telegram / imap / gmail / matrix / webhook) — `channel` is required, there
  is no owner channel, and it carries no `type` (its inbox rows are always
  `info`). The shared native-emit helpers live in `alpi/outputs.py`
  (`create_output_and_emit_message`, `_suppress_native_emit`). Clients must
  surface every `agent.message` — do not suppress it (e.g. for the active
  chat).

- **`schedule.done` / `schedule.failed` events carry structured output.**
  The scheduler tick emits `{profile, job_id, kind, message, reply,
  delivered_to, silent}` on the host event bus. `message` is the
  operational status for daemon logs and ops UIs. `reply` is the clean
  agent/script output, capped at 2000 chars, intended for native
  notification bodies. A job has one delivery axis, `notify: bool` (default
  `false`). `delivered_to` is `""` (silent, `notify:false`) | `"alpi"`
  (`notify:true` → the daemon re-emits the reply as `agent.message`) |
  `"external"` (the agent called `notify` itself → no duplicate). Failures
  always file an `error` inbox row and emit `schedule.failed`, regardless of
  `notify`. `silent` means a successful job produced no user-facing output.
  Do not parse `message` in clients when an explicit field exists. When
  changing the contract, update desktop/mobile consumers and bump the docs
  here.

- **`host.network.*` is the canonical network config surface for
  desktop/mobile.** `host.network.status` returns
  `{scope_in_use, host_in_use, is_override, port, device_name,
  candidates: {tailscale, lan, configured, docker}, diagnosis}` so clients
  can show the live pairing endpoint AND let the user pick a different one
  without dropping to `alpi setup`. `scope_in_use` is the network
  character of the host (`tailscale | lan | custom | docker`) computed
  via `network.classify_scope` — NOT the resolution path. `is_override`
  carries the "this came from `cfg.host.tcp_host`" bit separately.
  `host.network.set_advertised({host, device_name})` persists
  `cfg.host.tcp_host` + `cfg.host.device_name`; empty `host` unsets the
  override (back to auto-detect). Validation rejects public IPs (token
  leak), loopback, multicast/link-local/reserved, and malformed
  hostnames — accepts RFC1918, Tailscale CGNAT (100.64/10), and any
  valid hostname. `host.network.restart_host_server` ends the current
  daemon process (supervisor respawns with fresh config) and is the
  explicit handshake clients use after writing. **Known gotcha:** a
  stale override (e.g. Tailscale IP saved in config but Tailscale now
  off) still classifies as `tailscale` because the IP literally is one,
  but the daemon won't be listening on it — clients should compare
  `host_in_use` against `candidates` to detect this and warn.

## Testing

```bash
pytest -q                # fast suite (unit + filesystem)
pytest --integration -q  # adds tests that open sockets / use sandbox-exec
pytest --llm             # adds tests that make real LLM calls
```

CI (`.github/workflows/test.yml`) runs `fast` and `integration` jobs on
every push and PR — backstop only, not a substitute for running the suite
locally before declaring done.

A repo-versioned `pre-commit` hook (`.githooks/pre-commit`) runs only
the suites touched by the staged diff — alpi (pytest), desktop
(`pnpm test` + `cargo test`), mobile (`npm test`). Enable once per
clone:

```bash
git config core.hooksPath .githooks
```

Override with `git commit --no-verify` only when you know what you're
doing (half-merge in progress, etc.).
