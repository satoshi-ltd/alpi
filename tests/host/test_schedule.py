from __future__ import annotations

import json
from pathlib import Path

import pytest

from alpi.host import handlers as data_handlers
from alpi.host import schedule as data_schedule
from alpi.host import server as host_server


def _seed_jobs(home: Path, *jobs: dict) -> Path:
    p = home / "schedule" / "jobs.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(list(jobs)))
    return p


@pytest.mark.asyncio
async def test_list_returns_empty_when_no_file(tmp_path: Path, monkeypatch) -> None:
    home = tmp_path / "h"
    home.mkdir()
    monkeypatch.setattr(data_handlers, "_resolve_home", lambda p: home)
    srv = host_server.Server(home=home)
    data_schedule.register(srv)

    resp = await srv._dispatch({
        "id": "r", "method": "host.schedule.list",
        "params": {"profile": "default"},
    })
    assert resp["result"]["jobs"] == []


@pytest.mark.asyncio
async def test_list_returns_jobs(tmp_path: Path, monkeypatch) -> None:
    home = tmp_path / "h"
    home.mkdir()
    monkeypatch.setattr(data_handlers, "_resolve_home", lambda p: home)
    _seed_jobs(
        home,
        {"id": "abc12345", "kind": "cron", "expression": "0 9 * * 1",
         "prompt": "weekly digest"},
        {"id": "def67890", "kind": "once", "run_at": "2026-12-31T23:59:00",
         "prompt": "year end"},
    )
    srv = host_server.Server(home=home)
    data_schedule.register(srv)

    resp = await srv._dispatch({
        "id": "r", "method": "host.schedule.list",
        "params": {"profile": "default"},
    })
    rows = resp["result"]["jobs"]
    assert [r["id"] for r in rows] == ["abc12345", "def67890"]
    from datetime import datetime
    assert datetime.fromisoformat(rows[0]["next_fire"]) is not None
    assert rows[1]["next_fire"].startswith("2026-12-31T23:59")


@pytest.mark.asyncio
async def test_remove_drops_target_job(tmp_path: Path, monkeypatch) -> None:
    home = tmp_path / "h"
    home.mkdir()
    monkeypatch.setattr(data_handlers, "_resolve_home", lambda p: home)
    p = _seed_jobs(
        home,
        {"id": "keep0001", "kind": "cron", "expression": "* * * * *",
         "prompt": "stay"},
        {"id": "drop0001", "kind": "once", "run_at": "2030-01-01T00:00:00",
         "prompt": "go"},
    )
    srv = host_server.Server(home=home)
    data_schedule.register(srv)

    resp = await srv._dispatch({
        "id": "r", "method": "host.schedule.remove",
        "params": {"profile": "default", "id": "drop0001"},
    })
    assert resp["result"]["ok"] is True

    remaining = json.loads(p.read_text())
    assert [j["id"] for j in remaining] == ["keep0001"]


@pytest.mark.asyncio
async def test_remove_unknown_returns_404(tmp_path: Path, monkeypatch) -> None:
    home = tmp_path / "h"
    home.mkdir()
    monkeypatch.setattr(data_handlers, "_resolve_home", lambda p: home)
    _seed_jobs(home, {"id": "real0001", "kind": "cron", "expression": "* * * * *",
                       "prompt": "x"})
    srv = host_server.Server(home=home)
    data_schedule.register(srv)

    resp = await srv._dispatch({
        "id": "r", "method": "host.schedule.remove",
        "params": {"profile": "default", "id": "ghost000"},
    })
    assert resp["error"]["code"] == -32004


@pytest.mark.asyncio
async def test_remove_rejects_unsafe_id(tmp_path: Path, monkeypatch) -> None:
    """Path-traversal-ish ids are rejected by the shared ``_check_id``
    regex before they reach the JSON read."""
    home = tmp_path / "h"
    home.mkdir()
    monkeypatch.setattr(data_handlers, "_resolve_home", lambda p: home)
    srv = host_server.Server(home=home)
    data_schedule.register(srv)

    resp = await srv._dispatch({
        "id": "r", "method": "host.schedule.remove",
        "params": {"profile": "default", "id": "../etc"},
    })
    assert resp["error"]["code"] == -32602


