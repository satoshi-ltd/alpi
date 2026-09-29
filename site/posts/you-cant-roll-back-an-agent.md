---
title: You can't roll back an agent
date: 2026-09-24
description: Rollback undoes code, not consequences. An agent's value is acting outside your systems, so recovery has to be designed in before the action, not after.
tags: [agents, operations, reliability]
---

# You can't roll back an agent

Continuous delivery taught a generation of engineers that a bad change is temporary. Ship it, watch the graphs, and if something breaks, revert and redeploy. The service goes back to how it was, and the damage is usually a window of wrong answers you can explain in a postmortem.

Agents inherit the deploy pipeline but not the guarantee. You can revert an agent's code, prompt or model in a minute. You cannot revert what it did while it was wrong: the email it sent, the ticket it filed, the comment it posted, the payment it started. Those actions live in systems you do not own, and they stay done.

So "can we roll this agent back?" is the wrong question. The useful one is "which of its actions can be undone, and what stops the ones that can't?"

## Why rollback works for services

Rollback works because most of what a conventional service does stays inside its own boundary. A request arrives, logic runs, a row changes in a database you control. When the logic is wrong you fix the logic, repair the rows, and the outside world mostly never noticed.

An agent is built to cross that boundary. Its whole point is to act: send, file, post, book, pay, update someone else's system. The moment an action leaves your perimeter, reversibility stops being a property of your code and becomes a property of the other system. Some of them offer an undo. Many offer only a new action that tries to compensate, like a refund, a correction or an apology, and that new action has consequences of its own.

## A kill switch only stops the next action

The first control teams reach for is a kill switch, and it is worth having. It is not recovery. Stopping an agent prevents its next action; it does nothing about the ones already delivered. By the time a human notices a problem, the agent has usually done the damaging thing several times.

Scheduled and event-driven agents make this sharper. There is often no long-running process to stop, only a job that fired, did its work and exited. The first sign of trouble is a reply from a customer.

That leaves one place to put the safety: before the action runs.

## Sort actions by what it takes to undo them

The design move that pays off is to classify what an agent can do by how reversible it is, and to gate each class differently.

- **Reads** — searching, fetching, reading files, querying. Nothing changes, so they can run freely; the controls that matter are scope and data access.
- **Compensable writes** — drafts, internal records, tickets that can be closed, changes with a cheap and honest inverse. They can run unattended if the inverse exists before the tool ships and every write is logged.
- **Irreversible actions** — external email, payments, deletions, public posts, anything whose inverse is only an apology. These need a human looking at the exact thing that will go out, or they should not be available to an unattended agent at all.

The common mistake is one approval flow for everything. When most requests are harmless reads, reviewers learn to approve without reading, and the one irreversible action that mattered goes through on habit. A gate that fires constantly is no longer a gate.

## Gates that hold for irreversible actions

**Review the artifact, not a summary.** The person approving should see the exact email body, the exact payment amount and recipient, the exact diff. A summary written by the same agent that wants to act is the weakest possible evidence.

**Stage by scope.** Failures in agents are rarely spread evenly; they cluster around a customer, a language, a kind of request. Widening an irreversible capability one scope at a time, a single account or team first, exposes that kind of failure while it is still small.

**Build the compensation first.** If an action can have a correction path, write it before the action exists. If it cannot, the action is not a candidate for autonomy.

**Deny by default for unattended runs.** A scheduled job has nobody to ask. Anything that would need a human's yes should fail closed there, with an error that says why, instead of silently proceeding.

**Keep the record.** When something goes wrong, the first questions are what the agent did, in what order, with what input. If that record does not exist, the incident becomes guesswork.

## What alpi does today, and where it stops

alpi applies these ideas where it can enforce them, and it is worth being precise about where that is.

- **Shell commands are classified before they run.** Every `terminal` command is sorted into safe, caution or dangerous. Safe commands run. Caution commands, such as recursive deletes, force pushes, `git reset --hard` or SQL `DROP`, pause for approval in an interactive session and are refused automatically on unattended surfaces. Dangerous commands are always blocked, with no configuration switch to re-enable them.
- **Every approval decision is logged.** Caution and dangerous decisions go to the profile's `approval.log`, and every turn leaves a run journal with its tool calls and outcome, so "what did it do" has an answer.
- **Capabilities are removed per agent, not trusted.** `tools.deny` takes a tool away from a profile entirely. An agent that only writes documents does not need a shell, so it does not get one.
- **Spend is capped.** Each profile has a `budget.daily_usd` limit checked on every turn, so a runaway loop ends at a number you chose rather than at the invoice.
- **Tool output is data, not instructions.** Results from web pages, email and other tools reach the model wrapped as untrusted data, which narrows the path from an injected instruction to an action.

The honest limit: alpi does not yet label every tool by reversibility. The command classifier covers the shell; for other tools the controls are coarser. You can deny the tool for that agent, or keep it behind a skill whose contract requires an explicit instruction before anything is sent. That is enough to keep irreversible actions out of unattended runs, but it is not the per-action, artifact-level review described above, and it would be misleading to call it that.

## The takeaway

Stop treating revert as your recovery plan for agents. Recovery for an agent is designed in before the action: classify what it can do, let reads and compensable writes flow with a log, and put irreversible actions behind a human who sees the exact artifact, or out of the agent's reach entirely.

If you want to see where your own agents stand, list every tool they can call and write next to each one how you would undo it. The tools where that line is blank are where the gates go.

```
uv tool install alpi-agent
```
