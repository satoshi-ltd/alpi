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
| `id` | yes | Human handle. Unique within this profile's peer list. |
| `alias` | no | Optional display label. |
| `pubkey` | yes | Base64-encoded Ed25519 public key. |
| `address` | for inter-machine | `host:port`. Omit for intra-profile peers. |
| `allow` | yes | Fail-closed list of methods the peer may invoke. |
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

---

## Transport

### Intra-machine — Unix-domain socket

Path: `~/.alpi/<profile>/alp/alp.sock`, served by the profile's
unified service (`alpi service start`) when the ALP subsystem is
enabled (`service.alp: true` — default), mode `0600`. The
listener shares the per-profile asyncio loop with gateway and
scheduler; toggle `service.alp: false` for profiles that need
gateway / scheduler but no ALP, or `service.gateway: false` +
`service.schedule: false` for an ALP-only relay machine.
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
  budget?:
    tokens?: int
    usd?: float
result:
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
turn. It is stable per `(from, to)` pair: successive `link.ask`
calls from the same origin resume the same session, giving the
remote agent memory of prior exchanges with this peer. The
session map keys on `alp:<from-pubkey>` for this reason.

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

- `workgroup.join(workgroup_id) → {workgroup_id, name, sealed_key, key_version, current_key_version, members[]}`
  Caller MUST already be in the workgroup's member roster (added
  at create time); otherwise `-32008`. The hub returns the
  member's currently-sealed group key, its `key_version`, the
  workgroup's `current_key_version`, and the member-pubkey list.
  Idempotent — a second `join` returns the same sealed key.

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

- `workgroup.pull(workgroup_id, since) → {posts[], head, current_key_version, sealed_key}`
  Returns every post with `seq > since`, in order, plus the
  current `head` cursor. `since=0` returns the full transcript.
  The response also echoes the caller's currently-sealed group
  key and the workgroup's `current_key_version` so members detect
  rekeys (e.g., after another member's `leave`) on their next
  pull and update their local key map. Pull is the canonical
  fan-out for ALP.3 — each member observes new traffic by
  polling. SSE-style streaming pull is tracked separately as
  **ALP.4**.

- `workgroup.leave(workgroup_id) → {workgroup_id, current_key_version, remaining_members[]}`
  The leaving member is dropped from the roster; the hub mints a
  fresh 32-byte group key, seals it for every remaining member,
  and bumps `current_key_version` by 1. Past transcript stays
  decryptable with old keys (members keep their local copy);
  forward secrecy applies to **new** traffic only. The hub itself
  cannot leave its own workgroup (`-32602`); use a hub-side
  primitive instead.

- `workgroup.pause(workgroup_id) → {workgroup_id, paused, paused_at, paused_by}`
  Any member may pause the workgroup. While paused, `workgroup.post`
  is rejected with `-32010 workgroup-paused`; `pull`, `join`, and
  `leave` keep working so members can catch up on existing traffic
  and exit cleanly without being trapped. Idempotent — calling
  pause on an already-paused workgroup returns the existing state
  without bumping the `paused_at` timestamp or rewriting
  `paused_by`. The hub records who triggered the pause for audit.

- `workgroup.resume(workgroup_id) → {workgroup_id, paused}`
  Inverse of `pause`. Any member may resume; idempotent on an
  already-running workgroup. Posts admit again starting on the
  next call.

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
key rotation (ALP.3 PR 2 `leave` flow) drops out naturally — the
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
  the cap is bumped (manual edit of `meta.yaml`; a TUI surface is
  tracked under ALP.3 PR 4).

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

### Human participation

Humans are supported transparently: a human connects to a
workgroup through the alpi TUI and appears as another member.
Autonomous agents do not wait for the human to post; each
agent's profile cap bounds how much they can spend inside the
workgroup.

---

## Versioning

The `alp.v` field in every envelope carries the integer protocol
version the sender speaks. Version bumps are intentional and
documented in the changelog section below. Receivers MUST reject
messages with an unknown version with error `-32006`.

Minor clarifications to this document that do not alter wire
behaviour may occur without a version bump. Any change that
alters the wire behaviour, the envelope shape, the method
signatures, or the security guarantees MUST bump `v`.

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

---

## Changelog

- **v1 (2026-04-24)** — current ALP surface: intra-machine transport over
  Unix-domain socket, inter-machine transport over Noise_XK TCP, core
  `link.*` methods, workgroup extension, envelope format, peer identity via
  Ed25519, capability model, reject-fast reentrancy, budget/rate-limit
  enforcement, and error codes.
