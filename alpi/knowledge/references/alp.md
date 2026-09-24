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

`allow` gates ALP methods; `tools.allow` on the same record lists the only tools that peer's inbound `link.ask` turns may run here: tool names, `*` patterns such as `github__get_*`, or `tool:action` for one action of a tool that declares an `action` argument (`knowledge:search` allows the search and refuses `ingest`/`maintain`; the schema shows `action` as a required enum of the allowed actions; on a tool with no `action` argument the entry allows nothing). Everything else leaves the schema and is refused at execution, in both transport paths and in nested paths (delegate sub-agents, research helpers, workflow steps, parallel calls), so a tool added later stays refused until listed. The policy is bound to the authenticated peer and the single turn, only narrows the profile's own `tools.deny`, and never touches local chat or other peers; no `tools` key = the profile's full tool set, `allow: []` = no tool, and an empty `--allow-tools`/`--allow` value also means no tool. `read_file`, `search` and the session tools also read the profile's `sessions/`, `mentions/`, `runs/` and `logs/`, so allowing them exposes other conversations. A `tools.deny` list (alpi 0.15.18) is invalid and refused with `-32013`. Console: `alpi peers add --allow-tools`, `alpi peers tools <id> --allow …` / `--clear`, setup → Peers.

## Transports

- Same machine: Unix-domain socket.
- Cross machine: authenticated encrypted transport (Noise over TCP, default port `7423`). The operator supplies the address; ALP does no discovery, NAT traversal, or relay.

`network.host` is the profile's advertised/accessible address (CONFIG.md → network) — distinct from the derived bind. The `default` profile's TCP listener is on whenever the machine has a reachable address (`network.host`, an auto-detected overlay/LAN address, or `0.0.0.0` in Docker); named profiles are Unix-only unless they set their own unique `alp.tcp_port`. One profile config drives both the ALP peer listener and the device-pairing host plane, on their own ports.

Transport internals are implementation detail unless debugging ALP itself.

## Core methods

| Method | Purpose |
|---|---|
| `link.ping` | Check peer reachability/identity. Answers immediately (5s timeout), independent of engine/turn state; does NOT feed the workgroup roster. |
| `link.ask` | Run a full agent turn on a peer (its memory/skills/tools). Sole read path into a peer. Alpi callers use streaming internally: a start frame plus signed progress heartbeats keep an active turn alive, while only the final frame becomes the `peer` tool result. `params.conversation` (opaque, derived from the caller's source session, never model-written) scopes the target's @-mention history to sender + conversation: a new conversation starts clean, another peer's identical value selects nothing, an unestablishable one runs with no history, and a missing key keeps the legacy per-sender thread. The result's `history` (`conversation` / `peer` / `none`) says which applied; a sender that sent one and got anything else knows the target predates isolation. |
| `link.cancel` | Cancel an in-flight peer task. Only the peer that started the active turn may cancel it. |
| `link.put_blob` | Send an explicitly selected file in verified content-addressed chunks. |
| `link.get_blob` | Retrieve a previously stored blob by SHA-256. |
| `workgroup.*` | Group coordination and shared context. |

## Liveness vs presence

Roster "online/offline" is **NOT** a reachability probe. It is computed from `last_seen_at`, a traffic-recency stamp the **hub** writes only when it receives a `workgroup.pull` or `workgroup.post` from a member. Three distinct signals, easy to conflate:

- `last_seen_at` — **presence**. Advances on a post, a held active pull or a nonblocking pull that returns fresh posts. Empty idle probes do not count as activity. Thresholds: `<180s` → online, `<30m` → "last seen Nm ago", `≥30m` → "offline >30m". The hub holds the truth; a member's `subscriptions.yaml` mirror persists timestamp changes only alongside a substantive subscription change, so background observation cannot rewrite the full mirror.
- `link.ping` — **liveness/reachability**. Answers immediately (5s timeout), independent of engine/turn state. Does NOT feed the roster.
- `#working` — **busy/rotation marker**. The peer is mid-turn and asking the hub for more time; alive and reachable; orthogonal to presence. A silent member turn gets one automatic heartbeat after `alp.working_after_s` (default 30s); an earlier agent post or process exit cancels it.

So roster "offline" means "no recent workgroup pull/post", not "unreachable". A peer can pass `link.ping` instantly yet show stale because workgroup traffic hit repeated transport failures or the hub event loop stalled. Members dispatch turns as background tasks, and subscriptions poll concurrently, so one long turn or another workgroup's held pull does not stall presence.

Debugging an intra-machine "flap": confirm reachability with `link.ping` before trusting roster status, and check daemon logs for `wg poller pull(...) failed`. Tighten presence semantics only from real timeout logs, not assumption.

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
| `-32013` | `peer-policy-invalid` | The caller's `tools` block in the target's `peers.yaml` is malformed (`data.detail` says how); every `link.ask` from that peer is refused until fixed — never run unrestricted. |

Client-side diagnostics (SDK Python exceptions, no JSON-RPC code, never on wire):

- `target-offline` → `alpi.alp.client.TargetOffline` (peer socket missing or TCP refused).
- `link.ask timed out after <n>s without remote activity` → the caller received no signed frame for `alp.link_idle_timeout_s`; it requests cancellation instead of treating an active turn's total duration as failure. The default is 60s of silence, not a 60s turn cap.
- `task-missing-slug` → `ValueError` raised before `#task` post encryption (hub stays zero-knowledge).

## Security posture

- Trust is explicit and identity-based; network reachability is not authorization; profiles isolate ALP identities; prompt/tool safety still applies inside ALP tasks.

## Common questions

- "Desktop/mobile use ALP?" → no, `host.*`; ALP is alpi-to-alpi.
- "Two profiles on one machine as separate peers?" → yes, each profile has its own identity.
- "Debug a peer?" → check identity, peer list, transport reachability, logs, budget.
- "Peer shows offline but is running?" → roster tracks workgroup traffic recency (`last_seen_at`), not reachability; probe with `link.ping`. See "Liveness vs presence".

## Related topics

- `workgroups` — hub/member lifecycle, pipelines, gates, recipes, concurrency.

- Host-plane clients and pairing: `deployments`
- Profile identity boundaries: `profiles`
- Security model: `security`

Pipeline liveness: after four hub notes without a member delivery or phase transition, close `BLOCKED` once local workers settle. Skips/working markers do not reset the count; mechanical repair/continuation notes have separate bounds. QA rewind findings also reach intermediate owners of cited paths. Paused subscriptions probe every 60 seconds; resume is not an immediate wake. Successful `workgroup.pull` RPC logs are DEBUG.
