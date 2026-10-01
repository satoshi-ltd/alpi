from __future__ import annotations

import base64
import json
from pathlib import Path

import pytest
import websockets

from alpi import attachments as att
from alpi.host import attachments_rpc, connections
from alpi.host import sessions as host_sessions
from alpi.session import Session, Turn
from tests.host.test_tcp_listener import _start_security_test_server, short_tmp  # noqa: F401

PNG = b"\x89PNG\r\n\x1a\nbytes-of-the-chart"


async def _call(url: str, token: str, method: str, **params) -> dict:
    async with websockets.connect(url) as ws:
        await ws.send(json.dumps({
            "id": "1", "method": method,
            "params": {"auth_token": token, "profile": "default", **params},
        }))
        return json.loads(await ws.recv())


def _fetch_ok(response: dict) -> bool:
    return "result" in response and response["result"].get("size", 0) > 0


def _forbidden(response: dict) -> bool:
    return response.get("error", {}).get("message") == "forbidden"


def _save(root: Path, conn: str, device: str, turn: Turn) -> str:
    session = Session(root, "model", connection_id=conn, device_id=device)
    session.turns.append(turn)
    session.save()
    return session.id


async def _world(short_tmp: Path, monkeypatch, scope: str):
    host_sessions._clear_row_cache()
    host_sessions._clear_payload_cache()
    connections.invalidate_cache()
    server, url = await _start_security_test_server(short_tmp, monkeypatch)
    attachments_rpc.register(server)
    row, device_a = connections.create_connection("Web", role="member", session_scope=scope)
    _row, device_b = connections.add_device(row["id"])
    device_a, device_b = {**device_a, "connection": row["id"]}, {**device_b, "connection": row["id"]}
    root = short_tmp
    out = root / "out"
    out.mkdir(exist_ok=True)
    report = out / "report.md"
    report.write_text("# quarterly report")
    shared = out / "shared.md"
    shared.write_text("# shared by everyone on the connection")
    chart = root / "chart.png"
    chart.write_bytes(PNG)
    _save(root, row["id"], device_a["id"], Turn(
        1, "make the report", [], "done",
        output_attachments=[{"path": str(report), "name": "report.md", "mime": "text/markdown"}],
    ))
    _save(root, row["id"], device_a["id"], Turn(
        1, "plot it", [], f"Here is the chart: ![chart]({chart})",
    ))
    _save(root, row["id"], "", Turn(
        1, "the old shared one", [], "ok",
        output_attachments=[{"path": str(shared), "name": "shared.md", "mime": "text/markdown"}],
    ))
    staged = await _call(
        url, device_a["token"], "host.attachments.stage",
        name="upload.png", mime="image/png", data_base64=base64.b64encode(PNG).decode(),
    )
    return server, url, device_a, device_b, str(report), str(shared), str(chart), staged["result"]["attachment"]["path"]


@pytest.mark.asyncio
async def test_a_produced_file_is_served_only_to_the_device_that_owns_the_session(short_tmp, monkeypatch) -> None:
    server, url, a, b, report, *_ = await _world(short_tmp, monkeypatch, "device")
    try:
        assert _fetch_ok(await _call(url, a["token"], "host.attachments.fetch", path=report))
        assert _forbidden(await _call(url, b["token"], "host.attachments.fetch", path=report))
    finally:
        await server.stop()


@pytest.mark.asyncio
async def test_an_image_an_assistant_turn_referenced_stays_fetchable_for_that_device_only(short_tmp, monkeypatch) -> None:
    server, url, a, b, _report, _shared, chart, _staged = await _world(short_tmp, monkeypatch, "device")
    try:
        assert _fetch_ok(await _call(url, a["token"], "host.attachments.fetch", path=chart))
        assert _forbidden(await _call(url, b["token"], "host.attachments.fetch", path=chart))
    finally:
        await server.stop()


@pytest.mark.asyncio
async def test_a_staged_upload_belongs_to_the_device_that_staged_it(short_tmp, monkeypatch) -> None:
    server, url, a, b, *_rest, staged = await _world(short_tmp, monkeypatch, "device")
    try:
        assert _fetch_ok(await _call(url, a["token"], "host.attachments.fetch", path=staged))
        assert _forbidden(await _call(url, b["token"], "host.attachments.fetch", path=staged))
    finally:
        await server.stop()


@pytest.mark.asyncio
async def test_a_session_without_a_device_is_fetchable_by_the_whole_connection(short_tmp, monkeypatch) -> None:
    server, url, a, b, _report, shared, *_ = await _world(short_tmp, monkeypatch, "device")
    try:
        assert _fetch_ok(await _call(url, a["token"], "host.attachments.fetch", path=shared))
        assert _fetch_ok(await _call(url, b["token"], "host.attachments.fetch", path=shared))
    finally:
        await server.stop()


@pytest.mark.asyncio
async def test_under_connection_scope_every_device_fetches_the_same_files(short_tmp, monkeypatch) -> None:
    server, url, a, b, report, _shared, chart, staged = await _world(short_tmp, monkeypatch, "connection")
    try:
        for path in (report, chart, staged):
            assert _fetch_ok(await _call(url, a["token"], "host.attachments.fetch", path=path))
            assert _fetch_ok(await _call(url, b["token"], "host.attachments.fetch", path=path))
    finally:
        await server.stop()


