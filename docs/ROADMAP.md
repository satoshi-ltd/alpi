# Roadmap

Open work for alpi. Shipped work lives in
[CHANGELOG.md](../CHANGELOG.md) — this file never repeats it. For
technical reference of what currently ships, see
[ARCHITECTURE.md](ARCHITECTURE.md).

Audience: the creator ([@soyjavi](https://github.com/soyjavi)) and
any future contributor reading the repo cold.

Legend: ✅ shipped · 🔵 backlog · 🟡 next up · ⏸ blocked · 🔴 gate.

---

## v0.9 cycle (open)

**Theme: safer unattended runtime.**
The retrieval spine is done. v0.9 focuses on letting profiles run longer,
farther away from the user's main machine, and with better failure evidence —
without turning Alpi into a broad orchestration platform.

| ID | Item | Status |
|---|---|---|
| AUDIT.1 | `alpi audit` — local dependency / config / security posture scan: stale deps, known CVEs, exposed binds, risky permissions, and missing hardening warnings. | 🟡 |

v0.9 should stay narrow: improve observability and failure handling on
surfaces Alpi already owns. No new execution backend, no worker-lane
marketplace, no cloud sandbox abstraction, and no automatic file migration.
With the credential-file denylist shipped, `AUDIT.1` is next and
closes the safety posture.

### AUDIT.1. `alpi audit`

`alpi doctor` explains whether the current install is healthy. AUDIT.1 is the
deeper, explicit security / maintenance pass: dependency CVEs, stale pinned
versions, risky host binds, world-readable control files, bad permissions,
disabled hardening, and config combinations that are valid but unsafe for an
unattended profile.

The first version should stay local and report-only. No cloud telemetry, no
auto-upgrades, no package-manager writes. It can call public vulnerability
databases only when the user explicitly runs the command and network is
available; otherwise it reports what can be checked offline.

## v0.10 cycle (planned)

**Theme: artifact-capable agents on lighter runtime surfaces.**
v0.8 gave profiles semantic recall and workgroup transcript search. v0.9
hardens unattended safety. v0.10 should make that base more useful for real
agentic work: browsing exact past conversations, moving artefacts between
peers without abusing JSON envelopes, and proving whether the browser stack
can get lighter on small hosts.

This cycle can be more ambitious than v0.9, but it should still stay inside
surfaces Alpi already owns. No worker-pool scheduler, no marketplace, no cloud
sandbox, no new gateway family, and no default anti-bot posture.

| ID | Item | Status |
|---|---|---|
| CM.5 | Exact session browse / scroll — cheap lexical session navigation around the original message window, complementing CM.4 semantic recall. | 🟡 |
| ALP.5 | Blob transfer — `link.put_blob` / `link.get_blob`, content-addressed and chunked, for screenshots, PDFs, skill outputs, and other artefacts that should not live inline in an ALP JSON envelope. | 🔵 |
| BROWSER.1 | Optional lightweight browser backend — acceptance-test Obscura or a similar CDP backend behind the existing `browser` tool to cut Chromium's footprint on small hosts. | 🔵 |

### CM.5. Exact session browse / scroll

CM.4 gives semantic recall over past sessions. Sometimes the right answer is
not another embedding hit, but the exact message window around a remembered
conversation. CM.5 adds a cheap lexical/browse layer: list recent sessions,
search exact text, and scroll around a message window without extra LLM calls.

This complements `recall_sessions`; it does not replace it. The semantic tool
finds "that conversation about pricing thresholds", while CM.5 lets the agent
open the original surrounding turns once it has a session id or anchor.

### ALP.5. Blob transfer

Two new verbs — `link.put_blob(bytes, hash)` and `link.get_blob(hash)` —
for sharing artefacts that have no business inline in a JSON envelope:
a PDF, a dataset, the output of a skill, a screenshot.

**Wire shape.** Content-addressed by SHA-256; the recipient stores under
`~/.alpi/<profile>/alp/blobs/<hash>` and dedups across calls. Chunked
transfer with per-chunk AEAD; the final frame carries the full-blob
signature so the receiver can verify end-to-end.

**Scope guard.** ALP.5 is for peer-to-peer artefact transfer only. It does not
turn ALP into a shared filesystem, does not add sync folders, and does not
auto-ship every output attachment. The sender still chooses what to share.

### BROWSER.1. Optional lightweight browser backend

The `browser` tool drives a full Playwright + Chromium install. That is the
right engine for interactive automation, but Chromium is heavy: a ~520MB
per-bump download and 200MB+ of RAM, which hurts small or headless hosts. A
Rust headless engine like Obscura speaks the Chrome DevTools Protocol and
ships as a ~70MB binary in ~30MB of RAM, so it could back the same tool far
more cheaply where full fidelity is not required.

It would land as an **opt-in CDP backend behind the existing tool interface** —
never the default, never with stealth/anti-detect on. Playwright stays the
engine for the interactive `browser` tool.

**Why it waits.** Obscura is a young, reimplemented engine (V8 plus a partial
DOM and a CDP subset) with a scraping-evasion trust profile, against a
battle-tested Playwright + Chromium. It earns adoption only after its source is
vetted, its WPT conformance is tracked, it passes real acceptance, and it
measurably cuts Chromium's footprint on a host that needs it.

---

## Backlog — demand-gated

Items worth keeping, but not committed to a numbered cycle. Some are
well-defined and simply waiting for pull from real usage; others are
deliberately parked because they would broaden the product. The promotion
criterion is always the same: real user demand, or a concrete blocker for a
v0.x feature that depends on it. Nothing graduates because it is interesting.

| ID | Item | Status |
|---|---|---|
| TERM.2 | Docker / SSH terminal backends — isolated or remote command execution for unattended profiles once local sandboxing is no longer enough. | 🔵 |
| AUDIT.2 | Enterprise audit & accountability — actor attribution on the host plane, append-only / external audit sink, LLM-egress logging + provider policy, at-rest encryption, and RBAC/SSO. | 🔵 |
| Notify.ntfy | ntfy gateway — accountless self-hostable notification gateway, opt-in only. | 🔵 |
| ORG.2.B/C | Workspace overlay (`cfg.workspace_path` as list) + first-class runtime org entity (`~/.alpi/orgs/<id>/`) with roles, event fan-out, and shared RAG. | ⏸ |
| ALP.7 | Pinned shared memory per workgroup (hub-anchored `wiki.md`). | 🔵 |
| ALP.8 | Workgroup capacity scheduling — optional profile capacity, queue/defer telemetry, or worker-pool assignment for high-throughput orgs. | 🔵 |
| ALP.3+ | Multi-task workgroups — opt-in `multitask`, letter-prefixed task IDs, per-task roster/dispatch/budget. | 🔵 |
| Signal | Signal gateway via signal-cli. | 🔵 |
| AY | Skills marketplace — federated, signed, never centralised. | 🔵 |
| SK.2 | Safe skill import (`alpi skill import <dir\|zip>` — preview, scan, install). | 🔵 |
| BF-8 | Skill versioning / install-update flows. | 🔵 |
| AI (2) | Memory v2 — TUI panel (collapsible, edit-in-place, "forget this"). | 🔵 |
| AI (3) | Entity memory — structured SQLite store (`entities`/`relations`/`observations`) replacing the markdown memory model, with selective injection per turn instead of full-blob system prompt. | 🔵 |
| AJ | Browser realism — Cloudflare / captcha / fingerprint depth. | 🔵 |
| AQ | Continuous voice mode (push-to-talk, hotword loops). | 🔵 |
| Webhook | Inbound HTTP triggers (HMAC-signed). | 🔵 |
| BG re-audit | LiteLLM quarterly review — bump pin, run LLM probe, swap if better alternative emerges. | 🔵 |
| Matrix E2EE | Olm/Megolm sessions, encryption store, SAS device verification, encrypted-room send/read tests. | 🔵 |
| TTS.1 | Local TTS engine + daemon-served voice — single host-served voice catalog, deprecate desktop-local synthesis. | 🔵 |
| UX.6 | Desktop `.env` manager — per-profile environment editor (mask/reveal/audit) for keys other than provider keys. | 🔵 |
| External secrets | Bitwarden / external secret manager resolver for provider keys. | 🔵 |

### TERM.2. Docker / SSH terminal backends

Local terminal execution plus optional OS sandboxing is enough for the
current product. Docker and SSH become worthwhile only when a real
unattended profile needs stronger isolation, reproducibility, or a remote
machine that the agent can damage without touching its own code or the
user's main workstation.

The first implementation should be conservative: one configured backend
per profile, no provider zoo, no cloud sandbox abstraction, and no
automatic migration of local files.

**Promotion condition.** A real profile needs isolation or a remote machine
that the local terminal + OS sandbox cannot provide. Until then, TERM.2 stays
backlog; hardening the existing runtime comes first.

### Notify.ntfy. ntfy gateway

An optional gateway for users who already run or trust ntfy and want a
simple notification overlap path. It should be opt-in, accountless where
possible, and clearly secondary to Alpi-owned apps plus persistent outputs.

**Why it waits.** Native app notifications are the primary product path.
Adding another gateway is only justified if users explicitly ask for ntfy,
or if self-hosted homelab users need a notification bridge while mobile app
delivery remains local/poll-based.

### ORG.2.B/C. Workspace overlay + first-class runtime org entity

ORG.2 is a three-layer plan. **Layer A — convention** — shipped as the
`organizations/` source tree with per-org `org.yaml`, default workspace
at `~/alpi/organizations/<name>/`, and a unified `organizations/setup.py`
that bootstraps any org from its YAML. Each profile carries
`cfg.org = <name>` after bootstrap so it knows which org it belongs
to. See [`organizations/README.md`](../organizations/README.md) and
[`docs/ORGANIZATION.md`](ORGANIZATION.md).

Layers B and C remain deferred. They're only worth building if the
convention proves insufficient — non-Archive writers in `company`,
concurrent scans on the hot path, or enforced access roles across
humans.

1. **Layer B · Workspace overlay.** `cfg.workspace` (a single string
   today) becomes a list: `[profile_workspace, org_workspace]`. File
   tools read both and write to the profile root by default, with an
   explicit shared scope when the agent intends to touch org-shared
   files. Adds a real ownership model without inventing a new runtime
   primitive.
2. **Layer C · First-class runtime org entity.**
   `~/.alpi/orgs/<id>/workspace/` with member profiles, per-member
   roles, event fan-out across the org, and a shared RAG index.
   Heaviest option — only land if the overlay also proves insufficient.

Promotion condition for B: a user reports that the convention forces
awkward duplication or coordination between two profiles in the same
org. Promotion condition for C: B itself proves insufficient.

### AUDIT.2. Enterprise audit & accountability

`AUDIT.1` (v0.9) is the local posture scan — "is this install hardened?".
AUDIT.2 is the orthogonal axis a CTO asks about — "can I prove who did
what, and can the trail be trusted?". alpi already records a lot (session
transcripts, the run ledger, the approval log, the cost ledger, ALP
peer-attributed calls — see
[SECURITY.md → Audit trail & accountability](SECURITY.md)), but it is
personal-grade: local, mutable, and unattributed on the host plane.
AUDIT.2 is the set of changes that make it fleet-grade, in rough
priority order:

1. **Actor attribution on the host plane.** Propagate the validated
   device `token_id` (and its role) into every host RPC handler and stamp
   it onto the run ledger, approval log, and config-mutation events. Today
   the token is checked at dispatch and then dropped — a privileged change
   cannot be tied to a device or human. Highest value, smallest change; no
   redesign needed.
2. **Append-only / external audit sink.** Mirror sessions, runs,
   approvals, and config mutations to a tamper-evident destination
   (syslog/SIEM, or S3 with object-lock / a WORM path), optionally with
   per-record signing or a hash chain so local edits are detectable.
   Closes the "logs are locally mutable" gap.
3. **LLM-egress logging + provider policy.** Record what leaves to each
   model provider (at least prompt/message/tool-output sizes and a
   content hash, optionally full payloads), and a policy knob to restrict a
   profile to approved or on-prem (Ollama) providers. The compliance gap
   that matters for regulated data.
4. **At-rest encryption** of sessions/memory/logs (reuse the backup KDF,
   or lean on FileVault/LUKS at the deployment layer and document it).
5. **RBAC / SSO.** Groups beyond admin/member and an IdP-bound
   device↔human mapping. Heaviest; only if a managed fleet needs it.

**Why it waits.** alpi is a personal, local-first agent; this whole axis
is dead weight for a single owner who already trusts their own machine.
It is also large and partly deployment-specific (a SIEM, an IdP, an
object store the user already runs).

**Promotion condition.** A concrete fleet/enterprise deployment asks for
attributable, tamper-evident audit — or a compliance regime (SOC 2,
HIPAA, PCI) is in scope for a real operator. Start with item 1 (actor
attribution): it is cheap, useful even for a single power user, and a
prerequisite for everything else.

### Listening-first notes

The items below are intentionally light until a real deployment pulls them
forward:

- **ALP.7** waits because pinned shared memory adds concurrency, history, and
  role semantics to every workgroup. Promote only if workgroups become heavily
  used and the transcript is no longer enough.
- **ALP.8** waits because current dispatch already allows opportunistic
  concurrency across workgroups. Promote only if users need guaranteed
  throughput, dynamic worker pools, or capacity negotiation beyond adding more
  profiles.
- **ALP.3+** waits because targeted tasks plus pipeline continuation already
  cover sequential project pipelines. Revisit only if persistent workgroups
  (`template`, `quality`, `brand-library`) show real sustained parallelism.
- **Signal** is a strong privacy fit, but new gateways are out of scope while
  Alpi-owned clients are the primary mobile surface.
- **AY / SK.2 / BF-8** wait on a real import or author community. Until then,
  skills stay user-owned and local.
- **AI (2) / AI (3)** wait until markdown memory demonstrably breaks: either
  power users need a TUI memory editor, or `MEMORY.md` becomes large enough
  that prompt size / cost is a real bottleneck.
- **AJ** is cat-and-mouse browser evasion. Without a concrete failing use case,
  scope cannot close.
- **AQ / TTS.1** wait until voice becomes a real surface. If that happens,
  daemon-served local voice should land before always-on voice loops.
- **Webhook** waits because it is another inbound automation surface, not core
  product UX.
- **BG re-audit** is standing maintenance, not product scope; cadence and
  procedure live in `OPERATIONS.md → Dependencies`.
- **Matrix E2EE** waits until a user runs the Matrix gateway against a
  non-self-hosted homeserver.
- **UX.6 / External secrets** wait until editing non-provider `.env` entries or
  central key rotation becomes repeated user friction.

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
| Gateway sprawl: WhatsApp, Discord, Slack, XMPP | High token/blast-radius or operational cost; Alpi-owned apps are the primary surface. |
| Gateway "open in Alpi" nudges | Would incentivise gateway usage; gateways stay text-first and secondary. |
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
