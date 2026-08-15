# ALP answer pack

## Answer directly

- Desktop/mobile do NOT use ALP; they use `host.*`.
- ALP is the peer-to-peer plane for trusted alpi-to-alpi peers and workgroups; separate from the local desktop/mobile host API.
- Trust is explicit, identity-based, and profile-scoped — not machine-scoped. Separate concerns → separate profiles.
- Network reachability is never authorization.
- Answer workgroup questions concretely: identity, membership, briefing, budget, liveness, cancellation.

## Planes

| Plane | Purpose |
|---|---|
| `host.*` | Device client↔daemon API over local Unix socket or paired WebSocket. Desktop/mobile use this. |
| `link.*`, `workgroup.*` | ALP peer-to-peer methods for trusted alpi instances. |

## Identity

Each profile owns its own ALP identity (a long-term keypair); trust is profile-scoped, not machine-scoped. If work and personal must not trust the same peers, use separate profiles.

## Peer list

Peers are explicit; a peer record binds identity and reachability. Don't treat arbitrary network callers as trusted just because they can reach a socket/port.

Peer `id` is a **local label** for human/UI use only — never on the wire, never used to locate a co-located peer. Intra-machine peers resolve by `pubkey` against other local profiles' keypairs, so a peer pinned under any alias still routes; the `id`-only fallback applies when the pubkey matches no local profile.

## Transports

- Same machine: Unix-domain socket.
- Cross machine: authenticated encrypted transport (Noise over TCP, default port `7423`). The operator supplies the address; ALP does no discovery, NAT traversal, or relay.

`network.host` is the profile's advertised/accessible address (CONFIG.md → network) — distinct from the derived bind. The `default` profile's TCP listener is on whenever the machine has a reachable address (`network.host`, an auto-detected overlay/LAN address, or `0.0.0.0` in Docker); named profiles are Unix-only unless they set their own unique `alp.tcp_port`. One profile config drives both the ALP peer listener and the device-pairing host plane, on their own ports.

Transport internals are implementation detail unless debugging ALP itself.

## Core methods

| Method | Purpose |
|---|---|
| `link.ping` | Check peer reachability/identity. Answers immediately (5s timeout), independent of engine/turn state; does NOT feed the workgroup roster. |
| `link.ask` | Run a full agent turn on a peer (its memory/skills/tools). Sole read path into a peer. |
| `link.cancel` | Cancel an in-flight peer task. |
| `link.put_blob` | Send an explicitly selected file in verified content-addressed chunks. |
| `link.get_blob` | Retrieve a previously stored blob by SHA-256. |
| `workgroup.*` | Group coordination and shared context. |

## Workgroups

Workgroups coordinate multiple alpi profiles/peers around a shared task space hosted by a **hub** (authoritative transcript + group key). They involve: member identities, shared briefing/context, group key/versioning, hub state, liveness, budget controls, human participation rules. Answer concretely: identity, membership, briefing, budget, liveness, or cancellation.

Over-the-wire verbs: `workgroup.join`, `.post`, `.pull`, `.file_put`, `.file_get`, `.file_list`, `.leave`, `.pause`, `.resume`. `workgroup.create` is a local hub primitive (TUI/CLI), not on the wire.

