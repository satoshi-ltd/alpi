# Roadmap

Open work for alpi. Shipped work lives in
[CHANGELOG.md](../CHANGELOG.md) — this file never repeats it. For
technical reference of what currently ships, see
[ARCHITECTURE.md](ARCHITECTURE.md).

Audience: the creator ([@soyjavi](https://github.com/soyjavi)) and
any future contributor reading the repo cold.

Legend: 🔵 backlog · 🟡 next up · ⏸ blocked · 🔴 gate.

---

## v0.7 cycle (active)

**Theme: owned-client UX + self-improving library + prompt reliability
+ operator surfaces.**
v0.6 makes the system observable and reliable. v0.7 uses that evidence
to improve the agent's long-term assets, move richer interaction
patterns into Alpi-owned clients rather than gateways, and tighten the
operator surfaces (device scope, mobile parity, daemon restart) that
sovereignty depends on.

### Owned client experience

| ID | Item | Status |
|---|---|---|
| UX.2 | Rich tool cards parity — desktop/mobile render approvals, file mutations, memory promotions, and workgroup events as first-class cards. | 🔵 |
| UX.3 | Gateway migration nudges — gateway replies can point users back to Alpi clients for flows that need approvals, files, workgroups, or rich UI. | 🔵 |

### Self-improving skills

| ID | Item | Status |
|---|---|---|
| AC.2 | Curator apply flow — after preview, archive stale skills, add `absorbed_into:` metadata, and move detail into umbrella skill `references/` when consolidation is accepted. | 🔵 |

### Cost and model behavior

| ID | Item | Status |
|---|---|---|
| BD | Model-family conditional prompt guidance — inject heavier tool-use/verification guidance only for model families that real logs show need it. | 🔵 |

### Protocol

| ID | Item | Status |
|---|---|---|
| ALP.3.J | Workgroup state ledger — hub-served task state (no client-side refold/decrypt); `wg.blocked` card rendering. | 🔵 |
| ALP.3.K | Rekey edge cases — leave/kick/rekey while a task is open (hub-side key history, or auto-close / re-pin). | 🔵 |
| ALP.3+ | Multi-task workgroups — opt-in `multitask: true`, letter-prefixed task IDs, per-task roster/dispatch/budget. **Deferred**: targeted tasks + pipeline continuation cover sequential per-project pipelines; revisit only if the persistent workgroups (`template`/`quality`/`brand-library`) prove real parallelism. | 🔵 |

### UX.2 / UX.3. Owned client experience

Desktop and mobile are the primary product surfaces. Gateways stay
text-first by design. v0.7 should make the owned clients materially
better than any chat bridge:

- approvals, file mutations, memory promotions, and workgroup events
  become stable cards with state, actions, and replay;
- gateway replies can include a lightweight "open in Alpi" pointer when
  the flow needs rich UI.

**Non-goals.** No Telegram/Discord/Slack button framework, no
gateway-specific onboarding, no attempt to turn chat apps into Alpi
clients. Gateways remain useful because they are ubiquitous and
automation-friendly, but they are not where new product UX goes.

### AC.2. Skill curator apply flow

AC.1 (shipped) writes a recommendations report. AC.2 closes the loop by
applying those recommendations after explicit preview:

- archive stale skills through the existing `.archive/` path;
- mark consolidating archives with `absorbed_into: <skill>`;
- preserve original bodies in `references/`;
- never mutate pinned skills.

The curator reconciles its LLM summary against the actual tool-call log
of the curator run. If the summary says a skill was absorbed but no tool
call did that, the report marks a mismatch instead of trusting prose.

### BD. Model-family conditional prompt guidance

Different model families need different operational guidance. BD adds a
small routing table so heavy enforcement blocks are injected only for
families that real logs show need them. Other families keep the shorter
baseline prompt.

Promotion condition: `alpi digest` or LLM test traces show repeated,
family-specific failures such as under-calling tools, skipping
verification, or closing turns early despite open commitments.

### ALP.3+ — Multi-task workgroups (deferred)

> **Deferred to future (out of v0.7).** Targeted tasks + pipeline
> continuation give sequential per-project workflows everything
> they need without multitask's extra state, partial-closure, quorum, and
> UI edge cases. Multitask only earns its complexity if the *persistent*
> workgroups (`template`, `quality`, `brand-library`) show real, sustained
> parallelism. Until then this stays backlog.

v0.3 ships strict single-task: a new `#task` preempts the open one
(`"preempted by …"`), which forces convergence and keeps context narrow.
ALP.3+ would lift it via `multitask: true` + letter-prefixed IDs (`#task A …`,
`#done A: …`), each task carrying its own active state, per-member
`last_responded_seq`, dispatch gating, and budget headroom. Single-task stays
the default and fits per-project pipelines (one owner per phase via targeted
tasks); multitask earns its complexity — per-task quorum filters, N-thread UI,
per-task budget accounting — only when the persistent workgroups (`template`,
`quality`, `brand-library`) show sustained parallelism.

### ALP.3.J — Workgroup state ledger

Task state is re-derived client-side by folding the decrypted transcript on
every `pull` — no canonical ledger, so inspection means decrypt-and-fold by
hand. The hub already recomputes task state for the closure-quorum check;
expose it (via `workgroup.show` / `pull`) so clients and operators don't each
refold. Includes `wg.blocked` card rendering in the clients.

### ALP.3.K — Rekey edge cases

A `leave` / `kick` mid-task rotates the group key; the open `#task` post stays
under the old version, so the hub (holding only the new key) blanks it on fold
(`_post_as_hub`) → the task drops from the hub's ledger and can't be closed
hub-side. Remaining members keep the old key and still see it — a hub-side
blind spot, not data loss. Fix: persist a hub-side key history so the hub folds
the full transcript, or auto-close / re-pin active tasks on rekey.

**Explicitly not in scope.** Author-declared post cost (the honour-system
budget gate) and hub-anchored availability (cold workgroup when the hub
is offline) are deliberate design choices for a closed, trusted,
one-org-per-machine deployment — not defects. Single-task → multi-task
is tracked above as ALP.3+.

## v0.8 cycle (planned)

**Theme: multimodal input + RAG ingestion.**
v0.7 sharpens owned clients and operator surfaces. v0.8 opens the
agent to non-text content (PDFs, images) and closes the
durable-knowledge loop ("learn this file") so workspace + RAG become
the agent's long-term memory of documents.

### Multimodal + ingestion

| ID | Item | Status |
|---|---|---|
| MM.1 | Multimodal chat input — `host.chat.send` accepts attachments; TUI/desktop/mobile let users attach images and PDFs; engine forwards them through the model's multimodal payload. | 🔵 |
| RAG.2 | Document ingestion — "learn this file" flow drops the attachment into `workspace/`, reindexes the per-profile RAG store, and exposes it through `search_workspace` like any other workspace content. | 🔵 |

### MM.1. Multimodal chat input

The chat protocol is text-only today: `host.chat.send` carries a `text`
field, and the model never sees binary content unless a tool (e.g.
`read_file`) extracts it as text first. That works for code, logs and
markdown. It breaks for the two most common operator inputs that
**aren't** text: PDF documents and screenshots / photos.

litellm already speaks vision against most modern providers (OpenAI 4o,
Claude 3.5+, Gemini, OpenRouter vision routes). The missing pieces are
wire format and surfaces:

- `host.chat.send` accepts `attachments: [{path, mime, …}]`. The daemon
  reads the bytes and embeds images as base64 in the multimodal
  payload. Text-bearing PDFs go through `pypdf` (already in deps);
  scanned PDFs get rendered to images via `pypdfium2` (also in deps)
  and treated as image attachments so the model's vision can read them
  — no separate OCR step.
- TUI gets a `/attach <path>` slash command; desktop gets a paperclip
  in the composer; mobile reuses the OS file/photo picker.
- Engine logs attachments in the session JSON so resume/replay
  reconstructs the full multimodal turn, not just the text.

**Non-goals.** No image generation (that's `N` long-term). No OCR tool
exposed to the agent — scanned PDFs become rendered pages routed
through the same vision path as any other image. No video or audio
attachments — voice has its own path via gateway audio + STT.

### RAG.2. Document ingestion ("learn this file")

MM.1 ships per-turn multimodal — the file lives only in the message it
arrived with. RAG.2 closes the loop for the durable case: "remember
this document forever, treat it as a knowledge source."

Flow:

1. user drops the file in chat with an intent ("learn this", or an
   explicit button in desktop/mobile);
2. the daemon moves the file into `workspace/<filename>` (the agent's
   long-term storage root, already present);
3. reindexes the per-profile `rag/store.sqlite` via the existing
   `core/embed.py` + sqlite-vec primitives;
4. the agent reaches it through `search_workspace`, the same surface as
   every other workspace document.

**Why funnel through `workspace/`.** Single storage model: the agent's
long-term knowledge lives in `workspace/`, and the RAG index is a
derived view of it. No second store, no orphan vectors that don't map
back to a file, backups already cover `workspace/` in the per-profile
snapshot.

**Non-goals.** No auto-ingestion of every attached file
(predictability matters; users decide what becomes permanent). No
external corpus crawl ("ingest this URL deep-walk"). No cross-profile
shared RAG — that's an org concern (`ORG.2`).

## Future releases

Items worth doing, but not part of the next two cycles.

| ID | Item | Status |
|---|---|---|
| TERM.2 | Docker / SSH terminal backends — isolated or remote command execution for unattended profiles once local sandboxing is no longer enough. | 🔵 |
| ALP.5 | Blob transfer — `link.put_blob` / `link.get_blob`, content-addressed, chunked AEAD. Depends on real workgroup usage to justify the protocol complexity. | 🔵 |
| ORG.2.B/C | Workspace overlay (`cfg.workspace_path` as list) + first-class runtime org entity (`~/.alpi/orgs/<id>/`) with roles, event fan-out, and shared RAG. Deferred — see entry below. | ⏸ |

### TERM.2. Docker / SSH terminal backends

Local terminal execution plus optional OS sandboxing is enough for the
current product. Docker and SSH become worthwhile when unattended
profiles need stronger isolation, reproducibility, or a remote machine
that the agent can damage without touching its own code or the user's
main workstation.

The first implementation should be conservative: one configured backend
per profile, no provider zoo, no cloud sandbox abstraction, and no
automatic migration of local files.

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
| Signal | Signal gateway via signal-cli | Strong privacy fit, but new gateways are out of scope now that Alpi-owned clients are the primary mobile surface |
| AY | Skills marketplace — federated, signed, never centralised | Presupposes an active author community + adoption for discovery to matter |
| SK.2 | Safe skill import (`alpi skill import <dir\|zip>` — preview, scan, install) | Pulls toward marketplace/import-ecosystem mental model without a concrete user pull. Promote when somebody actually needs to migrate a batch of skills from another stack. |
| BF-8 | Skill versioning / install-update flows | Depends on SK.2 and imported-source metadata. Keep it out while import itself is deferred. |
| AI (2) | Memory v2 — TUI panel (collapsible, edit-in-place, "forget this") | UI weight for niche audience (power users with much memory); item 1 covers the substantive part |
| AI (3) | Entity memory — structured SQLite store (`entities`/`relations`/`observations`) replacing the markdown memory model, with selective injection per turn instead of full-blob system prompt | Markdown memory hasn't demonstrably broken yet for real users; AI(1) is a quality pass on the existing model. Promote when a user reports `MEMORY.md` is large enough that prompt size / cost becomes a real bottleneck. BA's shared `store` primitive (v0.5) is designed so the migration is incremental when promoted. |
| AJ | Browser realism — Cloudflare / captcha / fingerprint depth | Cat-and-mouse perpetuo; without concrete failing use case, scope can't close |
| AQ | Continuous voice mode (push-to-talk, hotword loops) | Niche unless voice becomes a real surface for users |
| Webhook | Inbound HTTP triggers (HMAC-signed) | Automation bridge, not product UX; needs repeated real demand before adding another inbound surface |
| Cost telemetry | Cost split per-skill / per-tool | Only pays off with many skills + notably different costs; today neither holds |
| BG re-audit | LiteLLM quarterly review — bump pin, run LLM probe, swap if better alternative emerges | Standing maintenance task; cadence + procedure documented in `OPERATIONS.md → Dependencies` |
| Matrix E2EE | Olm/Megolm sessions, encryption store, SAS device verification, encrypted-room send/read tests | MVP intentionally unencrypted; promote when an external user runs the bot against a non-self-hosted homeserver |
| CM.4 | Semantic recall over past sessions — opt-in vector retrieval when lexical `session_search` starts missing real queries | Lexical layer hasn't visibly failed yet; promote on the first "I know we discussed X, where is it?" miss |
| ALP.6 | Workgroup search — semantic search over workgroup transcripts | Depends on CM.4 being stable; promotes with it, not before |
| TTS.1 | Local TTS engine + daemon-served voice — single host-served voice catalog, deprecate desktop-local synthesis | Current cloud TTS path works; promote alongside `AQ` (continuous voice) or when desktop/daemon catalog drift becomes a real operator burden |
| UX.6 | Desktop `.env` manager — per-profile environment editor (mask/reveal/audit) for keys other than provider keys | Provider keys already have a first-class flow; promote when editing other `.env` entries by hand becomes a real friction reported by users |

Promotion criteria: real user demand, or concrete blocker for
a v0.x feature that depends on it. None of these items
graduate "because we feel like it".

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
skills shippable through user-controlled imports (see CM.2 above),
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

### Cost telemetry per-skill / per-tool

The daily ledger today is per-day per-profile. Splitting by
skill / tool would surface "which skill costs me $14/mo, which
tool costs $2/turn" — input for pruning.

**Why it waits.** Only pays off with many skills + notably
different costs per skill — neither holds today (skills are
entirely user-owned, with a handful at most per profile). The
dimension explosion is dead weight until the catalog grows. May
be discarded entirely if no demand emerges by v0.6.

### CM.4. Semantic recall over past sessions

Lexical `session_search` stays the first layer: cheap, explicit,
easy to reason about. Semantic recall becomes worthwhile when
session volume grows and users ask "when did we discuss X?" but
cannot find it.

When promoted, reuse the existing local embedding / store
primitives. The first shape is opt-in indexing plus an explicit
recall/search tool. Automatic injection only comes later if
manual retrieval proves valuable.

**Why it waits.** The promotion signal — lexical search visibly
failing on real queries — has not materialised. Promote on the
first concrete "I know we discussed X, where is it?" miss, not
on speculative scale.

### ALP.6. Workgroup search

`workgroup.search(workgroup_id, query)` returns top matching
posts from a workgroup transcript. The hub indexes its local
transcript; members search through existing host/workgroup
surfaces rather than receiving a new protocol family.

**Why it waits.** Depends on `CM.4`'s retrieval layer being
stable. If semantic session recall is not reliable enough,
workgroup search waits — they promote together.

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

## Long-term / stretch

### N. Image generation

`generate_image(prompt, style)` using the active vision model or a
dedicated endpoint (DALL-E, SD). Useful for "make me a quick
logo" prompts. Low priority unless a concrete use case appears.

### Σ.1. Mixture-of-agents (stretch goal)

Spawn multiple LLMs on the same prompt, aggregate answers with a
final synthesizer. Use case: hard decisions where one model is weak
and you want "wisdom of crowds" at 3× cost.

Not planned — tracked here because it's a known technique and
might become useful if we hit a ceiling on single-model research
quality.

### Σ.2. RL training / fine-tuning hooks (stretch goal)

If we ever want to fine-tune a smaller local model on real conversation
patterns, the dataset-collection scaffold would live here.

Not planned. Research-grade, irrelevant for everyday personal use.

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

- **Auto-reflect on Ctrl+C.** Dangerous.
- **Post-session `/reflect` loop.** Tried it — removed because the TUI
  implementation was broken and inline memory writes are cleaner.
  Replaced by hardened system prompt + tool-description rules for
  inline `memory(add)` + `skill(create)`.

**Rejected dependencies:**

- **duckduckgo-search.** Deprecated → migrated to `ddgs`.
