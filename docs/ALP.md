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
```

| Field | Required | Meaning |
|---|---|---|
| `id` | yes | Human handle. Unique within this profile's peer list. Not transmitted on the wire and not used to locate the target — the daemon resolves intra-machine peers by `pubkey` against the other local profiles' keypairs, so naming a local peer under an arbitrary `id` is fine. |
| `alias` | no | Optional display label. |
| `pubkey` | yes | Base64-encoded Ed25519 public key. The sole routing key for intra-machine dispatch. |
| `address` | for inter-machine | `host:port`, opaque to ALP — resolved by the OS at dial time. Any reachable host works: a LAN IP, a private hostname, a Docker/compose DNS name, a VPN / Tailscale / WireGuard address, or a public IP. ALP does no discovery, NAT traversal, or relay — you supply the address. Omit for intra-profile peers (the local Unix socket is resolved by `pubkey`). |
| `allow` | yes | Fail-closed list of methods the peer may invoke. `workgroup.*` methods bypass this list — workgroup membership (enforced per-handler with `-32008 workgroup-not-member`) is the real gate. |
| `rate_limit.per_minute` | no | Throttle. Default `60` requests/min/peer (`alpi/alp/rate_limit.py::DEFAULT_PER_MINUTE`). Enforced before handler dispatch; over-cap requests get JSON-RPC `-32005`. |

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
  `tokens_in`, `tokens_out`, `cost`, `interrupted`.

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
| `-32008` | `workgroup-not-member` | Caller is not a pinned member of the workgroup. |
| `-32009` | `workgroup-not-found` | No workgroup with the requested id at the hub. |
| `-32010` | `workgroup-paused` | Workgroup is paused; `post` rejected. `pull` / `join` / `leave` still work. |
| `-32011` | `file-not-found` | Requested workgroup file is absent. |
| `-32012` | `blob-not-found` / `file-quota-exceeded` | Generic link blob absent, or a workgroup file upload would exceed its 200 MiB store. Distinguish via `message`. |

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

- `workgroup.pull(workgroup_id, since, wait_s?) → {posts[], head, current_key_version, sealed_key, members[]}`
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
```

A freshly created workgroup is dormant until its first post: every
wake trigger keys off transcript content, so an empty transcript
wakes nobody. The kickoff is always an explicit first post — the
hub's opening `#task` (from the TUI, CLI, or a bootstrap script).

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

### Recipes (host-plane launch)

Creating a workgroup by hand means naming it, picking members,
writing a briefing, and — for a pipeline — spelling out every
phase, owner, and gate. For workgroups launched repeatedly with
the same shape (a standing review board, a per-project production
line), that shape is *constant*; only a parameter or two and the
brief change. A **recipe** captures the constant shape as data, so
a launch is "load this file, fill the blanks."

A recipe is a plain YAML file. A hub keeps reusable recipes in
`<profile-home>/recipes/<id>.yaml`; the filename stem is the recipe id.
Clients list those recipes through the host plane and launch them by id.
One-off or externally versioned recipes remain supported: the desktop file
picker and CLI can read any `.yaml` / `.yml` file and hand its contents to the
daemon. Both routes use the same parser and launcher.

Recipes are a **host-plane** convenience, not part of the ALP wire
protocol — ALP gains no recipe or project verbs. A launch just
assembles the existing `workgroup.create` primitive (plus, when
asked, a project clone) from the resolved recipe. Three host methods:

- `host.workgroup.recipes.list(profile)` — list and describe the saved
  recipes owned by that hub profile. A saved recipe declaring another hub is
  rejected.
- `host.workgroup.recipes.describe(yaml)` — parse a recipe and
  return its shape (hub, declared params + patterns, briefing
  draft, whether it clones a project). Scope-free; the desktop
  uses it to render the launch form.
- `host.workgroup.launch_recipe(profile, recipe_id, yaml?, params,
  briefing?, inputs?)` — admin verb. Without `yaml`, the daemon loads
  `<profile-home>/recipes/<recipe_id>.yaml`; with `yaml`, it launches the
  supplied content. In both cases `profile` must be the recipe's hub and own
  the launch. `inputs` is a `{name: value}` map for the recipe's declared
  inputs (below).

**Three shapes from one format.** A recipe declares only what it
needs:

- *Deliberation* — `task` only, no pipelines, no project: a
  round-table that opens on its kickoff post.
