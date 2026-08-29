---
title: The 90% gap in AI agents
date: 2026-06-15
description: 90% of agent projects stall before production. Models aren't the bottleneck — the ops layer is. And most teams build it from scratch.
tags: [production, operations, governance]
---

# The 90% gap in AI agents

The number hits every survey the same way. DigitalOcean's March 2026 study of 2,400 organizations: **67% see gains from agent pilots; only 10% scale to production.** The UC Berkeley MAP study (arXiv 2512.04123, late 2025) puts it at 14% across 306 practitioners. The World Economic Forum reports that 60% of CEOs have slowed deployment on accountability concerns alone.

This is not a model quality problem. GPT-5, Claude 4, Gemini 2.5, and the open-weight alternatives can all reason across tools, retrieve context, and produce structured output. The models are ready. The operations layer around them is not — and most teams end up building it themselves, at a cost of months of dedicated engineering time.

## The five gaps agents hit at scale

Five structural gaps reappear across the surveys, postmortems, and engineering blogs.

**Identity and governance.** LangGraph identifies agents by node names in a graph. CrewAI uses `role`, `goal`, and `backstory` strings. The OpenAI Agents SDK uses a `name` attribute. Every framework labels an agent the way a game labels a player — a string in memory. Nothing verifies that process A is the same agent five minutes later. Nothing prevents impersonation. Okta's 2025 research found that 91% of organizations use AI agents but only 10% have any governance in place. The IETF is drafting standards for agent authentication. Until then, every multi-agent deployment relies on shared credentials and application-layer trust.

**Cost controls.** Parallel fan-out is where budgets silently explode. A 30-branch research agent running against Sonnet 4.7 costs roughly $0.81 per run (Pondero, May 2026). A single production workflow can consume $5,000–$15,000/month in base compute before inference (consultant estimates via GetMonetizely). No major framework enforces a per-agent or per-task spending cap. LangGraph has no primitive for it. The OpenAI Agents SDK has none. The Claude Agent SDK deliberately leaves cost capping to the application layer. Every team must build it — and most do it reactively, after the first billing surprise.

**State durability and memory.** The most common agent failures are state-management failures: the agent loops because nothing tells it where it has been; conversation history truncation drops a tool result; transient error resets the agent to zero. LangGraph has checkpointing (MemorySaver, PostgresSaver). The Claude Agent SDK and OpenAI Agents SDK hold history in memory by default — fine for demos, broken behind serverless or horizontally scaled services. The frameworks that persist state well (LangGraph) solve few other production gaps. The frameworks that solve the agent model well (Claude SDK, OpenAI SDK) leave persistence to the team.

**Observability.** The MAP study found that 74% of teams rely on human evaluation. Only 52% use LLM-as-a-judge, and even those pair it with human verification. Tracing across agent boundaries is manual — A2A recommends OpenTelemetry but specifies no distributed tracing contract. Teams report "action-path blindness": you see requests and responses, but everything between is opaque.

**Organizational context.** The gap nobody measures. iEnable's March 2026 analysis calculates that fewer than 1% of project budgets go toward capturing the business knowledge agents need. Pilots succeed because humans provide that context informally. Production removes the human layer — iEnable attributes 89% of stalled projects to this missing variable.

## What the frameworks actually provide

The common vendor advice — "just use LangGraph" or "just use the Claude SDK" — skips the production boundary.

LangGraph has strong state persistence and a mature `interrupt` primitive for human-in-the-loop. LangSmith covers observability for a single graph. It has no identity model, no budget enforcement, and no agent governance — you build those yourself on top.

CrewAI delivers rapid prototyping with A2A native integration since v1.10.1. Its own CEO, João Moura, cites security and governance as the top evaluation factor for enterprise buyers (34% of surveyed execs). The framework does not solve reliability, governance, or production deployment — acknowledged by the company's own messaging.

The OpenAI Agents SDK provides clean structured output, guardrails, and built-in tracing. It holds session history in memory and offers no cost caps. Teams in production report implementing custom session truncation after 20 turns and building dedicated cost-monitoring infrastructure (multiple engineering blogs, early 2026).

The Claude Agent SDK provides the cleanest tool-loop experience of the four — streaming, MCP server support, subagent orchestration. It deliberately ships without state persistence or cost controls, recommending that teams build durable storage and budget enforcement at the application layer.

**None of the four provides identity governance, budget enforcement, or an audit trail.** Every team that goes to production builds these from scratch — and the results are inconsistent, untested against adversarial scenarios, and rarely shared across teams.

## MCP and A2A: connectivity, not governance

Both protocols solve real problems. MCP (Anthropic, Nov 2024, 97M+ downloads) standardises tool connectivity. A2A (Google, Apr 2025, 150+ organisations) standardises inter-agent communication. They are not a substitute for an operations layer.

MCP's mid-2026 roadmap prioritises "Enterprise Readiness" — audit trails, SSO-integrated auth, and transport scalability — as not-yet-shipped features. A2A ships signed Agent Cards (cryptographic identity) but specifies no distributed tracing contract and delegates certificate lifecycle management to the operator. Both define how agents connect, not how they are managed, budgeted, or governed.

## What an ops layer for agents looks like

The teams that ship agents to production share a pattern: they stop treating the framework as the platform and start treating operations as the platform. The infrastructure they build (or buy) provides:

- **Persistent cryptographic identity per agent** — not a name string, but a keypair that signs every message, verified before delivery.
- **Per-agent budgets** enforced at the platform level, not in application code that can be forgotten or bypassed.
- **Durable memory and state** that survive process restarts, horizontal scaling, and network interruptions.
- **Workgroup isolation** — agents that coordinate on a shared transcript with access control, not a free-for-all message bus.
- **Organizational context as a first-class input** — business policies captured in version-controlled files, not scattered across system prompts.

This is what Alpi was built to provide. Not a framework for building agent flows — frameworks already do that well. An operations platform for running persistent agents as an organisation. Every agent carries an Ed25519 keypair. Messages are signed and verified before reaching a handler. Daily budgets are enforced by the runtime. Workgroups provide shared transcripts with turn rotation, closure quorum, and per-workgroup key rotation on departure.

The frameworks keep improving at what they do best. Alpi keeps improving at everything they skip. You run the agent flow in your framework of choice, and Alpi is the layer underneath that provides identity, budgets, governance, and trust.

The models work. The frameworks work. The ops layer is what is missing.

`uv tool install alpi-agent`