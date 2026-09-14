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

| ID | Item | Status |
|---|---|---|
| COST.1 | Per-pipeline cost telemetry: attribute ledger spend and tokens to a pipeline run, replacing manual checkpoint arithmetic. | 🔵 |
| BG.1 | `alpi doctor` verifies the installed LiteLLM against the pinned version and hashes, catching a supply-chain swap locally (review cadence stays in [OPERATIONS.md](OPERATIONS.md)). | 🔵 |

### Knowledge subsystem

Raised by the 2026-08-28 audit of `alpi/tools/knowledge_base.py`. Invariant
for every item: **the Markdown tree stays the source of truth and SQLite a
derived, rebuildable index.** Recommended order: KB.1 is risk-free and
independent; KB.2 goes next because it loses user data; KB.3 and KB.4 share
`_ensure_schema` and ship together; KB.5 to KB.7 touch lint, links and
frontmatter as one unit; KB.8 closes. Each fix lands with its own test.

| ID | Item | Status |
|---|---|---|
| KB.1 | Drop "OKF" from every model- and user-facing string: the system prompt, the `knowledge` tool description and action text, the maintain synthesizer prompt, the lint message `required OKF file is missing`, `alpi/knowledge/references/*` (including the `## OKF knowledge wiki` heading) and `docs/ARCHITECTURE.md` / `docs/CONFIG.md`. Say "knowledge wiki: Markdown pages under `knowledge/`". The acronym was never expanded anywhere and names no external standard; the model repeats the vocabulary the prompt gives it, so fixing the runtime text alone stops new memories from carrying the term (no sanitizer needed). The `okf_*` tables and the v0.10.9 changelog entry stay. Creator decisions: whether to add a one-line system-prompt guard ("talk about knowledge as the user's own notes; never expose internal format, index or table names") at the cost of tokens on every turn, and whether alpi-mirai memories need a manual `memory replace` sweep (local profiles and promotion queue verified clean). | 🟡 |
| KB.2 | `maintain` no longer truncates existing pages. The synthesizer only sees 700-character search snippets of `related_pages`, and `_apply_maintenance` overwrites the whole file, so any page longer than a snippet shrinks to what the model reconstructed: silent, permanent loss in the one place the user chose to keep things, with no version control underneath. Load the full body of each related page from disk (per-page and aggregate byte caps, same order as the 12 000-character source excerpt) and report `bytes_before`/`bytes_after` per written page so the model can tell the user about a shrink instead of staying quiet. Test: a multi-KB page survives a `maintain` that touches it. | 🟡 |
| KB.3 | Atomic index rebuild. `_ensure_schema` drops the tables and commits before any page is embedded, so a transient embedder failure during `index` with `force` (or after root drift) leaves an empty index committed and the previous one gone; incremental runs are already atomic. Keep drop+create inside the open transaction and commit once at the end of `index_knowledge`. Verify first that the `vec0` and `fts5` virtual tables cooperate inside a transaction; if not, embed everything in memory before touching the database. Test: an embedder raising on the second batch leaves the previous index intact. | 🟡 |
| KB.4 | Make the single-root index honest about `path`. `search` ignores `path` and reads whichever bundle was indexed last, and the auto-index after a `maintain(path=…)` triggers the `root_changed` drop+rebuild that wipes the primary workspace index. `search_knowledge` takes the root, compares it with the stored `knowledge_root` and returns an actionable error on mismatch ("index built for X; run `knowledge(action="index", path=…)` first") instead of results from the wrong bundle; a root change rebuilds only with explicit `force`. Test: index root A, search with `path=B` errors with zero results from A; `maintain` on a foreign root leaves A's index alone. | 🟡 |
| KB.5 | The synthesizer prompt stops steering toward broken links. It shows root-relative paths (`concepts/example.md`) while `_extract_links` resolves page-relative, so a page under `projects/` linking `concepts/x.md` lints as broken, the target as orphan, and `broken=1` rows drop out of search. Page-relative stays canonical (CommonMark, GitHub, Obsidian, VS Code); the prompt declares the convention with a subfolder example (`../concepts/x.md`) and each `related_pages` entry carries a precomputed href to copy rather than infer. Test: a proposal linking across two subfolders lints clean. | 🔵 |
| KB.6 | Lint and apply robustness: normalize path case in the link graph (on APFS a proposed `Concepts/Example.md` lands in the existing `concepts/` and then reports false broken and orphan pages; case-sensitive systems fork a duplicate tree); validate every proposed page before writing any (`_apply_maintenance` stops mid-loop, leaving earlier pages on disk but unindexed and unlogged while the tool reports failure); a symlinked `.md` escaping the root becomes a per-page issue instead of an uncaught `ValueError` that aborts the whole `lint` or `index`; add the `_TOPIC_SUMMARIES` ↔ `TOPICS` symmetry test that `alpi/tools/knowledge.py` claims exists, or drop the claim. | 🔵 |
| KB.7 | Round-trip with external editors. Export already works (opens as an Obsidian vault; GitHub and VS Code render clean); import does not. An unquoted ISO `updated_at`, which a hand edit or Obsidian's properties panel writes, arrives as `datetime` from `yaml.safe_load`, fails the string check, and the page is rejected by lint and purged from the index: accept `date`/`datetime` and normalize to string on read. `_LINK_RE` only sees inline `[t](dest)`: recognize `[[wikilinks]]` and CommonMark reference links for the graph (never emit them, alpi keeps writing standard relative links) and skip fenced code blocks, which today yield real broken-link findings. Note in docs that `type` collides with Hugo's reserved layout key and that the no-orphans rule is alpi's own, the main reason an external vault fails lint. | 🔵 |
| KB.8 | Cover the untested rules: the orphan rule, required `index.md`/`log.md` (every test bundle ships both), root drift across two roots, embedder drift without `force`, attachment resolution in ingest, `_parse_llm_json`, `_update_index`, `_append_log`, `k` bounds, the tool-level `index`/`lint` branches and the OCR paths. Separate PR from the fixes above. | 🔵 |

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
| OKF.1 | Spreadsheet (`.xlsx`) to OKF conversion in the document-publishing path: one Markdown table per sheet, headers from the first row, `type: source`. The container ships neither `openpyxl` nor `pandas`, so this is either a stdlib zip+XML reader or a new image dependency. Promote when a real document set arrives as spreadsheets; the 2026-09 Confluence publishing skill covers Markdown, PDF and Word only. |
| ATT.1 | Keep an attachment when the user asks to. The host already stages every chat attachment under `<home>/host/attachments/tmp/<id>/<name>` and lists those absolute paths in the message for skills to read, but the staging area is swept after 6 hours, so a file the user wants to keep working with across days has to be re-attached. Add an explicit "keep this file" path (a tool or a `save_attachment` skill hook) that copies a staged attachment into `<workspace>/attachments/` and returns the durable path. Promote when a real flow needs a file to outlive the turn; on 2026-09-14 the Confluence publishing flow did not, because it publishes in the same turn. |

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
| True multi-root knowledge index | Partitioning the `knowledge.sqlite` tables by root is a large change for a use case nobody has; KB.4 makes the single-root API honest instead. |
| Renaming the `okf_*` SQLite tables | Internal and never rendered, and the rename runs the drop+rebuild path that KB.3 fixes; revisit only after KB.3 and only with an observable benefit. |
| Hard-rejecting page shrinks in `maintain` | Consolidating is legitimate; KB.2 reports `bytes_before`/`bytes_after` instead of blocking. |
| Root-relative fallback in the knowledge link resolver | Would pass lint while breaking the links in Obsidian, GitHub and VS Code; page-relative stays canonical (KB.5). |
| Renaming the `type` frontmatter key | Invalidates every existing page over a Hugo layout-key collision that will likely never matter; documented in KB.7. |
| Defining what "OKF" stands for | The acronym was coined without a referent; writing an expansion now would invent a retroactive justification. KB.1 removes it. |