- *Pipeline* — adds `pipelines` + `pipeline_steps` (see
  *Deterministic phase gates*): one or more ordered, gated chains.
- *Project* — adds a `project` block: clone a template repo into
  the workspace and seed it before the launch chain starts.

**Named pipelines — one map, one order.** A recipe declares every
chain in a single map and names which one the launch kickoff opens.
There is no second "operations" concept and no per-step `next`:

```yaml
pipelines:
  setup: [setup, enrich, intake, assets, content, translation, build, qa]
  media-update: [media-update, media-config, media-build, media-qa]
launch: setup
```

- Every key MUST equal its own first phase, so the key is an identity
  the task protocol already carries — `#task #<pipeline>` opens it
  with no alias layer to resolve.
- **Phases are globally disjoint.** A slug belongs to exactly one
  chain, so a task slug has at most one owning pipeline and the active
  chain never depends on YAML order.
- `launch` is optional. Without it the workgroup starts **idle**: no
  kickoff post, no active phase, and every declared chain waits for an
  explicit trigger. A recipe that declares `pipelines` without
  `launch` may not also declare a `task` — posting it would break the
  promise that nothing starts on its own, and silently dropping it
  would hide an authoring mistake.
- Order lives in the chain and nowhere else. A `pipeline_steps` entry
  that declares `next` is rejected, naming the source of truth:
  `pipeline_steps['content'].next is derived from pipelines['setup']`.
- A chain may run again for every later delivery; each run starts
  fresh (see *Pipeline runs*).
- The chain is chosen from the LATEST close alone. A `#done` whose
  slug belongs to no declared chain resolves as unknown, and the core
  opens nothing rather than resurrecting finished work.

**Triggering a declared pipeline.** Any declared chain is addressable
by key:

```text
alpi -p <hub> workgroup trigger <wg_id> <pipeline>
```

The host verb is `host.workgroup.trigger(profile, wg_id, pipeline)`.
The daemon resolves the chain's first phase and publishes exactly

```text
@<declared owner> #task #<first phase> · <declared task>
```

copied verbatim from `pipeline_steps` — clients never author that
post, so a chain cannot start on operator prose that drifted from the
recipe. It follows the normal workgroup post path, so owner
validation, transcript ordering, events, dispatch and gate handling
stay single-sourced. **Pipelines run one at a time.** Starting a chain stops whatever was
mid-flight: the opener preempts an open task (the transcript records the
displaced phase as `preempted by #<slug>`, never as done) and the
displaced run stops being advanced. The trigger returns what it stopped
(`{pipeline, phase, status, open_task, same_pipeline}` or `null`) so
every surface can name it before and after — a `blocked` run counts as
stopped too, since what it loses is its position. An operator starting a chain
is an explicit abandon, so the trigger is exempt from the
`phase-gate-abandoned` guard — that guard exists to stop the HUB talking
its way past a red gate, not to stop a human changing course.

Trigger is hub-admin only. An unknown key, a paused workgroup, a
subscriber, or a first phase with no declared owner/task
(`pipeline-trigger-contract-missing`) are rejected without appending
anything. Recipe validation enforces that contract for every
declared chain, including the launch one, so a recipe cannot ship a
chain nobody can start.

**A recipe is the only place chains are declared.** There is no manual
pipeline creation and no post-launch editing: `workgroup create` makes
a deliberation workgroup, `workgroup update` refuses a `pipeline`
argument, and every client surface is read-only. The reason is
structural — a client can edit a phase *list* but cannot write
`pipeline_steps`, and a phase with no declared owner and task cannot be
dispatched or triggered. Changing a chain means editing the recipe and
launching again.

**The retired shape is rejected, not migrated.** `pipeline: [...]` plus
`operations: {name: {steps: [...]}}` is gone. A recipe carrying either
key is a `RecipeError`; a `meta.yaml` carrying either does not load (the
daemon logs which workgroup and why, and skips it, and its
`host.workgroups.list` row carries `needs_relaunch: true` so the apps can
say so); a subscription entry carrying either is skipped — logged once,
and dropped for good on the next save. Nothing writes those keys any
more.

A workgroup created before the upgrade therefore stops loading. There is
no migration path by design: relaunch it from the updated recipe, which
is the only thing that can supply `pipeline_steps` anyway.

**Parameters vs inputs — two kinds of operator-supplied value.**

