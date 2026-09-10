---
title: Prompt injection can't be solved. It has to be contained.
date: 2026-09-03
description: The industry has stopped pretending it can filter injection away. The ones that survive treat it as a blast-radius problem — and bound it with permissions, not prompts.
tags: [security, operations, agents]
---

# Prompt injection can't be solved. It has to be contained.

An attacker in late 2025 planted a single GitHub issue in a public repository. When a developer's AI assistant read it, the injected instructions told the agent to list private repositories and exfiltrate salaries, API keys, and customer data — by committing it to a public pull request in the attacker's own repo. The official GitHub MCP server held a broad personal-access token covering both public and private repos, so the agent had all the reach the instructions needed. No credentials were stolen. They were already there.

That is indirect prompt injection, and it is the defining security problem of agentic AI. OWASP's first Top 10 for agentic applications, released December 2025, ranks it **number one** — ahead of stealable identity, poisoned memory, and tool misuse. This post is about the uncomfortable conclusion that the industry has converged on: you cannot filter injection away, and you should stop trying. You can only make it not matter.

## The model does not distinguish instructions from data

The temptation is to treat prompt injection like SQL injection — patch the parser, escape the input, and the class of bug dies. The UK's NCSC made the point directly: prompt injection is *not* SQL injection, because inside a model's context there is no hard boundary between instructions and data. Text you intended as inert content and text an attacker wrote to steer behavior occupy the same tokens, and the model cannot reliably tell them apart.

This is why every guardrail layer is breakable. Researchers measured **Best-of-N attacks succeeding 89% of the time against GPT-4o** and 78% against Claude 3.5 Sonnet, defeating content filters, rate limiting, and safety training in one shot. Models are better at *resisting* injection than they were a year ago — but resistance is a probability, not a guarantee, and the agent only needs to lose once. OpenAI's own security leadership conceded in late 2025 that prompt injection "may never be fully solved" for agentic workloads.

So the honest goal is containment, not prevention. The question shifts from *"how do I stop the injection?"* to *"if the agent is injected, how little can it do?"*

## Blast radius is a permissions problem

Indirect injection only causes damage proportional to what an agent is allowed to do. An innocent customer-site chatbot being told to hallucinate a car deal is embarrassing; that same trick on an agent holding a wide token that spans private repositories exfiltrates your customer data. The difference is not the injection — it is the permissions.

The highest-leverage defense is least privilege, applied the way security teams already apply it to human accounts, but per agent and per action:

- **Capability allow-lists.** An agent gets the exact tools its workflow needs and nothing else. Deny everything by default. An email-reading agent that has no write tool cannot exfiltrate a contact list by sending it anywhere.
- **Short-lived, scoped credentials.** The GitHub MCP incident hinged on a long-lived token that could read and write both public and private repos. Scoped, short-TTL tokens bounded to one repo make an injected agent much less useful.
- **Separate the reader from the actor.** Simon Willison's dual-LLM pattern — a quarantined model that reads untrusted content but holds no tools, passing only structured summaries to a privileged model that holds tools but never reads raw external content — severs the path by which injected instructions reach anything that can act. OWASP cites it directly.

The stable rule underneath all three: **treat tool output as data, not instruction.** System context holds instruction; everything the agent fetched from a web page, an email, a PDF, or a GitHub issue is unverified input. A policy layer — not the model's own judgment — should decide whether a proposed action is consistent with the original task.

## The last line is a human gate, not another model

For the actions that least privilege still leaves open — sending external mail, mutating data, moving money, approving a commit — the check belongs to a human, not to a second LLM doing the same context-evaluation job and vulnerable to the same attack. Approval should be gated on **action risk, not model confidence**: an agent saying it is confident a request is legitimate proves nothing, because it may be the injected instruction talking.

This is blunt but it works, and it is how every serious vendor frames it: human-in-the-loop is the last line of defense on irreversible, high-side-effect, or financially meaningful actions. It costs a little latency. Not injecting a failed email blast or an unauthorized payment saves considerably more than that.

## What fail-closed looks like

There is a shape to agent infrastructure that survives injection as a matter of design, and it does not depend on the model being vigilant. It is unglamorous and it compounds:

- **Identity per agent.** Cryptographic identity, so an action can be attributed to a specific agent and its permissions scoped to that agent alone.
- **Fail-closed transport.** Unknown peers dropped at the transport layer; an agent only talks to agents and tools it is explicitly allowed to reach.
- **Approval and audit as platform primitives.** Human gates on privileged actions, and a durable record of what each agent did — so when an injected agent does get loose, you can see exactly what it touched, and can revoke it.

This is the operational layer, and it is exactly what frameworks and vendor SDKs do not ship: they give you the graph and the model call, and leave identity, scoping, budgets, and gates to the team. Six to twelve engineering-months of building it yourself, in the usual telling.

## Containment is a feature, not a fix

Prompt injection will keep happening. The models will get better at resisting it, and attackers will keep finding the margin. The organizations that run agents without severe incident are not the ones with the cleverest guards — they are the ones who built their agent layer so that a successful injection is an inconvenience, not a crisis. Least privilege, tool output as untrusted data, human gates on the dangerous actions, and a platform that makes identity and approval defaults rather than afterthoughts.

The next time someone sells you a prompt that is immune to injection, remember the car that sold for a dollar, and the private repo that walked out in a public pull request. Defend where you can, and bound where you cannot.

If you want to see the operational defaults that make containment practical, `uv tool install alpi-agent` and read the source.