# Roadmap

Open work for alpi. Shipped work lives in
[CHANGELOG.md](../CHANGELOG.md) — this file never repeats it. For
technical reference of what currently ships, see
[ARCHITECTURE.md](ARCHITECTURE.md).

Audience: the creator ([@soyjavi](https://github.com/soyjavi)) and
any future contributor reading the repo cold.

Legend: 🔵 backlog · 🟡 next up · ⏸ blocked · 🔴 gate.

---

## v0.4 cycle (active)

**Theme: alpi gets a face.** v0.3 made alpi a credible
private-agent tool on the terminal. v0.4 is the cycle where the
project earns wider adoption: a desktop app (Ollama-style
distribution), skills mature into mini-apps, a federated gateway
ships, and the security story closes with a third-party audit.
Tightly scoped — 2 items — to ship in 3-4 months without
becoming a broken release.

### Hardening

| ID | Item | Status |
|---|---|---|
| AW | Encrypted profile backup/restore — zero-knowledge passphrase-encrypted archive of `~/.alpi/<profile>/` | 🔵 |

### Commercial track

| ID | Item | Status |
|---|---|---|
| AX-desktop | App de escritorio (Tauri) — `alpi daemon` local + visual UI for chat / profiles / peers / workgroups. In progress on `feat/desktop-app`; lands at v0.4 cut | 🟡 |
| Matrix | Federated + E2EE gateway — flagship gateway of v0.4. Self-hosted homeserver, no phone number, matches the "private agent network" thesis | 🔵 |
| BF | Skills v2 (items 1-3) — scaffolder, declared `requires`/`env`, per-skill SQLite. The "skills = mini-apps" pillar. Absorbs BE | 🔵 |

### Observability

| ID | Item | Status |
|---|---|---|
| `alpi diff` | "What changed in my profile in last N hours" — memory writes, peer additions, skill installs, sessions. Pairs with the **BC** audit story | 🔵 |

---

## v0.4 — detailed scope

### BC. External security audit before public release

**Why before v0.4, not v0.3.** A real audit is 4-8 weeks of vendor
engagement plus remediation. Forcing it into the v0.3 window would
be theatre. v0.3 ships with a public commitment: the contract
becomes part of the launch story, the report lands at
`docs/audits/v0.4-<vendor>.md` before the v0.4 cut.

**Scope of the engagement.**

- Threat model: who is the attacker, what's protected, what's
  non-goal. Draft lives in `docs/SECURITY.md` today; the auditor
  formalises and challenges it.
- ALP cryptography review: envelope signing (Ed25519 PKCS8),
  replay cache, Noise_XK wrapper, peer-pinning workflow, workgroup
  key handling.
- Tool surface review: approval system, sandbox posture (macOS
  sandbox-exec profile + Linux bwrap), shell denylist, skill
  scanner, OSV check, SSRF guards in `browser` / `web_*` tools.
- Dependency posture: `pip-audit` output, third-party-code risks
  documented in `docs/SECURITY.md → Third-party code`.
- Privacy review: confirm **Zero Knowledge** + **Privacy by
  Design** claims match the code — no hidden telemetry paths, no
  analytics beacons, no cloud coupling that's not user-chosen.

**Output.** A public report. Issues found are either fixed before
v0.4 or documented in the report with a timeline. The report being
published is part of the trust story — sitting on findings isn't.

### AW. Encrypted profile backup/restore

Zero-knowledge archive of `~/.alpi/<profile>/`: memories, peers,
skills, sessions, the `.env`, the `config.yaml`. Two verbs:

- `alpi backup [--out PATH]` — passphrase-prompt; emits a single
  age-encrypted file (`profile-name.YYYY-MM-DD.alpi-backup`).
- `alpi restore PATH` — passphrase-prompt; reverses the above into
  `~/.alpi/<profile>/`, refusing to overwrite a non-empty profile
  unless `--force`.

Crypto: **age** with passphrase recipient (no asymmetric keys for
the user to manage). Argon2id KDF. The profile owner is the only
party who can decrypt; we never see the plaintext.

**Why it matters commercially.** "Carry your agent between
machines" + "no vendor lock-in" + "if your laptop dies, you have
your agent back" — every commercial AI tool today loses your
context when you re-install. We don't.

### AX-desktop. Desktop app — Tauri, ALP.1 client to local service

The flagship adoption item of v0.4. Ollama proved that a CLI
project crosses the chasm to non-hacker users when it ships a
proper desktop app — tray icon, native window, "download the
.dmg, click open, you're running". alpi gets the same.

**Architecture.** A Tauri (Rust + WebView) app that talks to the
local `alpi daemon` over the host plane on a Unix socket
(`~/.alpi/host/host.sock`, default profile only — sibling
profiles are reached via a `profile` parameter on every host
verb). The agent itself stays in the daemon — the desktop does
not run an LLM, does not own tools, does not duplicate security.
It is a visual host-plane client: chat surface, profile manager,
peer / workgroup viewer, settings, log viewer. Same model
**AX-mobile** (v0.5) will use over ALP.2.

**Why Tauri, not Electron, not native.** Tauri = one codebase
for macOS / Linux / Windows, ~10 MB binary, Rust ecosystem
(`snow` covers Noise_XK if we ever need it inter-machine).
Electron rejected: 200 MB per app contradicts the "no fat
dependencies" posture. Native (SwiftUI / GTK / WPF) rejected
for v0.4 — 3× engineering for marginal polish. Revisit per-OS
native if Tauri hits a ceiling.

**Distribution.** Signed `.dmg` (macOS), `.AppImage` (Linux),
`.exe` installer (Windows). Self-update via the same
`alpi update` cache the CLI uses, with a UI prompt instead of
a shell command.

**Branch parallel.** Work begins immediately on
`feat/desktop-app`, in parallel with v0.3.x patch releases on
`main`. The branch lands at v0.4 cut after the rest of the v0.4
backlog (BC, AV, AW, Matrix, BF 1-3, BG) is in.

**What it explicitly does NOT do in v0.4.**
- No mobile (iOS / Android) — that's **AX-mobile** in v0.5,
  which adds App Store / signing / background-restriction work
  on top of an already-validated UI.
- No standalone agent. Always talks to a local `alpi daemon`.
- No theme marketplace, no plugins. Boring shell on top of the
  agent — that's the design.

### Matrix. Federated + E2EE gateway

The gateway most aligned with the project's thesis. Federated
(user chooses homeserver), E2EE by default (Olm/Megolm),
self-hostable (Synapse, Conduit), no phone number. Pairs with
the "home server hosts your alpi" topology in DEPLOYMENTS §2.

**Scope.** `alpi/gateway/platforms/matrix.py` using `matrix-nio`
(Python, well-maintained). `alpi setup → Gateways → Matrix`
prompts for homeserver URL + access token + room allowlist.
Outbound replies E2EE by default; the bot device gets verified
on first run via emoji SAS.

**Why flagship and not parity-with-Telegram.** Telegram is
"what people have" (so it shipped first, in v0.3). Matrix is
"what makes alpi's pitch unique" — the gateway you use when you
don't want to depend on anyone, including us. That's a story
neither Hermes nor openclaw can tell because their backends
hold every platform's tokens centrally.

LOC estimate: ~250.

### BF. Skills v2 — items 1-3 (mini-app pillar)

v0.3 ships skills as prompt augmentation. v0.4 adds the three
foundational items that turn skills into **real mini-apps with
state**; the discoverability / composition / testing items
follow in v0.5 once `agent.log` evidence calibrates them.

1. **Scaffolder.** `alpi skill new <name>` — wizard producing
   a SKILL.md skeleton with a discoverability-friendly
   description, declared `requires` / `env`, and an example
   invocation prompt. Validates uniqueness, lints frontmatter.
2. **Declared dependencies.** Frontmatter
   `requires: [browser, read_file]` + `env: [HTTP_PROXY]`.
   Loud failure at install if a required tool is disabled in
   the profile (instead of a silent bad-LLM-call later). Pairs
   with **AV** — the env allowlist becomes the same primitive.
3. **Per-skill SQLite.** `~/.alpi/<profile>/skills_db/<name>.db`,
   exposed as `db.query` / `db.exec` only to the owning skill.
   Schema declared in frontmatter (`db.migrations: [...]`).
   Quotas: 50 MB size / 5 s query / 10k rows. Backed up by
   `alpi backup` (**AW**). `alpi skill reset <name>` nukes the
   DB without touching others.

**Why these three first, not the full eight.** They form the
narrative pillar — a user can write a skill, declare its
dependencies, and persist structured state. That alone is a
mini-app. Output schemas, triggers, composition, test harness
and versioning (items 4-8, in v0.5) layer on top once the
foundation is solid and `agent.log` shows where authoring
breaks down in practice.

**Marketing differentiator.** Skills with their own SQLite
travel with the user's profile via **AW** backup =
**mini-apps you wrote in 50 lines**, living inside *your*
agent, not a vendor's backend. Hermes and openclaw can't ship
this — their skills run in their backend, not the user's.

**Absorbs the v0.3-deferred BE** (revisit `@alpi/knowledge`):
the scaffolder + declared deps make all skills more reliable
to author, including the bundled one.

### `alpi diff` — what changed in this profile

`alpi diff [--since 7d]` lists what changed in the profile's
state since N hours/days ago: memory writes, peer additions,
skill installs, session counts, budget consumption.

**Use cases.**
- Came back from holiday — "what did my service do while I
  was away?"
- Workgroup ran autonomously overnight — daily summary view.
- Audit / post-incident review — alternative to grepping
  `agent.log` by hand.
- Sync between machines — "what changed in
  `~/.alpi/personal/` that I should propagate?"

**Why v0.4.** Pairs naturally with **BC** (the external
audit) — the auditor's threat model and `alpi diff`'s output
co-design. Both ship in v0.4.

---

## v0.5 cycle

**Theme: depth + reach.** v0.4 made alpi adoptable (desktop
app, Skills v2 foundation, Matrix gateway, audited security).
v0.5 extends reach (mobile, second gateway, second bundled
skill) and deepens what already exists (ALP streaming + blobs,
workgroup search, RAG, skills v2 composition). Tightly scoped
— items waiting on user evidence live in the **Future
versions** section below this one.

### Adoption — mobile + viewers

| ID | Item | Status |
|---|---|---|
| AX-mobile | Mobile companion (iOS / Android) — same client model as AX-desktop, over ALP.2 | 🔵 |
| AZ | Workgroup viewer — folds into AX-mobile and AX-desktop (read-only or read/write transcript) | 🔵 |

### Gateways

| ID | Item | Status |
|---|---|---|
| Signal | Signal gateway via signal-cli — best E2EE consumer messenger | 🔵 |

### ALP depth

| ID | Item | Status |
|---|---|---|
| ALP.4 | Streaming `link.ask` — SSE-style chunked replies between peers | 🔵 |
| ALP.5 | Blob transfer — `link.put_blob` / `link.get_blob`, content-addressed, chunked AEAD | 🔵 |
| ALP.6 | Workgroup search — semantic search over a workgroup transcript via local RAG (depends on **BA**) | 🔵 |

### Skills + bundled

| ID | Item | Status |
|---|---|---|
| BF (4-8) | Skills v2 — output schemas, triggers, composition, test harness, versioning. Layers on the v0.4 foundation | 🔵 |
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

After **AX-desktop** validates the visual UI in v0.4, mobile is
the next surface. Same architecture (ALP client to a remote
alpi profile), more friction (App Store signing, iOS
background restrictions, distribution).

**Why a companion, not a full port.** A mobile alpi running its
own LLM + tools doubles the security surface and the
maintenance cost without adding capability. ALP is already the
protocol for "another machine talks to my profile" — the
companion is just another peer.

**Surfaces this could replace or extend:**
- Telegram gateway (today's mobile story) — keep working but
  optional once the companion is real.
- `/peers`, `/budget`, `/memory` panels exposed read-only on
  the go.
- Workgroup viewer (**AZ**) folds in here — the same companion
  that mirrors a 1:1 chat shows the workgroup transcript.

**Open questions before scope locks:**
- Tauri vs. native (SwiftUI / Kotlin) — Tauri wins on desktop
  but mobile is more contested; native may be better for iOS
  background + push notifications.
- iOS background restrictions — running an ALP TCP listener on
  iOS is non-trivial; the companion likely *initiates*
  connections to the user's profile rather than accepting them.
- Distribution — TestFlight + Play Store internal track at
  first.

### AZ. Workgroup viewer

Folds into AX-mobile and AX-desktop. The same companion that
mirrors a 1:1 chat shows the workgroup transcript: read-only
view by default; read/write when the user is an active member.
No separate codebase, no separate distribution.

### Signal. Gateway via signal-cli

Signal has the strongest E2EE posture of any consumer
messenger; integration runs `signal-cli` as a local daemon
exposing an HTTP/JSON-RPC endpoint that alpi POST/GETs against.
v0.5 because the user-facing setup needs **AX-desktop** (v0.4)
to make the SIM-registration flow tolerable.

**Scope.** `alpi/gateway/platforms/signal.py` talking to a
locally-running `signal-cli daemon --http 127.0.0.1:…`.
First-run: user registers a bot number, follows signal-cli's
captcha + SMS verify flow once
(`signal-cli -u <num> register`), then
`alpi setup → Gateways → Signal` stores the daemon URL +
allowlist of sender numbers.

**Operational note.** Requires a SIM / VoIP number (~$5/mo on
Twilio / JustCall). Niche unless the user values E2EE +
self-hosted on a messenger non-techies can already use.

LOC estimate: ~200 (HTTP client + polling loop + send).

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
index (**BA**, shipped in v0.4). The hub indexes its own
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

### BF (items 4-8). Skills v2 — composition, schemas, triggers, tests, versioning

Layers on the v0.4 foundation (scaffolder + declared deps +
per-skill SQLite). Each item shippable independently; order
driven by `agent.log` evidence from real v0.4 usage.

4. **Output schemas.** Optional
   `output: { schema: json, fields: [...] }` in frontmatter.
   Runner validates and surfaces structured findings to the
   user instead of free text.
5. **Triggers.** `trigger: { schedule: "weekly", on_keywords:
   [...], on_workgroup_post: true }`. Hooks the existing
   scheduler; keyword triggers boost dispatch prior in the
   system prompt — fixes the `@alpi/knowledge` follow-rate
   problem on small models without a special case.
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

**Why these five later, not in v0.4.** They depend on the
foundation landing first (items 1-3) and on agent.log evidence
to calibrate the discoverability mechanism (item 5 in
particular).

### `@alpi/home`. Second bundled skill — home orchestration

After `@alpi/knowledge` (v0.3) validated the bundled-skills
pattern, `@alpi/home` is the second one — and demonstrates the
v0.4 Skills v2 primitives in real use. One coherent voice/text
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

**Per-skill SQLite (BF item 3, v0.4).** Caches device state +
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

**Why v0.5, not v0.4.** Once **AX-desktop** ships (v0.4), the
heavy rich-text surface lives there — Markdown rendering in
WebView is a solved problem. The TUI rich-text work in v0.5
is "polish for users who stay on the terminal", not "the
place we render structured replies".

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
| AY | Skills marketplace — federated, signed, never centralised | Presupposes an active author community + adoption for discovery to matter |
| AI (2) | Memory v2 — TUI panel (collapsible, edit-in-place, "forget this") | UI weight for niche audience (power users with much memory); item 1 covers the substantive part |
| AJ | Browser realism — Cloudflare / captcha / fingerprint depth | Cat-and-mouse perpetuo; without concrete failing use case, scope can't close |
| AQ | Continuous voice mode (push-to-talk, hotword loops) | Niche unless voice becomes a real surface for users |
| BD | Model-aware tool-use-enforcement guidance | Small change, but value unproven; needs `agent.log` evidence first |
| Webhook | Inbound HTTP triggers (HMAC-signed) | "Swiss-army-knife trap" — needs real demand, not speculation |
| Cost telemetry | Cost split per-skill / per-tool | Only pays off with many skills + notably different costs; today neither holds |

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
yet; once v0.4 + v0.5 generate enough real sessions, the
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

The competitor landscape routinely ships "Codex OAuth" / "Claude Code
OAuth" features.
**alpi does not, and will not.** If a vendor publishes an official
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
  scoped for v0.4 as "needed by AX-desktop to render sessions".
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
  desktop app (**AX-desktop**, v0.4) is the right surface for
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
