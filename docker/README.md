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

## Node runtime and private Git recipes

The image ships Node.js 24 LTS, npm, and npx. Node is a first-class runtime: it
runs npm-based project gates as well as MCP servers launched through `npx`, and a
container never depends on its Docker host's Node install. Native daemon
installations must expose Node.js 24 LTS (`node`, `npm`, `npx`) on the service
PATH. The npm/npx cache lives in `/data/.npm` and persists in the volume, so a
package is downloaded once per volume rather than once per container start.

A plain container needs nothing more. **Only if a recipe clones a project repo**
— its setup phase runs `git clone` + `npm ci` inside the container — does the
deployment also need:

- outbound DNS and HTTPS to GitHub and `registry.npmjs.org`;
- a writable `/data` volume owned by the runtime user (UID/GID 1000);
- room for one clone and `node_modules` per project, plus the shared npm cache.

**If that recipe uses an SSH URL** (`git@github.com:…`), provision a dedicated
deploy key and `known_hosts` in `/data/.ssh`, owned by UID 1000, at runtime —
never bake SSH keys or tokens into the image or repository. The image includes
`openssh-client`, and Git inherits `HOME=/data` so it resolves these credentials
normally:

```sh
mkdir -p data/alpi/.ssh
sudo chown -R 1000:1000 data/alpi
chmod 700 data/alpi/.ssh
chmod 600 data/alpi/.ssh/id_ed25519
```

Verify the runtime inside the container after rebuilding:

```sh
docker compose exec alpi sh -lc \
  'node --version && npm --version && npx --version && git --version && ssh -V'
```

## Fleets (several machines)

An agent's identity is the keypair inside its `/data` volume. **Never copy a
`/data` volume to another machine** — both daemons would hold the same
identity, peers route to whichever answered last, and the agents appear to
interfere with each other. Provision each machine with an empty volume and
pair it fresh.

`alpi doctor` (run it on every machine: `docker compose exec alpi alpi doctor`)
verifies the fleet-integrity signatures: a peer entry carrying this agent's
own pubkey, one pubkey shared by several peer entries, two peers dialing the
same address, and a container with no advertised `ALPI_NETWORK_HOST`.

Settings changes apply in place: gateways, subsystem toggles and the ALP port
hot-reload within seconds — connections, peers and workgroups stay up. Only a
change to `ALPI_NETWORK_HOST` or the pairing host port still needs a restart
(in compose: edit the env/ports and `docker compose up -d` to recreate).

## Kubernetes

The same image runs in a cluster as a plain **stateful, single-writer**
workload. There is no Helm chart or manifest set yet — these are the
constraints that matter when you write your own:

- **`replicas: 1`, always.** A daemon owns its home exclusively
  (`service.lock`); there is no leader election, no shared-home HA.
  Run more agents by running more single-replica workloads, one
  volume each — that's a fleet, not a replica set.
- **StatefulSet + PVC** (`ReadWriteOnce`) mounted at `/data`, with
  `runAsUser: 1000` / `fsGroup: 1000` — the image's runtime user owns
  the volume, exactly like the plain-Docker layout.
- **Env**: `ALPI_ALP_TCP_PORT` and `ALPI_HOST_TCP_PORT` pick the two
  listener ports; `ALPI_NETWORK_HOST` must be the address peers and
  paired apps will actually dial — a LoadBalancer/Service address or,
  better, a Tailscale/WireGuard overlay IP from a sidecar-less node
  network. Keep both ports off the public internet.
- **Service** exposing the two TCP ports; a plain TCP `readinessProbe`
  on the host-plane port is enough (the WebSocket listener accepts as
  soon as the daemon is up).
- **Secrets**: `.env` files under `/data/.alpi/` (root and per profile)
  — project them from Kubernetes Secrets via an initContainer or
  `kubectl exec` once per credential change; never bake keys into the
  image.
- **Egress**: HTTPS to your model provider; GitHub + the npm registry
  only when recipes clone projects (see the section above).

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
