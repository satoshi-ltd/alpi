# Roadmap

Open work for alpi. Shipped work lives in
[CHANGELOG.md](../CHANGELOG.md) — this file never repeats it. For
technical reference of what currently ships, see
[ARCHITECTURE.md](ARCHITECTURE.md).

Audience: the creator ([@soyjavi](https://github.com/soyjavi)) and
any future contributor reading the repo cold.

Legend: 🔵 backlog · 🟡 next up · ⏸ blocked · 🔴 gate.

---

## v0.14 — production exposure and runtime hardening

v0.13 never shipped: its number was skipped when the runtime work landed
first as v0.14.0, so its production-exposure gates carry over unchanged and
remain the exit criterion for this cycle. The five-hotel web-factory
validation that cleared v0.14.0 for release also left a short hardening
list targeting v0.14.x patch releases.

### Runtime hardening

MCP.1 and PROC.1 were isolated on the 2026-09-03 mirai box: sentinel's
PR-review cron leaked one orphaned `bitbucket-mcp` server per run, 38 zombies
against 41 h of daemon uptime.

| ID | Item | Status |
|---|---|---|
| MCP.1 | `MCPClient.stop()` signals only the process it spawned. A stdio server started through `npx` is a wrapper chain (`npm exec …` → `sh` → server), so `terminate()` reaches the wrapper and the real server survives, orphaned, on every turn. Spawn with `start_new_session=True` and stop the group with `os.killpg`, the pattern `_stop_process_group` in `alpi/alp/pipeline_gates.py` and the `terminal` tool already use — `alpi/mcp/client.py` is the only spawn site that does neither. | 🟡 |
| PROC.1 | The daemon is PID 1 inside the image (`ENTRYPOINT ["alpi-docker"]`, no init), so every orphan in the container reparents to it and stays a zombie: it never calls `wait()` on children it did not spawn. Reap them when `os.getpid() == 1` — a SIGCHLD handler draining `waitpid(-1, WNOHANG)` — so a hard-killed turn, a crashed MCP server, or a `terminal` grandchild cannot accumulate. Independent of MCP.1: that closes the common leak, this bounds every other path. | 🟡 |
| COST.1 | Per-pipeline cost telemetry: attribute ledger spend and tokens to a pipeline run, replacing manual checkpoint arithmetic. | 🔵 |
| BG.1 | `alpi doctor` verifies the installed LiteLLM against the pinned version and hashes, catching a supply-chain swap locally (review cadence stays in [OPERATIONS.md](OPERATIONS.md)). | 🔵 |

### Host token hardening

Raised by the 2026-09 mirai WSS deployment review. Migration invariant for
every item: **no existing connection is lost or re-paired.** The cleartext
token lives on the client, which keeps presenting it unchanged; only the
server-side representation and policy move.

| ID | Item | Status |
|---|---|---|
| TOKEN.1 | Store device tokens hashed at rest (SHA-256), matching what pairing secrets already do. Rename `token` → `token_hash` so the one-shot store migration is explicit and idempotent — same pattern as the `devices.yaml` → `connections.yaml` migration; auth hashes the presented token before `compare_digest`. | 🟡 |
| TOKEN.2 | Optional device-token expiry driven by **inactivity**, not age: `host.token_ttl_days` (absent = today's behavior, no expiry) evaluated against `last_seen`, so devices in active use never expire and legacy rows stay valid until the operator sets the policy. Expired rows must read as inactive to `_active_authorizations` so live sessions drop too. | 🟡 |
| RATE.1 | Simple pre-auth rate limit on the WS listener: reuse the sliding-window `RateLimiter` from `alpi/alp/rate_limit.py` keyed by source address, counting auth failures only; over-cap closes `1013` before token validation. Behind Caddy the socket peer is the proxy, so honor `X-Forwarded-For` only when the peer address is private/loopback. Settles the edge per-IP decision left open in ONLINE.4. | 🟡 |

### Production client exposure

The public host channel already ships: WSS routes, one-time pairing,
per-device revocation, role/profile scope, abuse bounds, Docker/Caddy topology,
and attributed administrative activity. Beyond the token hardening above,
this cycle does not add another security layer to that protocol. It proves
the supplied design on the first definitive customer deployment.

| ID | Item | Status |
|---|---|---|
| ONLINE.1 | Deploy one isolated Alpi runtime and volume per mutually untrusted customer; profiles/connections remain an identity and RPC boundary, not tenant isolation. | 🔴 |
| ONLINE.2 | Put the definitive hostname behind Caddy with a valid public certificate; publish only TCP 80/443 and verify the effective Compose config exposes neither 49200 nor 7423. | 🔴 |
| ONLINE.3 | Run external Desktop/Mobile acceptance: authenticated WSS RPC succeeds, invalid certificates fail closed, live-stream revocation disconnects only the target device, and direct public probes to 49200/7423 fail. | 🔴 |
| ONLINE.4 | Establish the operating checks: certificate-expiry monitoring, WebSocket capacity/rejection alerts, and an explicit decision on an edge per-IP limit where the real client IP is available. | 🔴 |

The cycle is complete only after those checks pass against the real domain and
firewall, not another local tunnel. Credential-loss and backup-exposure
response is already defined in [OPERATIONS.md](OPERATIONS.md);
enterprise-grade external audit remains demand-gated as `AUDIT.2` below.

---

## Backlog — demand-gated

Only plausible next moves stay prominent. Everything here waits for observed
usage or a concrete blocker; standing maintenance belongs in
[OPERATIONS.md](OPERATIONS.md), not in the product backlog.

### Candidates

| ID | Candidate and promotion condition |
|---|---|
| TERM.2 | SSH terminal backend for remote command execution. Promote when an unattended profile needs to operate on a remote machine. |
| SANDBOX.1 | OS sandbox effective inside the managed Docker runtime, so a `terminal`-enabled profile stays contained even when the container is the only wall. Promote before any member-scoped connection is granted a profile with `terminal` enabled (mirai: neo). |
| AUDIT.2 | Enterprise audit and accountability: complete local mutation coverage, then add tamper-evident external records, provider policy, encryption, or RBAC only when a real fleet or compliance regime requires them. |
| ALP.7 | Pinned shared memory per workgroup (`wiki.md`). Promote when sustained workgroup use shows that the transcript is no longer enough. |
| SK.2 | Safe skill import (`alpi skill import <dir\|zip>` with preview, scan, and install). Promote when users repeatedly exchange skills outside their own profile. |
| AI (3) | Structured entity memory with selective injection. Promote when keeping the markdown store coherent becomes a repeated source of defects or selective recall is required. |
| TTS.1 | Host-served local TTS and a single voice catalog. Promote when voice becomes a sustained client surface. |

### Watchlist

These ideas remain recorded without presenting them as likely next work.

| ID | Revisit only when |
|---|---|
| BROWSER.1 | A vetted lightweight backend passes real acceptance and Chromium's measured disk or RAM footprint blocks a target host. |
| ALP.8 | Users need guaranteed throughput, dynamic worker pools, or capacity negotiation. |
| ALP.3+ | Persistent workgroups demonstrate sustained parallel tasks that targeted tasks and pipeline continuation cannot cover. |
| AY / BF-8 | A real skill author or import community needs a federated marketplace, versioning, or update flows. |
| AJ | A concrete site requires browser realism beyond Playwright's current posture. |
| AQ | A real voice surface needs continuous push-to-talk or hotword loops after host-served TTS exists. |
| UX.6 / External secrets | Editing non-provider `.env` entries or central key rotation becomes repeated friction. |

---

## Principles

alpi **respects the ToS of every provider it integrates with**. When
an LLM vendor offers a paid subscription tied to a specific first-party
client (the vendor's own chat app, IDE, or CLI), that subscription is
for THAT client. Reverse-engineering the private OAuth flow of the
official CLI to route a third-party agent against the same quota is:

- A clear ToS violation.
- Disrespectful to the vendor's product boundaries.
- Unsafe for users (accounts can be banned; the reversed flow can
  break any time).

Private subscription routing is not part of alpi's product shape. If
a vendor publishes an official
OAuth-for-third-parties flow in the future (documented, stable,
bindable), we adopt it then.

**Practical consequence:** users pay per-token API access through
their own keys. That cost is honest and visible. Subscription
routing is not on the roadmap.

See the **Why alpi is built like this** section in
[README.md](../README.md) for how the six Satoshi Ltd. principles
(Privacy by Design, User Sovereignty, Security First, Open Source,
Zero Knowledge, Digital Sovereignty) map to concrete choices in this
repo.

---

## Decisions discarded — don't relitigate

| Decision | Reason |
|---|---|
| Vendor subscription OAuth | ToS violation and account-risk surface; users bring normal API keys. |
| Chat-app gateways (Telegram, Matrix, Signal, WhatsApp, Discord, …) | Retired in v0.10 — third-party chat bridges add attack surface and upkeep; the desktop/mobile/terminal apps are the surface, and email is an on-demand tool. |
| Smart-home orchestration | Device protocols and physical-world policy belong in Home Assistant / MCP / user skills, not core. |
| LangGraph / CrewAI / AutoGen as core | Graph frameworks do not match Alpi's profile/workgroup runtime and pull toward hosted observability. |
| Image generation as a core tool | Useful via MCP or user skills, but a built-in provider surface would turn Alpi into a creative-tool platform. |
| Mixture-of-agents runtime | Expensive research pattern; workgroups cover explicit multi-profile collaboration. |
| RL / fine-tuning hooks | Research infrastructure, not a personal-agent product surface. |
| Cost telemetry per skill / tool | Per-profile daily ledger is enough while skills are sparse and user-owned. |
| Browser anti-bot depth / camoufox | Cat-and-mouse and heavy dependencies; current Playwright posture is enough until a real user hits a wall. |
| Go / Bubbletea rewrite | No upside over the Python stack and LiteLLM ecosystem. |
| Heavy TUI chrome / rich.Live inline UI | Tried; Textual minimal TUI is the maintained shape. |
| SQLite `state.db` for sessions | Plain JSON remains fast and inspectable at current scale. |
| Separate conversation export schema | Host JSON-RPC session verbs are the contract; add export only for a second real consumer. |
| Pending approval files / skill approval gate | Removed; scanner + inline tool flows are lower friction. |
| Regex shell sandbox / workspace wall | False security without OS sandboxing; use real sandboxing and sensitive-path denylist. |
| `.bak` sibling on every `write_file` | Too much workspace clutter; backups stay limited to memory files. |
| `alpi setup → Identity` wizard / starter packs | Profiles are shaped through chat and examples, not binary templates. |
| Default skills bundle | Runtime capabilities are first-class tools; skills are user-owned. |
| `alpi run "<prompt>"` | Covered by `alpi chat --once "<prompt>"`. |
| Auto-reflect on Ctrl+C / post-session `/reflect` | Unsafe or redundant; inline memory/skill updates are the path. |
| TUI accessibility pass | Desktop is the right accessible surface; terminal APIs are weaker. |
| `duckduckgo-search` | Deprecated; migrated to `ddgs`. |
