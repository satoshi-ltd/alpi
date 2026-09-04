import json
import time

from alpi import ledger, service

POLLER_CURSORS = (
    "hub_last_dispatch_at",
    "hub_last_responded_seq",
    "hub_watchdog_fired_seq",
    "hub_watchdog_fire_count",
    "hub_continuation_fire_count",
)


def _profile(tmp_path, cap, spent=0.0):
    home = tmp_path / "p"
    home.mkdir()
    (home / "config.yaml").write_text(f"budget:\n  daily_usd: {cap}\n")
    if spent:
        ledger.record(home, usd=spent, tokens=10, tokens_in=8, tokens_out=2)
    return home


def test_under_cap_does_not_block(tmp_path):
    home = _profile(tmp_path, 5.0, spent=1.0)
    assert service._budget_blocks_dispatch(home, "scout", "wg_1", "site-x") is False
    assert not service.turn_log_path(home).exists()


def test_uncapped_profile_never_blocks(tmp_path):
    home = tmp_path / "p"
    home.mkdir()
    (home / "config.yaml").write_text("{}\n")
    ledger.record(home, usd=999.0, tokens=10, tokens_in=8, tokens_out=2)
    assert service._budget_blocks_dispatch(home, "scout", "wg_1", "site-x") is False


def test_over_cap_blocks_and_logs_the_event_once(tmp_path):
    home = _profile(tmp_path, 5.0, spent=6.0)

    for _ in range(3):
        assert service._budget_blocks_dispatch(home, "scout", "wg_1", "site-x") is True

    events = [
        json.loads(line)
        for line in service.turn_log_path(home).read_text().splitlines()
        if line.strip()
    ]
    budget = [e for e in events if e.get("event") == "budget-exhausted"]
    assert len(budget) == 1, "turns.jsonl must not grow on every poll"
    assert budget[0]["profile"] == "scout"
    assert budget[0]["cap"] == 5.0
    assert budget[0]["used"] >= 6.0


def test_block_is_silent_in_the_workgroup(tmp_path, monkeypatch):
    home = _profile(tmp_path, 5.0, spent=6.0)
    posted = []
    monkeypatch.setattr(
        "alpi.alp.workgroup_client.post",
        lambda *a, **k: posted.append(a),
    )
    service._budget_blocks_dispatch(home, "scout", "wg_1", "site-x")
    assert posted == [], (
        "a budget block must not post: the protocol would read it as the owner's "
        "substantive delivery and let the hub close the phase without one"
    )


def test_block_leaves_every_poller_cursor_untouched(tmp_path):
    home = _profile(tmp_path, 5.0, spent=6.0)
    service._save_poller_state(home, {"seed": 1})

    assert service._budget_blocks_dispatch(home, "scout", "wg_1", "site-x") is True

    state = service._load_poller_state(home)
    assert state.get("seed") == 1
    for cursor in POLLER_CURSORS:
        assert not state.get(cursor), f"{cursor} advanced while the turn never ran"


def test_raising_the_cap_unblocks_the_same_wake(tmp_path):
    home = _profile(tmp_path, 5.0, spent=6.0)
    assert service._budget_blocks_dispatch(home, "scout", "wg_1", "site-x") is True

    (home / "config.yaml").write_text("budget:\n  daily_usd: 20.0\n")
    assert service._budget_blocks_dispatch(home, "scout", "wg_1", "site-x") is False


