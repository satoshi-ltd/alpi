from __future__ import annotations

import asyncio
import itertools
import json
import tempfile
import time
from pathlib import Path

import pytest

from alpi.tui import activity, host_client
from alpi.tui.activity import ActivityPanel
from alpi.tui.app import AlpiApp
from alpi.tui.screens import ApprovalPanel, ClarificationPanel


def _activity() -> dict:
    return {
        "needs_you": [
            {"kind": "approval", "request_id": "ap1", "profile": "casa", "title": "rm -rf build",
             "severity": "caution", "ts": time.time(), "timeout_s": 60, "session_id": None},
            {"kind": "clarification", "request_id": "cl1", "profile": "casa", "title": "Which env?",
             "ts": time.time(), "timeout_s": 300, "session_id": "s1"},
        ],
        "running": [
            {"kind": "turn", "profile": "casa", "session_id": "s1", "title": "Deploy notes",
             "started_at": time.time() - 90, "source": "schedule"},
            {"kind": "workgroup", "profile": "hub", "workgroup_id": "wg1", "name": "web", "pipeline": "p",
             "phase": "build", "phases_done": 2, "phases_total": 5},
        ],
        "scheduled": [
            {"profile": "casa", "job_id": "j1", "title": "Morning brief", "next_fire": "2026-10-01T07:00:00+00:00",
             "last_run_at": None, "last_run_status": "error"},
        ],
    }


class _FakeReader:
    def __init__(self, lines: list[bytes]) -> None:
        self._lines = list(lines)

    async def readline(self) -> bytes:
        return self._lines.pop(0) if self._lines else b""


class _FakeWriter:
    def __init__(self) -> None:
        self.sent: list[dict] = []

    def write(self, data: bytes) -> None:
        self.sent.append(json.loads(data.decode()))

    async def drain(self) -> None:
        pass

    def close(self) -> None:
        pass

    async def wait_closed(self) -> None:
        pass


def _fake_socket(monkeypatch, tmp_path: Path, reply) -> _FakeWriter:
    sock = tmp_path / "host.sock"
    sock.touch()
    monkeypatch.setattr(host_client, "socket_path", lambda: sock)
    monkeypatch.setattr(host_client, "_ids", itertools.count(1))
    writer = _FakeWriter()

    async def fake_open(path):
        return _FakeReader([b"not json\n", json.dumps({"id": "other"}).encode() + b"\n",
                            json.dumps({"id": "tui-1", **reply}).encode() + b"\n"]), writer

    monkeypatch.setattr(host_client, "_open", fake_open)
    return writer


@pytest.mark.asyncio
async def test_acall_returns_the_matching_result(monkeypatch, tmp_path) -> None:
    payload = {"needs_you": [], "running": [], "scheduled": []}
    writer = _fake_socket(monkeypatch, tmp_path, {"result": payload})
    result = await host_client.acall("host.activity.list")
    assert result == payload
    assert writer.sent == [{"id": "tui-1", "method": "host.activity.list", "params": {}}]


@pytest.mark.asyncio
async def test_acall_maps_missing_verbs(monkeypatch, tmp_path) -> None:
    _fake_socket(monkeypatch, tmp_path, {"error": {"code": -32601, "message": "method-not-found"}})
    with pytest.raises(host_client.HostError) as exc:
        await host_client.acall("host.activity.list")
    assert exc.value.missing_verb


