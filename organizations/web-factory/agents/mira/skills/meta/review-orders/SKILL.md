---
name: review-orders
description: Materialize a human review work order (REV-*), triage every note to one declared review phase, and close note by note once the chain has run.
category: meta
version: 2.0.0
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
`## Approved appearance configuration` JSON block. Treat it as a reduced
briefing.

The `review` pipeline is declared in the recipe and the daemon sequences it:

```
review @mira → review-config @scout → review-content @quill →
review-translation @lingua → review-media @muse → review-build @pixel →
review-qa @lens → review-close @mira
```

Start it with `alpi -p mira workgroup trigger <wg_id> review` (or the Run
action in the app). The opener is the recipe's, not yours. Do not re-derive
this order in a post and never fan out `#review-fix` tasks — the phases ARE
the fan-out, and a phase with nothing to do closes as `skipped`.

## Phase `review` — materialize, always first

An inline document → write it VERBATIM to `work/review/<review-id>.md` before
anything else. VERBATIM is a COPY operation, not a retelling: reproduce the
source text character by character, from `# Review work order` to the last
line. You are NOT allowed to rewrite a note's request from your own analysis
of the project — a note you "improved" is a fabricated client request, the
worst failure of this protocol. Before triaging, re-read the file you wrote
and compare each note id's request against the source; any mismatch means you
rewrite the file, not the notes. A referenced file → verify it exists on disk.
The file is immutable input, like `brief.md`: never edit, renumber, or reword
it.

Then post your triage: for each note id, the phase that owns it. Cite the file
plus note ids and never re-paste the document into a task or a triage post —
that text is re-injected into every member turn, while the file is read once by
whoever needs it. Close with `#done review triaged · <n> notes → <phases>`. The
daemon opens `review-config` next.

Only id + URL + the request text are guaranteed per note; missing optional
fields (Locale, Node, Source, Current) never block triage — locate the target
by searching the quoted `Current:` text in the content files of the URL's
page.

## Triage: every note to exactly one phase

| Signal | Phase |
|---|---|
| `## Approved appearance configuration` block, or site.json-level requests (nav, sections, theme, booking) | `review-config` |
| `Source:` under `src/content/**`, or copy/order/structure requests on entries and pages | `review-content` |
| `(only this locale)` on a non-source locale, or translation quality | `review-translation` |
| `Source:` under `assets/manifest.yaml`, or image/media requests | `review-media` |
| Requests that need runtime edits (`src/i18n/*`, components, styles, scripts) — e.g. chrome labels with no `Source:` | NOBODY — out of boundary |

Out-of-boundary notes are NEVER fixed by members: carry them to
`review-close` as `template-gap`.

## The fix phases

Each owner reads `work/review/<review-id>.md`, applies ONLY the notes triaged
to their phase, and hands off. `review-translation` also restores parity for
whatever `review-content` changed. An empty category is closed explicitly with
`#done skipped · no <category> notes in <review-id>` — the phase stays in the
chain, it does not disappear. A failed gate re-opens the SAME phase with a
fresh task; it is never advanced red.

## Phase `review-close` — close note by note

The closing `#done` lists EVERY note id with exactly one outcome:

- `applied` — what changed, one line;
- `rejected` — why: conflicts with `brief.md` facts, the schema, or an
  explicit client choice (the brief always wins over the work order);
- `template-gap` — out of boundary, reported for the template maintainers.

A note silently dropped is a failure of this protocol.
