from __future__ import annotations

import asyncio
import json
import threading
import time
from pathlib import Path

import pytest

from alpi.host import activity
from alpi.host import approval as host_approval
from alpi.host import clarification as host_clarification
from alpi.host import events as host_events
from alpi.host import server as host_server
from alpi.host.connection_context import ConnectionContext, use
from tests.host.test_workgroup_pipeline_run import _CHAIN, _STEPS, _append, _hub


@pytest.fixture(autouse=True)
def _clean(monkeypatch):
    activity._reset_for_tests()
    monkeypatch.setattr(activity, "DEBOUNCE_S", 0.0)
    captured: list[tuple[str, dict]] = []

    def listener(kind: str, data: dict) -> None:
        captured.append((kind, dict(data)))

    host_events.add_listener(listener)
    yield captured
    host_events.remove_listener(listener)
    host_events.remove_listener(activity._on_event)
    activity._reset_for_tests()
    host_approval._reset_for_tests()
    host_clarification._reset_for_tests()


def _enable() -> None:
    activity._enabled = True
    host_events.add_listener(activity._on_event)


def _changes(captured: list[tuple[str, dict]]) -> list[str]:
    return [data["profile"] for kind, data in captured if kind == "activity.changed"]


def _member(connection_id: str = "conn-a") -> ConnectionContext:
    return ConnectionContext(connection_id=connection_id, source="remote", role="member")


def _pending(module, request_id: str, **meta) -> None:
    with module._pending_lock:
        module._pending_meta[request_id] = {"request_id": request_id, **meta}


def test_snapshot_shape(monkeypatch, tmp_path: Path) -> None:
    home = tmp_path / "default"
    (home / "schedule").mkdir(parents=True)
    (home / "schedule" / "jobs.json").write_text(json.dumps([
        {"id": "brief", "title": "daily brief", "kind": "once", "run_at": "2099-01-01T08:00:00+00:00"},
    ]))
    monkeypatch.setattr(activity, "_profile_homes", lambda: [("default", home)])
    _pending(
        host_approval, "ap1", command="rm -rf build", severity="caution", profile="default",
        ts=20.0, timeout_s=60.0, session_id="s1", connection_id="host", device_id="",
    )
    _pending(
        host_clarification, "cl1", question="Which one?", profile="default",
        ts=10.0, timeout_s=300.0, session_id=None, connection_id="host", device_id="",
    )
    activity.start_run("default", "run-1", session_id="s1", title="deploy summary", connection_id="host")

    snap = activity.snapshot()

    assert snap["needs_you"] == [
        {"kind": "clarification", "request_id": "cl1", "profile": "default", "title": "Which one?",
         "ts": 10.0, "timeout_s": 300.0, "session_id": None},
        {"kind": "approval", "request_id": "ap1", "profile": "default", "title": "rm -rf build",
         "severity": "caution", "ts": 20.0, "timeout_s": 60.0, "session_id": "s1"},
    ]
    [turn] = snap["running"]
    assert {k: v for k, v in turn.items() if k != "started_at"} == {
        "kind": "turn", "profile": "default", "session_id": "s1",
        "title": "deploy summary", "source": "chat",
    }
    assert isinstance(turn["started_at"], float)
    assert snap["scheduled"] == [{
        "profile": "default", "job_id": "brief", "title": "daily brief",
        "next_fire": "2099-01-01T08:00:00+00:00", "last_run_at": None, "last_run_status": None,
    }]


