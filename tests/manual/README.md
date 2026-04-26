# Manual integration tests

End-to-end scripts that exercise alpi the way a user would — with
real profiles, real LLM calls, real ALP traffic, and real money on
the meter. They are NOT collected by `pytest` (excluded via
`norecursedirs` in `pyproject.toml`) and they are NOT run in CI.

## Why they exist

The unit suite under `tests/` covers ~860 isolated cases but cannot
prove the live system converges. Whether two alpis on different
profiles can hold a workgroup conversation, react to each other,
and close a `#task` with `#done` is an emergent behaviour that only
shows up end-to-end. These scripts assert the **outcome**, not the
exact text — fine-grained text checks would brittle out the moment
a model rev changes phrasing.

Run them when:

- Closing a feature that touches the autonomous loop (engine
  pre-turn hook, workgroup poller, engagement guardrails).
- Suspecting a regression in cross-profile messaging.
- Demoing alpi to anyone — these are the most honest demo.

Don't run them on every commit. Each one costs LLM money and
takes minutes.

## Contract for scripts in this folder

Every script:

1. **Self-checks preconditions** at the top (profiles exist, peers
   pinned, models configured) and bails with a clear message if any
   are missing. Never silently proceeds with an under-configured
   system.
2. **Wipes its own state** before starting (relevant workgroups,
   subscriptions, poller cursors) so reruns are deterministic.
3. **Documents in its docstring**: what it tests, what preconditions
   you need, the cost ballpark per run, and what success looks like.
4. **Uses a real budget cap** so a regression doesn't burn through
   your wallet (e.g. `--budget-usd 3.0` per workgroup).
5. **Asserts outcome, not text.** Pass = the system reached the goal
   state (e.g. `#done` landed). Fail = timeout or budget exhausted
   without convergence.

## Index

### `test_alice_bob_workgroup.py`

Verifies the full autonomous workgroup loop: two alpi profiles
(alice as hub, bob as remote member) collaborate on a stack-decision
`#task` and close it with `#done` without any human in the loop.

**Preconditions:**

- Profiles `alice` and `bob` exist under `~/.alpi/profiles/`, each
  with a configured model, a workspace, and the other peer pinned.
- Both profiles have ALP listening on the conventional addresses
  (the script restarts both services to pick up the latest code).
- Optional: distinct `public_bio` set on each profile via
  `alpi -p <name> setup → ALP → Identity` (the script no longer
  overrides them).

**Cost ballpark:** ~$0.01–$0.05 per run; capped at $3 by the
workgroup's lifetime budget regardless.

**Run:**

```bash
uv run python tests/manual/test_alice_bob_workgroup.py
```

**Success looks like:** the script prints each new post with the
poster's spend, and exits with `task CLOSED with #done` typically
within 5–10 posts (~3–8 minutes wall clock).

**Failure modes worth investigating:**

- Timeout (25 min) without `#done` → engagement rules failing to
  trigger closure. Inspect transcript for paraphrase loops or
  evidence-hunting rabbit holes.
- Cost climbing past ~$0.50 → guardrails not biasing toward
  silence. Check `WORKGROUP_GUARDRAILS` in
  `alpi/alp/agent_context.py`.
- Connection refused on kickoff → alpi service didn't bind in
  time. Check `~/.alpi/profiles/<name>/service.log`.
