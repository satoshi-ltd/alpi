# Deployments answer pack

Use this for "where should I run alpi?", laptops, home servers, many
profiles, teams, and service topology.

## Main rule

Deployment shape follows trust boundary and availability needs. Use
profiles to separate identities; use the daemon where inbound gateway
or scheduled work must run while the TUI is closed.

## Common shapes

| Shape | Use when | Notes |
|---|---|---|
| Laptop only | Interactive personal use. | Run `alpi`; daemon optional. |
| Laptop + daemon | Telegram/email/schedules on same machine. | `alpi daemon start`. |
| Home server | Always-on gateway/scheduler/host plane. | Pair desktop/mobile over host-plane WebSocket. |
| One machine, many profiles | Work/personal/client separation. | One daemon supervises all profiles. |
| Multi-device personal | Laptop plus trusted server/peer. | Use ALP for alpi-to-alpi links. |
| Small team/family | Multiple identities with explicit trust. | Separate profiles and ALP peers. |

## Commands

```bash
alpi daemon start
alpi daemon status
alpi daemon restart
```

## Desktop/mobile rule

Desktop/mobile clients should talk to the daemon through `host.*`.
Desktop supports local socket plus paired remote host-plane endpoints;
mobile starts from one paired endpoint. They should not read profile
files directly and should not spawn `alpi`.

## Gateway rule

Gateways need a running daemon. If a gateway does not respond, check:

- profile,
- daemon status,
- gateway config,
- logs,
- provider/platform credentials.

## ALP rule

Use ALP for trusted alpi-to-alpi communication across machines. ALP is
not the local desktop host API.

## What not to promise

- No hosted control plane is required.
- No automatic enterprise fleet manager is shipped.
- No global trust across profiles; trust is profile/identity scoped.
