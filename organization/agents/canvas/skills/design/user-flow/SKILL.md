---
name: user-flow
description: Map a user flow as a sequence of screens, decisions, and outcomes — including unhappy paths
category: design
version: 0.1.0
origin: user
requires_env: []
tools: [write_file]
keywords: [user flow, ux, journey, navigation, flow]
created_at: 2026-05-05
---

## When to use
When designing or auditing a multi-step user interaction — onboarding, checkout, settings change, or any flow that involves more than two screens. Also use when engineering asks "what happens if the user does X in the middle of the flow?"

## Output format

**Flow name** — what this flow accomplishes.

**Entry points** — all the places a user can start this flow. Flows with multiple entry points often have inconsistent behavior; list them explicitly.

**Happy path** — the primary sequence:

```
[Screen A] → user action → [Screen B] → user action → [Outcome]
```

Each step includes:
- Screen name
- What the user sees
- What action moves them forward
- What data is captured or changed

**Branch points** — decisions where the flow diverges:

```
[Decision point]
  ├─ Condition A → [Screen X]
  └─ Condition B → [Screen Y]
```

**Unhappy paths** — at minimum, cover:
- User cancels or navigates away mid-flow: what state is left?
- Input validation fails: where is the user returned?
- System error mid-flow: what is recoverable vs. must restart?
- Session expires mid-flow: where does the user land after re-auth?

**Exit points** — all the places the flow can end, with the resulting system state.

**Open questions** — decision points where product has not yet determined the correct behavior.

## Approach
- Map the unhappy paths before the happy path. The happy path is usually obvious; the unhappy paths reveal the real design work.
- Every branch must have an exit. Flows that loop or dead-end are bugs, not design choices.
- State at cancellation is frequently undefined in specs. If the user abandons a multi-step form, is progress saved? This is a product decision that must be explicit.
- Entry points determine context. A user entering from an email invite has different state than one entering from the dashboard. The flow must handle both.
