"""``host.schedule.list`` + ``host.schedule.remove`` — read-only view +
delete of ``schedule/jobs.json`` from the desktop control plane.
Mutations beyond delete (add / pause) are intentionally not exposed:
job creation lives inside the agent (``schedule`` tool) so the
threat-scan + skill rules stay enforced; the desktop is just a
visibility + cleanup surface."""

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
    """``host.schedule.fire`` delegates to ``scheduler.run.fire_by_id``
    so manual + auto fires share the same threat-scan + dispatch."""
    home = tmp_path / "h"
    home.mkdir()
    monkeypatch.setattr(data_handlers, "_resolve_home", lambda p: home)
    _seed_jobs(home, {"id": "real0001", "kind": "cron",
                       "expression": "* * * * *", "prompt": "x"})
    srv = host_server.Server(home=home)
    data_schedule.register(srv)

    captured: list[tuple[Path, str]] = []

    def fake_fire(h, jid):
        captured.append((h, jid))
        return True, "fired"

    monkeypatch.setattr("alpi.scheduler.run.fire_by_id", fake_fire)

    resp = await srv._dispatch({
        "id": "r", "method": "host.schedule.fire",
        "params": {"profile": "default", "id": "real0001"},
    })
    assert resp["result"] == {"ok": True, "detail": "fired"}
    assert captured == [(home, "real0001")]


@pytest.mark.asyncio
async def test_fire_runs_off_loop_so_chat_can_progress(
    tmp_path: Path, monkeypatch,
) -> None:
    """fire_by_id wraps subprocess.run(timeout=600). If the host handler
    awaits it inline, the host loop freezes — same root cause as
    scheduler.serve()'s old inline tick()."""
    import asyncio
    import time as _time

    home = tmp_path / "h"
    home.mkdir()
    monkeypatch.setattr(data_handlers, "_resolve_home", lambda p: home)
    _seed_jobs(home, {"id": "blkr1234", "kind": "cron",
                       "expression": "* * * * *", "prompt": "x"})
    srv = host_server.Server(home=home)
    data_schedule.register(srv)

    fire_started = asyncio.Event()
    fire_done = asyncio.Event()
    block_s = 0.4

    def slow_fire(h, jid):  # noqa: ANN001
        loop.call_soon_threadsafe(fire_started.set)
        _time.sleep(block_s)
        loop.call_soon_threadsafe(fire_done.set)
        return True, "fired"

    monkeypatch.setattr("alpi.scheduler.run.fire_by_id", slow_fire)

    loop = asyncio.get_running_loop()
    counter = {"wakes": 0}

    async def heartbeat() -> None:
        while not fire_done.is_set():
            await asyncio.sleep(0.05)
            counter["wakes"] += 1

    dispatch_task = asyncio.create_task(srv._dispatch({
        "id": "r", "method": "host.schedule.fire",
        "params": {"profile": "default", "id": "blkr1234"},
    }))
    hb_task = asyncio.create_task(heartbeat())

    try:
        await asyncio.wait_for(fire_started.wait(), timeout=2.0)
        resp = await asyncio.wait_for(dispatch_task, timeout=block_s + 2.0)
    finally:
        hb_task.cancel()
        try:
            await hb_task
        except (asyncio.CancelledError, Exception):  # noqa: BLE001
            pass

    assert resp["result"] == {"ok": True, "detail": "fired"}
    assert counter["wakes"] >= 3, (
        f"host loop starved during host.schedule.fire — only {counter['wakes']} "
        "heartbeats fired while fire_by_id blocked; handler must run it in an executor"
    )


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
    target = tmp_path / "jobs.json"
    data_schedule._atomic_write_json(target, [{"id": "a"}])
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
