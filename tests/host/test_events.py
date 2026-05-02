"""Tests for ``host.events.subscribe``."""

from __future__ import annotations

import asyncio
import json
import shutil
import tempfile
from pathlib import Path

import pytest

from alpi.host import server as host_server
from alpi.alp.keys import load_or_generate
from alpi.host import events as data_events


@pytest.fixture
def short_tmp() -> Path:
    d = Path(tempfile.mkdtemp(prefix="alp-events-", dir="/tmp"))
    try:
        yield d
    finally:
        shutil.rmtree(d, ignore_errors=True)


def test_emit_with_no_subscribers_is_noop(short_tmp: Path) -> None:
    data_events.emit("session_changed", {"id": "x"})


@pytest.mark.asyncio
async def test_subscribe_receives_emitted_events(short_tmp: Path) -> None:
    home = short_tmp / "h"
    home.mkdir()
    load_or_generate(home)

    srv = host_server.Server(home=home)
    data_events.register(srv)
    await srv.start()

    try:
        reader, writer = await asyncio.open_unix_connection(str(srv.socket_path()))
        writer.write(
            (json.dumps({"id": "r", "method": "host.events.subscribe"}) + "\n").encode()
        )
        await writer.drain()

        first = json.loads(await reader.readline())
        assert first["event"] == "subscribed"

        data_events.emit("session_changed", {"id": "abc"})

        second = json.loads(await asyncio.wait_for(reader.readline(), timeout=2.0))
        assert second["event"] == "session_changed"
        assert second["data"] == {"id": "abc"}

        writer.close()
        await writer.wait_closed()
    finally:
        await srv.stop()


@pytest.mark.asyncio
async def test_subscribe_filters_by_kinds(short_tmp: Path) -> None:
    home = short_tmp / "h"
    home.mkdir()
    load_or_generate(home)

    srv = host_server.Server(home=home)
    data_events.register(srv)
    await srv.start()

    try:
        reader, writer = await asyncio.open_unix_connection(str(srv.socket_path()))
        writer.write((json.dumps({
            "id": "r",
            "method": "host.events.subscribe",
            "params": {"kinds": ["workgroup_message"]},
        }) + "\n").encode())
        await writer.drain()

        first = json.loads(await reader.readline())
        assert first["event"] == "subscribed"

        data_events.emit("session_changed", {"id": "ignored"})
        data_events.emit("workgroup_message", {"id": "kept"})

        line = await asyncio.wait_for(reader.readline(), timeout=2.0)
        frame = json.loads(line)
        assert frame["event"] == "workgroup_message"
        assert frame["data"]["id"] == "kept"

        writer.close()
        await writer.wait_closed()
    finally:
        await srv.stop()
