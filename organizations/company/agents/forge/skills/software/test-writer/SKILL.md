---
name: test-writer
description: Write tests that verify behavior, not implementation — with clear arrange/act/assert structure and meaningful names
category: software
version: 0.1.0
origin: user
requires_env: []
tools: [read_file, search, write_file, edit_file]
keywords: ['tests', 'unit-test', 'integration-test', 'tdd', 'coverage']
created_at: 2026-05-05
---

## When to use
When adding a new feature, fixing a bug (regression test), or when an existing untested function needs coverage before modification. Also use when asked to review test quality rather than write new tests.

## Output format

**What is being tested** — function, behavior, or user flow. State the unit clearly before writing tests.

**Test cases**

For each test:
- Name: describes the scenario and expected outcome (e.g., `returns_empty_list_when_input_is_null`, not `test_case_1`)
- Arrange: setup — what state, inputs, or mocks are needed
- Act: the single operation under test
- Assert: the specific outcome verified and why it matters

Group by: happy path / edge cases / error conditions.

**Coverage gaps** — behaviors that are not tested by the cases above and why they were excluded (out of scope, too expensive to test, covered by integration tests elsewhere).

**Test type recommendation**
- Unit: pure logic, no I/O dependencies
- Integration: behavior that crosses module or service boundaries
- E2E: user-observable behavior through the full stack

## Approach
- Test behavior, not implementation. A test that breaks when you rename a private method is testing the wrong thing.
- One assertion per test is a goal, not a law. What matters is that a failing test points to exactly one thing that broke.
- The test name is documentation. A reader should understand what was tested and what the expected outcome is without reading the test body.
- Mocks should mock things you don't own (external APIs, databases). Mocking your own code to avoid test difficulty usually means the interface needs fixing.
- A regression test for a bug must include a comment with the condition that caused it. Otherwise the test becomes mysterious when the original context is lost.
