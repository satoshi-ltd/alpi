---
title: Your multi-agent pipeline has no message authentication
date: 2026-07-09
description: Every major agent framework passes messages between agents as plaintext — no signatures, no verification. That is the defining security gap of multi-agent systems in 2026.
tags: [security, architecture, agents]
---

# Your multi-agent pipeline has no message authentication

Multi-agent systems are scaling fast — 69% of enterprises are piloting or running agent deployments, and the market is projected to grow from $7.6B to $47.1B by 2030. But the infrastructure those agents run on has a gap most teams haven't noticed yet: **no agent in a pipeline can cryptographically verify where a message came from.**

This is not a hypothetical. Prompt injection attacks rose 340% year-over-year between Q1 2025 and Q1 2026. 88% of organizations report security incidents with deployed agents. And the attack vectors that exploit multi-agent pipelines — cross-agent privilege escalation, memory poisoning, tool-output injection — all rely on the same weakness: inter-agent messages are plaintext strings passed through shared context with no signature, no trust boundary, and no verification.

Every major framework leaves this gap. Here is what it means and what fixing it requires.

## How injection propagates through agent pipelines

The fundamental architectural problem is that LLMs cannot distinguish between instructions and data — both occupy the same token stream with the same attention mechanisms. In a chatbot, that means a single compromised input. In a multi-agent pipeline, it means the attack propagates.

**Tool-output injection.** A compromised tool returns data containing hidden instructions. The agent running that tool treats the output as legitimate execution context and acts on it — potentially triggering API calls, database writes, or email sends. MCP (Model Context Protocol) expanded this vector significantly because tool descriptions visible to the agent are themselves injectable. A 2025 threat model found that 5 out of 7 evaluated MCP clients implemented no static validation of server-provided tool metadata.

**Cross-agent propagation.** A compromised worker agent passes malicious instructions upward through the delegation chain. Researchers have documented this attack surface expanding multiplicatively with the number of agents in a pipeline — every additional agent is another potential vector into the trusted context. At no point does the receiving agent have a way to verify that the message is authentic.

**Memory poisoning (delayed injection).** Instructions planted in an agent's long-term memory during one session activate in subsequent sessions. The MINJA attack, presented at NeurIPS 2025, showed that an attacker who can only send queries — with no access to the memory store — can inject malicious records through carefully crafted interaction patterns. OWASP now classifies this as a top-tier risk (ASI06).

## Why agents amplify the risk beyond chatbots

A compromised chatbot produces bad text. A compromised agent triggers real actions — API calls, data exfiltration, credential use. The EchoLeak vulnerability (CVE-2025-32711, CVSS 9.3) demonstrated this at scale: a crafted email coerced Microsoft 365 Copilot into extracting files and chat logs from OneDrive, SharePoint, and Teams, exfiltrating them through Markdown image rendering to an attacker-controlled server. Zero clicks from the user.

The Promptware Kill Chain (Schneier et al., 2026) formalizes the pattern as a five-stage malware lifecycle operating entirely in natural language: initial access → privilege escalation → persistence → lateral movement → actions on objective. Agents make this viable because they hold credentials, operate unattended for minutes or hours, and trust the context they are given.

## The framework gap: no one signs messages

As of mid-2026, none of the major frameworks provide built-in message authentication between agents:

| Framework | Message auth | What they do instead |
|---|---|---|
| **LangGraph** | ❌ | State/context management primitives; security is the developer's responsibility |
| **CrewAI** | ❌ | Community workarounds include regex sanitization wrappers and delegation scope restrictions — applied post-hoc |
| **AutoGen / AG2** | ❌ | Relies on MCP/A2A for cross-agent routing, but no signing or verification at the message layer |
| **OpenAI Agents SDK** | ❌ | Ships harness-compute separation and guardrails (April 2026 update), but no agent-to-agent message authentication |

The protocols connecting agents follow the same pattern. MCP standardizes tool definitions but has no immutability or message signing. A2A (Google ADK) provides structured communication between agents but doesn't cryptographically authenticate identities at the transport layer. Okta's XAA protocol is the first serious effort at identity-bound agent access — 95% of organizations say a standard like XAA would improve deployment confidence.

The security model across the board is "policy enforcement at tool boundaries" — not trust between the agents themselves.

## What production actually needs

Meta's Rule of Two captures the core architectural constraint: an agent should possess at most two of (A) processing untrusted inputs, (B) accessing sensitive systems, (C) changing state externally. Agents with all three are indefensible without human supervision.

That rule is a design principle, not infrastructure. The infrastructure layer needs three things that do not yet ship with any major framework:

**Cryptographic identity per agent.** Each agent carries a long-term keypair. Agents prove who they are at the start of every interaction, not once at deployment time. Ed25519 keys are the standard choice — the signature size and verification speed are negligible at application scale.

**Signed messages at the transport layer.** Every message between agents carries a signature the receiving agent verifies before the message reaches any handler. Unknown peers — agents without a pinned key — are dropped before they consume context or compute. This catches injection propagation at the first hop: a compromised agent sending malicious instructions cannot impersonate a trusted peer.

**Fail-closed capabilities.** Each agent has an explicit allow-list of peers it will accept messages from. A message from an unlisted peer is denied at the verification layer, not passed to the model for interpretation. This is the difference between rejecting a forged message and hoping the receiving agent "notices" the injection.

These three primitives exist — they are not speculative. Every major framework could ship them tomorrow if message authentication were treated as infrastructure rather than application code.

## Why teams should care now

69% of enterprises say security concerns are slowing agent adoption. 88% of deployed agents have already been involved in a security incident. Only 17% of organizations monitor agent-to-agent interactions continuously. The gap between deployment velocity and operational security is the widest it has been in the agent space.

If you are building a multi-agent system today — with LangGraph, CrewAI, or any other framework — the single highest-leverage security investment is establishing cryptographic identity and signed messaging between your agents before you add the third one. The moment a pipeline has more than two agents, plaintext trust is no longer tenable. And if you would rather not build that layer yourself, choose infrastructure that ships it.

`uv tool install alpi-agent`