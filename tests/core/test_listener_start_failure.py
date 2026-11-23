from __future__ import annotations

import asyncio
import shutil
import tempfile
from pathlib import Path

import pytest

from alpi import home as home_mod
from alpi import service
from alpi.alp.server import Server as AlpServer
from alpi.host.server import Server as HostServer


@pytest.fixture
def home(monkeypatch):
    root = Path(tempfile.mkdtemp(prefix="alpi-sock-", dir="/tmp"))
    monkeypatch.setattr(home_mod, "_ROOT", root)
    yield root
    shutil.rmtree(root, ignore_errors=True)


def _fail_socket_chmod(monkeypatch) -> list[asyncio.AbstractServer]:
    listeners: list[asyncio.AbstractServer] = []
    real_start_unix_server = asyncio.start_unix_server
    real_chmod = Path.chmod

    async def start_unix_server(*args, **kwargs):
        listener = await real_start_unix_server(*args, **kwargs)
        listeners.append(listener)
        return listener

    def chmod(self, mode, **kwargs):
        if self.suffix == ".sock":
            raise PermissionError("chmod refused")
        return real_chmod(self, mode, **kwargs)

    monkeypatch.setattr(asyncio, "start_unix_server", start_unix_server)
    monkeypatch.setattr(Path, "chmod", chmod)
    return listeners


@pytest.mark.asyncio
async def test_an_alp_start_that_fails_after_binding_leaves_nothing_open(home: Path, monkeypatch) -> None:
    monkeypatch.setattr(service, "_resolve_alp_tcp", lambda *a, **k: (None, None))
    listeners = _fail_socket_chmod(monkeypatch)
    servers: list[AlpServer] = []
    real_start = AlpServer.start

    async def start(self):
        servers.append(self)
        await real_start(self)

    monkeypatch.setattr(AlpServer, "start", start)

    for _ in range(2):
        with pytest.raises(PermissionError):
            await service._run_alp(home, "default")

    assert len(listeners) == 2 and not any(listener.is_serving() for listener in listeners)
    assert all(s.replay._fd is None for s in servers)
    assert not (home / "alp" / "alp.sock").exists()


@pytest.mark.asyncio
async def test_a_host_start_that_fails_after_binding_leaves_nothing_open(home: Path, monkeypatch) -> None:
    async def ready(self):
        return True

    monkeypatch.setattr(HostServer, "_ensure_credentials_ready", ready)
    listeners = _fail_socket_chmod(monkeypatch)

    for _ in range(2):
        with pytest.raises(PermissionError):
            await service._run_host(home, "default")

    assert len(listeners) == 2 and not any(listener.is_serving() for listener in listeners)
    assert not (home / "host" / "host.sock").exists()


def test_the_host_runner_test_above_left_no_activity_running() -> None:
    from alpi.host import activity, events

    assert activity._enabled is False
    assert activity._on_event not in events._listeners
