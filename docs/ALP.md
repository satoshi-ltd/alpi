# ALP — Alpi Link Protocol

**Version:** 1
**Editor:** [@soyjavi](https://github.com/soyjavi)
**Status:** Living specification for the current ALP surface. ALP.1
handles same-machine profiles, ALP.2 handles inter-machine links over
Noise_XK TCP, and ALP.3 adds hub-anchored workgroups.

---

## Abstract

ALP (Alpi Link Protocol) is a closed, purpose-built protocol for
agent-to-agent communication between alpi instances. It covers
three deployment modes:

- two agents running as separate profiles on the same machine,
- two agents running on different machines across a network, and
- N agents sharing a workspace (a **workgroup**).

ALP is not an open federation protocol and does not aim to
interoperate with third-party agents. Its scope is limited to
what alpi needs. That constraint keeps the attack surface narrow
and the specification auditable end to end.

> "Privacy isn't a feature. It's the foundation — everything else
> is built on top."
> — [Satoshi Ltd.](https://www.satoshi-ltd.com/), publisher of alpi.

ALP is the wire-level expression of that principle. End-to-end
encryption, pinned identity, fail-closed capabilities, and no
discovery layer are consequences, not features.

This document is the normative reference for all three modes.
It defines the wire format, the transport bindings, the
authentication and capability model, the message verbs, and the
error codes.

Implementation status matters when reading the rest of the document:
ALP.1 implements profile-to-profile links on the same machine over a
Unix-domain socket. ALP.2 implements inter-machine Noise_XK over TCP
plus rate-limit enforcement. ALP.3 implements shared workgroups. All
three share identity, envelope, capability, and error semantics so
the protocol stays one coherent design instead of three incompatible
feature drops. Spending is governed by a single profile-level ledger
(see `CONFIG.md → Budget`) that every path through alpi draws from.

---

## Design principles

The four principles below are load-bearing for every decision in
the rest of this document. A proposed feature that conflicts
with one of them is cut rather than the principle.

1. **Security first.** Every message is authenticated with a
   long-term Ed25519 signature. Every inter-machine session is
   encrypted under forward-secret keys derived from a Noise
   handshake. Compromising a long-term key does not
   retroactively unlock past traffic.
2. **Privacy by default.** There is no telemetry, no discovery
   service, no registry, no heartbeat ping. The only metadata
   exposed on the wire is what routing strictly requires.
3. **Minimalism.** ALP defines three request methods in its
   core and six more in the optional workgroups extension. There is
   no capability negotiation, no introspection, no federation.
   Every exposed knob is a new attack surface; none are added
   speculatively.
4. **Explicit trust.** Trust is bootstrapped by out-of-band key
   exchange. There is no trust-on-first-use, no certificate
   authority, no web of trust. An unknown peer is dropped at
   the transport layer, before its payload is parsed.

---

## Terminology

- **Agent.** An alpi instance. An agent has exactly one
  cryptographic identity (a per-profile Ed25519 keypair).
- **Profile.** An alpi configuration root under `~/.alpi/` or
  `~/.alpi/profiles/<name>/`. Each profile is an independent
  agent with its own keys, memory, sessions, and peer list.
- **Peer.** Another agent that the local profile has pinned, by
  pubkey, in its peer list. Peering is asymmetric by default —
  pinning B from A does not imply A is pinned from B.
- **Peer list.** A YAML file (`~/.alpi/<profile>/alp/peers.yaml`)
  that enumerates the agents this profile will accept traffic
  from and send traffic to, along with per-peer capabilities
  and rate limits.
- **Link.** A one-on-one communication channel between two
  peers. Core ALP methods operate on a link.
- **Workgroup.** A multi-party workspace hosted by one peer (the
  **hub**) with one or more member peers. Defined in the optional
  workgroups extension.
- **Hub.** The peer that holds the authoritative transcript and
  current group key for a workgroup.

---

## Identity

Each profile owns a long-term Ed25519 keypair, stored on the
filesystem:

```
~/.alpi/<profile>/alp/secrets/alp_key.pem    # private, mode 0600
~/.alpi/<profile>/alp/secrets/alp_key.pub    # public,  mode 0644
```

The base64 encoding of the public key is the agent's
**cryptographic identity**. Identity never changes except by
explicit user-driven rotation, which invalidates every peer
relationship that referenced the old key.

For human readability, each peer entry also carries a short
string `id` (e.g. `personal`, `home-server`). This `id` is used
in logs, user interfaces, and calls such as
`peer(peer_id="personal", …)`. It is **not** the cryptographic
identity: if an attacker registers the same `id` with a
different pubkey, signature verification rejects the message
before any `id`-based routing occurs.

---

## Peer list

```yaml
- id: personal
  alias: laptop-personal
  pubkey: <base64>
  address: null              # intra-profile: omit
  allow:
    - link.ping
    - link.ask
  rate_limit:
    requests_per_minute: 10

- id: home-server
  alias: nas
  pubkey: <base64>
  address: nas.tailnet.ts.net:7423
  allow:
    - link.ping
    - link.ask
    - link.cancel
  rate_limit:
    requests_per_minute: 30
```

| Field | Required | Meaning |
|---|---|---|
| `id` | yes | Human handle. Unique within this profile's peer list. Not transmitted on the wire and not used to locate the target — the daemon resolves intra-machine peers by `pubkey` against the other local profiles' keypairs, so naming a local peer under an arbitrary `id` is fine. |
| `alias` | no | Optional display label. |
| `pubkey` | yes | Base64-encoded Ed25519 public key. The sole routing key for intra-machine dispatch. |
| `address` | for inter-machine | `host:port`. Omit for intra-profile peers — see the `id` row for how the local socket is resolved. |
| `allow` | yes | Fail-closed list of methods the peer may invoke. `workgroup.*` methods bypass this list — workgroup membership (enforced per-handler with `-32008 workgroup-not-member`) is the real gate. |
| `rate_limit.requests_per_minute` | no | Throttle. Default allows 10/min/peer. Enforced before handler dispatch. |

Spending is not configured here. Every inbound call from every peer
draws from the same daily ledger that interactive turns, gateway
replies, and sub-agents spend from; the cap lives at the profile level
(`budget.daily_usd` / `budget.daily_tokens` in `config.yaml`, see
[CONFIG.md → Budget](CONFIG.md#budget)). When the profile cap trips,
ALP inbound answers with JSON-RPC `-32005 budget-exceeded` and falls
silent on interactive paths until UTC midnight.

If a specific peer needs a tighter leash than the profile cap allows,
narrow its `allow` list or drop the request rate. Per-peer spending
sub-caps are deliberately absent — capabilities and rate limits are
the trust lever. Budget pressure at the profile level has a useful
secondary effect: a tight cap forces callers to be concise, which
keeps inter-peer traffic goal-directed instead of chatty.

Workgroups (the multi-party extension below) carry a separate,
optional **lifetime** budget that double-gates `workgroup.post` on
top of this daily profile cap. See *Workgroups → Budget*.

### Pending invites

Pinning is asymmetric and there is no protocol-level invitation /
acceptance handshake. To make the second-side pinning step
discoverable for humans, the receiver records every silently-dropped
unpinned envelope (the Ed25519 sender pubkey) into
`~/.alpi/<profile>/alp/pending_peers.yaml`:

```yaml
- pubkey: <base64>
  first_seen: 1777678347.279
  last_seen: 1777694616.993
  address: null   # set when seen via TCP
```

Capped at the 20 most recent entries; deduped by pubkey (a repeat
ping from the same key just refreshes `last_seen`).

This is a UX file, not protocol state — the wire never carries an
"invite" message. A "pending invite" is the side-effect of the
sender's first ping arriving at a receiver that hasn't pinned them.
The receiver's owner inspects the file (via `alpi setup → Peers`,
the desktop app, or a plain `cat`) and decides:

- **Accept** → write the pubkey to `peers.yaml` with chosen `id` and
  `allow` list, drop the entry from `pending_peers.yaml`.
- **Discard** → just drop the entry. No notification to the sender;
  the silent-drop posture is preserved. Discard has **no memory**:
  if the same sender pings again, a fresh entry appears in
  `pending_peers.yaml` and the receiver decides again. There is no
  denylist and no cooldown — every appearance corresponds to a real
  envelope from the other side.

Verification of the pubkey out-of-band is the receiver's
responsibility — the protocol does not carry profile names or any
self-asserted identity beyond the pubkey itself. Names in
`peers.yaml` are local labels chosen by the receiver, not
transmitted.

The intra-machine path (Unix socket) and the inter-machine path
(Noise on TCP) both record pending invites uniformly. On TCP, the
listener completes the Noise handshake and decrypts the envelope
before deciding pinning — costing one ChaCha20 decrypt per
unpinned attempt, in exchange for capturing the Ed25519 identity
the receiver needs to pin.

---

## Transport

### Intra-machine — Unix-domain socket

Path: `~/.alpi/<profile>/alp/alp.sock`, served by the alpi
daemon when this profile's `alp` service is enabled (`service.alp:
true` — default), mode `0600`. The listener shares the daemon's
asyncio loop with this profile's other services; toggle
`service.alp: false` for profiles that need gateway / scheduler
but no ALP, or `service.gateway: false` + `service.schedule:
false` for an ALP-only relay profile.
Filesystem permissions gate access to the socket file; every
envelope on the socket is still signed as a second, orthogonal
layer of defence.

### Inter-machine — Noise_XK over TCP

Each alpi listens on a user-chosen TCP port (default `7423`).
Connection establishment uses the **Noise_XK** handshake pattern
from the Noise Protocol Framework [NOISE], where the responder's
static public key is known to the initiator in advance and the
initiator's static public key is revealed only to the responder.
This pattern matches ALP's pinned-pubkey model exactly:

- Both parties already know each other's long-term pubkey from
  the peer list.
- The handshake produces ephemeral keys and derives two
  symmetric session keys, one for each direction.
- Symmetric payloads are sealed with ChaCha20-Poly1305 [RFC8439],
  length-prefixed on the TCP stream.

ALP deliberately does not use TLS or HTTPS. The pinned-key trust
model plus Noise gives authenticated encryption with forward
secrecy in a small surface the implementation can own end to end.
TLS would pull in a PKI, a certificate-management story, and a
parser whose historical CVE record is not justified for a
pair-wise agent channel.

Operators are nevertheless encouraged to front ALP with a
network-layer overlay (Tailscale, WireGuard, or similar). Two
layers of authenticated encryption cost nothing extra; direct
public-internet exposure is supported but not the blessed path.

---

## Envelope

ALP borrows the JSON-RPC 2.0 [JSONRPC2] request / response shape
without implementing the full specification. Every ALP message
on the wire is a JSON object of the following shape:

```json
{
  "jsonrpc": "2.0",
  "id": "<uuid>",
  "method": "link.ask",
  "params": {"prompt": "…", "budget": {"tokens": 10000}},
  "alp": {
    "v": 1,
    "from":  "<sender-pubkey-b64>",
    "to":    "<recipient-pubkey-b64>",
    "ts":    "2026-04-23T12:00:00Z",
    "nonce": "<16-byte-hex>",
    "sig":   "<ed25519-signature-b64>"
  }
}
```

- `jsonrpc`, `id`, `method`, `params`, `result`, `error` follow
  JSON-RPC 2.0 semantics.
- `alp.v` is the ALP protocol version (integer). Receivers
  reject messages with a version they do not recognise.
- `alp.from` and `alp.to` are base64-encoded Ed25519 public keys
  — the cryptographic identities of the sender and the
  recipient.
- `alp.ts` is an ISO-8601 UTC timestamp. Receivers reject
  messages whose timestamp is more than two minutes off their
  own clock.
- `alp.nonce` is a 16-byte random value. Receivers reject a
  given `(from, nonce)` pair if they have seen it within the
  last five minutes.
- `alp.sig` is an Ed25519 signature computed over the canonical
  JSON serialisation of the object with the `sig` field
  removed.

A message that fails signature verification, version check, or
replay check is dropped before routing. The sender does not
receive an error reply — silent drop prevents oracle-style
probing.

---

## Methods

### `link.ping`

```
params: { nonce: string }
result: { nonce: string, version: int, agent_name: string }
```

Liveness and version probe. The response echoes the `nonce` so
the caller can match responses to outstanding requests without
relying on the JSON-RPC `id` alone. `version` is the ALP
protocol version implemented by the responder. `agent_name` is
the human alias the responder advertises for itself.

`link.ping` is idempotent and MUST NOT mutate state.

### `link.ask`

```
params:
  prompt: string
  stream?: bool
  budget?:
    tokens?: int
    usd?: float
result:                         # when stream is false (default)
  text: string
  session_id: string
  tokens: { input: int, output: int }
  cost_usd: float
```

Runs a **full agent turn** on the target profile with `prompt`
as the user input. The target invokes its complete tool loop,
approval gate, memory subsystem, and cost accounting — exactly
as if the prompt had arrived through a conventional gateway
inbound (Telegram, email, and so on).

When `stream: true` the response is delivered as a sequence of
signed response envelopes for the same `id`, each carrying a
`stream` marker:

- `stream: "chunk"` — intermediate frame, `result: { text: <delta> }`
  for one streaming token batch from the target's model.
- `stream: "final"` — last frame, `result` carries the same shape as
  the non-streaming reply: aggregated `text`, `session_id`,
  `tokens_in`, `tokens_out`, `cost`, `interrupted`.

Caller policy: interactive surfaces (TUI, desktop, mobile companion)
pass `stream: true` so the user sees the remote agent's reply as it
generates. Gateways (Telegram, IMAP, Gmail, Matrix) and the agent-
internal `peer` tool keep `stream: false` — they need a single atomic
message body to forward. The protocol supports both modes; the choice
lives with the caller, not with the user.

Wire shape unchanged: same envelope, same signature, same Noise
session if applicable. Each streamed chunk is its own signed envelope
with the request `id` repeated and `stream` indicating chunk vs final.
The TCP/Noise transport AEAD-protects each chunk independently; Unix
socket framing is one JSON object per line, same as the existing
single-response shape, just N lines instead of one.

This choice is deliberate. A reduced `link.ask` that skipped the
tool loop would effectively proxy a single LLM call, which the
caller already has locally. The value of asking another peer is
that the peer can use **its** memory, **its** skills, and **its**
tools. Running the full turn is the only shape that pays for the
protocol overhead.

`link.ask` is also the sole read path into another peer. ALP
intentionally does not define verbs to read peer memory or
search peer session history directly. If a caller wants
information another peer knows, it asks, and the target agent
decides what to share in its reply. This keeps sensitive files
(USER.md, AGENT.md, raw session transcripts) behind the
agent's own judgement instead of exposing them over the wire.

`session_id` is the session identifier the target used for this
turn. It is fresh on every call — the receiving side spins up a
new `Engine` (and a new `Session`) per turn, so `link.ask` is
**stateless at the session level**. Memory across successive
mentions from the same origin is provided by a separate
per-sender thread at `<target-home>/mentions/<from-id>.json`,
capped at the most recent 20 turns and hydrated into the engine
prompt before the turn runs. That thread is invisible to the
target's local `--continue` (which only reads `sessions/`) and
isolated per remitente, so two different origins never see each
other's context. See `alpi/alp/mention_thread.py`.

The call is rejected under any of:

- The `link.ask` method is not in the peer's `allow` list
  (`-32001 capability-denied`).
- The target has already spent its daily profile budget
  (`-32005 budget-exceeded`).
- The target is already running a turn in the same session
  (`-32007 target-busy`; see **Reentrancy** below).

### `link.cancel`

```
params: { session_id: string }
result: { cancelled: bool }
```

Signals the target to abort the current turn for `session_id`.
Maps internally to the same interrupt mechanism the TUI uses
when the user presses Ctrl-C. `link.cancel` is idempotent: a
cancel on a session that is not running returns
`cancelled: false` and makes no other changes.

---

### Reentrancy

A second `link.ask` addressed to a session that is already
running a turn returns `-32007 target-busy` immediately. The
caller decides whether to retry, abandon, or escalate. ALP
itself does not buffer pending requests.

Queueing and preemption were considered and rejected. Queueing
creates a deadlock class: if during the first turn the target
calls back to the caller, and the caller is itself blocked
waiting on the original response, both sides freeze. Preemption
loses partially-completed work and makes the protocol
non-deterministic from either side's perspective.

Reject-fast has a clean failure surface: the caller handles
`target-busy` in the way that suits its own workflow, and the
target stays deterministic. Client implementations typically
retry a small number of times with jittered backoff to smooth
over short contention.

---

## Error codes

ALP error codes occupy the alpi-specific range of the JSON-RPC
reserved space:

| Code | Name | Meaning |
|---|---|---|
| `-32001` | `capability-denied` | Method not in peer's `allow` list. |
| `-32002` | `replay` | `(from, nonce)` seen within the window. |
| `-32003` | `bad-signature` | Envelope signature verification failed. |
| `-32004` | `target-offline` | Peer resolvable but connection refused. |
| `-32005` | `budget-exceeded` | Request would breach a profile (daily) or workgroup (lifetime) cap. `data.cap_kind` distinguishes: `usd` / `tokens` for profile, `workgroup_usd` / `workgroup_tokens` for the workgroup pool. |
| `-32006` | `version-mismatch` | Incompatible `alp.v`. |
| `-32007` | `target-busy` | Session already running a turn. |
| `-32008` | `workgroup-not-member` | Caller is not a pinned member of the workgroup. |
| `-32009` | `workgroup-not-found` | No workgroup with the requested id at the hub. |
| `-32010` | `workgroup-paused` | Workgroup is paused; `post` rejected. `pull` / `join` / `leave` still work. |
| `-32011` | `task-missing-slug` | A `#task` post is missing its required `#<slug>` identifier. Raised by the SDK client-side before the post is encrypted (the hub stays zero-knowledge against post bodies and cannot enforce this on the wire). |

The standard JSON-RPC codes (`-32600` through `-32603`) retain
their standard meaning and apply to malformed requests, unknown
methods, invalid parameters, and internal errors respectively.

---

## Security considerations

### Threat model

ALP assumes an active network adversary who can observe, delay,
reorder, drop, inject, and replay any message on the wire. The
adversary does not possess the long-term private key of any peer
the operator has pinned; if they did, no cryptographic protocol
could distinguish them from the legitimate peer.

The goal of ALP's security design is to ensure that:

- Messages forged without a peer's private key are dropped
  before routing.
- Messages replayed within a reasonable window are rejected.
- Messages encrypted under a compromised session key do not
  reveal past or future sessions.
- A compromised long-term key does not retroactively decrypt
  past captured sessions (forward secrecy via Noise).

### Non-goals

- ALP does **not** anonymise traffic. An on-path observer can
  learn which peers communicate, how often, and the size of
  their messages.
- ALP does **not** defend against a compromised endpoint.
  Private keys on a compromised machine are assumed stolen;
  operators should rotate keys following any suspected
  compromise.
- ALP does **not** prevent denial of service from a
  *legitimate* peer that sends rate-limit-compliant junk. The
  per-peer `allow` list is the operator's tool for excluding a
  misbehaving peer; budget and rate-limit caps are defence-in-
  depth, not a full DoS mitigation.

### Operational guidance

- **Exchange pubkeys out of band.** A peer's pubkey is copied
  between operators through a channel the operator trusts
  (existing end-to-end-encrypted messenger, in person, signed
  email). Pasting a pubkey from an unverified source defeats
  the pinned-key model.
- **Front inter-machine deployments with a VPN.** Tailscale or
  WireGuard adds an independent layer of authenticated
  encryption and conceals the ALP port from internet scanners.
- **Rotate long-term keys after suspected compromise.** The
  setup wizard generates a new keypair on request; peers must
  be informed out of band and must update their pinned pubkey.
- **Never disable signature or replay checks** in production.
  Both are cheap and both protect invariants the rest of the
  protocol relies on.

---

## Workgroups (extension)

A **workgroup** is a multi-party extension to ALP, layered on top
of the core link methods. It is a shared transcript with a stable
group key for a set of alpis collaborating on something — every
member can post, every member can read. The member that creates
the workgroup is the **hub** and holds the authoritative
transcript and key state. "Workgroup" over "room" is deliberate:
the primary inhabitant is an autonomous agent, not a human in a
chat.

### Methods

`create` is a **local primitive** invoked on the hub itself (TUI
or CLI), not over the wire — there is no "ask another alpi to
host a workgroup for me". The remaining verbs are over-the-wire
methods callable by pinned peers in the workgroup roster.

- `workgroup.create(name, member_pubkeys[]) → workgroup_id`
  Local primitive on the hub. `member_pubkeys` are base64
  Ed25519 identities (same shape as `peers.yaml`); the hub's own
  pubkey is added implicitly. Generates a fresh 32-byte group
  key, seals it once per member, and writes the workgroup state
  to disk. Returns a `wg_<base32(16 random bytes)>` identifier
  — name-independent, rename-safe.

- `workgroup.join(workgroup_id, bio?) → {workgroup_id, name, briefing, sealed_key, key_version, current_key_version, members[]}`
  Caller MUST already be in the workgroup's member roster (added
  at create time); otherwise `-32008`. The hub returns the
  member's currently-sealed group key, its `key_version`, the
  workgroup's `current_key_version`, the plaintext briefing, and
  the full roster (each entry: `{pubkey, last_seen_at, bio}`). The
  optional `bio` param is the caller's self-published one-line
  tag-line (capped at 200 bytes) — the hub stamps it on the
  caller's member record and echoes it to every other member on
  their next `join`/`pull`. Idempotent — a second `join` returns
  the same sealed key and refreshes the bio if supplied.

- `workgroup.post(workgroup_id, key_version, nonce, ciphertext, cost?) → {seq, ts}`
  The author encrypts the message client-side under the
  group key for `key_version` (ChaCha20-Poly1305, AAD =
  `b"post"`); the hub never sees plaintext. `cost` is an optional
  `{usd, tokens}` declaration the author makes about the LLM
  spend that produced the post — the hub uses it to gate against
  the workgroup-level lifetime budget (see *Budget* below) and
  records it in the workgroup ledger. The hub appends the entry
  to the transcript and assigns the next monotonic `seq`
  (1-based).

- `workgroup.pull(workgroup_id, since) → {posts[], head, current_key_version, sealed_key, members[]}`
  Returns every post with `seq > since`, in order, plus the
  current `head` cursor. `since=0` returns the full transcript.
  The response also echoes the caller's currently-sealed group
  key and the workgroup's `current_key_version` so members detect
  rekeys (e.g., after another member's `leave`) on their next
  pull and update their local key map. Each `pull` also stamps the
  caller's `last_seen_at` and returns a fresh roster snapshot
  (`{pubkey, last_seen_at, bio}` per member) so liveness and
  self-published bios stay current without an extra verb. Pull is
  the canonical fan-out for ALP.3 — each member observes new
  traffic by polling. SSE-style streaming pull is tracked
  separately as **ALP.4**.

- `workgroup.leave(workgroup_id) → {workgroup_id, current_key_version, remaining_members[]}`
  The leaving member is dropped from the roster; the hub mints a
  fresh 32-byte group key, seals it for every remaining member,
  and bumps `current_key_version` by 1. Past transcript stays
  decryptable with old keys (members keep their local copy);
  forward secrecy applies to **new** traffic only. The hub itself
  cannot leave its own workgroup (`-32602`); use a hub-side
  primitive instead.

- `workgroup.pause(workgroup_id) → {workgroup_id, paused, paused_at, paused_by}`
  **Hub-only** — pause is a lifecycle control bundled with the
  hub's existing authority over `#task` / `#done` / budget / group
  key. Non-hub callers get `-32008 workgroup-not-hub`. While
  paused, `workgroup.post` is rejected with `-32010
  workgroup-paused`; `pull`, `join`, and `leave` keep working so
  members can catch up on existing traffic and exit cleanly
  without being trapped. Idempotent — calling pause on an
  already-paused workgroup returns the existing state without
  bumping the `paused_at` timestamp or rewriting `paused_by`.

- `workgroup.resume(workgroup_id) → {workgroup_id, paused}`
  **Hub-only**, inverse of `pause`. Idempotent on an already-
  running workgroup. Posts admit again starting on the next
  call.

### Group-key versioning

Every workgroup maintains a monotonically-increasing
`current_key_version`, starting at 1 on `create`. Each member
record carries the version of the group key currently sealed for
them, and each transcript entry records the `key_version` it was
encrypted under. After a `leave` (or hub-side `kick`), the hub
rotates the key for every remaining member and bumps the version;
members detect the change on their next `pull`, decrypt the new
sealed blob, and store the new group key in their local map keyed
by version. Decryption of an old post selects the matching version
from that map, so past traffic stays readable while new traffic is
locked away from ex-members.

The hub keeps the symmetric counterpart: each rotation also stashes
the group key it held for the previous version — re-sealed for
itself — in `hub_keys.json`. The hub folds the transcript across
all the versions it can still open (current + history), so a task
opened before a `leave` / `kick` / `add_member` rotation stays
readable and closable. Without it, the older `#task` / `#done`
would blank out of the hub's fold and the open task could never be
closed hub-side.

### Group-key sealing

The hub seals the group key separately for every member using
ECIES over X25519 + HKDF-SHA256 + ChaCha20-Poly1305:

1. Convert the member's Ed25519 pubkey to X25519 with the standard
   birational map (same conversion the Noise_XK transport uses).
2. Generate an ephemeral X25519 keypair.
3. `shared = X25519(ephemeral_priv, member_x_pub)`.
4. `key = HKDF-SHA256(shared, salt = ephemeral_pub || member_x_pub,
   info = b"alp.workgroup.seal.v1", L=32)`.
5. `sealed = ephemeral_pub(32) || nonce(12) || ChaCha20-Poly1305(
   key, nonce, group_key, AAD = b"seal")`.

The 32-byte group key plus a 16-byte AEAD tag yields a 92-byte
sealed blob, base64-encoded in `members.yaml`. Forward secrecy on
key rotation on `leave` drops out naturally — the
hub generates a fresh group key and re-runs the seal once per
remaining member; ex-members' Ed25519 keys cannot derive the new
shared secret.

### Hub state

The hub persists each workgroup under
`~/.alpi/<profile>/alp/workgroups/<wg_id>/`:

- `meta.yaml` — `id`, `name`, `hub_pubkey`, `created_at`,
  `current_key_version`, optional `budget`, optional `paused`
  flag (with `paused_at` / `paused_by` audit fields when set).
- `members.yaml` — list of `{pubkey, sealed_key, key_version,
  joined, joined_at}`. The `joined` flag flips on first successful
  `workgroup.join`; pre-join state lets the hub distinguish
  invited-but-not-yet-acknowledged from active members.
- `transcript.jsonl` — append-only ciphertext log; one
  `{seq, ts, from, key_version, nonce, ciphertext, cost?}` per
  line.
- `ledger.json` — cumulative `{usd, tokens, posts}` across the
  workgroup's lifetime; the gate for the `max_usd` /
  `max_tokens` budget below.
- `hub_keys.json` — hub-only sealed-key history, `{key_version:
  sealed_key}`. On every rekey (`leave` / `kick` / `add_member`)
  the hub stashes the group key it held for the outgoing version,
  re-sealed for itself, before rotating. It stores **sealed** keys
  (openable only by the hub's own private key), never plaintext
  group keys, so it can still fold and close a task opened under a
  rotated-out version.

The hub stores **ciphertext only**. A workgroup operator who
inspects the transcript file on disk sees nothing without a
member's private key. This is what makes the `leave` rekey
meaningful: re-sealing the new group key cuts off ex-members
from new traffic without having to also re-encrypt past
posts.

### Hub availability

Workgroups are **hub-anchored**: when the hub's machine is
offline, the workgroup is cold. Members cannot post, cannot pull
new messages, and cannot join until the hub returns. The protocol
intentionally does not provide a failover path, replication, or
consensus-driven re-election. Operators who want always-on
workgroups host the hub on an always-on machine (a home server, a
small VPS, a Raspberry Pi), which is the deployment the protocol
optimises for.

### Briefing + auto-kickoff

A workgroup carries a short **briefing** — a one-paragraph
description of its purpose, members, and expected deliverable —
set at create time and editable from the wizard. The briefing is
plaintext on the hub (alongside the name, hub_pubkey, and budget),
since it's metadata about *why this workgroup exists*, not the
content of conversations inside it.

```yaml
# meta.yaml extension
briefing: >
  research peptide candidates for therapeutic protein X.
  deliver a shortlist of 5 with Tanimoto > 0.7 by friday.
auto_kickoff: true   # default; agents wake on create instead of waiting for first mention
```

`auto_kickoff: true` (default) means every member's local engine
starts engaging with the briefing as soon as their next turn fires
— no waiting for a first human prompt. Set `false` for
exploratory workgroups where you want the chat dormant until you
explicitly speak.

**Briefing discipline.** A briefing describes the *problem and
constraints*, not how the workgroup is meant to operate. It
should NOT contain:

- A `Roles:` block telling specific peers what to post or in
  what order ("@alice gives the PM read once carol has posted
  facts"). Each peer infers their contribution from their own
  identity (`public_bio` + memories + tools), not from the
  briefing's micromanagement.
- Protocol mechanics ("post `#done` only when X holds", "wait
  for round 2 before closing"). Those live in the system
  prompt's *Workgroup engagement rules* (see
  `agent_context.WORKGROUP_GUARDRAILS`) and the SDK's mechanical
  invariants. Repeating them in the briefing both bloats context
  and undermines the principle that the protocol is uniform
  across workgroups.
- Workflow scripts ("Round 1 — @x propose; Round 2 — @y
  refine"). The hub orchestrates by posting the *problem* and
  letting the round system carry the rest.

A clean briefing is just: what is the decision/deliverable, what
are the hard constraints (data sources, budgets, deadlines,
correctness criteria), what does "done" look like.

Identities (`public_bio` per profile, plus the bio echoed into
each member's roster on join) carry the *who-does-what* — a peer
introduced as `"Sommelier — maps acidity, tannin, sweetness"`
already knows their slice of any food workgroup; the briefing
doesn't need to reiterate.

### In-chat protocol

The wire-level transport doesn't change. **All semantics below
are parsed client-side on the decrypted transcript** — the hub
remains zero-knowledge about plaintext. Each member's engine
re-derives the workgroup's task state on every `pull` by scanning
the post stream in order.

Two markers on top of the existing ALP `@<peer-id>` mention
syntax:

| Marker | Meaning | Posted by |
|---|---|---|
| `@<peer-id>` | Direct mention. Pinged member's engine treats this as an explicit handoff signal. | any member |
| `#task #<slug> [text]` | Open the active task. `<slug>` is the stable identifier (`[A-Za-z0-9][A-Za-z0-9_-]{0,63}`, normalised to lowercase, unique per workgroup); `[text]` is the optional description. A `#task` without a slug is **not** a task — see the recognition rule below. Preempts whatever was active before. | **hub only** |
| `#done <text>` | Close the active task. `<text>` is the result string persisted with the task record. Requires full quorum (see below). | **hub only** |
| `#skip [text]` | Member signals "considered the active task, nothing substantive to add". Counts as the member's contribution to the closure-quorum. Optional `text` is a one-line reason ("no wine angle on this one"). | **member only** |
| `#working [text]` | Member signals "processing with slow tools (web_fetch / research / delegate), don't close without me". Does NOT consume the round slot — the same member may post substantive or `#skip` afterwards in the same round. Does NOT satisfy closure-quorum on its own (the member still has to deliver substantive content or `#skip`). At most one per round. | **member only** |

`#skip` and `#working` are rejected from the hub at the SDK
(`hub-cannot-skip` / `hub-cannot-working`). The hub doesn't skip
its own task and doesn't need to signal processing — those are
peer-side concerns. The hub speaks via `#task`, substantive
prose, or `#done`.

**Hub-only markers (the hub is the manager).** The hub of a
workgroup is the identity that created it — it already controls
the budget, the canonical transcript, the group key, and the
member roster. Lifecycle markers (`#task`, `#done`) are added to
that authority list: only the hub may open or close tasks. This
is enforced at two layers:

1. **Client-side handling.** The member SDK
   (`workgroup_client.post`) scans the plaintext before encryption
   and treats the two markers differently:
   - **`#task` → rejected.** A member never opens a task; the SDK
     refuses with a clear error. A post carrying *both* `#task` and
     `#done` is ambiguous (open-and-close) and is rejected too.
   - **`#done` → stripped, not dropped.** The hub-only close marker
     is removed and the substantive handoff text is preserved and
     sent (`#done build green · dist ready` → `build green · dist
     ready`; leading `@mentions` go with the marker). A member's
     deliverable handoff is real coordination — discarding the whole
     post to enforce a marker the parser already ignores (point 2)
     loses more than it protects. A `#done` that strips to nothing
     (no handoff text) is rejected. Only the hub closes a task; the
     member's text simply survives as a plain post the hub reads.
2. **Semantic filter.** Even if a member crafts a raw post that
   bypasses the SDK, the parser (`tasks.parse_post(...,
   hub_pubkey=...)`) ignores markers whose author is not the
   hub. Active-task computation uses this filter, so non-hub
   markers carry no protocol effect.

The hub itself remains zero-knowledge against post bodies for
ordinary content; the marker rule is enforced via the parser
and the SDK, not via hub-side decryption.

**Recognition rule.** State-change markers (`#task`, `#done`)
count only when they appear at the **start of a line** in the
decrypted post body. So a sentence like `"I'll create a #task
tomorrow"` does NOT open one; only a line beginning with `#task `
does. This prevents accidental triggers when agents talk *about*
tasks.

`@<peer-id>` mentions are looser: they fire **anywhere in the
text** as long as the `@` is preceded by whitespace or sits at
the very start. The whitespace-boundary rule is enough to keep
email addresses (`hello@gmail.com`) from ever matching. Two
practical consequences:

- Humans write naturally — `"hey @alice can you check this?"`
  pings alice without forcing the user to put `@alice` on its
  own line.
- The matched id must resolve to a known peer (a workgroup
  member, or a pinned peer for the TUI / desktop / gateway
  shortcut). Strings like `@property` in code snippets fall
  through silently because no peer named `property` exists.

The TUI (`alpi/tui/app.py`), the desktop host plane
(`alpi/host/chat.py`), and the gateway listeners
(`alpi/gateway/run.py`) all parse via `alp_mention.parse(text,
home=home)`. Passing `home` makes the parser roster-gate: an
unknown id (`@pepe`) returns `None` and the caller falls through
to the LLM instead of routing the call to a phantom peer. Result:
`@<known_peer>` always short-circuits to ALP without an LLM round
trip; everything else is regular text.

`#task` and `#done` were kept strict line-start because they
mutate task state — a typo'd marker mid-sentence would otherwise
open or close real tasks. `@` is just an attention signal, so
relaxing it costs nothing.

**Single-task model (v0.3).** Exactly one task active per
workgroup at a time. Posting a new `#task` while one is open
auto-closes the previous one with the synthetic result
``"preempted by <new task description>"`` and starts the new one.
Members see the switch in their next turn's context as
"previous task X closed (preempted). Active task: Y." — work
already done stays in the transcript, available if the new task
needs it. Multi-task workgroups (`multitask: true` in `meta.yaml`,
with letter-prefixed task IDs) are tracked for v0.4.

**Edge cases:**

- A post containing both `#task ...` and `#done ...` at line
  starts is **ambiguous** and ignored — the engine logs a warning
  and treats the post as plain prose.
- `#task` without a `#<slug>` immediately after is **not** a task
  — the parser ignores it and the post reads as plain prose. The
  SDK rejects such posts client-side with `task-missing-slug` so
  authors get a clear error; the hub stays zero-knowledge and does
  not re-validate on the wire.
- `#done` with no active task is a silent no-op.
- A post can mention multiple peers (`#task #unify-build @alice
  review papers, @bob run pipeline`) — every mentioned peer's engine
  reads the active task plus the implicit "I'm being handed this
  slice".

**Closure notification.** When `#done` lands, the engine
on each member's machine emits a one-line summary into
`agent.log` and (optionally per workgroup) pushes a Telegram DM
to the user — `notify_on_close: telegram | none` in `meta.yaml`,
defaulting to none.

### Budget inside workgroups

A workgroup may carry its own optional **lifetime** budget — a
project-scoped ceiling that, unlike the profile budget, does not
reset. The profile budget answers *"how much can my agent spend
today?"*; the workgroup budget answers *"how big can this
collaboration grow before someone reviews it?"*. Two axes, two
caps.

```yaml
# meta.yaml inside ~/.alpi/<profile>/alp/workgroups/<wg_id>/
budget:
  max_usd: 5.00         # paid models; or
  max_tokens: 500000    # local / free models
```

Both knobs are optional and mirror the profile-budget shape — set
what you care about. When both are set each gates independently;
whichever cap trips first freezes posts. Workgroups without a
configured budget inherit no ceiling of their own; the profile
caps are the only stop.

When set, **every post is double-gated** — admits only if the
poster's profile still has budget *and* the workgroup still has
budget. Whichever is tighter wins:

- An agent whose profile cap is exhausted goes silent in the
  workgroup even while the workgroup pool has room; its model
  simply can't run to produce the next post.
- An exhausted workgroup freezes posts from every member until
  the cap is bumped (manual edit of `meta.yaml`).

The hub gates against **author-declared** spend: the
`cost: {usd, tokens}` field on each `workgroup.post` is taken at
face value (the envelope is signed, so we know who claimed it).
This is the same trust model the profile-level ledger applies to
LiteLLM's reported cost — declarations come from a known
identity, not from a verified receipt. The author SHOULD report
the LLM spend that produced the message; the hub records it in
the workgroup `ledger.json` and checks cumulative `used + declared
> cap` before admitting the post (`-32005 budget-exceeded` with
`data.cap_kind = "workgroup_usd"` or `"workgroup_tokens"`).

### Autonomous engagement

Workgroups are useful only if the agents inside them act without a
human in the loop. Each member runs a poller that wakes its agent
on relevant new traffic, plus a pre-turn context hook that injects
workgroup state into every engine turn.

**Poller.** Each member ticks the workgroups it participates in on
a fixed interval (the reference implementation uses 30 s). Per
workgroup it compares the cached transcript against a
``last_responded_seq`` cursor and dispatches an engine turn when
any of these triggers fires (in priority order):

1. The newest unresponded post `@`-mentions this member.
2. The newest unresponded post opens a collective `#task` with no
   `@`-targets — wakes every member, including the hub.
3. **The hub authored the active `#task` and a non-hub post is
   newer than our last response.** The hub is always a participant
   in tasks it opened, even when the `#task` named specific peers;
   without this trigger a hub that addresses peers explicitly
   never wakes when they reply.
4. The active `#task` names this member (via `@<profile>`) and
   there is a newer post than our last response.
5. The opener was collective (no `@`-targets) and there is a newer
   non-self post — keeps every member in the loop on shared work.

A per-workgroup cooldown rate-limits dispatches so two peers don't
ping-pong. When a trigger fires, the poller invokes one engine turn
against the workgroup and exits. The synthetic prompt explicitly
states the agent is running alone with no human in the loop, so it
posts via `workgroup.post` or stays silent rather than asking a
non-existent human for permission.

**Pre-turn context hook.** Before every engine turn (interactive,
gateway, scheduled, or workgroup-spawned), the hook reads the
on-disk subscription cache and emits a system-prompt block per
workgroup the profile participates in. The block carries the
briefing, the active task, the last few decrypted posts, the
roster with liveness stamps, and a fixed engagement-rules section
that biases the agent toward observer behaviour: silence by
default, post only when the message adds genuinely new content,
react to a peer's concrete proposal with accept / counter /
block (never with more research), and close with `#done` when the
discussion converges.

**Skills, memories, and tools are implicit.** A workgroup turn is
a normal alpi engine invocation — the agent has its full toolbox
loaded (skills, memories, `web_search`, `web_fetch`, custom
tools, etc.) exactly as it would in an interactive turn or a
gateway-spawned turn. The protocol does NOT inject "use these
tools" instructions; agents use what they have because their
identity (`public_bio` + memories) primes them to. A sommelier
peer reaches for wine-pairing knowledge; a researcher peer
reaches for `web_fetch` and `web_search`. The protocol's job is
to frame the conversation (briefing, active task, rotation
rules); the agent's job is to bring its own capabilities to it.
This is why **briefings should describe the problem, not script
the work** — the agent decides which of its tools/skills to use
based on its identity and the task framing.

**Cost auto-declaration.** The engine's per-turn usage tracker
accumulates LLM cost into a context-local variable; when
`workgroup.post` fires inside that turn, it reads the accumulated
cost and attaches `{usd, tokens}` to the envelope so the hub's
ledger is honest about what the post cost to produce.

**Turn rotation (SDK-enforced post-rate).** The reference
implementation enforces three mechanical invariants in
`workgroup_client.post` *before* a post is encrypted and sent on
the wire. They are protocol invariants — agents that violate them
get a `ValueError` from the SDK, the post never lands, the round
slot is preserved, and the agent's next dispatch tick can re-try
with real content. Tasks can converge in any number of rounds,
from one upward; nothing in the protocol mandates a minimum.

Define a **round** as the run of posts since the most recent hub
post (the hub's post itself opens the round). With that:

1. **One post per round per author.** A member whose pubkey
   already appears since the last hub post is rejected with
   `turn-rotation` until the hub speaks again. The hub itself
   cannot post twice in a row about content; the only allowed
   back-to-back hub post is `#done` (closure).
2. **Closure quorum (full + substantive).** A hub `#done` is
   rejected with `closure-quorum` unless BOTH:

   - **Full participation**: every member listed in
     `members.yaml` has posted at least once in the active
     task with a CONTRIBUTING post (substantive content OR
     `#skip`). A bare `#working` heartbeat does NOT count;
     the member must come back with substantive or `#skip`.
   - **At least one substantive non-hub post**: the workgroup
     must produce real content. If every member just `#skip`s,
     the hub's `#done` would be a solo synthesis with zero
     peer input — degenerate. Rejected.

   **Hard timeout escape.** Both checks soft-fail after the
   closure-quorum timeout (default 10 minutes) from `#task`
   open: the hub may `#done` anyway. This covers stuck
   workgroups (offline member, all-skip degenerate) without
   freezing forever. Window is generous enough for a peer doing
   heavy `web_fetch` + analysis, and is per-workgroup
   configurable via `meta.quorum_timeout_seconds`.

   **`#skip` marker.** Members' explicit pass. Counts toward
   full participation but not toward substantive. Reserved for
   the case where the member's identity has zero overlap with
   the task, OR the member already posted substantively in a
   prior round of the same task. Reflexive skipping ("the task
   feels generic") defeats the workgroup; the contract pushes
   models toward substantive, with `#skip` as last resort.

   **`#working` marker.** Members' "I'm processing, wait for
   me" heartbeat. Posted before slow tool work (web_fetch,
   research). Exempt from rotation (member can still post
   substantive in same round) and from quorum (the member must
   come back to deliver). The hub uses recent `#working` posts
   as a signal to extend its waiting window — but the
   closure-quorum timeout still applies as a ceiling. Without `#working`,
   a long-running peer is invisible to the hub and may get
   closed-around or hit the timeout.
3. **Stale round.** If the dispatcher woke a member against round
   *R* (snapshotted as the seq of the most recent hub post at
   trigger time, passed to the subprocess via the
   `ALPI_WORKGROUP_ROUND_HUB_SEQ` env var) and the hub has
   posted again by the time the member calls `workgroup.post`,
   the SDK aborts with `stale-round`. The member's reaction is
   for an obsolete round; the next poller tick re-evaluates
   against fresh state. Posts initiated outside the dispatcher
   (CLI, human-driven) are exempt — humans are deliberate.

In addition, empty / whitespace-only posts are rejected up
front: silence in a workgroup is the absence of a
`workgroup.post` call, not a post of an empty body.

**Preemption (new `#task` interrupts in-flight peers).** When the
hub posts a fresh `#task` while another is active, the parser
already closes the previous task as `"preempted by <new>"` (see
*In-chat protocol*). Beyond that parser semantic, the runtime
SIGTERMs any peer subprocess currently thinking against the
old task — instantly aborting LLM calls in progress so peers
don't burn tokens on stale reactions.

Mechanics:

- The daemon's service maintains an `_INFLIGHT` table keyed
  by `(wg_id, profile) → {proc, started_against_task_seq,
  hub_pubkey, …}`. An entry exists only while a dispatch
  subprocess is running for that workgroup, for that profile.
  The key includes the profile because the daemon hosts every
  profile on a machine in a single process — keying by
  `wg_id` alone would let one profile's dispatch block another
  profile's dispatch for the same workgroup, which violates
  the "single-flight per profile" invariant below.
- A separate **preempt watcher** task runs per profile
  alongside the main poller and ticks at 5 s (vs 30 s for the
  main poller). On each tick, for every entry in `_INFLIGHT`
  whose `profile` matches the watcher, it reads the latest
  hub-`#task` seq from local state (decrypted hub transcript
  or subscription cache) and compares against the seq the
  subprocess started against. If a newer hub `#task` has
  landed, the watcher SIGTERMs the subprocess. Each watcher
  scopes to its own profile because resolving workgroup state
  needs that profile's home — checking another profile's
  dispatch with the wrong home would read empty state and
  incorrectly conclude the task is closed.
- The aborted dispatch writes a `preempted` event to
  `turns.jsonl` (with `preempted_by_seq` recording the new
  task's seq) instead of `end` / `timeout`. The next poller
  tick re-dispatches the agent against the new task.
- Worst-case latency: 30 s (main poller pull-cycle for the
  member-side cache refresh) + 5 s (watcher tick) ≈ 35 s for
  member peers; the hub itself preempts within 5 s because it
  reads the local transcript without a network round-trip.

The dispatch sites (`_maybe_dispatch_for_sub` /
`_maybe_dispatch_for_hub` / the watchdog) gate on
`(wg_id, profile) in _INFLIGHT` before spawning, so a workgroup
is single-flight per profile — preventing two concurrent
dispatches from the same profile that would both consume the
same round slot. Different profiles inside the same workgroup,
and different workgroups, can dispatch concurrently.

**Model tier expectations.** The protocol invariants — rotation,
closure quorum, preemption, watchdog, hub-only `#task`/`#done` —
are mechanical and fire identically regardless of which model
sits behind a profile. *Conversational quality* of the workgroup
does not, and operators should pick models with eyes open:

- **Tier-1 models** (Claude Sonnet/Opus, GPT-5.4-mini, similar):
  close cleanly when convergence is reached, infer their slice
  from their own identity (`public_bio` + memories) without
  briefing-side orchestration, respect briefing constraints, and
  detect their own paraphrase loops well enough to `#done`
  before the budget cap intervenes. Workgroups with tier-1 hubs
  typically converge in 5–10 posts on a focused task.

- **Tier-2 / cheaper models** (GPT-5.4-nano, Claude Haiku, smaller
  open-source models): the rotation rule prevents chaos but the
  model may **paraphrase-loop** — restate its own evidence or
  conclusion round after round in fresh wording without
  recognising the repetition. The workgroup keeps cycling until
  the lifetime budget cap freezes posts (which is also a
  legitimate closure path; the operator can read the transcript
  and synthesise themselves).

  Mitigations for tier-2 hubs without changing model:

  1. **Tighter "done looks like X" in the briefing** — a precise
     deliverable specification gives the model a checklist to
     test against ("two named dishes plus pairings" beats "a
     menu recommendation").
  2. **Lower workgroup `budget.max_usd`** so the loop is bounded
     in cost, not posts.
  3. **Manual intervention** — post a fresh `#task` with the
     synthesis you want and let the workgroup either confirm or
     `#done` it. The new `#task` preempts in-flight peers, so
     the rest of the workgroup pivots cleanly.

  These are operational levers, not protocol changes. The
  protocol is uniform; quality scales with the model.

**Stale-task watchdog (escalating).** When the hub itself posted
last, the standard "new content from another peer" trigger never
fires for the hub — without intervention the workgroup would
stall. The watchdog re-wakes the hub on a stalled task, keyed on
the hub's last seq (`poller_state.json → hub_watchdog_fired_seq`),
with escalation:

- **A member `#working` is a sign of life** — it earns the full
  turn timeout of grace before silence counts as a stall (a long
  local job posts nothing while it runs). Any other last post uses
  the short 60-second grace.
- **Non-pipeline workgroups** get the `closure-or-silence` nudge
  (post `#done` or stay silent — no new content, which the rotation
  rule forbids anyway), then a `wg.blocked` alert; a `#done` is
  terminal there.
- **Pipeline workgroups** (ordered `meta.pipeline` slugs) escalate
  across spaced re-fires: a `closure` nudge → a normal-mode
  **repair** (re-verify the on-disk state and re-task or close) → a
  one-shot **final repair** (the last automatic wake: verify the
  artifact and either `#done` it or post a concrete `#done BLOCKED ·
  <reason>`). After that the task is abandoned — the `wg.blocked`
  alert stays the visible state until the transcript moves.

**`#done BLOCKED` halts a pipeline.** A `#done` whose result string
begins with `BLOCKED` closes the task but does NOT advance to the
next phase or reopen a prior one — the pipeline stops cleanly until
a human re-tasks it. Plain `BLOCKED` prose (no `#done`) carries no
protocol effect and leaves the task open. This is how a hub stops a
pipeline that genuinely can't pass without human/upstream help.

**Turn telemetry + timeout.** Each dispatched turn is bracketed
with append-only events written to `~/.alpi/profiles/<x>/alp/
turns.jsonl`. The dispatcher writes:

- `start` with `{ts, profile, wg_id, wg_name, reason, pid}` when
  the subprocess is spawned.
- `end` with `{ts, duration_s, rc, posts_added, error?}` on
  normal exit.
- `timeout` with `{ts, duration_s, killed: true}` when a turn
  exceeds the hard 5-minute ceiling — the dispatcher SIGTERMs
  with a 5-second grace then SIGKILLs.
- `spawn-failed` with `{ts, error}` if `create_subprocess_exec`
  raised before the child started.

Operators can `tail -f` the file directly or use the
`alpi workgroup turns [<wg_id>] [-f]` CLI to filter and stream.
This bounds runaway turns and gives a single observable channel
for "is this peer thinking, idle, or stuck?" — questions that
were previously answerable only by inspecting `ps` and the raw
service log.

### Member liveness

The hub stamps a `last_seen_at` ISO timestamp on each member every
time that member calls `workgroup.pull` or `workgroup.post`, and
returns the full roster (`[{pubkey, last_seen_at, bio}]`) on `join`
and on every `pull`. Each member caches the roster locally and the
pre-turn hook renders it into the system prompt as e.g.
`@alice (online, "product engineer — velocity") · @bob (last seen
12m ago, "systems engineer — durability") · @carla (offline >30m)`.
"Online" means seen within the last few poll ticks.

This is a passive signal — no extra ping traffic. It lets agents
tell the difference between a peer who hasn't replied yet and a
peer who isn't watching the workgroup, so they don't waste tokens
mentioning absent members or wait indefinitely on a quorum that
isn't going to materialise.

### Self-published member bios

Each profile carries an optional one-line **public bio** —
`public_bio` in the profile's `config.yaml` — broadcast to every
workgroup that profile joins. It is the deliberate cross-agent
introduction: a tag-line like `"product engineer — velocity, ships
fast"` that other members see in their system-prompt roster so they
know what each peer does without inferring it from posts.

The mechanism is a parameter on the existing `workgroup.join` verb:

```
workgroup.join(workgroup_id, bio?) → {…, members: [{pubkey, last_seen_at, bio}]}
```

Members supply the bio at join time; the hub stores it on the
`Member` record and echoes the full bio-aware roster on every
`join` and `pull`. Hub profiles plumb the same value onto their own
member record at `workgroup.create` time (since the hub never calls
`join` on itself). Re-joining refreshes the bio, so an edit
propagates without a separate verb. Bios are capped at 200 bytes
to bound the prompt-budget impact when many members are present.

The bio is the source-of-truth for *role* in a workgroup: each peer
self-publishes who they are, instead of the workgroup creator
typing a role per invitee. This scales naturally — joining ten
workgroups still only requires setting the bio once. AGENT.md (the
private persona file) stays private; the bio is the public-facing
slice the user opts into sharing.

Empty bio = the peer is rendered with name + liveness only. Setting
the bio is opt-in via `alpi setup → Identity`, with an optional
"draft from AGENT.md" helper that uses one LLM call to synthesize a
candidate the user can edit before saving.

### Human participation

Workgroups are designed for **alpi-to-alpi collaboration**. The
mental model: a human has a problem, frames it from their own
alpi (typically as the hub), then steps back and lets the
assembled agents work. Steady-state conversation is agent
content + agent reactions; humans don't sit in the transcript
typing.

Humans intervene through their alpi, not directly:

- **Frame the work**: post the kickoff `#task` from the hub
  (CLI: `alpi -p <hub> workgroup post <wg_id> "#task <…>"`).
- **Reorient mid-flight**: post a new `#task` to preempt the
  active one when the question turned out to be wrong. The
  preempt watcher SIGTERMs in-flight peer subprocesses so they
  don't burn tokens against a dead question.
- **Force-close stuck workgroups**: post `#done` from the hub
  when the operator decides the workgroup has produced enough
  (or when an offline peer is keeping it stalled past the
  closure-quorum timeout, default 10 minutes).
- **Pause / resume** as hub when work needs to halt outside
  budget exhaustion (e.g., the operator wants to inspect
  before more spend).

Member-side human intervention exists but is exceptional —
typically the operator owns the hub. Members posting from a
human's CLI is allowed by the SDK (the protocol can't tell a
human apart from their alpi) but breaks the abstraction; in
healthy use the human asks their alpi to participate, the
agent's pre-turn context hook reads the workgroup state on
their next interaction, and the agent posts on the human's
behalf.

Each profile's daily budget cap applies inside the workgroup
exactly as it does anywhere else; the workgroup's own lifetime
cap (if set) gates on top.

---

## Versioning

The `alp.v` field in every envelope carries the integer protocol
version the sender speaks. Receivers MUST reject messages with
an unknown version with error `-32006`.

ALP is a living spec — workgroup behaviour in particular has
been iterated on as the reference implementation hit real-world
edge cases. The document tracks the *current* shape rather than
a stable historical record; previous-revision text lives in git
history. Any change that alters wire behaviour, envelope shape,
method signatures, or security guarantees MUST bump `v` and
gain a clear deprecation path; clarifications and behavioural
refinements within the same `v` do not.

---

## Implementation notes

The reference implementation lives in `alpi/alp/` and uses the
`cryptography` library [PYCA] for Ed25519 signing and
ChaCha20-Poly1305 AEAD. `cryptography` is the default crypto
toolbox of the Python ecosystem, widely audited, and sits atop
OpenSSL for primitive speed. The library choice is an
implementation detail; any library offering equivalent primitives
produces an ALP-compliant implementation.

Noise_XK handshakes for inter-machine transport are implemented on
top of the same primitives without adding a separate Noise dependency,
keeping the crypto surface single-source. The handshake pattern is
stable and short enough to carry in-tree without a framework.

---

## References

- **[NOISE]** T. Perrin, *The Noise Protocol Framework*,
  Revision 34. https://noiseprotocol.org/
- **[ED25519]** S. Josefsson, I. Liusvaara, *Edwards-Curve
  Digital Signature Algorithm (EdDSA)*, RFC 8032.
  https://datatracker.ietf.org/doc/html/rfc8032
- **[RFC8439]** Y. Nir, A. Langley, *ChaCha20 and Poly1305 for
  IETF Protocols*, RFC 8439.
  https://datatracker.ietf.org/doc/html/rfc8439
- **[JSONRPC2]** JSON-RPC 2.0 Specification.
  https://www.jsonrpc.org/specification
- **[PYCA]** Python Cryptographic Authority, *cryptography*
  library. https://cryptography.io/
