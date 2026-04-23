# Model recommendations

alpi works with any model that speaks the OpenAI tool-calling protocol
via LiteLLM, but **not every model is a good agent**. Tool-calling
fluency, system-prompt adherence, memory-tool triggering, and
tolerance for long tool chains vary wildly — and token cost / latency
vary just as much. This page is the distilled recommendation so you
don't have to learn the hard way.

## How this list was built

Signals combined, in order of weight:

- **Hands-on testing inside alpi** — each candidate ran the same
  smoke tests: persona adoption on turn 1, proactive `memory`
  writes, `session_search` usage, tool-chain discipline, behaviour
  across 30+ turn sessions.
- **Usage signal on comparable agents** — OpenRouter's public
  rankings for [Hermes Agent][h] (Nous Research's persistent-memory
  agent, 4.11T tokens/month, #3 global) and [OpenClaw][oc] (17.2T
  tokens/month, #1 global, agent loop with shell + browser +
  email). Both share alpi's shape: tool-heavy, long sessions, real
  actions.
- **Community field reports** — Reddit's `/r/LocalLLaMA` megathreads
  and GitHub issues on wrapper compatibility. Benchmarks deliberately
  down-weighted; real loop behaviour up-weighted.
- **Integration friction** — models with repeated wrapper-support
  issues (e.g. GPT-5.4 on OpenClaw at launch) penalised, regardless
  of benchmark score.

[h]: https://openrouter.ai/apps/hermes-agent
[oc]: https://openrouter.ai/apps/openclaw

Last updated: **2026-04-23**. Re-check every 2-3 months — rankings
shift fast and new releases reset the bar. Prices are list from
OpenRouter, per 1M tokens in / out; reasoning tokens, retries, and
agent loops can push real spend well above list.

## Tier 1 — best quality

Pick when the cost of a wrong tool call or a missed refactor beats
the cost of API tokens. These adopt the persona from
`PERSONALITY.md` on turn 1, call `memory` proactively, respect the
tool schema, and hold coherence across long sessions.

| Model | OpenRouter ID | Input | Output | Notes |
|---|---|---:|---:|---|
| **MiMo-V2-Pro** | `xiaomi/mimo-v2-pro` | $1.00 | $3.00 | Default premium recommendation. #1 on Hermes Agent globally. 1M context, built for agent frameworks, feels close to Opus 4.6 in perceived quality at a fraction of the cost. |
| **Claude Opus 4.6** | `anthropic/claude-opus-4.6` | $5.00 | $25.00 | Ceiling when debugging long chains or doing multi-step refactors matters more than the bill. OpenRouter positions it as their strongest coding model. |
| **Claude Sonnet 4.6** | `anthropic/claude-sonnet-4.6` | $3.00 | $15.00 | Most sensible daily premium. 1M context, strong coding + computer-use story, clearly cheaper than Opus for frequent sessions. |
| **Qwen3.6 Plus** | `qwen/qwen3.6-plus` | $0.325 | $1.95 | Challenger that wins on price-for-quality. 1M context, 78.8 on SWE-bench Verified, field reports in agentic coding noticeably better than Qwen 3.5. |
| **GLM 5.1** | `z-ai/glm-5.1` | $1.05 | $3.50 | Frontier open-weight for long-horizon engineering. OpenRouter's copy talks about >8h tasks; community rates it especially high on code review. Slight wrapper lag — pin a newer version when available. |

If you can only run one Tier 1 model across every profile, pick
**MiMo-V2-Pro**. If the cost of mistakes dwarfs the API bill, go
**Opus 4.6**. For the best middle ground, **Sonnet 4.6**.

## Tier 2 — cost / service

Best return per token when there are tools, long context, and
repeated calls. Not the cheapest available — the cheapest that
still respects the tool schema and doesn't derail past turn 20.

| Model | OpenRouter ID | Input | Output | Notes |
|---|---|---:|---:|---|
| **Step 3.5 Flash** | `stepfun-ai/step-3.5-flash` | $0.10 | $0.30 | Best cheap workhorse. Open-source reasoning, 400K context, heavy real-use adoption. Ideal for heartbeats, status checks, low-stakes turns. |
| **MiniMax M2.7** | `minimax/minimax-m2.7` | $0.30 | $1.20 | Favourite mid-tier. Agentic-serious, strong benchmarks on real workflows, community reports excellent tool-parallelism vs M2.5. Occasional slip on tool-parameter filling. |
| **MiMo-V2-Flash** | `xiaomi/mimo-v2-flash` | $0.09 | $0.29 | Best A/B budget pick. 1M context, #1 open-source multimodal on SWE-bench Verified per OpenRouter, comparable to Sonnet 4.5 at ~3.5% of the cost. |
| **DeepSeek V3.2** | `deepseek/deepseek-v3.2` | $0.252 | $0.378 | Price floor that's still hard to beat for reasoning + tool use. Still described as strong on agentic tool use. |
| **Nemotron 3 Super** | `nvidia/nemotron-3-super-120b-a12b:free` | free | free | Value wildcard. 1M context, explicit multi-agent focus. Don't rank it above M2.7 or MiMo on raw quality, but on dollars-per-turn it's unbeatable. Expect rate limits on free tier. |

