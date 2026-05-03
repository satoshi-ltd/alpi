# Models answer pack

Use this for "what model should I use?", especially with skills,
tools, gateways, and long sessions.

## Main rule

alpi needs tool-calling discipline more than chat benchmark scores.
For skill-heavy profiles, prefer a model that reliably notices the
skill index, calls `skill(action="view")`, preserves tool schemas, and
recovers from tool errors.

## Good primary routers

Use these for profiles with many skills, persistent memory, database
state, shell commands, or important side effects:

| Model | ID |
|---|---|
| MiMo-V2-Pro | `xiaomi/mimo-v2-pro` |
| Claude Sonnet 4.6 | `anthropic/claude-sonnet-4.6` |
| Qwen3.6 Plus | `qwen/qwen3.6-plus` |
| MiniMax M2.7 | `minimax/minimax-m2.7` |
| GLM 5.1 / GLM 5 Turbo | `z-ai/glm-5.1`, `z-ai/glm-5-turbo` |
| GPT-5.4 | `openai/gpt-5.4` |

## Cheap service turns

Use these for low-risk gateway traffic, heartbeats, summaries, simple
lookups, and short commands:

| Model | ID |
|---|---|
| Step 3.5 Flash | `stepfun-ai/step-3.5-flash` |
| MiMo-V2-Flash | `xiaomi/mimo-v2-flash` |
| GPT-5.4-mini | `openai/gpt-5.4-mini` |
| Gemini Flash / Flash Lite | provider-specific |
| DeepSeek V3.2 / V4 Flash | provider-specific |

`GPT-5.4-mini` is acceptable as a router only when the skill catalog is
small, clean, and low-risk. It is better as a cheap worker than as the
only brain for a complex personal-agent profile.

## Avoid as primary skill router

- Nano-class models: too likely to miss the skill index or fill tool
  parameters loosely.
- Free-tier models: rate limits and provider variability can break a
  tool loop mid-turn.
- Small local models without proven tool calling: fine for privacy
  constrained short tasks, weak for multi-tool routing.
- Any model with known wrapper instability, even if benchmarks look
  strong.

## Local/private profiles

Default local pick: Qwen3.6 in the 27B/35B class. Gemma4 is a good
local family when multimodal/function-calling support matters.
qwen3-coder-next and devstral-small-2 are better treated as coding
specialists than general personal-agent brains.

## Evidence

OpenRouter public app pages are useful because they show model use in
agent workloads similar to alpi:

- OpenClaw: messaging, commands, web browsing, files, email.
- Hermes Agent: persistent memory, reusable skills, browser/search,
  scheduled automations, subagents.

Usage is not quality, but sustained usage in comparable tool-heavy
agents is more relevant than generic chat benchmarks.

## Production guidance

alpi currently selects one primary model per profile. `fallback_models`
exists in config, but do not assume automatic runtime escalation unless
the installed version explicitly implements it. Use separate profiles
for different model roles today.
