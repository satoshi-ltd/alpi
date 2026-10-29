---
title: Your context window is an attention budget, not a bucket
date: 2026-10-29
description: Models degrade long before the context window fills. Compaction, sub-agent isolation, and just-in-time retrieval beat "buy a bigger window" every time.
tags: [context-engineering, architecture]
---

# Your context window is an attention budget, not a bucket

Every few months a model ships with a bigger context window, and every few months teams read it as permission to stop thinking about what goes into it. If the model can hold a million tokens, why bother curating? Just paste more.

That instinct is measurably wrong, and 2025 made it explicit. A window size tells you how much a model will *accept*. It says nothing about how much it can *use*. Three independent lines of research now show model performance degrading as input grows — long before anything gets truncated. The window is not storage. It is an attention budget, and you spend it on every single call.

"Context engineering" is the name for spending that budget well. Andrej Karpathy called it "the delicate art and science of filling the context window with just the right information for the next step" — and Anthropic's own framing is blunt: find "the smallest possible set of high-signal tokens" that gets the job done. This post is about why that is the real constraint, and what actually moves the needle when you're running agents in production.

## The window stopped being the bottleneck

The classic mental model — performance is flat until you hit the limit, then falls off a cliff — is not what the data shows.

- **Chroma's Context Rot study (2025)** ran 18 models across roughly 194,000 calls and found performance degrading as input length grows *even on trivial tasks*, like copying a repeated word. Degradation was non-uniform across models, worsened with distractors, and — counterintuitively — models scored *better* on shuffled inputs than logically ordered ones. On LongMemEval's factual-recall task, focused prompts of about 300 tokens beat full inputs of about 113,000 tokens across every model tested.
- **"Lost in the Middle" (Liu et al., TACL 2024)** documented the U-shaped curve: accuracy is highest when the relevant passage sits at the start or end of the context and sags when it sits in the middle. On a 20-document QA task, GPT-3.5-Turbo scored about 75.8% with the answer document first, 63.2% with it last, and 53.8% in the middle — the middle case landing *below* the score it gets with no documents at all.
- **NoLiMa (2025)** drew the advertised-versus-real line. Of 13 models claiming contexts of 128K tokens or more, 11 fell to below half their short-context baseline at just 32K tokens — a quarter of what they advertise. Even the best exception, GPT-4o, dropped from a 99.3% baseline to 69.7%.

Read together: the effective window is a fraction of the advertised one, and the degradation is a gradient, not a cliff. There is no clean line where context stops working; it just works a little less at every step along the way.

## Why "just use a bigger window" doesn't fix this

It helps to understand the mechanism. A transformer computes attention across every pair of tokens, so relationships scale with the square of sequence length — every added token competes for the same attention budget, and models are generally under-trained on very long sequences. A larger window widens the container. It does not raise the attention each token gets.

Then the economics bite. Providers price long context on tiers: Google explicitly doubles the per-token input rate past 200K tokens because attention cost rises with length. And agents multiply the problem rather than solving it — Anthropic reports agents using roughly 4× the tokens of a chat, and multi-agent systems roughly 15×. Stuffing the window makes each call both slower and more expensive, at exactly the point where quality is already decaying.

## What actually works

The productive answer is not more tokens. It is spending fewer of them, better.

- **Compaction** — When an agent nears its limit, summarize the conversation and start fresh with the summary. The detail matters: Claude Code preserves architectural decisions, open bugs, and implementation details while discarding redundant tool output. Tune for recall first, then precision.
- **Sub-agent context isolation** — A specialized sub-agent runs one focused task in its own clean window, may explore tens of thousands of tokens, and returns a condensed summary of roughly 1,000–2,000 tokens. Anthropic's multi-agent research system — an Opus 4 lead with Sonnet 4 subagents — outperformed single-agent Opus 4 by 90.2% on their internal eval using the *same* models. Token usage alone explained about 80% of the performance variance. Context architecture beat model choice.
- **Just-in-time retrieval** — Keep lightweight identifiers — file paths, query strings, links — in context and load the payload only through tools when the agent needs it. Progressive disclosure instead of a pre-loaded firehose.
- **Prompt caching** — Reusing a stable prefix cuts cached-input reads to roughly a tenth of base price on major providers. But caching matches *exact prefixes*: sloppy context hygiene that shuffles the top of the prompt breaks the cache and the discount with it.
- **Tool design as a context contract** — A bloated tool set with overlapping functions doesn't just waste tokens; it creates ambiguous decision points for the model. Fewer, sharper tools are a context strategy, not just an API nicety.

## Where this lands in a running agent

Context engineering is a per-call discipline, but it needs a durable home — something that owns *which* files and state an agent assembles from, across sessions.

That is the unit alpi is built around: the profile. Each profile keeps its own memory, model choice, tool list, and budget as plain Markdown and JSON in files you control, so the context an agent assembles on a call is drawn from state you can read, diff, and edit — not a black box the runtime owns. Because alpi is model-agnostic through LiteLLM, the practical lever this unlocks is routing: send a task that needs careful reasoning to a frontier model, and route the compaction and summarization passes to something cheaper, without rewriting the agent. And the per-agent budget cap means an agent that decides to re-read half a repository hits a wall at the spend limit, not on the monthly invoice.

The honest limits are worth stating. Alpi gives a profile a place to own its context and a cap to spend it against; it does not magically retrieve the right pieces for you. Compaction policy, retrieval strategy, and what counts as high-signal are judgment calls you still make. The platform makes them enforceable and auditable — it does not make them disappear.

Start by measuring the honest window: take a task your agent currently handles by stuffing context, and run it again with a compacted, retrieved subset. If the smaller prompt wins — and the research says it usually will — you have your answer about the next window upgrade.

`uv tool install alpi-agent`
