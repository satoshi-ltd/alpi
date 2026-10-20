from __future__ import annotations

import asyncio
import tempfile
import threading
import socket
from pathlib import Path

import pytest
from click.testing import CliRunner

from alpi import cli, home as home_mod, ui
from alpi.host import activity, handlers, schedule, server
from alpi.scheduler import jobs_store
from alpi.scheduler import run as scheduler
from alpi.tools.schedule import Schedule
from alpi.tui import host_client


@pytest.mark.parametrize("entry", ["cli", "setup", "tool"])
def test_console_entries_delegate_to_the_same_fire_path(tmp_home_no_env, monkeypatch, entry):
    calls = []
    monkeypatch.setattr(scheduler, "fire_from_console", lambda h, jid: (calls.append((h, jid)) or (True, "accepted")))
    monkeypatch.setattr(cli, "_bootstrap", lambda h: None)
    jobs_store.update(tmp_home_no_env, lambda _jobs: [{"id": "job00001", "kind": "cron", "expression": "* * * * *", "prompt": "test"}])
    if entry == "cli":
        result = CliRunner().invoke(cli.main, ["schedule", "fire", "job00001"])
        assert result.exit_code == 0, result.output
    elif entry == "setup":
        choices = iter(["job00001", "fire", None])
        monkeypatch.setattr(ui, "menu", lambda *a, **kw: next(choices))
        monkeypatch.setattr(ui, "ok_and_wait", lambda *a: None)
        cli._schedules_setup(tmp_home_no_env)
    else:
        assert Schedule().run(action="fire", id="job00001").ok
    assert calls == [(tmp_home_no_env, "job00001")]


def test_console_fire_keeps_local_execution_without_a_daemon(tmp_home_no_env, monkeypatch):
    monkeypatch.setattr(host_client, "daemon_present", lambda: False)
    calls = []
    monkeypatch.setattr(scheduler, "fire_by_id", lambda h, jid: (calls.append((h, jid)) or (True, "finished")))
    assert scheduler.fire_from_console(tmp_home_no_env, "job00001") == (True, "finished")
    assert calls == [(tmp_home_no_env, "job00001")]


def test_connect_timeout_before_writing_falls_back_locally(tmp_home_no_env, monkeypatch):
    path = tmp_home_no_env / "host" / "host.sock"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.touch()
    monkeypatch.setattr(host_client, "socket_path", lambda: path)

    async def no_connection(_path):
        raise asyncio.TimeoutError

    monkeypatch.setattr(host_client, "_open", no_connection)
    calls = []
    monkeypatch.setattr(scheduler, "fire_by_id", lambda h, jid: (calls.append((h, jid)) or (True, "finished")))
    assert scheduler.fire_from_console(tmp_home_no_env, "job00001") == (True, "finished")
    assert calls == [(tmp_home_no_env, "job00001")]


@pytest.mark.parametrize("profile", ["default", "work"])
def test_console_routes_the_job_to_its_profile(tmp_home_no_env, monkeypatch, profile):
    target = tmp_home_no_env if profile == "default" else tmp_home_no_env / "profiles" / profile
    monkeypatch.setattr(host_client, "daemon_present", lambda: True)
    calls = []

    async def call(method, params):
        calls.append((method, params))
        return {"ok": True}

    monkeypatch.setattr(host_client, "acall", call)
    assert scheduler.fire_from_console(target, "job00001")[0]
    assert calls == [("host.schedule.fire", {"profile": profile, "id": "job00001"})]


@pytest.mark.parametrize("failure", [host_client.HostUnavailable("timeout"), host_client.HostError(-32601, "method-not-found"), None])
def test_console_never_repeats_an_attempted_daemon_mutation(tmp_home_no_env, monkeypatch, failure):
    monkeypatch.setattr(host_client, "daemon_present", lambda: True)
    calls = []

    async def call(*a, **kw):
        calls.append(a)
        if failure:
            raise failure
        return {"unexpected": True}

    monkeypatch.setattr(host_client, "acall", call)
    monkeypatch.setattr(scheduler, "fire_by_id", lambda *a: pytest.fail("ambiguous fire repeated locally"))
    ok, message = scheduler.fire_from_console(tmp_home_no_env, "job00001")
    assert not ok and "check Activity" in message
    assert len(calls) == 1


