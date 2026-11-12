---
title: Agentic payments standardized consent. Nobody standardized the enforcement.
date: 2026-11-12
description: AP2, ACP, x402 and the card networks standardized how an agent gets payment consent. None enforce it at runtime — that gap is an operations problem.
tags: [payments, authorization, operations]
---

# Agentic payments standardized consent. Nobody standardized the enforcement.

For two years the hard question about agents was whether they could do real work. In 2026 the question moved: agents can spend money. Google's AP2 mandates, Stripe and OpenAI's Agentic Commerce Protocol, Coinbase's x402, and the card networks' agent programs all shipped in the last eighteen months, and with them came a wave of confident claims that autonomous commerce is solved.

It isn't, and the reason is specific. Every one of these protocols standardizes the same thing well: how an agent obtains and presents proof of what a human *authorized*. They answer "can this agent pay?" Almost none answer "should this payment happen, right now, under this policy, and who can prove it afterward." The consent layer got a standard. The enforcement layer didn't.

That gap is where an agent's money actually escapes, and it is an operations problem before it is a payments problem.

## What the new stack standardizes

- **AP2** (originated at Google, moved to the FIDO Alliance in 2026) — cryptographically signed *mandates*: an Intent Mandate carrying the user's price caps and conditions, and a Cart Mandate recording the exact items and price, signed at approval. It produces a tamper-evident chain from intent to payment.
- **The Agentic Commerce Protocol (ACP)** — built by Stripe and OpenAI under Apache-2.0 — standardizes agent-to-merchant checkout and passes payment credentials as scoped tokens, keeping the merchant as merchant of record.
- **x402** — Coinbase's HTTP-native stablecoin flow, now stewarded via the Linux Foundation — revives the 402 "Payment Required" status code so a machine can pay for a request.
- **Mastercard Agent Pay** and **Visa Intelligent Commerce**, including Visa's Trusted Agent Protocol — the card networks' answer: registered agents, network tokens scoped to an agent and merchant, and spending caps and time windows that travel with the transaction.

Read that list and a pattern is hard to miss. Each entry is a better way to *represent* authorization. None is a way to *enforce* it at runtime. The protocols define how consent is expressed; they leave the enforcement of it to whoever integrates them.

## Consent is not enforcement

A signed mandate proves what the user agreed to. It does not, mid-task, stop an agent that a prompt injection has redirected from spending against that mandate somewhere else. The token is valid. The action isn't what the human intended. This is the confused-deputy problem wearing a payments feature — and it's why security teams keep saying the real threat model is authority management, not injection.

Runtime enforcement is being left to the implementer. A mandate that a checkout service verifies is not the same as a spending limit that survives an agent restart, a retry loop, or a second agent in the delegation chain. The per-request signature gets checked; the policy behind it usually doesn't. And attenuation — the rule that a sub-agent may only *reduce* a limit, never raise one — is not something a standard mandate format enforces for you.

The failure mode teams underrate isn't fraud. It's a valid credential doing what it was told too many times. The documented spending incidents cluster there: sessions that ran unattended overnight, retry loops that duplicated infrastructure, and — the case that should worry anyone relying on config — a hard spending cap that was set and then silently failed to enforce. The control existed on paper. It did not exist in the path the money took.

## Nobody agrees who the agent even is

Enforcement needs an identity to enforce against. Financial systems have spent decades on authentication and still assume the party at the other end is the human who owns the account. Agents break that assumption: three identities — the human, the agent acting for them, and the service actually executing — routinely collapse into one long-lived API key.

The governance data reflects the collapse. In Cloud Security Alliance research, 68% of organizations couldn't distinguish agent actions from human ones, 74% said agents routinely get more access than their tasks require, and only 28% could trace an agent's action back to a human sponsor. Most agents, in most stacks, are not identities. They're shared credentials wearing a role string.

You cannot cap the spend of a thing you cannot name. That is the whole problem stated in one line.

## The protocols moved faster than liability

When something does go wrong, someone has to own it, and the rules here are still being written. Visa's core rules treat an agentic transaction as if the cardholder initiated it. American Express's 2026 Agent Purchase Protection covers eligible cardholders for agent error — but only when the agent is registered, authenticated purchase intent was captured, and the error deviates from it. Worldpay's read of the market: no liability shift exists yet.

The chargeback framework is binary — authorized or not — and has no box for "I told my agent to buy something cheap and it bought something expensive." That case falls between the consumer, the platform, and the merchant, and the law has not assigned it. Protocols that define how consent is expressed do not define who carries the consequences when it's exceeded.

## What actually contains an agent that spends

The controls that hold are boring and structural, and they have to sit below the application, where the agent can't reach them:

- **A real identity per agent** — a long-lived keypair, not a shared key. Every message between agents and services is signed and verified before it's handled, so a transaction can be traced to the agent that originated it rather than the credential it borrowed.
- **A budget enforced out-of-band** — a spend cap the platform applies to the agent, not a config value the agent's own code is trusted to respect. Because the documented failure is precisely the cap the code forgot.
- **Capability scoped to the task** — fail-closed allow-lists: an agent may talk to specific peers and services, and anything unlisted is denied before the request leaves the process, not after it returns.
- **An audit record that survives the run** — an append-only log tying each action to the agent that took it and the approval behind it, good enough to reconstruct a spend after the fact.

This is the layer Alpi was built as. Each agent carries its own Ed25519 identity, so it's a nameable party in a payment or delegation chain rather than an anonymous token. Its daily budget is a platform primitive that fails with a budget-exceeded error instead of an application-level check — the limit lives outside the thing being limited. Peer capabilities are fail-closed allow-lists, so a scoped agent is scoped at the transport, not in a prompt. And every message is signed, so the trail is evidence rather than a log line someone may or may not have written.

The honest limit: Alpi does not process the payment and does not want your card data. It governs the agent that makes the call — its identity, its budget, its permissions, and its record. The protocol still moves the money; the operations layer decides whether the agent was allowed to ask.

## The gap is the layer to build now

The agentic payments stack is young and patchy. Card programs are still deploying, one headline standard has already been scaled back from in-chat checkout to a referral model, and the liability rules are openly unfinished. None of that is an argument to wait. It's an argument to put the enforcement layer in before the volume arrives — identity, budget, scope, and record for every agent that can move money, enforced below the application where a prompt can't rewrite them.

If you're wiring agents to anything that spends, start there. It installs in one command and you can read the source today: `uv tool install alpi-agent`.