- `params` are single-line **interpolation tokens**: every `{name}`
  in the recipe's strings is a declared param, each required, with
  an optional `pattern` regex the value must fullmatch. Resolution
  is a single non-recursive pass — a param cannot smuggle in YAML, a
  marker (`#done`/`#task`), or a newline (all rejected). Undeclared
  placeholders or unsupplied params fail the launch before anything
  is created.
- `inputs` are multiline **file seeds**: arbitrary operator-provided
  text written verbatim to a file in the clone. Each input declares
  a `dest` (relative path inside the project), an optional `label` /
  `placeholder` for the form, and `required` (default true). Inputs
  are *not* interpolated and carry no injection surface — they are
  content, not tokens — so they carry the material a param can't
  (a whole client brief). Inputs require a `project` block.

This split is why web-factory keeps the *workgroup briefing*
(metadata, a param-interpolated string) separate from the *hotel
brief* (an input written to `brief.md`): different roles, different
constraints.

**The atomic launch.** A project recipe materialises as one unit,
rolled back whole on any failure:

```
validate → clone (into staging) → seed → move into place →
write recipe inputs → workgroup.create → kickoff post
```

The dynamic values — the operator-edited briefing, the declared
`inputs` — land *before* `create` and the
kickoff, so the first `#task` reaches a project that already
carries its final declared input files; binary media is added to the
project's git after launch. Required inputs are validated before the
clone, so a missing one fails fast with no orphaned project. A
failure at any later step removes the workgroup (including the local
member subscriptions auto-join created) and the cloned project; the
launch returns `{workgroup_id, project_path}` only after every step
succeeds.

**Seed** writes template config before the pipeline runs, via two
explicit ops under `project.seed`:

- `json_merge: {path: {…}}` — deep-merge a patch into an existing
  JSON file (objects merge; scalars and arrays replace).
- `files: {path: contents}` — write a fixed file outright (e.g. an
  `intake.md` stub the pipeline later fills). Seed is recipe-authored
  boilerplate; operator-supplied content is an `input`, not a seed.

**Provenance.** The launched workgroup records its origin in
`meta.launch` — recipe id, content digest, resolved params,
project destination, and the template commit it cloned — so an
audit can tie a running workgroup back to the exact recipe that
produced it. Editing the source recipe never mutates a live
workgroup.

**Surfaces.** Launch a saved hub recipe from the CLI —

```
alpi -p mira workgroup launch --recipe hotel \
  --param slug=casa-bahia --input brief=./brief.md
```

`--recipe` accepts either a saved id or a YAML path. `--input NAME=FILE`
seeds the declared input `NAME` with FILE's contents (repeatable). The desktop
New Workgroup modal lists recipes saved by the selected hub and keeps
"Import recipe…" as a separate file-picker path. After either selection it
renders the same fields: hub, name, briefing, a field per declared param and a
textarea per declared input. The operator can edit the briefing draft before
launching.

A worked recipe (only `{slug}` varies per launch):

```yaml
hub: mira
members: [scout, quill, lingua, pixel, lens]
name: "proj-{slug}"
quorum_timeout_seconds: 180
budget_usd: 50

params:
  slug:
    pattern: "^[a-z0-9][a-z0-9-]{0,63}$"

inputs:
  brief:
    label: "Client brief (immutable)"
    dest: brief.md
    required: true
    placeholder: "paste the raw client brief"

briefing: |
  Workgroup for '{slug}' — produce its launch-ready site.
  Raw brief (immutable): projects/{slug}/brief.md

task: "@scout #task #intake · start {slug}"

pipelines:
  intake: [intake, content, translation, build, qa]
launch: intake
pipeline_steps:
  intake:      { owner: scout,  task: "start {slug}",              gate: { argv: [python3, scripts/intake-check.py],  cwd: "projects/{slug}" } }
  content:     { owner: quill,  task: "author the source locale",  gate: { argv: [python3, scripts/content-check.py], cwd: "projects/{slug}" } }
  translation: { owner: lingua, task: "bring locales to parity",   gate: { argv: [python3, scripts/content-check.py], cwd: "projects/{slug}" } }
  build:       { owner: pixel,  task: "build the site",            gate: { argv: [test, -d, dist],                    cwd: "projects/{slug}" } }
  qa:          { owner: lens,   task: "audit and return a verdict" }

project:
  template_repo: git@github.com:acme/site-template.git
  dest: "projects/{slug}"
  seed:
    files:
      intake.md: "# Intake — {slug}\n\n(scout fills this in the intake phase)"
```

