# ALP — Alpi Link Protocol

**Version:** 1
**Editor:** [@soyjavi](https://github.com/soyjavi)
**Status:** Living specification for the current ALP surface. ALP.1
handles same-machine profiles, ALP.2 handles inter-machine links over
Noise_XK TCP, and ALP.3 adds hub-anchored rooms.

---

## Abstract

ALP (Alpi Link Protocol) is a closed, purpose-built protocol for
agent-to-agent communication between alpi instances. It covers
three deployment modes:

- two agents running as separate profiles on the same machine,
- two agents running on different machines across a network, and
- N agents sharing a workspace ("room").

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
plus budget/rate-limit enforcement. ALP.3 implements shared rooms.
The three modes share identity, envelope, capability, budget, and
error semantics so the protocol stays one coherent design instead of
three incompatible feature drops.

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
   core and six more in the optional rooms extension. There is
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
  and budgets.
- **Link.** A one-on-one communication channel between two
  peers. Core ALP methods operate on a link.
- **Room.** A multi-party workspace hosted by one peer (the
  **hub**) with one or more member peers. Rooms are defined in
  the optional rooms extension.
- **Hub.** The peer that holds the authoritative transcript and
  current group key for a room.

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
  budget:
    tokens_per_day: 200000
    usd_per_day: 0.50
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
  budget:
    tokens_per_day: 1000000
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
| `budget.tokens_per_day` | no | Hard daily token cap for this peer. Exceeding returns `-32005`. Accepted today; enforcement lands with the spending-ledger work in the BG roadmap item. |
| `budget.usd_per_day` | no | Hard daily spend cap for this peer. Ollama and other free-inference setups omit this. Same enforcement timing as the token cap. |
| `rate_limit.requests_per_minute` | no | Throttle. Default allows 10/min/peer. Enforced before handler dispatch. |

Budget fields are independent and optional, and they act as an
**optional sub-cap under a profile-level ceiling** — the profile's
own `alp.budget.{daily_usd, daily_tokens}` is the pool from which
every inbound method from every peer (and every interactive turn, and
every sub-agent spawn) draws. An absent peer cap means the peer
shares the pool directly; a peer cap tightens below the profile
ceiling. Budgets reset at UTC midnight; unused allowance does not
carry over. One unified ledger drives both the profile ceiling and
the per-peer sub-caps, reset timer, and the `-32005` response path.

The token budget has a secondary purpose beyond cost control: a
tight cap forces the caller to be concise, which keeps inter-
peer traffic goal-directed instead of chatty.

---

## Transport

### Intra-machine — Unix-domain socket

Path: `~/.alpi/<profile>/alp/alp.sock`, served by the profile's
ALP listener daemon (`alpi alp start`), mode `0600`. The listener
runs as its own service (launchd / systemd); it is deliberately
separate from the gateway daemon so `alpi` instances that never
expose Telegram / email still participate in ALP. Filesystem
permissions gate access
to the socket file; every envelope on the socket is still signed
as a second, orthogonal layer of defence.

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
- The target would breach its daily budget cap on this peer
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
| `-32005` | `budget-exceeded` | Request would breach daily cap. |
| `-32006` | `version-mismatch` | Incompatible `alp.v`. |
| `-32007` | `target-busy` | Session already running a turn. |

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

## Rooms (extension)

Rooms are a multi-party extension to ALP, layered on top of the
core link methods. A room is a shared transcript with a stable
group key; every member can post, every member can read. The
member that creates the room is the **hub** and holds the
authoritative transcript and key state.

### Methods

- `room.create(name, members[]) → room_id`
- `room.join(room_id)` — the hub responds with the current group
  key, encrypted to the joining member's pubkey.
- `room.post(room_id, text)` — the author encrypts under the
  current group key and sends to the hub, which fans out.
- `room.pull(room_id, since)` — poll for new messages since a
  cursor; may be served as SSE on inter-machine links.
- `room.leave(room_id)` — the hub generates a new group key and
  distributes it to remaining members so past keys can no
  longer decrypt new traffic.
- `room.pause(room_id)` / `room.resume(room_id)` — any member
  may pause a room, suspending all posts until a resume.

### Hub availability

Rooms are **hub-anchored**: when the hub's machine is offline,
the room is cold. Members cannot post, cannot pull new messages,
and cannot join until the hub returns. The protocol intentionally
does not provide a failover path, replication, or consensus-
driven re-election. Operators who want always-on rooms host the
hub on an always-on machine (a home server, a small VPS, a
Raspberry Pi), which is the deployment the protocol optimises
for.

### Budget inside rooms

Room posts count against the peer's global daily budget defined
in the peer list. An agent that reaches its cap during a room
conversation goes silent: it does not post a "I'm out of budget"
message and it does not leave the room. Silent capping keeps the
transcript clean of infrastructure noise and lets the budget
self-rate-limit autonomous agents without human intervention.
Budgets reset at UTC midnight.

There is no separate per-room budget in ALP v1. A single
per-peer cap covers every inbound path from that peer: core
link calls and room posts alike. Per-room caps can be added in a
future version if real usage reveals a room that monopolises an
agent's budget.

### Human participation

Humans are supported transparently: a human connects to a room
through the alpi TUI and appears as another member. Autonomous
agents do not wait for the human to post; the per-peer budget in
the peer list bounds how much any agent spends inside a given
room.

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
  `link.*` methods, room extension, envelope format, peer identity via
  Ed25519, capability model, reject-fast reentrancy, budget/rate-limit
  enforcement, and error codes.
