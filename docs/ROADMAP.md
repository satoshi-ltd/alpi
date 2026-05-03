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

**Theme: owned mobile access.** v0.4 shipped the secure local-device
foundation: desktop is a host-plane client, profile state sits behind
`host.*`, and encrypted backup/restore makes a profile portable. v0.5
should make the remote-access story obvious: a mobile companion reaches
the user's own profile over ALP, brings the existing desktop workgroup
experience to the phone, and ALP streaming makes remote turns feel
live. Umbrel support gives that mobile client an easy always-on
home-server target without turning alpi into a hosted service.

This is the cycle where gateways stop being the main mobile story.
Telegram, IMAP, Gmail, and Matrix stay useful, but the project should
not depend on third-party chat apps as the primary way to reach a
personal agent.

### Mobile + live access

| ID | Item | Status |
|---|---|---|
| AX-mobile | Mobile companion (iOS / Android) — chat, status, peers, and workgroups from the user's own profile over ALP.2 | 🔵 |
| ALP.4 | Streaming `link.ask` — incremental remote replies for peer calls, mobile, and workgroups | 🔵 |

### Server distribution

| ID | Item | Status |
|---|---|---|
| Umbrel | Umbrel app MVP — one-click home-server deployment for an always-on alpi profile through the existing TUI | 🟡 |

### ALP depth

| ID | Item | Status |
|---|---|---|
| ALP.5 | Blob transfer — `link.put_blob` / `link.get_blob`, content-addressed, chunked AEAD | 🔵 |
| ALP.6 | Workgroup search — semantic search over a workgroup transcript via local RAG (pairs with **BA**) | 🔵 |

### Skills + bundled

| ID | Item | Status |
|---|---|---|
| BF (4, 6-8) | Skills v2 — output schemas, composition, test harness, versioning (triggers shipped as keyword hint in v0.3.11) | 🔵 |
| BJ | Skills capability stress test — author one non-trivial real skill end-to-end (web a11y reviewer with Playwright) and let the gaps drive the BF backlog | 🔵 |
| `@alpi/home` | Second bundled skill (after `@alpi/knowledge` in v0.3). Orchestrates Home Assistant + optional connectors (Hue, Xiaomi, Alexa / Google Home) behind a single voice/text interface | 🔵 |

### Knowledge + memory

| ID | Item | Status |
|---|---|---|
| BA | Local RAG over `workspace/` — local-only embeddings, semantic search tools | 🔵 |
| AI (1) | Memory v2 — generation quality (tool description, dedup threshold, confidence field). Server-side only; the TUI panel waits for user evidence | 🔵 |

### UX polish

| ID | Item | Status |
|---|---|---|
| BB | Enhanced rich text in UI — extend baseline link renderer to lists, code blocks, tables, headings | 🔵 |

### AX-mobile. Mobile companion (iOS / Android)

After **desktop-v0.1.0** validated the visual UI, mobile is the
next surface. Same architecture (ALP client to a remote
alpi profile), more friction (App Store signing, iOS
background restrictions, distribution).

**Why a companion, not a full port.** A mobile alpi running its
own LLM + tools doubles the security surface and the
maintenance cost without adding capability. ALP is already the
protocol for "another machine talks to my profile" — the
companion is just another peer.

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

The mobile surface can start read-only if pairing, posting, or key
handling need more hardening, but the target is the same capability as
desktop.

**Open questions before scope locks:**
- Tauri vs. native (SwiftUI / Kotlin) — Tauri wins on desktop
  but mobile is more contested; native may be better for iOS
  background + push notifications.
- iOS background restrictions — running an ALP TCP listener on
  iOS is non-trivial; the companion likely *initiates*
  connections to the user's profile rather than accepting them.
- Distribution — TestFlight + Play Store internal track at
  first.

### Umbrel. Home-server app MVP

Umbrel is not another client surface. It is the easiest way to put an
alpi profile on a machine that is already meant to run 24/7 at home.
That makes it a natural companion to mobile: the phone talks to the
user's own always-on profile instead of relying on chat gateways as
the remote-access story.

