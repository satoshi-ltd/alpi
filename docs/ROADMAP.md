# Roadmap

Open work for alpi. Shipped work lives in
[CHANGELOG.md](../CHANGELOG.md) — this file never repeats it. For
technical reference of what currently ships, see
[ARCHITECTURE.md](ARCHITECTURE.md).

Audience: the creator ([@soyjavi](https://github.com/soyjavi)) and
any future contributor reading the repo cold.

Legend: 🔵 backlog · 🟡 next up · ⏸ blocked.

---

## Open items

| ID | Item | Target | Status |
|---|---|---|---|
| AR | v0.3 production release — website + content rewrite | v0.3 | 🟡 v0.3 gate — blocks the cut |
| AT | Audit system prompt + tool descriptions vs hermes | v0.3 | 🔵 research first |
| AI | Memory v2 — better generation + TUI panel | v0.3 | 🔵 research first |
| AJ | Browser realism — session persistence + login state + deeper antibot | v0.3 | 🔵 |
| AO | Default skills bundle (writer / coder / webmaster …) | v0.3 | 🔵 research first |
| AQ | Voice mode polish — STT + TTS quality + continuous mode | v0.3 | 🔵 |
| BA | Schedule: ad-hoc job fire (`tick` / force-run) for circuit testing | v0.3 | 🔵 |
| BB | TUI: shared link renderer (bold + underline; hover = accent bg + black) | v0.3 | 🔵 |
| BC | External security audit before v0.3 public release | v0.3 | 🔴 gate on AR |
| BD | Model-aware tool-use-enforcement guidance (Claude/MiMo brevity, GPT/Codex/Gemini full block) | v0.3 | 🔵 needs A/B on agent.log first |
| BE | Bundled skills infrastructure (loader; no content yet) | v0.3 | 🔵 dual-source lookup or seed-on-create — land alongside first real bundled skill |
| ALP.2 | Alpi Link Protocol — inter-machine Noise-protocol transport + budget / rate-limit enforcement | v0.4 | 🔵 — depends on ALP.1 (shipped) |
| ALP.3 | Alpi Link Protocol — shared rooms (group chat, humans optional) | v0.4 | 🔵 — depends on ALP.1 (shipped) |
| H | Home Assistant integration | long-term | ⏸ blocked on user confirmation |
| N | Image generation | long-term | 🔵 no concrete use case yet |
| U | Signal gateway (signal-cli) | long-term | 🔵 requires dedicated phone number |
| Σ.1 | Mixture-of-agents tool (ensemble inference) | stretch | 🔵 not planned, tracked for later |
| Σ.2 | RL training / fine-tuning hooks | stretch | 🔵 not planned, tracked for later |

v0.3.0 ships when **AR** lands — every other v0.3 row is "nice to
have before the cut, not required". **ALP.2** + **ALP.3** are firmly
v0.4.

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

The competitor landscape (hermes, similar third-party agents)
routinely ships "Codex OAuth" / "Claude Code OAuth" features.
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

## v0.3 cycle

### AR. v0.3 production release — website + content rewrite (v0.3 gate)

v0.3 is the first release intended for public consumption. That
implies a presence (static site) and a content pass across
`README.md`, `docs/*`, and the future landing page aligned with
[satoshi-ltd.com](https://satoshi-ltd.com):

- **Positioning.** Privacy-first. No telemetry. Local-first,
  cloud-last. Your keys, your machine, your data.
- **Competitor framing.** Speak generically about the landscape
  (hermes-style third-party agents, Claude-style official clients).
  Avoid naming them gratuitously in marketing copy; when a
  comparison is needed, state the difference in terms of *what
  alpi does differently*, not what they do wrong.
- **Differentiators to lead with.** UX discipline (one wizard, no
  CLI sprawl), security posture (three-tier approval, OSV malware
  check, opt-in OS sandbox, fail-closed allowlists), privacy (no
  hidden network, no telemetry, no account), focused scope (only
  the tools / skills that pay rent — no kitchen-sink registry).

**Deliverables before cutting v0.3.0:**

1. Static site — single-page, minimal, matching satoshi-ltd.com
   visual language. Lives in `site/` at the repo root; deploys
   from there.
2. README rewrite with the new positioning. Today's README is
   install-first; the new one leads with why alpi, install is a
   section.
3. [`docs/ARCHITECTURE.md`](ARCHITECTURE.md) +
   [`docs/SECURITY.md`](SECURITY.md) audited for old framing
   ("experimental", "personal-use", "stretch goal") that no longer
   fits a production release.
4. A short launch post for the personal blog / X account —
   optional, but the effort pays off once.

v0.3.0 doesn't ship until AR lands. The code is already
v0.3-shaped (CLI shrunk, observability in, doctor live, centralised
logs, ALP.1 shipped); what's missing is the narrative to back it.

### AT. Audit system prompt + tool descriptions vs hermes

Research-first. Today `alpi/prompts/system_prompt.md` + each tool's
description field are our main levers for how the LLM uses alpi.
They've been tweaked reactively (add a line when a model misbehaves,
compress when the prompt bloats) but never audited as a whole.

**What to compare.** Hermes is the closest reference codebase (see
the memory entry for its path). For each alpi tool, read the hermes
equivalent side by side and note:

- Is our description shorter and still as clear? Longer without
  paying for it?
- Are the parameter hints as concrete? Hermes tends to include a
  one-line "use this when…" at the top of every tool; do we?
- Do we over-invest in negative instructions ("do NOT…") where a
  positive example would land better with the LLM?
- Are there tools where hermes' description consistently produces
  better calls in our own traffic? The `agent.log` plus session
  transcripts are the data set.

**System prompt.** Same exercise for `system_prompt.md`: read our
current version against hermes' system prompt, look for load-bearing
guidance we're missing or redundant text we can drop. Bias toward
shorter — every token in the system prompt is paid on every turn.

**Done criterion.** A short report listing the 3–5 concrete edits
worth making, each with before / after + a rationale tied to
observed behaviour in `agent.log` or sessions. Apply the edits that
clear the bar; leave the rest.

**Why research-first.** "Rewrite all tool descriptions" is the easy
way to waste a week. Measure first, edit surgically.

### AI. Memory v2 — generation + TUI panel

Two sub-tasks, research-first:

1. **Generation quality.** Revisit the `memory` tool description
   and body. Open questions: are we writing the right type per
   signal? Is the 70% Jaccard dedup too loose / too tight? Should
   the tool take a "confidence" field so low-conf writes
   auto-expire? Compare against Hermes + the latest public memory
   patterns (Mem0, Letta) and pick what fits our scope.
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

### AO. Default skills bundle

Today there are no bundled skills. Fresh profiles start with an
empty `{home}/skills/` dir; the `skill` tool only looks under
`{home}`, so nothing ships by default. Making bundles reachable
is the prerequisite (see **BE**). A starter pack on top of a
working loader would help new users see what skills are for:

- **writer** — drafting, editing, tone shifting; reusable across
  essays/emails.
- **coder** — language-agnostic conventions for the code review +
  refactor patterns alpi does repeatedly.
- **webmaster** — site audit, SEO, broken link check via the
  browser tool.
- Others TBD.

**Research first:** read the hermes skills, scan popular agent-OS
patterns (Claude Skills, Cursor Rules, Copilot Instructions),
decide what's alpi-shaped vs what's bloat. Land one or two first,
watch real usage, then expand.

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

### BA. Schedule: ad-hoc job fire

Today a cron job added via the `schedule` tool only fires when its
time comes. That makes end-to-end testing painful — add a job, wait
for the next window, hope it works. What's missing is a way to say
"run this job *now*, exactly as the scheduler would have".

**Scope.**

- **CLI**: `alpi schedule fire <job_id>` — looks up the job in
  `jobs.json`, executes it through the same path the scheduler
  daemon uses (`_run_once` + the same envelope), writes to
  `schedule/output/` and `schedule.log` as normal.
- **Tool**: `schedule(action="fire", id=...)` so the agent can
  self-test a job it just created.
- **Safety**: same threat-scan (X) runs on fire as on cron tick.
  No bypass of approval gate.

**Why it matters.** Closes the only feedback loop where the user
has to wait N minutes to learn their job is broken. Also useful
for operations — when debugging a cron that's not firing on the
expected interval, force one run and tail the logs.

### BB. TUI: shared link renderer

Markdown links (`[text](url)`) today render as Rich's default —
underlined text in the base foreground colour. Works, but blends
with body text when the terminal's theme is low-contrast.

**Proposed look.**

- **Default state**: bold + underline, base foreground colour.
  Mimics the classic HTML anchor convention. Reads as a link at a
  glance without burning accent colour on every link.
- **Hover / selected state**: accent background, black foreground.
  High contrast, unambiguous affordance. Matches the selection
  visual already used by `OptionList` rows.

**Scope.**

- New helper in `alpi/tui/links.py` (or inline in
  `alpi/tui/formatting.py`) that walks a Rich `Text` / markdown
  tree and rewrites link nodes to the two-state style.
- Apply transversally: `AssistantMessage` render path, every
  `FloatingPanel` subclass that can contain links (`/memory`
  `/help`, future `/peers` detail). One call site per widget is
  fine as long as they all share the helper.
- Keep the URL copyable — don't swap link text for the URL;
  Textual's built-in link handling stays.

**Done criterion.** Walking through `/memory`, `/help`, a chat
reply containing links, and an error message with a link renders
them all with the same two-state visual. No widget has its own
link style.

### BC. External security audit before v0.3 public release

**Gate on AR.** v0.3 is the first release intended for public
consumption (`docs/ROADMAP.md → AR`). Before we cut it, contract
an external firm for a formal audit.

**Scope of the engagement.**

- Threat model: who is the attacker, what's protected, what's
  non-goal. Draft lives in `docs/SECURITY.md` today; the auditor
  formalises and challenges it.
- ALP cryptography review: envelope signing (Ed25519 PKCS8),
  replay cache, Noise_XK wrapper when ALP.2 lands, peer-pinning
  workflow.
- Tool surface review: approval system, sandbox posture (macOS
  sandbox-exec profile + Linux bwrap), shell denylist, skill
  scanner, OSV check, SSRF guards in `browser` / `web_*` tools.
- Dependency posture: `pip-audit` output, third-party-code risks
  documented in `docs/SECURITY.md → Third-party code`.
- Privacy review: confirm **Zero Knowledge** + **Privacy by
  Design** claims match the code — no hidden telemetry paths, no
  analytics beacons, no cloud coupling that's not user-chosen.

**Output.** A public report lives at `docs/audits/v0.3-<vendor>.md`
(or linked from there). Issues found are either fixed before the
release or documented in the report with a timeline. The report
being published is part of the trust story — sitting on findings
isn't.

**Why external, not internal.** Satoshi Ltd. builds the tool; an
independent security firm reads it. The Satoshi principle "Open
Source — Auditable code. Reproducible builds. Trust, but verify"
applies to the organisation too.

### BE. Bundled skills infrastructure

The `skill` tool only searches `{home}/skills/` today. There is no
way to ship skills with the package — fresh profiles start empty,
and any SKILL.md authored in the repo is invisible to the agent.

Infrastructure first, content second. When a concrete bundled
skill has a clear use case (the first plausible one is a memory
consolidator, but `memory(replace|remove)` already covers it
ad-hoc), land the loader at the same time.

**Two implementation options.**

- **Seed-on-create:** on `ensure_home`, copy bundled package
  resources into `{home}/skills/`. Simple; each profile pins the
  skill version it was created with. User edits override.
- **Dual-source lookup:** `skill(action="run"|"view")` searches
  `{home}/skills/` first, falls back to package resources.
  Bundled skills always latest; user edits land in the profile
  and shadow the bundle (copy-on-write).

Dual-source is the cleaner model (matches Python package
resolution) but the seed path is what users intuitively expect.
Pick at implementation time, alongside the first real skill that
justifies the work.

### BD. Model-aware tool-use-enforcement guidance

Gate the "Actually CALL the tool…" paragraph in
`alpi/prompts/system_prompt.md` on model family. Claude / MiMo /
Qwen / Sonnet / Opus follow tool instructions well without the
long enforcement block; GPT / Codex / Gemini / Gemma / Grok
need it. Hermes gates this via a model-substring list; measure
on `agent.log` before committing.

Output: short report showing tool-call rate on a Claude session
with vs without the block (same prompts). Apply the split only if
no regression on the shorter variant.

---

## v0.4 cycle

### ALP — Alpi Link Protocol

alpi agents couldn't talk to each other. ALP is alpi's own closed
protocol for agent↔agent: intra-profile on the same machine,
inter-machine over the public internet, shared rooms for N-agent
workspaces. Security + privacy are hard requirements — every
message is signed + encrypted, every peer is explicitly pinned (no
discovery, no TOFU), every capability is fail-closed. Spec at
[`docs/ALP.md`](ALP.md). Three phases; ALP.1 (intra-profile) shipped
in v0.2.68.

### ALP.2 — Inter-machine Noise-protocol transport (v0.4)

Depends on ALP.1. New transport `alpi/alp/noise.py` + gateway
listener — TCP listener with Noise_XK handshake producing
forward-secret session keys, per-peer AEAD encryption on top.
Explicitly NOT HTTPS: we use Noise (same framework as WireGuard)
so we don't drag TLS's 30-year legacy of downgrade attacks and
cert-management headaches into a peer-to-peer tool. Peer entry
gains `address: host:port`. Same verbs as ALP.1, different
transport. Tailscale / WireGuard as a network-layer front-end is
the blessed deployment; direct public-internet exposure is
supported but discouraged.

Also in ALP.2: **budget + rate-limit enforcement**. The
`peers.yaml` `budget.tokens_per_day`, `budget.usd_per_day`, and
`rate_limit.requests_per_minute` fields already parse in ALP.1 but
don't enforce. ALP.2 ships the ledger + UTC-midnight reset + the
`-32005 budget-exceeded` response path.

### ALP.3 — Shared rooms (v0.4)

Depends on ALP.1. First-class group-chat workspaces — N alpis
(different profiles, different machines) post into a shared
transcript; a human can join via TUI `/room` or stay out entirely.
Hub model (the room creator holds transcript + group key), not
gossip. Per-room agent budget and kill switch as safety levers.
New verbs (`room.create`, `room.join`, `room.post`, `room.pull`,
`room.leave`, `room.pause`), rekey on member leave.

---

## Long-term / stretch

### H. Home Assistant integration

Only if @soyjavi runs Home Assistant. Hermes has
`homeassistant_tool` as a reference. Requires `HA_URL` + a
long-lived token in `.env`. Typical uses: read sensors, toggle
lights/scenes, query occupancy. **Blocked on confirmation that HA
is part of the setup.**

### N. Image generation

`generate_image(prompt, style)` using the active vision model or a
dedicated endpoint (DALL-E, SD). Useful for "hazme un logo
rápido". Low priority unless a concrete use case appears.

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

### Σ.1. Mixture-of-agents (stretch goal)

Spawn multiple LLMs on the same prompt, aggregate answers with a
final synthesizer. Hermes has this as `mixture_of_agents_tool.py`.
Use case: hard decisions where one model is weak and you want
"wisdom of crowds" at 3× cost.

Not planned — tracked here because it's a known technique and
might become useful if we hit a ceiling on single-model research
quality.

### Σ.2. RL training / fine-tuning hooks (stretch goal)

Hermes has `rl_training_tool.py` for recording agent runs and
building training datasets. If we ever want to fine-tune a smaller
local model on your actual conversation patterns, the
dataset-collection scaffold would live here.

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

**Rejected behaviours:**

- **Auto-reflect on Ctrl+C.** Dangerous.
- **Post-session `/reflect` loop.** Tried it — removed because
  Hermes doesn't do post-session reflection either, and the TUI
  implementation was broken. Replaced by hardened system prompt +
  tool-description rules for inline `memory(add)` + `skill(create)`.

**Rejected dependencies:**

- **duckduckgo-search.** Deprecated → migrated to `ddgs`.
