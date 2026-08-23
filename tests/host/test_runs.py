from __future__ import annotations

from pathlib import Path

import pytest

from alpi import runs
from alpi.core.run_context import RunContext
from alpi.host import handlers, runs as host_runs
from alpi.host.connection_context import ConnectionContext, use
from alpi.host.server import Server


def _context(home: Path, run_id: str, connection_id: str = "host") -> RunContext:
    return RunContext(
        run_id=run_id, home=home, workspace=home, profile="default", source="user",
        session_id="s1", connection_id=connection_id,
    )


def _server(home: Path, monkeypatch) -> Server:
    monkeypatch.setattr(handlers, "_resolve_home", lambda _profile: home)
    server = Server(home=home)
    host_runs.register(server)
    return server


@pytest.mark.asyncio
async def test_list_and_read_are_connection_scoped(tmp_path: Path, monkeypatch) -> None:
    own = _context(tmp_path, "own")
    other = _context(tmp_path, "other", "conn_other")
    for context in (own, other):
        runs.start(context, model="m")
        runs.finish(context, "completed")
    server = _server(tmp_path, monkeypatch)

    response = await server._dispatch({
        "id": "1", "method": "host.runs.list", "params": {"profile": "default"},
    })
    assert [row["id"] for row in response["result"]["runs"]] == ["own"]

    missing = await server._dispatch({
        "id": "2", "method": "host.run.read",
        "params": {"profile": "default", "id": "other"},
    })
    assert missing["error"]["message"] == "not-found"


@pytest.mark.asyncio
async def test_cancel_interrupts_owned_active_run(tmp_path: Path, monkeypatch) -> None:
    context = _context(tmp_path, "active", "conn_a")
    runs.start(context)
    server = _server(tmp_path, monkeypatch)

    class FakeEngine:
        reason = ""
        session = type("Session", (), {"connection_id": "conn_a"})()

        def request_interrupt(self, reason: str) -> None:
            self.reason = reason

    engine = FakeEngine()
    monkeypatch.setattr("alpi.host.chat.active_run", lambda profile, run_id: engine)
    with use(ConnectionContext("conn_a", "dev_a", "remote")):
        response = await server._dispatch({
            "id": "1", "method": "host.run.cancel",
            "params": {"profile": "default", "id": "active"},
        })
    assert response["result"] == {"cancelled": True}
    assert engine.reason == "run-cancel-rpc"


@pytest.mark.asyncio
async def test_local_operator_can_cancel_a_remote_run(tmp_path: Path, monkeypatch) -> None:
    context = _context(tmp_path, "remote-active", "conn_phone")
    runs.start(context)
    server = _server(tmp_path, monkeypatch)

    class FakeEngine:
        reason = ""

        def request_interrupt(self, reason: str) -> None:
            self.reason = reason

    engine = FakeEngine()
    runs.register_active(context, engine)
    try:
        response = await server._dispatch({
            "id": "1", "method": "host.run.cancel",
            "params": {"profile": "default", "id": "remote-active"},
        })
    finally:
        runs.unregister_active(context)

    assert response["result"] == {"cancelled": True}
    assert engine.reason == "run-cancel-rpc"


@pytest.mark.asyncio
async def test_remote_admin_cannot_cancel_another_connections_run(
    tmp_path: Path, monkeypatch,
) -> None:
    context = _context(tmp_path, "other-active", "conn_other")
    runs.start(context)
    server = _server(tmp_path, monkeypatch)

    class FakeEngine:
        reason = ""

        def request_interrupt(self, reason: str) -> None:
            self.reason = reason

    engine = FakeEngine()
    runs.register_active(context, engine)
    try:
        with use(ConnectionContext("conn_admin", "dev_admin", "remote", role="admin")):
            response = await server._dispatch({
                "id": "1", "method": "host.run.cancel",
                "params": {"profile": "default", "id": "other-active"},
            })
    finally:
        runs.unregister_active(context)

    assert response["error"]["message"] == "not-found"
    assert engine.reason == ""
