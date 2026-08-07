# Deployments

Topologies alpi is designed to support. Each section is a reference
shape — pick the closest one to what you want, read the trade-offs,
adapt. For the primitives each shape leans on see
[PROFILES.md](PROFILES.md) (identity + isolation) and
[ALP.md](ALP.md) (the wire protocol).

The shapes below are technical deployment patterns, not pricing tiers.
Personal use, evaluation, and non-production deployments are free.
Commercial production deployments are covered by the terms in
[LICENSE](../LICENSE); contact `info@satoshi-ltd.com` when you are
planning that rollout.

## 1. Laptop only

The baseline. One profile, one machine, TUI or desktop app for chat.

```
┌─────────────────────────────────────┐
│ laptop                              │
│                                     │
│   alpi (TUI / desktop)              │
│     │                               │
│     ├─ ~/.alpi/  (default profile)  │
│     └─ alpi daemon                  │
│          ├─ scheduler (cron)        │
│          ├─ ALP listener            │
│          ├─ workgroups poller       │
│          └─ host plane (default)    │
└─────────────────────────────────────┘
```

- **Profiles:** 1 (`default`).
- **ALP:** the listener is one of the daemon's services — leave it
  on (default) even when nothing else dials in; it's idle and
  costs nothing.
- **Ops:** the daemon is installed automatically on the first
  `alpi setup` (launchd plist on macOS, systemd-user unit on
  Linux). 24/7 cron + ALP from minute one.
- **Best for:** individual, personal use. Zero-config after the
  quickstart.

## 2. Laptop + home server

