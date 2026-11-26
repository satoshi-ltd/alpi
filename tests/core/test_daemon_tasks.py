from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path

import pytest
from click.testing import CliRunner

from alpi import daemon_tasks, service


@pytest.fixture
def fast(monkeypatch, tmp_path: Path) -> dict:
    monkeypatch.setattr(daemon_tasks, "RESTART_BASE_S", 0.01)
    monkeypatch.setattr(daemon_tasks, "RESTART_MAX_S", 0.04)
    monkeypatch.setattr(daemon_tasks, "HEALTHY_AFTER_S", 0.2)
    alerts: list[dict] = []

    def fake_alert(home, profile, *, title, body, code, type="error", kind="provider"):
        alerts.append({"profile": profile, "title": title, "body": body, "code": code, "type": type, "kind": kind})

    monkeypatch.setattr("alpi.provider_pause._file_alert", fake_alert)
    daemon_tasks.configure(tmp_path)
    yield {"alerts": alerts, "root": tmp_path}
    daemon_tasks.clear(tmp_path)


def _snapshot(root: Path) -> dict:
    return {row["task"]: row for row in daemon_tasks.read(root, os.getpid())}


@pytest.mark.asyncio
async def test_a_task_that_raises_is_started_again(fast, monkeypatch) -> None:
    monkeypatch.setattr(daemon_tasks, "HEALTHY_AFTER_S", 30.0)
    calls: list[int] = []
    stop = asyncio.Event()

    async def flaky(home: Path, profile: str) -> None:
        calls.append(1)
        if len(calls) < 3:
            raise RuntimeError("listener died")
        await stop.wait()

    guard = asyncio.create_task(service._guard_task(flaky, fast["root"], "alice", "alp"))
    for _ in range(200):
        if len(calls) >= 3:
            break
        await asyncio.sleep(0.01)
    assert len(calls) == 3
    row = _snapshot(fast["root"])["alice/alp"]
    assert row["state"] == "running"
    assert row["failures"] == 2
    assert "listener died" in row["last_error"]
    assert fast["alerts"] == []
    guard.cancel()
    with pytest.raises(asyncio.CancelledError):
        await guard
    assert "alice/alp" not in _snapshot(fast["root"])


@pytest.mark.asyncio
async def test_repeated_failures_alert_the_owner_once_then_say_it_recovered(fast) -> None:
    calls: list[int] = []
    stop = asyncio.Event()

    async def broken(home: Path) -> None:
        calls.append(1)
        if len(calls) <= 5:
            raise OSError("token sk-ant-api03-ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 rejected")
        await stop.wait()

    guard = asyncio.create_task(service._guard_task(broken, fast["root"], "bob", "schedule"))
    for _ in range(300):
        if any(a["code"] == "task_recovered" for a in fast["alerts"]):
            break
        await asyncio.sleep(0.01)
    guard.cancel()
    with pytest.raises(asyncio.CancelledError):
        await guard
    codes = [a["code"] for a in fast["alerts"]]
    assert codes == ["task_failing", "task_recovered"]
    failing = fast["alerts"][0]
    assert failing["profile"] == "bob" and failing["kind"] == "daemon" and failing["type"] == "error"
    assert "schedule" in failing["title"]
    assert "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789" not in failing["body"]


@pytest.mark.asyncio
async def test_the_restart_delay_grows_and_is_capped(fast, monkeypatch) -> None:
    delays: list[float] = []
    real_sleep = asyncio.sleep

    async def record(delay, *a, **k):
        delays.append(delay)
        await real_sleep(0)

    monkeypatch.setattr(daemon_tasks.asyncio, "sleep", record)
    calls: list[int] = []

    async def always(home: Path) -> None:
        calls.append(1)
        if len(calls) > 5:
            return
        raise RuntimeError("x")

    await service._guard_task(always, fast["root"], "carol", "schedule")
    assert delays == [0.01, 0.02, 0.04, 0.04, 0.04]
    assert _snapshot(fast["root"])["carol/schedule"]["state"] == "stopped"


