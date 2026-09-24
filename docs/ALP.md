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
3. **Minimalism.** ALP defines five request methods in its core and
   nine more in the optional workgroups extension. There is
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
- **Peer list.** A YAML file (`~/.alpi/alp/peers.yaml` for the default profile, `~/.alpi/profiles/<name>/alp/peers.yaml` for a named one)
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
<profile-home>/alp/secrets/alp_key.pem    # private, mode 0600
<profile-home>/alp/secrets/alp_key.pub    # public,  mode 0644
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
    - link.put_blob
    - link.get_blob
  rate_limit:
    per_minute: 10

- id: home-server
  alias: nas
  pubkey: <base64>
  address: home-server.internal:7423   # any reachable host:port
  allow:
    - link.ping
    - link.ask
    - link.cancel
  rate_limit:
    per_minute: 30
  tools:
    allow:                             # the only tools this peer's link.ask turns may run here
      - knowledge:search
      - read_file
```

| Field | Required | Meaning |
|---|---|---|
| `id` | yes | Human handle. Unique within this profile's peer list. Not transmitted on the wire and not used to locate the target — the daemon resolves intra-machine peers by `pubkey` against the other local profiles' keypairs, so naming a local peer under an arbitrary `id` is fine. |
| `alias` | no | Optional display label. |
| `pubkey` | yes | Base64-encoded Ed25519 public key. The sole routing key for intra-machine dispatch. |
| `address` | for inter-machine | `host:port`, opaque to ALP — resolved by the OS at dial time. Any reachable host works: a LAN IP, a private hostname, a Docker/compose DNS name, a VPN / Tailscale / WireGuard address, or a public IP. ALP does no discovery, NAT traversal, or relay — you supply the address. Omit for intra-profile peers (the local Unix socket is resolved by `pubkey`). |
| `allow` | yes | Fail-closed list of methods the peer may invoke. `workgroup.*` methods bypass this list — workgroup membership (enforced per-handler with `-32008 workgroup-not-member`) is the real gate. |
| `rate_limit.per_minute` | no | Throttle. Default `60` requests/min/peer, enforced before handler dispatch; over-cap requests get JSON-RPC `-32005`. It governs ordinary calls only: a held `workgroup.pull` and the chunk streams of the blob and file verbs run on their own fixed, much higher budget, so a long transfer cannot be starved by a tight per-peer limit. |
| `tools.allow` | no | The only tools an inbound `link.ask` from this peer may run on this profile: names, `*` patterns or `tool:action`. See *Per-peer tool policy* below. |

Spending is not configured here. Every inbound call from every peer
draws from the same daily ledger that interactive turns, scheduled
jobs, and sub-agents spend from; the cap lives at the profile level
(`budget.daily_usd` in `config.yaml`, see
[CONFIG.md → Budget](CONFIG.md#budget)). When the profile cap trips,
ALP inbound answers with JSON-RPC `-32005 budget-exceeded` and falls
silent on interactive paths until UTC midnight.

If a specific peer needs a tighter leash than the profile cap allows,
narrow its `allow` list or drop the request rate. Per-peer spending
sub-caps are deliberately absent — capabilities and rate limits are
the trust lever. Budget pressure at the profile level has a useful
secondary effect: a tight cap forces callers to be concise, which
keeps inter-peer traffic goal-directed instead of chatty.

### Per-peer tool policy

`allow` decides which ALP methods a peer may call; it says nothing about
what the target agent may *do* once `link.ask` runs a turn with the
profile's own tools. `tools.allow` on a peer record closes that gap: it
lists the only tools that peer's turns may run on this profile, and every
other tool is removed from what the model sees and refused if called
anyway, in both transport paths and in nested execution (sub-agents from
`delegate`, `research` helpers, `workflow` steps, parallel calls). A tool
added later, a skill runner or a new MCP server is refused until you list it.

An entry is one of:

- a tool name: `alpi_knowledge`;
- a `*` pattern: `github__get_*` for part of an MCP server;
- `tool:action` for a single action of a tool that declares an `action`
  argument: `knowledge:search` allows the knowledge search and refuses
  `ingest` and `maintain`. The model sees `action` as required, limited to
  the allowed actions, and a call with any other action, or none, is
  refused. On a tool that declares no `action` argument such an entry
  allows nothing.

A read-only knowledge relay needs nothing else:

```yaml
- id: alexandra
  pubkey: <base64>
  allow: [link.ping, link.ask]
  tools:
    allow:
      - knowledge:search
      - alpi_knowledge
