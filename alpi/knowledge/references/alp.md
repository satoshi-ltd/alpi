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

Over-the-wire verbs: `workgroup.join`, `.post`, `.pull`, `.leave`, `.pause`, `.resume`. `workgroup.create` is a local hub primitive (TUI/CLI), not on the wire.

- `join(workgroup_id, bio?)` → `{workgroup_id, name, briefing, sealed_key, key_version, current_key_version, members[]}`. Caller must already be in the roster else `-32008`. `bio` (≤200 bytes) is the caller's self-published role tag-line.
- `post(workgroup_id, key_version, nonce, ciphertext, cost?)` → `{seq, ts}`. Author encrypts client-side (ChaCha20-Poly1305); the hub stays zero-knowledge. `cost {usd, tokens}` is the author's declared LLM spend, gating the workgroup lifetime budget.
- `pull(workgroup_id, since, wait_s?)` → `{posts[], head, current_key_version, sealed_key, members[]}`. Canonical fan-out; also stamps `last_seen_at` and refreshes the roster. `wait_s` (≤25) long-polls: the hub holds the request and answers early when a fresh post lands.

Roster entry shape: `{pubkey, last_seen_at, bio}`. Group key is a 32-byte key sealed per member; `current_key_version` is monotonic (starts at 1), rotated and bumped on `leave`/`kick`/`add_member` for forward secrecy on new traffic (past transcript stays decryptable). Transcript entries record the `key_version` they were encrypted under.

`#task` / `#done` are **hub-only** lifecycle markers; `#skip` / `#working` are **member-only**. Markers count only at the start of a decrypted line; `#task` requires a `#<slug>` (`[A-Za-z0-9][A-Za-z0-9_-]{0,63}`, lowercased). Single active task at a time; a new `#task` preempts the prior — but re-opening the currently-active slug is rejected (`task-already-active`), EXCEPT in pipeline workgroups when the phase is stalled (no non-hub post since the opener; `#working` heartbeats don't count) — there the same-slug re-task is the sanctioned repair move. `#done` needs full + substantive closure quorum (scoped to the opener's `@participants` when the task is targeted; full roster when collective), with a hard-timeout escape (`meta.quorum_timeout_seconds`, default 600s). In pipeline workgroups, closing a phase whose owner never posted is rejected (`phase-owner-missing`; unresolvable owners → `phase-owner-unresolved`); the loud overrides `#done skipped · <reason>` / `#done BLOCKED · <reason>` (exact form, non-empty reason) close the ACTIVE phase immediately, waiving quorum. `#done BLOCKED` halts a pipeline without advancing. Watchdog closure-only wakes are SDK-enforced (`ALPI_WORKGROUP_CLOSURE_ONLY=1` rejects any non-`#done` post). Each remote subscription owns one concurrent long-poll (`wait_s`≤25s), reopened immediately after an empty success; local hubs use a 5s cached transcript probe. Fresh/open work uses a 10s dispatch cooldown, while transport failures back off exponentially to 15 min. In pipeline workgroups, a non-hub post's `@mentions` wake only the hub (routing goes up, never sideways). Hub-local `meta.pipeline_steps` add deterministic phase gates: when the expected owner posts, the runtime runs a local check (`shell=False`, cwd jailed in the workspace, minimal env, capped output → `gates/<phase>-<seq>.log` 0600) and on success closes the phase and opens the next via the normal hub SDK path (machine-authored `#done … · gate:<check>`); a failing gate wakes the hub agent with the bounded error and never advances. Accepted posts also nudge the hub poller in-process (`alp/wakes.py`) for near-immediate reaction, with polling as recovery.

## Workgroup recipes

A recipe is a **host-plane** launch convenience, NOT an ALP wire verb (ALP gains no recipe/project methods): a plain YAML file — a git artifact, not owned by a profile and never stored in `~/.alpi`. No catalogue, no install — the client reads the file and sends its CONTENT to the daemon. It captures a repeatable workgroup shape as data so a launch is "load file + fill params/inputs + edit briefing." Two host methods: `host.workgroup.recipes.describe(yaml)` → shape (hub, params+patterns, inputs, briefing draft, `has_project`); `host.workgroup.launch_recipe(profile, yaml, params, briefing?, inputs?)` (admin; `profile` must be the recipe's hub; `inputs` is a `{name: value}` map).

Three shapes from one format: **deliberation** (`task` only), **pipeline** (`pipeline` + `pipeline_steps`), **project** (+ a `project` block that clones a template repo and seeds it). Top-level keys: `hub`, `name` (both required), `members`, `briefing`, `task`, `quorum_timeout_seconds`, `budget_usd`, `pipeline`, `pipeline_steps`, `params`, `inputs`, `project`. Two kinds of operator-supplied value: **params** = single-line interpolation tokens — every `{name}` is a declared, REQUIRED param with an optional `pattern` (fullmatch); single non-recursive pass over string fields; rejected if non-scalar or carrying newlines (blocks YAML/marker injection). **inputs** = multiline file seeds — `{name: {dest, label?, placeholder?, required?}}`, arbitrary operator text written verbatim to `dest` (relative path in the clone), NOT interpolated, no injection surface; require a `project` block. So the *workgroup briefing* (param-interpolated metadata string) stays separate from e.g. a *hotel brief* (an input written to `brief.md`).

Project launch is ONE atomic unit, rolled back whole on any failure: `validate → clone (staging) → seed → move into place → write recipe inputs → workgroup.create → kickoff post`. Required inputs are validated pre-clone (missing → fail fast, no orphan). The dynamic values (operator-edited briefing, declared inputs) land BEFORE create+kickoff, so the first `#task` sees a project already carrying its final declared input files (binary media is added to the project git after launch); a later failure removes the workgroup (incl. the local subscriptions auto-join created) AND the clone; returns `{workgroup_id, project_path}`. `project.seed` (recipe-authored boilerplate, not operator content) has two ops: `json_merge` (deep-merge into an existing JSON file — objects merge, scalars/arrays replace) and `files` (write a fixed file outright). The workgroup records provenance in `meta.launch` (recipe id, content digest, resolved params, dest, template commit); editing the source recipe never mutates a live workgroup.

Recipe gates are `argv` run node-free on the daemon (raw commands, never engine turns — same runtime as `meta.pipeline_steps` above; a recipe just generates `meta.pipeline`/`meta.pipeline_steps`). Surfaces: CLI `alpi workgroup launch --recipe <f> --param k=v --input name=<file>` (`--input` reads FILE's contents into the declared input; binary media never travels at launch — it lands later in the project git); desktop New Workgroup modal "Import recipe…" (describe → standard fields hub/name/briefing, then a RECIPE INPUTS section: one field per param + one textarea per input).

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
| `-32012` | `blob-not-found` | Requested content hash is absent or fails verification. |

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
