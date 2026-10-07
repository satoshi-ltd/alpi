# Model recommendations

alpi works with any model that speaks the OpenAI tool-calling protocol
via LiteLLM, but **not every model is a good agent**. The important
question is not "what scores highest on a benchmark?" but "what model
keeps choosing the right tool after 20 turns, with memory, skills,
shell commands, browser calls, and user-specific state in context?"

Use this page as a practical selector. Prices, context windows, and
provider wrappers move quickly; re-check them every 2-3 months.

Last updated: **2026-10-07** (Anthropic and OpenAI ids, windows and prices checked that day against the providers' model and pricing pages).

## What matters for alpi

For skill-heavy profiles, model quality mostly shows up in routing:

- noticing that a skill exists before reaching for generic tools,
- calling `skill(action="view", name=...)` with the right name,
- preserving tool schemas across long chains,
- passing the right parameters to `terminal`, `db`, `memory`, and
  `session_search`,
- recovering when a tool result says a skill is inactive or invalid.

A cheap model can be excellent for status checks and short commands
while still being a bad primary model for a profile with many skills.

## External usage signal

Public provider dashboards can be useful when they show model use in
tool-heavy agent workloads rather than chat-only benchmarks. Treat
that data as a weak signal, not a ranking: defaults, price, rate
limits, regional availability, and provider wrappers all bias usage.

OpenRouter's public leaderboard for the week ending 2026-09-28 put
DeepSeek V4.1 Flash first by tokens processed (about 20.8T), ahead of a
stealth model, with GLM 5.3 Flash third, DeepSeek V4 Flash 0731 sixth
and the new MiMo V2.6 Flash seventh. It ranks adoption, not quality, it
counts only traffic the caller did not mark private, and a single
large application can move a row several places.

## Two hazards, often confused

A **floating id** redirects. `~vendor/model-latest` resolves to whatever the
vendor ships next, so the agent changes underneath a running fleet with no
config change and no notice. On OpenRouter every alias carries the `~` prefix,
which makes them easy to refuse; `alias_target` in the models API confirms it.

A **preview or experimental id** carries a different risk: its endpoint can be
withdrawn, and that is a hard failure rather than a silent swap. Some carry a dated
snapshot in `canonical_slug`; others, like `deepseek/deepseek-v3.2-exp`, repeat
the id instead, which tells you the id is not visibly pinned but not what it
will resolve to tomorrow. The substring `exp` or `preview` alone does not tell
you which case you are in: `alias_target` is the reliable test for redirection,
a dated `canonical_slug` is evidence of pinning, and its absence is only the
absence of that evidence.

Prefer dated snapshots. Accept an experimental route only where losing it is
survivable, as with the vision route below.

## The advertised context is not your input budget

A slug's headline window is the ceiling of its best endpoint. Most of the
models here are also served by 256K endpoints, so the window you actually get
depends on routing. Narrowing the provider list reduces that spread, though a
single provider can publish several endpoints of its own, so it buys less
variance rather than a guaranteed window.

Separately, alpi does not offer the whole window as input. The per-model input
limit in `alpi/providers/openrouter_models.yaml` reserves a reply margin —
capped at 32,768 tokens, at the provider's own maximum output, and at a
quarter of the window, whichever is smallest — and `ctx_window` uses that
number to decide when to compact. Expect the usable figure to sit below the
advertised one on both counts.

## Pick by workload

The tables below use **OpenRouter routes** as the primary ID — a
single OPENROUTER_API_KEY covers every entry, and several picks
(MiMo, DeepSeek, MiniMax, Nemotron) only ship via
OpenRouter. For Anthropic and OpenAI you can also use **native
routes** if you have those provider keys; the convention is shown
under the tables.

### Skill router / long tool chains

Use these when the profile has many skills, persistent memory,
stateful tools, or real side effects. This is the default category for
daily interactive alpi use.

| Model | OpenRouter ID | Why |
|---|---|---|
| **DeepSeek V4.1 Flash** | `deepseek/deepseek-v4.1-flash` | **The alpi team's recommended default.** Low cache-read price, which suits an agent whose system prompt is large and stable. Text and image input, up to 1M context. First by weekly tokens on OpenRouter's public leaderboard (week ending 2026-09-28); released 2026-09-10 and not yet scored on the agentic index. |
| **GLM 5.3 Flash** | `z-ai/glm-5.3-flash` | Highest published agentic index of the cheap tier (Artificial Analysis, via OpenRouter, read 2026-09-11); up to 1.25M context, image and video input. Reasoning is mandatory and defaults to `max`; `low` and `high` are also accepted, so set `model_reasoning.effort` deliberately. |
| **DeepSeek V4 Flash 0731** | `deepseek/deepseek-v4-flash-0731` | Text only, up to 1.25M context, served by a large number of providers. Sixth by weekly tokens on OpenRouter's public leaderboard (week ending 2026-09-28). |
| **Claude Sonnet 5.5** | `anthropic/claude-sonnet-5.5` | Premium daily driver; strongest tool discipline and coding judgement at this tier. $2 / $10 per MTok, 1M context. |
| **MiMo V2.5 Pro** | `xiaomi/mimo-v2.5-pro` | Text only, up to 1M context. Scores above the base MiMo on the published agentic and coding indices, at about three times the input price. |
| **MiniMax M3** | `minimax/minimax-m3` | Mid-tier agent model. 1M is the announced ceiling; several of its endpoints serve 512K or 256K, so the window you get depends on routing. |

If you can only choose one model for a skill-heavy profile, start with
DeepSeek V4.1 Flash, the alpi team's recommendation. Move to Sonnet 5.5
when budget allows and tool discipline matters more than price.
`deepseek/deepseek-v4-pro` is no longer a recommended daily driver: the bare
id is pinned to the 2026-04 build, and a measured audit put it behind the
flash tier at many times the price.

### Cheap service turns

Use these for high-volume service turns, heartbeats, summaries, simple
lookups, and low-risk commands. They are not the first choice for
creating or debugging skills.

| Model | OpenRouter ID | Why |
|---|---|---|
| **DeepSeek V4.1 Flash** | `deepseek/deepseek-v4.1-flash` | Recommended default for service turns too; cheap cache read when the prompt is large and barely changes between turns. |
| **DeepSeek V4 Flash 0731** | `deepseek/deepseek-v4-flash-0731` | Cheapest model with a real agentic score; 1.25M context and broad provider support. |
| **MiMo V2.5** | `xiaomi/mimo-v2.5` | Budget sibling to MiMo V2.5 Pro; 1M context, useful for A/B testing cheap service profiles. |
| **Claude Haiku 4.5** | `anthropic/claude-haiku-4.5` | Cheap and fast with reasoning support; reliable for short-chain turns. $1 / $5 per MTok, 200K context. |
| **GPT-6 Luna** | `openai/gpt-6-luna` | Cheapest OpenAI tier ($0.10 / $0.50 per MTok, cached input $0.01, 1.05M context); fine for mechanical, high-volume turns, not for skill work. |

### Vision for `read_image`

Use `deepseek/deepseek-v4-flash-vision-exp` as the profile's **Vision
model** when its main model is text-only. This OpenRouter route accepts text
and images with a 1M context window, but it is explicitly experimental: keep
the main model as the fallback rather than making the vision route the whole
agent. The setting applies to `read_image` and opt-in browser screenshot
analysis. Images attached directly to chat remain part of the main model's
turn.

### High-stakes engineering

Use these when a wrong tool call is expensive: refactors, code review,
long debugging sessions, schema changes, release work.

| Model | OpenRouter ID | Why |
|---|---|---|
| **Claude Fable 5.1** | `anthropic/claude-fable-5.1` | Ceiling: Anthropic's most capable widely released model, for long-running agents. $10 / $50 per MTok, 1M context. |
| **Claude Opus 5.5** | `anthropic/claude-opus-5.5` | Flagship for complex agentic coding; supersedes Opus 5 at a lower price ($4 / $20 per MTok), 1M context. Thinking cannot be turned off; its default effort is `medium`. |
| **Claude Sonnet 5.5** | `anthropic/claude-sonnet-5.5` | Best daily premium balance for coding-heavy profiles. |
| **GPT-6 Astra** | `openai/gpt-6-astra` | OpenAI flagship ($10 / $50 per MTok, cached input $1, 1.05M context). |
| **GPT-6.1 Sol** | `openai/gpt-6.1-sol` | OpenAI's recommended balance of intelligence and cost ($2 / $10 per MTok, cached input $0.10, 1.05M context), strong at coding. |
| **Nemotron 3 Super** | `nvidia/nemotron-3-super-120b-a12b` | Open-weight engineering option; 256K context. |

OpenAI's 1.05M is the whole window, input plus output. On the native
OpenAI route alpi budgets the conversation against the input share LiteLLM
reports (about 922K); through OpenRouter it uses OpenRouter's limit (about
1.017M). Either way it compacts before the limit.

