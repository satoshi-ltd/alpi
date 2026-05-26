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

**Theme: owned-client UX + self-improving library + recall/cost depth.**
v0.6 makes the system observable and reliable. v0.7 uses that evidence
to improve the agent's long-term assets and to move richer interaction
patterns into Alpi-owned clients rather than gateways.

### Owned client experience

| ID | Item | Status |
|---|---|---|
| UX.1 | Structured clarification — the agent asks closed questions that desktop/mobile render as native choices; gateways degrade to numbered text. | 🔵 |
| UX.2 | Rich tool cards parity — desktop/mobile render approvals, file mutations, memory promotions, and workgroup events as first-class cards. | 🔵 |
| UX.3 | Gateway migration nudges — gateway replies can point users back to Alpi clients for flows that need approvals, files, workgroups, or rich UI. | 🔵 |

### Self-improving skills

| ID | Item | Status |
|---|---|---|
| AC.1 | Skill curator recommendations — use the v0.5.9 telemetry to flag stale, duplicate, overly narrow, or umbrella-candidate skills. Produces reports and manual apply plans; no silent deletes. | 🔵 |
| AC.2 | Curator apply flow — after preview, archive stale skills, add `absorbed_into:` metadata, and move detail into umbrella skill `references/` when consolidation is accepted. | 🔵 |

### Recall and workgroup search

| ID | Item | Status |
|---|---|---|
| CM.4 | Semantic recall over past sessions — opt-in vector/semantic retrieval over session history when lexical `session_search` starts missing real queries. | 🔵 |
| ALP.6 | Workgroup search — semantic search over workgroup transcripts via the local RAG primitives, exposed through workgroup/host surfaces after CM.4 proves stable. | 🔵 |
| ORG.1 | Organization workspace convention — document and scaffold the "hub profile owns the shared workspace" pattern before adding shared-filesystem runtime. | 🔵 |

### Cost and model behavior

| ID | Item | Status |
|---|---|---|
| CL.1 | Prompt caching across providers — stable-prefix audit, marker-required provider support, optional cache-key hints for auto-cache providers, and measurement in `alpi digest`. | 🟡 |
| BD | Model-family conditional prompt guidance — inject heavier tool-use/verification guidance only for model families that real logs show need it. | 🔵 |

### Voice

| ID | Item | Status |
|---|---|---|
| TTS.1 | Local TTS engine + daemon-served voice — choose a local/default engine, move synthesis behind the daemon, and collapse desktop/TUI/gateway voice catalogs into one host-served catalog. | 🔵 |

### UX.1 / UX.2 / UX.3. Owned client experience

Desktop and mobile are the primary product surfaces. Gateways stay
text-first by design. v0.7 should make the owned clients materially
better than any chat bridge:

- structured clarifications render as native choices instead of asking
  the user to type an option number;
- approvals, file mutations, memory promotions, and workgroup events
  become stable cards with state, actions, and replay;
- gateway replies can include a lightweight "open in Alpi" pointer when
  the flow needs rich UI.

**Non-goals.** No Telegram/Discord/Slack button framework, no
gateway-specific onboarding, no attempt to turn chat apps into Alpi
clients. Gateways remain useful because they are ubiquitous and
automation-friendly, but they are not where new product UX goes.

### AC.1 / AC.2. Skill curator

The curator is post-hoc, not in-loop. It runs after real skill usage has
accumulated, reads `skills/.usage.json`, and writes an auditable report
under `logs/curator/<timestamp>/`.

The first phase only recommends:

- stale skills unused for a configurable evidence window;
- prefix/name clusters such as `debug-parser-*`;
- narrow session-specific skills that should become `references/` under
  a broader umbrella;
- imported skills with newer upstream revisions.

The second phase applies only after preview:

- archive stale skills through the existing `.archive/` path;
- mark consolidating archives with `absorbed_into: <skill>`;
- preserve original bodies in `references/`;
- never mutate pinned skills.

The curator reconciles its LLM summary against the actual tool-call log
of the curator run. If the summary says a skill was absorbed but no tool
call did that, the report marks a mismatch instead of trusting prose.

### CM.4. Semantic recall over past sessions

Lexical `session_search` stays the first layer: cheap, explicit, easy to
reason about. Semantic recall becomes worthwhile when session volume
grows and users ask "when did we discuss X?" but cannot find it.

When promoted, reuse the existing local embedding/store primitives. The
first shape is opt-in indexing plus an explicit recall/search tool.
Automatic injection only comes later if manual retrieval proves valuable.

### ALP.6. Workgroup search

`workgroup.search(workgroup_id, query)` returns top matching posts from
a workgroup transcript. The hub indexes its local transcript; members
search through existing host/workgroup surfaces rather than receiving a
new protocol family.

