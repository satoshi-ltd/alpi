---
name: code-review
description: Produce a structured code review that separates blockers from suggestions and explains the why behind each
category: software
version: 0.1.0
origin: user
requires_env: []
tools: [read_file, search]
keywords: ['code-review', 'pr', 'pull-request', 'quality', 'feedback']
created_at: 2026-05-05
---

## When to use
When reviewing a pull request or a code diff before merge. Also use when asked to audit a specific module or function for correctness, readability, or maintainability. Do not use for architectural reviews — use the ADR format for those.

## Output format

**What this change does** — one sentence. If you can't state it clearly, the PR description needs work before review continues.

**Blockers** — changes that must be addressed before merge. Each entry must include:
- File and line reference
- What the problem is
- Why it matters (not just "bad practice")
- A concrete fix or alternative

**Suggestions** — improvements worth considering but not blocking. Label each as: readability / performance / maintainability / test coverage.

**Questions** — things that need clarification from the author. Not objections — genuine unknowns.

**What's good** — at least one specific thing done well. Omitting this makes reviews feel adversarial and obscures what patterns to repeat.

**Overall verdict** — Approve / Approve with minor fixes / Request changes. One sentence explaining the verdict.

## Approach
- Read the test changes before the implementation changes. Tests reveal intent. Implementation without a test that covers the new behavior is a blocker.
- Separate what the code does from what it should do. "This is confusing" is a suggestion. "This will throw a null pointer exception when X" is a blocker.
- Be specific about the why. "This is a code smell" is not a review comment. "This coupling means any change to Y requires editing this file, which has caused bugs before" is.
- Flag missing error handling at system boundaries (external APIs, user input, database calls). These are blockers, not suggestions.
- One nit about naming is enough. Don't fill a review with style comments when there are real issues — it signals the reviewer didn't prioritize.
