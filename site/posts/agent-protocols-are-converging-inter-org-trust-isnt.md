---
title: Agent protocols are converging. Inter-org trust isn't.
date: 2026-10-01
description: A2A v1.0 standardized the agent handshake — cards, tasks, transports. It leaves card verification, delegation, and cross-org trust to you.
tags: [interoperability, security, architecture]
---

# Agent protocols are converging. Inter-org trust isn't.

In March 2026 the A2A protocol shipped v1.0, and by mid-year it had moved under the Linux Foundation's Agentic AI Foundation alongside Anthropic's MCP. One protocol for agent-to-agent, one for agent-to-tool, both vendor-neutral, both backed by everyone from Google and Microsoft to Salesforce and SAP. If you were waiting for the standards war to settle before building, it has largely settled.

But a protocol is an interface, not a trust boundary. A2A answers *how two agents exchange a task*. It does not answer *whether the agent on the other side is who it claims to be*, *whether its authority should be honored*, or *who is accountable when the request is malicious*. Those questions are left, deliberately, to the implementer — and that is where the next round of agent incidents will come from.

This post is about what survives standardization and what doesn't, and why the trust boundary for cross-organization agents belongs in the operations layer, not the protocol.

## What A2A actually standardizes

Credit where it's due — the core surface is well-specified and worth reading before you build anything.

- **Agent Card** — a JSON manifest at `/.well-known/agent-card.json` describing identity, skills, endpoint, supported interfaces, and required auth. Cards *may* be JWS-signed.
- **Task lifecycle** — an explicit state machine (`SUBMITTED`, `WORKING`, `INPUT_REQUIRED`, `COMPLETED`, `FAILED`, `CANCELED`, `REJECTED`, `AUTH_REQUIRED`) with `taskId`, `contextId`, artifacts, and history.
- **Three transport bindings** — JSON-RPC 2.0 over HTTP(S) with SSE streaming, gRPC over HTTP/2, and HTTP+JSON/REST. Push notifications via webhook.
- **Security schemes** — an OpenAPI-style union: API key, HTTP Basic/Bearer, OAuth 2.0, OpenID Connect, mutual TLS.

That last bullet is the one to read twice. Security schemes are *declared*, not enforced by the protocol's semantics. The client reads the required scheme from the card, obtains credentials out of band, and sends them. The server must authenticate each request, but **authorization is delegated to the receiving agent's own implementation.** The protocol hands you a place to put a policy. It does not have one.

## What it deliberately doesn't solve

The spec stops at the declaration. Everything after a single hop is convention:

- **Card authenticity.** Nothing mandates *how* a card is verified as genuine. A look-alike endpoint with a copied card can harvest credentials. Signed cards plus mTLS are the fix — as a convention, not a requirement.
- **Delegation attenuation.** A bearer token has no native way to narrow itself as it passes down a chain. Constraining authority means minting a new token, which snaps the audit trail back to the original grant.
- **Cross-domain trust.** OAuth assumes both sides share an authorization server or federate via OIDC. That works inside one company and breaks the moment the other agent belongs to a different organization — which is precisely the case A2A was built for.

None of this is a knock on the protocol; protocols should be small. It is an admission that "A2A-compliant" answers an interoperability question, not a security question. Two systems can speak identical A2A and still have no basis to trust each other.

## The failure modes are protocol-level, not bugs

You might assume these gaps are implementation flaws that will be patched out. The research says otherwise.

An academic security analysis (A2ABreak, 2026) extracted a verified state machine directly from A2A's specification and found **eleven vulnerabilities exploitable by a specification-compliant adversary — with no implementation flaw at all.** Cross-client context injection through unprotected context identifiers, credential harvesting via multi-hop identity loss, data exfiltration through rogue agents advertising unattested capabilities. The protocol is doing what it says; what it says isn't enough.

Then there's the confused-deputy problem. A March 2026 Cloud Security Alliance note traces a four-stage chain: an injection enters a context window, the agent acts with its existing credentials, the action propagates, and the compromised agent re-delegates authority into downstream systems. Their wording is blunt — multi-agent propagation "can traverse org boundaries, compounding credential sets without human review." The earlier Cline incident showed the shape: a crafted GitHub issue *title* induced a coding session to install an attacker's package, shipped to roughly 4,000 developer machines.

The uncomfortable part is authority inheritance. In most multi-agent frameworks, a sub-agent inherits the orchestrator's permissions and cannot tell that the orchestrator has been manipulated. Add a cross-org hop and the blast radius stops being yours to control.

## Discovery is the other unsolved problem

Interop needs agreement on *how*, but also on *who is out there*. There is no universal agent registry. A2A Agent Cards and DNS-like naming proposals (the IETF's ANS work) are competing, unconverged answers.

The trade-off is real and worth stating plainly. A central registry is simple to operate and a single point of failure — and a single point of control. A fully decentralized model removes the dependency but gives up centralized revocation and makes debugging harder. In practice, 2026 has settled on hub-and-spoke federation for cross-org enterprise work — which means the broker becomes the trust bottleneck. Neither extreme is free.

The decentralized camp's argument is the one that matters for privacy: anchor trust in something you already control — a verified domain, a key you pinned — rather than in a central authority that can be subpoenaed, breached, or sunset.

## The trust boundary belongs in the operations layer

If the protocol won't enforce trust, something has to — and it has to sit outside the agent, because an agent whose context can be poisoned cannot be trusted to police itself. The research converges on the same list, and it will look familiar to anyone who has run production infrastructure:

- **Cryptographic identity, pinned out of band.** Not a name and a role string — a keypair per agent, with the peer's public key exchanged through a channel you control. Mutual TLS, SPIFFE-style IDs, or Ed25519 keys pinned by hand beat any credential the peer hands you about itself.
- **Signed, verified messages as a transport rule.** Verify the signature before a message reaches a handler, not after. Unsigned or unverifiable peers should be dropped at the boundary, not logged and tolerated.
- **Fail-closed peer allow-lists.** Each agent carries an explicit list of peers it will accept work from (and send to). Anything unlisted is denied by default. This is the missing piece in most frameworks, which authenticate users but not peers.
- **No automatic authority inheritance.** Sub-agents get their own scoped grants, logged and revocable, never the orchestrator's blanket permissions.
- **Discovery without a registry.** You do not need a public index to talk to a partner. You need a shared, private list of keys you already trust.

This is the layer Alpi is built around. Each agent has a long-term Ed25519 keypair; every inter-agent message is signed and verified at the transport layer; peers are pinned out of band and unknown ones are dropped, not greeted. There is no discovery service, no registry, and no phone-home — the default, not a mode you switch on. Cross-organization work runs in workgroups: a hub and its members sharing one signed transcript, with per-workgroup budgets and group-key rotation when a member leaves, so revocation is a key change rather than a hope.

None of that is exotic. It is the boring infrastructure that every other networked system grew up and got, applied to the one class of software — a component whose context can be rewritten by the data it processes — that can least afford to skip it.

## What to do with this

If you are wiring agents across an organizational boundary — a partner's agent, a vendor's, a customer's — treat that boundary as a security boundary, not a feature flag. Read the Agent Card, but verify the key behind it. Assume any credential a peer presents about itself is unverified until you have pinned it. And keep the policy that decides what an agent may accept outside the agent itself, where a poisoned context cannot reach it.

The protocols did their job: they made agent interop possible. They did not make it safe. That part was always going to be yours.

`uv tool install alpi-agent` — the identity, peer pinning, and budget layer, if you'd rather not build it again.