def test_daemon_status_json_lists_each_task(fast, monkeypatch) -> None:
    from alpi.cli import main as cli

    root = fast["root"]
    daemon_tasks._set("default/host", state="running", since=1.0, retry_at=None)
    daemon_tasks._set("default/alp", state="restarting", failures=2, last_error="OSError: port busy", retry_at=2.0)
    monkeypatch.setattr(service, "daemon_running_pid", lambda r: os.getpid())
    monkeypatch.setattr(service, "_uptime_seconds", lambda pid: 5)
    monkeypatch.setattr(service, "_detect_backend", lambda: None)
    monkeypatch.setattr("alpi.cli._root", lambda: root)
    monkeypatch.setattr("alpi.cli._provider_pauses", lambda: {})

    out = CliRunner().invoke(cli, ["daemon", "status", "--json"])
    assert out.exit_code == 0, out.output
    tasks = {t["task"]: t for t in json.loads(out.output)["tasks"]}
    assert tasks["default/host"]["state"] == "running"
    assert tasks["default/alp"]["state"] == "restarting" and tasks["default/alp"]["failures"] == 2

    text = CliRunner().invoke(cli, ["daemon", "status"]).output
    assert "tasks: 1 running" in text
    assert "default/alp  · restarting after 2 failure(s): OSError: port busy" in text


def test_a_snapshot_from_another_process_is_ignored(fast) -> None:
    daemon_tasks._set("default/host", state="running")
    assert daemon_tasks.read(fast["root"], os.getpid() + 1) is None
    assert daemon_tasks.read(fast["root"], None) is None


@pytest.mark.asyncio
async def test_cancelling_the_supervisor_lets_the_task_finish_its_cleanup(fast) -> None:
    started = asyncio.Event()
    cleaned: list[bool] = []

    async def server(home: Path, profile: str) -> None:
        started.set()
        try:
            await asyncio.Event().wait()
        finally:
            await asyncio.sleep(0.01)
            cleaned.append(True)

    guard = asyncio.create_task(service._guard_task(server, fast["root"], "default", "host"))
    await started.wait()
    guard.cancel()
    with pytest.raises(asyncio.CancelledError):
        await guard
    assert cleaned == [True]


@pytest.mark.asyncio
async def test_a_cancellation_raised_inside_the_task_is_a_failure_not_a_shutdown(fast) -> None:
    calls: list[int] = []
    stop = asyncio.Event()

    async def closed_from_elsewhere(home: Path, profile: str) -> None:
        calls.append(1)
        if len(calls) == 1:
            raise asyncio.CancelledError()
        await stop.wait()

    guard = asyncio.create_task(service._guard_task(closed_from_elsewhere, fast["root"], "default", "host"))
    for _ in range(200):
        if len(calls) >= 2:
            break
        await asyncio.sleep(0.01)
    assert len(calls) == 2
    row = _snapshot(fast["root"])["default/host"]
    assert row["state"] == "running" and row["failures"] == 1
    guard.cancel()
    with pytest.raises(asyncio.CancelledError):
        await guard


@pytest.mark.asyncio
async def test_a_recovered_task_shows_no_old_error_and_the_file_is_private(fast) -> None:
    calls: list[int] = []
    stop = asyncio.Event()

    async def once(home: Path) -> None:
        calls.append(1)
        if len(calls) == 1:
            raise RuntimeError("first boot failed")
        await stop.wait()

    guard = asyncio.create_task(service._guard_task(once, fast["root"], "eve", "schedule"))
    await asyncio.sleep(0.4)
    row = _snapshot(fast["root"])["eve/schedule"]
    assert row["failures"] == 0 and not row.get("last_error")
    assert (daemon_tasks.snapshot_path(fast["root"]).stat().st_mode & 0o777) == 0o600
    guard.cancel()
    with pytest.raises(asyncio.CancelledError):
        await guard


@pytest.mark.asyncio
async def test_a_hot_reloaded_task_starts_with_a_clean_row(fast) -> None:
    daemon_tasks._set("alice/alp", state="stopped", failures=4, last_error="old")
    stop = asyncio.Event()

    async def listener(home: Path, profile: str) -> None:
        await stop.wait()

    guard = asyncio.create_task(service._guard_task(listener, fast["root"], "alice", "alp"))
    await asyncio.sleep(0.02)
    row = _snapshot(fast["root"])["alice/alp"]
    assert row["failures"] == 0 and "last_error" not in row
    guard.cancel()
    with pytest.raises(asyncio.CancelledError):
        await guard


