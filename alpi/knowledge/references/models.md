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

**Two different hazards, often confused.** A *floating id* redirects: `~vendor/model-latest` resolves to whatever the vendor ships next, so the agent changes underneath a running fleet with no config change and no notice. On OpenRouter every alias carries the `~` prefix, which makes them easy to refuse. A *preview or experimental id* carries a different risk: its endpoint can be withdrawn, and withdrawal is a hard failure rather than a silent swap. Some carry a dated snapshot in `canonical_slug` and some, like `deepseek/deepseek-v3.2-exp`, repeat the id instead, which tells you the id is not visibly pinned but not what it will resolve to tomorrow. Neither hazard is diagnosed by the substring alone: `alias_target` is the reliable test for redirection, a dated `canonical_slug` is evidence of pinning, and the absence of one is only the absence of that evidence. Prefer a dated snapshot; accept an experimental one only where losing it is survivable.

**The advertised context is not your input budget.** A slug's headline window is the ceiling of its best endpoint, and most of these models are also served by 256K endpoints, so the window you actually get depends on routing. Separately, alpi does not offer the whole window as input: `alpi/providers/openrouter_models.yaml` holds a per-model input limit that reserves a reply margin, and `ctx_window` uses that number. Expect the usable figure to be below the advertised one on both counts.

The tables below use **OpenRouter routes** as the primary ID. Native routes also work for Anthropic and OpenAI if you have those provider keys — see the Native routes section at the bottom.

## Good primary routers

For profiles with many skills, persistent memory, database state, shell commands, or important side effects. Availability and provider names move; check the catalog if exact availability matters.

| Model | OpenRouter ID | Notes |
|---|---|---|
| GLM 5.3 Flash | `z-ai/glm-5.3-flash` | Highest published agentic index of the cheap tier (Artificial Analysis, via OpenRouter, read 2026-09-11); up to 1.25M context, image and video in. Reasoning is mandatory and defaults to `max`, with `low` and `high` also accepted — set `model_reasoning.effort` deliberately. |
| DeepSeek V4.1 Flash | `deepseek/deepseek-v4.1-flash` | Encoder-decoder architecture with a low cache-read price; suits agents whose system prompt is large and stable. Released 2026-09-10 and not yet scored on the agentic index. |
| DeepSeek V4 Flash 0731 | `deepseek/deepseek-v4-flash-0731` | Text only, up to 1.25M context, served by a large number of providers. Third by weekly tokens on OpenRouter's public leaderboard (window ending 2026-09-10). |
| Claude Sonnet 5 | `anthropic/claude-sonnet-5` | Premium daily driver; strongest tool discipline at this tier. |
| MiMo V2.5 Pro | `xiaomi/mimo-v2.5-pro` | Text only, up to 1M context; scores above the base MiMo on agentic and coding, at about 3x the input price. |
| MiniMax M3 | `minimax/minimax-m3` | Mid-tier agent model. 1M is the announced ceiling; some endpoints serve 512K or 256K. |

Pick one for a skill-heavy profile: start with GLM 5.3 Flash or Sonnet 5 by budget/provider. `deepseek/deepseek-v4-pro` is no longer recommended as a daily driver: the bare id is pinned to the 2026-04 build and a measured audit put it behind the flash tier at many times the price.

## Vision route

`deepseek/deepseek-v4-flash-vision-exp` is the current DeepSeek experimental
vision route on OpenRouter. Configure it as the Vision model when the main model
is text-only: it is used by `read_image` and browser screenshot analysis, not by
ordinary chat turns or inline chat attachments. Experimental aliases can move;
clear the override to fall back to the profile model.

## Cheap service turns

For scheduled-job turns, heartbeats, summaries, simple lookups, low-risk commands. Not for creating/debugging skills.

| Model | OpenRouter ID | Notes |
|---|---|---|
| DeepSeek V4 Flash 0731 | `deepseek/deepseek-v4-flash-0731` | Cheapest model with a real agentic score; 1.25M context, broad provider support. |
| DeepSeek V4.1 Flash | `deepseek/deepseek-v4.1-flash` | Cheap cache read; the better pick when the prompt is large and mostly unchanged between turns. |
| MiMo V2.5 | `xiaomi/mimo-v2.5` | Budget sibling to MiMo V2.5 Pro; 1M context. |
| Claude Haiku 4.5 | `anthropic/claude-haiku-4.5` | Cheap, fast, reasoning support; reliable on short chains. |
| GPT-5.6 Terra | `openai/gpt-5.6-terra` | Balanced OpenAI; router only when the skill catalog is small and clean. |
| GPT-5.6 Luna | `openai/gpt-5.6-luna` | Cheapest OpenAI tier; mechanical turns only. |

## High-stakes engineering

When a wrong tool call is expensive: refactors, code review, long debugging, schema changes, release work.

| Model | OpenRouter ID | Notes |
|---|---|---|
| Claude Fable 5 | `anthropic/claude-fable-5` | Ceiling — next-gen intelligence for long-running agents; most capable widely-released model. |
| Claude Opus 5 | `anthropic/claude-opus-5` | Flagship for complex agentic coding and enterprise engineering; supersedes Opus 4.8 at the same price. |
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
| Anthropic | `anthropic/claude-opus-5` | `claude-opus-5` (hyphens, not dots) |
| Anthropic | `anthropic/claude-sonnet-5` | `claude-sonnet-5` |
| Anthropic | `anthropic/claude-haiku-4.5` | `claude-haiku-4-5` |
| OpenAI | `openai/gpt-5.6-sol` | `gpt-5.6-sol` (alias `gpt-5.6`, no prefix) |
| OpenAI | `openai/gpt-5.6-terra` | `gpt-5.6-terra` |
| OpenAI | `openai/gpt-5.6-luna` | `gpt-5.6-luna` |

## Prompt caching

Caching is transparent and fail-safe: unsupported providers/models receive the normal request. LiteLLM adds an explicit marker only where supported; OpenRouter also receives a hashed stable conversation `session_id` (never raw profile/session/peer/workgroup/job identifiers). Provider telemetry differs: zero is a measured miss, missing fields mean unknown (`no provider cache data`), not zero. Native Anthropic, OpenRouter/DeepSeek, and other routes therefore execute the same way but may expose different counts, discount, or cost precision.

The stable system prompt is the cacheable prefix; fresh clock/workgroup/skill/relay context rides each user turn so ordinary growth is append-only. First contact, model/tools/system changes, compaction, resume, reset, or edit-and-resend can legitimately cool/rewrite the prefix. Inspect `/status` and `alpi digest`; only provider-reported cost is invoice-grade, so reconcile against the provider dashboard.

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