@pytest.mark.asyncio
async def test_an_admin_and_the_local_socket_are_not_narrowed(short_tmp, monkeypatch) -> None:
    server, url, _a, _b, report, *_ = await _world(short_tmp, monkeypatch, "device")
    try:
        _row, admin = connections.create_connection("Ops", role="admin", session_scope="device")
        assert _fetch_ok(await _call(url, admin["token"], "host.attachments.fetch", path=report))
        local = await server._dispatch({
            "id": "1", "method": "host.attachments.fetch", "params": {"profile": "default", "path": report},
        })
        assert _fetch_ok(local)
    finally:
        await server.stop()


@pytest.mark.asyncio
async def test_a_path_a_user_typed_does_not_make_it_fetchable(short_tmp, monkeypatch) -> None:
    server, url, a, b, report, *_ = await _world(short_tmp, monkeypatch, "device")
    try:
        _save(short_tmp, b["connection"], b["id"], Turn(1, f"please open {report}", [], "I cannot do that"))
        assert _forbidden(await _call(url, b["token"], "host.attachments.fetch", path=report))
    finally:
        await server.stop()


@pytest.mark.asyncio
async def test_a_file_in_a_session_saved_after_the_first_fetch_becomes_fetchable(short_tmp, monkeypatch) -> None:
    server, url, a, b, *_ = await _world(short_tmp, monkeypatch, "device")
    try:
        late = short_tmp / "out" / "late.md"
        late.write_text("# late")
        assert _forbidden(await _call(url, b["token"], "host.attachments.fetch", path=str(late)))
        _save(short_tmp, b["connection"], b["id"],
              Turn(1, "late", [], "ok", output_attachments=[{"path": str(late), "name": "late.md"}]))
        assert _fetch_ok(await _call(url, b["token"], "host.attachments.fetch", path=str(late)))
    finally:
        await server.stop()


@pytest.mark.asyncio
async def test_repeated_fetches_do_not_rescan_the_transcripts(short_tmp, monkeypatch) -> None:
    from alpi.host import offered_paths

    server, url, a, _b, report, *_ = await _world(short_tmp, monkeypatch, "device")
    reads: list[str] = []
    real_read = host_sessions.read_session
    monkeypatch.setattr(
        offered_paths.host_sessions, "read_session",
        lambda home, sid: reads.append(sid) or real_read(home, sid),
    )
    offered_paths._clear()
    try:
        assert _fetch_ok(await _call(url, a["token"], "host.attachments.fetch", path=report))
        first = len(reads)
        assert _fetch_ok(await _call(url, a["token"], "host.attachments.fetch", path=report))
        assert first > 0
        assert len(reads) == first
    finally:
        await server.stop()


@pytest.mark.asyncio
async def test_an_agent_that_repeats_a_path_the_user_typed_does_not_make_it_fetchable(short_tmp, monkeypatch) -> None:
    server, url, _a, b, report, *_ = await _world(short_tmp, monkeypatch, "device")
    try:
        session = Session(short_tmp, "model", connection_id=b["connection"], device_id=b["id"])
        session.turns.append(Turn(
            1, f"read {report}", [], f"I could not read {report}.",
        ))
        session.save()
        assert _forbidden(await _call(url, b["token"], "host.attachments.fetch", path=report))
    finally:
        await server.stop()


@pytest.mark.asyncio
async def test_dot_dot_after_a_symlink_cannot_borrow_the_lexical_path_of_an_offered_file(short_tmp, monkeypatch) -> None:
    server, url, _a, b, report, *_ = await _world(short_tmp, monkeypatch, "device")
    try:
        (short_tmp / "out" / "sub").mkdir()
        (short_tmp / "link").symlink_to(short_tmp / "out" / "sub")
        decoy = short_tmp / "report.md"
        _save(short_tmp, b["connection"], b["id"], Turn(
            1, "decoy", [], "ok", output_attachments=[{"path": str(decoy), "name": "report.md"}],
        ))
        sneaky = f"{short_tmp}/link/../report.md"

        assert _forbidden(await _call(url, b["token"], "host.attachments.fetch", path=sneaky))
    finally:
        await server.stop()


@pytest.mark.asyncio
async def test_a_failed_marker_write_leaves_no_upload_behind(short_tmp, monkeypatch) -> None:
    server, url, a, *_ = await _world(short_tmp, monkeypatch, "device")
    try:
        monkeypatch.setattr(attachments_rpc, "_record_owner", lambda directory: (_ for _ in ()).throw(OSError("disk full")))
        before = {p.name for p in (short_tmp / "host" / "attachments" / "tmp").glob("*")}

        response = await _call(
            url, a["token"], "host.attachments.stage",
            name="late.png", mime="image/png", data_base64=base64.b64encode(PNG).decode(),
        )

        assert "error" in response
        assert {p.name for p in (short_tmp / "host" / "attachments" / "tmp").glob("*")} == before
    finally:
        await server.stop()