Reality check on pricing: at list prices, **Step 3.5 Flash** runs
**~30× cheaper on input and ~50× cheaper on output** than
**Sonnet 4.6**. **MiMo-V2-Flash** lands ~33× / ~52× cheaper.
**DeepSeek V3.2** is ~12× / ~40× cheaper. For a profile that runs a
gateway daemon hitting Telegram inbound all day, those multipliers
compound into real savings — many of those turns don't need
Tier 1 reasoning.

## Tier 3 — best on Ollama

"Best" here means best inside the Ollama ecosystem specifically.
Explicit OpenClaw / coding-agent launches, useful context windows,
sensible sizes, and recent updates weighed more than raw benchmark
numbers. Mark each as local-only or local + `:cloud` variant.

| Model | Mode | Notes |
|---|---|---|
| **Qwen3.6** | local — 27B/35B, 17–24GB, 256K ctx | Default local pick. Ollama positions it for agentic coding with thinking preservation, ships direct OpenClaw launch integration, clear step-up from 3.5. Community preference leans 27B over 35B for long-session stability. |
| **Gemma4** | local + cloud — 7.2GB–20GB, 128K–256K ctx | Best "sovereign" local family if you want multimodal + native function calling. Official OpenClaw launch documented; some field reports of crashes on very long coding-agent loops. |
| **qwen3-coder-next** | local + cloud — 52GB q4, 256K ctx | Pure coding specialist. Ollama page covers OpenClaw launch, 800K executable tasks, 3B active-per-token, production-ready tool calling. Use as a dedicated coder rather than a general brain. |
| **devstral-small-2** | local + cloud — 15GB q4, 384K ctx | Best repo-tooling option at moderate size. Official Ollama page lists OpenClaw integration and 65.8% on SWE-bench Verified. Built for cross-file editing in large codebases. |
| **Kimi K2.6** | cloud on Ollama — 256K ctx | High-end expert *within* the Ollama ecosystem, not a true local. Ollama page frames it for long-horizon coding, swarms, 24/7 agents. Field reports still call out over-thinking and token burn on hard debugging. |

If your constraint is **truly zero cloud**, the realistic order is
**Qwen3.6 > Gemma4 > qwen3-coder-next > devstral-small-2**, with
**Kimi K2.6** excluded (it's `:cloud`-tagged on Ollama's own page).

## Recommended production setups

alpi supports a primary model with automatic fallbacks, so mixing
tiers by role is cheap to wire up:

- **Single-model, every profile**: **MiMo-V2-Pro**. Best adoption
  across tool-heavy agents, good context, sensible price.
- **Router-style (high-volume profiles with gateway daemons)**:
  **Step 3.5 Flash** as base + **MiMo-V2-Pro** or
  **Sonnet 4.6** as fallback for hard turns. Matches how long-running
  agents are deployed elsewhere — heartbeats and simple shell calls
  don't need frontier reasoning.
- **Persistent / multi-session heavy**: **MiniMax M2.7** or
  **Qwen3.6 Plus** as daily driver, **GLM 5.1** for code review,
  refactors, and autonomous engineering tasks.
- **Sovereign local**: **Qwen3.6 27B** for balanced coverage or
  **Gemma4 26B / 31B** if you want multimodal and a well-packaged
  stack, plus **qwen3-coder-next** or **devstral-small-2** as a
  coding specialist for repo-heavy work.

## Free tier reality check

OpenRouter's `:free` variants exist to funnel users into the
ecosystem. For agent use:

- **Mostly useless** for disciplined tool chains — the `:free` tag
  tracks the model, not a quality threshold.
- **Rate-limited aggressively** — long sessions hit the ceiling and
  return 429s mid-tool-call, which breaks the loop.
- **Still worth a smoke test** to check a workflow runs at all.
  Don't make them your daily driver.

## Switching model

Three ways, any of them works:

- `alpi setup` → Model / Provider → pick provider, pick model.
- `/model` slash command inside the TUI.
- Edit `model:` in `~/.alpi/config.yaml` (or
  `~/.alpi/profiles/<name>/config.yaml`).

The choice is per-profile. `alpi -p work` can run Sonnet 4.6 while
`alpi -p personal` runs MiMo-V2-Flash — no interference.
