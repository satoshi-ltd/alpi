# Model recommendations

alpi works with any model that speaks the OpenAI tool-calling protocol
via LiteLLM, but **not every model is a good agent**. The important
question is not "what scores highest on a benchmark?" but "what model
keeps choosing the right tool after 20 turns, with memory, skills,
shell commands, browser calls, and user-specific state in context?"

Use this page as a practical selector. Prices, context windows, and
provider wrappers move quickly; re-check them every 2-3 months.

Last updated: **2026-06-20**.

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
include owl-alpha, MiMo V2.5 Pro / V2.5, DeepSeek V4 Pro / Flash,
MiniMax M3, Claude Sonnet 4.6 / Opus 4.8, Nemotron 3 Super, and
OpenAI GPT-5.5 / 5.4-mini.

## Pick by workload

The tables below use **OpenRouter routes** as the primary ID — a
single OPENROUTER_API_KEY covers every entry, and several picks
(owl-alpha, MiMo, DeepSeek, MiniMax, Nemotron) only ship via
OpenRouter. For Anthropic and OpenAI you can also use **native
routes** if you have those provider keys; the convention is shown
under the tables.

### Skill router / long tool chains

Use these when the profile has many skills, persistent memory,
stateful tools, or real side effects. This is the default category for
daily interactive alpi use.

| Model | OpenRouter ID | Why |
|---|---|---|
| **owl-alpha** | `owl-alpha` | Most-used OpenRouter model for tool-heavy workloads; 1M context, alpha channel — fast iteration, expect occasional wrapper churn. |
| **DeepSeek V4 Pro** | `deepseek/deepseek-v4-pro` | Strong tool discipline at 1M context; sensible flagship-class daily driver. |
| **MiMo V2.5 Pro** | `xiaomi/mimo-v2.5-pro` | Strong adoption in persistent-agent workloads; 1M context, good price-for-quality. |
| **MiniMax M3** | `minimax/minimax-m3` | Mid-tier agent model; 512K context, decent for persistent sessions. |
| **Claude Sonnet 4.6** | `anthropic/claude-sonnet-4.6` | Premium daily driver; strongest tool discipline and coding judgement at this tier. |

If you can only choose one model for a skill-heavy profile, start with
owl-alpha, DeepSeek V4 Pro, MiMo V2.5 Pro, or Sonnet 4.6 depending on
budget and provider preference.

### Cheap service turns

Use these for high-volume service turns, heartbeats, summaries, simple
lookups, and low-risk commands. They are not the first choice for
creating or debugging skills.

| Model | OpenRouter ID | Why |
|---|---|---|
| **DeepSeek V4 Flash** | `deepseek/deepseek-v4-flash` | 1M context at the cheap-fast tier; the headroom is useful even for short turns. |
| **MiMo V2.5** | `xiaomi/mimo-v2.5` | Budget sibling to MiMo V2.5 Pro; 1M context, useful for A/B testing cheap service profiles. |
| **Claude Haiku 4.5** | `anthropic/claude-haiku-4.5` | Cheap and fast with reasoning support; reliable for short-chain turns. |
| **GPT-5.4 Mini** | `openai/gpt-5.4-mini` | Reasonable OpenAI budget pick for simple tool use; acceptable as a router only when the skill catalog is clean and small. |
| **GPT-5.4 Nano** | `openai/gpt-5.4-nano` | Cheapest OpenAI tier; mechanical turns only. |

### High-stakes engineering

Use these when a wrong tool call is expensive: refactors, code review,
long debugging sessions, schema changes, release work.

| Model | OpenRouter ID | Why |
|---|---|---|
| **Claude Opus 4.8** | `anthropic/claude-opus-4.8` | Flagship — expensive ceiling for hard multi-step engineering and long-context judgement. |
| **Claude Sonnet 4.6** | `anthropic/claude-sonnet-4.6` | Best daily premium balance for coding-heavy profiles. |
| **GPT-5.5** | `openai/gpt-5.5` | OpenAI flagship; strong general engineering. |
| **GPT-5.5 Pro** | `openai/gpt-5.5-pro` | Extended-reasoning variant for the hardest multi-step tasks. |
| **o3** | `openai/o3` | Heavy-reasoning specialist; not a router, use for one-shot analysis. |
| **GPT-5.3 Codex** | `openai/gpt-5.3-codex` | Coding-specific; good for repo-tooling profiles. |
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
| Anthropic | `anthropic/claude-opus-4.8` | `claude-opus-4-8` (hyphens, not dots) |
| Anthropic | `anthropic/claude-sonnet-4.6` | `claude-sonnet-4-6` |
| Anthropic | `anthropic/claude-haiku-4.5` | `claude-haiku-4-5` |
| OpenAI | `openai/gpt-5.5` | `gpt-5.5` (no prefix) |
| OpenAI | `openai/gpt-5.5-pro` | `gpt-5.5-pro` |
| OpenAI | `openai/gpt-5.4-mini` | `gpt-5.4-mini` |
| OpenAI | `openai/gpt-5.4-nano` | `gpt-5.4-nano` |
| OpenAI | `openai/gpt-5.3-codex` | `gpt-5.3-codex` |
| OpenAI | `openai/o3` | `o3` |

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

alpi currently selects one primary model per profile. `fallback_models`
exists in config, but do not rely on automatic runtime escalation unless
your installed version explicitly implements it. Use profiles to split
roles today:

- **Personal skill-heavy profile**: owl-alpha, DeepSeek V4 Pro,
  MiMo V2.5 Pro, or Sonnet 4.6.
- **High-volume service profile**: DeepSeek V4 Flash, MiMo V2.5,
  Haiku 4.5, or GPT-5.4-mini, with fewer skills and tighter prompts.
- **Engineering profile**: Sonnet 4.6, Opus 4.8, GPT-5.5, GPT-5.5-pro,
  or o3.
- **Local/private profile**: a current Qwen-coder, Gemma, or codestral
  family model, sized to your VRAM.

## Switching model

Three ways, any of them works:

- `alpi setup` -> Model / Provider -> pick provider, pick model.
- `/model` slash command inside the TUI.
- Edit `model:` in `~/.alpi/config.yaml` or
  `~/.alpi/profiles/<name>/config.yaml`.

The choice is per-profile. `alpi -p work` can run Sonnet 4.6 while
`alpi -p personal` runs MiMo V2.5 without interference.
