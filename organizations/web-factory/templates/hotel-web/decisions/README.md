# Template ADRs

Architecture Decision Records for the master template, owned by the
`template` workgroup. One file per decision (`NNN-short-title.md`).

Format:

```md
# NNN — Short title

**Date:** YYYY-MM-DD
**Status:** proposed | accepted | superseded by NNN
**Hub:** forge
**Members involved:** canvas, atlas, lingua, lens

## Context
What problem are we solving? What evidence triggered this?

## Decision
What we're changing in the template.

## Alternatives considered
What we rejected, and why.

## Consequences
What this enables, what it breaks, what migrations downstream projects
need (if any).
```

ADRs are append-only. To change a previous decision, write a new ADR
that supersedes it and mark the old one `Status: superseded by NNN`.
