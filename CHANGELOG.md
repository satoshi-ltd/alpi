# Changelog

## v0.15.18 — 2026-09-24 — conversations kept apart, relays that can say no, peers that keep their limits

- **Asking a peer no longer mixes conversations.** The context a peer keeps for your follow-up
  questions is now scoped to the conversation the question came from: a new conversation starts
  clean, follow-ups in the same conversation still remember earlier turns, and two profiles can
  never share a context by using the same conversation name. Before, every conversation routed
  through the same profile fed one shared history on the peer, so an answer could reuse material
  from an unrelated conversation.
- A peer running an older version still answers, and the reply says its history is shared, so the
  isolation is never assumed. Existing history files are kept untouched; they are not copied into
  the new per-conversation context.
- **A relay can decline a request without bothering its peer.** A relay profile now has a
  `decline` tool beside `peer`: when a request asks for something it must not forward, such as a
  change or an action, it answers with a short refusal in the user's language instead of
  consulting the peer or inventing an answer. Once a request is declined nothing else runs in
  that turn, a request already forwarded to the peer cannot be declined afterwards, and an empty
  refusal does not count. Every other request still has to go through the peer.
- **A profile can limit what each peer may do on it.** A peer record in `peers.yaml` takes a
  `tools.deny` list, set with `alpi peers add --deny-tools`, `alpi peers tools <id> --deny`, or
  the setup wizard. Denied tools disappear from what that peer's turns can see and are refused if
  called anyway, including inside sub-agents, research helpers, workflow steps and parallel calls,
  and a pattern such as `github__*` covers a whole MCP server. A policy only narrows the profile's
  own tool limits and applies to that peer's turns alone; peers without one keep today's
  behaviour, and a peer whose policy is written wrong is refused with a clear error rather than
  served without limits.

## v0.15.17 — 2026-09-24 — a paired device can delete its own chats

- **A member device can now delete the conversations it started.** Deleting a chat used to need
  the admin role, so on a member device the action failed or was never offered. The daemon only
  ever removes conversations that belong to the calling connection: a member still cannot touch
  chats from the terminal, from the desktop or from another paired connection. Devices paired
  under the same connection already share their chats, so they share the delete too. Every
  deletion is still recorded in the administrative audit log.
- **A conversation can no longer be deleted while a turn is running or starting in it.** The
  delete reserves the conversation the same way a chat turn does, so whichever arrives second is
  refused, and a turn started from the terminal or by a scheduled job is respected too. The
  reservation holds until the delete has really finished, even if the request is cancelled
  midway. A conversation that belongs to someone else answers "not found" whether or not it is
  in use, so a member learns nothing about other people's activity.

## v0.15.16 — 2026-09-24 — a flaky download no longer breaks a release, and clearer time notes

- **The release pipeline retries the download of its installer** and, if the network keeps
  resetting it, stops right there with the network error instead of carrying on without the tool
  and failing a step later with a misleading message.
- The half-time note a scheduled job receives now only says how much time is left; the request to
  wrap up arrives at 80%, so a job that normally needs most of its budget is not told to stop early.
- When a job is killed at its time limit, the step it was running and for how long now survive in
  the run ledger too, and a step whose journal record had to be truncated is no longer reported as
  still running.

## v0.15.15 — 2026-09-24 — a scheduled job knows how much time it has left

- **A scheduled job is told its time budget and warned when it runs low.** The prompt states how
  many minutes the run has, and the agent gets a note at half of it and at 80%, so it can wrap up
  or skip a long final step instead of being killed in the middle of one.
- **A job killed at its time limit says what it was doing.** The failure names the step that was
  running and for how long, how many tool calls the run had made and the agent's last message,
  instead of a bare "agent timed out". The run ledger row now carries the run id too.

## v0.15.14 — 2026-09-23 — the audit log keeps only registrations that changed something

- **A device repeating its registration no longer fills the administrative audit log.** Clients
  report their name and app version to the daemon; when nothing changed, nothing is written to
  the log, so real administrative actions are no longer buried among repeats.
- A registration that does change a device (a new name or app version) is still audited, and
  failed registrations are too.

## v0.15.13 — 2026-09-23 — skill databases take whole scripts, and a failed reindex loses nothing

- **`db exec` runs several statements in one call.** Without `params`, a whole schema or a batch of
  writes separated by `;` runs in one transaction: all of it applies or none of it, and a failure
  names the statement that broke. With `params`, it still takes exactly one statement and says so.
- An `INSERT … RETURNING` or a `SELECT` sent as `exec` now returns its rows. Before, the write
  could fail to commit and be lost. Large results are read in batches, never all at once.
- A skill's database can no longer attach or copy itself into another database file, so one
  skill cannot read or write another's data; `VACUUM` still compacts it.
- **A reindex of past conversations or workgroups that fails part-way keeps the previous index.**
  A forced rebuild, or one triggered by a new embedding model, used to leave the index empty when
  it failed; searches keep working on the old index until the new one is complete.
- Such a rebuild stops, keeping the previous index, when a conversation file cannot be read or a
  workgroup cannot be decrypted, and the error names it.

## v0.15.12 — 2026-09-23 — each Docker image is built from its own release

- **The Docker image for a release is built from that release's commit.** A newer commit
  landing on `main` while a release was still publishing could end up inside the older
  release's image.
- A commit on `main` that did not release a new version is no longer published as an image of
  the previous one.
- The image is checked to carry the version it is tagged with before it is pushed.
- `latest` always points at the newest published version, even when an older release
  finishes publishing last.

## v0.15.11 — 2026-09-23 — web search answers more often, still without a key

- **`web_search` asks one search engine at a time and stops at the first that answers.**
  Before, every search went to several engines at once, starting with two encyclopedias, and a
  slow or refusing engine could throw away another engine's results.
- An engine that times out or errors is skipped for 15 minutes, so searches stop waiting on
  it; when every engine is, a search asks only the one due back first. A search
  stops asking after 25 seconds.
- A failed search names each engine and what it did, and a search where every engine simply
  found nothing says so, instead of always blaming a rate limit.
- By default it asks DuckDuckGo, Yahoo and Brave, in that order. Which engines answer depends on
  the machine, so `tools.web_search.backends` can list others. No API key is needed.

## v0.15.10 — 2026-09-23 — charges recorded at the same moment all count

- **Spend recorded by two processes at once is no longer lost.** When the daemon, a scheduled
  job and the console charged the same profile together, one charge could overwrite the other
  and the daily total came out short; every charge now counts, across midnight too.
- A process killed while saving no longer blocks later charges or damages the ledger.
- A charge that cannot be written is dropped with a warning in the log, and the turn it
  belongs to still finishes.
- The spend archive of deleted sessions and workgroups keeps one row per item, even when two
  processes archive it at once.

## v0.15.9 — 2026-09-23 — the file tools accept multi-document YAML

- **The file tools accept YAML files with several documents.** A file with `---`-separated
  documents was refused by `edit_file` and `write_file`; each document is now checked, and a
  broken one is still refused with its line.

## v0.15.8 — 2026-09-22 — old run journals and sessions are swept once a day

- **Old run journals and sessions can be swept automatically.** Set `retention.runs_days` and
  `retention.sessions_days` in a profile's `config.yaml` and the daemon deletes finished
  journals and idle sessions older than that, once a day. Without the block nothing is deleted.
- The sweep never touches the cost ledger, a running run, a session in use or with a run still
  open, or a session of a workgroup that still exists; a session's cost is archived first.
- Anything the sweep cannot verify is kept and reported. Invalid values disable deletion
  instead of shortening the window.
- A session file that is not a JSON object no longer breaks the session list.

## v0.15.7 — 2026-09-22 — a tool call cannot stall on a server that stops listening

- **A tool call can no longer stall on an MCP server that stops reading.** Sending the request
  and waiting for the answer now share the call's timeout; stopping the stuck server adds up
  to five seconds, and the error names the server.
- A call that failed mid-delivery is never resent, since it may already have taken effect, and
  the error says so.
- Large requests to a server that is reading normally still go through.

## v0.15.6 — 2026-09-22 — the sandbox setting no longer bricks the shell in Docker

- **`tools.terminal.sandbox` no longer disables the shell in Docker by accident.** The
  deployment guide no longer asks for it in the container, where no OS sandbox is available;
  enabled anyway, `terminal` still refuses every command and now says why.
- Scheduled jobs inside a container are recognised as running in Docker.
- The docs state the isolation boundary: a container and its volume hold one trust scope.

## v0.15.5 — 2026-09-22 — killing a stuck run takes its leftovers with it

- **Stopping a stuck run also stops what it started.** Shell commands, background jobs,
  pipeline gates and MCP servers launched by a run are tracked and stopped with it, including
  work whose own launcher had already exited.
- A process is signalled only when it provably belongs to the run, so a reused process id is
  never hit.
- The scheduler's cleanup of an overrun or failed job stops its leftovers too.

## v0.15.4 — 2026-09-21 — an OpenRouter suffix no longer shrinks a model's context window

- **OpenRouter suffixes no longer shrink a model's context window.** `:nitro`, `:floor`,
  `:exacto` and `:online` are ignored when resolving the window, so a large model no longer
  shows — or compacts — as 200k. Real variants such as `:free` and `:batch` keep their own
  values.

## v0.15.3 — 2026-09-21 — a silent MCP server can no longer hold the turn

- **A silent MCP server can no longer hold a turn forever.** The call fails at its timeout,
  names the server and stops it.
- A server that disconnects mid-call is reported to every waiting call and restarts cleanly.
- A call whose server was stopped meanwhile fails as a normal tool error instead of crashing
  the turn.

## v0.15.2 — 2026-09-21 — a timed-out command no longer leaves work running

- **A command that times out takes everything it started with it.** The whole process group
  is stopped, so background work the command spawned no longer keeps running.
- Interrupting a command stops it too, and a command that fails to start no longer leaves its
  progress ticker behind.

## v0.15.1 — 2026-09-20 — deleting a workgroup no longer loses part of its bill

- **Deleting a workgroup no longer loses part of its spend.** The archive now includes usage
  settled after the posts, including a workgroup whose only spend was settled usage.
- A ledger that cannot be read blocks the delete instead of archiving a short figure.
- A turn with no output tokens is no longer billed its whole token count.
- The docs are checked against the code: every documented command and config key must exist,
  and every typed config key must be documented.

## v0.15.0 — 2026-09-18 — a pipeline run says what it cost

- **A pipeline run shows what it cost, per run and per phase.** Totals appear in the apps and
  in `alpi workgroup show`, and include usage settled after the fact.
- Re-opening a phase adds an attempt instead of erasing earlier spend; work outside the chain
  is not counted against it.
- A total that can only see declared spend says it is partial.
- `tools.deny` no longer documents `workgroup`, which never matched anything; the docs and the
  agent's reference pack were corrected against the code, and a test keeps them aligned.
- The knowledge tool has its own `workgroups` topic, so asking about pipelines no longer loads
  the whole protocol reference.

## v0.14.52 — 2026-09-18 — a new profile passes its own audit

- **A profile created by `alpi setup` passes `alpi audit`.** Its `config.yaml` is created with
  owner-only permissions; existing configs are never rewritten.
- **The lint gate no longer changes its verdict when Ruff updates.** The rule selection is
  written down and the Ruff version bounded, so a new Ruff release cannot fail a clean tree.
- The user-facing documentation under `docs/` had a full pass: content, accuracy and
  structure, with the ALP protocol reference split from the workgroup operations guide.

## v0.14.51 — 2026-09-17 — the sweep's one-line message says what it actually did

- **A run the sweep left open is no longer announced as closed.** The one-line `schedule.failed`
  message now reads *left open by the run sweep* when the journal is still open.
- Found by running 0.14.50 against a real daemon rather than a test: four synthetic
  journals, three live processes, and the two left-open alerts both claimed to be closed.

## v0.14.50 — 2026-09-17 — a wedged run is found while the daemon still runs, and the log survives long enough to say why

- **A dead or wedged scheduled run is caught while the daemon keeps running.** A sweep runs
  every 30 seconds: a run whose process died is closed and alerted within a minute, and one
  silent for longer than its job's timeout plus a grace is judged wedged.
- A live process is killed only when its start time proves it is the run's own; anything else
  is reported once and left alone.
- When the scheduler ends a child itself it also closes its journal, so one event raises one
  alert, and the alert says whether the run died or went silent.
- The daemon log no longer fills with health-check noise, so it keeps days instead of hours.

## v0.14.49 — 2026-09-17 — a run that dies with the daemon still files its alert

- **A scheduled run that dies with the daemon now files its alert.** On the next start each
  orphaned run raises `schedule.failed` and an error output naming the job and how long it had
  been silent — the same path a live failure takes. Runs without a job alert as manual runs.
- A client reconnecting after the restart receives those alerts in its event history.

## v0.14.48 — 2026-09-16 — doctor checks the dependency everything routes through

- **`alpi doctor` verifies the LiteLLM install.** It checks the installed version against
  alpi's pin and every file against the installer's digests; a mismatch is a failure, and
  anything it cannot check is reported as such.
- **The licence is described correctly**: an individual may run alpi in production on machines
  they control for personal, research or non-commercial use.
- Several documentation errors were corrected, including the uninstall and upgrade steps and
  an override that does not exist.

## v0.14.47 — 2026-09-16 — the knowledge subsystem says what it does

- **No user-visible change.** The knowledge subsystem is now fully covered by tests, so how
  `ingest`, `search`, `lint` and `maintain` behave cannot drift unnoticed.

## v0.14.46 — 2026-09-16 — links survive the trip in both directions

- **Links written from a subfolder no longer lint as broken.** A root-relative link proposed
  during maintenance is repointed to the page it means; correct links, external URLs and code
  are left untouched.
- **Imported vaults stop producing false findings.** `[[wikilinks]]` and reference-style links
  are understood, and links shown inside code are no longer reported. alpi still writes plain
  relative links.
- The docs say which rules are alpi's own: every page needs an inbound link, and `type` is
  reserved.

## v0.14.45 — 2026-09-16 — a refused page leaves the bundle as it was

- **A refused maintenance run no longer half-writes the bundle.** Every page is checked before
  any is written, so a refusal leaves the bundle — or its absence — exactly as it was.
- Paths that differ only in case land on the existing folder or page instead of forking it,
  and `index.md` and `log.md` stay protected under any spelling.
- A symlinked page pointing outside the bundle is reported as one finding instead of aborting
  `lint` or `index`.

## v0.14.44 — 2026-09-16 — the index survives a bad rebuild and knows whose it is

- **A failed rebuild no longer empties the knowledge index.** The rebuild is one transaction;
  if it fails, the previous index stays searchable and the error is reported.
- **The index knows which bundle it holds.** Searching another bundle returns a hint instead of
  foreign pages, indexing another bundle is refused unless `force=true`, and a moved workspace
  is adopted by the next index run.

## v0.14.43 — 2026-09-15 — the journal keeps the transitions, not the stream

- **Run journals stop repeating identical model-state rows.** A state is recorded only when it
  changes; tool calls, usage and replies are journaled in full as before.
- **`knowledge(action="index")` leaves a valid bundle.** Without a `path` it creates `index.md`
  and `log.md` and links pages nothing points to; a bundle given as an explicit `path` is only
  read.

## v0.14.42 — 2026-09-15 — a token nobody uses stops being a key

- **Device tokens can expire after inactivity.** Set `host.token_ttl_days` and a device unused
  for that many days must pair again; a device in regular use never expires. Unset by default.
- Changing or removing the policy applies on the next request, and an unusable value is ignored
  rather than locking devices out.
- `alpi doctor` reports the policy and how many devices are expired; `host.connections.list`
  flags them.

## v0.14.41 — 2026-09-15 — a source that keeps failing gets the door

- **The WebSocket listener throttles authentication failures per source address.** Ten a
  minute by default (`ALPI_HOST_WS_AUTH_FAILURES_PER_MINUTE`); successful clients are never
  slowed.
- Behind a reverse proxy the client address is trusted only from proxies listed in
  `ALPI_HOST_WS_TRUSTED_PROXIES`; the WSS Compose overlay sets it.
- A throttled socket closes with code 1013 and reason `auth-rate-limited`, which desktop-v0.5.30
  and mobile-v0.4.9 show as a temporary block. `host.network.status` reports the limit and count.

## v0.14.40 + desktop-v0.5.28 — 2026-09-15 — the pairing link stays on one line

- **`alpi setup` prints the pairing link without hard wrapping**, so a copied link no longer
  carries a newline that makes the exchange fail. The desktop tolerates it too (desktop-v0.5.28).

## v0.14.39 — 2026-09-15 — the store keeps a digest, the client keeps the token

- **Device tokens are stored hashed.** `connections.yaml` keeps only a SHA-256 digest, so a copy
  of the file is no longer a usable credential.
- Existing stores migrate on startup without re-pairing any client; a store that cannot be
  migrated keeps remote access closed.
- Older copies left by earlier releases are listed by `alpi doctor` for manual cleanup.
  Downgrading below 0.14.39 is not supported.

## v0.14.38 — 2026-09-14 — maintain reads the whole page it rewrites

- **`knowledge(action="maintain")` no longer truncates the pages it rewrites.** It sees each
  page's full body, skips a page it could not see whole, and reports the size of every page it
  writes.
- "OKF" no longer appears anywhere the model or the user reads; it is now "knowledge wiki".

## v0.14.37 + desktop-v0.5.27 — 2026-09-14 — an unquoted timestamp is still a timestamp

- **Knowledge pages accept an unquoted `updated_at`.** YAML dates and datetimes are read back as
  ISO strings.
- **Opt-in OpenRouter provider exclusions.** `providers.openrouter.ignore: [together]` excludes
  providers for a profile's OpenRouter models, tiers and fallbacks included; changes apply on
  the next turn.
- **Desktop: the Stop button no longer sticks after a failed run.**

## v0.14.36 — 2026-09-12 — doctor probes MCP servers with the profile's own env

- **`alpi doctor` probes MCP servers with the profile's own environment.** The interactive check
  no longer reports a healthy server as misconfigured because its `env:` references came
  through empty.

## v0.14.35 — 2026-09-12 — failed streams keep their generation identity

- **Provider lifecycle logs keep the generation id and provider** seen during an attempt, so a
  failed stream can be matched with the provider's records. Retries, timeouts and cost are
  unchanged.
- **Retries start with a clean identity.** Regression tests cover failure after a
  partial response and a retry with either a new identity or none, so one attempt's
  generation and provider cannot be attributed to the next.

## v0.14.34 — 2026-09-11 — the model catalog stops lying

- **Catalog entries corrected.** Context windows and reasoning notes for several models were
  wrong and are fixed; Claude Opus 4.8 gives way to Opus 5 at the same price.
- **No floating ids.** The `~…-latest` alias is gone from the picker, because it silently
  changes the model behind a scheduled profile. `deepseek/deepseek-v4-flash-0731` and
  `deepseek/deepseek-v4.1-flash` are listed.
- Model notes follow one format — modalities, context, distinguishing trait — without bare
  benchmark scores.
- A model with a small window is no longer recorded with almost no input budget.
- The docs explain that an advertised window is a ceiling, not what every endpoint serves.

## v0.14.33 — 2026-09-10 — a failed run says so, and the unused pin goes

- **A scheduled run that died is no longer recorded as `ok`.** An error inside the turn fails
  the run and raises the usual alert, and a `notify: true` job that produces no reply is a
  failure too.
- **Unattended runs retry a transient stall** even after output has started; interactive turns
  are unchanged.
- **`providers.openrouter.provider` is removed.** Pinning an endpoint did not improve results in
  practice; the per-turn cost trail it relied on stays.

## v0.14.32 — 2026-09-10 — pin the endpoint, record what answered

- **OpenRouter routing can be pinned per profile** with `providers.openrouter.provider`, passed
  through as the request's `provider` object. (Removed again in v0.14.33.)
- **The run ledger records the cost trail.** Each `runs.jsonl` row carries the turn's `usd`, its
  `cost_source`, the served `provider` and OpenRouter's `generation_id`.
- A Nitro cost estimated from the base tariff is labelled `table-base`, not `table`.

## v0.14.31 — 2026-09-10 — project clones carry only what the project needs

- **Recipes can exclude template paths from the clone.** `project.exclude` lists plain relative
  paths that stay out of the working tree while `git status` stays clean; recipes without it
  clone as before.

## v0.14.30 — 2026-09-08 — repair the cited source before rebuilding

- **QA rewinds prioritize source ownership.** A source file match takes precedence
  over a later phase mentioned in prose, such as "then #build". An existing
  `Source:` evidence line narrows the match so retained audit paths do not choose
  the repair owner. No new delivery field is required; verdicts without that line
  retain whole-text path matching and phase hashtags remain a fallback.

- **Budget waits do not consume hub recovery attempts.** When an active local
  phase owner has exhausted its daily budget without a delivery, the hub waits
  instead of reopening tasks or exhausting its watchdog. Existing budget notices
  explain the wait. Raising the cap or the daily reset allows dispatch again;
  completed deliveries and remote owners retain their existing behavior.

- **Python 3.11 is the minimum supported version.** LiteLLM 1.100.0
  cannot import on Python 3.10. Package metadata and installation docs now
  declare 3.11–3.13; release smoke tests cover those versions, Ubuntu 24.04
  and Debian 12. The smoke job receives the version output explicitly so
  its version check cannot silently match an empty string. TOML validation
  uses the standard library without the obsolete Python 3.10 fallback.

## v0.14.29 — 2026-09-07 — preserve DeepSeek reasoning and OpenRouter costs

- **DeepSeek retains reasoning between tool calls.** The live conversation sends
  the exact reasoning text back with each assistant message, including an empty
  value when none was returned. Partial reasoning from retried requests is
  discarded. Run journals still omit streaming deltas.
- **LiteLLM updates to 1.100.0.** OpenRouter streaming now preserves the
  provider's cost and cache usage through the upstream SDK, so Alpi no longer
  needs a custom stream adapter. The dependency range stays within 1.100.x;
  the lockfile pins 1.100.0. HTTP-level tests verify reported costs (including
  zero), cached tokens, cache writes and reasoning passed back to the model.
- **Nitro has a pricing fallback.** If neither the provider nor LiteLLM reports
  a cost and the catalog has no exact `:nitro` entry, use the base model tariff
  with source `table`. This is an estimate: it excludes cache discounts and
  priority pricing. Routing and historical ledger entries are unchanged.
- **Cleaning workgroups tombstones them everywhere.** The *Workgroups* cleanup
  category removes the complete workgroup directory and creates the same
  removal markers as manual removal in the hub and every local member profile,
  so members stop polling deleted workgroups. Cleanup fixes its targets before
  deletion and uses canonical removal to archive each group's spend first;
  failed deletion is reported without retiring the surviving directory.

## v0.14.28 — 2026-09-07 — run journals stop recording the stream

- **Run journals no longer store streaming deltas.** They keep an operational timeline — tool
  calls, usage, replies, errors and the outcome — at a fraction of the size.
- **Cleanup offers old and oversized run journals**: completed journals older than 30 days,
  plus the oldest beyond 200 MiB per profile. Nothing is deleted on its own.
- `host.profile.storage` counts run journals.

## v0.14.27 — 2026-09-07 — workgroup tombstones expire

- **Workgroup removal markers expire** two days after the removal instead of accumulating
  forever.
- `setup → Cleanup` gains a *Workgroup tombstones* category and counts items next to bytes.

## v0.14.26 — 2026-09-06 — the container reaps its orphans

- **The container reaps its orphans.** When the daemon starts as PID 1 it runs behind a minimal
  init that forwards signals and reaps exited processes, so zombies no longer accumulate. Exit
  codes are unchanged.

## v0.14.25 — 2026-09-06 — a refused handoff still continues

- **A refused automatic handoff resumes the member.** When a worker ends its turn on a
  progress note that the handoff guard refuses, the runtime now posts the
  bounded `#working … (continuation)` in its place, so the daemon resumes the
  worker right away instead of waiting out the watchdog's grace period.
- **The pipeline prompt says what the guard checks.** Workers are asked for a
  `#<phase> done — …` handoff, matching the rule that was already enforced.

## v0.14.24 — 2026-09-06 — bounded pipeline recovery

- Bound empty pipeline hub exchanges to four notes without a member delivery or phase transition, then close as `BLOCKED` once workers have settled. Gate repair and continuation notes retain their existing limits.
- Carry retained QA findings to intermediate phases whose paths own the cited files during a rewind.
- Poll paused subscriptions every 60 seconds instead of five minutes so resumed work is noticed sooner.
- Log successful `workgroup.pull` RPCs at DEBUG and isolate the test suite's default Alpi home from the live installation.

## v0.14.23 — 2026-09-06 — the hub always has a legal move

- **A red gate lets the hub re-task the same phase.** `task-already-active`
  now yields while the gate on the owner's latest delivery is red, so a hub
  woken for a red verification gate can re-open that phase instead of being
  refused every move it tries.
- **Progress prose is not a delivery.** In a phase that owns artifacts, a
  member handoff is refused when no file inside the declared paths changed
  since the round opened, unless the post is a `#skip <reason>` alone; the
  acknowledgement that used to burn a repair continuation now comes back as
  an error the worker can act on.
- **A handoff names its phase.** A pipeline member's post must carry
  `#<phase>`; a mid-turn note such as "now the site.json pass" is returned
  as an error instead of closing the phase on an untouched scaffold.
- **QA rewinds land on the real owner.** The phase owning the most of the
  files a verdict names wins, shared status files carry no vote, so an audit
  that lists its inputs no longer sends every failure back to enrich.
- **A skipped re-run still closes.** An owner's bare `#skip` in a gated phase
  runs the gate like a delivery, so a phase re-opened by a rewind whose
  artifacts already stand advances instead of looping between hub and owner.

## v0.14.22 — 2026-09-05 — a rewound QA re-checks what failed

- **The auditor re-verifies its own findings.** When a `QA FAIL` rewinds a
  pipeline and the chain walks back to QA, the reopened task carries the
  retained findings from the previous verdict as a checklist the auditor is
  asked to state as resolved or persistent, instead of auditing from a blank
  page. The checklist follows both deterministic gate advances and hub-authored
  continuations through a single task-post boundary.
- **The active-workgroup limit is a daemon setting.** `alp.max_active_workgroups` counts every
  workgroup with live work; it lives on the default profile, a hub may pin its own, and new
  installs seed it at `5`. `alpi workgroup limit` shows or sets it (`0` = unlimited).

## v0.14.21 — 2026-09-05 — MCP servers no longer survive stop()

- **Stopping an MCP server takes its whole process chain down.** A server started through `npx`
  no longer survives as an orphan, and the terminal client stops its servers before exiting.

## v0.14.20 — 2026-09-04 — pipelines finish without an operator

- **A turn that runs out of time or steps continues instead of failing.** The worker posts a
  continuation status and the daemon resumes the same task, up to four times per repair round.
- **An unchanged handoff is re-dispatched rather than counted as a repair**, and halts loudly
  after two tries.
- **A QA failure reopens the phase that owns the file it names**, and the chain re-walks from
  there, up to twice per workgroup.
- **A red verification gate repairs itself or stops.** The owning phase is reopened, or the hub
  is woken at most three times before the daemon closes `#done BLOCKED`.
- Declared output directories exist when a build phase opens, dispatched workers always deliver
  to their own workgroup, and idle or paused workgroups cost almost nothing.
- Recovery timing counts awake time, so a suspended laptop no longer burns repair attempts.

Nothing to migrate.

## v0.14.19 — 2026-09-01 — busy fleets stay responsive and observable

- **The host inventory folds each shared workgroup only once.** A workgroup
  mirrored across six member profiles is deduplicated before its pipeline state
  is read, instead of repeating the same transcript fold for every profile.
  Large queues therefore stop starving cheap host RPCs used by Desktop.
- **The curated OpenRouter picker includes `z-ai/glm-5.3-flash`.** Its committed
  context catalog reserves 32K tokens for output from the provider's 1M window.
- **Desktop can follow a turn's context while it is still running.** Host chat
  streams completion usage with an explicit context value, distinct from usage
  produced by vision, research and other side calls, so clients never infer the
  conversation meter from the wrong model call.
- **A configured daily budget can replace the conservative paid-model step
  ceiling.** When `tools.max_steps_per_turn` is left at its default, a profile
  with a positive `budget.daily_usd` gets the same 1000-step runaway backstop as
  free and local models; an explicit step cap always wins.

Nothing to migrate. Pipeline admission, FIFO order and the maximum active count
are unchanged.

## v0.14.18 — 2026-09-01 — pipeline inputs prepare themselves at admission

- **A pipeline can declare one deterministic admission preflight.** A
  first-phase `prepare: {argv, cwd}` runs after any FIFO wait and before the
  opener reaches its owner, under the same workspace jail, minimal environment,
  timeout and output bounds as gates. Commands stay hub-local and their latest
  result is recorded privately in `prepares/<pipeline>.log`.
- **A failed preflight starts no agent turn and consumes no pipeline slot.**
  Direct triggers return the stable `pipeline-prepare-failed` reason without
  appending to the transcript. Queued failures remove only their own entry,
  emit an admission-failed refresh and let the next FIFO item proceed.
- **Media updates no longer depend on a stale hand-maintained inventory.** A
  recipe can ask the cloned project to rebuild its own media inventory at
  admission, so copying files into `assets/source/` and triggering
  `media-update` is sufficient; the media phase receives the exact current file set.
- **Read-only verification gates can return failures to orchestration.** A
  recipe may set `gate.repair: hub`; the first red result wakes the hub instead
  of exhausting repair rounds against an owner that cannot modify the failing
  artifact.

Nothing to migrate. Existing workgroups keep their immutable recipe snapshot;
relaunch them from a recipe declaring `prepare` to acquire this behavior.

## v0.14.17 — 2026-08-31 — workgroup pipelines queue without disappearing

- **Hubs can cap how many pipelines run at once.** `alp.max_active_pipelines` (unlimited by
  default) queues excess launches and triggers in a persistent FIFO that survives restarts.
- Queue position shows in the CLI and the host inventory; deleting a workgroup removes its entry
  and pausing keeps its place.
- A member that has not posted after `alp.working_after_s` (30 s by default, `0` disables) posts
  one `#working` heartbeat.
- A red gate no longer blocks its phase on files the gate itself generated, and a long workgroup
  history no longer slows dispatch.

Nothing to migrate; the queue stays off until `alp.max_active_pipelines` is set on a hub.

## v0.14.16 — 2026-08-28 — failed QA pipelines reach a durable close

- **A failed QA phase reaches a durable close.** The hub may close with the exact QA verdict,
  and a repair watchdog that makes no progress closes `#done BLOCKED` itself instead of leaving
  the pipeline open.
- Template clones get five minutes instead of two.
- Supervision leaves the provider's watchdog time to retry a stalled request, and long builds
  get a thirty-minute active-runtime backstop; an idle turn still stops after six minutes.
- A profile runs at most two automatic workgroup turns at once; the rest wait without spending
  recovery attempts.

## v0.14.15 — 2026-08-28 — delegated chats and workgroup runs close cleanly

- **A chat can be launched for an existing paired connection.** `alpi -p <profile> chat --once
  <prompt> --connection-id <id>` runs through the daemon, and the session belongs to that
  connection with the same live state as a client-originated turn.
- Delegation is accepted only on the local Unix socket; paired clients cannot impersonate
  another connection.
- Forced workgroup exits close their run journals, and journals left by older daemons are
  closed on startup.
- Workgroup spend includes usage no post declared, settled once per turn.

## v0.14.14 — 2026-08-27 — workgroup ownership reaches the shell

