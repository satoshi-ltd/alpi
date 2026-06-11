---
title: Agents Don't Know Who They're Talking To
date: 2026-06-11
description: Every major agent framework identifies agents by a name and a role string — no keys, no signatures, no peer verification. What production actually needs.
tags: [identity, security, architecture]
---

# Agents Don't Know Who They're Talking To

You build a multi-agent system. You give Agent A the role "researcher" and Agent B the role "reviewer." They pass messages, delegate tasks, and produce output together. At no point does Agent A have a way to prove it is the same agent it was five minutes ago. At no point can Agent B verify that the message claiming to be from Agent A was actually written by Agent A. There is no key. No signature. No cryptographic handshake at any layer.

This is the default state of the agent ecosystem in mid-2026. Every major framework — LangGraph, CrewAI, the OpenAI Agents SDK, the Claude Agent SDK — identifies agents the same way a multiplayer game from 1998 identified players: by a string the application wrote into memory.

For demo code this is fine. For agents that move money, sign contracts, modify data, or communicate across machines, it is a structural vulnerability. This post examines how each platform handles (or fails to handle) agent identity, and what a production-grade answer looks like.

## The default: a name and a role string

Every framework has a way to label an agent. In CrewAI you write a `role`, a `goal`, and a `backstory` in YAML or Python dicts. In LangGraph an agent is a node in a state graph — it has a name and a configuration. In the OpenAI Agents SDK an agent is a config object with `name`, `instructions`, and `tools`. In the Claude Agent SDK the pattern is the same: a name, a system prompt, and a tool list.

These are labels, not identities. Nothing prevents process A from claiming to be process B. Nothing verifies that the output attributed to "researcher" was actually produced by the agent configured as the researcher. The trust model is: *everything in the same process is who it says it is, because we said so.*

That assumption breaks the moment agents run in separate processes, on separate machines, across organizational boundaries, or against an adversarial prompt.

## What the frameworks actually do

### LangGraph: user auth, not agent auth

LangGraph Platform ships a mature authentication layer — but it authenticates *users*, not agents. The platform validates API keys and surfaces the authenticated user identity via `config["configurable"]["langgraph_auth_user"]`. This means a human can prove who they are to the agent. The agent itself has no keypair, cannot sign its outputs, and cannot cryptographically authenticate to another agent node.

Inter-agent communication within a LangGraph is in-process function calls — no transport boundary, no signing, no verification. Across graphs, identity is application code you write and maintain. The ecosystem has noticed the gap: Arcade.dev sells a just-in-time authorization layer for tool access, and the open-source AIP project (Agent Identity Protocol) adds Ed25519 DIDs as a LangChain tool plugin. Both are third-party add-ons bolted onto a framework that does not ship identity as a primitive.

### CrewAI: roles as strings, no transport

CrewAI agents are in-process Python objects that delegate tasks to each other through the framework's orchestration layer. The `role` field is a prompt string — it tells the LLM what persona to adopt. There is no cryptographic material attached to an agent, no way for one agent to verify another's identity, and no signed message layer. The CrewAI AMP enterprise suite adds tracing, observability, and security scanning, but agent-to-agent authentication remains absent from the core framework.

### OpenAI Agents SDK: sandbox execution, same identity gap

The April 2026 update to the Agents SDK brought native sandbox execution, durable state with snapshotting, and a harness-compute separation designed for security. It even supports workload identity federation (AWS IAM roles, Azure managed identities, SPIFFE) for API credential management. But agent-to-agent identity remains a configuration string. Sub-agents are spawned and orchestrated by the parent agent — there is no key exchange, no message signing, no verification that a sub-agent is what it claims to be. Guardrails and sandboxing contain the blast radius of a compromised agent, but they do not authenticate the agent itself.

### Claude Agent SDK: same pattern

Anthropic's SDK follows the same design: agents are configured with names, system prompts, and tools. Sub-agent delegation creates separate sessions with their own context windows, but identity is a label attached to the session. No cryptographic verification crosses the boundary between parent and sub-agent.

### AIP: the third-party proof the gap is real

The Agent Identity Protocol (AIP) layers Ed25519-based DIDs, challenge-response verification, and signed outputs onto LangChain, CrewAI, and other frameworks as a pip package. It proves two things: the gap exists, and a capable community recognizes it. It also proves that identity bolted on at the application layer — rather than baked into the transport — will always be optional infrastructure most teams skip.

## What identity means at the transport layer

Cryptographic identity for agents is not about labels. It is about three properties that must hold before any application code runs:

1. **The sender is who they claim to be** — every message carries a signature that can be verified against a known public key. This is not a JWT issued by a platform. It is a keypair the agent owns, generated and stored locally, that survives restarts.

2. **The message has not been tampered with** — the signature covers the payload. A modified message fails verification before it reaches a handler.

3. **The peer is authorized to speak at all** — unknown public keys are rejected at the transport layer. The message is never parsed, never logged, never routed to a handler. Closed is the default.

No framework listed above ships these three properties. Every one of them requires the developer to build identity as application code, which means most teams skip it.

## Alpi's model: identity as infrastructure

Alpi was designed around these three properties from day one. The architecture is not a framework you add identity to — it is an agent operating system where identity is the foundation.

- **Ed25519 per profile.** Every agent generates a long-term keypair on creation. The public key is its identity across its entire lifecycle. No platform-issued token, no registry, no phone-home.

- **Signed messages at the protocol level.** Every ALP message is signed by the sender's keypair and verified by the receiver before any handler touches it. Signing is the transport, not a tool the agent may optionally call.

- **Unknown peers dropped at the transport layer.** A connecting peer whose public key is not in the local allow-list has its TCP connection refused before a single protocol byte is parsed. No discovery, no auto-peering, no "accept and restrict later."

- **Capabilities fail-closed.** Even a verified peer can only call methods explicitly allow-listed. Deny is the default.

- **Model-agnostic.** Because identity lives at the transport layer, it does not depend on which LLM provider a profile uses. An agent running Claude can authenticate to an agent running GPT, Ollama, or a deterministic script.

## The honest trade-off

This design carries real costs. Generating and managing keypairs adds operational surface. Allow-lists and capability tables require explicit configuration — there is no "just run it and see." ALP's fail-closed posture means a misconfigured peer silently fails to connect, and debugging requires checking key fingerprints and allow-list entries rather than reading a log line.

These costs are worth it when agents operate across machines, handle sensitive data, or run unattended. They are excessive for a single-process demo with two agents in the same Python runtime.

The frameworks are not wrong for skipping cryptographic identity. They are optimized for development velocity, and that is the right trade for their primary audience. The problem is that the absence of identity infrastructure means production deployments quietly spend months building it themselves — or skip it entirely and accept the risk.

## Identity is infrastructure

The agent ecosystem is going through a transition that the web infrastructure went through twenty years ago: from "trust everything on the local network" to "verify every request." Frameworks are where the web was in 1998 — HTTP with no TLS, plaintext passwords, application-level auth that every team implemented differently. TLS did not become universal because it was easy. It became universal because the web could not scale without it.

Multi-agent systems that span machines, organizations, and trust boundaries cannot scale without cryptographic identity at the transport layer. The question is not whether the ecosystem will get there — it is how many production incidents it takes before teams stop treating agent identity as an application concern.

Alpi ships identity as infrastructure today. You can see exactly how it works — the ALP protocol is Apache 2.0, and the agent core is source-available.

```bash
uv tool install alpi-agent
```