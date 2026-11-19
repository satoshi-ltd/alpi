from __future__ import annotations

import asyncio
import shutil
import tempfile
import time
from pathlib import Path

import pytest
from click.testing import CliRunner

from alpi.tui import host_client


@pytest.fixture
def stuck_socket(monkeypatch):
    base = Path(tempfile.mkdtemp(prefix="hc-", dir="/tmp"))
    path = base / "host.sock"
    monkeypatch.setattr(host_client, "socket_path", lambda: path)
    yield path
    shutil.rmtree(base, ignore_errors=True)


async def _serve(path: Path, chatter: bool):
    async def handle(reader, writer):
        try:
            while True:
                if chatter:
                    writer.write(b'{"event": "heartbeat"}\n')
                    await writer.drain()
                await asyncio.sleep(0.1)
        except (ConnectionError, asyncio.CancelledError):
            pass

    return await asyncio.start_unix_server(handle, path=str(path))


@pytest.mark.asyncio
@pytest.mark.parametrize("chatter", [False, True])
async def test_a_daemon_that_never_answers_is_reported_within_the_short_timeout(stuck_socket, chatter):
    server = await _serve(stuck_socket, chatter)
    try:
        start = time.monotonic()
        with pytest.raises(host_client.HostUnavailable) as exc:
            await host_client.ensure_responsive(timeout=0.5)
        assert time.monotonic() - start < 2.0
        assert "did not answer within 0.5s" in str(exc.value)
        assert "alpi daemon status" in str(exc.value)
    finally:
        server.close()
        await server.wait_closed()


@pytest.mark.asyncio
async def test_a_call_is_bounded_as_a_whole_not_per_line(stuck_socket):
    server = await _serve(stuck_socket, chatter=True)
    try:
        start = time.monotonic()
        with pytest.raises(host_client.HostUnavailable):
            await host_client.acall("host.workgroup.remove", {}, timeout=0.5)
        assert time.monotonic() - start < 2.0
    finally:
        server.close()
        await server.wait_closed()


@pytest.mark.asyncio
async def test_a_daemon_without_the_probe_verb_still_counts_as_answering(stuck_socket):
    async def handle(reader, writer):
        line = await reader.readline()
        import json
        rid = json.loads(line)["id"]
        writer.write((json.dumps({"id": rid, "error": {"code": -32601, "message": "method-not-found"}}) + "\n").encode())
        await writer.drain()
        writer.close()

    server = await asyncio.start_unix_server(handle, path=str(stuck_socket))
    try:
        await host_client.ensure_responsive(timeout=1.0)
    finally:
        server.close()
        await server.wait_closed()


def test_workgroup_launch_exits_with_the_unresponsive_message_instead_of_waiting(stuck_socket, tmp_path, monkeypatch):
    import threading

    from alpi import cli

    ready = threading.Event()
    stop = threading.Event()

    def run_server():
        async def main():
            server = await _serve(stuck_socket, chatter=False)
            ready.set()
            while not stop.is_set():
                await asyncio.sleep(0.05)
            server.close()
            await server.wait_closed()
        asyncio.run(main())

    thread = threading.Thread(target=run_server, daemon=True)
    thread.start()
    assert ready.wait(5)
    monkeypatch.setattr(host_client, "ensure_responsive", lambda timeout=0.5, _real=host_client.ensure_responsive: _real(timeout=0.5))
    recipe = tmp_path / "chat.yaml"
    recipe.write_text("hub: default\nname: n\ntask: \"@scout hi\"\n")
    try:
        start = time.monotonic()
        result = CliRunner().invoke(cli.main, ["workgroup", "launch", "--recipe", str(recipe)])
        assert time.monotonic() - start < 5.0
        assert result.exit_code != 0
        assert "did not answer within" in result.output
    finally:
        stop.set()
        thread.join(5)


@pytest.mark.asyncio
async def test_a_connection_the_daemon_closes_is_not_called_unresponsive(stuck_socket):
    async def handle(reader, writer):
        await reader.readline()
        writer.close()

    server = await asyncio.start_unix_server(handle, path=str(stuck_socket))
    try:
        with pytest.raises(host_client.HostUnavailable) as exc:
            await host_client.ensure_responsive(timeout=1.0)
        assert "did not answer within" not in str(exc.value)
    finally:
        server.close()
        await server.wait_closed()


def test_workgroup_remove_checks_the_daemon_answers_first(monkeypatch, tmp_path):
    from alpi import cli
    from alpi.alp import workgroup as wg_mod
    from alpi.alp.keys import load_or_generate

    probed = []

    async def stuck(timeout=5.0):
        probed.append(timeout)
        raise host_client.HostUnavailable(host_client.UNRESPONSIVE.format(secs=timeout))

    async def never(*a, **k):
        raise AssertionError("remove was sent to a daemon that does not answer")

    home = cli.home.get_home(None)
    wg = wg_mod.create(home, name="t", hub_kp=load_or_generate(home), member_pubkeys=[])
    monkeypatch.setattr(host_client, "daemon_present", lambda: True)
    monkeypatch.setattr(host_client, "ensure_responsive", stuck)
    monkeypatch.setattr(host_client, "acall", never)
    result = CliRunner().invoke(cli.main, ["workgroup", "remove", wg.meta.id, "--yes"])
    assert result.exit_code != 0
    assert "did not answer within" in result.output
    assert probed == [5.0]


@pytest.mark.asyncio
async def test_host_ping_answers_without_work():
    from alpi.host import device_state, server as host_server

    assert await device_state._host_ping({}, None) == {"ok": True}
    assert "host.ping" in host_server._SCOPE_FREE_METHODS
