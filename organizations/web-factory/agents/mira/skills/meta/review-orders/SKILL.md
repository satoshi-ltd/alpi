---
name: review-orders
description: Process a human review work order (REV-*) into per-owner fix tasks, verify closure note by note, and re-run the gates.
category: meta
version: 1.0.0
origin: user
requires_env: []
tools: [read_file, write_file, search, terminal, workgroup_post]
keywords: ['review', 'work-order', 'feedback', 'triage', 'REV']
created_at: 2026-07-25
---

# Review work orders

A review work order is a human-authored markdown document produced by the
template's draft preview tools: requests keyed by stable note ids
(`REV-<REF>-NN`), grouped by page, optionally closing with an
`## Approved appearance configuration` JSON block. It arrives as a `#review`
task either INLINE (the full document pasted in the post) or as a reference
to an existing `work/review/REV-*.md` file. Treat it as a reduced briefing.

## Step 1 — materialize, always first

Inline document → write it VERBATIM to `work/review/<review-id>.md` before
anything else. Referenced file → verify it exists on disk. The file is
immutable input, like `brief.md`: never edit, renumber, or reword it. Every
later task cites the file plus note ids — never re-paste the document into a
task (task text is re-injected into every member turn; the file is read once
by whoever needs it).

## Step 2 — triage every note to exactly one owner

| Signal | Owner |
|---|---|
| `Source:` under `src/content/**`, or copy/order/structure requests on entries and pages | quill |
| `(only this locale)` on a non-source locale, or translation quality | lingua |
| `Source:` under `assets/manifest.yaml`, or image/media requests | muse |
| `## Approved appearance configuration` block, or site.json-level requests (nav, sections, theme, booking) | scout |
| Requests that need runtime edits (`src/i18n/*`, components, styles, scripts) — e.g. chrome labels with no `Source:` | NOBODY — out of boundary |

Only id + URL + the request text are guaranteed per note; missing optional
fields (Locale, Node, Source, Current) never block triage — locate the target
by searching the quoted `Current:` text in the content files of the URL's
page. Out-of-boundary notes are NEVER fixed by members: collect them for the
template-gap section of your closing report.

## Step 3 — dispatch in this order, thin tasks only

1. scout — apply the appearance JSON verbatim onto `src/config/site.json`
   (schema-legal keys only) plus config-level notes; gate `check:config`.
2. quill — source-locale content notes; gate `check:content`.
3. lingua — locale-specific notes + parity for whatever quill changed; gate
   `check:content:all`.
4. muse — manifest/media notes; gate `assets:optimize`.
5. pixel — rebuild; gate `check:dist`.
6. lens — re-audit the touched pages; one QA verdict.

One task per owner, skip empty stages:
`@<owner> #task #review-fix <review-id> · notes <ids> · work/review/<review-id>.md`.
Owners apply ONLY their notes. A failed gate follows the standard rule: the
phase re-opens with a fresh task; it is never advanced red.

## Step 4 — close note by note

The closing `#done` lists EVERY note id with exactly one outcome:

- `applied` — what changed, one line;
- `rejected` — why: conflicts with `brief.md` facts, the schema, or an
  explicit client choice (the brief always wins over the work order);
- `template-gap` — out of boundary, reported for the template maintainers.

A note silently dropped is a failure of this protocol.