A recipe's gates are `argv` run node-free on the daemon (the
example uses `python3`), matching *Deterministic phase gates* — the
checks are raw commands, never engine turns.

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
  member, or a pinned peer for the TUI / desktop
  shortcut). Strings like `@property` in code snippets fall
  through silently because no peer named `property` exists.

The TUI (`alpi/tui/app.py`) and the desktop host plane
(`alpi/host/chat.py`) both parse via `alp_mention.parse(text,
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
`agent.log` and (optionally per workgroup) pushes the summary
to the owner's own apps via `notify` — `notify_on_close` in
`meta.yaml`, defaulting to none.

### Budget inside workgroups

A workgroup may carry its own optional **lifetime** budget — a
project-scoped ceiling that, unlike the profile budget, does not
reset. The profile budget answers *"how much can my agent spend
today?"*; the workgroup budget answers *"how big can this
collaboration grow before someone reviews it?"*.

```yaml
# meta.yaml inside ~/.alpi/<profile>/alp/workgroups/<wg_id>/
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

### Autonomous engagement

Workgroups are useful only if the agents inside them act without a
human in the loop. Each member runs a poller that wakes its agent
on relevant new traffic, plus a pre-turn context hook that injects
workgroup state into every engine turn.

**Poller.** Every remote subscription owns one independent held
pull (`wait_s`≤25 s), so workgroups wait concurrently and a fresh
post returns immediately even after a long idle period. An empty
successful pull is reopened at once; only transport failures back
off exponentially (30 s to 15 min). Local hub workgroups use a 5 s
transcript-stat probe whose decrypted result is cached, so an idle
fleet performs no model work and little file I/O without becoming
deaf. Fresh posts, open tasks and in-flight dispatches use the
short 10 s dispatch cooldown. Per workgroup the poller compares
the cached transcript against a ``last_responded_seq`` cursor and
dispatches an engine turn when any of these triggers fires (in
priority order):

1. The newest unresponded post `@`-mentions this member — unless
   the mention sits inside a `#done` post (a closure crediting
   people is synthesis, not a handoff; it wakes nobody), or the
   workgroup is a **pipeline** and the post's author is not the
   hub: sideways member→member mentions never wake there (routing
   goes up — a member reports to the hub, the hub assigns), while
   member mentions OF the hub still do.
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

When none of these fire, one fallback trigger runs: a member whose
own latest post in the active task was `#working` (and who has
posted nothing since) is re-dispatched so the promised delivery
isn't lost to a missed wake.

A per-workgroup cooldown rate-limits dispatches so two peers don't
ping-pong. When a trigger fires, the poller invokes one engine turn
against the workgroup and exits. The synthetic prompt explicitly
states the agent is running alone with no human in the loop, so it
posts via `workgroup.post` or stays silent rather than asking a
non-existent human for permission.

**Pre-turn context hook.** Before every engine turn (interactive,
scheduled, or workgroup-spawned), the hook reads the
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
scheduled turn. The protocol does NOT inject "use these
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
2. **Closure quorum (full + substantive), scoped to the task's
   participants.** A hub `#done` is rejected with `closure-quorum`
   unless BOTH:

   - **Full participation across the quorum roster**: a `#task`
     whose opener line `@`-mentions specific members narrows the
     roster to just those members; a collective task (no mentions)
     expects every member in `members.yaml`. Mentioned names that
     resolve to no known member fall back to the full roster. Each
     expected member must have posted at least once in the active
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

**Concurrency is opportunistic, not a worker-pool guarantee.**
The single-flight key is `(workgroup_id, profile)`, not just
`profile`: the runtime does not impose a global queue where one
profile must finish every other workgroup before reacting to the
next. A profile may therefore have turns running in different
workgroups at the same time. That is useful for latency, but it
does not make a profile a stateless parallel worker. The profile
still shares one home directory, memory, skills, logs, budgets,
provider credentials, model limits, and any local tool resources.
Operators should treat this as best-effort concurrency rather
than a throughput SLA or a fairness scheduler. For predictable
high-throughput production, add more profiles/workers or run
fewer active workgroups at once.

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

