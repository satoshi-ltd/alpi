from __future__ import annotations

from pathlib import Path

import pytest

from alpi.host import _chat_events, chat, handlers, runs as host_runs, sessions as host_sessions
from alpi.host.connection_context import ConnectionContext, owns_session_row, use
from alpi.host.server import HandlerError, Server
from alpi.session import Session, Turn


def _ctx(device_id: str, scope: str = "device", connection_id: str = "conn") -> ConnectionContext:
    return ConnectionContext(connection_id, device_id, "remote", "member", session_scope=scope)


def _save(root: Path, text: str, *, connection_id: str = "conn", device_id: str = "") -> str:
    session = Session(root, "model", connection_id=connection_id, device_id=device_id)
    session.turns.append(Turn(1, text, [], "reply"))
    session.save()
    return session.id


@pytest.fixture
def root(monkeypatch, tmp_path: Path) -> Path:
    from alpi import home
    monkeypatch.setattr(home, "_ROOT", tmp_path)
    host_sessions._clear_row_cache()
    host_sessions._clear_payload_cache()
    return tmp_path


@pytest.fixture
def seeded(root: Path) -> dict[str, str]:
    return {
        "a": _save(root, "from a", device_id="dev_a"),
        "b": _save(root, "from b", device_id="dev_b"),
        "legacy": _save(root, "before the flag"),
        "other": _save(root, "other connection", connection_id="conn_other", device_id="dev_x"),
    }


@pytest.mark.asyncio
async def test_device_scope_lists_own_and_legacy_sessions_only(root: Path, seeded) -> None:
    with use(_ctx("dev_a")):
        result = await handlers._sessions_list({"profile": "default"}, Server(root))
    assert sorted(row["first_user"] for row in result["sessions"]) == ["before the flag", "from a"]
    assert {row["device_id"] for row in result["sessions"]} == {"dev_a", ""}


@pytest.mark.asyncio
async def test_connection_scope_keeps_every_device_session_visible(root: Path, seeded) -> None:
    with use(_ctx("dev_a", scope="connection")):
        result = await handlers._sessions_list({"profile": "default"}, Server(root))
    assert sorted(row["first_user"] for row in result["sessions"]) == [
        "before the flag", "from a", "from b",
    ]


@pytest.mark.asyncio
async def test_local_socket_sees_host_sessions_and_ignores_scope(root: Path, seeded) -> None:
    host_id = _save(root, "from the desk", connection_id="host")
    result = await handlers._sessions_list({"profile": "default"}, Server(root))
    assert [row["id"] for row in result["sessions"]] == [host_id]


@pytest.mark.asyncio
async def test_device_scope_reads_own_and_legacy_sessions(root: Path, seeded) -> None:
    with use(_ctx("dev_a")):
        for sid in (seeded["a"], seeded["legacy"]):
            read = await handlers._session_read({"profile": "default", "id": sid}, Server(root))
            assert read["session"]["id"] == sid


@pytest.mark.asyncio
async def test_device_scope_hides_a_sibling_session_from_read_and_delete(root: Path, seeded) -> None:
    server = Server(root)
    with use(_ctx("dev_a")):
        with pytest.raises(HandlerError) as error:
            await handlers._session_read({"profile": "default", "id": seeded["b"]}, server)
        assert error.value.message == "not-found"
        outcome = await handlers._sessions_delete(
            {"profile": "default", "ids": [seeded["b"], seeded["legacy"]]}, server,
        )
    assert outcome == {
        "deleted": [seeded["legacy"]],
        "errors": [{"id": seeded["b"], "code": "not-found"}],
    }
    assert (root / "sessions" / f"{seeded['b']}.json").exists()


