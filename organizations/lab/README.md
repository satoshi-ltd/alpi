# Protocol Lab

The smallest org that exercises the **entire** ALP workgroup protocol.
Four profiles, one workgroup (`bench`), and a harness (`test-protocol.py`)
that walks every invariant in [`docs/ALP.md`](../../docs/ALP.md) → *Workgroups*.

Use it to:

- **Regression-test the protocol** after touching `alpi/alp/tasks.py`,
  `alpi/alp/workgroup_client.py`, `alpi/alp/workgroup.py`, or the poller in
  `alpi/service.py`. The suites are LLM-free and deterministic.
- **See the markers render in the apps** — every post is real, so `#task` /
  `#working` / `#skip` / `#done` show up in the desktop / mobile workgroup
  view as the harness runs.

This org produces nothing on disk; the "work" is a pretext for collaboration
so the markers, rounds, and closure rules fire against real turns.

## Roster

| Agent | Tier | Reasoning | Role | Tools |
|---|---|---|---|---|
| **mind** | strong | medium | Hub of `bench` — frames the question, synthesises, closes | no web/comms |
| **scribe** | default | off | Wording — always has a phrasing angle | no web/comms |
| **tally** | default | off | Structure — maps the tradeoff, `#skip`s when there is none | no web/comms |
| **probe** | default | low | Evidence — fetches real data (`#working`), `#skip`s when nothing to look up | web tools on |

Souls carry identity only — the protocol rules are runtime knowledge, never
re-explained in the souls. In `--live` each agent's identity steers it to a
different marker on its own (probe → `#working`/`#skip`, tally → `#skip` on a
no-tradeoff question, scribe → substantive, mind → close).

## The driver: single-task + a listener

The protocol is **single-task** — one task active at a time, no multitasking.
Every mode honours this with the same discipline: open ONE task, then **read
the workgroup until a hub `#done` closes it**, and only then open the next.
Never preempts, never overlaps. In the deterministic modes the script posts
the `#done` and reads it back; in `--live` it waits for the *real* hub to
close. The bench is reset (removed + recreated, members rejoin) before each
run so every run starts on an empty transcript (`--no-reset` to append).

## Bootstrap

```bash
uv run python organizations/setup.py lab
```

Four profiles, six peer pins, one workgroup. No workspace scaffold.

## test-protocol.py

```bash
uv run python organizations/lab/test-protocol.py            # suite (default)
uv run python organizations/lab/test-protocol.py --live     # real agents
uv run python organizations/lab/test-protocol.py --stress   # edge cases
uv run python organizations/lab/test-protocol.py --stress --slow  # + 10-min escape
```

### `suite` (default) — the narrative, single-task

Phase 0 rejects on an empty bench (none open a task), then four tasks worked
one at a time, each closed before the next, with a listener confirming the
`#done`:

| Stage | Verifies |
|---|---|
| Phase 0 | empty-post · slug-required · member-can't-`#task`/`#done` · hub-can't-`#skip`/`#working` |
| Task `#memo-indent` | full-quorum close · premature `#done` blocked · hub back-to-back blocked · member one-post-per-round |
| Task `#h1-caps` | `#skip` counts toward quorum (with reasons rendered) |
| Task `#footer-text` | all-skip blocks `#done`, one substantive unblocks (mix of bare + reasoned skips) |
| Task `#cite-cwv` | `#working` is rotation-exempt and doesn't satisfy quorum alone |

### `--live` — real agents, sequential

Seeds one open-ended task as the hub, waits for the real agents to converge
and mind to `#done`, then seeds the next. Watch `#working` / `#skip` / `#done`
render live in the apps. `--timeout` bounds the wait per task.

### `--stress` — edge cases the narrative doesn't reach

| Group | Verifies |
|---|---|
| Recognition | mid-sentence `#task` stays prose · `#done` on an empty slot is a no-op |
| Preemption | a new `#task` closes the old (`preempted by #<new>`, fold-verified) |
| Pause / resume | post blocked `-32010` · `pull` still works · hub-only |
| Budget | workgroup lifetime cap `-32005` (in-process `_gate_post`; the CLI can't declare a cost) |
| Leave + rekey | group-key rotation + **forward secrecy** — an ex-member's old key reads old traffic but not new |
| `--slow` | all-skip → the 10-minute hard-timeout escape lets the hub close |

## Known gaps / notes

- **Frontend divergence (not fixed):** a post with both `#task` and `#done` at
  line starts is treated as **prose** by the backend (`tasks.parse_post`), but
  the desktop/mobile parser renders it as a `#task` card. The apps don't
  implement the ambiguity rule. The harness avoids posting such messages.
- **Preemption SIGTERM** (the runtime killing in-flight peer subprocesses) is a
  service-level behavior; `--stress` verifies the *fold* semantics, not the
  SIGTERM. Watch it by hand in `--live` via `turns.jsonl`.

## Adapting

Add a fifth member to stress quorum harder, or a second workgroup with a
different hub. Keep the souls free of protocol mechanics — the whole point is
that agents already know the rules at runtime, and the harness asserts the SDK
enforces them regardless.