@pytest.mark.asyncio
async def test_set_paused_flips_flag(tmp_path: Path, monkeypatch) -> None:
    home = tmp_path / "h"
    home.mkdir()
    monkeypatch.setattr(data_handlers, "_resolve_home", lambda p: home)
    p = _seed_jobs(
        home,
        {"id": "abc12345", "kind": "cron", "expression": "* * * * *",
         "prompt": "x"},
    )
    srv = host_server.Server(home=home)
    data_schedule.register(srv)

    resp = await srv._dispatch({
        "id": "r", "method": "host.schedule.set_paused",
        "params": {"profile": "default", "id": "abc12345", "paused": True},
    })
    assert resp["result"] == {"ok": True, "paused": True}
    after = json.loads(p.read_text())
    assert after[0].get("paused") is True

    resp = await srv._dispatch({
        "id": "r", "method": "host.schedule.set_paused",
        "params": {"profile": "default", "id": "abc12345", "paused": False},
    })
    assert resp["result"]["paused"] is False
    after = json.loads(p.read_text())
    assert after[0].get("paused") is False


@pytest.mark.asyncio
async def test_paused_jobs_skip_tick(tmp_path: Path) -> None:
    """``is_due`` short-circuits paused jobs so the scheduler tick
    leaves them alone — pause is "stop the schedule", not "delete"."""
    from alpi.scheduler.run import is_due

    job = {"id": "x", "kind": "cron", "expression": "* * * * *",
           "paused": True}
    assert is_due(job) is False
    job["paused"] = False
    assert is_due(job) is True


@pytest.mark.asyncio
async def test_fire_runs_job_via_scheduler(tmp_path: Path, monkeypatch) -> None:
    import asyncio

    home = tmp_path / "h"
    home.mkdir()
    monkeypatch.setattr(data_handlers, "_resolve_home", lambda p: home)
    _seed_jobs(home, {"id": "real0001", "kind": "cron",
                       "expression": "* * * * *", "prompt": "x"})
    srv = host_server.Server(home=home)
    data_schedule.register(srv)

    captured: list[tuple[Path, str]] = []
    done = asyncio.Event()
    loop = asyncio.get_running_loop()

    def fake_fire(h, jid):
        captured.append((h, jid))
        loop.call_soon_threadsafe(done.set)
        return True, "fired"

    monkeypatch.setattr("alpi.scheduler.run.fire_by_id", fake_fire)

    resp = await srv._dispatch({
        "id": "r", "method": "host.schedule.fire",
        "params": {"profile": "default", "id": "real0001"},
    })
    assert resp["result"] == {"ok": True, "id": "real0001"}
    await asyncio.wait_for(done.wait(), timeout=2.0)
    assert captured == [(home, "real0001")]


@pytest.mark.asyncio
async def test_fire_returns_before_job_completes(
    tmp_path: Path, monkeypatch,
) -> None:
    import asyncio
    import time as _time

    home = tmp_path / "h"
    home.mkdir()
    monkeypatch.setattr(data_handlers, "_resolve_home", lambda p: home)
    _seed_jobs(home, {"id": "blkr1234", "kind": "cron",
                       "expression": "* * * * *", "prompt": "x"})
    srv = host_server.Server(home=home)
    data_schedule.register(srv)

    block_s = 0.6
    fire_done = asyncio.Event()
    loop = asyncio.get_running_loop()

    def slow_fire(h, jid):  # noqa: ANN001
        _time.sleep(block_s)
        loop.call_soon_threadsafe(fire_done.set)
        return True, "fired"

    monkeypatch.setattr("alpi.scheduler.run.fire_by_id", slow_fire)

    t0 = _time.monotonic()
    resp = await srv._dispatch({
        "id": "r", "method": "host.schedule.fire",
        "params": {"profile": "default", "id": "blkr1234"},
    })
    elapsed = _time.monotonic() - t0

    assert resp["result"] == {"ok": True, "id": "blkr1234"}
    assert elapsed < block_s / 2, (
        f"host.schedule.fire blocked for {elapsed:.2f}s while the job "
        f"itself took {block_s}s — handler is not fire-and-forget."
    )

    # The background task still runs to completion and invokes fire_by_id.
    await asyncio.wait_for(fire_done.wait(), timeout=block_s + 2.0)