def test_member_sees_only_its_own_connection(monkeypatch, tmp_path: Path) -> None:
    home = tmp_path / "default"
    (home / "schedule").mkdir(parents=True)
    (home / "schedule" / "jobs.json").write_text(json.dumps([
        {"id": "j", "kind": "once", "run_at": "2099-01-01T08:00:00+00:00"},
    ]))
    monkeypatch.setattr(activity, "_profile_homes", lambda: [("default", home)])
    _pending(host_approval, "mine", command="a", profile="default", ts=1.0,
             connection_id="conn-a", device_id="")
    _pending(host_approval, "theirs", command="b", profile="default", ts=2.0,
             connection_id="conn-b", device_id="")
    _pending(host_clarification, "host-q", question="q", profile="default", ts=3.0,
             connection_id="host", device_id="")
    activity.start_run("default", "r-a", session_id="sa", connection_id="conn-a")
    activity.start_run("default", "r-b", session_id="sb", connection_id="conn-b")
    activity.start_run("default", "r-host", session_id="sh", connection_id="host")
    activity.start_run("default", "schedule:j", source="schedule", connection_id="host")

    with use(_member("conn-a")):
        snap = activity.snapshot()

    assert [r["request_id"] for r in snap["needs_you"]] == ["mine"]
    assert [r["session_id"] for r in snap["running"]] == ["sa"]
    assert snap["scheduled"] == []
    assert all("connection_id" not in r for r in snap["running"])

    local = activity.snapshot()
    assert {r["request_id"] for r in local["needs_you"]} == {"mine", "theirs", "host-q"}
    assert {r.get("session_id") for r in local["running"]} == {"sa", "sb", "sh", None}
    assert [r["job_id"] for r in local["scheduled"]] == ["j"]

    with use(ConnectionContext(connection_id="conn-b", source="remote", role="admin")):
        remote_admin = activity.snapshot()
    assert {r["request_id"] for r in remote_admin["needs_you"]} == {"mine", "theirs", "host-q"}
    assert {r.get("session_id") for r in remote_admin["running"]} == {"sa", "sb", "sh", None}


def test_scope_filter_drops_out_of_scope_profiles() -> None:
    payload = {"id": "x", "result": {
        "needs_you": [{"profile": "a"}, {"profile": "b"}],
        "running": [{"profile": "b"}],
        "scheduled": [{"profile": "a"}],
    }}
    out = host_server._filter_payload_by_scope("host.activity.list", payload, ["a"])
    assert out["result"] == {
        "needs_you": [{"profile": "a"}], "running": [], "scheduled": [{"profile": "a"}],
    }
    assert "host.activity.list" in host_server._SCOPE_FREE_METHODS


def test_scheduled_sorts_soonest_first_caps_and_keeps_failures(monkeypatch, tmp_path: Path) -> None:
    home = tmp_path / "default"
    (home / "schedule").mkdir(parents=True)
    jobs = [
        {"id": f"j{i:02d}", "kind": "once", "run_at": f"2099-01-{i + 1:02d}T00:00:00+00:00"}
        for i in range(25)
    ]
    jobs.append({"id": "paused", "kind": "once", "run_at": "2098-01-01T00:00:00+00:00", "paused": True})
    jobs.append({"id": "broken", "kind": "once", "run_at": "2026-01-01T03:00:00+00:00",
                 "last_run_at": "2026-01-01T03:00:00+00:00", "last_run_status": "error"})
    (home / "schedule" / "jobs.json").write_text(json.dumps(jobs))
    monkeypatch.setattr(activity, "_profile_homes", lambda: [("default", home)])

    rows = activity.snapshot()["scheduled"]

    assert len(rows) == activity.SCHEDULED_MAX
    ids = [r["job_id"] for r in rows]
    assert "broken" in ids and "paused" not in ids
    assert ids[:3] == ["j00", "j01", "j02"]
    assert ids[-1] == "broken" and rows[-1]["next_fire"] is None
    assert "j18" in ids and "j19" not in ids


def test_running_workgroup_reports_phase_progress(monkeypatch, tmp_path: Path) -> None:
    home = tmp_path / "hub"
    wg = _hub(home, pipelines=_CHAIN, launch="intake", steps=_STEPS)
    for body in ("@scout #task #intake gather", "#done intake ready", "@quill #task #content copy"):
        _append(home, wg.meta.id, body)
    monkeypatch.setattr(activity, "_profile_homes", lambda: [("hub", home)])

    rows = [r for r in activity.snapshot()["running"] if r["kind"] == "workgroup"]

    assert rows == [{
        "kind": "workgroup", "profile": "hub", "workgroup_id": wg.meta.id, "name": "factory",
        "pipeline": "intake", "phase": "content", "phases_done": 1, "phases_total": 4,
    }]


