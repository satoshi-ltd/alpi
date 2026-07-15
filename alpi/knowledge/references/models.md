# Models answer pack

alpi works with any model speaking the OpenAI tool-calling protocol via LiteLLM, but not every model is a good agent. What matters is tool-calling discipline across long sessions, not chat benchmark scores.

## Answer directly

- Tool-heavy profile -> strong tool-calling/router model (see Good primary routers).
- Cheap background work -> cheaper service model, only if the task is low-risk.
- Local/private -> capable local model; warn that weak local tool calling breaks multi-step workflows.
- Fallback models: stored in config, but do not promise automatic runtime escalation unless the installed version explicitly implements it.

## What matters

For skill-heavy profiles, quality shows up in routing:

- noticing a skill exists before reaching for generic tools,
- calling `skill(action="view", name=...)` with the right name,
- preserving tool schemas across long chains,
- passing correct params to `terminal`, `db`, `memory`, `session_search`,
- recovering when a tool result says a skill is inactive or invalid.

A cheap model can be excellent for status checks yet a bad primary for a many-skill profile.

The tables below use **OpenRouter routes** as the primary ID. Native routes also work for Anthropic and OpenAI if you have those provider keys — see the Native routes section at the bottom.

## Good primary routers

For profiles with many skills, persistent memory, database state, shell commands, or important side effects. Availability and provider names move; check the catalog if exact availability matters.

| Model | OpenRouter ID | Notes |
|---|---|---|
| owl-alpha | `owl-alpha` | Most-used OpenRouter model for tool-heavy workloads; 1M context, alpha channel (occasional wrapper churn). |
| DeepSeek V4 Pro | `deepseek/deepseek-v4-pro` | Strong tool discipline at 1M context; sensible flagship-class daily driver. |
| MiMo V2.5 Pro | `xiaomi/mimo-v2.5-pro` | Strong persistent-agent adoption; 1M context, good price/quality. |
| MiniMax M3 | `minimax/minimax-m3` | Mid-tier agent model; 512K context. |
| Claude Sonnet 5 | `anthropic/claude-sonnet-5` | Premium daily driver; strongest tool discipline at this tier. |

Pick one for a skill-heavy profile: start with owl-alpha, DeepSeek V4 Pro, MiMo V2.5 Pro, or Sonnet 5 by budget/provider.

## Cheap service turns

For scheduled-job turns, heartbeats, summaries, simple lookups, low-risk commands. Not for creating/debugging skills.

| Model | OpenRouter ID | Notes |
|---|---|---|
| DeepSeek V4 Flash | `deepseek/deepseek-v4-flash` | 1M context at the cheap-fast tier. |
| MiMo V2.5 | `xiaomi/mimo-v2.5` | Budget sibling to MiMo V2.5 Pro; 1M context. |
| Claude Haiku 4.5 | `anthropic/claude-haiku-4.5` | Cheap, fast, reasoning support; reliable on short chains. |
| GPT-5.6 Terra | `openai/gpt-5.6-terra` | Balanced OpenAI; router only when the skill catalog is small and clean. |
| GPT-5.6 Luna | `openai/gpt-5.6-luna` | Cheapest OpenAI tier; mechanical turns only. |

## High-stakes engineering

When a wrong tool call is expensive: refactors, code review, long debugging, schema changes, release work.

| Model | OpenRouter ID | Notes |
|---|---|---|
| Claude Fable 5 | `anthropic/claude-fable-5` | Ceiling — next-gen intelligence for long-running agents; most capable widely-released model. |
| Claude Opus 4.8 | `anthropic/claude-opus-4.8` | Flagship for complex agentic coding and enterprise engineering. |
| Claude Sonnet 5 | `anthropic/claude-sonnet-5` | Best daily premium balance for coding-heavy profiles. |
| GPT-5.6 Sol | `openai/gpt-5.6-sol` | OpenAI flagship; leads the coding-agent index, strong general engineering. |
| Nemotron 3 Super | `nvidia/nemotron-3-super-120b-a12b` | Open-weight engineering option; 256K context. |

## Local/private profiles

"Best" means best inside the local model ecosystem (Ollama, llama.cpp, vLLM), not best overall. The curated catalog does not pin specific local IDs — the field moves fast and the right pick depends on VRAM. Choose from current Qwen-coder, Gemma, codestral, or Mistral families. Expect more prompt sensitivity than cloud frontier models and tighter context windows.

For privacy-constrained work that needs more headroom than the hardware allows: `nvidia/nemotron-3-super-120b-a12b` (256K) or `deepseek/deepseek-v4-pro` (1M) — not local, but no proprietary frontier dependency.

## Native routes for Anthropic and OpenAI

When the user has ANTHROPIC_API_KEY or OPENAI_API_KEY, native routes work and usually mean lower latency.

| Provider | OpenRouter route | Native route |
|---|---|---|
| Anthropic | `anthropic/claude-fable-5` | `claude-fable-5` |
| Anthropic | `anthropic/claude-opus-4.8` | `claude-opus-4-8` (hyphens, not dots) |
| Anthropic | `anthropic/claude-sonnet-5` | `claude-sonnet-5` |
| Anthropic | `anthropic/claude-haiku-4.5` | `claude-haiku-4-5` |
| OpenAI | `openai/gpt-5.6-sol` | `gpt-5.6-sol` (alias `gpt-5.6`, no prefix) |
| OpenAI | `openai/gpt-5.6-terra` | `gpt-5.6-terra` |
| OpenAI | `openai/gpt-5.6-luna` | `gpt-5.6-luna` |

## Avoid as primary skill router

Usable as workers, not the main model for a skill-dependent profile:

- Nano-class: miss the skill index, skip `skill(action="view")`, fill params loosely. Low-risk mechanical turns only.
- Free-tier: rate limits and provider variability break tool loops mid-turn. Smoke tests, not daily automation.
- Small local models without proven tool calling: ok for privacy-constrained short tasks, poor for multi-tool routing.
- Wrapper-unstable models: avoid even with strong benchmarks; agents fail at integration boundaries first.

## Production setups

One primary model per profile; split roles across profiles (picks per tier in the tables above). Dynamic routing is opt-in via config: `tiers.fast` runs bounded side-work (compaction, memory reviewer, `research(depth=fast)`, `delegate(tier=fast)`, scheduled jobs with `tier: fast`), `tiers.deep` runs `research(depth=deep)` / `delegate(tier=deep)` plus the once-per-turn reactive escalation (3 consecutive tool failures or an empty reply; effort→high on the same model first, blocked past 80% of the daily budget), and `fallback_models` is the availability chain when the active model fails before producing any output. Unconfigured tiers resolve to the main model. Provider dashboards are a weak signal at best (biased by defaults/price/rate limits), and only when they reflect tool-heavy use, not chat benchmarks.

## Switching model

- `alpi setup` -> Model / Provider -> pick provider, pick model.
- `/model` slash command inside the TUI.
- Edit `model:` in `~/.alpi/config.yaml` or `~/.alpi/profiles/<name>/config.yaml`.

Per-profile: `alpi -p work` can run Sonnet 4.6 while `alpi -p personal` runs MiMo V2.5.

## Related topics

- Model config keys: `config`
- Skills and tool routing: `skills`
- Provider setup: `install`