@pytest.mark.asyncio
async def test_fire_emits_schedule_done_event(
    tmp_path: Path, monkeypatch,
) -> None:
    import asyncio

    from alpi.host import events as host_events
    from alpi.scheduler.run import JobOutcome

    home = tmp_path / "h"
    home.mkdir()
    monkeypatch.setattr(data_handlers, "_resolve_home", lambda p: home)
    _seed_jobs(home, {"id": "evt00001", "kind": "cron",
                       "expression": "* * * * *", "prompt": "x"})
    srv = host_server.Server(home=home)
    data_schedule.register(srv)

    seen: list[tuple[str, dict]] = []
    monkeypatch.setattr(host_events, "emit",
                        lambda kind, data: seen.append((kind, data)))
    # Stub run_job (not fire_by_id) so the real emit path inside fire_by_id runs.
    monkeypatch.setattr("alpi.scheduler.run.run_job",
                        lambda job, home: JobOutcome(True, "delivered"))

    resp = await srv._dispatch({
        "id": "r", "method": "host.schedule.fire",
        "params": {"profile": "default", "id": "evt00001"},
    })
    assert resp["result"] == {"ok": True, "id": "evt00001"}

    for _ in range(20):
        if any(k == "schedule.done" for k, _ in seen):
            break
        await asyncio.sleep(0.05)

    done_events = [d for k, d in seen if k == "schedule.done"]
    assert done_events, f"expected schedule.done event, got: {[k for k, _ in seen]}"
    assert done_events[0]["job_id"] == "evt00001"


@pytest.mark.asyncio
async def test_fire_emits_schedule_failed_on_failure(
    tmp_path: Path, monkeypatch,
) -> None:
    import asyncio

    from alpi.host import events as host_events
    from alpi.scheduler.run import JobOutcome

    home = tmp_path / "h"
    home.mkdir()
    monkeypatch.setattr(data_handlers, "_resolve_home", lambda p: home)
    _seed_jobs(home, {"id": "fail0001", "kind": "cron",
                       "expression": "* * * * *", "prompt": "x"})
    srv = host_server.Server(home=home)
    data_schedule.register(srv)

    seen: list[tuple[str, dict]] = []
    monkeypatch.setattr(host_events, "emit",
                        lambda kind, data: seen.append((kind, data)))
    monkeypatch.setattr("alpi.scheduler.run.run_job",
                        lambda job, home: JobOutcome(False, "agent rc=1: boom"))

    resp = await srv._dispatch({
        "id": "r", "method": "host.schedule.fire",
        "params": {"profile": "default", "id": "fail0001"},
    })
    assert resp["result"] == {"ok": True, "id": "fail0001"}

    for _ in range(20):
        if any(k == "schedule.failed" for k, _ in seen):
            break
        await asyncio.sleep(0.05)

    failed_events = [d for k, d in seen if k == "schedule.failed"]
    assert failed_events, f"expected schedule.failed event, got: {[k for k, _ in seen]}"
    assert failed_events[0]["job_id"] == "fail0001"
    assert "boom" in failed_events[0]["message"]


@pytest.mark.asyncio
async def test_fire_holds_strong_reference_to_background_task(
    tmp_path: Path, monkeypatch,
) -> None:
    import asyncio
    import gc

    from alpi.host import schedule as sched_mod

    home = tmp_path / "h"
    home.mkdir()
    monkeypatch.setattr(data_handlers, "_resolve_home", lambda p: home)
    _seed_jobs(home, {"id": "refs0001", "kind": "cron",
                       "expression": "* * * * *", "prompt": "x"})
    srv = host_server.Server(home=home)
    data_schedule.register(srv)

    started = asyncio.Event()
    finish = asyncio.Event()
    loop = asyncio.get_running_loop()

    def slow_fire(h, jid):
        loop.call_soon_threadsafe(started.set)
        # Hold here until the test releases us.
        while not finish.is_set():
            import time as _t
            _t.sleep(0.02)
        return True, "fired"

    monkeypatch.setattr("alpi.scheduler.run.fire_by_id", slow_fire)

    sched_mod._BACKGROUND_FIRES.clear()
    await srv._dispatch({
        "id": "r", "method": "host.schedule.fire",
        "params": {"profile": "default", "id": "refs0001"},
    })
    await asyncio.wait_for(started.wait(), timeout=2.0)

    # Force a GC pass while the task is still in flight; without the strong ref this could collect the task object.
    gc.collect()
    assert len(sched_mod._BACKGROUND_FIRES) == 1, (
        "background task lost its strong reference; would be GC-eligible mid-fire"
    )

    finish.set()
    # Wait for the discard callback.
    for _ in range(40):
        if not sched_mod._BACKGROUND_FIRES:
            break
        await asyncio.sleep(0.05)
    assert not sched_mod._BACKGROUND_FIRES, (
        "discard callback did not run; task set leaks finished entries"
    )