def test_mid_turn_budget_abort_keeps_the_real_cause(tmp_path, monkeypatch):
    from alpi import config as cfg_mod, engine, llm

    home = tmp_path / "h"
    home.mkdir()
    (home / "config.yaml").write_text("model: openrouter/x/y\nbudget:\n  daily_usd: 1.0\n")
    ledger.record(home, usd=0.10, tokens=1, tokens_in=1, tokens_out=0)

    def _one_expensive_tool_call(**_kw):
        yield {
            "final": True,
            "tool_calls": [{"id": "1", "name": "todo", "arguments": "{}"}],
            "input_tokens": 1, "output_tokens": 1, "cost_usd": 5.0,
        }

    monkeypatch.setattr(llm, "stream", _one_expensive_tool_call)

    recorded = {}
    monkeypatch.setattr(
        engine.Engine, "_record_run",
        lambda self, **kw: recorded.update(kw),
    )

    events = []
    engine.Engine(home, cfg_mod.load(home)).run_turn(
        "go", events.append, persist_inflight=False,
    )
    errors = [e.text for e in events if e.kind == "error"]

    assert len(errors) == 1, f"one cause, not a cause plus a wrong summary: {errors}"
    assert "Daily budget reached" in errors[0]
    assert "Reached max tool steps" not in " ".join(errors), (
        "the fallback overwrote the budget abort — the failure that made a "
        "budget-blocked fleet look like a step-cap problem"
    )
    assert "Daily budget reached" in recorded["assistant"], (
        "the run ledger must carry the real cause; recording 'max tool steps' "
        f"is what sent the diagnosis down the wrong path: {recorded.get('assistant')!r}"
    )
    assert "Reached max tool steps" not in recorded["assistant"]


class _Meta:
    id = "wg_1"
    name = "site-x"
    hub_pubkey = "HUB"
    paused = False
    pipeline = ("intake",)
    pipeline_steps = {}


class _WG:
    meta = _Meta()


def _stale_open_task():
    import datetime as dt

    old = (dt.datetime.now(tz=dt.timezone.utc) - dt.timedelta(hours=6)).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )
    return [
        {"seq": 1, "from": "HUB", "ts": old, "text": "@scout #task #intake · go"},
        {"seq": 2, "from": "SCOUT", "ts": old, "text": "on it"},
    ]


def test_watchdog_burns_no_retry_while_the_budget_is_exhausted(tmp_path, monkeypatch):
    import asyncio

    home = _profile(tmp_path, 5.0, spent=6.0)
    spawned, blocked = [], []
    def _capture(wg_id, coro):
        coro.close()
        spawned.append(wg_id)

    monkeypatch.setattr(service, "_spawn_dispatch", _capture)
    monkeypatch.setattr(service, "_emit_wg_blocked", lambda *a, **k: blocked.append(a))
    monkeypatch.setattr(service, "_emit_wg_blocked_once", lambda *a, **k: blocked.append(a))

    for _ in range(4):
        asyncio.run(
            service._maybe_watchdog_close(home, "scout", _WG(), _stale_open_task())
        )

    state = service._load_poller_state(home)
    for cursor in POLLER_CURSORS:
        assert not state.get(cursor), (
            f"{cursor} advanced on a tick that never ran a turn — four of these "
            "exhaust the watchdog's retries and the phase never recovers"
        )
    assert spawned == []
    assert blocked == [], "wg.blocked fired while the real cause was budget"

    (home / "config.yaml").write_text("budget:\n  daily_usd: 50.0\n")
    service._WATCHDOG_OBSERVED_AT[(str(home), "wg_1")] = (
        2,
        time.monotonic() - service._HUB_FOLLOWUP_STALE_SECONDS - 1,
    )
    asyncio.run(
        service._maybe_watchdog_close(home, "scout", _WG(), _stale_open_task())
    )
    assert len(spawned) == 1, "raising the cap must let the same wake dispatch"
    fired = service._load_poller_state(home)["hub_watchdog_fire_count"]["wg_1"]
    assert fired[-1] == 1, f"first real fire must be attempt 1, got {fired}"


def test_every_dispatching_function_has_a_budget_guard():
    import ast

    def calls(node):
        return {
            sub.func.id
            for sub in ast.walk(node)
            if isinstance(sub, ast.Call) and isinstance(sub.func, ast.Name)
        }

    tree = ast.parse(service.Path(service.__file__).read_text())
    dispatchers = [
        fn for fn in ast.walk(tree)
        if isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef))
        and "_spawn_dispatch" in calls(fn)
    ]
    assert dispatchers, "no function spawns dispatches — the guards moved"
    for fn in dispatchers:
        assert "_budget_blocks_dispatch" in calls(fn), (
            f"{fn.name} spawns a turn with no budget guard; place it before the "
            "poller cursors so a blocked wake re-fires when the cap resets"
        )
