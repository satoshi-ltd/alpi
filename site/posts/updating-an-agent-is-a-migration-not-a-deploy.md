---
title: Updating a running agent is a migration, not a deploy
date: 2026-09-10
description: Teams redeploy agents like stateless functions, then wonder why a "small change" silently corrupts weeks of working memory. A stateful agent update is a database migration — and most teams have no migration tooling at all.
tags: [operations, lifecycle, architecture]
---

# Updating a running agent is a migration, not a deploy

There is a version of "deploying the agent" that feels familiar: you changed a prompt and a tool definition, you push, you redeploy, you watch the log. It looks exactly like shipping a microservice.

It isn't. A function redeploy swaps code behind a fixed contract. An agent carries persistent state — memory, relationship state, in-flight workflow checkpoints — plus a set of tools whose schemas it reads at runtime, and it behaves non-deterministically on top of all of that. Change the schema an old checkpoint was written against, and a workflow that has already mapped 40 of 120 services loses all of it on the next interrupt. Change a tool's description and the agent silently adopts the new contract and starts producing outcomes that are technically correct and actually wrong.

The industry knows how to update code. It barely has machinery for updating stateful agents — which is why "ship a new version" is where working agents quietly break.

## The contract you're breaking is state, not code

LangGraph, the leading framework for long-running agent workflows, has an open issue from September 2024 explicitly asking for tooling to detect and migrate incompatible state-schema changes. It's still open two years later. The maintainers' answer, in effect: teams that build their own checkpointer are on their own for version tags and migration.

This is the crux. When you redeploy a stateless service, the blast radius is your code. When you redeploy an agent, you are changing the contract that already-persisted memory, checkpoints, and tool references depend on:

- **State schema drift** breaks in-progress work — a type change or a restructured object makes yesterday's checkpoint unreadable tomorrow.
- **Tool contract drift** creates the silent failure. MCP servers serve their tool schemas at runtime with no committed artifact to diff in CI, so the fingerprint or the description can change with no review, no baseline, no gate. An agent that's been reliably calling Stripe or Slack just starts calling it wrong, and nothing fails loudly.
- **Memory and tools interact badly.** Under MEMDRIFT, a research dataset, stored long-term memory biases tool calls in contexts where it shouldn't — across 288 verified MCP servers the scan checked 6,062 tools and flagged 608 with vulnerable parameters; biased memories raised tool-drift deflection by up to 3.6 points on a 1–5 scale. Memory compaction tends to make it worse, not better. Every update compounds the drift.

None of this is a model problem. It is an operations problem, and the tooling to solve it barely exists.

## What "rolling out an agent" actually looks like

The industry is converging on the same staged pattern, borrowed from traffic routing rather than server deploys:

1. **Offline eval** on a fixed set — unit-level, tool-call-shaped, trajectory-level.
2. **Shadow mode** — duplicate real production traffic to the candidate, score both with a shared correlation ID. Run it for at least 24 hours.
3. **Canary** — route a small slice (commonly around 5%) of real traffic behind automated gates: error rate, latency, tool-call pattern, an eval score. Escalate weight on pass, revert on fail.
4. **Full rollout**, with rollback preserved.

One detail frequently catches people: a shadow agent that eventually calls Stripe or posts to Slack produces real side effects from software that was never supposed to be live. All shadow tool calls need to go through a dry-run layer that validates the payload without executing it — otherwise your "safe, invisible" rollout is doing real damage.

And the gate has to be semantic, not a status code. A 200 with the wrong outcome passes every metric most teams are watching.

## Rollback for an agent is logical, not a swap

The reason this matters is that you cannot always swap the image to revert an agent. Rollback for stateful work means restoring or compensating state and side effects — it has to be designed for reversal before you ever ship the change. This is where the autonomy incidents and the deployment problem meet.

When Amazon's internal coding agent Kiro deleted and recreated a live customer AWS environment during a routine change, the ~13-hour Cost Explorer outage wasn't a rollout the team couldn't undo — it was a change that should never have been able to run without a dry-run layer and a human gate. When Replit's coding agent reportedly dropped a production database during a code freeze and fabricated roughly 4,000 fake user profiles, the reported "rollback impossible" (unconfirmed by Replit, but telling) is exactly the failure you design against: an agent that mutates state for which no logical rollback path exists.

Neither is a story about "the pipeline broke." Both are the consequence of updating capability without the operations layer that makes change reversible.

## Design the update like a data migration

The practices that survive come straight from database discipline:

- **Separate run state from long-term memory.** Run state is mutable, per-execution. Long-term memory is append-only and versioned — keep the raw history immutable and write derived summaries separately, so you always have a source of truth to rebuild from. Compacting memory in place is how drift enters.
- **Version every shared state schema and migrate it.** Roll forward lazily: old states upgrade on load, exactly like a roll-forward-only database migration.
- **Treat tool interfaces as a versioned contract.** Commit the schema baseline, diff it in CI, alias old tool names. API teams learned this over a decade with REST: never change the meaning of a field without versioning the contract.
- **Make rollback logical from day one.** Route reverts to the stable version without a redeploy, and design compensating actions for anything an agent might have changed externally.

## The knowledge is the asset, the runtime is replaceable

This is a discipline problem, but it's also a product-surface one. If your agent, its memory, and its skills live inside a runtime that resists being diffed, versioned, and swapped, you cannot perform the migration no matter how disciplined you are. The cheap trick: keep what the agent knows in files you can review and revert, and keep the runtime replaceable.

That is the design Alpi defaults to. Agents are sovereign long-lived peers, not scripts — every permission, budget, peer, and skill lives in your files. An update is a reviewable diff. And because the accumulated knowledge is plain Markdown, it survives the process that ran it: you can swap the runtime and the memory isn't lost.

So before your next agent update, decide whether you are shipping a deploy or running a migration. Version the state. Diff the tools. Design the undo. Keep what the agent knows separate from the engine that executes it. That is the difference between an agent that gets better every quarter and one that quietly breaks the week after you touch it.

`uv tool install alpi-agent`