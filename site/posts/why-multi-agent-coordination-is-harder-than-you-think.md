---
title: Why multi-agent coordination is harder than you think
date: 2026-06-19
description: The hard part of multi-agent systems isn't building agents — it's how they coordinate. Most frameworks leave that as your problem. Workgroups shouldn't be an afterthought.
tags: [coordination, architecture, workgroups]
---

# Why multi-agent coordination is harder than you think

Two agents talking sounds simple. Agent A sends a result to Agent B; Agent B acts on it. Anything beyond that — three agents, a shared context, a task that spans both — and the failure modes multiply faster than most teams expect.

DigitalOcean's 2026 study: 67% of organizations see gains from agent pilots, but only 10% scale to production. The gap isn't model quality. It is the layer between agents — coordination, state, identity, trust. The framework ecosystem has been slow to own it.

## The quadratic trap

Coordination cost does not grow linearly with agent count. Two agents have one potential interaction. Four agents have six. Ten agents have forty-five. Each interaction is a seam — a place where context gets dropped, decisions conflict, or the wrong agent acts on stale information.

In production telemetry documented across several deployments, coordination overhead from raw message passing exceeds the parallelization benefit beyond a handful of agents. The system becomes more brittle.

The structural problem: most frameworks treat agent interaction as message passing between independent processes. Each agent holds its own view of the world. Every handoff is a compression step — you either forward the full conversation (quadratic token growth) or summarize it (lossy, edge cases vanish). Either way, the downstream agent works with an incomplete picture.

## What the frameworks actually give you

LangGraph models workflows as directed graphs: nodes are function calls, edges define state flow. It is precise, typed, deterministic — and it leaves identity, authentication, and peer verification to the implementor. There is no "which agent is talking" at the protocol level.

CrewAI abstracts agents as roles with goals and backstories. Intuitive for prototyping — until you need actual coordination. The hierarchical "manager" does not orchestrate in practice: it sequences tasks in order regardless of routing logic. Agents overwrite each other's outputs because there is no write arbitration. A detailed investigation found the manager ignores its routing logic and runs tasks in the order they were listed.

Neither framework is wrong for what it does. The gap is that both assume coordination is a wiring problem — put agents in the right order, give them tools, they will sort it out. Production teams consistently find the wiring is the easy part. The hard part is the layer underneath: who each agent is, what it is trusted to do, how handoffs are authenticated, how the team recovers when an agent goes off-course.

## The industry woke up to this gap in 2025

Google released Agent2Agent (A2A), a protocol for cross-framework agent communication. Anthropic's MCP and the emerging Agent Communication Protocol (arXiv, Feb 2026) define how agents discover each other and delegate tasks. OpenAI's Agents SDK introduced first-class handoff primitives.

All acknowledge the same truth: agent-to-agent communication needs a designed protocol, not a convention in code. But protocols define what a message looks like, not how agents stay in sync, share a transcript, or enforce a budget across a multi-step workflow.

## What a workgroup layer provides that messaging does not

An agent workgroup is not a shared inbox. It is a structured coordination space with properties ad-hoc message passing lacks:

- **Shared transcript, not point-to-point messages.** Every agent in the workgroup sees the same thread. No "did Agent C receive the update" — it is in the transcript. This eliminates the stale-state propagation pattern that accounts for a large share of production failures.
- **Signed identity on every post.** The transcript records which agent said what, signed by that agent's key. Downstream agents verify that a message claiming to be from the Researcher was actually written by the Researcher. This prevents the "hallucinated consensus" failure where a false output propagates undetected because nobody can audit the source.
- **Turn rotation and quorum, not free-for-all.** Workgroups define who speaks when and how decisions close. A task reaches closure only when required agents have posted. No ping-pong loops burning API budget while agents pass the same unresolved task back and forth.
- **Per-workgroup budget.** Coordination cost is managed at the workgroup level. A daily ceiling; when exhausted, the workgroup fails closed. No runaway loops.

## Alpi's workgroups as the infrastructure layer

This is where Alpi's workgroup model enters — not as a competing framework for building agent logic, but as the coordination layer frameworks do not provide.

A workgroup in Alpi is minimal: a hub, a shared transcript, and member agents, each with its own Ed25519 keypair. Messages are signed by the sender and verified by the hub before reaching other members. Unknown peers are dropped at the transport layer. The transcript is encrypted for the workgroup; when a member leaves, the group key rotates.

Budgets are a first-class property of the workgroup, not a monitoring afterthought. Enforced by the platform, not by application code a developer might forget to write.

The design is conservative by intention. Alpi does not assume agents can self-regulate their coordination. It provides structural constraints — identity, budgets, transcript integrity — that make multi-agent systems predictable enough to leave running unattended.

## The test for your next multi-agent system

Before adding another agent to a deployment, ask: does the platform provide cryptographic identity for every agent? Does it verify every message before it reaches a handler? Is there a shared, tamper-evident transcript? A budget enforced at the workgroup level?

If the answer to any is "we will build that ourselves," reconsider. Teams routinely spend six to twelve engineering-months building this layer on top of a framework — not because the framework is bad, but because it was never designed to provide it.

`uv tool install alpi-agent`