**Pipeline workgroups (`meta.pipelines`).** Declaring at least one
named chain turns a workgroup into a pipeline: every `#task` must be
`@`-targeted (`pipeline-task-untargeted` otherwise — each phase has
one owner), and after the hub's `#done` the runtime detects the
closure and re-wakes the hub to open the next phase's task (bounded
to 3 continuation wakes per closed seq before a `wg.blocked` alert).
The flag is `pipelines`, not the launch selector: an idle workgroup
that declares chains but selects none for launch gets the same
targeting, turn budgets and closure rules as one that launches.

**What members learn.** `workgroup.join` and `workgroup.pull` carry
`pipelines`, `launch_pipeline`, `pipeline_mode` and a `phase_map` of
`{owner, task?}` per phase — never gate `argv`/`cwd`, never gate
output, never recipe provenance. Every successful pull refreshes them,
so a hub-side edit reaches existing subscriptions without a rejoin,
and the member's agent context renders the chains directly instead of
depending on a briefing that narrates them by hand.

**Deterministic phase gates (`meta.pipeline_steps`, hub-local).** A
phase may declare `{owner, task, gate: {argv, cwd?}}` in the
hub's own metadata — never transmitted on the wire, never accepting
remote text into `argv`/`cwd`. When the expected owner posts while
that phase is active, the runtime executes the gate locally
(`shell=False`, cwd jailed inside the configured workspace, minimal
env without profile secrets, bounded timeout and output) and, on
success, closes the phase and opens the next one itself through the
normal hub SDK path — rotation, quorum and `task-already-active`
still apply, and the machine-authored close is auditable
(`#done <phase> verified · gate:<check> · …` plus a private
`gates/<phase>-<seq>.log`, mode 0600). A failing gate never
advances: it wakes the hub's agent with the bounded error, one
attempt per owner post. Phases without a step (or whose transition
needs judgment — intake signals, QA) stay LLM-owned, and so does a
step that declares `{owner, task}` but omits `gate`: it is
still dispatched and owner-typed, it just closes on quorum instead of
on a check. Omitting the gate is the right call for a phase that may
legitimately produce nothing — its owner posts `#skip`, then the hub
closes `#done skipped · <reason>` before any substantive delivery —
because a gate there would fail a correct outcome.

`skipped` remains valid only while the resolved owner has made no
substantive delivery for that phase in the current pipeline run. Reopening
the same or an earlier phase, including the first, does not erase an earlier
delivery. Only an explicit operator pipeline trigger starts a fresh run.
Unresolved ownership fails closed and requires re-pinning or an explicit
`BLOCKED` close.

**Per-phase authorship (`pipeline_steps.*.paths`, hub-local).** A gated
phase may declare the path globs its owner is allowed to touch. When the
task opens the daemon snapshots the project's file state (derived trees
— `node_modules`, `dist`, `.git`, `.astro`, `public` — excluded); when
the gate would run, changes outside the declared globs red the phase
*before the command executes*, naming each file and its owner — gate
pressure is precisely what causes cross-phase edits, so the edit is
surfaced instead of graded. The dispatched owner receives the same globs as
its native file-tool write boundary; non-owners cannot use native file
mutation tools during that phase. On bare metal, `terminal` keeps the workspace
readable but is forced through the OS sandbox even when the profile disables
it: only exact literal paths and trailing `/**` subtrees are writable,
unsupported globs fail closed, and `ALPI_HOME` stays read-only. A scope-only
sandbox preserves the profile's existing network access. In the official
Docker runtime, `terminal` is unavailable during scoped phases; native file and
search tools remain available and daemon gates still run. Phase denials are
reported separately from profile `tools.deny`; the gate remains the final
workspace-diff audit. A missing or unreadable baseline fails closed because
the daemon cannot prove
lane ownership. `paths` requires a `gate` — its `cwd` anchors the project root
and its run is the check moment.

