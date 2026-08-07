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

Pair a client to `HOST_IP:49200`. Set `ALPI_HOST_TCP_PORT` in `.env` before
starting when this instance needs a different port; Compose keeps the
environment value and the 1:1 mapping aligned.

## Secure Internet access (WSS)

Do not publish the daemon's plaintext WebSocket port on the Internet. The
repository includes a Compose overlay that puts Caddy in front of Alpi:

```text
Desktop / Mobile
  -> wss://your.domain.com:443
  -> Caddy (certificate + WebSocket proxy)
  -> alpi:<ALPI_HOST_TCP_PORT> on the private Compose network
```

Only ports `80` and `443` are published by this topology. The overlay removes
the base mappings for both `49200` (host plane) and `7423` (ALP).

### 1. Prepare DNS and the firewall

Create an `A` record (and `AAAA` only when IPv6 really reaches this host) for
the domain you control:

```text
your.domain.com -> public IP of the Docker host
```

Allow inbound TCP `80` and `443`. Deny public access to the effective Alpi host
port and to `7423`. Port 80 is used for certificate issuance/renewal and HTTPS
redirects; clients use WSS on 443.

### 2. Configure the deployment

The WSS overlay requires Docker Compose **2.24.4 or newer** because older
versions may silently ignore `!reset` and leave the daemon ports published.

```sh
docker compose version
```

Create `.env` beside the compose files:

```dotenv
HOST_IP=192.168.1.50
ALPI_DOMAIN=your.domain.com
```

`HOST_IP` is still Alpi's private advertised address. It can be a LAN or
Tailscale IP. It does not become public when the WSS overlay is active. To use a
non-default host-plane port, add it once:

```dotenv
ALPI_HOST_TCP_PORT=30494
```

The same value now configures the daemon and Caddy's private upstream. It is
not added to the public URL: `wss://your.domain.com` already means port 443.

### 3. Verify the effective Compose model

Render the merged configuration before starting it:

```sh
docker compose \
  -f docker-compose.yml \
  -f docker-compose.wss.yml \
  config
```

The `alpi` service must have no `ports:` entries. Only `caddy` should publish
`80:80` and `443:443`; `expose:` on Alpi is private to the Compose network.

Start both services:

```sh
docker compose \
  -f docker-compose.yml \
  -f docker-compose.wss.yml \
  up -d
```

Follow Caddy until certificate issuance succeeds:

```sh
docker compose \
  -f docker-compose.yml \
  -f docker-compose.wss.yml \
  logs -f caddy
```

### 4. Tell Alpi to advertise the public route

Caddy makes WSS reachable, but it does not change pairing metadata. Open the
local setup UI inside the container:

```sh
docker compose \
  -f docker-compose.yml \
  -f docker-compose.wss.yml \
  exec alpi alpi setup
```

Go to **Connections -> Network -> Public route**, add
`wss://your.domain.com`, and save. The route is advertisement metadata; it
does not contain a token and changing it does not restart the daemon.

Alpi may also display a Private route derived from `HOST_IP`. The WSS overlay
does not publish that port on the Docker host, so select the Public WSS route
when generating a pairing code. Restoring direct LAN/Tailscale access requires
an explicit private-interface mapping; do not add a catch-all host mapping as a
fallback.

#### Existing paired devices need a new WSS pairing

A paired device stores the URL selected when it was paired. Adding a Public
route does not rewrite that local client state. When the overlay removes the
direct host mapping, devices still pointing at `ws://HOST_IP:PORT` go offline
even though their server-side records remain active and show their previous
`last_seen`.

Plan a short cutover window. After Caddy is healthy and the Public route is
configured, migrate each existing client from the local setup UI:

1. open its existing connection under **Connections**;
2. choose **Add device** and generate a code using the Public WSS route;
3. pair the same Desktop/Mobile client with that new code;
4. verify WSS chat/events, then revoke the old direct-WS device row.