**MVP scope.**

- Docker image for `alpi-agent` with persistent profile storage.
- Umbrel app package (`umbrel-app.yml`, `docker-compose.yml`,
  `exports.sh` when useful).
- `alpi daemon start` as the long-running service.
- Existing Alpi TUI served through Umbrel's app proxy with a browser
  terminal. The app should feel like opening Alpi on the home server,
  not like a second web product.
- Volume layout documented so backup/restore works cleanly with
  the encrypted profile archive.

**Non-goals for the MVP.**

- No full desktop-app port to web.
- No separate web dashboard unless the terminal TUI proves insufficient.
- No browser access to raw profile files.
- No direct exposure of the host Unix socket to the browser.
- No broad settings dashboard until the minimal server install proves
  useful.

**Why v0.5.** Mobile needs a credible always-on host. Umbrel users
already understand local servers, app proxies, backups, and Tailscale.
The app gives alpi a home-server install path without requiring the
user to SSH into a box and run CLI setup by hand.

### ALP.4. Streaming `link.ask`

Today `link.ask` is request/response: a peer asks "research X"
and waits until the full answer lands. Streaming chunks turns
that into *watching the other agent think* — reasoning tokens,
tool traces, partial answers all flow as they happen.

**Wire shape.** Same envelope as today; the response carries a
`stream: true` flag and the body becomes a sequence of
`{kind: "chunk"|"final"|"error", payload: …}` frames. Over Unix
socket: line-delimited JSON. Over TCP/Noise: each frame is its
own encrypted record. No new crypto, no new auth — the
existing envelope signature covers the stream as a whole
(signed at the final frame); intermediate chunks are
AEAD-protected by the Noise session for inter-machine, by the
Unix-socket trust boundary intra-machine.

**Why it matters.** Two payoffs. (1) Demos: "two alpis
collaborating" looks like one watching the other type, the
single most legible visualisation of agent-to-agent work we
can ship. (2) Inside workgroups (ALP.3), a long
`workgroup.post` appears live for every member — the workgroup
transcript becomes a real-time surface, not a polling one. The
same primitive lets **AX-mobile** stream a remote profile's
reply incrementally instead of waiting for the full turn.

### ALP.5. Blob transfer

Two new verbs — `link.put_blob(bytes, hash)` and
`link.get_blob(hash)` — for sharing artefacts that have no
business inline in a JSON envelope: a PDF, a dataset, the
output of a skill, a screenshot.

**Wire shape.** Content-addressed by SHA-256; the recipient
stores under `~/.alpi/<profile>/alp/blobs/<hash>` and dedups
across calls. Chunked transfer (default 64 KiB) with per-chunk
AEAD; the final frame carries the full-blob signature so the
receiver can verify the artefact end-to-end. Caps: per-call
max blob size (config knob, 100 MiB default), per-day inbound
budget per peer (separate from the spending ledger — this
gates *bytes*, not LLM cost).

**Pairs naturally with workgroups.** A workgroup post can
reference a blob (`{text: "see attached", blob: "<hash>"}`);
the hub fans out the post and members `link.get_blob` from the
hub on demand. No need to upload to the cloud, no third-party
intermediary.

### ALP.6. Workgroup search

Once a workgroup runs for weeks, scrolling becomes useless.
`workgroup.search(workgroup_id, query)` returns the top-K posts
matching a query, ranked by semantic similarity using the local RAG
index (**BA**). The hub indexes its own
transcript on disk; members search remotely via the existing ALP
transport.

**Why it pairs with BA.** Reuses the same embedding model and
vector store; no separate ML surface to maintain. The hub embeds
each post when it lands and answers `workgroup.search` from the
local index — no roundtrip to a third party, no plaintext leaks
beyond the workgroup membership.

