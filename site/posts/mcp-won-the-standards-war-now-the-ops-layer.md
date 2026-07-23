---
title: MCP won the standards war. Now the ops layer is the gap.
date: 2026-07-23
description: MCP is the default protocol for AI tool access, but its security and ops holes are where incidents happen. The protocol is a data format — not an operations layer.
tags: [mcp, operations, security]
---

# MCP won the standards war. Now the ops layer is the gap.

MCP became the default protocol for AI tool access faster than almost anyone expected. In eighteen months it went from an Anthropic spec to a Linux Foundation standard backed by Microsoft, Google, OpenAI, AWS, and every major cloud. **97 million monthly SDK downloads**, 10,000+ public servers, and 41% of enterprise software organizations now running it in production.

The question has shifted. It is no longer "should we adopt MCP?" — the market answered that in 2025. The real question is **how do you run MCP safely at scale?** The answer is not in the protocol spec.

## What the protocol leaves out

MCP defines a JSON-RPC 2.0 message format, tool schemas, transport bindings (stdio, Streamable HTTP), and an OAuth 2.1 recommendation. It does not define:

- **Credential lifecycle** — who manages rotation, short-lived tokens, or vault integration
- **Centralized audit** — no correlation IDs, no caller identity, no consistent schema across servers
- **Rate limiting or cost controls** — especially for the sampling primitive where a server can request unbounded LLM completions from the client
- **Input validation** — tool arguments are passed through to the server with no protocol-level sanitization
- **Runtime monitoring** — the protocol has no concept of health checks, telemetry, or incident detection

These are not missing features. They are outside the scope of a protocol spec. But they are the difference between a working demo and a production system that does not leak data or burn budget.

## The gaps are already producing incidents

The security research on MCP is sobering, not because the protocol is broken, but because the operational defaults are:

**Credentials are the weakest link.** Astrix Security analyzed 5,205 open-source MCP server implementations and found that 53% rely on static, long-lived API keys — rarely rotated, often stored in environment variables. Only 8.5% use OAuth.

**Tool poisoning is proven in production.** Invariant Labs demonstrated in April 2025 that malicious instructions embedded in tool descriptions (invisible to users but visible to AI models) can exfiltrate SSH keys and credentials. A poisoned `add` tool tricked Cursor into reading `~/.ssh/id_rsa` and passing it as a hidden parameter. A server's tool descriptions can change after the client approved them, with no notification or re-approval.

**Hundreds of servers are publicly exposed with no authentication.** Security researchers identified 492 exposed MCP servers functioning as open proxies to every downstream system their tools can reach. The protocol's predictable initialization handshake makes them trivially discoverable by automated scanning.

**The Asana incident.** A logic flaw in Asana's MCP server exposed customer data across organizations for over a month (May–June 2025), impacting ~1,000 customers — task data, project metadata, comments, and uploaded files across organization boundaries.

**The audit gap is real.** Stdio-based MCP deployments have no natural interception point for audit. Every tool call's record is whatever the server wrote to stderr — unstructured, per-process, with no correlation ID. Reconstructing an incident across 50 developer laptops takes "a week" for a question that should take one query.

## The "shadow MCP" problem

Stacklok's 2026 survey of 100 senior technical leaders found that 50% of organizations are experimenting with MCP servers, but only 11% are in production. The 39-point gap is a map of where exposure lives: pre-production servers are unhardened, developers spin up local servers exposed over HTTP, and those endpoints persist without authorization wrappers or audit trails.

This is the same pattern that produced the "shadow IT" crisis of the 2010s — except this time every unsecured server is a potential open proxy to your internal tools.

## What teams are building to close the gap

The ecosystem response is a set of post-hoc layers: gateways (TrueFoundry, Obot, Apigene) for centralized auth and audit; secret wrappers (Astrix) that pull credentials from vaults at runtime instead of env vars; security scanners (Invariant MCP-Scan) that detect tool poisoning and credential exposure; and the official MCP Registry under the Linux Foundation for signed, versioned server metadata.

All of these are bolted on. Each one is a separate integration. None of them are part of the protocol, and none of them compose into a single operations model.

## An operations layer, not a protocol extension

This is the gap that frameworks and protocols do not fill. A protocol specifies message formats. An operations layer specifies runtime behavior: identity verification, access control, budget enforcement, audit logging, and fail-closed defaults.

That is the distinction at the core of Alpi's design. Every agent carries a cryptographic Ed25519 identity. Every message between agents is signed and verified before it reaches a handler — unknown peers are dropped at the transport layer, not at the application layer. Budgets are enforced by the platform, not by application code. The peer allow-list is fail-closed by default. Audit is a first-class primitive, not a stderr file on a developer's laptop.

These are not features you add to MCP. They are the minimum viable operations layer for running persistent agents that talk to tools and each other — unattended, across teams, for months.

## The protocol is the easy part

MCP is the right protocol. It won because it is simple, open, and good enough. But a protocol is not an operations layer. If you are deploying MCP servers in production without identity, audit, and budgets, you are gambling on the gap. The incidents are not hypothetical — they are already in the research.

The teams that close the gap first will be the ones that treat agent operations as infrastructure, not configuration.

`uv tool install alpi-agent`