```

List only what the peer needs. `read_file`, `search` and the session tools
(`session_search`, `session_read`, `recall_sessions`) read the profile's own
stores too, where `sessions/`, `mentions/`, `runs/` and `logs/` hold every
other conversation, so allowing them lets that peer read those.

The policy is bound to the authenticated peer and the individual turn: two
peers with different policies cannot affect one another, and local chat is
untouched. It only narrows: the profile's own `tools.deny` still applies, so
a peer can never reach a tool the profile itself denies. A peer without
`tools` keeps today's behaviour, the profile's full tool set. `allow: []`
lets the peer run no tool at all. Set it with `alpi peers add --allow-tools …`,
`alpi peers tools <id> --allow …` (`--clear` removes it), or the setup
wizard when pinning. An empty value, on the command line or in the wizard
once you choose to limit the tools, allows no tool; only leaving the policy
out gives the full tool set.

A `tools` block that is present but malformed — not a mapping, an `allow`
that is not a list, a key other than `allow`, an entry that is not a tool
name, `*` pattern or `tool:action` — is a configuration error, not an empty
policy: every `link.ask` from that peer is refused with `-32013
peer-policy-invalid` and the detail names the problem, until the record is
fixed. That includes a `tools.deny` list written by alpi 0.15.18, which
`alpi peers tools <id> --allow …` replaces. `alpi peers list`, `alpi peers
tools <id>` and the setup detail show the same diagnostic. Only an absent
`tools` key means "no policy".

### Pending invites

Pinning is asymmetric and there is no protocol-level invitation /
acceptance handshake. To make the second-side pinning step
discoverable for humans, the receiver records every silently-dropped
unpinned envelope (the Ed25519 sender pubkey) into
`<profile-home>/alp/pending_peers.yaml`:

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

Path: `<profile-home>/alp/alp.sock`, served by the alpi
daemon for every profile, mode `0600`. The listener is an internal
daemon task isolated from the scheduler and workgroup poller.
Filesystem permissions gate access to the socket file; every
envelope on the socket is still signed as a second, orthogonal
layer of defence.

### TCP transport — Noise_XK

The second transport is a TCP listener, used whenever two agents are not on the
same Unix socket — a different machine, a VM, another container, or across a
LAN / overlay. ALP defines identity, envelope, Noise, verbs, and workgroups; the
**underlay is the operator's choice** (LAN, WireGuard, Tailscale, a private
hostname, a Docker network, or a public address if they accept the exposure).
ALP itself does no discovery, NAT traversal, or relay.

The `default` profile listens on a TCP port (default `7423`) whenever the
machine has a reachable address — the shared accessible address (`network.host`
— see `CONFIG.md → network`), an auto-detected overlay/LAN address, or `0.0.0.0`
in Docker; with no reachable address it stays Unix-only. **Named profiles are
Unix-only** unless they set their own explicit, unique `alp.tcp_port` (otherwise
profiles would collide on the shared port). A profile is configured once and
both the ALP peer listener and the device-pairing host plane use the same
address, on their own ports.
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

The resulting Noise session carries sequential request/response exchanges
until either side closes it. Clients keep a separate session for each
`workgroup.pull` subscription, one for `link.ask`, and a shared RPC session for
short calls. A held pull never serialises another workgroup or a post, and
`link.cancel` can reach a running ask. A per-session lock keeps cipher counters
ordered; broken sessions are discarded without replaying the request, and the
next call reconnects. Clients retire sessions after 60 idle seconds and
responders close them after 90 seconds (10 seconds for an unrecognised Noise
identity waiting to present its signed envelope).

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
  "params": {"prompt": "…", "budget": {"usd": 0.50}},
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
  last five minutes. The receiver journals live pairs under
  `alp/secrets/replay.jsonl`, so restarting the daemon does not
  reopen that replay window.
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
  conversation?: string         # opaque id of the caller's conversation, [A-Za-z0-9_-]{1,64}
  budget?:
    tokens?: int
    usd?: float
result:                         # when stream is false (default)
  text: string
  session_id: string
  tokens_in: int
  tokens_out: int
  cost: float                   # USD; matches the per-turn ledger entry
  interrupted: bool             # true when link.cancel landed mid-turn
  transient: bool               # true when failure is safe to retry
  history: string               # "conversation" | "peer" | "none" — which @-mention thread was used
```