**Pairing with `@alpi/knowledge`.** v0.3 ships `@alpi/knowledge`
v1 (keyword grep) as the first bundled skill. **BA** and
**ALP.6** ship together in v0.5 — `@alpi/knowledge` v2 swaps
to the same RAG backend that ALP.6 uses, so one embedding
stack covers two surfaces (knowledge over docs, search over
transcripts).

### BF (items 4, 6-8). Skills v2 — schemas, composition, tests, versioning

Layers on the v0.3.11 foundation (declared `requires_env`,
per-skill SQLite via the `db` tool, schema-validated frontmatter,
`set_meta` for surgical updates). Item 5 (triggers) shipped as
the `keywords` hint in v0.3.11; the schedule/workgroup flavors
were dropped as redundant with the existing `schedule` tool.

4. **Output schemas.** Optional
   `output: { schema: json, fields: [...] }` in frontmatter.
   Runner validates and surfaces structured findings to the
   user instead of free text.
6. **Composition.** `skill.invoke(name, args)` as a tool. A
   skill can call another skill; reuses the existing surface;
   no new wire format.
7. **Test harness.** `alpi skill test <name>` runs prompt
   fixtures and verifies (a) the LLM dispatched, (b) tool
   calls match expected pattern, (c) output validates against
   the schema.
8. **Versioning.** `alpi skill install <url>` pins to a commit
   hash. `alpi skill update <name>` shows the diff before
   applying.

Each item shippable independently. Composition and output
schemas pair: schemas have most of their value when consumed by
a calling skill.

### BJ. Skills capability stress test

v0.3.11 shipped the foundation (eligibility, schema, db, set_meta,
keyword hint). The honest question is: is it enough to author a
**non-trivial real skill** end-to-end? The hypothetical canary:

> *"web accessibility reviewer — open the landing + a docs page in
> headless Playwright, on desktop and mobile viewports, run an
> axe-core or lighthouse pass, persist findings in
> ``state/db.sqlite``, regress against the previous run."*

The skill needs to: declare `requires_env` for any auth, declare
optional Playwright/axe-core deps and degrade gracefully when
absent, run scripts that capture screenshots into `assets/`, store
structured findings in SQLite, present a diff against the previous
run.

What we'll likely find missing (driving BF backlog):

- **Output schemas** so the parent agent gets a structured report, not free-form prose.
- **Composition** if we factor "open page" / "axe pass" / "diff vs previous" into separate sub-skills.
- **Test harness** to validate the skill keeps working as Playwright versions move.
- **Version pinning** so a Playwright API change doesn't silently break the skill.
- A way to declare "needs Playwright; degrade if absent" (currently `requires_env` covers env vars only — no analogous `requires_python_pkg`).

Author the skill, ship it as `@alpi/web-a11y` if it earns its way
to bundled (or as a documented user skill if not). Whatever the
authoring surfaces complains about loudest becomes the next BF
sub-item to attack. Scope of the work is intentionally
**capability-driven**, not feature-driven.

### `@alpi/home`. Second bundled skill — home orchestration

After `@alpi/knowledge` (v0.3) validated the bundled-skills
pattern, `@alpi/home` is the second one — and demonstrates the
Skills v2 primitives in real use. One coherent voice/text
interface to the user's home, regardless of which underlying
ecosystem(s) they run.

**Surface.** A skill that orchestrates one or more of:
- **Home Assistant** (primary) — sensors, lights, scenes,
  occupancy, switches.
- **Philips Hue** — directly via the Hue Bridge HTTP API.
- **Xiaomi Mi Home** — via `python-miio`.
- **Google Home / Alexa** — via their official assistant
  device APIs (read-only "is anyone home" queries; speak via
  the device).

The user enables only the integrations they have. The skill
declares each as an optional `requires:` and degrades
gracefully when an integration isn't configured.

