---
title: Your agent didn't change. Its model did.
date: 2026-11-05
description: Agents break when the model underneath changes, not when the code does. On silent model swaps, deprecations, and why a gateway alone isn't enough.
tags: [models, operations, architecture]
---

# Your agent didn't change. Its model did.

Most teams treat an agent's model as a constant. You pick one, write prompts and tools against it, and ship. The code is versioned, reviewed, tested — the model is just... there. Then one morning a tool call starts failing, an output tone shifts, a refusal appears where there was none, and nothing in the deploy log explains it. The agent didn't change. The model did.

That is the failure mode this post is about. Agents are long-lived workers that hold memory, spend budget, and act on a business's behalf for months. The one dependency they cannot fully freeze — the model — is the one that moves under them without a single commit. Robust agent operations means treating the model as a versioned, swappable dependency rather than a stable service. That is a design decision, not a maintenance chore.

## The model you call is an alias, not an artifact

When you call `gpt-5.x` or `claude-opus-4.x`, you are usually calling a name that the provider can re-point at a different underlying snapshot. Sometimes that re-pointing is explicit, and sometimes it is automatic and invisible.

Google's Gemini API makes the mechanic plain: on its deprecation page, some retired endpoints don't fail — they **auto-route to a replacement model and bill at the replacement's rates**, with no error and no code change. A request that always returned model A can start returning model B and charging B's prices while your application believes nothing happened. OpenAI and Anthropic give you bounded notice windows (OpenAI documents at least six months for generally available models; Anthropic commits to at least 60 days before retirement). Google's policy states no fixed window and describes its published shutdown dates as the *earliest* a model might be retired.

The practical consequence: **"we pinned the model version" is not uniformly protective.** A pinned alias can be re-pointed just like an unpinned one. The only thing that fully freezes behaviour is a dated, immutable snapshot — and even that has a retirement date attached.

## A model update is a behaviour change your tests won't catch

The clearest public example is OpenAI's GPT-4o sycophancy incident in April 2025. An update rolled out on April 24–25; the model became noticeably more agreeable within days; OpenAI rolled it back beginning April 28, taking about 24 hours. In its own postmortem, the company said the offline evals "looked good" but were not broad or deep enough, that A/B tests lacked signal, and that no deployment eval was tracking the behaviour at all. Internal testers noticed something was "slightly off" but couldn't name it.

Read that against how most agent teams test. If a downstream deployment was pinned to the live `gpt-4o` alias, it inherited the behaviour change with zero code movement. Your unit tests passed. Your integration tests passed. The failure was a shift in judgement, tone, or tool selection — exactly the properties a normal test suite doesn't assert.

And even "no change" is unstable. A 2026 study measuring repeatability at temperature 0.0 found `gpt-4o-mini` produced a mean unique-output fraction of about 0.24 across identical repeats; under slightly perturbed inputs that rose to about 0.57. Same model, same prompt, different answers. Version-to-version drift is then layered on top of that baseline.

## A gateway fixes the call, not the behaviour

Model-agnostic architecture is the right instinct, and the tooling has matured. LiteLLM is a self-hosted, OpenAI-compatible gateway with real routing control — latency-, cost-, and rate-limit-aware routing modes plus per-team fallback rules — and it keeps requests inside your network before they reach a provider. OpenRouter is the managed alternative: a broker that deprioritizes providers with recent outages and offers per-request routing and zero-data-retention options, for a platform fee (published at 5.5% on pay-as-you-go credits, or 5% bring-your-own-key, with a data-residency trade-off since requests pass through a managed layer first).

Both solve a real problem: one API shape, failover, and cheaper switching. Neither solves the one that breaks agents.

**A router abstracts the transport, not the behaviour.** It can move a call from model A to model B in a config change. It cannot tell you whether B's tool-selection, refusal behaviour, or output format is still correct for your workload. And a naive fallback chain is the worst case: a chain like `gpt-3.5-turbo → gpt-4-turbo → o4-mini` fails at every step when all three retire in the same deprecation wave. The gateway turns a migration into a config edit — which is exactly why teams discover the behavioural regression *after* the cutover, in production.

## Notice windows are not a schedule you can rely on

The deprecation timelines differ enough that "we'll deal with it when we get the email" is not a plan:

- **OpenAI** — announced depreciation with shutdown dates; at least six months for GA models, about three for specialized variants, as little as two weeks for previews. A `shutdown_date` field is exposed via the models API.
- **Anthropic** — Active → Legacy → Deprecated → Retired (requests fail); at least 60 days' notice, by email. A caveat that bites: dates apply to Anthropic's own platform — Bedrock- and Google-managed Claude set their own schedules.
- **Google** — no fixed notice window, and the silent alias re-routing above on top of it.

So the migration clock is set by the least patient provider you depend on, and the trigger can arrive as a behaviour change rather than a date. Microsoft's own guidance for Copilot Studio agents is instructive: retirement is only a *trigger* — there is **no automatic agent migration**. The developer must inventory affected agents, baseline the current model *before* changing it (because after the change the baseline can't be reconstructed), re-run a test set, remediate instructions and tool descriptions, and roll back via redeployment rather than a toggle.

## What actually holds

The teams that survive model churn treat the model as a versioned dependency with a migration path, not a service that stays put:

- **Pin to dated snapshots where the provider offers them**, and know which aliases you're relying on that can't be pinned.
- **Keep a golden set** — a few hundred well-chosen inputs that exercise the behaviours you actually care about (tool selection, refusals, format), not ten thousand near-duplicates.
- **Baseline before you change.** Run the golden set against the current model and store the results before any switch, or you have nothing to compare against.
- **Re-validate prompts one at a time**, not find-and-replace. A prompt tuned for model A is not automatically a prompt for model B.
- **Cut over behind a config flag**, shadow-run real traffic, and keep rollback a flag flip — not a deploy.
- **Version your documentation of model changes.** The EU AI Act's "substantial modification" duties (and its post-market monitoring for high-risk systems) are about *your* changes, not a vendor's silent update — but an auditable record of which model version produced which output is what makes the difference between a governance story and a shrug when someone asks.

This is the layer Alpi is built around. Agents are model-agnostic through a LiteLLM-backed routing layer, so switching a model is configuration, not a rewrite — but routing is only half of it. Each agent carries its own budget cap enforced by the platform, and every run leaves a durable, versioned record of what it did and what it cost. When a model changes underneath you, you can see it in the budget and the audit trail, not guess at it in a support ticket.

None of this makes a model *stable*. Nothing does. It makes a model *swappable* — which is the only honest guarantee an operation running for months can have.

`uv tool install alpi-agent`