**The gate is level-triggered where the transcript alone would strand a
run.** Four behaviours close the measured stall family: a red verdict is
provisional, so the poller re-runs the gate on the open phase — no new
post required, no hub wake spent — and an owner who fixed the workspace
without re-posting gets a machine close. A still-red re-run is SILENT:
it neither re-posts the round's findings nor consumes a repair round,
because the note the owner needs is already in the transcript. Re-runs
are held to one per phase per interval, skipped while a turn is live for
the workgroup, and skipped again unless the project's content fingerprint
moved since the red verdict — so a permanently red gate is spawned once,
not on every tick. A watchdog pass verifies through those SAME guards —
there is no bypass, because an unguarded verification respawns a stalled
red gate's command on every tick. The wake still fires either way; the
findings it would re-carry are already in the transcript.
`workgroup resume` clears the in-memory gate state for the workgroup, so
a delivery parked behind a pause re-fires its gate on the next tick. A
terminal close whose verdict carries the owner's exact failure token in
verdict position (a `·`-segment starting with it: `#done <phase> ·
QA FAIL · …`; prose mentions, quotes or negations do not count, and a
FAIL may not stand in for a BLOCKED) and routes nothing draws exactly
ONE follow-up wake — re-task the findings or leave the run halted,
loudly. And the targeted phase owner
is exempt from the one-post-per-round rotation cap: a repair delivery
may arrive in pieces (a fix note, then the re-delivery the gate re-runs
on) without muting the owner. A `#done BLOCKED` still halts its chain,
but a hub `#task` on any phase EARLIER in the chain is now allowed. A
rewind re-walks the same run, including when it returns to the first phase.

**One authority decides the successor.** Both the continuation path (a
phase closed by quorum, gate-less or LLM-owned) and the gate path call
`pipeline_successor(meta, phase)`: the slug after `phase` in its own
chain, empty at the terminal phase. A phase can no longer advance
differently depending on whether its gate ran, and there is no way to
declare an order that disagrees with the chain.

**Order is single-sourced, but who WRITES the successor's `#task` still differs by path.** On the
gate path the daemon opens the next phase itself with the step's declared
`task` verbatim (`@owner #task #<phase> · <task>`). On the continuation
path it wakes the hub AGENT, which authors the opener in its own words —
so the successor's declared `task` is never sent. Making a phase gate-less
therefore delegates the wording of the NEXT phase's task to the hub, and
any recipe-side length or content discipline on that text stops binding.
Each accepted
`workgroup.post` also nudges the hub's poller in-process
(`alp/wakes.py`), so gate reactions are near-immediate; polling
remains the recovery path.

**A recovery slug resolves to its longest declared phase.** Exact phase
membership wins first; otherwise the longest declared-phase prefix of
the slug is the phase it repairs, so `#content-fix`, `#content-recheck`
and an invented `#content-repair` all canonicalise back to `#content`,
and a green repair of the TERMINAL phase completes the run instead of
reopening the phase before it. Longest — not shortest — is what keeps a
declared operational chain like `#content-update` from being swallowed
by `#content`. A `#task` whose slug still maps to no declared chain is
REFUSED at post time (`task-slug-unroutable`, naming the declared
phases): an unroutable opener nulls the run and closing it advances
nothing, which used to strand a pipeline with every check green.

**Pipeline runs.** Static definitions and the currently relevant run
are separate surfaces. `host.workgroups.list` returns the definitions
without decrypting anything; `host.workgroup.tasks` folds the task
ledger and adds `pipeline_run`:

```json
{
  "pipeline": "media-update",
  "status": "running",
  "started_seq": 37,
  "current_phase": "media-build",
  "phases": [
    {"slug": "media-update", "state": "completed", "seq": 40},
    {"slug": "media-config", "state": "skipped", "seq": 42},
    {"slug": "media-build", "state": "current", "seq": 43},
    {"slug": "media-qa", "state": "pending", "seq": null}
  ]
}
```

`status` is `running` (a mapped task is open), `between` (a
non-terminal phase closed and its successor is not open yet),
`blocked`, or `completed` (the terminal phase closed). A
`#done skipped · <reason>` advances the chain but records `skipped` —
never collapsed into `completed` — and is rejected once the owner has
posted a substantive delivery. Delivered work must pass its gate,
repair the same phase, or close `BLOCKED`. A blocked phase stays
`current` and the run-level status carries the failure.

The LATEST task overall selects the visible run, so an ad-hoc task
opened after a chain makes `pipeline_run` null rather than leaving a
finished chain on screen. Runs are cut at boundaries, not at every
occurrence of a first slug: a same-slug reopen — the first phase
included — is another attempt inside the current run and the latest
attempt owns the phase's visible state. Only an opener written by the
explicit operator trigger starts a fresh run. A
preempted attempt is never `completed`. The fold is cached by
transcript identity plus a fingerprint of the definitions, so a
metadata edit can't serve a stale mapping and repeated reads don't
re-decrypt. Console, desktop and mobile all consume this contract;
none of them decides independently which pipeline is active.

