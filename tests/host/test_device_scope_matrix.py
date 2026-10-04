from __future__ import annotations

import asyncio
import base64
import contextlib
import json
import shutil
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from alpi import runs
from alpi.core.run_context import RunContext
from alpi.host import _chat_events, activity, attachments_rpc, chat, connections, handlers, sessions as host_sessions
from alpi.host import approval as host_approval
from alpi.host import clarification as host_clarification
from alpi.host import device_state as host_device_state
from alpi.host import events as host_events
from alpi.host import runs as host_runs
from alpi.host import server as host_server
from alpi.host.connection_context import ConnectionContext, use
from alpi.session import Session, Turn

SECRET = "SECRET-WRITTEN-BY-DEVICE-A"


@pytest.fixture
def world(tmp_path: Path, monkeypatch):
    from alpi import home

    monkeypatch.setattr(home, "_ROOT", tmp_path)
    connections.invalidate_cache()
    host_sessions._clear_row_cache()
    host_sessions._clear_payload_cache()
    host_device_state.invalidate_summary()
    activity._reset_for_tests()
    host_approval._reset_for_tests()
    host_clarification._reset_for_tests()

    row, device_a = connections.create_connection("Web", role="member", session_scope="device")
    _row, device_b = connections.add_device(row["id"])
    conn = row["id"]

    produced = tmp_path / "out" / "secret.md"
    produced.parent.mkdir(exist_ok=True)
    produced.write_text(SECRET)
    session = Session(tmp_path, "model", connection_id=conn, device_id=device_a["id"])
    session.turns.append(Turn(
        1, f"{SECRET} question", [], f"{SECRET} answer",
        output_attachments=[{"path": str(produced), "name": "secret.md", "mime": "text/markdown"}],
    ))
    session.save()

    context = RunContext.create(
        home=tmp_path, workspace=tmp_path, profile="default", source="user",
        session_id=session.id, connection_id=conn, device_id=device_a["id"], role="member",
    )
    runs.start(context, model="model", input_text=f"{SECRET} journal")
    runs.finish(context, "completed")

    _chat_events.reset_for_turn(tmp_path, session.id, "req-a", conn, device_a["id"])
    _chat_events.append(tmp_path, session.id, "req-a", {"event": "assistant_delta", "text": f"{SECRET} replay"})

    activity.start_run(
        "default", "run-a", session_id=session.id, title=f"{SECRET} running",
        connection_id=conn, device_id=device_a["id"],
    )
    for module, request_id, meta in (
        (host_approval, "ap-a", {"command": f"{SECRET} rm", "severity": "caution"}),
        (host_clarification, "cl-a", {"question": f"{SECRET} which?"}),
    ):
        with module._pending_lock:
            module._pending_meta[request_id] = {
                "request_id": request_id, "profile": "default", "ts": 1.0, "timeout_s": 60.0,
                "session_id": session.id, "connection_id": conn, "device_id": device_a["id"], **meta,
            }

    server = host_server.Server(home=tmp_path)
    for module in (handlers, host_runs, activity, host_device_state, chat, host_events,
                   host_approval, host_clarification, attachments_rpc):
        module.register(server)

    yield SimpleNamespace(
        root=tmp_path, server=server, conn=conn, session_id=session.id, run_id=context.run_id,
        produced=str(produced),
        a=device_a, b=device_b,
    )

    activity._reset_for_tests()
    host_approval._reset_for_tests()
    host_clarification._reset_for_tests()
    connections.invalidate_cache()


async def _call(world, device, method: str, **params) -> str:
    sent: list[dict] = []

    async def send(payload):
        sent.append(payload)

    body = {"id": "1", "method": method, "params": {"profile": "default", "auth_token": device["token"], **params}}
    await world.server._handle_request(json.dumps(body), send, require_token=True)
    return json.dumps(sent, sort_keys=True)


