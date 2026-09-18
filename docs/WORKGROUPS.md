# Workgroups in practice

How alpi agents actually collaborate inside an ALP workgroup: the briefing,
the `#task` / `#done` markers, recipes that launch a workgroup from a file,
pipelines with deterministic phase gates, the poller that wakes each member,
and the places where a human steers.

The wire protocol — identity, envelope, the `workgroup.*` methods, group-key
sealing, hub state, budgets — is specified in [ALP.md](ALP.md). Everything on
this page is parsed and enforced by the reference implementation on top of
that wire; the hub stays zero-knowledge about post bodies throughout.

---

## Briefing + auto-kickoff

A workgroup carries a short **briefing** — a one-paragraph
description of its purpose, members, and expected deliverable —
set at create time and editable from the wizard. The briefing is
plaintext on the hub (alongside the name, hub_pubkey, and budget),
since it's metadata about *why this workgroup exists*, not the
content of conversations inside it.

```yaml
# meta.yaml extension
briefing: >
  research peptide candidates for therapeutic protein X.
  deliver a shortlist of 5 with Tanimoto > 0.7 by friday.
```

A freshly created workgroup is dormant until its first post: every
wake trigger keys off transcript content, so an empty transcript
wakes nobody. The kickoff is always an explicit first post — the
hub's opening `#task` (from the TUI, CLI, or a bootstrap script).

**Briefing discipline.** A briefing describes the *problem and
constraints*, not how the workgroup is meant to operate. It
should NOT contain:

