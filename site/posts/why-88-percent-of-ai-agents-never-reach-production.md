---
title: Why 88% of AI agents never reach production
date: 2026-06-25
description: Most teams test agents by eyeballing outputs. The 67/10 gap — 67% see gains, 10% reach production — is an evaluation problem, not a model problem.
tags: [evaluation, testing, production]
---

# Why 88% of AI agents never reach production

DigitalOcean's 2026 survey: 67% of organizations see measurable gains from agent pilots. Only 10% reach production. The 88% that stall are not failing because the models are bad. They are failing because the teams building them have no way to verify whether the agent is working.

Most teams test agents the same way: run them a few times, look at the output, decide it "looks right." That works for a demo you watch. It fails for a system you leave running unattended for weeks.

Agents are built to *do* things, not to be *tested*. The gap between demo performance and production reliability is the single largest cause of abandonment — and it is solvable with the right infrastructure.

## "Looks right" is not a test

An agent is not a function. It has no deterministic output, no fixed code path, no consistent state after running the same input twice. The same prompt can produce different tool calls, different reasoning chains, and different results in successive runs. This makes conventional testing — unit tests, integration tests, snapshot tests — insufficient.

Teams that ship agents to production instead rely on three layers of evaluation:

**Layer 1: Trajectory tests.** The agent equivalent of unit tests. Instead of asserting output values, you assert the *sequence of tool calls* the agent made. Strict match (exact order) for high-risk workflows like payments. Unordered match for research agents where the path is flexible. Subset match to check the agent at least called the required tools. These are fast, deterministic, and runnable in CI.

**Layer 2: LLM-as-judge.** A separate model evaluates the agent's output against a structured rubric — correctness, completeness, safety. Best practice is a tiered approach: a cheap model (Claude Haiku, GPT-4o-mini) as a first-pass gate, escalating ambiguous cases to a stronger judge. Calibration sets validate that the judge's scores align with human evaluators (expect 74–82% agreement).

**Layer 3: Runtime guardrails.** Pre-inference (input validation, PII redaction, injection detection) and post-inference (hallucination checks, format compliance). The effective pattern is self-correction: a guardrail detects an issue, feeds it back to the agent with a correction prompt, and the agent retries before the user sees a failure.

Even teams that implement all three layers face a deeper problem: the infrastructure their agents run on produces none of the raw material these evaluations need.

## What the failure patterns actually are

A 2026 analysis of production agent traces identified seven failure patterns. Two dominate: **scope creep** (34% — agents tasked with more than their architecture supports) and **data quality failures** (27% — tested on clean data, deployed on messy production data). Security blockers account for another 14% — not vulnerabilities per se, but missing audit logs, access controls, and injection detection.

Multi-agent systems introduce a distinct class of failures. The MAST taxonomy (based on 200+ production traces from UC Berkeley) documents information withholding between agents, ignored inputs from collaborators, and task derailment. The deadliest is the shared-state problem: one agent updates a fact, another does not know, and the output looks *almost* right — worse than obviously wrong because it passes casual review.

And the economics are not neutral. Multi-agent systems consume roughly 15 times more tokens than simple chat interactions. Tool calling fails 3–15% of the time in well-engineered production systems. Without per-task cost tracking, a failing multi-agent loop can burn through a budget before anyone notices.

## The infrastructure gap

A team updates a system prompt. A downstream agent starts producing different output. How do they know? Most platforms produce logs, but logs without identity are noise. No traceability to a specific agent, no way to ask "who wrote this?" after a failure.

Production evaluation of agents requires infrastructure that most frameworks were not designed to provide:

- **Signed outputs traceable to a specific agent.** Without cryptographic identity per agent, every message is an orphan — no way to verify the sender, no chain of custody.
- **Per-agent budgets enforced at the platform level.** A runaway agent test should hit a hard cap, not consume the evaluation budget until someone checks the dashboard.
- **Shared, immutable transcripts.** When an agent in a workgroup produces a wrong output, you need the full context — what every other agent knew at that point, in order, tamper-evident.
- **Fail-closed capabilities.** A test agent should be unable to reach a production database because the platform never allowed it in the first place, not because a developer remembered to add a guard.

None of these are unique to evaluation. They are the same properties that make agents safe to run unattended at all. Evaluation is just the first place the gap shows.

## The evaluable agent

An agent is evaluable when every output carries a verifiable author, every task has a cost budget, every interaction is recorded in an append-only transcript, and every capability boundary is enforced by the platform instead of convention.

That is the architectural bet Alpi makes. Agent identity is Ed25519 keypairs at the profile level — every message signed, every receiver verifying before handling. Budgets are a platform primitive: a daily cap per agent and per workgroup, enforced at the transport layer. Workgroup transcripts are shared, encrypted, and tamper-evident — they *are* the evaluation dataset.

These properties do not replace an evaluation framework. LangSmith, Galileo, and others provide sophisticated scoring, tracing, and observability for agent workflows. What they cannot provide is the substrate underneath: per-agent identity that makes signed outputs possible, budget enforcement that prevents runaway evaluation costs, and shared transcripts that capture the full coordination context.

You can adopt any evaluation layer. What you cannot do in most platforms is add the infrastructure layer later.

## Start narrow, evaluate honestly

The teams that bridge the 67/10 gap share one practice: they start narrow, invest in evaluation infrastructure before scaling, and treat guardrails as execution logic rather than afterthoughts. The organizations that rush scope before building evaluability never leave the pilot phase.

The infrastructure to make agents evaluable is not a product feature. It is the design decision that determines whether an agent system survives its first production incident.

`uv tool install alpi-agent`