### Local / sovereign profiles

"Best" here means best inside the local model ecosystem (Ollama,
llama.cpp, vLLM), not best overall. The curated catalog does not pin
specific local IDs because the field moves fast and the right pick
depends on your VRAM budget. Choose from current Qwen-coder, Gemma,
codestral, or Mistral families. Expect more prompt sensitivity than
cloud frontier models and tighter context windows.

For privacy-constrained work that needs more headroom than your
hardware allows, consider an open-weight cloud model like
`nvidia/nemotron-3-super-120b-a12b` (256K) or
`deepseek/deepseek-v4-pro` (1M) — not local, but no proprietary
frontier dependency.

### Native routes for Anthropic and OpenAI

If you have ANTHROPIC_API_KEY or OPENAI_API_KEY, you can use native
routes instead of the OpenRouter aliases. Native usually means lower
latency and one less layer to break.

| Provider | OpenRouter route | Native route |
|---|---|---|
| Anthropic | `anthropic/claude-fable-5.1` | `claude-fable-5-1` (hyphens, not dots) |
| Anthropic | `anthropic/claude-opus-5.5` | `claude-opus-5-5` |
| Anthropic | `anthropic/claude-sonnet-5.5` | `claude-sonnet-5-5` |
| Anthropic | `anthropic/claude-haiku-4.5` | `claude-haiku-4-5` |
| OpenAI | `openai/gpt-6-astra` | `gpt-6-astra` |
| OpenAI | `openai/gpt-6.1-sol` | `gpt-6.1-sol` |
| OpenAI | `openai/gpt-6-luna` | `gpt-6-luna` |

