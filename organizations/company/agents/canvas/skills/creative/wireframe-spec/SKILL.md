---
name: wireframe-spec
description: Produce a text-based wireframe specification that engineering can implement without ambiguity
category: creative
version: 0.1.0
origin: user
requires_env: []
tools: [write_file]
keywords: [wireframe, spec, ui, interface, layout]
created_at: 2026-05-05
---

## When to use
When a new screen, modal, or flow needs to be designed before visual work begins, or when a handoff to engineering requires a precise interface spec. Also use when reviewing an existing design to check for missing states and undefined behavior.

## Output format

**Screen / component name** — unique identifier used throughout the spec.

**User goal** — what the user is trying to accomplish on this screen. One sentence. If unclear, stop — the design cannot be good without this.

**Layout description** — describe the structure in hierarchical prose or ASCII layout. Include:
- Primary regions (header, body, sidebar, footer)
- Content hierarchy within each region
- Relative sizing or proportion cues where they affect meaning

**Components** — for each interactive or meaningful element:
- Name
- Type: button / input / dropdown / toggle / link / label / etc.
- State: default / hover / active / disabled / loading / error / empty
- Behavior: what happens when interacted with
- Copy: the exact text, not a placeholder

**States to design**
- Empty state: what does the user see with no data?
- Error state: what does the user see when something fails?
- Loading state: is there any async operation?
- Overflow: what happens with very long content?

**Navigation** — where does the user come from and where can they go?

**Open questions** — design decisions not yet made. Do not leave these implicit.

## Approach
- Specify behavior, not appearance. Color and spacing are for the visual design phase. This spec describes what is there and what it does.
- Empty state is a first-class design problem, not an afterthought. It is often the first thing a new user sees.
- Copy is part of the design. Placeholder text like "Click here" in a spec is not a spec — it is deferred design work.
- Open questions section is mandatory. Design specs with no open questions usually have hidden ambiguity.
