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
- Container binds `0.0.0.0`; set `ALPI_NETWORK_HOST` to the address clients dial (LAN/Tailscale IP for direct WS, or a hostname with an explicit certificate-validated `wss://` entry in `host.endpoints`). It can't see the host's interfaces, so this knob carries the advertised address.
- Ports: `49200` = host plane for paired desktop/mobile (`host.*`, TCP/WS); `7423` = ALP peer traffic (`link.*`, `workgroup.*`, Noise_XK), only for cross-machine peers.

### Docker WSS recipe

- Set `.env`: `HOST_IP=<private IP>` and `ALPI_DOMAIN=your.domain.com`; optional `ALPI_HOST_TCP_PORT=<custom port>` drives both Alpi and Caddy's private upstream.
- Point public DNS at the Docker host. Permit TCP 80/443; deny public access to 49200 (or the custom host port) and 7423.
- Requires Docker Compose >= 2.24.4 because `docker-compose.wss.yml` uses `!reset` to remove the base daemon port mappings.
- Render first: `docker compose -f docker-compose.yml -f docker-compose.wss.yml config`. Alpi must have no published ports; only Caddy publishes 80/443.
- Start: `docker compose -f docker-compose.yml -f docker-compose.wss.yml up -d`.
- Configure `wss://your.domain.com` at `alpi setup -> Connections -> Network -> Public route`; then create a member connection scoped to the profiles that client needs and generate one pairing credential per device.
- Existing clients retain their original URL. After enabling WSS, re-pair every client that stored direct `ws://` through Add device on its existing connection, verify WSS, then revoke the old device row; role/scope stay on the connection.
- Test from an external network, validate the certificate hostname, and confirm the daemon port is closed externally.
- Updates must retain both `-f` arguments for `pull` and `up -d`; using the base file alone republishes its direct ports.
- Several Alpis on one public host share one Caddy: one hostname and private upstream port per Alpi, all public WSS URLs on 443. Do not start one Caddy per instance because they would compete for 80/443.
- `!reset` affects only the named `alpi` service. Every added `alpi-2`-style service must reset/remove its own ports and get its own Caddy route.

Caddy obtaining a certificate and Alpi advertising a route are separate. The
proxy never creates a connection or credential, and `host.endpoints` never
opens a listener.

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