- `join(workgroup_id, bio?)` → `{workgroup_id, name, briefing, sealed_key, key_version, current_key_version, members[]}`. Caller must already be in the roster else `-32008`. `bio` (≤200 bytes) is the caller's self-published role tag-line.
- `post(workgroup_id, key_version, nonce, ciphertext, cost?, turn_id?)` → `{seq, ts}`. Author encrypts client-side (ChaCha20-Poly1305); the hub stays zero-knowledge. `cost {usd, tokens}` is the LLM spend accrued since this turn's preceding accepted post, gating the workgroup lifetime budget without counting a `#working` heartbeat twice; a rejected post retains the same delta for retry. The optional split `{tokens_in, tokens_out, cached_in, measured_in}` rides along: `measured_in` is the input from completions that reported cache info at all (the honest hit-rate denominator), `cached_in` is the prefix-cache share OF `measured_in`, and both are clamped (`cached <= measured <= tokens_in`) on BOTH the remote handler and the hub-local post path. ABSENT `cached_in` = unmeasured; `0` = measured miss — never write an unmeasured zero. Entries with `cached_in` but no `measured_in` predate the split; their denominator is `tokens_in`. `turn_id` is an optional 32-character correlation id shared with the daemon's `alp/turns.jsonl` start/end events; old posts remain valid without it.
- `pull(workgroup_id, since, wait_s?)` → `{posts[], head, current_key_version, sealed_key, members[]}`. Canonical fan-out; also stamps `last_seen_at` and refreshes the roster. `wait_s` (≤25) long-polls: the hub holds the request and answers early when a fresh post lands.
- `file_put(...)` / `file_get(...)` transfer encrypted file sidecars through the hub in 256 KiB ciphertext chunks. `file_list(offset?, limit?)` pages through metadata newest-first so older files remain discoverable after their marker leaves recent context. Files are content-addressed by plaintext SHA-256, capped at 20 MiB each / 200 MiB per workgroup, encrypted once with the versioned group key, and announced only by an encrypted `#file <name> · <size> · sha256:<digest>` transcript marker. The `workgroup_file` tool lists files, sends workspace/current-turn attachment paths, and fetches a digest on demand; agents must never paste file contents into posts. Old files remain decryptable through retained sealed key versions.

Roster entry shape: `{pubkey, last_seen_at, bio}`. Group key is a 32-byte key sealed per member; `current_key_version` is monotonic (starts at 1), rotated and bumped on `leave`/`kick`/`add_member` for forward secrecy on new traffic (past transcript stays decryptable). Transcript entries record the `key_version` they were encrypted under.