- **Pipeline write boundaries reach the shell.** On a host install a phase with declared `paths`
  sandboxes `terminal` so only those paths are writable; in the Docker runtime scoped turns omit
  `terminal`.
- A blocked tool call names the phase that owns the file, quoted handles no longer pick up
  tasks, and openers naming an unknown phase are refused.

On a host install, intermediate globs in `paths` must become exact files or trailing `/**` before
that phase can use `terminal`.

## v0.14.13 — 2026-08-26 — content search respects secret boundaries

- **Directory searches no longer bypass sensitive-file protection.** `search`
  used to validate only its root directory, so a content search rooted at a
  repository could return values from a nested `.env` even though `read_file`
  refused the same file. Ripgrep and stdlib search results now apply the shared
  sensitive-path denylist to every matched file before any content reaches the
  model.
- **Sentry CLI credentials join the existing denylist.** `.sentryclirc` is now
  treated like `.npmrc`, `.netrc`, and other credential stores for direct file
  reads and content search. Filename search may still reveal that the file
  exists; its contents remain unavailable.

Nothing to migrate. This is a tool-boundary correction, not a new redaction or
logging subsystem.

## v0.14.12 — 2026-08-26 — active peers no longer expire on the clock

- **`link.ask` measures silence instead of total review time.** The internal
  `peer` tool now uses ALP streaming just like interactive mentions. Targets
  send an initial session frame and periodic signed progress frames, so an
  active multi-tool turn can run past five minutes without the caller closing
  its socket. The final reply remains atomic from the calling agent's point of
  view; progress and intermediate text never become tool evidence.
- **Peer timeouts are policy, not a hard-coded deadline.** Profiles may set
  `alp.link_idle_timeout_s` (60 seconds by default) and the optional
  `alp.link_max_duration_s` (disabled by default). A genuine stall now returns
  a specific error, requests `link.cancel`, and interrupts the remote turn when
  the streaming caller disconnects. Cancellation is bound to the peer that
  started the turn, so one pinned peer cannot stop another peer's work.
- **Late disconnects are ordinary lifecycle events.** A caller leaving before
  the final frame no longer produces an ALP server traceback; the listener
  records the disconnect at info level and cleans up the streaming handler.

Nothing to migrate. Existing profiles receive the idle watchdog and unlimited
active-turn duration automatically; the two `alp.*` keys are optional.

## v0.14.11 — 2026-08-26 — vision has one explicit route

- **Image inspection can use its own model without changing the agent.**
  `alpi setup → Routing models` now exposes a Vision model that writes the
  existing `tools.read_image.model` contract. It powers `read_image` and
  opt-in browser screenshot analysis; clearing it returns both to the main
  model. Chat attachments deliberately stay on the main turn.
- **Clients receive the vision route and selectable models.** `host.profile.detail` returns
  `vision_model`, and profiles with an OpenRouter key get the curated OpenRouter choices next to
  their own saved models.
- **Empty overrides leave no dead configuration behind.** Clearing Vision model
  through a client prunes the empty `tools.read_image` block instead of
  persisting a meaningless empty mapping.

Nothing to migrate. Existing profiles continue to use their main model until a
Vision model is selected.

## v0.14.10 — 2026-08-25 — a failing tool gets to say why

- **A failing tool's own diagnosis reaches the model**, on the main loop and in `delegate` and
  `research` alike.
- **`delegate` fences tool output as untrusted content**, as the other paths already did.
- **ALP secrets directories are private** (0700) and repair themselves on daemon start.

## v0.14.9 — 2026-08-24 — a tool that cannot run is no longer offered

- **The browser tool works in Docker.** The image installs the libraries Chromium needs,
  including fonts for Thai and CJK.
- **The browser download is a third of the size**, and existing profiles reclaim the unused
  full build.
- **An unavailable tool is no longer offered to the model**, and `alpi doctor` names what is
  missing with a command that works.
- `alpi doctor` reports three groups of checks it had been skipping, including duplicate peer
  identities.
- **`web_search` stops racing itself into rate limits.** Searches are serialised, spaced, retried
  once and bounded per turn (`tools.web_search.max_per_turn`).

Nothing to migrate.

## v0.14.8 — 2026-08-23 — every turn has a spine

- **Every turn has a durable run.** Runs from chat, schedules, workgroups, research and
  delegates get a stable id and a bounded, redacted journal, inspectable with `alpi runs`,
  `/runs` and the host API; an active run can be interrupted by id.
- Terminal command text is never stored in journals, saved turns or reconnect sidecars.
- Read-only tools may run concurrently when the whole batch allows it; results keep the
  model's order.
- Every tool call — direct, nested, MCP or workflow — crosses the same policy checks.
- Profiles can opt into an ephemeral Docker terminal backend, with network off by default.

Nothing to migrate; the new behavior is opt-in.

## v0.14.7 — 2026-08-23 — the daemon stops choking on its own bookkeeping

- **The apps stop reporting the daemon as unreachable.** It no longer freezes for seconds at a
  time with several profiles subscribed to several workgroups.
- An empty workgroup poll no longer rewrites the subscription file, and idle workgroups back off
  their polling.
- A turn launched after a burst of messages still sees the message that opened its task.
- YAML files can no longer lose a character on save, and the hub's roster and workgroup files
  are written atomically.

## v0.14.6 — 2026-08-21 — a wedged hub always has a legal move

- **A hub task cannot jump into a dormant chain**; the post is refused with the legal moves
  named.
- **An owner's QA verdict is read exactly.** Only a token in verdict position counts, and a
  close must carry it verbatim.
- A rejected close names the exact accepted shape, so a hub fixes it in one retry.

## v0.14.5 — 2026-08-20 — a busy member is not a dead member

- **The stall watchdog respects a phase's declared `turn_budget_s`**, so a member using its full
  budget is no longer treated as stalled; a genuinely dead member is still escalated.
- A turn's end is detected even when a leftover child process holds its pipes.

## v0.14.4 — 2026-08-19 — the phase boundary has no side doors

- **A delegated sub-agent obeys the phase write scope.** During a pipeline turn it inherits the
  dispatch's denied tools, both in its schema and at execution.
- **Skill files cannot be modified mid-phase.** The `skill` tool wrote
  through its own atomic writer without consulting the write scope, so any
  member — owner included — could create, edit or delete skill files during
  a scoped pipeline turn. All eight mutating verbs are now refused while a
  phase scope is active, because skill files never sit inside a phase's
  declared paths; reading, listing and running skills still work.
- **The workspace root fails closed instead of drifting to the working directory.** A config that
  fails to load surfaces as a tool error, and an active write scope refuses writes when no
  workspace is configured.

## v0.14.3 — 2026-08-19 — a gate nobody can run is refused up front

- **A recipe can no longer declare a gate the runtime would skip.** A gated phase owned by the
  hub is rejected at parse time and at launch; assign it to a member or drop the gate.

## v0.14.2 — 2026-08-18 — the preview belongs to its connection

- **A client no longer sees another connection's chat preview.** `host.profile.summaries` shows
  only sessions the asking connection owns, with no admin bypass; the local socket is unchanged.

## v0.14.1 — 2026-08-17 — the bind address follows the network

- **The advertised bind address follows the network instead of the first
  probe.** `detect_bind_ip` cached its first result for the daemon's entire
  lifetime, so a daemon started before Tailscale was up — or during an outage
  — advertised a stale LAN address, or none at all, until restart. The probe
  now expires after thirty seconds while still absorbing the launchd startup
  burst with a single blocking call.

## v0.14.0 — 2026-08-15 — profiles own the work they launch

- **Recipes belong to the hub profile.** The console, host API and desktop app list, describe and
  launch the same recipes; the `organizations/` layer is removed.
- Concurrent workgroup pulls no longer cause duplicate member turns.
- Declared phase paths constrain file writes while a phase runs, and owners can remove a file
  with the new `delete_file` tool.
- A `#working` heartbeat no longer wakes the hub into an empty turn.
- **Provider stalls recover without losing the turn.** A silent stream is retried after the idle
  window, and a ten-minute per-request limit stops a stream that never completes.
- Pipeline recovery keeps phase outcomes honest; only an operator trigger starts a new run.

## v0.12.13 — 2026-08-09 — every surface knows what the cache saved

- **Every LLM call records what the prompt cache saved.** Tool-side calls, sub-agents and
  wrap-ups get the same cache and cost accounting as the main turn, and a provider that reports
  nothing is left out of the hit rate instead of counting as a miss.
- **Recorded spend says where the figure came from** — the provider's own cost, a price
  estimate, or none — so it can be reconciled with the real invoice.
- **Cache hit rates show in `/status` and `alpi digest`**, and the host usage window plots them.
- **Conversation history is append-only**, so the provider cache is no longer broken every turn,
  and OpenRouter conversations carry a hashed sticky routing key.
- A turn with a low cache hit records why, without storing prompt text.
- Workgroup posts no longer count earlier usage twice.

## v0.12.12 — 2026-08-08 — the change has an actor

- **Administrative changes on the host plane are recorded with their actor.**
  `admin-audit.jsonl` notes the device, role, method and result of each change — never tokens,
  config values or chat content — and rotates at 5 MB.
- `host.audit.list` and `alpi audit-log` page and filter the trail.
- Untrusted traffic cannot flood it, and a damaged row is skipped instead of hiding the rest.

## v0.12.11 — 2026-08-07 — the QR is not the key

- **Pairing links no longer contain the permanent credential.** A QR carries a one-time grant
  that expires in ten minutes; the first scan exchanges it for a separate device token.
- Pending, used, expired and cancelled pairings are visible and cancellable in `alpi setup`,
  Desktop and the host API.
- **Update Desktop and Mobile before pairing with a new QR.** QRs generated by older daemons
  still hold permanent tokens; revoke unclaimed devices whose `last_seen` is `never`.

## v0.12.10 — 2026-08-07 — WSS gets a front door

- **The supplied Docker overlay terminates public TLS without publishing the
  daemon.** Caddy serves the configured domain on ports 80/443 and forwards
  WebSocket upgrades over the private Compose network. The overlay removes the
  base mappings for the host plane and ALP, so ports 49200 and 7423 do not
  become accidental Internet entry points.
- **Custom host-plane ports stay coherent through the proxy.**
  `ALPI_HOST_TCP_PORT` now drives the daemon listener, its direct Docker
  mapping and Caddy's private upstream. Deployments that use 49201, 30494 or
  another per-instance port no longer need to edit the Caddyfile separately.
- **The WSS runbook covers the whole operator path.** DNS, firewall rules,
  Compose version requirements, effective-config verification, certificate
  checks, public-route configuration, scoped pairing, external-network tests,
  updates and rollback are documented together. The packaged knowledge
  references carry the same deployment and security boundaries.
- **The publish suite no longer searches serialized YAML for arbitrary
  substrings.** Workgroup tests inspect the parsed phase map, so a random
  Base64 public key containing text such as `cwd` cannot fail an otherwise
  valid release.

## v0.12.9 — 2026-08-07 — a public socket has finite patience

- **Unauthenticated WebSockets get finite time and capacity.** Connections are capped globally
  and per device, and a socket must authenticate within ten seconds.
- **Revoking a device closes its live sockets and streams**, including revocations made outside
  the running daemon.
- `host.network.status` reports the limits and rejections; limits are tunable with
  `ALPI_HOST_WS_*` variables.

## v0.12.8 — 2026-08-06 — one connection, every safe route

- **Pairing advertises an ordered list of routes.** `host.endpoints` can put a public `wss://`
  address first and keep a private `ws://` fallback; every device still gets its own token and
  scope.
- Old pairings and links keep working, and new QR codes carry the connection id so Mobile
  refreshes the same connection.
- `ws://` requires a private IP literal and hostnames require certificate-validated `wss://`; a
  WSS-only list keeps a private fallback.
- Network settings in `alpi setup` and Desktop show the detected address and port, and an
  invalid endpoint list reports a specific error.
- The dead `service.*` switches are removed; `service.prefetch` migrates to `runtime.prefetch`,
  and `alpi doctor` warns about leftovers.

## v0.12.7 — 2026-08-06 — an abandoned task stops shouting

- **A terminally stalled task no longer spams the log and the poller state.**
  Once a task has spent every recovery wake, each poll tick was still counting
  another "closure nudge", writing it to disk and logging a warning, hundreds
  an hour for a single stalled task. The recovery ladder is untouched
  and each of its steps still fires exactly once; past the last one, the poller
  goes quiet until a new post moves the task.

## v0.12.6 — 2026-08-06 — a red gate says what it found, and notices when it's fixed

- **A red gate reports what it found**, with the command and the next step, instead of calling
  correct work "unverified".
- A member named in a post receives the gate's full findings, not a trimmed line.
- **A phase fixed in place closes by itself.** The workspace is re-checked after a red gate, but
  only once something has changed.
- Prompt-cache usage is recorded end to end, and a provider that reports nothing counts as
  unmeasured, not as zero.
- Shell runs record which workgroup they came from; the command line still never is.

## v0.12.5 — 2026-08-05 — a reply says when it landed

- **A turn now records when it ended, not only when it started.** Turns that
  chain dozens of tools run for many minutes, and the reply was carrying the
  timestamp of the question — a fresh answer showed up already twenty-five
  minutes old. Clients get an `ended_at` alongside `at` and can stamp each side
  of the exchange honestly.
- **Session recency follows the end of the last turn**, so a long piece of work
  no longer sorts and dates itself by the moment it was asked for.

Sessions written before this release carry no end stamp and keep reading exactly
as they did.

## v0.12.4 — 2026-08-04 — a stalled run tells someone

- **An invented repair slug no longer strands the run.** A phase named
  `#intake-repair` belonged to no chain, so closing it advanced nothing and the
  run sat with every check green for over an hour. Any `<phase>-<suffix>` now
  recovers to its phase, and an opener that still maps nowhere is refused at
  post time naming the forms that work.
- **A halt that names another member gets one wake.** Closing BLOCKED while
  naming another member as the owner described a hand-off nobody opened; the hub
  is now woken once to open it or to say plainly that nobody can act.
- **A boundary finding leads with the action its owner can take.** It used to
  say "restore each file" to owners with no way to restore anything, which
  burned three repair rounds twice; naming the file in the handoff comes first.

## v0.12.3 — 2026-08-04 — the model list tells the truth again

- **DeepSeek V4 Flash 0731 is now a first-class pick.** It keeps the 1M context
  of the model it replaces at roughly two thirds of the price, and it shows up
  in `alpi setup` and `/model` like any other curated model.
- **A model you pick gets the context window it actually has.** The catalogue
  had drifted since it was last refreshed, so some models were credited with
  less room than they really offer — DeepSeek V4 Flash among them, which was
  short by about 50K tokens on every turn.
- **Retired models no longer clutter the picker.** Thirty-seven entries that
  the provider has since dropped are gone, `owl-alpha` included — it had been
  offered for weeks after it stopped existing, which meant picking it left a
  profile unable to answer at all.
- **Pinned snapshots over moving names.** The curated DeepSeek entry now names
  a dated snapshot, so a provider swapping what a generic name points to can no
  longer change how your agents behave overnight.

## v0.12.2 — 2026-08-04 — a repair keeps its voice to the end of a phase

- **An owner repairing its own phase is no longer silenced deep into it.** The
  exemption that lets a fix note and its re-delivery arrive as two posts stopped
  applying once the phase's opening task scrolled out of the member's recent
  view — which is exactly what happens after a few repair rounds. One phase sat
  frozen for over two hours in that state; it now finishes on its own.

## v0.12.1 — 2026-08-03 — pipelines that recover on their own

- **A removed workgroup stays removed.** Deleting one could race a member's
  in-flight write and quietly resurrect its subscription. Removals are now sticky, and a
  deliberate re-join still works.
- **A stalled pipeline recovers without an operator.** If the owner fixed the
  files but never re-posted, the check re-runs before the hub is woken and a
  green result closes the phase by itself; resuming a paused workgroup re-fires
  a check that was parked behind the pause; and a final verdict that fails gets
  one wake to route its findings instead of freezing the run.
- **A repair can arrive in pieces.** The phase owner is no longer silenced for
  posting a fix note before the re-delivery, and after a blocked phase the hub
  may re-open any earlier phase — rewinding re-walks the chain forward.
- **A recipe can declare which files each phase may touch.** Editing outside the
  declared paths turns the check red naming each file, before the check runs,
  because an agent editing another phase's files could force a red check green.
- **Workgroup turns cache better.** The per-turn prompt now keeps its stable
  text first and the volatile lines last, so providers that price cached input
  can actually reuse the prefix between turns.

## v0.12.0 — 2026-07-31 — one map of named pipelines, declared only by a recipe

**Breaking:** the old `pipeline` + `operations` recipe shape is gone; recipes declare `pipelines`
(named ordered chains) and `launch`. Workgroups created with the old shape stop loading and must
be relaunched from the updated recipe. Upgrade hubs and members together.

- **Only a recipe declares a pipeline**, and no surface edits a chain after launch; a workgroup
  created by hand is a deliberation.
- **Any declared chain can be started by name** with `alpi workgroup trigger <wg_id> <pipeline>`,
  using the recipe's own owner and task.
- **Pipelines run one at a time.** Starting one stops what was running and says so; without
  `launch`, a workgroup waits idle until triggered.
- Members read the workflow — chains and phase owners — from the daemon, and the console and apps
  show which chain is running.
- A deliberately skipped phase reads as skipped, repairs stay inside their phase, and a recipe
  with a gap is rejected.
- A phase the hub owns can be worked and closed by the hub.

## v0.11.19 — 2026-07-30 — declared post-launch chains, and gates that cannot be talked past

- **Recipes can declare `operations`**: named post-launch chains the daemon advances on its own,
  run only when triggered.
- **The desktop keeps its connection under load.** The sidebar listing is computed once per
  burst and still refreshes the moment something changes.
- **A checked phase closes only when its check passed** on the owner's latest delivery; the
  repair is to re-open the same phase.
- A heartbeat is not a delivery, and a phase whose check never runs is reported once.
- Research guidance points agents at the extracting reader first, which is far cheaper than
  downloading whole pages.

## v0.11.18 — 2026-07-29 — a profile out of budget says so

- **A profile that hits its daily cap no longer stalls its workgroups in
  silence.** The poller checks the cap before starting a turn, so it stops
  burning subprocesses that die with no reply, and records the block once per
  workgroup per day in the turn log.
- **A blocked turn keeps its place in the queue.** The check runs before any
  poller cursor moves, so the watchdog's recovery attempts are not spent while
  the agent has no budget — raising the cap resumes the phase where it left
  off instead of finding it abandoned.
- **Turns aborted on budget now report it.** They were being logged as
  "Reached max tool steps", which sent diagnosis after a step limit that had
  not been reached; the real cause now survives into the run ledger.

## v0.11.17 — 2026-07-28 — files move with the workgroup

- **Any workgroup member can now send, rediscover, and fetch files through the hub.**
  Files stay end-to-end encrypted, transfer in bounded chunks, are addressed
  by their SHA-256 digest, and leave only a small `#file` marker in the shared
  transcript. Existing chat attachments can be forwarded directly from an
  agent turn with the new `workgroup_file` tool.
- **Members now receive the workgroup's actual briefing.** Up to 4096
  characters are injected for both hubs and members, with visible truncation
  beyond that limit; recent post previews remain compact.

## v0.11.16 — 2026-07-27 — pausing a profile pauses its schedules

- **A paused profile no longer fires its scheduled jobs.** "Pause profile"
  used to only block the chat while crons kept running in the background;
  now the scheduler skips every job of a paused profile until you resume it.
- Manually firing a job stays possible while paused — an explicit request
  always wins, same as firing a paused job.

## v0.11.15 — 2026-07-25 — smooth daemon under busy workgroups

- **Fixes the periodic freezes and "daemon disconnected" notices** on daemons
  hosting several active workgroups: member-subscription state is now parsed
  ~50x faster and cached between polls, so the background pull traffic no
  longer starves the daemon while the apps wait.

## v0.11.14 — 2026-07-24 — responsive local reads

- **Fixes the slowness and spurious "daemon disconnected" notices** introduced
  in 0.11.13: reading connections no longer waits on the write lock, so profile
  summaries and workgroup lists return fast instead of stalling or timing out.
  Concurrent device edits stay safely serialized.

## v0.11.13 — 2026-07-24 — paired devices survive concurrent edits

- **A paired device no longer vanishes** when another device is added or revoked
  at the same moment. Changes from the apps, the CLI, and the running daemon are
  now serialized, so two simultaneous edits can no longer overwrite each other.

## v0.11.12 — 2026-07-24 — recipe launches carry text only

- **`alpi workgroup launch` no longer accepts `--assets`.** A launch carries
  the recipe's declared text inputs (e.g. the client brief as markdown) and
  nothing else — binary media never travels at launch.
- **Binary files arrive after launch**: add them to the project's own git,
  following its template's structure, and open a follow-up task for the crew.
- A non-UTF-8 file passed to `--input` now fails with a clear message instead
  of a traceback: launch inputs are text-only.

## v0.11.11 — 2026-07-24 — install requirements for every deployment shape

- **INSTALL.md now opens with a requirements matrix** for the three ways to run
  alpi — native, Docker, and Kubernetes: Python/Node versions, service manager,
  state layout, and the exact inbound/outbound network needs of each shape.
- **docker/README.md gains a Kubernetes section**: the image runs as a plain
  stateful single-writer workload — `replicas: 1` always, PVC at `/data`
  (UID/GID 1000), `ALPI_NETWORK_HOST` as the dial address, TCP readiness on the
  host-plane port, secrets as `.env` files never baked into the image.
- Retired the outdated "there is no Docker image" claim — the official image is
  `satoshiltd/alpi`, for headless fleet daemons; the personal agent stays a
  native install.

## v0.11.10 — 2026-07-23 — monthly spend at a glance

