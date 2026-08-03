# alpi — pending work

Everything that lives in this repo: the core (`alpi/`) and the web-factory organization (`organizations/`). Template asks live in `astro-tasks.md`, in template vocabulary. Ordered by impact within each scope. Each item carries the evidence that justifies it, because an item without evidence gets argued about instead of done.

---

## 1. RC6 — turn write-back clobbers external `subscriptions.yaml` edits

The one crash-recovery addendum still open, now with two measured instances via `workgroup remove`:

- Removing `wg_dmbnnc7dt2maehw3` printed `also purged subscriptions on: lens, lingua, muse, pixel, quill, scout`; twenty minutes later four of six still carried the dead id, their `subscriptions.yaml` rewritten *after* the purge.
- Removing `wg_fzkx4ypyvvrjym6i` reported all six purged; only `lingua` resurrected — the one-in-six ratio the race predicts (only a profile with a write in flight at purge time writes back its pre-purge snapshot), ruling out "the purge never runs".
- 2026-08-02, the mass case: removing the seven maestranza workgroups while the 7-hotel fleet was mid-flight resurrected ten subscriptions across five profiles (muse 4, quill 3, lingua/pixel/lens 1 each) — every member had turns in flight, so the race fired near-universally. `workgroup leave` per pair cleaned all ten on the first try, confirming the member-side path is the safe one.

`_purge_after_delete` (`alpi/alp/workgroup.py:549`, unchanged in v0.12.0) walks `~/.alpi/profiles/*` and edits each profile's file behind its running poller, and returns the profiles it *touched*, not the ones that stayed clean. The member-side path (`workgroup leave`) does stick because it goes through that profile's own daemon. Fix: delegate the purge to each profile over its ALP socket, or re-read after a grace window and report only what verified clean. Same family: the setup TUI's trigger flow now writes the hub transcript from outside the daemon process — appends, not rewrites, so lower risk, but it is another writer behind a running poller.

## 2. Re-run the gate before waking the hub past the repair cap

**Measured on the maestranza rerun (2026-08-02).** Quill fixed the red findings
on disk during repair round 3 but never re-posted, so the gate never re-ran; the
rounds expired and the hub was woken. Mira re-verified by hand — `check:content`
exit 0 — then closed `#done BLOCKED` whose own text says "Handing off to
#translation": right verification, wrong verb, halted run (the contract line
"BLOCKED HALTS — choose by intent" did not hold, third prose failure of this
shape). Structural fix: when the repair cap expires, the daemon re-runs the gate
ONCE before waking the hub — green means machine close + advance and the hub is
never woken over work that is already done; red means the hub wake carries the
fresh findings. Kills both the silent-fixer stall and the wrong-verb close in
one move.

Second shape, same family (abad rerun, same day): lingua burned the 3 rounds on
drip findings, and at round 3 its RE-DELIVERY was rejected by turn-rotation —
"you already posted in the current round (since the hub's last post)" — because
the fix note + `#working` had consumed the cap. Muted owner → gate never
re-runs → hub never woken → poller resumes the owner forever at +0 posts. An
operator hub post broke the cycle. Fix alongside the re-run: the owner's
re-delivery during a repair round must be exempt from the rotation cap (or each
daemon repair note opens a fresh round).

Fifth shape (jaime measurement run, 2026-08-03, ZERO operator pushes): lens
returned an honest QA FAIL (8 content entries missing from the intake table),
mira closed `#done QA FAIL · <findings>` — and the run froze there for good:
once the hub's own close is the newest post, no poller path wakes it again, so
the routing it stated in prose never becomes a task. Third instance of the
class; the first two were masked by operator routing. Fix candidates, pick one:
the daemon refuses a hub `#done` that quotes QA FAIL unless the same turn opens
the re-task or closes BLOCKED; or a `#done` containing QA FAIL triggers one
daemon follow-up wake ("route the findings or halt").

