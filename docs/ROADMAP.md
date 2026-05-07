# Roadmap

Open work for alpi. Shipped work lives in
[CHANGELOG.md](../CHANGELOG.md) — this file never repeats it. For
technical reference of what currently ships, see
[ARCHITECTURE.md](ARCHITECTURE.md).

Audience: the creator ([@soyjavi](https://github.com/soyjavi)) and
any future contributor reading the repo cold.

Legend: 🔵 backlog · 🟡 next up · ⏸ blocked · 🔴 gate.

---

## v0.5 cycle (active)

**Theme: owned device access — closing the loop.** v0.4 shipped the
secure local-device foundation and v0.5 completes the remote-access
story: desktop multi-host connections shipped (desktop-v0.2.2/v0.2.3),
mobile uses the same host-plane pairing contract, and the agent's
self-improvement primitives (memory quality, rich text) reach a usable
baseline. v0.6 builds on that base with a self-improving skill library
and the live-access infrastructure the product can now justify.

This is the cycle where gateways stop being the main mobile story.
Telegram, IMAP, Gmail, and Matrix stay useful, but the project should
not depend on third-party chat apps as the primary way to reach a
personal agent.

### Device + live access

| ID | Item | Status |
|---|---|---|
| AX-desktop-remote | Desktop multi-host host-plane connections — switch between local Unix socket and paired remote daemons over WebSocket/Tailscale using per-device tokens. | ✅ desktop-v0.2.2 / v0.2.3 |
| AX-mobile | Mobile companion (iOS / Android) — full chat, status, peers, and workgroups surface from the user's own profile. Daemon side shipped in v0.4.1 (host plane on WebSocket + per-device pairing tokens, see CHANGELOG). Mobile preview exists; desktop remains the reference surface. | 🟡 |

### Skills + bundled

| ID | Item | Status |
|---|---|---|
| `@alpi/home` | Second bundled skill (after `@alpi/knowledge` in v0.3). Full home orchestration behind a single voice/text interface: Home Assistant first, with optional Hue, Xiaomi, Alexa / Google Home integrations layered in. | 🔵 |

### Self-improvement loop

| ID | Item | Status |
|---|---|---|
| AI (1) | Memory v2 — quality, injection scanning, and post-turn background review. Dedup threshold, confidence field, prompt-injection scan on writes, and a lightweight background agent that reviews the conversation after every N turns and writes memory without blocking the active session. Also lands per-tool conditional guidance (the surface that needs an enabled-tools concept). | 🟡 |
| AT | Skill safety primitives — auto-archive instead of destructive delete (skills move to `skills/.archive/`, recoverable), `.bak` snapshot before every `edit`/`patch` (mirrors the memory `.bak` pattern), `pinned: true` frontmatter flag that protects a skill from auto-archive and any future curator pass, `absorbed_into:` metadata recorded on consolidating deletes. Memory entries get the same `pinned` flag. | 🟡 |

### UX polish

| ID | Item | Status |
|---|---|---|
| BB | Enhanced rich text in UI — extend baseline link renderer to lists, code blocks, tables, headings | 🔵 |

### AX-desktop-remote. Desktop multi-host host-plane connections — ✅ shipped

Shipped in desktop-v0.2.2 (connection store, transport abstraction, switcher UI,
auth-failed revocation) and desktop-v0.2.3 (per-connection status tracking,
offline banner, probe architecture, thread exhaustion guard). See
[desktop/CHANGELOG.md](../desktop/CHANGELOG.md) for details.

### AX-mobile. Mobile companion (iOS / Android)

After **desktop-v0.1.0** validated the visual UI, mobile is the
next surface. Same product contract as desktop remote mode: a
host-plane client paired to a user's own daemon over WebSocket with a
per-device token. More friction lives in App Store signing, iOS
background restrictions, and distribution.

**Why a companion, not a full port.** A mobile alpi running its
own LLM + tools doubles the security surface and the
maintenance cost without adding capability. The companion controls an
owned daemon through `host.*`; ALP remains the peer-to-peer plane for
alpi-to-alpi links and workgroups.

**Surfaces this could replace or extend:**
- Telegram / Matrix gateways — keep working, but optional once the
  companion is real.
- `/peers`, `/budget`, `/memory` panels exposed read-only on
  the go.
- Workgroups use the desktop view as the reference surface:
  transcript, roster, active task, post composer, pause/resume state,
  and task markers.

**Workgroup scope.** Desktop workgroups are already operational, so
mobile does not invent a separate viewer. It ports the same product
surface into the companion:

- transcript with speaker identity, task markers, and working/done
  state;
- roster + peer status;
- create/join/manage where the mobile UX can do it safely;
- post composer for active members;
- notifications for mentions, new `#task`, and task completion.

Mobile ships full parity with desktop. Read-only fallbacks are only
acceptable as last-mile implementation cuts (e.g., a specific iOS
background limitation that blocks one verb), never as the v0.5 target.

**Open questions before scope locks:**
- Tauri vs. native (SwiftUI / Kotlin) — Tauri wins on desktop
  but mobile is more contested; native may be better for iOS
  background + push notifications.
- iOS background restrictions — mobile should initiate host-plane
  connections to the user's daemon rather than accepting inbound
  connections.
- Distribution — TestFlight + Play Store internal track at
  first.

### `@alpi/home`. Second bundled skill — full home orchestration

After `@alpi/knowledge` (v0.3) validated the bundled-skills pattern,
`@alpi/home` is the second one. One coherent voice/text interface to the
user's home, regardless of which underlying ecosystem(s) they run. This is
the full surface, not a thin slice.

**Surface.** A skill that orchestrates one or more of:
- **Home Assistant** (primary) — sensors, lights, scenes, occupancy, switches.
- **Philips Hue** — directly via the Hue Bridge HTTP API.
- **Xiaomi Mi Home** — via `python-miio`.
- **Google Home / Alexa** — read-only "is anyone home" queries via their
  official device APIs.

The user enables only the integrations they have. Each is an optional
`requires:` in the frontmatter; the skill degrades gracefully when an
integration isn't configured.

**Per-skill SQLite.** Caches device state + last-seen timestamps so the agent
doesn't re-poll every turn ("is the kitchen light on?" answers from cache;
"turn it on" pushes through).

**Configuration.** Per-profile `.env` for tokens (`HA_URL`, `HA_TOKEN`,
`HUE_BRIDGE_IP`, `XIAOMI_TOKEN`, …); allowlist of entity domains in
`config.yaml` so the skill can only touch what the user explicitly opted in.

LOC estimate: ~400 (HA covers ~250, Hue + Xiaomi ~50 each, Google/Alexa ~50 stub).

### AI (1). Memory v2 — quality + injection scanning + background review

Three complementary improvements to the memory system.

**Quality pass.** Server-side only; the TUI panel waits for user evidence.
- Dedup threshold calibration: is 70% Jaccard too loose / too tight in
  practice? Measure on real session memory files before tuning.
- Confidence field: low-confidence writes (`confidence: low`) auto-expire
  after N sessions without reinforcement rather than living forever.
- Type routing: ensure USER.md vs MEMORY.md vs AGENT.md signals are
  described precisely enough that the agent routes correctly on the first write.

**Injection scanning on write.** Memory is injected into the system prompt
on every session, exactly the same vector that skill bodies use. Skill bodies
already pass through `_DANGER_PATTERNS` in `alpi/tools/skill.py` (74 patterns:
`ignore previous instructions`, exfil-via-curl, ssh backdoors, invisible
unicode, base64-pipe-to-bash, etc.). Memory writes accept anything today.
Wire the same scanner into `Memory.run` for `add`, `replace`, and batch `entries`,
returning a `Blocked: …` error on match. Reuses existing infrastructure; no new
dependencies.

**Post-turn background review.** After every N turns (configurable, default
off / opt-in) the daemon forks a lightweight reviewer agent with a snapshot
of the conversation. The reviewer has access only to `memory(add/replace/remove)`
and `skill(create/patch)`. Its prompt is narrow: "did the user reveal a preference
or correct a behaviour? If yes, save it. If nothing qualifies, say nothing."
The reviewer thread installs an auto-deny approval callback so any dangerous
tool call inside the fork resolves without blocking on a TUI prompt that does
not exist. The active session's system prompt stays frozen throughout (prefix
cache intact); writes land on the shared memory store and are picked up next
session.

