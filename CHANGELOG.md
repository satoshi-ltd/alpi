# Changelog

## v0.2.47 — 2026-04-23

### setup
- first-time help text in gateway/MCP wizards (AG closed) (`88e4086`)

## v0.2.46 — 2026-04-23

### cli
- shrink surface, unify logs, add live doctor (AD/AE/AF) (`b110569`)

## v0.2.41 — 2026-04-23

### setup
- normalise wizard UX across the board (`b46929f`)

## v0.2.40 — 2026-04-23

### gateway
- service install/uninstall wizard (AB closed) (`f372ec0`)

## v0.2.39 — 2026-04-22

### cleanup
- `alpi setup → Cleanup` wizard (AA closed) (`5825e87`)

## v0.2.38 — 2026-04-22

### approval
- panel styled like /model, YOLO removed (`6be95ca`)

## v0.2.37 — 2026-04-22

### approval
- three-severity command gate for terminal (W closed) (`2064d10`)

## v0.2.36 — 2026-04-22

### browser
- humanised typing, dismiss camoufox (`a54425f`)

## v0.2.35 — 2026-04-22

### tidy
- move PERSONALITY.md under memories/, gmail_token under secrets/ (`2914fe0`)

## v0.2.34 — 2026-04-22

### gateway
- persist telegram offset, log backlog catch-up (`418d2fb`)

## v0.2.33 — 2026-04-22

### misc
- profile list: accent diamond + model + size + abbreviated path (`4a832b6`)

## v0.2.32 — 2026-04-22

### setup
- reorder Model wizard — Ollama first, cloud second (`1e4b119`)

## v0.2.31 — 2026-04-22

### tui
- profile disk size in top bar + document TUI features (`416f203`)

## v0.2.30 — 2026-04-22

### sandbox
- allow_network=off now blocks Python-native network tools (`83f9d00`)

## v0.2.29 — 2026-04-22

### tos
- remove C (Codex OAuth) and V (Anthropic OAuth) from backlog (`5e77f17`)

## v0.2.28 — 2026-04-22

### misc
- tts + send_message: autoplay off on gateway, terse outputs (`5e80755`)

## v0.2.27 — 2026-04-22

### brand
- nickname → alpi across ~130 files (`00722a9`)

## v0.2.26 — 2026-04-22

### misc
- mcp + providers: OpenAI-compat tool names, curated lists, ctx window (`6ddf316`)

## v0.2.25 — 2026-04-22

### voice
- tts + stt + telegram voice inbound/outbound (M closed) (`1af86d6`)

## v0.2.23 — 2026-04-22

### gmail
- OAuth2 gateway + mail tool dispatch (T closed) (`d8b644e`)

## v0.2.22 — 2026-04-22

### refactor
- email → mail/imap rename for upcoming Gmail backend (T commit 1/3) (`d9cd7de`)

## v0.2.21 — 2026-04-22

### read_image
- auto-resize oversized images before vision (S closed) (`2823b4b`)

## v0.2.20 — 2026-04-22

### misc
- security pack: tool budget + OSV malware + schedule threat-scan (`8d79faf`)

## v0.2.19 — 2026-04-22

### roadmap
- extend backlog with TTS/STT, Gmail/Signal, approval, OSV (`2e504f3`)

## v0.2.18 — 2026-04-22

### research/delegate
- batch parallel tasks (R.3 closed) (`5eec824`)

## v0.2.17 — 2026-04-22

### skill
- add validate action for correctness checks (Q closed) (`88e2721`)

## v0.2.16 — 2026-04-22

### browser
- Playwright tool with stealth-by-default and optional vision (`9710574`)

## v0.2.15 — 2026-04-21

### ollama
- first-class provider + kill the generic custom slot (`9a3b4e1`)

### todo
- add in_progress status to match the prompt promise (`664e184`)

## v0.2.14 — 2026-04-21

### tui
- /tools skips MCP-registered tools (`836f28a`)

## v0.2.13 — 2026-04-21

### misc
- remove the config tool — config is user-owned (`ba7ce49`)

## v0.2.12 — 2026-04-21

### rename
- alf → alpi across the entire codebase (`85384c3`)

## v0.2.11 — 2026-04-21