@pytest.mark.asyncio
async def test_main_all_writes_the_snapshot_and_clear_removes_it(tmp_path: Path, monkeypatch) -> None:
    root = tmp_path
    stop_after = asyncio.Event()

    def fake_start(root_, profiles, registry):
        daemon_tasks._set("default/host", state="running")
        stop_after.set()

    monkeypatch.setattr(service, "_start_new_profiles", fake_start)
    monkeypatch.setattr(service, "_load_env", lambda *a, **k: None)
    monkeypatch.setattr(service, "_PROFILE_RESCAN_SECONDS", 0.01)
    monkeypatch.setattr("alpi.updater.install_kind", lambda: None)
    main = asyncio.create_task(service._main_all(root, ["default"]))
    await stop_after.wait()
    await asyncio.sleep(0.02)
    assert daemon_tasks.snapshot_path(root).is_file()
    main.cancel()
    with pytest.raises(asyncio.CancelledError):
        await main
    daemon_tasks.clear(root)
    assert not daemon_tasks.snapshot_path(root).exists()


@pytest.mark.asyncio
async def test_a_cancel_after_the_healthy_window_stops_even_if_cleanup_raises(fast) -> None:
    starts: list[int] = []
    started = asyncio.Event()

    async def server(home: Path, profile: str) -> None:
        starts.append(1)
        started.set()
        try:
            await asyncio.Event().wait()
        finally:
            raise OSError("stop() failed")

    guard = asyncio.create_task(service._guard_task(server, fast["root"], "default", "host"))
    await started.wait()
    await asyncio.sleep(0.3)
    guard.cancel()
    with pytest.raises(asyncio.CancelledError):
        await asyncio.wait_for(guard, 2)
    assert starts == [1]


@pytest.mark.asyncio
async def test_each_streak_alerts_once_and_recovers_once(fast, monkeypatch) -> None:
    plan = ["fail"] * 3 + ["ok"] + ["fail"] * 3 + ["ok"]
    gates: list[asyncio.Event] = []

    async def scripted(home: Path) -> None:
        step = plan.pop(0) if plan else "hold"
        if step == "fail":
            raise RuntimeError("down")
        gate = asyncio.Event()
        gates.append(gate)
        if step == "ok":
            await asyncio.sleep(0.3)
            raise RuntimeError("down again")
        await gate.wait()

    guard = asyncio.create_task(service._guard_task(scripted, fast["root"], "zed", "schedule"))
    for _ in range(400):
        if not plan and len(gates) >= 3:
            break
        await asyncio.sleep(0.01)
    await asyncio.sleep(0.3)
    guard.cancel()
    with pytest.raises(asyncio.CancelledError):
        await guard
    codes = [a["code"] for a in fast["alerts"]]
    assert codes == ["task_failing", "task_recovered", "task_failing", "task_recovered"]


@pytest.mark.asyncio
async def test_a_task_that_never_stops_failing_is_still_supervised(fast, monkeypatch) -> None:
    monkeypatch.setattr(daemon_tasks, "RESTART_BASE_S", 5.0)
    monkeypatch.setattr(daemon_tasks, "RESTART_MAX_S", 300.0)
    monkeypatch.setattr(daemon_tasks, "HEALTHY_AFTER_S", 300.0)
    monkeypatch.setattr(daemon_tasks, "_write", lambda: None)
    monkeypatch.setattr(daemon_tasks.log, "error", lambda *args, **kwargs: None)
    delays: list[float] = []
    real_sleep = asyncio.sleep

    async def instant(delay: float) -> None:
        delays.append(delay)
        await real_sleep(0)

    monkeypatch.setattr(daemon_tasks.asyncio, "sleep", instant)
    calls = 0
    stop = asyncio.Event()

    async def broken(home: Path) -> None:
        nonlocal calls
        calls += 1
        if calls <= 1100:
            raise RuntimeError("still broken")
        await stop.wait()

    guard = asyncio.create_task(service._guard_task(broken, fast["root"], "alice", "schedule"))
    for _ in range(20000):
        if calls > 1100 or guard.done():
            break
        await real_sleep(0)
    assert not guard.done(), guard.exception()
    assert calls == 1101
    assert delays[:7] == [5.0, 10.0, 20.0, 40.0, 80.0, 160.0, 300.0]
    assert set(delays[6:]) == {300.0}
    assert daemon_tasks._states["alice/schedule"]["failures"] == 1100
    guard.cancel()
    with pytest.raises(asyncio.CancelledError):
        await guard


def test_the_restart_delay_grows_to_its_cap_for_any_failure_count() -> None:
    assert [daemon_tasks.restart_delay(n) for n in (0, 1, 2, 7, 1025, 10**9)] == [5.0, 5.0, 10.0, 300.0, 300.0, 300.0]