def _two_rows_for_one_workgroup(monkeypatch, tmp_path: Path) -> None:
    hub_home, alice_home = tmp_path / "hub", tmp_path / "alice"
    monkeypatch.setattr(activity, "_profile_homes", lambda: [("hub", hub_home), ("alice", alice_home)])
    def row(profile: str, is_hub: bool) -> dict:
        return {
            "kind": "workgroup", "profile": profile, "workgroup_id": "w1", "name": "factory",
            "pipeline": "intake", "phase": "content", "phases_done": 1, "phases_total": 4, "_hub": is_hub,
        }

    def hub_rows(home, profile):
        return [("w1", row(profile, True))] if profile == "hub" else []

    def member_rows(home, profile):
        return [("w1", row(profile, False))] if profile == "alice" else []

    monkeypatch.setattr(activity, "_hub_rows", hub_rows)
    monkeypatch.setattr(activity, "_member_rows", member_rows)


def _workgroup_profiles(ctx: ConnectionContext) -> list[str]:
    with use(ctx):
        return [r["profile"] for r in activity.snapshot()["running"] if r["kind"] == "workgroup"]


def test_a_caller_scoped_to_the_member_profile_keeps_the_pipeline(monkeypatch, tmp_path: Path) -> None:
    _two_rows_for_one_workgroup(monkeypatch, tmp_path)
    scoped = ConnectionContext(connection_id="conn-a", source="remote", role="member", profile_scope=("alice",))

    assert _workgroup_profiles(scoped) == ["alice"]


def test_a_caller_who_sees_both_profiles_still_gets_one_row_from_the_hub(monkeypatch, tmp_path: Path) -> None:
    _two_rows_for_one_workgroup(monkeypatch, tmp_path)
    both = ConnectionContext(connection_id="conn-a", source="remote", role="member", profile_scope=("alice", "hub"))
    unscoped = ConnectionContext(connection_id="conn-a", source="remote", role="member")

    assert _workgroup_profiles(both) == ["hub"]
    assert _workgroup_profiles(unscoped) == ["hub"]
    assert _workgroup_profiles(ConnectionContext(role="admin")) == ["hub"]


def test_the_server_hands_the_authenticated_profile_scope_to_the_handler(monkeypatch, tmp_path: Path) -> None:
    seen: list[tuple[str, ...]] = []

    async def probe(params, server):
        from alpi.host.connection_context import current
        seen.append(current().profile_scope)
        return {}

    srv = host_server.Server(tmp_path)
    srv.register("host.probe", probe)
    monkeypatch.setattr(
        host_server, "_check_token_meta",
        lambda body: host_server.AuthMeta(True, "member", ["alice", "bob"], "conn-a", "dev-a"),
    )

    async def run():
        async def send(payload):
            return None
        await srv._handle_request(
            json.dumps({"id": "1", "method": "host.probe", "params": {"profile": "alice", "auth_token": "t"}}),
            send, require_token=True,
        )

    asyncio.run(run())

    assert seen == [("alice", "bob")]


def test_workgroup_without_active_pipeline_is_not_running(monkeypatch, tmp_path: Path) -> None:
    home = tmp_path / "hub"
    wg = _hub(home, pipelines=_CHAIN, launch="intake", steps=_STEPS)
    for body in ("@scout #task #intake a", "#done a", "@quill #task #content b", "#done b",
                 "@pixel #task #build c", "#done c", "@mira #task #qa d", "#done d"):
        _append(home, wg.meta.id, body)
    monkeypatch.setattr(activity, "_profile_homes", lambda: [("hub", home)])

    assert activity.snapshot()["running"] == []


def test_phase_change_emits_activity_changed_only_when_the_phase_moves(
    monkeypatch, tmp_path: Path, _clean,
) -> None:
    home = tmp_path / "hub"
    wg = _hub(home, pipelines=_CHAIN, launch="intake", steps=_STEPS)
    _append(home, wg.meta.id, "@scout #task #intake gather")
    monkeypatch.setattr(activity, "_profile_homes", lambda: [("hub", home)])
    _enable()

    activity._wg_check("hub", wg.meta.id)
    assert _changes(_clean) == ["hub"]
    activity._wg_check("hub", wg.meta.id)
    assert _changes(_clean) == ["hub"]

    _append(home, wg.meta.id, "#done intake ready")
    _append(home, wg.meta.id, "@quill #task #content copy")
    activity.snapshot()
    activity._wg_check("hub", wg.meta.id)
    assert _changes(_clean) == ["hub", "hub"]