`#task` / `#done` are **hub-only** lifecycle markers; `#skip` / `#working` are **member-only**. Markers count only at the start of a decrypted line; `#task` requires a `#<slug>` (`[A-Za-z0-9][A-Za-z0-9_-]{0,63}`, lowercased). Single active task at a time; a new `#task` preempts the prior — but re-opening the currently-active slug is rejected (`task-already-active`), EXCEPT in pipeline workgroups when the phase is stalled (no non-hub post since the opener; `#working` heartbeats don't count) — there the same-slug re-task is the sanctioned repair move. `#done` needs full + substantive closure quorum (scoped to the opener's `@participants` when the task is targeted; full roster when collective), with a hard-timeout escape (`meta.quorum_timeout_seconds`, default 600s). In pipeline workgroups, closing a phase whose owner never posted is rejected (`phase-owner-missing`; unresolvable owners → `phase-owner-unresolved`); the loud overrides `#done skipped · <reason>` / `#done BLOCKED · <reason>` (exact form, non-empty reason) close the ACTIVE phase immediately, waiving quorum. `#done BLOCKED` halts a pipeline without advancing. Watchdog closure-only wakes are SDK-enforced (`ALPI_WORKGROUP_CLOSURE_ONLY=1` rejects any non-`#done` post). Each remote subscription owns one concurrent long-poll (`wait_s`≤25s), reopened immediately after an empty success; local hubs use a 5s cached transcript probe. Fresh/open work uses a 10s dispatch cooldown, while transport failures back off exponentially to 15 min. In pipeline workgroups, a non-hub post's `@mentions` wake only the hub (routing goes up, never sideways). Hub-local `meta.pipeline_steps` add deterministic phase gates: when the expected owner posts, the runtime runs a local check (`shell=False`, cwd jailed in the workspace, minimal env, capped output → `gates/<phase>-<seq>.log` 0600) and on success closes the phase and opens the next via the normal hub SDK path (machine-authored `#done … · gate:<check>`); a failing gate wakes the hub agent with the bounded error and never advances. A step may declare `{owner, task}` and OMIT `gate` — still dispatched and owner-typed, it closes on quorum instead of on a check, which is the right shape for a phase that may legitimately produce nothing (its owner posts `#skip <reason>`, then the hub closes `#done skipped · <reason>`; a gate there would fail a correct outcome). PER-PHASE AUTHORSHIP: a gated phase may declare `paths:` (relative globs); the daemon snapshots the project at task open and reds the gate BEFORE the command when files outside the globs changed, naming each file (missing baseline fails closed; `paths` requires a `gate`). The dispatched owner receives those globs as its native file-tool write boundary; non-owners cannot use native file mutation tools during that phase. `terminal` follows the profile's tool policy, while the gate remains authoritative over the workspace diff. LEVEL-TRIGGERED GATE: a red verdict is PROVISIONAL — the poller re-runs the gate on the open phase with no new post and no hub wake, so an owner who fixed the workspace without re-posting still gets a machine close; a still-red re-run is SILENT (never re-posts findings, never consumes a repair round), held to one per phase per interval, skipped while any turn is live for the workgroup, and skipped unless the project's content fingerprint moved since the red verdict (so a permanently red gate spawns its command once, not per tick); a watchdog pass verifies through those SAME guards — no bypass exists, so a stalled red gate is never respawned per tick and the wake fires without re-carrying findings already in the transcript; `workgroup resume` clears gate state so a pre-pause delivery re-fires; a terminal close carrying an explicit failure word — or a `#done BLOCKED` naming an owner OTHER than the blocked phase's own — that routes nothing draws exactly ONE routing wake; the targeted phase owner is exempt from the one-post-per-round cap (repair deliveries arrive in pieces); and after `#done BLOCKED`, a hub `#task` on any EARLIER phase of the chain is allowed (a rewind re-walks forward). ONE authority picks the successor: both the continuation path (quorum/gate-less close) and the gate path call `pipeline_successor(meta, phase)` — the slug after `phase` in its own chain, empty at the terminal phase — so a phase can no longer advance differently depending on whether its gate ran. A `pipeline_steps` entry that declares `next` is rejected (`pipeline_steps['content'].next is derived from pipelines['setup']`). Recovery slugs resolve to their LONGEST declared-phase prefix: exact membership first, then the longest prefix that is a declared phase, so `#content-fix`, `#content-recheck` and an invented `#content-repair` all map to `#content` (a green repair of the TERMINAL phase completes the run) while a declared `#content-update` chain still wins by being exact. A hub `#task` whose slug maps to no declared chain is REFUSED at post time (`task-slug-unroutable`). RE-TASKING: a new `#task` preempts the open one (`result = "preempted by #<slug>"`, never reported as done) and a peer already working is stopped twice over — the preempt watcher SIGTERMs its in-flight dispatch within ~5s, and any post that survives is refused `stale-round`. Only a fresh `#task` preempts; a `#done` is caught by `stale-round` alone. In a DELIBERATION wg any hub `#task` is fine (collective included) and a `#done` is terminal. In a PIPELINE wg every `#task` must name its owner, and a manual `#task <other slug>` is ACCEPTED while a gate-less phase is open but REJECTED (`phase-gate-abandoned`) while a GATED one is — the guard exists so a red gate cannot be renamed out of the way, and only `workgroup trigger` is exempt. An AD-HOC slug is refused before it can be posted, so it can no longer null `pipeline_run`; if a legacy one exists, `_next_pipeline_phase` still reports it unknown and advances nothing. Recovery is a PHASE RE-OPEN (`@owner #task #<phase>` → the run returns at that phase, earlier ones pending, and its close continues the chain), NOT a re-trigger — a trigger always starts a fresh run from the chain's first phase and discards the position reached. A phase whose declared owner IS the hub profile is worked by the hub itself: it may post its deliverable back-to-back and close without non-hub quorum, and `_check_pipeline_close_owner` still requires that delivery post. Order is single-sourced, but the two paths still differ in who WRITES the successor's opener: on the gate path the daemon sends the step's declared `task` verbatim (`@owner #task #<phase> · <task>`), while on the continuation path it wakes the hub agent, which authors the opener in its own words and never sends the declared `task` — so making a phase gate-less delegates the NEXT phase's task wording to the hub, and recipe-side discipline on that text stops binding. Accepted posts also nudge the hub poller in-process (`alp/wakes.py`) for near-immediate reaction, with polling as recovery.

