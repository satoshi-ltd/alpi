# Roadmap

Status of in-progress work, plans for the next cycle, and a brief log of
what's already shipped. For technical reference of what's currently in
the codebase see [ARCHITECTURE.md](ARCHITECTURE.md).

Audience: the creator (@soyjavi) and any future contributor reading the repo cold.

---

## Now — v0.2 in progress

| ID | Item | Status |
|---|---|---|
| A | `send_message` outbound messaging | ✅ shipped (commit 6e31ace) |
| B | Interactive browser (Playwright) | ✅ shipped (v0.2.16) |
| C | OpenAI Codex provider (ChatGPT subscription auth) | ❌ rejected — ToS violation, see "Principles" |
| D | Vision (`read_image`) | ✅ shipped (v0.2.4) |
| E | Multi-profile CLI | ✅ shipped (commit 630f97c) |
| F | Gateway workspace validation | ✅ shipped (commit 04bdaba) |
| G | Terminal + code execution OS sandbox | ✅ shipped opt-in/experimental (commit e78b428) |
| H | Home Assistant integration | ⏸ blocked on user confirmation |
| I | MCP client | ✅ shipped (commit 0d376ac) |
| J | Anti-bot browsing (camoufox) | ❌ dismissed — humanised Playwright (v0.2.36) covers the real detection surface; camoufox adds +230 MB Firefox for marginal gain |
| K | Scroll resilience under heavy streaming | ✅ shipped (commit 9ed4139 — `VerticalScroll.anchor()`) |
| L | Reasoning-as-state (TUI) | ✅ shipped (commits 62f7fa7 + fd1fec4) |
| M | TTS / STT / voice-mode (local-first) | ✅ shipped (v0.2.25, 2 tools + Telegram voice inbound/outbound, no continuous voice mode) |
| N | Image generation | 🔵 backlog — no concrete use case yet |
| AA | Cleanup wizard (`alpi setup → Cleanup`) | ✅ shipped (v0.2.39) |
| AB | Gateway service install/uninstall wizard | ✅ shipped (v0.2.40, simpler scope than originally drafted — per-profile toggle, not a full split) |
| AC | Auto-generated CHANGELOG.md from commits | ✅ shipped (v0.2.48) — `alpi release notes [--since REV] [-o FILE]` parses `git log`, treats `pyproject.toml` version-bump commits as release boundaries, groups commits by `type:` prefix within each version. Initial CHANGELOG.md reconstructs the full v0.1.0 → v0.2.48 history (44 releases). |
| AD | CLI surface shrink + unified `alpi logs` + scheduler auto-install | ✅ shipped (v0.2.42) — dropped `gateway {stop,status,install,uninstall,logs}` / `schedule {stop,status,install,uninstall,logs}` / `mcp list`; daemon entrypoints hidden; one `alpi logs [--source]` replaces the per-subsystem tails; scheduler installs silently on first run |
| AE | Centralised `~/.alpi/logs/` + `approval` / `agent` audit trails | ✅ shipped (v0.2.43) — all subsystem logs flattened into one dir; new `approval.log` (security audit of non-SAFE command decisions) and `agent.log` (one line per turn: cross-session grep index for "what has alpi been doing") |
| AG | First-time help text in gateway/MCP wizards | ✅ shipped (v0.2.47) — Telegram (BotFather + @userinfobot), IMAP (hosts, ports, app password, fail-closed allowlist), MCP add (what MCPs are + GitHub example + registry link). Only shown when no value is configured yet, so editing flows stay terse. |
| AF | `alpi doctor` health check | ✅ shipped (v0.2.45) — **live** audit: Telegram `getMe`, IMAP login, Gmail token refresh, MCP spawn+handshake, service PID liveness, workspace + API-key presence, sandbox backend. Parallel execution with per-check timeouts; total runtime ≈ slowest single check (~8s on a working profile, bounded to ~15s on a broken one). Reachable from CLI and `alpi setup → Health check`. Exit 1 on fail. |
| R.1 | Research step-counter in state label | ✅ shipped (v0.2.2) |
| R.2 | `delegate` — write-capable sub-agent | ✅ shipped (v0.2.3, named `delegate` not `delegate_task`) |
| R.3 | Batch parallel sub-agents (`tasks[]`) | ✅ shipped (v0.2.18) |
| S | `read_image` auto-resize (cost saver) | ✅ shipped (v0.2.21) |
| T | Gmail API (OAuth2) gateway | ✅ shipped (v0.2.23, 2 commits: T.1 rename + T.2 full Gmail) |
| U | Signal gateway (signal-cli) | 🔵 backlog — requires dedicated phone number |
| V | Anthropic subscription OAuth | ❌ rejected — ToS violation, see "Principles" |
| W | Approval system (dangerous cmd + session allowlist) | ✅ shipped (v0.2.37) |
| X | Schedule prompt threat-scan | ✅ shipped (v0.2.20) |
| Y | Tool result budget / truncation | ✅ shipped (v0.2.20) |
| Z | OSV malware check (skills + MCP installers) | ✅ shipped (v0.2.20) |
| Σ.1 | Mixture-of-agents tool (ensemble inference) | 🔵 stretch goal — not planned, tracked for later |
| Σ.2 | RL training / fine-tuning hooks | 🔵 stretch goal — not planned, tracked for later |
| AH | TUI panel list rendering unified with CLI style | ✅ shipped (v0.2.51) — new `alpi/tui/list_row.py` helper with `row_text` + `build_options`. Selectable panels (`/model` providers, `/model` models, approval, `/help`) render entries as `glyph name · muted-description` with a leading `◆` in the profile accent marking the configured/active row. `/help` now runs the picked slash command on enter/click. Display-only panels (`/tools`, `/mcps`, `/skills`) keep their two-line `entry-name` / `entry-desc` stack — that reads better for content than for choices. |
| AI | Memory v2: better generation + TUI panel | 🔵 backlog — research first (see below) |
| AJ | Browser realism: session persistence + login state + deeper antibot | 🔵 backlog |
| AK | Telegram: richer reply formatting + command shortcuts | 🔵 backlog |
| AL | `alpi` auto-resumes last session by config | ✅ shipped (v0.2.50) — new `tui.auto_resume` flag (default `false`). When `true`, bare `alpi` behaves as if `-c` was passed; `/new` inside the TUI still starts a fresh thread. `alpi chat --once` (scripts + gateway) always starts clean. Explicit `-c` stays as a manual override. |
| AM | Dependency audit (drop/upgrade, security-first) | 🔵 backlog |
| AN | Gateway session model — per-chat persistence | 🔵 backlog — design decision |
| AO | Default skills bundle (writer / coder / webmaster …) | 🔵 backlog — research first |
| AP | Profile scaffold: drop `.env.example` | ✅ shipped (v0.2.53) — `config.seed_defaults()` no longer writes `~/.alpi/.env.example`. The wizards (`alpi setup`) are the canonical onboarding path; CONFIG.md is the canonical key reference for non-interactive setups. Removes the double-authoring drift risk (example was already out of sync with the Ollama multi-endpoint reshape). |
| AQ | Voice mode polish — STT + TTS quality + continuous mode | 🔵 backlog |
| AR | v0.3 production release — website + content rewrite | 🔵 v0.3 gate — blocks the cut |
| AS.1 | ALPI-to-ALPI protocol — design doc + inter-profile prototype | 🔵 v0.3 — research-first |
| AS.2 | ALPI-to-ALPI protocol — inter-machine `peer` gateway | 🔵 v0.4 — depends on AS.1 |
| AT | Audit system prompt + tool descriptions vs hermes | 🔵 backlog — research first |

