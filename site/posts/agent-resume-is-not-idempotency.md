---
title: Agent resume is not idempotency
date: 2026-11-19
description: Durable execution recovers where an agent was, not what it already did. The gap between a side effect and its journal is where double charges live.
tags: [operations, reliability, architecture]
---

# Agent resume is not idempotency

An agent is twelve steps into a fourteen-step task. It has already pulled the invoice, validated the amounts, and called the payment API. Then the worker gets redeployed, or the container OOMs, or a rate limit throws. The process dies. You bring it back up, the runtime finds the last checkpoint, and it resumes.

From step one. It re-pulls the invoice. It re-validates. And because nothing told it the payment already went through, it charges the card a second time.

The instinct is to blame the model — it must have re-planned badly. It didn't. The model did nothing wrong. The failure is in the runtime around it: the platform recovered *where* the agent was, and never asked *what it had already done*. Those are two different guarantees, and most agent stacks ship only the first.

## Position recovery is not effect recovery

Almost every "durable agent" claim you'll read is about position. Temporal replays workflow code against an event history so completed activities aren't re-run. LangGraph writes a checkpoint at each super-step boundary, keyed by `thread_id`, so a graph can pick up at the last node. DBOS checkpoints each step's output into Postgres tables and an executor recovers its own `PENDING` workflows on launch. All of that is real, and all of it is about *where execution was*.

The harder guarantee is about *whether the effect already happened*. And here the platforms are more honest in their own docs than the marketing around them. Temporal's activity model is **at-least-once** by default — the docs say so plainly, and an activity that timed out is retried even though the provider may have committed it. DBOS is explicit that outcomes are recorded exactly once but *steps may execute more than once*. Inngest states it does not guarantee exactly-once by default: "if the external provider accepts a request but loses the response, Inngest will retry the action." LangGraph is at-least-once across crashes — its own conformance work describes the profile as "exactly-once across interrupts, at-least-once across crashes."

Read those sentences again. Every one of them is saying: *we recover the position; making the effect safe is your job.* That is not a knock on the platforms — it's a statement about where the boundary of the problem actually is.

## The window no ordering closes

The root cause is a gap that no amount of clever write-ordering can eliminate. Your agent does two things that can never be atomic: it performs a side effect in *someone else's system* (charge the card, send the email, open the ticket) and it records that it did so in *your journal*. Those live in different systems, so there is always a window where one has happened and the other hasn't.

- **Record after the effect** — the process dies in between, and recovery replays the step. The side effect runs twice: a double charge, a duplicate refund, two identical emails.
- **Record before the effect** — the process dies in between, and recovery skips the step, believing it's done. The effect never happens, and nothing tells you. Silent lost work, which is usually worse than a loud duplicate.

Nothing about engine choice fixes this. It's a property of talking to systems you don't control. A recent study of checkpoint and rollback behaviour in agent frameworks (arXiv 2608.29381, August 2026) demonstrated the duplicate-effect case end-to-end and found that reversing the order didn't help: across 96 microbenchmark workflows, executing before committing failed 90 times, and committing before executing failed 93.

Restate is one of the few projects that documents the window explicitly rather than papering over it — a maintained issue in its docs repo reproduces a tool call firing twice on a crash between the effect and the journal, in 30 of 30 trials; add an idempotency key drawn from durable state, and it fires once, in 30 of 30. The lesson is a single sentence worth memorizing: *once the result is journaled, a step is never re-executed; if the process dies after the action but before its result is journaled, the action runs again.*

## Why long tasks fail so much more than short ones

This is why agents that look reliable in a demo fall apart in production, and the arithmetic makes it stark. Reliability compounds multiplicatively, not additively. An agent that is 95% reliable *per step* is roughly 49% reliable across a 14-step task (0.95¹⁴ ≈ 0.49). The same agent at 99% per step clears the same task about 87% of the time.

Two consequences follow. First, long-running work — the kind that pauses for a human approval, waits on a slow external system, or runs for hours — is exactly where crashes are most likely and where restarts are most expensive, because there's the most completed work to duplicate. OpenAI's Codex, which runs sessions of six-plus hours on a durable-execution backbone, is the exception that proves the rule: it only works because every LLM call and tool execution is wrapped as a recoverable step.

Second, the interesting failures are silent. An agent that errors out is annoying. An agent that *forgets* it already did something, runs again, and reports success is the one that hits your customers twice.

## The fixes that hold

None of this is unsolvable, but the solutions live in your code, not in a checkbox on the platform.

- **Wrap every side effect in a named, stable step.** Renaming it or changing its logic signals "new work"; keep the ID stable across deploys.
- **Derive the idempotency key from durable state**, not from a fresh `uuid4()`, not from a timestamp, and not from the model's `tool_call_id` — the model mints a new tool-call ID for the same intent on a retry, so it's not identity.
- **Check the key at the system of record, in the same transaction as the effect.** The dedupe has to live where the effect lands, because that's the only place that knows the truth.
- **Treat a timeout as UNKNOWN, never as FAILED.** A timeout tells you what the caller observed, not what the server committed.
- **Train on crash injection.** Kill the process after the LLM responds, after the external API succeeds but before your write, and after an approval but before execution. If those runs survive, you have durability. If not, you have luck.

The honest caveat: even all of this can fail under *concurrent* resumption — two workers both resuming the same parked approval can both fire the gated effect, which is why the dedupe belongs in the database with a uniqueness constraint, not in an `if` check.

## Where this lands for a local-first stack

The reason position recovery and idempotency get tangled together is that most agent stacks keep the agent's *thinking* in memory and push durability out to a separate service you have to wire up and operate. When the process dies, the state dies with it, and the only thing left is the last checkpoint you remembered to write.

A profile in Alpi keeps the opposite default: an agent's memory, skills, schedules, and workgroup transcripts are durable plain files on your own disk, and the agent's identity is a long-term key rather than a process name. A restart brings back the same agent, at its real position, without a separate orchestration backend to keep alive — the state was never only in memory, so there's nothing to lose.

That solves position recovery by construction. It does not make an external payment API idempotent — nothing can, from the outside. Deriving the key from durable state and enforcing it at the system of record is still on you, and any platform that tells you otherwise is selling you a guarantee it can't keep. What a good platform owes you is the honest boundary: durable state for the agent, and a clear seam where your idempotency has to live.

If you want to see what that looks like when the agent's state is a file you own:

```
uv tool install alpi-agent
```