For pipeline closes, `skipped` is a no-deliverable outcome: once the resolved phase owner has posted substantive work in the current pipeline run, the hub must pass the gate, repair that phase, or close `BLOCKED`; it cannot relabel the delivery as skipped. Reopening any phase, including the first, preserves that run; only an explicit operator pipeline trigger starts a fresh run. An unresolved owner always fails closed and requires re-pinning or `BLOCKED`.

Hub-owned `#task` phases wake the hub immediately only while that task remains active.

## Workgroup recipes

A recipe is a **host-plane** launch convenience, NOT an ALP wire verb (ALP gains no recipe/project methods). Reusable recipes live under the hub profile as `recipes/<id>.yaml`; `host.workgroup.recipes.list(profile)` returns their launch shape. External YAML remains supported through the desktop file picker and CLI path. Both routes use `host.workgroup.recipes.describe(yaml)` for supplied content and `host.workgroup.launch_recipe(profile, recipe_id, yaml?, params, briefing?, inputs?)` for the atomic launch; without `yaml`, the daemon loads the saved recipe by id. The recipe captures a repeatable workgroup shape as data so a launch is "select recipe + fill params/inputs + edit briefing." `profile` must be the recipe's hub; `inputs` is a `{name: value}` map.

Three shapes from one format: **deliberation** (`task` only), **pipeline** (`pipelines` + `pipeline_steps`), **project** (+ a `project` block that clones a template repo and seeds it). Top-level keys: `hub`, `name` (both required), `members`, `briefing`, `task`, `quorum_timeout_seconds`, `budget_usd`, `pipelines`, `launch`, `pipeline_steps`, `params`, `inputs`, `project`. **`pipelines`** is ONE map of named ordered chains — `pipelines: {setup: [setup, …], media-update: [media-update, …]}` — and `launch: <key>` names the chain the kickoff opens. Every key MUST equal its own first phase (so `#task #<pipeline>` opens it with no alias layer) and phases are GLOBALLY DISJOINT, so a task slug has at most one owning pipeline and the active chain never depends on YAML order. `launch` is OPTIONAL: without it the workgroup starts idle — no kickoff, no active phase, every chain awaiting an explicit trigger — and declaring `pipelines` without `launch` but WITH a `task` is rejected. Every declared chain must be triggerable: its first phase declares a non-empty `owner` AND `task`. Order lives in the chain only; `pipeline_steps.*.next` is rejected. Trigger a chain by key with `alpi workgroup trigger <wg_id> <pipeline>` / `host.workgroup.trigger` — the daemon publishes exactly `@<declared owner> #task #<first phase> · <declared task>` verbatim from the recipe (clients never author it) and rejects unknown key, paused, subscriber, or missing-contract (`pipeline-trigger-contract-missing`) without appending. PIPELINES RUN ONE AT A TIME: starting a chain stops whatever was mid-flight — the opener preempts an open task (recorded `preempted by #<slug>`, never done) and the trigger returns `stopped` = `{pipeline, phase, status, open_task, same_pipeline}` | null so every surface can name it. An operator trigger is an explicit abandon, so it is exempt from `phase-gate-abandoned` (that guard stops the HUB renaming its way past a red gate, not a human changing course). A RECIPE IS THE ONLY DECLARER: there is no manual pipeline creation and no post-launch editing — `workgroup create` makes a deliberation workgroup, `host.workgroup.update` refuses a `pipeline` param ("pipelines are declared by a recipe"), and every client surface is read-only, because a client can edit a phase list but cannot write the `pipeline_steps` owner/task a phase needs to be dispatchable. The retired `pipeline` + `operations` shape is REJECTED, not migrated: such a recipe raises RecipeError, such a `meta.yaml` does not load (logged + skipped; its list row carries `needs_relaunch: true`), such a subscription entry is skipped (logged, then dropped on the next save), and nothing writes those keys. The active chain is derived from the LATEST close alone; a close whose slug is in no chain resolves unknown and advances nothing. Two kinds of operator-supplied value: **params** = single-line interpolation tokens — every `{name}` is a declared, REQUIRED param with an optional `pattern` (fullmatch); single non-recursive pass over string fields; rejected if non-scalar or carrying newlines (blocks YAML/marker injection). **inputs** = multiline file seeds — `{name: {dest, label?, placeholder?, required?}}`, arbitrary operator text written verbatim to `dest` (relative path in the clone), NOT interpolated, no injection surface; require a `project` block. So the *workgroup briefing* (param-interpolated metadata string) stays separate from e.g. a *hotel brief* (an input written to `brief.md`).

