---
name: doc-curator
description: Audit a documentation set for accuracy, gaps, and staleness — and produce a curation plan with clear ownership
category: research
version: 0.1.0
origin: user
requires_env: []
tools: [read_file, search, write_file, edit_file, db]
keywords: [documentation, curation, knowledge-base, audit, maintenance]
created_at: 2026-05-05
---

## When to use
When the team is relying on documentation that hasn't been reviewed in more than 6 months, when a new team member reports that existing docs are confusing or incorrect, or when the documentation set has grown without governance and no one knows what's current.

## Output format

**Scope** — what collection of documents is being curated (product docs, internal wiki, runbooks, onboarding guides, API docs).

**Inventory**

| Document | Last updated | Owner | Status | Action |
|---|---|---|---|---|
| [Title] | [Date] | [Person/team] | Current / Stale / Conflicting / Orphaned | Keep / Update / Archive / Delete |

Status definitions:
- Current: accurate and actively maintained
- Stale: content was correct but has not been reviewed against recent changes
- Conflicting: contradicts another document in the set
- Orphaned: no owner, no last-update date, unclear if still relevant

**Critical gaps** — important topics or procedures that have no documentation:
- [Topic]: [why it matters, who needs it, who should write it]

**Conflicting documents** — pairs of documents that contradict each other:
- [Doc A] vs. [Doc B]: [what they say differently and which is likely correct]

**Curation plan**

| Action | Document(s) | Owner | Deadline |
|---|---|---|---|
| Update | | | |
| Archive | | | |
| Delete | | | |
| Create | | | |

**Governance recommendation** — how should this documentation set be maintained to prevent the same decay? (Review cadence, ownership model, trigger for review when related product changes.)

## Approach
- Wrong documentation is worse than no documentation. It creates false confidence and produces errors. Archiving and deleting are legitimate curation actions.
- "Orphaned" means no owner. No owner means it will not be maintained. Assign an owner or archive it.
- Conflicting documents are an organizational signal: the process that should have updated one document when the other changed doesn't exist. Fix the process, not just the documents.
- A curation plan without deadlines and owners is an aspiration. Documentation debt compounds; it does not resolve itself.
- The governance recommendation is the most important output. A one-time audit that doesn't produce a maintenance model will need to be repeated in 12 months.

## State
The doc inventory IS the curation surface — a queryable list of every doc with ownership and freshness.

Tables live under `state/db.sqlite` (per-skill). Schema is additive-only — `CREATE TABLE IF NOT EXISTS`, never `ALTER` destructively or `DROP`.

```sql
CREATE TABLE IF NOT EXISTS docs (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    path            TEXT NOT NULL UNIQUE,
    title           TEXT NOT NULL,
    owner           TEXT,
    last_reviewed   TEXT,
    staleness_flag  TEXT,                        -- fresh / aging / stale / abandoned
    action          TEXT,                        -- update / merge / retire / leave
    audit_date      TEXT NOT NULL
)
```

Run audits periodically: `WHERE last_reviewed < date('now', '-180 days') OR last_reviewed IS NULL` flags candidates. Update `action` and `staleness_flag` per audit. Retired docs stay in the table — what was retired is itself useful information.
