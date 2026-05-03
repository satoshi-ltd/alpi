# Model recommendations

alpi works with any model that speaks the OpenAI tool-calling protocol
via LiteLLM, but **not every model is a good agent**. The important
question is not "what scores highest on a benchmark?" but "what model
keeps choosing the right tool after 20 turns, with memory, skills,
shell commands, browser calls, and user-specific state in context?"

Use this page as a practical selector. Prices, context windows, and
provider wrappers move quickly; re-check them every 2-3 months.

Last updated: **2026-05-03**.

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

OpenRouter's public app rankings are useful because they measure
models inside agents that look like alpi, not chat-only benchmarks:

- [OpenClaw][oc] is an agent that connects to messaging apps and takes
  actions with commands, web browsing, file management, and email. On
  2026-05-03 OpenRouter showed it at **11.7T total tokens**, **#1
  daily global rank**, and **374 models used**.
- [Hermes Agent][h] is a persistent-memory agent with reusable skills,
  web search, browser automation, vision, scheduled automations, and
  subagents. On 2026-05-03 OpenRouter showed it at **5.59T total
  tokens**, **#2 daily global rank**, and **341 models used**.

Usage is not quality. Defaults, price, rate limits, and availability
all bias the chart. Still, sustained usage inside comparable
tool-heavy agents is a better signal than generic leaderboard wins.

Common high-usage models across those agents currently include
MiMo-V2-Pro, Qwen3.6 Plus, MiniMax M2.7, Step 3.5 Flash, Nemotron 3
Super, Claude Sonnet / Opus 4.6, GLM 5.x, Gemini Flash variants,
Kimi K2.x, DeepSeek V3/V4, and OpenAI GPT-5.4 / 5.4-mini.

[h]: https://openrouter.ai/apps/hermes-agent
[oc]: https://openrouter.ai/apps/openclaw

## Pick by workload

### Skill router / long tool chains

Use these when the profile has many skills, persistent memory,
stateful tools, or real side effects. This is the default category for
daily interactive alpi use.

| Model | OpenRouter ID | Why |
|---|---|---|
| **MiMo-V2-Pro** | `xiaomi/mimo-v2-pro` | Strong adoption in Hermes-style persistent agents; good price/context balance for tool-heavy profiles. |
| **Claude Sonnet 4.6** | `anthropic/claude-sonnet-4.6` | Strong general tool discipline and coding judgement; sensible premium daily driver. |
| **Qwen3.6 Plus** | `qwen/qwen3.6-plus` | High OpenClaw usage; good price-for-quality candidate for skill routing. |
| **MiniMax M2.7** | `minimax/minimax-m2.7` | Strong mid-tier agent model; good for persistent sessions, with occasional parameter-filling slips. |
| **GLM 5.1 / GLM 5 Turbo** | `z-ai/glm-5.1`, `z-ai/glm-5-turbo` | Strong usage in coding-agent workloads; watch wrapper/version stability. |
| **GPT-5.4** | `openai/gpt-5.4` | Good premium fallback when OpenAI compatibility matters. |

If you can only choose one model for a skill-heavy profile, start with
MiMo-V2-Pro, Qwen3.6 Plus, MiniMax M2.7, or Sonnet 4.6 depending on
budget and provider preference.

### Cheap service turns

Use these for Telegram gateway traffic, heartbeats, summaries, simple
lookups, and low-risk commands. They are not the first choice for
creating or debugging skills.

| Model | OpenRouter ID | Why |
|---|---|---|
| **Step 3.5 Flash** | `stepfun-ai/step-3.5-flash` | Very high Hermes usage after 2026-04-24; good cheap workhorse for simple turns. |
| **MiMo-V2-Flash** | `xiaomi/mimo-v2-flash` | Budget sibling to MiMo-V2-Pro; useful for A/B testing cheap service profiles. |
| **Gemini Flash / Flash Lite** | provider-specific | High OpenClaw usage; good for simple tasks, less convincing as the main skill router. |
| **DeepSeek V3.2 / V4 Flash** | provider-specific | Good cost floor; use when price matters more than perfect tool discipline. |
| **GPT-5.4-mini** | `openai/gpt-5.4-mini` | Reasonable budget OpenAI choice for simple tool use; acceptable as a router only when the skill catalog is clean and small. |

### High-stakes engineering

Use these when a wrong tool call is expensive: refactors, code review,
long debugging sessions, schema changes, release work.

| Model | OpenRouter ID | Why |
|---|---|---|
| **Claude Opus 4.6** | `anthropic/claude-opus-4.6` | Expensive ceiling for hard multi-step engineering and long-context judgement. |
| **Claude Sonnet 4.6** | `anthropic/claude-sonnet-4.6` | Best daily premium balance for coding-heavy profiles. |
| **GLM 5.1** | `z-ai/glm-5.1` | Strong open-weight engineering candidate; useful for reviews and long tasks. |
| **GPT-5.5 / GPT-5.4** | provider-specific | Good choice when OpenAI compatibility or ecosystem behaviour is the constraint. |

### Local / sovereign profiles

"Best" here means best inside the Ollama-style local ecosystem, not
best overall. Expect more prompt sensitivity than cloud frontier
models.

| Model | Mode | Notes |
|---|---|---|
| **Qwen3.6** | local, 27B/35B class | Default local pick for balanced agentic use. |
| **Gemma4** | local + cloud variants | Good local family when multimodal/function-calling support matters. |
| **qwen3-coder-next** | local + cloud variants | Coding specialist; do not treat it as the general personal-agent brain. |
| **devstral-small-2** | local + cloud variants | Good repo-tooling option at moderate size. |
| **Kimi K2.6** | cloud on Ollama | Strong within the Ollama ecosystem, but not a true local model. |

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

- **Personal skill-heavy profile**: MiMo-V2-Pro, Qwen3.6 Plus,
  MiniMax M2.7, or Sonnet 4.6.
- **High-volume gateway profile**: Step 3.5 Flash, MiMo-V2-Flash,
  Gemini Flash Lite, or GPT-5.4-mini, with fewer skills and tighter
  prompts.
- **Engineering profile**: Sonnet 4.6, Opus 4.6, GLM 5.1, GPT-5.5, or
  GPT-5.4.
- **Local/private profile**: Qwen3.6 first, then Gemma4 or a coding
  specialist for repo-specific work.

## Switching model

Three ways, any of them works:

- `alpi setup` -> Model / Provider -> pick provider, pick model.
- `/model` slash command inside the TUI.
- Edit `model:` in `~/.alpi/config.yaml` or
  `~/.alpi/profiles/<name>/config.yaml`.

The choice is per-profile. `alpi -p work` can run Sonnet 4.6 while
`alpi -p personal` runs MiMo-V2-Flash without interference.