@pytest.mark.asyncio
async def test_device_scope_refuses_to_continue_a_sibling_session(root: Path, seeded, monkeypatch) -> None:
    monkeypatch.setattr(chat, "_resolve_home", lambda profile: root)
    frames: list[dict] = []

    async def send_frame(frame: dict) -> None:
        frames.append(frame)

    with use(_ctx("dev_a")):
        await chat._data_chat_send(
            {"profile": "default", "text": "hi", "request_id": "r1", "session_id": seeded["b"]},
            Server(root), send_frame,
        )
    assert frames == [{"event": "error", "text": f"session not found: {seeded['b']}"}]


@pytest.mark.asyncio
async def test_device_scope_partitions_the_replay_sidecar(root: Path) -> None:
    _chat_events.reset_for_turn(root, "pending", "req", "conn", "dev_a")
    assert _chat_events.owner(root, "pending") == ("conn", "dev_a")
    server = Server(root)
    params = {"profile": "default", "session_id": "pending"}
    with use(_ctx("dev_b")):
        with pytest.raises(HandlerError) as error:
            await chat._data_chat_events_since(params, server)
    assert error.value.message == "not-found"
    with use(_ctx("dev_a")):
        assert (await chat._data_chat_events_since(params, server))["exists"] is True
    with use(_ctx("dev_b", scope="connection")):
        assert (await chat._data_chat_events_since(params, server))["exists"] is True


@pytest.mark.asyncio
async def test_device_scope_blocks_cancelling_a_sibling_turn(root: Path, monkeypatch) -> None:
    class FakeEngine:
        reason = ""
        session = type("S", (), {"connection_id": "conn", "device_id": "dev_a"})()

        def request_interrupt(self, reason: str) -> None:
            self.reason = reason

    engine = FakeEngine()
    monkeypatch.setitem(chat._active, "req-a", engine)
    server = Server(root)
    with use(_ctx("dev_b")):
        assert await chat._data_chat_cancel({"request_id": "req-a"}, server) == {"cancelled": False}
    assert engine.reason == ""
    with use(_ctx("dev_b", scope="connection")):
        assert await chat._data_chat_cancel({"request_id": "req-a"}, server) == {"cancelled": True}
    assert engine.reason == "cancel-rpc"


def test_device_scope_applies_to_run_rows() -> None:
    owned = {"connection_id": "conn", "device_id": "dev_a"}
    legacy = {"connection_id": "conn", "device_id": None}
    with use(_ctx("dev_b")):
        assert host_runs._visible(owned) is False
        assert host_runs._visible(legacy) is True
    with use(_ctx("dev_a")):
        assert host_runs._visible(owned) is True
    with use(_ctx("dev_b", scope="connection")):
        assert host_runs._visible(owned) is True


def test_device_scope_applies_to_the_latest_chat_summary(root: Path, seeded) -> None:
    with use(_ctx("dev_b")):
        row = host_sessions.latest_chat_summary(root, can_read=owns_session_row)
    assert row is not None and row["id"] == seeded["legacy"]
    with use(_ctx("dev_b", scope="connection")):
        row = host_sessions.latest_chat_summary(root, can_read=owns_session_row)
    assert row is not None and row["id"] == seeded["legacy"]
    _save(root, "newest from b", device_id="dev_b")
    with use(_ctx("dev_a")):
        row = host_sessions.latest_chat_summary(root, can_read=owns_session_row)
    assert row is not None and row["id"] == seeded["legacy"]


def test_sessions_record_their_device_under_connection_scope_so_a_later_switch_hides_them(root: Path) -> None:
    from alpi.config import Config, ToolsConfig
    from alpi.engine import Engine
    from alpi.host.connection_context import owns_session
    home = root / "h"
    home.mkdir()
    with use(_ctx("dev_a", scope="connection")):
        engine = Engine(home=home, cfg=Config(home=home, model="m", tools=ToolsConfig(), raw={}))
    assert engine.session.device_id == "dev_a"
    with use(_ctx("dev_b", scope="connection")):
        assert owns_session("conn", engine.session.device_id)
    with use(_ctx("dev_b", scope="device")):
        assert not owns_session("conn", engine.session.device_id)
    with use(_ctx("dev_a", scope="device")):
        assert owns_session("conn", engine.session.device_id)

