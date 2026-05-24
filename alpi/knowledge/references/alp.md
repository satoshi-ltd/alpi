# ALP answer pack

Use this for Alpi Link Protocol, peer identity, link methods,
workgroups, budgets, and ALP vs local host API.

## Answer directly

- Desktop/mobile should not use ALP; they use `host.*`.
- ALP is for trusted alpi-to-alpi peers and workgroups.
- Trust is explicit and profile-scoped, not machine-scoped.
- For workgroups, answer in terms of hub, members, transcript, budget, and group key.

## Short answer

ALP is the peer-to-peer plane for trusted alpi instances. It is used
for cross-machine agent links and workgroups. It is separate from the
local desktop/mobile host API.

## ALP vs host API

| Plane | Purpose |
|---|---|
| `host.*` | Device client-to-daemon API over local Unix socket or paired WebSocket. Desktop/mobile should use this. |
| `link.*`, `workgroup.*` | ALP peer-to-peer methods for trusted alpi instances. |

## Identity

Each profile owns its own ALP identity. Trust is profile-scoped, not
machine-scoped. If work and personal should not trust the same peers,
use separate profiles.

## Peer list

Peers are explicit. A peer record binds identity and reachability
metadata. Do not treat arbitrary network callers as trusted just
because they can reach a socket/port.

## Transports

- Same machine: Unix-domain socket.
- Cross machine: authenticated encrypted transport.

The exact transport details are implementation internals unless the
user is debugging ALP itself.

## Core methods

| Method | Purpose |
|---|---|
| `link.ping` | Check peer reachability/identity. |
| `link.ask` | Ask a peer to handle a task/question. |
| `link.cancel` | Cancel an in-flight peer task. |
| `workgroup.*` | Manage group coordination and shared context. |

## Workgroups

Workgroups coordinate multiple alpi profiles/peers around a shared
task space. They involve:

- member identities,
- shared briefing/context,
- group key/versioning,
- hub state,
- liveness,
- budget controls,
- human participation rules.

Answer workgroup questions concretely: identity, membership, briefing,
budget, liveness, or cancellation.

## Budget

ALP/workgroup tasks must respect profile budget settings. If a peer or
hub runs out of budget, the correct behavior is to stop or synthesize a
bounded result rather than silently retrying expensive work.

## Security posture

- Trust is explicit and identity-based.
- Network reachability is not authorization.
- Profiles isolate ALP identities.
- Prompt/tool safety still matters inside ALP tasks.

## Common questions

- "Should desktop/mobile use ALP?" -> no, use `host.*`; ALP is for
  alpi-to-alpi peers.
- "Can two profiles on one machine be separate peers?" -> yes, each
  profile has its own identity.
- "How do I debug a peer?" -> check identity, peer list, transport
  reachability, logs, and budget.

## Related topics

- Host-plane clients and pairing: `deployments`
- Profile identity boundaries: `profiles`
- Security model: `security`
