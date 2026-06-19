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
| `workgroup.*` | Group coordination and shared context. |

## Workgroups

Workgroups coordinate multiple alpi profiles/peers around a shared task space hosted by a **hub** (authoritative transcript + group key). They involve: member identities, shared briefing/context, group key/versioning, hub state, liveness, budget controls, human participation rules. Answer concretely: identity, membership, briefing, budget, liveness, or cancellation.

Over-the-wire verbs: `workgroup.join`, `.post`, `.pull`, `.leave`, `.pause`, `.resume`. `workgroup.create` is a local hub primitive (TUI/CLI), not on the wire.

- `join(workgroup_id, bio?)` → `{workgroup_id, name, briefing, sealed_key, key_version, current_key_version, members[]}`. Caller must already be in the roster else `-32008`. `bio` (≤200 bytes) is the caller's self-published role tag-line.
- `post(workgroup_id, key_version, nonce, ciphertext, cost?)` → `{seq, ts}`. Author encrypts client-side (ChaCha20-Poly1305); the hub stays zero-knowledge. `cost {usd, tokens}` is the author's declared LLM spend, gating the workgroup lifetime budget.
- `pull(workgroup_id, since)` → `{posts[], head, current_key_version, sealed_key, members[]}`. Canonical fan-out; also stamps `last_seen_at` and refreshes the roster.

Roster entry shape: `{pubkey, last_seen_at, bio}`. Group key is a 32-byte key sealed per member; `current_key_version` is monotonic (starts at 1), rotated and bumped on `leave`/`kick`/`add_member` for forward secrecy on new traffic (past transcript stays decryptable). Transcript entries record the `key_version` they were encrypted under.

`#task` / `#done` are **hub-only** lifecycle markers; `#skip` / `#working` are **member-only**. Markers count only at the start of a decrypted line; `#task` requires a `#<slug>` (`[A-Za-z0-9][A-Za-z0-9_-]{0,63}`, lowercased). Single active task at a time; a new `#task` preempts the prior. `#done` needs full + substantive closure quorum (or hard-timeout escape). `#done BLOCKED` halts a pipeline without advancing.

## Liveness vs presence

Roster "online/offline" is **NOT** a reachability probe. It is computed from `last_seen_at`, a traffic-recency stamp the **hub** writes only when it receives a `workgroup.pull` or `workgroup.post` from a member. Three distinct signals, easy to conflate:

- `last_seen_at` — **presence**. Advances solely on inbound workgroup traffic at the hub. Thresholds: `<90s` → online (≈3 poll ticks at the 30s `WORKGROUP_TICK_SECONDS`), `<30m` → "last seen Nm ago", `≥30m` → "offline >30m".
- `link.ping` — **liveness/reachability**. Answers immediately (5s timeout), independent of engine/turn state. Does NOT feed the roster.
- `#working` — **busy/rotation marker**. The peer is mid-turn and asking the hub for more time; alive and reachable; orthogonal to presence.

So roster "offline" means "no recent workgroup pull/post", not "unreachable". A peer can pass `link.ping` instantly yet show stale because workgroup *traffic* stalled — a briefly busy hub event loop, a serial pull backlog across many subscriptions, or a transient hiccup. Members dispatch turns as background tasks, so a long turn alone does not stall the member's own polling.

Debugging an intra-machine "flap": confirm reachability with `link.ping` before trusting roster status, and check daemon logs for `wg poller pull(...) failed`. No hysteresis today — three consecutive missed pulls cross the 90s window. Tighten (ping-driven presence or a grace tick) only from real timeout logs, not assumption.

## Workgroup concurrency

Do not describe workgroups as globally serial, and do not promise guaranteed parallel workers. Dispatch is single-flight per `(workgroup_id, profile)`: the same profile will not run two turns for the same workgroup round slot, but different workgroups may dispatch the same profile concurrently. That is opportunistic concurrency only. A profile is a shared runtime identity with one home, memory, skills, tools, logs, budget, provider credentials, and rate limits — not a stateless worker pool. For predictable throughput, recommend more profiles/workers or fewer active workgroups, not an ALP protocol change.

## Budget

ALP/workgroup tasks respect profile budget settings (`budget.daily_usd`, CONFIG.md → Budget — USD or unlimited, no token cap). On exhaustion, stop or synthesize a bounded result rather than silently retrying. A workgroup may add a separate optional **lifetime** cap (`max_usd`) that double-gates `workgroup.post` on top of the daily profile cap.

## Error codes

| Code | Name | Meaning |
|---|---|---|
| `-32001` | `capability-denied` | Method not in peer's `allow`. |
| `-32002` | `replay` | `(from, nonce)` seen within window. |
| `-32003` | `bad-signature` | Signature verification failed. |
| `-32004` | `target-offline` | Resolvable peer, connection refused. |
| `-32005` | `budget-exceeded` | Profile (daily) or workgroup (lifetime) cap. `data.cap_kind`: `usd` (profile) or `workgroup_usd`. |
| `-32006` | `version-mismatch` | Incompatible `alp.v`. |
| `-32007` | `target-busy` | Session already running a turn. |
| `-32008` | `workgroup-not-member` (`workgroup-not-hub` for hub-only verbs) | Not a pinned member / not the hub. |
| `-32009` | `workgroup-not-found` | No workgroup with that id at the hub. |
| `-32010` | `workgroup-paused` | Paused; `post` rejected (`pull`/`join`/`leave` still work). |
| `-32011` | `task-missing-slug` | `#task` post lacks its `#<slug>` (SDK-side; hub stays zero-knowledge). |

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
