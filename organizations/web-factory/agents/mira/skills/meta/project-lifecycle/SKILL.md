---
name: project-lifecycle
description: Drive a hotel project's build lifecycle (intake → qa → launched) and the QA-fail loop; mira is the only agent that mutates status.yaml. Post-launch maintenance lives in maintenance-intake, end-of-life in project-archive.
category: meta
version: 0.2.0
origin: user
requires_env: []
tools: [read_file, terminal, search, workgroup_post, write_file]
keywords: ['lifecycle', 'state-machine', 'maintenance', 'iteration', 'launch', 'status']
created_at: 2026-05-29
---

## When to use

Every time a project's state changes. Mira owns this end-to-end — other agents post handoffs in `proj-<slug>`, mira reads them and advances the machine. Applies for the entire life of a project, which spans years post-launch.

## The state machine

```
created → intake → assets → content → translation → build → qa → launched ──┐
                                                       ▲        │            │
                                              iterating └──(QA fail loop)     │
                                                                              │
                                     maintenance ───────────────────────────┤  (recurring)
                                                                              ▼
                                                                          archived (terminal)
```

**Six** owner-driven build phases (intake → qa), then `launched`;
`assets` may close trivially (below); `iterating` is the QA-fail loop;
one **recurring** state (maintenance ↔ launched) and one **terminal**
state (archived).

### Build phases — 6 (Lean), STRICTLY sequential, one owner each

The factory is the 4-theme Astro kit — the git base repo cloned into each
`projects/<slug>/`. Agents
produce **only data** — `src/config/site.json` (scout) and `src/content/**`
(quill/lingua) — never components, themes, or `.ts`. **design + seo are NOT
phases**: the themes carry the design (canvas advises brand tokens only if
the hotel has a real kit), and SEO is structural (sitemap, hreflang, JSON-LD,
per-page meta live in the fixed template) plus the `seo` copy quill writes.

**Deterministic gates own four transitions.** The runtime itself closes
`intake` (ONLY on the trivial path: `visual_assets: not_required` +
`assets/` empty → straight to `content`, no muse ping ever), `content`,
`translation` and `build`, opening the next phase the moment the owner's
handoff passes the local gate (`intake-check` / `content-check` / `dist`
on disk) — you will see machine-authored `#done … · gate:<check>` posts in
the transcript. Do NOT re-close or re-open those phases; your judgment
turns are the non-trivial `assets` path (signal `required`/`optional`, or
photos on disk — the intake gate fails on purpose and wakes you), `qa`,
fail→fix routing, and maintenance. A `GATE <phase> FAILED` wake means
either the assets decision is yours or the owner's deliverable failed the
mechanical check — route accordingly, exactly like a QA fail.

Every wake, drive it like a gate:

1. **Read `status.yaml`** — the current phase. Open ONLY the single next
   phase. Never jump ahead.
2. **Verify the current phase's files on disk** (table). Missing → re-task
   the owner; do NOT advance.
3. When verified, **in the same wake**: post `#done`, update `status.yaml`
   (append history, bump `state:`), then open the next phase's `#task` as a
   **separate `workgroup_post`** — the `#done` and the next `#task` are two
   distinct posts, never combined in one post body (mixed markers in one body
   break the protocol).
4. **Before opening a later phase, confirm earlier deliverables still
   exist.**
5. **Open each task CONCRETE — name the deliverables, not just the phase.**
   A generic "produce the content" sends the owner exploring the filesystem;
   a specific list makes it write. e.g. content → "write `src/content/**` —
   the rooms from intake's inventory, `pages/home`, amenities, dining, per
   the binding catalogue, tagged `lang=<src>`"; translation → "translate
   every source entry into `<locales>`".

Each phase `#task` is **addressed to its owner** — `@quill #task #content
…` — so only that owner wakes and the close-quorum is just them.

