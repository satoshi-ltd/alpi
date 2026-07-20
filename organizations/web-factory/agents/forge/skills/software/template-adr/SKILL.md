---
name: template-adr
description: Write an Architecture Decision Record when the master template needs to change. Forge owns the format; the `template` workgroup reviews + approves.
category: software
version: 0.1.0
origin: user
requires_env: []
tools: [read_file, write_file, edit_file]
keywords: ['adr', 'architecture', 'template', 'decision-record', 'change-control']
created_at: 2026-05-29
---

## When to use

When the `template` workgroup proposes a change to the master template that affects any locked invariant. NOT every template edit needs an ADR — only changes that:

- Modify Zod schemas in `src/content/config.ts`
- Change the i18n routing strategy
- Add/remove a top-level `pages/[lang]/` route
- Change `astro.config.mjs` integrations or output mode
- Modify the performance budget thresholds
- Change accessibility floor (raises OK; lowers requires vera signoff via override path)
- Add/remove a hero variant or other locked component contract

Routine edits (bug fix, prose tweak, dependency bump within semver minor) skip the ADR.

## Inputs

- The proposed change with rationale
- Cross-project evidence (≥ 3 projects asked for the same thing → strong signal)
- Affected files / contracts

## Approach

1. **Number the ADR**: scan `decisions/` at the template-checkout root (satoshi-ltd/alpi-mirai-web-factory) for the highest sequence number, increment by 1
2. **Slug from the change**: `<seq>-<kebab-case-summary>.md`
3. **Write the ADR** at `decisions/<seq>-<slug>.md` (template-checkout root) using the format below
4. **Post in `template` wg**: link + 1-line summary asking for review
5. **Status transitions**:
   - `proposed` — under review
   - `accepted` — wg signed off; change merged into template
   - `superseded by <new-adr>` — newer ADR overrides this; keep both files
   - `rejected` — closed without merge; kept for history

## Format

```markdown
# <seq> · <Title>

Status: proposed | accepted | superseded by <seq> | rejected
Date: 2026-MM-DD
Authors: forge, <co-authors from template wg>

## Context

What surfaced this. Which projects asked. Quote the evidence:
- proj-<slug-1> asked for X on <date>
- proj-<slug-2> hit the same in <state>
- The current handle / invariant blocks the request because <reason>

What other approaches were considered:
1. <approach A> — rejected because <reason>
2. <approach B> — rejected because <reason>
3. <chosen approach>

## Decision

Concrete change. Be specific:
- File: `src/content/config.ts`
- Change: add `seasonalBanner: z.optional(...)` to the page schema
- Migration: existing project clones pick up the optional field via a `git pull`/merge of the base repo (or a fresh clone); no breaking change
- Backwards compatibility: yes / no — if no, document the upgrade path

If the change touches multiple files, list each one.

## Consequences

What needs to adapt:
- canvas: ... (new design handle)
- quill: ... (new content field to write)
- lens: ... (new checklist item)

What rolls back if this proves wrong:
- Revert the schema change. Existing projects keep their data (optional fields don't break).

## Open questions

- (if any) — explicit, not hand-waved
```

## Examples of past-fictional ADRs

- `001-add-hero-fullbleed-gallery-variant.md` — when resort starter needed the variant
- `002-tighten-jsonld-room-coverage.md` — when atlas needed `containsPlace` for hotels with > 10 rooms
- `003-add-dark-mode-handle-to-tokens.md` — when canvas wanted per-starter dark variants
- `004-supersede-001-with-broader-hero-system.md` — supersedes the first when a 4-variant system replaces ad-hoc additions

## When NOT to write an ADR

- "We want to fix a typo in the README" — just commit
- "Update Astro from 4.16 to 4.17" — patch dependency, no ADR
- "Per-hotel customisation" — that's tuning within the handle space, not template change
- "Add a new brand starter" — that's brand-library wg's domain, not template (and starters add files, they don't change locked invariants)

## Common failure modes

| Symptom | Cause | Fix |
|---|---|---|
| ADR written for routine change | Over-formalising | Skip; commit directly |
| Context says "Mira asked" with no project list | Insufficient evidence | Wait until ≥ 3 projects converge on the same need |
| Decision says "we'll figure out migration later" | Incomplete spec | Block; migration is part of the decision |
| ADR accepted but not actually applied to template | Drift between record and reality | Re-check accepted ADRs against current code; reconcile |

## Voice

- Past tense for context, present tense for decision
- Quote project slugs and dates — the evidence is the strongest part
- Don't soften the "rejected" path — say WHY each alternative didn't fit
- ADRs are read once and referenced for years — invest in clarity