Claude refuses a forced tool call whenever it is thinking: always on Fable,
Opus 5.5 and Sonnet 5.5, and on any current Claude model with an effort set. alpi
never forces one then (a workgroup turn's final handoff asks for
`workgroup_post` without forcing it, and posts a continuation itself if the
model does not call it).

#### Superseded, still served

These still answer, so a profile that pins one keeps working, but the
curated pickers no longer offer them: Claude Fable 5, Opus 5, Opus 4.8 and
Sonnet 5 (replaced by Fable 5.1, Opus 5.5 and Sonnet 5.5); GPT-6 Sol
(replaced by GPT-6.1 Sol at the same price, half the cached-input price) and
the GPT-5.6 Sol, Terra and Luna lineup (replaced by the GPT-6 family).
alpi never changes a profile's configured model; switch it yourself with
`alpi setup` or the apps.

## Prompt caching

Prompt caching is transparent and best-effort. Every supported provider and
model still runs when caching is unavailable: alpi asks LiteLLM for an explicit
cache marker only when that model reports support, and otherwise sends the
normal request. OpenRouter routes additionally receive a hashed, stable
conversation `session_id` to improve routing affinity; raw profile, session,
peer, schedule, and workgroup identifiers are never sent.

Telemetry varies by provider and model. A reported zero is a measured cache
miss; missing cache fields are `no provider cache data`, not a fabricated zero.
OpenRouter, native Anthropic, DeepSeek, and other LiteLLM routes therefore share
the same execution path but may expose different cache counts, discounts, or
cost precision. This affects observability, never whether the response is
accepted.

The cacheable prefix is the stable system prompt. Fresh clock/workgroup/skill/
relay context rides the user turn so normal conversation growth stays
append-only. First contact, switching model, changing tools or system content,
compaction, resume, reset, and edit-and-resend can legitimately produce a cold
or rewritten prefix. Inspect `/status` for the current session and `alpi digest`
for a calendar-day aggregate; use the provider dashboard as billing authority.

## Not recommended as the primary skill router

These can still be useful as workers, but they should not be the main
model for a profile that depends on skills:

- **Nano-class models**: too likely to miss the skill index, skip
  `skill(action="view")`, or fill tool parameters loosely. Use only for
  low-risk, mechanical turns.
- **Free-tier models**: rate limits and provider variability can break
  tool loops mid-turn. Good for smoke tests, not daily automation.
- **Small local models without proven tool calling**: acceptable for
  privacy-constrained short tasks, poor fit for multi-tool skill
  routing.
- **Models with wrapper instability**: avoid as the primary model even
  when benchmark numbers look strong. Agents fail at integration
  boundaries first.

## Production setups

alpi selects one primary model per profile, with optional dynamic
routing around it (see `docs/CONFIG.md` → `tiers` / `fallback_models`):

- `tiers.fast` — a cheap model for bounded side-work: compaction
  summaries, the memory reviewer, bio drafting, `research(depth=fast)`,
  and `delegate` / scheduled jobs that opt into `tier: fast`.
- `tiers.deep` — a stronger model for `research(depth=deep)`,
  `delegate(tier=deep)`, and reactive escalation: after 3 consecutive
  tool failures or an empty reply the turn escalates once (effort→high
  on the same model first, else the deep tier), never past 80% of
  `budget.daily_usd`.
- `fallback_models` — availability chain when the active model fails
  before producing output (provider down, credits exhausted).

Unconfigured tiers always resolve to the main model, so none of this
changes behavior until you opt in. Profiles still split roles best:

- **Personal skill-heavy profile**: GLM 5.3 Flash, Sonnet 5.5, or
  MiMo V2.5 Pro.
- **High-volume service profile**: DeepSeek V4 Flash 0731,
  DeepSeek V4.1 Flash, MiMo V2.5, Haiku 4.5, or GPT-6 Luna, with
  fewer skills and tighter prompts.
- **Engineering profile**: Sonnet 5.5, Opus 5.5, Fable 5.1,
  GPT-6.1 Sol or GPT-6 Astra.
- **Local/private profile**: a current Qwen-coder, Gemma, or codestral
  family model, sized to your VRAM.

## Switching model

Three ways, any of them works:

- `alpi setup` -> Model / Provider -> pick provider, pick model.
- `/model` slash command inside the TUI.
- Edit `model:` in `~/.alpi/config.yaml` or
  `~/.alpi/profiles/<name>/config.yaml`.

The choice is per-profile. `alpi -p work` can run Sonnet 5.5 while
`alpi -p personal` runs MiMo V2.5 without interference.
