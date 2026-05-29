---
name: strategic-memo
description: Write a structured strategy memo with decision, rationale, tradeoffs, and what we are not doing
category: productivity
version: 0.1.0
origin: user
requires_env: []
tools: [write_file, read_file]
keywords: [strategy, memo, decision, tradeoff, direction]
created_at: 2026-05-05
---

## When to use
When a strategic direction needs to be committed to writing — for a Council discussion, a quarterly pivot, a go/no-go call, or any decision that other agents will execute against. Also use when asked to summarise a workgroup discussion into a clear directive.

## Output format

**Decision** — one sentence. What we will do.

**Why now** — two to three sentences. The external or internal condition that makes this the right moment. If the answer is "because it feels right", the decision is not ready.

**Tradeoff** — explicit. What we give up by making this choice. If there is no tradeoff, it is not a strategy.

**What we are not doing** — bullet list. At least two items. The most tempting alternatives we are explicitly setting aside.

**Success looks like** — one to two sentences. A concrete, observable condition within a defined time window.

**Kill criterion** — one sentence. The signal that tells us we were wrong and need to reverse.

## Approach
- State the decision first, context second. Executives read the first line and skim the rest.
- Surface the tradeoff before defending the choice. Hiding the cost of a decision is not strategy, it is advocacy.
- Keep it under 300 words. If it requires more, the decision is not clear yet.
- Do not hedge with "it depends" — that belongs in a risk memo, not a strategic directive.
- Never write "we will try to" or "we hope to". Commit or don't.

## State
Append a one-line summary to `state/memos.jsonl` after every memo. Volume is low (≈10/year), so a flat append-only log beats a database — `grep` and `tail` are enough.

Each line is a JSON object:
```json
{"date":"2026-05-12","title":"Q3 focus","audience":"council","recommendation":"freeze net-new features for 8 weeks","status":"sent","superseded_by":null}
```

To append: read the file, add the new line, write it back. To find prior strategy on a topic: `grep` the JSONL by audience or recommendation keyword. When a memo overrides an old one, set the previous entry's `superseded_by` to the new title.
