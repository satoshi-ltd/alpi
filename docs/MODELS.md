# Model recommendations

alpi works with any model that speaks the OpenAI tool-calling protocol
via LiteLLM, but **not every model is a good agent**. The important
question is not "what scores highest on a benchmark?" but "what model
keeps choosing the right tool after 20 turns, with memory, skills,
shell commands, browser calls, and user-specific state in context?"

Use this page as a practical selector. Prices, context windows, and
provider wrappers move quickly; re-check them every 2-3 months.

Last updated: **2026-07-15**.

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

Common high-usage models in tool-heavy agent workloads currently
include MiMo V2.5 Pro / V2.5, DeepSeek V4 Pro / V4 Flash, MiniMax M3,
Claude Sonnet 5 / Opus 4.8 / Fable 5, Nemotron 3 Super, and OpenAI
GPT-5.6 Sol / Terra.

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
| **DeepSeek V4 Pro** | `deepseek/deepseek-v4-pro` | Strong tool discipline at 1M context; sensible flagship-class daily driver. |
| **MiMo V2.5 Pro** | `xiaomi/mimo-v2.5-pro` | Strong adoption in persistent-agent workloads; 1M context, good price-for-quality. |
| **MiniMax M3** | `minimax/minimax-m3` | Mid-tier agent model; 512K context, decent for persistent sessions. |
| **Claude Sonnet 5** | `anthropic/claude-sonnet-5` | Premium daily driver; strongest tool discipline and coding judgement at this tier. |

If you can only choose one model for a skill-heavy profile, start with
DeepSeek V4 Pro, MiMo V2.5 Pro, or Sonnet 5 depending on budget and
provider preference.

### Cheap service turns

Use these for high-volume service turns, heartbeats, summaries, simple
lookups, and low-risk commands. They are not the first choice for
creating or debugging skills.

| Model | OpenRouter ID | Why |
|---|---|---|
| **DeepSeek V4 Flash** | `deepseek/deepseek-v4-flash-0731` | 1M context at the cheap-fast tier, and the cheapest way to get that headroom. Pinned snapshot rather than the moving alias, so a silent swap can't change behaviour under you. Replies cap at 64K output. |
| **MiMo V2.5** | `xiaomi/mimo-v2.5` | Budget sibling to MiMo V2.5 Pro; 1M context, useful for A/B testing cheap service profiles. |
| **Claude Haiku 4.5** | `anthropic/claude-haiku-4.5` | Cheap and fast with reasoning support; reliable for short-chain turns. |
| **GPT-5.6 Terra** | `openai/gpt-5.6-terra` | Balanced OpenAI tier for simple tool use; acceptable as a router when the skill catalog is clean and small. |
| **GPT-5.6 Luna** | `openai/gpt-5.6-luna` | Cheapest OpenAI tier; mechanical turns only. |

### High-stakes engineering

Use these when a wrong tool call is expensive: refactors, code review,
long debugging sessions, schema changes, release work.

| Model | OpenRouter ID | Why |
|---|---|---|
| **Claude Fable 5** | `anthropic/claude-fable-5` | Ceiling — next-gen intelligence for long-running agents; most capable widely-released model. |
| **Claude Opus 4.8** | `anthropic/claude-opus-4.8` | Flagship for complex agentic coding and enterprise engineering. |
| **Claude Sonnet 5** | `anthropic/claude-sonnet-5` | Best daily premium balance for coding-heavy profiles. |
| **GPT-5.6 Sol** | `openai/gpt-5.6-sol` | OpenAI flagship; leads the coding-agent index, strong general engineering. |
| **Nemotron 3 Super** | `nvidia/nemotron-3-super-120b-a12b` | Open-weight engineering option; 256K context. |

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
| Anthropic | `anthropic/claude-fable-5` | `claude-fable-5` |
| Anthropic | `anthropic/claude-opus-4.8` | `claude-opus-4-8` (hyphens, not dots) |
| Anthropic | `anthropic/claude-sonnet-5` | `claude-sonnet-5` |
| Anthropic | `anthropic/claude-haiku-4.5` | `claude-haiku-4-5` |
| OpenAI | `openai/gpt-5.6-sol` | `gpt-5.6-sol` (alias `gpt-5.6`, no prefix) |
| OpenAI | `openai/gpt-5.6-terra` | `gpt-5.6-terra` |
| OpenAI | `openai/gpt-5.6-luna` | `gpt-5.6-luna` |

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

- **Personal skill-heavy profile**: DeepSeek V4 Pro, MiMo V2.5 Pro,
  or Sonnet 5.
- **High-volume service profile**: DeepSeek V4 Flash, MiMo V2.5,
  Haiku 4.5, or GPT-5.6 Terra, with fewer skills and tighter prompts.
- **Engineering profile**: Sonnet 5, Opus 4.8, Fable 5, or
  GPT-5.6 Sol.
- **Local/private profile**: a current Qwen-coder, Gemma, or codestral
  family model, sized to your VRAM.

## Switching model

Three ways, any of them works:

- `alpi setup` -> Model / Provider -> pick provider, pick model.
- `/model` slash command inside the TUI.
- Edit `model:` in `~/.alpi/config.yaml` or
  `~/.alpi/profiles/<name>/config.yaml`.

The choice is per-profile. `alpi -p work` can run Sonnet 5 while
`alpi -p personal` runs MiMo V2.5 without interference.
