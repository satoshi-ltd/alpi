# Integrations

How to talk to a profile or a workgroup from your own code — a Node
service, a Java backend, a CI step, anything that can open a WebSocket.

Audience: a developer wiring an external project to an alpi daemon
running on another machine. For the human chat surfaces see the apps;
for agent-to-agent links see [ALP.md](ALP.md).

## The model

There is no public HTTP API and there is no cloud middleman. Your code
becomes a **host-plane client** of a specific daemon — the same role the
mobile app plays. It dials the daemon over a WebSocket — on a private network,
or through a TLS front-end (a self-hosted reverse proxy, or a managed TLS edge
such as a cloud load balancer / CDN) — authenticates with one device credential
under a **connection**, and
calls the same `host.*` JSON-RPC methods the apps use.

```
┌──────────────────────┐                  ┌───────────────────────────┐
│ machine A            │                  │ machine B                 │
│                      │   ws:// + token  │                           │
│  your node/java app  │───Tailscale/LAN─▶│  alpi daemon              │
│  (host-plane client) │   host.chat.send │    ├─ profile "abby"      │
│                      │◀──frames─────────│    └─ workgroup "casa-ops" │
└──────────────────────┘                  └───────────────────────────┘
```

### Which route

| | Host-plane connection (this doc) | ALP peer ([ALP.md](ALP.md)) |
|---|---|---|
| Use when | both machines share a trusted private net (Tailscale/LAN) | the network is untrusted, or you want a first-class peer identity |
| Transport | WebSocket + JSON-RPC | Noise_XK over TCP, signed envelopes |
| Auth | bearer device token, profile-scoped | Ed25519 keypair pinned in `peers.yaml` |
| Integration cost | a WebSocket + JSON — minutes | embed an ALP client (handshake + signing) |
| Can `@mention` / be a workgroup peer identity | no (acts as a local member) | yes |

For "a script on the private net wants to ask a profile", the device-token
route is the right one. The rest of this doc covers it.

Use `ws://` only with a Tailscale/private IP literal over a trusted network;
hostname routes require `wss://`. For Internet access, put a TLS front-end on
`wss://` — a self-hosted reverse proxy, or a managed TLS edge (a cloud load
balancer / CDN terminating TLS) — and keep the daemon's plaintext listener
private. Desktop and mobile validate the served certificate and reject invalid TLS.

## Step 1 — turn on the listener (machine B)

The daemon always serves a local Unix socket; the remote WebSocket
listener is what your code dials. Relevant `~/.alpi/config.yaml` keys:

```yaml
network:
  host: ""                 # advertised address; empty = auto-detect Tailscale, then LAN

host:
  tcp_port: 49200          # default
  allow_public_bind: false # keep false — public IPs are rejected unless this is true
  device_name: ""          # pairing label; defaults to the hostname
  endpoints:
    - url: wss://your.domain.com
      label: Secure Internet
    - url: ws://100.64.10.2:49200
      label: Direct
```