- **The usage feed now carries a 30-day total.** `host.usage.daily` returns a
  `total30` block (cost, tokens in/out over the ledger's full 30-day retention)
  alongside the 14-day daily series, so clients can show the monthly cost as a
  number next to the recent-trend chart.

## v0.11.9 — 2026-07-23 — provider hiccups no longer kill a turn

- **A transient provider error mid-stream retries instead of failing the chat**, as long as no
  visible text has streamed yet — same model first, then `fallback_models`.

## v0.11.8 — 2026-07-22 — workgroup dispatch survives daemon restarts

- **A daemon restart mid-turn no longer orphans an open task.** A member's
  response cursor now advances only when its dispatched turn actually
  completes, so after a crash or restart the still-open task re-dispatches
  within one poller tick instead of being silently forgotten. This is
  at-least-once semantics: duplicate posts are guarded by the rotation rules,
  but a turn that crashed after an external side effect may repeat it on the
  re-run.
- **A stalled pipeline phase gets re-tasked, never silently skipped.** The hub
  may now re-open the same phase for its owner when the owner never responded,
  the repair wake tells the hub that this is the one correct move, and closing
  a phase whose owner never posted is mechanically rejected — skipping stays
  possible but loud, via `#done skipped · <reason>` or `#done BLOCKED ·
  <reason>`.

## v0.11.7 — 2026-07-22 — spend survives workgroup deletion everywhere

- **Deleting a workgroup now preserves its spend history on every surface.**
  One canonical delete — used by the apps' delete button, `alpi workgroup
  remove`, and the TUI wizard — archives the workgroup's total cost and tokens
  before destroying the transcript (the same contract storage cleanup already
  honored) and refuses to delete anything if that archive cannot be written.
- **A failed delete no longer reports success.** If removing the workgroup
  directory fails (permissions, I/O), the operation reports the failure;
  subscriptions and search index are only purged after the directory is gone.

## v0.11.6 — 2026-07-22 — large attachments over remote connections

- **Attaching files from a remote device no longer drops the connection.** Messages up to the
  20 MiB attachment limit are accepted, an over-cap file gets a structured error, and desktop
  ≥ 0.4.49 and mobile ≥ 0.2.19 check the cap before uploading.

## v0.11.5 — 2026-07-21 — Node 24 in the container image

- **The Docker image ships Node.js 24 LTS.** A dockerized daemon runs npm-based
  project gates and `npx`-launched MCP servers on its own, without relying on the
  host's Node install.
- **Dockerized daemons can clone private project repos over SSH.** The image now
  includes an SSH client, so a recipe whose setup clones a private template
  (`git clone` + `npm ci`) works inside the container. Provide a deploy key under
  `/data/.ssh` at runtime; credentials are never baked into the image.

## v0.11.4 — 2026-07-21 — read-only knowledge relays

- **A profile can be a read-only front door to another agent.** With `relay: {peer: <id>}` it is
  offered only the `peer` tool and must answer through that peer, enforced by the engine;
  protecting the agent behind it stays with that agent's own permissions.
- **Cross-agent spend is attributed to the caller.** When one agent answers
  another's question over ALP, that turn's cost is now recorded against the
  calling peer (`peer:<id>`) in the daily ledger's connection breakdown instead
  of the generic `host` bucket.

## v0.11.3 — 2026-07-19 — workgroup recipes

- **Launch a whole workgroup from a recipe file.** `alpi workgroup launch --recipe <file> --param …
  --input …` validates the recipe, clones and seeds the project, creates the workgroup and
  posts the first task in one step, rolling everything back on failure.
- **Recipes are plain files, not installed state.** The daemon keeps no
  catalogue; it reads a recipe's contents at launch and validates them
  (parameters, pipeline, hub ownership) before anything is created.
- **Hardened peer workgroup access.** A malformed workgroup id from a paired
  peer can no longer reach another profile's workgroup data; ids are now strictly
  validated everywhere they arrive over the wire.
- **Projects are created from a recipe.** Spinning up a project is now a single
  `workgroup launch --recipe`; the old per-project setup scripts and the bundled
  template are gone — the template lives in its own git base repo the launch clones,
  and template updates reach a live project via `git pull`.
- **Post-launch changes stay with the hub.** New locale, rebrand, content or a
  new section come in as a maintenance request; the hub classifies it, routes the
  owners, and closes only once the change is rebuilt into the live site.

## v0.11.2 — 2026-07-17 — verified pipelines and durable spend

- **Spend survives deletion.** Removing a chat session or a workgroup now
  durably writes its total cost, token counts and connection attribution to an
  idempotent append-only archive (`logs/spend_archive.jsonl`) before the files
  go. Cleanup aborts rather than deleting data when that archive cannot be
  confirmed.
- **Mechanical pipeline transitions no longer need an orchestration turn.**
  Hub-local `pipeline_steps` can run a bounded deterministic gate after the
  expected owner hands off, persist its private audit log, close the verified
  phase and open the next task through the normal workgroup SDK.
- **Local handoffs wake immediately.** Accepted posts nudge the owning hub
  poller in-process while the existing poll remains the recovery path; tasks
  opened by a verified gate bypass only the handoff cooldown.
- **Bulk delegates can request a larger bounded work loop.** `delegate` now
  accepts `max_steps` up to 100 LLM/tool rounds, including parallel batches.

## v0.11.1 — 2026-07-17 — cleanup you can actually read

- **`setup → Cleanup` is simplified.** Instead of eleven fine-grained
  directories (including confusing ones like "Curator reports"), it now offers
  one **Clean all safe** action that reclaims caches, logs and knowledge in a
  single step, and lists only the destructive categories separately behind a
  confirm. Empty categories are hidden.

## v0.11.0 — 2026-07-17 — faster workgroups and verified artefacts

- **Active workgroups advance in seconds.** Remote subscriptions hold their pull open and local
  hubs probe every 5 seconds, while idle groups stay cheap.
- Cross-machine workgroups reuse their encrypted sessions, and replay protection survives daemon
  restarts.
- The task protocol is stricter: a duplicate `#task` opener is refused, and a pipeline member's
  mentions wake only the hub.
- **Peers can transfer files** with `link.put_blob` / `link.get_blob`, addressed and verified by
  SHA-256.
- Translation phases can fan out safely by locale with bounded delegates.
- The unused `auto_kickoff` setting is removed.

## v0.10.36 — 2026-07-16 — the whole inbox in one call

- **Clients can fetch outputs across every profile in a single request** —
  `host.outputs.list` accepts `all: true` and returns the merged, newest-first
  inbox with each row tagged by profile.
- **`alpi outputs list --all-profiles`** does the same from the console:
  every profile's inbox merged newest-first, each row tagged `@profile`.

## v0.10.35 — 2026-07-15 — attach any file, not just images and docs

- **Any file type can now be attached to chat**: images, PDFs and text are
  still read inline; anything else (a `.fit`, a spreadsheet, an archive, an
  export…) rides along as a file the agent can open by path with its tools,
  instead of being rejected at upload.

## v0.10.34 — 2026-07-15 — ask for a file, get it as a download

- **Generated files come back as downloads**: when you ask the agent to
  produce a document, report or export, it now attaches it to the reply as a
  downloadable file instead of only writing it into the workspace — which
  mobile, desktop and remote members can't browse.

## v0.10.33 — 2026-07-15 — snappier turns, no dead air before the first reply

- **Tool servers are reused across messages** instead of being restarted and
  re-handshaked on every send, so every turn after the first starts noticeably
  faster — and a leak that spawned a fresh set of servers per message is gone.
- **No more silent gap before the first "thinking"**: a message is acknowledged
  immediately and the connection is kept alive while the turn spins up, so
  setup time reads as "working" instead of a frozen screen.
- **A second message to a conversation that's already replying is turned away
  at once**, instead of redoing the setup work before noticing it's busy.

## v0.10.32 — 2026-07-15 — members can work without changing shared setup

- **Member connections keep the usual working tools** while skills, memory,
  and schedules stay protected: members can view and run existing skills, but
  cannot create, change, reset, or delete them; they can read memory and list
  schedules without changing either.
- **A member only sees its own conversations**: session search, browsing and
  semantic recall are scoped to the member's connection — another person's (or
  the host's) history is invisible.
- **File tools keep the profile's private files out of reach**: device tokens,
  keys, secrets, sessions and schedule state are off-limits to member file
  reads and writes. The workspace and chat transcripts stay open.

## v0.10.31 — 2026-07-15 — current models on tap

- **OpenAI models refreshed to the GPT-5.6 family**: Sol (flagship · coding),
  Terra (balanced) and Luna (cheap · fast) replace the older 5.3–5.5 lineup.
- **Anthropic models refreshed**: Claude Fable 5 (new flagship) and Claude
  Sonnet 5 join Opus 4.8 and Haiku 4.5; the superseded Sonnet 4.6 is dropped.

## v0.10.30 — 2026-07-15 — member connections stay members

- **Management surfaces are admin-only over remote connections:** memory files, skills, schedules
  and the notifications inbox refuse member tokens, and member profile reads are limited to what
  chat needs, with no `..` or symlink escapes.
- **The event stream respects the same boundary**: a member connection no
  longer receives notification, schedule or spend events — live or on
  reconnect — so nothing the admin-only verbs hide leaks back through the bus.
- **Scheduled runs are always accounted to `host`**: the daemon owns every
  scheduled job regardless of which connection created it; the job keeps its
  creator as provenance only.

## v0.10.29 — 2026-07-14 — one connection, multiple devices

- **Connections replace the flat paired-device list.** One label, role and
  profile scope can now hold separate desktop/mobile credentials; each device
  can be added or revoked without affecting the others. Existing
  `devices.yaml` installs migrate automatically with every token preserved.
- **Chat history and accounting belong to the connection that created them.**
  Session explorers are isolated per connection, while daily input/output
  tokens and cost are available as a 14-day connection breakdown. Local CLI,
  TUI and Unix-socket activity remains grouped under `host`.
- Sessions created before this upgrade have no connection identity and remain
  available locally under `host`; remote connection explorers only show new
  sessions created through that connection.
- **Full console management in `alpi setup → Connections`**: create, rename,
  scope, enable/disable or delete a connection, add/revoke individual devices,
  and inspect sessions plus 14-day usage.

## v0.10.28 — 2026-07-13 — generated files get a real lifecycle

- **`out/` is now the standard home for chat-delivered artifacts** (generated
  images, exported documents): documented for skill authors, ignored by the
  bootstrap `.gitignore`, and excluded from `alpi backup` (they are
  regenerable — backups get lighter).
- **New cleanup category "Generated files"**: artifacts older than 30 days can
  be reclaimed from `alpi setup` and the apps, like any other category.
- **Documents generated by a profile are now downloadable from the apps** —
  the attachment fetch allows `out/` for non-image files (PDFs, spreadsheets),
  which previously could be attached but not downloaded.

## v0.10.27 — 2026-07-13 — schedule definitions split from run state

- **`jobs.json` now holds only your job definitions.** The scheduler's
  bookkeeping (last run time and status) moved to its own file,
  `schedule/runs.json`, merged transparently when jobs are listed.
- **Editing a job can no longer race the scheduler.** A job firing mid-edit
  only writes the run-state file; your definitions are never rewritten unless
  they actually changed.
- **Zero-touch migration** — existing `jobs.json` files split automatically on
  the first write; CLI, TUI, and the apps keep working unchanged.
- **`alpi doctor`** warns when the run-state file is unreadable (the scheduler
  refuses to run any job until it is repaired).

## v0.10.26 — 2026-07-13 — memory you can measure and edit

- **Each memory file now reports a budget %.** AGENT.md, MEMORY.md and USER.md
  expose how much of their character budget is used, so you and the agent can
  see at a glance how close a file is to full. AGENT.md's budget is advisory —
  writes are never rejected, just flagged over 100%.
- **Memory files are editable from the apps.** The daemon serves a guarded write
  for the three memory files; a saved edit is live on the next message (no
  restart — the prompt re-reads memory every turn).

## v0.10.25 — 2026-07-13 — MCP tools that only return structured data

- **MCP tools that reply with structured JSON now come through.** Servers whose
  results carry only `structuredContent` (no mirrored text block) used to render
  blank; alpi now falls back to the structured payload so the reply isn't empty.

## v0.10.24 — 2026-07-11 — the console catches up

- **The TUI can browse your history.** `/sessions` lists saved sessions with a
  preview and turn count — press enter to resume one in place, or `d` twice to
  delete it.
- **Outputs are no longer invisible in the terminal.** `/outputs` in the TUI
  and `alpi outputs list|show|read-all` on the CLI browse the same inbox the
  apps show — notifications, cron replies, produced files — and mark them read.
- **Scheduled jobs are manageable from the console.** `alpi schedule list`
  prints every job with its next fire time, and `alpi setup → Schedules` can
  fire, pause, resume, or delete them.
- **Storage cleanup is now a host capability.** The same categories behind
  `alpi setup → Cleanup` (caches, logs, old transcripts, knowledge-index
  bloat) are exposed to paired apps, so remote daemons can be tidied without
  a shell.

## v0.10.23 — 2026-07-11 — schedule reports its next run

- **Scheduled jobs now tell paired apps when they'll next fire.** The daemon
  computes each cron job's upcoming run time, so desktop and mobile can show
  "next: tomorrow 07:00" instead of just the raw cron expression.

## v0.10.22 — 2026-07-11 — every token lands in the ledger

- **Every LLM call now counts against the daily budget.** Web extraction,
  knowledge ingestion and maintenance, context compaction, the memory
  reviewer, and bio drafting all report their tokens and cost — previously
  they spent invisibly.
- **Every spend point checks the cap before spending.** `delegate` and
  `research` stop mid-loop and before their final synthesis, compaction skips
  its summary, the memory reviewer skips its pass, and a turn whose
  compaction crossed the cap never starts — instead of only being caught on
  the next turn.

## v0.10.21 — 2026-07-10 — the right model for every job

- **Profiles can route work across model tiers.** Configure an optional cheap
  `fast` model and a strong `deep` model next to your main one; anything left
  unset simply runs on the main model, so nothing changes until you opt in.
- **Routine background work gets cheaper automatically.** Context compaction,
  the memory reviewer, and bio drafting run on the fast tier, and sub-agents
  and scheduled jobs can pick a tier — `research` depths share the tier
  names at the extremes (fast/deep) so one vocabulary routes everything.
- **Stuck turns escalate instead of failing.** After repeated tool failures or
  an empty reply, the turn retries once with more reasoning or the deep model —
  never past 80% of the daily budget.
- **Provider outages fall back automatically.** `fallback_models` now retries
  down the chain when the active model fails before answering.
- **Every reply records the model that produced it**, and a new "Routing
  tiers" section in `alpi setup` configures it all from the terminal.

## v0.10.20 — 2026-07-10 — assistants can hand you files

- **Assistants can now attach a file they produce to a reply.** Ask for a report,
  export, or document and get it back as a downloadable file — Markdown, text,
  CSV, PDF, and more — instead of a wall of text in the message.
- **Attached files reach paired apps, not just the local machine.** The daemon
  serves the file's bytes to the desktop and mobile clients on request, while
  keeping profile secrets off-limits.

## v0.10.19 — 2026-07-09 — TUI shows your Markdown

- **Markdown you type now renders in the TUI transcript.** User messages keep
  their `>` quote blocks, inline code, lists, and other supported Markdown
  styling instead of showing the raw markup.

## v0.10.18 — 2026-07-09 — steadier empty replies and knowledge recall

- **Empty model replies are covered by regression tests.** If a provider closes
  a turn with no final text, Alpi nudges once and keeps the turn clean instead
  of surfacing an empty answer.
- **Knowledge searches now bias toward the corpus language.** The `knowledge`
  tool tells the model to phrase search queries in the same language as the
  stored knowledge, improving recall when the user's prompt is in another
  language.

## v0.10.17 — 2026-07-08 — attach a scanned PDF to any profile

- **Scanned PDFs now work as chat attachments, even without vision or a
  knowledge base.** Attach a scan and ask for a summary: a vision model reads
  the page images as before, and a text-only model now falls back to on-device
  OCR instead of erroring. No `knowledge` ingest step required.
- **Long PDFs are no longer clipped to 15 pages.** Digital-text PDFs are read
  in full, bounded only by the overall text budget — so "summarize this
  50-page report" actually sees the whole report.
- **Attachment text budget now scales with the model automatically.** How much
  extracted text an attachment can feed the model defaults to half the active
  model's context window — so a big-context model reads far more (a 1M model
  ~500k tokens vs the old flat ~40k), a small one proportionally less, with no
  config. Override per profile with `tools.attachments.max_text_tokens` to bound
  cost or force a fixed size. See `docs/CONFIG.md`.
- **Images on a text-only model** stay explicit: instead of silently vanishing,
  the model is told it can't see the image and to switch to a vision model.
- Internal: PDF text extraction, page rendering, and OCR now live in one shared
  module (`alpi/extract.py`) used by both chat attachments and the knowledge
  tool — no more two diverging code paths.

## v0.10.16 — 2026-07-06 — replies you can actually listen to

- **New `host.voice.script` verb.** Before reading a reply aloud, the daemon
  now turns it into a spoken briefing — under a minute of audio, in the
  reply's own language, leading with the outcome. No emojis, no markdown, no
  URLs spelled letter by letter; however long the reply, the audio is the
  executive summary and the full text stays on screen.
- **Each script is computed once.** Scripts are cached on disk per profile,
  so replaying a message — or listening to it from another device — never
  pays the LLM call twice. Script generation counts against the profile's
  daily budget like any other model call, and a capped profile falls back
  to plain cleanup instead of spending.
- **Voice synthesis accepts longer texts** (280 → 700 chars), fixing read
  aloud silently failing on longer replies from the mobile app.

## v0.10.15 — 2026-07-06 — big chats and long histories load faster

- **Opening a long conversation no longer re-parses it for every page.** The
  daemon keeps recently opened sessions parsed in memory, so the first read
  does the heavy lifting and every follow-up slice — paging older history,
  refreshing the tail — returns in milliseconds, even for multi-megabyte
  chats.
- **Listing sessions survives a daemon restart without re-reading everything.**
  Session summaries are now indexed on disk, so a profile with hundreds of
  conversations lists them instantly after a restart instead of parsing every
  file again. The index maintains itself: it prunes deleted sessions and
  rebuilds transparently if it's ever corrupted.

## v0.10.14 — 2026-07-04 — chat history in slices

- **Chat history can now be read in slices, newest first.** `host.session.read`
  accepts `before_turn`/`max_turns` to page older turns backwards, alongside
  the existing `after_turn`/`tail_turns` — so a client can paint the latest
  messages immediately and backfill the rest, instead of shipping the whole
  transcript before anything renders.
- **Sliced reads now say what kind of session they are** (chat, workgroup,
  scheduled…), classified from the true first turn — a client that only
  fetched the tail can no longer mistake a chat for something else.

## v0.10.13 — 2026-07-03 — chat history stops crying wolf

- **A turn is marked interrupted only when it really was** — by Stop, Ctrl+C or a peer cancel —
  never just because its reply had not arrived yet when another device looked.
- **A reply made only of tool actions, with no closing comment, is no longer
  mislabeled interrupted either** — the same fix applies to any turn that
  legitimately ends without final text.
- **`host.session.read` now reports whether a session currently has a turn
  running** (`in_flight`), so a client reopening a long-running chat can show
  "still working" instead of guessing from an empty reply. Desktop and mobile
  pick this up in their own next release.
- **Fixed a rare cross-profile mixup: two profiles that happen to have a
  session with the same id could interfere with each other** — one profile's
  running turn could make an unrelated profile's identically-named session
  wrongly report "busy" (blocking sends and deletes) or "still working."
  Session activity is now tracked per profile, not just per session id.

## v0.10.12 — 2026-07-03 — tighter guards on paired-device access

- **A profile-scoped device can no longer act outside its profiles.** Answering
  a running agent's clarification prompt is now checked against the device's
  allowed profiles, closing a gap where a scoped phone could reply to another
  profile's agent.
- **Network settings stay local-only, everywhere.** Changing the daemon's
  listening ports, advertised address, or public-exposure flag is now blocked
  over remote connections even for admin devices — matching the rule that
  already applied to the dedicated network commands.

## v0.10.11 — 2026-07-02 — a faster, steadier host plane for the apps

- **Opening a chat no longer stalls the daemon.** Reading a session's history
  now runs off the event loop and supports partial reads, so the apps fetch
  only the turns they are missing instead of the full transcript every time.
- **Profile listings stop re-reading every session from disk.** Unchanged
  sessions are served from an in-daemon cache, making inbox and sidebar
  refreshes much lighter on busy profiles.
- **Settings load in one round trip.** The profile snapshot computes its
  sections in parallel, caches storage sizes briefly, and lets clients request
  only the sections they need.
- **Fewer daemon-wide hiccups.** Schedule reads/writes, chat setup (including
  MCP server startup), usage pricing, Ollama probes, and device-token
  validation all moved off the event loop, so one slow request no longer
  delays every connected app.

## v0.10.10 — 2026-07-02 — schedules remember their last run

- **A schedule now records whether its last run succeeded or failed**, alongside
  when it ran, so the apps can show a job's health at a glance instead of only
  its next fire time.

## v0.10.9 — 2026-07-01 — workspace knowledge replaces raw-file RAG

- **Workspace knowledge is now a first-class Markdown wiki.** The new
  `knowledge` tool searches, ingests, maintains, lints, and indexes
  OKF-style Markdown pages under `<workspace>/knowledge/`, with SQLite kept as
  a derived profile-local index.
- **The old raw workspace RAG tools are retired.** `learn_file`,
  `search_workspace`, and `index_workspace` are no longer published; explicit
  learning now synthesizes durable Markdown knowledge instead of copying raw
  files into `.alpi/documents/`.
- **The derived knowledge index lives at `<profile>/knowledge.sqlite`.** Cleanup,
  backup, storage reporting, and prefetch now use the knowledge name instead of
  `rag/store.sqlite`.
- **Prompt and docs now separate current-turn attachments, durable knowledge,
  and Alpi self-knowledge.** Agents use attached files directly, call
  `knowledge(action="search")` for user/workspace knowledge, and keep
  `alpi_knowledge` for how Alpi itself works.

## v0.10.8 — 2026-07-01 — SMB AppleDouble files no longer break skills

- Skill validation now ignores macOS/SMB AppleDouble files (`._*`) and
  `__pycache__` artifacts, so profiles stored on SMB volumes do not fail
  validation when Finder or the mount creates resource-fork sidecars.

## v0.10.7 — 2026-07-01 — paired devices stop vanishing

- **A host no longer randomly drops to "offline" in the apps.** A momentary read
  glitch on the paired-device store could wipe every paired token at once,
  silently logging out every app and forcing a re-pair. The store is now never
  rewritten from a failed read, and two writers can no longer corrupt it.

## v0.10.6 — 2026-06-30 — peer @mention replies preserved, no stray sessions

- **A peer's `@mention` reply is preserved on the calling turn** — kept up to
  the same size cap as a normal assistant message, instead of clipped to a
  short tool-result snippet.
- **Mentioning a profile no longer leaves a stray session in it.** The
  mentioned profile answers over the peer link without persisting an
  "interrupted" chat in its own history; the exchange stays in its mention
  thread as before.

## v0.10.5 — 2026-06-29 — apps can list an MCP server's tools

- **The daemon can report the tools an MCP server exposes.** A new
  `host.mcp.tools` verb handshakes with a configured MCP server and returns its
  tool list (name + description), so the desktop and mobile apps can show what a
  server offers from a profile's settings — not just its command and args. The
  handshake uses a short timeout so a broken server fails fast instead of
  hanging.

## v0.10.4 — 2026-06-29 — email "Test connection" tells the truth

- **Testing an email account now really connects.** "Test connection" logs
  into IMAP and calls the Gmail API for real (refreshing the token when due)
  instead of just pinging the port or checking a token file exists — so a
  revoked Gmail token or a wrong password shows up as an error instead of a
  misleading green.

## v0.10.3 — 2026-06-29 — leaner session files

- **Session files shrink further.** Routine tool calls no longer carry
  per-field size/hash metadata — that's written only when a field is actually
  clipped, so everyday sessions stay lighter on disk. Older session files keep
  loading unchanged.

## v0.10.2 — 2026-06-29 — compact sessions keep long runs reviewable

- **New sessions are compact on disk.** Session files now carry
  `schema_version: 2` and store large reasoning/tool payloads as
  preview + byte count + hash instead of raw megabyte blobs. The live replay
  sidecar keeps incremental deltas intact and clips oversized frames, so long
  agent runs stay reviewable without producing 100 MB chat files.

## v0.10.1 — 2026-06-29 — faster Settings, even with huge session histories

- **The daemon serves a profile's whole Settings view in one request** — model
  and providers, usage, schedules, workgroups, email accounts and storage — so
  desktop and mobile load a profile's settings in a single round-trip instead
  of six. A noticeable difference over a remote Tailscale link. Per-device
  permission scoping and member redaction are unchanged.
- **Profiles with very large session histories stay responsive.** Listing and
  summarizing sessions now reads only a bounded head of multi-megabyte session
  files instead of parsing each one whole, so a busy profile no longer stalls
  the profile list and Settings.

## v0.10.0 — 2026-06-26 — email is a tool now; chat-app gateways retired

- **Telegram and Matrix gateways are removed.** The desktop, mobile, and terminal apps already do far more, and bridging third-party chat apps meant extra attack surface and upkeep for little gain. alpi no longer listens on any chat platform.
- **Email becomes an on-demand integration.** Instead of a poller that watches your inbox and auto-replies, the agent reads, searches, sends, and replies to mail (IMAP / Gmail) when a conversation or a scheduled job needs it. Configure an account under `alpi setup → Email`.
- **Add as many email accounts as you want** — any mix of IMAP and Gmail — instead of one of each.
- **"Gateways" is now "Email" everywhere** — `alpi email` on the CLI and an Email panel in the apps.
- **Smaller footprint:** a chunk of listener and bridge code is gone, along with the `matrix-nio` dependency.

## v0.9.35 — 2026-06-26 — a working chat isn't killed by your next message

- **A turn that's still working is no longer cancelled when you send another message in
  the same chat.** The daemon keeps the running turn alive and tells the new message the
  chat is busy; only an explicit Stop ends a turn — so long tasks (deep research,
  enrichment) run to completion instead of being thrown away mid-work.
- **Fixed a chat getting stuck unable to accept new messages** after a turn was cancelled
  or errored during start-up.

## v0.9.34 — 2026-06-25 — slow scheduled jobs finish gracefully instead of timing out

- **A scheduled job that runs long no longer dies with "agent timed out."**
  As it approaches its time limit it stops calling tools and returns a
  best-effort final reply from what it already has — the same graceful close
  long turns already got at the tool-call limit, instead of being killed with
  nothing to show.
- **The default per-job time limit is now 15 minutes** (was 10). It is a
  stuck-process backstop, not a spending cap — daily spend stays governed by
  `budget.daily_usd`. Heavy jobs can still raise it per job up to one hour via
  `schedule(add|update, timeout=…)`.

## v0.9.33 — 2026-06-25 — long turns finish with an answer instead of cutting off

- **A turn that does a lot of work no longer ends without a reply.** When an
  agent reaches its per-turn tool-call limit, it now gives a best-effort final
  answer from what it has already gathered — instead of failing with
  "interrupted before final reply" and throwing the work (and its cost) away.
- **The default tool-call limit per turn is now 100** (was 40), so skills that
  legitimately chain many steps run to completion. This limit is a
  runaway-loop backstop, not the spending cap — daily spend stays governed by
  `budget.daily_usd`; set `tools.max_steps_per_turn` in `config.yaml` to
  override.

## v0.9.32 — 2026-06-24 — skills reference the workspace implicitly via $ALPI_WORKSPACE

- **A profile's workspace is now exposed to skills and scheduled jobs as
  `$ALPI_WORKSPACE`**, injected the same way `$ALPI_HOME` already was — for
  skill scripts, cron jobs, the gateway and terminal commands. Skills no
  longer need to hard-code the workspace path.
- **Move a workspace by editing one line:** point `config.yaml`'s `workspace:`
  somewhere new and every skill or scheduled/gateway/workgroup subprocess using
  `$ALPI_WORKSPACE` follows — no skill-by-skill edits.

## v0.9.31 — 2026-06-24 — scheduled-job notifications carry the job title; skill tools list built-ins first

- **A scheduled job that notifies on completion now uses the job's title**
  as the notification headline, instead of a title-less push.
- **A skill's tools are listed with alpi's built-in tools first and MCP
  tools last**, so every client groups them the same way.

## v0.9.30 — 2026-06-24 — notifications are normalised to a clean report-grade format

- **Notifications arrive clean and structured on every device.** Whatever an
  agent writes is tidied at the source: only 🔴🟡🟢 status emoji survive
  (others are stripped), raw HTML and stray images/links are removed, and a
  long study keeps a title, section headings, subsections, lists, tables,
  quotes and code — a report, not a wall of text. Older notifications are
  tidied too when re-read.
- **`alpi_knowledge` gained two answer packs:** writing good notifications,
  and talking to a profile or workgroup programmatically.

## v0.9.29 — 2026-06-23 — scheduled-job failure alerts now name the schedule and the reason

- **A failed scheduled job's alert tells you which schedule failed and why.**
  The failure notification now carries the job's name plus the reason — the
  error, or "agent timed out" with the timeout — instead of a bare one-liner,
  so you can act on it without opening the logs. (Failures were already
  surfaced; this enriches the existing alert rather than creating it.)

## v0.9.28 — 2026-06-23 — MCP stderr reader shuts down cleanly on a failed server start

- **No more spurious traceback when an MCP server fails to start.** A server
  that died mid-handshake left its background error-log reader racing against
  the teardown, which logged an `AttributeError` as the thread fell over. The
  reader now exits cleanly. The server was already skipped correctly; this
  only removes the noisy traceback and the dangling thread crash.

## v0.9.27 — 2026-06-22 — profile-name path traversal closed; profile docs reconciled

- **Profile names are validated.** Names must match `^[A-Za-z0-9][A-Za-z0-9._-]*$`; path
  traversal such as `-p ../escape` is refused, and `default` cannot be created because it
  already exists.
- The profile docs list every per-profile file and directory.

## v0.9.26 — 2026-06-22 — host plane hardening: atomic peers.yaml, constant-time token compare, no token suffix in auth-failure logs

- **`peers.yaml` is written atomically and under a file lock**, so a crash or a concurrent update
  can no longer lose the peer roster.
- Device tokens are compared in constant time.
- A failed-authentication log no longer includes part of the presented token.

## v0.9.25 — 2026-06-22 — multi-profile organizations are first-class in alpi_knowledge

- **`alpi_knowledge` answers questions about organizations** through a new `organization` topic.
- `docs/ORGANIZATION.md` matches the bootstrap code, and a test keeps them aligned.

## v0.9.24 — 2026-06-22 — pipe-to-interpreter detector rewritten on shlex.shlex

- **Piping a download into an interpreter is detected reliably.** `curl x|bash`, multi-pipe
  chains, wrappers such as `sudo` or `env`, and redirections are all caught, while
  `curl … || bash fallback.sh` is no longer a false positive.
- SECURITY.md describes exactly what the sandbox confines on Linux and macOS.

## v0.9.23 — 2026-06-21 — ALP wire contract reconciled with the runtime

- **The ALP wire documentation matches the daemon.** `link.ask` returns flat `tokens_in`,
  `tokens_out`, `cost` and `interrupted`; the error table lists only errors that cross the wire,
  and `-32005` documents both `budget-exceeded` and `rate-limited`.

## v0.9.22 — 2026-06-20 — skills + config docs reconciled with the runtime

- **Skill frontmatter is documented accurately.** `tools:` is inventory metadata and not enforced,
  `pinned` protects a skill from deletion and curation, and `requires_config` gates the skill
  index and explicit runs.
- **CONFIG.md lists every key the code actually parses.** Added
  `tools.browser.allow_local`, `model_reasoning.effort`, `public_bio`,
  `paused`, and explicit `gateway.telegram` / `gateway.matrix`
  placeholder rows. `tools.browser.allow_local` describes its actual
  scope — loopback only (`127.0.0.1`, `::1`, `localhost`); RFC1918,
  CGNAT, and Tailscale addresses stay blocked.
- **Documentation drift won't slip through CI.** A new test extracts
  every backticked config key from `docs/CONFIG.md` and asserts each
  one resolves in `alpi/config.py` (`DEFAULT_CONFIG`, the `Config`
  dataclass, or an explicit allowlist for keys parsed by their own
  subsystems). The check is bidirectional: every leaf of
  `DEFAULT_CONFIG` and every scalar field on `Config` must appear in
  `CONFIG.md` too, so new code can't ship undocumented.

## v0.9.21 — 2026-06-20 — scheduler, filesystem, and outbound-HTTP hardening

- **Scheduled jobs survive concurrent edits and corrupt files.** Every writer of
  `schedule/jobs.json` shares one locked store, and a corrupt file is never overwritten.
- **Profile state directories are owner-only** (`0700`), and `alpi audit` flags drift.
- **`web_fetch` and `read_image` resist DNS rebinding** by pinning connections to validated
  addresses.
- The documented peer rate-limit key is corrected to `rate_limit.per_minute`.

## v0.9.20 — 2026-06-20 — current model recommendations + safer org bootstrap

- **Model recommendations refreshed against the current OpenRouter catalog.**
  The top-picks tables (skill router / cheap turns / engineering) now use
  models that actually exist — owl-alpha, DeepSeek V4 Pro/Flash, MiMo V2.5
  Pro/V2.5, MiniMax M3, Claude Opus 4.8 / Sonnet 4.6, GPT-5.5 / 5.4-mini —
  alongside the native Anthropic and OpenAI routes for users who have those
  provider keys. The example config also uses a model the catalog recognises.
- **`organizations/setup.py --check` rejects unknown skill categories.** A
  skill declaring a category outside alpi's closed enum (e.g. `factory`,
  `seo`, `qa`) is no longer silently dropped from the system-prompt skill
  index at runtime — bootstrap now fails fast with the valid list, so an org
  can't deploy a roster whose agents can't discover their own skills.

## v0.9.19 — 2026-06-19 — faster, more reliable daemon startup

- **The control socket comes up immediately on startup.** Network detection
  (Tailscale) is now cached and reused for the daemon's lifetime, run off the
  event loop, so the apps connect right away instead of waiting ~35 seconds
  while every profile probed the network in turn.
- **Only the default profile claims the shared ALP TCP port.** Named profiles
  no longer collide on it — set a unique `alp.tcp_port` to expose one.
- **A failed TCP listener no longer takes down the local socket.** If the
  network bind fails (port in use, no address), the Unix control plane keeps
  serving instead of the whole host subsystem dropping.
- **Single-instance lock** so two daemons can't start at once, replacing a
  pidfile check that raced (portable across Unix and Windows).

## v0.9.18 — 2026-06-19 — skills are fully inspectable

- **Skills are now fully inspectable from the apps.** Each skill reports
  whether it's active or inactive — and when inactive, why (a missing env var,
  binary, platform, or config key) — along with its requirements and the files
  inside it. Individual skill files can be opened on demand; secret files are
  never exposed, only counted.

## v0.9.17 — 2026-06-18 — accurate per-model context windows

- **Context windows are now accurate per model.** Instead of a fixed 200K
  default, alpi resolves each model's safe input capacity — from a bundled
  offline catalog for OpenRouter models, from litellm for cloud providers
  (OpenAI / Anthropic / …), and from the local Ollama daemon for Ollama
  models — so large-context models report their real limit and the context
  bar fills against the right denominator.

## v0.9.16 — 2026-06-18 — notifications can carry a title

- **Notifications can now carry a title.** The `notify` tool already accepted a
  `title`; it's now stored on the notification so paired apps can show it as a
  headline and the push can lead with it.

## v0.9.15 — 2026-06-17 — profile summaries expose the TTS voice

- **Profile listings now include the configured voice**, so paired apps can
  read a notification aloud in the same voice the profile uses elsewhere.

## v0.9.14 — 2026-06-17 — interrupted turns read as interrupted

- **A cut-off turn now reads as interrupted, not pending.** When a message was
  interrupted before its reply (e.g. a restart mid-task), the terminal chat now
  shows a discreet "interrupted — no final reply" on resume instead of making
  it look like the agent is still about to answer; paired apps get the same
  signal.

## v0.9.13 — 2026-06-17 — session & state hardening

- **Continuing a chat that no longer exists fails cleanly.** Asking to resume
  a deleted session used to silently start a disconnected one — your reply
  saved under a different id than the one streaming the updates. It now returns
  a clear "session not found" instead.
- **A crash while saving a chat can't corrupt it.** Session files are written
  atomically (write-then-swap), so an interrupted save leaves the previous copy
  intact instead of a half-written file.
- **Per-chat threading no longer loses updates.** On Telegram/email, two
  messages arriving at once could drop one chat's session pointer; the map is
  now updated under a lock.
- **Background commands aren't kept on disk.** A backgrounded terminal job no
  longer records its raw command (which can carry secrets) in its job file.

## v0.9.12 — 2026-06-17 — resuming a session no longer answers an old unanswered message

- **A new message no longer gets the answer meant for a previous, unanswered
  one.** If a turn was interrupted (e.g. the daemon restarted mid-research) it
  was saved with no reply; on resume the model saw that dangling request and
  answered *it* instead of what you just sent. Turns without a final reply or
  produced files are now dropped when rebuilding the prompt, so your new
  message gets its own answer.

## v0.9.11 — 2026-06-16 — `chat --once` can resume a session

- **`alpi chat --once` can now continue a conversation.** `-c` / `--continue`
  resumes the last chat (it used to be silently ignored outside the interactive
  TUI), and a new `--session <id>` resumes a specific one (erroring on an
  unknown id instead of silently starting fresh) — so a script can drive a
  multi-turn chat where each turn keeps the earlier turns' context.

## v0.9.10 — 2026-06-16 — multi-turn image editing on text-only models

- **An attached image no longer dead-ends a model that can't see images.**
  Sending a photo to a chat whose model has no vision used to abort the turn
  with "this model does not support image input." Now the agent gets the file's
  path and can route it through a vision-capable tool or skill instead of
  failing — so an agent running on a text model still inspects and edits what
  you send.
- **Agents remember the files they made earlier in the chat.** Ask to tweak an
  image the agent just produced — "now change the lighting to sunset" — and it
  reuses that file instead of replying it has nothing to work with; paths of
  files produced in the conversation now carry across turns.

## v0.9.9 — 2026-06-15 — scheduled jobs can run longer

- **A scheduled job can set its own timeout.** Jobs that do real work — deep
  research, multi-step writing, publishing — used to be capped at 10 minutes and
  killed mid-run. `schedule` (add/update) now takes an optional `timeout`
  (seconds, default 600, up to 1 hour), so a heavy weekly job gets the time it
  needs while quick jobs keep the tight default that guards against runaway
  unattended runs.

## v0.9.8 — 2026-06-15 — pause a profile

- **Profiles can be paused.** A new `paused` flag (toggled from the desktop/
  mobile apps) marks a profile as not-for-chatting — the apps sort it last and
  dim it, never pick it as the new-chat default, and open it read-only (the
  composer and retry/edit are disabled). It's a UI/chat hint surfaced in
  `host.profile.summaries`; the daemon keeps running the profile's subsystems,
  so nothing scheduled or gateway-driven stops.

## v0.9.7 — 2026-06-15 — responsive host under a busy fleet

- **The daemon stays responsive when many profiles share a workgroup mesh.**
  Background polling no longer monopolizes the host control plane: profile
  pollers are staggered instead of firing in lockstep, hand control back
  between workgroups, and poll idle or finished workgroups progressively less
  often — workgroups with a live task keep the base cadence. Local and remote
  clients that used to flap to "offline" now hold steady.
- **An idle fleet sits idle.** Hub transcripts are re-decrypted only when they
  actually change, so a daemon with nothing happening stops burning CPU on
  every tick.

## v0.9.6 — 2026-06-14 — update a daemon from the apps

- **New `host.daemon.update`** lets a paired client trigger a self-upgrade: the
  daemon checks PyPI, upgrades (uv / pipx) and restarts. It no-ops cleanly on
  source or image-pinned (Docker) installs, reporting that the version is fixed.
- **`host.version` now reports `update_available`** so the apps can flag a daemon
  that's running behind the latest release.

## v0.9.5 — 2026-06-13 — simpler notifications

- **Dropped the `source` tag on notifications.** Inbox rows no longer carry a
  `send_message`/`schedule` provenance field — it leaked an internal delivery
  detail and mislabeled owner `notify` alerts as "send msg". The apps show the
  content and the `type` (info/warning/error); nothing else changes.

## v0.9.4 — 2026-06-13 — name your scheduled jobs

- **Scheduled jobs can carry a title.** `schedule` now takes an optional `title`
  — a short human label the apps show instead of the raw prompt or `python3 …`
  command, so your scheduled tasks are easy to tell apart. Jobs without a title
  are unchanged; they keep showing the prompt.

## v0.9.3 — 2026-06-12 — system prompt hardening

- **Clearer agent ground rules.** The system prompt now states plainly that the
  workspace is a default root, not a sandbox — paths you give explicitly are
  honoured — and that a literal `curl`/`wget` command you type runs as-is.
