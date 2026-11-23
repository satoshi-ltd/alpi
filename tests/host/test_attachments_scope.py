from __future__ import annotations

import asyncio
import base64
import json
import os
from pathlib import Path

import pytest
import websockets

from alpi.host import attachments_rpc, connections
from alpi.host import sessions as host_sessions
from alpi.session import Session, Turn
from tests.host.test_tcp_listener import _start_security_test_server
from tests.host.test_tcp_listener import short_tmp as short_tmp

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
@pytest.mark.parametrize("broken", ["{", "[]", "{}", "null", '{"connection_id": [], "device_id": ""}', "unreadable"])
async def test_an_invalid_existing_owner_marker_never_grants_access(short_tmp, monkeypatch, broken) -> None:
    server, url, a, b, *_rest, staged = await _world(short_tmp, monkeypatch, "device")
    marker = (Path(staged).parent / ".owner").resolve()
    original = marker.read_text()
    try:
        if broken == "unreadable":
            read = Path.read_text

            def fail_marker(path, *args, **kwargs):
                if path.resolve() == marker:
                    raise PermissionError("cannot read owner")
                return read(path, *args, **kwargs)

            with monkeypatch.context() as patch:
                patch.setattr(Path, "read_text", fail_marker)
                assert _forbidden(await _call(url, b["token"], "host.attachments.fetch", path=staged))
        else:
            marker.write_text(broken)
            assert _forbidden(await _call(url, b["token"], "host.attachments.fetch", path=staged))
            marker.write_text(original)
        assert _fetch_ok(await _call(url, a["token"], "host.attachments.fetch", path=staged))
        assert _forbidden(await _call(url, b["token"], "host.attachments.fetch", path=staged))
    finally:
        await server.stop()


@pytest.mark.asyncio
@pytest.mark.parametrize("scope", ["device", "connection"])
async def test_an_upload_with_no_marker_is_served_to_no_remote_member(short_tmp, monkeypatch, scope) -> None:
    server, url, a, b, *_rest, staged = await _world(short_tmp, monkeypatch, scope)
    try:
        (Path(staged).parent / ".owner").unlink()
        assert _forbidden(await _call(url, a["token"], "host.attachments.fetch", path=staged))
        assert _forbidden(await _call(url, b["token"], "host.attachments.fetch", path=staged))
        local = await server._dispatch({
            "id": "1", "method": "host.attachments.fetch", "params": {"profile": "default", "path": staged},
        })
        assert _fetch_ok(local)
    finally:
        await server.stop()


@pytest.mark.asyncio
@pytest.mark.parametrize("scope", ["device", "connection"])
async def test_another_connection_fetches_nothing_the_first_one_produced_or_staged(short_tmp, monkeypatch, scope) -> None:
    server, url, a, _b, report, shared, chart, staged = await _world(short_tmp, monkeypatch, scope)
    try:
        _row, outsider = connections.create_connection("Other", role="member", session_scope=scope)
        for path in (report, shared, chart, staged):
            assert _fetch_ok(await _call(url, a["token"], "host.attachments.fetch", path=path))
            assert _forbidden(await _call(url, outsider["token"], "host.attachments.fetch", path=path))
    finally:
        await server.stop()


@pytest.mark.asyncio
async def test_a_connection_fetches_what_its_own_sessions_offered_even_beside_another_connection(short_tmp, monkeypatch) -> None:
    server, url, _a, _b, report, *_ = await _world(short_tmp, monkeypatch, "connection")
    try:
        row, outsider = connections.create_connection("Other", role="member", session_scope="connection")
        _save(short_tmp, row["id"], outsider["id"], Turn(
            1, "mine", [], "ok", output_attachments=[{"path": report, "name": "report.md"}],
        ))
        assert _fetch_ok(await _call(url, outsider["token"], "host.attachments.fetch", path=report))
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