def _emit_text_events(world) -> None:
    owner = {"connection_id": world.conn, "device_id": world.a["id"]}
    host_events.emit("chat.turn_done", {
        "profile": "default", "session_id": world.session_id, "source": "user",
        "duration_s": 6.0, "tool_count": 2, "summary": f"{SECRET} reply", **owner,
    })
    host_events.emit("file_mutations", {
        "profile": "default", "session_id": world.session_id,
        "mutations": [{"path": "notes.md", "diff_preview": f"+{SECRET}"}], **owner,
    })
    host_events.emit("session_changed", {
        "profile": "default", "id": world.session_id, "subdir": "sessions", "in_flight": False, **owner,
    })
    host_events.emit("approval.request", {"request_id": "ap-a", "command": f"{SECRET} rm", **owner})
    host_events.emit("clarification.request", {"request_id": "cl-a", "question": f"{SECRET} which?", **owner})


async def _stream_text(world, device) -> str:
    sent: list[dict] = []
    subscribed = asyncio.Event()

    async def send(payload):
        sent.append(payload)
        if payload.get("event") == "subscribed":
            subscribed.set()

    body = {"id": "s", "method": "host.events.subscribe", "params": {"auth_token": device["token"]}}
    task = asyncio.create_task(world.server._handle_request(json.dumps(body), send, require_token=True))
    try:
        await asyncio.wait_for(subscribed.wait(), timeout=2.0)
        _emit_text_events(world)
        host_events.emit("session_changed", {"id": "sentinel", "profile": "default"})
        for _ in range(200):
            if any(frame.get("data", {}).get("id") == "sentinel" for frame in sent):
                break
            await asyncio.sleep(0.01)
        else:
            raise AssertionError("the stream never delivered its sentinel, so the row would prove nothing")
    finally:
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task
    return json.dumps(sent, sort_keys=True)


async def _history_text(world, device) -> str:
    _emit_text_events(world)
    return await _call(world, device, "host.events.history", limit=200)


RPC_PATHS = {
    "host.sessions.list": lambda w, d: _call(w, d, "host.sessions.list"),
    "host.session.read": lambda w, d: _call(w, d, "host.session.read", id=w.session_id),
    "host.profile.summaries": lambda w, d: _call(w, d, "host.profile.summaries"),
    "host.chat.events_since": lambda w, d: _call(w, d, "host.chat.events_since", session_id=w.session_id, after_seq=0),
    "host.runs.list": lambda w, d: _call(w, d, "host.runs.list"),
    "host.run.read": lambda w, d: _call(w, d, "host.run.read", id=w.run_id),
    "host.activity.list": lambda w, d: _call(w, d, "host.activity.list"),
    "host.approval.pending": lambda w, d: _call(w, d, "host.approval.pending"),
    "host.clarification.pending": lambda w, d: _call(w, d, "host.clarification.pending"),
    "host.attachments.fetch": lambda w, d: _call(w, d, "host.attachments.fetch", path=w.produced),
    "host.events.history": _history_text,
    "host.events.subscribe": _stream_text,
}


@pytest.mark.asyncio
@pytest.mark.parametrize("path", sorted(RPC_PATHS))
async def test_a_sibling_device_never_reads_what_device_a_wrote(world, path: str) -> None:
    marker = {
        "host.runs.list": world.run_id,
        "host.attachments.fetch": base64.b64encode(SECRET.encode()).decode(),
    }.get(path, SECRET)
    owner_sees = await RPC_PATHS[path](world, world.a)
    sibling_sees = await RPC_PATHS[path](world, world.b)

    assert marker in owner_sees, f"{path}: the owner must see its own data or this row proves nothing"
    assert marker not in sibling_sees, path


def _tool_context(world, device) -> ConnectionContext:
    return ConnectionContext(world.conn, device["id"], "remote", "member", session_scope="device")


def _run_tool(world, device, tool, **kwargs) -> str:
    with use(_tool_context(world, device)):
        result = tool.run(**kwargs)
    return json.dumps({"ok": result.ok, "output": result.output, "error": result.error}, default=str)


def _session_search(world, device) -> str:
    from alpi.tools.session_search import SessionSearch

    return _run_tool(world, device, SessionSearch(), query="answer")


def _session_read_list(world, device) -> str:
    from alpi.tools.session_read import SessionRead

    return _run_tool(world, device, SessionRead())


def _session_read_open(world, device) -> str:
    from alpi.tools.session_read import SessionRead

    return _run_tool(world, device, SessionRead(), session=world.session_id)


