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

**Theme: closing the device-access loop on mobile + tightening the
capability core.** Remote desktop, local recall over the workspace
(BA), the memory v2 quality pass, and the v0.5 capability hardening
pass (skills eligibility, granular approval allowlist, memory
promotion queue, compaction event log + regression guard) all
shipped during the v0.4 line. What remains for v0.5 is the second
real client surface — the mobile companion — and the second bundled
skill, `@alpi/home`. v0.6 builds on that base with a self-improving
skill library and capability maintenance.

This is the cycle where gateways stop being the main mobile story.
Telegram, IMAP, Gmail, and Matrix stay useful, but the project should
not depend on third-party chat apps as the primary way to reach a
personal agent.

### Device + live access

| ID | Item | Status |
|---|---|---|
| AX-mobile | Mobile companion (iOS / Android) — full chat, status, peers, and workgroups surface from the user's own profile. Daemon side shipped in v0.4.1 (host plane on WebSocket + per-device pairing tokens, see CHANGELOG). Mobile preview exists; desktop remains the reference surface. | 🟡 |

### Skills + bundled

| ID | Item | Status |
|---|---|---|
| `@alpi/home` | Second bundled skill (after `@alpi/knowledge` in v0.3). Full home orchestration behind a single voice/text interface: Home Assistant first, with optional Hue, Xiaomi, Alexa / Google Home integrations layered in. | 🔵 |

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

---

## v0.6 cycle (planned)

**Theme: self-improving agent + capability maintenance.** With the
device-access, local-recall, and v0.5 hardening layers in place, v0.6
turns the skill library into something that improves itself over time,
adds operator-facing memory diagnostics, and introduces safe local
skill import without adopting a marketplace or plugin runtime.

### Self-improving skills

| ID | Item | Status |
|---|---|---|
| AC | Skill telemetry + curator — usage tracking per skill (`view_count`, `use_count`, `last_used`, `state: active/stale/archived`) and a periodic background consolidation pass that promotes narrow session-specific skills into broad class-level umbrellas. Builds on the v0.5 AT primitives (auto-archive + `pinned` flag); adds the curator-specific pieces: `absorbed_into:` metadata on consolidating deletes, memory `pinned` flag (memory entries are also reviewer-mutable in v0.6), and a `.bak` ring per skill if single-snapshot proves insufficient under aggressive curation. | 🔵 |
| BD | Model-family conditional prompt guidance — the tool-use enforcement block + GPT/Gemini-specific operational guidance only injected for model families that need it (per `TOOL_USE_ENFORCEMENT_MODELS`). Claude / Opus / Sonnet / Qwen / MiMo run on the shorter prompt. Promoted from Future once v0.5 generates enough multi-model session evidence. | 🔵 |

### Capability maintenance

| ID | Item | Status |
|---|---|---|
| CM.1 | Memory audit CLI — `alpi memory audit` reports docs/code drift signals, low-confidence expiry candidates, duplicate clusters, promotion candidates, and memory usage pressure. | 🔵 |
| CM.2 | Safe skill import — `alpi skill import <dir\|zip>` previews, normalizes, scans, and installs a local skill into the alpi contract; no marketplace, no remote registry. | 🔵 |
| CM.3 | Tool availability checks — add optional `check_fn` probes so unavailable tools can be hidden or flagged consistently when real profiles show broken visible tools. | 🔵 |

### Cost / latency

| ID | Item | Status |
|---|---|---|
| CL.1 | Prompt caching across providers — cached input is ~90% cheaper everywhere; this is the single highest-leverage cost optimization for tool-heavy turns. Provider matrix: **OpenAI** (gpt-4o+/gpt-5.x) caches automatically at ≥1024 tokens, no marker; optional `prompt_cache_key` improves shard hit rate. **Gemini 2.5+** caches implicitly by default. **Anthropic** (`anthropic/*` and `openrouter/anthropic/*`) requires explicit `cache_control: {"type": "ephemeral"}` markers on message content blocks. **OpenRouter** passes through to upstream; same code as the upstream provider. **Ollama / local**: N/A. Work breakdown: (1) cross-cutting — audit `Engine` + `engine._maybe_auto_compact` for any reordering or non-deterministic mutation of the early messages, since stable prefix is the precondition for ALL three caches. (2) Anthropic — add the marker on the system message (biggest win); optionally a second breakpoint on the last tool result. (3) OpenAI — add `prompt_cache_key` derived from `session.id` for better routing. (4) Gemini explicit cache — only if we ever hit a workload where the implicit cache miss rate is measurable; not worth the API complexity otherwise. Measured impact in one of the WHOOP-debug Sonnet turns: ~$0.40-0.50 of the $3.67 was the system prompt re-billed across 26 iterations. Bigger savings on longer / multi-turn sessions. | 🔵 |

### Memory quality (evidence-gated)

| ID | Item | Status |
|---|---|---|
| AI (1.c) | Dedup threshold recalibration — the 70% Jaccard cutoff in `alpi/memory.py::_find_duplicate_index` was an initial guess. Measure near-duplicate density on real session-memory accumulation across multiple profiles, then tighten or loosen. Pure data exercise; the audit produces a single number change. | 🔵 |