By default the listener binds to the machine's Tailscale address if one
is detected, otherwise the LAN address. A public IP is refused unless you
explicitly set `host.allow_public_bind: true` (don't, for an integration).

Configure routes in `alpi setup` → **Connections** → **Network**. Their order
is preserved and the first route is the default encoded in a pairing code.
For the supplied Docker/Caddy topology, follow
[`docker/README.md`](../docker/README.md#secure-internet-access-wss); for a
managed edge, point it at the daemon's private listener instead. Either way the
front-end must be reachable and its certificate valid before a client can dial
the advertised route.

## Step 2 — create a scoped connection

Run `alpi setup` → **Connections** → **New connection** on machine B:

1. Label it (e.g. `ci-bot`).
2. Choose **member** (not admin) — admin can manage profiles
   and devices; an integration never needs that.
3. Restrict it to the profile(s) it may reach (e.g. `abby`). Blank means
   all profiles — avoid that for an integration.

You get a QR code and an
`alpi://device?url=…&name=…&pairing_token=…` link. The pairing grant expires
after ten minutes and can be exchanged once. A normal Desktop/Mobile client
does that automatically. A headless integration sends
`host.connections.exchange_pairing` as its first unauthenticated WebSocket
message with `pairing_token`, `client`, `name` and `app_version`, then stores
the returned **device token before any probe or other fallible setup**, then
uses it as `params.auth_token`. Add another
device from the connection detail when another client should share the same
sessions and accounting; each exchange returns a separate token so either
device can be revoked without affecting the other.

A `member` token restricted to `abby` can only reach `abby`, is blocked
from every admin method, and gets profile-scoped filtering on responses
and events.

**Revoke** at any time from `alpi setup` → **Connections** → select the
connection → select the device. Admin integrations can use
`host.connections.revoke_device(connection_id, device_id)`. A `member`
credential cannot manage connections.

## Step 3 — the wire protocol

One WebSocket message is one JSON object. Every request carries
`auth_token` in `params`. There are two ids and they should match:
the top-level JSON-RPC `id` (the daemon echoes it on every frame, so you
can demux) and `params.request_id` (the turn identity used by cancel and
backfill). `request_id` must be a non-empty value.

`host.chat.send` is a **streaming** method — it answers with a sequence
of frames, not one reply. There is no non-streaming chat method.

Request:

```json
{ "id": 1, "method": "host.chat.send",
  "params": { "auth_token": "<TOKEN>", "profile": "abby",
              "text": "status of the deploy?", "request_id": 1,
              "session_id": "<optional, to continue a conversation>" } }
```

For file input, stage the file first with `host.attachments.stage` and
pass the returned metadata as `params.attachments` (a list).

Frames (each is `{ "id": 1, "event": "...", ... }`):

| `event` | Fields | Meaning |
|---|---|---|
| `session_start` | `session_id`, `model_used` | first frame; capture `session_id` to continue later |
| `reasoning_delta` | `text` | extended-reasoning fragment |
| `assistant_delta` | `text` | a chunk of the answer — concatenate |
| `tool_start` / `tool_state` / `tool_end` | `tool_id`, `name`, … | the agent ran a tool |
| `auto_compact` | `text`, `tokens_before`, `tokens_after` | context was compacted |
| `heartbeat` | — | keep-alive (every 5s); ignore |
| `reply` | `text`, `session_id`, `attachments?` | the final answer text |
| `done` | `session_id` | **terminal** — stream ends here |

Errors: a JSON-RPC error (`{ "id":1, "error": { "code", "message" } }`)
means the request was rejected (e.g. `-32000 auth-failed`,
`-32001 forbidden` for an out-of-scope profile). A frame with
`event: "error"` (carrying `text`) means the turn failed mid-stream; it
arrives before `done`.

To continue a conversation, pass the `session_id` you got back as
`params.session_id` on the next `host.chat.send`.

### Local delegated chat

A sovereign local operator can create a chat owned by an existing paired
connection without bypassing the daemon's streaming lifecycle:

```sh
alpi -p smith chat --once "audit engine-payments" --connection-id conn_javi
```

The CLI calls the local-only `host.chat.delegate`, which validates the active
connection and its profile scope, then executes through `host.chat.send`.
Consequently the paired clients see the session as `in_flight` and can replay
tool activity through `host.chat.events_since`. The method is rejected over
WebSocket even for remote admins; it is an operator facility, not an integration
API.

## Step 4 — talk to a profile (Node)

```js
import WebSocket from 'ws'; // npm i ws

let _id = 0;
const nextId = () => ++_id; // never 0 — an empty request_id is rejected

export function chat(endpoint, { profile, text, sessionId, onDelta }) {
  return new Promise((resolve, reject) => {
    const ws = new WebSocket(`ws://${endpoint.ip}:${endpoint.port}`);
    const id = nextId();
    let reply = '';
    let session = sessionId || null;

    ws.on('open', () => ws.send(JSON.stringify({
      id,
      method: 'host.chat.send',
      params: {
        auth_token: endpoint.token,
        profile,
        text,
        request_id: id,
        ...(sessionId ? { session_id: sessionId } : {}),
      },
    })));

    ws.on('message', (raw) => {
      let f;
      try { f = JSON.parse(raw.toString()); } catch { return; }
      if (f.id !== id) return;
      if (f.error) { ws.close(); return reject(new Error(`${f.error.code} ${f.error.message}`)); }
      switch (f.event) {
        case 'session_start': session = f.session_id; break;
        case 'assistant_delta': reply += f.text; onDelta?.(f.text); break;
        case 'reply': reply = f.text; session = f.session_id; break;
        case 'error': ws.close(); return reject(new Error(f.text || 'stream error'));
        case 'done': ws.close(); return resolve({ text: reply, sessionId: session });
      }
    });

    ws.on('error', reject);
  });
}

const endpoint = { ip: '100.64.50.234', port: 49200, token: process.env.ALPI_TOKEN };

const first = await chat(endpoint, { profile: 'abby', text: 'Did the nightly deploy pass?' });
console.log(first.text);

