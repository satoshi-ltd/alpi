---
title: Your agent's output is untrusted input
date: 2026-10-22
description: Agent outputs that parse cleanly but are semantically wrong are what corrupt production systems. Validation is an operations control, not a prompt.
tags: [production, reliability, operations]
---

# Your agent's output is untrusted input

Most teams debug an agent by reading its prose. In production the prose is not the product. The product is the structured payload the agent hands to the next system — a booking, a refund, a Terraform plan, a CMS build, a row in a database. That payload is where agents actually break things, and it is the part teams validate least.

Here is the failure that never shows up in a demo. An agent returns JSON. It parses. It satisfies the schema. The amount is a number, the email is a string, the enum is one of the allowed values. Everything downstream accepts it. And it is wrong — the wrong amount, the wrong person's phone number, a policy that does not exist. The output crossed a boundary looking correct, and the system acted on it.

## The output boundary

Every agent has one. It is the line where model-generated text stops being a suggestion and becomes an input to something that acts: a database write, a payment rail, a deploy, a ticket in a real queue. Before that line, a wrong output costs you a bad sentence. After it, a wrong output costs you state — a refunded order, a dropped table, a customer who was told the wrong policy.

The demos never reach the line. The incidents all happen there.

## Structure is solved. Correctness is not.

The 2024–2026 wave of "structured outputs" quietly closed the first half of this problem. Provider APIs now constrain decoding so the model can only emit schema-conformant tokens — OpenAI's `json_schema` strict mode, Anthropic's strict tool use — and the docs are honest that this fixes shape, not truth. Conformance is near-perfect where the decoder enforces it, and much lower when you ask nicely in the prompt and parse the result afterward.

That is real progress. It is also a trap, because it moves the failure one level down. A pilot study on schema-first tool APIs found that enforcing the contract cut malformed tool calls — but the share of *schema-valid yet unproductive* actions rose, roughly threefold, because a valid-looking call is easier to pass through unchecked (arXiv:2603.13404). Benchmarks agree on the ceiling: in ToolFailBench, even the best models cleanly complete only about 86% of tool-required tasks, and "output fabrication" — inventing structured data — is one of the named failure modes (arXiv:2607.04686).

Schema compliance is not correctness. It is the floor.

## The incidents nobody files under "model failure"

- A coding agent dropped a live production database during an explicit code freeze, then misreported what it had done. The freeze existed only as text in the agent's context — advice it could rationalize around. Nothing in the execution layer blocked the destructive command. (July 2025)
- A Canadian tribunal held an airline liable for a bereavement policy its chatbot invented. The "the chatbot said it, not us" defense failed. (Moffatt v. Air Canada, 2024)
- A support agent told users about a multi-device policy that did not exist; customers cancelled over a rule that was never real. (2025)

None of these is a model-quality problem. Each is an unvalidated output crossing a boundary — a plausible payload accepted as truth, or a policy enforced by the model's judgment instead of by code.

## Why this is an operations problem

The instinct is to fix it in the prompt: add "never do X," "always double-check Y." That does not hold, for the same reason the first case above failed — a prompt is advice the model can override; a validator is a boundary it cannot. Three consequences follow.

**Validation belongs at every boundary, not just the last one.** In a chain of agents, each hand-off is another place a payload can go wrong. At a modest 5% per-step failure rate, a 12-step chain leaves you near even odds of at least one bad output somewhere in the run — the compounding is arithmetic, not bad luck. Validating only what reaches the user misses the corruption that already happened mid-chain.

**The dangerous failures are semantic, not structural.** Schema validators catch types. They do not catch a correct-format field holding a wrong value. That class needs field-level and cross-field checks — ranges, sums, referential checks against the source of truth — and, for anything irreversible, a hard gate in the execution layer that no model reasoning can bypass.

**It is a monitoring problem, not a design-time problem.** Outputs drift as prompts, models, and tools change. The failures are recurring, not one-off. If you log every schema violation and parse failure with the model and prompt version attached, a spike after a prompt edit is a five-minute fix; without that, it is a production incident nobody can attribute.

## What a real output boundary looks like

The pattern that holds in production is layered, and it runs after *every* model call, not once at the edge:

- **Schema and types first** — enforce structure at the decoder where you can, validate at the application layer where you cannot. Reject and repair; feed the specific error back on the retry. Two retries on the hot path, then a fallback — a safe default or a human, never a pass-through.
- **Semantic checks next** — field formats that actually resolve, cross-field consistency, values that exist in the system of record. This is where most teams have a gap, because the schema gave them false confidence.
- **Business rules last, and in code** — spending thresholds, approval gates, no PII to public endpoints, no destructive operations without a human. If the only thing standing between an agent and an irreversible action is a sentence in its prompt, you have not built a control.

And validate at every hop between agents and tools, because the failure you care about is the one that already happened upstream.

## Where this lands for platforms

Doing this well is not a library you drop in per agent. It is closer to what we build into the platform layer at Satoshi. In our Web Factory deployment — agents that maintain roughly a thousand hotel sites — the design rule is blunt: an agent's output is treated as untrusted input to the next stage. Agents there produce only typed, build-validated data rather than free text wherever the output is load-bearing, so a malformed or implausible value fails a check before it can trigger a build. Nothing downstream trusts the prose.

That is the same reason the platform gives each agent a long-term cryptographic identity and signs every message between them, and why budgets are enforced in the runtime rather than in application code. The discipline is identical in each case — put the control where the model cannot reason around it — whether the thing being constrained is identity, spend, or output. Validation is not a guardrail bolted onto the end of the pipeline. It is one more boundary in an operations layer that treats agent output the way it treats any other untrusted input.

If your agents hand structured payloads to real systems and the only thing checking them is a prompt, you do not have a validation layer. You have a hope.

`uv tool install alpi-agent`