This fixes the main gap in the current model: the agent only writes memory when
it decides to mid-turn — it often misses signals that are obvious in retrospect.
The background reviewer has the full conversation in view and a single job.
The reviewer prompt borrows the Hermes insight that **user frustration is a
first-class skill signal**, not just a memory signal — corrections like "stop
doing X" or "don't format like that" should patch the responsible skill, not
just leave a memory note.

Outcome: measurable on memory file size, duplicate rate, "was this actually
recalled next session", and skill patch rate on real sessions.

### AT. Skill safety primitives

Three small changes that make the skill library safe enough to grow
aggressively in v0.6 (when the curator and telemetry land).

**Auto-archive instead of destructive delete.** Today `skill(action="delete")`
removes the skill directory permanently. Change it to move the directory to
`skills/.archive/<name>-<timestamp>/`. The behaviour for the agent is the same
(skill no longer loadable); recovery is `mv` away. Bundled `@alpi/*` skills
remain delete-protected as today.

**`.bak` snapshot before every `edit` / `patch` / `set_meta`.** Alpi already
takes a `.bak` snapshot before every memory write (`alpi/memory.py:194-200`).
Apply the same pattern to skill mutations: write the previous SKILL.md content
to `<skill>/.bak/<timestamp>.md` before persisting the change. Bounded ring of
the last N snapshots per skill (configurable, default 10).