@pytest.mark.asyncio
async def test_acall_without_a_socket_is_unavailable(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(host_client, "socket_path", lambda: tmp_path / "missing.sock")
    with pytest.raises(host_client.HostUnavailable):
        await host_client.acall("host.activity.list")


def test_row_formatting() -> None:
    title, meta = activity.needs_row(_activity()["needs_you"][0])
    assert title == "rm -rf build"
    assert meta.startswith("approval · casa · caution · expires in")
    assert activity.running_line(_activity()["running"][0]).startswith("casa · Deploy notes · schedule · 1m")
    assert activity.running_line(_activity()["running"][1]) == "hub · workgroup web · build (2/5)"
    assert activity.scheduled_line(_activity()["scheduled"][0]).endswith("· last run failed")


async def _open_activity(app: AlpiApp, pilot) -> ActivityPanel:
    app._handle_slash("/activity")
    for _ in range(50):
        await pilot.pause(0.02)
        panels = list(app.query(ActivityPanel))
        if panels and (panels[0].message and panels[0].message != "loading…"):
            return panels[0]
    raise AssertionError("activity panel did not load")


@pytest.mark.asyncio
async def test_activity_says_when_the_daemon_is_not_running(tui_home) -> None:
    app = AlpiApp(home_dir=tui_home)
    async with app.run_test(size=(120, 50)) as pilot:
        panel = await _open_activity(app, pilot)
        assert panel.message == activity.NOT_RUNNING


@pytest.mark.asyncio
async def test_activity_hides_behind_an_old_daemon(tui_home, monkeypatch) -> None:
    async def old(method, params=None, *, timeout=5.0):
        raise host_client.HostError(-32601, "method-not-found")

    monkeypatch.setattr(host_client, "acall", old)
    app = AlpiApp(home_dir=tui_home)
    async with app.run_test(size=(120, 50)) as pilot:
        panel = await _open_activity(app, pilot)
        assert panel.message == activity.TOO_OLD


def _fake_daemon(monkeypatch) -> list[tuple[str, dict]]:
    calls: list[tuple[str, dict]] = []

    async def fake(method, params=None, *, timeout=5.0):
        calls.append((method, dict(params or {})))
        if method == "host.activity.list":
            return _activity()
        if method == "host.clarification.pending":
            return {"requests": [{"request_id": "cl1", "question": "Which env?", "choices": [
                {"label": "staging"}, {"label": "prod"}], "allow_other": False, "multi": False}]}
        return {"ok": True}

    monkeypatch.setattr(host_client, "acall", fake)
    return calls


@pytest.mark.asyncio
async def test_activity_lists_sections_and_answers_an_approval(tui_home, monkeypatch) -> None:
    calls = _fake_daemon(monkeypatch)
    app = AlpiApp(home_dir=tui_home)
    async with app.run_test(size=(120, 50)) as pilot:
        panel = await _open_activity(app, pilot)
        assert panel.message == "2 need you · 2 running · 1 scheduled"
        rendered = " ".join(str(w.render()) for w in panel.query(".list-row"))
        assert "Deploy notes" in rendered and "build (2/5)" in rendered and "Morning brief" in rendered
        await pilot.press("enter")
        for _ in range(20):
            await pilot.pause(0.02)
            if app.query(ApprovalPanel):
                break
        approval = app.query_one(ApprovalPanel)
        assert not approval.blocking
        assert approval.hint_text().startswith("esc back · expires in")
        await pilot.press("enter")
        for _ in range(20):
            await pilot.pause(0.02)
            if ("host.approval.respond", {"request_id": "ap1", "choice": "once", "profile": "casa"}) in calls:
                break
        assert ("host.approval.respond", {"request_id": "ap1", "choice": "once", "profile": "casa"}) in calls


@pytest.mark.asyncio
async def test_activity_answers_a_clarification(tui_home, monkeypatch) -> None:
    calls = _fake_daemon(monkeypatch)
    app = AlpiApp(home_dir=tui_home)
    async with app.run_test(size=(120, 50)) as pilot:
        await _open_activity(app, pilot)
        await pilot.press("down", "enter")
        for _ in range(20):
            await pilot.pause(0.02)
            if app.query(ClarificationPanel):
                break
        await pilot.pause()
        await pilot.press("down", "enter")
        for _ in range(20):
            await pilot.pause(0.02)
            if any(m == "host.clarification.respond" for m, _ in calls):
                break
        assert ("host.clarification.respond", {"request_id": "cl1", "choice": "prod", "profile": "casa"}) in calls


@pytest.mark.asyncio
async def test_escape_on_a_remote_prompt_closes_without_answering(tui_home, monkeypatch) -> None:
    calls = _fake_daemon(monkeypatch)
    app = AlpiApp(home_dir=tui_home)
    async with app.run_test(size=(120, 50)) as pilot:
        await _open_activity(app, pilot)
        await pilot.press("enter")
        for _ in range(20):
            await pilot.pause(0.02)
            if app.query(ApprovalPanel):
                break
        await pilot.press("escape")
        await pilot.pause()
        assert not app.query(ApprovalPanel)
        assert not any(m == "host.approval.respond" for m, _ in calls)


@pytest.mark.asyncio
async def test_remote_multi_answers_are_sent_as_a_json_array(tui_home, monkeypatch) -> None:
    calls: list = []

    async def fake(method, params=None, *, timeout=5.0):
        calls.append((method, dict(params or {})))
        if method == "host.clarification.pending":
            return {"requests": [{"request_id": "cl1", "question": "Pick", "choices": [
                {"label": "a, b"}, {"label": "c"}], "multi": True}]}
        return {"ok": True}

    monkeypatch.setattr(host_client, "acall", fake)
    app = AlpiApp(home_dir=tui_home)
    async with app.run_test(size=(120, 50)) as pilot:
        panel = await activity.open_review(app, _activity()["needs_you"][1])
        app._show_panel(panel)
        await pilot.pause()
        await pilot.press(*"1,2", "enter")
        for _ in range(20):
            await pilot.pause(0.02)
            if any(m == "host.clarification.respond" for m, _ in calls):
                break
        sent = [p for m, p in calls if m == "host.clarification.respond"]
        assert sent and json.loads(sent[0]["choice"]) == ["a, b", "c"]


@pytest.mark.asyncio
async def test_status_line_counts_remote_prompts(tui_home, monkeypatch) -> None:
    _fake_daemon(monkeypatch)
    monkeypatch.setattr(host_client, "daemon_present", lambda: True)
    app = AlpiApp(home_dir=tui_home)
    async with app.run_test(size=(160, 50)) as pilot:
        for _ in range(20):
            await pilot.pause(0.02)
            if app.status_line.waiting == 2:
                break
        assert app.status_line.waiting == 2


@pytest.mark.integration
@pytest.mark.asyncio
async def test_acall_against_a_real_unix_socket(monkeypatch) -> None:
    sock = Path(tempfile.mkdtemp(dir="/tmp")) / "h.sock"

    async def handle(reader, writer):
        body = json.loads((await reader.readline()).decode())
        writer.write((json.dumps({"id": body["id"], "result": {"method": body["method"]}}) + "\n").encode())
        await writer.drain()
        writer.close()

    server = await asyncio.start_unix_server(handle, path=str(sock))
    monkeypatch.setattr(host_client, "socket_path", lambda: sock)
    try:
        assert await host_client.acall("host.activity.list") == {"method": "host.activity.list"}
    finally:
        server.close()
        await server.wait_closed()


@pytest.mark.asyncio
async def test_socket_is_opened_with_a_large_line_limit(monkeypatch, tmp_path) -> None:
    seen: dict = {}

    async def fake_open_unix(path, **kwargs):
        seen.update(kwargs)
        raise ConnectionRefusedError("nope")

    monkeypatch.setattr(host_client.asyncio, "open_unix_connection", fake_open_unix)
    sock = tmp_path / "host.sock"
    sock.touch()
    monkeypatch.setattr(host_client, "socket_path", lambda: sock)
    with pytest.raises(host_client.HostUnavailable):
        await host_client.acall("host.activity.list")
    assert seen["limit"] >= 16 * 1024 * 1024


class _OverrunReader:
    async def readline(self) -> bytes:
        raise ValueError("Separator is not found, and chunk exceed the limit")


@pytest.mark.asyncio
async def test_an_oversized_reply_is_an_invalid_response(monkeypatch, tmp_path) -> None:
    sock = tmp_path / "host.sock"
    sock.touch()
    monkeypatch.setattr(host_client, "socket_path", lambda: sock)

    async def fake_open(path):
        return _OverrunReader(), _FakeWriter()

    monkeypatch.setattr(host_client, "_open", fake_open)
    with pytest.raises(host_client.HostError) as exc:
        await host_client.acall("host.activity.list")
    assert exc.value.message == host_client.INVALID_RESPONSE


@pytest.mark.asyncio
async def test_bad_replies_keep_the_panel_and_poll_alive(tui_home, monkeypatch) -> None:
    async def broken(method, params=None, *, timeout=5.0):
        raise host_client.HostError(None, host_client.INVALID_RESPONSE)

    monkeypatch.setattr(host_client, "acall", broken)
    monkeypatch.setattr(host_client, "daemon_present", lambda: True)
    app = AlpiApp(home_dir=tui_home)
    async with app.run_test(size=(120, 50)) as pilot:
        panel = await _open_activity(app, pilot)
        assert panel.message == host_client.INVALID_RESPONSE

        async def explode(method, params=None, *, timeout=5.0):
            raise RuntimeError("boom")

        monkeypatch.setattr(host_client, "acall", explode)
        app._poll_activity()
        await pilot.pause(0.1)
        assert app.is_running
        assert app.status_line.waiting == 0


@pytest.mark.asyncio
async def test_a_remote_prompt_with_no_time_left_reads_expired(tui_home) -> None:
    app = AlpiApp(home_dir=tui_home)
    async with app.run_test(size=(120, 50)):
        item = {**_activity()["needs_you"][0], "ts": time.time() - 120}
        panel = await activity.open_review(app, item)
        assert panel.deadline is not None
        assert panel.hint_text() == "esc back · expired"
