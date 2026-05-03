"""Matrix adapter — sync / send / allowlist with mocked nio client."""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from alpi.gateway.platforms.matrix import Matrix


def _set_matrix_env(monkeypatch: pytest.MonkeyPatch, **extra: str) -> None:
    monkeypatch.setenv("MATRIX_HOMESERVER_URL", "http://test.local:8008")
    monkeypatch.setenv("MATRIX_USER_ID", "@alpi-bot:test.local")
    monkeypatch.setenv("MATRIX_ACCESS_TOKEN", "syt_token")
    monkeypatch.setenv("MATRIX_ALLOWED_ROOMS", "!room1:test.local")
    for k, v in extra.items():
        monkeypatch.setenv(k, v)


class _FakeTextEvent:
    """Test double for ``nio.RoomMessageText``. Patched in via
    ``patch('nio.RoomMessageText', _FakeTextEvent)`` so the
    ``isinstance`` check in ``Matrix.listen`` accepts it."""
    def __init__(self, sender: str, body: str, event_id: str = "$evt"):
        self.sender = sender
        self.body = body
        self.event_id = event_id


def _fake_text_event(sender: str, body: str, event_id: str = "$evt") -> _FakeTextEvent:
    return _FakeTextEvent(sender, body, event_id)


def _install_fake_nio(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(
        sys.modules,
        "nio",
        SimpleNamespace(RoomMessageText=_FakeTextEvent),
    )


class _FakeRoom:
    def __init__(self, events):
        self.timeline = SimpleNamespace(events=events)


class _FakeSyncResponse:
    def __init__(self, next_batch: str, joined: dict):
        self.next_batch = next_batch
        self.rooms = SimpleNamespace(join=joined)


def test_cursor_persisted_across_runs(tmp_home_no_env: Path) -> None:
    home = tmp_home_no_env
    state = home / "gateway" / "matrix-state.json"
    state.parent.mkdir(parents=True)
    state.write_text(json.dumps({"next_batch": "s100"}))

    m = Matrix(home)
    assert m._next_batch == "s100"

    m._save_cursor("s200")
    reloaded = json.loads(state.read_text())
    assert reloaded["next_batch"] == "s200"


def test_listen_idle_when_credentials_missing(
    tmp_home_no_env: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("MATRIX_HOMESERVER_URL", raising=False)
    monkeypatch.delenv("MATRIX_USER_ID", raising=False)
    monkeypatch.delenv("MATRIX_ACCESS_TOKEN", raising=False)

    m = Matrix(tmp_home_no_env)

    async def run():
        agen = m.listen()
        # First await should hit the idle sleep, not a sync call.
        with patch("asyncio.sleep", new=AsyncMock(side_effect=asyncio.CancelledError)):
            with pytest.raises(asyncio.CancelledError):
                await agen.__anext__()

    asyncio.run(run())


def test_filter_room_allowlist(
    tmp_home_no_env: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Messages from non-allowlisted rooms must NOT yield."""
    _set_matrix_env(monkeypatch)
    _install_fake_nio(monkeypatch)

    m = Matrix(tmp_home_no_env)
    m._next_batch = "s1"

    
    allowed_event = _fake_text_event("@user:test.local", "in allowed", "$1")
    blocked_event = _fake_text_event("@user:test.local", "in blocked", "$2")
    
    

    sync_responses = [
        _FakeSyncResponse(
            next_batch="s2",
            joined={
                "!room1:test.local": _FakeRoom([allowed_event]),
                "!nope:test.local": _FakeRoom([blocked_event]),
            },
        ),
        _FakeSyncResponse("s3", {}),
    ]

    fake_client = MagicMock()
    fake_client.user_id = "@alpi-bot:test.local"
    fake_client.sync = AsyncMock(side_effect=sync_responses)

    async def run():
        with patch.object(Matrix, "_build_client", return_value=fake_client), \
             patch("nio.RoomMessageText", _FakeTextEvent):
            agen = m.listen()
            try:
                msg = await asyncio.wait_for(agen.__anext__(), timeout=2)
            except asyncio.CancelledError:
                msg = None
            return msg

    msg = asyncio.run(run())
    assert msg is not None, "no message yielded — allowed room was filtered out"
    assert msg.text == "in allowed"
    assert msg.external_chat_id == "!room1:test.local"


def test_filter_sender_allowlist(
    tmp_home_no_env: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_matrix_env(monkeypatch, MATRIX_ALLOWED_SENDERS="@me:test.local")
    _install_fake_nio(monkeypatch)

    m = Matrix(tmp_home_no_env)
    m._next_batch = "s1"

    
    me_ev = _fake_text_event("@me:test.local", "from me", "$1")
    other_ev = _fake_text_event("@stranger:test.local", "from stranger", "$2")
    
    

    fake_client = MagicMock()
    fake_client.user_id = "@alpi-bot:test.local"
    fake_client.sync = AsyncMock(side_effect=[
        _FakeSyncResponse("s2", {"!room1:test.local": _FakeRoom([me_ev, other_ev])}),
        _FakeSyncResponse("s3", {}),
    ])

    async def run():
        msgs = []
        with patch.object(Matrix, "_build_client", return_value=fake_client), \
             patch("nio.RoomMessageText", _FakeTextEvent):
            agen = m.listen()
            try:
                msgs.append(await asyncio.wait_for(agen.__anext__(), timeout=2))
                msgs.append(await asyncio.wait_for(agen.__anext__(), timeout=0.5))
            except (asyncio.TimeoutError, asyncio.CancelledError, StopAsyncIteration):
                pass
        return msgs

    msgs = asyncio.run(run())
    assert len(msgs) == 1, f"expected 1 yielded msg, got {len(msgs)}"
    assert msgs[0].external_user_id == "@me:test.local"


def test_does_not_echo_own_messages(
    tmp_home_no_env: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The bot must not feed its own replies back into the engine."""
    _set_matrix_env(monkeypatch)
    _install_fake_nio(monkeypatch)

    m = Matrix(tmp_home_no_env)
    m._next_batch = "s1"

    
    own_ev = _fake_text_event("@alpi-bot:test.local", "my own reply", "$1")
    

    fake_client = MagicMock()
    fake_client.user_id = "@alpi-bot:test.local"
    fake_client.sync = AsyncMock(side_effect=[
        _FakeSyncResponse("s2", {"!room1:test.local": _FakeRoom([own_ev])}),
        _FakeSyncResponse("s3", {}),
    ])

    async def run():
        with patch.object(Matrix, "_build_client", return_value=fake_client), \
             patch("nio.RoomMessageText", _FakeTextEvent):
            agen = m.listen()
            try:
                return await asyncio.wait_for(agen.__anext__(), timeout=0.5)
            except (asyncio.TimeoutError, asyncio.CancelledError, StopAsyncIteration):
                return None

    msg = asyncio.run(run())
    assert msg is None, f"bot echoed its own message: {msg}"


def test_first_sync_skips_backlog(
    tmp_home_no_env: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A fresh Matrix() with no cursor must NOT replay history on first sync."""
    _set_matrix_env(monkeypatch)
    _install_fake_nio(monkeypatch)

    m = Matrix(tmp_home_no_env)
    assert m._next_batch is None

    
    backlog_ev = _fake_text_event("@user:test.local", "from backlog", "$1")
    

    fake_client = MagicMock()
    fake_client.user_id = "@alpi-bot:test.local"
    fake_client.sync = AsyncMock(side_effect=[
        _FakeSyncResponse("s2", {"!room1:test.local": _FakeRoom([backlog_ev])}),
        _FakeSyncResponse("s3", {}),
    ])

    async def run():
        with patch.object(Matrix, "_build_client", return_value=fake_client), \
             patch("nio.RoomMessageText", _FakeTextEvent):
            agen = m.listen()
            try:
                return await asyncio.wait_for(agen.__anext__(), timeout=0.5)
            except (asyncio.TimeoutError, asyncio.CancelledError, StopAsyncIteration):
                return None

    msg = asyncio.run(run())
    assert msg is None, "first sync replayed backlog instead of skipping it"
    # Cursor advanced past the initial None — backlog sync token was saved.
    assert m._next_batch is not None
    assert m._next_batch in {"s2", "s3"}


def test_send_calls_room_send(
    tmp_home_no_env: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    from alpi.gateway.base import OutgoingMessage

    _set_matrix_env(monkeypatch)
    m = Matrix(tmp_home_no_env)

    fake_client = MagicMock()
    fake_client.room_send = AsyncMock()

    async def run():
        with patch.object(Matrix, "_build_client", return_value=fake_client):
            await m.send(OutgoingMessage(
                external_chat_id="!room1:test.local",
                text="hello world",
            ))

    asyncio.run(run())

    fake_client.room_send.assert_awaited_once()
    call = fake_client.room_send.await_args
    assert call.kwargs["room_id"] == "!room1:test.local"
    assert call.kwargs["message_type"] == "m.room.message"
    assert call.kwargs["content"] == {"msgtype": "m.text", "body": "hello world"}