### What's left to call v0.2 done

The minimum-viable shape of v0.2 is what's already shipped. Anything
else listed under "🔵 backlog" can move to v0.3 without blocking
release. The bar for "ship v0.2" is **clean docs + version bump +
real-use validation across a few sessions** — not feature
exhaustiveness.

**Nothing open for v0.2.** Everything the original roadmap promised is shipped. Items still in the backlog — **H** (Home Assistant), **N** (image gen), **U** (Signal), **Σ.1/Σ.2** (stretch goals), plus **AI, AJ, AK, AM, AN, AO, AQ** (TUI polish, Memory v2, browser realism, Telegram polish, dep audit, gateway sessions, default skills, scaffold review, voice mode polish), **AS.1** (ALPI protocol design + inter-profile prototype), and **AT** (system-prompt / tool-description audit) — roll forward to v0.3. Cutting **v0.3.0** is gated by **AR** (production release — website + content rewrite). **AS.2** (inter-machine `peer` gateway) is scoped for v0.4. **C** (OpenAI Codex OAuth), **V** (Anthropic OAuth), and **J** (camoufox) were rejected — C/V on ToS grounds (see Principles), J after humanised Playwright made it redundant.

Once the v0.3 cycle picks up a few of those + a fresh CHANGELOG
entry summarises v0.2, bump to `v0.3.0` and reopen the table.

---

## Principles

alpi **respects the ToS of every provider it integrates with**. When an LLM vendor (OpenAI, Anthropic, …) offers a paid subscription for a first-party client (ChatGPT Plus/Pro, Claude Pro/Max, Claude Code), that subscription is for THAT client. Reverse-engineering the private OAuth flow of the official CLI to route a third-party agent against the same quota is:

- A clear ToS violation.
- Disrespectful to the vendor's product boundaries.
- Unsafe for users (accounts can be banned; the reversed flow can break any time).

The competitor landscape (hermes, similar third-party agents) routinely ships "Codex OAuth" / "Claude Code OAuth" features. **alpi does not, and will not.** If a vendor publishes an official OAuth-for-third-parties flow in the future (documented, stable, bindable), we adopt it then.

**Practical consequence:** users pay per-token API access through their own keys. That cost is honest and visible. Subscription routing is not on the roadmap.

## Backlog — high value, on deck

### H. Home Assistant integration

Only if @soyjavi runs Home Assistant. Hermes has `homeassistant_tool` as a reference. Requires `HA_URL` + a long-lived token in `.env`. Typical uses: read sensors, toggle lights/scenes, query occupancy. **Blocked on confirmation that HA is part of the setup.**

### N. Image generation

`generate_image(prompt, style)` using the active vision model or a dedicated endpoint (DALL-E, SD). Useful for "hazme un logo rápido". Low priority unless a concrete use case appears.

### AH. Unify TUI list rendering with the CLI

Every floating panel that shows a list (`/memory`, `/tools`, `/mcps`, `/model`, approval choices, provider picker) currently has its own glyphs, padding, and active-item marker. Align them on the pattern already used by the CLI `ui.menu` after the wizard normalisation: `<name>` left-padded to the max name width in the list, `·` separator, muted `<description>` on the right, active row rendered with the profile accent (matching `row_accent` in `alpi/ui.py`).

**Scope.** Touch each panel that inherits from `FloatingPanel` and has a selectable list. Factor the shared renderer out so adding a new panel later doesn't drift the style back. Keep interaction behaviour untouched — this is purely visual alignment.

**Done criterion.** Walking through `/memory`, `/tools`, `/mcps`, `/model`, approval, and provider panels produces rows that are column-aligned with the same glyph + accent treatment in every one.

### AI. Memory v2 — generation + TUI panel

Two sub-tasks, research-first:

1. **Generation quality.** Revisit the `memory` tool description and body. Open questions: are we writing the right type per signal? Is the 70% Jaccard dedup too loose / too tight? Should the tool take a "confidence" field so low-conf writes auto-expire? Compare against Hermes + the latest public memory patterns (Mem0, Letta) and pick what fits our scope.
2. **TUI panel.** `/memory` today shows the three files verbatim. Options: section-collapsible view, edit-in-place, "forget this" quick action, filter by type.

Ship 1 first (server-side quality) then 2 (surface improvements).

### AJ. Browser realism — Cloudflare + captcha survival

Research-first. What exists: Playwright with `playwright-stealth`, humanised typing (v0.2.36), per-profile `browser/state.json`. The open question is whether the current posture clears common anti-bot checkpoints — Cloudflare's "verify you are human" interstitial, Turnstile, hCaptcha challenges when they fire on the agent's traffic.

**Step 1 — measurement.** Build a scorecard script that runs the browser tool against the standard detection sites (`bot.sannysoft.com`, `abrahamjuliot.github.io/creepjs`, the Cloudflare "Are you under attack" demo) and captures what each detector reports. That grounds the gap analysis.

**Step 2 — analysis.** With the scorecard in hand, identify the top 3 signals we fail (webdriver flag, audio context fingerprint, canvas, WebGL, timing patterns, …) and decide which are worth closing. Not everything is worth chasing: a perfect stealth score is a moving target and extreme measures (full fingerprint rotation, residential proxy) carry their own risk.

**Step 3 — implementation.** Land the improvements behind the existing `browser` tool surface — no new config knobs unless strictly needed. Session persistence and login-state detection are adjacent concerns that naturally fall out of this work (a cookie-expired page looks different from a logged-in one); fold them in when the detection scaffold makes it cheap.

### AK. Telegram reply polish

Two things:

- **Markdown rendering.** Telegram has its own MarkdownV2 format with escape rules for `_`, `*`, `[`, `]`, `(`, `)`, `~`, `` ` ``, `>`, `#`, `+`, `-`, `=`, `|`, `{`, `}`, `.`, `!`. Agent replies today go through as plain text; a render pass that converts the common Markdown the agent emits (bold / italic / code / links) to MarkdownV2 would make replies readable without breaking on the special chars.
- **Command shortcuts.** Today every inbound message spawns a full agent turn. A lightweight command parser for `/new` (fresh session), `/continue` (resume last), `/model` (swap current model), `/help` (list the shortcuts), and `/status` (active session id + cumulative cost) covers the day-to-day operations without the LLM round-trip. Scope is intentionally small — anything beyond these five should go through the agent.

### AL. `alpi` auto-resumes last session by default

