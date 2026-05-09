---
name: copy-editor
description: Edit a piece of writing for clarity, brevity, and precision — with tracked changes and explanation of each cut
category: writing
version: 0.1.0
origin: user
requires_env: []
tools: [read_file, edit_file]
keywords: [editing, copy, clarity, brevity, proofreading]
created_at: 2026-05-05
---

## When to use
When a piece of writing needs to be tighter, clearer, or more precise before publication. Also use when content has been drafted quickly and needs a pass before it goes to a broad audience. Works on landing page copy, email body, blog posts, documentation, and internal memos.

## Output format

**Piece type and audience** — what this is and who reads it.

**Edited version** — the full edited text. Do not show tracked changes inline — produce a clean version first.

**Changes explained** — a list of the most significant edits, grouped by type:

*Cut* — what was removed and why (redundant / padding / obvious / changed meaning)  
*Rewritten* — what was restructured and what problem it solved (clarity / passive voice / buried lead / wrong register)  
*Preserved* — anything that might look like a mistake but was kept intentionally, and why

**Readability check**
- Average sentence length (target: under 20 words for consumer copy; can be longer for technical)
- Passive voice instances remaining (if any, are they intentional?)
- Jargon or corporate-speak flagged: [list any remaining or explain why it was kept]

**One thing that still needs work** — the single most impactful remaining issue, if any.

## Approach
- Cut adjectives by default; keep verbs. "Quickly delivers powerful results" → "delivers results."
- The lead buries itself most often in second and third paragraphs. Move the most important sentence first.
- Passive voice is not always wrong. "The server was breached" is correct when the actor is unknown. "The button should be clicked by the user" is not.
- Don't edit for length — edit for clarity. Sometimes the right edit makes a piece longer by adding a missing sentence that makes everything else make sense.
- Preserve the writer's voice; remove their noise. These are different things.