def test_wg_post_event_queues_a_phase_check(monkeypatch, _clean) -> None:
    _enable()
    checked = threading.Event()
    monkeypatch.setattr(activity, "_wg_check", lambda profile, wg_id: checked.set())
    host_events.emit("wg.post", {"profile": "hub", "wg_id": "w1", "seq": 3})
    assert checked.wait(2.0)


def test_turn_start_and_end_emit_activity_changed(_clean) -> None:
    _enable()
    activity.start_run("smith", "r1")
    assert _changes(_clean) == ["smith"]
    activity.end_run("smith", "r1")
    activity.end_run("smith", "r1")
    assert _changes(_clean) == ["smith", "smith"]


def test_disabled_outside_the_daemon(_clean) -> None:
    activity.start_run("smith", "r1")
    activity.end_run("smith", "r1")
    assert _changes(_clean) == []


def test_changes_are_debounced_per_profile(monkeypatch, _clean) -> None:
    _enable()
    monkeypatch.setattr(activity, "DEBOUNCE_S", 0.2)
    for _ in range(5):
        activity.changed("a")
    activity.changed("b")
    assert _changes(_clean) == ["a", "b"]
    deadline = time.time() + 2.0
    while len(_changes(_clean)) < 3 and time.time() < deadline:
        time.sleep(0.02)
    assert _changes(_clean) == ["a", "b", "a"]


def test_schedule_events_trigger_activity_changed(_clean) -> None:
    _enable()
    host_events.emit("schedule.failed", {"profile": "doc", "job_id": "x"})
    host_events.emit("session_changed", {"profile": "doc", "id": "s"})
    assert _changes(_clean) == ["doc"]


def test_scheduled_run_is_listed_while_it_runs(tmp_path: Path) -> None:
    home = tmp_path / "profiles" / "doc"
    home.mkdir(parents=True)
    with activity.scheduled_run(home, {"id": "weekly", "title": "weekly labs"}):
        [row] = activity._running_turns(admin=True)
        assert row["source"] == "schedule"
        assert row["title"] == "weekly labs"
        assert row["job_id"] == "weekly"
        assert row["profile"] == "doc"
    assert activity._running_turns(admin=True) == []


async def _make_server(home: Path) -> host_server.Server:
    srv = host_server.Server(home=home)
    host_events.register(srv)
    host_approval.register(srv)
    host_clarification.register(srv)
    activity.register(srv)
    await srv.start()
    return srv


async def _rpc(srv: host_server.Server, method: str, params: dict) -> dict:
    reader, writer = await asyncio.open_unix_connection(str(srv.socket_path()))
    try:
        writer.write((json.dumps({"id": "r", "method": method, "params": params}) + "\n").encode())
        await writer.drain()
        return json.loads(await asyncio.wait_for(reader.readline(), timeout=2.0))
    finally:
        writer.close()
        await writer.wait_closed()


async def _wait_for(predicate, timeout: float = 2.0) -> None:
    deadline = time.time() + timeout
    while not predicate():
        if time.time() > deadline:
            raise AssertionError("condition not met in time")
        await asyncio.sleep(0.02)


@pytest.mark.asyncio
async def test_approval_request_and_resolve_drive_the_verb(monkeypatch, _clean) -> None:
    import shutil
    import tempfile

    from alpi import home as home_mod
    from alpi.alp.keys import load_or_generate
    from alpi.tools import _approval

    short = Path(tempfile.mkdtemp(prefix="alp-activity-", dir="/tmp"))
    home = short / "h"
    home.mkdir()
    load_or_generate(home)
    monkeypatch.setattr(activity, "_profile_homes", lambda: [])
    srv = await _make_server(home)
    out: dict = {}

    def _run() -> None:
        token = home_mod.set_active_session("sess-42")
        try:
            out["decision"] = _approval.check("rm -rf build")
        finally:
            home_mod.reset_active_session(token)

    try:
        worker = threading.Thread(target=_run, daemon=True)
        worker.start()
        await _wait_for(lambda: host_approval.pending_requests())
        [request] = [d for k, d in _clean if k == "approval.request"]
        assert request["session_id"] == "sess-42"

        listed = (await _rpc(srv, "host.activity.list", {}))["result"]
        [row] = listed["needs_you"]
        assert row["kind"] == "approval"
        assert row["title"] == "rm -rf build"
        assert row["session_id"] == "sess-42"
        assert set(listed) == {"needs_you", "running", "scheduled"}
        changes_before = len(_changes(_clean))
        assert changes_before >= 1

        resp = await _rpc(srv, "host.approval.respond", {"request_id": row["request_id"], "choice": "deny"})
        assert resp["result"]["ok"] is True
        await asyncio.to_thread(worker.join, 2.0)
        await _wait_for(lambda: len(_changes(_clean)) > changes_before)
        assert (await _rpc(srv, "host.activity.list", {}))["result"]["needs_you"] == []
    finally:
        await srv.stop()
        _approval.set_prompt_callback(None)
        _approval.clear_session_allowlist()
        shutil.rmtree(short, ignore_errors=True)


