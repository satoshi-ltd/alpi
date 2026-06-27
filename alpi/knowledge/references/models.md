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
| Claude Sonnet 4.6 | `anthropic/claude-sonnet-4.6` | Premium daily driver; strongest tool discipline at this tier. |

Pick one for a skill-heavy profile: start with owl-alpha, DeepSeek V4 Pro, MiMo V2.5 Pro, or Sonnet 4.6 by budget/provider.

## Cheap service turns

For scheduled-job turns, heartbeats, summaries, simple lookups, low-risk commands. Not for creating/debugging skills.

| Model | OpenRouter ID | Notes |
|---|---|---|
| DeepSeek V4 Flash | `deepseek/deepseek-v4-flash` | 1M context at the cheap-fast tier. |
| MiMo V2.5 | `xiaomi/mimo-v2.5` | Budget sibling to MiMo V2.5 Pro; 1M context. |
| Claude Haiku 4.5 | `anthropic/claude-haiku-4.5` | Cheap, fast, reasoning support; reliable on short chains. |
| GPT-5.4 Mini | `openai/gpt-5.4-mini` | Budget OpenAI; router only when the skill catalog is small and clean. |
| GPT-5.4 Nano | `openai/gpt-5.4-nano` | Cheapest OpenAI tier; mechanical turns only. |

## High-stakes engineering

When a wrong tool call is expensive: refactors, code review, long debugging, schema changes, release work.

| Model | OpenRouter ID | Notes |
|---|---|---|
| Claude Opus 4.8 | `anthropic/claude-opus-4.8` | Flagship — ceiling for hard multi-step engineering and long-context judgement. |
| Claude Sonnet 4.6 | `anthropic/claude-sonnet-4.6` | Best daily premium balance for coding-heavy profiles. |
| GPT-5.5 | `openai/gpt-5.5` | OpenAI flagship; strong general engineering. |
| GPT-5.5 Pro | `openai/gpt-5.5-pro` | Extended reasoning for the hardest tasks. |
| o3 | `openai/o3` | Heavy-reasoning specialist; not a router, use for one-shot analysis. |
| GPT-5.3 Codex | `openai/gpt-5.3-codex` | Coding-specific; good for repo-tooling profiles. |
| Nemotron 3 Super | `nvidia/nemotron-3-super-120b-a12b` | Open-weight engineering option; 256K context. |

## Local/private profiles

"Best" means best inside the local model ecosystem (Ollama, llama.cpp, vLLM), not best overall. The curated catalog does not pin specific local IDs — the field moves fast and the right pick depends on VRAM. Choose from current Qwen-coder, Gemma, codestral, or Mistral families. Expect more prompt sensitivity than cloud frontier models and tighter context windows.

For privacy-constrained work that needs more headroom than the hardware allows: `nvidia/nemotron-3-super-120b-a12b` (256K) or `deepseek/deepseek-v4-pro` (1M) — not local, but no proprietary frontier dependency.

## Native routes for Anthropic and OpenAI

When the user has ANTHROPIC_API_KEY or OPENAI_API_KEY, native routes work and usually mean lower latency.

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

## Avoid as primary skill router

Usable as workers, not the main model for a skill-dependent profile:

- Nano-class: miss the skill index, skip `skill(action="view")`, fill params loosely. Low-risk mechanical turns only.
- Free-tier: rate limits and provider variability break tool loops mid-turn. Smoke tests, not daily automation.
- Small local models without proven tool calling: ok for privacy-constrained short tasks, poor for multi-tool routing.
- Wrapper-unstable models: avoid even with strong benchmarks; agents fail at integration boundaries first.

## Production setups

One primary model per profile; split roles across profiles (picks per tier in the tables above). `fallback_models` is stored in config — do not assume automatic runtime escalation unless the installed version implements it. Provider dashboards are a weak signal at best (biased by defaults/price/rate limits), and only when they reflect tool-heavy use, not chat benchmarks.

## Switching model

- `alpi setup` -> Model / Provider -> pick provider, pick model.
- `/model` slash command inside the TUI.
- Edit `model:` in `~/.alpi/config.yaml` or `~/.alpi/profiles/<name>/config.yaml`.

Per-profile: `alpi -p work` can run Sonnet 4.6 while `alpi -p personal` runs MiMo V2.5.

## Related topics

- Model config keys: `config`
- Skills and tool routing: `skills`
- Provider setup: `install`