| Phase | Owner | Verify on disk | Then open |
|---|---|---|---|
| `intake` | scout | `src/config/site.json` (valid `theme`, `brand.name`, `locales`, `defaultLocale`; `url` matching the brief's domain VERBATIM when the brief names one — an invented or "adapted" domain is a re-task, never something you or pixel supply) + `intake.md`. Facts the brief lacks are **omitted** in `site.json`, marked `[NEEDS HOTEL]` only in `intake.md` prose — not a re-task reason. | the `assets` gate (below) |
| `assets` | muse | Gated on scout's `visual_assets:` signal (below). When tasked: `assets/assets.yaml` + every file it references. When the signal is `not_required`: nothing — close trivially in the same wake. | `@quill #task #content` |
| `content` | quill | `src/content/**` source-locale entries (`pages/home.<src>.json` + `rooms/*` at minimum) tagged `lang=<src>`, per the binding catalogue | `@lingua #task #translation` |
| `translation` | lingua | the same entries for **every** other locale in `site.json.locales` (`lang=<target>`). Expect a counted handoff (`<written>/<expected> · no missing`); a partial/count-less one (e.g. "de,nl × 5") is a miss → re-task naming the gap, don't accept dribbles | `@pixel #task #build` |
| `build` | pixel | `dist/` HTML per declared locale + `sitemap.xml`/`robots.txt`, checked with deterministic shell (`find`/`test -f`), never `search` | `@lens #task #qa` |
| `qa` | lens | verdict, audited against `dist/` on disk | pass → `launched`; fail → the QA-fail loop below |

**`build` gate — open `@pixel #task #build` only when** the source content
exists AND every locale in `site.json.locales` has its translated entries.
A site missing a declared locale is a defective deliverable, not a fast one.

**The `assets` phase — a REAL pipeline phase with a trivial close.** It is
never skipped, only closed. On scout's `#done intake`, read the
`visual_assets:` signal from its handoff and act mechanically:
- `required before content` → `@muse #task #assets` (template below). Content
  does NOT open until this phase closes.
- `not_required` → **first check disk**: if `projects/<slug>/assets/` holds any
  image, the signal is WRONG (supplied photos need restoring) — task muse to
  restore + write `assets.yaml`, do NOT skip. Only when `assets/` has no image
  do you close it yourself in the same wake:
  `#done assets skipped · signal not_required`, then open `#content`.
- `optional` → default to the trivial close; task muse only when the brief
  argues for it. A later QA fail re-enters via `#assets-fix`.

muse writes to `projects/<slug>/assets/` (logo as SVG, hero/ambience/gallery as
raster, restored photos), which `npm run ship` materialises into `public/img/`.
**Close a tasked `#assets` by DISK EVIDENCE, not muse's post**: if it sits in
`#working`, check `projects/<slug>/assets/` — `assets.yaml` + its files exist →
close and open `#content`; files but no `assets.yaml` → re-task muse for the
manifest only (don't regenerate); no files → re-task normally. (muse posts a
PLAIN handoff, never `#done`.)

### Task templates (fill `<…>`; one phase per post, owner-addressed; never mix `#done` and `#task` in one post)

- `@scout  #task #intake · pick the theme + write src/config/site.json + intake.md; end the handoff with the visual_assets: signal line`
- `@muse   #task #assets · brand-critical only: logo (if missing) + home hero; a small home gallery ONLY if the brief asks. Write assets/assets.yaml. Never fabricate specific room/dining/amenity photos.`
- `@quill  #task #content · write src/content/** source-locale entries per the binding catalogue (factory/template-spec.json); every pages/*.json intro value is an object: "intro": {"title": "...", "body": "..."}, never a string; NEVER write image/gallery paths`
- `@lingua #task #translation · translate every source entry into <locales>`
- `@pixel  #task #build · green npm run ship ONLY (manifest → build → preflight), dist/ on disk`
- `@lens   #task #qa · audit dist/ against the launch checklist; one PASS/FAIL verdict`

**Single-locale projects**: lingua has nothing to translate — it posts a **plain
skip handoff** ("translation skipped · single locale", never a `#`-marker), and
you close `translation` as soon as it opens and move to `build`.

If a handoff claims done but the files aren't on disk, re-task the same
owner (max twice). After two, **close** with `#done BLOCKED · <phase> · <owner>
· <missing>` and wait — never @-escalate outside the workgroup, never loop.

**Blocking is a `#done`, not prose.** Always block by CLOSING the task:
`#done BLOCKED · <phase> · <reason>`. A plain `BLOCKED · …` line leaves the
task open and the pipeline hangs. A `#done` whose result starts with `BLOCKED`
closes the task and the core halts the pipeline (no auto-advance, no reopen)
until a human re-tasks it; also set `status.yaml → blocked`.

**The artifact on disk is the deliverable — not the handoff post.** The
inverse also holds: never block a phase that IS done on disk just because the
member's handoff is missing or malformed (a `#done` a member wrongly prefixed
is stripped by the protocol, so the line can read oddly or vanish). On any
wake, if the current phase's verify-target is on disk, close it yourself.
Before closing `content`, run `cd projects/<slug> && npm run content-check`.
This cheap source-locale gate catches malformed editorial JSON before Lingua
multiplies it across every locale. A failure is a Quill `#content-fix`; re-task
Quill with the exact file and error, then rerun the gate (max twice). Only a
green `content-check` may advance to translation. Run the same gate again
before closing `translation`; a target-locale-only failure is a Lingua
`#translation-fix`, not a template bug. Only a second green check may advance
to build. For
`build` specifically, check with **deterministic shell, never `search`/semantic
globs** (they miss or mis-rank files — a real `dist/` can read as absent): run
`terminal` read-only — `find projects/<slug>/dist -name '*.html'` (a set per
declared locale), `test -f projects/<slug>/dist/sitemap.xml`, `test -f
projects/<slug>/dist/robots.txt`. All pass → the build is green: post `#done
build verified` and open `@lens #task #qa` in the same turn as a separate
`workgroup_post`, with or without pixel's handoff. Any locale's HTML or
sitemap/robots missing → re-task pixel (BLOCK after two misses). A green `dist/`
left unclosed while you wait for perfect wording is the failure mode, not
patience.

