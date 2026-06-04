# Roadmap

Open work for alpi. Shipped work lives in
[CHANGELOG.md](../CHANGELOG.md) — this file never repeats it. For
technical reference of what currently ships, see
[ARCHITECTURE.md](ARCHITECTURE.md).

Audience: the creator ([@soyjavi](https://github.com/soyjavi)) and
any future contributor reading the repo cold.

Legend: ✅ shipped · 🔵 backlog · 🟡 next up · ⏸ blocked · 🔴 gate.

---

## v0.8 cycle (shipped)

**Theme: multimodal input + knowledge retrieval — complete.**
v0.8 opened the agent to non-text content (MM.1), made attachments durable,
searchable workspace documents (RAG.2), added semantic recall over past
sessions (CM.4), and semantic search over workgroup transcripts (ALP.6) — all
shipped on one local embedding / sqlite-vec retrieval layer. One store, three
surfaces: workspace documents, conversation history, workgroup transcripts.
Per-feature detail lives in [CHANGELOG.md](../CHANGELOG.md).

## v0.9 cycle (open)

**Theme: safer unattended runtime.**
The retrieval spine is done. v0.9 focuses on letting profiles run longer,
farther away from the user's main machine, and with better failure evidence —
without turning Alpi into a broad orchestration platform.

| ID | Item | Status |
|---|---|---|
| OPS.1 | Turn / process run ledger — compact per-turn records for long-running agent, schedule, terminal, and workgroup turns: pid, backend, start/end, timeout reason, last tool, output tail. | 🟡 |
| RT.1 | Provider stale-call hardening — first-byte / stream-idle watchdogs, jittered retries, and clearer terminal-failure surfacing for slow or stuck LLM providers. | 🟡 |

v0.9 should stay narrow: improve observability and failure handling on
surfaces Alpi already owns. No new execution backend, no worker-lane
marketplace, no cloud sandbox abstraction, and no automatic file migration.

### OPS.1. Turn / process run ledger

Long-running work today leaves evidence in several places: session events,
schedule events, terminal output, workgroup transcript posts, and daemon logs.
OPS.1 would add one compact per-turn run ledger so failures are diagnosable
without spelunking every surface.

The record should stay operational, not product analytics: profile,
session/workgroup/job id when present, process id, terminal backend, start/end,
exit code, timeout reason, last tool, and a capped output tail. It should help
answer "what was running, where did it stop, and why?" for schedules,
workgroup poller turns, terminal commands, and unattended agent turns.

**Why now.** The retrieval and workgroup layers are productive enough that
Alpi is doing more unattended work. Before adding a new backend, the existing
runtime needs one reliable evidence trail for hangs, timeouts, and silent
turns.

### RT.1. Provider stale-call hardening

Alpi already hardened workgroup turns with idle/backstop timeouts. RT.1
applies the same discipline to LLM provider calls: first-byte watchdogs,
stream-idle watchdogs, jittered retries, and clearer surfaced failure reasons
when a provider accepts a request and then stalls.

Scope stays runtime-only. No provider marketplace, no automatic model
switching beyond the existing fallback policy, and no telemetry upload. The
deliverable is predictable failure and retry behaviour for slow or flaky
providers.

**Why now.** Provider stalls are one of the few failure modes that can make
Alpi look frozen while the daemon is otherwise healthy. This is hardening of
the existing loop, not a new product surface.

## Future releases

Items worth doing, but not part of the next two cycles.

| ID | Item | Status |
|---|---|---|
| SEC.1 | Context injection hardening — shared scanner for recalled memory, learned documents, workgroup transcript snippets, and tool results before they enter model context. | 🔵 |
| FS.1 | Credential file denylist audit — defense-in-depth read/write blocks for provider keys, profile control files, `.env*`, SSH/cloud creds, and project-local secret stores. | 🔵 |
| AUDIT.1 | `alpi audit` — local dependency / config / security posture scan: stale deps, known CVEs, exposed binds, risky permissions, and missing hardening warnings. | 🔵 |
| CM.5 | Exact session browse / scroll — cheap lexical session navigation that complements CM.4 semantic recall when the user needs the original message window. | 🔵 |
| TERM.2 | Docker / SSH terminal backends — isolated or remote command execution for unattended profiles once local sandboxing is no longer enough. | 🔵 |
| ALP.5 | Blob transfer — `link.put_blob` / `link.get_blob`, content-addressed, chunked AEAD. Depends on real workgroup usage to justify the protocol complexity. | 🔵 |
| Notify.ntfy | ntfy gateway — accountless self-hostable notification gateway, opt-in only. Lower priority because Alpi-owned apps + outputs remain the primary notification surface. | 🔵 |
| ORG.2.B/C | Workspace overlay (`cfg.workspace_path` as list) + first-class runtime org entity (`~/.alpi/orgs/<id>/`) with roles, event fan-out, and shared RAG. Deferred — see entry below. | ⏸ |

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

### SEC.1. Context injection hardening

RAG.2, CM.4, and ALP.6 made Alpi better at remembering: learned files,
past sessions, and workgroup transcripts can now return text into future
model context. That also makes poisoned recalled content more relevant.
SEC.1 adds a shared scanner for content that enters model context from
memory, learned documents, transcript search, session recall, and tool
results.

The first version should be warning-first except for clearly dangerous
write/install paths. It should detect classic prompt injection, hidden
unicode, system-prompt exfiltration requests, and obvious credential
exfiltration. The goal is a single small library used consistently, not a
security product or a moderation layer.

### FS.1. Credential file denylist audit

Alpi's tools should not casually read or write obvious credential stores.
FS.1 is a defense-in-depth audit across file tools, attachment learning, and
terminal-adjacent helpers for `.env*`, SSH keys/config, cloud credentials,
profile control files, provider key stores, and project-local secret files.

This is not a hard security boundary while terminal access exists. It is a
model-facing guardrail and audit signal: tools should return clear denials for
paths the agent normally has no legitimate reason to inspect directly.

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

**Why it waits.** ALP.5 is only worth the protocol complexity if
workgroups are heavily used and blobs are a real bottleneck.

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

---

## Future versions — listening first

Items that may or may not have legs. We deliberately don't
commit to a cycle for them — we'd rather hear from real alpi
users which ones they actually need before building. Each is
already analysed; the "why now?" question is the open one.

| ID | Item | Reason it waits |
|---|---|---|
| ALP.7 | Pinned shared memory per workgroup (hub-anchored `wiki.md`) | Heavy new surface (concurrency, history, roles) only justified if workgroups become heavily used |
| ALP.3+ | Multi-task workgroups — opt-in `multitask`, letter-prefixed task IDs, per-task roster/dispatch/budget | Targeted tasks + pipeline continuation already cover sequential per-project pipelines; revisit only if the persistent workgroups (`template`/`quality`/`brand-library`) show real, sustained parallelism |
| Signal | Signal gateway via signal-cli | Strong privacy fit, but new gateways are out of scope now that Alpi-owned clients are the primary mobile surface |
| AY | Skills marketplace — federated, signed, never centralised | Presupposes an active author community + adoption for discovery to matter |
| SK.2 | Safe skill import (`alpi skill import <dir\|zip>` — preview, scan, install) | Pulls toward marketplace/import-ecosystem mental model without a concrete user pull. Promote when somebody actually needs to migrate a batch of skills from another stack. |
| BF-8 | Skill versioning / install-update flows | Depends on SK.2 and imported-source metadata. Keep it out while import itself is deferred. |
| AI (2) | Memory v2 — TUI panel (collapsible, edit-in-place, "forget this") | UI weight for niche audience (power users with much memory); item 1 covers the substantive part |
| AI (3) | Entity memory — structured SQLite store (`entities`/`relations`/`observations`) replacing the markdown memory model, with selective injection per turn instead of full-blob system prompt | Markdown memory hasn't demonstrably broken yet for real users; AI(1) is a quality pass on the existing model. Promote when a user reports `MEMORY.md` is large enough that prompt size / cost becomes a real bottleneck. BA's shared `store` primitive (v0.5) is designed so the migration is incremental when promoted. |
| AJ | Browser realism — Cloudflare / captcha / fingerprint depth | Cat-and-mouse perpetuo; without concrete failing use case, scope can't close |
| AQ | Continuous voice mode (push-to-talk, hotword loops) | Niche unless voice becomes a real surface for users |
| Webhook | Inbound HTTP triggers (HMAC-signed) | Automation bridge, not product UX; needs repeated real demand before adding another inbound surface |
| BG re-audit | LiteLLM quarterly review — bump pin, run LLM probe, swap if better alternative emerges | Standing maintenance task; cadence + procedure documented in `OPERATIONS.md → Dependencies` |
| Matrix E2EE | Olm/Megolm sessions, encryption store, SAS device verification, encrypted-room send/read tests | MVP intentionally unencrypted; promote when an external user runs the bot against a non-self-hosted homeserver |
| TTS.1 | Local TTS engine + daemon-served voice — single host-served voice catalog, deprecate desktop-local synthesis | Current cloud TTS path works; promote alongside `AQ` (continuous voice) or when desktop/daemon catalog drift becomes a real operator burden |
| UX.6 | Desktop `.env` manager — per-profile environment editor (mask/reveal/audit) for keys other than provider keys | Provider keys already have a first-class flow; promote when editing other `.env` entries by hand becomes a real friction reported by users |
| External secrets | Bitwarden / external secret manager resolver for provider keys | Useful in managed fleets, but likely too much setup for the current solo/local product. Promote only if users ask for central rotation instead of local `.env` files. |

Promotion criteria: real user demand, or concrete blocker for
a v0.x feature that depends on it. None of these items
graduate "because we feel like it".

### ALP.3+ — Multi-task workgroups

Deferred out of v0.7: targeted tasks + pipeline continuation give sequential
per-project workflows everything they need without multitask's extra state,
partial-closure, quorum, and UI edge cases. It only earns its complexity if the
*persistent* workgroups (`template`, `quality`, `brand-library`) show real,
sustained parallelism.

v0.3 ships strict single-task: a new `#task` preempts the open one
(`"preempted by …"`), which forces convergence and keeps context narrow.
ALP.3+ would lift it via `multitask: true` + letter-prefixed IDs (`#task A …`,
`#done A: …`), each task carrying its own active state, per-member
`last_responded_seq`, dispatch gating, and budget headroom. Single-task stays
the default and fits per-project pipelines (one owner per phase via targeted
tasks); multitask earns its complexity — per-task quorum filters, N-thread UI,
per-task budget accounting — only when those persistent workgroups show
sustained parallelism.

**Explicitly not in scope.** Author-declared post cost (the honour-system
budget gate) and hub-anchored availability (cold workgroup when the hub
is offline) are deliberate design choices for a closed, trusted,
one-org-per-machine deployment — not defects. Single-task → multi-task
is tracked above as ALP.3+.

### ALP.7. Pinned shared memory per workgroup

Workgroups today are append-only chat. **ALP.7** would add a
single mutable surface per workgroup — a `wiki.md` held by the
hub, read by every member, writable by members the hub flagged
with the `writer` role at create or via `workgroup.grant`.
Captures state that does not belong in the rolling transcript:
design decisions, shared conventions, links, the workgroup's
"about" page.

**Verbs (proposed).** `workgroup.wiki.read(workgroup_id) →
text`, `workgroup.wiki.write(workgroup_id, text, parent_hash)
→ new_hash`, `workgroup.wiki.history(workgroup_id, limit)`.
Optimistic concurrency via `parent_hash` — two writers racing
get a clean conflict response, not a clobber.

**Why it waits.** Heavy new surface (concurrency, history,
roles). Only justified once workgroups are heavily used and
users start putting durable shared state into the transcript
where it doesn't belong. Until that happens, ALP.5 (blob
transfer, Future releases) covers the file case.

### AY. Skills marketplace

A curated, signed, *federated* registry. Not a centralised
store. A skill would be published by writing its manifest +
body to a git repo (any forge — GitHub, sourcehut,
self-hosted Gitea); the manifest carries a public key and the
body is signed. `alpi skill install <url>` clones the repo,
verifies the signature, runs the existing security scanner,
and lands the skill under `skills/<name>/`. There is no central
index; users discover skills the same way they discover npm
packages (links, blog posts, word-of-mouth) and the trust
anchor is the publisher's pubkey.

**Why federated, not centralised.** A central marketplace
becomes a chokepoint (review queue, takedowns, account bans,
eventual acquisition). Federation matches the Satoshi
principles — **Open Source**, **User Sovereignty** — and
reuses the same trust pattern as ALP peers (pubkey-pinned, no
discovery service).

**Why it waits.** Presupposes an active author community + a
catalog big enough that discovery matters. The runtime no longer
ships skills — capabilities the agent needs to self-describe live
as first-class tools (e.g. ``alpi_knowledge``), and skills are
entirely user-owned. BF skills v2 primitives make third-party
skills shippable through user-controlled imports (see SK.2 above),
so domain-specific work belongs in user-published skills.
Marketplace promotes only when there's evidence that real authors
want to publish for real users.

### AI item 2. Memory v2 — TUI panel

`/memory` today shows the three files verbatim. Item 2 would
add a richer surface: section-collapsible view, edit-in-place,
"forget this" quick action, filter by type.

**Why it waits.** UI work for a niche audience — power users
with enough memory accumulated to need navigation. AI item 1
(server-side generation quality, v0.5) covers the substantive
improvement. The panel promotes only when a user reports
"can't manage my memory from the TUI" as a real friction,
which has not happened yet.

### AJ. Browser realism — Cloudflare / captcha / fingerprint

Research-deferred. What exists: Playwright with
`playwright-stealth`, humanised typing, per-profile
`browser/state.json`. The open question is whether the current
posture clears common anti-bot checkpoints — Cloudflare's
"verify you are human" interstitial, Turnstile, hCaptcha
challenges when they fire on the agent's traffic.

**Why it waits.** Cat-and-mouse with anti-bot infrastructure
is perpetual; without a concrete failing use case (a user
reporting "I asked alpi to research X and it bounced off
Cloudflare"), scope can't close. Promote when a real user
hits a real wall, not on speculative parity. Extreme measures
(full fingerprint rotation, residential proxy) carry their own
risk and are not on the table without strong evidence.

### AQ. Continuous voice mode

Today voice is turn-based (record, transcribe, reply, speak).
Continuous mode would add push-to-talk or hotword-triggered
loops in the TUI / desktop app — turning voice into a usable
mode rather than a demo.

**Why it waits.** Niche unless voice becomes a real surface
for users. Until usage data shows voice is more than
occasional, the engineering cost (VAD, hotword detection,
continuous-mode UX) outweighs the benefit. STT + TTS quality
fixes can land incrementally on `main` without committing to
this larger redesign.

### Webhook. Inbound HTTP triggers (HMAC-signed)

Inbound HTTP triggered turns: GitHub Actions, Linear, Stripe,
calendar systems. The shape isn't obvious — auth model,
rate-limit policy, what subset of the agent is even safe to
expose to a webhook payload (read-only? full tools?).

**Why it waits.** A webhook gateway is the kind of feature
that *invites* people to wire their agent to anything — the
swiss-army-knife trap the project deliberately avoids. Need
evidence the use cases are real before building the surface.
Promote when several users describe the *same* webhook source
they want to wire, not on speculative coverage.

### TTS.1. Local TTS engine + daemon-served voice

Today speech synthesis is duplicated: daemon-side TTS and
desktop-side TTS have separate catalogs and caches. The clean
shape is one daemon-owned voice path:

1. benchmark local candidates on quality, disk size, latency,
   license, and locale coverage;
2. expose daemon-hosted synthesis and voice listing over the host
   plane;
3. deprecate desktop-local synthesis;
4. keep cloud TTS as an explicit opt-in provider if useful.

**Why it waits.** Current cloud TTS path works. Promote alongside
`AQ` (continuous voice mode) — at that point a single daemon-owned
voice path becomes the prerequisite rather than a cleanup
exercise. Or earlier if desktop/daemon catalog drift becomes a
real operator burden.

### UX.6. Desktop `.env` manager

Provider keys already have a first-class flow
(`host.providers.set_key`, masked in UI, audit-log on write).
Everything else in the per-profile `.env` — Bitbucket creds,
Telegram bot token, custom integration secrets — today requires
editing the file by hand or via terminal.

When promoted, `Settings → Environment` gets a per-profile card:

- list of `KEY` entries with mask + reveal toggle (same pattern
  as provider keys);
- inline edit / add / delete, debounced save via new
  `host.config.set_env_field` / `unset_env_field` verbs;
- never echo values in logs; the audit ledger records the key
  name + action, never the value.

**Why it waits.** Power users edit `.env` by hand without much
friction. Promote when somebody reports the manual edit + daemon
restart loop as a real operational pain. No mobile counterpart
either way — entering secrets on a phone keyboard is hostile UX.

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

**Rejected integrations / providers:**

- **Vendor subscription OAuth** (reverse-engineering an official
  first-party CLI's auth flow to bind a paid subscription to alpi).
  ToS violation, see "Principles".
- **J. camoufox** (+230 MB Firefox) for anti-bot. Humanised
  Playwright covers the real detection surface without the weight.
- **WhatsApp gateway.** Meta Business API requires company
  verification + is expensive; `whatsapp-web.js` / Baileys are
  reverse-engineered with frequent bans, and the attack surface
  is catastrophic (a compromised bot leaks every chat). Not worth
  shipping for a personal agent.
- **Smart-home orchestration.** Owning device protocols (Hue,
  Xiaomi, Zigbee, Matter, vendor APIs) would pull Alpi into
  hardware-specific maintenance and physical-world safety policy,
  and the surface depends almost entirely on which hardware each
  user happens to own. Users who need it can expose Home Assistant
  through an MCP server or a local profile skill — Alpi consumes
  that without owning a single device protocol. Core Alpi stays
  focused on profiles, workgroups, host-plane clients, memory, and
  operator tooling.
- **Discord gateway.** Bot tokens grant full server access — same
  blast-radius profile as Telegram with no added value, since
  Telegram covers the "messaging gateway" role already.
- **Slack gateway.** Enterprise-focused, per-workspace tokens with
  broad scopes, operationally heavy. No real personal-agent use
  case.
- **XMPP gateway.** Matrix covers the same federated + E2EE
  audience with better tooling and active community. XMPP's
  user base today (`conversations.im`) overlaps heavily with
  Matrix users — same population, fewer obstacles.
- **LangGraph / CrewAI / AutoGen as a core dependency.** Third-party
  agent-orchestration frameworks are out of core scope. They overlap
  with `alpi/engine.py` (the LLM loop + tool dispatch) but bring a
  graph/state-machine mental model that doesn't match Alpi's
  "profile = personality + memory + tools, peers talk over ALP"
  shape. They also drag in heavy dependency trees and push users
  toward hosted observability (LangSmith and similar) that contradicts
  the "zero server, zero telemetry" stance. Users who already run
  one of these stacks should expose their workflow as an **MCP
  server** that Alpi consumes, or wrap it in a **scripted skill**.
  ALP stays the protocol for sovereign profile-to-profile
  collaboration; MCP stays the interop layer for external runtimes.
- **Image generation as a core tool.** Alpi can consume image generators
  through MCP or user-owned skills when somebody needs them. A built-in
  provider surface would pull the product toward a creative-tool platform
  and add provider/cost policy without strengthening the personal-agent core.
- **Mixture-of-agents as a core runtime.** Spawning multiple models on one
  prompt and synthesising the answer is an expensive research pattern, not
  a daily personal-agent primitive. Workgroups already cover explicit
  multi-profile collaboration when it has a real shape.
- **RL / fine-tuning hooks.** Dataset collection and model training are
  research infrastructure, not an Alpi product surface. Local-first memory
  and retrieval remain the path for personalisation.
- **Cost telemetry split per skill / tool.** The per-profile daily ledger is
  enough while skills are user-owned and sparse. Splitting cost by every
  tool adds schema and UI weight before there is a real catalog or budget
  problem to solve.

**Rejected architecture attempts:**

- **Go + Bubbletea rewrite.** Rejected.
- **rich.Live + prompt_toolkit inline UI.** Worked but had ceiling
  (no modals, suspend races). Replaced by Textual.
- **Full Textual app with sidebar + modals + fullscreen chrome**
  (first attempt). Rolled back as too heavy. Current is
  mother.py-style minimal.
- **SQLite state.db.** Plain JSON files scan fast for <1000
  sessions.
- **Conversation export format (JSON canonical).** Originally
  scoped as "needed by the desktop app to render sessions".
  The premise was wrong: sessions already serialise to JSON in
  `~/.alpi/profiles/<name>/sessions/{id}.json` (`session.py:save`).
  The desktop / mobile client now reads them via the host control
  plane (`host.session.read`, `host.sessions.list`) — the contract
  is the JSON-RPC verb shape, not a separate export schema. The
  desktop in this monorepo acts as the regression test. Formalise
  a versioned export schema only when a *second* consumer
  (marketplace, external integration) ships and needs one.
- **Pending-approval gate for skills.** Tried in v0.1, removed in
  v0.2. Friction outweighed benefit; security scanner is the gate.
- **Workspace wall on file tools.** Removed in v0.2. Without OS
  sandbox active, the wall was friction without isolation
  (terminal escaped it in one tool call). File tools now follow
  terminal's posture: shared sensitive-path denylist, no workspace
  restriction.
- **Pending-approval files** (`pending_skills.md`,
  `pending_personality.md`). Replaced inline.
- **Regex-gating shell commands** to enforce sandbox. Too many
  false positives (legitimate `..`, env-var expansion, command
  substitution). Real enforcement needs OS-level sandbox.
- **`.bak` sibling on every `write_file`.** Tried it, rejected —
  clutters every directory alpi writes in. Kept only on memory
  files where it pays off.
- **`alpi setup → Identity` wizard for editing AGENT.md.**
  Rejected after consideration. The `memory` tool already mutates
  `AGENT.md` from inside chat, and the LLM captures nuance
  ("less formal but not jokey; respect my code-switching") that a
  form can't.
- **Default skills bundle (AO, v0.3).** Resolved as "ship nothing
  by default". Skills are entirely user-owned; runtime capabilities
  (e.g. ``alpi_knowledge``) live as first-class tools, not skills.
  Community marketplace ideas live in Future versions.
- **`alpi run "<prompt>"` as a separate command.** Already
  covered by `alpi chat --once "<prompt>"`. Adding a second
  alias is bloat without value.
- **Profile starter packs (`--template coding|home|research`).**
  Pushes toward swiss-army-knife thinking — alpi's premise is
  that each user shapes their own profile. Templates live in
  the docs as examples, not in the binary as commands.
- **TUI accessibility pass.** Deferred indefinitely. The
  desktop app is the right surface for
  screen-reader / large-text / high-contrast use cases —
  modern accessibility APIs are richer there than in any
  terminal. The TUI keeps the current minimal posture.

**Rejected behaviours:**

- **UX.3 — gateway "open in Alpi" nudges.** Appending an "open in Alpi"
  pointer to gateway replies (for file/approval/workgroup flows) would
  incentivise gateway usage; we don't want to. Gateways stay text-first and
  are not a surface we grow. Discarded.
- **Auto-reflect on Ctrl+C.** Dangerous.
- **Post-session `/reflect` loop.** Tried it — removed because the TUI
  implementation was broken and inline memory writes are cleaner.
  Replaced by hardened system prompt + tool-description rules for
  inline `memory(add)` + `skill(create)`.

**Rejected dependencies:**

- **duckduckgo-search.** Deprecated → migrated to `ddgs`.