def _recall(world, device) -> str:
    from alpi.tools import recall as recall_tool

    return _run_tool(world, device, recall_tool.RecallSessions(), query=f"{SECRET} question")


TOOL_PATHS = {
    "session_search": _session_search,
    "session_read (list)": _session_read_list,
    "session_read (open by id)": _session_read_open,
    "recall_sessions": _recall,
}


@pytest.fixture
def stub_embedder(monkeypatch):
    from alpi.core import embed as embed_mod
    from tests.test_recall import StubEmbedder

    embedder = StubEmbedder()
    monkeypatch.setattr(embed_mod, "_DEFAULT", embedder)
    yield embedder
    monkeypatch.setattr(embed_mod, "_DEFAULT", None)


@pytest.mark.parametrize("path", sorted(TOOL_PATHS))
def test_a_sibling_devices_agent_tools_never_read_what_device_a_wrote(world, stub_embedder, path: str) -> None:
    from alpi.tools import recall as recall_tool

    recall_tool.index_sessions(world.root)

    owner_sees = TOOL_PATHS[path](world, world.a)
    sibling_sees = TOOL_PATHS[path](world, world.b)

    assert SECRET in owner_sees, f"{path}: the owner must see its own text or this row proves nothing"
    assert SECRET not in sibling_sees, path


@pytest.mark.asyncio
async def test_a_sibling_device_cannot_delete_what_device_a_wrote(world) -> None:
    stored = world.root / "sessions" / f"{world.session_id}.json"

    refused = await _call(world, world.b, "host.sessions.delete", ids=[world.session_id])

    assert stored.exists()
    assert world.session_id not in json.loads(refused)[0]["result"]["deleted"]
    assert SECRET not in refused


@pytest.mark.asyncio
async def test_a_sibling_device_cannot_continue_what_device_a_wrote(world) -> None:
    refused = await _call(
        world, world.b, "host.chat.send",
        text="and then?", request_id="req-b", session_id=world.session_id,
    )

    frames = json.loads(refused)
    assert any(frame.get("event") == "error" and "not found" in frame.get("text", "") for frame in frames)
    assert SECRET not in refused


@pytest.mark.asyncio
async def test_a_replay_sidecar_with_no_session_file_yet_belongs_to_its_device(world) -> None:
    sid = "pending-session-of-a"
    _chat_events.reset_for_turn(world.root, sid, "req-p", world.conn, world.a["id"])
    _chat_events.append(world.root, sid, "req-p", {"event": "assistant_delta", "text": f"{SECRET} pending"})

    owner_sees = await _call(world, world.a, "host.chat.events_since", session_id=sid, after_seq=0)
    sibling_sees = await _call(world, world.b, "host.chat.events_since", session_id=sid, after_seq=0)

    assert SECRET in owner_sees
    assert SECRET not in sibling_sees


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["chat.turn_done", "file_mutations"])
async def test_an_event_without_an_owner_is_not_shown_to_a_member_device(world, kind: str) -> None:
    host_events.emit(kind, {
        "profile": "default", "session_id": "recorded-before-the-upgrade",
        "summary": f"{SECRET} legacy", "mutations": [{"path": "x", "diff_preview": f"+{SECRET}"}],
    })

    for device in (world.a, world.b):
        assert SECRET not in await _call(world, device, "host.events.history", limit=200)


@pytest.mark.integration
@pytest.mark.skipif(
    not (sys.platform.startswith("linux") and shutil.which("bwrap")),
    reason="needs bwrap (Linux)",
)
def test_a_sibling_devices_terminal_never_reads_what_device_a_wrote(world) -> None:
    from alpi.tools.terminal import Terminal

    sessions = world.root.resolve() / "sessions"
    command = f"cat {sessions}/*.json"
    sibling_sees = _run_tool(world, world.b, Terminal(), command=command, timeout=30)
    with use(ConnectionContext(world.conn, world.a["id"], "remote", "admin")):
        admin_sees = Terminal().run(command=command, timeout=30).output

    assert SECRET in admin_sees, "the admin control must read the session or this row proves nothing"
    assert SECRET not in sibling_sees