**Re-tasking, and what actually stops a peer.** Opening a new `#task`
is the single way to change direction. `fold_tasks` keeps one task open
at a time, so the previous one closes with
`result = "preempted by #<new slug>"` — a preemption is never reported
as done, in the fold or in any client.

A peer already working does not merely have its answer ignored; two
independent mechanisms stop it:

- the **preempt watcher** (`_run_preempt_watcher`, 5 s tick) compares
  each in-flight dispatch's `started_against_task_seq` against the
  hub's latest `#task` seq and sends `SIGTERM` to the subprocess when a
  newer one exists;
- if a turn survives that anyway, its post is rejected by the SDK with
  `stale-round`: the dispatcher stamps `ALPI_WORKGROUP_ROUND_HUB_SEQ`
  into the child's environment, and `_check_member_round_fresh` refuses
  a post whose round the hub has already moved past.

Only a fresh `#task` preempts. A hub `#done` is caught by
`stale-round` alone, by design — closing a task is not a change of
direction.

**In a deliberation workgroup** any hub `#task` is accepted, including
a collective one with no `@`-mentions, and re-tasking with a different
slug is the normal pivot. Re-opening the slug that is already active is
rejected (`task-already-active`) — a duplicate would only preempt
itself. A `#done` there is terminal: nothing continues afterwards.

**In a pipeline workgroup the same pivot is deliberately harder.**
Every `#task` must name its owner (`pipeline-task-untargeted`
otherwise), and a declared phase's opener must mention the owner the
recipe declared (`workflow-task-owner-missing`). On top of that:

| While the open phase is… | A manual `#task <other slug>` |
|---|---|
| gate-less, same chain | accepted — it preempts, and the chain stops being reported |
| gate-less, another declared chain | **rejected** with `chain-jump` — declared chains are trigger-only |
| gated | **rejected** with `phase-gate-abandoned` |

The refusal is the point. If the hub could open `#build` while
`#content` sat red, the gate would be worth nothing — the guard exists
so a failed check cannot be renamed out of the way. Because nearly
every phase in a production recipe declares a gate, a hand-written
`#task` mid-chain will usually be refused; `workgroup trigger` is the
one path exempt from it, since there the decision to abandon is
explicitly an operator's.

**An ad-hoc task stops the chain, and the chain does not resume by
itself.** A slug that belongs to no declared pipeline makes
`pipeline_run` null and leaves the core with nothing to infer:

```text
@pixel #task #hotfix urgent      → pipeline_run: null
#done hotfix shipped             → next None, known False — no advance
```

`_next_pipeline_phase` reports the close as unknown rather than
guessing a successor. Two ways out, and they are not equivalent:

- **re-open the phase** — `@scout #task #setup …` puts the run back at
  that phase with the earlier ones `pending`, and its close continues
  the chain normally (`#setup` → `#build`);
- **trigger the chain again** — starts a *fresh* run from its first
  phase, discarding the position it had reached.

So recovery after a detour is a phase re-open, not a re-trigger. The
same distinction applies to a chain a trigger has just displaced: what
was lost is its *position*, not its work — the transcript still holds
every post, and re-opening the phase it had reached picks it back up.

**Where each surface stands.** Definitions are read-only everywhere
outside the recipe, and the apps are read-only on runtime too: the chat
shows the running chain, settings list the declared chains and mark the
launch one, and neither starts anything. The trigger is an operator
verb: `workgroup trigger` on the console, `host.workgroup.trigger` on
the host plane.

The
closure-quorum grace is per-workgroup via
`meta.quorum_timeout_seconds` (default 600 s, editable in
`alpi setup → Workgroups`).

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
  (post `#done` or stay silent), then a `wg.blocked` alert; a
  `#done` is terminal there. Closure-only wakes are SDK-enforced:
  the dispatched turn runs with `ALPI_WORKGROUP_CLOSURE_ONLY=1` and
  `workgroup_client.post` rejects any non-`#done` post
  (`closure-only`), so a nudged hub cannot reopen the round with
  fresh content.
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
  exceeds its ceiling — two independent limits, both
  pipeline-aware: an **idle** kill when the subprocess emits no
  event/output for 180 s (300 s in pipeline workgroups), and a
  **backstop** kill at 300 s total (900 s in pipeline
  workgroups). The dispatcher SIGTERMs with a 5-second grace then
  SIGKILLs.
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
