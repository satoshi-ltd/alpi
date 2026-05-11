---
name: knowledge-recall
description: Answer a question about org knowledge by consulting workspace + decisions DB + memory + past sessions, synthesizing the best answer with citations and surfacing conflicts
category: knowledge
version: 0.1.0
origin: user
requires_env: []
tools: [search_workspace, read_file, db, memory, session_search]
keywords: [recall, knowledge, query, lookup, synthesis, citations]
created_at: 2026-05-11
---

## Scope

This is the canonical recall skill for the org. When another agent
reaches Archive — via `link.ask`, by `@archive` in a workgroup, or
because a human typed something to the Archive profile — this is the
skill that produces the answer.

**Use this skill** when:
- A peer agent asks "what do we know about X" / "what did we decide on
  Y" / "who owns Z".
- A human asks Archive a recall question.
- A workgroup needs prior context to avoid relitigating a closed
  decision.

**Do NOT use this for** writing new knowledge. Capture skills handle
that (`decision-capture`, `post-mortem`, `doc-curator`). This skill is
read-only over the org's existing record.

## When to use

Whenever Archive is asked something it can answer from the four layers
it owns:

1. `workspace` — canonical company documents (PDFs, markdowns, contracts,
   meeting notes, scanned docs).
2. `db` — structured records inside Archive's own skill tables
   (`decisions`, `post_mortems`, `doc_audits`).
3. `memory` — org invariants in `USER.md` / `MEMORY.md` / `AGENT.md`.
4. `session_search` — past conversations Archive has had with peers.

## Approach

Consult in order. Stop as soon as you have a confident answer, but
never silently. The order matters because the layers have different
trust profiles:

- **Workspace** is the broadest — the raw artifacts the org has actually
  produced. Start here. A snippet from a real document beats a memory of
  what someone said about that document.
- **DB** is canonical for decisions and process. If workspace and DB
  agree, you have high confidence. If only DB has the fact, that's
  still strong — every entry was the closure of a `#done`.
- **Memory** holds invariants the org has explicitly taught Archive
  (e.g. "Vera has final say on strategy"). Short, hand-curated.
- **Sessions** are the long tail. Use only if 1-3 miss.

When two sources disagree, do not pick a winner silently. Quote both.
The asker decides what to trust. This is the single most important
rule of this skill — Archive's value is honesty about the record, not
confidence in synthesis.

## Output format

A single synthesized paragraph (or short structured answer if the
question demands one), **always with citations**:

- File path + line range when citing from workspace (e.g.
  `~/Documents/company-archive/policies/remote-work-v3.md:42-58`).
- Decision id when citing from the DB (`decision #42 (architecture,
  2026-02-15)`).
- Memory entry tag when citing from memory.
- Session id + turn when citing from sessions.

If sources conflict, structure as:

> **Workspace says** (handbook.pdf:p4): "remote work permitted up to
> 4 days/week".
> **DB says** (decision #18, growth, 2026-03-01): "remote work capped
> at 3 days/week".
> Both are dated; the handbook is older. The DB decision is the
> binding record. The handbook should be updated.

If Archive genuinely doesn't know, say so plainly:

> "Nothing in workspace, DB, or memory mentions Q3 hiring targets. The
> last hiring-related decision is #29 (Q2 plan). Suggest asking Vera or
> Ledger directly."

## State

This skill has no DB of its own — it reads from sibling skills'
state (`decisions`, `post_mortems`, `doc_audits`) and from Archive's
workspace, memory, and sessions. No writes.

## When NOT to use

- For capturing new decisions → use `decision-capture`.
- For writing a post-mortem → use `post-mortem`.
- For auditing the docs themselves → use `doc-curator`.
- For pure web lookups unrelated to the org → that's `atlas` (market
  intel), not Archive.
