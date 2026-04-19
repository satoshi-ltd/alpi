---
name: consolidate-memory
description: Merge duplicates and prune obsolete entries in USER.md and MEMORY.md when they approach their char limit.
category: meta
version: 0.1.0
requires_env: []
tools: [read_file, write_file]
created_at: 2026-04-18
---

# Consolidate memory

Trigger this when `USER.md` or `MEMORY.md` reports ≥80% usage or when you
hit a write-rejection because the file is full.

## Procedure

1. Read both `~/.alf/memories/USER.md` and `~/.alf/memories/MEMORY.md`.
2. For each file, walk the entries (split by `§`) and:
   - **Merge** entries that state the same fact in different words into one
     canonical entry.
   - **Drop** entries that are stale (contradict a newer one, refer to a
     project/tool the user no longer uses).
   - **Tighten** wording — remove hedges, repetition, timestamps that aren't
     load-bearing.
3. Keep the structure: one entry per distinct fact, separated by `§`.
4. Preserve the *why* when a memory records a rule — don't strip the reason
   the user gave, because that's what lets future-you judge edge cases.
5. Write the cleaned file back. Verify the new total is under the limit
   (1,375 chars for USER.md, 2,200 for MEMORY.md) and leave ≥20% headroom
   if possible.
6. Report what was merged, what was dropped, and the final char usage.

## Do not

- Invent facts that weren't in the original file.
- Drop anything that looks like explicit user feedback ("don't do X") even
  if it sounds minor — those rules are the highest-signal memories.
- Mix USER.md and MEMORY.md content. They're separate on purpose.
