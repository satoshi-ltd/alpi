from __future__ import annotations

import asyncio
import json
import shutil
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
import websockets

from alpi import outputs, run_ledger
from alpi.alp import workgroup, workgroup_files
from alpi.host import admin_audit
from alpi.host import server as host_server

BAD = "tool output \ud800 and \udfff end"
GOOD = "tool output � and � end"


@pytest.fixture
def short_tmp() -> Path:
    d = Path(tempfile.mkdtemp(prefix="alp-surr-", dir="/tmp"))
    try:
        yield d
    finally:
        shutil.rmtree(d, ignore_errors=True)


async def _handler(_params, _server):
    return {"text": BAD, BAD: 1}


@pytest.mark.asyncio
async def test_a_lone_surrogate_in_a_reply_reaches_a_unix_client_as_a_replacement_character(short_tmp: Path) -> None:
    srv = host_server.Server(home=short_tmp)
    srv.register("host.echo", _handler)
    await srv.start()
    try:
        reader, writer = await asyncio.open_unix_connection(str(srv.socket_path()))
        writer.write((json.dumps({"id": "1", "method": "host.echo", "params": {}}) + "\n").encode())
        await writer.drain()
        frame = json.loads(await asyncio.wait_for(reader.readline(), 5))
        writer.close()
        await writer.wait_closed()
    finally:
        await srv.stop()
    assert frame["result"] == {"text": GOOD, GOOD: 1}


@pytest.mark.asyncio
async def test_a_lone_surrogate_in_a_reply_reaches_a_websocket_client_as_a_replacement_character(
    short_tmp: Path, monkeypatch,
) -> None:
    from alpi import home as home_mod
    from alpi.host import devices as devices_mod
    monkeypatch.setattr(home_mod, "_ROOT", short_tmp)
    row = devices_mod.add(label="test", role="member")
    with patch.object(
        host_server.Server, "_validate_tcp_bind", staticmethod(lambda b, allow_public_bind=False: b),
    ):
        srv = host_server.Server(home=short_tmp / "h", tcp_bind=("127.0.0.1", 0))
        srv.register("host.echo", _handler)
        await srv.start()
        try:
            port = srv._ws_server.sockets[0].getsockname()[1]
            async with websockets.connect(f"ws://127.0.0.1:{port}") as ws:
                await ws.send(json.dumps({"id": "1", "method": "host.echo", "params": {"auth_token": row["token"]}}))
                frame = json.loads(await asyncio.wait_for(ws.recv(), 5))
        finally:
            await srv.stop()
    assert frame["result"] == {"text": GOOD, GOOD: 1}


def test_an_output_row_with_a_lone_surrogate_is_stored(tmp_path: Path) -> None:
    row = outputs.append(tmp_path, profile="p", body=BAD, title=BAD, summary=BAD)
    stored = outputs.read(tmp_path, row["id"])
    assert stored is not None and stored["body"] == GOOD and stored["title"] == GOOD


def test_a_run_ledger_row_with_a_lone_surrogate_is_stored(tmp_path: Path) -> None:
    run_ledger.record(tmp_path, kind="agent", outcome="error", elapsed_s=1.0, output_tail=BAD)
    rows = run_ledger.read(tmp_path)
    assert len(rows) == 1 and "\ud800" not in json.dumps(rows[0], ensure_ascii=False)


def test_an_audit_event_with_a_lone_surrogate_is_written(tmp_path: Path) -> None:
    assert admin_audit._safe_text(BAD) == GOOD
    assert admin_audit._append(tmp_path, {"event": "x", "label": BAD})
    line = admin_audit.audit_path(tmp_path).read_text(encoding="utf-8").strip()
    assert json.loads(line)["label"] == GOOD


def test_a_workgroup_transcript_entry_with_a_lone_surrogate_is_written(tmp_path: Path) -> None:
    workgroup._append_transcript(tmp_path, {"text": BAD})
    line = (tmp_path / workgroup._TRANSCRIPT).read_text(encoding="utf-8").strip()
    assert json.loads(line)["text"] == GOOD


def test_a_workgroup_file_record_with_a_lone_surrogate_is_written(tmp_path: Path) -> None:
    target = tmp_path / "meta.json"
    workgroup_files._atomic_json(target, {"name": BAD})
    assert json.loads(target.read_text(encoding="utf-8"))["name"] == GOOD