Runs a **full agent turn** on the target profile with `prompt`
as the user input. The target invokes its complete tool loop,
approval gate, memory subsystem, and cost accounting — exactly
as if the prompt had arrived through an interactive surface.

When `stream: true` the response is delivered as a sequence of
signed response envelopes for the same `id`, each carrying a
`stream` marker:

- `stream: "chunk"` — intermediate frame. Text batches carry
  `result: { text: <delta> }`; control frames carry
  `result: { event: "started" | "progress", session_id: <id> }` and no
  model text. `started` is emitted before the turn runs and `progress` keeps
  an active tool/model turn from looking stalled.
- `stream: "final"` — last frame, `result` carries the same shape as
  the non-streaming reply: aggregated `text`, `session_id`,
  `tokens_in`, `tokens_out`, `cost`, `interrupted`, `transient`.

Caller policy: Alpi's interactive surfaces and agent-internal `peer` tool pass
`stream: true`. Interactive callers render text chunks; `peer` ignores those
intermediate chunks and gives its model only the final atomic reply. Both use
the control frames as liveness, so long active turns are bounded by an idle
watchdog rather than a fixed total duration. The protocol retains
`stream: false` for compatibility with callers that require one response.

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
mentions from the same origin is provided by a separate thread at
`<target-home>/mentions/<from-id>@<conversation>.json`, capped at
the most recent 20 turns and hydrated into the engine prompt
before the turn runs. `conversation` is an opaque, stable
identifier the caller derives from its own source session (Alpi
hashes the session id; it is never a model-written argument), so
repeated asks from one conversation keep their context and a new
conversation starts clean. The thread is keyed by the
authenticated sender **and** the conversation together: the same
`conversation` value sent by another peer selects nothing. A
request that carries `conversation` but cannot establish one
(empty, malformed, too long) runs with no history and writes
none. A request without the key comes from a caller that predates
the identity and keeps the legacy per-sender thread
`mentions/<from-id>.json`; that file is never imported into a
conversation thread and never deleted by this change. `history`
in the result names which of the three applied. An Alpi caller
that sent a `conversation` and did not get `history:
"conversation"` back knows the target predates isolation: the
`peer` tool says so in its output and the sender logs a warning.
Every thread is invisible to the target's local `--continue`
(which only reads `sessions/`). See `alpi/alp/mention_thread.py`.

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
result: { cancelled: bool, session_id: string }
```

Signals the target to abort the current turn for `session_id`.
Maps internally to the same interrupt mechanism the TUI uses
when the user presses Ctrl-C. `link.cancel` is idempotent: a
cancel on a session that is not running returns
`cancelled: false` and makes no other changes.
Only the peer that started the active turn can cancel it. Alpi clients make a
best-effort cancel request after their idle or maximum-duration watchdog fires;
closing a streaming connection also interrupts its still-running target turn.

### `link.put_blob` / `link.get_blob`

ALP transfers explicitly selected non-inline artefacts by SHA-256 without
turning peers into shared filesystems. Blob storage is private to the receiving
profile under `alp/blobs/<sha256>` and capped at 20 MiB, matching the attachment
contract.

`link.put_blob` accepts sequential 512 KiB chunks:

```text
params: {
  hash: string,       # lowercase SHA-256
  size: int,
  offset: int,
  data: string,       # base64
  final: bool
}
result: { hash, size, next_offset, complete }
```

The receiver stages chunks privately, requires an exact next offset, and only
publishes the blob with an atomic rename after its size and full hash match.
Sending the same verified hash again is idempotent.

`link.get_blob({hash})` streams ordered `{hash, offset, data}` chunks followed
by a signed final `{hash, size}` frame. The client writes a temporary file and
publishes the requested destination only after verifying the complete size and
hash. It never overwrites an existing destination.

Every chunk remains inside a signed ALP envelope; cross-machine transfers also
use the Noise session's AEAD. The final request/response signs the full content
hash. Peers need explicit `link.put_blob` and/or `link.get_blob` capabilities.
Console equivalents:

```bash
alpi -p sender peers blob-put receiver ./report.pdf
alpi -p sender peers blob-get receiver <sha256> --output ./report.pdf
```

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
| `-32005` | `budget-exceeded` / `rate-limited` | Request would breach a cap. `message: "budget-exceeded"` for profile (daily) or workgroup (lifetime) spend caps — `data.cap_kind` is `usd` (profile) or `workgroup_usd` (workgroup). `message: "rate-limited"` when the peer's `rate_limit.per_minute` is exhausted — `data.window_seconds` is the sliding-window length. Same code, two reasons; check `message`. |
| `-32007` | `target-busy` | Session already running a turn. |
| `-32008` | `workgroup-not-member` / `workgroup-not-joined` | Caller is not in the workgroup's roster, or is in the roster but has never completed a `workgroup.join`. Check `message`. |
| `-32009` | `workgroup-not-found` | No workgroup with the requested id at the hub. |
| `-32010` | `workgroup-full` | The workgroup transcript has reached its post cap. Same code as `workgroup-paused`; check `message`. |
| `-32010` | `workgroup-paused` | Workgroup is paused; `post` rejected. `pull` / `join` / `leave` still work. |
| `-32011` | `file-not-found` | Requested workgroup file is absent. |
| `-32012` | `blob-not-found` / `file-quota-exceeded` | Generic link blob absent, or a workgroup file upload would exceed its 200 MiB store. Distinguish via `message`. |
| `-32013` | `peer-policy-invalid` | The caller's record in the target's `peers.yaml` has a malformed `tools` block; `data.detail` names the problem. The target refuses every `link.ask` from that peer until the record is fixed. |

The standard JSON-RPC codes (`-32600` through `-32603`) retain
their standard meaning and apply to malformed requests, unknown
methods, invalid parameters, and internal errors respectively.

### Client-side diagnostics

Not every failure travels on the wire. Two conditions are detected
locally and raised by the SDK as plain Python exceptions, with no
JSON-RPC `code` attached:

| Symbol | SDK class | When |
|---|---|---|
| `target-offline` | `alpi.alp.client.TargetOffline` | The peer's Unix socket is missing or the TCP connect is refused. The offline target cannot answer, so this never crosses a wire. |
| `task-missing-slug` | `ValueError` | A `#task` post lacks its required `#<slug>` identifier. Raised client-side before the post is encrypted — the hub stays zero-knowledge against post bodies and could not enforce it anyway. |

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
- **Prefer a private network for TCP ALP.** A private LAN or an
  overlay (Tailscale, WireGuard, or similar) keeps the ALP port off
  the public internet and adds an independent layer of authenticated
  encryption. Public exposure is supported (Noise + pinned keys hold
  on their own) but is not the blessed path.
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
  to disk. Returns a `wg_<base32(10 random bytes)>` identifier
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

