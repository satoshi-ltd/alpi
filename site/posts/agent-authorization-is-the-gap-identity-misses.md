---
title: Agent authorization is the gap that identity misses
date: 2026-08-20
description: Who an agent is matters less than what it's allowed to do. Frameworks ship auth-n but leave the scoping that actually contains blast radius to you.
tags: [authorization, security, operations]
---

The security conversation around AI agents has settled on one question: *who is this agent talking to?* Identity, signatures, peer verification — there's a whole genre of writing about it, and rightly so. But it's the quieter question that determines whether an agent running your operations can hurt you: *what is this agent allowed to do?*

A verified identity doesn't shrink blast radius. If an agent is authenticated but holds broad or unrestricted access to tools, the signature only tells you who to blame after it deleted something it shouldn't. The containment property lives in authorization — the permissioning that decides which tools an agent may invoke, on which resources, under what conditions. That layer is where production agents fail, and it's the layer almost every framework leaves to you.

## What the tooling actually ships

The honest picture of 2026 agent stacks: everyone built the **authentication** branch, and the **authorization** branch is a patchwork.

OpenAI's Agents SDK is the most explicit. A tool can declare `allowed_callers` (which runtime may invoke it) and `is_enabled` (feature-gated, "disabled tools are completely hidden from the LLM"). For approval it has `needs_approval`, which pauses the run and lets a human approve or reject. Sandboxing exists, but selectively — hosted CodeInterpreter and ShellTool run in containers, plain `FunctionTool` runs in your own process. And there's no role or ACL system to speak of: tools are callable by the model unless you opt in to gating. The defaults are permissive, not fail-closed.

LangGraph's DeepAgents is the other pole. It ships `FilesystemPermission` rules — declarative allow/deny/interrupt policies over paths and operations — plus per-tool human-in-the-loop gates. But the default when no rule matches is **allow**, not deny. And its own docs warn that filesystem permissions do *not* apply to a sandbox `execute` tool that runs arbitrary commands — which is exactly how you'd bypass a carefully-written path allowlist. The intent is there; the enforcement is incomplete.

MCP, the protocol that won the tools war, delegates authorization to OAuth scopes at the transport level: servers challenge `insufficient_scope`, clients escalate, tokens are bound to a server's audience. That's a real capability pattern. But MCP defines **no per-tool allowlist or ACL**, and leaves which scopes map to which tools entirely to the server. Scopes gate *which server you may call*, not *which operation you may run*. The protocol that standardized the tool interface stopped short of standardizing its most sensitive edge.

## The default is scope, not least privilege

What's striking about all of it is the shared default. In frameworks and in MCP implementations alike, the load-bearing posture is **trust the model and gate the extremes.** Tools are available unless you explicitly carve them out. Write is allowed unless a rule denies it. That's the opposite of least privilege, and it's cheaper to ship, which is why it ships.

The shape of these failures is worth naming in production language:

- **Broad Owner/Admin roles granted to unblock a pilot, never narrowed.** Microsoft's 2026 framing on least privilege for agents calls this an anti-pattern alongside shared secrets and JIT-less standing access that becomes permanent in practice.
- **Prompt-level safety made to carry permission.** A system prompt that says "be careful with destructive actions" is a request, not an enforcement boundary. If the only thing stopping an agent from a write is the model being well-behaved that run, you don't have an access control grant, you have a wish.
- **Audit trails that log the response and skip the call.** When the authorization wasn't in the log, you can't prove what happened — the exact gap Microsoft flags as a useless trail.
- **Permission that doesn't cover the path that matters.** The DeepAgents "filesystem permissions do not cover the sandbox execute tool" pattern, generalized: the allowlist covers the happy path and misses the escape hatch.

## What authorization actually takes in production

The security and ops people writing about this have converged on a vocabulary: **deny-by-default allowlists**, **task-scoped roles**, **blast-radius-based approval**, **reversibility gates**, **JIT elevation**, **capability tokens**. The guidance is the cleanest iteration — bind tools with an allowlist, restrict agents to approved APIs/MCP servers, deny everything else — and gate approvals on reversibility, blast radius, and data sensitivity, avoiding both the rubber-stamp extreme and the endless-approval extreme. Microsoft's treatment adds the missing plumbing: agents as first-class principals with dedicated identities, tool-by-tool audit, and a guarded credential rotation.

The patterns worth keeping:

- **Deny-by-default.** Everything unlisted is denied at a layer the model can't override. This is what separates merely-controlled from actually-least-privilege.
- **Task-scoped, not blanket, authority.** An agent gets permission for the work given, not the union of everything it *could* invoke.
- **Step-up approval on irreversible or high-blast-radius actions.** Delete, pay, send, provision — those pause, even in an otherwise autonomous agent. Reversible, low-sensitivity ops don't.
- **Re-check and revoke on a schedule, not on a problem.** Rotation, expiry, scope reduction built in; nothing permanent.

## Where alpi lands

Alpi's relevant design choice is that capabilities are **fail-closed at the transport layer before a peer or capability exists by default.** Each agent holds an explicit allow-list of permitted peers and capabilities; anything unlisted is denied at the transport boundary, not politely declined by the model. There's no fallback to "ask the model what it wants," and no permissive default that identifies itself into more scope.

The scope is task-shaped, per independently-budgeted peer inside workgroups — a group has its own budget and membership, so a single over-broad capability can't span everything. And budget acts as a *de facto* authorization cap: an agent spending against a daily ceiling fails closed with budget-exceeded rather than continuing with widened discretion. None of that is optional; it's the platform default, which is the point. You can relax it, but deny is where a fresh agent starts.

That's the difference the frameworks are missing. They hand you the tools and a hope. Alpi hands you a boundary, checked by default, that no prompt can talk its way past.

## The practical close

Stop treating the safety of your agents as a property of the model or the prompt and start treating it as a property of the permission boundary. On the stack you already have: write the allowlist, flip the default to deny, gate the irreversible calls behind an approval step, and log the tool invocation, not just the answer the LLM produced. If you're choosing a platform, pick the one where fail-closed is the shipped default and a new capability starts denied, not available. That's the meaningfully better day today and substantially less cleanup later.

And if you're standing a fresh set of agents up small, that's a two-line start: `uv tool install alpi-agent`, and watch what the platform refuses before you even have privileges to mis-scope. — not an ad, just the path with fewer surprises.