Today: `alpi` → fresh session; `alpi -c` → resume most recent. Change: `alpi` behaves like `alpi -c` always, no time limit. The last session is the thread you're in; opening the TUI should pick it up where you left off, the way a text editor reopens the last file. A user who explicitly wants a fresh start has `/new` inside the TUI — that's the only supported path.

**Scope.** Flip the default in `cli.py::main` so `continue_last` is true when the bare subcommand fires; keep `alpi chat --once` starting clean (scripts want deterministic, empty context). No new config key needed — resume is the product behaviour, not a toggle.

### AM. Dependency audit

Sweep of `pyproject.toml` dependencies with security + value lens:

- Run `pip-audit` / `uv tree` against current `uv.lock`, note any known CVE.
- Drop unused transitives, pin majors where a breaking upgrade would land.
- Evaluate whether big-footprint deps (litellm, playwright, textual, questionary-equivalents already removed) still earn their weight.
- Document the kept set in ARCHITECTURE with a one-liner per dep.

Low-risk, high-signal. Do after the TUI and browser work so the audit reflects final usage.

### AN. Gateway session model — analyse and unify

Research-first. Today every inbound message (Telegram / IMAP / Gmail) spawns `alpi chat --once` which implicitly resumes the last global session for the profile. That means a Telegram chat and an email thread collide: context written in one bleeds into the other, and the TUI session interleaves with whatever the gateway did while you were away.

**Step 1 — write down how it actually works today.** Trace `gateway/run.py` + `_run_once` in `cli.py` + `session.py` load/save and document the current behaviour: where the session id is picked, when a new one starts, how `agent.log` associates turns with originator.

**Step 2 — frame the options against real use.**

- **Per-gateway**: one session per channel. Telegram conversation ≠ email thread ≠ TUI. Cleanest for the "these are different contexts" case.
- **Per-chat / per-sender**: finer-grained (two Telegram groups = two sessions). More accurate to how humans think of messaging, but explodes session count.
- **Shared / all together**: today's behaviour. Simple but leaky.

**Step 3 — recommend based on how the agent is actually used.** If gateway traffic is low volume and coherent with the TUI thread, "shared" is fine. If it's high volume or topically separate, per-gateway wins. Only after the analysis lands should we pick + implement.

### AO. Default skills bundle

Today the only bundled skill is `meta/consolidate-memory`. A starter pack would help new users see what skills are for:

- **writer** — drafting, editing, tone shifting; reusable across essays/emails.
- **coder** — language-agnostic conventions for the code review + refactor patterns alpi does repeatedly.
- **webmaster** — site audit, SEO, broken link check via the browser tool.
- Others TBD.

**Research first:** read the hermes skills, scan popular agent-OS patterns (Claude Skills, Cursor Rules, Copilot Instructions), decide what's alpi-shaped vs what's bloat. Land one or two first, watch real usage, then expand.

### AP. Profile scaffold review

Today `home.ensure_home()` creates `memories/`, `secrets/`, `sessions/`, `skills/`, `schedule/output/`, `logs/` + a `.gitignore`. And `config.py::seed_defaults()` drops a `.env.example`. Question: is `.env.example` the right onboarding pattern vs. filling `.env` from the wizards directly?

**Arguments for keeping `.env.example`:** self-documenting, copy-paste friendly, works for non-interactive setups (CI, devcontainers).

**Arguments against:** every key that lives there is also prompted in `alpi setup`, so it's double authoring. New keys added to wizards easily forgotten in the example.

Decide + align. Cheap to do.

### AQ. Voice mode polish — STT + TTS + continuous mode

M (v0.2.25) landed the primitives: a `tts` tool (edge-tts), a `stt` tool (faster-whisper local), Telegram voice inbound/outbound. What's missing is everything that makes voice feel like a first-class surface instead of a pair of utility tools.

Open areas to evaluate before committing scope:

- **STT quality vs. latency.** Are we on the right whisper model size by default? Do we need VAD (silence trimming) to cut latency? How bad is the current word-error rate on accented speech?
- **TTS quality + personality.** Edge-tts voices are decent but robotic compared to OpenAI's `tts-1-hd` or ElevenLabs. Trade-off: local-first vs. quality. Maybe a per-profile toggle.
- **Continuous voice mode.** M shipped without it explicitly — today voice is turn-based (record, transcribe, reply, speak). A push-to-talk or hotword-triggered loop in the TUI would turn voice into a usable mode, not a demo.
- **Voice output in gateway context.** The autoplay-off-on-gateway fix (v0.2.28) works; still room to improve how voice notes are chunked for Telegram when replies are long.

Start with a measurement pass (record a few real prompts, check STT accuracy + TTS latency end-to-end), then pick the two or three biggest wins.

### AR. v0.3 production release — website + content rewrite (v0.3 gate)