**`pinned: true` frontmatter flag.** New optional boolean in skill frontmatter
and in memory entries. Pinned items are protected from auto-archive (AT) and
from any future curator consolidation pass (AC, v0.6). Pinning is user-facing
in the TUI / desktop UI and agent-facing through `skill(action="set_meta",
pinned=true)` / `memory(action="pin", entry=...)`.

**`absorbed_into` metadata.** When a skill is deleted as part of a merge into
an umbrella, the delete records `absorbed_into: <umbrella-name>` in the
archived skill's metadata. Agent-facing only today; foundational for the
v0.6 curator audit trail.

### BB. Enhanced rich text in TUI

The link renderer (the original v0.3 BB) shipped a baseline. v0.5 extends it
across the rest of the rich-text surface:

- Lists (ordered + unordered) — consistent indent, marker style.
- Inline code + fenced blocks — monospace font, accent-aware background,
  per-language syntax highlight where it pays off.
- Tables — column alignment, header style, fits to terminal width.
- Headings inside chat replies — sized hierarchy, not just bold.

**Why now.** With the desktop app shipped, the heavy rich-text surface lives
there — Markdown rendering in WebView is a solved problem. The TUI rich-text
work is "polish for users who stay on the terminal".

---

## v0.6 cycle (planned)

**Theme: self-improving agent + live access.** v0.5 closes the device
access story and gets memory to a reliable baseline. v0.6 turns the
skill library into something that improves itself over time, and
ships the streaming and search infrastructure that makes the live
multi-device experience feel real.

### Self-improving skills

| ID | Item | Status |
|---|---|---|
| AC | Skill telemetry + curator — usage tracking per skill (`view_count`, `use_count`, `last_used`, `state: active/stale/archived`) and a periodic background consolidation pass that promotes narrow session-specific skills into broad class-level umbrellas. Builds on the AT auto-archive + pin + `absorbed_into` primitives that ship in v0.5. | 🔵 |
| BD | Model-family conditional prompt guidance — the tool-use enforcement block + GPT/Gemini-specific operational guidance only injected for model families that need it (per `TOOL_USE_ENFORCEMENT_MODELS`). Claude / Opus / Sonnet / Qwen / MiMo run on the shorter prompt. Promoted from Future once v0.5 generates enough multi-model session evidence. | 🔵 |

### Live access + search

| ID | Item | Status |
|---|---|---|
| ALP.4 | Streaming `link.ask` — incremental remote replies for peer calls, mobile, and workgroups | 🔵 |
| BA | Local RAG over `workspace/` — local-only embeddings (`search_workspace`, `index_workspace`), no cloud roundtrip. Trade-off to settle: sentence-transformers (~80 MB) vs lighter GGUF alternative. | 🔵 |

### AC. Skill telemetry + curator

**Telemetry.** A sidecar `.usage.json` inside `skills/` tracks per-skill
activity: view count, use count, patch count, created/last-used timestamps,
and state (`active` / `stale` / `archived`). The `skill` tool updates this on
every `load`, `run`, and `patch` call. No external service — local JSON only.
Pinned skills (AT, v0.5) appear in telemetry but the state machine never
auto-transitions them.