@pytest.mark.asyncio
async def test_fire_swallows_background_exceptions(
    tmp_path: Path, monkeypatch,
) -> None:
    import asyncio

    home = tmp_path / "h"
    home.mkdir()
    monkeypatch.setattr(data_handlers, "_resolve_home", lambda p: home)
    _seed_jobs(home, {"id": "boom0001", "kind": "cron",
                       "expression": "* * * * *", "prompt": "x"})
    srv = host_server.Server(home=home)
    data_schedule.register(srv)

    raised = asyncio.Event()
    loop = asyncio.get_running_loop()

    def crash(h, jid):
        loop.call_soon_threadsafe(raised.set)
        raise RuntimeError("boom")

    monkeypatch.setattr("alpi.scheduler.run.fire_by_id", crash)

    resp = await srv._dispatch({
        "id": "r", "method": "host.schedule.fire",
        "params": {"profile": "default", "id": "boom0001"},
    })
    assert resp["result"] == {"ok": True, "id": "boom0001"}
    await asyncio.wait_for(raised.wait(), timeout=2.0)
    # Give the background task a moment to land in the except clause.
    await asyncio.sleep(0.1)


@pytest.mark.asyncio
async def test_remove_emits_schedule_changed(tmp_path: Path, monkeypatch) -> None:
    from alpi.host import events as host_events

    home = tmp_path / "h"
    home.mkdir()
    monkeypatch.setattr(data_handlers, "_resolve_home", lambda p: home)
    _seed_jobs(home, {"id": "drop0001", "kind": "cron",
                       "expression": "* * * * *", "prompt": "x"})
    srv = host_server.Server(home=home)
    data_schedule.register(srv)

    captured: list[tuple[str, dict]] = []
    monkeypatch.setattr(
        host_events, "emit",
        lambda kind, data=None: captured.append((kind, data or {})),
    )

    await srv._dispatch({
        "id": "r", "method": "host.schedule.remove",
        "params": {"profile": "default", "id": "drop0001"},
    })
    assert ("schedule.changed", {
        "profile": "default", "id": "drop0001", "action": "removed",
    }) in captured


@pytest.mark.asyncio
async def test_set_paused_emits_schedule_changed(tmp_path: Path, monkeypatch) -> None:
    from alpi.host import events as host_events

    home = tmp_path / "h"
    home.mkdir()
    monkeypatch.setattr(data_handlers, "_resolve_home", lambda p: home)
    _seed_jobs(home, {"id": "abc12345", "kind": "cron",
                       "expression": "* * * * *", "prompt": "x"})
    srv = host_server.Server(home=home)
    data_schedule.register(srv)

    captured: list[tuple[str, dict]] = []
    monkeypatch.setattr(
        host_events, "emit",
        lambda kind, data=None: captured.append((kind, data or {})),
    )

    await srv._dispatch({
        "id": "r", "method": "host.schedule.set_paused",
        "params": {"profile": "default", "id": "abc12345", "paused": True},
    })
    await srv._dispatch({
        "id": "r", "method": "host.schedule.set_paused",
        "params": {"profile": "default", "id": "abc12345", "paused": False},
    })
    actions = [d["action"] for k, d in captured if k == "schedule.changed"]
    assert actions == ["paused", "resumed"]