### Final QA + launch

| State | Owner | Signal | Mira's action |
|---|---|---|---|
| `qa` | lens | `QA PASS` verdict, audited against `dist/` | `#done qa green`; move `status.yaml → launched`, set `launched_at` |
| `launched` | mira | build green + QA PASS recorded | Append `CHANGELOG.md`; post the final summary in the workgroup |

**`launched` = built + QA-passed + `status.yaml` updated, NOT a live deploy.**
This workgroup has no CDN/deploy step; a real production deploy is a separate,
explicit phase or tool if/when one exists. Don't claim a production URL serves or
"monitoring green" unless one genuinely does.

### QA-fail loop (qa ↔ iterating, autonomous)

Lens's verdict is the launch gate. A single fail blocks `launched`. Lens
posts the verdict but **can't close the qa task** — only mira can. On a
FAIL, mira must NOT `#done` it: a `#done` marks the last pipeline phase
complete and strands the project (the continuation sees qa done → nothing
left to open → no wake). Instead mira's single post opens the correction
task, which supersedes the open qa (single-task model). The fail stays on
record via lens's verdict post. These slugs are off-pipeline — the core
won't auto-advance; each step is driven by the owner's handoff waking mira:

1. Advance `status.yaml → iterating` (bump `iterations`) — bookkeeping.
2. Open **exactly one** targeted correction `#task` to the primary owner
   of the failing item (this is mira's next post, no `#done` first):

   | Failing checklist item | Owner · task |
   |---|---|
   | source-locale JSON violates the documented binding/Zod shape, placeholder / lorem in page **prose**, weak/missing page `seo`, or **content thin (preflight `content thin:` minimums)** | `@quill #task #content-fix` |
   | `[NEEDS HOTEL]` / placeholder in **contact or JSON-LD** (source: `site.json`) | `@scout #task #intake-fix` |
   | translated JSON alone violates the source shape, translation gap, wrong locale, untranslated section | `@lingua #task #translation-fix` |
   | gallery empty / hero missing / no brand logo — missing or low-quality visual assets | `@muse #task #assets-fix` |
   | missing `dist/sitemap*.xml`, build error, image budget, perf, responsive, a11y | `@pixel #task #build-fix` |
   | documented data shape is valid but a component ignores it, or the fixed Zod schema contradicts `factory/template-spec.json` | close `#done BLOCKED · template · <what>` — forge owns it org-wide and isn't in this workgroup; never re-task quill/pixel |
   | brand-visual / token regression | `#done BLOCKED · brand · <what>` — canvas owns it in `brand-library`, out-of-band; canvas is NOT a member of this workgroup, so never `@canvas #task` here |

   **Data-vs-template:** if the content entry has the right value but the
   built page shows generic/placeholder text, the template isn't binding it →
   that's a **template bug for forge**, never a content-fix for quill/lingua
   (re-tasking them is an unfixable loop). One workgroup operates on ONE
   project — every path uses this workgroup's slug, never another project's.

   SEO is structural (sitemap, hreflang, JSON-LD live in the fixed template);
   the *words* are quill's page `seo` copy and the JSON-LD *facts* are scout's
   `site.json`. **atlas audits structured data + Core Web Vitals in qa — it
   advises the owner above, it never owns a write-fix.**

3. On the fix's `#done`, **rebuild before re-judging** — any
   content / translation / `site.json` fix changes the source, so `dist/` is
   stale: open `@pixel #task #build-recheck`; on its `#done`, open
   `@lens #task #qa-recheck`. A pixel-only fix may skip to `#qa-recheck`.
4. Read the next verdict. PASS → `launched`. FAIL → repeat.

**Cap: 3 fail→fix rounds.** If lens still fails after the third, close
`#done BLOCKED · qa · <unresolved items>` and stop — never loop a fourth time.

### Maintenance loop (post-launch, recurring)

The workgroup stays open; a project lives in `launched`/`maintenance` for years.
A post-launch change request is handled by the **`maintenance-intake`** skill —
classify → document in `changes/<seq>-<slug>.md` → move `launched`→`maintenance`,
open the `#task`, ship, append `CHANGELOG.md`, move back to `launched`. A
"migrate to a different starter" request is a sub-project, not maintenance: spawn
`proj-<slug>-v2`.

### Terminal archive

End-of-life only — **never** triggered by launch. When a terminal condition
holds (service cancelled, hotel closed, platform migration, or 2+ years dormant),
mira runs the **`project-archive`** skill (move to `archive/<year>-q<n>/`, close
the workgroup, write the retro).

## status.yaml contract

```yaml
slug: casa-bahia
theme: boutique
state: launched              # one of: created | intake | assets | content | translation | build | qa | iterating | blocked | launched | maintenance | archived
created: 2026-05-29
launched_at: 2026-06-09      # null until launch
launch_target: 2026-06-09    # provisional from the recipe launch, scout may revise
archived_at: null            # null until terminal archive
iterations: 1                # cumulative QA-fix rounds; useful for portfolio review
history:
  - state: created
    at: 2026-05-29
    by: recipe
  - state: intake
    at: 2026-05-29
    by: recipe
    note: kickoff task posted to scout
  - state: content
    at: 2026-06-02
    by: mira
    note: scout's site.json + theme verified
  - state: translation
    at: 2026-06-04
    by: mira
  - state: build
    at: 2026-06-06
    by: mira
  - state: qa
    at: 2026-06-07
    by: mira
  - state: iterating
    at: 2026-06-07
    by: mira
    note: qa fail — placeholder copy; re-tasked quill (#content-fix)
  - state: qa
    at: 2026-06-08
    by: mira
    note: qa-recheck
  - state: launched
    at: 2026-06-09
    by: mira
```

Append to `history` on every transition. Never delete entries.

**State must match disk.** If `dist/` is green but `state` is still `build`,
close build and open `#qa` — do **not** re-run content/intake "to be safe". After
a PASS, `state` is `launched` and qa never reopens. On a stale wake, reconcile
`state` by reading the transcript + what's on disk before acting.

## Blockers and overrides

- **Lens fails an item in qa**: run the **QA-fail loop** above — **do NOT `#done` the qa** (that marks the terminal phase complete and strands the project). Move `status.yaml → iterating` and open one targeted correction task to the owner (it supersedes the open qa), then `#build-recheck` → `#qa-recheck`. State only advances to `launched` when lens posts green. Cap at 3 rounds, then close `#done BLOCKED · qa · <unresolved>`.
- **Quality override**: requires vera signoff via `vera/meta/quality-gate-override` skill. Mira does not unilaterally relax the bar.
- **Scope creep mid-build**: if the ask requires template change, mira pushes to the `template` workgroup. The per-project work pauses on that specific element.
- **Iteration over-cycling**: at 3 rounds, flag. At 5, escalate to vera.

## Capacity rule

Hard ceiling: 5 active builds (state ∈ {intake, assets, content, translation, build, qa, iterating}). Projects in `launched`/`maintenance` don't count against the cap — they're dormant most of the time.

When at cap, mira responds to new project requests with "queued for <month>" rather than overcommitting.

## Voice

- Date and owner in every status post: "→ qa on 2026-07-08, owner: lens"
- No hedging. "Lens blocks launch on accessibility item A2" beats "There may be an accessibility issue"
- Default to template-fits-the-need — escalate scope to vera only when the request truly bends the system
- After launch, the project is **alive but quiet**. Mira's job shifts from orchestration to availability — answer maintenance requests, watch portfolio health
