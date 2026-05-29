---
name: kill-criterion
description: Define explicit kill criteria for a feature or initiative so that failure is detectable and the decision to stop is pre-committed
category: productivity
version: 0.1.0
origin: user
requires_env: []
tools: []
keywords: [kill, criterion, sunset, deprecate, hypothesis]
created_at: 2026-05-05
---

## When to use
When opening a feature on the roadmap, when launching an experiment, or when reviewing a live feature to determine if it should continue. Use proactively — kill criteria set at launch are far more credible than kill criteria set when the feature is underperforming.

## Output format

**Feature / initiative** — name.

**Hypothesis** — one sentence. "We believe [feature] will [outcome] for [user segment] because [reason]."

**Primary success metric** — the single number that confirms the hypothesis is working.

**Target** — the specific value that success looks like, by a specific date.

**Kill threshold** — the specific value that triggers a review for discontinuation. Not a vague "below expectations" — a number.

**Kill date** — the date by which, if the kill threshold is reached or not exceeded, the team meets to decide: pivot, extend, or kill.

**Kill decision owner** — who makes the final call. Not a committee.

**Zombie prevention** — features die slowly because no one wants to call it. State explicitly: if the kill threshold is reached by the kill date, the default action is [kill / pivot to X / reduce investment]. This default is overruled only by an explicit decision with a written rationale.

## Approach
- Kill criteria set after a feature is underperforming are not kill criteria — they are rationalizations. Set them at launch.
- The kill threshold should be uncomfortable. If you set it so low that you would never actually reach it, it is not a real criterion.
- The zombie prevention section is the most important. Most features do not die — they just quietly consume engineering and PM cycles forever. The pre-committed default is what breaks that pattern.
- One decision owner. A group deciding whether to kill something will almost always choose to extend it.