This depends on CM.4's retrieval layer being stable. If semantic session
recall is not reliable enough, workgroup search waits.

### ORG.1. Organization workspace convention

The organization scaffold exists, but there is no first-class runtime
organization or shared filesystem. v0.7 documents the cheapest useful
pattern: designate one hub/secretary profile as the organization
workspace owner. Other agents reach it via existing `@hub` / `link.ask`
flows, and workgroup outputs land there by convention.

This is intentionally not the workspace overlay or first-class org
entity. Those designs wait for real user demand.

### CL.1. Prompt caching across providers

Cached input is the highest-leverage cost optimization for tool-heavy
turns, but it depends on stable prompt prefixes. v0.7 scopes it in this
order:

1. audit `Engine` and compaction for non-deterministic early-message
   mutation;
2. add marker support for providers that require explicit cache control;
3. add optional cache-key hints for auto-cache providers where useful;
4. measure cache savings in `alpi digest`.

Explicit cache APIs are adopted only where implicit/marker caching shows
measurable miss-rate problems.

### BD. Model-family conditional prompt guidance

Different model families need different operational guidance. BD adds a
small routing table so heavy enforcement blocks are injected only for
families that real logs show need them. Other families keep the shorter
baseline prompt.

Promotion condition: `alpi digest` or LLM test traces show repeated,
family-specific failures such as under-calling tools, skipping
verification, or closing turns early despite open commitments.

### TTS.1. Local TTS engine + daemon-served voice

Today speech synthesis is duplicated: daemon-side TTS and desktop-side
TTS have separate catalogs and caches. v0.7 chooses one daemon-owned
voice path:

1. benchmark local candidates on quality, disk size, latency, license,
   and locale coverage;
2. expose daemon-hosted synthesis and voice listing over the host plane;
3. deprecate desktop-local synthesis;
4. keep cloud TTS as an explicit opt-in provider if useful.

This is the prerequisite for any future continuous voice mode.

## Future releases

Items worth doing, but not part of the next two cycles.

| ID | Item | Status |
|---|---|---|
| TERM.2 | Docker / SSH terminal backends — isolated or remote command execution for unattended profiles once local sandboxing is no longer enough. | 🔵 |
| ALP.5 | Blob transfer — `link.put_blob` / `link.get_blob`, content-addressed, chunked AEAD. Depends on real workgroup usage to justify the protocol complexity. | 🔵 |
| ORG.2 | Organization workspace overlay / first-class org entity — shared filesystem roots, roles, and shared RAG once convention-only org workspaces prove insufficient. | 🔵 |

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

### ORG.2. Organization workspace overlay / first-class org entity

If ORG.1's convention-only pattern becomes insufficient, two heavier
designs remain available:

1. **Workspace overlay.** `cfg.workspace_path` becomes a list:
   `[profile_workspace, org_workspace]`. File tools read both and write
   to the profile root by default, with an explicit shared scope.
2. **First-class org entity.** `~/.alpi/orgs/<id>/workspace/` with
   member profiles, roles, event fan-out, and a shared RAG index.

Both add a real trust model, so they stay out of v0.7 unless users hit a
specific organization-sharing wall.

---

## Future versions — listening first

Items that may or may not have legs. We deliberately don't
commit to a cycle for them — we'd rather hear from real alpi
users which ones they actually need before building. Each is
already analysed; the "why now?" question is the open one.

| ID | Item | Reason it waits |
|---|---|---|
| ALP.3+ | Multi-task workgroups (`multitask: true`, letter-prefixed task IDs) | Single-task model has not yet proven insufficient |
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

Promotion criteria: real user demand, or concrete blocker for
a v0.x feature that depends on it. None of these items
graduate "because we feel like it".

### ALP.3+. Multi-task workgroups

v0.3 ships a strict single-task model: posting a new `#task`
while one is open auto-closes the previous with `"preempted by
…"`. The constraint is a feature — it forces convergence and
keeps the agent context narrow. ALP.3+ would lift it for
workgroups that **need** parallel streams.

Workgroups would opt in with `multitask: true` in `meta.yaml`.
Markers extend with letter-prefixed IDs: `#task A research the
peptide`, `#task B audit the contract`, closures match prefix
(`#done A: shortlist of 5`). Each task carries its own active
state, its own `last_responded_seq` per member, its own
dispatch gating.

**Why it waits.** The single-task model has not yet proven
insufficient in real use. Multi-task adds real complexity
(per-task roster filters, per-task budget headroom, UI for
showing N concurrent threads). Promote when a real workgroup
outgrows single-task, not before.

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