def test_clarification_request_carries_session_id(monkeypatch, _clean) -> None:
    from alpi import home as home_mod

    loop = asyncio.new_event_loop()
    thread = threading.Thread(target=loop.run_forever, daemon=True)
    thread.start()
    monkeypatch.setattr(host_clarification, "_loop_ref", loop)
    monkeypatch.setattr(host_clarification, "CLARIFICATION_TIMEOUT_S", 0.1)
    try:
        token = home_mod.set_active_session("sess-7")
        try:
            host_clarification.host_clarification_handler("Pick?", [{"label": "A"}], False)
        finally:
            home_mod.reset_active_session(token)
        [request] = [d for k, d in _clean if k == "clarification.request"]
        assert request["session_id"] == "sess-7"
        host_clarification.host_clarification_handler("Again?", [{"label": "A"}], False)
        second = [d for k, d in _clean if k == "clarification.request"][-1]
        assert second["session_id"] is None
    finally:
        loop.call_soon_threadsafe(loop.stop)
        thread.join(1.0)
        loop.close()


@pytest.mark.asyncio
async def test_workgroup_dispatch_turn_is_listed_while_it_runs(_clean) -> None:
    import shutil
    import sys
    import tempfile

    from alpi import service

    _enable()
    short = Path(tempfile.mkdtemp(prefix="alp-activity-wg-", dir="/tmp"))
    home = short / "alice"
    (home / "alp").mkdir(parents=True)
    real_create = service.asyncio.create_subprocess_exec

    async def fake_create(*argv, **kw):  # noqa: ANN002, ANN003
        return await real_create(
            sys.executable, "-c", "import time; time.sleep(0.4)",
            stdout=service.asyncio.subprocess.PIPE, stderr=service.asyncio.subprocess.PIPE,
        )

    service.asyncio.create_subprocess_exec = fake_create
    try:
        task = asyncio.create_task(service._dispatch_workgroup_turn(
            home, profile="alice", wg_id="wg_x", wg_name="design", reason="test",
        ))
        await _wait_for(lambda: activity._running_turns(admin=True))
        [row] = activity._running_turns(admin=True)
        assert row["source"] == "workgroup"
        assert row["workgroup_id"] == "wg_x"
        assert row["title"] == "design"
        with use(_member("conn-a")):
            assert [r["workgroup_id"] for r in activity._running_turns(admin=False)] == ["wg_x"]
        await task
    finally:
        service.asyncio.create_subprocess_exec = real_create
        shutil.rmtree(short, ignore_errors=True)
    assert activity._running_turns(admin=True) == []
    assert _changes(_clean).count("alice") >= 2


def test_scheduler_fire_is_listed_while_the_job_runs(monkeypatch, tmp_path: Path, _clean) -> None:
    from alpi.scheduler import run as sched_run

    home = tmp_path / "profiles" / "doc"
    (home / "schedule").mkdir(parents=True)
    (home / "schedule" / "jobs.json").write_text(json.dumps([
        {"id": "weekly", "title": "weekly labs", "kind": "cron", "expression": "0 3 * * 1"},
    ]))
    _enable()
    seen: list = []

    def fake_run_job(job, h):  # noqa: ANN001
        seen.extend(activity._running_turns(admin=True))
        return sched_run.JobOutcome(True, "ok")

    monkeypatch.setattr(sched_run, "run_job", fake_run_job)
    monkeypatch.setattr(sched_run, "_emit_schedule_event", lambda *a, **k: None)

    ok, _msg = sched_run.fire_by_id(home, "weekly")

    assert ok
    assert [(r["source"], r["job_id"], r["title"]) for r in seen] == [("schedule", "weekly", "weekly labs")]
    assert activity._running_turns(admin=True) == []
    assert _changes(_clean) == ["doc", "doc"]