- **Recall has its own section.** Guidance for finding past conversations,
  workspace documents, and workgroup history is grouped and easier for the
  agent to follow.
- **Matrix replies render correctly.** The agent now knows Matrix messages are
  plain text and avoids Markdown that would show as literal asterisks.
- **Denying `alpi_knowledge` is consistent** — the prompt no longer tells the
  agent to call a tool the profile has denied.
- **Profiles without an `AGENT.md` get the default persona** instead of
  starting with no identity.

## v0.9.2 — 2026-06-12 — browse past conversations exactly

- **New `session_read` tool** lets the agent open the exact message window of a
  past conversation — list recent sessions, or jump to the turns around an exact
  phrase and scroll from there — with no embedding or extra model call. It pairs
  with `session_search` (lexical find) and `recall_sessions` (semantic).

## v0.9.1 — 2026-06-12 — auto-read voice toggles

- **Profiles and workgroups can read agent output aloud automatically.** A new
  per-profile *auto-read replies* toggle and a per-workgroup *auto-read
  messages* toggle let the desktop speak each agent message as it arrives. Your
  own messages and directives are never read back.

## v0.9.0 — 2026-06-12 — `alpi audit` security posture scan

- **New `alpi audit` command** — a read-only security scan of your whole
  install, every profile at once (not just the active one). It flags
  world-readable secrets (`.env`, ALP keys, `secrets/`), public network binds,
  disabled hardening (terminal sandbox off, no spend cap, stale-call watchdog
  off), and known CVEs in your installed dependencies (via osv.dev).
- **`alpi audit --offline`** skips the network lookup for a pure-local scan.
- It only reports — it never changes permissions, config, or packages.

## v0.8.25 — 2026-06-12 — file tools won't read your .env secrets

- **The file tools now refuse `.env` files** (`.env`, `.env.local`,
  `.env.production`, `.envrc`, …) anywhere on disk, not just inside `~/.alpi`.
  Templates without secrets — `.env.example`, `.env.sample`, `.env.template`,
  `.env.dist` — stay readable.

## v0.8.24 — 2026-06-12 — budgets are dollars or nothing

- **The daily budget is now one honest knob: a USD cap, or unlimited.** The
  token-based cap is gone — tokens were never a meaningful spend limit (their
  cost varies by model), so a profile (and a workgroup) now caps real dollars
  or runs uncapped.
- Token *usage* is still tracked and charted; only the cap changed.
- Setup, the desktop app, and the docs drop the token-cap option accordingly.

## v0.8.23 — 2026-06-12 — daemon FD limit + clean stream disconnects

- **The daemon no longer runs out of file descriptors.** launchd, systemd and the Docker compose
  pin a ceiling of 8192; reinstall the daemon (`alpi daemon install`) or recreate the container
  to apply it.
- **Quitting a client no longer logs a false daemon error.** When the desktop
  app or a paired device disconnects from the live event stream, the daemon now
  ends that stream cleanly instead of recording the normal disconnect as a crash.

## v0.8.22 — 2026-06-11 — MCP servers read the profile's own .env

- **MCP servers resolve `env:` credentials from the profile's `.env`** first, then the daemon
  environment — the same precedence as every other tool.

## v0.8.21 — 2026-06-11 — local-build browsing, Gemini-safe tools, security docs

- **The browser can view your local builds.** A new opt-in
  `tools.browser.allow_local` lets the browser tool reach loopback
  addresses (e.g. a dev server at `127.0.0.1`) while every other private
  range stays blocked by the SSRF guard.
- **Tool schemas work with Gemini.** Tool argument schemas now use `anyOf`
  instead of type-union lists, which Gemini's schema translator rejected —
  the `db` tool (and any future union-typed argument) works across all
  providers.
- **Security & audit docs.** `SECURITY.md` now documents the audit-trail
  and accountability posture (what's recorded, and the honest gaps for a
  fleet), with the enterprise-audit work tracked as `AUDIT.2` in the
  roadmap.

## v0.8.20 — 2026-06-10 — heavy downloads only when they're needed

- **The daemon no longer grabs ~600 MB at boot on machines that won't use it.**
  Chromium and the embedding weights now download only when something actually
  needs them: no semantic index → no embedder, browser denied everywhere → no
  Chromium, and on Docker the prefetch is off by default (first use still
  fetches on demand). When it does run, it waits out the startup rush instead
  of competing with your apps reconnecting.
- **~150 MB of memory back per daemon.** The embedding model no longer sits
  loaded in every running daemon — it loads on the first semantic search.
- **Old Chromium builds are cleaned up.** Each upgrade used to leave the
  previous ~520 MB build behind forever; stale builds are now pruned after a
  successful install.
- **`alpi doctor` shows an Assets section** — what's downloaded, what will
  fetch on first use, your prefetch mode, and stale builds wasting disk.
- A failed Chromium install now logs a clear warning and is retried on the
  next attempt instead of failing silently.

## v0.8.19 — 2026-06-10 — OpenRouter traffic is credited to alpi

- **OpenRouter requests now identify as alpi.** Calls carry the app's name and
  version, so your OpenRouter dashboard attributes the usage to `alpi/<version>`
  instead of litellm.

## v0.8.18 — 2026-06-10 — settings apply without restarting the daemon

- **Saving settings no longer drops your connections.** Gateway configs,
  subsystem toggles and the ALP port now apply in place within seconds — the
  daemon reloads just the affected piece instead of restarting whole. On
  Docker this was the big one: every settings save used to restart the entire
  container, knocking the agent off the peer network and disconnecting every
  app mid-change.
- **Profile changes apply live too.** Creating or deleting a profile is picked
  up by the running daemon — no restart needed.
- **MCP servers work out of the box in Docker.** The image now bundles Node 22,
  so `npx`-launched MCP servers run without manual setup — and their downloads
  persist in the volume, so they install once, not on every container start.
- **`alpi doctor` now spots a corrupted fleet.** Running it on each machine
  flags cloned `/data` volumes (a peer carrying this agent's own identity, or
  one identity under several peers), two peers dialing the same address, and a
  Docker container with no advertised address for clients to reach.
- **Docs:** the Docker guide explains fleet identity (never copy a `/data`
  volume between machines) and which settings hot-reload versus the two that
  still need a container recreate (advertised address, pairing port).

## v0.8.17 — 2026-06-10 — event streams announce they're alive

- **The daemon's event stream now sends a keepalive ping every 25 seconds.**
  Desktop and mobile apps use it to tell a quiet daemon apart from a dead
  connection — they recover in seconds from daemon restarts and dropped
  Tailscale links instead of hanging on a silent socket.

## v0.8.16 — 2026-06-10 — every tool in a meaningful group

- **The tools browser lost its "Other" junk drawer.** A dozen tools (semantic
  search, notifications, workgroup posting…) sat in a catch-all bucket; every
  tool now lives in its domain group.
- **Recall tools sit where you'd look for them.** Workspace gathers document
  search, indexing and file learning; session recall joined Memory; workgroup
  search joined Collab; notify and ask_user joined Comms.

## v0.8.15 — 2026-06-10 — removing a provider removes its models too

- **Removing a provider takes its models with it.** Deleting an API key (or an
  Ollama server) now clears the profile's active model when it pointed at that
  provider — before, the model lingered in pickers and made the removal look
  like it never happened.
- **Model lists only show what you can actually use.** Saved OpenRouter models
  stay hidden while their key is missing (they come back if you re-add it),
  and a selected model whose key was removed by hand no longer surfaces in the
  apps.
- **Consistent everywhere.** Desktop and mobile Settings, the `alpi providers`
  CLI, and the setup TUI all apply the same cleanup.

## v0.8.14 — 2026-06-10 — notifications go to your own apps, not a gateway

- **Alpi can now ping you directly.** Ask to be reminded, alerted, or told when
  something finishes and the message arrives as a native notification on your
  paired desktop / mobile apps — no Telegram, no chat id, no gateway setup.
- **Scheduled jobs notify you the same way.** Set a job to notify you and its
  reminder or daily summary lands in your app inbox; the old "no chat_id and no
  default for alpi" failure is gone.
- **Reaching other people is now explicit.** Sending to a third party (Telegram,
  email, …) is a separate, deliberate step — so a job meant to remind *you*
  never accidentally messages someone else.
- **One way to set a notification's level.** A notification is `info` (default),
  `warning`, or `error` — no more overlapping "severity" and "kind" knobs to
  reason about. Your apps colour-code it accordingly.

## v0.8.13 — 2026-06-10 — security hardening pass

- **Tighter terminal guardrails.** Commands that read credential files
  (`~/.aws`, `~/.ssh`, `.netrc`, the profile `.env`), dump the environment, or
  write to config/credential files are refused outright — and the OS sandbox
  fails closed if its config can't be read.
- **The daily budget is a hard ceiling.** A long multi-step turn now aborts the
  moment it crosses the cap instead of running to completion.
- **Less reachable from a hostile network.** Web fetches block more private,
  carrier-grade, and cloud-metadata addresses (and fail closed when a host
  won't resolve); file tools refuse more credential and persistence paths
  (authorized_keys, shell rc files, launch agents).
- **Inbound messages are treated as untrusted.** Telegram/Matrix/webhook text
  gets the same injection scan + "data, not instructions" framing email already
  had; an optional `{PLATFORM}_ALLOWED_USER_IDS` pins who may drive the agent
  inside an allowed group chat.
- **Workgroup posts can't skew the budget or flood the hub.** A posting peer's
  declared cost is clamped, posting requires having joined, duplicate nonces and
  oversized/over-many posts are rejected, and handshakes are rate-limited.
- **Session logs redact more** — credential URLs, private-key blocks, and
  attachment metadata are scrubbed before they hit disk.

## v0.8.12 — 2026-06-09 — daily token usage and cost, per profile and workgroup

- **The daemon now reports the last 14 days of token usage and cost** — per day,
  split input vs output — for a profile and for a workgroup you host, so a client
  can chart spend over time instead of recomputing it.
- **Workgroup posts now carry their input/output token split**, not just a
  combined total, so a workgroup's usage breaks down the same way as a profile's.
  Posts from before this release keep their combined figure. The Usage chart
  itself lands in the desktop release.

## v0.8.11 — 2026-06-09 — recalled memory is checked for injection

- **`USER.md` and `MEMORY.md` are scanned for prompt injection when loaded.** A suspicious note is
  marked as untrusted data the model must not obey; genuine notes are never blocked.
- **Your agent's persona is left untouched.** `AGENT.md` is instruction by
  design, not recalled data, so it's never marked untrusted.
- **One shared scanner backs every check** — skills, memory, and inbound content
  now run the same injection and danger detection, so coverage stays consistent.

## v0.8.10 — 2026-06-09 — agents know the host Python version

- **When an agent writes a scripted skill's `scripts/run.py` it now knows the
  host's Python version** — the script runs on exactly that interpreter — and
  targets it, instead of guessing newer syntax that fails on an older one (e.g.
  `X | Y` type unions or `match` on Python 3.9). Terminal `python3` comes from
  PATH, so the prompt also nudges checking `python3 --version` when it matters.

## v0.8.9 — 2026-06-09 — free models get a higher per-turn step ceiling

- **A free model (zero per-token pricing) or a local one gets a much higher
  per-turn step ceiling by default (1000 instead of 40)** — long agentic tasks on
  a no-cost model aren't cut short. Paid models keep the regular cost guard, and
  an explicit `tools.max_steps_per_turn` you set is always respected.

## v0.8.8 — 2026-06-09 — turns record how long the agent reasoned

- **Each turn now records the time the agent spent reasoning before it answered**,
  persisted with the session — so a client can surface it (e.g. a collapsible
  "Reasoned for 12s"). Rich rendering lands in the desktop/mobile releases.

## v0.8.7 — 2026-06-09 — files you attach keep a preview in history

- **A file you attach now keeps its thumbnail in the conversation, not just a
  filename.** Best-effort: a file attached on one device may not be reachable
  from another, so there it falls back to a labelled chip instead.

## v0.8.6 — 2026-06-08 — agents can hand you the files they make

- **Files an agent produces are now first-class output attachments.** When a
  skill makes a file — a generated image, a PDF, a spreadsheet, a document — Alpi
  emits it on the turn and persists it with the session, so it's no longer just a
  path buried in the reply text. Works whether the agent writes a sentence or
  only hands over the file.
- **Every text surface lists them.** The terminal (`chat --once`), the TUI, the
  messaging gateways, and ALP peers all print the produced files, so a file-only
  reply is never silently lost. Rich inline rendering (image previews, etc.)
  lands separately in the desktop and mobile app releases.
- **Only real files, never guessed from text.** Only a file a tool actually
  wrote — validated by type and content, inside the profile's own folders — is
  surfaced; a chat can't smuggle in or mislabel a file by writing a path.

- **What concurrency you actually get is now spelled out.** Pointing the same
  profile at several workgroups does not spin up parallel workers: the runtime
  overlaps turns opportunistically for latency, but a profile stays one shared
  identity — single home, memory, skills, budget, provider credentials, and rate
  limits. Ask an agent about ALP concurrency and it now says this plainly instead
  of over-promising parallelism.
- **Guidance for throughput.** For predictable high-volume production, add more
  profiles/workers or run fewer active workgroups at once — not an ALP protocol
  change. Capacity scheduling is tracked as a future roadmap item.

## v0.8.5 — 2026-06-07 — serve agent-made images to remote clients

- **Mobile can now show images an agent produced.** A new daemon endpoint
  streams an image's bytes to a paired device so generated/restored photos
  render in the mobile chat, not just as a file path. Reads are scoped to the
  profile's workspace, its home, and temp dirs — a device authorised for a
  profile can fetch an image under those roots by path (see SECURITY.md).
- **Attach files from the CLI.** `alpi chat --once "…" --attach photo.jpg`
  (repeatable) sends a file with the turn, so the terminal can hand the agent
  an image to read or restore — parity with desktop/mobile.

## v0.8.4 — 2026-06-07 — skill API spend counts toward your budget

- **Paid calls inside a skill now show up in your spend.** When a skill runs a
  script that hits a metered API (e.g. image generation), its cost is added to
  the day's total and counts against the profile's daily limit — no more
  invisible spend slipping past the budget.
- **Attached files work with file-based skills.** An image (or file) you attach
  to a message now exposes its path to the agent, so skills that take a file —
  like photo restore/enhance — can act on what you attached, not just describe it.

## v0.8.3 — 2026-06-06 — chat reports the model it used

- **Easier to tell which model ran.** Each chat send now reports the effective
  model — after any per-message override — in its opening event, so a wrong or
  stale model shows up in the trace instead of being a guessing game.

## v0.8.2 — 2026-06-05 — stop stalled providers from hanging a turn

- **A stuck LLM no longer freezes the turn.** If a provider accepts a request
  and then goes silent — no first token, or a long gap mid-answer — the turn
  now fails with a clear reason instead of hanging indefinitely.
- **Automatic retry on transient hiccups.** Connection drops, timeouts, and
  rate limits retry a couple of times with backoff before giving up — but only
  before any text has streamed, so a half-written answer is never replayed.
- **Tunable, reasoning-friendly.** `runtime.first_byte_timeout_s`,
  `stream_idle_timeout_s`, and `max_retries` are configurable; defaults are
  generous so slow reasoning models aren't cut off, and `0` disables a watchdog.

## v0.8.1 — 2026-06-05 — a run ledger for unattended turns

- **Every long-running turn now leaves a record.** Agent turns, scheduled jobs,
  workgroup turns, and terminal commands each append one compact line — start,
  duration, outcome, exit code, timeout reason, last tool — so when something
  runs unattended you can see what it was doing and where it stopped without
  piecing it together from separate logs.
- **Operational, private, bounded.** It's a capped rolling log inside your
  profile; captured output is scrubbed for secrets and commands are never
  stored in the ledger.
- **See it in `alpi digest`.** The evidence digest has a new *Runs* section —
  totals by kind, the most recent failures and timeouts, and the slowest runs —
  so a quick `alpi digest` tells you what's been going wrong unattended.

## v0.8.0 — 2026-06-04 — search a workgroup's history by meaning

- **Find old workgroup decisions by meaning.** `workgroup_search` does semantic
  search over a workgroup's past transcript, so you can recall what was decided
  even when you don't remember the exact words or who said them.
- **Hub-owned and private.** Only the hub indexes its own workgroups, on its own
  machine — there's no search across other people's workgroups. Opt-in
  (`index_workgroups`), and deleting a workgroup drops it from search.
- Built on the same local index as document and conversation recall — nothing
  leaves the machine, and the encrypted transcript on disk is untouched.

## v0.7.4 — 2026-06-04 — recall past conversations by meaning

- **"When did we discuss…" now works by meaning, not just keywords.**
  `recall_sessions` does semantic search over your past conversations, so you
  can find an old session even when you don't remember the exact words.
  `session_search` (keyword) stays as the quick first pass.
- **Opt-in and forgettable.** Sessions are only indexed when you ask
  (`index_sessions`); the index lives in your profile and never leaves the
  machine. Delete a session and it drops out of recall — nothing lingers.
- The active conversation is never indexed or recalled, and nothing is
  injected automatically — recall happens only when it's actually useful.

## v0.7.3 — 2026-06-04 — learn a file into the workspace

- **"Learn this file" makes an attachment permanent.** Attach a file and ask the
  agent to learn, remember, or save it: it copies the file into your workspace
  and indexes it, so `search_workspace` can find it in later conversations — not
  just the turn you sent it in.
- **You stay in control.** Nothing is learned automatically — only when you ask.
  Learned files land under `.alpi/documents/`, dated, never overwriting an
  existing one.
- **What it learns.** Text and source files, and PDFs with a text layer; images
  and scanned PDFs only when you ask for OCR. Anything else is declined with a
  clear message.

## v0.7.2 — 2026-06-03 — attach files to chat

- **Messages can carry files.** Images, PDFs and text or source files reach the model; the TUI
  stages them with `/attach <path>`, desktop and mobile with a paperclip or drag-and-drop.
  Scanned PDFs are rendered as images for vision models, and a model without vision fails
  clearly.
- **Remote clients can upload attachments.** A new `host.attachments.stage`
  call lets a phone (or any remote client) hand the daemon a file's bytes and
  get back a path to send. Size caps and a type allowlist
  (`png` / `jpeg` / `webp` / `pdf`, plus the text types) apply.
- The model sees a file in the turn it's attached. The session log keeps
  bytes-free metadata (name, type, size) so you can see which turn carried
  which file — but a later turn doesn't re-read the bytes. Durable, cross-turn
  multimodal context is a separate step (RAG.2).

## v0.7.1 — 2026-06-03 — one network address

- **One accessible address instead of two.** A profile now has a single
  `network.host` — the address your devices and trusted peers reach it at —
  shared by both device pairing and ALP peer links. Leave it empty to
  auto-detect (Tailscale, then your LAN) or set anything: a Tailscale/VPN IP, a
  LAN IP, a hostname, or a public IP. Each plane keeps its own port. The old
  separate per-plane host addresses are gone.
- **ALP peer links work out of the box.** The ALP listener is now on by default
  (port 7423) whenever your machine has a reachable address — no switch to flip
  first. Don't want it? Turn ALP off entirely from Services; the local socket
  keeps working regardless.
- **The advertised address and the bind are separate now.** Pointing
  `network.host` at a hostname or a public address no longer stops the daemon
  from starting — alpi advertises what you typed and listens on an address it
  can actually bind. A public address still needs the explicit
  `host.allow_public_bind` opt-in (which now covers both pairing and ALP), and
  `alpi doctor` warns when the listener is exposed on every interface.

## v0.7.0 — 2026-06-03 — curator can apply its own cleanup

- **`alpi curator apply` archives stale skills.** It previews the list, asks for confirmation and
  moves each skill to `skills/.archive/`; pinned skills are never touched.
- **A workgroup phase can't silently half-transition anymore.** The hub could
  post a single message that both closed one task and opened the next (`#done …`
  + `#task …`); that post was treated as plain prose, so a phase looked
  "launched" in the conversation but never moved in the canonical task ledger.
  The hub must now use one lifecycle marker per post — a mixed post is rejected
  with a clear instruction to close first, then open next turn.
- **Cost shows up for brand-new OpenRouter models.** OpenRouter calls now
  request provider-side usage/cost, and when a model is too new to be in the
  pricing catalog the per-call cost falls back to OpenRouter's own published
  per-token prices — so spend is tracked instead of logged as $0.

## v0.6.37 — 2026-06-03 — prompt guidance adapts to the model

- **Smaller models get the reminders they need.** Less capable model families —
  local/Ollama models, OpenAI mini variants, and Gemini Flash — now receive
  extra operational guidance (reach for tools before answering; verify work
  before calling it done). Stronger families keep a leaner prompt without the
  redundant reminders.

## v0.6.36 — 2026-06-02 — a task survives a member leaving mid-task

- **Removing a member no longer strands an open task.** Kicking a member (or a
  member leaving) rotates the workgroup's encryption key. A task opened before
  that rotation used to become unreadable to the hub — it dropped from the hub's
  view and could never be closed. The hub now keeps the prior keys, so it reads
  the whole transcript across rotations and a mid-task departure leaves the task
  intact and closable.

## v0.6.35 — 2026-06-02 — the hub serves workgroup task state

- **Task state is computed once, by the hub.** A workgroup's current task, its
  recent closed tasks, and whether it's blocked are now folded on the hub and
  exposed for operators, scripts, and future clients — no decrypting and
  re-folding the whole transcript by hand. Desktop and mobile also surface a
  blocked workgroup from the transcript they already render.

## v0.6.34 — 2026-06-02 — workgroup turns recover and pipelines stop cleanly

- **Pipeline rechecks now stop at green.** A terminal phase variant such as
  `#qa-recheck` now maps back to its canonical pipeline phase (`qa`), so a
  green/PASS recheck completes the pipeline instead of reopening `build → qa`
  after launch. Negative results (`FAIL`, `BLOCKED`, `not pass`, etc.) still
  win and keep the repair/blocking path intact.
- **A member that heartbeats then dies is retried.** When a workgroup member
  posts `#working` (the "still busy" heartbeat) but its turn ends without
  delivering, the hub now re-dispatches that member instead of leaving the task
  to stall until the watchdog escalates — bounded to one retry per heartbeat.
- **Killed turns leave a trail.** Each turn now records the tail of its activity
  (and why it was stopped — idle vs hard cap) in the workgroup turn log, so a
  turn that died mid-tool is diagnosable instead of vanishing silently.
- **Per-workgroup closure deadline.** The wait before a hub may close a task
  with no peer input (default 10 minutes) is now configurable per workgroup.

## v0.6.33 — 2026-06-02 — workgroup turns die only when truly stuck

- **A productive workgroup turn is no longer killed by the clock.** A turn stops only when it
  goes idle or hits a hard backstop, and the log says which.
- **Pausing a workgroup stops it.** All automatic turns on the hub and its members halt, and
  resuming picks up a task left mid-way.

## v0.6.32 — 2026-06-01 — workgroup handoffs survive, blocks halt cleanly

- **A member's handoff is never lost.** A `#done` from a non-hub member keeps its text and
  reaches the hub.
- **A hub can halt a pipeline** with `#done BLOCKED · <reason>` until a human re-tasks it.
- A stalled task gets one last repair wake before the watchdog gives up, and a `#working`
  heartbeat earns the full turn timeout.
- **A workgroup can carry an ordered pipeline of phases**, set with `workgroup create
  --pipeline …` or in the desktop and mobile create forms.

## v0.6.31 — 2026-05-30 — Docker deployment, Umbrel retired

Alpi now ships as a plain Docker image for any Linux host; the Umbrel
package is gone.

- **Official Docker image.** `satoshiltd/alpi` runs the always-on daemon
  on any Linux box — `docker compose up -d`, then `docker compose exec
  alpi alpi` for the TUI. Multi-arch (amd64 + arm64); state persists in a
  `/data` volume.
- **Many agents per host.** Run several agents on one machine, each on its
  own ports and data volume; clients pair to `<host>:<port>` over your LAN
  or, optionally, Tailscale.
- **Umbrel package removed.** Superseded by the generic image; the old
  `satoshiltd/alpi-umbrel` is no longer maintained.

## v0.6.30 — 2026-05-29 — `#task #<slug>`, `tools.deny` visibility, opus 4.8

Three protocol / catalog tweaks bundled together.

- **Task slugs are mandatory.** Every opener reads `#task #<slug> <description>`; a slug-less
  attempt is refused with `-32011 task-missing-slug`.
- **`tools.deny` shows up in introspection.** `host.tools.list` now
  reads the requested profile's `config.yaml` and emits `denied: true`
  on each entry listed under `tools.deny`. Apps render those rows
  muted instead of pretending the agent has access. Returning the
  entry (rather than dropping it) is deliberate — the operator wants
  to see what's been switched off, not have it silently vanish.
- **Claude Opus 4.8 in the curated catalog.** `claude-opus-4-8` is now
  the flagship choice in the setup wizard's model picker; Opus 4.7
  stays as a fallback. The reasoning regex already covered the
  `opus-[4-9]` family, so thinking support works out of the box.

## v0.6.29 — 2026-05-28 — workgroup posts reach the hub again

Members on `~/.alpi/profiles/*` could not post into workgroups after
v0.6.27. The hub opened a `#task`, members were woken by the poller,
and every `workgroup_post` failed silently with
`No such file or directory` — transcripts stayed at seq 1.

- `home.alpi_root()` now strips the `…/profiles/<name>` suffix when
  the daemon sets `ALPI_HOME` to a profile dir for a dispatched turn.
  Peer scans (`find_home_by_pubkey`, `local_socket_path`) see siblings
  again instead of nesting under self. Containers/relocated installs
  with a real root in `ALPI_HOME` are unchanged.

## v0.6.28 — 2026-05-28 — per-device profile scope

- **A non-admin device can be limited to some profiles.** Pairing takes a profile list and
  `host.devices.set_profiles` changes it without re-pairing; devices paired before keep full
  access.
- Every profile-aware request and event stream is filtered to the device's scope; admins are
  unrestricted.
- `host.devices.list` is admin-only, and `alpi setup` and the desktop pairing dialog offer a
  profile picker for non-admin devices.

## v0.6.27 — 2026-05-27 — local peer routing centralised

Two more code paths still resolved co-located peer sockets by
`peer_id` instead of pubkey — `alpi peers ping` CLI and the workgroup
client. Both hit the exact bug 0.6.24 closed for the host probe and
`link.ask`: a peer pinned under any alias different from the real
profile name would route to the wrong directory and fail.

- New helper `peers_mod.local_socket_path(peer)` is the single source
  of truth for "where is this co-located peer's `alp.sock`". Tries
  `home.find_home_by_pubkey(peer.pubkey)` first, falls back to
  `peer.id` only when the pubkey isn't co-located. Five callers now
  go through it: `host.peers.ping`, `link.ask` (`alpi.alp.mention`),
  the setup TUI probe, the workgroup client and `alpi peers ping`
  CLI.
- The previous per-module helpers (`_target_home`, `_intra_socket_path`)
  are gone — no caller can drift back to id-only routing by accident.

## v0.6.26 — 2026-05-27 — Umbrel container restart hardening

Two boot-time fixes that together stop the Umbrel app from looping
through `Error: daemon already running (pid 9)` after a `stop`/`start`
or any abnormal exit.

- **Persistent fastembed cache.** `core.embed.FastembedEmbedder` passes
  `cache_dir=alpi_root() / "cache" / "fastembed"` to
  `TextEmbedding(...)`. On Umbrel this lands inside the `/data` VOLUME
  so the ONNX weights survive `restart`/`stop`/`start`; on Mac/Linux
  it lands inside `~/.alpi/` next to every other daemon-managed
  artifact. The new path inherits the existing backup exclusion
  (`cache/` is already in `alpi.backup._EXCLUDE_DIRS`).
- **A stale pidfile no longer stops a new container from starting.** The pidfile records the
  process start time, so a reused PID is recognised as someone else's and the daemon starts
  fresh.

## v0.6.25 — 2026-05-27 — device revoke is idempotent

Same UX fix as `host.peers.remove` (v0.6.23), extended to paired
devices: clicking Revoke on a row that's already gone no longer
errors out — the user's intent is "be gone", the end state is the
same either way.

- `host.devices.revoke` returns `{ok: true, existed: <bool>}` instead
  of raising `-32004 not-found` when the token_id no longer matches a
  pinned device. `host.devices.{rename,promote,demote}` still raise
  because they mutate state of an existing row.

## v0.6.24 — 2026-05-27 — local peer routing + safer reads

Two classes of peer bug closed without adding any hidden state: local
peers under an arbitrary alias now route end-to-end, and read-only
peer lookups stop materialising ALP secrets on disk. Discard stays
honest — it clears the current pending row and nothing else.

- Local peer routing resolves by **pubkey** in every code path —
  `host.peers.ping`, `link.ask` (`alpi.alp.mention`) and the setup TUI
  probes. Peering another local profile under any alias works
  end-to-end, not just on the liveness chip.
- `host.peers.pending_discard` is idempotent: discarding a pubkey
  that's no longer in pending returns `{ok: true, existed: false}`
  instead of `-32004 not-found`. Discard only removes the current
  pending row — no denylist, no cooldown, no hidden state. If the
  other peer keeps trying, the invite reappears; you decide each time.
- `_local_profile_pubkeys` and `find_home_by_pubkey` no longer
  generate ALP keypairs as a side effect of read-only lookups, so a
  `pending_list` roundtrip never materialises secrets on disk.

## v0.6.23 — 2026-05-27 — peer remove is idempotent

Removing a peer no longer fails when the peer is already gone — the
user's intent (peer unpinned) is the same end state either way, so a
stale UI, a half-succeeded retry or a parallel client should not block
the click.

- `host.peers.remove` returns `{ok: true, existed: <bool>}` in every
  case instead of raising `-32004 not-found` when the peer is missing.
  `peers_changed` only fires when the row was actually dropped.
- CLI `alpi peers remove` is unchanged — typo suggestions still help
  when you mistype an id at the terminal.

## v0.6.22 — 2026-05-27 — per-profile tool denylist

You can now hide individual tools from a profile so the LLM never
sees them in its schema and the executor refuses them. Useful for
tightening profiles exposed to less-trusted input — e.g. a librarian
profile that other peers reach via `link.ask` and that has no
business writing files, running shell, or sending mail.

- New `tools.deny: [<name>, …]` key in `config.yaml`. Denied tools
  are absent from the schema AND refused by the executor as defence
  in depth. Unknown names are no-ops, so typos are harmless.
- The `peer` tool no longer claims its prompt is "single-shot — no
  session resume"; the receiver hydrates up to 20 prior @-mention
  turns from the caller, so follow-ups already work.

## v0.6.21 — 2026-05-27 — storage report covers the whole profile

`host.profile.storage` now reports every on-disk shape a user might
want to inspect, not just chat transcripts and logs.

- New rows on top of the existing five: **skills**, **memories**,
  **rag** (workspace embeddings), **outputs** (notifications inbox),
  **gateway** (telegram/email/matrix chat sessions) and **mentions**
  (@-mention threads from ALP peers).
- Same shape and payload — clients that already iterate the response
  surface the new rows automatically.

## v0.6.20 — 2026-05-27 — outputs can be deleted

You can now remove individual entries from the agent's inbox; the
backend has the verb, owned clients use it.

- New `host.outputs.delete` RPC removes one entry by id and emits
  `output.updated { action: deleted }` so other clients drop it from
  their list. Member-callable, like the other outputs verbs.

## v0.6.19 — 2026-05-27 — gateways stay text-first

Telegram and Matrix no longer post intermediate tool-call lines into the
chat. You get a single, clean reply per turn — the same one a human
would send. If you want to watch what the agent is doing, use a
TUI / desktop / mobile session.

- Removed the per-platform ``show_tool_trace`` knob from
  ``config.yaml`` (silently ignored on load — no migration needed).
- ``@mention`` replies on gateways no longer prefix a ``◆ peer …``
  trace line.
- Owned clients (TUI / desktop / mobile) are unchanged: they keep
  rendering tool calls in their own native UI.

## v0.6.18 — 2026-05-27 — ask_user (UX.1) + approval gets cwd context

- **New `ask_user` tool for closed questions.** Desktop, mobile and the TUI render the choices
  natively; gateways fall back to a numbered list.
- The approval prompt shows the directory a command will run in.
- The agent no longer second-guesses shell commands in prose; `terminal`'s own approval is the
  safety gate.

## v0.6.17 — 2026-05-27 — runtime-created profiles come online without a daemon restart

Creating a profile while the daemon was running left it half-alive:
chat worked through ``host.sock``, but the per-profile peer-link
listener (``alp/alp.sock``) never bound. Peers that pointed at the new
profile by pubkey saw it as ``offline`` even though both lived on the
same host. The daemon had taken a one-shot snapshot of ``profiles/``
at boot and never looked again.

- The central service now rescans ``profiles/`` every 5 seconds and
  starts subsystems for any newly observed profile. New profiles
  reach ``online`` within one tick of creation, regardless of whether
  they were created from the CLI, desktop, mobile, or a script.
- A broken ``config.yaml`` in one profile no longer blocks discovery
  of the others; the offending profile is retried on the next tick.
- Profile homes resolve against the running daemon's root rather than
  the import-time root. Daemons started with ``ALPI_HOME`` pointed
  elsewhere (Umbrel deployments, tests with temp roots) now see the
  correct ``profiles/<name>/`` paths.
- ``SIGTERM``/``SIGINT`` still wake the wait immediately, so shutdown
  latency is unchanged.
- Out of scope: dynamic stop for deleted/archived profiles — those
  still require a daemon restart.

## v0.6.16 — 2026-05-26 — skill curator (AC.1, report-only)

Post-hoc curator that reads ``skills/.usage.json`` + the on-disk
skills tree and writes a markdown + json report under
``<home>/logs/curator/<UTC-timestamp>/``. Never mutates skills — apply
suggestions land in AC.2.

- New ``alpi curator review`` writes the report and prints its path.
  Flag ``--window-days N`` widens the staleness threshold (defaults
  to 30, matching ``skills_usage.STALE_DAYS``); ``--profile name``
  inspects a non-active profile.
- Heuristics: **stale** (telemetry exists, ``last_seen`` past the
  window, not pinned), **cold** (on-disk skill with no telemetry row
  whose ``SKILL.md`` mtime is itself past the window), and **prefix
  clusters** (three or more skills sharing a ``<word>-`` prefix —
  candidates for umbrella consolidation).
- ``alpi curator list`` lists past reports newest-first.
- ``alpi setup → Cleanup`` gains a **Curator reports** row that
  rm-trees every ``logs/curator/<ts>/`` dir at once. The existing
  ``Subsystem logs`` category only walked top-level files in
  ``logs/`` — the per-run subdirs would have piled up otherwise.
- Out of scope for this phase: session-narrowness detection (telemetry
  lacks session ids), upstream-update checks (no import system yet),
  and any mutation — that is AC.2.

## v0.6.15 — 2026-05-26 — prompt caching (CL.1)

- **Prompt caching.** The system prompt is a stable prefix, and models that support explicit
  cache markers get one on it automatically — no configuration needed.
- Tool definitions are byte-stable between calls, so the cache is no longer broken on every
  request.

## v0.6.14 — 2026-05-26 — storage hygiene

- ``alpi doctor`` gains a Storage check that flags outsized
  per-profile stores: sessions > 1 GB, TTS cache > 500 MB,
  workgroup transcripts > 250 MB. Warning-only — it points you to
  ``alpi setup → Cleanup`` (or desktop Manage Sessions for the
  sessions store) and never deletes on its own. Silent on the
  happy path.
- ``alpi setup → Cleanup`` splits the old "Audio cache" row into
  **TTS cache** and **Inbound media cache** so you can reclaim
  synthesised speech without touching downloaded voice notes (or
  the other way round).
- Documented contract: ``host.events.*`` is transport with a
  bounded replay window for reconnects, never the source of truth
  for anything a user can browse. Durable state lives in
  ``outputs.jsonl`` / ``sessions/<id>.json`` / workgroup
  transcripts. UI history features must read those, not
  ``host.events.history``.

## v0.6.13 / desktop-v0.3.22 — 2026-05-26 — Manage Sessions on desktop

The desktop client gets a real session manager. The Sessions
popover in the chat header now has a ``Manage sessions →``
footer link that opens a full inbox: every chat thread on the
profile, with activity, turns, and disk size; filter chips for
``All``, ``≥ 30 days``, ``≥ 90 days``, ``< 3 turns``; sort by
size / activity / turns / created. Bulk-select with checkboxes
(``⌘A`` / Shift+click range), then delete with a typed-confirm.

- The active session is locked — its checkbox is disabled and
  the row carries a ``◆ current session`` marker.
- Backend gains a ``host.sessions.delete`` admin verb that takes
  ``ids: [...]`` and returns ``{deleted, errors}``. Refuses
  in-flight sessions with ``session-busy`` and missing ids with
  ``not-found``. Removes both ``<id>.json`` and the per-turn
  replay sidecar ``_events_<id>.jsonl`` in one go.
- ``host.sessions.list`` now exposes ``size_bytes`` per row
  (session file + sidecar), so the UI can show real disk
  pressure without a second RPC.
- The Sessions popover footer also shows the per-profile
  session count next to the new link.

## v0.6.12 / desktop-v0.3.21 / mobile-v0.1.17 — 2026-05-26 — tts stops trying to be a player

- **The daemon no longer plays audio.** `tts` always writes an MP3 to the cache; the apps'
  per-message play button is the way to listen.
- `tools.tts.autoplay`, `alpi voice autoplay` and `host.voice.autoplay` are removed, and `ffmpeg`
  is no longer needed.
- TTS sent to Telegram arrives as an MP3 attachment instead of a voice note.

## v0.6.11 — 2026-05-25 — persistent inbox for proactive messages

- **Proactive messages land in a persistent inbox.** Every `send_message` and schedule failure
  files a row under the profile's `outputs/`, kept up to 500, and notifications deep-link to it.
- Rows track read state and which channels delivered them; silent runs write nothing.
- New `host.outputs.*` verbs and `output.created` / `output.updated` events let clients show the
  inbox without polling.

## v0.6.10 — 2026-05-25 — paired devices get a role (admin / member)

**Breaking:** re-pair every device after upgrading; a device without an explicit role becomes
`member`.

- **Paired devices carry a role, admin or member.** Admin devices can do remote setup —
  profiles, gateways, devices, schedules, daemon restart — while members are read-mostly. The
  local socket keeps full authority.
- `host.devices.promote` / `demote` change a device's role, and `host.version` returns the
  caller's role so clients can hide admin actions.
- `host.profile.read_file` refuses secret files for every caller.
- An empty device store no longer accepts any token; the first device is paired from the local
  socket.
- `member` limits the control plane, not the agent's tools; use the OS sandbox or separate
  profiles for that.

## v0.6.9 — 2026-05-25 — Gmail OAuth works against remote daemons

- **Gmail OAuth works against a remote daemon.** The desktop app runs the consent redirect on
  your own machine, and `alpi setup` offers a paste flow when no browser is available
  (`ALPI_HEADLESS=1` forces it).
- `host.gateway.gmail_authorize` is replaced by `host.gateway.gmail.begin` and
  `host.gateway.gmail.exchange`.

## v0.6.8 — 2026-05-25 — workspace index goes back to incremental, with safer corners

- **Workspace indexing is incremental again.** Unchanged files are skipped, removed files are
  purged, and a new workspace root, embedder or vector size triggers a full rebuild on its own.
- `force=true` forces a full rebuild and compacts the database afterwards.
- Embedding runs in batches, so a very large file no longer risks running out of memory.

## v0.6.7 — 2026-05-24 — alpi self-knowledge moves from skill to first-class tool

- **alpi's self-knowledge is a tool, not a skill.** `alpi_knowledge` lists topics and returns
  packaged reference answers, and the system prompt tells the agent to use it before answering
  questions about alpi.
- Skills are now entirely user-owned; the bundled `@alpi/` skills are removed.

## v0.6.6 — 2026-05-24 — host.version exposes a stable device_id

Mobile / desktop clients had no way to detect that two paired
connections referred to the same daemon (e.g. LAN address vs
Tailscale address). The ALN background poll was deduping by
`(ip, port)`, which still treated those as different daemons →
duplicated notifications.

- ``host.version`` now returns a ``device_id`` (UUID4 minted on
  first call, persisted in ``~/.alpi/host/device_id`` and stable
  across daemon restarts). Paired clients use it to dedupe and
  to namespace their per-daemon state. First-call mint is atomic
  (``O_CREAT | O_EXCL``, mode ``0o600``) so two clients racing the
  initial ``host.version`` cannot end up with distinct ids.

## v0.6.5 — 2026-05-22 — host.network.status no longer freezes the UI, agent notification deep link

- **Opening the default profile's settings no longer freezes the desktop.** Network probing runs
  once per request, off the daemon's event loop.
- Notification deep links from `send_message` open the right profile's chat.

## v0.6.4 — 2026-05-22 — daemon identifies itself on pair

The daemon now reports its own ``device_name`` (set via
``alpi setup``) in the ``host.version`` reply. Pairing clients
use that as the connection label instead of whatever string the
pairing URL carried — fixes mobile showing the device-being-paired
label (e.g. "iPhone") as if it were the daemon's name.

- ``host.version`` returns ``{agent_name, version, device_name}``.
  ``device_name`` is blank when ``alpi setup`` hasn't been run;
  clients then fall back to the URL-provided name (back-compat).

## v0.6.3 — 2026-05-22 — fire-and-forget schedule

Manual schedule fires from desktop / mobile no longer block the UI
for the full duration of the agent's run (often 20-60s, sometimes
minutes). The host returns immediately; the job continues in the
background and its result still arrives through the existing
`agent.message` / `schedule.done` events.

