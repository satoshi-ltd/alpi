# Alpi on Docker

A single image (`satoshiltd/alpi`) that runs the Alpi daemon for a normal
Linux host. The container entrypoint supervises the daemon as PID 1 — there is
no install/start/stop inside the container, and no web terminal: reach an
agent's TUI with `docker exec`.

## Quick start (compose)

From the repo root, create a `.env` with the address clients use to reach this
machine, then bring it up:

```sh
echo "HOST_IP=192.168.1.50" > .env     # a LAN IP, or a Tailscale IP for remote
docker compose up -d
docker compose exec alpi alpi          # open the TUI for the agent
```

`HOST_IP` is the address a desktop/mobile client dials. On a trusted LAN use the
host's LAN IP; for off-network access use a Tailscale IP/MagicDNS name.
**Tailscale is optional** — just one way to reach the host from outside the LAN.

Pair a client to `HOST_IP:49200`.

## Quick start (docker run)

```sh
docker run -d --name alpi \
  -e ALPI_NETWORK_HOST=192.168.1.50 \
  -p 192.168.1.50:49200:49200 \
  -p 192.168.1.50:7423:7423 \
  -v "$PWD/data/alpi:/data" \
  satoshiltd/alpi:latest
docker exec -it alpi alpi
```

## Ports

| Port    | Purpose                                            |
|---------|----------------------------------------------------|
| `49200` | Host control plane — desktop/mobile pairing.       |
| `7423`  | ALP peer network — cross-machine workgroups (opt). |

Map only what you need. Pairing needs `49200`; `7423` only if this agent talks
to peers on other machines.

## Environment

| Var                  | Default | Meaning                                              |
|----------------------|---------|------------------------------------------------------|
| `ALPI_NETWORK_HOST`  | —       | The one address clients/peers dial (LAN IP / Tailscale IP / hostname). **Shared by both planes** — control-plane pairing and ALP advertise the same host. Required for pairing: the container can't see the host's interfaces. |
| `ALPI_HOST_TCP_PORT` | `49200` | Control-plane port (desktop/mobile pairing). Map 1:1. |
| `ALPI_ALP_TCP_PORT`  | `7423`  | ALP peer-network port. ALP TCP is always-on in the container; this only changes the port. |

There is one host knob: `ALPI_NETWORK_HOST`. The container always binds
`0.0.0.0` (Docker maps the published ports); `ALPI_NETWORK_HOST` is just what
clients and peers are told to dial. Ports are per-plane.

State (profiles, keys, config, sessions) lives under `/data` — mount a volume
so it survives restarts.

## Updating

Pull the latest image and recreate only the containers whose image changed:

```sh
docker compose pull && docker compose up -d
```

Agent state (profiles, keys, sessions) is in the `/data` volume and is
untouched by the update. Run this on each host whenever a new release is out.

Avoid auto-update tools that require mounting `/var/run/docker.sock` (e.g.
Watchtower) — socket access is equivalent to root on the host.

## Several agents on one host

Each agent is identified by its keypair (its `/data` volume), not its IP — so
many agents share one host behind one address on **distinct ports**. Give each
its own ports (`ALPI_HOST_TCP_PORT` / `ALPI_ALP_TCP_PORT`, mapped 1:1) and its
own volume. See the commented `alpi-2` service in the root `docker-compose.yml`.

Clients then pair to `HOST_IP:49200`, `HOST_IP:49201`, … one per agent.