Heavy work (schedules, long research, cron jobs) runs on a home
server; interactive chat stays on the laptop. Linked via ALP over
Tailscale (or over Unix sockets if you're on the same machine,
but that'd just be two profiles — see topology 3).

```
┌──────────────────┐                ┌──────────────────────┐
│ laptop           │                │ home server          │
│                  │   ALP.2 over   │                      │
│  alpi (TUI)      │───Tailscale───▶│  alpi daemon         │
│  ~/.alpi/        │                │  ~/.alpi/            │
│  peers: home     │                │  peers: laptop       │
│                  │◀───────────────│  (reaches back only  │
│                  │   link.ask     │   for link.ask)      │
└──────────────────┘                └──────────────────────┘
```

- **Profiles:** 1 on each machine (both `default` is fine — the
  cryptographic identity is the Ed25519 pubkey, not the name).
- **ALP:** ALP.2 with Noise_XK over TCP, fronted by
  Tailscale / WireGuard.
- **Peers:** cross-pinned. Capabilities narrow — laptop grants
  `home-server` only `link.ping` + `link.ask`; home-server grants
  laptop only `link.ask`. See [ALP.md §Capability model](ALP.md).
- **Ops:** home server runs `alpi setup` once (auto-installs the
  daemon, which hosts the scheduler + ALP listener). Laptop
  just runs `alpi` when the user sits down.
- **Best for:** power-user individual with a house NAS /
  mini-server. Also: "I want scheduled jobs to run even when my
  laptop is closed."

## 2a. Docker home server

The packaged form of the home-server topology. The daemon runs inside a
container as PID 1, stores the Alpi root on a mounted volume, and exposes
the host plane (and optionally the ALP peer port) so desktop / mobile
clients pair to it. No web terminal — reach the TUI with `docker exec`.

```
┌──────────────────────────────────────┐
│ Linux host (Docker)                  │
│                                      │
│  container: satoshiltd/alpi          │
│    alpi daemon (PID 1)               │
│      ├─ scheduler                    │
│      ├─ ALP listener (:7423)         │
│      ├─ workgroups poller            │
│      └─ host plane (:49200)          │
│                                      │
│  /data  (mounted volume → .alpi)     │
└──────────────────────────────────────┘
        │ :49200 pairing · :7423 ALP
        ▼  bound to the host address clients dial
```

- **Image / package:** `satoshiltd/alpi`, built from `docker/`.
  Compose and full instructions in [docker/README.md](../docker/README.md)
  — including a Kubernetes section for running the same image as a
  single-writer stateful workload.
- **Profiles:** starts with `default`, same multi-profile layout as any
  Linux install. Several agents on one host = distinct ports per
  container (see [§3](#3-one-machine-many-profiles) for the profile
  model, `docker/README.md` for the port mapping).
- **UI:** `docker exec -it <name> alpi` opens the TUI; no web dashboard.
- **Storage:** the volume mounts at `/data`, and `HOME=/data` makes
  `/data/.alpi` the profile root — state survives restarts.
- **Reachability:** the container can't see the host's network
  interfaces, so set `ALPI_NETWORK_HOST` to the address clients
  dial — a LAN/Tailscale IP for direct WS, or a hostname paired with an
  explicit certificate-validated `wss://` entry in `host.endpoints`
  (**Tailscale is optional**). The control plane binds `0.0.0.0`
  inside the container; you map a host port to it.
- **Remote access split:** `49200` is the host plane used by paired
  desktop / mobile clients (`host.*`, TCP/WS). `7423` is separate — it
  enables ALP peer traffic between alpis (`link.*`, `workgroup.*`,
  Noise_XK) and is only needed for cross-machine peers.
- **Backup:** `alpi backup` archives the entire alpi home (every profile
  + global config) into a single passphrase-encrypted file; `alpi
  restore` reverses it. You can also back up the mounted volume.

### Public client access through WSS

Internet-facing Desktop/Mobile access uses a TLS reverse proxy. The daemon
continues speaking plaintext WebSocket only inside the private host or Compose
network:

```text
client -> wss://your.domain.com:443 -> Caddy -> alpi:49200
```

Use the supplied `docker-compose.wss.yml` overlay and `docker/Caddyfile`. The
overlay publishes Caddy on `80/443`, removes the base mappings for `49200` and
`7423`, and forwards to the effective `ALPI_HOST_TCP_PORT` over the private
Compose network. It requires Docker Compose 2.24.4 or newer for `!reset`.

The operator must still complete four independent steps:

1. point `ALPI_DOMAIN` in public DNS at the Docker host;
2. allow public TCP 80/443 and deny the daemon ports;
3. configure `wss://your.domain.com` as the **Public route** under
   `alpi setup -> Connections -> Network`;
4. create a scoped connection and test its pairing from an external network.

Existing clients keep the URL selected at their original pairing. A device
stored as `ws://HOST_IP:PORT` does not automatically adopt the new Public
route and goes offline when the overlay removes that mapping. Re-pair each
existing physical client through **Add device** on its current connection,
select WSS, verify it, then revoke the old direct-WS device credential. The
connection's role and profile scope remain unchanged.

`!reset` is scoped to the named Compose service. The supplied overlay protects
`alpi` only; every additional service such as the commented `alpi-2` template
must remove/reset its own `ports:` and receive its own Caddy upstream.

The proxy and the advertised route are deliberately separate: starting Caddy
does not mint credentials or rewrite Alpi config, and adding `host.endpoints`
does not open a port or obtain a certificate. See the complete commands,
certificate checks, update procedure and custom-port behavior in
[docker/README.md](../docker/README.md#secure-internet-access-wss).

## 3. One machine, many profiles

Same machine, multiple profiles with different roles, linked
intra-profile via ALP.1 (Unix sockets). This is the private-network
starter kit on a single host.

```
┌────────────────────────────────────────────────────┐
│ single machine                                     │
│                                                    │
│  ~/.alpi/profiles/assistant/  ← daily driver       │
│  ~/.alpi/profiles/researcher/ ← deep-research role │
│  ~/.alpi/profiles/cron/       ← scheduled jobs     │
│                                                    │
│  intra-machine ALP = Unix-domain sockets           │
│      (~/.alpi/profiles/<name>/alp/alp.sock)        │
│                                                    │
│  assistant  ──@researcher──▶  researcher           │
│  assistant  ──@cron──────▶    cron                 │
│  researcher ──@cron──────▶    cron                 │
└────────────────────────────────────────────────────┘
```

- **Profiles:** N, each with its own identity, model, memory,
  skills, and capability surface. **One daemon** supervises every
  profile — N profiles do not mean N processes or N plists.
- **ALP:** ALP.1 (Unix sockets). Each profile's `alp/alp.sock` is
  `0600`; the OS file-system permissions are the first line of
  defence, Ed25519 signatures the second.
- **Capabilities are how you specialise.** `cron` might only grant
  `link.ask` to `assistant` and nothing to `researcher`.
  `researcher` grants `link.ask` to both.
- **Capabilities are always supervised.** Scheduler, ALP and workgroup tasks
  are fixed daemon capabilities. Actual activity is controlled by jobs, peer
  grants and workgroup membership rather than subsystem on/off switches. Add or
  remove a profile and restart the daemon to refresh the supervised profile
  set.
- **Best for:** family on one home server, individual with
  specialised-role agents, prototyping an enterprise rollout on
  one box before distributing.

## 4. Multi-device personal

Your alpis follow you across devices (laptop + desktop + phone)
over Tailscale. Each device runs its own profile with its own
identity; all mutual peers.

```
┌──────────────┐       ┌──────────────────┐       ┌──────────────┐
│ laptop       │       │ phone (Termux /  │       │ home desktop │
│ alpi         │◀──────│  iSH)            │──────▶│ alpi         │
│              │       │  alpi (minimal)  │       │              │
└──────┬───────┘       └────────┬─────────┘       └──────┬───────┘
       │                        │                        │
       └────────── ALP.2 over Tailscale ──────────────────┘
                 (every device pinned to every other)
```

- **Profiles:** 1 per device. Common pattern: each gets a name
  matching the hostname (`laptop`, `phone`, `desktop`).
- **ALP:** ALP.2 mesh. Every device has every other device in
  its `peers.yaml`.
- **Identity hygiene:** if a device is lost, the remaining alpis
  drop its pubkey from their `peers.yaml`. Network-level access
  (Tailscale) alone isn't enough — losing a long-term key
  invalidates the peer's ability to reach you.
- **Ops trade-off:** more keys to manage. Worth it for the
  sovereignty gain — no cloud broker, no shared account.

## 5. Family / small team

Multiple humans, each with their own alpi, optionally sharing a
workgroup. Hub-anchored.

```
┌──────────────┐       ┌──────────────┐       ┌──────────────┐
│ Jane's alpi  │       │ Raj's alpi   │       │ Mia's alpi   │
│ (laptop)     │       │ (laptop)     │       │ (laptop)     │
└──────┬───────┘       └──────┬───────┘       └──────┬───────┘
       │                      │                      │
       └──────────────────────┴──────────────────────┘
                              │
                   ┌──────────▼───────────┐
                   │ home-server alpi     │
                   │ (the workgroup hub)  │
                   │                      │
                   │ workgroup: household │
                   │   members: Jane,     │
                   │            Raj, Mia  │
                   └──────────────────────┘
```

- **Profiles:** 1 per human, 1 on the home server acting as workgroup
  hub.
- **ALP:** ALP.3 workgroups. The home server creates the workgroup,
  holds the group key + transcript; members post via
  `workgroup.post(workgroup_id, text)`.
- **Human interaction:** Jane can subscribe to the workgroup via her
  TUI or stay out entirely. Agents inside the workgroup act
  autonomously within their per-member budget.
- **Privacy:** transcript encrypted with the group key; the home
  server can see ciphertext + metadata (who posted when), not
  beyond its role as hub. Agents from outside the workgroup can't read
  anything.
- **Best for:** household coordination ("what's the plan for the
  week?"), small team stand-ups, a book club with bots helping
  the humans.

## 6. Enterprise — private agent network

Per-employee profiles, mesh linked via ALP.2 over Tailscale or a
VPN. Shared services (research-bot, tools-bot) as pinned peers
with narrow capabilities. Audit trail centralised.

```
┌──────────────────────────────────────────────────────────────┐
│ corporate Tailscale network                                  │
│                                                              │
│  ┌──────┐  ┌──────┐  ┌──────┐  ┌──────┐  ┌──────┐            │
│  │Jane  │  │Raj   │  │Mia   │  │Léa   │  │... N │            │
│  │alpi  │  │alpi  │  │alpi  │  │alpi  │  │      │            │
│  └──┬───┘  └──┬───┘  └──┬───┘  └──┬───┘  └──┬───┘            │
│     │         │         │         │         │                │
│     └─────────┴─────────┴─────────┴─────────┘                │
│                       │                                      │
│              ┌────────┴─────────┐                            │
│              │                  │                            │
│    ┌─────────▼──────┐    ┌──────▼─────────┐                  │
│    │ research-bot   │    │ tools-bot      │                  │
│    │ (shared, RO)   │    │ (HR queries,   │                  │
│    │                │    │  calendar, …)  │                  │
│    └────────────────┘    └────────────────┘                  │
│                       │                                      │
│              ┌────────▼──────────┐                           │
│              │ audit + log hub   │                           │
│              │ (aggregates       │                           │
│              │  agent.log,       │                           │
│              │  approval.log)    │                           │
│              └───────────────────┘                           │
└──────────────────────────────────────────────────────────────┘
```

- **Profiles:** 1 per employee on their device, plus 1 per shared
  service (research-bot, tools-bot), plus 1 for the log hub.
- **Identity & capability surface:** each employee grants
  `research-bot` only `link.ask`, nothing else. `tools-bot` might
  get `link.ask` with a narrow budget. Peer lists are seeded at
  onboarding by the IT admin.
- **Audit.** Every agent turn is logged to `agent.log`; every
  non-safe shell decision to `approval.log`. An employee's logs
  live on their device; a forwarder (rsyslog, Vector, fluentd)
  ships them to the log hub in a format your SIEM consumes. See
  [OPERATIONS.md](OPERATIONS.md) for the log schema.
- **Cost management.** Per-profile `.env` + model selection means
  finance can ring-fence spend per team. ALP.2 enforces budgets on
  peer traffic with daily token / USD caps and per-minute limits.
- **Sandbox + approval.** The company policy pushes
  `tools.terminal.sandbox: true` into every profile's
  `config.yaml` at onboarding. Dangerous commands always deny
  without `ALPI_YOLO=1` (which isn't set).
- **Network posture.** ALP.2 speaks Noise_XK directly over
  Tailscale / WireGuard. No HTTPS, no cert management, no public
  endpoint. If Tailscale goes, alpis can't reach each other —
  that's the point. Local TUIs keep working.
- **Commercial path.** This topology is production deployment by a
  legal entity. Evaluation and internal development are covered by
  the Additional Use Grant; production rollout goes through
  Satoshi Ltd. (`info@satoshi-ltd.com`).

### What alpi does not try to solve at enterprise scale

Deliberately out of scope, so users don't wait for features that
aren't coming:

- **SSO / SAML / OIDC for human access.** Each user owns their
  own profile on their own device — authentication is to your
  OS, not to alpi. Enterprise SSO belongs at the Tailscale /
  VPN / device-policy layer.
- **Centralised secret management.** Per-profile `.env` is
  deliberately local. If you want HashiCorp Vault / AWS Secrets
  Manager, wire it up with an MCP server that resolves secrets
  on demand — alpi itself does not hold a central secret store.
- **Federation with non-alpi agents.** ALP is a closed protocol
  on purpose (see [ALP.md Design principles](ALP.md)). If you
  want to talk to non-alpi agents, expose them as MCP servers
  and each alpi connects to them individually — not through ALP.

## Choosing your shape

| You are… | Start with | Upgrade path |
|---|---|---|
| A single user on one machine | **(1) Laptop only** | → (4) Multi-device when you get a second device. |
| A user with a NAS / home server | **(2) Laptop + home server** | → (3) add specialised roles on the home server. |
| A user wanting role-based alpis | **(3) One machine, many profiles** | → (5) if the household wants in. |
| A family / small team | **(5) Family / small team** | → (6) when it stops being a household. |
| A company | **(6) Enterprise** (commercial path) | — |
