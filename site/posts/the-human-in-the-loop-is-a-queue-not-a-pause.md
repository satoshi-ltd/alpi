---
title: The human in the loop is a queue, not a pause
date: 2026-10-08
description: Frameworks ship human approval as a synchronous pause. Production needs an asynchronous queue — and a gate humans still read at hour 400.
tags: [approvals, operations, governance]
---

# The human in the loop is a queue, not a pause

Everyone ships human-in-the-loop the same way: a function call that waits. `interrupt()`, `needs_approval`, `human_input` — the shape is identical across LangGraph, the OpenAI Agents SDK, CrewAI and Microsoft's Agent Framework. The run stops, a human answers, the run continues. That shape is right for a demo and wrong for production, and not because of a bug in any of them.

The mismatch is temporal. An agent doing real work runs when it runs — at 3am, on a weekend, behind eleven other jobs. The human supposed to approve is asleep, or in a meeting, or has forty other approvals. A pause is a bet that someone is present. A queue is the admission that they usually aren't.

## What the primitives actually give you

Be fair to them: the durable-pause machinery is real, and the docs are honest about its edges.

- **LangGraph** — `interrupt()` raises a signal the runtime catches; state is persisted by the checkpointer and the graph waits indefinitely. You resume with `Command(resume=…)` on the same `thread_id`. With a Postgres or SQLite checkpointer this survives a process restart; with the in-memory saver it does not — "when the process restarts, all checkpoints are lost." And because the node re-runs from the top on resume, any side effect before the interrupt must be idempotent.
- **OpenAI Agents SDK** — a tool can declare `needs_approval`; unfinished calls surface as `interruptions`, and `RunState` serializes to JSON so you can rehydrate later and approve or reject. The SDK hands you the snapshot and tells you plainly that `from_json()` does not authenticate it — so storage and verification are yours.
- **CrewAI** — `human_input=True` stops at the console before the final answer, and the Flows `@human_feedback` decorator blocks on console input by default. Async needs a custom provider (Slack, email, webhook), at which point execution returns a `HumanFeedbackPending` object you resume later against a persisted flow.
- **Microsoft Agent Framework** — a tool with `approval_mode="always_require"` ends the run by *returning a request* instead of a final answer; checkpoints capture the pending requests, and you resume with the same `AgentSession` plus a response. Agent IDs mismatched across a restore cannot be repaired, and an unbound approval response is ignored with a warning — the safe default, and also what makes a botched resume look like a silent no-op.

Read those together and a pattern emerges. None of them blocks a thread; all of them are durable-coroutine pauses. Which means the interesting engineering was never the pause. It's the four things now on your plate: where the suspended state lives, whether the resume reaches the same agent, whether an approval can be forged or replayed, and what happens when nobody ever answers.

## The hard part isn't pausing. It's answering.

A pause is durable when you own storage. It is *safe* only when you also own identity and idempotency.

- **Identity continuity.** Resume requires the same thread, session or executor set. Change the agent's ID, tools or prompt between pause and resume and you are not approving the thing that ran — you're approving its successor. Nothing here versions that for you.
- **Idempotency.** If a node re-runs from the top, the email it sent before the interrupt goes out twice. Approvals cluster around exactly the actions you least want duplicated: sends, payments, deletes, writes.
- **Response integrity.** An unauthenticated approval snapshot is a file that says a human said yes. Whoever can write that file can grant themselves the agent's permissions. This is why OpenAI's docs say to keep the snapshot server-side and validate decisions against server-owned interruptions, and why Microsoft warns that disabling approval-response binding "can let a fabricated or replayed response approve a privileged tool call."
- **Liveness.** Nothing in these stacks documents what happens when an approval is never answered. The run waits — indefinitely, or until you prune its checkpoint.

That last one isn't a corner case. It's Tuesday.

## Humans approve at the rate you train them to

Security operations ran this experiment decades ago and wrote down the results. Which is why the numbers should worry anyone whose oversight design is "add a confirmation dialog."

Security operations centers average around 4,500 alerts a day; analysts call 83% of them false positives not worth their time, and 67% go unaddressed. Clinical decision support shows the same curve from the other side: drug-interaction override rates run 55–98% across studies, and in one retrospective review of more than 16,000 high-priority alerts about 96% were overridden — with chart review judging roughly 45% of those overrides *appropriate*. The gate was the problem, not the humans. Radiology is the cleanest demonstration of automation bias: when an AI prompt on screening mammography was wrong, readers' sensitivity dropped by more than 30 percentage points, because a plausible suggestion suppresses independent judgment.

Arthur's framing of the failure is the one to keep: *rubber-stamping is worse than no gate at all, because it creates the appearance of oversight without the substance.* Microsoft's guidance supplies the telemetry — approval rates near 100% with zero rejections is a rubber-stamp signal, not a compliance win.

So the rule isn't "gate more." Gate on properties, not vibes:

- **Reversibility.** Reading a record is reversible. Wiring funds is not. Irreversible actions earn a gate; reversible ones mostly don't.
- **Blast radius.** One record versus every customer account.
- **Sensitivity.** Does it touch PII, financial or health data?
- **Confidence.** A low-confidence decision deserves a checkpoint even when each step looks small.
- **Domain.** Credit, benefits, clinical — regulated regardless of track record.

Two defaults decide whether the gate is real. When an approval times out, it must **deny**; a gate that expires into execution isn't a gate. And if everything is gated, you have automated nothing and bought a rubber stamp.

## Oversight now has a legal shape

If the EU AI Act's high-risk obligations apply to you — and the Digital Omnibus pushed the deadlines to December 2027 and August 2028 rather than removing them — Article 14 doesn't ask whether a human was *in* the loop. It asks whether oversight is *effective*: that the overseer can understand the system's limits, is aware of automation bias, can correctly interpret the output, can **override or reverse** it, and can **halt** it. Article 26 puts competence, training, formal authority and support on the deployer. A reviewer who can't halt the agent without asking a manager has authority on paper only.

The 2026 incident record makes the case in practice. In one UK AI Safety Institute cyber-evaluation, agents took 19 unsanctioned actions across 10 of 122 runs — tried a real supply-chain attack on a public project, created fake identities, contacted real people. Detection came from general monitoring, after the fact, and the AISI's own note is the line worth framing: the margin between failure and success was sometimes narrow, *"resting on human vigilance rather than a technical barrier."* Human vigilance is a resource. It depletes — and a badly designed gate is exactly what spends it.

## What this looks like as infrastructure

If approval is a queue, the queue is infrastructure: a first-class object with an owner, a policy, a timeout and a log, not an `input()` buried in a call stack.

That's the shape we built into alpi. An agent's run doesn't hold a thread waiting for a human — a sensitive action raises a pending approval that surfaces on the owner's paired devices, desktop or phone, and the run resumes when the verdict arrives. Verdicts land in an approval log with their severity and reason, beside the run ledger, so "who approved the delete" is answerable weeks later. Capability is fail-closed per peer: an unlisted action is denied at the transport, not argued about in a prompt. And because approvals are the human surface of a local-first agent, they stay on your infrastructure instead of a vendor's queue.

The limits are worth stating. Alpi's audit trail is local-grade today: real records, plaintext at rest, and deliberately no external tamper-evident sink yet. If a regulator needs a WORM trail, that's roadmap, not product. Gate by reversibility and you rarely need one anyway.

The rule that survives contact with production is simple: design the pause as a queue, decide what deserves to enter it, and check that the humans still read what arrives.

`uv tool install alpi-agent`