- `workgroup.pull(workgroup_id, since, wait_s?) → {posts[], head, current_key_version, sealed_key, members[]}`
  Returns every post with `seq > since`, in order, plus the
  current `head` cursor. `since=0` returns the full transcript.
  The response also echoes the caller's currently-sealed group
  key and the workgroup's `current_key_version` so members detect
  rekeys (e.g., after another member's `leave`) on their next
  pull and update their local key map. A held pull, or a pull returning
  fresh posts, stamps the caller's `last_seen_at`; an empty nonblocking
  idle probe does not. Every response returns a fresh roster snapshot
  (`{pubkey, last_seen_at, bio}` per member) so liveness and
  self-published bios stay current without an extra verb. Pull is
  the canonical fan-out for ALP.3 — each member observes new
  traffic by polling. **Long-poll (ALP.4):** an optional `wait_s`
  (clamped to 25 s) holds the request at the hub when no fresh
  posts exist and answers early the moment one lands, giving
  active members near-instant wake without any push
  infrastructure; SSE-style continuous streaming remains future
  work.

- `workgroup.file_put(workgroup_id, sha256, name, size, key_version, nonce, offset, data_base64, done, note?)`
  Uploads one 256 KiB ciphertext chunk to the hub. The SHA-256 and
  size describe the plaintext; the complete ciphertext is one
  ChaCha20-Poly1305 message under the workgroup key. The hub checks
  offsets, decrypts and verifies the completed file, stores it by
  plaintext digest, then appends an encrypted `#file <name> ·
  <size> · sha256:<digest>` marker authored as the uploader. Files
  are capped at 20 MiB and the workgroup file store at 200 MiB.

- `workgroup.file_get(workgroup_id, sha256, offset) → {data_base64, size, ciphertext_size, eof, name, key_version, nonce}`
  Returns one ciphertext chunk. The member reassembles it, opens the
  retained sealed key for the file's `key_version`, decrypts, and
  verifies plaintext size and SHA-256 before writing locally. There
  is no automatic download and file bytes never enter the transcript.

- `workgroup.file_list(workgroup_id, offset?, limit?) → {files, total, next_offset}`
  Lists stored file metadata newest-first without downloading content.
  Results are paginated (50 by default, 200 maximum); each row carries
  `name`, `size`, `sha256`, `uploaded_by`, `uploaded_at`, and `note`.
  This keeps files discoverable after their `#file` marker leaves the
  recent-post context window.

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
`<profile-home>/alp/workgroups/<wg_id>/`:

- `meta.yaml` — `id`, `name`, `hub_pubkey`, `created_at`,
  `current_key_version`, the plaintext `briefing`, optional `budget`,
  optional `paused` flag (with `paused_at` / `paused_by` audit fields when
  set), the closure-quorum timeout, and — for a pipeline — the declared
  chains and their per-phase steps.
- `members.yaml` — list of `{pubkey, sealed_key, key_version,
  joined, joined_at}`. The `joined` flag flips on first successful
  `workgroup.join`; pre-join state lets the hub distinguish
  invited-but-not-yet-acknowledged from active members.
- `transcript.jsonl` — append-only ciphertext log; one
  `{seq, ts, from, key_version, nonce, ciphertext, cost?}` per
  line.
- `ledger.json` — cumulative `{usd, tokens, posts}` across the
  workgroup's lifetime; the gate for the `max_usd` budget below.
- `hub_keys.json` — hub-only sealed-key history, `{key_version:
  sealed_key}`. On every rekey (`leave` / `kick` / `add_member`)
  the hub stashes the group key it held for the outgoing version,
  re-sealed for itself, before rotating. It stores **sealed** keys
  (openable only by the hub's own private key), never plaintext
  group keys, so it can still fold and close a task opened under a
  rotated-out version.
- `files/<sha256>.bin` + `files/<sha256>.json` — encrypted file
  sidecar and plaintext metadata (`name`, size, digest, key version,
  nonce, uploader, timestamp, note). Interrupted uploads remain as
  hidden `.part` files and expire lazily after 24 hours.

The hub stores **post and file contents as ciphertext**. Workgroup
metadata, including file names and notes, remains plaintext. An
operator who inspects the transcript or a `.bin` sidecar sees no
message/file contents without a member's private key. This is what
makes the `leave` rekey meaningful: re-sealing the new group key cuts
off ex-members from new traffic without having to also re-encrypt
past posts or files.

### Transcript search (ALP.6)

Because the hub holds the authoritative, decryptable transcript, semantic
search over old workgroup history is a **hub-local** capability, not a
protocol extension. The `index_workgroups` / `workgroup_search` tools decrypt
the hub's own transcript (through the existing key-history-aware decrypt path),
embed it locally, and store a derived index in the profile's `knowledge.sqlite`,
the same `fastembed + sqlite-vec` layer as workspace knowledge and session recall.
This stays inside the ALP trust model: a profile only ever indexes workgroups
it hubs, there is **no cross-peer or federated search**, and removing a
workgroup purges its index. No new ALP verbs, no change to the wire or the
ciphertext-only on-disk format.

### Hub availability

Workgroups are **hub-anchored**: when the hub's machine is
offline, the workgroup is cold. Members cannot post, cannot pull
new messages, and cannot join until the hub returns. The protocol
intentionally does not provide a failover path, replication, or
consensus-driven re-election. Operators who want always-on
workgroups host the hub on an always-on machine (a home server, a
small VPS, a Raspberry Pi), which is the deployment the protocol
optimises for.

### Working inside a workgroup

Briefings, `#task` / `#done` markers, recipes, pipelines with deterministic
gates, the autonomous poller and the ways a human steers a workgroup are
operational behaviour of the reference implementation, not wire protocol.
They live in [WORKGROUPS.md](WORKGROUPS.md).

### Budget inside workgroups

A workgroup may carry its own optional **lifetime** budget — a
project-scoped ceiling that, unlike the profile budget, does not
reset. The profile budget answers *"how much can my agent spend
today?"*; the workgroup budget answers *"how big can this
collaboration grow before someone reviews it?"*.

```yaml
# meta.yaml inside <profile-home>/alp/workgroups/<wg_id>/
budget:
  max_usd: 5.00
```

`max_usd` is optional and mirrors the profile-budget shape (dollars or
nothing — no token cap). Workgroups without a configured budget inherit
no ceiling of their own; the profile caps are the only stop.

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
An author MAY also split the total — `tokens_in`, `tokens_out`,
`cached_in` and `measured_in`. `measured_in` is the input from
completions whose provider reported cache info at all: the honest
denominator for a hit rate. `cached_in` is the prefix-cache share of
that, and the hub clamps both (`cached <= measured <= tokens_in`), since
a share cannot exceed its base. The distinction the fields carry is
absence: an ABSENT `cached_in` means the provider reported nothing,
while `0` means a measured miss — the two must never be conflated,
because coercing silence to zero biases every fleet hit rate down.
Entries written before the split carry `cached_in` alone; readers use
`tokens_in` as their denominator.
This is the same trust model the profile-level ledger applies to
LiteLLM's reported cost — declarations come from a known
identity, not from a verified receipt. The author SHOULD report
the LLM spend that produced the message; the hub records it in
the workgroup `ledger.json` and checks cumulative `used + declared
> cap` before admitting the post (`-32005 budget-exceeded` with
`data.cap_kind = "workgroup_usd"`).

### Member liveness

The hub stamps a `last_seen_at` ISO timestamp on each member when it
posts, holds an active pull or receives fresh posts through a pull, and
returns the full roster (`[{pubkey, last_seen_at, bio}]`) on `join`
and on every `pull`. Each member caches the roster locally and the
pre-turn hook renders it into the system prompt as e.g.
`@alice (online, "product engineer — velocity") · @bob (last seen
12m ago, "systems engineer — durability") · @carla (offline >30m)`.
"Online" means real workgroup activity was seen within 180 seconds;
empty idle probes do not refresh presence.

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

---

## Versioning

The `alp.v` field in every envelope carries the integer protocol
version the sender speaks. Receivers MUST silently drop messages
with an unknown version — same posture as bad signature, replay,
or stale timestamp (see **Envelope**). No JSON-RPC error reaches
the wire; this denies the sender any oracle.

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