### misc
- sandbox polish: promote from "experimental" to per-profile opt-in (`679fca8`)

## v0.2.10 — 2026-04-21

### ui
- drop questionary, build menu()+text() directly on prompt_toolkit (`1063bf2`)

## v0.2.9 — 2026-04-21

### tui
- AlfTopBar drops labels in narrow mode (`a5fd740`)

## v0.2.8 — 2026-04-21

### tui
- AlfHeader adapts to available width (`c065e14`)

## v0.2.7 — 2026-04-21

### tui
- panel header elevation flips in light mode (`6c02eeb`)

## v0.2.6 — 2026-04-21

### tui
- /mcps panel listing running MCP servers (`b13ed62`)

## v0.2.5 — 2026-04-21

### tui+setup
- /model as panel, user-driven openrouter, live anthropic/openai fetch (`f64bebf`)

## v0.2.4 — 2026-04-21

### read_image
- vision tool with URL, SVG, and model-override (D) (`b71ce2f`)

## v0.2.3 — 2026-04-21

### delegate
- write-capable sub-agent with file/terminal/web toolsets (R.2) (`fdf999a`)

## v0.2.2 — 2026-04-21

### research
- prefix inner emit_state with step counter (R.1) (`1722fab`)

## v0.2.1 — 2026-04-21

### tui
- theme system + floating panels + scaffold polish (`9ed4139`)

## v0.2.0 — 2026-04-21

### docs
- add MODELS.md — tiered model recommendations for agent use (`df29cfc`)
- record identity-wizard decision as rejected (`60122b7`)
- split CONTEXT into ARCHITECTURE + ROADMAP, position alf as lighter Hermes, bump to v0.2.0 (`6b946e4`)

### fix
- propagate active profile to tool context + sharpen memory prompt (`1470bdb`)

### gateway
- stream tool traces + typing indicator; simplify allowlist (`fe3a3d4`)

### gateway/schedule
- fail fast if the profile has no usable workspace (`04bdaba`)

### schedule
- fix immediate-fire, UTC vs local tz, duplicate delivery (`3dd4522`)
- kind=once and LLM time grounding (`1fc3610`)

### skills
- unified tool, subdir contract, live-by-default, path guards (`2e67830`)
- auto-inject index into system prompt + render skill name in tool cards (`4035327`)

### tooling
- level-2 comment cleanup across alf/ (`a07e40a`)

### tools
- rename delegate → research, depth tiers driven by config (`d2ceb74`)

### tui
- surface inter-tool prose + reasoning tokens in live indicator (`62f7fa7`)
- reasoning persists across sessions, show_reasoning toggle, tighter layout (`fd1fec4`)

### web_search
- dedup by domain + lean description (`b04b394`)

### misc
- remove stray test artifacts and fix layout in README (`56d1711`)
- send_message tool + delivery refactor (`6e31ace`)
- schedule daemon: tool + CLI + rename from cron (`2245e42`)
- install/uninstall for gateway + schedule (launchd + systemd) (`cd62da0`)
- profile CLI + drop all migration/legacy code (`630f97c`)
- email subsystem + alf setup UX polish (`c67e618`)
- email gateway channel + per-platform config namespace (`4691df8`)
- mcp client — user-configured MCP servers as alf tools (`0d376ac`)
- setup UX: shared ui primitives, profile-scoped status, CLI polish (`7a81770`)
- memory tool: compress description to Hermes-style, keep all invariants (`b214ce6`)
- tool descriptions: compress terminal/email/schedule/send_message/session_search (`19f1287`)
- config polish: minimal seed, config tool, /new session, accent spinners (`2dadc09`)
- tool descriptions: restore CALL directives + English-only language rule (`6be1685`)
- security phase 1: terminal denylist, SSRF block, tool-output injection scan (`a54d99d`)
- security phase 2: opt-in OS sandbox (sandbox-exec / bubblewrap) (`e78b428`)
- merge glob + grep into search; fix relative-path resolution (`2b73091`)
- file tools: drop workspace wall, match terminal's denylist posture (`3e2dc29`)
- skill tool: patch/view actions, state/ subdir, scanner beef-up (`211c022`)

## v0.1.0 — 2026-04-19

### misc
- initial commit — alf v0.1 (`a0c7630`)
