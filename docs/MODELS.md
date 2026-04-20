# Model recommendations

alf works with any model that speaks the OpenAI tool-calling protocol
via LiteLLM, but **not every model is a good agent**. Tool-calling
fluency, system-prompt adherence, and memory-tool triggering vary
wildly — and token cost and latency vary just as much. This page is
the distilled recommendation so you don't have to learn the hard way.

## How this list was built

- **Usage signal**: OpenRouter's public rankings for [Hermes Agent][h]
  (Nous Research's personal agent — comparable workload to alf:
  tool-heavy CLI, 40+ tools, persistent memory, 3.41T tokens/month).
- **Coding-agent signal**: same service, "Coding Agents" category —
  a proxy for disciplined tool-chain use.
- **Empirical**: hands-on testing inside alf with the same set of
  smoke questions (identity adoption, proactive `memory` writes,
  session_search usage, tool-chain discipline).

[h]: https://openrouter.ai/apps/hermes-agent

Last updated: **2026-04-20**. Re-check every 2-3 months — the
rankings shift fast, free tiers come and go, and new releases
(Claude Opus 4.7, MiMo-V2-Pro successors) reset the bar.

## Tier A — reliable, pick if cost isn't the top constraint

These adopt the persona from `PERSONALITY.md` on turn 1, call
`memory` proactively when you drop a fact, and chain tools cleanly
without needing rhetorical nudges.

| Model | OpenRouter ID | Notes |
|---|---|---|
| **Claude Opus 4.6** | `anthropic/claude-opus-4.6` | Gold standard for agent discipline. Most expensive. Pick for research-heavy sessions where a wrong tool call costs more than the premium. |
| **Claude Sonnet 4.6** | `anthropic/claude-sonnet-4.6` | 80% of Opus for ~15% of cost. The pragmatic daily driver if the budget allows. |
| **GPT-5.4** | `openai/gpt-5.4` | Slightly different failure modes than Claude — sometimes over-calls tools, rarely under-calls. Similar reliability. |
| **MiMo-V2-Pro** | `xiaomi/mimo-v2-pro` | **#1 model on Hermes Agent globally** (1.37T tokens/month). Surprisingly good at tool discipline for its price. Chinese vendor — some users prefer to avoid. |
| **Qwen3.6 Plus** | `qwen/qwen3.6-plus` | #2 on Hermes. Strong tool-calling, good long-context behaviour, mid cost. |

## Tier B — cheap daily driver, works well enough

These sometimes need an explicit nudge ("save that in your memory")
but respect the system prompt and tool schema. Great for high-volume
or low-stakes sessions where you don't want to burn through Tier A
credit.

| Model | OpenRouter ID | Notes |
|---|---|---|
| **MiMo-V2-Flash** | `xiaomi/mimo-v2-flash` | **Validated locally in alf** — adopts persona fine, respects tool schema, very fast, very cheap. Our current default recommendation for personal daily use. |
| **Gemini 3 Flash Preview** | `google/gemini-3-flash-preview` | Fast, generous context, Google-cheap. Slightly laxer about proactive memory writes. |
| **GLM 5.1** | `z-ai/glm-5.1` | #8 on Hermes. Competent, mid-cheap. Good fallback when Gemini rate-limits. |
| **MiniMax M2.7** | `minimax/minimax-m2.7` | #3 on Hermes. Decent for conversation, slightly weaker on multi-step tool chains. |
| **Kimi K2.5** | `moonshotai/kimi-k2.5` | Long context, careful answers. Slow vs the flash tier. |

## Tier C — avoid for agentic use

These ignore persona instructions, skip tool calls in favour of
conversational acknowledgement ("¡Por supuesto! Voy a recordarlo" —
but nothing gets written to disk), and drift out of the
system-prompt discipline within a few turns.

| Model | OpenRouter ID | Why it's here |
|---|---|---|
| **Nemotron 3 Super 120B (free)** | `nvidia/nemotron-3-super-120b-a12b:free` | Hallucinates tool-call results. Claimed to read `PERSONALITY.md` and fabricated content that wasn't there. #4 on Hermes, but Hermes apparently uses it for non-agentic subtasks. Do not use as your main model. |
| **Llama 3.1 8B** (and smaller) | any `meta-llama/llama-3.1-8b-*` | Too small for agentic discipline. OK for single-turn Q&A, not for tool chains. |
| **Older than 2024-Q4 flagships** | e.g. `claude-3-haiku`, `gpt-3.5-turbo`, original Mistral | Tool-calling was still experimental. If you need cheap, use MiMo-V2-Flash instead — same price range, far better behaviour. |

## Free tier reality check

OpenRouter's `:free` variants exist to get users into the ecosystem.
For agent use the rule is simple:

- **Mostly useless** for disciplined tool chains. The `:free` tag
  tracks the model, not a magic quality threshold.
- **Rate-limited aggressively** — a long session hits the ceiling
  and starts returning 429s mid-tool-call, which breaks the agent
  loop.
- **Still worth trying** for one-off "does this workflow even run"
  smoke tests. Just don't make them your daily driver.

## What Javi actually uses

For transparency (and because recommendations age badly when they
drift from real usage):

- **Personal profile, daily driver**: `xiaomi/mimo-v2-flash` via
  OpenRouter — fast, ~free at personal-use volume, respects the
  Lucía persona and the memory tool.
- **Default profile, when stakes are higher**: `anthropic/claude-sonnet-4.6`
  for anything that involves writing code or making decisions I
  can't verify quickly.
- **Experiments**: whatever's top of Hermes rankings this month,
  run through the same smoke test before promoting.

## Switching model

Three ways, any of them works:

- `alf setup` → Model / Provider → pick provider, pick model.
- `/model` slash command inside the TUI.
- Edit `model:` in `~/.alf/config.yaml` (or
  `~/.alf/profiles/<name>/config.yaml`).

The choice is per-profile. `alf -p work` can run Claude Sonnet
while `alf -p personal` runs MiMo-V2-Flash — no interference.