def test_activity_changed_is_live_only(_clean) -> None:
    _enable()
    before = len(host_events._history)
    activity.changed("doc")
    assert _changes(_clean) == ["doc"]
    assert all(ev.get("event") != "activity.changed" for ev in list(host_events._history)[before:])


def test_concurrent_fires_of_one_job_get_their_own_rows(tmp_path: Path) -> None:
    home = tmp_path / "profiles" / "doc"
    home.mkdir(parents=True)
    job = {"id": "weekly", "title": "weekly labs"}
    with activity.scheduled_run(home, job):
        with activity.scheduled_run(home, job):
            assert len(activity._running_turns(admin=True)) == 2
        assert len(activity._running_turns(admin=True)) == 1
    assert activity._running_turns(admin=True) == []


@pytest.mark.asyncio
async def test_mention_turn_is_listed_while_the_peer_answers(monkeypatch, tmp_path: Path) -> None:
    from types import SimpleNamespace

    import alpi.engine
    from alpi import config as cfg_mod
    from alpi.alp import mention as alp_mention
    from alpi.host import chat as dc

    home = tmp_path / "profiles" / "abby"
    home.mkdir(parents=True)
    seen: list = []

    async def _stream(*a, **k):  # noqa: ANN002, ANN003
        seen.extend(activity._running_turns(admin=True))
        yield {"kind": "chunk", "text": "hi"}

    monkeypatch.setattr(alp_mention, "execute_stream", _stream)
    monkeypatch.setattr(alp_mention, "reply_text", lambda peer, final, parts: "".join(parts))
    monkeypatch.setattr(cfg_mod, "load", lambda h: SimpleNamespace(model="x"))
    session = SimpleNamespace(
        id="s-m", subdir="sessions", connection_id="host", device_id="",
        log_turn=lambda **kw: None, save=lambda: None,
    )
    monkeypatch.setattr(alpi.engine, "Engine", lambda *, home, cfg: SimpleNamespace(session=session))
    frames: list = []

    async def send(frame):  # noqa: ANN001
        frames.append(frame)

    await dc._send_mention(home, SimpleNamespace(peer_id="bob", prompt="status?"), "req-m", None, send)

    [row] = seen
    assert (row["profile"], row["source"], row["session_id"]) == ("abby", "peer", "s-m")
    assert row["title"] == "@bob status?"
    assert activity._running_turns(admin=True) == []
    assert frames[-1]["event"] == "done"


@pytest.mark.asyncio
async def test_dispatch_setup_failure_leaves_no_running_row(monkeypatch) -> None:
    import shutil
    import sys
    import tempfile

    from alpi import service

    short = Path(tempfile.mkdtemp(prefix="alp-activity-wg-", dir="/tmp"))
    home = short / "alice"
    (home / "alp").mkdir(parents=True)
    real_create = service.asyncio.create_subprocess_exec

    async def fake_create(*argv, **kw):  # noqa: ANN002, ANN003
        return await real_create(
            sys.executable, "-c", "pass",
            stdout=service.asyncio.subprocess.PIPE, stderr=service.asyncio.subprocess.PIPE,
        )

    def boom(_home):  # noqa: ANN001
        raise RuntimeError("config unreadable")

    monkeypatch.setattr(service.asyncio, "create_subprocess_exec", fake_create)
    monkeypatch.setattr(service, "_working_after_for", boom)
    try:
        with pytest.raises(RuntimeError):
            await service._dispatch_workgroup_turn(
                home, profile="alice", wg_id="wg_x", wg_name="design", reason="test", member_turn=True,
            )
    finally:
        info = service._INFLIGHT.pop(("wg_x", "alice"), {})
        if info.get("proc") is not None:
            await info["proc"].wait()
            await asyncio.sleep(0.05)
        shutil.rmtree(short, ignore_errors=True)
    assert activity._running_turns(admin=True) == []