def test_atomic_write_no_tmp_left_behind(tmp_path: Path) -> None:
    from alpi.scheduler import jobs_store
    home = tmp_path / "h"
    jobs_store.update(home, lambda _old: [{"id": "a"}])
    target = jobs_store.jobs_path(home)
    assert target.exists()
    assert not target.with_suffix(target.suffix + ".tmp").exists()
    assert json.loads(target.read_text()) == [{"id": "a"}]


@pytest.mark.asyncio
async def test_fire_unknown_returns_404(tmp_path: Path, monkeypatch) -> None:
    home = tmp_path / "h"
    home.mkdir()
    monkeypatch.setattr(data_handlers, "_resolve_home", lambda p: home)
    _seed_jobs(home)  # empty
    srv = host_server.Server(home=home)
    data_schedule.register(srv)

    resp = await srv._dispatch({
        "id": "r", "method": "host.schedule.fire",
        "params": {"profile": "default", "id": "ghost000"},
    })
    assert resp["error"]["code"] == -32004

@pytest.mark.asyncio
async def test_schedule_list_runs_off_the_event_loop(
    tmp_path: Path, monkeypatch,
) -> None:
    import asyncio as _asyncio
    home = tmp_path / "h"
    home.mkdir()
    monkeypatch.setattr(data_handlers, "_resolve_home", lambda p: home)
    _seed_jobs(home, {"id": "abc12345", "kind": "cron", "expression": "* * * * *", "prompt": "x"})
    seen: list[str] = []
    real = _asyncio.to_thread

    async def spy(fn, *args, **kwargs):
        seen.append(getattr(fn, "__name__", ""))
        return await real(fn, *args, **kwargs)

    monkeypatch.setattr(data_schedule.asyncio, "to_thread", spy)
    srv = host_server.Server(home=home)
    data_schedule.register(srv)
    resp = await srv._dispatch({
        "id": "r", "method": "host.schedule.list", "params": {"profile": "default"},
    })
    assert [r["id"] for r in resp["result"]["jobs"]] == ["abc12345"]
    assert "read" in seen


def test_next_fire_shares_due_semantics() -> None:
    from datetime import datetime, timedelta

    from alpi.scheduler.run import next_fire

    now = datetime(2026, 6, 17, 12, 0).astimezone()
    # paused → no next fire
    assert next_fire({"kind": "cron", "expression": "0 7 * * *", "paused": True}, now) is None
    # never run → due on the next tick (now), not tomorrow's slot
    assert next_fire({"kind": "cron", "expression": "0 7 * * *"}, now) == now
    # overdue (last ran 2 days ago on a daily 7am cron) → still due now
    overdue = {"kind": "cron", "expression": "0 7 * * *",
               "last_run_at": (now - timedelta(days=2)).isoformat()}
    assert next_fire(overdue, now) == now
    # ran on schedule today → next is tomorrow's slot, in the future
    ran = {"kind": "cron", "expression": "0 7 * * *",
           "last_run_at": now.replace(hour=7, minute=0).isoformat()}
    nf = next_fire(ran, now)
    assert nf is not None and nf > now
    # past `once` not yet run → due now (fires next tick), not null
    assert next_fire({"kind": "once", "run_at": "2020-01-01T00:00:00"}, now) == now
    # future `once` → its run_at
    assert next_fire({"kind": "once", "run_at": "2030-01-01T00:00:00"}, now) is not None
    # `once` already run → done, no next fire
    assert next_fire({"kind": "once", "run_at": "2030-01-01T00:00:00",
                      "last_run_at": now.isoformat()}, now) is None


@pytest.mark.asyncio
async def test_list_next_fire_uses_home_for_due_inactivity(tmp_path: Path, monkeypatch) -> None:
    home = tmp_path / "h"
    home.mkdir()
    monkeypatch.setattr(data_handlers, "_resolve_home", lambda p: home)
    _seed_jobs(home, {"id": "inact001", "kind": "inactivity", "after_hours": 2,
                       "prompt": "nudge"})
    srv = host_server.Server(home=home)
    data_schedule.register(srv)
    resp = await srv._dispatch({
        "id": "r", "method": "host.schedule.list", "params": {"profile": "default"},
    })
    # No sessions yet → is_due(inactivity, home) is True; next_fire must delegate
    # to it (needs home) and report "now", not null.
    assert resp["result"]["jobs"][0]["next_fire"] is not None
