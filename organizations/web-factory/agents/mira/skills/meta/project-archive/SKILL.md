---
name: project-archive
description: Terminal archive — only runs when a project genuinely ends (service cancelled, hotel closed, platform migration, or 2+ years dormant). NOT triggered by launch. Moves projects/<slug>/ to archive/, closes proj-<slug> workgroup, captures the long-form retro.
category: meta
version: 0.2.0
origin: user
requires_env: []
tools: [read_file, write_file, terminal, workgroup_post]
keywords: ['archive', 'retro', 'terminal', 'end-of-life', 'workgroup-close']
created_at: 2026-05-29
---

## When to use

Only when ONE of these terminal conditions holds:

1. **Service cancellation** — the hotel has notified (in writing, via mira or sales) that they're ending the Mirai/factory engagement
2. **Hotel out of business** — verified externally (Google "permanently closed", domain expired, etc.)
3. **Platform migration** — hotel moved to a different web platform / different vendor
4. **Long dormancy** — 2+ years of zero `#task` activity in `proj-<slug>` AND production URL is still serving (low-confidence terminal — confirm with sales first)

**Launch does NOT trigger archive.** A launched project stays in `launched`/`maintenance` states for years. Archive is end-of-life, not post-launch wind-down.

## Inputs

- `projects/<slug>/status.yaml` (current state can be `launched`, `maintenance`, or even an interrupted earlier state in cases of cancellation pre-launch)
- The full `CHANGELOG.md` (it'll inform the retro)
- All `changes/*.md` (maintenance history)
- The `proj-<slug>` workgroup transcript

## Approach

### 1. Confirm the terminal trigger

Before any irreversible action:

- For **cancellation**: confirm with mira/sales that you have the cancellation document or email. Quote it in the retro.
- For **out-of-business**: pull external evidence (Google result, public registry). Don't archive on rumour.
- For **migration**: confirm the new platform; capture the date it went live (we hand off, then archive).
- For **dormancy**: surface in `vera/meta/portfolio-health-review`'s weekly digest at month 18; final decision at month 24. Don't auto-archive.

### 2. Write the retro

Append to (or create) `projects/<slug>/retro.md`. This is the long-form one — projects can have years of history to summarise.

```markdown
# Retro · <slug>

Launched: 2026-08-15
Total iterations to launch: 2
Years live: 3.2
Maintenance requests handled: 14
Archived: 2029-09-30
Archive trigger: service cancellation (email from owner, 2029-09-25)

## The launch
<one paragraph: starter chosen, iterations needed, anything notable>

## Post-launch life
<one paragraph per significant change — rebrand, new locale, photography refresh,
new section. Pull from CHANGELOG.md and changes/*.md.>

## What worked
- ...

## What didn't
- ...

## Insights to feed back to the factory
- Pattern observed: ...  → propose to <workgroup>
- Tool/skill gap: ...    → suggested by ...

## Production URL
- Last verified serving: <date>
- Final analytics snapshot: <if available>
```

### 3. Move the project tree

```bash
year=$(date "+%Y")
q=$(date "+%q")   # 1..4 for Q1..Q4
mkdir -p archive/$year-q$q
mv projects/<slug> archive/$year-q$q/
```

If the workspace is on a filesystem that doesn't support `mv` (e.g. across volumes), use `cp -r` then `rm -rf` — verify the copy before delete.

### 4. Update status.yaml in the archived location

```yaml
state: archived
archived_at: 2029-09-30
archive_trigger: service-cancellation
archive_path: archive/2029-q3/<slug>
history:
  # ... all existing entries ...
  - state: archived
    at: 2029-09-30
    by: mira
    note: service cancelled (email 2029-09-25); production handed off
```

### 5. Close the workgroup

Post a final message in `proj-<slug>`:

```
Project archived · 2029-09-30
Trigger: service cancellation
Production: served at https://<...> for 3.2 years
Total iterations: 2 to launch + 14 maintenance changes
Retro: archive/2029-q3/<slug>/retro.md

Thanks team. Closing the workgroup.
```

Run `alpi -p mira workgroup close proj-<slug>` (or the equivalent close verb).

### 6. Strategic notification (optional)

If the archive is strategically significant (a major client, a representative project failure to learn from):
- Notify factory-vera in the `quality` workgroup
- Vera decides whether the operator needs a portfolio-level review

## What this is NOT

- **Not a backup**. Archive moves the tree on the factory machine — not off-machine. Real backups are out of scope.
- **Not a launch step**. Repeat: launch ≠ archive.
- **Not reversible** automatically. If a hotel un-cancels, restoring is manual (`mv archive/<year-q>/<slug> projects/`, re-open workgroup). Rare enough to not need automation.

## Common failure modes

| Symptom | Cause | Fix |
|---|---|---|
| Archived a project that was just dormant 9 months | Trigger fired too early | Wait until 24 months minimum; check with sales first |
| Archived during an active maintenance request | Crossed wires | Confirm zero open `#task` in the workgroup before archiving |
| Production URL still resolves after archive — confusing | Source-side archive only; deployment still live | Either confirm hotel knows + accepts (cancellation case), or decommission the deployment first |
| Retro is one paragraph for a 3-year project | Lazy archive | Write the full retro; it's the only legacy this project leaves |

## Voice

- Mark archive triggers verbatim with the source evidence
- Write the retro for future-mira reading it cold 5 years later
- Don't archive defensively — if any doubt, hold and re-evaluate next quarter