- `host.schedule.fire` validates the job id synchronously (a stale
  id from the UI still returns the same `-32004` error as before)
  and then schedules the job in a background task. The handler
  resolves in well under 100ms instead of waiting for the agent.
- `fire_by_id` now emits `schedule.done` / `schedule.failed` on the
  host event stream the same way `tick()` did, so a manual fire
  that errors out still surfaces in the UI instead of going silent
  after the initial "started" toast.
- No change to the actual job execution path — same threat-scan,
  same dispatch, same delivery surfaces.

## v0.6.2 — 2026-05-22 — user message visible mid-turn

Fix: a paired client (desktop / mobile remount) reading a session
during a long-running turn no longer has to wait until the assistant
replies to see what the user just said.

- ``Engine.run_turn`` now writes a stub turn (your message, empty
  assistant + tools) to ``session.json`` as soon as the user message
  is appended, and emits ``session_changed`` via the existing host
  event stream. The final turn replaces the stub in place — exactly
  one turn per call, no duplicates on interrupt or error.
- Side benefit: desktop's "Last activity" + chat preview update the
  instant a message lands, not minutes later when a tool finally
  finishes.

## v0.6.1 — 2026-05-22 — agent.message event + send_message default to alpi channel

- **Notifications reach your own apps by default.** `send_message` delivers to paired desktop and
  mobile apps through the new `agent.message` event; gateways are opt-in with `channel`
  (`telegram`, `imap`, `gmail`, `matrix`, `webhook` or `both`).
- Skills that pass `platform="telegram"` must switch to `channel="telegram"`.
- Scheduled jobs notify through `send_message(channel="alpi")`; failures still notify
  automatically.
- Workgroup mentions no longer raise a native banner, and the desktop shows approval requests as
  a banner when it is not focused.

## v0.6.0 — 2026-05-22 — evidence digest (OPS.1)

Minor bump closing the v0.6 reliability + operator-diagnostics cycle.

- Added ``alpi digest [--since 7d]``: a read-only local report over
  existing evidence from tool availability, gateway breaker state, skill
  telemetry, memory promotion backlog / pressure, and compaction logs.
- ``--since`` accepts ``7d`` / ``12h`` / ``30m`` shorthand or a raw
  numeric day value. ``--json`` emits the full dataclass schema for
  automation and downstream tooling.
- The digest deliberately stays small: no LLM summary, no
  recommendations, no dashboard, no metrics service, no new on-disk
  state, and no telemetry leaving the machine.
- The v0.6 cycle is now closed. Its through-line was reliability before
  new surface area: untrusted-output boundaries (CF.1), tool
  availability checks (TL.1), memory audit (CM.1), local-notification
  backend events (ALN), skill telemetry (SK.1), gateway containment
  (GW.1), and now the operator evidence digest (OPS.1).
- SK.2 ``alpi skill import`` remains deferred until there is real user
  pull for batch migration from another stack; foreground toasts for
  extra notification event kinds also stay out until a concrete UX gap
  appears.
- Umbrel package + image tag bumped to ``0.6.0``.

## v0.5.10 — 2026-05-22 — gateway containment (GW.1)

- **A failing gateway platform no longer affects the others.** Each platform on each profile has
  its own circuit breaker: after five consecutive failures it backs off, from 5 minutes up to an
  hour, while sibling platforms and other profiles keep running.
- A `gateway.state` event reports transitions, and `alpi doctor` lists any degraded or disabled
  platform.
- Umbrel package + image tag bumped to `0.5.10`.

## v0.5.9 — 2026-05-21 — skill telemetry (SK.1)

- **Skills record how they are used.** View, use and patch counts are kept per skill in
  `skills/.usage.json`, for measurement only — nothing is pruned.
- `alpi doctor` gains a Skills group, including pinned skills that have gone unused.
- Umbrel package + image tag bumped to `0.5.9`.

## v0.5.8 — 2026-05-21 — AX Local Notify (ALN) groundwork

- **New host events for mobile notifications:** `wg.mention` when a workgroup post mentions the
  profile, and `chat.turn_done` when a substantial user turn completes.
- Mobile notifications poll the daemon over your own network — no APNs, FCM or relay in between
  — at the cost of system-paced latency. The mobile side lands in `mobile-v0.1.4`.
- Umbrel package + image tag bumped to `0.5.8`.

## v0.5.7 — 2026-05-21 — memory audit CLI (CM.1) + reasoning capability fix

- **`alpi memory audit` reports memory quality without changing anything:** file pressure,
  low-confidence entries, near-duplicates, misplaced operational state and the promotion
  backlog; `--json` for scripts.
- The reasoning-effort setting appears for every reasoning-capable model, `openai/gpt-5.*`
  included.
- Umbrel package + image tag bumped to `0.5.7`.

## v0.5.6 — 2026-05-21 — tool availability probes (TL.1)

Patch on top of v0.5.5. Tools whose optional runtime deps are missing
are now hidden from the LLM schema and flagged in ``alpi doctor``,
so a partial install can't surface a broken capability that fails at
the first call.

- Every ``Tool`` subclass can override ``check() -> (available, reason)``.
  Default is "available"; override for tools with heavy/optional deps.
- ``browser`` / ``stt`` / ``tts`` probe their underlying package
  (``playwright`` / ``faster-whisper`` / ``edge-tts``) and report
  unavailable cleanly when missing instead of crashing at call time.
- Probes are cached for 60 s so schema generation stays cheap.
- ``alpi doctor`` adds a ``Tools`` group: a single OK summary when
  every tool is available, plus one warn row per missing tool with the
  reason. Warns don't break the exit code, so a minimal install still
  passes CI / cron.
- Probes never install anything; if a probe passes but the tool's
  runtime still fails, the tool's own error remains the final
  authority.
- Umbrel package + image tag bumped to ``0.5.6``.

## v0.5.5 — 2026-05-21 — untrusted-data boundary for tool outputs (CF.1)

Patch on top of v0.5.4. Every tool result, success or error, now
re-enters the model's message history wrapped in explicit
data-not-instruction markers. Built-in tools and MCP tools share
the same hook, so hostile text from web pages, MCP responses,
subprocess stderr, file contents or DB rows is consistently
boundaried — never treated as latent instructions.

- Every ``role: "tool"`` message is wrapped with
  ``[UNTRUSTED OUTPUT tool=<name> kind=data|error …]`` /
  ``[END OUTPUT tool=<name>]``. The raw payload is preserved
  verbatim between the markers so debugging stays intact.
- Errors (previously injected as plain ``ERROR: …``) are wrapped
  the same way with ``kind=error`` — stderr, MCP failures, DB
  errors all flow through the same boundary now.
- When a known injection pattern (override directives, fake system
  / assistant turns, credential-exfil verbs, invisible unicode) is
  detected, a ``[SECURITY WARNING …]`` line is added inside the
  header so the model treats the body with extra suspicion.
- The wrapping is model-context only — the desktop / mobile / TUI
  event streams keep the raw payload, so no marker noise appears
  in the user-facing UI.
- Umbrel package + image tag bumped to ``0.5.5``.

## v0.5.4 — 2026-05-21 — reasoning effort per profile model (MC.1)

Patch on top of v0.5.3. Profile setup and settings now expose a
`off / low / medium / high` reasoning effort control for the default
model, applied automatically to every flow that uses it (TUI,
desktop, mobile, schedules, gateways, skills).

- Setup wizard prompts for effort right after picking a reasoning-
  capable model. Setting is persisted in `model_reasoning.effort`.
- Desktop + mobile profile settings expose the same control. The
  dropdown only appears when the picked model supports reasoning;
  changing to an unsupported model auto-clears the value.
- Mid-chat model overrides (desktop / mobile composer, TUI `/model`)
  do NOT carry effort — overrides are "a different model, no extra
  knobs". Tool sub-models (`web_extract`, `read_image`) are also
  protected.
- Supported: OpenAI o-series, Claude 3.7+ / 4+, Gemini 2.5+,
  DeepSeek R1, Grok 3-4 reasoning. OpenRouter models always show
  the dropdown — alpi forwards the unified `reasoning` parameter,
  which OpenRouter normally no-ops when the upstream provider
  doesn't accept it under default routing.
- Umbrel package + image tag bumped to `0.5.4`.

## v0.5.3 — 2026-05-21 — memory routing: pronoun-based, not noun-based

Patch on top of v0.5.2. Fixes a misrouting where "your name is Clara"
ended up in `USER.md` (as "the user wants to be called Clara") instead
of `AGENT.md` (as the assistant's own identity).

- Memory tool now decides target by pronoun, not by keyword: *you / your*
  → `AGENT.md`, *I / my* → `USER.md`. Seven explicit disambiguation
  examples cover the common confusions.
- System prompt reinforces the rule in the Memory section.
- Umbrel package + image tag bumped to `0.5.3`.

## v0.5.2 — 2026-05-21 — file mutation evidence after each tool batch (CF.2)

Patch on top of v0.5.1. The agent now reasons over what actually got
written to disk instead of what it intended to write.

- After every tool batch, the next model step receives a compact
  footer listing each file touched: path, op, hash, byte + line
  delta. Closes a common failure mode where the model "thought" it
  had written something it hadn't.
- Failed writes (lint refusal, missing file, no unique match…)
  produce no footer entry — only committed state is reported.
- The same evidence rides the host event bus as `file_mutations`,
  tagged with profile + session, with a short diff preview per
  mutation for future surface integration in desktop / mobile chat.
- Umbrel package + image tag bumped to `0.5.2`.

## v0.5.1 — 2026-05-21 — terminal approvals over the host plane (CF.3)

First v0.6-cycle release. Caution-command approvals (recursive `rm`,
`sudo`, force-push, …) are no longer TUI-only — desktop and mobile
can answer them through the daemon. The TUI flow is untouched; the
daemon and any subscribed client are now equivalent surfaces.

- Caution prompts are streamed to subscribed clients while the
  engine waits; the client's choice resumes the turn.
- 60-second auto-deny matches the existing TUI behavior; nothing
  changes for schedules, gateways, or cron-platform turns.
- A client opened mid-window can fetch in-flight prompts on mount
  and answer them, instead of silently waiting out the timeout.
- Each prompt carries the active profile so multi-profile daemons
  show the right tag in the modal.
- Bumped Umbrel package + image tag to `0.5.1`.

## v0.5.0 — 2026-05-21 — v0.5 cycle close: mobile client shipped

Milestone release closing the v0.5 cycle; no new daemon contract since `v0.4.54`.

- The cycle delivered capability hardening, a memory quality pass, the host plane for owned
  clients (pairing, per-device tokens, events) and the first mobile client.
- `desktop-v0.3.6` and `mobile-v0.1.1` require `alpi v0.4.52` or newer.
- Umbrel package + image tags bumped to `0.5.0`.

## v0.4.54 — 2026-05-20 — daemon: skill prose-mode env passthrough, terminal `ALPI_HOME`/`WORKSPACE`, `send_message` profile env

Patch on top of v0.4.53. Four gaps left over from the v0.4.52/.53 env-isolation refactor:

- `alpi/tools/skill.py`: prose branch of `_run_or_test` now calls `_state.add_skill_env(...)` with `requires_env`/`env` from the eligibility metadata. Parity with `_view`. Without this, prose-only skills can reach for `terminal` while the subprocess sees no declared secrets.
- `alpi/tools/terminal.py`: `_build_subprocess_env` now always sets `ALPI_HOME=str(get_home())` (contextvar-bound, not `os.environ`) and `WORKSPACE=str(cfg.workspace_path)` when the active profile declares one. Skill prose like `${ALPI_HOME}/skills/.../triage.py` and `ls -d $WORKSPACE/*/` now resolves correctly.
- `alpi/tools/send_message.py` + `alpi/gateway/delivery.py`: `SendMessage.run` builds `env = effective_profile_env(get_home())` and threads it into `delivery.default_chat_id(env=)` and `delivery.send_to(env=)`. `_send_email_sync` now accepts `env` and routes through `ImapClient.from_env_map(env)`. Closes the multi-profile leak where `TELEGRAM_*` / `WEBHOOK_POST_URL` / `IMAP_*` only living in `<home>/.env` were invisible.
- Tests: 4 new in `tests/tools/test_skill_env_chain.py` + `tests/tools/test_send_message.py` covering the prose-run env path, contextvar-bound `ALPI_HOME`, `WORKSPACE` from `config.yaml`, and profile-env passthrough in `SendMessage`. Existing `send_message` stubs updated to the new `env=` kwarg.
- Bumped Umbrel package metadata and image tags to `0.4.54`.

## v0.4.53 — 2026-05-20 — daemon: profile-env shortcuts in skills, scheduler, mail, and setup wizards

Patch on top of v0.4.52: that release promised per-profile env isolation but left a handful of `skill_eligibility` callsites and subprocess-env builders still defaulting to `os.environ`, plus three setup wizards still mutating it on credential writes. The visible symptom: a chat in profile `doc` reported `coros` (and any skill with `requires_env`) as inactive, because the daemon no longer pre-loaded per-profile `.env` into the process env and these callsites never picked up `effective_profile_env(home)`. The remaining `os.environ` mutations after this patch are process-level only (`ALPI_PROFILE` in `cli.py::_resolve_home` so child processes inherit the active profile; `LITELLM_LOG` in `llm.py` to silence the library at import) — never profile credentials.

- `alpi/tools/skill.py`: `_run_or_test` (the dispatch for `skill(action='run' | 'test' | 'invoke')`), `_state_tag` (used by `skill(action='list')`), and `keyword_match_hint` (the per-turn skill hint injected into the prompt) now all pass `env=effective_profile_env(home)` to `skill_eligibility`. `_list` and `keyword_match_hint` build the env once per call and reuse it across rows.
- `alpi/service.py`: workgroup-dispatch subprocess env is now `effective_profile_env(home, extra={ALPI_HOME, ALPI_WORKGROUP_DISPATCH, …})`. Was `dict(os.environ)` + manual extras.
- `alpi/scheduler/run.py`: the three `subprocess` env builders (no-agent job dispatch, agent-mode `alpi chat --once`, schedule supervisor spawn) all go through `effective_profile_env(home, extra=…)`. The local `_load_profile_env` helper is removed — it duplicated the new helper.
- Credential wizards no longer write secrets into the process environment; they read and
  pre-fill from the profile's own `.env`, so multi-profile setups show the right account.
- Tests: 4 new in `tests/tools/test_skill_ch1_eligibility.py` pinning the contract — `requires_env` satisfied by the profile's `.env` (and only the profile's) must keep the skill eligible from `run`, `list`, the system-prompt skills block, and the per-turn keyword hint. Full suite **1841 passed, 76 skipped**.
- Bumped Umbrel package metadata and image tags to `0.4.53`.

## v0.4.52 — 2026-05-20 — daemon: multi-profile isolation, seq-only events, lite/detail host plane, Tailscale perf

Daemon-side contract release. The daemon keeps accepting legacy params for older clients;
`desktop-v0.2.20` and the matching mobile builds adopt the new shapes.

- **Profiles no longer leak secrets into each other.** Each profile's `.env` is read on demand,
  and the daemon never writes provider keys into the shared process environment.
- **Events use a sequence cursor.** `host.events.history({after_seq, limit, kinds})` returns
  `{events, next_seq}`; the wall-clock `since` is ignored, and clients subscribe first, then
  backfill.
- **Every mutation emits an invalidation event** (`config_changed`, `gateway_changed`,
  `peers_changed`, `profile_changed`, `workgroup_changed`, `schedule.changed`…), so clients
  refresh without polling.
- **Lighter payloads.** `host.skills.list` omits skill bodies unless `include_body=true`,
  `host.profile.summaries` carries only list fields with `host.profile.detail` for the rest,
  workgroup transcripts load their recent tail first, and WebSocket traffic is compressed.
- `host.chat.send` opens with a `session_start` frame, and heavy host handlers no longer block
  the daemon's event loop.
- Umbrel package + image tags bumped to `0.4.52`.

## v0.4.51 — 2026-05-19 — `host.network.*` RPCs for desktop/mobile pairing config

Closes the parity gap between `alpi setup → devices → network` (CLI) and the desktop / mobile pairing UI. Previously the desktop's `PairDeviceModal` could only show whatever `host.devices.generate` returned and gave no way to switch between Tailscale and LAN or set a custom advertised host — the user had to drop to the terminal. Three new RPCs make the daemon's pairing endpoint queryable and editable over the host plane.

- `host.network.status` returns the live pairing endpoint plus every detected candidate
  (`tailscale`, `lan`, `configured`) and a diagnosis, so clients can offer a picker.
- `host.network.set_advertised({host?, device_name?})` persists the advertised address and device
  name; public, loopback and reserved addresses are rejected, and the result says whether a
  restart is needed.
- `host.network.restart_host_server` SIGTERMs the running daemon so the supervisor respawns it with the fresh config — same mechanism as `alpi setup`'s `_restart_daemon_for_apply`. Idempotent: returns `{ok: true, restarted: false}` when no daemon is running.
- All three verbs are flagged `_LOCAL_ONLY_METHODS` in `alpi/host/server.py` — a paired remote client cannot mutate daemon config or restart the host server over WS. Handlers use `server.home` (not the module-level `_ROOT`) so the host plane contract holds for any daemon instance.
- Wiring: registered in `alpi/service.py` alongside the rest of the host plane handlers. No changes to existing verbs; the new namespace is purely additive.
- Tests in `tests/host/test_network_rpc.py` pin the validation matrix, the three RPC handlers across every status branch (no network, tailscale-only, lan-only, configured override), write paths (persist, unset, no-op, reject invalid), absent-vs-empty parameter semantics, and the local-only transport gate via `_handle_request(..., require_token=True)`. Full suite green.
- Bumped Umbrel package metadata and image tags to `0.4.51`.

The CLI's `_devices_network_setup` flow continues to work unchanged. The desktop UI that consumes these RPCs ships in its own release cycle.

## v0.4.50 — 2026-05-19 — session list exposes last-turn previews for mobile inbox

Adds two truncated fields to every row returned by `host.sessions.list`. The mobile inbox previously had to choose between rendering the thread topic (`first_user`, oldest turn) or pulling the full session per row just to show the latest activity — neither is acceptable for a scrolling list.

- `alpi/host/sessions.py`: `list_sessions` now emits `last_user` and `last_assistant` alongside `first_user`. Both are `_truncate`d to the same `_FIRST_USER_MAX` ceiling, so a one-line preview fits without leaking session context. Single-turn sessions report `first == last`; empty-turn rows report empty strings; no client-side post-processing is required.
- `alpi/host/device_state.py`: `_latest_chat_for` forwards the same fields into the `device.state.latest_chat` payload so the mobile home screen can pick them up without a second round trip.
- Tests in `tests/host/test_sessions.py` pin the contract: multi-turn ordering (first = oldest, last = newest), single-turn identity (first == last), and empty-turn defensiveness.
- Bumped Umbrel package metadata and image tags to `0.4.50`.

## v0.4.49 — 2026-05-19 — schedule auto-infers `no_agent` for shell-style prompts

Closes a foot-gun in the `schedule` tool: a scheduled job whose prompt looked like a shell command (`python3 .../say.py "..."`) but omitted `no_agent=true` was accepted as a regular agent prompt — at fire time the daemon then fed the shell line to the LLM as user input instead of running the script. Caller-side mistakes (LLM forgetting the flag) now self-correct at `add` time.

- `schedule(action="add")` infers `no_agent=true` when the prompt is a Python script path, and
  validates the path at save time; an explicit `no_agent=False` is respected.
- Output of `add` includes `· auto-inferred no_agent=true (prompt is a shell command)` when the inference triggered, so both the LLM and the user see the correction.
- A legitimate LLM prompt that happens to begin with `python` (`python is a language, explain it`) is NOT inferred — the discriminator is the first non-flag token, not just the first word.
- Bumped Umbrel package metadata and image tags to `0.4.49`.
- Tests added: 13 cases in `tests/core/test_schedule_auto_no_agent.py` covering the helper heuristic (python forms, prose rejection, flag-skip, quoted paths, `${ALPI_HOME}` expansion) and end-to-end `add` action (auto-inference triggers, persists `no_agent: true`, output suffix, path validator still rejects bad paths, explicit `False` is respected, normal LLM prompts unchanged). Full suite **1761 passed / 75 skipped**.

## v0.4.48 — 2026-05-19 — host event backfill + scheduled reply contracts

Host-plane reliability release for desktop/mobile clients and scheduled jobs.

- Added `host.events.history({since?, kinds?, limit?})`, backed by a bounded in-memory ring and compacted JSONL sidecar, so clients can backfill recent daemon events after reconnecting. Live event frames now include `at`.
- Added structured schedule outcomes: `schedule.done` / `schedule.failed` now carry `message`, `reply`, `delivered_to`, and `silent`, so clients can render clean notification bodies without parsing operational status text.
- Marked final assistant replies explicitly with `AgentEvent.final`; CLI, host chat, ALP, scheduler delivery, and tests now ignore pre-tool assistant narration when building canonical replies.
- Improved host device/config APIs: Ollama model discovery returns partial `{models, errors}` results, and `host.voice.preview` provides short daemon-side MP3 previews with controlled errors.
- Bumped Umbrel package metadata and image tags to `0.4.48`.
- Refreshed organization tooling: profile voice assignment, more patient ALP peer verification, organization skill linting, workgroup task bootstrap, and explicit per-skill `state/db.sqlite` notes.
- Docs: updated architecture contracts for host events/schedule payloads and rewrote the roadmap around v0.6 reliability + v0.7 owned-client UX.
- Tests added for event history, schedule reply payloads, final assistant replies, run-once preamble suppression, Ollama errors, voice preview, host chat, and ALP handlers.

