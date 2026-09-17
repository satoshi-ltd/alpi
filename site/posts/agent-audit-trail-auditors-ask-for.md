---
title: The agent audit trail auditors will ask for — and why most teams don't have one
date: 2026-09-17
description: Regulators converge on one demand — prove who approved what, human and agent. What that log must contain, where agent platforms put the evidence instead, and the honest limits.
tags: [compliance, operations, audit]
---

# The agent audit trail auditors will ask for — and why most teams don't have one

An auditor will not ask whether your agent works. They will ask you to reconstruct, from months back, one decision: which human authorized it, which agent executed it, what data it touched, what it returned, and who approved the result. Then they will ask you to show that neither the agent nor anyone operating the platform could have edited that record since.

That request breaks most agent deployments — not through carelessness, but through architecture. The evidence exists, just in the wrong place: filed under a human's user ID, spread across session state that was never persisted, held in a vendor's cloud on the vendor's retention clock and in the vendor's chosen region.

This is the gap I want to name. Agent observability tells you what your system is doing right now. Auditability is a different property: a third party, months later, can rebuild the chain of authority behind a specific action. Most teams have the first and assume it implies the second. It doesn't.

## The deadline everyone quotes is wrong

The obligation this tends to come up in is the EU AI Act. As of September 2026, the widely repeated "August 2026 high-risk deadline" no longer holds: the Digital Omnibus on AI, [Regulation (EU) 2026/1744](https://eur-lex.europa.eu/eli/reg/2026/1744/oj/eng), amended Article 113's timeline. Annex III high-risk obligations — including the deployer duties in Article 26 — now apply from **2 December 2027**, and Annex I high-risk from **2 August 2028**.

What did *not* move:

- **GPAI provider obligations** — in force since 2 August 2025.
- **Article 50 transparency** — live since 2 August 2026. If your agent converses with people, they need to know it isn't a person.

The deferral is a planning gift, not a reason to wait. Article 26 compliance is a workstream: oversight design, log retention, worker information, updated DPIAs. Twelve to fifteen months is roughly how long that takes in a real organisation, which puts the start date about now.

## What "high-risk" actually turns on

Not architecture. Intended purpose. An autonomous agent is not high-risk because it is autonomous; it is high-risk when its output feeds a listed decision. Annex III point 4(a) is the one that catches most enterprise deployments: recruitment and selection — filtering CVs, evaluating candidates — is high-risk by name. Credit scoring, insurance pricing, benefits eligibility and biometric categorisation are too.

And a trap worth reading twice: under Article 25, a deployer that substantially modifies a high-risk system, or repurposes an Annex III system, **becomes the provider** — and inherits conformity assessment and CE marking, not just the deployer's lighter duties. Build-your-own HR screening is the full provider burden.

## What the log has to contain

The regulatory text is narrower than vendor material suggests, and more specific than it sounds.

- **Article 12 (provider duty)** — a high-risk system must technically allow automatic recording of events over its lifetime, with enough traceability to identify risk situations and support post-market monitoring.
- **Article 26(6) (deployer duty)** — you keep the automatically generated logs for at least **six months**, unless other law demands longer. HIPAA's six years for ePHI is that other law.
- **Article 26(2)–(3)** — human oversight is assigned to competent, trained, authorised named people. An oversight role with no name attached is not oversight.
- **Article 14** — the oversight person must be able to interpret outputs, recognise automation bias, override or reverse a decision, and interrupt the system.

Compress that into a sentence and you get the audit question that generalises past Europe: *who approved what, executed by which agent, on whose authority, with what data, and can you prove the record is intact?*

## Where the evidence actually lives

Four failure modes, all common.

**The agent is logged as the human.** In citizen-developer, shared-session and vendor-embedded setups, agent actions get written under the triggering user's identity. The log looks like a busy employee. There is no agent principal in it at all, which means an incident review cannot distinguish a person from an agent following standing instructions, an agent reasoning badly, or a compromised agent three hops down a delegation chain.

**The chain was never persisted.** Multi-agent flows span several hops, each with its own credential and log format. The delegation relationships — who handed what to whom — often exist only in ephemeral session state. Reconstructing them afterwards means correlating records with different identifiers and different clocks.

**Retention is set by someone else.** Vendor-managed observability generally retains agent traces for weeks, not the years a SOC 2 or HIPAA cycle assumes; Microsoft's own Agent 365 administration documentation is unusually candid on this point, stating that observability data is deleted after 30 days and that Advanced Data Residency is not supported even though the EU Data Boundary is honoured. Residency and retention are properties of your contract, not your architecture.

**Nobody planned for approvals.** Approval events — the moments where a human authorised an agent's action — are the first thing an investigator asks for and the last thing a framework gives you. The trigger, the approver, the scope, the timestamp, the result. If your platform has no first-class approval record, that evidence never existed.

## Readiness, measured

This is not a theoretical anxiety.

- **Deloitte's 2026 State of AI in the Enterprise** survey of 3,235 IT and business leaders found only **21%** have a mature agentic-AI governance model. The three capabilities it names as missing: action boundaries, real-time monitoring, audit trails.
- **EY's US AI Risk & Governance Survey** (200+ senior decision-makers at $1B+ revenue firms, September 2026) found **85%** of agentic adopters have agents acting without real-time human intervention, and **49%** have not updated their governance for agentic AI. Roughly a quarter cannot detect unauthorised internal agents.

Two independent surveys, one conclusion: the agents are running, the controls are not.

## What "auditable by construction" costs

There is no way to retrofit this at the log-aggregator layer. The material has to be produced at the point of action. Concretely, four properties:

1. **Every action carries a cryptographic identity.** If each agent owns an Ed25519 keypair and every message is signed and verified at the transport layer, the transcript is tamper-evident by construction — not because someone promised not to edit it, but because editing it breaks verification. This is how Alpi's peer protocol works, and it is the one design decision that makes the rest cheap: attribution stops being a logging convention and becomes arithmetic.
2. **Both identities are recorded.** The executing agent and the authorising human, as separate principals in the same record.
3. **Approvals are first-class events**, with approver, scope, timestamp and outcome on the transcript rather than in a queue that gets drained.
4. **The record lands where you control it.** An agent that stores its transcript on your own machine, inside the profile, with no telemetry and no phone-home, gives you a retention policy you can actually change, in a jurisdiction you can name — or export, if an auditor wants it in their tooling. Fail-closed peer allow-lists help here too: an unlisted peer is denied at the transport layer, so the set of actors that *could* appear in an incident is knowable in advance.

## The honest limits

Signing is not compliance. Alpi produces the raw material — attributable, tamper-evident, locally retained records of decisions, tool calls and approvals — and nothing beyond that. It does not perform your conformity assessment, write your fundamental-rights impact assessment, or tell you which of your use cases is Annex III. Retention and pruning policy is a decision you make, not a default the platform enforces. And a signed append-only transcript is tamper-*evident*, which is not the same as tamper-*proof*: if you need an external, write-once store for regulatory purposes, plan to export to one.

The rule to take away is simpler than the regulation: if you cannot name the human who approved a given agent action, and show a record of it that neither party could have altered, you do not have an audit trail — you have application logs. Start the workstream now, while the deadline is still fifteen months out.

`uv tool install alpi-agent` — a first profile is free to install and evaluate.