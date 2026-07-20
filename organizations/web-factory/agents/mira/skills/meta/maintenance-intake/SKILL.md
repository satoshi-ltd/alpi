---
name: maintenance-intake
description: Receive a post-launch change request from the hotel, classify it, plan the work, open the right #task in the dormant proj-<slug> workgroup. The entry point for everything that happens to a project after launch.
category: meta
version: 0.1.0
origin: user
requires_env: []
tools: [read_file, write_file, edit_file, workgroup_post]
keywords: ['maintenance', 'change-request', 'post-launch', 'lifecycle', 'scope']
created_at: 2026-05-29
---

## When to use

When the hotel requests something post-launch. Channels (out of factory's control how) could be: email to mira, Slack message, Mirai client portal ticket, escalation from sales. Whatever the channel, the request lands with mira.

Mira applies this skill **before** any agent starts work. The output is a queued `#task` with classification + plan documented.

## Inputs

- The request (verbatim from the hotel)
- `projects/<slug>/status.yaml` (must be `launched` or `maintenance`; if `archived`, this isn't a maintenance request — see below)
- `projects/<slug>/CHANGELOG.md` (recent history; useful for context)
- `projects/<slug>/intake.md` + `src/config/site.json` + `src/content/**` (the hotel's data)

## Approach

### 1. Classify the request

Apply `mira/meta/scope-bend-decision` thinking, but post-launch. Categories:

| Category | Examples | Scope |
|---|---|---|
| **Update** | Price changes, hours change, contact email update, social handle update | Edit the content entry (price/hours) or `site.json` (contact/social) + rebuild. Hours. |
| **Add** | New room, new amenity, new photography for a section | Add the content entry (quill/lingua), drop assets in `assets/`, rebuild. Days. |
| **Locale add** | "We need Italian now" | New target locale. Lingua translates everything. Atlas adds slug map. Pixel rebuilds. Week. |
| **Photography refresh** | "We've done a new shoot, replace the hero" | Pixel reprocesses + wires. Canvas reviews if hero variant needs change. Week. |
| **Rebrand within theme** | "Our new brand colour is teal instead of bronze" | Canvas recommends the `site.json` `tokens` override; scout applies it; lens verifies contrast. Days. |
| **New section** | "We want a journal page" | Turn the page on in `site.json.pages`, quill writes the content, lingua translates, pixel rebuilds, lens audits. Week. |
| **Template-layer tweak** | "Smooth scrolling", "blur behind the header", a hover effect — behaviour/style of the fixed design layer | Never per-project work (no agent may edit components/CSS in a clone). Route to the `template` workgroup: forge lands it in the master template (or declines per the 80/20 rule). If it lands, port the landed base-repo change into `projects/<slug>` via a `git pull`/`merge` of the base repo, then pixel rebuilds and lens spot-checks. Week. |
| **Major redesign** | "We want to switch from boutique to resort theme" | A theme switch is just `site.json.theme` + new content for the theme's sections — but if it's a full re-do, spawn `proj-<slug>-v2`. |
| **Out of scope** | "Can you also handle our PMS?", "Can you build our booking engine?" | Decline; mira routes to sales for a different scope of engagement. |

### 2. Document the request

Open `projects/<slug>/changes/<seq>-<short-slug>.md`. Sequence is per-project (001, 002, ...). Slug is a kebab-case summary.

Template:

```markdown
# <seq> · <Title>

Status: queued | in-progress | shipped | declined | superseded
Received: 2026-MM-DD
Channel: email | portal | sales-escalation
Classification: update | add | locale-add | photography-refresh | rebrand-within-starter | new-section | major-redesign | out-of-scope

## Request

Quote verbatim from the hotel. Don't paraphrase.

> Hi Mira, we'd like to move check-in from 15:00 to 14:00 because a lot of
> our guests arrive earlier by boat...

## Classification rationale

Why this category. One paragraph.

## Plan

What changes, in which files, with which owners. Specific:

- `src/content/pages/location.<src>.json` → update the check-in line (quill)
- the same for every other locale (lingua)
- if the contact phone/email changed instead: `src/config/site.json`
  `contact` (scout)
- pixel rebuilds; the template re-emits the JSON-LD from `site.json`
- Owners: quill (source copy), lingua (locales), pixel (build). scout only
  if the change touches `site.json` (contact / theme / booking).

Effort: ~4 hours across owners.

## Resolution

(Filled when shipped.)

- Date shipped:
- Commit / deploy reference:
- Verified at: <production URL>
- Notes:

## Closure date

(Filled when verified.)
```

### 3. Move state, open task

1. Set `status.yaml.state = maintenance`. Append history entry.
2. Post the `#task` in `proj-<slug>` (which is dormant — this wakes it up):

```
#task maint-<seq>-<short-slug>: <Title>

Source: changes/<seq>-<short-slug>.md
Classification: <category>

@<owner-1> @<owner-2> ... — see the change doc for the full plan.

#done when:
- Files changed per plan
- Build green (npm run build clean)
- Atlas verifies JSON-LD if relevant
- Lens spot-checks if a11y or perf could regress (skip for trivial changes)
- changes/<seq>-<short-slug>.md "Resolution" filled
- CHANGELOG.md updated with a one-line entry
```

> **Sequence the rebuild; a data owner finishing is NOT the task finishing.** A
> maint change is done only when it is live in the rebuilt `dist/`. After the
> data owners finish (scout/quill/lingua), route to **pixel** to `npm run ship`
> and confirm the change is actually in `dist/` before you `#done`. Never mark a
> `#working` owner "stalled" — a slow owner (e.g. lingua translating a whole
> locale, ~1 day) is not a stalled one; wait for the handoff, don't preempt.

### 4. On completion

When the owner posts `#done`:

1. Verify the change doc's "Resolution" is filled
2. Append the change to `CHANGELOG.md`:
   ```
   ## 2026-09-12 · check-in time updated to 14:00 (request from hotel)
   - changes/001-checkin-14.md
   - Owners: pixel, quill, lingua, atlas
   ```
3. Set `status.yaml.state = launched`. Append history entry.
4. Post a brief summary in `proj-<slug>` confirming the change is live in production.

### Special handling

**Major redesign / starter switch**: route to a sub-project. Launch the recipe with slug `<slug>-v2` to create `proj-<slug>-v2`, treat the original as legacy until cutover. Then the original archives normally via `project-archive`.

**Hotel sends a "list of 12 things"**: split each into its own changes/<seq> entry. Don't bundle. Each gets its own `#task` so the workgroup stays focused.

**Hotel asks for the same thing 3 times across 3 projects**: pattern. Atlas/forge/canvas may want to propose a template change via `template-adr`. Mira posts in `template` workgroup.

**Request received but project is already archived**: this isn't maintenance, this is a re-engagement. Confirm with sales that the hotel is back as a client; if yes, restore project from archive (`mv archive/<year-q>/<slug> projects/`), re-open workgroup, treat as a new project with prior context.

## Common failure modes

| Symptom | Cause | Fix |
|---|---|---|
| Hotel's request applied immediately without classification | Mira bypassed the change doc | Re-do: write the change doc retroactively. The audit trail is non-negotiable. |
| Maintenance #task lands with wrong owner | Misclassification | Re-route. Update the change doc's plan section. |
| CHANGELOG.md drifts from actual changes | Owner posts #done without updating CHANGELOG | Mira gates closure on CHANGELOG update; refuses to mark "shipped" until both done |
| Bundled 12-item request as one task | Lazy intake | Split. One change-doc per discrete change. |
| "Migration to new starter" started as maintenance, ballooned to 6 weeks | Wrong classification | Re-classify as sub-project mid-stream; spawn `proj-<slug>-v2` |

## Voice

- Quote the hotel's request verbatim. Their words, not your paraphrase.
- Numbers in the plan: file counts, locale counts, owner counts
- Classification is decisive, not hedged. "Update" or "Add" or "Rebrand", pick one.
- After closure, the CHANGELOG entry is the only thing future-mira reads — make it tell the story.
