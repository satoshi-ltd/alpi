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

### `test_money_workgroup.py`

End-to-end one-shot that owns three profiles (`alice`, `bob`,
`carol`) from scratch and runs **two workgroups in parallel** to
exercise concurrent dispatcher behaviour:

- **`money-2026`** (hub=alice, members=alice/bob/carol) — pick PATH
  A vs B for the [Money app](https://satoshi-ltd.com/case-studies/money)
  2026 strategy.
- **`alpi-v05-roadmap`** (hub=carol, members=carol/alice) — read
  https://alpi-agent.com/docs/ROADMAP and decide whether the
  proposed v0.5 scope is right. Bob excluded.

Roles:

- **alice** — product manager (hub of money, member of roadmap).
- **bob** — marketer (member of money only).
- **carol** — user researcher (member of money, hub of roadmap;
  web-fetches both source pages).

Transport: alice + carol intra-machine unix socket; bob over
TCP/Noise_XK on a Tailscale hostname (`TCP` dict at top of script —
edit this to match your environment).

**Preconditions:**

- `OPENAI_API_KEY` in `~/.alpi/.env` (it's the only secret the
  script propagates).
- Tailscale up and the configured hostname resolves to your machine
  (else change `TCP["bob"]["host"]` to `127.0.0.1`).

**Cost ballpark:** ~$0.10–$0.30 total per run across both workgroups
(money cap $5, roadmap cap $3 — set inside the script).

**Run:**

```bash
uv run python tests/manual/test_money_workgroup.py
```

> **Warning:** this WIPES `~/.alpi/profiles/{alice,bob,carol}` every
> run. Don't point it at profiles you actually use.

**Success looks like:** the script prints each new post tagged with
its workgroup name and the poster's spend, and exits with `all
workgroups closed.` once both have hit `#done`.

**Failure modes worth investigating:**

- One workgroup stalls while the other progresses → poller starvation
  (one wg dominating the per-profile dispatcher). Check
  `_print_turn_panel` output for which profile is wedged.
- TCP path failures (only affect bob) → `peers ping bob` from alice
  or carol returns connection refused. Verify Tailscale hostname
  resolves and bob's listener bound it (`alpi daemon status`
  shows the daemon's per-profile services and listener bindings).
- Timeout without `#done` → engagement rules failing to trigger
  closure. Inspect transcripts for paraphrase loops or
  evidence-hunting rabbit holes.
- Cost climbing past the budget → guardrails not biasing toward
  silence. Check `WORKGROUP_GUARDRAILS` in
  `alpi/alp/agent_context.py`.

## Quick check — inline images across clients (v0.8.5)

Not a script; a one-shot to verify agent-made images render inline (and
the attachment → `--input` path reaches the agent). Pick a profile whose
image skill is active (e.g. a `muse`-style profile):

```
alpi -p muse chat --once "Reshoot this room, more Airbnb, new angle, keep its identity. Save to /tmp/x.png and show it." --attach ~/Desktop/room.jpg
```

Success: the reply contains `![...](/tmp/x.png "…")`, the file exists, and
it's a real transformation (not the input echoed). In the desktop/mobile
chat the same reply renders as a captioned card; tap/click opens the
lightbox. Reads stay within workspace/home/temp (see `docs/SECURITY.md`).
