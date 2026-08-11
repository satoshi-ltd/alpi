# alpi — pending work

Everything that lives in this repo: the core (`alpi/`) and the web-factory organization (`organizations/`). Template asks live in `astro-tasks.md`, in template vocabulary. Each item carries the evidence that justifies it, because an item without evidence gets argued about instead of done.

---

## 1. Confirm whether the hub authors hotel data, then move the boundary into structure

**Suspected on hotel-abad v18, 2026-08-05 — a lead, not a verdict.** A corrective
write landed inside the hub's turn window and outside the owner's. The hub's
contract forbids authoring hotel data and nothing enforces it: `terminal` is not
in its deny list, so a shell redirect writes any file in the workspace.

Terminal runs now carry `workgroup_id` in the run ledger. First telemetry,
2026-08-06: 17 hub terminal runs attributed across a fleet, every output tail
consistent with diagnosis (ls, cat, diffs, check runs), none with a write
signature — but tails cannot prove absence, so the question stays open until a
run reproduces the anomaly under instrumentation.

Same class, second instance, measured on jaime-primero 2026-08-06: a member with
`edit_file`+`terminal` denied still created `tmp-slot.txt` at the project root
via `write_file` — and could not delete it, burning three repair rounds on a
boundary red it could see but not act on. Write tools are jailed to the
workspace, not to the phase's declared `paths:`. The structural fix is one-sided
permissions: what a phase may WRITE should be the set the boundary check
enforces.

**Third instance, and the costliest: hotel-abad-v6, 2026-08-11. It recovers, so
the defect is waste, not deadlock.** The causal chain, reconstructed from the
run: @scout emitted canonical slugs carrying the `room-` media prefix, @muse
built `assets/manifest.yaml` on that contract, and the inconsistency only
surfaced when `check:content` ran for @quill. The gate then asked @quill for a
repair that also required editing `work/intake.md` — @scout's file, outside
`content`'s declared paths. @quill made the edit, the boundary rejected it, and
after several rounds `content` closed BLOCKED:

> `#content` gate RED: boundary finding on `work/intake.md` (changed-during-phase,
> owned by @scout not @quill). @quill routed it to @scout in seq #26 but the file
> remains unsanctioned on disk — no owner can clear the #content gate while
> intake.md's canonical room rows live in a phase they don't belong to.

The hub then re-opened `intake` for @scout on its own; the workgroup was paused
by the operator mid-recovery, not stuck. So the runtime self-heals — it just
pays a full phase re-open for a contract error that was detectable three phases
earlier. Rate: 1 in 15 hotel-runs (v4 0/5, v5 0/5, v6 1/5).

The measured slug failure is now closed upstream: `check:intake` rejects a
canonical slug that already carries its collection's media prefix (`room-x`,
`amenity-x`, `dining-x`, `experience-x`), and Scout's contract names the same
rule. The bad contract cannot reach Muse or Quill. When another inconsistency
does surface later, the owning phase should still re-open rather than the
current owner being asked to cross a boundary it cannot cross.

Acceptance: a hub write to a phase owner's file surfaces as a finding rather
than as silent success; a member cannot create what it cannot remove; and a
slug-contract mismatch is caught by the phase that authored the contract.

## 2. A fact that changes must reach every surface that renders it

**The defining escape family of both post-launch chains, measured twice on
jaime-primero, 2026-08-06.** Two independent runs, same shape:

- `content-update`: the checkout correction (12:00 → 12:30) landed as a new row
  in the source locale's practical facts and never reached EN/FR — locale
  parity is per-file and per-schema, so a row added inside an existing file is
  invisible. Guests reading English get no checkout time at all. STILL LIVE on
  the built site.
- `review`: the client's star correction (3 → 4) updated the prose in three
  locales but not `site.json`'s `identity.category` — so the badge and the
  JSON-LD still say 3 while the copy says 4, in all locales. The triage routed
  the note to content and the config half never happened. STILL LIVE.

