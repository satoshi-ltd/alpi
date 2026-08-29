---
title: Orphaned AI agents are the incident you haven't budgeted for
date: 2026-08-27
description: Agent fleets double quarterly, but only a fifth of teams decommission agents. Orphaned agents keep credentials, memory, and budgets alive long after their owners are gone.
tags: [operations, lifecycle, security]
---

# Orphaned AI agents are the incident you haven't budgeted for

In one 18-month fieldwork account of a home-grown fleet, an operator ran 49 scheduled agents on a laptop and deliberately switched off 24 more — and still had three silent failures in a single week. One job was valid on disk, symlinked correctly, and worked when run by hand, but had never been registered with the scheduler, so it never ran. It surfaced four days later, and only because someone noticed. The author's conclusion: *exit code 0 is not proof of work.*

That is the quiet shape of the agent problem. Not the model, not the prompt — the agents you stopped paying attention to. Enterprise fleets are roughly **doubling every quarter**, but the systems that run them treat an agent like a script you can orphan: nothing retires it, revokes its credentials, or reclaims its budget when its owner moves on. OWASP's 2025 Non-Human Identities Top 10 ranks **improper offboarding as the number one non-human identity risk** — ahead of leaked secrets. This post is about why that risk compounds, and what actually retiring an agent requires.

## The problem is the attrition you never see

When an engineer leaves, a project dies, or a vendor reorgs, the humans get deprovisioned. The agents rarely do. Every survey in this space tells the same story from a different angle:

- **82%** of organizations have unknown agents running in their environments, and **41%** have discovered unknown agents more than once ([Cloud Security Alliance 2026, n=418](https://cloudsecurityalliance.org/press-releases/2026/04/21/new-cloud-security-alliance-survey-reveals-82-of-enterprises-have-unknown-ai-agents-in-their-environments)).
- **Only ~21%** have a formal decommissioning process. The other 79% retire agents by deleting the directory.
- Of enterprises that had agent incidents in the past year (**65%**), **61%** traced them to data exposure — and only **~1 in 5** teams individuate agent identities at all, so attribution is guesswork.
- **70–91%** of secrets stay valid years after the project that issued them died; a large share of non-human identities are over a year old, and a measurable share live past a decade.

The concrete version: an engineer's Okta account is disabled, but six MCP server connections — the GitHub, the data warehouse, the internal deployment API — keep working because they were issued to the *agent*, not the person. Departing employees' experiment agents still hold a token. A retired pipeline's memory store is still being written to by nothing. None of this shows up on a cost dashboard as a line item, because the cost is a future credential you no longer know exists.

## Why your stack won't catch it

The tools teams reach for are built for the build-and-monitor half of an agent's life. Observability platforms (LangSmith, Langfuse, LangGraph's own tracing) will tell you exactly what a running agent is doing. They will not, on their own, tell you the agent is orphaned, revoke its access from the five systems it was connected to, or transfer its work when an owner leaves. Retirement is end-of-life, and end-of-life is infrastructure, not monitoring.

Move up the same failure: an IAM inventory will list a stale service account but not the *agent* that was issued it and the memory it still holds. A cost cap stops a runaway loop but leaves an idle agent holding headroom and a budget nobody remembers allocating. The ecosystem wants you to build your own decommissioning ledger — by hand, one administrative console at a time — and that guesswork is exactly why 79% of the industry still has no process.

## What retiring an agent actually takes

An agent isn't a running process; it's a bundle of four things that each have to be ended for "offboarding" to mean anything:

- **Identity** — a keypair, a peer ID, the cryptographic identity everything derives from.
- **Credentials** — the tokens and grants into the systems it touched, which must be revoked *at those destinations*, not just removed from a file.
- **State and memory** — the logs, the long-term memory, the write-audits; all of it needs an owner decision between archive and delete (archiving runs head-on into privacy, copying deletes nothing).
- **Budget and peers** — the spending cap and the access-permissioning stop granting anything the moment the owner does.

Retire *before* that last list and you have a ghost: an identity nobody can prove is dead, holding a permission that outlived its reason to exist. That is precisely the "improper offboarding" case OWASP ranks first — not because one credential leaks, but because, unaudited, nothing is ever signed off and closed out.

## The "one explicit act" model

This is where the right account model changes the cost. When an agent's identity, budget, peers, memory, and logs live inside a single operational profile — and each profile is a first-class, sovereign object with its own keypair — "retiring the agent" becomes one explicit act: decommission the profile, rotate whatever it touched, archive its state as a unit. Offboarding stops being surgery on five disconnected systems and a running process you no longer own.

The point isn't that this is easy — decommissioning a profile and reclaiming its budget is still real work. The point is the loop closes. When an agent is a thing you can deprovision completely, the accidental persistence of a credential becomes *provable*. The audit trail says "this agent's key was rotated on this date, its state archived here," and that record is signed and verifiable, rather than a hope that someone noticed an unexplained token in a secrets store. That provability is what compliance is really buying: not a log, but the ability to show you closed the loop.

## Close the loop

The models, the prompts, the coordination — that's where the industry's attention goes. Retirement is where the incidents accrue. The cheapest fix is also the least likely to get done: inventory which agents run what, which human owns each one, and what happens the day you decommission it. Not a security convenience — that's a steady-state operating budget nobody has allocated.

Spend an afternoon on the inventory, a weekend on the offboarding checklist. If you'd rather treat the lifecycle as a first-class property of the agent than a script you maintain, install once and read the source: `uv tool install alpi-agent`.