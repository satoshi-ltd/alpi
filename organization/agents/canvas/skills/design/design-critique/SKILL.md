---
name: design-critique
description: Critique a design against usability, consistency, and user goal criteria — separating problems from opinions
category: design
version: 0.1.0
origin: user
requires_env: []
tools: [read_file, read_image]
keywords: [design critique, ux review, usability, feedback, review]
created_at: 2026-05-05
---

## When to use
When reviewing a design before it moves to implementation, when evaluating a shipped feature against user goals, or when a design has received unclear or conflicting feedback and needs structured critique.

## Output format

**Design under review** — name and what user goal it serves.

**Usability issues** — problems where users are likely to fail, be confused, or take longer than necessary:
- Describe the issue precisely
- State which user segment is most affected
- Severity: blocking (users can't complete the goal) / degrading (users complete with friction) / minor (polish)

**Consistency issues** — deviations from the design system or existing patterns that create cognitive overhead:
- What the deviation is
- What the consistent pattern is
- Whether the deviation is intentional (call it out as a decision) or an oversight

**Alignment with user goal** — does the design help the user accomplish what they came to do?
- Is the primary action the most prominent element?
- Does the information hierarchy match the decision order?
- Is there content that distracts from the user goal?

**What works** — at least two specific design decisions that are correct and should be carried forward. Critique without acknowledgment of what works produces defensive designers.

**Recommendation** — one sentence: ready to implement / revise and re-review / needs user testing before proceeding.

## Approach
- "I don't like it" is not a critique. "Users will not see the primary action because it has the same visual weight as the secondary action" is.
- Distinguish personal preference from design problems. Preference is valid but should be labeled as such: "this is my preference, not a user problem."
- Design critique is about the user's experience, not the designer's intention. What the designer meant to communicate is irrelevant if the user reads it differently.
- "Make it pop" is the most common form of content-free design feedback. Don't give it; push back on it when received.
