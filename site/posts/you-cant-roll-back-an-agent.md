---
title: You can't roll back an agent
date: 2026-08-20
description: Rollback restores code, not state. A morning of Claude Code and OpenCode debugging showed why the recovery primitive for a stateful agent is different from the one for a service.
tags: [agents, infrastructure, reliability]
---

I spent the morning debugging agent sessions in Claude Code and OpenCode, and the same lesson kept surfacing in different clothes. Both tools give you rollback, and in both cases rollback is the wrong mental model for what actually went wrong.

The concrete version first. An agent session had accumulated a working state: a checked-out worktree, a long conversation history, a set of files it had edited, a plan it was midway through executing. Something downstream broke. The instinct — the DevOps instinct, the one CI/CD drilled into all of us — was to roll back to the last good revision and try again.

That works for a service. A service is stateless by construction. Its state lives outside it, in a database or a queue, and redeploying an old image is a clean operation because you are replacing the code and nothing else. The database didn't get un-updated; the schema didn't quietly drift backward; nothing external mutated while you weren't looking.

An agent is the opposite. The agent *is* the state.

When you roll back the code, you don't roll back the conversation. The context window still holds the failed plan, the half-finished edits, the tool outputs from a world that no longer exists. You have reinstalled the interpreter and left the program in memory. The next thing the agent does is try to reconcile a history that describes one world with a filesystem that now describes another.

This is where it goes wrong quietly, and this is the part worth writing down, because it is not obvious from the outside.

## The reconciliation is where the damage happens

Give a model a stale plan and a fresh filesystem and it does the reasonable thing: it tries to make them agree. It re-applies the edits that were evidently intended. It re-runs the commands whose effects are visibly missing. It is not malfunctioning. It is being *helpful*, in exactly the way you want it to be helpful, against a premise that is now false.

The failure is not the model being dumb. The failure is that the model has no way to know it has been transported. Nothing in the transcript says "the world changed underneath you." So it infers the only explanation consistent with its training: the work simply wasn't done yet.

I have now watched this happen with file edits that got re-applied on top of already-edited files, producing duplicated blocks. With commands re-run against a service that had already been acted upon once. With plans that had been superseded being resumed as if they were still live.

## What actually works

The recovery primitive is not revert-with-state-preserved. It is one of two things, and you have to pick deliberately:

- **Discard the session.** Start clean, with the current filesystem as the new ground truth, and re-state the goal in fresh words. You lose the accumulated context, which is the point — that context is the contaminated artifact.
- **Snapshot the session.** Capture the full state — history, files, plan, tool results — and resume *from* the snapshot, so the model's world model and the world move together. The snapshot is not a rollback target. It is a checkpoint you always resume from, never rewind to.

The reason the first is often the right call and not a cop-out: the transcript's value degrades once the premise is false. A long history that describes a world that no longer exists is worse than no history. It is a source of confident, well-formed, wrong actions.

## The general shape

Stateless systems can be rolled back because state and code are separable. Stateful systems can't be, because there is no state-free position to roll back to. The moment your system accumulates context that affects its future behavior, the recovery primitive changes from *revert* to *fork* or *discard* — never rewind-in-place.

The practical rule I keep arriving at: before you hit rollback, ask what survives it. If the answer is "the state that made this go wrong," rollback will re-create the failure, sometimes faster, because now the agent has a plan it believes in.

That last sentence is the one that cost me the morning. The second attempt is not a retry. It is the first attempt, plus a story about why it deserves to happen.
