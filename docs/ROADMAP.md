# Roadmap

Open work for alpi. Shipped work lives in
[CHANGELOG.md](../CHANGELOG.md) — this file never repeats it. For
technical reference of what currently ships, see
[ARCHITECTURE.md](ARCHITECTURE.md).

Audience: the creator ([@soyjavi](https://github.com/soyjavi)) and
any future contributor reading the repo cold.

Legend: 🔵 backlog · 🟡 next up · ⏸ blocked · 🔴 gate.

---

## v0.16 — production client exposure

The public host channel already ships: WSS routes, one-time pairing,
per-device revocation, role/profile scope, abuse bounds, device tokens hashed
at rest with optional inactivity expiry, per-source authentication-failure
throttling, Docker/Caddy topology, and attributed administrative activity. The
token hardening shipped in v0.14.39 to v0.14.42; this cycle adds no further
security layer to that protocol. The channel is live on a customer deployment
behind a public terminating proxy, with the daemon's own ports unreachable from
outside it.

What remains is runtime work: what an external tenant would either be exposed to
or read and act on, and every item is a defect confirmed in the shipped code.

| ID | Item | Status |
|---|---|---|
| SANDBOX.1 | Make the OS sandbox effective inside the managed Docker runtime. `tools.terminal.sandbox` defaults to false, the shipped image installs no `bubblewrap`, and the Linux wrapper refuses rather than isolates when `bwrap` is absent — so `terminal` there runs unwrapped with the whole container readable, and the `docker` execution backend is equally unavailable. [DEPLOYMENTS.md](DEPLOYMENTS.md) already tells an enterprise operator to push `tools.terminal.sandbox: true` into every profile at onboarding; on the shipped container that turns every `terminal` call into a refusal instead of a sandboxed run. The promotion condition has fired: a profile that denies neither `terminal` nor everything else, reached by a connection whose empty `profile_scope` the device store treats as unrestricted, already has the container as its only wall. | 🟡 |
| ALP.9 | `alp.max_active_workgroups` is an admission threshold, not a cap. It is compared against the active count in exactly one place — the pipeline queue drain — so anything that re-enters the active set without going through a trigger bypasses it. Pausing a workgroup frees the slot, the drain admits a queued pipeline, and resuming brings the paused one back unchecked; so does the daemon's own QA rewind, and so does a plain `#task` re-opening a pipeline that closed `#done BLOCKED`. An operator who set the limit to bound provider concurrency gets N+1 running pipelines with no warning. Either re-check capacity on re-entry, or stop calling it a cap in [CONFIG.md](CONFIG.md). | 🔵 |

SANDBOX.1 is the precondition for a second, mutually untrusted tenant: isolation
cannot be claimed while an unrestricted member connection reaches an unsandboxed
`terminal`.
Credential-loss and backup-exposure response is already defined in
[OPERATIONS.md](OPERATIONS.md); enterprise-grade external audit remains
demand-gated as `AUDIT.2` below.

---

## Backlog — demand-gated

Only plausible next moves stay prominent. Everything here waits for observed
usage or a concrete blocker; standing maintenance belongs in
[OPERATIONS.md](OPERATIONS.md), not in the product backlog.

### Candidates

| ID | Candidate and promotion condition |
|---|---|
| TERM.2 | SSH terminal backend for remote command execution. Promote when an unattended profile needs to operate on a remote machine. |
| AUDIT.2 | Enterprise audit and accountability: complete local mutation coverage, then add tamper-evident external records, provider policy, encryption, or RBAC only when a real fleet or compliance regime requires them. |
| ALP.7 | Pinned shared memory per workgroup (`wiki.md`). Promote when sustained workgroup use shows that the transcript is no longer enough. |
| SK.2 | Safe skill import (`alpi skill import <dir\|zip>` with preview, scan, and install). Promote when users repeatedly exchange skills outside their own profile. |
| AI (3) | Structured entity memory with selective injection. Promote when keeping the markdown store coherent becomes a repeated source of defects or selective recall is required. |
| TTS.1 | Host-served local TTS and a single voice catalog. Promote when voice becomes a sustained client surface. |
| KB.9 | Spreadsheet (`.xlsx`) ingest into knowledge pages: one Markdown table per sheet, headers from the first row, `type: source`. The container ships neither `openpyxl` nor `pandas`, so this is either a stdlib zip+XML reader or a new image dependency. Promote when a real document set arrives as spreadsheets; the 2026-09 Confluence publishing skill covers Markdown, PDF and Word only. |
| ATT.1 | Keep an attachment when the user asks to. The host already stages every chat attachment under `<home>/host/attachments/tmp/<id>/<name>` and lists those absolute paths in the message for skills to read, but the staging area is swept after 6 hours, so a file the user wants to keep working with across days has to be re-attached. Add an explicit "keep this file" path (a tool or a `save_attachment` skill hook) that copies a staged attachment into `<workspace>/attachments/` and returns the durable path. Promote when a real flow needs a file to outlive the turn; on 2026-09-14 the Confluence publishing flow did not, because it publishes in the same turn. |

### Watchlist

These ideas remain recorded without presenting them as likely next work.

| ID | Revisit only when |
|---|---|
| BROWSER.1 | A vetted lightweight backend passes real acceptance and the headless-shell footprint (344 MB since v0.14.9, down from 984 MB) still blocks a target host. |
| ALP.8 | Per-profile capacity (`alp.max_active_workgroups`) and a durable admission queue already ship; users need dynamic worker pools or cross-peer capacity negotiation on top of them. |
| ALP.3+ | Persistent workgroups demonstrate sustained parallel tasks that targeted tasks and pipeline continuation cannot cover. |
| AY / BF-8 | A real skill author or import community needs a federated marketplace, versioning, or update flows. |
| AQ | A real voice surface needs continuous push-to-talk or hotword loops on top of the read-aloud path that already ships (host-served synthesis, per-profile voice, auto-read). |
| UX.6 / External secrets | A masked, auditable editor for arbitrary `.env` keys (the RPC already writes any key; only provider keys are listed back), or central key rotation, becomes repeated friction. |

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

See **Why alpi exists** in [README.md](../README.md) for how the
publisher's principles map to concrete choices in this repo.

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
| `.bak` sibling on every `write_file` | Too much workspace clutter; backups stay limited to memory and skill files. |
| Profile identity wizard / starter packs | Profiles are shaped through chat and examples, not binary templates. Unrelated to the shipped `setup → Identity` screen, which only sets the ALP public bio. |
| Default skills bundle | Runtime capabilities are first-class tools; skills are user-owned. |
| `alpi run "<prompt>"` | Covered by `alpi chat --once "<prompt>"`. |
| Auto-reflect on Ctrl+C / post-session `/reflect` | Unsafe or redundant; inline memory/skill updates are the path. |
| TUI accessibility pass | Desktop is the right accessible surface; terminal APIs are weaker. |
| `duckduckgo-search` | Deprecated; migrated to `ddgs`. |
| True multi-root knowledge index | Partitioning the `knowledge.sqlite` tables by root is a large change for a use case nobody has; v0.14.44 made the single-root API honest instead: the index names the one bundle it holds, refuses to be replaced by another, and `force=true` retargets deliberately. |
| Renaming the `okf_*` SQLite tables | Internal and never rendered; the rename runs the drop and rebuild path, which v0.14.44 made transactional, so the only bar left is an observable benefit and there is none. |
| Hard-rejecting page shrinks in `maintain` | Consolidating is legitimate; `maintain` reports `bytes_before`/`bytes_after` per written page instead of blocking. |
| Root-relative fallback in the knowledge link resolver | Would pass lint while breaking the links in Obsidian, GitHub and VS Code; page-relative stays canonical (KB.5). |
| Renaming the `type` frontmatter key | Invalidates every existing page over a Hugo layout-key collision that will likely never matter; the docs note the collision instead (KB.7). |
| Defining what "OKF" stands for | The acronym was coined without a referent; writing an expansion now would invent a retroactive justification. It is gone from every model- and user-facing string; only the `okf_*` table names keep it. |
