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
For the product framing behind this cycle, see
[Alpi vs LangChain for Agentic Organizations](ALPI_VS_LANGCHAIN.md).

| ID | Item | Status |
|---|---|---|
| SEC.1 | Context injection hardening — shared scanner for recalled memory, learned documents, workgroup transcript snippets, and tool results before they enter model context. | 🟡 |
| FS.1 | Credential file denylist audit — defense-in-depth read/write blocks for provider keys, profile control files, `.env*`, SSH/cloud creds, and project-local secret stores. | 🔵 |
| AUDIT.1 | `alpi audit` — local dependency / config / security posture scan: stale deps, known CVEs, exposed binds, risky permissions, and missing hardening warnings. | 🔵 |

v0.9 should stay narrow: improve observability and failure handling on
surfaces Alpi already owns. No new execution backend, no worker-lane
marketplace, no cloud sandbox abstraction, and no automatic file migration.
`SEC.1` is next — scanning recalled content before it reaches the model;
`FS.1` + `AUDIT.1` then close the safety posture.

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

## Future releases

Items worth doing, but not part of the next two cycles.

| ID | Item | Status |
|---|---|---|
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
| LangGraph / CrewAI / AutoGen as core | Graph frameworks do not match Alpi's profile/workgroup runtime and pull toward hosted observability. See `ALPI_VS_LANGCHAIN.md`. |
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
