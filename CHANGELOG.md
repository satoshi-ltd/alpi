# Changelog

## v0.4.34 — 2026-05-13 — capability hardening v0.5 (CH.3): memory promotion queue

Auto-compaction must never write to `USER.md` / `MEMORY.md` / `AGENT.md` directly — a single bad summary would otherwise pollute long-term memory. This release introduces a staging queue between compaction and durable memory, with a genuine human-in-the-loop gate.

- New `alpi/promotion.py` module: append-only JSONL store at `<home>/memories/promotion_queue.jsonl`. Bounded (`MAX_PENDING = 200`) and pending candidates auto-expire after `MAX_AGE_DAYS = 30` on read. Each candidate carries id, source, session_id, model, target file, text, confidence, and preview warnings.
- `alpi/compaction.py` gains `parse_candidates()` (tolerant JSON parser for the LLM's structured output) and `emit_candidates_from_summary()` which runs an extra short LLM call against the just-built summary using `CANDIDATE_PROMPT`. On enqueue, each candidate is annotated with the same warnings `memory(action="add")` computes at write time — operational-state heuristic, cross-file duplicate, safety scan — so the preview is genuinely useful.
- Engine wires the extraction step right after `auto_compact` emit. Each fired compaction emits up to 5 candidates per call. Best-effort: any LLM error is swallowed so compaction itself never breaks on flaky extraction.
- Two `memory` tool actions surface the queue safely: `promotion_list` (read-only) and `promotion_discard(id)` (drops without writing). **There is no agent-callable apply.** The agent cannot promote facts to durable memory by any tool call — `promotion_apply` returns a clear error pointing at the CLI.
- New CLI `alpi memory promote` is the only write path from the queue. Interactive review with `[a]pply / [d]iscard / [s]kip / [q]uit` per item; `--apply-all` and `--discard-all` cover unattended sweeps. Applications go through the standard `memory(action="add")` safety pipeline; if that path rejects (safety scan, duplicate), the candidate stays in the queue for retry.
- Tool description text in `memory` updated to advertise the new actions and explicitly direct routing user "remember this" requests to ``add``, not the queue.
- Tests: 32 new (9 queue store + 11 tool actions including warnings on enqueue + 10 compaction integration + 2 adversarial probes confirming the agent has no apply path). Suite 1590 passed.

## v0.4.33 — 2026-05-13 — capability hardening v0.5 (CH.2): granular terminal approval allowlist

- `tools.terminal.approval.allowlist` now accepts two entry shapes in the same list: legacy **pattern descriptions** (e.g. `recursive rm`, `sudo`) bypass an entire severity-category, and new **command globs** (e.g. `sudo apt *`, `git reset --hard origin/main`) match the literal command via `fnmatch` for per-command exceptions. Entries that match a built-in pattern desc keep the old category-bypass behavior; anything else is treated as a glob.
- Globs only override **caution** classification — `dangerous` commands stay blocked regardless of allowlist contents (no override path for `mkfs`, `dd of=/dev/…`, fork bombs, pipe-to-interpreter, ssh-key reads, system-dir writes).
- Globs do **not** apply to **compound** commands (containing `&&`, `||`, `;`, `|`, newline, backticks, or `$(…)`). Otherwise `"sudo apt *"` would also approve `sudo apt update && rm -rf build`. Compound commands fall back to the prompt unless a category-desc bypass covers them.
- `classify()` now scans every pattern and returns the **worst** severity, not the first match — a dangerous pattern hiding behind an earlier caution one (`rm -rf build && mkfs.ext4 /dev/sda`) is now correctly classified as `DANGEROUS` and blocked, even with `recursive rm` in the allowlist. Restores the "dangerous commands stay blocked regardless of allowlist" invariant.
- Storage stays in `config.yaml`. No second policy file, no `exec-approvals.json`. The `Always` button still persists pattern-descs; users wanting per-command globs hand-edit the list.
- The decision's `reason` now distinguishes `config allowlist` (legacy desc match) from `config allowlist (glob: '<entry>')` so audit logs are unambiguous.

## v0.4.32 — 2026-05-13 — capability hardening v0.5 (CH.1): skill eligibility fields

- Three new frontmatter fields gate skill availability alongside the existing `requires_env`: `requires_bins` (executables on PATH, checked with `shutil.which`), `requires_config` (dotted paths the user must set explicitly in `~/.alpi/config.yaml` — alpi defaults do not satisfy this gate), and `platforms` (`macos` / `linux` / `windows`, checked against the current OS). Missing requirements hide the skill from `skills_index_block` and `keyword_match_hint`, and surface in `skill(action="list")` with a compound `[inactive: missing …]` reason.
- Explicit invocations (`skill(action="run" | "test" | "invoke")`) on an inactive skill fail fast with a clear "missing …" error instead of half-running and failing mid-turn.
- `skill(action="create")` accepts the three new params directly; `set_meta` accepts them too. `skills_index_block` and `keyword_match_hint` also skip schema-invalid skills so malformed hand-edits never leak into the prompt.

## v0.4.31 — 2026-05-12 — capability hardening v0.5 (CH.0 + CH.4) + compaction event log

- **CH.0** — docs/code reconciliation: `docs/SKILLS.md` now lists `state/` as the fifth subdir and all skill actions (`view`, `patch`, `validate`, `set_meta`, `reset_state`, `run`, `test`, `invoke`); `docs/ARCHITECTURE.md` corrects memory char limits (`USER_CHAR_LIMIT = 3000` / `MEMORY_CHAR_LIMIT = 5000`) and documents v2 quality metadata (confidence/reinforcement/expiry, Trojan-Source scanner, post-turn reviewer).
- **CH.4** — regression guard: sentinel-based tests assert `skills_index_block` and `keyword_match_hint` stay metadata-only and never inject SKILL.md bodies, scripts, or references into the system prompt.
- **Compaction event log** — every `auto_compact` event now appends one JSONL line to `~/.alpi/profiles/<name>/logs/compaction.jsonl` (before/after tokens, summarized-message and tool-truncation counts, trigger, session id, model, ctx_window). Feeds CM.1 audit in v0.6. Compaction policy stays as constants in `alpi/compaction.py` — no config knobs until evidence demands them.

## v0.4.30 — 2026-05-12 — auto-compact: preemptive context compaction before LLM overflow

- New ``alpi.compaction`` module: cheap tool-output truncation first, then proportional summarization that preserves system + head + tail; never destroys history on a failed summarizer.
- Engine fires ``auto_compact`` events when projected prompt exceeds ``trigger_ratio`` of the model's context window; ctx window resolved via the existing ``alpi.ctx_window`` (litellm + Ollama runtime).
- ``/compact`` is now a manual "force auto-compact now" shortcut routed through the same pipeline — no second code path.

## v0.4.29 — 2026-05-12 — chat concurrency: interrupt-and-replace on the same session (+ desktop-v0.2.11)

- ``host.chat.send`` now serializes by ``session_id`` and interrupts the previous turn when the user sends a replacement prompt on the same session.
- Desktop chat events now carry ``request_id`` so stale ``interrupted`` / ``reply`` / ``done`` frames from the cancelled turn are ignored.
- Fixes the "mixed replies / pending turn cleared by the wrong stream" bug on the desktop chat surface.

## v0.4.28 — 2026-05-12 — per-profile env isolation + silent scheduled jobs + MCP grouping

- Per-profile ``.env`` loads in the daemon now use ``override=True`` so later profiles do not inherit the first profile's provider keys.
- Scheduled jobs without ``platform`` are now silent by default; auto-delivery stays opt-in for explicit gateway jobs.
- ``host.tools.list`` groups MCP tools as ``MCP · <server>`` instead of dumping them into ``Other``.

## v0.4.27 — 2026-05-12 — host introspection verbs (tools + skills body)

- New ``host.tools.list`` verb exposes the live tool registry to the host plane, with UI-facing category metadata.
- ``host.skills.list`` now returns the skill ``body`` and ``path`` so clients can render the full SKILL.md content.
- Unblocks desktop browse panels for tools and skills without special-case filesystem access.

## v0.4.26 — 2026-05-12 — peer status probes + TUI session sync + log rotation

- Fixes peer-status reporting in ``alpi doctor`` and consolidates probe timeout handling around the shared ALP ping constant.
- TUI ``@peer`` mentions now persist into the local session log, so desktop and TUI stay in sync on the same session file.
- Rotating logs now actually rotate; Telegram 409 polling spam is deduplicated and backed off.
- IMAP gateway metadata now includes the SMTP keys consistently across CLI, host-plane config, and desktop settings.

## v0.4.25 — 2026-05-12 — streaming `link.ask` (ALP.4)

- ``link.ask`` can now stream signed response chunks over the existing ALP transport when callers pass ``stream: true``.
- TUI and desktop ``@peer`` mentions render incrementally instead of waiting for a single atomic reply.
- ``peer`` tool and gateway paths keep the non-streaming shape, so interactive and delivery surfaces can diverge cleanly.

## v0.4.24 — 2026-05-11 — identity drafting as a primitive

- New ``alpi.identity`` module extracts public-bio drafting from the CLI into a reusable primitive.
- New host verb ``host.identity.draft`` lets desktop and future clients request a drafted bio without TUI coupling.
- Fixes the previous quote-stripping bug in drafted bios.

## v0.4.23 — 2026-05-11 — memory v2 quality pass (AI(1).c)

- Memory entries now carry confidence / capture / reinforcement metadata and support reinforcement on near-duplicate writes.
- Low-confidence, never-reinforced entries can auto-expire after a configurable age.
- ``memory(add=...)`` accepts ``confidence`` and batch-add now behaves per-item instead of all-or-nothing.

## v0.4.22 — 2026-05-11 — BA local RAG over `workspace/`

- Adds ``search_workspace`` and ``index_workspace`` for per-profile semantic recall over the user's workspace.
- Uses a local ``sqlite-vec`` store, ``fastembed`` for embeddings, and opt-in OCR with ``rapidocr-onnxruntime`` for scans/images.
- Supports incremental reindex, deleted-file purge, force rebuild on embedder mismatch, and daemon-side asset prefetch.
- Prompt/search guidance now routes "what do my files say about X?" queries to workspace recall before regex search.

## v0.4.21 — 2026-05-10 — `alpi` reserved as a profile name

- ``alpi`` is now reserved alongside ``default`` so the bundled identity cannot be shadowed by a user-created profile.
- The same rule is enforced across CLI and host-plane profile creation.

## v0.4.20 — 2026-05-09 — robust endpoint detection + diagnostic pairing errors

- Host advertised-address detection now prefers a platform-neutral UDP routing probe before falling back to shell parsing.
- Pairing failures now surface structured endpoint diagnostics instead of a generic "cannot pair" error.

## v0.4.19 — 2026-05-09 — pairing admin is local-only at the transport layer

- Pairing-admin verbs are now blocked on remote WebSocket transport and remain local-only over the Unix socket.
- Closes a protocol hole where a paired device token could manage other devices on the host.

## v0.4.18 — 2026-05-09 — Gmail OAuth from the host plane

- Adds host-plane support for interactive Gmail OAuth so desktop can configure the gateway without shelling out to ``alpi setup``.
- Includes validation and host-side config plumbing for the desktop flow.

## v0.4.17 — 2026-05-08 — short timeout on peer-ping probes

- Tightens the host peer-probe path so noisy or slow peers stop holding status refreshes open for too long.
- Keeps the dedicated regression coverage in ``tests/host/test_probes.py``.

## v0.4.16 — 2026-05-08 — host plane keeps WebSocket open for multiple RPCs

- Host WebSocket connections now accept multiple RPCs on the same socket instead of one message per connection.
- This is the server-side prerequisite for the desktop pooled remote WebSocket hot path.

## v0.4.15 — 2026-05-08 — TUI rich-text polish (BB)

- Improves TUI markdown / rich-text presentation and adds regression coverage for the new styling path.
- Removes the shipped BB item from the roadmap now that it is live.

## v0.4.14 — 2026-05-07 — post-turn memory reviewer (AI(1).b)

- Adds the post-turn memory reviewer pass plus the related config wiring.
- Includes dedicated regression coverage for the reviewer behavior.

## v0.4.13 — 2026-05-07 — memory write safety scan (AI(1).a)

- Memory writes now go through the same safety scanner used for skill content.
- Blocks prompt-injection, secret leakage, invisible Unicode, and other dangerous payload classes before persistence.

## v0.4.12 — 2026-05-07 — skill safety primitives (AT)

- Skill deletion is now recoverable through archive-on-delete plus a pinned flag for protected skills.
- Adds the schema/runtime support needed for safer future curation passes.

## v0.4.11 — 2026-05-07 — system prompt sharpening for skill quality (AS)

- Tightens system-prompt guidance so the agent reaches for relevant skills more reliably before generic tools.
- Ships with focused prompt-behavior regression tests.

## v0.4.10 — 2026-05-07 — desktop connection stability and session listing

- `host.sessions.list` — accepts an optional `limit` so clients can load recent sessions quickly without parsing every session file on dropdown open. Results remain newest-first, and search-capable clients can still request the full list.
- Desktop host-plane compatibility — remote connections are treated as IP endpoints, avoiding unbounded hostname / mDNS resolution in the desktop WebSocket transport.
- Umbrel package — container entrypoint now monitors both the daemon and TUI process; if the daemon exits, the container exits non-zero so Umbrel / Docker can restart it instead of leaving a half-alive app.
- Tests — session limit coverage, desktop host-client transport tests, and Umbrel entrypoint assertions cover the new release behavior.

## v0.4.9 — 2026-05-07 — Umbrel host summaries and pairing labels

- `alpi/host/device_state.py` — daemon liveness now uses `os.kill(pid, 0)` instead of shelling out to `kill -0`. This fixes `host.profile.summaries` inside the slim Umbrel container, where the external `kill` binary may not exist.
- `alpi setup -> Devices -> Network` — new optional pairing name (`host.device_name`). Pairing QR labels now resolve through configured name, Umbrel device hostname, system hostname, then `Alpi`, avoiding container-id labels such as `cded386e8d10`.
- Docs / Umbrel package — package docs, compose tag, manifest version, submission notes, and publish workflow default move to `0.4.9` so the Umbrel image can ship the daemon-summary fix.
- Tests — host device-state coverage verifies the daemon liveness check no longer depends on an external `kill`; Umbrel setup tests cover saving the pairing name.

## v0.4.8 — 2026-05-07 — skill runtime contracts and composition

- `alpi/tools/skill.py` — `output_schema` is now a real runtime contract for scripted skills. `skill(action="run")` validates JSON stdout against it, `skill(action="test")` exercises the same scripted path as a minimal harness, and `skill(action="invoke")` adds strict composition for scripted skills only (`scripts/run.py` + `output_schema` required).
- `alpi/tools/_skill_schema.py` — frontmatter validation understands `output_schema` and validates a small JSON Schema subset (`type`, `properties`, `required`, `items`, `enum`) without adding a new dependency.
- Docs — `docs/ARCHITECTURE.md`, `docs/SKILLS.md`, `docs/ROADMAP.md`, and `alpi/prompts/system_prompt.md` now describe the three execution surfaces clearly: `run` for general entry, `test` for harnessing, `invoke` for structured composition. BF-8 (versioning/install-update flows) is moved out of the active cycle and kept in **Future releases**.
- Tests — `tests/tools/test_skill_run.py` (invoke/test/runtime contracts), `tests/tools/test_skill_schema.py` (`output_schema` frontmatter validation), `tests/tools/test_skill_set_meta.py` (`output_schema` metadata updates).

## v0.4.7 — 2026-05-07 — skill execution and schedule guardrails

Five fixes converging on one theme: the agent loop should make it
hard to lie about side-effects and easy to do the right thing in one
call. Distilled from a real 35-turn session that ended up with a
duplicate cron job, a fragmented memory write across 16 calls, and
three "done — no, you didn't" exchanges.

- `alpi/tools/skill.py` — new `skill(action="run", name=..., [args])`. If the skill ships `scripts/run.py`, alpi validates it, then spawns it with `cwd` = skill dir and an env enriched with `ALPI_HOME` / `ALPI_SKILL_NAME` / `ALPI_SKILL_DIR`; stdout/stderr come back as the tool result. No script → SKILL.md is returned with a directive prefix so the agent follows the prose instead of improvising. Scripts that try to import tools/MCP methods from `alpi` are blocked before execution.
- `alpi/tools/memory.py` — `memory(action="add", entries=[...])` batches multiple writes into one call. Each entry is duplicate-checked independently and the target file is written once, so a later duplicate/limit failure cannot leave a half-written batch. Partial successes return the kept entries plus per-skip notes. Works for `USER.md`, `MEMORY.md`, and `AGENT.md`. Backwards-compatible: `content=...` still works.
- `alpi/tools/schedule.py` — `schedule(action="add")` rejects a near-duplicate of an existing job (same `kind` + cron / run_at / inactivity-window AND fingerprint of the first 80 chars of the prompt) unless `force=true`. `schedule(action="update", id=...)` edits an existing job in place, avoiding the remove/recreate loop that produced duplicate schedules. Prompts that explicitly say "send/post to Telegram" are rejected because scheduled replies are already auto-delivered to `platform` + `chat_id`.
- `alpi/tools/_skill_schema.py` — `tools:` frontmatter validator now accepts MCP names (`name__methodCamelCase`) alongside snake_case built-ins. Stops the validator from flagging `bitbucket__getPullRequests` as a typo.
- `alpi/prompts/system_prompt.md` — four new rules in **Tool use** ("past tense ⇒ tool_call this turn", "list before create when state is involved", no trailing "if you'd like, the next step…", memory is for facts not runtime logic) and a "Running a skill" paragraph in **Skills** that names `skill(action="run", ...)` as the canonical execution path.
- Docs — `docs/ROADMAP.md` marks BF as active and narrows Skills v2 to the remaining backlog now that the real-world skill stress test has shipped.
- Tests — `tests/tools/test_skill_run.py` (9), `tests/tools/test_memory_batch.py` (9), `tests/core/test_schedule_dedup.py` (10), `tests/tools/test_skill_schema_mcp.py` (6).

## v0.4.6 — 2026-05-06 — chat rewrite truncation over host plane

- `alpi host` — `host.chat.send` accepts `rewrite_from_turn` when resuming an existing session. The hydrated session is truncated before the new turn runs, so desktop "rewrite from here" continues from the kept prefix instead of carrying discarded turns in memory/context.
- `tests/host/test_chat.py` covers the resumed-session truncation path: kept turns/messages are trimmed to the requested prefix and usage counters are reset before the new turn runs.

## v0.4.5 — 2026-05-06 — schedule no-save + desktop hot-path cleanup

- `alpi scheduler` — scheduled jobs now invoke `alpi chat --once --emit-events --no-save`. A schedule run still streams events to the scheduler for delivery, budget, and logs, but it no longer writes a local chat session. This keeps cron output out of TUI / desktop profile history.
- `alpi cli` — `--continue` / `tui.auto_resume` now resume only local chat sessions. Historical scheduled, gateway, workgroup, and system sessions already present under `sessions/` are skipped.
- `alpi host` / desktop — profile `latest_session` is treated as local-chat-only. Desktop also rejects non-chat session payloads defensively so older daemons or historical files cannot open scheduled/gateway/workgroup turns as a normal profile chat.
- Desktop — streaming/render hot paths were reduced: filesystem-change reloads are debounced, active streaming avoids full session rereads, historical turns are memoized, and composer peer probes no longer rerun on every profile-list refresh.

## v0.4.4 — 2026-05-06 — daemon PATH for MCP spawns + docs alignment

Fixes MCP servers crashing silently when reached through the daemon
(desktop client path): the daemon's launchd / systemd PATH did not see
user-installed Node / Python tools, so `npx`-based servers (e.g.
`bitbucket-mcp`) failed with `command not found`. The TUI was unaffected
— it inherits the user's shell PATH. Plus a docs sweep to match the
per-machine daemon reality and a v0.5 roadmap pivot to "owned device
access".

- `alpi/mcp/client.py` — `_augmented_path()` prepends user-tool dirs (nvm, volta, homebrew, `/usr/local/bin`, snap, `~/.local/bin`, `~/.cargo/bin`, `~/.bun/bin`, `~/.deno/bin`) ahead of the inherited PATH; `_build_env` writes it into every MCP subprocess env. Tests in `tests/mcp/test_mcp.py` cover preservation, ordering, and skip-when-absent.
- Docs — `alpi daemon status/start` replaces `alpi setup → Service → Install`, Matrix joins the gateway list, `alpi backup` / `alpi restore` are top-level. Knowledge skill mirrors re-synced.
- `docs/ROADMAP.md` — v0.5 theme renamed to "owned device access"; new `AX-desktop-remote` work item for desktop multi-host host-plane connections (local Unix socket vs paired remote daemon over WebSocket).

## v0.4.3 — 2026-05-06 — Umbrel app + companion endpoint cleanup

Closes the first Umbrel-ready deployment of alpi and tightens the
device-access story around the host plane. Umbrel now ships as a real
app package running the existing TUI behind Umbrel's app proxy, the
daemon/setup UX stops pretending systemd or launchd exist inside the
container, and `Devices` gains an explicit network override so mobile
and desktop companions can advertise a stable endpoint instead of
depending entirely on autodetection.

- `deploy/umbrel/alpi/` — new Umbrel app package: Docker image, app manifest, compose file, entrypoint, and store-facing docs. The package persists the profile under `/data/.alpi`, serves the Textual TUI via `ttyd` on port `8080`, and publishes the host-plane WebSocket on `49200` for paired clients.
- `alpi/cli.py` — `alpi setup` is Umbrel-aware. The daemon lifecycle screen is hidden there, services read as `managed by Umbrel`, `Devices -> Network` lets the user pin an advertised host, and the old ambiguous ALP label `TCP port (inter-machine)` becomes `Peer TCP listener`.
- `alpi/host/network.py`, `alpi/service.py`, `alpi/host/server.py` — host-plane remote access now separates the address the server binds from the address the client QR advertises. Umbrel binds the host API inside the container and can advertise `umbrel.local`, a Tailscale IP, or a MagicDNS hostname without relying on container-local network detection.
- `alpi/doctor.py` — daemon health checks report Umbrel-managed state instead of implying a missing system service.
- `alpi/host/device_state.py` — host config coercion now accepts `host.tcp_port` edits through the same device-facing config surface as `alp.tcp_port`.
- Docs — Umbrel operations, persistence, and submission flow land under `deploy/umbrel/`; deployments docs now spell out the split between the host-plane companion endpoint (`host.*`) and the ALP peer listener (`link.*`, `workgroup.*`).

## v0.4.2 — 2026-05-05 — workgroup poller correctness + protocol-aligned language

Tightens workgroup dispatch so peers in the same daemon stop blocking
each other, kills a class of wasted dispatches against already-closed
tasks, and makes peer agents follow the language of the active
``#task`` instead of defaulting to English. ALP wire behaviour is
unchanged; ``alp.v`` stays at 1. The fixes align the implementation
with the protocol description and update ALP.md where the description
had drifted.

- ``alpi/service.py`` — ``_INFLIGHT`` rekeyed from ``wg_id`` to ``(wg_id, profile)``. The "single-flight per profile" invariant in ALP.md → *Workgroups → Preemption* assumed per-profile state; with the unified daemon (``one supervisor per machine, every profile inside``) the old key let one profile's dispatch lock another profile's dispatch for the same workgroup. Concrete observed effect: 4 peers receiving the same ``#task`` would serialise behind one in-flight LLM instead of running in parallel.
- ``alpi/service.py`` — preempt watcher now scopes to its own profile (``info["profile"] == profile`` filter). Previously every profile's watcher iterated the global table and called ``_active_task_seq_for(<own_home>, …)`` against another profile's dispatch; since each home only knows its own subscriptions / hub state, it read empty and incorrectly concluded the task was closed → SIGTERM 200 ms after dispatch. Each watcher now only manages dispatches it can actually evaluate.
- ``alpi/service.py`` — ``_should_dispatch`` no longer fires ``collective #task opened`` when ``active_task()`` shows the task has been ``#done``-closed. Without this, a member whose poller saw the original ``#task`` after the hub had already closed it would dispatch a turn whose only legal outcome was ``#skip`` — burn budget for a noise post.
- ``alpi/service.py`` — workgroup dispatch prompt grows a final ``LANGUAGE`` block: write every post (substantive, ``#working``, ``#skip``, ``#done``) in the language of the active ``#task``. Recency-biased placement at the end of the prompt (the trigger message is otherwise English-dominated, which leaked into ``#working`` reasons even when the ``#task`` was Spanish).
- ``alpi/alp/agent_context.py`` — ``LANGUAGE`` rule in the system-prompt guardrails simplified to "match the language of the active ``#task``". Previous wording defaulted to English with a briefing override clause that was never wired (no parser, just a hint to the user); briefing is for problem framing, not configuration.
- ``docs/ALP.md`` — *Workgroups → Preemption* updated to describe ``_INFLIGHT`` as ``(wg_id, profile) → {…}`` and the watcher's per-profile scope, with a one-line reason for the keying. Wire shape, methods, and invariants unchanged. The protocol's intent (``single-flight per profile``) was already correct — only the implementation snippet was wrong.

## v0.4.1 — 2026-05-04 — host plane over WebSocket, per-device pairing tokens

Closes the daemon-side foundation for **AX-mobile** and unifies the
desktop control path: the host plane now serves `host.*` over a
WebSocket on Tailscale or LAN in addition to the existing Unix
socket, every remote request carries a per-device pairing token,
and the desktop Tauri layer routes its previously-shelled-out
commands through the same JSON-RPC verbs.

- ``alpi/host/server.py`` — second listener on ``ws://<bind>:49200`` (port configurable via ``host.tcp_port``). Bind validated up front: only Tailscale CGNAT (``100.64.0.0/10``) or RFC1918 private ranges (``10/8``, ``172.16/12``, ``192.168/16``) accepted; loopback, ``0.0.0.0``, and public IPs refused. Token middleware on the WS path requires ``params.auth_token``; Unix socket stays token-less (filesystem perms = trust). Empty device store keeps the listener open as a v0.4 → v0.4.1 migration window.
- ``alpi/host/devices.py`` — pairing-token store at ``~/.alpi/host/devices.yaml`` (mode 0600) with ``host.devices.{list,generate,revoke,rename}`` verbs. ``secrets.token_urlsafe(24)`` (192 bits, 32 chars). The full token escapes the daemon exactly once (in the QR returned by ``generate``); listing redacts to a ``token_id`` (last 8 chars).
- ``alpi/host/network.py`` — ``detect_bind_ip()`` picks Tailscale first, falls back to the first private LAN address, returns ``None`` when neither exists (listener stays Unix-only). Tailscale lookup uses ``tailscale ip -4`` with a fallback to parsing ``ifconfig`` so the daemon works under launchd on macOS where the App Store binary refuses subcommands without a GUI/keychain context.
- ``alpi/host/probes.py`` — new ``host.gateway.probe``, ``host.peers.ping``, and ``host.model.ctx_window`` verbs. Same logic the desktop used to shell out to via ``alpi gateway probe``, ``alpi peers ping``, and ``alpi ctx``; now reusable from any host-plane client.
- ``alpi/host/workgroup_admin.py`` — ``host.workgroup.{create,update,add_member,kick,remove,action,post}`` covers workgroup CRUD end-to-end so mobile (and the migrated desktop) no longer need a CLI subprocess.
- ``alpi/host/device_state.py`` — ``latest_session`` is the most recent local chat session. Gateway, schedule, workgroup, and other non-interactive turns stay out of the TUI / desktop profile history.
- TUI ``alpi setup → Devices`` is a real device manager: list paired devices with ``Last seen``, **+ Add device** generates a one-shot QR (compact ``{v:2, i, p, n, t}`` payload, ECC-L), Rename / Revoke per device. The QR generator runs inside ``ui.activity()`` so the user sees feedback while it builds.
- ``desktop/src-tauri/src/lib.rs`` — workgroup CRUD, gateway probe, peer ping, and ctx-window resolution dropped their ``Command::new("alpi")`` shell-outs and now call ``host_client::call(...)``. Two shell-outs remain on purpose: ``service_action`` (the daemon may not be running yet) and ``voice_test`` (audio plays on the client machine). ``alpi`` is no longer required on ``$PATH`` for general desktop use.
- Docs — ARCHITECTURE / SECURITY / CONFIG document the two transports, the bind invariant, and the device-token lifecycle. Knowledge skill mirrors track the public docs.

## v0.4.0 — 2026-05-03 — secure device access

Closes the alpi side of the v0.4 cycle: profile state now has a
shared device-facing host-plane API, profiles are portable through
encrypted backup/restore, and desktop/mobile clients can use the
daemon contract instead of reading profile files directly.

- ``alpi/host/device_state.py`` — new host-plane read/mutation surface for device clients: profile list/summaries, bounded file reads, profile storage, config field edits, gateway status/config, skills, workgroups, workgroup members, and Ollama model discovery. These are ``host.*`` verbs, not desktop-only helpers, so mobile can reuse the same daemon contract.
- ``alpi/backup.py`` — encrypted profile archive/restore is part of the 0.4 baseline. Restore validates v1 crypto parameters before Scrypt and pre-validates archive paths before writing, so hostile archives cannot force partial extraction or unbounded KDF work.
- Docs — roadmap moves v0.4 to shipped history; architecture documents ``host.device_state`` as the shared desktop/mobile device state layer.

## v0.3.14 — 2026-05-03 — encrypted profile backup / restore

Two new top-level commands close the v0.4 **AW** roadmap item and
make the profile portable between machines: ``alpi backup`` writes
``<profile>.<YYYY-MM-DD>.alpi-backup`` (single file, 0600,
passphrase-encrypted, zero-knowledge); ``alpi restore PATH``
reverses it into the active profile, refusing a non-empty target
unless ``--force``.

- ``alpi/backup.py`` — Scrypt KDF (n=2¹⁷, r=8, p=1) → ChaCha20-Poly1305 over a gzipped tar of the profile. Same primitives as ``age`` with a passphrase recipient, but no new runtime dep — ``cryptography`` is already pinned. Header (KDF params, salt, nonce, profile name, timestamp, file count) is bound as AAD so any tamper flips the AEAD tag.
- Excludes: ``cache/``, ``logs/``, ``profiles/`` (nested-profile root), ``.trash/``, ``*.sock``, ``*.pid``. Memories, skills (incl. ``state/``), sessions, ``.env``, ``config.yaml``, ALP keys all round-trip.
- Both commands accept ``--passphrase-stdin`` for scripting; otherwise prompt with hidden input (and confirmation on backup). Restore refuses entries with ``..`` segments — a hostile archive cannot escape the target dir.
- ``tests/core/test_backup.py`` — 14 cases: round-trip, ephemeral exclusion, wrong passphrase, header tamper, archive overwrite refusal, target overwrite refusal + ``--force``, header inspect without decrypt, non-backup file rejection, path-traversal rejection, empty passphrase, empty profile, plus two CLI end-to-end via ``CliRunner``.

## v0.3.12 — 2026-05-03 — `default_agent.md` slim

Rewrote the persona seed and lifted operative rules into the
system prompt. New profiles boot with a 10-line audience-neutral
persona (no "engineering-level familiarity assumed", no project-
ethos baked in). Project rules
live in `system_prompt.md` where they apply to every profile.

- ``alpi/prompts/default_agent.md`` — 30 → 10 lines. Identity + Voice (5 bullets) only. Stance section dropped (paternalistic / audience-assuming). "Edit me" meta-block dropped (the user edits via chat).
- ``alpi/prompts/system_prompt.md`` — new ``## Conversation`` section consolidates operative rules that were scattered between ``default_agent.md`` and ``Tool use``: match user's language on replies (persist in English), quote paths verbatim, don't ask clarification on minor ambiguity, don't ask rhetorical permission. Deduplicated against the existing ``Tool use`` section.
- ``alpi/prompts/system_prompt.md`` — skill-creation guidance retuned: "consider creating" instead of "call it proactively", with an explicit "create without asking only when the pattern is clearly recurring". Lowers the false-positive rate where a single one-off ask would trigger a skill.
- Existing profiles untouched — ``~/.alpi/<profile>/memories/AGENT.md`` is user-owned content. Only new profiles seed with the slim shape.
- ``tests/llm/`` — new LLM-in-loop test suite (engine-direct, parametrised across multiple providers). Runs with ``pytest tests/llm --llm``; skipped by default. Asserts on tool calls + filesystem state, never on prose. Covers skill create / set_meta / db usage / eligibility gate / memory routing / persona manifestation / don't-over-skill.

Validation: full reshape via chat (rename to "Mira", add Basque-cuisine
expertise, add responsibilities, populate USER + MEMORY) lands
cleanly. State integration in follow-up turns works end-to-end —
a recipe reply respects expertise, gluten intolerance, family
size, the wine-pairing persona rule, and the Thermomix tool note
all at once.

## v0.3.11 — 2026-05-03 — skills overhaul

Skill surface tightened after a strategic review of comparable
agent workflows, plus integration probing on real profiles.

- **Persistence in English.** `memory` / `skill` / `schedule` tool descriptions mandate English on every persisted entry regardless of chat language (they reload into context every turn). Three pre-existing Spanish examples in `system_prompt.md` translated.
- **`requires_env` enforced + subprocess passthrough fixed.** `skills_index_block` filters skills with unset env vars; `_list` tags them `[inactive: missing env var FOO]`. `_view` now forwards declared vars to terminal subprocesses — without that fix scripts ran with empty `$VAR`.
- **Frontmatter schema validator.** `alpi/tools/_skill_schema.py` — `Issue(field, severity, message)` per problem; errors block, warnings surface to the agent. Covers every documented field. `skill(action='validate')` returns `ok=False` on errors and no longer writes `__pycache__`.
- **SQLite first-class — `db` tool + `reset_state`.** `db(action='query'|'exec', skill, sql, params)` over `<skill>/state/db.sqlite`. Stdlib `sqlite3`, zero new deps. Quotas: 50 MB / 10k rows / 5 s busy timeout. Per-skill scope; bundled rejected. `skill(action='reset_state')` wipes `state/`. Scanner is env-aware: `os.getenv("VAR")` allowed only when declared.
- **Keyword discovery boost.** Optional `keywords:` in frontmatter; engine injects a per-turn `# SKILL HINT` when the user message contains any keyword as a whole token. Hyphenated keywords supported. Cap 3 hits per turn.
- **`set_meta` + `edit` hardening.** New `skill(action='set_meta')` — surgical frontmatter update, prose byte-preserved, accepts top-level kwargs. `_edit` rejects body with frontmatter blocks (points at `set_meta`) and placeholder bodies (`[PENDING_VIEW]` etc.) that would nuke real prose.
- **`_list` state tags.** Inline: active / `[invalid: <field>]` / `[inactive: …]`. Runtime "broken" stays in `validate`.
- **Misc.** Knowledge skill references rewritten as compact answer-packs (~3500 → ~1000 lines). `docs/MODELS.md` reorganised by workload. 95+ new tests covering every primitive end-to-end.

## v0.3.10 — 2026-05-02 — `alpi diff`

What changed in this profile since N hours/days ago — memory
edits, sessions, mentions, skills, peer-list mutations, fired
schedules, today's budget. mtime-driven, side-effect free, safe
from cron or SSH. One primitive (``alpi/diff.py``) shared by the
CLI subcommand and the TUI ``/diff`` panel; a host-plane verb
will follow once the desktop has a use for it.

- ``alpi diff [--since 24h|7d|2026-04-25] [--json]`` — top-level command. ``--json`` emits the raw report dict for scripts / dashboards.
- ``/diff [since]`` slash command in the TUI; opens a floating panel rendered from the same report.
- ``docs/OPERATIONS.md`` — new "What changed in this profile?" section with cron / pre-backup / SSH-snapshot use cases.
- ``tests/core/test_diff.py`` — 23 cases covering ``parse_since``, every scanner branch, the empty-profile baseline, and a render smoke test.

## v0.3.9 — 2026-05-02 — daemon refactor + host plane

The v0.4 cycle lands as a single 0.3.9 release on the alpi side:
a unified per-machine daemon (replacing the per-profile service
model), a new host-plane control API for visual / remote clients
to talk to, and the cycle of alpi improvements (workgroups
protocol overhaul, peer mention via ``link.ask``, mention thread
fix, pending invites, gateway session isolation, budget-zone
signal, test reorg). The first public Tauri desktop client ships
on its own track as ``desktop-v0.1.0`` — see
[desktop/CHANGELOG.md](desktop/CHANGELOG.md).

### alpi cycle

- ALP.3 workgroups protocol overhaul — hub-anchored multi-party transcripts with per-workgroup budgets, single-task rotation, ``#task`` / ``#done`` markers, mention-based engagement triggers, key rotation on member change.
- Peer mention via ``link.ask`` — ``@<peer>`` from TUI / gateway short-circuits the LLM and routes through the shared executor as the ``peer`` tool. Roster-gated by ``alp_mention.parse(text, home=home)`` so unknown ids fall through to the engine.
- Mention thread fix — hydrated turns flagged as conversational context, not authoritative; re-read memory on memory-driven questions to avoid stale answers after the user edited memory between turns.
- Pending invites — inbound from an unpinned peer leaves a pending entry under ``<home>/alp/pending/`` for explicit accept / discard from wizard / desktop.
- Per-sender ``@``-mention threads + isolated gateway sessions — ``mentions/<sender>.json`` per peer; gateway sessions move to ``gateway/sessions/`` and stay invisible to local ``--continue``.
- Budget-zone signal — workgroup turn context grows a one-line gradient nudge once the daily cap crosses 40% so the agent biases toward shorter posts before the cap actually trips.
- Test reorg — ``tests/`` flat → ``tests/{alp,core,gateway,host,mail,mcp,tools,tui,manual}/``; CI runs ``pytest -q`` on PRs.
- AGENTS.md hardening — comments rule sharpened: not for humans, one-line preferred.

### Daemon

- One ``com.alpi.daemon`` process per machine supervises every profile under ``~/.alpi/``, replacing the per-profile process model (N daemons + N plists). Per-(profile, service) tasks supervised independently.
- ``alpi service`` group → ``alpi daemon``; ``com.alpi.service.<profile>.plist`` → ``com.alpi.daemon.plist``; ``alpi-service-<profile>.service`` → ``alpi-daemon.service``.
- ``home.set_active_home`` ``ContextVar`` bound by ``Engine.run_turn`` — tools resolve to the right profile across concurrent turns in one process. Without this every profile's tools would write to default's home.
- ``alpi setup`` auto-installs the daemon on first run; no opt-in step. Linux install runs ``loginctl enable-linger`` so the unit survives logout (long-standing bug).
- Manual workgroup scripts updated for the post-refactor API (single ``svc.install_daemon`` instead of N per-profile installs).

### Host plane

- New Unix-socket control API (``~/.alpi/host/host.sock``, default profile only). JSON-RPC-shaped, auth via filesystem perms. Not ALP — different transport, different trust model.
- Verb namespaces: reads (``host.sessions.*`` / ``host.session.read`` / ``host.workgroup.transcript``), chat (``host.chat.send`` streaming + ``host.chat.cancel`` with ``@<peer>`` shortcut parity with TUI), config mutations (``host.providers.*``, ``host.peers.*``, ``host.profile.*``, ``host.mcp.*``, ``host.gateway.remove``, ``host.sandbox.*``, ``host.voice.*``), schedule (``host.schedule.{list,remove,set_paused,fire}``), daemon (``host.daemon.restart``), events (``host.events.subscribe`` push channel).
- Path-traversal-safe via shared ``_check_id`` regex; protected env keys (``HOME``, ``PATH``, ``ALPI_HOME``, etc.) refused at the verb layer.
- Schedule creation stays in the agent (``schedule`` tool) so the threat-scan + skill rules continue to gate prompt content; the host-plane is a visibility + cleanup surface.

### Desktop

- First public Tauri client lands as ``desktop-v0.1.0`` on its own release track. See [desktop/CHANGELOG.md](desktop/CHANGELOG.md) for the per-release notes.

## v0.3.8 — 2026-04-28 — security audit hardening

External audit verdict landed; 9 of 10 verified findings hold.
This release closes them in P0/P1/P2 order without changing
public behaviour for existing profiles.

- `alpi/mcp/client.py` — MCP subprocess no longer inherits all of `os.environ`. Same safelist + declared-`env:` pattern as the v0.3.6 terminal fix. Closes API key/token leak to any third-party MCP server.
- `alpi/alp/envelope.py`, `alpi/alp/client.py`, `alpi/alp/server.py` — `verify()` now accepts `expected_to`/`expected_from`/`expected_id` and raises `WrongRecipient`/`WrongSender`/`IdMismatch`. Server pins `alp.to == self.kp`; client pins both response sender and JSON-RPC id. Closes ALP cross-target replay between trusted peers.
- `alpi/tools/_guards.py`, `alpi/tools/web_fetch.py` — SSRF: `check_url` switches `gethostbyname` → `getaddrinfo` (all A/AAAA records) and rejects non-`http(s)` schemes; `_direct_fetch` follows redirects manually and revalidates each hop against the blocklist.
- `alpi/_redact.py` (new), `alpi/session.py` — secret-shape redaction (`sk-…`, `ghp_…`, `AIza…`, Telegram tokens, key names containing `password`/`token`/`secret`/`api_key`/etc.) before `sessions/<id>.json` is written.
- `alpi/gateway/platforms/imap.py`, `alpi/gateway/platforms/gmail.py` — every inbound email body is wrapped with an `[external email — UNTRUSTED…]` warning + `scan_injection` result before reaching the LLM.
- `alpi/tools/browser.py` — Playwright `context.route` handler revalidates every navigation/subresource via `check_url`; redirects to private/loopback are aborted regardless of the initial check.
- `alpi/mcp/client.py` `_fetch_tools` — third-party MCP tool descriptions go through `scan_injection` and gain a one-line warning prefix when patterns match.
- `alpi/model_selector.py` — `_append_env`/`_remove_env_key` now write atomically via temp + `os.replace` and `chmod 0600`.
- `alpi/tools/send_message.py` — attachment paths run through `_paths.resolve_path` (same denylist as `email(send)`); rejects sensitive paths instead of forwarding them to delivery.
- Tests: `test_alp_envelope.py` (+5 binding cases), `test_mcp.py` (+2 env scoping), `test_guards.py` (+2 multi-A/scheme), `test_redact.py` (9 new).
- `docs/SECURITY.md` — Layer 1 entries updated to reflect what the audit closed.

## v0.3.7 — 2026-04-28 — Email PGP + test env isolation fix

Closes Email PGP from v0.4. Outbound IMAP/Gmail messages are
signed with the configured key and encrypted when every recipient
has a public key on `~/.gnupg`; inbound `multipart/encrypted` is
decrypted before the agent reads it. Default off. Also fixes a
test fixture that copied the dev's real `~/.alpi/.env` into every
test home, leaking `TELEGRAM_BOT_TOKEN` + API keys into
`os.environ` for the test process.

- `alpi/mail/pgp.py` — RFC 3156 PGP/MIME wrapper around `python-gnupg`; passthrough to plaintext on any failure.
- `alpi/mail/imap.py`, `alpi/mail/gmail.py` — wrap on send + decrypt on read; Gmail re-fetches `format=raw` when encrypted.
- `alpi/mail/pgp_setup.py` — wizard step at tail of `alpi setup → Gateways → IMAP`/`Gmail`. macOS+brew offers `brew install gnupg`; Linux/Windows print the right hint and skip. Defensive top-level wrap so PGP can never break the gateway flow.
- `tests/conftest.py` — `tmp_home` no longer copies `.env`. New autouse scrub of TELEGRAM/API/IMAP/SMTP env vars. `tmp_home_with_real_env` fixture isolates real-creds behaviour to `--llm` tests only.
- `pyproject.toml` — `python-gnupg>=0.5`.
- `tests/test_mail_pgp.py` (10) + `tests/test_mail_pgp_setup.py` (14).

## v0.3.6 — 2026-04-28 — terminal subprocess env scoping (AV)

Closes roadmap AV. The `terminal()` tool now starts every
subprocess with an explicit `env=` dict instead of inheriting
the parent's `os.environ` — a prompt-injected skill running
`terminal('env')` no longer sees `OPENAI_API_KEY` or any other
secret. Skills opt back into specific vars via `SKILL.md`
frontmatter `env: [FOO]`, scoped per-turn.

- `alpi/tools/terminal.py` — `_SAFE_ENV_KEYS` safelist + `_build_subprocess_env()`; both fg + bg subprocess sites pass `env=`.
- `alpi/tools/_state.py`, `alpi/engine.py` — per-turn allowlist ContextVar, reset at turn start.
- `alpi/tools/skill.py` — frontmatter `env:` parsed on view; sub-file reads don't register.
- `tests/test_skill_env_scoping.py` — 9 tests including real `terminal('env')` subprocess assertions.

## v0.3.5 — 2026-04-28 — TUI input responsiveness + multi-line paste

Closes roadmap BG early. Two compounding daily-UX TUI bugs:
typing lagged during streaming because every delta re-parsed
markdown via `Markdown.get_stream().write()`, and multi-line
paste delivered only the first line because Textual's `Input`
hardcodes `splitlines()[0]`. Fix renders in-flight tokens into
a cheap `Static` and swaps to `Markdown` once finalised; a
`ChatInput` subclass flattens pasted newlines to spaces.

- `alpi/tui/widgets.py` — `AssistantMessage` rewritten: streaming `Static` updated every 0.15s, `replace()` swaps to `Markdown` at finalise (idempotent via `_finalized`); spinner ticks dropped 6Hz→4Hz. New `ChatInput(Input)` overrides `_on_paste` with `event.prevent_default()` + `event.stop()`.
- `alpi/tui/app.py` — composes `ChatInput`; non-streaming callsites use `replace()` so markdown lands immediately.
- `tests/test_tui_streaming_perf.py` — gated `@pytest.mark.perf` fixture: 240 tokens at 60 tok/s with key injection, asserts per-keystroke p99 < 50 ms (observed 1–9 ms).
- `pyproject.toml` — `perf` marker registered.

## v0.3.4 — 2026-04-28 — workgroup hardening for tier-2 models

Workgroups now keep workflow shape on tier-2 models
(`gpt-5.4-nano`). Three failures fixed: members closing tasks
they couldn't close, infinite refinement loops, deadlocks when
every peer was caught up. Discipline moves from per-workgroup
briefings (which small models ignored) into protocol +
dispatcher. A 12-post nano run that previously looped now
closes at post 6.

- `alpi/alp/tasks.py` — `parse_post`/`active_task` gain optional `hub_pubkey` filter; non-hub markers ignored. New `has_markers()` helper.
- `alpi/alp/workgroup_client.py` — `post()` rejects non-hub `#task`/`#done` client-side with `ValueError`.
- `alpi/alp/agent_context.py` — `WORKGROUP_GUARDRAILS` rewritten with role-conditional rules: members default-silent unless `@`-named, hub must close after 4+ posts with no new evidence.
- `alpi/service.py` — `_build_role_aware_addendum()` (state-aware dispatcher cue), `_maybe_watchdog_close()` (180s stale-task force-fire), `turn_log_path()`/`_append_turn_event()` (append-only `start`/`end`/`timeout` events at `~/.alpi/profiles/<x>/alp/turns.jsonl`, mode 0600), hard 300s `asyncio.wait_for` turn timeout with SIGTERM→SIGKILL.
- `alpi/cli.py` — new `alpi workgroup turns [<wg_id>] [-f]` command.
- `tests/test_alp_tasks.py`, `test_alp_workgroup_client.py`, `test_alp_workgroup_poller.py`, `test_alp_agent_context.py` — hub-pubkey filter, SDK rejection, telemetry, timeout path.
- `tests/manual/test_money_workgroup.py` — new 3-peer nano demo; `docs/ALP.md` — protocol + autonomous engagement updates.

## v0.3.3 — 2026-04-28 — workgroup poller + capability fixes

Two ALP.3 bugs kept workgroups from cycling: a hub posting
`#task` in its own workgroup didn't wake its local agent, and
joiners couldn't pull because `workgroup.join` doesn't add
`workgroup.*` to the peer's `allow:`, hitting `-32001
capability-denied`. Also extracts curated provider model lists
into shared YAML for the desktop app + adds two hidden `chat`
flags for desktop GUI drive.

- `alpi/service.py` — `_should_dispatch` rewritten to scan every unacknowledged post; priority: explicit `@<profile>`, collective `#task`, active-task participant. Self-authored non-task posts shadow earlier triggers.
- `alpi/alp/peers.py` — `Peer.may_call` bypasses per-peer `allow:` for `workgroup.*`; membership is the real gate.
- `docs/ALP.md`, `alpi/skills/knowledge/references/alp.md` — clarifies bypass.
- `tests/test_alp_workgroup.py`, `test_alp_workgroup_poller.py` — rewritten + collective-task wake test.
- `alpi/providers/curated_models.yaml` (new) + `curated.py` (loader) — single source of truth, replacing inline `_CURATED` tuples in `openai.py`/`anthropic.py`. `pyproject.toml` ships `providers/*.yaml`.
- `alpi/cli.py` — `chat` gains hidden `--session-id` and `--model` (per-turn, not persisted).

## v0.3.2 — 2026-04-27 — `@peer` and doctor reach remote peers

Two bugs kept ALP.2 (TCP/Noise) traffic from working in
practice. A peer pinned with `address:` (the canonical "remote
machine" signal) was rejected by the highest-traffic code
paths and misreported by the health check, so a Tailscale-
exposed peer looked unreachable from outside even when its TCP
listener was accepting Noise handshakes.

- `alpi/alp/mention.py` — `execute()` routes through `alp_client.call_peer()` when `address:` is set; removes the "@<id> is remote — ALP.2 pending" rejection.
- `alpi/tools/peer.py` — docstring + tool description no longer claim "intra-machine only".
- `alpi/doctor.py` — `_check_alp` reuses `setup._probe_all` to fire `link.ping` over TCP for remote peers; reachable Tailscale peers now show `1/1 reachable`.
- `tests/test_alp_mention.py` — new `test_execute_routes_remote_peer_over_tcp` asserts TCP path with right `peer_id`/`method`/`params`.

## v0.3.1 — 2026-04-27 — brand accent unified

Single brand accent `#c8a24e` across every alpi surface. TUI
dropped its orange `#ff8800`, the marketing site dropped
`#a89b76`, and both adopt the warmer gold the desktop app uses.
Existing profiles with custom `tui.accent` keep their override.

- `alpi/config.py`, `alpi/cli.py`, `alpi/tui/app.py` — default `tui.accent` literal updated to `#c8a24e`.
- `alpi/skills/knowledge/references/config.md`, `docs/CONFIG.md` — config reference reflects new default.
- `site/templates/demo.css`, `site/templates/landing.html` — hero/playwright console + mono note recoloured.

## v0.3.0 — 2026-04-26 — public release

First public release of alpi: installable from PyPI
(`uv tool install alpi-agent`); docs, site, and onboarding
stable for external users. The v0.3 cycle stacked the work
that makes alpi usable beyond a single hacker on a laptop.
Per-patch detail preserved in v0.2.x entries below.

- ALP shipped end-to-end: ALP.1 (Unix sockets), ALP.2 (Noise_XK over TCP, rate limits + budgets), ALP.3 (workgroups: hub state, pause/resume, leave + rekey, member bios, `@<peer>` mentions anywhere).
- Service unification — one `alpi service` per profile hosts gateway, scheduler, ALP listener.
- Distribution — `alpi-agent` on PyPI with publish workflow; `alpi update` + version badge in doctor + TUI top bar.
- `@alpi/knowledge` — first bundled skill ships alpi's own docs.
- Browser tool — Chromium downloads itself on first use.
- Security & budget — profile `.env`/`config.yaml` off-limits to file tools and terminal; daily spending ledger with profile-level cap.
- UX + site — wizard headings + copy pass, TUI markdown link style, `/memory` rewrite, streaming lag fix, Delete profile, "did you mean" polish; landing + 15 docs pages, OG + JSON-LD, demo widget.

## v0.2.97 — 2026-04-26

### `@alpi/knowledge` — first bundled skill

alpi's first bundled skill bundles 12 user-facing docs as
package resources so the agent answers questions about alpi
without `web_search` or training-data guesses. SKILL.md
carries a topic→reference routing table; skills index has an
imperative rule biasing small models (~70% follow on nano).

- `alpi/skills/knowledge/` — wheel resources (README/QUICKSTART/INSTALL/PROFILES/SKILLS/MODELS/ALP/ARCHITECTURE/CONFIG/SECURITY/DEPLOYMENTS/OPERATIONS); CHANGELOG/ROADMAP/RELEASE/LICENSE excluded.
- `scripts/sync_knowledge.py` — keeps `references/` in lockstep with `docs/` + READMEs.
- `tests/test_alpi_knowledge.py` — 10 cases. Suite at 911 (was 901).
- `docs/SKILLS.md`, `QUICKSTART.md`, `docs/ROADMAP.md` — "Why ship skills" section, curation policy, **BE** for v0.4.

## v0.2.96 — 2026-04-26

### `@<peer>` mentions match anywhere in the text — ALP.3.1

The `@<peer>` shortcut now fires anywhere in the text — `"hey
@mirai can you check?"` pings mirai naturally. Boundary rules:
`@` must follow whitespace or be at position 0
(`email@gmail.com` skips), and the id must resolve to a pinned
peer (`@property` falls to LLM). `#task`/`#done` stay strict
line-start — state-change markers must not fire by accident.

- `alpi/alp/mention.py::parse` — relaxed regex + optional `home: Path` for roster validation; backward-compatible.
- `alpi/tui/app.py`, `alpi/gateway/run.py` — dispatch no longer gates on `text.startswith("@")`.
- `tests/test_alp_mention.py` — 14 cases (mid-text, email immunity, multi-mention first-wins, roster check). Suite: 901 (was 894).
- `docs/ALP.md` — Recognition rule distinguishes attention vs state-change markers.

## v0.2.95 — 2026-04-26

### `alpi update` — version check and self-upgrade

alpi tells you when there's a new release on PyPI. Daemon
thread on every `alpi` invocation (8h TTL) writes
`~/.alpi/cache/update_check.json`; `doctor` + TUI top bar read
the cache. `alpi update` bypasses the cache, detects install
method (uv tool / pipx / dev), upgrades, verifies new version
matches PyPI.

- `alpi/updater.py` (new) — version compare (handles `0.2.10 > 0.2.9`), cache I/O, 3s-timeout daemon, install-method detect.
- `alpi/cli.py` — `alpi update [--check|-y]`; `alpi/doctor.py`, `alpi/tui/app.py` — Version row + accent badge.
- Env: `ALPI_SKIP_UPDATE_CHECK=1` (autouse fixture sets it), `ALPI_UPDATE_INDEX` for TestPyPI.
- `tests/test_updater.py` — 26 cases mocked at `httpx.Client`. Suite: 894 (was 868).
- `docs/INSTALL.md`, `docs/ARCHITECTURE.md`, `README.md`, `docs/ROADMAP.md` (AU 1+2 ticked).

## v0.2.94 — 2026-04-26

### browser tool — Chromium downloads itself on first use

The browser tool already JIT-installed Chromium on first run;
docs hadn't caught up and still told users to run `playwright
install chromium` themselves. Aligns docs with code: no
separate install step, ~200MB download cached at
`~/.cache/ms-playwright/`, users who never browse pay nothing.

- `alpi/tools/browser.py` — install banner now writes to stderr (avoids stdout pollution under `chat --once` / gateway); `playwright import failed` message points at `uv tool install alpi-agent --reinstall` instead of `pip install playwright`.
- `tests/test_browser.py` — `test_launch_chromium_installs_on_first_run` (raise→install→retry), `test_launch_chromium_propagates_unrelated_errors` (JIT path is for binary-missing only). Suite: 868.
- `README.md`, `QUICKSTART.md`, `docs/INSTALL.md`, landing — drop the manual playwright install step.

## v0.2.93 — 2026-04-26

### distribution — first PyPI publish path

Installable from PyPI as `alpi-agent` — closes **AU**. CLI
binary + Python import + `~/.alpi/` stay `alpi`. Auto-publish
on push to `main` when `pyproject.toml` version differs from
PyPI; smoke install across 5 container images (Python
3.10/3.11/3.12-slim, Ubuntu 22.04, Debian 12); OIDC Trusted
Publisher; auto-tag + GitHub release with CHANGELOG body.

- `.github/workflows/publish.yml` — version-delta gate, `uv build`, `twine check`, multi-image smoke, OIDC publish; `workflow_dispatch` preserved for TestPyPI (idempotent).
- `pyproject.toml` — PEP 639 SPDX (`license = "BUSL-1.1"` + `license-files`), `[project.urls]`, classifiers, keywords.
- `docs/INSTALL.md` (new) — uv/pipx/dev/update/uninstall/troubleshooting + "no curl|bash" stance.
- `docs/RELEASE.md` (new) — maintainer cut checklist.
- `QUICKSTART.md`, `README.md`, `docs/ROADMAP.md`, landing — install step + `INSTALL` in docs grid (slug 02; subsequent renumbered).

## v0.2.92 — 2026-04-26

### self-published member bios in workgroups

Each profile carries an optional one-line `public_bio` that
propagates to every workgroup it joins. Surfaces in roster as
`@alice (online, "product engineer — velocity")` so agents see
who-does-what from turn 1. AGENT.md stays private. Inverts
earlier creator-assigned `roles` (which didn't scale).

- `alpi/config.py` — new `public_bio: str` (empty = unpublished).
- `alpi/alp/workgroup.py` — `workgroup.join`/`create` accept `bio`/`hub_bio` (capped 200 bytes); `pull` returns `bio` per member; re-joining refreshes.
- `alpi/cli.py` — `alpi setup → ALP → Identity` inline edit; `clear` unsets, `draft` synthesises from AGENT.md via one-shot LLM.
- `tests/test_alp_workgroup_client.py`, `tests/test_alp_agent_context.py` — 6 new cases. Suite: 866 (was 860).
- `tests/manual/` (new) — moves alice+bob convergence test out of `scripts/`; `norecursedirs` excludes from collection.

## v0.2.91 — 2026-04-26

### alp.3 — workgroups (PR 5): functional autonomy

Closes ALP.3. Workgroups self-drive: each member's service
polls the hub on a 30s tick and dispatches one engine turn
when a post mentions them, opens a collective `#task`, or
names them in the active task. 60s per-workgroup cooldown
rate-limits ping-pong. Suite: 860.

- `alpi/alp/agent_context.py` (new) — pre-turn hook injects briefing + active task + last 5 posts + roster + `WORKGROUP_GUARDRAILS` into every engine turn. Guardrails: silence default; accept/counter/block peer proposals (not more research); `#done` on convergence.
- `workgroup_post` auto-declares turn USD/tokens via ContextVar; hub-of-itself short-circuit writes directly to local transcript.
- `alpi/alp/workgroup.py` — `Meta.briefing`, `auto_kickoff`, `notify_on_close`; `Member.last_seen_at` stamped on `pull`/`post`; `#task`/`#done` parsed client-side (hub zero-knowledge).
- `alpi/service.py` — TCP bind failure falls back to unix-only with warning; `_supervise` per subsystem.
- `tests/test_alp_agent_context.py`, `test_alp_tasks.py`, `test_alp_workgroup_poller.py`, `test_state_turn_usage.py`.

## v0.2.90 — 2026-04-25

### service unification — one process per profile

Three legacy daemons (gateway, scheduler, ALP) collapse into a
single `alpi service` per profile. One asyncio loop hosts every
enabled subsystem — one PID, one log, one launchd/systemd
unit. Memory drops ~2/3. Every profile now starts opt-in
(auto-install of scheduler removed, aligning with sandbox /
budgets / peers).

- `alpi/service.py` (new) — orchestrator; `serve(home, profile)` builds asyncio task per enabled subsystem, signal handlers, cooperative cancel; owns install/uninstall (single plist/unit).
- `alpi/cli.py` — `alpi service {start,stop,restart,status}`; removes `gateway`/`alp` groups; `schedule` keeps `run-once`/`fire` only.
- `alpi/gateway/run.py`, `alpi/scheduler/run.py` — expose `async def serve(home)`; StreamHandler only on TTY (avoids double-logging under launchd/systemd).
- `alpi/config.py`, `alpi/doctor.py` — new `service: {gateway, schedule, alp}` toggles (default all-on); wizard replaces 3 entries; `_check_services` collapses to one row. `setproctitle` → `ps aux` shows `alpi (<profile>)`.
- Tests — drops `test_daemon_ops.py`, `test_bootstrap_autoinstall.py`, legacy `test_service.py` (~30); adds 20 new (backend selection, install/uninstall, toggle defaults, PID stale-cleanup, etime parser). Suite: 804 passed, 8 skipped.

## v0.2.89 — 2026-04-25

### alp.3 — workgroups: pause/resume + member state + management UX

Protocol gains `workgroup.pause`/`resume` (idempotent; `post`
returns `-32010 workgroup-paused`; `pull`/`join`/`leave` keep
working — pause must not trap members). Members get their own
`Subscription` state + full management surface. Hub identity
is explicit per subscription (probing pinned peers would leak
the id and let a malicious peer impersonate by pre-creating a
same-id workgroup).

- `alpi/alp/workgroup.py` — `Meta.paused`/`paused_at`/`paused_by`; new `pause`/`resume` handlers.
- `alpi/alp/subscription.py` (new) — `~/.alpi/<profile>/alp/secrets/subscriptions.yaml` (0600); per-wg record (`wg_id`, `name`, `hub_id`, `hub_pubkey`, sealed keys, `last_seq`). Sealed keys stay sealed on disk.
- `alpi/alp/workgroup_client.py` (new) — member-side `join`/`post`/`pull`/`leave`/`pause`/`resume`; transport-resolved via `peers.yaml`; refreshes sealed key on rotation.
- `alpi/cli.py` — `alpi workgroup` group (9 verbs split by role); `setup → ALP → Workgroups` wizard (Hub-of/Member-of, Read messages, alias-aware Members, edit-in-place Budget, create auto-grants 6 verbs).
- Workgroup budget validation relaxed: both `max_usd` + `max_tokens` may be set. Agent tool `workgroup_post` minimal (auto-pull/briefing → PR 5). `tests/test_alp_workgroup.py` (9 new pause/resume) + `test_alp_workgroup_client.py` (8 new). Suite: 817 (was 800).

## v0.2.88 — 2026-04-25

### alp.3 — workgroups (PR 2: leave + rekey + lifetime budget)

Members can leave; hub rotates the group key for remaining
members (forward secrecy: old key opens past posts, fails on
new ones). Optional **lifetime** budget (USD or tokens,
project-scoped, no daily reset) — posts double-gate on top of
profile cap. Profile gate fires upstream of workgroup gate.

- `alpi/alp/workgroup.py` — `Member.key_version` + `Meta.current_key_version`; `_rekey()` mints fresh 32-byte key, re-seals per remaining member; `workgroup.leave` (hub can't leave own wg, `-32602`); `pull` includes `current_key_version` + caller's sealed key for in-band rekey detect; `post` accepts `key_version` + optional `cost: {usd, tokens}`; `_validate_budget` enforces `max_usd` xor `max_tokens` positive; `ledger.json` accumulates `{usd, tokens, posts}`. `kick(home, wg_id, target_pubkey)` hub-side primitive. Cap hit returns `-32005` with `data.cap_kind = "workgroup_usd"`/`"workgroup_tokens"`.
- `docs/ALP.md` — `leave`, `key_version`/`cost` on `post`, rekey-via-pull, "Group-key versioning", project-lifetime cap with author-declared cost trust model.
- `tests/test_alp_workgroup.py` — 15 new (forward-secrecy, hub-can't-leave, kick rotation, budget shape, USD/tokens admit-then-block, ledger init, v1→v2→v3 monotonic, concurrent post+leave, profile gate upstream). PR 1's 20 still green. Suite: 804 (was 789).

## v0.2.87 — 2026-04-25

### alp.3 — workgroups (PR 1: hub state + 4 core verbs)

Hub side of shared workgroups: profile can `create` with a
chosen roster; pinned remote peers `join`/`post`/`pull` over
existing ALP transport (Unix or Noise_XK/TCP). End-to-end
encrypted: hub stores ciphertext, group keys sealed per-member.
Suite: 789 (was 769).

- `alpi/alp/workgroup.py` (new, ~430 lines) — Crypto: ECIES seal X25519 (Ed25519→X25519 birational) + HKDF-SHA256 + ChaCha20-Poly1305 with AAD contexts (`b"seal"`, `b"post"`). Storage: `~/.alpi/<profile>/alp/workgroups/<wg_id>/` with `meta.yaml`, `members.yaml`, append-only `transcript.jsonl`; IDs `wg_<base32(16 random)>`. Verbs: `create()` local; `register()` wires `workgroup.join`/`post`/`pull`. New error codes `-32008 workgroup-not-member`, `-32009 workgroup-not-found`.
- `alpi/cli.py` — `alpi alp start` registers handlers alongside `link.ask`.
- `docs/ALP.md` — concrete signatures (`workgroup.post(wg_id, nonce, ciphertext)` — encryption client-side); sealing scheme.
- `tests/test_alp_workgroup.py` — 20 new (crypto round-trip + isolation, end-to-end Unix + Noise/TCP, 3-alpi multi-member, `asyncio.gather` concurrent posts, restart persistence, error paths).

## v0.2.86 — 2026-04-25

### setup wizard — section headings + copy pass

`alpi setup` main menu splits into 5 sections (Agent,
Boundaries, Messaging, ALP, Maintenance); model picker into
Local/Cloud/Manage. Headings non-selectable, verbatim
rendering, auto-spaced. Copy pass across the wizard —
Sandbox/Workspace/Budget/TCP-port dim blocks trimmed to 3–6
lines; daemon-service wizards reduced to one line each.

- `alpi/ui.py` — new `Heading(NamedTuple)`; `menu()` adds blank rows, keeps cursor off.
- `alpi/cli.py::setup_cmd` — flat 13/14-item list rewritten as 5 sections; `_delete_profile_status` copy trimmed.
- `alpi/model_selector.py` — Local/Cloud/Manage grouping; Manage only when removable items exist.
- `tests/test_ui_menu.py` — 4 cases (heading shape, non-selectable mask, verbatim text, no-leading-blank). Suite: 769 passed, 8 skipped.

## v0.2.85 — 2026-04-25

### security — profile `.env` and `config.yaml` off-limits to tools

File tools and `terminal` refuse to read/write the active
profile's `.env` and `config.yaml` (provider API keys, gateway
tokens, sandbox flag, allowlist). A prompt-injected mailbox or
page can't coax the agent into leaking or rewriting them; they
stay editable by hand or `alpi setup`. Workspace `.env`
outside `~/.alpi/` deliberately untouched (path-scoped, not
basename-scoped).

- `alpi/tools/_paths.py` — denylist regex matches `~/.alpi/.env`, `~/.alpi/config.yaml`, and same under `~/.alpi/profiles/<name>/`.
- `alpi/tools/_guards.py` — three patterns: read profile secret (cat/head/tail/cp/scp/grep/awk/sed/xxd/...), write profile config (`>`/`>>`/`tee`), dump env (bare `env`/`printenv`). `env VAR=x cmd` and `printenv HOME` allowed.
- `tests/test_guards.py` (12 reject + 6 allow), `tests/test_paths_denylist.py` (12). Suite: 765 (was 734).
- `docs/SECURITY.md` § Layer 1 — new patterns + note skill scripts still run inside parent's `os.environ` (closed in v0.3.6 / AV).

## v0.2.84 — 2026-04-25

### budget — daily spending ledger, profile-level cap

Every spend path flows through one ledger + one cap
(`budget.daily_usd` or `daily_tokens`); per-peer sub-caps
dropped — peer trust lives in capabilities + rate limits.
Verified live on bob with `daily_usd: $0.05`; `/status` reads
`daily budget $0.0554 / $0.05 · capped`.

- `alpi/ledger.py` (new) — JSON at `~/.alpi/<profile>/logs/ledger.json`; profile total + per-peer buckets, atomic writes, midnight UTC reset, ContextVar attributing turn spend to remote peer.
- `alpi/engine.py` — admit-check before every turn; record after turn body + each sub-agent (`research`, `delegate`, `read_image`).
- `alpi/alp/server.py` + `handlers.py` — inbound `link.ask` admits; over-cap returns `-32005 budget-exceeded` (`cap_kind`/`cap`/`used` in `data`).
- `alpi/cli.py` — `alpi setup → Budget` prompts daily USD or tokens (pick-one); `alpi/status.py` (new) shared rows for TUI + Telegram `/status`.
- `tests/test_ledger.py` (15), `test_alp_budget.py` (3), 1 status-panel test. Suite: 734.
- Renames "alpi-rooms" → "workgroup" across ALP/CONFIG/PROFILES/OPERATIONS/ARCHITECTURE/ROADMAP.

## v0.2.83 — 2026-04-24

### alp — inter-machine Noise_XK transport, rate limits, wizard

Inter-machine half of ALP. Peers with `address` in
`peers.yaml` route over TCP+Noise_XK; ALP.1 Unix socket
untouched. New roadmap **BG** scopes v0.3 budget shape (one
ceiling per profile, `daily_usd` or `daily_tokens`).
Verified on same host and over Tailscale via MagicDNS.

- `alpi/alp/noise.py` — own `Noise_XK_25519_ChaChaPoly_SHA256` on `cryptography` primitives; Ed25519→X25519 birational so peers keep one pinned identity.
- `alpi/alp/transport_tcp.py` — TCP framing (u16 handshake, u32 bulk capped 1 MiB), pinned-key cross-check between Noise-authenticated static and `peers.yaml`.
- `alpi/alp/rate_limit.py` — sliding-window per peer, default 60/min overridable. Over-cap returns `-32005`.
- `alpi/alp/server.py`, `client.py` — TCP listener alongside Unix when `alp.tcp_port` set; new `call_tcp()`/`call_peer()`.
- `alpi/config.py`, `alpi/cli.py` — new `alp` section + `alpi setup → ALP → TCP port` wizard (`0.0.0.0` behind confirm); `alpi alp start --port --host`; `alpi peers ping` routes over TCP.
- `tests/test_alp_noise.py` (17), `test_alp_tcp.py` — handshake happy/tamper, bulk, ping, `-32005`, capability denial. Suite: 715.

## v0.2.82 — 2026-04-24

### site/docs — private agent network narrative + tool polish

Public narrative matches product shape: alpi is a profile-
based personal AI that grows into a private network across
machines. Third pass on AT (prompt + tool descriptions audit
against comparable persistent-agent behaviour) — three targeted
additions.

- `README.md` — leads with profiles, model/key ownership, multi-machine coordination, current ALP surface.
- Landing + docs — "your private / agent network"; ALP.1/.2/.3 stated directly across ALP/Deployment/Security/Operations/Profiles/Config/Roadmap.
- `alpi/tools/browser.py` — "re-check snapshot for real role/name when click/type can't find element" hint (stops blind selector retries).
- `alpi/tools/search.py` — regex-metachar gotcha (`{ } ( ) | . * +` need escaping in content mode).
- `alpi/tools/stt.py` — "Use when" preamble so gateway voice notes trigger transcription.

## v0.2.80 — 2026-04-24

### site — header/nav unified, docs index redesigned, SEO at 100%

Second pass on the static site under `site/`. Single shared
nav across landing/`/docs/`/`/docs/*`; combined logo + alpaca
favicon; burger menu under 760px in <20 lines inline JS. SEO
across every page: unique title/description, canonical, Open
Graph, Twitter Card with `@soyjavi`, JSON-LD, `sitemap.xml`
(16 URLs with `lastmod`) + `robots.txt` on every build.

- `site/scripts/build.mjs` — `renderNav()` shared shell (1240px + `clamp(24px, 5vw, 64px)`); breadcrumb tail varies (DOCS, DOCS/{slug}); fixes nested `<a>` bug.
- `site/dist/` — three assets (logo, alpaca, social card 1200×800); `/docs/` rebuilt with `.docs > .doc` card grid, H1 72px/600/-.035em.
- `SITE_URL` env var configurable, default `https://alpi.satoshi-ltd.com`.

## v0.2.79 — 2026-04-24

### site — static marketing + docs scaffold under `site/`

First cut of alpi.site as zero-dependency static site: vanilla
HTML/CSS/JS + single Node build script reads `README.md`,
`QUICKSTART.md`, `CHANGELOG.md`, `LICENSE`, `docs/*.md` at HEAD
and bakes `site/dist/` — landing at `/`, doc index, one
pre-rendered HTML per doc. Versions derived from
`pyproject.toml`; no runtime fetch, CORS, or rate limits.

- `site/scripts/build.mjs` — Node build entry.
- `site/scripts/markdown.mjs` — zero-dep renderer (headings, fenced code, lists, tables, blockquotes, inline code, bold/italic, links).
- Cloudflare Pages: build `node site/scripts/build.mjs`, output `site/dist`. Based on a `claude design` mockup (mockup folder removed after migration).

## v0.2.78 — 2026-04-24

### skills — auto-validate on every mutation

Every mutating action on a user skill (`create`/`edit`/`patch`/
`add_file`/`remove_file`) runs `_skill_validate.validate_skill`
(py_compile, missing imports, OAuth race, port coherence) and
surfaces findings inline so the LLM iterates without a
separate `validate` call. Reverted the `@alpi/plan` experiment
— `@alpi/*` stays reserved + live, but nothing ships by
default until concrete patterns justify it.

- `alpi/tools/skill.py` — auto-validate hook on each mutation.
- `alpi/prompts/create_skill_guide.md` — Scripts section (prefer stdlib, dry-run/smoke, exit codes) + auto-validation note.
- `tests/test_skill_auto_validate.py` — 6 regression tests.
- `docs/ROADMAP.md → AO`, `docs/SKILLS.md` — bundled-skill position clarified.

## v0.2.77 — 2026-04-24

### skills — bundled infrastructure (BE closed)

Read-only namespace for skills shipped with the alpi package;
no content bundled yet, infrastructure only. Bundled skills
addressed as `@alpi/<name>`; `@` not legal as on-disk category
so collisions impossible. Suite: 692.

- `alpi/tools/skill.py` — `_bundled_root()` via `importlib.resources.files("alpi.skills")`; `_bundled_skill(name)` returns package resource for `@alpi/*` or `None`. `_find_skill` tries bundled first. Discovery: `skills_index_block()` + `skill list` lists user skills then `@alpi/ [bundled]:`. Write guards reject mutating actions on `@alpi/*`. `all_skills` skips on-disk categories starting with `@`.
- `pyproject.toml` — package-data ships `skills/**/*`; `alpi/skills/` empty except `__init__.py`.
- `tests/test_bundled_skills.py` — 14 regression tests.
- `docs/SKILLS.md` "Bundled vs user skills"; `docs/ARCHITECTURE.md` package tree updated.

## v0.2.76 — 2026-04-24

### tui — markdown link styling + memory panel rewrite (BB closed)

Textual 8.2.3 exposes only `@click` meta on markdown link
spans, no style — links rendered as plain prose. Fix monkey-
patches `MarkdownBlock._token_to_content` at import to add
bold+underline on `@click` spans (idempotent, global).
`/memory` panel replaces the code-block hack with stacked
`Static` headers + per-entry `Markdown` widgets split on `§`.
Streaming input lag fixed by 12.5Hz timer coalesce vs ~60/s
`asyncio.create_task` per delta.

- `alpi/tui/_links.py` (new) — monkey-patch; `alpi/tui/widgets.py` — `/memory` rewrite + `_FLUSH_INTERVAL = 0.08` coalesce; new `.memory-section` CSS.
- `alpi/prompts/default_agent.md` — `# Identity`/`# Voice`/`# Defaults` → `##` (Textual centers `h1`).
- `alpi/tools/memory.py` — `§` guidance tightened; `fuzzy_find_unique_entry` adds "`§` is delimiter" hint. `docs/ROADMAP.md` — BF removed.

## v0.2.75 — 2026-04-24

### wizard / cli — profile lifecycle + polish

New `alpi -p <name> setup → Delete profile` (non-default
profiles only) — one-shot teardown: summary → service warning
→ typed-name confirmation → uninstall services → `rmtree` →
exit. Collapses what was "uninstall each service manually,
then `alpi profile remove`" into a single guided action.
"Did you mean…?" suggestions across `profile remove`, `peers
remove`/`ping`, `schedule fire` via shared `_suggest()`
(`difflib`).

- `alpi/cli.py` — Delete profile wizard; `profile remove` redirects to wizard when services installed; `_suggest()` helper; fixes the misleading "→ Gateway service" hint.
- Dropped `.githooks/` (pre-push CHANGELOG regen — opt-in and unused).
- `docs/PROFILES.md`, `docs/ARCHITECTURE.md` — wizard-redirect flow + setup menu.

## v0.2.74 — 2026-04-24

### schedule — ad-hoc job fire (BA closed)

Closes the tightest feedback loop in schedule lifecycle: add
cron, verify it works, without waiting for the cron window.

- `alpi/scheduler/run.py::fire_by_id(home, job_id)` — runs the job through the same path as the daemon tick (threat scan + `alpi chat --once` subprocess + delivery); updates `last_run_at`; does **not** consume `once` jobs (ad-hoc fire is testing).
- `alpi/cli.py` — `alpi schedule fire <job_id>` (exit 1 on failure).
- `alpi/tools/schedule.py` — `schedule(action="fire", id=...)` so the LLM can self-test after adding.
- `tests/test_schedule.py` — 5 new tests. Suite: 675.

## v0.2.73 — 2026-04-24

### skills / memory / docs — stop shipping what we don't use

Deleted the `alpi/skills/` package — only blueprint
(`meta/consolidate-memory/SKILL.md`) never reached profiles
(skill tool only searches `{home}/skills/`). Runtime skills
system untouched — `~/.alpi/skills/<category>/<name>/` still
works.

- `pyproject.toml` — package-data no longer includes `skills/**/*.md`.
- `alpi/tools/memory.py`, `alpi/prompts/system_prompt.md`, `create_skill_guide.md` — ≥80% hint now says "consider consolidating old entries" instead of pointing at a non-existent skill.
- `docs/ARCHITECTURE.md` — package tree updated; bridge paragraph to Profile home layout.
- `docs/ROADMAP.md` — **BE** reframed as "bundled skills infrastructure (loader; no content yet)"; **AO** drops consolidate-memory bundling claim.
- `tests/test_memory_tool_v2.py` — two regressions assert new wording.

## v0.2.72 — 2026-04-24

### memory — v2 rules (AI partial)

Renames `PERSONALITY.md` → **AGENT.md** across codebase /
prompts / tests / docs (user/agent pair now symmetric). File
migration manual per project policy. Char limits: USER.md
1375→3000, MEMORY.md 2200→5000.

- **A** — AGENT.md uses paragraph-fold + Jaccard dedup (`is_duplicate_stanza` in `alpi/memory.py`); paraphrased voice blocks no longer accumulate.
- **B** — `alpi/prompts/default_agent.md` "Edit me" footer rewritten teaching `replace` vs `add`.
- **C** — cross-file dedup: `add` to USER.md/MEMORY.md rejects when content is already in the other.
- **E** — operational-state ⚠ warning when entry matches session/chat log pattern (non-blocking).
- **F** — `≥80%` usage triggers "run consolidate-memory skill" hint.
- **D**/**G deferred** — Jaccard 2→1 produced false positives (`Dato A`/`Dato B` collapsed to `{dato}`); periodic self-consolidation out per "no over-engineering".
- `tests/test_memory_tool_v2.py` — 11 new regressions.

## v0.2.71 — 2026-04-24

### engine / prompts (AT partial — 4 of 5 candidate edits applied)

Per-surface platform hint: `_platform_hint()` in
`alpi/engine.py` reads `ALPI_PLATFORM` and injects a matching
block (`cron`/`telegram`/`email`/`gmail`). Cron jobs stop
asking phantom users for clarification; Telegram replies
arrive Markdown-aware; email replies plain-text-only. New **BD**
for v0.3 (model-aware tool-use guidance — needs `agent.log` A/B).

- `alpi/engine.py` — `_platform_hint()`; `alpi/gateway/run.py` sets `ALPI_PLATFORM=msg.platform`; `alpi/scheduler/run.py` sets `cron`. TUI no hint. 6 regression tests.
- `alpi/tools/memory.py` — declarative ✓/✗ examples ("User prefers concise replies" ✓ vs "Always reply concisely" ✗).
- `alpi/tools/skill.py`, `alpi/tools/email.py` — descriptions lead with "Use when".
- `alpi/prompts/system_prompt.md` — drops "Past conversations" (already in `session_search`). ~10 fewer tokens/turn.
- `docs/ARCHITECTURE.md` — documents `ALPI_PLATFORM` contract.

## v0.2.70 — 2026-04-23

### license + foundational docs

Repo re-licensed under **Business Source Licence 1.1**.
Licensor: Satoshi Ltd. Change Date 2030-04-23 → Apache 2.0.
Additional Use Grant for personal/research/non-commercial;
commercial production requires a licence from
`info@satoshi-ltd.com`. Repo rooted in Satoshi Ltd.'s six
operating principles, each doc mapping to its principle.

- `LICENSE`, `pyproject.toml` (`BUSL-1.1`), `README.md` License section rewritten.
- `QUICKSTART.md` (new) — first-day walkthrough (install → model → workspace → chat → resume → gateway → second profile → ALP → doctor).
- `docs/PROFILES.md` (new) — canonical reference for the core isolation primitive.
- `docs/DEPLOYMENTS.md` (new) — six topologies laptop → enterprise networks with ASCII diagrams + BSL boundaries.
- `docs/OPERATIONS.md` (new) — runbook (logs, lifecycle, upgrades, backup/restore, ALP rotation, monitoring, DR). `docs/ROADMAP.md` sanitised; dropped 64 shipped-item rows + commit table duplicating CHANGELOG.

## v0.2.69 — 2026-04-23

### models

- `docs/MODELS.md` rebuilt around a neutral 3-tier recommendation from a standalone deep-research pass (Tier 1 quality, Tier 2 cost/service, Tier 3 Ollama) with production-setup suggestions. Personal-usage section + deliberately-left-out list dropped to keep the doc unbiased.
- `alpi/config.py::seed_defaults` — fresh profile scaffold no longer pins a default model; `config.yaml` ships with `model: ""` so the setup wizard is the canonical picker.
- `docs/CONFIG.md` — empty default reflected.

## v0.2.68 — 2026-04-23

### alp (Alpi Link Protocol — ALP.1 closed)

ALP.1 ships: Ed25519 identity, signed JSON-RPC envelope with
replay cache, fail-closed peer list, Unix-socket server +
client. `link.ping`, `link.ask` (reject-fast reentrancy),
`link.cancel` (idempotent). Setup wizard health-check no
longer blocks menu render on 5–10s of probes — runs on-demand.

- `alpi/alp/` (new package) — identity, envelope, server, client, `link.*` handlers.
- `alpi/tools/peer.py` — LLM-driven cross-profile calls; TUI `@peer rest…` gesture (strict leading-`@`); `/peers` panel; gateway inbound interception hits same code path without firing local LLM.
- `alpi/cli.py` — `alpi alp start|stop|restart`; service install via `alpi setup → ALP service` (launchd/systemd); doctor sub-checks (Identity/Socket/Peers); `alpi setup → Peers` wizard with clipboard copy + ●/○/? probe status; `alpi peers key|list|add|remove|ping` for scripting.
- `docs/ALP.md` (new) — spec v1 (envelope, verbs, errors, security); `docs/ROADMAP.md`, `docs/ARCHITECTURE.md` updated.

## v0.2.54 — 2026-04-23

### gateway

- per-chat session threading (AN closed) + AU backlog entry (`e0f093d`)

## v0.2.1 – v0.2.53 — 2026-04-21 → 2026-04-23

Two days of rapid iteration after the v0.2.0 split. Patch
bumps collapsed into thematic groups; full per-commit detail
in `git log`.

- **brand** — project renamed `alf` → `alpi` across codebase, docs, config paths (~130 files).
- **TUI** — theme system + floating panels; new panels `/model`/`/mcps`/`/tools`/`/help`; profile disk size + accent diamond; `tui.auto_resume` (AL closed); dropped questionary, menus + inputs rebuilt on `prompt_toolkit`.
- **setup wizards** — normalised UX; new wizards Cleanup (AA), Gateway service install/uninstall (AB), live Doctor (AD/AE/AF), first-time help text (AG), Model wizard reordered (Ollama first); `.env.example` dropped (AP).
- **voice + gateways** — voice pack `tts`+`stt`+Telegram voice (M closed); TTS autoplay off on gateways; Gmail OAuth2 + mail tool (T closed); Telegram offset persistence + backlog catch-up.
- **tools** — `browser` Playwright with stealth + humanised typing + optional vision; `read_image` URL/SVG/model-override (D, S closed); `research`+`delegate` batch parallel (R.3), delegate write-capable (R.2), research step counter (R.1); `skill` validate action (Q closed); removed `config` tool (config user-owned).
- **security** — three-severity command gate for terminal (W closed); approval panel restyled, YOLO removed; tool budget + OSV malware check + schedule threat-scan; sandbox per-profile opt-in; `allow_network=off` blocks Python-native net tools; `tos`: removed C (Codex OAuth) and V (Anthropic OAuth) backlog.
- **release pipeline** — auto-generated CHANGELOG from git history (AC closed) + pre-push CHANGELOG hook; CLI surface shrunk; `PERSONALITY.md` → `memories/`, `gmail_token` → `secrets/`.
- **MCP + providers** — OpenAI-compat tool names, curated provider lists, context-window awareness; `/tools` skips MCP-registered (rendered in `/mcps`); Ollama first-class; generic custom slot removed.

## v0.2.0 — 2026-04-21

Foundational v0.2 cut: split CONTEXT → ARCHITECTURE + ROADMAP,
positions alf as a lighter private-agent runtime; tiered model docs; profile
propagation through tool context; new send_message + schedule
+ email + mcp subsystems; security phases 1–2.

- **docs** — `MODELS.md` (tiered model recommendations) (`df29cfc`); identity-wizard rejected (`60122b7`); CONTEXT split into ARCHITECTURE + ROADMAP, bump to v0.2.0 (`6b946e4`).
- **gateway / schedule** — stream tool traces + typing indicator (`fe3a3d4`); fail fast on bad workspace (`04bdaba`); fix immediate-fire + UTC vs local tz + duplicate delivery (`3dd4522`); kind=once + LLM time grounding (`1fc3610`); schedule daemon tool+CLI+rename from cron (`2245e42`); install/uninstall for gateway+schedule (`cd62da0`); email subsystem (`c67e618`); email gateway + per-platform config (`4691df8`).
- **skills / tools / tui** — unified skill tool + subdir contract + path guards (`2e67830`); auto-inject skill index into system prompt (`4035327`); rename delegate → research + depth tiers (`d2ceb74`); level-2 comment cleanup (`a07e40a`); inter-tool prose + reasoning tokens in indicator (`62f7fa7`); reasoning persists across sessions + show_reasoning toggle (`fd1fec4`); skill tool patch/view + state subdir (`211c022`).
- **misc** — fix profile propagation + memory prompt (`1470bdb`); send_message tool (`6e31ace`); profile CLI + drop migration (`630f97c`); mcp client (`0d376ac`); shared ui primitives (`7a81770`); memory description tightened (`b214ce6`); tool description compression (`19f1287`, `6be1685`); minimal config seed + /new session (`2dadc09`); security phase 1 — terminal denylist + SSRF + injection scan (`a54d99d`); security phase 2 — opt-in OS sandbox (`e78b428`); merge glob+grep into search (`2b73091`); file tools drop workspace wall (`3e2dc29`); web_search dedup by domain (`b04b394`); README layout (`56d1711`).

## v0.1.0 — 2026-04-19

### misc
- initial commit — alf v0.1 (`a0c7630`)