@pytest.mark.asyncio
async def test_a_link_named_like_an_image_never_serves_what_it_points_at(short_tmp, monkeypatch) -> None:
    server, url, a, *_ = await _world(short_tmp, monkeypatch, "device")
    try:
        other, _device = connections.create_connection("Other", role="member", session_scope="device")
        their_session = _save(short_tmp, other["id"], _device["id"], Turn(1, "private", [], "secret plans"))
        their_chart = short_tmp / "out" / "theirs.png"
        their_chart.write_bytes(PNG)
        (short_tmp / "config.yaml").write_text("model: x\n")
        (short_tmp / "memories").mkdir(exist_ok=True)
        (short_tmp / "memories" / "USER.md").write_text("private facts")
        targets = {
            "session.png": next((short_tmp / "sessions").rglob(f"*{their_session}*")),
            "config.png": short_tmp / "config.yaml",
            "user.png": short_tmp / "memories" / "USER.md",
            "chart.png": their_chart,
        }
        links = []
        for name, target in targets.items():
            link = short_tmp / f"link-{name}"
            link.symlink_to(target)
            links.append(str(link))
        mine = short_tmp / "mine.png"
        mine.write_bytes(PNG)
        _save(short_tmp, a["connection"], a["id"], Turn(
            1, "list the workspace", [], "Files: " + " ".join([*links, str(mine)]),
        ))

        for link in links:
            assert _forbidden(await _call(url, a["token"], "host.attachments.fetch", path=link)), link
        assert _fetch_ok(await _call(url, a["token"], "host.attachments.fetch", path=str(mine)))
    finally:
        await server.stop()


@pytest.mark.asyncio
async def test_the_mime_of_a_fetch_comes_from_the_file_actually_read(short_tmp, monkeypatch) -> None:
    server, url, *_ = await _world(short_tmp, monkeypatch, "device")
    try:
        report = short_tmp / "out" / "report.md"
        link = short_tmp / "out" / "report.png"
        link.symlink_to(report)
        local = await server._dispatch({
            "id": "1", "method": "host.attachments.fetch", "params": {"profile": "default", "path": str(link)},
        })
        assert local["result"]["mime"] == "text/markdown"
    finally:
        await server.stop()


@pytest.mark.asyncio
@pytest.mark.parametrize("swap", ["link", "rename", "fifo"])
async def test_a_file_swapped_after_the_checks_is_not_read(short_tmp, monkeypatch, swap) -> None:
    server, url, a, *_ = await _world(short_tmp, monkeypatch, "device")
    try:
        (short_tmp / "memories").mkdir(exist_ok=True)
        secret = short_tmp / "memories" / "USER.md"
        secret.write_text("private facts")
        mine = short_tmp / "mine.png"
        mine.write_bytes(PNG)
        _save(short_tmp, a["connection"], a["id"], Turn(1, "show it", [], f"Here: {mine}"))
        # Exists before the swap: a file created after `mine` is unlinked can be handed the same inode number on Linux.
        other = short_tmp / "other.md"
        other.write_text("private facts")
        real_check = attachments_rpc._caller_may_fetch

        def swap_after_check(home, requested, real):
            allowed = real_check(home, requested, real)
            if swap == "rename":
                other.rename(mine)
                return allowed
            mine.unlink()
            if swap == "link":
                mine.symlink_to(secret)
            else:
                os.mkfifo(mine)
            return allowed

        monkeypatch.setattr(attachments_rpc, "_caller_may_fetch", swap_after_check)
        response = await asyncio.wait_for(_call(url, a["token"], "host.attachments.fetch", path=str(mine)), 10)
        assert _forbidden(response)
        assert b"private facts" not in json.dumps(response).encode()
    finally:
        await server.stop()


@pytest.mark.asyncio
async def test_a_member_reaches_a_workspace_by_its_configured_link_but_not_by_another_alias(short_tmp, monkeypatch) -> None:
    server, url, a, *_ = await _world(short_tmp, monkeypatch, "device")
    try:
        real_ws = short_tmp / "real-ws"
        real_ws.mkdir()
        (short_tmp / "ws").symlink_to(real_ws)
        (short_tmp / "alias").symlink_to(real_ws)
        (short_tmp / "config.yaml").write_text(f"workspace: {short_tmp / 'ws'}\n")
        (real_ws / "notes.md").write_text("# notes")
        configured = str(short_tmp / "ws" / "notes.md")
        aliased = str(short_tmp / "alias" / "notes.md")
        _save(short_tmp, a["connection"], a["id"], Turn(1, "notes", [], f"See {configured} and {aliased}"))

        assert _fetch_ok(await _call(url, a["token"], "host.attachments.fetch", path=configured))
        assert _forbidden(await _call(url, a["token"], "host.attachments.fetch", path=aliased))
    finally:
        await server.stop()
