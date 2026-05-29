---
name: test-plan
description: Write a test plan for a feature — scope, test types, environment requirements, and acceptance criteria
category: software
version: 0.1.0
origin: user
requires_env: []
tools: [write_file]
keywords: ['test-plan', 'qa', 'acceptance', 'feature-testing', 'regression']
created_at: 2026-05-05
---

## When to use
When a feature is about to enter testing or has been handed off from engineering. Also use when reviewing whether a shipped feature was adequately tested, or when deciding how much testing is enough before a release.

## Output format

**Feature under test** — name and one-sentence description of what it does.

**Scope**
- In scope: what this plan covers
- Out of scope: what is explicitly excluded (with reason)

**Acceptance criteria** — the conditions that must be true for this feature to be considered working. Each criterion must be binary (pass/fail), not subjective.

**Test cases**

| ID | Scenario | Input / Precondition | Expected result | Test type | Priority |
|---|---|---|---|---|---|

Test type: unit / integration / manual / e2e  
Priority: P0 (blocking) / P1 (high) / P2 (nice to have)

**Edge cases** — inputs or states outside the happy path that must be explicitly tested. (See the edge-case-enum skill for a fuller enumeration.)

**Environment requirements**
- Data: [specific fixtures, seed data, or account states required]
- Config: [feature flags, environment variables, service dependencies]
- External dependencies: [third-party APIs — use real / stub / mock?]

**Regression risk** — which existing features could break because of this change?

**Exit criteria** — what must be true before testing is declared complete and the feature is approved for release?

## Approach
- Acceptance criteria are not test cases. Acceptance criteria define done; test cases verify specific behaviors that prove done.
- P0 test cases are not optional, even under schedule pressure. If a P0 can be skipped, it wasn't P0.
- Environment requirements are often the reason test plans fail. Specify them before testing starts, not during.
- Regression risk should reference real past failures when available. "Could affect checkout" is worse than "the last checkout regression was caused by a similar change in the payment module."
- A test plan with no scope exclusions is a test plan that will never finish.