// continue the same conversation
const next = await chat(endpoint, {
  profile: 'abby', sessionId: first.sessionId, text: 'And the migration step?',
});
console.log(next.text);
```

### Surviving a dropped connection

If the WebSocket dies mid-turn the daemon keeps running the turn and
records every frame to a sidecar. Replay with `host.chat.events_since`
(non-streaming): pass `{ profile, session_id, after_seq }` and it returns
`{ events, next_seq, exists, in_flight }`. Track `next_seq` as your cursor
and poll while `in_flight` is true. For a fire-and-forget integration you
rarely need this; the apps use it for reconnect resilience.

## Step 5 — talk to a workgroup (Node)

A workgroup is a shared, encrypted transcript anchored at a hub. Your
token acts **as a local member profile**: the daemon holds that profile's
keys and does the crypto for you. A `member` token can list, read, post,
and read task state; creating or administering a workgroup is admin-only.

```js
// one-shot unary RPC (no request_id needed for non-chat methods)
function call(endpoint, method, params) {
  return new Promise((resolve, reject) => {
    const ws = new WebSocket(`ws://${endpoint.ip}:${endpoint.port}`);
    const id = nextId();
    ws.on('open', () => ws.send(JSON.stringify({
      id, method, params: { auth_token: endpoint.token, ...params },
    })));
    ws.on('message', (raw) => {
      let b; try { b = JSON.parse(raw.toString()); } catch { return; }
      if (b.id !== id) return;
      ws.close();
      if (b.error) return reject(new Error(`${b.error.code} ${b.error.message}`));
      resolve(b.result);
    });
    ws.on('error', reject);
  });
}

// what workgroups is this profile in?
const { workgroups } = await call(endpoint, 'host.workgroups.list', { profile: 'abby' });

// post a message
await call(endpoint, 'host.workgroup.post', {
  profile: 'abby', wg_id: 'casa-ops', text: 'CI: build 412 green ✅',
});

// read new posts incrementally
let after = 0;
const { posts, next_seq } = await call(endpoint, 'host.workgroup.transcript', {
  profile: 'abby', wg_id: 'casa-ops', after_seq: after,
});
after = next_seq;
for (const p of posts) console.log(`#${p.seq} ${p.from}: ${p.body}`);

// fold task state (active / closed / blocked)
const tasks = await call(endpoint, 'host.workgroup.tasks', { profile: 'abby', wg_id: 'casa-ops' });
```

Member-callable workgroup methods (all take `profile`, scope-checked):

| Method | Params | Returns |
|---|---|---|
| `host.workgroups.list` | `profile?`, `include_pipeline_status?` | `{ workgroups: [{ id, profile, name, members, is_hub, hub_id, pipeline_status?, queued_pipeline?, queue_position?, … }] }` |
| `host.workgroup.post` | `profile`, `wg_id`, `text` | `{ ok, seq }` |
| `host.workgroup.transcript` | `profile`, `wg_id`, `after_seq?`, `limit?`, `tail?` | `{ posts: [{ seq, at, from, body, cost }], next_seq, limit }` |
| `host.workgroup.tasks` | `profile`, `wg_id` | `{ active, closed, blocked, pipeline_run }` |

`host.workgroup.create` / `update` / `add_member` / `kick` / `remove` /
`action` are **admin-only** — out of reach for a member token.

## Security

- **Scope to one profile.** A `member` token restricted to a single
  profile cannot touch any other profile or any admin method.
- **Use an encrypted route.** Dial a private IP over Tailscale/trusted LAN, or
  use certificate-validated `wss://` through a reverse proxy for Internet
  access. Leave `host.allow_public_bind: false` and keep the daemon's plaintext
  listener private. The token is a bearer secret; treat it like a password and
  keep it out of source control.
- **Revoke on rotation.** Each integration gets its own token so you can
  revoke one without disturbing the others.
- **Inbound text drives an agent with tools.** Every message you send is
  run by the target profile with its full tool set — treat the profile as
  reachable by whatever can reach your integration, and scope its tools
  accordingly (`tools.deny`, sandbox; see [CONFIG.md](CONFIG.md) and
  [SECURITY.md](SECURITY.md)). Don't point an integration at a profile
  with destructive tools unless the caller is as trusted as you are.

## Stability

`host.*` is the same surface the bundled apps use, and alpi takes clean
breaks over compatibility shims (see [ARCHITECTURE.md](ARCHITECTURE.md)).
Pin your client to a known daemon version and re-check this contract when
you upgrade — method names, params and frame shapes can change between
releases.

## See also

- [ALP.md](ALP.md) — the peer route (Ed25519, Noise, workgroups as a peer).
- [SECURITY.md](SECURITY.md) — threat model and the approval gate.
- [CONFIG.md](CONFIG.md) — every config key, including listener and tools.
- [DEPLOYMENTS.md](DEPLOYMENTS.md) — laptop / home-server / multi-device shapes.