Project launch is ONE atomic unit, rolled back whole on any failure: `validate → clone (staging) → seed → move into place → write recipe inputs → workgroup.create → kickoff post`. Required inputs are validated pre-clone (missing → fail fast, no orphan). The dynamic values (operator-edited briefing, declared inputs) land BEFORE create+kickoff, so the first `#task` sees a project already carrying its final declared input files (binary media is added to the project git after launch); a later failure removes the workgroup (incl. the local subscriptions auto-join created) AND the clone; returns `{workgroup_id, project_path}`. `project.seed` (recipe-authored boilerplate, not operator content) has two ops: `json_merge` (deep-merge into an existing JSON file — objects merge, scalars/arrays replace) and `files` (write a fixed file outright). The workgroup records provenance in `meta.launch` (recipe id, content digest, resolved params, dest, template commit); editing the source recipe never mutates a live workgroup.

Recipe gates are `argv` run node-free on the daemon (raw commands, never engine turns — same runtime as `meta.pipeline_steps` above; a recipe just generates `meta.pipelines`/`meta.launch_pipeline`/`meta.pipeline_steps`). Members receive `pipelines`, `launch_pipeline`, `pipeline_mode` and a `phase_map` of `{owner, task?}` on join and on EVERY pull (so hub-side edits land without a rejoin) — never gate `argv`/`cwd`, gate output, or provenance; agent context renders the chains from that instead of from briefing prose. Runtime state is separate from definitions: `host.workgroups.list` returns definitions without decrypting, while `host.workgroup.tasks` adds `pipeline_run` = `{pipeline, status, started_seq, current_phase, phases: [{slug, state, seq}]}` with `state` in `completed|skipped|current|pending` and `status` in `running|between|blocked|completed`. `#done skipped · <reason>` renders `skipped`, never `completed`; a blocked phase stays `current` and the run status carries the failure; the LATEST task overall selects the visible run, so an ad-hoc task nulls `pipeline_run` instead of leaving a finished chain on screen. Reopening any phase, including the first, preserves the run and its latest attempt owns the phase state; only an explicit operator trigger starts a fresh run. The fold is cached by transcript identity + a definitions fingerprint. Definitions are read-only outside the recipe, and the apps are read-only on runtime too (the chat shows the running chain, settings list the declared chains and mark the launch one — neither starts anything); the trigger is an operator verb on the console (`workgroup trigger`) and host plane only. Surfaces: CLI `alpi workgroup launch --recipe <id-or-path> --param k=v --input name=<file>` (`--input` reads FILE's contents into the declared input; binary media never travels at launch — it lands later in the project git); desktop lists the selected hub's saved recipes and keeps "Import recipe…" for external YAML. Both render the standard hub/name/briefing fields plus one field per param and one textarea per input.

## Liveness vs presence

Roster "online/offline" is **NOT** a reachability probe. It is computed from `last_seen_at`, a traffic-recency stamp the **hub** writes only when it receives a `workgroup.pull` or `workgroup.post` from a member. Three distinct signals, easy to conflate:

- `last_seen_at` — **presence**. Advances solely on inbound workgroup traffic at the hub. Thresholds: `<90s` → online, `<30m` → "last seen Nm ago", `≥30m` → "offline >30m". Remote subscriptions continuously reopen held pulls, so an idle healthy member refreshes presence without launching agent turns.
- `link.ping` — **liveness/reachability**. Answers immediately (5s timeout), independent of engine/turn state. Does NOT feed the roster.
- `#working` — **busy/rotation marker**. The peer is mid-turn and asking the hub for more time; alive and reachable; orthogonal to presence.

So roster "offline" means "no recent workgroup pull/post", not "unreachable". A peer can pass `link.ping` instantly yet show stale because workgroup traffic hit repeated transport failures or the hub event loop stalled. Members dispatch turns as background tasks, and subscriptions poll concurrently, so one long turn or another workgroup's held pull does not stall presence.

Debugging an intra-machine "flap": confirm reachability with `link.ping` before trusting roster status, and check daemon logs for `wg poller pull(...) failed`. No hysteresis today — three consecutive missed pulls cross the 90s window. Tighten (ping-driven presence or a grace tick) only from real timeout logs, not assumption.

## Workgroup concurrency

Do not describe workgroups as globally serial, and do not promise guaranteed parallel workers. Dispatch is single-flight per `(workgroup_id, profile)`: the same profile will not run two turns for the same workgroup round slot, but different workgroups may dispatch the same profile concurrently. That is opportunistic concurrency only. A profile is a shared runtime identity with one home, memory, skills, tools, logs, budget, provider credentials, and rate limits — not a stateless worker pool. For predictable throughput, recommend more profiles/workers or fewer active workgroups, not an ALP protocol change.

## Budget

ALP/workgroup tasks respect profile budget settings (`budget.daily_usd`, CONFIG.md → Budget — USD or unlimited, no token cap). On exhaustion, stop or synthesize a bounded result rather than silently retrying. A workgroup may add a separate optional **lifetime** cap (`max_usd`) that double-gates `workgroup.post` on top of the daily profile cap.

## Error codes

| Code | Name | Meaning |
|---|---|---|
| `-32001` | `capability-denied` | Method not in peer's `allow`. |
| `-32005` | `budget-exceeded` / `rate-limited` | Two reasons under one code. `budget-exceeded` (`data.cap_kind=usd`/`workgroup_usd`) → profile/workgroup spend cap. `rate-limited` (`data.window_seconds`) → peer `rate_limit.per_minute` exhausted. Distinguish via `message`. |
| `-32007` | `target-busy` | Session already running a turn. |
| `-32008` | `workgroup-not-member` (`workgroup-not-hub` for hub-only verbs) | Not a pinned member / not the hub. |
| `-32009` | `workgroup-not-found` | No workgroup with that id at the hub. |
| `-32010` | `workgroup-paused` | Paused; `post` rejected (`pull`/`join`/`leave` still work). |
| `-32011` | `file-not-found` | Requested workgroup file is absent. |
| `-32012` | `blob-not-found` / `file-quota-exceeded` | Generic link blob absent, or workgroup file store would exceed 200 MiB. |

Client-side diagnostics (SDK Python exceptions, no JSON-RPC code, never on wire):

- `target-offline` → `alpi.alp.client.TargetOffline` (peer socket missing or TCP refused).
- `task-missing-slug` → `ValueError` raised before `#task` post encryption (hub stays zero-knowledge).

## Security posture

- Trust is explicit and identity-based; network reachability is not authorization; profiles isolate ALP identities; prompt/tool safety still applies inside ALP tasks.

## Common questions

- "Desktop/mobile use ALP?" → no, `host.*`; ALP is alpi-to-alpi.
- "Two profiles on one machine as separate peers?" → yes, each profile has its own identity.
- "Debug a peer?" → check identity, peer list, transport reachability, logs, budget.
- "Peer shows offline but is running?" → roster tracks workgroup traffic recency (`last_seen_at`), not reachability; probe with `link.ping`. See "Liveness vs presence".

## Related topics

- Host-plane clients and pairing: `deployments`
- Profile identity boundaries: `profiles`
- Security model: `security`