**Curator.** A background pass (triggered by inactivity, default every 7 days)
that reviews the agent-created skill library and consolidates it. The curator's
job is not to delete — it is to **promote**: a narrow skill like
`debug-parser-may` should become a subsection of a broader
`debugging-patterns` umbrella, with the session detail demoted to
`references/`. Skills unused for 30+ days are flagged `stale`; 90+ days move
to `skills/.archive/` via the AT auto-archive primitive (recoverable). Each
consolidating delete carries the `absorbed_into:` metadata from AT so the
audit trail is intact. Bundled `@alpi/*` skills and pinned skills are never
touched.

**Algorithmic + LLM signals.** Two consolidation triggers run together: an
algorithmic pass detects prefix clusters (`debug-parser-*`, `research-bug-*`)
as candidates regardless of LLM judgment, and an LLM pass runs the umbrella-
building review on the candidate set. Cheap candidates first means the LLM
spends tokens only on real ambiguity.

**Reconciliation paranoia.** When the LLM declares a consolidation in its
structured output ("absorbed `debug-parser-may` into `debugging-patterns`"),
the curator reconciles that against the actual tool-call audit log of the
review thread. Mismatches surface as warnings in the per-run report rather
than silently trusting the model. Same pattern is applicable to any place
alpi asks the LLM to summarise what it just did.

**Per-run reports.** Each curator run writes a report under
`~/.alpi/<profile>/logs/curator/<timestamp>/` (`run.json` + `REPORT.md`)
covering classification, consolidations attempted, mismatches, and skills
moved. Audit trail for any future "what happened to skill X" question.

**What this fixes.** Skills today accumulate as flat narrow entries because
the agent writes them turn-by-turn without a global view. The curator adds
that global view without requiring the agent to reason about the whole library
on every turn.

**Design constraint vs Hermes.** Hermes nudges the agent to create a skill
after every 15 tool calls — deliberately aggressive. alpi's curator is
post-hoc and read-only during the session: it never creates skills, only
consolidates what already exists. Skill creation remains agent-driven,
guided by the AS system-prompt rules that ship in v0.5.

### BD. Model-family conditional prompt guidance

Hermes routes parts of the system prompt through a `TOOL_USE_ENFORCEMENT_MODELS`
table: the long "Actually CALL the tool…" enforcement block is injected only
for Gemini, GPT, Codex, Grok, Gemma — model families that empirically need it.
Claude / Sonnet / Opus / MiMo / Qwen run on the shorter prompt with no
regression on tool-call rate.

Hermes additionally ships `OPENAI_MODEL_EXECUTION_GUIDANCE` (tagged blocks for
`<tool_persistence>`, `<mandatory_tool_use>`, `<act_dont_ask>`,
`<verification>`, `<missing_context>`) and `GOOGLE_MODEL_OPERATIONAL_GUIDANCE`
targeting known failure modes of those families.

**Why v0.6 not v0.5.** This was already in alpi's Future versions table as BD,
gated on session evidence. v0.5's mobile work + post-turn reviewer should
generate enough cross-model session data to calibrate the routing decisions.
Promote to v0.6 once `agent.log` has a clear signal.

### ALP.4. Streaming `link.ask`

Today `link.ask` is request/response: a peer asks "research X" and waits
until the full answer lands. Streaming turns that into watching the other
agent think — reasoning tokens, tool traces, partial answers flow as they
happen.

**Wire shape.** Same envelope as today; the response carries a `stream: true`
flag and the body becomes a sequence of `{kind: "chunk"|"final"|"error",
payload: …}` frames. No new crypto, no new auth — existing envelope
signature covers the stream; intermediate chunks are AEAD-protected by the
Noise session.

**Why v0.6 not v0.5.** The protocol change touches every ALP transport path.
Without a base of real peer/workgroup sessions to validate against, the scope
cannot close cleanly. v0.5's mobile work generates that base.

### BA. Local RAG over `workspace/`

Two new tools — `index_workspace(path?)` and `search_workspace(query, k=5)`.
Embeddings and the vector store live in `~/.alpi/<profile>/index/`; nothing
leaves the machine. The agent reads matched snippets with the existing
`read_file` tool.

**Prerequisite to resolve before scoping.** Sentence-transformers brings ~80 MB
of PyTorch weights. A GGUF/llama.cpp CPU alternative is lighter but slower
to index. Decide based on install-size feedback from real v0.5 users before
committing.

## Future releases

Items worth doing, but not part of the current cycle.