Both escapes shipped through green gates and a 100/100 audit, because every
check compares a surface with itself, never a fact across surfaces. The July
report mocked romanuevedos for exactly this ("cama King size" vs "cama doble
200 cm"); the factory now demonstrably produces the same class of defect under
change.

**The `review` half no longer reproduces. Re-measured on a clean
`hotel-maestranza-v5`, 2026-08-11**, with a work order carrying the same defect
shape in reverse (stars 4 → 3): the correction reached `site.json`
`identity.category.rating`, the prose in both locales, and `starRating` in all
36 built JSON-LD blocks, with no stale `4` anywhere in `src/` or `dist/`. The
chain closed 8/8 including the terminal hub-owned phase.

**The `content-update` half does not reproduce either, but it exposed a
different gap. Measured on `hotel-abad-v5` (es/en/fr), 2026-08-11**, with a work
order carrying both mechanisms:

- Value change in an existing row — checkout 12:00 → 12:30 — propagated to all
  three locales (`Hasta las 12:30`, `Until 12:30 pm`, `Jusqu'à 12h30`).
- A row ADDED — paid late check-out until 15:00 for 25 € — appears in no locale,
  **including the source one**. Not a parity failure: @scout extracted the fact
  into `work/intake.md` and deliberately withheld it, recording *"Recorded as a
  GAP, not authored: the monetary-provenance gate"* because the price has no
  provenance source beyond the client's own note.

The policy is now explicit: a hotel stating its own price or commercial
condition in `work/update-*.md` is first-party canonical provenance, equivalent
to the launch brief. The content gate reads those files, so the 25 € update is
publishable without weakening monetary verification. Lens must also emit a
`RETAINED` line for every explicit publishable brief/update requirement absent
from `dist`, and a retained requirement cannot accompany `QA PASS`. This closes
both the provenance gap and the silent-green outcome; the next isolated run
must verify the complete chain.

jaime's two live defects still need repairing on their own project; the runs
above were clean-room reproductions, not fixes to jaime.

## 3. The audit scores structure, not completeness

**Measured across v4/v5/v6, 2026-08-11.** `work/audit.json` is a fixed
structural checklist, not a census of what was produced: hotel-maestranza scored
**99/99 in both v4 and v5** with an identical check distribution (intake 45,
locales 20, content 19, dist 14, boundary 1) — while the artefacts differed:

| | content files | content bytes | built pages |
|---|---|---|---|
| v4 | 36 | 30 KB | 41 |
| v5 | 20 (−44%) | 22 KB (−27%) | 37 (−10%) |

The manual brief comparison is complete. v5 preserves the explicit room,
service, dining, direct-booking, location and legal requirements from v4; its
smaller file count is consolidation, not demonstrated quality loss. It also
correctly omits testimonials whose dates were not verifiable. The original
"thinner means worse" concern is closed for this case.

The comparison did expose one concrete extraction miss: both v4 and v5 omit
the tourism registration `H/MA/01460` from intake, source content and `dist`
although it is explicit in the identical brief. Both still score 99/99. The
remaining problem is therefore narrower and evidenced: a structural audit does
not prove absolute brief coverage.

Fleet-wide spread on identical briefs and identical code is 13–37% by content
volume, while cost per phase stays within ±8%. The factory is economically
reproducible and editorially not.

Items 2 and 3 are two links in one guarantee chain:

```
brief.md → canonical intake → surfaces → dist
```

Two distinct contracts, neither fully guaranteed today: **extraction** (every
brief requirement reached the intake) and **propagation** (every intake fact
reached every surface that renders it). The audit checks mainly internal
coherence among the surfaces that happen to exist.

Lens now performs the smallest useful coverage check: compare explicit
publishable requirements in `brief.md` and `work/update-*.md` with the built
artifact, then report every omission before its verdict. This is deliberately
not a new semantic score or gate. The next isolated run should prove that the
registration omission becomes visible and prevents a false PASS.

## 4. Quill's reuse patterns need contract structure, not more prose

**Measured by the editorial panel across the fleet, 2026-08-06, and
hand-verified.** Three recurring machine-tells, each in at least three hotels:

- a paragraph reused verbatim across pages (maestranza's Gastrobar Sensur block
  on home AND restaurant; regio's Salón Drago likewise; roma's welcome copy),
- five room cards sharing one amenity list in identical order (roma),
- a pull-quote attributed to the hotel itself, reading as a fake testimonial
  (roma, abad, jaime).

These live in quill's lane (`organizations/`), and the lesson of 8.2 applies:
another prose rule will not survive load. Candidates with structure: the
content check already parses every entry, so a verbatim-duplicate-paragraph
detector across pages is cheap and mechanical; the self-attributed quote is a
schema question (a quote's `author` should never equal the hotel's own name).
Decide scope with the creator before building — this brushes against
no-overengineering.

## 5. jaime's official site is still unmeasured

`hoteljaimeprimero.com` has returned HTTP 429 on three attempts with different
agents. Retry periodically; the report keeps the stated limit until it answers.

## 6. ON HOLD — creator's call: review redesign

The first real review run (jaime, 2026-08-06) worked 7 of 8 phases and exposed
two design flaws. The hub-owned terminal deadlock is resolved and verified live
(`hotel-maestranza-v5`, 2026-08-11, chain closed 8/8 through `review-close`).
Applied notes that do not chase every surface where a fact renders (item 2) are
half-resolved. The remaining review-design decision is deliberately parked:

- **A** — keep the declared 8-phase chain and add a propagation guard. The
  runtime deadlock is already fixed, but every order still pays all 8 phases.
- **B** — drop the fixed chain: the hub triages the work order and re-opens the
  earliest owning phase of the LAUNCH chain; the re-walk forward (content →
  translation → build → qa) forces every downstream surface to reconcile, which
  kills both measured flaws by construction. Recipe + contracts only, no daemon
  code. Standing recommendation on the table.
- **C** — transport, later: the hosted preview (devops' CloudFront template)
  lands the client's work order as a git commit in `work/review/` and triggers
  the flow, removing the operator copy-paste. Pairs with either A or B.

B alone does not remove the three waste causes — re-opening the owning phase
fixes the routing, not the opener or the triage. It needs three contracts
alongside it: the opener addresses exactly ONE structured recipient (no
incidental `@handles` that wake agents with no task), triage is forbidden from
modifying artefacts and may only classify, and the downstream route is derived
from the owning phase rather than declared. Without them, incidental mentions
and triage-time edits reappear.

**Cost makes this the highest-return item on the list. Measured on
hotel-maestranza-v5, 2026-08-11: the launch chain cost $0.569 and the review
chain that followed cost $0.557 — 98%.** Reviewing three notes cost as much as
building the whole site. The waste is structural: incidental `@handles` in the
opener wake agents who have no task, triage edits instead of only classifying,
and one residual defect re-walks the whole chain instead of owner → build → QA.
Option B addresses all three by construction.