## v0.4.47 — 2026-05-18 — host runtime version + Umbrel local package prep

Small compatibility release for desktop/mobile clients and real Umbrel smoke tests.

- `host.version` returns the running Alpi agent name and package version over the host plane. Clients can now display daemon compatibility from the same API surface they already use, without filesystem reads or subprocess probes.
- Umbrel package metadata moves to `0.4.47`, and `deploy/umbrel/prepare-local-package.sh` generates a side-load package with public icon/gallery URLs while keeping the official store submission manifest clean (`icon: ""`, `gallery: []`).
- Umbrel operations docs now describe the local side-load flow, digest pinning, app icon verification, and persistence checks.
- Tests cover the new host verb, local package generation, and the updated Umbrel asset expectations.

## v0.4.46 — 2026-05-18 — agent date/time grounding

- **The agent knows the current date and time.** The system prompt carries the user's timezone
  and every turn adds a fresh `# NOW` block, so long sessions no longer guess the day — without
  breaking the prompt cache.

## v0.4.45 — 2026-05-18 — Telegram profile isolation

Multi-profile daemons now isolate Telegram gateway state per profile. Telegram long-polling allows only one active `getUpdates` consumer per bot token, so Alpi now treats one Telegram bot per profile as a hard contract and avoids using a sibling profile's env for inbound authorization.

- `alpi setup → telegram` and `host.providers.set_key` reject a `TELEGRAM_BOT_TOKEN` already configured by another profile, naming the owner. `alpi.home.telegram_token_owner()` and `read_profile_env()` provide the shared implementation, including quoted-token handling.
- `Platform` now captures a frozen per-profile env snapshot (`{**os.environ, **<home>/.env}`) at construction. Telegram reads its token from that snapshot, and inbound allowlist checks use `delivery.is_allowed(..., env=platform.env)` so another profile's allowlist cannot authorize this profile's chats.
- Scheduler delivery now loads the firing profile's `.env` into a local env dict and passes it through `delivery.default_chat_id()` / `delivery.send_to()` instead of relying on process-global env.
- Telegram 409 conflicts now log once with recovery instructions and back off for 60s, avoiding noisy repeated warnings when another machine still owns the bot token.

Docs: `docs/ARCHITECTURE.md` and the bundled knowledge reference document the one-bot-per-profile rule, frozen gateway env snapshots, and the current caveat that Matrix / IMAP still read some credentials directly from `os.environ`.

## v0.4.44 — 2026-05-17 — daemon event bus: 4 new kinds for native desktop notifications

- **Four new daemon events for native desktop notifications:** `wg.done` when a hub closes a
  task, `schedule.done` / `schedule.failed` after every job, and `budget.threshold` when spend
  crosses 80% or 100% of the daily cap. The desktop consumer ships in `desktop-v0.2.19`.

## v0.4.43 — 2026-05-14 — resource-leak hygiene pass after the RAG bloat hunt

Audit triggered by the v0.4.42 RAG freelist bug. Read-only sweep across SQLite handles, file opens, subprocess pipes, and the live daemon's FD table found a handful of small leaks and one latent deadlock — none catastrophic, but the same shape of slow accumulation that bit us on `rag/store.sqlite`. Fixed the actionable ones.

- **Daemon subprocesses can no longer deadlock on a full pipe.** Output is drained while the
  child runs, with bounded memory, and a failing send no longer leaks zombie processes.
- **File-handle leaks closed** in image reading, binary sniffing and background terminal
  spawns.
- **Dead state in `service.py`'s workgroup poller** — `cancelled` flag set but never read; removed.

## v0.4.42 — 2026-05-14 — whole-machine backup with pre-encrypt preview + RAG bloat fix

Per-profile backup was the wrong primitive: a typical user runs 2–3 profiles and forgetting one defeats the point. `alpi backup` now archives the entire `~/.alpi/` tree in one shot, shows a per-profile + largest-files preview *before* prompting for the passphrase, and `--force` restore is a clean replace instead of an overlay. Surfacing the preview also caught a long-standing bug: a 1.6GB `rag/store.sqlite` made of 99.997% dead SQLite pages, a force-reindex leak that's now fixed at the source and exposed in setup → Cleanup as a one-click VACUUM.

- `alpi/backup.py` rewritten for whole-home semantics: `_iter_files` prunes `cache/`, `logs/`, `.trash/`, `*.sock`, `*.pid` + `.DS_Store`/`Thumbs.db` recursively; header carries `"scope": "machine"` (validated on `inspect` and `restore`); default filename is `alpi.<YYYY-MM-DD>.alpi-backup`. The `-p` flag is ignored by both commands.
- `restore --force` now wipes the target's children AFTER the AEAD tag verifies (never on wrong passphrase or tampered archive), preserving the archive file itself if it lives inside the target. `_restore_entries` rejects tar roots other than `alpi-home`.
- New `backup.preview(home)` returns a split breakdown (default section for global config + default-profile data, profiles section per named profile) plus the top 5 individual files ≥1MB. `cmd_backup` prints it before the passphrase prompt; Ctrl-C aborts before any Scrypt work.
- RAG bloat fix — `alpi/tools/workspace.py::_index` runs `VACUUM` after a `force=True` rebuild commits (was leaving the old pages on the SQLite freelist forever). `alpi/core/store.py` gains `reclaimable_bytes()` + `compact()` helpers. `setup → Cleanup` gains a "RAG store bloat" entry with a special `vacuum` action — no unlink, just reclaim.
- Docs (`docs/OPERATIONS.md` + the `references/operations.md` mirror) updated to whole-machine semantics. 26 backup + 7 cleanup + 24 workspace tests passing; full suite 1673 green.

## v0.4.41 — 2026-05-14 — `safe_write_secret`: atomic credential writes close the TOCTOU window

`write_text` + `chmod 0o600` is two syscalls — between them the file briefly exists at umask perms (0o644) and a local attacker can read it. This release centralizes the pattern in one helper and uses it at every alpi credential write.

