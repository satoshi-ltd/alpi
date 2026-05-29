---
name: edge-case-enum
description: Enumerate edge cases for a function, feature, or flow systematically across input, state, and environment dimensions
category: software
version: 0.1.0
origin: user
requires_env: []
tools: [read_file, search]
keywords: ['edge-cases', 'boundary', 'qa', 'adversarial', 'inputs']
created_at: 2026-05-05
---

## When to use
When writing tests for a non-trivial function, when reviewing a PR for missed failure modes, or when a feature is about to ship and the question is "what could go wrong?" Also use when a category of bugs has recurred and the team needs a systematic enumeration to close the gap.

## Output format

**Subject** — the function, feature, or flow being enumerated.

**Input edges** — all non-happy-path inputs:
- Empty / null / undefined
- Zero, negative, maximum value (for numeric inputs)
- Maximum length, special characters, Unicode (for string inputs)
- Invalid types or formats
- Boundary values (one below minimum, at minimum, at maximum, one above maximum)

**State edges** — system states that could affect behavior:
- Uninitialized or partially initialized objects
- Concurrent modification (if relevant)
- Expired sessions, tokens, or cache
- Missing or deleted related records
- Network unavailability or timeout for any external call

**Permission and auth edges**
- Unauthenticated access
- Insufficient permissions
- Acting on another user's data

**Environmental edges**
- Database at capacity or returning slow
- Time-dependent behavior (timezone edge, daylight saving, leap year, end of month)
- Feature flags in unexpected states

**Severity classification** for each edge case:
- P0: causes data loss, security breach, or silent wrong result
- P1: causes visible failure or degraded behavior
- P2: cosmetic or low-frequency

## Approach
- Enumerate before you evaluate. List all cases first, then assign severity. Evaluating as you go causes early pruning of cases that turn out to be P0.
- "Edge case" does not mean rare. Users with empty profile fields, zero balances, or no timezone set are common. These are not edge cases; they are segments.
- Silent wrong results are more dangerous than thrown exceptions. An exception fails loudly; a wrong result ships.
- Enumerate permission edges for every feature that touches user data, not just auth flows.