**Per-skill SQLite.** Caches device state +
last-seen timestamps so the agent doesn't re-poll every
turn ("is the kitchen light on?" answers from cache; "turn it
on" pushes through).

**Configuration.** Per-profile `.env` for tokens (`HA_URL`,
`HA_TOKEN`, `HUE_BRIDGE_IP`, `XIAOMI_TOKEN`, …); allowlist of
entity domains in `config.yaml` so the skill can only touch
what the user explicitly opted in.

**Why a bundled skill, not a tool family.** A tool family
("home_assistant" as a top-level tool) hardcodes our taste
into every profile. A bundled skill is opt-in (load on
demand), sandboxed by Skills v2 quotas, and demonstrates that
**alpi ships skills the way Linux distros ship packages** —
curated, opinionated, optional. The marketplace (deferred to
Future versions) extends this to community-published skills
later.

LOC estimate: ~400 (HA covers ~250, Hue + Xiaomi ~50 each,
Google/Alexa ~50 stub).

### BA. Local RAG over `workspace/`

Semantic search over the user's project files without sending
a byte to a third party. Two new tools:

- `index_workspace(path?)` — embeds the workspace into a local
  vector store (`~/.alpi/<profile>/index/`). Default model is a
  small sentence-transformer (`all-MiniLM-L6-v2` or similar);
  optionally swappable.
- `search_workspace(query, k=5)` — returns top-K snippets with
  filepath + line range. The agent then reads the matching
  ranges with the existing `read_file` tool.

**Why not piggy-back on a cloud RAG.** The whole point is that
the workspace contents never leave the machine. Embedding
model + index both live locally; no API roundtrips during
search.

**Trade-offs to settle.** Sentence-transformers ships ~80 MB of
PyTorch weights — significant install weight. A pure-CPU
alternative (e.g., GGUF + llama.cpp) keeps the install lighter
at the cost of slower indexing. Decide during scope.

### AI (item 1). Memory v2 — generation quality

Server-side improvements to the `memory` tool. The TUI panel
(item 2) waits for user evidence in Future versions.

Open questions to settle:
- Are we writing the right memory type per signal?
- Is the 70% Jaccard dedup threshold too loose / too tight?
- Should the tool take a "confidence" field so low-confidence
  writes auto-expire?
- Compare against comparable agents + the latest public
  memory patterns (Mem0, Letta) and pick what fits our scope.

Small surface, measurable outcomes (memory file size,
duplicate rate, "useful at recall" judgement on real
sessions).

### BB. Enhanced rich text in TUI

The link renderer (the original v0.3 BB) shipped a baseline.
v0.5 extends it across the rest of the rich-text surface:

- Lists (ordered + unordered) — consistent indent, marker
  style.
- Inline code + fenced blocks — monospace font, accent-aware
  background, per-language syntax highlight where it pays off.
- Tables — column alignment, header style, fits to terminal
  width.
- Headings inside chat replies — sized hierarchy, not just
  bold.

**Why now.** With the desktop app shipped, the heavy rich-text
surface lives there — Markdown rendering in WebView is a solved
problem. The TUI rich-text work is "polish for users who stay on
the terminal", not "the place we render structured replies".

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
| BD | Model-aware tool-use-enforcement guidance | Small change, but value unproven; needs `agent.log` evidence first |
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
transfer, v0.5) covers the file case.

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
catalog big enough that discovery matters. v0.3 ships the
first bundled skill (`@alpi/knowledge`); v0.5 ships the second
(`@alpi/home`) and the BF (4-8) primitives that make
third-party skills shippable (signing, versioning, test
harness). Marketplace promotes only when there's evidence that
real authors want to publish for real users.

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

### BD. Model-aware tool-use-enforcement guidance

Gate the "Actually CALL the tool…" paragraph in
`alpi/prompts/system_prompt.md` on model family. Claude /
MiMo / Qwen / Sonnet / Opus follow tool instructions well
without the long enforcement block; GPT / Codex / Gemini /
Gemma / Grok appear to need it.

**Why it waits.** Small change, but value unproven. Needs
`agent.log` evidence: tool-call rate on a Claude session with
vs without the block (same prompts). Apply the split only if
no regression on the shorter variant. The data isn't there
yet; once the desktop/mobile surfaces generate enough real sessions, the
decision becomes calibrated rather than guessed.

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