- New `alpi/secrets_io.py::safe_write_secret(path, content, mode=0o600)`: writes via `tempfile.mkstemp` (O_EXCL + 0o600 at creation, random unique name in the target dir), then `os.replace` onto the target. Immune to a stale `<target>.tmp` sibling lingering at looser perms — the deterministic-tmp + O_CREAT approach from a draft of this release would have inherited that file's mode.
- Refactored 4 callsites to use it: `model_selector._atomic_write_env` (.env writes), `mail/gmail_auth._save` (gmail token), `alp/pending.save` (pending peers yaml), and `alp/keys.create` (the worst case — was writing the private key directly to its final path and chmod'ing after).
- Tests cover the helper directly (0o600 mode, no tmp left behind, custom mode, bytes input, parent-dir creation, umask resistance, tmp cleanup on write error); existing integration tests for the 4 callsites pass unchanged.

## v0.4.40 — 2026-05-14 — pre-write lint refuses syntactically broken writes

A malformed `jobs.json` silently disabled the scheduler in v0.4.39 testing; same class of bug for `config.yaml`, skill scripts, `pyproject.toml`. This release runs a parser-based syntax check before every `write_file` / `edit_file` lands on disk — on failure the write is refused and the original file (if any) is untouched.

- New `alpi/tools/_lint.py::lint_content(path, content)`: `.py` via `ast`, `.json` via `json`, `.yaml`/`.yml` via PyYAML, `.toml` via `tomllib` on 3.11+ or `tomli` on 3.10 (now a conditional dep). Other suffixes pass through. Errors include source line/col.
- `write_file` lints `content` before tmp+rename; `edit_file` lints the post-replace content. Either rejects without touching disk.
- Tests cover each parser (valid + invalid) plus the two write paths; `docs/ARCHITECTURE.md` and the `references/architecture.md` mirror document the new behavior.

## v0.4.39 — 2026-05-13 — `no_agent` cron mode: skip the LLM for deterministic scripts

Cron jobs whose work is deterministic (data sync, file processors) had no reason to spawn a full agent turn but did, costing ~$0.05–$0.13 and ~20–30s per fire. This release adds an opt-in `no_agent: true` flag that exec's the prompt as a shell command directly.

- `scheduler/run.py::_run_script_only` shlex-tokenizes the prompt (`shell=False`), expands `${ALPI_HOME}`, and merges the profile's `.env` over inherited env so the firing profile's `FOLDER` wins over a sibling's. Empty stdout = silent ok; non-empty + `platform` = delivered.
- `validate_no_agent_command` form-based allowlist: only `python[3] [flags] <script>` or `<script>` directly, where `<script>` is under `${HOME}/skills/<category>/<name>/scripts/`. Blocks `-c`/`-m` and non-python executables even with a skills/ path in args. Enforced at `schedule(add|update)` and before exec.
- `Schedule` tool gains a `no_agent` parameter; the on↔off transition re-runs the appropriate validators against the inherited prompt.

## v0.4.38 — 2026-05-13 — todo as binding contract: engine re-prompts when the model closes early

The `todo` tool used to be advisory: a model could `add` + `start` a task list and then close the turn with a final text-only message, leaving work unfinished. Cheap models did this routinely ("Hecho" with a 22-byte scaffold). This release turns open todos into a contract the engine enforces.

- `Session.todos` (runtime-only) replaces the module-level `_TODOS` in `alpi/tools/todo.py`. Parallel sessions (desktop / gateway / scheduler) no longer share state.
- `alpi/tools/todo.py` is wired via a `ContextVar`; the engine binds the current session's store before invoking tools and resets in `finally`.
- New guard in `alpi/engine.py`: when the model returns without `tool_calls` and any todo is `pending` or `in_progress`, the engine appends a synthetic `role: user` continuation listing the open items + remaining steps, and re-loops. Bounded by `max_steps_per_turn` (default 40), so a model that refuses to advance cuts off naturally.
- Premature `assistant_done` suppression: when the guard fires the text the model emitted to close early is no longer emitted as a final `assistant_done` event — only legitimate closes surface as final.
- `todo` tool description now states the contract explicitly so well-behaved models avoid tripping the guard at all.
- Tests cover per-session isolation, guard firing with open todos, no-guard when todos are completed or never opened, persistent-refusal bounded by `max_steps`, store-binding correctness, and cross-session non-leakage.
- Skill docs clarify where secrets live: shared profile secrets in `~/.alpi/.env` via
  `requires_env`, and per-skill credentials and runtime auth state under `<skill>/secrets/`.
- v0.6 roadmap: new `CL.1` item parks prompt caching across providers (OpenAI/Gemini automatic, Anthropic explicit markers) with the stable-prefix invariant as the cross-cutting precondition.

## v0.4.37 — 2026-05-13 — FD leak fix for skill DB calls

Long tool-heavy turns could exhaust the daemon's open-file limit after repeated `db` tool calls, then surface as unrelated save failures such as `ledger.json.tmp`.

- Fixed the `db` tool SQLite leak: `sqlite3.Connection` context managers commit/rollback but do not close, so per-call skill DB connections are now explicitly closed.
- Ledger saves now log and drop an `OSError` instead of crashing a live turn when the process is already under FD pressure.
- `host.chat.send` now emits an `error` frame before `done` if the engine raises mid-turn, so desktop clients do not silently clear the pending turn before seeing the failure.
- Added regressions for DB FD exhaustion, ledger `EMFILE` handling, and chat error-before-done ordering.

## v0.4.36 — 2026-05-13 — daemon loop isolation + chat event replay sidecar

A scheduled job in one profile could freeze a live chat stream in another because the scheduler tick ran inline on the daemon's asyncio loop. Fixes the cause and adds a client-side recovery path.

- Scheduler `tick()` and ad-hoc `host.schedule.fire` now run in `run_in_executor` so a long `subprocess.run` can't block gateway listeners, ALP, or `host.chat.send` in sibling profiles.
- New per-turn JSONL sidecar (`sessions/_events_<session_id>.jsonl`) + `host.chat.events_since` RPC: a desktop whose stream socket dies mid-turn replays missed frames from disk instead of losing the reply.
- `host.chat.send` keeps draining and persisting events even after the client socket dies, so the sidecar always ends with `reply` + `done`.
- 5s `heartbeat` keepalive on `host.chat.send` so long tool calls don't trip the client's stall watchdog.

## v0.4.35 — 2026-05-13 — config surface trim + two save-time bug fixes

- Fixed silent data loss: `config.save()` was dropping `tools.terminal.approval.allowlist` because `TerminalToolConfig` lacked an `approval` field and `_tools_delta()` never serialized it. New `ApprovalConfig` dataclass closes the round-trip; regression test added.
- Fixed phantom config: `memory.low_confidence_max_age_days` was documented as configurable but never loaded from YAML. Now an honest constant (`alpi.memory.LOW_CONFIDENCE_MAX_AGE_DAYS = 30`); calibration is the v0.6 evidence-gated `AI(1.c)` item, not a user knob.
- Twelve config keys that were technical tuning rather than preferences became constants — image
  resizing, browser typing, research step counts and gateway typing indicators among them.
- `alpi logs --source` now accepts `service` (was missing despite `service.log` being a real file). `compaction.jsonl` description clarified to include `fired=false` cases (tool-truncation-only).

## v0.4.34 — 2026-05-13 — capability hardening v0.5 (CH.3): memory promotion queue

Auto-compaction must never write to `USER.md` / `MEMORY.md` / `AGENT.md` directly — a single bad summary would otherwise pollute long-term memory. This release introduces a staging queue between compaction and durable memory, with a genuine human-in-the-loop gate.

- New `alpi/promotion.py` module: append-only JSONL store at `<home>/memories/promotion_queue.jsonl`. Bounded (`MAX_PENDING = 200`) and pending candidates auto-expire after `MAX_AGE_DAYS = 30` on read. Each candidate carries id, source, session_id, model, target file, text, confidence, and preview warnings.
- `alpi/compaction.py` gains `parse_candidates()` (tolerant JSON parser for the LLM's structured output) and `emit_candidates_from_summary()` which runs an extra short LLM call against the just-built summary using `CANDIDATE_PROMPT`. On enqueue, each candidate is annotated with the same warnings `memory(action="add")` computes at write time — operational-state heuristic, cross-file duplicate, safety scan — so the preview is genuinely useful.
- Engine wires the extraction step right after `auto_compact` emit. Each fired compaction emits up to 5 candidates per call. Best-effort: any LLM error is swallowed so compaction itself never breaks on flaky extraction.
- Two `memory` tool actions surface the queue safely: `promotion_list` (read-only) and `promotion_discard(id)` (drops without writing). **There is no agent-callable apply.** The agent cannot promote facts to durable memory by any tool call — `promotion_apply` returns a clear error pointing at the CLI.
- New CLI `alpi memory promote` is the only write path from the queue. Interactive review with `[a]pply / [d]iscard / [s]kip / [q]uit` per item; `--apply-all` and `--discard-all` cover unattended sweeps. Applications go through the standard `memory(action="add")` safety pipeline; if that path rejects (safety scan, duplicate), the candidate stays in the queue for retry.
- Tool description text in `memory` updated to advertise the new actions and explicitly direct routing user "remember this" requests to ``add``, not the queue.
- Tests: 32 new (9 queue store + 11 tool actions including warnings on enqueue + 10 compaction integration + 2 adversarial probes confirming the agent has no apply path). Suite 1590 passed.

## v0.4.33 — 2026-05-13 — capability hardening v0.5 (CH.2): granular terminal approval allowlist

- `tools.terminal.approval.allowlist` now accepts two entry shapes in the same list: legacy **pattern descriptions** (e.g. `recursive rm`, `sudo`) bypass an entire severity-category, and new **command globs** (e.g. `sudo apt *`, `git reset --hard origin/main`) match the literal command via `fnmatch` for per-command exceptions. Entries that match a built-in pattern desc keep the old category-bypass behavior; anything else is treated as a glob.
- Globs only override **caution** classification — `dangerous` commands stay blocked regardless of allowlist contents (no override path for `mkfs`, `dd of=/dev/…`, fork bombs, pipe-to-interpreter, ssh-key reads, system-dir writes).
- Globs do **not** apply to **compound** commands (containing `&&`, `||`, `;`, `|`, newline, backticks, or `$(…)`). Otherwise `"sudo apt *"` would also approve `sudo apt update && rm -rf build`. Compound commands fall back to the prompt unless a category-desc bypass covers them.
- `classify()` now scans every pattern and returns the **worst** severity, not the first match — a dangerous pattern hiding behind an earlier caution one (`rm -rf build && mkfs.ext4 /dev/sda`) is now correctly classified as `DANGEROUS` and blocked, even with `recursive rm` in the allowlist. Restores the "dangerous commands stay blocked regardless of allowlist" invariant.
- Storage stays in `config.yaml`. No second policy file, no `exec-approvals.json`. The `Always` button still persists pattern-descs; users wanting per-command globs hand-edit the list.
- The decision's `reason` now distinguishes `config allowlist` (legacy desc match) from `config allowlist (glob: '<entry>')` so audit logs are unambiguous.

## v0.4.32 — 2026-05-13 — capability hardening v0.5 (CH.1): skill eligibility fields

- **Skills can declare what they need:** `requires_bins`, `requires_config` and `platforms` join
  `requires_env`. A skill whose requirements are missing is hidden from the index and listed as
  inactive with the reason.
- Explicit invocations (`skill(action="run" | "test" | "invoke")`) on an inactive skill fail fast with a clear "missing …" error instead of half-running and failing mid-turn.
- `skill(action="create")` accepts the three new params directly; `set_meta` accepts them too. `skills_index_block` and `keyword_match_hint` also skip schema-invalid skills so malformed hand-edits never leak into the prompt.

## v0.4.31 — 2026-05-12 — capability hardening v0.5 (CH.0 + CH.4) + compaction event log

- **CH.0** — docs/code reconciliation: `docs/SKILLS.md` now lists `state/` as the fifth subdir and all skill actions (`view`, `patch`, `validate`, `set_meta`, `reset_state`, `run`, `test`, `invoke`); `docs/ARCHITECTURE.md` corrects memory char limits (`USER_CHAR_LIMIT = 3000` / `MEMORY_CHAR_LIMIT = 5000`) and documents v2 quality metadata (confidence/reinforcement/expiry, Trojan-Source scanner, post-turn reviewer).
- **CH.4** — regression guard: sentinel-based tests assert `skills_index_block` and `keyword_match_hint` stay metadata-only and never inject SKILL.md bodies, scripts, or references into the system prompt.
- **Compaction event log** — every `auto_compact` event now appends one JSONL line to `~/.alpi/profiles/<name>/logs/compaction.jsonl` (before/after tokens, summarized-message and tool-truncation counts, trigger, session id, model, ctx_window). Feeds CM.1 audit in v0.6. Compaction policy stays as constants in `alpi/compaction.py` — no config knobs until evidence demands them.

## v0.4.30 — 2026-05-12 — auto-compact: preemptive context compaction before LLM overflow

- New ``alpi.compaction`` module: cheap tool-output truncation first, then proportional summarization that preserves system + head + tail; never destroys history on a failed summarizer.
- Engine fires ``auto_compact`` events when projected prompt exceeds ``trigger_ratio`` of the model's context window; ctx window resolved via the existing ``alpi.ctx_window`` (litellm + Ollama runtime).
- ``/compact`` is now a manual "force auto-compact now" shortcut routed through the same pipeline — no second code path.

## v0.4.29 — 2026-05-12 — chat concurrency: interrupt-and-replace on the same session (+ desktop-v0.2.11)

- ``host.chat.send`` now serializes by ``session_id`` and interrupts the previous turn when the user sends a replacement prompt on the same session.
- Desktop chat events now carry ``request_id`` so stale ``interrupted`` / ``reply`` / ``done`` frames from the cancelled turn are ignored.
- Fixes the "mixed replies / pending turn cleared by the wrong stream" bug on the desktop chat surface.

## v0.4.28 — 2026-05-12 — per-profile env isolation + silent scheduled jobs + MCP grouping

- Per-profile ``.env`` loads in the daemon now use ``override=True`` so later profiles do not inherit the first profile's provider keys.
- Scheduled jobs without ``platform`` are now silent by default; auto-delivery stays opt-in for explicit gateway jobs.
- ``host.tools.list`` groups MCP tools as ``MCP · <server>`` instead of dumping them into ``Other``.

## v0.4.27 — 2026-05-12 — host introspection verbs (tools + skills body)

- New ``host.tools.list`` verb exposes the live tool registry to the host plane, with UI-facing category metadata.
- ``host.skills.list`` now returns the skill ``body`` and ``path`` so clients can render the full SKILL.md content.
- Unblocks desktop browse panels for tools and skills without special-case filesystem access.

## v0.4.26 — 2026-05-12 — peer status probes + TUI session sync + log rotation

- Fixes peer-status reporting in ``alpi doctor`` and consolidates probe timeout handling around the shared ALP ping constant.
- TUI ``@peer`` mentions now persist into the local session log, so desktop and TUI stay in sync on the same session file.
- Rotating logs now actually rotate; Telegram 409 polling spam is deduplicated and backed off.
- IMAP gateway metadata now includes the SMTP keys consistently across CLI, host-plane config, and desktop settings.

## v0.4.25 — 2026-05-12 — streaming `link.ask` (ALP.4)

- ``link.ask`` can now stream signed response chunks over the existing ALP transport when callers pass ``stream: true``.
- TUI and desktop ``@peer`` mentions render incrementally instead of waiting for a single atomic reply.
- ``peer`` tool and gateway paths keep the non-streaming shape, so interactive and delivery surfaces can diverge cleanly.

## v0.4.24 — 2026-05-11 — identity drafting as a primitive

- New ``alpi.identity`` module extracts public-bio drafting from the CLI into a reusable primitive.
- New host verb ``host.identity.draft`` lets desktop and future clients request a drafted bio without TUI coupling.
- Fixes the previous quote-stripping bug in drafted bios.

## v0.4.23 — 2026-05-11 — memory v2 quality pass (AI(1).c)

- Memory entries now carry confidence / capture / reinforcement metadata and support reinforcement on near-duplicate writes.
- Low-confidence, never-reinforced entries can auto-expire after a configurable age.
- ``memory(add=...)`` accepts ``confidence`` and batch-add now behaves per-item instead of all-or-nothing.

## v0.4.22 — 2026-05-11 — BA local RAG over `workspace/`

- Adds ``search_workspace`` and ``index_workspace`` for per-profile semantic recall over the user's workspace.
- Uses a local ``sqlite-vec`` store, ``fastembed`` for embeddings, and opt-in OCR with ``rapidocr-onnxruntime`` for scans/images.
- Supports incremental reindex, deleted-file purge, force rebuild on embedder mismatch, and daemon-side asset prefetch.
- Prompt/search guidance now routes "what do my files say about X?" queries to workspace recall before regex search.

## v0.4.21 — 2026-05-10 — `alpi` reserved as a profile name

- ``alpi`` is now reserved alongside ``default`` so the bundled identity cannot be shadowed by a user-created profile.
- The same rule is enforced across CLI and host-plane profile creation.

## v0.4.20 — 2026-05-09 — robust endpoint detection + diagnostic pairing errors

- Host advertised-address detection now prefers a platform-neutral UDP routing probe before falling back to shell parsing.
- Pairing failures now surface structured endpoint diagnostics instead of a generic "cannot pair" error.

## v0.4.19 — 2026-05-09 — pairing admin is local-only at the transport layer

- Pairing-admin verbs are now blocked on remote WebSocket transport and remain local-only over the Unix socket.
- Closes a protocol hole where a paired device token could manage other devices on the host.

## v0.4.18 — 2026-05-09 — Gmail OAuth from the host plane

- Adds host-plane support for interactive Gmail OAuth so desktop can configure the gateway without shelling out to ``alpi setup``.
- Includes validation and host-side config plumbing for the desktop flow.

## v0.4.17 — 2026-05-08 — short timeout on peer-ping probes

- Tightens the host peer-probe path so noisy or slow peers stop holding status refreshes open for too long.
- Keeps the dedicated regression coverage in ``tests/host/test_probes.py``.

## v0.4.16 — 2026-05-08 — host plane keeps WebSocket open for multiple RPCs

- Host WebSocket connections now accept multiple RPCs on the same socket instead of one message per connection.
- This is the server-side prerequisite for the desktop pooled remote WebSocket hot path.

## v0.4.15 — 2026-05-08 — TUI rich-text polish (BB)

- Improves TUI markdown / rich-text presentation and adds regression coverage for the new styling path.
- Removes the shipped BB item from the roadmap now that it is live.

## v0.4.14 — 2026-05-07 — post-turn memory reviewer (AI(1).b)

- Adds the post-turn memory reviewer pass plus the related config wiring.
- Includes dedicated regression coverage for the reviewer behavior.

## v0.4.13 — 2026-05-07 — memory write safety scan (AI(1).a)

- Memory writes now go through the same safety scanner used for skill content.
- Blocks prompt-injection, secret leakage, invisible Unicode, and other dangerous payload classes before persistence.

## v0.4.12 — 2026-05-07 — skill safety primitives (AT)

- Skill deletion is now recoverable through archive-on-delete plus a pinned flag for protected skills.
- Adds the schema/runtime support needed for safer future curation passes.

## v0.4.11 — 2026-05-07 — system prompt sharpening for skill quality (AS)

- Tightens system-prompt guidance so the agent reaches for relevant skills more reliably before generic tools.
- Ships with focused prompt-behavior regression tests.

## v0.4.10 — 2026-05-07 — desktop connection stability and session listing

- `host.sessions.list` — accepts an optional `limit` so clients can load recent sessions quickly without parsing every session file on dropdown open. Results remain newest-first, and search-capable clients can still request the full list.
- Desktop host-plane compatibility — remote connections are treated as IP endpoints, avoiding unbounded hostname / mDNS resolution in the desktop WebSocket transport.
- Umbrel package — container entrypoint now monitors both the daemon and TUI process; if the daemon exits, the container exits non-zero so Umbrel / Docker can restart it instead of leaving a half-alive app.
- Tests — session limit coverage, desktop host-client transport tests, and Umbrel entrypoint assertions cover the new release behavior.

## v0.4.9 — 2026-05-07 — Umbrel host summaries and pairing labels

- `alpi/host/device_state.py` — daemon liveness now uses `os.kill(pid, 0)` instead of shelling out to `kill -0`. This fixes `host.profile.summaries` inside the slim Umbrel container, where the external `kill` binary may not exist.
- `alpi setup -> Devices -> Network` — new optional pairing name (`host.device_name`). Pairing QR labels now resolve through configured name, Umbrel device hostname, system hostname, then `Alpi`, avoiding container-id labels such as `cded386e8d10`.
- Docs / Umbrel package — package docs, compose tag, manifest version, submission notes, and publish workflow default move to `0.4.9` so the Umbrel image can ship the daemon-summary fix.
- Tests — host device-state coverage verifies the daemon liveness check no longer depends on an external `kill`; Umbrel setup tests cover saving the pairing name.

## v0.4.8 — 2026-05-07 — skill runtime contracts and composition

- `alpi/tools/skill.py` — `output_schema` is now a real runtime contract for scripted skills. `skill(action="run")` validates JSON stdout against it, `skill(action="test")` exercises the same scripted path as a minimal harness, and `skill(action="invoke")` adds strict composition for scripted skills only (`scripts/run.py` + `output_schema` required).
- `alpi/tools/_skill_schema.py` — frontmatter validation understands `output_schema` and validates a small JSON Schema subset (`type`, `properties`, `required`, `items`, `enum`) without adding a new dependency.
- Docs — `docs/ARCHITECTURE.md`, `docs/SKILLS.md`, `docs/ROADMAP.md`, and `alpi/prompts/system_prompt.md` now describe the three execution surfaces clearly: `run` for general entry, `test` for harnessing, `invoke` for structured composition. BF-8 (versioning/install-update flows) is moved out of the active cycle and kept in **Future releases**.
- Tests — `tests/tools/test_skill_run.py` (invoke/test/runtime contracts), `tests/tools/test_skill_schema.py` (`output_schema` frontmatter validation), `tests/tools/test_skill_set_meta.py` (`output_schema` metadata updates).

## v0.4.7 — 2026-05-07 — skill execution and schedule guardrails

Five fixes converging on one theme: the agent loop should make it
hard to lie about side-effects and easy to do the right thing in one
call. Distilled from a real 35-turn session that ended up with a
duplicate cron job, a fragmented memory write across 16 calls, and
three "done — no, you didn't" exchanges.

- **`skill(action="run")`** runs a skill's `scripts/run.py` with its own directory and
  environment, and returns its output; a skill without a script returns its instructions
  instead.
- `alpi/tools/memory.py` — `memory(action="add", entries=[...])` batches multiple writes into one call. Each entry is duplicate-checked independently and the target file is written once, so a later duplicate/limit failure cannot leave a half-written batch. Partial successes return the kept entries plus per-skip notes. Works for `USER.md`, `MEMORY.md`, and `AGENT.md`. Backwards-compatible: `content=...` still works.
- **`schedule` refuses near-duplicate jobs** unless `force=true`, and `schedule(action="update")`
  edits a job in place.
- `alpi/tools/_skill_schema.py` — `tools:` frontmatter validator now accepts MCP names (`name__methodCamelCase`) alongside snake_case built-ins. Stops the validator from flagging an MCP tool name as a typo.
- `alpi/prompts/system_prompt.md` — four new rules in **Tool use** ("past tense ⇒ tool_call this turn", "list before create when state is involved", no trailing "if you'd like, the next step…", memory is for facts not runtime logic) and a "Running a skill" paragraph in **Skills** that names `skill(action="run", ...)` as the canonical execution path.
- Docs — `docs/ROADMAP.md` marks BF as active and narrows Skills v2 to the remaining backlog now that the real-world skill stress test has shipped.
- Tests — `tests/tools/test_skill_run.py` (9), `tests/tools/test_memory_batch.py` (9), `tests/core/test_schedule_dedup.py` (10), `tests/tools/test_skill_schema_mcp.py` (6).

## v0.4.6 — 2026-05-06 — chat rewrite truncation over host plane

- `alpi host` — `host.chat.send` accepts `rewrite_from_turn` when resuming an existing session. The hydrated session is truncated before the new turn runs, so desktop "rewrite from here" continues from the kept prefix instead of carrying discarded turns in memory/context.
- `tests/host/test_chat.py` covers the resumed-session truncation path: kept turns/messages are trimmed to the requested prefix and usage counters are reset before the new turn runs.

## v0.4.5 — 2026-05-06 — schedule no-save + desktop hot-path cleanup

- `alpi scheduler` — scheduled jobs now invoke `alpi chat --once --emit-events --no-save`. A schedule run still streams events to the scheduler for delivery, budget, and logs, but it no longer writes a local chat session. This keeps cron output out of TUI / desktop profile history.
- `alpi cli` — `--continue` / `tui.auto_resume` now resume only local chat sessions. Historical scheduled, gateway, workgroup, and system sessions already present under `sessions/` are skipped.
- `alpi host` / desktop — profile `latest_session` is treated as local-chat-only. Desktop also rejects non-chat session payloads defensively so older daemons or historical files cannot open scheduled/gateway/workgroup turns as a normal profile chat.
- Desktop — streaming/render hot paths were reduced: filesystem-change reloads are debounced, active streaming avoids full session rereads, historical turns are memoized, and composer peer probes no longer rerun on every profile-list refresh.

## v0.4.4 — 2026-05-06 — daemon PATH for MCP spawns + docs alignment

Fixes MCP servers crashing silently when reached through the daemon
(desktop client path): the daemon's launchd / systemd PATH did not see
user-installed Node / Python tools, so `npx`-based servers failed with
`command not found`. The TUI was unaffected
— it inherits the user's shell PATH. Plus a docs sweep to match the
per-machine daemon reality and a v0.5 roadmap pivot to "owned device
access".

- `alpi/mcp/client.py` — `_augmented_path()` prepends user-tool dirs (nvm, volta, homebrew, `/usr/local/bin`, snap, `~/.local/bin`, `~/.cargo/bin`, `~/.bun/bin`, `~/.deno/bin`) ahead of the inherited PATH; `_build_env` writes it into every MCP subprocess env. Tests in `tests/mcp/test_mcp.py` cover preservation, ordering, and skip-when-absent.
- Docs — `alpi daemon status/start` replaces `alpi setup → Service → Install`, Matrix joins the gateway list, `alpi backup` / `alpi restore` are top-level. Knowledge skill mirrors re-synced.
- `docs/ROADMAP.md` — v0.5 theme renamed to "owned device access"; new `AX-desktop-remote` work item for desktop multi-host host-plane connections (local Unix socket vs paired remote daemon over WebSocket).

## v0.4.3 — 2026-05-06 — Umbrel app + companion endpoint cleanup

Closes the first Umbrel-ready deployment of alpi and tightens the
device-access story around the host plane. Umbrel now ships as a real
app package running the existing TUI behind Umbrel's app proxy, the
daemon/setup UX stops pretending systemd or launchd exist inside the
container, and `Devices` gains an explicit network override so mobile
and desktop companions can advertise a stable endpoint instead of
depending entirely on autodetection.

- `deploy/umbrel/alpi/` — new Umbrel app package: Docker image, app manifest, compose file, entrypoint, and store-facing docs. The package persists the profile under `/data/.alpi`, serves the Textual TUI via `ttyd` on port `8080`, and publishes the host-plane WebSocket on `49200` for paired clients.
- `alpi/cli.py` — `alpi setup` is Umbrel-aware. The daemon lifecycle screen is hidden there, services read as `managed by Umbrel`, `Devices -> Network` lets the user pin an advertised host, and the old ambiguous ALP label `TCP port (inter-machine)` becomes `Peer TCP listener`.
- `alpi/host/network.py`, `alpi/service.py`, `alpi/host/server.py` — host-plane remote access now separates the address the server binds from the address the client QR advertises. Umbrel binds the host API inside the container and can advertise `umbrel.local`, a Tailscale IP, or a MagicDNS hostname without relying on container-local network detection.
- `alpi/doctor.py` — daemon health checks report Umbrel-managed state instead of implying a missing system service.
- `alpi/host/device_state.py` — host config coercion now accepts `host.tcp_port` edits through the same device-facing config surface as `alp.tcp_port`.
- Docs — Umbrel operations, persistence, and submission flow land under `deploy/umbrel/`; deployments docs now spell out the split between the host-plane companion endpoint (`host.*`) and the ALP peer listener (`link.*`, `workgroup.*`).

## v0.4.2 — 2026-05-05 — workgroup poller correctness + protocol-aligned language

Tightens workgroup dispatch so peers in the same daemon stop blocking
each other, kills a class of wasted dispatches against already-closed
tasks, and makes peer agents follow the language of the active
``#task`` instead of defaulting to English. ALP wire behaviour is
unchanged; ``alp.v`` stays at 1. The fixes align the implementation
with the protocol description and update ALP.md where the description
had drifted.

- Workgroup dispatch is single-flight per profile again, so peers receiving the same task run in
  parallel instead of queueing behind one another.
- Each profile's preempt watcher manages only its own dispatches, so one profile can no longer
  stop another's turn moments after it starts.
- ``alpi/service.py`` — ``_should_dispatch`` no longer fires ``collective #task opened`` when ``active_task()`` shows the task has been ``#done``-closed. Without this, a member whose poller saw the original ``#task`` after the hub had already closed it would dispatch a turn whose only legal outcome was ``#skip`` — burn budget for a noise post.
- ``alpi/service.py`` — workgroup dispatch prompt grows a final ``LANGUAGE`` block: write every post (substantive, ``#working``, ``#skip``, ``#done``) in the language of the active ``#task``. Recency-biased placement at the end of the prompt (the trigger message is otherwise English-dominated, which leaked into ``#working`` reasons even when the ``#task`` was Spanish).
- ``alpi/alp/agent_context.py`` — ``LANGUAGE`` rule in the system-prompt guardrails simplified to "match the language of the active ``#task``". Previous wording defaulted to English with a briefing override clause that was never wired (no parser, just a hint to the user); briefing is for problem framing, not configuration.
- ``docs/ALP.md`` — *Workgroups → Preemption* updated to describe ``_INFLIGHT`` as ``(wg_id, profile) → {…}`` and the watcher's per-profile scope, with a one-line reason for the keying. Wire shape, methods, and invariants unchanged. The protocol's intent (``single-flight per profile``) was already correct — only the implementation snippet was wrong.

## v0.4.1 — 2026-05-04 — host plane over WebSocket, per-device pairing tokens

Closes the daemon-side foundation for **AX-mobile** and unifies the
desktop control path: the host plane now serves `host.*` over a
WebSocket on Tailscale or LAN in addition to the existing Unix
socket, every remote request carries a per-device pairing token,
and the desktop Tauri layer routes its previously-shelled-out
commands through the same JSON-RPC verbs.

- **A WebSocket listener for paired devices** on port 49200 (`host.tcp_port`), bound only to
  Tailscale or private-network addresses and requiring a device token; the Unix socket stays
  token-less.
- ``alpi/host/devices.py`` — pairing-token store at ``~/.alpi/host/devices.yaml`` (mode 0600) with ``host.devices.{list,generate,revoke,rename}`` verbs. ``secrets.token_urlsafe(24)`` (192 bits, 32 chars). The full token escapes the daemon exactly once (in the QR returned by ``generate``); listing redacts to a ``token_id`` (last 8 chars).
- ``alpi/host/network.py`` — ``detect_bind_ip()`` picks Tailscale first, falls back to the first private LAN address, returns ``None`` when neither exists (listener stays Unix-only). Tailscale lookup uses ``tailscale ip -4`` with a fallback to parsing ``ifconfig`` so the daemon works under launchd on macOS where the App Store binary refuses subcommands without a GUI/keychain context.
- ``alpi/host/probes.py`` — new ``host.gateway.probe``, ``host.peers.ping``, and ``host.model.ctx_window`` verbs. Same logic the desktop used to shell out to via ``alpi gateway probe``, ``alpi peers ping``, and ``alpi ctx``; now reusable from any host-plane client.
- ``alpi/host/workgroup_admin.py`` — ``host.workgroup.{create,update,add_member,kick,remove,action,post}`` covers workgroup CRUD end-to-end so mobile (and the migrated desktop) no longer need a CLI subprocess.
- ``alpi/host/device_state.py`` — ``latest_session`` is the most recent local chat session. Gateway, schedule, workgroup, and other non-interactive turns stay out of the TUI / desktop profile history.
- TUI ``alpi setup → Devices`` is a real device manager: list paired devices with ``Last seen``, **+ Add device** generates a one-shot QR (compact ``{v:2, i, p, n, t}`` payload, ECC-L), Rename / Revoke per device. The QR generator runs inside ``ui.activity()`` so the user sees feedback while it builds.
- ``desktop/src-tauri/src/lib.rs`` — workgroup CRUD, gateway probe, peer ping, and ctx-window resolution dropped their ``Command::new("alpi")`` shell-outs and now call ``host_client::call(...)``. Two shell-outs remain on purpose: ``service_action`` (the daemon may not be running yet) and ``voice_test`` (audio plays on the client machine). ``alpi`` is no longer required on ``$PATH`` for general desktop use.
- Docs — ARCHITECTURE / SECURITY / CONFIG document the two transports, the bind invariant, and the device-token lifecycle. Knowledge skill mirrors track the public docs.

## v0.4.0 — 2026-05-03 — secure device access

Closes the alpi side of the v0.4 cycle: profile state now has a
shared device-facing host-plane API, profiles are portable through
encrypted backup/restore, and desktop/mobile clients can use the
daemon contract instead of reading profile files directly.

- ``alpi/host/device_state.py`` — new host-plane read/mutation surface for device clients: profile list/summaries, bounded file reads, profile storage, config field edits, gateway status/config, skills, workgroups, workgroup members, and Ollama model discovery. These are ``host.*`` verbs, not desktop-only helpers, so mobile can reuse the same daemon contract.
- ``alpi/backup.py`` — encrypted profile archive/restore is part of the 0.4 baseline. Restore validates v1 crypto parameters before Scrypt and pre-validates archive paths before writing, so hostile archives cannot force partial extraction or unbounded KDF work.
- Docs — roadmap moves v0.4 to shipped history; architecture documents ``host.device_state`` as the shared desktop/mobile device state layer.

## v0.3.14 — 2026-05-03 — encrypted profile backup / restore

Two new top-level commands close the v0.4 **AW** roadmap item and
make the profile portable between machines: ``alpi backup`` writes
``<profile>.<YYYY-MM-DD>.alpi-backup`` (single file, 0600,
passphrase-encrypted, zero-knowledge); ``alpi restore PATH``
reverses it into the active profile, refusing a non-empty target
unless ``--force``.

- ``alpi/backup.py`` — Scrypt KDF (n=2¹⁷, r=8, p=1) → ChaCha20-Poly1305 over a gzipped tar of the profile. Same primitives as ``age`` with a passphrase recipient, but no new runtime dep — ``cryptography`` is already pinned. Header (KDF params, salt, nonce, profile name, timestamp, file count) is bound as AAD so any tamper flips the AEAD tag.
- Excludes: ``cache/``, ``logs/``, ``profiles/`` (nested-profile root), ``.trash/``, ``*.sock``, ``*.pid``. Memories, skills (incl. ``state/``), sessions, ``.env``, ``config.yaml``, ALP keys all round-trip.
- Both commands accept ``--passphrase-stdin`` for scripting; otherwise prompt with hidden input (and confirmation on backup). Restore refuses entries with ``..`` segments — a hostile archive cannot escape the target dir.
- ``tests/core/test_backup.py`` — 14 cases: round-trip, ephemeral exclusion, wrong passphrase, header tamper, archive overwrite refusal, target overwrite refusal + ``--force``, header inspect without decrypt, non-backup file rejection, path-traversal rejection, empty passphrase, empty profile, plus two CLI end-to-end via ``CliRunner``.

## v0.3.12 — 2026-05-03 — `default_agent.md` slim

Rewrote the persona seed and lifted operative rules into the
system prompt. New profiles boot with a 10-line audience-neutral
persona (no "engineering-level familiarity assumed", no project-
ethos baked in). Project rules
live in `system_prompt.md` where they apply to every profile.

- ``alpi/prompts/default_agent.md`` — 30 → 10 lines. Identity + Voice (5 bullets) only. Stance section dropped (paternalistic / audience-assuming). "Edit me" meta-block dropped (the user edits via chat).
- ``alpi/prompts/system_prompt.md`` — new ``## Conversation`` section consolidates operative rules that were scattered between ``default_agent.md`` and ``Tool use``: match user's language on replies (persist in English), quote paths verbatim, don't ask clarification on minor ambiguity, don't ask rhetorical permission. Deduplicated against the existing ``Tool use`` section.
- ``alpi/prompts/system_prompt.md`` — skill-creation guidance retuned: "consider creating" instead of "call it proactively", with an explicit "create without asking only when the pattern is clearly recurring". Lowers the false-positive rate where a single one-off ask would trigger a skill.
- Existing profiles untouched — ``~/.alpi/<profile>/memories/AGENT.md`` is user-owned content. Only new profiles seed with the slim shape.
- An opt-in suite of end-to-end tests with a real model (`pytest tests/llm --llm`).

## v0.3.11 — 2026-05-03 — skills overhaul

Skill surface tightened after a strategic review of comparable
agent workflows, plus integration probing on real profiles.

- **Persistence in English.** `memory` / `skill` / `schedule` tool descriptions mandate English on every persisted entry regardless of chat language (they reload into context every turn). Three pre-existing Spanish examples in `system_prompt.md` translated.
- **`requires_env` enforced + subprocess passthrough fixed.** `skills_index_block` filters skills with unset env vars; `_list` tags them `[inactive: missing env var FOO]`. `_view` now forwards declared vars to terminal subprocesses — without that fix scripts ran with empty `$VAR`.
- **Frontmatter schema validator.** `alpi/tools/_skill_schema.py` — `Issue(field, severity, message)` per problem; errors block, warnings surface to the agent. Covers every documented field. `skill(action='validate')` returns `ok=False` on errors and no longer writes `__pycache__`.
- **SQLite first-class — `db` tool + `reset_state`.** `db(action='query'|'exec', skill, sql, params)` over `<skill>/state/db.sqlite`. Stdlib `sqlite3`, zero new deps. Quotas: 50 MB / 10k rows / 5 s busy timeout. Per-skill scope; bundled rejected. `skill(action='reset_state')` wipes `state/`. Scanner is env-aware: `os.getenv("VAR")` allowed only when declared.
- **Keyword discovery boost.** Optional `keywords:` in frontmatter; engine injects a per-turn `# SKILL HINT` when the user message contains any keyword as a whole token. Hyphenated keywords supported. Cap 3 hits per turn.
- **`set_meta` + `edit` hardening.** New `skill(action='set_meta')` — surgical frontmatter update, prose byte-preserved, accepts top-level kwargs. `_edit` rejects body with frontmatter blocks (points at `set_meta`) and placeholder bodies (`[PENDING_VIEW]` etc.) that would nuke real prose.
- **`_list` state tags.** Inline: active / `[invalid: <field>]` / `[inactive: …]`. Runtime "broken" stays in `validate`.
- **Misc.** Knowledge skill references rewritten as compact answer-packs (~3500 → ~1000 lines). `docs/MODELS.md` reorganised by workload. 95+ new tests covering every primitive end-to-end.

## v0.3.10 — 2026-05-02 — `alpi diff`

What changed in this profile since N hours/days ago — memory
edits, sessions, mentions, skills, peer-list mutations, fired
schedules, today's budget. mtime-driven, side-effect free, safe
from cron or SSH. One primitive (``alpi/diff.py``) shared by the
CLI subcommand and the TUI ``/diff`` panel; a host-plane verb
will follow once the desktop has a use for it.

- ``alpi diff [--since 24h|7d|2026-04-25] [--json]`` — top-level command. ``--json`` emits the raw report dict for scripts / dashboards.
- ``/diff [since]`` slash command in the TUI; opens a floating panel rendered from the same report.
- ``docs/OPERATIONS.md`` — new "What changed in this profile?" section with cron / pre-backup / SSH-snapshot use cases.
- ``tests/core/test_diff.py`` — 23 cases covering ``parse_since``, every scanner branch, the empty-profile baseline, and a render smoke test.

## v0.3.9 — 2026-05-02 — daemon refactor + host plane

The v0.4 cycle lands as one release: a single daemon per machine, a host-plane control API for
visual and remote clients, and a round of workgroup and peer improvements. The first desktop
client ships separately as `desktop-v0.1.0` — see [desktop/CHANGELOG.md](desktop/CHANGELOG.md).

- **One daemon supervises every profile.** `alpi service` becomes `alpi daemon`, with one
  `com.alpi.daemon` / `alpi-daemon.service` per machine; `alpi setup` installs it on first run,
  and on Linux it keeps running after logout.
- **Host-plane control API** on `~/.alpi/host/host.sock` for reading sessions, chatting,
  changing configuration, managing schedules and subscribing to events.
- **Workgroups overhaul:** hub-anchored transcripts with per-workgroup budgets, `#task` /
  `#done` markers, and key rotation when members change.
- **Peers:** `@<peer>` mentions route straight to the peer, requests from unknown peers wait as
  pending invites, and each sender keeps its own mention thread.
- A budget nudge asks the agent for shorter posts once the daily cap passes 40%.

## v0.3.8 — 2026-04-28 — security audit hardening

External audit verdict landed; 9 of 10 verified findings hold.
This release closes them in P0/P1/P2 order without changing
public behaviour for existing profiles.

- `alpi/mcp/client.py` — MCP subprocess no longer inherits all of `os.environ`. Same safelist + declared-`env:` pattern as the v0.3.6 terminal fix. Closes API key/token leak to any third-party MCP server.
- `alpi/alp/envelope.py`, `alpi/alp/client.py`, `alpi/alp/server.py` — `verify()` now accepts `expected_to`/`expected_from`/`expected_id` and raises `WrongRecipient`/`WrongSender`/`IdMismatch`. Server pins `alp.to == self.kp`; client pins both response sender and JSON-RPC id. Closes ALP cross-target replay between trusted peers.
- `alpi/tools/_guards.py`, `alpi/tools/web_fetch.py` — SSRF: `check_url` switches `gethostbyname` → `getaddrinfo` (all A/AAAA records) and rejects non-`http(s)` schemes; `_direct_fetch` follows redirects manually and revalidates each hop against the blocklist.
- `alpi/_redact.py` (new), `alpi/session.py` — secret-shape redaction (`sk-…`, `ghp_…`, `AIza…`, Telegram tokens, key names containing `password`/`token`/`secret`/`api_key`/etc.) before `sessions/<id>.json` is written.
- `alpi/gateway/platforms/imap.py`, `alpi/gateway/platforms/gmail.py` — every inbound email body is wrapped with an `[external email — UNTRUSTED…]` warning + `scan_injection` result before reaching the LLM.
- `alpi/tools/browser.py` — Playwright `context.route` handler revalidates every navigation/subresource via `check_url`; redirects to private/loopback are aborted regardless of the initial check.
- `alpi/mcp/client.py` `_fetch_tools` — third-party MCP tool descriptions go through `scan_injection` and gain a one-line warning prefix when patterns match.
- `alpi/model_selector.py` — `_append_env`/`_remove_env_key` now write atomically via temp + `os.replace` and `chmod 0600`.
- `alpi/tools/send_message.py` — attachment paths run through `_paths.resolve_path` (same denylist as `email(send)`); rejects sensitive paths instead of forwarding them to delivery.
- Tests: `test_alp_envelope.py` (+5 binding cases), `test_mcp.py` (+2 env scoping), `test_guards.py` (+2 multi-A/scheme), `test_redact.py` (9 new).
- `docs/SECURITY.md` — Layer 1 entries updated to reflect what the audit closed.

## v0.3.7 — 2026-04-28 — Email PGP + test env isolation fix

Closes Email PGP from v0.4. Outbound IMAP/Gmail messages are
signed with the configured key and encrypted when every recipient
has a public key on `~/.gnupg`; inbound `multipart/encrypted` is
decrypted before the agent reads it. Default off. Also fixes a
test fixture that copied the dev's real `~/.alpi/.env` into every
test home, leaking `TELEGRAM_BOT_TOKEN` + API keys into
`os.environ` for the test process.

- `alpi/mail/pgp.py` — RFC 3156 PGP/MIME wrapper around `python-gnupg`; passthrough to plaintext on any failure.
- `alpi/mail/imap.py`, `alpi/mail/gmail.py` — wrap on send + decrypt on read; Gmail re-fetches `format=raw` when encrypted.
- `alpi/mail/pgp_setup.py` — wizard step at tail of `alpi setup → Gateways → IMAP`/`Gmail`. macOS+brew offers `brew install gnupg`; Linux/Windows print the right hint and skip. Defensive top-level wrap so PGP can never break the gateway flow.
- `tests/conftest.py` — `tmp_home` no longer copies `.env`. New autouse scrub of TELEGRAM/API/IMAP/SMTP env vars. `tmp_home_with_real_env` fixture isolates real-creds behaviour to `--llm` tests only.
- `pyproject.toml` — `python-gnupg>=0.5`.
- `tests/test_mail_pgp.py` (10) + `tests/test_mail_pgp_setup.py` (14).

## v0.3.6 — 2026-04-28 — terminal subprocess env scoping (AV)

Closes roadmap AV. The `terminal()` tool now starts every
subprocess with an explicit `env=` dict instead of inheriting
the parent's `os.environ` — a prompt-injected skill running
`terminal('env')` no longer sees `OPENAI_API_KEY` or any other
secret. Skills opt back into specific vars via `SKILL.md`
frontmatter `env: [FOO]`, scoped per-turn.

- `alpi/tools/terminal.py` — `_SAFE_ENV_KEYS` safelist + `_build_subprocess_env()`; both fg + bg subprocess sites pass `env=`.
- `alpi/tools/_state.py`, `alpi/engine.py` — per-turn allowlist ContextVar, reset at turn start.
- `alpi/tools/skill.py` — frontmatter `env:` parsed on view; sub-file reads don't register.
- `tests/test_skill_env_scoping.py` — 9 tests including real `terminal('env')` subprocess assertions.

## v0.3.5 — 2026-04-28 — TUI input responsiveness + multi-line paste

Closes roadmap BG early. Two compounding daily-UX TUI bugs:
typing lagged during streaming because every delta re-parsed
markdown via `Markdown.get_stream().write()`, and multi-line
paste delivered only the first line because Textual's `Input`
hardcodes `splitlines()[0]`. Fix renders in-flight tokens into
a cheap `Static` and swaps to `Markdown` once finalised; a
`ChatInput` subclass flattens pasted newlines to spaces.

- `alpi/tui/widgets.py` — `AssistantMessage` rewritten: streaming `Static` updated every 0.15s, `replace()` swaps to `Markdown` at finalise (idempotent via `_finalized`); spinner ticks dropped 6Hz→4Hz. New `ChatInput(Input)` overrides `_on_paste` with `event.prevent_default()` + `event.stop()`.
- `alpi/tui/app.py` — composes `ChatInput`; non-streaming callsites use `replace()` so markdown lands immediately.
- `tests/test_tui_streaming_perf.py` — gated `@pytest.mark.perf` fixture: 240 tokens at 60 tok/s with key injection, asserts per-keystroke p99 < 50 ms (observed 1–9 ms).
- `pyproject.toml` — `perf` marker registered.

## v0.3.4 — 2026-04-28 — workgroup hardening for tier-2 models

Workgroups now keep workflow shape on tier-2 models
(`gpt-5.4-nano`). Three failures fixed: members closing tasks
they couldn't close, infinite refinement loops, deadlocks when
every peer was caught up. Discipline moves from per-workgroup
briefings (which small models ignored) into protocol +
dispatcher. A 12-post nano run that previously looped now
closes at post 6.

- `alpi/alp/tasks.py` — `parse_post`/`active_task` gain optional `hub_pubkey` filter; non-hub markers ignored. New `has_markers()` helper.
- `alpi/alp/workgroup_client.py` — `post()` rejects non-hub `#task`/`#done` client-side with `ValueError`.
- `alpi/alp/agent_context.py` — `WORKGROUP_GUARDRAILS` rewritten with role-conditional rules: members default-silent unless `@`-named, hub must close after 4+ posts with no new evidence.
- `alpi/service.py` — `_build_role_aware_addendum()` (state-aware dispatcher cue), `_maybe_watchdog_close()` (180s stale-task force-fire), `turn_log_path()`/`_append_turn_event()` (append-only `start`/`end`/`timeout` events at `~/.alpi/profiles/<x>/alp/turns.jsonl`, mode 0600), hard 300s `asyncio.wait_for` turn timeout with SIGTERM→SIGKILL.
- `alpi/cli.py` — new `alpi workgroup turns [<wg_id>] [-f]` command.
- `tests/test_alp_tasks.py`, `test_alp_workgroup_client.py`, `test_alp_workgroup_poller.py`, `test_alp_agent_context.py` — hub-pubkey filter, SDK rejection, telemetry, timeout path.
- `tests/manual/test_money_workgroup.py` — new 3-peer nano demo; `docs/ALP.md` — protocol + autonomous engagement updates.

## v0.3.3 — 2026-04-28 — workgroup poller + capability fixes

Two ALP.3 bugs kept workgroups from cycling: a hub posting
`#task` in its own workgroup didn't wake its local agent, and
joiners couldn't pull because `workgroup.join` doesn't add
`workgroup.*` to the peer's `allow:`, hitting `-32001
capability-denied`. Also extracts curated provider model lists
into shared YAML for the desktop app + adds two hidden `chat`
flags for desktop GUI drive.

- `alpi/service.py` — `_should_dispatch` rewritten to scan every unacknowledged post; priority: explicit `@<profile>`, collective `#task`, active-task participant. Self-authored non-task posts shadow earlier triggers.
- `alpi/alp/peers.py` — `Peer.may_call` bypasses per-peer `allow:` for `workgroup.*`; membership is the real gate.
- `docs/ALP.md`, `alpi/skills/knowledge/references/alp.md` — clarifies bypass.
- `tests/test_alp_workgroup.py`, `test_alp_workgroup_poller.py` — rewritten + collective-task wake test.
- `alpi/providers/curated_models.yaml` (new) + `curated.py` (loader) — single source of truth, replacing inline `_CURATED` tuples in `openai.py`/`anthropic.py`. `pyproject.toml` ships `providers/*.yaml`.
- `alpi/cli.py` — `chat` gains hidden `--session-id` and `--model` (per-turn, not persisted).

## v0.3.2 — 2026-04-27 — `@peer` and doctor reach remote peers

Two bugs kept ALP.2 (TCP/Noise) traffic from working in
practice. A peer pinned with `address:` (the canonical "remote
machine" signal) was rejected by the highest-traffic code
paths and misreported by the health check, so a Tailscale-
exposed peer looked unreachable from outside even when its TCP
listener was accepting Noise handshakes.

- `alpi/alp/mention.py` — `execute()` routes through `alp_client.call_peer()` when `address:` is set; removes the "@<id> is remote — ALP.2 pending" rejection.
- `alpi/tools/peer.py` — docstring + tool description no longer claim "intra-machine only".
- `alpi/doctor.py` — `_check_alp` reuses `setup._probe_all` to fire `link.ping` over TCP for remote peers; reachable Tailscale peers now show `1/1 reachable`.
- `tests/test_alp_mention.py` — new `test_execute_routes_remote_peer_over_tcp` asserts TCP path with right `peer_id`/`method`/`params`.

## v0.3.1 — 2026-04-27 — brand accent unified

Single brand accent `#c8a24e` across every alpi surface. TUI
dropped its orange `#ff8800`, the marketing site dropped
`#a89b76`, and both adopt the warmer gold the desktop app uses.
Existing profiles with custom `tui.accent` keep their override.

- `alpi/config.py`, `alpi/cli.py`, `alpi/tui/app.py` — default `tui.accent` literal updated to `#c8a24e`.
- `alpi/skills/knowledge/references/config.md`, `docs/CONFIG.md` — config reference reflects new default.
- `site/templates/demo.css`, `site/templates/landing.html` — hero/playwright console + mono note recoloured.

## v0.3.0 — 2026-04-26 — public release

First public release of alpi: installable from PyPI
(`uv tool install alpi-agent`); docs, site, and onboarding
stable for external users. The v0.3 cycle stacked the work
that makes alpi usable beyond a single hacker on a laptop.
Per-patch detail preserved in v0.2.x entries below.

- ALP shipped end-to-end: ALP.1 (Unix sockets), ALP.2 (Noise_XK over TCP, rate limits + budgets), ALP.3 (workgroups: hub state, pause/resume, leave + rekey, member bios, `@<peer>` mentions anywhere).
- Service unification — one `alpi service` per profile hosts gateway, scheduler, ALP listener.
- Distribution — `alpi-agent` on PyPI with publish workflow; `alpi update` + version badge in doctor + TUI top bar.
- `@alpi/knowledge` — first bundled skill ships alpi's own docs.
- Browser tool — Chromium downloads itself on first use.
- Security & budget — profile `.env`/`config.yaml` off-limits to file tools and terminal; daily spending ledger with profile-level cap.
- UX + site — wizard headings + copy pass, TUI markdown link style, `/memory` rewrite, streaming lag fix, Delete profile, "did you mean" polish; landing + 15 docs pages, OG + JSON-LD, demo widget.

## v0.2.97 — 2026-04-26

### `@alpi/knowledge` — first bundled skill

alpi's first bundled skill bundles 12 user-facing docs as
package resources so the agent answers questions about alpi
without `web_search` or training-data guesses. SKILL.md
carries a topic→reference routing table; skills index has an
imperative rule biasing small models (~70% follow on nano).

- `alpi/skills/knowledge/` — wheel resources (README/QUICKSTART/INSTALL/PROFILES/SKILLS/MODELS/ALP/ARCHITECTURE/CONFIG/SECURITY/DEPLOYMENTS/OPERATIONS); CHANGELOG/ROADMAP/RELEASE/LICENSE excluded.
- `scripts/sync_knowledge.py` — keeps `references/` in lockstep with `docs/` + READMEs.
- `tests/test_alpi_knowledge.py` — 10 cases. Suite at 911 (was 901).
- `docs/SKILLS.md`, `QUICKSTART.md`, `docs/ROADMAP.md` — "Why ship skills" section, curation policy, **BE** for v0.4.

## v0.2.96 — 2026-04-26

### `@<peer>` mentions match anywhere in the text — ALP.3.1

The `@<peer>` shortcut now fires anywhere in the text — `"hey
@builder can you check?"` pings builder naturally. Boundary rules:
`@` must follow whitespace or be at position 0
(`email@gmail.com` skips), and the id must resolve to a pinned
peer (`@property` falls to LLM). `#task`/`#done` stay strict
line-start — state-change markers must not fire by accident.

- `alpi/alp/mention.py::parse` — relaxed regex + optional `home: Path` for roster validation; backward-compatible.
- `alpi/tui/app.py`, `alpi/gateway/run.py` — dispatch no longer gates on `text.startswith("@")`.
- `tests/test_alp_mention.py` — 14 cases (mid-text, email immunity, multi-mention first-wins, roster check). Suite: 901 (was 894).
- `docs/ALP.md` — Recognition rule distinguishes attention vs state-change markers.

## v0.2.95 — 2026-04-26

### `alpi update` — version check and self-upgrade

alpi tells you when there's a new release on PyPI. Daemon
thread on every `alpi` invocation (8h TTL) writes
`~/.alpi/cache/update_check.json`; `doctor` + TUI top bar read
the cache. `alpi update` bypasses the cache, detects install
method (uv tool / pipx / dev), upgrades, verifies new version
matches PyPI.

- `alpi/updater.py` (new) — version compare (handles `0.2.10 > 0.2.9`), cache I/O, 3s-timeout daemon, install-method detect.
- `alpi/cli.py` — `alpi update [--check|-y]`; `alpi/doctor.py`, `alpi/tui/app.py` — Version row + accent badge.
- Env: `ALPI_SKIP_UPDATE_CHECK=1` (autouse fixture sets it), `ALPI_UPDATE_INDEX` for TestPyPI.
- `tests/test_updater.py` — 26 cases mocked at `httpx.Client`. Suite: 894 (was 868).
- `docs/INSTALL.md`, `docs/ARCHITECTURE.md`, `README.md`, `docs/ROADMAP.md` (AU 1+2 ticked).

## v0.2.94 — 2026-04-26

### browser tool — Chromium downloads itself on first use

The browser tool already JIT-installed Chromium on first run;
docs hadn't caught up and still told users to run `playwright
install chromium` themselves. Aligns docs with code: no
separate install step, ~200MB download cached at
`~/.cache/ms-playwright/`, users who never browse pay nothing.

- `alpi/tools/browser.py` — install banner now writes to stderr (avoids stdout pollution under `chat --once` / gateway); `playwright import failed` message points at `uv tool install alpi-agent --reinstall` instead of `pip install playwright`.
- `tests/test_browser.py` — `test_launch_chromium_installs_on_first_run` (raise→install→retry), `test_launch_chromium_propagates_unrelated_errors` (JIT path is for binary-missing only). Suite: 868.
- `README.md`, `QUICKSTART.md`, `docs/INSTALL.md`, landing — drop the manual playwright install step.

## v0.2.93 — 2026-04-26

### distribution — first PyPI publish path

Installable from PyPI as `alpi-agent` — closes **AU**. CLI
binary + Python import + `~/.alpi/` stay `alpi`. Auto-publish
on push to `main` when `pyproject.toml` version differs from
PyPI; smoke install across 5 container images (Python
3.10/3.11/3.12-slim, Ubuntu 22.04, Debian 12); OIDC Trusted
Publisher; auto-tag + GitHub release with CHANGELOG body.

- `.github/workflows/publish.yml` — version-delta gate, `uv build`, `twine check`, multi-image smoke, OIDC publish; `workflow_dispatch` preserved for TestPyPI (idempotent).
- `pyproject.toml` — PEP 639 SPDX (`license = "BUSL-1.1"` + `license-files`), `[project.urls]`, classifiers, keywords.
- `docs/INSTALL.md` (new) — uv/pipx/dev/update/uninstall/troubleshooting + "no curl|bash" stance.
- `docs/RELEASE.md` (new) — maintainer cut checklist.
- `QUICKSTART.md`, `README.md`, `docs/ROADMAP.md`, landing — install step + `INSTALL` in docs grid (slug 02; subsequent renumbered).

## v0.2.92 — 2026-04-26

### self-published member bios in workgroups

Each profile carries an optional one-line `public_bio` that
propagates to every workgroup it joins. Surfaces in roster as
`@alice (online, "product engineer — velocity")` so agents see
who-does-what from turn 1. AGENT.md stays private. Inverts
earlier creator-assigned `roles` (which didn't scale).

- `alpi/config.py` — new `public_bio: str` (empty = unpublished).
- `alpi/alp/workgroup.py` — `workgroup.join`/`create` accept `bio`/`hub_bio` (capped 200 bytes); `pull` returns `bio` per member; re-joining refreshes.
- `alpi/cli.py` — `alpi setup → ALP → Identity` inline edit; `clear` unsets, `draft` synthesises from AGENT.md via one-shot LLM.
- `tests/test_alp_workgroup_client.py`, `tests/test_alp_agent_context.py` — 6 new cases. Suite: 866 (was 860).
- `tests/manual/` (new) — moves alice+bob convergence test out of `scripts/`; `norecursedirs` excludes from collection.

## v0.2.91 — 2026-04-26

### alp.3 — workgroups (PR 5): functional autonomy

Closes ALP.3. Workgroups self-drive: each member's service
polls the hub on a 30s tick and dispatches one engine turn
when a post mentions them, opens a collective `#task`, or
names them in the active task. 60s per-workgroup cooldown
rate-limits ping-pong. Suite: 860.

- `alpi/alp/agent_context.py` (new) — pre-turn hook injects briefing + active task + last 5 posts + roster + `WORKGROUP_GUARDRAILS` into every engine turn. Guardrails: silence default; accept/counter/block peer proposals (not more research); `#done` on convergence.
- `workgroup_post` auto-declares turn USD/tokens via ContextVar; hub-of-itself short-circuit writes directly to local transcript.
- `alpi/alp/workgroup.py` — `Meta.briefing`, `auto_kickoff`, `notify_on_close`; `Member.last_seen_at` stamped on `pull`/`post`; `#task`/`#done` parsed client-side (hub zero-knowledge).
- `alpi/service.py` — TCP bind failure falls back to unix-only with warning; `_supervise` per subsystem.
- `tests/test_alp_agent_context.py`, `test_alp_tasks.py`, `test_alp_workgroup_poller.py`, `test_state_turn_usage.py`.

## v0.2.90 — 2026-04-25

### service unification — one process per profile

Three legacy daemons (gateway, scheduler, ALP) collapse into a
single `alpi service` per profile. One asyncio loop hosts every
enabled subsystem — one PID, one log, one launchd/systemd
unit. Memory drops ~2/3. Every profile now starts opt-in
(auto-install of scheduler removed, aligning with sandbox /
budgets / peers).

- `alpi/service.py` (new) — orchestrator; `serve(home, profile)` builds asyncio task per enabled subsystem, signal handlers, cooperative cancel; owns install/uninstall (single plist/unit).
- `alpi/cli.py` — `alpi service {start,stop,restart,status}`; removes `gateway`/`alp` groups; `schedule` keeps `run-once`/`fire` only.
- `alpi/gateway/run.py`, `alpi/scheduler/run.py` — expose `async def serve(home)`; StreamHandler only on TTY (avoids double-logging under launchd/systemd).
- `alpi/config.py`, `alpi/doctor.py` — new `service: {gateway, schedule, alp}` toggles (default all-on); wizard replaces 3 entries; `_check_services` collapses to one row. `setproctitle` → `ps aux` shows `alpi (<profile>)`.
- Tests — drops `test_daemon_ops.py`, `test_bootstrap_autoinstall.py`, legacy `test_service.py` (~30); adds 20 new (backend selection, install/uninstall, toggle defaults, PID stale-cleanup, etime parser). Suite: 804 passed, 8 skipped.

## v0.2.89 — 2026-04-25

### alp.3 — workgroups: pause/resume + member state + management UX

Protocol gains `workgroup.pause`/`resume` (idempotent; `post`
returns `-32010 workgroup-paused`; `pull`/`join`/`leave` keep
working — pause must not trap members). Members get their own
`Subscription` state + full management surface. Hub identity
is explicit per subscription (probing pinned peers would leak
the id and let a malicious peer impersonate by pre-creating a
same-id workgroup).

- `alpi/alp/workgroup.py` — `Meta.paused`/`paused_at`/`paused_by`; new `pause`/`resume` handlers.
- `alpi/alp/subscription.py` (new) — `~/.alpi/<profile>/alp/secrets/subscriptions.yaml` (0600); per-wg record (`wg_id`, `name`, `hub_id`, `hub_pubkey`, sealed keys, `last_seq`). Sealed keys stay sealed on disk.
- `alpi/alp/workgroup_client.py` (new) — member-side `join`/`post`/`pull`/`leave`/`pause`/`resume`; transport-resolved via `peers.yaml`; refreshes sealed key on rotation.
- `alpi/cli.py` — `alpi workgroup` group (9 verbs split by role); `setup → ALP → Workgroups` wizard (Hub-of/Member-of, Read messages, alias-aware Members, edit-in-place Budget, create auto-grants 6 verbs).
- Workgroup budget validation relaxed: both `max_usd` + `max_tokens` may be set. Agent tool `workgroup_post` minimal (auto-pull/briefing → PR 5). `tests/test_alp_workgroup.py` (9 new pause/resume) + `test_alp_workgroup_client.py` (8 new). Suite: 817 (was 800).

## v0.2.88 — 2026-04-25

### alp.3 — workgroups (PR 2: leave + rekey + lifetime budget)

Members can leave; hub rotates the group key for remaining
members (forward secrecy: old key opens past posts, fails on
new ones). Optional **lifetime** budget (USD or tokens,
project-scoped, no daily reset) — posts double-gate on top of
profile cap. Profile gate fires upstream of workgroup gate.

- **Workgroup keys rotate when a member leaves.** Remaining members get a fresh sealed key, the
  hub can remove a member, posts may carry their cost, and a workgroup can cap spend in USD or
  tokens (`-32005` when reached).
- `docs/ALP.md` — `leave`, `key_version`/`cost` on `post`, rekey-via-pull, "Group-key versioning", project-lifetime cap with author-declared cost trust model.
- `tests/test_alp_workgroup.py` — 15 new (forward-secrecy, hub-can't-leave, kick rotation, budget shape, USD/tokens admit-then-block, ledger init, v1→v2→v3 monotonic, concurrent post+leave, profile gate upstream). PR 1's 20 still green. Suite: 804 (was 789).

## v0.2.87 — 2026-04-25

### alp.3 — workgroups (PR 1: hub state + 4 core verbs)

Hub side of shared workgroups: profile can `create` with a
chosen roster; pinned remote peers `join`/`post`/`pull` over
existing ALP transport (Unix or Noise_XK/TCP). End-to-end
encrypted: hub stores ciphertext, group keys sealed per-member.
Suite: 789 (was 769).

- **Encrypted workgroups:** hub-anchored transcripts sealed per member, with `create`, `join`,
  `post` and `pull`, and new error codes `-32008 workgroup-not-member` and
  `-32009 workgroup-not-found`.
- `alpi/cli.py` — `alpi alp start` registers handlers alongside `link.ask`.
- `docs/ALP.md` — concrete signatures (`workgroup.post(wg_id, nonce, ciphertext)` — encryption client-side); sealing scheme.
- `tests/test_alp_workgroup.py` — 20 new (crypto round-trip + isolation, end-to-end Unix + Noise/TCP, 3-alpi multi-member, `asyncio.gather` concurrent posts, restart persistence, error paths).

## v0.2.86 — 2026-04-25

### setup wizard — section headings + copy pass

`alpi setup` main menu splits into 5 sections (Agent,
Boundaries, Messaging, ALP, Maintenance); model picker into
Local/Cloud/Manage. Headings non-selectable, verbatim
rendering, auto-spaced. Copy pass across the wizard —
Sandbox/Workspace/Budget/TCP-port dim blocks trimmed to 3–6
lines; daemon-service wizards reduced to one line each.

- `alpi/ui.py` — new `Heading(NamedTuple)`; `menu()` adds blank rows, keeps cursor off.
- `alpi/cli.py::setup_cmd` — flat 13/14-item list rewritten as 5 sections; `_delete_profile_status` copy trimmed.
- `alpi/model_selector.py` — Local/Cloud/Manage grouping; Manage only when removable items exist.
- `tests/test_ui_menu.py` — 4 cases (heading shape, non-selectable mask, verbatim text, no-leading-blank). Suite: 769 passed, 8 skipped.

## v0.2.85 — 2026-04-25

### security — profile `.env` and `config.yaml` off-limits to tools

File tools and `terminal` refuse to read/write the active
profile's `.env` and `config.yaml` (provider API keys, gateway
tokens, sandbox flag, allowlist). A prompt-injected mailbox or
page can't coax the agent into leaking or rewriting them; they
stay editable by hand or `alpi setup`. Workspace `.env`
outside `~/.alpi/` deliberately untouched (path-scoped, not
basename-scoped).

- `alpi/tools/_paths.py` — denylist regex matches `~/.alpi/.env`, `~/.alpi/config.yaml`, and same under `~/.alpi/profiles/<name>/`.
- `alpi/tools/_guards.py` — three patterns: read profile secret (cat/head/tail/cp/scp/grep/awk/sed/xxd/...), write profile config (`>`/`>>`/`tee`), dump env (bare `env`/`printenv`). `env VAR=x cmd` and `printenv HOME` allowed.
- `tests/test_guards.py` (12 reject + 6 allow), `tests/test_paths_denylist.py` (12). Suite: 765 (was 734).
- `docs/SECURITY.md` § Layer 1 — new patterns + note skill scripts still run inside parent's `os.environ` (closed in v0.3.6 / AV).

## v0.2.84 — 2026-04-25

### budget — daily spending ledger, profile-level cap

Every spend path flows through one ledger + one cap
(`budget.daily_usd` or `daily_tokens`); per-peer sub-caps
dropped — peer trust lives in capabilities + rate limits.
Verified live on bob with `daily_usd: $0.05`; `/status` reads
`daily budget $0.0554 / $0.05 · capped`.

- `alpi/ledger.py` (new) — JSON at `~/.alpi/<profile>/logs/ledger.json`; profile total + per-peer buckets, atomic writes, midnight UTC reset, ContextVar attributing turn spend to remote peer.
- `alpi/engine.py` — admit-check before every turn; record after turn body + each sub-agent (`research`, `delegate`, `read_image`).
- `alpi/alp/server.py` + `handlers.py` — inbound `link.ask` admits; over-cap returns `-32005 budget-exceeded` (`cap_kind`/`cap`/`used` in `data`).
- `alpi/cli.py` — `alpi setup → Budget` prompts daily USD or tokens (pick-one); `alpi/status.py` (new) shared rows for TUI + Telegram `/status`.
- `tests/test_ledger.py` (15), `test_alp_budget.py` (3), 1 status-panel test. Suite: 734.
- Renames "alpi-rooms" → "workgroup" across ALP/CONFIG/PROFILES/OPERATIONS/ARCHITECTURE/ROADMAP.

## v0.2.83 — 2026-04-24

### alp — inter-machine Noise_XK transport, rate limits, wizard

Inter-machine half of ALP. Peers with `address` in
`peers.yaml` route over TCP+Noise_XK; ALP.1 Unix socket
untouched. New roadmap **BG** scopes v0.3 budget shape (one
ceiling per profile, `daily_usd` or `daily_tokens`).
Verified on same host and over Tailscale via MagicDNS.

- `alpi/alp/noise.py` — own `Noise_XK_25519_ChaChaPoly_SHA256` on `cryptography` primitives; Ed25519→X25519 birational so peers keep one pinned identity.
- `alpi/alp/transport_tcp.py` — TCP framing (u16 handshake, u32 bulk capped 1 MiB), pinned-key cross-check between Noise-authenticated static and `peers.yaml`.
- `alpi/alp/rate_limit.py` — sliding-window per peer, default 60/min overridable. Over-cap returns `-32005`.
- `alpi/alp/server.py`, `client.py` — TCP listener alongside Unix when `alp.tcp_port` set; new `call_tcp()`/`call_peer()`.
- `alpi/config.py`, `alpi/cli.py` — new `alp` section + `alpi setup → ALP → TCP port` wizard (`0.0.0.0` behind confirm); `alpi alp start --port --host`; `alpi peers ping` routes over TCP.
- `tests/test_alp_noise.py` (17), `test_alp_tcp.py` — handshake happy/tamper, bulk, ping, `-32005`, capability denial. Suite: 715.

## v0.2.82 — 2026-04-24

### site/docs — private agent network narrative + tool polish

Public narrative matches product shape: alpi is a profile-
based personal AI that grows into a private network across
machines. Third pass on AT (prompt + tool descriptions audit
against comparable persistent-agent behaviour) — three targeted
additions.

- `README.md` — leads with profiles, model/key ownership, multi-machine coordination, current ALP surface.
- Landing + docs — "your private / agent network"; ALP.1/.2/.3 stated directly across ALP/Deployment/Security/Operations/Profiles/Config/Roadmap.
- `alpi/tools/browser.py` — "re-check snapshot for real role/name when click/type can't find element" hint (stops blind selector retries).
- `alpi/tools/search.py` — regex-metachar gotcha (`{ } ( ) | . * +` need escaping in content mode).
- `alpi/tools/stt.py` — "Use when" preamble so gateway voice notes trigger transcription.

## v0.2.80 — 2026-04-24

### site — header/nav unified, docs index redesigned, SEO at 100%

Second pass on the static site under `site/`. Single shared
nav across landing/`/docs/`/`/docs/*`; combined logo + alpaca
favicon; burger menu under 760px in <20 lines inline JS. SEO
across every page: unique title/description, canonical, Open
Graph, Twitter Card with `@soyjavi`, JSON-LD, `sitemap.xml`
(16 URLs with `lastmod`) + `robots.txt` on every build.

- `site/scripts/build.mjs` — `renderNav()` shared shell (1240px + `clamp(24px, 5vw, 64px)`); breadcrumb tail varies (DOCS, DOCS/{slug}); fixes nested `<a>` bug.
- `site/dist/` — three assets (logo, alpaca, social card 1200×800); `/docs/` rebuilt with `.docs > .doc` card grid, H1 72px/600/-.035em.
- `SITE_URL` env var configurable, default `https://alpi.satoshi-ltd.com`.

## v0.2.79 — 2026-04-24

### site — static marketing + docs scaffold under `site/`

First cut of alpi.site as zero-dependency static site: vanilla
HTML/CSS/JS + single Node build script reads `README.md`,
`QUICKSTART.md`, `CHANGELOG.md`, `LICENSE`, `docs/*.md` at HEAD
and bakes `site/dist/` — landing at `/`, doc index, one
pre-rendered HTML per doc. Versions derived from
`pyproject.toml`; no runtime fetch, CORS, or rate limits.

- `site/scripts/build.mjs` — Node build entry.
- `site/scripts/markdown.mjs` — zero-dep renderer (headings, fenced code, lists, tables, blockquotes, inline code, bold/italic, links).
- Cloudflare Pages: build `node site/scripts/build.mjs`, output `site/dist`. Based on a `claude design` mockup (mockup folder removed after migration).

## v0.2.78 — 2026-04-24

### skills — auto-validate on every mutation

Every mutating action on a user skill (`create`/`edit`/`patch`/
`add_file`/`remove_file`) runs `_skill_validate.validate_skill`
(py_compile, missing imports, OAuth race, port coherence) and
surfaces findings inline so the LLM iterates without a
separate `validate` call. Reverted the `@alpi/plan` experiment
— `@alpi/*` stays reserved + live, but nothing ships by
default until concrete patterns justify it.

- `alpi/tools/skill.py` — auto-validate hook on each mutation.
- `alpi/prompts/create_skill_guide.md` — Scripts section (prefer stdlib, dry-run/smoke, exit codes) + auto-validation note.
- `tests/test_skill_auto_validate.py` — 6 regression tests.
- `docs/ROADMAP.md → AO`, `docs/SKILLS.md` — bundled-skill position clarified.

## v0.2.77 — 2026-04-24

### skills — bundled infrastructure (BE closed)

Read-only namespace for skills shipped with the alpi package;
no content bundled yet, infrastructure only. Bundled skills
addressed as `@alpi/<name>`; `@` not legal as on-disk category
so collisions impossible. Suite: 692.

- `alpi/tools/skill.py` — `_bundled_root()` via `importlib.resources.files("alpi.skills")`; `_bundled_skill(name)` returns package resource for `@alpi/*` or `None`. `_find_skill` tries bundled first. Discovery: `skills_index_block()` + `skill list` lists user skills then `@alpi/ [bundled]:`. Write guards reject mutating actions on `@alpi/*`. `all_skills` skips on-disk categories starting with `@`.
- `pyproject.toml` — package-data ships `skills/**/*`; `alpi/skills/` empty except `__init__.py`.
- `tests/test_bundled_skills.py` — 14 regression tests.
- `docs/SKILLS.md` "Bundled vs user skills"; `docs/ARCHITECTURE.md` package tree updated.

## v0.2.76 — 2026-04-24

### tui — markdown link styling + memory panel rewrite (BB closed)

Textual 8.2.3 exposes only `@click` meta on markdown link
spans, no style — links rendered as plain prose. Fix monkey-
patches `MarkdownBlock._token_to_content` at import to add
bold+underline on `@click` spans (idempotent, global).
`/memory` panel replaces the code-block hack with stacked
`Static` headers + per-entry `Markdown` widgets split on `§`.
Streaming input lag fixed by 12.5Hz timer coalesce vs ~60/s
`asyncio.create_task` per delta.

- `alpi/tui/_links.py` (new) — monkey-patch; `alpi/tui/widgets.py` — `/memory` rewrite + `_FLUSH_INTERVAL = 0.08` coalesce; new `.memory-section` CSS.
- `alpi/prompts/default_agent.md` — `# Identity`/`# Voice`/`# Defaults` → `##` (Textual centers `h1`).
- `alpi/tools/memory.py` — `§` guidance tightened; `fuzzy_find_unique_entry` adds "`§` is delimiter" hint. `docs/ROADMAP.md` — BF removed.

## v0.2.75 — 2026-04-24

### wizard / cli — profile lifecycle + polish

New `alpi -p <name> setup → Delete profile` (non-default
profiles only) — one-shot teardown: summary → service warning
→ typed-name confirmation → uninstall services → `rmtree` →
exit. Collapses what was "uninstall each service manually,
then `alpi profile remove`" into a single guided action.
"Did you mean…?" suggestions across `profile remove`, `peers
remove`/`ping`, `schedule fire` via shared `_suggest()`
(`difflib`).

- `alpi/cli.py` — Delete profile wizard; `profile remove` redirects to wizard when services installed; `_suggest()` helper; fixes the misleading "→ Gateway service" hint.
- Dropped `.githooks/` (pre-push CHANGELOG regen — opt-in and unused).
- `docs/PROFILES.md`, `docs/ARCHITECTURE.md` — wizard-redirect flow + setup menu.

## v0.2.74 — 2026-04-24

### schedule — ad-hoc job fire (BA closed)

Closes the tightest feedback loop in schedule lifecycle: add
cron, verify it works, without waiting for the cron window.

- `alpi/scheduler/run.py::fire_by_id(home, job_id)` — runs the job through the same path as the daemon tick (threat scan + `alpi chat --once` subprocess + delivery); updates `last_run_at`; does **not** consume `once` jobs (ad-hoc fire is testing).
- `alpi/cli.py` — `alpi schedule fire <job_id>` (exit 1 on failure).
- `alpi/tools/schedule.py` — `schedule(action="fire", id=...)` so the LLM can self-test after adding.
- `tests/test_schedule.py` — 5 new tests. Suite: 675.

## v0.2.73 — 2026-04-24

### skills / memory / docs — stop shipping what we don't use

Deleted the `alpi/skills/` package — only blueprint
(`meta/consolidate-memory/SKILL.md`) never reached profiles
(skill tool only searches `{home}/skills/`). Runtime skills
system untouched — `~/.alpi/skills/<category>/<name>/` still
works.

- `pyproject.toml` — package-data no longer includes `skills/**/*.md`.
- `alpi/tools/memory.py`, `alpi/prompts/system_prompt.md`, `create_skill_guide.md` — ≥80% hint now says "consider consolidating old entries" instead of pointing at a non-existent skill.
- `docs/ARCHITECTURE.md` — package tree updated; bridge paragraph to Profile home layout.
- `docs/ROADMAP.md` — **BE** reframed as "bundled skills infrastructure (loader; no content yet)"; **AO** drops consolidate-memory bundling claim.
- `tests/test_memory_tool_v2.py` — two regressions assert new wording.

## v0.2.72 — 2026-04-24

### memory — v2 rules (AI partial)

Renames `PERSONALITY.md` → **AGENT.md** across codebase /
prompts / tests / docs (user/agent pair now symmetric). File
migration manual per project policy. Char limits: USER.md
1375→3000, MEMORY.md 2200→5000.

- **A** — AGENT.md uses paragraph-fold + Jaccard dedup (`is_duplicate_stanza` in `alpi/memory.py`); paraphrased voice blocks no longer accumulate.
- **B** — `alpi/prompts/default_agent.md` "Edit me" footer rewritten teaching `replace` vs `add`.
- **C** — cross-file dedup: `add` to USER.md/MEMORY.md rejects when content is already in the other.
- **E** — operational-state ⚠ warning when entry matches session/chat log pattern (non-blocking).
- **F** — `≥80%` usage triggers "run consolidate-memory skill" hint.
- **D**/**G deferred** — Jaccard 2→1 produced false positives (`Dato A`/`Dato B` collapsed to `{dato}`); periodic self-consolidation out per "no over-engineering".
- `tests/test_memory_tool_v2.py` — 11 new regressions.

## v0.2.71 — 2026-04-24

### engine / prompts (AT partial — 4 of 5 candidate edits applied)

Per-surface platform hint: `_platform_hint()` in
`alpi/engine.py` reads `ALPI_PLATFORM` and injects a matching
block (`cron`/`telegram`/`email`/`gmail`). Cron jobs stop
asking phantom users for clarification; Telegram replies
arrive Markdown-aware; email replies plain-text-only. New **BD**
for v0.3 (model-aware tool-use guidance — needs `agent.log` A/B).

- `alpi/engine.py` — `_platform_hint()`; `alpi/gateway/run.py` sets `ALPI_PLATFORM=msg.platform`; `alpi/scheduler/run.py` sets `cron`. TUI no hint. 6 regression tests.
- `alpi/tools/memory.py` — declarative ✓/✗ examples ("User prefers concise replies" ✓ vs "Always reply concisely" ✗).
- `alpi/tools/skill.py`, `alpi/tools/email.py` — descriptions lead with "Use when".
- `alpi/prompts/system_prompt.md` — drops "Past conversations" (already in `session_search`). ~10 fewer tokens/turn.
- `docs/ARCHITECTURE.md` — documents `ALPI_PLATFORM` contract.

## v0.2.70 — 2026-04-23

### license + foundational docs

Repo re-licensed under **Business Source Licence 1.1**.
Licensor: Satoshi Ltd. Change Date 2030-04-23 → Apache 2.0.
Additional Use Grant for personal/research/non-commercial;
commercial production requires a licence from
`info@satoshi-ltd.com`. Repo rooted in Satoshi Ltd.'s six
operating principles, each doc mapping to its principle.

- `LICENSE`, `pyproject.toml` (`BUSL-1.1`), `README.md` License section rewritten.
- `QUICKSTART.md` (new) — first-day walkthrough (install → model → workspace → chat → resume → gateway → second profile → ALP → doctor).
- `docs/PROFILES.md` (new) — canonical reference for the core isolation primitive.
- `docs/DEPLOYMENTS.md` (new) — six topologies laptop → enterprise networks with ASCII diagrams + BSL boundaries.
- `docs/OPERATIONS.md` (new) — runbook (logs, lifecycle, upgrades, backup/restore, ALP rotation, monitoring, DR). `docs/ROADMAP.md` sanitised; dropped 64 shipped-item rows + commit table duplicating CHANGELOG.

## v0.2.69 — 2026-04-23

### models

- `docs/MODELS.md` rebuilt around a neutral 3-tier recommendation from a standalone deep-research pass (Tier 1 quality, Tier 2 cost/service, Tier 3 Ollama) with production-setup suggestions. Personal-usage section + deliberately-left-out list dropped to keep the doc unbiased.
- `alpi/config.py::seed_defaults` — fresh profile scaffold no longer pins a default model; `config.yaml` ships with `model: ""` so the setup wizard is the canonical picker.
- `docs/CONFIG.md` — empty default reflected.

## v0.2.68 — 2026-04-23

### alp (Alpi Link Protocol — ALP.1 closed)

ALP.1 ships: Ed25519 identity, signed JSON-RPC envelope with
replay cache, fail-closed peer list, Unix-socket server +
client. `link.ping`, `link.ask` (reject-fast reentrancy),
`link.cancel` (idempotent). Setup wizard health-check no
longer blocks menu render on 5–10s of probes — runs on-demand.

- `alpi/alp/` (new package) — identity, envelope, server, client, `link.*` handlers.
- `alpi/tools/peer.py` — LLM-driven cross-profile calls; TUI `@peer rest…` gesture (strict leading-`@`); `/peers` panel; gateway inbound interception hits same code path without firing local LLM.
- `alpi/cli.py` — `alpi alp start|stop|restart`; service install via `alpi setup → ALP service` (launchd/systemd); doctor sub-checks (Identity/Socket/Peers); `alpi setup → Peers` wizard with clipboard copy + ●/○/? probe status; `alpi peers key|list|add|remove|ping` for scripting.
- `docs/ALP.md` (new) — spec v1 (envelope, verbs, errors, security); `docs/ROADMAP.md`, `docs/ARCHITECTURE.md` updated.

## v0.2.54 — 2026-04-23

### gateway

- per-chat session threading (AN closed) + AU backlog entry (`e0f093d`)

## v0.2.1 – v0.2.53 — 2026-04-21 → 2026-04-23

Two days of rapid iteration after the v0.2.0 split. Patch
bumps collapsed into thematic groups; full per-commit detail
in `git log`.

- **brand** — project renamed `alf` → `alpi` across codebase, docs, config paths (~130 files).
- **TUI** — theme system + floating panels; new panels `/model`/`/mcps`/`/tools`/`/help`; profile disk size + accent diamond; `tui.auto_resume` (AL closed); dropped questionary, menus + inputs rebuilt on `prompt_toolkit`.
- **setup wizards** — normalised UX; new wizards Cleanup (AA), Gateway service install/uninstall (AB), live Doctor (AD/AE/AF), first-time help text (AG), Model wizard reordered (Ollama first); `.env.example` dropped (AP).
- **voice + gateways** — voice pack `tts`+`stt`+Telegram voice (M closed); TTS autoplay off on gateways; Gmail OAuth2 + mail tool (T closed); Telegram offset persistence + backlog catch-up.
- **tools** — `browser` Playwright with stealth + humanised typing + optional vision; `read_image` URL/SVG/model-override (D, S closed); `research`+`delegate` batch parallel (R.3), delegate write-capable (R.2), research step counter (R.1); `skill` validate action (Q closed); removed `config` tool (config user-owned).
- **security** — three-severity command gate for terminal (W closed); approval panel restyled, YOLO removed; tool budget + OSV malware check + schedule threat-scan; sandbox per-profile opt-in; `allow_network=off` blocks Python-native net tools; `tos`: removed C (Codex OAuth) and V (Anthropic OAuth) backlog.
- **release pipeline** — auto-generated CHANGELOG from git history (AC closed) + pre-push CHANGELOG hook; CLI surface shrunk; `PERSONALITY.md` → `memories/`, `gmail_token` → `secrets/`.
- **MCP + providers** — OpenAI-compat tool names, curated provider lists, context-window awareness; `/tools` skips MCP-registered (rendered in `/mcps`); Ollama first-class; generic custom slot removed.

## v0.2.0 — 2026-04-21

Foundational v0.2 cut: split CONTEXT → ARCHITECTURE + ROADMAP,
positions alf as a lighter private-agent runtime; tiered model docs; profile
propagation through tool context; new send_message + schedule
+ email + mcp subsystems; security phases 1–2.

- **docs** — `MODELS.md` (tiered model recommendations) (`df29cfc`); identity-wizard rejected (`60122b7`); CONTEXT split into ARCHITECTURE + ROADMAP, bump to v0.2.0 (`6b946e4`).
- **gateway / schedule** — stream tool traces + typing indicator (`fe3a3d4`); fail fast on bad workspace (`04bdaba`); fix immediate-fire + UTC vs local tz + duplicate delivery (`3dd4522`); kind=once + LLM time grounding (`1fc3610`); schedule daemon tool+CLI+rename from cron (`2245e42`); install/uninstall for gateway+schedule (`cd62da0`); email subsystem (`c67e618`); email gateway + per-platform config (`4691df8`).
- **skills / tools / tui** — unified skill tool + subdir contract + path guards (`2e67830`); auto-inject skill index into system prompt (`4035327`); rename delegate → research + depth tiers (`d2ceb74`); level-2 comment cleanup (`a07e40a`); inter-tool prose + reasoning tokens in indicator (`62f7fa7`); reasoning persists across sessions + show_reasoning toggle (`fd1fec4`); skill tool patch/view + state subdir (`211c022`).
- **Misc:** profile propagation and memory prompt fixes, the `send_message` tool, the profile CLI,
  an MCP client, compressed tool descriptions, a terminal denylist with SSRF and injection
  scanning, an opt-in OS sandbox, a merged file search, and web search deduplicated by domain.

## v0.1.0 — 2026-04-19

### misc
- initial commit — alf v0.1 (`a0c7630`)
