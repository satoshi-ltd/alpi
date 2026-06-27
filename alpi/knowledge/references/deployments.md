# Deployments answer pack

## Answer directly

Deployment shape follows trust boundary + availability needs. Profiles separate identities; the daemon runs where scheduled work or the host plane must keep running while the TUI is closed.

## Shapes

| Shape | Use when | Notes |
|---|---|---|
| Laptop only | Interactive personal use. | Run `alpi`; daemon optional. |
| Laptop + daemon | Schedules/host plane on same machine. | `alpi daemon start`. |
| Home server | Always-on scheduler/host plane. | Pair desktop/mobile over host-plane WebSocket. |
| One machine, many profiles | Work/personal/client separation. | One daemon supervises all profiles. |
| Multi-device personal | Laptop + trusted server/peer. | ALP for alpi-to-alpi links. |
| Small team/family | Multiple identities, explicit trust. | Separate profiles + ALP peers. |
| Docker home server | Packaged always-on daemon on a Linux host. | See Docker shape below. |

## Commands

```bash
alpi daemon start
alpi daemon status
alpi daemon restart
```

## Docker shape

- Image `satoshiltd/alpi`; daemon is PID 1. UI via `docker exec -it <name> alpi` (no web terminal).
- Volume mounts at `/data`; `HOME=/data` makes `/data/.alpi` the profile root, surviving restarts.
- Container binds `0.0.0.0`; set `ALPI_NETWORK_HOST` to the address clients dial (LAN IP, or Tailscale IP/MagicDNS for off-network). It can't see the host's interfaces, so this knob carries the advertised address.
- Ports: `49200` = host plane for paired desktop/mobile (`host.*`, TCP/WS); `7423` = ALP peer traffic (`link.*`, `workgroup.*`, Noise_XK), only for cross-machine peers.

## Decision rules

- **Desktop/mobile clients** talk to the daemon through `host.*`. Desktop supports a local socket plus paired remote host-plane endpoints; mobile starts from one paired endpoint. They never read profile files directly and never spawn `alpi`.
- **Schedules and the host plane** need a running daemon. If one doesn't respond, check: profile, daemon status, config, logs. Email is an on-demand tool (no listener); failures show as `email` tool errors, not daemon downtime.
- **ALP** is for trusted alpi-to-alpi communication across machines — not the local desktop host API.

## What not to promise

- No hosted control plane required.
- No automatic enterprise fleet manager shipped.
- No global trust across profiles; trust is profile/identity scoped.

## Related topics

- profiles — identity + isolation
- alp — wire protocol, capabilities, peers
- operations — daemon unit (launchd/systemd), KeepAlive/Restart, log paths