@pytest.mark.integration
def test_orphaned_socket_falls_back_before_any_request_is_sent(monkeypatch):
    with tempfile.TemporaryDirectory(prefix="act2-stale-", dir="/tmp") as directory:
        root = Path(directory)
        monkeypatch.setattr(home_mod, "_ROOT", root)
        monkeypatch.setenv("ALPI_HOME", str(root))
        path = root / "host" / "host.sock"
        path.parent.mkdir()
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as stale:
            stale.bind(str(path))
        calls = []
        monkeypatch.setattr(scheduler, "fire_by_id", lambda h, jid: (calls.append((h, jid)) or (True, "finished locally")))
        assert host_client.daemon_present()
        assert scheduler.fire_from_console(root, "job00001") == (True, "finished locally")
        assert calls == [(root, "job00001")]
        assert path.exists()


@pytest.mark.integration
@pytest.mark.parametrize("failure", ["close", "timeout"])
def test_console_does_not_fall_back_after_the_daemon_receives_the_request(monkeypatch, failure):
    with tempfile.TemporaryDirectory(prefix="act2-sent-", dir="/tmp") as directory:
        root = Path(directory)
        monkeypatch.setattr(home_mod, "_ROOT", root)
        monkeypatch.setenv("ALPI_HOME", str(root))
        path = root / "host" / "host.sock"
        path.parent.mkdir()
        original = host_client.acall
        monkeypatch.setattr(host_client, "acall", lambda method, params: original(method, params, timeout=.5))
        monkeypatch.setattr(scheduler, "fire_by_id", lambda *a: pytest.fail("sent request repeated locally"))

        async def check():
            received = []
            tasks = []
            release = asyncio.Event()

            async def handle(reader, writer):
                tasks.append(asyncio.current_task())
                received.append(await reader.readline())
                if failure == "timeout":
                    await release.wait()
                writer.close()
                await writer.wait_closed()

            srv = await asyncio.start_unix_server(handle, str(path))
            try:
                ok, message = await asyncio.to_thread(scheduler.fire_from_console, root, "job00001")
                assert not ok and "check Activity" in message
                assert len(received) == 1 and b'host.schedule.fire' in received[0]
            finally:
                release.set()
                srv.close()
                await srv.wait_closed()
                await asyncio.gather(*tasks)

        asyncio.run(check())


@pytest.mark.integration
def test_cli_fire_is_visible_in_daemon_activity_until_completion(monkeypatch):
    with tempfile.TemporaryDirectory(prefix="act2-", dir="/tmp") as directory:
        root = Path(directory)
        monkeypatch.setattr(home_mod, "_ROOT", root)
        monkeypatch.setenv("ALPI_HOME", str(root))
        monkeypatch.setattr(cli, "_bootstrap", lambda h: None)
        jobs_store.update(root, lambda _jobs: [{"id": "job00001", "title": "Test job", "kind": "cron", "expression": "* * * * *", "prompt": "test"}])
        entered, release = threading.Event(), threading.Event()

        def run_job(*a):
            entered.set()
            release.wait(5)
            return scheduler.JobOutcome(True, "finished")

        monkeypatch.setattr(scheduler, "run_job", run_job)

        async def check():
            srv = server.Server(home=root)
            handlers.register(srv)
            schedule.register(srv)
            activity.register(srv)
            await srv.start()
            try:
                result = await asyncio.to_thread(CliRunner().invoke, cli.main, ["schedule", "fire", "job00001"])
                assert result.exit_code == 0, result.output
                assert "accepted by daemon" in result.output
                for _ in range(100):
                    if entered.is_set():
                        break
                    await asyncio.sleep(.01)
                assert entered.is_set()
                state = await host_client.acall("host.activity.list")
                assert any(r.get("job_id") == "job00001" for r in state["running"])
            finally:
                release.set()
                if schedule._BACKGROUND_FIRES:
                    await asyncio.gather(*list(schedule._BACKGROUND_FIRES))
                await srv.stop()
                activity._reset_for_tests()
            assert not activity.snapshot()["running"]

        asyncio.run(check())
