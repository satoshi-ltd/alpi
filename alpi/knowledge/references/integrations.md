# Integrations answer pack

## Answer directly

To let external code (a Node/Java service, CI step, script) talk to a
profile or workgroup, the code becomes a **host-plane client** of a
specific daemon — the same role the apps play. It dials the daemon over a
WebSocket on a private network (Tailscale/LAN) or through a
certificate-validated WSS reverse proxy and authenticates with a
device credential under a **connection**, calling the same `host.*` JSON-RPC methods. There is no
public HTTP API and no cloud middleman. Use ALP only when you need a
first-class peer identity (`@mention`, peer-level workgroup membership) or
the network is untrusted.

## Routes

| | Host-plane connection | ALP peer |
|---|---|---|
| Use when | app/integration needs the host API | first-class peer identity |
| Transport | WebSocket + JSON-RPC; private `ws://` or public `wss://` | Noise_XK over TCP, signed Ed25519 envelopes |
| Auth | bearer device token, profile-scoped | keypair pinned in `peers.yaml`, capability `allow` list |
| Cost | a WebSocket + JSON | embed an ALP client (handshake + signing) |
| Port | 49200 (`host.tcp_port`) | 7423 (ALP TCP) |

Use plaintext `ws://` only with a private IP literal over Tailscale/LAN. Public
access requires a hostname, a valid certificate and `wss://`; keep the
daemon's plaintext listener private behind the reverse proxy.

## Host-plane client recipe

1. **Listener (machine B).** Config keys: `host.tcp_port` (default 49200),
   `host.allow_public_bind` (default false — public IPs refused),
   `network.host` (advertised address; empty = auto-detect Tailscale then
   LAN). Find the endpoint via `alpi setup` → Connections header
   (e.g. `tailscale · 100.64.50.234:49200`).
2. **Connection (machine B).** `alpi setup` → Connections → New connection. Choose
   **member** (not admin) and restrict `profile_scope` to the profile(s)
   it may reach. The QR / `alpi://device?…` link contains a one-time grant,
   not the permanent token.
3. **Exchange (machine A).** Open `ws://<private-ip>:<port>` or
   `wss://your.domain.com` and send `host.connections.exchange_pairing` as the
   first unauthenticated message with `pairing_token`, `client`, `name` and
   `app_version`. Store the returned device token before probing or doing any
   other fallible setup; the grant expires after ten minutes and the first
   successful exchange consumes it atomically.
4. **Use.** Reconnect and put the device token in `params.auth_token` on every
   request. A member token scoped to one profile is blocked from every
   `_ADMIN_METHODS` method and gets scope-filtered responses/events. One
   WebSocket message = one JSON object.
5. **Revoke.** `alpi setup` → Connections → select the device, or `host.connections.revoke_device`
   (**admin-only** — a member token cannot revoke).

## host.chat.send (streaming; no non-streaming variant exists)

Request `params`: `auth_token`, `profile`, `text` (or `attachments`),
`request_id` (required, non-empty), optional `session_id`, `model`,
`attachments`. The top-level JSON-RPC `id` is echoed on every frame —
demux on it; set it equal to `request_id`. For file input, stage with
`host.attachments.stage` and pass the returned metadata as
`params.attachments`.

Frames are `{ "id", "event", ... }`:

| `event` | Fields | Notes |
|---|---|---|
| `session_start` | `session_id`, `model_used` | first; capture `session_id` to continue |
| `assistant_delta` | `text` | concatenate for the answer |
| `reasoning_delta` | `text` | reasoning fragment |
| `tool_start`/`tool_state`/`tool_end` | `tool_id`, `name`, … | agent ran a tool |
| `auto_compact` | `text`, `tokens_before`, `tokens_after` | context compacted |
| `heartbeat` | — | every 5s; ignore |
| `reply` | `text`, `session_id`, `attachments?` | final answer |
| `done` | `session_id` | **terminal** |

A JSON-RPC `error` (`-32000 auth-failed`, `-32001 forbidden`) rejects the
request. A frame with `event:"error"` (`text`) means the turn failed
mid-stream; it precedes `done`. Continue a conversation by passing the
returned `session_id`. Reconnect/backfill: `host.chat.events_since`
`{ profile, session_id, after_seq }` → `{ events, next_seq, exists,
in_flight }`; track `next_seq`, poll while `in_flight`.

Local automation that must place the chat in an existing paired connection
uses `alpi -p <profile> chat --once <text> --connection-id <id>`. The CLI calls
the Unix-socket-only `host.chat.delegate`, validates that the connection is
active and in scope, and then reuses `host.chat.send`; clients therefore see
the canonical sidecar and `in_flight` state. Never expose delegation over the
WebSocket or implement a second run-to-chat reconstruction path.

## Workgroup methods (member-callable, all take `profile`, scope-checked)

| Method | Params | Returns |
|---|---|---|
| `host.workgroups.list` | `profile?` | `{ workgroups: [{ id, profile, name, members, is_hub, hub_id, … }] }` |
| `host.workgroup.post` | `profile`, `wg_id`, `text` | `{ ok, seq }` |
| `host.workgroup.transcript` | `profile`, `wg_id`, `after_seq?`, `limit?`, `tail?` | `{ posts: [{ seq, at, from, body, cost }], next_seq, limit }` |
| `host.workgroup.tasks` | `profile`, `wg_id` | `{ active, closed, blocked }` |

The token acts as a local member profile; the daemon holds that profile's
keys and does the group crypto. `create`/`update`/`add_member`/`kick`/
`remove`/`action` are **admin-only**.

## Decision rules

- Scope every integration token to one profile; one token per integration
  so revocation is isolated.
- Keep `host.allow_public_bind: false`. Use direct WS only on a private network;
  public access goes through certificate-validated WSS while the daemon port
  remains private. The token is a bearer secret — keep it out of source control.
- Inbound text drives the target profile with its full tool set — scope
  the profile's tools (`tools.deny`, sandbox) to what the integration
  needs; treat it as reachable by whatever reaches the integration.
- Pin the daemon version: `host.*` takes clean breaks across releases.

## What not to promise

- No public HTTP/REST API; no hosted control plane.
- No non-streaming chat method — `host.chat.send` is streaming-only.
- A member token cannot manage devices or administer workgroups.
- `host.*` is not a stable cross-version contract.

## Related topics

- alp — the peer route: identity, signatures, capabilities, workgroups
- security — threat model, approval gate, prompt-injection, sandbox
- config — listener keys, `tools.deny`, budgets
- deployments — laptop / home-server / multi-device shapes, ports
