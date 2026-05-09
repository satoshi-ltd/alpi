---
name: knowledge-base
description: Write or update a knowledge base article that prevents a recurring ticket by answering the question before it's asked
category: support
version: 0.1.0
origin: user
requires_env: []
tools: [read_file, search, write_file, edit_file]
keywords: [knowledge base, documentation, faq, self-service, help center]
created_at: 2026-05-05
---

## When to use
When the same question has been answered in tickets more than twice, when a new feature ships without support documentation, or when an existing article is out of date and generating re-opens. Also use to audit a knowledge base for coverage gaps against common ticket topics.

## Output format

**Article title** — written as the question the user is asking, not the feature name. "How do I reset my password?" not "Password Management." Users search with questions.

**When this applies** — the specific scenario or condition this article covers. Be precise: an article that's ambiguous about when it applies gets the wrong customers to the wrong answer.

**Solution** — step-by-step, numbered:
1. [Exact action, not description of action]
2. ...

Include screenshots or callouts for UI-specific steps where possible.

**If the solution doesn't work** — one or two specific troubleshooting steps before "contact support."

**Related articles** — two or three links to adjacent topics the reader may need next.

**Metadata** (for internal use)
- Product area
- Last verified: [date]
- Ticket volume this article targets: [low / medium / high]
- Linked from in-product? [yes / no]

## Approach
- The title is a search query. Write it as users would search for it, not as an internal team would label it.
- Step-by-step means step-by-step. "Navigate to the settings page" is insufficient. "Click your profile icon → Settings → Security" is a step.
- Every article needs a "if this doesn't work" section. An article that ends with the happy path and no fallback sends customers back to ticket queue.
- Outdated articles are worse than no articles. They create false confidence and generate tickets when the instructions don't match the current UI. Set a review cadence.
- Articles should be linked from inside the product at the moment of friction, not just findable in a help center.