v0.3 is the first release intended for public consumption. That implies a presence (static site) and a content pass across `README.md`, `docs/*`, and the future landing page aligned with the same voice as [satoshi-ltd.com](https://satoshi-ltd.com):

- **Positioning.** Privacy-first. No telemetry. Local-first, cloud-last. Your keys, your machine, your data.
- **Competitor framing.** Speak generically about the landscape (hermes-style third-party agents, Claude-style official clients). Avoid naming them gratuitously in marketing copy; when a comparison is needed, state the difference in terms of *what alpi does differently*, not what they do wrong.
- **Differentiators to lead with.** UX discipline (one wizard, no CLI sprawl), security posture (three-tier approval, OSV malware check, opt-in OS sandbox, fail-closed allowlists), privacy (no hidden network, no telemetry, no account), focused scope (only the tools / skills that pay rent — no kitchen-sink registry).

**Deliverables before cutting v0.3.0:**

1. Static site — single-page, minimal, matching satoshi-ltd.com visual language. Hosted on GitHub Pages or equivalent.
2. README rewrite with the new positioning. Today's README is install-first; the new one leads with why alpi, install is a section.
3. `docs/ARCHITECTURE.md` + `docs/SECURITY.md` audited for old framing ("experimental", "personal-use", "stretch goal") that no longer fits a production release.
4. A short launch post for the personal blog / X account — optional, but the effort pays off once.

v0.3.0 doesn't ship until AR lands. The code is already v0.3-shaped (CLI shrunk, observability in, doctor live, centralised logs); what's missing is the narrative to back it.

### AS.1. ALPI-to-ALPI protocol — design doc + inter-profile prototype (v0.3)

Lets two alpi instances talk to each other. AS.1 is the groundwork: a research doc that picks the wire shape, and a working inter-profile prototype on the same machine. Inter-machine (AS.2) builds on this once the protocol is validated.

**Use cases to validate first.** Before drawing protocol diagrams, lock the two concrete scenarios that justify the work. Candidates:

- **Cross-profile handoff.** `alpi -p work` kicks a long job, `alpi -p personal` gets notified when it's done.
- **Remote delegation.** TUI on a laptop with a small local model asks the home-server (bigger model) to do heavy research.
- **Federated memory read.** "What did my work alpi note about the Acme project last week?" from inside the personal profile.
- **Backup responder.** Inbound Telegram reaches any reachable alpi; whichever is online handles it.

Pick two and design against those. Over-generalising before the use cases are sharp is the main failure mode.

**Design axes to settle.**

- **Topology.** Peer-to-peer with a per-profile peer list, central broker, or mesh discovery. For 2–5 nodes, explicit peer lists win — simpler, no SPOF.
- **Transport.** HTTP/JSON-RPC, MCP-over-SSE, or WebSocket. MCP is tempting (we already speak it); weigh whether each alpi registers as an MCP server to its peers.
- **Auth + integrity.** Long-lived bearer tokens in `.env` rotate poorly. Ed25519 keypairs per profile, messages signed + optionally encrypted, is only marginally harder and ages better.
- **Capability model.** Every peer declares what tools / memory namespaces it accepts from others, fail-closed. A peer with `can_read_memory=true, can_call_terminal=false` is a read-only neighbour.
- **Addressing.** `profile@host` where `host` is a user-picked hostname resolvable via the peer list. Stable across IP changes, no mDNS dependency.

**Deliverables.**

1. `docs/PROTOCOL.md` — picked topology + transport + auth with the rationale.
2. An inter-profile prototype on the same machine (local socket, no TLS, no firewall) exercising signing + capability enforcement on one of the two picked use cases.
3. A clear cut line showing what slides to AS.2.

### AS.2. ALPI-to-ALPI protocol — inter-machine `peer` gateway (v0.4)

Depends on AS.1. A new gateway type in `alpi/gateway/platforms/peer.py`: an HTTPS listener that accepts signed messages from remote peers, runs them through the same allowlist + audit machinery as Telegram/IMAP, and replies. TLS, routing, discovery, and NAT traversal all land here.

Scope intentionally deferred until AS.1 validates the protocol — dropping into TLS before the capability model is settled is the wrong order.

### AT. Audit system prompt + tool descriptions vs hermes

Research-first. Today `alpi/prompts/system_prompt.md` + each tool's description field are our main levers for how the LLM uses alpi. They've been tweaked reactively (add a line when a model misbehaves, compress when the prompt bloats) but never audited as a whole.

**What to compare.** Hermes is the closest reference codebase (see the memory entry for its path). For each alpi tool, read the hermes equivalent side by side and note:

- Is our description shorter and still as clear? Longer without paying for it?
- Are the parameter hints as concrete? Hermes tends to include a one-line "use this when…" at the top of every tool; do we?
- Do we over-invest in negative instructions ("do NOT…") where a positive example would land better with the LLM?
- Are there tools where hermes' description consistently produces better calls in our own traffic? The `agent.log` (v0.2.43) plus session transcripts are the data set.

**System prompt.** Same exercise for `system_prompt.md`: read our current version against hermes' system prompt, look for load-bearing guidance we're missing or redundant text we can drop. Bias toward shorter — every token in the system prompt is paid on every turn.

**Done criterion.** A short report listing the 3–5 concrete edits worth making, each with before / after + a rationale tied to observed behaviour in `agent.log` or sessions. Apply the edits that clear the bar; leave the rest.

**Why research-first.** "Rewrite all tool descriptions" is the easy way to waste a week. Measure first, edit surgically.

### AC. Auto-generated CHANGELOG.md from commits

Every patch bump commits with a descriptive subject already. A script (`alpi release notes` or a git hook) that collects commits between two tags and renders a `CHANGELOG.md` stanza would let us stop writing release prose twice (once in the commit, once in ROADMAP). Group by type (feat / fix / tidy) via a lightweight prefix heuristic on commit subjects. Estimated ~80 LOC.

## Next — v0.3 planned



### U. Signal gateway (signal-cli)

Signal has the best security posture of any consumer messenger, but integration requires a **dedicated phone number for the bot** (you can't bot your own number — Signal won't allow two sessions simultaneously in a useful way). signal-cli runs as a local daemon exposing an HTTP/JSON-RPC endpoint; we just POST/GET messages.

**Scope.** `alpi/gateway/platforms/signal.py` talking to a locally-running `signal-cli daemon --http 127.0.0.1:…`. First-run: user registers a bot number, follows signal-cli's captcha + SMS verify flow once (`signal-cli -u <num> register`), then `alpi setup → Gateways → Signal` stores the daemon URL + allowlist of sender numbers.

**Estimated LOC:** ~200 (HTTP client + polling loop + send).

**Blocker:** requires extra SIM / VoIP number. Real cost: ~$5/mo (Twilio / JustCall). Nicho unless you want E2EE + self-hosted.

### Σ.1. Mixture-of-agents (stretch goal)

Spawn multiple LLMs on the same prompt, aggregate answers with a final synthesizer. Hermes has this as `mixture_of_agents_tool.py`. Use case: hard decisions where one model is weak and you want "wisdom of crowds" at 3× cost.

Not planned — tracked here because it's a known technique and might become useful if we hit a ceiling on single-model research quality.

### Σ.2. RL training / fine-tuning hooks (stretch goal)

Hermes has `rl_training_tool.py` for recording agent runs and building training datasets. If we ever want to fine-tune a smaller local model on your actual conversation patterns, the dataset-collection scaffold would live here.

Not planned. Research-grade, irrelevant for everyday personal use.

---

## Decisions discarded — don't relitigate

- **Go + Bubbletea rewrite.** Rejected.
- **rich.Live + prompt_toolkit inline UI.** Worked but had ceiling (no modals, suspend races). Replaced by Textual.
- **Full Textual app with sidebar + modals + fullscreen chrome** (first attempt). Rolled back as too heavy. Current is mother.py-style minimal.
- **Pending-approval gate for skills.** Tried in v0.1, removed in v0.2 commit 2e67830 ("live-by-default"). Friction outweighed benefit; security scanner is the gate.
- **Workspace wall on file tools.** Removed in v0.2 commit 3e2dc29. Without Layer 2 OS sandbox active, the wall was friction without isolation (terminal escaped it in one tool call). Now file tools follow terminal's posture: shared sensitive-path denylist, no workspace restriction.
- **Pending-approval files** (`pending_skills.md`, `pending_personality.md`). Replaced inline.
- **SQLite state.db.** Plain JSON files scan fast for <1000 sessions.
- **Auto-reflect on Ctrl+C.** Dangerous.
- **duckduckgo-search.** Deprecated → migrated to `ddgs`.
- **Post-session `/reflect` loop.** Tried it — `/reflect` slash + auto-trigger + `alpi/reflect.py` + 2 tests. Removed because Hermes doesn't do post-session reflection either, and the TUI implementation was broken (silenced Console output + `Prompt.ask` blocking the worker). Replaced by hardened system prompt + tool-description rules for inline `memory(add)` + `skill(create)`.
- **Regex-gating shell commands** to enforce sandbox. Too many false positives (legitimate `..`, env-var expansion, command substitution). Real enforcement needs OS-level sandbox (G).
- **`.bak` sibling on every `write_file`.** Tried it, rejected — clutters every directory alpi writes in. Kept only on memory files where it pays off.
- **`alpi setup → Identity` wizard for editing PERSONALITY.md.** Rejected after consideration. The `memory` tool already mutates `PERSONALITY.md` from inside chat, and the LLM captures nuance ("less formal but not jokey; respect my code-switching") that a form can't.
- **WhatsApp gateway.** Meta Business API requires company verification + is expensive; `whatsapp-web.js` / Baileys are reverse-engineered with frequent bans, and the attack surface is catastrophic (a compromised bot leaks every chat). Not worth shipping for a personal agent.
- **Discord gateway.** Bot tokens grant full server access — same blast-radius profile as Telegram with no added value, since Telegram covers the "messaging gateway" role already.
- **Slack gateway.** Enterprise-focused, per-workspace tokens with broad scopes, operationally heavy. No real personal-agent use case.

---

## Done — v0.1 + shipped v0.2 items

### v0.1 (released)

First usable cut. Textual TUI, 3-file memory with two-tier dedup, skill system with pending gate (later removed), workspace sandbox (later removed), `delegate` sub-agent (renamed `research` in v0.2), turn-based session format, interrupt-on-new-input, gateway (Telegram), schedule daemon (cron + once jobs), email tool + gateway channel, MCP client, multi-profile CLI, send_message tool, OS sandbox phase 1 + 2 (terminal denylist + opt-in OS sandbox), config tool + `/new` session.

### v0.2 (in progress — shipped so far)

| Commit | What landed |
|---|---|
| 2e67830 | Skills: unified `skill` tool, subdir contract, live-by-default, path guards |
| 2b73091 | Merge `glob` + `grep` into `search`; fix relative-path resolution |
| 62f7fa7 | TUI: surface inter-tool prose + reasoning tokens in live indicator |
| 3e2dc29 | File tools: drop workspace wall, match terminal's denylist posture |
| 211c022 | Skill tool: `patch`/`view` actions, `state/` subdir, scanner beef-up (~50 patterns) |
| fd1fec4 | TUI: reasoning persists across sessions, `show_reasoning` toggle, tighter layout |
| d2ceb74 | Tools: rename `delegate` → `research`, depth tiers driven by config |
| 4035327 | Skills: auto-inject index into system prompt + render skill name in tool cards |
| 9ed4139 | TUI: theme system + floating panels + anchored scroll + MarkdownStream (v0.2.1) |
| (next)  | Research: prefix inner `emit_state` with `step N/M · …` during tool loop (v0.2.2, R.1) |
| (next)  | `delegate` tool: write-capable sub-agent with file/terminal/web toolsets (v0.2.3, R.2) |
| (next)  | `read_image` tool: vision-capable image analysis, local path + http(s) URL with SSRF guard, SVG, model override (v0.2.4, D) |
| (next)  | `/model` as FloatingPanel (was ModalScreen); startup warn when no usable model; session-only model switch with reload on `/new`; OpenRouter user-driven model history (no catalog fetch); Anthropic/OpenAI fetch live with hardcoded fallback; setup flow polish — custom providers above "add new", active entry in accent, provider order, 3s fetch timeout (v0.2.5) |
| (next)  | `/mcps` panel listing running MCP servers with status and exposed tools (v0.2.6) |
| (next)  | Panel header elevation flips direction in light mode — `$surface-lighten-1` in dark, `$surface-darken-1` in light, so the header always contrasts with the body (v0.2.7) |
| (next)  | `AlpiHeader` responsive — 3 width tiers: wide (≥100) shows full `provider/model` path, medium keeps the short name, narrow (<60) drops the `ctx` label and halves the bar to 5 cells; `│` separators preserved across all tiers (v0.2.8) |
| (next)  | `AlpiTopBar` responsive — narrow (<60) drops `profile` / `workspace` labels, keeps values + `│` separators; matches `AlpiHeader` policy (v0.2.9) |
| (next)  | Drop `questionary`; `menu()` reimplemented directly on `prompt_toolkit` (O). Removes 5 workarounds in `ui.py` (empty qmark, FormattedText close hack, ANSI wipe, close sentinel, style overrides). Dependency gone from `pyproject.toml` (v0.2.10) |
| (next)  | Sandbox polish (P closed): `alpi setup → Sandbox` to toggle per profile, TUI top bar shows `sandbox on/off` next to workspace, `TerminalToolConfig` dataclass for clean `save()` delta, SECURITY.md + CONFIG.md drop "experimental" wording and reposition as "recommended for unattended profiles" (v0.2.11). Default stays `false` — dev workflows vary too much to pick a universal profile; the kill scenario is unattended runs, not interactive chat. |
| (next)  | Rename `alpi` → `alpi` across the codebase: package dir, CLI entrypoint, `~/.alpi` home, `ALPI_*` env vars, TUI brand, prompts, docs, tests. 357 tests green (v0.2.12) |
| (next)  | Remove the `config` tool (199 LOC + 112 LOC of tests). Config surface is now two-channel: `alpi setup` for structured settings (model, gateways, MCP, sandbox) + direct YAML edits for cosmetic knobs (`tui.*`, `max_steps_per_turn`, `poll_interval`, `fallback_models`). The conversational "change the accent to Facebook blue" case wasn't worth the tool-attention budget (v0.2.13) |
| (next)  | `/tools` panel filters out MCP-registered tools (`<server>:<tool>` shape) — they live in `/mcps`. Keeps `/tools` focused on alpi's own surface (v0.2.14) |
| (next)  | `todo` tool: `done: bool` → `status: pending\|in_progress\|completed` with a new `start` action. The description already promised "only ONE in_progress at a time" but the tool had no way to mark it — now the invariant is tool-enforced. Deliberately did not port hermes' IDs, merge mode, dedup, or /compact re-injection (v0.2.15) |
| (next)  | Ollama as a first-class provider (replaces the generic "Custom OpenAI-compatible endpoint" slot). Multiple named servers per profile (`home`, `gpu-box`, remote…), each with its own URL; model id becomes `<server-name>/<model>`. Live listing via `/api/tags` at setup time. Auto-resolves `num_ctx` from `/api/show` on every request so the model sees the full prompt instead of Ollama's 2K default — was the root cause of "never replies" with large system prompts. TUI header reads the resolved ctx as `ctx_window`; cost line hidden when `<= 0` for local models. `providers.custom` deleted entirely — no backwards-compat, no migration. ⚠ known limitation: small Ollama models (<7B) still hallucinate tool names regardless of transport (v0.2.15) |
| (next)  | `browser` tool shipped (B closed). Playwright + Chromium, 9 actions: `navigate`, `snapshot`, `click`, `type`, `scroll`, `press`, `screenshot`, `close`, `logout`. Uses Playwright's native `aria_snapshot()` for LLM-friendly page representation; targets elements by `role` + accessible `name` (or by visible `text`) — robust across re-renders, no fragile CSS selectors. `playwright-stealth` patches applied by default (navigator.webdriver hidden, plugins populated, etc.) so Cloudflare-lite protection doesn't block us. `screenshot` saves a PNG and returns the path; when `tools.browser.vision=true` in the profile's config, passing a `question` auto-chains the screenshot to `read_image` — otherwise path-only with a hint. Per-profile storage at `~/.alpi/profiles/<name>/browser/state.json` so cookies stay isolated across profiles. Single dedicated worker thread (`ThreadPoolExecutor(1)`) funnels every call to Playwright's sync API — sidesteps the "Cannot switch to a different thread" greenlet restriction in the TUI where each turn runs in a fresh Textual worker. SSRF via existing `check_url()`. ~400 LOC vs hermes' 2984 — deliberately dropped multi-provider abstraction, daemon process, `@e1` refs, LLM summarization, JS/console eval, Browserbase/BrowserUse cloud, orphan reaper (v0.2.16) |
| (next)  | `skill(action="validate")` shipped (Q closed). Four cheap correctness checks on a skill's `scripts/*.py`: `py_compile` for syntax, AST-walk + `find_spec` for missing third-party imports, OAuth race pattern (`webbrowser.open` before `serve_forever`/`handle_request`), and port coherence between `localhost:NNNN` mentioned in `SKILL.md` and `bind()` calls in code. Non-blocking — reports findings so the LLM decides what to do. ~150 LOC in `_skill_validate.py`. Did not port the 65-regex security scanner from hermes (we already had our own), nor the LLM-as-reviewer pattern (overlaps with asking alpi in chat "revisa esta skill") (v0.2.17) |
| (next)  | Batch parallel sub-agents shipped (R.3 closed). `research` and `delegate` now accept `tasks: [...]` (up to 3) and run them concurrently via `ThreadPoolExecutor(max_workers=3)`. Results aggregate into one report with per-task sections; failures are captured inline instead of short-circuiting the batch. Prerequisite: `alpi/tools/_state.py` refactored from module-global `_emit`/`_interrupt_getter`/`_usage_sink` to `contextvars.ContextVar`, so two workers can have distinct emit callbacks without racing. Worker threads re-seed `interrupt_getter` + `usage_sink` from the parent context (Python's `ThreadPoolExecutor` does not auto-propagate ContextVars) and install a per-task prefixed `emit`. Existing callers unchanged — the public API is identical; only `research.py` and `delegate.py` added `get_emit()` instead of reading `_emit` directly (v0.2.18) |
| (next)  | Roadmap sweep: extended backlog with 9 new items (TTS/STT local, Gmail OAuth, Signal, Anthropic OAuth as ToS-gray, approval system, schedule threat-scan, tool budget, OSV malware, stretch goals). Discarded WhatsApp/Discord/Slack with rationale (v0.2.19) |
| (next)  | Security hardening pack — three items shipped together (Y + Z + X, ~200 LOC): (1) **Tool result budget** in `alpi/tools/_budget.py` — `tools.budget.per_result_chars: 100_000` default, per-tool override via `tools.<name>.max_result_chars` (e.g. `-1` for unlimited on `read_file`), replaces the three hardcoded `[:10_000]` sites across engine/research/delegate with a clean elided suffix; (2) **OSV malware check** in `alpi/tools/_osv.py` — `api.osv.dev` query on skill `scripts/*.py` imports and MCP `npx` args at save time, blocks on MAL-* findings, fails open on network errors; (3) **Schedule prompt threat-scan** — reuses `scan_skill_body` patterns at both save and fire time so prompt-injected cron jobs don't escape into unattended runs. 17 new tests, 402 green total (v0.2.20) |
| (next)  | `read_image` auto-resize shipped (S closed). Pillow added as main dep (~3 MB). When `tools.read_image.auto_resize` (default `true`), any input image with a longer edge over `tools.read_image.max_edge` (default 1568 px — matches Anthropic's recommendation) is downscaled before base64-encoding. Aspect ratio preserved; PNGs with alpha stay PNG; everything else round-trips through JPEG q=85; SVG passthrough. Proactive (vs hermes' reactive "resize after API rejects too-large"). Typical saving: ~9× input-token cost on a 4K screenshot. 7 new tests, 409 green (v0.2.21) |
| (next)  | T.1 — rename `email` → `mail/imap` in preparation for a second backend. Pure refactor, no behaviour change. Classes `EmailClient`/`EmailError` → `ImapClient`/`ImapError`; gateway platform class `Email` → `Imap`; config `gateway.email.*` → `gateway.imap.*`; env vars `EMAIL_*` → `IMAP_*`/`SMTP_*`. Setup menu: "Email" → "IMAP". Tool name `email` kept (user-facing concept, backend-agnostic) (v0.2.22) |
| (next)  | T.2 — Gmail API (OAuth2) as a first-class parallel backend (T closed). `alpi/mail/gmail.py` implements the same 9 operations as `ImapClient` (list/search/read/send/reply/forward/move/delete/download_attachment) against `gmail.googleapis.com` with scopes `gmail.modify` + `gmail.send`. OAuth2 Authorization Code + PKCE with loopback callback server; refresh tokens stored per profile under `~/.alpi/<profile>/gmail_token.json` (0600, `fcntl`-locked). New `alpi/gateway/platforms/gmail.py` polls via `users.history.list` for delta-only fetches (no inbox rescans). Tool `email` gains an `account` param: auto-picks the only configured backend, demands explicit choice when both IMAP and Gmail are set. `send_message` platform enum grows `gmail`; delivery `_allowlist_env` maps gmail → `GMAIL_ALLOWED_SENDERS`. Setup wizard "Gateways → Gmail" walks through the GCP OAuth setup in 4 compact steps. Seed `.env.example` gains `GMAIL_CLIENT_ID` / `GMAIL_CLIENT_SECRET` / `GMAIL_ALLOWED_SENDERS`. Two post-landing correctness fixes: (a) `_list_history` no longer filters by `labelId: INBOX` — Gmail filter rules can route mail straight to custom labels (skipping INBOX), and those must still trigger alpi; SPAM/TRASH/DRAFT/CHAT/SENT excluded at processing time instead (matches IMAP's "only skip Junk" semantics); (b) `mark_as_read` moved from platform `listen()` to `run.py` post-allowlist via a new `IncomingMessage.ack` callback — previously automated/bulk and disallowed senders got `\Seen` / UNREAD removed without being processed, touching unrelated inbox traffic. 16 new tests (10 Gmail client + 6 dispatch). 425 green total (v0.2.23) |
| (next)  | M — voice shipped as two tools + Telegram inbound/outbound, no continuous voice mode. **tts** (`alpi/tools/tts.py`) wraps Edge TTS (Microsoft Neural voices, free, no API key); autoplays locally when `tools.tts.autoplay` on (default). Format auto-picked: MP3 in TUI, OGG/Opus on gateway (`ALPI_GATEWAY=1` subprocess env) for Telegram voice-note compatibility — MP3 is synthesised first and autoplayed (afplay decodes Opus badly), then ffmpeg-converted to OGG. Tool params: `text`, `voice`; `rate`/`pitch` are config-only (`tools.tts.{rate,pitch}`) to keep the LLM from fiddling with prosody every turn. 1000-char hard cap. Cache keyed by hash-of(voice, rate, pitch, format, text) under `~/.alpi/cache/tts/`. **stt** (`alpi/tools/stt.py`) wraps faster-whisper on CPU; spawns a subprocess per call to avoid `bad value(s) in fds_to_keep` when ctranslate2 forks under the Textual TUI's fd-munged event loop. Model (`tiny`/`base`/`small`/`medium`/`large-v3`) downloaded on first call into `~/.cache/huggingface/`. **send_message** grew an `attachment` param; Telegram platform picks the right endpoint by extension (`sendVoice` for `.ogg`, `sendAudio` for `.mp3`, etc.). **Telegram inbound voice notes** auto-transcribe: gateway downloads via `getFile`, caches under `~/.alpi/cache/inbound/`, runs `stt`, feeds `[voice note] <transcript>` as a normal text turn. Surface tag `[INBOUND TELEGRAM from <id>]` prepended so the LLM knows to chain `send_message(attachment=…)` when asked to deliver audio back. Engine post-processor `_strip_cache_noise` in `alpi/engine.py` filters lines containing `.alpi/cache/(tts|stt)/` from the assistant's final text so weak models (mimo-v2-flash parrots + hallucinates paths) can't leak the cache path into replies; TUI re-renders the `AssistantMessage` markdown with the cleaned buffer on `assistant_done`. Deliberately dropped vs hermes's 3050 LOC voice stack: continuous voice mode, streaming TTS, silence/VAD state machine, whisper-hallucination regex filter, 6 extra TTS providers, auxiliary LLM smart approval. 31 new tests (tts, stt, send_message attachment, telegram voice inbound, engine strip-cache). 458 green total (v0.2.25) |

| (next)  | Three tidy-ups bundled. (1) MCP tool-name OpenAI compatibility: MCP-exposed tools were named `<server>:<tool>` (e.g. `github:create_issue`), but OpenAI rejects any function name outside `^[a-zA-Z0-9_-]+$` — every OpenAI turn with MCP servers loaded crashed with `Invalid tools[N].function.name`. Anthropic/OpenRouter silently accepted the colon so the bug hid until an OpenAI model was picked. Switched separator to `__` (`github__create_issue`), sanitise server + tool names to collapse any other illegal char to `_`. (2) OpenAI + Anthropic provider lists curated manually instead of live-fetched from `/models` — raw catalogs include dozens of embeddings, TTS, moderation, and legacy variants that were never going to work as an agent brain, and the wizard scrolled forever. Dropped `_fetch()` + `_EXCLUDE_PREFIXES` in favour of a 5-model OpenAI list (`gpt-5.4` flagship, `gpt-5.4-mini` balanced, `gpt-5.4-nano` cheap, `gpt-5.3-codex` coding, `o3` heavy reasoning) and 4-model Anthropic list (`claude-opus-4-7` flagship, `claude-opus-4-6` 1M ctx, `claude-sonnet-4-6` balanced, `claude-haiku-4-5` fast). Each entry carries a short role tag rendered in the two-column setup wizard. Custom model id is still one click away for previews or anything not in the shortlist. Groq + Google were already curated. (3) Context window resolution: the TUI's header used to hardcode 200k for any non-Ollama model, which both under-reports (`gpt-5.4` is 1.05M, Claude 4.7 is 1M) and over-reports (`gpt-4o` is 128k). `_resolve_ctx_window` now probes `litellm.model_cost` after the Ollama branch — litellm ships an up-to-date cost/context DB for every mainstream provider, so we get accurate bars without maintaining a map in-repo. Ollama stays on its own `/api/show` path (local-only). Tests updated (v0.2.26) |

| (next)  | Brand cleanup across ~130 files. The Python package, binary, and home dir were already `alpi`, but the old nickname leaked everywhere — CLI help text, wizard banner titles, logger names, systemd/launchd service labels, User-Agent headers, tempfile prefixes, widget class names (`AlpiApp`, `AlpiHeader`, `AlpiTopBar`), function locals (`_locate_*`, `*_bin`, `*_home`), env vars (`ALPI_HOME`, `ALPI_PROFILE`, `ALPI_BIN`), shell aliases, docstrings, and docs. Rename staged in three regex passes: word-boundary, punctuated (`-`, `.`, `/`, `:`), and identifier-fragment (`_X_`, uppercase `X_`, capitalised `X`). Local git dir `~/git/alf/` kept intact (personal convention). 458 tests green (v0.2.27) |

| (next)  | tts autoplay skipped on gateway. Before, autoplay fired on every call — fine in TUI where the speaker is right there, but in gateway context the agent usually replies to a user who is on their phone, not sitting next to the Mac. Audio played through the server speakers reaches nobody and can interrupt anyone else in earshot. Autoplay now runs only when `ALPI_GATEWAY` is unset. Voice-note delivery to Telegram via `send_message(attachment=…)` is the real channel; the user taps play on their device. Also simplified the synthesis flow: MP3 for TUI (afplay-native) or OGG via ffmpeg for gateway (Telegram `sendVoice` needs Opus). Dropped the previous "synthesise MP3 first so autoplay has something afplay can decode, then convert to OGG for delivery" gymnastics — no longer needed now that gateway never autoplays. 458 tests green (v0.2.28) |

| (next)  | ToS stance codified. Removed **C** (OpenAI Codex OAuth against the private ChatGPT backend) and **V** (Anthropic Claude Pro/Code OAuth) from the backlog, marked both as rejected in the table. Added a "Principles" section to ROADMAP + README: alpi does not reverse-engineer the private OAuth flows that ChatGPT / Claude Code use for their official clients. Competitor agents (hermes, similar) ship these features; we do not. Users pay per-token API access through their own keys — honest + visible. If a vendor publishes an official OAuth-for-third-parties flow, we adopt it then. (v0.2.29) |

| (next)  | `allow_network=false` now blocks Python-native network tools too, not just the terminal subprocess. Before, toggling off `allow_network` only denied sockets to the shell sandbox (sandbox-exec / bwrap); `web_fetch`, `web_search`, `web_extract`, `browser`, `tts`, `send_message`, `email`, and URL-mode `read_image` all still reached out freely. That was semantically confusing — "network off" is meant to mean off, not "off for shell, on for everything else". Added `require_network(tool_name)` helper in `alpi/tools/_sandbox.py` that reads `tools.terminal.{sandbox,allow_network}` directly from `config.yaml` (no `load_dotenv` side effects that poisoned test env). Each network-using tool checks at entry and refuses with a clear error citing the config key. LLM transport (litellm) and gateway inbound listeners stay exempt — the LLM is the agent's brain and inbound is not exfiltration. TUI top bar now renders `offline` instead of `sandbox` when network is locked (muted style, no icons) so unattended profiles are auditable at a glance. 458 tests green (v0.2.30) |

| (next)  | TopBar shows the active profile's disk footprint next to its name (e.g. `profile default 2.8MB`). `~/.alpi/` for the default profile (with the `profiles/` subtree excluded so it doesn't double-count sibling profiles); `~/.alpi/profiles/<name>/` otherwise. `rglob`-based walk with 30 s cache; recomputed on profile / workspace / model changes. Hidden in narrow mode (< 60 columns). Useful hook for the planned cleanup wizard (reveal which profile has ballooned). Also documented alpi TUI's features/design choices in CONFIG.md — Textual vs hermes's prompt_toolkit CLI + separate Ink.js TUI, streaming markdown, tool cards with live state, inline reasoning tail, auto-suggest slash commands, responsive collapse, scroll anchoring. 458 tests green (v0.2.31) |

| (next)  | `alpi setup → Model` wizard reorders providers to put Ollama (local, offline-first) before cloud vendors. Existing Ollama servers + `Add Ollama` appear on top, then a blank separator, then OpenAI / Anthropic / OpenRouter / Google / Groq. The `Add Ollama` row carries the tag "local or remote — private, offline-first". Nudges new users toward the private path before they start pasting API keys. (v0.2.32) |

| (next)  | `alpi profile list` redesigned. Replaces old `* name /full/path` with: `◆` (solid) or `◇` (hollow) glyph in the profile's `tui.accent` colour, name, active model, disk size, and home-abbreviated path (`/Users/javi` → `~`, portable). Diamond shape carries the active/inactive distinction even in non-colour terminals. Rest of the row is plain — no dim, no bold, no per-column colours. Extracted `format_bytes`, `profile_size_label` (30 s cache, excludes sibling profiles when counting default), `shorten_home` from `alpi/tui/app.py` into `alpi/home.py` so CLI + TUI share one source. (v0.2.33) |

| (next)  | Telegram gateway offset now persists across restarts. Before, `self._offset = 0` on every `__init__` meant every restart replayed the last 24 h of unacked updates from Telegram — the bot answered the same inbound twice, the user saw ghost "hi" / "Hello" echoes. Saved to `~/.alpi/gateway/telegram-state.json` (matches the IMAP / Gmail pattern which already persisted UID / historyId). Offset written after each update is consumed so a mid-loop crash doesn't lose progress. Also added a one-shot "catching up on N message(s) from backlog" log on the first non-empty poll after startup, on all three platforms (telegram, imap, gmail) — makes it obvious when the agent is answering accumulated offline traffic vs real-time arrivals. Startup log now also includes the restored offset value for telegram so operators can spot a misconfigured state file. 458 tests green (v0.2.34) |

| (next)  | Humanised Playwright typing. `browser(type=...)` used `loc.fill(text)` which pastes the whole string instantly — a loud bot signature that anti-bot vendors (Cloudflare Turnstile, DataDome, PerimeterX) gate on. Replaced with `loc.clear()` + `loc.press_sequentially(text, delay=random.randint(lo, hi))` — letter by letter with a per-call random delay in ms. Config knobs: `tools.browser.human_typing` (default `true`) and `tools.browser.typing_delay_ms: [30, 80]` (jitter range). A small random 150-400 ms pause is also inserted before `press(Enter)` to avoid instant-submit after typing. Camoufox (J) dismissed from the backlog as a result — humanised playwright + stealth cover the real detection surface without the +230 MB Firefox binary. Three new backlog items (AA Cleanup wizard, AB Gateway profile split wizard, AC CHANGELOG auto-gen) added, all low-priority polish. Config loader reads YAML directly instead of going through `config.load()` to avoid `load_dotenv` polluting the process env (same trick as `require_network`). 459 tests green (v0.2.36) |

| (next)  | W shipped: command approval system on `terminal`. Replaces the static binary denylist (`_guards.check_command`) with a three-severity classifier (`safe`/`caution`/`dangerous`) in `alpi/tools/_approval.py`. 15 hardcoded patterns; safe runs through, caution prompts the user (TUI modal with four buttons: Once / Session / Always / Deny), dangerous always blocks unless `ALPI_YOLO=1` in env. Session approvals live in a module-level set (cleared on restart); Always persists the pattern description to `tools.terminal.approval.allowlist` in `config.yaml`. Non-TUI surfaces (gateway, schedule) auto-deny caution with an actionable error ("rerun from TUI or add to allowlist"). `ApprovalModal` (`alpi/tui/screens.py`) pushed via `call_from_thread` + `threading.Event` with 60 s timeout so the worker thread blocks cleanly on user input. Compared to hermes's `tools/approval.py` (~900 LOC): same 3-scope model, same surface-aware defaults, but dropped the smart-mode LLM auxiliary approver, the dual legacy/new pattern keys, the triple scanner stack (regex + Tirith + skills-guard), and the activity-heartbeat during blocking — ~200 LOC total. 13 new tests. 472 green. (v0.2.37) |

| (next)  | Approval panel polish + YOLO removal. The `ApprovalPanel` now mirrors `/model`: minimal CSS (transparent OptionList, `compact=True` row height, `max-height: 18`), option labels built with `rich.Text` bold name + muted hint, panel title carries severity + matched pattern (`⚠ CAUTION · recursive rm`). Command shown as an `entry-desc` static above the list with margin-bottom 1. Focus timed via `call_after_refresh` so Enter works first-shot (was stolen by `_show_panel`'s `set_focus(None)` before). Removed the `ALPI_YOLO` escape hatch — dangerous severity is now always-always blocked; if the user genuinely needs `mkfs` they run it from their shell, not through the agent. Also compressed the `terminal` rule in `system_prompt.md` from 7 lines to 2: "Don't refuse destructive commands in chat. `terminal` has a built-in approval gate that pauses for user confirmation. Just call it." (v0.2.38) |

| (next)  | AA shipped: Cleanup wizard (`alpi setup → Cleanup`). Scans the active profile's heavy directories — audio cache (tts output + inbound Telegram voice notes), sessions older than 30 days, gateway logs, schedule output — and shows each category with reclaimable size + file count in the setup menu. Picking a category opens a confirmation prompt ("Delete N file(s) · X from <label>?"); on yes, unlinks them and refreshes the list. Reuses `home.format_bytes` / `shorten_home`. Entry in the setup main menu shows the total reclaimable ("Cleanup · 1.8MB reclaimable" or "nothing to clean"). No automatic cleanup — only user-triggered; conservative by design. ~120 LOC. (v0.2.39) |

| (next)  | AB shipped: `alpi setup → Gateway service`. Simpler scope than the original "gateway vs TUI profile split" plan in the roadmap — we realised forcing a different model for the gateway breaks profile identity (a user talking to their `work` profile over Telegram should get the same model and memory as when they talk to it from the TUI). What users actually need is just the service registration automated. One toggle in the setup main menu: **Install** writes the launchd plist (macOS) or systemd `--user` unit (Linux) pointing at `alpi -p <profile> gateway start`; **Uninstall** removes it. Status line shows `running via launchd` / `not installed` / `no gateway configured` so the user sees state at a glance. Gated on at least one gateway channel (Telegram / IMAP / Gmail) having credentials; picking it before that shows an error and nudges them to configure first. Setup main menu reorganised into two groups separated by a blank line: config on top (Model, Gateways, MCPs, Voice), operational below (Sandbox, Gateway service, Cleanup). ~80 LOC. (v0.2.40) |
