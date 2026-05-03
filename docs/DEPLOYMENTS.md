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

The baseline. One profile, one machine, TUI for chat, optional
gateway for messaging.

```
┌─────────────────────────────────────┐
│ laptop                              │
│                                     │
│   alpi (TUI / desktop)              │
│     │                               │
│     ├─ ~/.alpi/  (default profile)  │
│     └─ alpi daemon                  │
│          ├─ gateway: Telegram /     │
│          │           IMAP / Gmail   │
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
  Linux). 24/7 messaging + cron from minute one.
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
  daemon, which hosts gateway + scheduler + ALP listener). Laptop
  just runs `alpi` when the user sits down.
- **Best for:** power-user individual with a house NAS /
  mini-server. Also: "I want scheduled jobs to run even when my
  laptop is closed."

## 2a. Umbrel home server

Umbrel is the packaged form of the home-server topology. The app runs
inside Docker, stores the Alpi root on a persistent Umbrel volume, and
opens the existing TUI through Umbrel's authenticated app proxy.

```
┌──────────────────────────────────────┐
│ Umbrel                               │
│                                      │
│  app_proxy                           │
│      │                               │
│      ▼                               │
│  ttyd → alpi TUI                     │
│                                      │
│  alpi daemon                         │
│    ├─ gateway: Telegram / IMAP /     │
│    │           Gmail / Matrix        │
│    ├─ scheduler                      │
│    ├─ ALP listener                   │
│    └─ workgroups poller              │
│                                      │
│  /data/.alpi  (persistent volume)    │
└──────────────────────────────────────┘
```

- **Package:** `deploy/umbrel/alpi/`.
- **Profiles:** starts with `default`, with the same multi-profile
  layout as any Linux install.
- **UI:** browser terminal running `alpi`; no separate web dashboard.
- **Storage:** `${APP_DATA_DIR}/data` is mounted as `/data`, and
  `HOME=/data` makes `/data/.alpi` the profile root.
- **Security boundary:** Umbrel authentication protects the terminal
  surface. The host Unix socket and raw profile files are not exposed
  to the browser.
- **Backup:** use the normal encrypted archive flow (`alpi backup
  create` / `alpi backup restore`) for portable profile moves; Umbrel
  can also back up the app volume.

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
- **Per-profile services.** Each profile's `service:` block in
  `config.yaml` decides what the daemon spawns: `assistant` runs
  Telegram + scheduler + ALP; `cron` runs only the scheduler;
  `researcher` only ALP. Add or remove a profile and `alpi daemon
  restart` to apply.
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