- A `Roles:` block telling specific peers what to post or in
  what order ("@alice gives the PM read once carol has posted
  facts"). Each peer infers their contribution from their own
  identity (`public_bio` + memories + tools), not from the
  briefing's micromanagement.
- Protocol mechanics ("post `#done` only when X holds", "wait
  for round 2 before closing"). Those live in the engagement rules
  every member's system prompt already carries. Repeating them in
  the briefing bloats context and undermines the principle that the
  protocol is uniform across workgroups.
- Workflow scripts ("Round 1 — @x propose; Round 2 — @y
  refine"). The hub orchestrates by posting the *problem* and
  letting the round system carry the rest.

A clean briefing is just: what is the decision/deliverable, what
are the hard constraints (data sources, budgets, deadlines,
correctness criteria), what does "done" look like.

Identities (`public_bio` per profile, plus the bio echoed into
each member's roster on join) carry the *who-does-what* — a peer
introduced as `"Sommelier — maps acidity, tannin, sweetness"`
already knows their slice of any food workgroup; the briefing
doesn't need to reiterate.

## Recipes (host-plane launch)

Creating a workgroup by hand means naming it, picking members,
writing a briefing, and — for a pipeline — spelling out every
phase, owner, and gate. For workgroups launched repeatedly with
the same shape (a standing review board, a per-project production
line), that shape is *constant*; only a parameter or two and the
brief change. A **recipe** captures the constant shape as data, so
a launch is "load this file, fill the blanks."

A recipe is a plain YAML file. A hub keeps reusable recipes in
`<profile-home>/recipes/<id>.yaml`; the filename stem is the recipe id.
Clients list those recipes through the host plane and launch them by id.
One-off or externally versioned recipes remain supported: the desktop file
picker and CLI can read any `.yaml` / `.yml` file and hand its contents to the
daemon. Both routes use the same parser and launcher.

Recipes are a **host-plane** convenience, not part of the ALP wire
protocol — ALP gains no recipe or project verbs. A launch just
assembles the existing `workgroup.create` primitive (plus, when
asked, a project clone) from the resolved recipe. Three host methods:

- `host.workgroup.recipes.list(profile)` — list and describe the saved
  recipes owned by that hub profile. A saved recipe declaring another hub is
  rejected.
- `host.workgroup.recipes.describe(yaml)` — parse a recipe and
  return its shape (hub, declared params + patterns, briefing
  draft, whether it clones a project). Scope-free; the desktop
  uses it to render the launch form.
- `host.workgroup.launch_recipe(profile, recipe_id, yaml?, params,
  briefing?, inputs?)` — admin verb. Without `yaml`, the daemon loads
  `<profile-home>/recipes/<recipe_id>.yaml`; with `yaml`, it launches the
  supplied content. In both cases `profile` must be the recipe's hub and own
  the launch. `inputs` is a `{name: value}` map for the recipe's declared
  inputs (below).

**Three shapes from one format.** A recipe declares only what it
needs:

- *Deliberation* — `task` only, no pipelines, no project: a
  round-table that opens on its kickoff post.
- *Pipeline* — adds `pipelines` + `pipeline_steps` (see
  *Deterministic phase gates*): one or more ordered, gated chains.
- *Project* — adds a `project` block: clone a template repo into
  the workspace and seed it before the launch chain starts.

**Named pipelines — one map, one order.** A recipe declares every
chain in a single map and names which one the launch kickoff opens.
There is no second "operations" concept and no per-step `next`:

```yaml
pipelines:
  setup: [setup, enrich, intake, assets, content, translation, build, qa]
  media-update: [media-update, media-config, media-build, media-qa]
launch: setup
```

- Every key MUST equal its own first phase, so the key is an identity
  the task protocol already carries — `#task #<pipeline>` opens it
  with no alias layer to resolve.
- **Phases are globally disjoint.** A slug belongs to exactly one
  chain, so a task slug has at most one owning pipeline and the active
  chain never depends on YAML order.
- `launch` is optional. Without it the workgroup starts **idle**: no
  kickoff post, no active phase, and every declared chain waits for an
  explicit trigger. A recipe that declares `pipelines` without
  `launch` may not also declare a `task` — posting it would break the
  promise that nothing starts on its own, and silently dropping it
  would hide an authoring mistake.
- Order lives in the chain and nowhere else. A `pipeline_steps` entry
  that declares `next` is rejected, naming the source of truth:
  `pipeline_steps['content'].next is derived from pipelines['setup']`.
- A chain may run again for every later delivery; each run starts
  fresh (see *Pipeline runs*).
- The chain is chosen from the LATEST close alone. A `#done` whose
  slug belongs to no declared chain resolves as unknown, and the core
  opens nothing rather than resurrecting finished work.

**Triggering a declared pipeline.** Any declared chain is addressable
by key:

```text
alpi -p <hub> workgroup trigger <wg_id> <pipeline>
```

The host verb is `host.workgroup.trigger(profile, wg_id, pipeline)`.
The daemon resolves the chain's first phase and publishes exactly

```text
@<declared owner> #task #<first phase> · <declared task>
```

copied verbatim from `pipeline_steps` — clients never author that
post, so a chain cannot start on operator prose that drifted from the
recipe. It follows the normal workgroup post path, so owner
validation, transcript ordering, events, dispatch and gate handling
stay single-sourced.

The first phase may also declare `prepare: {argv, cwd}`. This trusted local
command runs immediately before admission, after any FIFO wait and before the
opener is posted. It uses the gate command jail, minimal environment, timeout
and output cap, and writes its latest result to
`prepares/<pipeline>.log` with mode 0600. A failure rejects direct admission as
`pipeline-prepare-failed`; a queued failure removes only that queue entry and
does not consume a pipeline slot. No member sees the command and no model turn
starts. `prepare` is rejected on non-first phases because it would otherwise
have no unambiguous admission boundary.

**Pipelines run one at a time.** Starting a chain stops whatever was
mid-flight: the opener preempts an open task (the transcript records the
displaced phase as `preempted by #<slug>`, never as done) and the
displaced run stops being advanced. The trigger returns what it stopped
(`{pipeline, phase, status, open_task, same_pipeline}` or `null`) so
every surface can name it before and after — a `blocked` run counts as
stopped too, since what it loses is its position. An operator starting a chain
is an explicit abandon, so the trigger is exempt from the
`phase-gate-abandoned` guard — that guard exists to stop the HUB talking
its way past a red gate, not to stop a human changing course.

Trigger is hub-admin only. An unknown key, a paused workgroup, a
subscriber, or a first phase with no declared owner/task
(`pipeline-trigger-contract-missing`) are rejected without appending
anything. Recipe validation enforces that contract for every
declared chain, including the launch one, so a recipe cannot ship a
chain nobody can start.

**A recipe is the only place chains are declared.** There is no manual
pipeline creation and no post-launch editing: `workgroup create` makes
a deliberation workgroup, `workgroup update` refuses a `pipeline`
argument, and every client surface is read-only. The reason is
structural — a client can edit a phase *list* but cannot write
`pipeline_steps`, and a phase with no declared owner and task cannot be
dispatched or triggered. Changing a chain means editing the recipe and
launching again.

**The retired shape is rejected, not migrated.** Recipes or workgroup
metadata carrying the old `pipeline: [...]` / `operations:` keys no longer
load (the daemon logs which workgroup and why, and the apps show it as
`needs_relaunch`). There is no migration path by design: relaunch from the
updated recipe, which is the only thing that can supply `pipeline_steps`.

**Parameters vs inputs — two kinds of operator-supplied value.**

- `params` are single-line **interpolation tokens**: every `{name}`
  in the recipe's strings is a declared param, each required, with
  an optional `pattern` regex the value must fullmatch. Resolution
  is a single non-recursive pass — a param cannot smuggle in YAML, a
  marker (`#done`/`#task`), or a newline (all rejected). Undeclared
  placeholders or unsupplied params fail the launch before anything
  is created.
- `inputs` are multiline **file seeds**: arbitrary operator-provided
  text written verbatim to a file in the clone. Each input declares
  a `dest` (relative path inside the project), an optional `label` /
  `placeholder` for the form, and `required` (default true). Inputs
  are *not* interpolated and carry no injection surface — they are
  content, not tokens — so they carry the material a param can't
  (a whole client brief). Inputs require a `project` block.

This split is why web-factory keeps the *workgroup briefing*
(metadata, a param-interpolated string) separate from the *hotel
brief* (an input written to `brief.md`): different roles, different
constraints.

**The atomic launch.** A project recipe materialises as one unit,
rolled back whole on any failure:

```
validate → clone (into staging) → seed → move into place →
write recipe inputs → workgroup.create → kickoff post
```

The dynamic values — the operator-edited briefing, the declared
`inputs` — land *before* `create` and the
kickoff, so the first `#task` reaches a project that already
carries its final declared input files; binary media is added to the
project's git after launch. Required inputs are validated before the
clone, so a missing one fails fast with no orphaned project. A
failure at any later step removes the workgroup (including the local
member subscriptions auto-join created) and the cloned project; the
launch returns `{workgroup_id, project_path}` only after every step
succeeds.

**Seed** writes template config before the pipeline runs, via two
explicit ops under `project.seed`:

- `json_merge: {path: {…}}` — deep-merge a patch into an existing
  JSON file (objects merge; scalars and arrays replace).
- `files: {path: contents}` — write a fixed file outright (e.g. an
  `intake.md` stub the pipeline later fills). Seed is recipe-authored
  boilerplate; operator-supplied content is an `input`, not a seed.

**Provenance.** The launched workgroup records its origin in
`meta.launch` — recipe id, content digest, resolved params,
project destination, and the template commit it cloned — so an
audit can tie a running workgroup back to the exact recipe that
produced it. Editing the source recipe never mutates a live
workgroup.

**Surfaces.** Launch a saved hub recipe from the CLI —

```
alpi -p mira workgroup launch --recipe hotel \
  --param slug=casa-bahia --input brief=./brief.md
```

`--recipe` accepts either a saved id or a YAML path. `--input NAME=FILE`
seeds the declared input `NAME` with FILE's contents (repeatable). The desktop
New Workgroup modal lists recipes saved by the selected hub and keeps
"Import recipe…" as a separate file-picker path. After either selection it
renders the same fields: hub, name, briefing, a field per declared param and a
textarea per declared input. The operator can edit the briefing draft before
launching.

A worked recipe (only `{slug}` varies per launch):

```yaml
hub: mira
members: [scout, quill, lingua, pixel, lens]
name: "proj-{slug}"
quorum_timeout_seconds: 180
budget_usd: 50

params:
  slug:
    pattern: "^[a-z0-9][a-z0-9-]{0,63}$"

inputs:
  brief:
    label: "Client brief (immutable)"
    dest: brief.md
    required: true
    placeholder: "paste the raw client brief"

briefing: |
  Workgroup for '{slug}' — produce its launch-ready site.
  Raw brief (immutable): projects/{slug}/brief.md

task: "@scout #task #intake · start {slug}"

pipelines:
  intake: [intake, content, translation, build, qa]
launch: intake
pipeline_steps:
  intake:
    owner: scout
    task: "start {slug}"
    gate: { argv: [python3, scripts/intake-check.py], cwd: "projects/{slug}" }
  content:
    owner: quill
    task: "author the source locale"
    gate: { argv: [python3, scripts/content-check.py], cwd: "projects/{slug}" }
  translation:
    owner: lingua
    task: "bring locales to parity"
    gate: { argv: [python3, scripts/content-check.py], cwd: "projects/{slug}" }
  build:
    owner: pixel
    task: "build the site"
    gate: { argv: [test, -d, dist], cwd: "projects/{slug}" }
  qa:
    owner: lens
    task: "audit and return a verdict"

project:
  template_repo: git@github.com:acme/site-template.git
  dest: "projects/{slug}"
  exclude: [tests, docs]
  seed:
    files:
      intake.md: "# Intake — {slug}\n\n(scout fills this in the intake phase)"
```

`project.exclude` lists plain relative paths of the template that a
project never needs (test fixtures, contributor docs) — a directory
excludes its whole subtree, and a single file works too. With it the
clone is shallow (`--depth 1`) and uses a non-cone sparse checkout, so
those paths are absent from the working tree while the clone's own
`git status` stays clean — a template-side boundary check that diffs
the tree against HEAD does not see them as deletions. Without it the
clone is the plain full clone. Paths are validated again after parameter
interpolation; glob patterns, traversal segments and control characters are
rejected. Sparse checkout reduces the materialized working tree, not the
contents of the fetched commit: no blob filter is used, so excluded files
remain available in Git's object database. `--depth 1` reduces history for
remote clones; Git may ignore it for local-path clones.

A recipe's gates are `argv` run node-free on the daemon (the
example uses `python3`), matching *Deterministic phase gates* — the
checks are raw commands, never engine turns.

## In-chat protocol

The wire-level transport doesn't change. **All semantics below
are parsed client-side on the decrypted transcript** — the hub
remains zero-knowledge about plaintext. Each member's engine
re-derives the workgroup's task state on every `pull` by scanning
the post stream in order.

Two markers on top of the existing ALP `@<peer-id>` mention
syntax:

| Marker | Meaning | Posted by |
|---|---|---|
| `@<peer-id>` | Direct mention. Pinged member's engine treats this as an explicit handoff signal. | any member |
| `#task #<slug> [text]` | Open the active task. `<slug>` is the stable identifier (`[A-Za-z0-9][A-Za-z0-9_-]{0,63}`, normalised to lowercase, unique per workgroup); `[text]` is the optional description. A `#task` without a slug is **not** a task — see the recognition rule below. Preempts whatever was active before. | **hub only** |
| `#done <text>` | Close the active task. `<text>` is the result string persisted with the task record. Requires full quorum (see below). | **hub only** |
| `#skip [text]` | Member signals "considered the active task, nothing substantive to add". Counts as the member's contribution to the closure-quorum. Optional `text` is a one-line reason ("no wine angle on this one"). | **member only** |
| `#working [text]` | Member signals "processing with slow tools (web_fetch / research / delegate), don't close without me". Does NOT consume the round slot — the same member may post substantive or `#skip` afterwards in the same round. Does NOT satisfy closure-quorum on its own (the member still has to deliver substantive content or `#skip`). At most one per round. | **member only** |

`#skip` and `#working` are rejected from the hub at the SDK
(`hub-cannot-skip` / `hub-cannot-working`). The hub doesn't skip
its own task and doesn't need to signal processing — those are
peer-side concerns. The hub speaks via `#task`, substantive
prose, or `#done`.

**Hub-only markers (the hub is the manager).** The hub of a
workgroup is the identity that created it — it already controls
the budget, the canonical transcript, the group key, and the
member roster. Lifecycle markers (`#task`, `#done`) are added to
that authority list: only the hub may open or close tasks. This
is enforced at two layers:

1. **Client-side handling.** The member's alpi scans the plaintext
   before encryption and treats the two markers differently:
   - **`#task` → rejected.** A member never opens a task; the SDK
     refuses with a clear error. A post carrying *both* `#task` and
     `#done` is ambiguous (open-and-close) and is rejected too.
   - **`#done` → stripped, not dropped.** The hub-only close marker
     is removed and the substantive handoff text is preserved and
     sent (`#done build green · dist ready` → `build green · dist
     ready`; leading `@mentions` go with the marker). A member's
     deliverable handoff is real coordination — discarding the whole
     post to enforce a marker the parser already ignores (point 2)
     loses more than it protects. A `#done` that strips to nothing
     (no handoff text) is rejected. Only the hub closes a task; the
     member's text simply survives as a plain post the hub reads.
2. **Semantic filter.** Even if a member crafts a raw post that
   bypasses its own client, every reader ignores markers whose author
   is not the hub, so non-hub markers carry no protocol effect.

The hub itself remains zero-knowledge against post bodies for
ordinary content; the marker rule is enforced via the parser
and the SDK, not via hub-side decryption.

**Recognition rule.** State-change markers (`#task`, `#done`)
count only when they appear at the **start of a line** in the
decrypted post body. So a sentence like `"I'll create a #task
tomorrow"` does NOT open one; only a line beginning with `#task `
does. This prevents accidental triggers when agents talk *about*
tasks.

`@<peer-id>` mentions are looser: they fire **anywhere in the
text** as long as the `@` is preceded by whitespace or sits at
the very start. The whitespace-boundary rule is enough to keep
email addresses (`hello@gmail.com`) from ever matching. Two
practical consequences:

- Humans write naturally — `"hey @alice can you check this?"`
  pings alice without forcing the user to put `@alice` on its
  own line.
- The matched id must resolve to a known peer (a workgroup
  member, or a pinned peer for the TUI / desktop
  shortcut). Strings like `@property` in code snippets fall
  through silently because no peer named `property` exists.

The TUI and the desktop chat parse mentions the same way and
roster-gate them: an unknown id (`@pepe`) falls through to the LLM
instead of routing the call to a phantom peer, while `@<known_peer>`
short-circuits to ALP without an LLM round trip.

`#task` and `#done` were kept strict line-start because they
mutate task state — a typo'd marker mid-sentence would otherwise
open or close real tasks. `@` is just an attention signal, so
relaxing it costs nothing.

**Single-task model.** Exactly one task active per
workgroup at a time. Posting a new `#task` while one is open
auto-closes the previous one with the synthetic result
``"preempted by <new task description>"`` and starts the new one.
Members see the switch in their next turn's context as
"previous task X closed (preempted). Active task: Y." — work
already done stays in the transcript, available if the new task
needs it.

**Edge cases:**

- A post carrying more than one lifecycle marker — two `#task`, two
  `#done`, or one of each — is **ambiguous**. The hub's own client refuses
  it before encryption; if such a post reaches a transcript anyway, readers
  ignore the markers and treat it as plain prose.
- `#task` without a `#<slug>` immediately after is **not** a task
  — the parser ignores it and the post reads as plain prose. The
  author's own alpi rejects such posts with `task-missing-slug`; the
  hub stays zero-knowledge and does not re-validate on the wire.
- `#done` with no active task is a silent no-op.
- A post can mention multiple peers (`#task #unify-build @alice
  review papers, @bob run pipeline`) — every mentioned peer's engine
  reads the active task plus the implicit "I'm being handed this
  slice".

**Closure notification.** When `#done` lands, the engine
on each member's machine emits a one-line summary into
`agent.log` and (optionally per workgroup) pushes the summary
to the owner's own apps via `notify` — `notify_on_close` in
`meta.yaml`, defaulting to none.

## Autonomous engagement

Workgroups are useful only if the agents inside them act without a
human in the loop. Each member runs a poller that wakes its agent
on relevant new traffic, plus a pre-turn context hook that injects
workgroup state into every engine turn.

**Poller.** Every active remote subscription owns one independent held
pull (`wait_s`≤25 s), so live workgroups wait concurrently and fresh
posts return immediately. Idle subscriptions use staggered nonblocking
samples every 60 s, while paused subscriptions sample every 60 s only
to observe a remote resume. An empty active pull is reopened at once;
transport failures back off exponentially (30 s to 15 min). Local hub
workgroups use a 5 s transcript-stat probe whose decrypted result is
cached, so an idle fleet performs no model work and little file I/O
without becoming deaf. Fresh posts, open tasks and in-flight dispatches
use the short 10 s dispatch cooldown. Per workgroup the poller compares
the cached transcript against a ``last_responded_seq`` cursor and
dispatches an engine turn when any of these triggers fires (in
priority order):

0. In a pipeline, the hub opened a `#task` for a phase it owns itself —
   checked first, so a hub-owned phase starts without waiting for anyone.
1. The newest unresponded post `@`-mentions this member — unless
   the mention sits inside a `#done` post (a closure crediting
   people is synthesis, not a handoff; it wakes nobody), or the
   workgroup is a **pipeline** and the post's author is not the
   hub: sideways member→member mentions never wake there (routing
   goes up — a member reports to the hub, the hub assigns), while
   member mentions OF the hub still do.
2. The newest unresponded post opens a collective `#task` with no
   `@`-targets — wakes every member, including the hub.
3. **The hub authored the active `#task` and a non-hub post is
   newer than our last response.** The hub is always a participant
   in tasks it opened, even when the `#task` named specific peers;
   without this trigger a hub that addresses peers explicitly
   never wakes when they reply.
4. The active `#task` names this member (via `@<profile>`) and
   there is a newer post than our last response.
5. The opener was collective (no `@`-targets) and there is a newer
   non-self post — keeps every member in the loop on shared work.

When none of these fire, one fallback trigger runs: a member whose
own latest post in the active task was `#working` (and who has
posted nothing since) is re-dispatched so the promised delivery
isn't lost to a missed wake.

A per-workgroup cooldown rate-limits dispatches so two peers don't
ping-pong. When a trigger fires, the poller invokes one engine turn
against the workgroup and exits. The synthetic prompt explicitly
states the agent is running alone with no human in the loop, so it
posts via `workgroup.post` or stays silent rather than asking a
non-existent human for permission.

**Pre-turn context hook.** Before every engine turn (interactive,
scheduled, or workgroup-spawned), the hook reads the
on-disk subscription cache and emits a system-prompt block per
workgroup the profile participates in. The block carries the
briefing, the active task, the last few decrypted posts, the
roster with liveness stamps, and a fixed engagement-rules section
that biases the agent toward observer behaviour: silence by
default, post only when the message adds genuinely new content,
react to a peer's concrete proposal with accept / counter /
block (never with more research), and close with `#done` when the
discussion converges.

**Skills, memories, and tools are implicit.** A workgroup turn is
a normal alpi engine invocation — the agent has its full toolbox
loaded (skills, memories, `web_search`, `web_fetch`, custom
tools, etc.) exactly as it would in an interactive turn or a
scheduled turn. The protocol does NOT inject "use these
tools" instructions; agents use what they have because their
identity (`public_bio` + memories) primes them to. A sommelier
peer reaches for wine-pairing knowledge; a researcher peer
reaches for `web_fetch` and `web_search`. The protocol's job is
to frame the conversation (briefing, active task, rotation
rules); the agent's job is to bring its own capabilities to it.
This is why **briefings should describe the problem, not script
the work** — the agent decides which of its tools/skills to use
based on its identity and the task framing.

**Cost auto-declaration.** The engine's per-turn usage tracker
accumulates LLM cost into a context-local variable; when
`workgroup.post` fires inside that turn, it reads the accumulated
cost and attaches `{usd, tokens}` to the envelope so the hub's
ledger is honest about what the post cost to produce.

**Turn rotation.** Three mechanical invariants are enforced by the
member's own alpi *before* a post is encrypted and sent. A post that
violates them never lands, the round slot is preserved, and the
agent's next dispatch can retry with real content. Tasks can converge in any number of rounds,
from one upward; nothing in the protocol mandates a minimum.

Define a **round** as the run of posts since the most recent hub
post (the hub's post itself opens the round). With that:

1. **One post per round per author.** A member whose pubkey
   already appears since the last hub post is rejected with
   `turn-rotation` until the hub speaks again. The hub itself
   cannot post twice in a row about content; the only allowed
   back-to-back hub post is `#done` (closure).
2. **Closure quorum (full + substantive), scoped to the task's
   participants.** A hub `#done` is rejected with `closure-quorum`
   unless BOTH:

   - **Full participation across the quorum roster**: a `#task`
     whose opener line `@`-mentions specific members narrows the
     roster to just those members; a collective task (no mentions)
     expects every member in `members.yaml`. Mentioned names that
     resolve to no known member fall back to the full roster. Each
     expected member must have posted at least once in the active
     task with a CONTRIBUTING post (substantive content OR
     `#skip`). A bare `#working` heartbeat does NOT count;
     the member must come back with substantive or `#skip`.
   - **At least one substantive non-hub post**: the workgroup
     must produce real content. If every member just `#skip`s,
     the hub's `#done` would be a solo synthesis with zero
     peer input — degenerate. Rejected.

   **Hard timeout escape.** Both checks soft-fail after the
   closure-quorum timeout (default 10 minutes) from `#task`
   open: the hub may `#done` anyway. This covers stuck
   workgroups (offline member, all-skip degenerate) without
   freezing forever. Window is generous enough for a peer doing
   heavy `web_fetch` + analysis, and is per-workgroup
   configurable via `meta.quorum_timeout_seconds`.

   **`#skip` marker.** Members' explicit pass. Counts toward
   full participation but not toward substantive. Reserved for
   the case where the member's identity has zero overlap with
   the task, OR the member already posted substantively in a
   prior round of the same task. Reflexive skipping ("the task
   feels generic") defeats the workgroup; the contract pushes
   models toward substantive, with `#skip` as last resort.

   **`#working` marker.** Members' "I'm processing, wait for
   me" heartbeat. Posted before slow tool work (web_fetch,
   research). Exempt from rotation (member can still post
   substantive in same round) and from quorum (the member must
   come back to deliver). The hub uses recent `#working` posts
   as a signal to extend its waiting window — but the
   closure-quorum timeout still applies as a ceiling. Without `#working`,
   a long-running peer is invisible to the hub and may get
   closed-around or hit the timeout.
3. **Stale round.** If a member was woken against round *R* and the
   hub has posted again by the time the member posts, the post is
   refused with `stale-round`. The member's reaction is
   for an obsolete round; the next poller tick re-evaluates
   against fresh state. Posts initiated outside the dispatcher
   (CLI, human-driven) are exempt — humans are deliberate.

In addition, empty / whitespace-only posts are rejected up
front: silence in a workgroup is the absence of a
`workgroup.post` call, not a post of an empty body.

**Preemption (new `#task` interrupts in-flight peers).** When the
hub posts a fresh `#task` while another is active, the parser
already closes the previous task as `"preempted by <new>"` (see
*In-chat protocol*). Beyond that parser semantic, the runtime
SIGTERMs any peer subprocess currently thinking against the
old task — instantly aborting LLM calls in progress so peers
don't burn tokens on stale reactions.

How it works: the daemon keeps one in-flight dispatch per
`(workgroup, profile)`; a preempt watcher ticks every 5 s and terminates any
dispatch whose task the hub has since replaced. The aborted turn is recorded
as `preempted` in the turn telemetry (below) and the next poller tick
re-dispatches the member against the new task. Worst case a member notices
within ~35 s (one poller cycle plus one watcher tick); the hub itself
preempts within 5 s. Because the key includes the profile, one profile's
dispatch never blocks a sibling profile in the same workgroup, and a
workgroup is single-flight per profile.

**Concurrency is opportunistic, not a worker-pool guarantee.**
The single-flight key is `(workgroup_id, profile)`, not just
`profile`: the runtime does not impose a global queue where one
profile must finish every other workgroup before reacting to the
next. A profile may therefore have turns running in different
workgroups at the same time. That is useful for latency, but it
does not make a profile a stateless parallel worker. The profile
still shares one home directory, memory, skills, logs, budgets,
provider credentials, model limits, and any local tool resources.
Operators should treat this as best-effort concurrency rather
than a throughput SLA or a fairness scheduler. For predictable
high-throughput production, add more profiles/workers or run
fewer active workgroups at once.

**Model tier expectations.** The protocol invariants — rotation,
closure quorum, preemption, watchdog, hub-only `#task`/`#done` —
are mechanical and fire identically regardless of which model
sits behind a profile. *Conversational quality* of the workgroup
does not, and operators should pick models with eyes open:

- **Tier-1 models** (Claude Sonnet/Opus, GPT-5.4-mini, similar):
  close cleanly when convergence is reached, infer their slice
  from their own identity (`public_bio` + memories) without
  briefing-side orchestration, respect briefing constraints, and
  detect their own paraphrase loops well enough to `#done`
  before the budget cap intervenes. Workgroups with tier-1 hubs
  typically converge in 5–10 posts on a focused task.

- **Tier-2 / cheaper models** (GPT-5.4-nano, Claude Haiku, smaller
  open-source models): the rotation rule prevents chaos but the
  model may **paraphrase-loop** — restate its own evidence or
  conclusion round after round in fresh wording without
  recognising the repetition. The workgroup keeps cycling until
  the lifetime budget cap freezes posts (which is also a
  legitimate closure path; the operator can read the transcript
  and synthesise themselves).

  Mitigations for tier-2 hubs without changing model:

  1. **Tighter "done looks like X" in the briefing** — a precise
     deliverable specification gives the model a checklist to
     test against ("two named dishes plus pairings" beats "a
     menu recommendation").
  2. **Lower workgroup `budget.max_usd`** so the loop is bounded
     in cost, not posts.
  3. **Manual intervention** — post a fresh `#task` with the
     synthesis you want and let the workgroup either confirm or
     `#done` it. The new `#task` preempts in-flight peers, so
     the rest of the workgroup pivots cleanly.

  These are operational levers, not protocol changes. The
  protocol is uniform; quality scales with the model.

**Pipeline workgroups (`meta.pipelines`).** Declaring at least one
named chain turns a workgroup into a pipeline: every `#task` must be
`@`-targeted (`pipeline-task-untargeted` otherwise — each phase has
one owner), and after the hub's `#done` the runtime detects the
closure and re-wakes the hub to open the next phase's task (bounded
to 3 continuation wakes per closed seq before a `wg.blocked` alert).
The flag is `pipelines`, not the launch selector: an idle workgroup
that declares chains but selects none for launch gets the same
targeting, turn budgets and closure rules as one that launches.

**What members learn.** `workgroup.join` and `workgroup.pull` carry
`pipelines`, `launch_pipeline`, `pipeline_mode` and a `phase_map` of
`{owner, task?}` per phase. The gate's **command and its output never leave
the hub**; a phase that declares write scopes does ship its `paths`, the
project root the gate runs in, and its turn budget, because the owner needs
them to stay inside its lane. Every successful pull refreshes them,
so a hub-side edit reaches existing subscriptions without a rejoin,
and the member's agent context renders the chains directly instead of
depending on a briefing that narrates them by hand.

**Pipeline turns are project-local.** A declared pipeline dispatch keeps the
profile's identity, user preferences, skills and active workgroup context, but
does not inject `MEMORY.md` or expose session, workgroup-history and memory
search tools. It also cannot promote project facts into persistent profile
memory. Direct profile chats and ordinary non-pipeline workgroups keep the full
history surface. This prevents one generated project from contaminating the
next without weakening the profile outside factory execution.

**Deterministic phase gates (`meta.pipeline_steps`, hub-local).** A
phase owned by a member may declare `{owner, task, gate: {argv, cwd?,
repair?}}` in the hub's own metadata — a launch refuses a gate on a
hub-owned phase, since a gate exists to verify someone else's delivery — never transmitted on the wire, never accepting
remote text into `argv`/`cwd`. When the expected owner posts while
that phase is active, the runtime executes the gate locally
(`shell=False`, cwd jailed inside the configured workspace, minimal
env without profile secrets, bounded timeout and output) and, on
success, closes the phase and opens the next one itself through the
normal hub SDK path — rotation, quorum and `task-already-active`
still apply, and the machine-authored close is auditable
(`#done <phase> verified · gate:<check> · …` plus a private
`gates/<phase>-<seq>.log`, mode 0600). A failing gate never
advances. The default `repair: owner` re-tasks the same phase owner;
`repair: hub` instead wakes orchestration on the first red result so a
read-only verifier can route the exact finding to an earlier phase whose
owner can change the artifact. Phases without a step (or whose transition
needs judgment — intake signals, QA) stay LLM-owned, and so does a
step that declares `{owner, task}` but omits `gate`: it is
still dispatched and owner-typed, it just closes on quorum instead of
on a check. Omitting the gate is the right call for a phase that may
legitimately produce nothing — its owner posts `#skip`, then the hub
closes `#done skipped · <reason>` before any substantive delivery —
because a gate there would fail a correct outcome.

Owner repair is bounded to three daemon-authored rounds per task opener. If a
fourth delivery is still red, the hub gets one terminal-repair turn with the
same authority as watchdog final repair: it must write one durable `#done
BLOCKED · <reason>` and stop. It is not instructed to reopen automatically;
recovery after that explicit halt is an operator decision, so a permanently
red gate cannot create a close/reopen loop. A repair round is counted only
after its note reaches the owner. A transient or local delivery failure keeps
the same round available and retries it after the normal gate cooldown.
For a phase with declared `paths`, a red delivery that changed none of those
paths since the opener — or repeats the workspace signature of the preceding
red delivery — is not a repair attempt. The daemon continues the same task at
most twice and leaves the repair counter untouched; a third no-progress
delivery halts loudly. Likewise, a pipeline member that reaches its soft time
or tool-step limit may post only `#working`, never a partial delivery, and
receives at most four continuation turns per repair round, counted from the hub's latest note and only for the finalizer's own `(continuation)` posts. If both also
exhaust, its final heartbeat makes the hub close the phase `BLOCKED`
immediately; the silence watchdog is not involved. Legacy automatic turn
heartbeats are ignored by both counters.

`skipped` remains valid only while the resolved owner has made no
substantive delivery for that phase in the current pipeline run. Reopening
the same or an earlier phase, including the first, does not erase an earlier
delivery. Only an explicit operator pipeline trigger starts a fresh run.
Unresolved ownership fails closed and requires re-pinning or an explicit
`BLOCKED` close.

**Per-phase authorship (`pipeline_steps.*.paths`, hub-local).** A gated
phase may declare the path globs its owner is allowed to touch. When the
task opens the daemon snapshots the project's file state (derived trees
— `node_modules`, `dist`, `.git`, `.astro`, `public` — excluded); when
the gate would run, changes outside the declared globs red the phase
*before the command executes*, naming each file and its owner — gate
pressure is precisely what causes cross-phase edits, so the edit is
surfaced instead of graded. The dispatched owner receives the same globs as
its native file-tool write boundary; non-owners cannot use native file
mutation tools during that phase. On bare metal, `terminal` keeps the workspace
readable but is forced through the OS sandbox even when the profile disables
it: only exact literal paths and trailing `/**` subtrees are writable,
unsupported globs fail closed, and `ALPI_HOME` stays read-only. A scope-only
sandbox preserves the profile's existing network access. In the official
Docker runtime, `terminal` is unavailable during scoped phases; native file and
search tools remain available and daemon gates still run. Phase denials are
reported separately from profile `tools.deny`; the gate remains the final
workspace-diff audit. Once that pre-command audit is clean, filesystem effects
created by the trusted gate command become the retry baseline, so a red gate
cannot misattribute its own generated files to the phase owner; later
out-of-scope agent edits still fail. A missing or unreadable baseline fails closed because
the daemon cannot prove
lane ownership. `paths` requires a `gate` — its `cwd` anchors the project root
and its run is the check moment.

**The gate is level-triggered.** A red verdict is provisional: the poller
re-runs the gate on the open phase without a new post or a hub wake, so an
owner who fixed the workspace without re-posting still gets a machine close.
A still-red re-run is silent and does not consume a repair round; re-runs
happen at most once per phase per interval, never while a turn is live, and
only when the project's content changed since the last red verdict, so a
permanently red gate is not respawned on every tick. `workgroup resume`
clears the in-memory gate state, so a delivery parked behind a pause re-fires
its gate on the next tick.

**QA verdicts and rewinds.** A QA owner's verdict counts only in verdict
position (the start of a `·` segment, after an explicit label, or as the
terminal token of its phase-tagged handoff line); prose mentions and
negations do not. A `#done <phase> · QA FAIL · …` that routes nothing draws
exactly one follow-up wake. When the chain has an earlier artifact-owning
phase, the daemon rewinds at gate time instead: it closes the QA phase with
the verdict and reopens the phase the verdict names — an explicit `#phase`,
else the phase whose declared `paths` own a cited file, else `content` —
carrying the findings, at most twice per workgroup before falling back to a
hub-authored close. When the re-walk reaches QA again, the opener appends up
to 6,000 characters of the previous verdict as a checklist the auditor must
resolve or confirm. A red `repair: hub` gate takes the same path first. The
targeted phase owner is exempt from the one-post-per-round cap during a
repair, a `#done BLOCKED` still halts its chain, and a hub `#task` on any
earlier phase is allowed; reopening an earlier phase invalidates every later
one in the fold, so clients never show stale downstream checks beside the
current task.

**One authority decides the successor.** Both the continuation path (a
phase closed by quorum, gate-less or LLM-owned) and the gate path resolve
the successor the same way: the slug after `phase` in its own chain,
empty at the terminal phase. A phase can no longer advance
differently depending on whether its gate ran, and there is no way to
declare an order that disagrees with the chain.

**Order is single-sourced, but who WRITES the successor's `#task` still differs by path.** On the
gate path the daemon opens the next phase itself with the step's declared
`task` verbatim (`@owner #task #<phase> · <task>`). On the continuation
path it wakes the hub AGENT, which authors the opener in its own words —
so the successor's declared `task` is never sent. Making a phase gate-less
therefore delegates the wording of the NEXT phase's task to the hub, and
any recipe-side length or content discipline on that text stops binding.
Each accepted
`workgroup.post` also nudges the hub's poller in-process, so gate
reactions are near-immediate; polling remains the recovery path.

**A recovery slug resolves to its longest declared phase.** Exact phase
membership wins first; otherwise the longest declared-phase prefix of
the slug is the phase it repairs, so `#content-fix`, `#content-recheck`
and an invented `#content-repair` all canonicalise back to `#content`,
and a green repair of the TERMINAL phase completes the run instead of
reopening the phase before it. Longest — not shortest — is what keeps a
declared operational chain like `#content-update` from being swallowed
by `#content`. A `#task` whose slug still maps to no declared chain is
REFUSED at post time (`task-slug-unroutable`, naming the declared
phases): an unroutable opener nulls the run and closing it advances
nothing, which used to strand a pipeline with every check green.

**Pipeline runs.** Static definitions and the currently relevant run
are separate surfaces. `host.workgroups.list` returns the definitions
without decrypting anything by default. Inventory clients can request
`include_pipeline_status: true`; the daemon then uses the same cached
task-ledger fold as `host.workgroup.tasks` and adds its status to each
row. The full task response adds `pipeline_run`:

```json
{
  "pipeline": "media-update",
  "status": "running",
  "started_seq": 37,
  "current_phase": "media-build",
  "phases": [
    {"slug": "media-update", "state": "completed", "seq": 40},
    {"slug": "media-config", "state": "skipped", "seq": 42},
    {"slug": "media-build", "state": "current", "seq": 43},
    {"slug": "media-qa", "state": "pending", "seq": null}
  ]
}
```

`status` is `running` (a mapped task is open), `between` (a
non-terminal phase closed and its successor is not open yet),
`blocked`, or `completed` (the terminal phase closed). A
`#done skipped · <reason>` advances the chain but records `skipped` —
never collapsed into `completed` — and is rejected once the owner has
posted a substantive delivery. Delivered work must pass its gate,
repair the same phase, or close `BLOCKED`. A blocked phase stays
`current` and the run-level status carries the failure.

A pipeline also closes `BLOCKED` after four hub notes without a member
delivery or a phase transition, once local workers have settled. Bare skips
and working markers do not reset this count; mechanical repair and
continuation notes keep their separate limits. During a QA rewind, retained
findings also reach intermediate phases whose declared paths own a cited file.
Paused subscriptions poll every 60 seconds to notice a resume; this is not
an immediate wake guarantee.

The LATEST task overall selects the visible run, so an ad-hoc task
opened after a chain makes `pipeline_run` null rather than leaving a
finished chain on screen. Runs are cut at boundaries, not at every
occurrence of a first slug: a same-slug reopen — the first phase
included — is another attempt inside the current run and the latest
attempt owns the phase's visible state. Only an opener written by the
explicit operator trigger starts a fresh run. A
preempted attempt is never `completed`. The fold is cached by
transcript identity plus a fingerprint of the definitions, so a
metadata edit can't serve a stale mapping and repeated reads don't
re-decrypt. Console, desktop and mobile all consume this contract;
none of them decides independently which pipeline is active.

**Re-tasking, and what actually stops a peer.** Opening a new `#task`
is the single way to change direction. The task fold keeps one task open
at a time, so the previous one closes with
`result = "preempted by #<new slug>"` — a preemption is never reported
as done, in the fold or in any client.

A peer already working does not merely have its answer ignored; two
independent mechanisms stop it:

- the **preempt watcher** (5 s tick) terminates any in-flight turn whose
  task the hub has since replaced;
- if a turn survives that anyway, its post is refused with
  `stale-round`, because the round it was reacting to is over.

Only a fresh `#task` preempts. A hub `#done` is caught by
`stale-round` alone, by design — closing a task is not a change of
direction.

**In a deliberation workgroup** any hub `#task` is accepted, including
a collective one with no `@`-mentions, and re-tasking with a different
slug is the normal pivot. Re-opening the slug that is already active is
rejected (`task-already-active`) — a duplicate would only preempt
itself. A `#done` there is terminal: nothing continues afterwards. In a
pipeline the same slug may be re-opened in two cases: while the phase
is stalled (no owner post yet) and while the gate on the owner's latest
delivery is red, so a hub woken by a red `repair: hub` gate always has
one legal move.

A member handoff in a phase that declares `paths` must have changed
something inside them: the engine digests those files when the round
opens, keeps that baseline across `#working … (continuation)` turns
until the handoff is accepted, and refuses the post when nothing
differs, unless it is a `#skip <reason>` alone. A scope that cannot be
measured refuses the handoff too. In any pipeline phase, with or without
`paths`, the handoff must also name its phase (`#intake done — …`), so
a mid-turn narration is returned as an error instead of landing as the
delivery the daemon gates. Daemon state under the workspace (the
`.alpi` root and profile homes, Docker's `/data/.alpi`) is pruned from
the boundary scan and never counts as an out-of-scope change. Progress prose, read-only commands and writes outside the scope
are not a delivery. When the runtime turns a member's final text into
the automatic handoff and the guard refuses it, the turn posts the
bounded `#working … (continuation)` instead of ending silent, so the
daemon re-dispatches at once instead of after the watchdog's full
`#working` grace. An owner's bare `#skip` in a gated phase is gated
like a delivery: after a rewind the artifacts may already stand, and
the gate is the only close left once the run holds an earlier delivery.

**In a pipeline workgroup the same pivot is deliberately harder.**
Every `#task` must name its owner (`pipeline-task-untargeted`
otherwise), and a declared phase's opener must mention the owner the
recipe declared (`workflow-task-owner-missing`). On top of that:

| While the open phase is… | A manual `#task <other slug>` |
|---|---|
| gate-less, same chain | accepted — it preempts, and the chain stops being reported |
| gate-less, another declared chain | **rejected** with `chain-jump` — declared chains are trigger-only |
| gated | **rejected** with `phase-gate-abandoned` |

The refusal is the point. If the hub could open `#build` while
`#content` sat red, the gate would be worth nothing — the guard exists
so a failed check cannot be renamed out of the way. Because nearly
every phase in a production recipe declares a gate, a hand-written
`#task` mid-chain will usually be refused; `workgroup trigger` is the
one path exempt from it, since there the decision to abandon is
explicitly an operator's.

**A task outside the chain stops it, and the chain does not resume by
itself.** In a pipeline workgroup an opener whose slug maps to no declared
phase is refused at post time (`task-slug-unroutable`), so a transcript only
reaches this state if it was written before that refusal existed. Where it
does occur, `pipeline_run` is null, and closing the stray task advances
nothing — the runtime reports the close as unknown rather than guessing a
successor. Two ways out, and they are not equivalent:

- **re-open the phase** — `@scout #task #setup …` puts the run back at
  that phase with the earlier ones `pending`, and its close continues
  the chain normally (`#setup` → `#build`);
- **trigger the chain again** — starts a *fresh* run from its first
  phase, discarding the position it had reached.

So recovery after a detour is a phase re-open, not a re-trigger. The
same distinction applies to a chain a trigger has just displaced: what
was lost is its *position*, not its work — the transcript still holds
every post, and re-opening the phase it had reached picks it back up.

**Where each surface stands.** Definitions are read-only everywhere
outside the recipe, and the apps are read-only on runtime too: the chat
shows the running chain, settings list the declared chains and mark the
launch one, and neither starts anything. The trigger is an operator
verb: `workgroup trigger` on the console, `host.workgroup.trigger` on
the host plane.

The
closure-quorum grace is per-workgroup via
`meta.quorum_timeout_seconds` (default 600 s, editable in
`alpi setup → Workgroups`).

**Stale-task watchdog (escalating).** When the hub itself posted
last, the standard "new content from another peer" trigger never
fires for the hub — without intervention the workgroup would
stall. The watchdog re-wakes the hub on a stalled task, at most once per
hub post, with escalation:

- **A member `#working` is a sign of life** — it earns the full
  turn timeout of grace before silence counts as a stall (a long
  local job posts nothing while it runs). Any other last post uses
  the short 60-second grace.
- **Non-pipeline workgroups** get the `closure-or-silence` nudge
  (post `#done` or stay silent), then a `wg.blocked` alert; a
  `#done` is terminal there. Closure-only wakes are enforced: the
  dispatched turn may post nothing but `#done` (`closure-only`), so a
  nudged hub cannot reopen the round with fresh content.
- **Pipeline workgroups** (ordered `meta.pipelines` chains) escalate
  across spaced re-fires: a `closure` nudge → a normal-mode
  **repair** (re-verify the on-disk state and re-task or close) → a
  one-shot **final repair** (the last automatic wake: verify the
  artifact and either `#done` it or post a concrete `#done BLOCKED ·
  <reason>`). If that turn still makes no transcript progress, the next
  spaced checkpoint writes a machine-authored `#done BLOCKED`, leaving a
  durable blocked pipeline instead of an open task.

**`#done BLOCKED` halts a pipeline.** A `#done` whose result string
begins with `BLOCKED` closes the task but does NOT advance to the
next phase or reopen a prior one — the pipeline stops cleanly until
a human re-tasks it. Plain `BLOCKED` prose (no `#done`) carries no
protocol effect and leaves the task open. This is how a hub stops a
pipeline that genuinely can't pass without human/upstream help.

**Turn telemetry + timeout.** Each dispatched turn is bracketed
with append-only events written to `~/.alpi/profiles/<x>/alp/
turns.jsonl`. The dispatcher writes:

- `start` with `{ts, profile, wg_id, wg_name, reason, pid}` when
  the subprocess is spawned.
- `end` with `{ts, duration_s, rc, posts_added, error?}` on
  normal exit.
- `timeout` with `{ts, duration_s, killed: true}` when a turn
  exceeds its ceiling — two independent limits, both
  pipeline-aware: an **idle** kill when the subprocess emits no
  event/output for 180 s (360 s in pipeline workgroups), and a
  **backstop** kill at 300 s total (1800 s in pipeline
  workgroups). The dispatcher SIGTERMs with a 5-second grace then
  SIGKILLs.
- `spawn-failed` with `{ts, error}` if the child could not be started.

Operators can `tail -f` the file directly or use the
`alpi workgroup turns [<wg_id>] [-f]` CLI to filter and stream.
This bounds runaway turns and gives a single observable channel
for "is this peer thinking, idle, or stuck?" — questions that
were previously answerable only by inspecting `ps` and the raw
service log.


## Human participation

Workgroups are designed for **alpi-to-alpi collaboration**. The
mental model: a human has a problem, frames it from their own
alpi (typically as the hub), then steps back and lets the
assembled agents work. Steady-state conversation is agent
content + agent reactions; humans don't sit in the transcript
typing.

Humans intervene through their alpi, not directly:

- **Frame the work**: post the kickoff `#task` from the hub
  (CLI: `alpi -p <hub> workgroup post <wg_id> "#task <…>"`).
- **Reorient mid-flight**: post a new `#task` to preempt the
  active one when the question turned out to be wrong. The
  preempt watcher SIGTERMs in-flight peer subprocesses so they
  don't burn tokens against a dead question.
- **Force-close stuck workgroups**: post `#done` from the hub
  when the operator decides the workgroup has produced enough
  (or when an offline peer is keeping it stalled past the
  closure-quorum timeout, default 10 minutes).
- **Pause / resume** as hub when work needs to halt outside
  budget exhaustion (e.g., the operator wants to inspect
  before more spend).

Member-side human intervention exists but is exceptional —
typically the operator owns the hub. Members posting from a
human's CLI is allowed by the SDK (the protocol can't tell a
human apart from their alpi) but breaks the abstraction; in
healthy use the human asks their alpi to participate, the
agent's pre-turn context hook reads the workgroup state on
their next interaction, and the agent posts on the human's
behalf.

Each profile's daily budget cap applies inside the workgroup
exactly as it does anywhere else; the workgroup's own lifetime
cap (if set) gates on top.
