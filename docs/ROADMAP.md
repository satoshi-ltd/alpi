# Roadmap

Open work for alpi. Shipped work lives in
[CHANGELOG.md](../CHANGELOG.md) — this file never repeats it. For
technical reference of what currently ships, see
[ARCHITECTURE.md](ARCHITECTURE.md).

Audience: the creator ([@soyjavi](https://github.com/soyjavi)) and
any future contributor reading the repo cold.

Legend: 🔵 backlog · 🟡 next up · ⏸ blocked · 🔴 gate.

---

## v0.3 — public release

Three items left before the cut. Everything else previously parked
under v0.3 moved to v0.4 — none of it can land honestly in the
remaining window.

| ID | Item | Status |
|---|---|---|
| ALP.3 | Alpi Link Protocol — shared workgroups (collaborative spaces, humans optional) | ✅ shipped (PR 5 closes functional autonomy) |
| AU | Distribution — `uv tool install alpi`, `alpi update`, end-user install without source | 🔴 gate |
| SU | Service unification — single ``alpi service`` orchestrator per profile (replaces gateway/schedule/alp daemons) | ✅ shipped (was tracked for v0.4 architecture cleanup, brought forward) |

### ALP.3 — Shared workgroups

Depends on ALP.1 + ALP.2 (shipped) and the profile-level budget
ledger (shipped). First-class collaborative workspaces — N alpis
(different profiles, different machines) post into a shared
transcript; a human can join via the TUI or stay out entirely. Hub
model (the workgroup creator holds transcript + group key), not
gossip. Per-workgroup budget and pause switch as safety levers; posts
are double-gated against both profile and workgroup budgets. Verbs:
`workgroup.create`, `workgroup.join`, `workgroup.post`,
`workgroup.pull`, `workgroup.leave`, `workgroup.pause`; rekey on
member leave.

**PR 5 (functional closure)** lands the engine integration: each
member's service runs a workgroup poller that wakes the agent on
new posts; every interactive / gateway / scheduled turn auto-pulls
subscribed workgroups before running and injects the briefing +
recent transcript + active task as system prompt context. Two
in-chat markers, parsed client-side on the decrypted transcript:
`#task <text>` opens the active task (preempts the previous one
with synthetic result `"preempted by …"`), `#done <text>` closes
it. The hub stays zero-knowledge — task state is computed locally
from the post stream. Single-task model only; multi-task is
tracked separately for v0.4.

**v0.3 backlog (ALP.3 follow-ups, queued after PR 5):**

- **Workgroup roles** — optional ``roles: dict[peer_id, str]`` in
  ``meta.yaml`` so the workgroup creator publishes a one-line role
  hint per invited member (``alice: "product engineer — velocity"``
  / ``bob: "systems engineer — durability"``). The hub returns it
  on ``workgroup.join``, members cache it in their subscription,
  and the engine pre-turn hook surfaces it alongside the briefing.
  Lets every agent see the roster of who-does-what so misdirected
  tasks ("@bob frontend please") can be redirected with confidence
  instead of accepted blindly. AGENT.md stays private; ``roles`` is
  just the public-facing tag-line. No protocol change beyond a
  metadata field. Estimated ~50 LoC + tests.

- **Active liveness probes** (optional follow-up to passive
  liveness shipped in PR 5) — passive ``last_seen_at`` is in
  place: the hub stamps it on every ``workgroup.pull`` /
  ``workgroup.post`` and returns the roster on ``join`` /
  ``pull``; the engine pre-turn hook tags peers as ``online`` /
  ``last seen N min ago`` / ``offline (>30 min)``. If passive
  proves unreliable in the wild, layer an active probe via
  ``link.ping`` with a 500 ms timeout, but only on the wizard's
  "show members" view — never on every engine turn (would blow
  turn latency).

### AU — Distribution + update path

Today alpi is installed by cloning the repo and running `uv sync`. A
public release needs an end-user path that does not require git or
the source tree. Three deliverables:

1. **`uv tool install alpi`** — publish the package on PyPI so a
   plain `uv tool install alpi` (or `pipx install alpi`) lands a
   working `alpi` binary in the user's PATH. The package is already
   PyPI-shaped (`pyproject.toml` has `[project.scripts] alpi = …`);
   the missing pieces are the publish workflow, the trusted-publisher
   config on PyPI, and a smoke-test that asserts a fresh-machine
   install actually launches.

2. **`alpi update`** — a single command that bumps the user's
   installation to the latest release. Implementation is a thin
   wrapper around `uv tool upgrade alpi` (or `pipx upgrade`) with a
   pre-flight check against PyPI's JSON API (`/pypi/alpi/json`) to
   announce the version delta and the changelog link before pulling.
   Falls back gracefully on networks without PyPI access.

3. **Versioning + release process.** Document the cut: tag
   `v0.3.0`, build, publish, GitHub release with the CHANGELOG
   excerpt as body. Once the workflow is green, every patch bump
   (`v0.2.86 → v0.2.87 → …`) flows through the same pipeline so
   `alpi update` is meaningful and not a one-off.

**What's intentionally not in scope:** auto-update on launch (would
contradict the "no hidden network" principle), Homebrew formula
(double the maintenance for a uv-first tool), platform-specific
installers (macOS .pkg, Windows MSI). Users on those platforms get
alpi via `uv` like everyone else.

---

## v0.4 cycle

The v0.4 surface is wider on purpose: alpi v0.3 is a credible
private-agent tool; v0.4 is where the Satoshi positioning earns
recurring use. Items split into three groups — **hardening** (close
the loops we know are open), **commercial recorrido** (visible
roadmap for early users), and **deferred research** (work that needs
measurement before scope locks).

### Hardening

| ID | Item | Status |
|---|---|---|
| BC | External security audit before public release | 🔴 ships before v0.4 cut |
| AV | Per-skill env scoping — close the residual `os.environ` enumeration vector | 🔵 |
| AW | Encrypted profile backup/restore — zero-knowledge passphrase-encrypted archive of `~/.alpi/<profile>/` | 🔵 |

### Commercial recorrido

| ID | Item | Status |
|---|---|---|
| ALP.4 | Streaming `link.ask` — SSE-style chunked replies between peers | 🔵 |
| ALP.5 | Blob transfer — `link.put_blob` / `link.get_blob`, content-addressed, chunked AEAD | 🔵 |
| ALP.3+ | Multi-task workgroups — `multitask: true` in meta, letter-prefixed task IDs (`#task A …`, `#done A: …`) so several streams can run in the same workgroup | 🔵 deferred from v0.3 — emerges only when single-task in real use shows it's not enough |
| AX | Mobile / desktop companion — minimal client speaking ALP to the user's profile | 🔵 |
| AY | Skills marketplace — federated, signed, never centralised | 🔵 |
| AZ | Workgroup viewer — folds into AX (companion app surfaces the transcript read-only or read/write) | 🔵 |
| BA | Local RAG over `workspace/` — local-only embeddings (sentence-transformers), semantic search tools | 🔵 |
| BB | Enhanced rich text in UI — refine the link renderer baseline, extend to lists, code blocks, tables | 🔵 |
| H  | Home Assistant integration | ⏸ blocked on user confirmation |
| U  | Signal gateway (signal-cli) | 🔵 — requires dedicated phone number |

### Deferred research

| ID | Item | Status |
|---|---|---|
| AI | Memory v2 — better generation + TUI panel | 🔵 research first |
| AJ | Browser realism — session persistence + login state + deeper antibot | 🔵 |
| AQ | Voice mode polish — STT + TTS quality + continuous mode | 🔵 |
| BD | Model-aware tool-use-enforcement guidance (Claude/MiMo brevity, GPT/Codex/Gemini full block) | 🔵 needs A/B on `agent.log` first |

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

### AV. Per-skill env scoping

`~/.alpi/.env` and `~/.alpi/<profile>/config.yaml` are denied at the
file-tool layer (v0.2.85). Skill scripts still inherit the parent
process's `os.environ` and can enumerate every variable in Python
with no file access at all — a prompt-injected skill can therefore
exfiltrate `OPENAI_API_KEY` or `TELEGRAM_BOT_TOKEN` without ever
opening a file.

**Scope.** When a skill runs, scrub `os.environ` down to a
declarative allowlist read from the skill's frontmatter:

```yaml
# skills/<name>/SKILL.md frontmatter
env:
  - HTTP_PROXY  # if the skill genuinely needs it
```

The default is the empty allowlist. The skill executor builds a
restricted env dict, spawns the subprocess (or sets up the
restricted scope for in-process skills) without inheriting anything
beyond the allowlist plus the irreducible PATH / HOME / LANG set
needed for any process to run.

**Closes** the residual vector named in v0.2.85's CHANGELOG +
`docs/SECURITY.md → Layer 1`.

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

### ALP.4. Streaming `link.ask`

Today `link.ask` is request/response: a peer asks "research X" and
waits until the full answer lands. Streaming chunks turns that into
*watching the other agent think* — reasoning tokens, tool traces,
partial answers all flow as they happen.

**Wire shape.** Same envelope as today; the response carries a
`stream: true` flag and the body becomes a sequence of
`{kind: "chunk"|"final"|"error", payload: …}` frames. Over Unix
socket: line-delimited JSON. Over TCP/Noise: each frame is its own
encrypted record. No new crypto, no new auth — the existing
envelope signature covers the stream as a whole (signed at the
final frame); intermediate chunks are AEAD-protected by the Noise
session for inter-machine, by the Unix-socket trust boundary
intra-machine.

**Why it matters.** Two payoffs. (1) Demos: "two alpis
collaborating" looks like one watching the other type, which is the
single most legible visualisation of agent-to-agent work we can
ship. (2) Inside workgroups (ALP.3), a long `workgroup.post`
appears live for every member — the workgroup transcript becomes a
real-time surface, not a polling one. The same primitive lets the
companion app (AX) stream a remote profile's reply incrementally
instead of waiting for the full turn.

### ALP.5. Blob transfer

Two new verbs — `link.put_blob(bytes, hash)` and
`link.get_blob(hash)` — for sharing artefacts that have no business
inline in a JSON envelope: a PDF, a dataset, the output of a skill,
a screenshot.

**Wire shape.** Content-addressed by SHA-256; the recipient stores
under `~/.alpi/<profile>/alp/blobs/<hash>` and dedups across calls.
Chunked transfer (default 64 KiB) with per-chunk AEAD; the final
frame carries the full-blob signature so the receiver can verify
the artefact end-to-end. Caps: per-call max blob size (config
knob, 100 MiB default), per-day inbound budget per peer (separate
from the spending ledger — this gates *bytes*, not LLM cost).

**Pairs naturally with workgroups.** A workgroup post can reference
a blob (`{text: "see attached", blob: "<hash>"}`); the hub fans out
the post and members `link.get_blob` from the hub on demand. No
need to upload to the cloud, no third-party intermediary.

### AX. Mobile / desktop companion

A minimal client (likely Tauri or a thin native wrapper) that
speaks ALP to the user's main profile rather than running a full
agent locally. The phone / desktop app is a remote control + lens
on the agent that lives on the user's main machine.

**Why a companion, not a full port.** A mobile alpi running its own
LLM + tools doubles the security surface and the maintenance cost
without adding capability. ALP is already the protocol for
"another machine talks to my profile" — the companion is just
another peer.

**Surfaces this could replace or extend:**

- Telegram gateway (today's mobile story) — keep working but
  optional once the companion is real.
- `/peers`, `/budget`, `/memory` panels exposed read-only on the
  go.
- Workgroup viewer (**AZ**) folds in here — the same companion
  that mirrors a 1:1 chat shows the workgroup transcript.

**Open questions before scope locks:**

- Tauri vs. native (SwiftUI / Kotlin) — Tauri is one codebase, but
  ALP requires a Noise_XK implementation in the host language; we
  already have it in Python. A Rust crate (`snow`) covers Tauri
  cleanly.
- iOS background restrictions — running an ALP TCP listener on
  iOS is non-trivial; the companion likely *initiates* connections
  to the user's profile rather than accepting them.
- Distribution — TestFlight + Play Store internal track at first.

### AY. Skills marketplace

A curated, signed, *federated* registry. Not a centralised store.

**Shape.** A skill is published by writing its manifest + body to a
git repo (any forge — GitHub, sourcehut, self-hosted Gitea); the
manifest carries a public key and the body is signed. `alpi skill
install <url>` clones the repo, verifies the signature, runs the
existing security scanner, and lands the skill under
`skills/<name>/`. There is no central index; users discover skills
the same way they discover npm packages (links, blog posts,
word-of-mouth) and the trust anchor is the publisher's pubkey.

**Why federated, not centralised.** A central marketplace becomes a
chokepoint (review queue, takedowns, account bans, eventual
acquisition). Federation matches the Satoshi principles —
**Open Source**, **User Sovereignty** — and reuses the same
trust pattern as ALP peers (pubkey-pinned, no discovery service).

**Curation.** Satoshi Ltd. publishes a `@satoshi-ltd/skills` repo
with our blessed bundles (the v0.3 **AO** decision was "no default
bundle"; that holds — this is opt-in). Other publishers are equally
first-class.

### BA. Local RAG over `workspace/`

Semantic search over the user's project files without sending a
byte to a third party. Two new tools:

- `index_workspace(path?)` — embeds the workspace into a local
  vector store (`~/.alpi/<profile>/index/`). Default model is a
  small sentence-transformer (`all-MiniLM-L6-v2` or similar);
  optionally swappable.
- `search_workspace(query, k=5)` — returns top-K snippets with
  filepath + line range. The agent then reads the matching ranges
  with the existing `read_file` tool.

**Why not piggy-back on a cloud RAG.** The whole point is that the
workspace contents never leave the machine. Embedding model + index
both live locally; no API roundtrips during search.

**Trade-offs to settle.** Sentence-transformers ships ~80 MB of
PyTorch weights — significant install weight. A pure-CPU
alternative (e.g., GGUF + llama.cpp) keeps the install lighter at
the cost of slower indexing. Decide during scope.

### BB. Enhanced rich text in UI

The link renderer (the original v0.3 BB) shipped a baseline. v0.4
extends it across the rest of the rich-text surface:

- Lists (ordered + unordered) — consistent indent, marker style.
- Inline code + fenced blocks — monospace font, accent-aware
  background, per-language syntax highlight where it pays off.
- Tables — column alignment, header style, fits to terminal width.
- Headings inside chat replies — sized hierarchy, not just bold.

Goal: when an LLM emits structured Markdown in its reply, the TUI
renders it cleanly enough that users stop falling back to copying
the raw text into another tool.

### H. Home Assistant integration

Only if @soyjavi runs Home Assistant. Requires `HA_URL` + a
long-lived token in `.env`. Typical uses: read sensors, toggle
lights/scenes, query occupancy. **Blocked on confirmation that HA
is part of the setup.**

### U. Signal gateway (signal-cli)

Signal has the best security posture of any consumer messenger,
but integration requires a **dedicated phone number for the bot**
(you can't bot your own number — Signal won't allow two sessions
simultaneously in a useful way). signal-cli runs as a local daemon
exposing an HTTP/JSON-RPC endpoint; we just POST/GET messages.

**Scope.** `alpi/gateway/platforms/signal.py` talking to a
locally-running `signal-cli daemon --http 127.0.0.1:…`. First-run:
user registers a bot number, follows signal-cli's captcha + SMS
verify flow once (`signal-cli -u <num> register`), then
`alpi setup → Gateways → Signal` stores the daemon URL +
allowlist of sender numbers.

**Estimated LOC:** ~200 (HTTP client + polling loop + send).

**Blocker:** requires extra SIM / VoIP number. Real cost: ~$5/mo
(Twilio / JustCall). Niche unless you want E2EE + self-hosted.

### AI. Memory v2 — generation + TUI panel

Two sub-tasks, research-first:

1. **Generation quality.** Revisit the `memory` tool description
   and body. Open questions: are we writing the right type per
   signal? Is the 70% Jaccard dedup too loose / too tight? Should
   the tool take a "confidence" field so low-conf writes
   auto-expire? Compare against comparable agents + the latest
   public memory patterns (Mem0, Letta) and pick what fits our
   scope.
2. **TUI panel.** `/memory` today shows the three files verbatim.
   Options: section-collapsible view, edit-in-place, "forget this"
   quick action, filter by type.

Ship 1 first (server-side quality) then 2 (surface improvements).

### AJ. Browser realism — Cloudflare + captcha survival

Research-first. What exists: Playwright with `playwright-stealth`,
humanised typing, per-profile `browser/state.json`. The open
question is whether the current posture clears common anti-bot
checkpoints — Cloudflare's "verify you are human" interstitial,
Turnstile, hCaptcha challenges when they fire on the agent's
traffic.

**Step 1 — measurement.** Build a scorecard script that runs the
browser tool against the standard detection sites
(`bot.sannysoft.com`, `abrahamjuliot.github.io/creepjs`, the
Cloudflare "Are you under attack" demo) and captures what each
detector reports. That grounds the gap analysis.

**Step 2 — analysis.** With the scorecard in hand, identify the
top 3 signals we fail (webdriver flag, audio context fingerprint,
canvas, WebGL, timing patterns, …) and decide which are worth
closing. Not everything is worth chasing: a perfect stealth score
is a moving target and extreme measures (full fingerprint rotation,
residential proxy) carry their own risk.

**Step 3 — implementation.** Land the improvements behind the
existing `browser` tool surface — no new config knobs unless
strictly needed. Session persistence and login-state detection are
adjacent concerns that naturally fall out of this work (a
cookie-expired page looks different from a logged-in one); fold
them in when the detection scaffold makes it cheap.

### AQ. Voice mode polish — STT + TTS + continuous mode

The voice primitives shipped (`tts`, `stt` tools, Telegram voice
inbound/outbound) but the surface still feels like two utility
tools, not a first-class mode.

Open areas to evaluate before committing scope:

- **STT quality vs. latency.** Are we on the right whisper model
  size by default? Do we need VAD (silence trimming) to cut
  latency? How bad is the current word-error rate on accented
  speech?
- **TTS quality + personality.** Edge-tts voices are decent but
  robotic compared to OpenAI's `tts-1-hd` or ElevenLabs.
  Trade-off: local-first vs. quality. Maybe a per-profile toggle.
- **Continuous voice mode.** Today voice is turn-based (record,
  transcribe, reply, speak). A push-to-talk or hotword-triggered
  loop in the TUI would turn voice into a usable mode, not a demo.
- **Voice output in gateway context.** Autoplay-off-on-gateway
  works; still room to improve how voice notes are chunked for
  Telegram when replies are long.

Start with a measurement pass (record a few real prompts, check STT
accuracy + TTS latency end-to-end), then pick the two or three
biggest wins.

### BD. Model-aware tool-use-enforcement guidance

Gate the "Actually CALL the tool…" paragraph in
`alpi/prompts/system_prompt.md` on model family. Claude / MiMo /
Qwen / Sonnet / Opus follow tool instructions well without the
long enforcement block; GPT / Codex / Gemini / Gemma / Grok
need it. Measure on `agent.log` before committing.

Output: short report showing tool-call rate on a Claude session
with vs without the block (same prompts). Apply the split only if
no regression on the shorter variant.

---

## v0.5 cycle

The v0.5 surface deepens what v0.4 plants. ALP gets two more
extensions that turn workgroups from "shared chat" into "shared
workspace"; the rest emerges from how v0.4 lands in real use.

| ID | Item | Status |
|---|---|---|
| ALP.6 | Workgroup search — semantic search over a workgroup transcript via local RAG (depends on **BA**) | 🔵 |
| ALP.7 | Pinned shared memory per workgroup — hub-anchored `wiki.md`, role-based write | 🔵 |

### ALP.6. Workgroup search

Once a workgroup runs for weeks, scrolling becomes useless.
`workgroup.search(workgroup_id, query)` returns the top-K posts
matching a query, ranked by semantic similarity using the local RAG
index (**BA**). The hub indexes its own transcript on disk; members
search remotely via the existing ALP transport.

**Why it pairs with BA.** Reuses the same embedding model and
vector store; no separate ML surface to maintain. The hub embeds
each post when it lands and answers `workgroup.search` from the
local index — no roundtrip to a third party, no plaintext leaks
beyond the workgroup membership.

### ALP.7. Pinned shared memory per workgroup

Workgroups today are append-only chat. **ALP.7** adds a single
mutable surface per workgroup — a `wiki.md` held by the hub, read
by every member, writable by members the hub flagged with the
`writer` role at create or via `workgroup.grant`. The wiki captures
state that does not belong in the rolling transcript: design
decisions, shared conventions, links, the workgroup's "about"
page.

**Verbs.** `workgroup.wiki.read(workgroup_id) → text`,
`workgroup.wiki.write(workgroup_id, text, parent_hash) → new_hash`,
`workgroup.wiki.history(workgroup_id, limit)`. Optimistic
concurrency via the `parent_hash` — two writers racing get a clean
conflict response, not a clobber.

**Why "pinned memory" not "files"**. ALP.5 already covers blobs.
The wiki is deliberately a single text doc per workgroup —
opinionated, easy to render in the TUI and the companion (AX), and
sized for an agent to read in full as part of joining the
workgroup. Anything bigger goes through ALP.5.

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
dedicated endpoint (DALL-E, SD). Useful for "hazme un logo
rápido". Low priority unless a concrete use case appears.

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

**Rejected architecture attempts:**

- **Go + Bubbletea rewrite.** Rejected.
- **rich.Live + prompt_toolkit inline UI.** Worked but had ceiling
  (no modals, suspend races). Replaced by Textual.
- **Full Textual app with sidebar + modals + fullscreen chrome**
  (first attempt). Rolled back as too heavy. Current is
  mother.py-style minimal.
- **SQLite state.db.** Plain JSON files scan fast for <1000
  sessions.
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
  by default". The marketplace (**AY**) is the path: bundles ship
  out of `@satoshi-ltd/skills`, opt-in, never imposed.

**Rejected behaviours:**

- **Auto-reflect on Ctrl+C.** Dangerous.
- **Post-session `/reflect` loop.** Tried it — removed because the TUI
  implementation was broken and inline memory writes are cleaner.
  Replaced by hardened system prompt + tool-description rules for
  inline `memory(add)` + `skill(create)`.

**Rejected dependencies:**

- **duckduckgo-search.** Deprecated → migrated to `ddgs`.