| ID | Item | Status |
|---|---|---|
| BF-8 | Skill versioning / install-update flows — pinned install source, update preview/diff, revision metadata | 🔵 |
| ALP.5 | Blob transfer — `link.put_blob` / `link.get_blob`, content-addressed, chunked AEAD. Depends on real workgroup usage to justify the protocol complexity. | 🔵 |
| ALP.6 | Workgroup search — semantic search over workgroup transcripts via local RAG (pairs with **BA**). Depends on BA landing and workgroups being heavily used. | 🔵 |

### ALP.5. Blob transfer

Two new verbs — `link.put_blob(bytes, hash)` and `link.get_blob(hash)` — for
sharing artefacts that have no business inline in a JSON envelope: a PDF, a
dataset, the output of a skill, a screenshot.

**Wire shape.** Content-addressed by SHA-256; the recipient stores under
`~/.alpi/<profile>/alp/blobs/<hash>` and dedups across calls. Chunked
transfer (default 64 KiB) with per-chunk AEAD; the final frame carries the
full-blob signature so the receiver can verify end-to-end. Caps: per-call max
blob size (config knob, 100 MiB default), per-day inbound budget per peer
(separate from the spending ledger — this gates *bytes*, not LLM cost).

**Pairs naturally with workgroups.** A workgroup post can reference a blob
(`{text: "see attached", blob: "<hash>"}`); the hub fans it out and members
`link.get_blob` from the hub on demand. No cloud upload, no third-party
intermediary.

**Why it waits.** ALP.5 is only worth the protocol complexity if workgroups
are heavily used and blobs are a real bottleneck. That evidence doesn't exist
yet. Promote when a workgroup user reports "I can't share a file".

### ALP.6. Workgroup search

`workgroup.search(workgroup_id, query)` returns the top-K posts matching a
query, ranked by semantic similarity using the local RAG index (**BA**). The
hub indexes its own transcript on disk; members search remotely via the
existing ALP transport.

**Why it waits.** Depends on BA landing first, and on workgroups being heavily
used enough that scrolling becomes a real friction. Neither condition holds yet.

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
| Signal | Signal gateway via signal-cli | Strong privacy fit, but phone-number/SIM setup and daemon dependency make it less important once mobile is planned |
| AY | Skills marketplace — federated, signed, never centralised | Presupposes an active author community + adoption for discovery to matter |
| AI (2) | Memory v2 — TUI panel (collapsible, edit-in-place, "forget this") | UI weight for niche audience (power users with much memory); item 1 covers the substantive part |
| AJ | Browser realism — Cloudflare / captcha / fingerprint depth | Cat-and-mouse perpetuo; without concrete failing use case, scope can't close |
| AQ | Continuous voice mode (push-to-talk, hotword loops) | Niche unless voice becomes a real surface for users |
| Webhook | Inbound HTTP triggers (HMAC-signed) | "Swiss-army-knife trap" — needs real demand, not speculation |
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
catalog big enough that discovery matters. Bundled skills ship
under `@alpi/*` (`@alpi/knowledge` in v0.3, `@alpi/home` in v0.5)
and BF skills v2 primitives make third-party skills shippable.
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
different costs per skill — neither holds today (one bundled
skill in v0.3, second in v0.5, plus a handful of user-authored
ones at most). The dimension explosion is dead weight until
the catalog grows. May be discarded entirely if no demand
emerges by v0.6.

---

## Principles

alpi **respects the ToS of every provider it integrates with**. When
an LLM vendor (OpenAI, Anthropic, …) offers a paid subscription for a
first-party client (ChatGPT Plus/Pro, Claude Pro/Max, Claude Code),
that subscription is for THAT client. Reverse-engineering the private
OAuth flow of the official CLI to route a third-party agent against
the same quota is:

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

- **C. OpenAI Codex OAuth** (ChatGPT subscription auth). ToS
  violation, see "Principles".
- **V. Anthropic subscription OAuth** (Claude Pro/Code auth). ToS
  violation, see "Principles".
- **J. camoufox** (+230 MB Firefox) for anti-bot. Humanised
  Playwright covers the real detection surface without the weight.
- **WhatsApp gateway.** Meta Business API requires company
  verification + is expensive; `whatsapp-web.js` / Baileys are
  reverse-engineered with frequent bans, and the attack surface
  is catastrophic (a compromised bot leaks every chat). Not worth
  shipping for a personal agent.
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
  by default". Curated bundled skills under the reserved
  `@alpi/*` namespace (knowledge in v0.3, home in v0.5) are the
  path; community marketplace ideas live in Future versions.
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