### Org-level shared surfaces

| ID | Item | Status |
|---|---|---|
| ORG.1 | Organization workspace — a shared filesystem root visible to every profile in an organization (`organization/agent-organization.md`), so workgroup outputs, brand guides, shared templates, and cross-agent reference docs have a canonical landing zone instead of being trapped inside transcripts or duplicated across profile workspaces. | 🔵 |

### ORG.1. Organization workspace

Today each profile has its own ``cfg.workspace_path`` and the
``organization/`` scaffold is purely a bootstrap concept — there's no
runtime entity per organization, no shared filesystem. Information
that should be team-wide (Vera drafts strategy → Prism + Echo read it,
a workgroup ``#done`` produces an artefact that needs a home, brand
guides / CSVs / templates shared across roles) leaks into workgroup
transcripts as strings or gets duplicated across profile workspaces.

**Three levels of ambition, listed cheapest to most expensive. We
promote based on real demand, not speculative scope.**

1. **Convention only (no code).** Designate one profile as the
   "hub/secretary" of the org; its personal workspace *is* the org
   workspace. Other agents reach it via ``@hub`` (existing
   ``link.ask`` peer model). Zero new infrastructure, zero new trust
   model, zero new protocol. Documented in ``ORGANIZATION.md`` as a
   pattern. Covers the 70% case where the hub naturally orchestrates
   workgroups and is the canonical funnel for their outputs.

2. **Workspace overlay.** ``cfg.workspace_path`` becomes a list:
   ``[profile_workspace, org_workspace]``. File tools (``file_read``,
   ``file_write``, ``search``) read from both, write to the first by
   default, with an explicit ``scope: "org"`` argument for the shared
   root. New config, no new protocol, no new daemon entity. Promote
   when the convention-only pattern starts to feel hacky (e.g. agents
   confused about "is this my doc or the hub's?").

3. **First-class org entity.** ``~/.alpi/orgs/<id>/workspace/`` with
   member profiles, roles (reader / writer / admin), event fan-out on
   change, and shared BA RAG index across profiles. New trust model,
   new permissions UI, new protocol verbs. Significant scope —
   probably its own minor release. Only worth it when a real user
   reports "the overlay can't model what I need".

**Why it waits.** No documented demand from real org users yet.
v0.5 (mobile) and v0.6 (skill curator, ALP.4 already in v0.4.25)
are higher-leverage. Promote the convention into ``ORGANIZATION.md``
opportunistically when someone asks how to share a doc across the
17 agents; the overlay/first-class designs wait for that question to
become frequent.

### AI (1.c). Dedup threshold recalibration

The 70% Jaccard containment cutoff that decides whether a new memory entry is a near-duplicate of an existing one was chosen as a starting point in v0.4 with no production data to calibrate against. By v0.6 users will have weeks/months of accumulated memory across multiple profiles — enough signal to ask the right question: of the writes that today trigger reinforcement, how many are genuine paraphrases vs. false-positive collisions? And of the writes that pass dedup as distinct, how many are actually paraphrases the agent should have reinforced?

**Method.** A small audit pass across real `USER.md` / `MEMORY.md` files at a handful of thresholds (0.5 / 0.6 / 0.7 / 0.8 Jaccard containment), surfacing the near-duplicate pairs at each. Inspect the borderline cases by hand. Adjust the constant.

**Why it waits.** Calibration without data is just renaming the guess. v0.5 (with confidence + reinforcement + sharpened type-routing shipped in v0.4.23) gives the agent the right writes; v0.6 measures whether the dedup machinery around those writes is correctly tuned.

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
consolidating delete records `absorbed_into: <umbrella>` on the archived
skill's frontmatter so the audit trail is intact. Bundled `@alpi/*` skills
and pinned skills (AT) are never touched.

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

### CM.1. Memory audit CLI

`alpi memory audit` is the operator-facing view over the memory quality
machinery. It does not mutate memory by default. It reports:

- current `USER.md` / `MEMORY.md` usage and pressure;
- low-confidence entries eligible for expiry;
- near-duplicate clusters at multiple thresholds;
- operational-state-looking entries that should probably live in sessions,
  not memory;
- queued promotion candidates awaiting preview/apply;
- compaction frequency and ratio distribution, read from
  `logs/compaction.jsonl` — evidence for promoting compaction policy to
  config (or keeping it as constants).

The command is also the natural home for the v0.6 dedup calibration work: run
the audit at 0.5 / 0.6 / 0.7 / 0.8 containment, inspect borderline clusters,
then adjust the cutoff if the data supports it.

**Why v0.6.** v0.5 creates the promotion queue and tightens skill/tool
eligibility. v0.6 adds the review surface once there is enough real memory data
to make audit output meaningful.

### CM.2. Safe skill import

alpi should be able to reuse local skill material from Hermes, OpenClaw, Codex,
or a checked-out Git repository without adopting a marketplace. `alpi skill
import <dir|zip>` is a local, explicit import path:

1. inspect the source and show a preview;
2. reject path traversal, hidden files, symlinks escaping the root, and
   unsupported nested layouts;