This keeps the connection's role and profile scope while issuing a new,
independently revocable device credential. Repeat once per physical client.
The runbook's new-device test does not prove that these older stored URLs were
migrated.

Then create a connection under **Connections -> New connection**. Prefer a
`member` connection scoped to only the profiles that client needs. Generate a
separate pairing code for each Desktop or Mobile device; each device gets its
own revocable credential.

### 5. Test from outside

Use a device that is not relying on the host's LAN route (for example, Mobile
on cellular data). Pair it with the generated `alpi://` link or QR and confirm
that the stored endpoint is `wss://your.domain.com`.

Check the certificate independently:

```sh
openssl s_client \
  -connect your.domain.com:443 \
  -servername your.domain.com </dev/null
```

The final verification line must be `Verify return code: 0 (ok)`. From an
external machine, also verify that the daemon port is closed:

```sh
nc -vz YOUR_PUBLIC_IP 49200
```

Use the configured custom port instead of 49200 when applicable. That command
must fail. A successful WSS connection does not compensate for an exposed
plaintext listener.

### Optional private ALP access

The WSS overlay also removes the host mapping for `7423`. If cross-machine
peers need ALP, publish its effective port separately and bind it only to a LAN
or Tailscale address. ALP is not part of the Desktop/Mobile WSS route and should
not be opened to the public Internet.

### Several Alpis behind one Caddy

Public WSS does not need a different external port per instance. Give every
Alpi its own hostname and internal host-plane port; all public URLs still use
443 and Caddy selects the upstream by hostname:

```caddyfile
casa.your.domain.com {
    reverse_proxy alpi:49200
}

mirai.your.domain.com {
    reverse_proxy alpi-2:49201
}

satoshi.your.domain.com {
    reverse_proxy alpi-3:49202
}
```

All three DNS records point to the same public host. The Alpi services share
Caddy's private Docker network, keep distinct volumes and effective
`ALPI_HOST_TCP_PORT` values, and publish no daemon ports. Configure the matching
Public route separately inside each instance. The supplied overlay models one
Alpi; extend the compose and Caddyfile explicitly for a multi-instance host
rather than starting three Caddy containers that compete for 80/443.

Compose `!reset` applies only to the service where it appears. The overlay's
reset under `alpi` does not affect an uncommented `alpi-2` (or any other added
service); remove/reset every additional service's `ports:` explicitly before
calling the host Internet-safe.

### Stop WSS or return to private WS

Stop the merged deployment with the same two files:

```sh
docker compose \
  -f docker-compose.yml \
  -f docker-compose.wss.yml \
  down
```

Remove the Public route from Alpi before retiring the domain. To return to a
direct private-network deployment, start only the base file afterward:

```sh
docker compose up -d
```

That intentionally restores the direct host/ALP mappings bound to `HOST_IP`,
so first confirm that `HOST_IP` is a private LAN or Tailscale address and that
the firewall still rejects those ports from the Internet. Caddy's named
volumes preserve certificate state unless explicitly deleted.

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
| `ALPI_DOMAIN`        | —       | Public certificate hostname used by the optional WSS/Caddy overlay. |

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

Settings changes apply in place where supported; connections, peers and
workgroups remain durable. A change to `ALPI_NETWORK_HOST`, the host-plane port
or the ALP port requires recreating the container with the matching environment
and mappings.

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

For the normal private-network deployment, pull the latest image and recreate
the containers whose image changed:

```sh
docker compose pull && docker compose up -d
```

For a WSS deployment, every lifecycle command must retain both compose files:

```sh
docker compose -f docker-compose.yml -f docker-compose.wss.yml pull
docker compose -f docker-compose.yml -f docker-compose.wss.yml up -d
```

Running plain `docker compose up -d` after a WSS deployment applies only the
base file and republishes its direct daemon ports. Render `config` again after
any Compose or deployment-file upgrade.

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
