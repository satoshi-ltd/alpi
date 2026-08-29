---
title: Cost control is the missing infrastructure for AI agents
date: 2026-06-19
description: A market-research pipeline of four agents entered a loop that ran for 11 days and cost $47,000. No framework prevents this at the infrastructure layer.
tags: [cost, architecture, operations]
---

# Cost control is the missing infrastructure for AI agents

In November 2025 a market-research pipeline built with four LangChain agents — an Analyzer and a Verifier passing results back and forth — entered a ping-pong loop that ran for eleven days before billing data surfaced it. Cost: **$47,000**. The agents had no per-session budget cap. Monitoring alerted asynchronously; nobody acted in time.

That incident, documented in the Token Budgets paper (arXiv 2606.04056, which catalogs 63 confirmed budget-overrun incidents across 21 orchestration frameworks), is not an edge case. It is the shape of a structural gap: every major agent framework ships observability. None ships infrastructure-layer cost enforcement.

Gartner projected in March 2026 that **40% of AI agent projects will be cancelled by 2027 due to cost overruns alone** — not technical failure, not market fit. Uber's CTO publicly said the company's annual AI budget was exhausted by mid-April. Microsoft reduced thousands of internal Claude Code licenses, shifting developers to GitHub Copilot CLI because cost grew faster than captured value.

Cost surprise is not a deployment risk. For most teams today, it is the deployment blocker.

## How agents burn money differently from chatbots

Chatbot overruns are predictable: more users, higher traffic, longer conversations. Agent overruns are combinatorial and often silent.

### Runaway iteration loops

Agents are designed to retry, verify, and iterate. When iteration never terminates — a verification step that always finds something to fix, a search that keeps expanding — the same architectural feature becomes the cost vector. The $47K loop is the canonical example. It happened because four agents each had full context, unlimited retries, and no dollar ceiling.

### Context accumulation (O(n²) cost)

Every agent carries conversation history into each request. A session starting at 5K tokens reaches 80K+ by step 30 — the cost of step 30 is not 6× step 1, it is roughly **155×** because each prior turn compounds input size (5 + 10 + 20 + 40 + 80K). The Stanford Digital Economy Lab found that re-sent context accounts for **62% of total agent inference bills**. One developer tracked 42 agent runs and found 70% of tokens were carrying history the agent never used.

### Retry storms and unbounded tool calls

A single failed database read tripled token cost via retries (Cockroach Labs, June 2026). Agents re-send full context with each retry. The Agents Arcade blog calls retry storms "the hardest cost to forecast" because teams model averages, not probability distributions.

BAGEN (2026) found that frontier models cannot predict token-budget depletion in autonomous execution — agents waste **44% of tokens on tasks they will fail**.

## What the frameworks provide (and skip)

Every major framework in mid-2026 addresses cost at different layers. None addresses it at the enforcement layer.

**LangGraph** has `recursion_limit` (max super-step iterations per graph run), durable checkpointing, and LangSmith observability with token tracking. What it leaves to the developer: per-session dollar budgets, cumulative spend ceilings across sub-graphs, and model-tier routing policies.

**OpenAI Agents SDK** ships guardrails — input, output, and tool-call validators. There is no `budget_usd` parameter, no cross-request token accumulation, no cost ceiling per agent. Third-party wrappers like `agentguard47` (`@guard(budget_usd=2.00, on_exceed="raise")`) exist precisely because the SDK does not.

**Claude Agent SDK** provides per-subagent model caps via frontmatter (`model: haiku`), OpenTelemetry cost metrics, and workspace-level spend limits on API. But there is no hard per-session token budget that terminates mid-execution, and no aggregate fleet ceiling that auto-stops anomalous behavior.

**CrewAI** has no built-in cost enforcement at all.

The pattern is consistent: **none of the major frameworks provide pre-execution, session-terminating budget enforcement at the infrastructure layer.** They provide limits on loop depth (LangGraph), model tier assignment (Claude SDK), guardrails (OpenAI), and post-hoc dashboards (all of them). The gap between "the alert fired" and "the session stopped" is where the $47K incidents happen.

## What actually works in practice

Teams that avoid cost surprise in production combine four layers, because no single layer covers the full problem.

### Model tiering

Route orchestrators to frontier models (Opus, Claude 4.5 Sonnet, GPT-5), workers to mid-tier (GPT-4o), and mechanical tasks to cheap models (Haiku, Gemini Flash). Claude's SDK enforces this via subagent `model` frontmatter. Real economics at June 2026 API rates: a fleet of 1 Opus + 3 Sonnet + 1 Haiku costs **~40% less** than 5 identical Opus agents (empirically validated by Developer's Digest).

