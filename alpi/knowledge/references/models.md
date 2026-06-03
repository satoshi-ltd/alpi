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

## Good primary routers

For profiles with many skills, persistent memory, database state, shell commands, or important side effects. Availability/provider names change; check the provider or OpenRouter catalog if exact availability matters.

| Model | OpenRouter ID | Notes |
|---|---|---|
| MiMo-V2-Pro | `xiaomi/mimo-v2-pro` | Strong persistent-agent adoption; good price/context balance. |
| Claude Sonnet 4.6 | `anthropic/claude-sonnet-4.6` | Strong general tool + coding discipline; premium daily driver. |
| Qwen3.6 Plus | `qwen/qwen3.6-plus` | Strong price-for-quality skill routing. |
| MiniMax M2.7 | `minimax/minimax-m2.7` | Strong mid-tier; occasional parameter-filling slips. |
| GLM 5.1 / GLM 5 Turbo | `z-ai/glm-5.1`, `z-ai/glm-5-turbo` | Strong coding-agent usage; watch wrapper/version stability. |
| GPT-5.4 | `openai/gpt-5.4` | Premium fallback when OpenAI compatibility matters. |

Pick one for a skill-heavy profile: start with MiMo-V2-Pro, Qwen3.6 Plus, MiniMax M2.7, or Sonnet 4.6 by budget/provider.

## Cheap service turns

For Telegram gateway traffic, heartbeats, summaries, simple lookups, low-risk commands. Not for creating/debugging skills.

| Model | OpenRouter ID | Notes |
|---|---|---|
| Step 3.5 Flash | `stepfun-ai/step-3.5-flash` | Cheap workhorse for simple turns. |
| MiMo-V2-Flash | `xiaomi/mimo-v2-flash` | Budget sibling to MiMo-V2-Pro; A/B test cheap profiles. |
| GPT-5.4-mini | `openai/gpt-5.4-mini` | Budget OpenAI; router only when skill catalog is small/clean/low-risk. |
| Gemini Flash / Flash Lite | provider-specific | Simple tasks; weak as main skill router. |
| DeepSeek V3.2 / V4 Flash | provider-specific | Cost floor; use when price beats perfect tool discipline. |

## High-stakes engineering

When a wrong tool call is expensive: refactors, code review, long debugging, schema changes, release work.

| Model | OpenRouter ID | Notes |
|---|---|---|
| Claude Opus 4.6 | `anthropic/claude-opus-4.6` | Ceiling for hard multi-step engineering and long-context judgement. |
| Claude Sonnet 4.6 | `anthropic/claude-sonnet-4.6` | Best daily premium for coding-heavy profiles. |
| GLM 5.1 | `z-ai/glm-5.1` | Strong open-weight engineering; reviews and long tasks. |
| GPT-5.5 / GPT-5.4 | provider-specific | When OpenAI compatibility/ecosystem is the constraint. |

## Local/private profiles

"Best" means best inside the Ollama-style local ecosystem, not best overall; expect more prompt sensitivity than cloud frontier models.

| Model | Mode | Notes |
|---|---|---|
| Qwen3.6 | local, 27B/35B class | Default local pick for balanced agentic use. |
| Gemma4 | local + cloud | Good local family when multimodal/function-calling matters. |
| qwen3-coder-next | local + cloud | Coding specialist; not the general personal-agent brain. |
| devstral-small-2 | local + cloud | Repo-tooling option at moderate size. |
| Kimi K2.6 | cloud on Ollama | Strong within Ollama, but not a true local model. |

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

Per-profile: `alpi -p work` can run Sonnet 4.6 while `alpi -p personal` runs MiMo-V2-Flash.

## Related topics

- Model config keys: `config`
- Skills and tool routing: `skills`
- Provider setup: `install`
