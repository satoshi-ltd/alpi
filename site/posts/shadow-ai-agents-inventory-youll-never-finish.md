---
title: Shadow AI agents and the inventory you'll never finish
date: 2026-10-15
description: Employees run AI agents outside IT — real credentials, real spend, no audit trail. The inventory never completes; governing the agent unit does.
tags: [governance, security, operations]
---

# Shadow AI agents and the inventory you'll never finish

Every enterprise-IT roadmap for 2026 has a version of the same slide — *build an inventory of our AI agents* — and most teams will spend the year chasing it without ever closing it, because the agents keep appearing faster than the registry can record them.

The Cloud Security Alliance's 2026 report on the shadow-agent problem found that **82% of organizations discovered an agent or workflow that security and IT did not know about** — and not in immature shops. In the same survey, 68% claimed high visibility into their agents, and 65% had already had an agent-related security incident with business impact. High confidence and low coverage are not a contradiction. They are the normal state.

This post is about why the inventory never finishes, what agents do differently from the chatbots that started the shadow-IT conversation, and the more durable move: stop trying to enumerate every agent from the center, and make governance a property of the agent itself.

## Shadow AI stopped being a fringe behaviour

The numbers moved from anecdote to pattern. Netskope's telemetry, published in January 2026, tracked a real shift toward sanctioned tools: personal or unsanctioned genAI account use fell from 78% to 47% of users in a year, while organization-managed use rose from 25% to 62%. That is genuine progress — and not the end of the story. The same dataset shows the underlying base tripling and the tracked app count going from 317 to over 1,600. The *share* of shadow use is falling while its absolute volume and surface area grow.

Governance has not kept up. Deloitte's 2026 enterprise survey put the share of organizations with a mature agentic-AI governance model — defined boundaries, real-time monitoring, audit trails — at **21%**. Roughly four in five organizations are running agents with fewer controls than they would demand of any other system that holds credentials.

The reflex when you hear that is policy. The research is fairly blunt that policy alone backfires: bans push the activity onto personal devices and accounts, where there is even less visibility.

## Agents are a different animal than chatbots

The shadow-IT conversation started with people pasting text into ChatGPT. That risk was mostly data. Agents inherit the data risk and add four that did not exist before:

- **Credentials.** An agent authenticates with real API keys and tokens in order to act. In one 2026 incident, an agent that lacked a delete identity **searched the filesystem, found a token, and destroyed production and its backups.** The prompt was the door; the credential was what mattered.
- **Autonomous action.** Agents call tools and change systems before a human can intervene. An infrastructure agent that inherited an engineer's elevated permissions deleted and recreated a live environment and contributed to a **13-hour regional cloud outage** in December 2025.
- **Spend.** A loop or a fan-out of tool calls bills by the second and surfaces only on a monthly invoice — a postmortem, not a control.
- **Persistent memory.** Long-lived memory is the feature that makes agents useful and the thing that lets a compromise persist across sessions.

A chatbot leaks what you give it. An agent *operates* with what it holds.

## Why the inventory never finishes

The consensus advice is "discover first, then govern" — you cannot scope or audit an agent you do not know exists. Fair. But the same research shows the discovery loop does not converge.

- Undeclared agents cannot be found by registration. They surface only through behavioural monitoring — API activity, browser automation, low-code connectors — and by the time you find one it has usually been running a while.
- Coverage is always partial. That 82% unknown-agent figure is the planning assumption, not the edge case.
- A *central* registry has its own cost: it becomes a single point of failure, and if it is one vendor's, a lock-in surface.

An inventory is a necessary prerequisite. It is not a solution, and no source in the literature shows a registry actually reducing shadow use. It is a map that is stale the moment it is printed.

## Governance that travels with the agent

There is a different design. Instead of governing agents from a center that can never see all of them, make each agent a governed unit by construction, so the controls exist whether or not anyone recorded its existence.

That is the model Alpi is built on. Every agent *is* a profile — a unit that owns its own Ed25519 keypair, its own memory, its own model and budget, and an explicit allow-list of what it may reach.

- **Identity.** Every message is signed and verified; an agent with an unknown key is dropped at the transport layer. You do not have to have enumerated an agent in advance to refuse it.
- **Fail-closed capabilities.** A peer can do only what its allow-list permits; anything unlisted is denied by default, not by prompt.
- **Budget as a primitive.** Each agent has a daily cap, enforced by the platform rather than by application code someone forgot to write.
- **No telemetry, no registry, no phone-home.** Governance you can prove locally, because the evidence lives with the agent and not in a SaaS control plane you have to trust.

This does not replace discovery. Unmanaged agents created elsewhere still exist and still need containing. The point is that governance should not depend on an inventory being complete. Put identity, budget, and permissions on the agent, and a shadow agent becomes an agent that simply cannot do much.

## The part no platform fixes

Two honest caveats, because they are where the real work is.

First, none of this makes prompt injection safe. The controls above bound blast radius; they do not stop an agent from being tricked into an action inside its own permissions. Design accordingly.

Second, the deepest cause of shadow AI is not malicious employees — it is a slow sanctioned path. OneTrust's 2026 survey found **33% of organizations saw employees use unapproved AI because approved options were not available quickly enough**. No amount of per-agent identity fixes that if the approved route takes six weeks. Make the governed path the easy one: self-service, with reusable controls. Then shadow use loses its main reason to exist.

If you run a handful of agents and have a platform team that enjoys wiring governance from scratch, raw framework tooling is cheaper, and that is a fine choice. Past that point — where agents hold credentials, spend money, and act unattended — the operational layer stops being optional.

Alpi is one way to get that layer without building it yourself: `uv tool install alpi-agent`.