### Prompt caching — the highest-ROI single move

Anthropic's cache reads on Sonnet 4.6 cost $0.30/M tokens versus $3.00 standard — a **90% reduction**. Break-even is 2.3 reuses of the same cached prefix within the 1-hour TTL. One enterprise case went from $45K/mo to $8K/mo. The trap: timestamps, session IDs, or date strings in the system prompt destroy cache hits. A single `Today's date is...` line dropped a 90% discount to 1%.

### Hard caps on decision depth

Six maximum decision hops. Confidence thresholds that skip re-planning when retrieval confidence is high. Aggressive prompt compression. One deployment cited by Agents Arcade reduced token burn **38% overnight**.

### Structured context management

Compaction (summarizing and restarting near context limits), layered tool schemas (no agent carries 40 tool schemas when it needs 3), and just-in-time retrieval (pull context only when the agent signals need). Sub-agent isolation — each sub-agent gets a clean context window; the parent receives a 1,000–2,000 token summary.

## The architectural gap: monitoring is not enforcement

Cost monitoring reads what happened and reports it. Cost enforcement intercepts what is about to happen and evaluates the call against policy *before* the API proceeds. The difference is architectural.

The $47K loop happened despite full monitoring because:
- Monitoring is asynchronous: alert → human → action
- Agent costs compound between alert-fire and session-stop
- Prompt-layer cost instructions are fragile — Palisade Research found that models can sabotage their own shutdown mechanism when the instruction lives in the context where reasoning can reach it

Infrastructure-layer enforcement operates outside the agent's code and context. It evaluates each API call against a ceiling and terminates the session before the next call. The agent receives no message to act on — it simply stops. This is the same architectural choice that web infrastructure made when TLS moved from application-layer code to transport-layer protocol: the safety property holds regardless of the application author's attention.

The emerging best-practice stack is layered:

1. **Gateway / proxy** (MLflow AI Gateway, Waxell, custom) — pre-execution budget enforcement, model routing, caching
2. **Framework** (LangGraph, Claude SDK) — recursion limits, sub-agent model caps, checkpointing
3. **Observability** (LangSmith, OpenTelemetry) — per-node token tracking, attribution
4. **Business metrics** (cost per resolved ticket, value per 1K tokens) — ties spend to outcomes

No major cloud provider offers agent-specific cost enforcement as a managed service. No framework ships native per-session dollar budgets with termination. The capability is currently fragmented across third-party gateway tools, decorator libraries, and custom middleware.

## Budget as infrastructure, not application code

Alpi was built with a different product boundary. Every agent profile has a **daily spending cap** in dollars or tokens — enforced by the platform, not by a decorator the developer applies. When the cap is hit, the call fails with a documented error code (-32005 budget-exceeded) and the agent stops. No surprise invoice.

Every shared workspace (a workgroup) can carry its own lifetime budget. The budget is read before every LLM call, not checked asynchronously. It operates outside the agent's context where no reasoning can reach it.

This is not a feature that makes budgeting automatic — it is a structural default. On a framework, every team must rediscover that they need this and build it themselves. On Alpi, it ships, and the effort goes into setting the right ceilings per agent rather than reinventing budget enforcement as application middleware.

The honest trade-off: a per-agent daily cap is a coarse instrument. It does not distinguish between a legitimate expensive task and a runaway loop within the same session. Finer enforcement — per-task budgets, per-session ceilings — requires layering application logic on top of the platform primitive. But a coarse cap that actually stops execution is worth more than unlimited execution with perfect dashboards, because the dashboards arrive after the invoice.

## The next incident you won't have

The $47K loop did not happen because the team was careless. It happened because the infrastructure they used had no place to express the constraint "this agent should not spend more than X dollars." The monitoring fired; the budget was gone.

Frameworks are not wrong for skipping cost enforcement. They are optimized for development velocity, and hard dollar ceilings would break the developer experience on first run. The gap is that production deployments inherit those permissive defaults, and teams discover the gap when billing data catches their attention.

Budget enforcement at the infrastructure layer is where the web was before TLS became universal: everyone knew it mattered, but it was never the thing you ship on day one. Agents will not scale across an organization until the cost defaults are closed, not open.

You can install Alpi and set per-agent budgets today:

```bash
uv tool install alpi-agent
```