Fourth shape (overnight pause/resume, 2026-08-03): the gate is edge-triggered
on the owner's post arrival, so a handoff delivered just before `workgroup
pause` never fires its gate and `resume` does not re-scan — roma and maestranza
both sat 25+ minutes with verified-green deliveries and no machine close, until
an operator re-delivery re-fired the edge. The rotation state also resumes
stale (a muse post was first rejected as "already posted this round", then
accepted unchanged a minute later). Fix: on resume, level-trigger once — for
each open task whose newest owner post postdates the last machine close, run
the gate as if the post had just arrived.

Third shape (beachmate scaffold incident, same day): rewinding a chain is not
expressible. With `#assets` closed BLOCKED because intake had shipped the
untouched scaffold, a hub `#task #intake` was refused by
`blocked-phase-not-cleared` — the guard reads any non-P slug as advancing, even
an UPSTREAM phase — and the only guard-exempt opener (`trigger`) starts at a
pipeline's first phase. The operator's cheapest move was destroying the
workgroup and relaunching. Fix: the guard should allow a hub task on any phase
EARLIER in the chain than the blocked one (a rewind re-walks forward through
the blocked phase anyway, so nothing is skipped).

## 3. Input tokens are 98% of workgroup cost — cache the prefix, cap the replay

**Measured on the 2026-08-02 rerun: $23.43 / 165M tokens for 7 sites, and the
input:output ratio is ~53:1 (lingua: 57.4M in, 1.1M out).** The spend is not
generation, it is re-reading: every turn re-injects the member contract plus the
full workgroup transcript (50–80 posts by pipeline end), so cost grows with
turn count × transcript length. Two moves, complementary:

- **Stable prefix for provider caching.** DeepSeek prices cache-hit input at a
  fraction of cold input. Verify the request path emits a byte-stable prefix
  across a member's consecutive turns (contract first, then transcript
  append-only, volatile fields such as timestamps LAST), and confirm cache-hit
  rates via the provider's usage fields. If the prefix churns, fix the ordering.
- **Cap the transcript replay.** A turn rarely needs posts from three phases
  ago; replay the last N posts plus the pinned briefing and the current task,
  and let the member pull older context on demand. Acceptance: a translation
  turn on a 70-post workgroup carries a bounded transcript, and the per-site
  cost of a clean run drops measurably below the $2.21 baseline (roma,
  both chains clean).

## 4. Authorship boundaries are a convention, not a guarantee

**Two measured cases.** On v2, mira rewrote `src/content/dining/gastrobar-sensur.es.json` — Quill's domain — inside its own turn after the content gate failed; its `tools_deny` lists `edit_file`, and `write_file` is the tool that writes. On v5 `#media-build`, pixel edited `assets/manifest.yaml`, muse's domain, to fill the `logo-on-dark` slot, overriding a deliberate `placeholder` decision; its own contract says *"Do not edit hotel data to force a green build."* Both passed every gate.

Denying `write_file` is the immediate fix and it is not airtight: `terminal` writes too. Tool denies cannot express "these paths belong to that member", and the template's `check:boundary` is per-project, not per-phase, so any member editing any authoring file passes it. Either the recipe declares which paths a phase may touch and the check reads it, or stop describing the boundary as enforced. v0.12.0 makes the recipe-side half natural — `pipeline_steps` is already the per-phase contract surface, a `paths:` key beside `gate:` would be validated the same way — but the enforcement half still needs a checker that diffs the phase's changes against the declaration.

---

## 5. `roma-oficial-vs-fabrica.md` is written from one hotel

The report scores the factory against the hotel's own production site and was written when roma was the only measured case (64/80 vs the official site's 49/80). There are now seven, including a five-property resort, plus the alt-text finding from the abad run and the full v5 gate record. Rewriting it with fleet data is the difference between an anecdote and a result. Keep the document — it is the only artefact that argues the factory's case in the client's own terms.

## 6. Thin-brief fixtures

`briefings/hotel-maestranza/brief.md` is the reference format (495 words, eight sections) and both `BRIEFING.md` and `briefings/README.md` point at it. Open: whether `jaime-primero` and `kivir` get rewritten in that format or stay as the deliberately thin-brief fixtures they are — they are the only cases where exploration in `#enrich` still pays.