3. map compatible files into alpi's flat `scripts/`, `references/`, `assets/`,
   `secrets/`, and `state/` contract;
4. run the same scanner and schema validation as `skill(add_file)` /
   `skill(create)`;
5. install only after explicit confirmation.

**Non-goals.** No remote registry, no automatic dependency install, no silent
update flow, and no external trust database. A user can still `git clone` a
skill repository, inspect it, and import from disk.

### CM.3. Tool availability checks

Some tools depend on runtime capabilities that may be missing in a minimal
profile: browser automation needs Playwright/Chromium, STT needs its speech
stack, TTS may need audio/conversion helpers, and MCP tools depend on
configured servers. v0.6 adds an optional per-tool availability probe once
broken visible tools show up in real use.

The design is deliberately narrower than Hermes/OpenClaw's toolset policy
machinery:

- probes are fast and cached briefly;
- unavailable tools are either hidden from the model or shown in diagnostics
  with a clear reason;
- checks never install dependencies automatically;
- the normal tool implementation remains the source of truth for final runtime
  errors.

**Promotion condition.** Keep this as v0.6 work, not v0.5, unless v0.5 profiles
repeatedly expose tools that fail before doing useful work.

## Future releases

Items worth doing, but not part of the current cycle.

| ID | Item | Status |
|---|---|---|
| BF-8 | Skill versioning / install-update flows — pinned install source, update preview/diff, revision metadata | 🔵 |
| CM.4 | Semantic recall over past sessions — vector/semantic retrieval over session history when `session_search` stops being good enough. | 🔵 |
| TERM.2 | Docker / SSH terminal backends — isolated or remote command execution for unattended profiles once local sandboxing is no longer enough. | 🔵 |
| OPS.1 | Evidence digest — periodic synthetic report that surfaces the signals every evidence-gated roadmap item depends on (approval-prompt frequency, compaction rate, inactive skills, broken tools, promotion-queue backlog). | 🔵 |
| ALP.5 | Blob transfer — `link.put_blob` / `link.get_blob`, content-addressed, chunked AEAD. Depends on real workgroup usage to justify the protocol complexity. | 🔵 |
| ALP.6 | Workgroup search — semantic search over workgroup transcripts via local RAG (pairs with **BA**). Depends on BA landing and workgroups being heavily used. | 🔵 |

### CM.4. Semantic recall over past sessions

Session search is the right first layer: cheap, explicit, and easy to reason
about. Semantic recall over sessions waits until lexical search starts missing
real queries or session volume becomes large enough that users regularly ask
"when did we discuss X?" and cannot find it.

When promoted, reuse the existing local embedding/store primitives instead of
introducing an external memory provider. The first shape is an opt-in session
index plus an explicit recall/search tool; automatic injection only comes later
if manual retrieval proves valuable.

### TERM.2. Docker / SSH terminal backends

Local terminal execution plus optional OS sandboxing is enough for the current
product. Docker and SSH become worthwhile when unattended profiles need
stronger isolation, reproducibility, or a remote machine that the agent can
damage without touching its own code or the user's main workstation.

The first implementation should be conservative: one configured backend per
profile, no provider zoo, no cloud sandbox abstraction, and no automatic
migration of local files. Promote only when a real unattended workflow is
blocked by the current local sandbox.

### OPS.1. Evidence digest

Most of the items in this roadmap promote on evidence — CM.3 ("if broken
visible tools show up"), CM.4 ("when lexical search stops being good enough"),
TERM.2 ("when a real unattended workflow is blocked"), AI(1.c) ("when there is
enough memory data to recalibrate dedup"), BD ("once `agent.log` has a clear
signal"). Today that evidence lives in raw logs and only surfaces when the
creator happens to notice it.

`alpi ops digest [--since 7d]` synthesises the signals into a single report:

- approval-prompt frequency and the top patterns that triggered them (input
  for further `tools.terminal.approval.allowlist` glob entries);
- auto-compact rate, mean before/after ratio per model (read from
  `logs/compaction.jsonl`);
- inactive skills count and reasons (input for `@alpi/home`-style bundling
  and tuning the four eligibility fields);
- tools that failed before doing useful work (the gate condition for CM.3);
- memory promotion-queue backlog and CM.1 audit highlights;
- session-search misses or unanswered "when did we discuss X" queries (the
  gate condition for CM.4).

**Non-goal.** Not a dashboard, not a metrics service, not always-on
telemetry — a stateless `alpi ops digest` command the creator runs every few
weeks to decide which gates have flipped.

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

**Why it waits.** BA (v0.5) provides the RAG primitive, but workgroups
also need to be heavily used enough that scrolling becomes a real
friction. That second condition doesn't hold yet.

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
| AI (3) | Entity memory — structured SQLite store (`entities`/`relations`/`observations`) replacing the markdown memory model, with selective injection per turn instead of full-blob system prompt | Markdown memory hasn't demonstrably broken yet for real users; AI(1) is a quality pass on the existing model. Promote when a user reports `MEMORY.md` is large enough that prompt size / cost becomes a real bottleneck. BA's shared `store` primitive (v0.5) is designed so the migration is incremental when promoted. |
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
