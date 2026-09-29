# Roadmap

Open work for alpi. Shipped work lives in
[CHANGELOG.md](../CHANGELOG.md) — this file never repeats it. For
technical reference of what currently ships, see
[ARCHITECTURE.md](ARCHITECTURE.md).

Audience: the creator ([@soyjavi](https://github.com/soyjavi)) and
any future contributor reading the repo cold.

Legend: 🟡 prioritized · 🔵 optional / demand-gated. Priority is impact,
not permission to start implementation. Remove completed items; do not replace
them with broader work unless a new, evidenced need exists.

---

## Next cycle — isolated conversations, explicit limits, faithful ingest

Every item below was re-checked against the v0.15.26 source on 2026-09-29 and
is still open. A local reproduction confirmed the Word-table loss; the other
findings are source inspection. Fleet incidents are
operator-reported evidence, not independently replayed here.

The next cycle should repair observable failures, not add another orchestration
layer or reopen settled product decisions. The items below are bounded
fixes; each can ship independently. The order below is also the commit plan:
nine commits, with only KB.11 and KB.13 grouped. Each implementation includes
its tests, relevant docs, bump and changelog. UX.7 and UX.8 release desktop; the
other groups release alpi unless their implementation also changes a client.
Do not bundle unrelated work just because it is ready at the same time.

| Order | ID | Priority | Evidence | Outcome |
|---|---|---|---|---|
| 1 | TERM.3 | P3 · 🟡 | A Morpheus terminal command could not find the skill's volume JDK | Explicit profile environment reaches foreground, background and Docker commands. |
| 2 | KB.11 + KB.13 | P2 · 🟡 | Source text is silently cut at 12000 characters; Word tables are discarded | Ingest reports its cut and preserves ordinary Word tables in document order. |
| 3 | UX.7 | P3 · 🟡 | Storage repeats inventory bytes under separate reclaim/delete rows | One inventory with safe and individually confirmed destructive actions on each group. |
| 4 | KB.14 | P3 · 🟡 | The index uses mtime/size to decide whether to embed again | Unchanged content does not cause another paid embedding. |
| 5 | ATT.2 | P2 · 🟡 | `host.attachments.fetch` checks roots, never the caller; agora filters on its side | On a `session_scope: device` connection a device fetches only files it produced or staged. |
| 6 | AUTH.1 | P3 · 🟡 | One revoked device retrying from agora's address spends the auth budget of every agora user | A failure that names a device is throttled per device; anonymous failures stay per address. |
| 7 | UPD.1 | P3 · 🟡 | Desktop offers **Update alpi** on a Docker daemon that can never self-update, then prints a hint that is wrong for a pinned image tag | Clients know before the click whether a daemon can self-update and show the one correct manual step when it cannot. |
| 8 | UX.8 | P3 · 🟡 | The Usage bars are sized by tokens while the headline and the cap are in dollars | The chart shows the number the owner watches: cost when there is any, tokens otherwise. |
| 9 | SCHED.6 | P3 · 🟡 | `tick` stamps `last_run_at` for every job it fired only after the whole pass, with the pass's start time | A job that finished is stamped at once; a daemon restart during a later long job does not fire it again. |

### TERM.3 — let a profile hand `terminal` extra environment variables

**Evidence.** [terminal.py](../alpi/tools/terminal.py) builds the subprocess
environment itself; [CONFIG.md](CONFIG.md#tools) exposes the backend, the
sandbox, network and the approval allowlist, but no way to add variables.
A skill runner that installs its own toolchain into the volume (the Java
`repo-task` keeps JDKs and Maven under `/data/toolchains`) exports
`JAVA_HOME` and a `PATH` prefix only to the subprocesses it spawns; the
agent's own targeted commands through `terminal` see neither. In a
2026-09-22 Morpheus run the agent tried to discover them and the sandbox refused the
command as `dangerous pattern: dump environment`; it recovered by spelling
absolute paths, which every future Java task would have to repeat.

**Smallest change.** A `tools.terminal.env` map in the profile config
(`JAVA_HOME`, `PATH` and the like), applied on top of the environment the
tool already builds, with `PATH` prepended rather than replaced. Values are
plain strings; no secret expansion, no reading of `.env` keys into the
shell, and the existing sandbox and allowlist apply unchanged.
Do not let the map override Alpi's internal execution/ownership markers.
Docker has an explicit environment forwarding list: changing only the parent
`Popen` environment is not sufficient for that backend.

**Acceptance.** A profile with the map runs `java -version` through
`terminal` and finds the volume JDK; a profile without it is byte-for-byte
unchanged; `PATH` keeps the original entries after the prefix; the map is
listed in the takes-effect table and the packaged config reference. Test
foreground/background, native sandbox and Docker forwarding, invalid map
values, and protected internal variables. Preserve the backend's own PATH
when adding its prefix, not a host PATH that may not exist inside the image.

### KB.11 + KB.13 — preserve source content and report deliberate cuts

**Evidence.** [knowledge_base.py](../alpi/tools/knowledge_base.py) sends
`source_text[:12000]` without truncation metadata. The shared Word reader in
[workspace.py](../alpi/tools/workspace.py) reads `doc.paragraphs` only; a local
DOCX with a paragraph and a table loses the table. These are two small source
fidelity fixes, not new knowledge capabilities, and belong in one commit.

**Smallest change.** Keep the existing source budget, but tell both the
synthesizer and the tool caller whether it was cut, how many characters were
available and how many were used. Preserve ordinary Word tables and their
order relative to paragraphs using the existing `python-docx` dependency.
Do not add chunked synthesis, vision, translation or another document library.

**Acceptance.** Sources below, at and above the limit report accurate counts
in preview and apply results; the model sees the cut too. A paragraph/table/
paragraph fixture retains text in order, with explicit handling of empty and
merged cells and no claim of full Word layout fidelity. Exercise the shared
reader and the ingest path, plus regressions for its other consumers. The
existing protection of truncated related pages against overwrite remains.

### UX.7 — make the desktop Storage field one inventory again

**Evidence.** [maintenance.jsx](../desktop/src/features/settings/fields/maintenance.jsx)
renders three unrelated lists under one heading: a usage row per group in
`STORAGE_GROUPS` (up to seven), then a `reclaim` row with a single **Clean**
button for every non-destructive member of `host.cleanup.plan`, then a
`delete` row per destructive member (old sessions, mentions, run journals,
workgroup history, generated files). Fully populated that is thirteen rows,
five of them labelled `delete`. On 2026-09-24 a small local profile showed
nine: six usage rows, `RECLAIM · Clean · 571 KB · 19 items · caches, logs and
knowledge — always safe`, and two `DELETE` rows (`chats older than 30 days`,
`all @-mention threads`). Three things make it unreadable:

- The row label is the verb, not the target, so consecutive rows read
  `DELETE / DELETE` and the target is demoted to a muted note.
- The reclaim row re-counts bytes already shown above it (the 571 KB is part
  of Logs and Knowledge) without saying which rows would shrink; the user sees
  the same storage twice and cannot map one to the other.
- The safe / destructive split is real (`destructive: true` marks user content
  with a retention cut: chats and generated files older than 30 days, run
  journals, every mention thread, every workgroup transcript; the rest is
  regenerable) but the UI expresses it as two different sections instead of a
  property of the row it belongs to. The daemon already tags every plan member
  with its group (`GROUP_OF` in [cleanup.py](../alpi/cleanup.py)) and the
  component already builds `planByGroup`; the data to fold them is there.

The console (`alpi setup → Cleanup`) shows the same plan as one menu: **Clean
all safe** plus one entry per destructive category marked ⚠. Mobile's
`CleanupSheet` is a separate sheet with one row per member. Three surfaces,
three shapes, one contract.

**Smallest change.** Desktop rendering only; `host.profile.storage`,
`host.cleanup.plan` and `host.cleanup.apply` stay as they are, so console and
mobile are untouched. Each group row keeps its size and file count and gains,
on the same row, its reclaim actions: one **Clean** chip totalling the group's
safe members, plus one **Delete** chip per destructive member, named after the
target ("chats older than 30 days", "run journals") and confirmed. Groups are
mixed, so actions are never merged across members: Logs shows Clean plus
Delete run journals; Conversations shows three named Deletes and no Clean;
Files shows Clean plus Delete generated files. The standalone `reclaim` and
`delete` rows go away; one **Clean everything safe** summary may stay as a
single line if a real user misses the one-click sweep. Drop the "always safe"
prose; the chip placement says it. No new component library, no new verb.

**Acceptance.** With every category populated the field renders no more rows
than there are non-empty storage groups plus at most one summary line; no two
rows share a label. Every destructive plan member with something to reclaim
stays individually actionable; safe members are grouped per inventory row.
The per-row amounts sum
to the sweep total. Destructive actions still open `ConfirmDelete`; the safe
members of one group are one click; the admin-only gate (`canClean`) is
unchanged. `maintenance.test.jsx` covers the folded layout with a mixed group
and the desktop changelog entry pins no new alpi minimum.

### KB.14 — avoid re-embedding unchanged content

**Evidence.** [knowledge_base.py](../alpi/tools/knowledge_base.py) compares
mtime and size before deciding to skip a file. A metadata-only change therefore
re-embeds unchanged text. The fleet reports 274 pages taking 444 seconds after
a move; that timing was not independently reproduced.

**Smallest change.** Compare a content fingerprint before paying for another
embedding. Cover all content that affects the indexed page, not just its body;
an embedder change or explicit force still follows its existing rebuild
contract. Keep the single-root store and transactional rebuild. Limit schema
work to the metadata needed for this decision; no generalized index framework.

**Acceptance.** A touched unchanged page does not call the embedder; changed
text with the same size and restored mtime is not silently skipped. Metadata
changes update the index correctly. Existing indexes without a fingerprint
remain usable and acquire it on indexing without dropping unrelated tables.
Failure still rolls back the pass. Test with a counting embedder and real
SQLite, not timing or external API calls. Keep this separate from ingest fixes.

### ATT.2 — scope `host.attachments.fetch` to the device that owns the file

**Evidence.** `_fetch` in [attachments_rpc.py](../alpi/host/attachments_rpc.py)
checks only that the resolved path sits under `servable_roots` (images anywhere
under the profile home, `/tmp` or the workspace; documents under the staging
area, `out/` or the workspace) plus the secrets denylist; it never checks who
asks. Since 0.15.20 sessions are private per device when a connection runs
`session_scope: device` ([connection_context.py](../alpi/host/connection_context.py),
`_device_clause`), but produced files are not: any device of the connection that
learns or guesses a path such as `<workspace>/summary.md` downloads another
user's file. agora (one device per person on `agora-server` and
`alexandra-server`) closes the gap on its side by relaying only paths the daemon
already sent to that user; other clients get no such barrier.

**Decision.** For a remote caller on a `session_scope: device` connection,
`host.attachments.fetch` serves a path only if that device may see it: the path
appears in a session the device owns (`owns_session`) as a turn's
`attachments`, `output_attachments`, tool result or assistant text (so inline
images keep working), or the device staged it itself (`_stage` records the
owning `device_id` next to the staged file and `_fetch` reads it back). Admin,
local callers and `session_scope: connection` keep today's behaviour. Keep the
existing roots and the secrets denylist as the first barrier, and answer a
refused path with the same `-32001 forbidden` / `path not readable` as today, so
the error does not reveal whether the file exists. Do not rescan transcripts on
every call: keep a per-device index of offered paths, updated when a session is
saved and rebuilt lazily.

**Acceptance.** Two devices of one `session_scope: device` connection: A
produces `out/report.md` and can fetch it; B gets `forbidden` for that path and
for A's staged upload. On a `session_scope: connection` connection both fetch it,
as today. An image an assistant turn referenced stays fetchable for the device
that owns the session. Sessions saved before 0.15.20 (no `device_id`) stay
fetchable for every device of the connection, like the sessions themselves.
Admin and the Unix socket are unaffected.

### AUTH.1 — count a rejected known device against that device, not the shared address

**Evidence.** `_handle_websocket` in [server.py](../alpi/host/server.py) closes
every new socket from a source with 1013 once it records
`WS_AUTH_FAILURES_PER_MINUTE` (10) failures in a minute; the source is the socket
peer, or the `X-Forwarded-For` client when the peer is listed in
`ALPI_HOST_WS_TRUSTED_PROXIES`. A multi-user front end such as agora reaches alpi
from one address for all its users, so one person whose device was revoked or
whose token expired, with a client that keeps retrying, spends the budget of
that address and locks every other user out for a minute. `authenticate` in
[connections.py](../alpi/host/connections.py) already names the device for
`token-expired` and `connection-disabled`, but skips revoked devices
(`status != "active"`) and returns an anonymous failure, so a revoked known
device cannot be told from a stranger's guess. agora holds a rejected user back
on its side (1 min doubling to 15), which every front end would have to copy.

**Decision.** `authenticate` also matches the presented hash against revoked
devices and returns `reason="device-revoked"` with its `device_id` (still a
failure; the answer to the client does not change). The auth-failure limiter
counts a failure that names a device against that device, with the same limit
and window; only anonymous failures (unknown or missing token, malformed frame)
count against the source address as today. A device over its limit is closed
with the existing `auth-rate-limited` reason without spending the address
budget. Log `device-revoked` in the audit trail like the other reasons. Leave
`ALPI_HOST_WS_TRUSTED_PROXIES` as it is; it stays the fix for front ends that
can forward a real client address.

**Acceptance.** From one address, a revoked device retried 30 times in a minute
is throttled while a second, valid device from the same address keeps
connecting; ten unknown tokens from that address still close the address as
today; `token-expired` and `connection-disabled` also count per device; the
error sent to the client stays `auth-failed` with its existing reasons plus
`device-revoked`.

### UPD.1 — say before the click whether a daemon can update itself

**Evidence.** On 2026-09-29 the creator pressed **Update alpi** in desktop
Settings → Service against the mirai EC2 daemon (Docker, compose pinned to
`satoshiltd/alpi:0.15.25`, PyPI already at 0.15.26) and got *"Can't self-update
this installation. Docker: run docker compose pull, then docker compose up -d."*
The path: `host.daemon.update` ([daemon.py](../alpi/host/daemon.py)) calls
`updater.update_now()`; `_detect_installer()` in
[updater.py](../alpi/updater.py) returns `uv` or `pipx` only when `uv tool
list` / `pipx list` names the package, otherwise `dev`, and `dev` has no upgrade
command, so the answer is `reason: "manual"`. The image runs `pip install .` as
root ([Dockerfile](../docker/Dockerfile)) and the daemon runs as uid 1000, so a
container always lands there. Refusing is correct (an in-container upgrade
would be lost on the next recreate); the defects are around it:

- Nothing tells the client in advance: `host.version`
  ([device_state.py](../alpi/host/device_state.py)) reports `update_available`
  but not whether the daemon can act on it, so desktop shows the button and the
  connections list shows an update badge on every Docker daemon.
- The hint is wrong for a pinned tag: `docker compose pull` re-fetches the same
  version; the tag in `docker-compose.yml` has to change first.
- `dev` lumps a Docker image, a source checkout and a plain pip install
  together, although the image already sets `ALPI_PLATFORM=docker`.
- Three different texts for the same answer: desktop
  [DaemonField.jsx](../desktop/src/features/settings/fields/DaemonField.jsx),
  mobile [daemonUpdate.js](../mobile/src/features/settings/daemonUpdate.js) and
  mobile [ConnectionSheet.jsx](../mobile/src/features/sheets/ConnectionSheet.jsx)
  ("Image-pinned (Docker) — repull the image").
- The comment in `_daemon_update` says a restart keeps the container's writable
  layer, implying an in-container upgrade the updater never performs.

**Smallest change.** The updater names the install kind (`uv | pipx | docker |
source`, `docker` from `ALPI_PLATFORM`) and `host.version` adds `self_update:
bool` next to `update_available`. Clients show **Update alpi** only when
`self_update` is true; otherwise the same row (and the badge tooltip) shows one
shared manual step from `common/`: for `docker`, "set the image tag to
`X.Y.Z` in docker-compose.yml, then `docker compose up -d`"; for `source`,
"git pull and restart the daemon". `alpi update` in the console prints the same
text. No in-container upgrade, no compose editing from the daemon.

**Acceptance.** A Docker daemon reports `self_update: false` and
`installer: docker`; desktop and mobile hide the button and show the tag step
with the latest version filled in; a uv/pipx daemon keeps today's one-click
flow; a daemon older than this change (no `self_update` field) keeps today's
behaviour. One hint string, covered by both client suites; updater tests cover
each install kind with the environment and subprocess stubbed.

### UX.8 — chart usage by money when the profile pays for it

**Evidence.** The desktop Usage panel
([Usage.jsx](../desktop/src/features/settings/Usage.jsx)) sizes each day's bar
by tokens (`maxTok`) and shows the cost only in the tooltip, while the headline
and the daily cap are in dollars. With prompt caching the two diverge: on
2026-09-25 curator's day was 276M input tokens for $24.88 of a $40 cap, so the
bars say nothing about the number the owner watches. The ledger already keeps
cost and tokens per day ([ledger.py](../alpi/ledger.py)). Requested by the
creator on 2026-09-26.

**Smallest change.** Scale the bars by cost when the window has any cost, and by
tokens when every day costs nothing (free or local models). Desktop only; no new
verb.

**Acceptance.** A window with costs draws bars proportional to dollars and the
tooltip still shows both numbers; an all-free window draws tokens as today; the
desktop changelog entry pins no new alpi minimum.

### SCHED.6 — stamp each fired job when it finishes, not when the pass ends

**Evidence.** `tick` in [scheduler/run.py](../alpi/scheduler/run.py) runs the
due jobs of a profile one after another, collects them in `fired`, and writes
`last_run_at` / `last_run_status` for all of them in one `jobs_store.update`
after the loop, stamped with the time the pass started. Since v0.15.27 one fire
may run for up to 86400 s. If the daemon restarts while a later job of the same
pass is still running, the jobs that already finished never get their stamp and
fire again on the next start (a second delivery), and listings show them as due
until the pass ends. Found in the SCHED.4 review; source inspection, not
reproduced in production.

**Smallest change.** Stamp each job right after its `run_job` returns, with the
same `jobs_store.update` rules (first-seen, one-shot removal on success, stamp
on failure). Keep the serial pass; no new state.

**Acceptance.** With two due jobs where the second is still running, the first
is already stamped in `jobs.json`; a simulated restart after the first job does
not fire it again; one-shot and failure semantics are unchanged.

### Verification required to close this cycle

- Add a failing regression for each item, then prove the fix; a green suite
  without the reproduced failure is not closure.
- `publish.yml` runs only `pytest -q`: run the relevant integration tests for the
  exact release SHA before publishing, including direct-to-main releases.
- ATT.2 and AUTH.1 are proven over real WebSockets with two devices of one
  connection, not only through handler calls; UX.7 and UX.8 run both client
  suites and check the rendered desktop.
- No new runtime dependency, RPC framework or persisted state is presumed
  necessary; KB.14's index field does not authorize a persistence redesign.
- Large files alone are not defects: extract a helper only when it removes an
  evidenced duplication.

---

## Backlog — demand-gated

Only plausible next moves stay prominent. Everything here waits for observed
usage or a concrete blocker; standing maintenance belongs in
[OPERATIONS.md](OPERATIONS.md), not in the product backlog.

### Candidates

| ID | Candidate and promotion condition |
|---|---|
| SK.2 | Safe skill import (`alpi skill import <dir\|zip>` with preview, scan, and install). Promote when users repeatedly exchange skills outside their own profile. |
| SK.3 | Let a profile lock its own skills against its file tools. The denylist in [_paths.py](../alpi/tools/_paths.py) protects `config.yaml`, `.env` and skill `secrets/`, and keeps `skills/` away from members, but the profile itself can rewrite the scripts that enforce its own gates. On 2026-09-22 a scheduled Morpheus pass edited its `repo-task` runner mid-run, left a `run.py.bak`, fixed a real toolchain gap and broke one of the skill's tests; the live copy diverged from the fleet repository. Today the only guard is a sentence in `AGENT.md`. Opt-in only (inline skill updates are a product choice): a profile setting under which `write_file`, `edit_file` and the skill tool's write actions refuse the profile's own `skills/`. Promote when a second unattended profile edits its own skill, or when a fleet needs that guarantee enforced rather than asked for. |
| KB.10 | A language policy for `knowledge(action="ingest"\|"maintain")`. `_MAINTAIN_PROMPT` in [knowledge_base.py](../alpi/tools/knowledge_base.py) says nothing about language, so a synthesized page follows its source; a profile whose knowledge must be English cannot get that from the tool. On 2026-09-24 agora's audit found 239 Spanish titles and 152 pages with Spanish lines, and the fleet now routes every agora write through a skill gate instead of the tool. A `knowledge.language` setting passed to the prompt and checked on the proposal would do. Promote when a second profile needs a fixed knowledge language, or agora goes back to the tool for curation. |
| KB.12 | Vision in knowledge ingest. An image reaches `knowledge(action="ingest")` only with `ocr=true`, which keeps its text and loses everything a diagram or screenshot shows; `tools.read_image.model` is never used there. On 2026-09-24 agora needed a skill (read the image with `read_image`, store it as an asset, write an OKF page that embeds it) to keep diagrams. Promote when a second profile wants images kept as knowledge. |
| TIER.1 | A model tier per task, not only per job. A job's `tier` sets `ALPI_TIER` for its whole turn ([scheduler/run.py](../alpi/scheduler/run.py), read in `engine.py`), but a chat turn always runs on the main model. agora's nightly Confluence ingest runs on `deep` (`:nitro`, effort high), while the same writes asked from chat (a PDF, "add", "fix", "remove" through the `okf` and `confluence-ingest` skills) run on the default model. A skill-level `tier` that raises the rest of the turn once that skill runs would separate knowledge writes from questions. Promote when a second profile mixes cheap questions with quality-sensitive writes in chat. |

---

## Decisions discarded — don't relitigate

| Decision | Reason |
|---|---|
| Vendor subscription OAuth | alpi respects every provider's ToS: a subscription tied to a vendor's own client is for that client, and reversing its private OAuth flow is a ToS violation and an account-ban risk. Users pay per token with their own keys; an official, documented third-party OAuth flow would be adopted. |
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
| Longer-context embedder or smaller chunks (KB.15) | Measured 2026-09-26 on agora (13.5K chunks, 81 queries): all-MiniLM-L6-v2's 128-token cut loses no answers because hybrid search (bm25 over the full chunk) finds the page and the agent reads the file; 12-line chunks cost +39% index size, bge-small 10x indexing CPU. |
