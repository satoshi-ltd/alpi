"""Workgroup poller tests."""

from __future__ import annotations

import asyncio
import datetime as _dt
import shutil
import tempfile
import time
from pathlib import Path

import pytest

from alpi import service
from alpi.alp import subscription as sub_mod


@pytest.fixture
def short_tmp() -> Path:
    d = Path(tempfile.mkdtemp(prefix="alpi-poll-", dir="/tmp"))
    try:
        yield d
    finally:
        shutil.rmtree(d, ignore_errors=True)


# `_should_dispatch` wake decision.


def test_self_mention_wakes() -> None:
    posts = [
        {"seq": 1, "text": "@alice please review", "from": "bob_pk"},
    ]
    reason, new_seq = service._should_dispatch("alice", "alice_pk", posts, 0)
    assert reason and "@alice mentioned" in reason
    assert new_seq == 1


def test_collective_task_with_no_mentions_wakes() -> None:
    """An untagged `#task` should wake everyone."""
    posts = [
        {"seq": 1, "text": "#task #peptides research peptides", "from": "user_pk"},
    ]
    reason, _ = service._should_dispatch("bob", "bob_pk", posts, 0)
    assert reason and "collective" in reason


def test_targeted_task_does_not_wake_unmentioned_peer() -> None:
    """A task aimed at @alice must not wake bob."""
    posts = [
        {"seq": 1, "text": "#task #lit @alice take lit review", "from": "user_pk"},
    ]
    reason, _ = service._should_dispatch("bob", "bob_pk", posts, 0)
    assert reason is None


def test_uninteresting_traffic_silent() -> None:
    posts = [
        {"seq": 1, "text": "@bob nice work", "from": "carol_pk"},
        {"seq": 2, "text": "yep", "from": "bob_pk"},
    ]
    # Latest is bob's own post, so just advance the pointer.
    reason, new_seq = service._should_dispatch("bob", "bob_pk", posts, 0)
    assert reason is None
    assert new_seq == 2  # advance past own post


def test_targeted_task_wakes_named_peer() -> None:
    posts = [
        {"seq": 1, "text": "#task #lit @alice take lit review", "from": "user_pk"},
    ]
    reason, _ = service._should_dispatch("alice", "alice_pk", posts, 0)
    assert reason and "@alice mentioned" in reason


def test_participant_in_active_task_wakes_on_latest_other_post() -> None:
    """Named tasks keep waking on later peer replies."""
    posts = [
        {"seq": 1, "text": "#task #stack @alice @bob analyze the stack", "from": "user_pk"},
        {"seq": 2, "text": "I'd lean toward FastAPI + SQLite", "from": "alice_pk"},
    ]
    # seq 1 is already consumed; seq 2 should wake Bob.
    reason, new_seq = service._should_dispatch("bob", "bob_pk", posts, 1)
    assert reason and "active task" in reason
    assert new_seq == 2


def test_collective_task_wakes_any_member_on_peer_reply() -> None:
    """Collective tasks wake any member on peer replies."""
    posts = [
        {"seq": 1, "text": "#task #pick-stack pick stack for our tracker", "from": "alice_pk"},
        {"seq": 2, "text": "FastAPI + SQLite", "from": "alice_pk"},
    ]
    reason, new_seq = service._should_dispatch("bob", "bob_pk", posts, 1)
    assert reason and "active task" in reason
    assert new_seq == 2


def test_participant_silent_when_not_named_in_task() -> None:
    """Bob stays silent if he was not named."""
    posts = [
        {"seq": 1, "text": "#task #lit @alice take lit review", "from": "user_pk"},
        {"seq": 2, "text": "starting now", "from": "alice_pk"},
    ]
    reason, _ = service._should_dispatch("bob", "bob_pk", posts, 0)
    assert reason is None


def test_participant_trigger_silent_with_no_active_task() -> None:
    posts = [
        {"seq": 1, "text": "general thoughts", "from": "alice_pk"},
        {"seq": 2, "text": "more thoughts", "from": "bob_pk"},
    ]
    reason, _ = service._should_dispatch("alice", "alice_pk", posts, 0)
    assert reason is None


def test_silent_when_already_responded_to_latest() -> None:
    """Already-responded content does not refire."""
    posts = [
        {"seq": 1, "text": "#task #stack @alice @bob analyze the stack", "from": "user_pk"},
        {"seq": 2, "text": "I'd lean toward FastAPI + SQLite", "from": "alice_pk"},
    ]
    # Bob already handled seq 2, so no re-dispatch.
    reason, new_seq = service._should_dispatch("bob", "bob_pk", posts, 2)
    assert reason is None
    assert new_seq == 2


def test_re_fires_when_new_content_arrives_after_response() -> None:
    """New peer content wakes us again."""
    posts = [
        {"seq": 1, "text": "#task #analyze @alice @bob analyze", "from": "user_pk"},
        {"seq": 2, "text": "FastAPI + SQLite", "from": "alice_pk"},
        {"seq": 3, "text": "I'd push back on Postgres later", "from": "bob_pk"},
    ]
    reason, new_seq = service._should_dispatch("alice", "alice_pk", posts, 2)
    assert reason and "active task" in reason
    assert new_seq == 3


def test_empty_cache_returns_no_trigger() -> None:
    reason, new_seq = service._should_dispatch("alice", "alice_pk", [], 0)
    assert reason is None
    assert new_seq == 0


def test_working_redispatch_after_member_heartbeat() -> None:
    posts = [
        {
            "seq": 1,
            "ts": "2026-06-02T10:00:00Z",
            "text": "@quill #task #content write content",
            "from": "hub_pk",
        },
        {
            "seq": 2,
            "ts": "2026-06-02T10:01:00Z",
            "text": "#working writing content files (write_file)",
            "from": "quill_pk",
        },
    ]
    reason = service._working_redispatch_reason(
        "quill", "quill_pk", posts, "2026-06-02T10:00:30Z", "hub_pk",
    )
    assert reason and "resume after #working" in reason


def test_working_redispatch_not_repeated_for_same_heartbeat() -> None:
    posts = [
        {
            "seq": 1,
            "ts": "2026-06-02T10:00:00Z",
            "text": "@quill #task #content write content",
            "from": "hub_pk",
        },
        {
            "seq": 2,
            "ts": "2026-06-02T10:01:00Z",
            "text": "#working writing content files (write_file)",
            "from": "quill_pk",
        },
    ]
    reason = service._working_redispatch_reason(
        "quill", "quill_pk", posts, "2026-06-02T10:02:00Z", "hub_pk",
    )
    assert reason is None


def test_working_redispatch_ignores_nonparticipant() -> None:
    posts = [
        {
            "seq": 1,
            "ts": "2026-06-02T10:00:00Z",
            "text": "@quill #task #content write content",
            "from": "hub_pk",
        },
        {
            "seq": 2,
            "ts": "2026-06-02T10:01:00Z",
            "text": "#working writing content files (write_file)",
            "from": "quill_pk",
        },
    ]
    reason = service._working_redispatch_reason(
        "pixel", "pixel_pk", posts, "2026-06-02T10:00:30Z", "hub_pk",
    )
    assert reason is None


def test_working_redispatch_allows_same_second_as_dispatch() -> None:
    # #working in the SAME second the dispatch was stamped must still re-dispatch
    # (second-granular timestamps; a strict > would wrongly suppress it).
    posts = [
        {
            "seq": 1, "ts": "2026-06-02T10:00:00Z",
            "text": "@quill #task #content write content", "from": "hub_pk",
        },
        {
            "seq": 2, "ts": "2026-06-02T10:00:30Z",
            "text": "#working writing content files (write_file)", "from": "quill_pk",
        },
    ]
    reason = service._working_redispatch_reason(
        "quill", "quill_pk", posts, "2026-06-02T10:00:30Z", "hub_pk",
    )
    assert reason and "resume after #working" in reason


# Cooldown — `_in_cooldown_str`


def test_cooldown_unset() -> None:
    assert service._in_cooldown_str("") is False


def test_cooldown_recent_true() -> None:
    stamp = _dt.datetime.now(tz=_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    assert service._in_cooldown_str(stamp) is True


def test_cooldown_stale_false() -> None:
    long_ago = _dt.datetime.now(tz=_dt.timezone.utc) - _dt.timedelta(hours=1)
    assert service._in_cooldown_str(long_ago.strftime("%Y-%m-%dT%H:%M:%SZ")) is False


def test_cooldown_robust_to_malformed_timestamp() -> None:
    assert service._in_cooldown_str("not a date") is False


# Responded-seq state — `_get_hub_responded_seq` / `_set_hub_responded_seq`


def test_hub_responded_seq_starts_at_zero(short_tmp: Path) -> None:
    home = short_tmp / "alice"; home.mkdir()
    (home / "alp").mkdir()
    assert service._get_hub_responded_seq(home, "wg_x") == 0


def test_hub_responded_seq_advances_monotonically(short_tmp: Path) -> None:
    home = short_tmp / "alice"; home.mkdir()
    (home / "alp").mkdir()
    service._set_hub_responded_seq(home, "wg_x", 5)
    assert service._get_hub_responded_seq(home, "wg_x") == 5
    service._set_hub_responded_seq(home, "wg_x", 3)  # lower → no-op
    assert service._get_hub_responded_seq(home, "wg_x") == 5
    service._set_hub_responded_seq(home, "wg_x", 10)
    assert service._get_hub_responded_seq(home, "wg_x") == 10


def test_subscription_last_responded_seq_persists(short_tmp: Path) -> None:
    home = short_tmp / "alice"; home.mkdir()
    sub = sub_mod.Subscription(
        wg_id="wg_x", name="x", hub_id="h", hub_pubkey="k",
        last_responded_seq=5,
    )
    sub_mod.upsert(home, sub)
    reloaded = sub_mod.get(home, "wg_x")
    assert reloaded is not None
    assert reloaded.last_responded_seq == 5


# Turn telemetry.


def test_append_turn_event_creates_jsonl_with_0600(short_tmp: Path) -> None:
    """First write creates the file; later writes append JSONL."""
    import json
    import os
    import stat as _stat
    home = short_tmp / "alice"; home.mkdir()
    (home / "alp").mkdir()

    service._append_turn_event(home, {"event": "start", "wg_id": "wg_x"})
    service._append_turn_event(home, {"event": "end", "wg_id": "wg_x", "rc": 0})

    p = service.turn_log_path(home)
    assert p.exists()
    mode = _stat.S_IMODE(os.stat(p).st_mode)
    assert mode == 0o600, f"expected 0600, got {oct(mode)}"

    lines = p.read_text().strip().splitlines()
    assert len(lines) == 2
    a = json.loads(lines[0])
    b = json.loads(lines[1])
    assert a["event"] == "start" and a["wg_id"] == "wg_x"
    assert b["event"] == "end" and b["rc"] == 0


def test_append_turn_event_survives_unwritable_parent(short_tmp: Path) -> None:
    """Telemetry failures are swallowed."""
    home = short_tmp / "alice"; home.mkdir()
    # Make the parent read-only to simulate write failure.
    import os as _os
    (home / "alp").mkdir()
    _os.chmod(home / "alp", 0o500)
    try:
        service._append_turn_event(home, {"event": "start"})
    finally:
        _os.chmod(home / "alp", 0o700)


@pytest.mark.asyncio
async def test_dispatch_records_start_and_end_events(short_tmp: Path) -> None:
    """A clean dispatch writes start and end telemetry."""
    import json
    import sys as _sys
    home = short_tmp / "alice"; home.mkdir()
    (home / "alp").mkdir()

    # Swap the subprocess for a fast no-op Python process.
    real_create = service.asyncio.create_subprocess_exec

    async def fake_create(*argv, **kw):
        # Use a trivial process that emits one event line.
        return await real_create(
            _sys.executable, "-c", "print('{\"kind\":\"tool_start\"}')",
            stdout=service.asyncio.subprocess.PIPE,
            stderr=service.asyncio.subprocess.PIPE,
        )

    service.asyncio.create_subprocess_exec = fake_create
    try:
        await service._dispatch_workgroup_turn(
            home, profile="alice", wg_id="wg_x",
            wg_name="design", reason="test trigger",
        )
    finally:
        service.asyncio.create_subprocess_exec = real_create

    p = service.turn_log_path(home)
    assert p.exists()
    events = [json.loads(l) for l in p.read_text().strip().splitlines()]
    assert len(events) == 2
    assert events[0]["event"] == "start"
    assert events[0]["wg_id"] == "wg_x"
    assert events[0]["wg_name"] == "design"
    assert events[0]["reason"] == "test trigger"
    assert events[0]["pid"] > 0
    assert events[1]["event"] == "end"
    assert events[1]["rc"] == 0
    assert "duration_s" in events[1]
    assert events[1]["posts_added"] == 0
    assert events[1]["event_tail"] == '{"kind":"tool_start"}'


@pytest.mark.asyncio
async def test_dispatch_env_carries_alpi_workspace(short_tmp: Path) -> None:
    import sys as _sys
    home = short_tmp / "alice"; home.mkdir()
    (home / "alp").mkdir()
    ws = home / "ws"
    (home / "config.yaml").write_text(f"workspace: {ws}\n")

    captured: dict = {}
    real_create = service.asyncio.create_subprocess_exec

    async def fake_create(*argv, **kw):
        captured["env"] = kw.get("env") or {}
        return await real_create(
            _sys.executable, "-c", "pass",
            stdout=service.asyncio.subprocess.PIPE,
            stderr=service.asyncio.subprocess.PIPE,
        )

    service.asyncio.create_subprocess_exec = fake_create
    try:
        await service._dispatch_workgroup_turn(
            home, profile="alice", wg_id="wg_x",
            wg_name="design", reason="test trigger",
        )
    finally:
        service.asyncio.create_subprocess_exec = real_create

    assert captured["env"].get("ALPI_WORKSPACE") == str(ws.resolve())
    assert captured["env"].get("ALPI_WORKGROUP_DISPATCH") == "wg_x"


@pytest.mark.asyncio
async def test_dispatch_timeout_kills_and_records(
    short_tmp: Path, monkeypatch,
) -> None:
    """Timeouts are recorded and the child is killed."""
    import json
    import sys as _sys
    home = short_tmp / "alice"; home.mkdir()
    (home / "alp").mkdir()

    # Tighten the test ceilings.
    monkeypatch.setattr(service, "_TURN_TIMEOUT_SECONDS", 0.5)
    monkeypatch.setattr(service, "_TURN_SIGTERM_GRACE_SECONDS", 0.2)

    real_create = service.asyncio.create_subprocess_exec

    async def fake_create(*argv, **kw):
        # Sleep past the ceiling to force timeout.
        return await real_create(
            _sys.executable, "-c",
            "import time; print('{\"kind\":\"tool_state\"}', flush=True); time.sleep(30)",
            stdout=service.asyncio.subprocess.PIPE,
            stderr=service.asyncio.subprocess.PIPE,
        )

    service.asyncio.create_subprocess_exec = fake_create
    try:
        await service._dispatch_workgroup_turn(
            home, profile="alice", wg_id="wg_x",
            wg_name="design", reason="test trigger",
        )
    finally:
        service.asyncio.create_subprocess_exec = real_create

    p = service.turn_log_path(home)
    events = [json.loads(l) for l in p.read_text().strip().splitlines()]
    assert events[0]["event"] == "start"
    assert events[1]["event"] == "timeout"
    assert events[1]["killed"] is True
    assert events[1]["duration_s"] >= 0.5
    assert events[1]["event_tail"] == '{"kind":"tool_state"}'


def test_collective_task_silent_after_hub_done() -> None:
    """A `#task` already closed by the hub does not re-trigger dispatch."""
    posts = [
        {"seq": 1, "text": "#task #arch analyze the architecture", "from": "hub_pk"},
        {"seq": 2, "text": "#done synthesis: pick option A", "from": "hub_pk"},
    ]
    reason, _ = service._should_dispatch("alice", "alice_pk", posts, 0)
    assert reason is None


def test_mention_silent_when_inside_done_post() -> None:
    """A `@<peer>` mention buried in a `#done` body is not a handoff —
    the task is closed; the mention is just part of the synthesis."""
    posts = [
        {"seq": 1, "text": "#task #analyze analyze", "from": "hub_pk"},
        {"seq": 2, "text": "#done @alice owns the writeup", "from": "hub_pk"},
    ]
    reason, _ = service._should_dispatch("alice", "alice_pk", posts, 0)
    assert reason is None


def test_collective_task_still_wakes_when_open_after_substantive() -> None:
    """Regression guard: a `#task` that's still open (no `#done`) must
    keep waking peers even when there are intermediate substantive
    posts. The closed-task gate must not over-shoot."""
    posts = [
        {"seq": 1, "text": "#task #arch analyze the architecture", "from": "hub_pk"},
        {"seq": 2, "text": "first thoughts on the stack", "from": "bob_pk"},
    ]
    reason, _ = service._should_dispatch("alice", "alice_pk", posts, 0)
    assert reason is not None
    assert "task" in reason.lower()


def test_inflight_keyed_by_wg_id_and_profile() -> None:
    """Two profiles can hold independent in-flight locks for the same wg."""
    service._INFLIGHT[("wg_test", "alice")] = {"profile": "alice"}
    service._INFLIGHT[("wg_test", "bob")] = {"profile": "bob"}
    try:
        assert ("wg_test", "alice") in service._INFLIGHT
        assert ("wg_test", "bob") in service._INFLIGHT
        # A profile not currently dispatching is unlocked.
        assert ("wg_test", "carol") not in service._INFLIGHT
    finally:
        service._INFLIGHT.pop(("wg_test", "alice"), None)
        service._INFLIGHT.pop(("wg_test", "bob"), None)


@pytest.mark.asyncio
async def test_dispatch_installs_and_pops_inflight_under_tuple_key(
    short_tmp: Path,
) -> None:
    """The dispatcher installs the lock under `(wg_id, profile)` and
    pops the same key on exit. Captured during the subprocess wait,
    when the lock is live."""
    import asyncio as _asyncio
    import sys as _sys
    home = short_tmp / "alice"; home.mkdir()
    (home / "alp").mkdir()

    captured: dict = {}
    real_create = service.asyncio.create_subprocess_exec

    async def fake_create(*argv, **kw):
        # Sleep briefly so the lock is observable from outside the
        # dispatch coroutine.
        return await real_create(
            _sys.executable, "-c", "import time; time.sleep(0.3)",
            stdout=service.asyncio.subprocess.DEVNULL,
            stderr=service.asyncio.subprocess.PIPE,
        )

    service.asyncio.create_subprocess_exec = fake_create
    try:
        async def watch():
            # Snapshot _INFLIGHT keys mid-flight.
            await _asyncio.sleep(0.1)
            captured["keys"] = list(service._INFLIGHT.keys())

        await _asyncio.gather(
            service._dispatch_workgroup_turn(
                home, profile="alice", wg_id="wg_x",
                wg_name="design", reason="test trigger",
            ),
            watch(),
        )
    finally:
        service.asyncio.create_subprocess_exec = real_create

    # During dispatch, the key was installed as a tuple.
    assert ("wg_x", "alice") in captured["keys"]
    # On exit, the same key was popped.
    assert ("wg_x", "alice") not in service._INFLIGHT


# Pipeline continuation watchdog (ALP.3.H — workflow continuation).

import types as _types


def _pipe_wg(pipeline=True, hub: str = "HUB"):
    # `pipeline` is now an ordered slug list. Map the legacy bool args used
    # across these tests: True → a default phase list, False → empty.
    if pipeline is True:
        pipeline = ("intake", "design", "content")
    elif not pipeline:
        pipeline = ()
    return _types.SimpleNamespace(
        meta=_types.SimpleNamespace(
            id="wg1", name="proj", hub_pubkey=hub, pipeline=tuple(pipeline),
        ),
    )


def test_continuation_due_for_pipeline_after_hub_done() -> None:
    recent = [{"seq": 3, "from": "HUB", "text": "#done verified"}]
    assert service._pipeline_continuation_due(_pipe_wg(True), recent, None) is True


def test_continuation_not_due_for_non_pipeline_workgroup() -> None:
    recent = [{"seq": 3, "from": "HUB", "text": "#done verified"}]
    assert service._pipeline_continuation_due(_pipe_wg(False), recent, None) is False


def test_continuation_not_due_when_member_spoke_last() -> None:
    recent = [{"seq": 3, "from": "SCOUT", "text": "some content"}]
    assert service._pipeline_continuation_due(_pipe_wg(True), recent, None) is False


def test_continuation_not_due_when_last_hub_post_not_done() -> None:
    recent = [{"seq": 3, "from": "HUB", "text": "thinking about it"}]
    assert service._pipeline_continuation_due(_pipe_wg(True), recent, None) is False


def test_continuation_not_due_when_task_still_open() -> None:
    recent = [{"seq": 3, "from": "HUB", "text": "#done verified"}]
    active = _types.SimpleNamespace()  # any non-None = a task is open
    assert service._pipeline_continuation_due(_pipe_wg(True), recent, active) is False


@pytest.mark.asyncio
async def test_watchdog_dispatches_pipeline_continuation_once(
    short_tmp: Path, monkeypatch,
) -> None:
    home = short_tmp / "mira"; home.mkdir()
    old = (
        _dt.datetime.now(tz=_dt.timezone.utc) - _dt.timedelta(minutes=10)
    ).strftime("%Y-%m-%dT%H:%M:%SZ")
    recent = [
        {"seq": 1, "from": "HUB", "text": "@scout #task #intake go", "ts": old},
        {"seq": 2, "from": "SCOUT", "text": "intake on disk", "ts": old},
        {"seq": 3, "from": "HUB", "text": "#done verified", "ts": old},
    ]
    calls: list[dict] = []

    def fake_dispatch(*a, **kw):
        calls.append(kw)
        async def _noop():
            return None
        return _noop()

    spawned: list[str] = []

    def fake_spawn(wg_id, coro):
        spawned.append(wg_id)
        coro.close()

    monkeypatch.setattr(service, "_dispatch_workgroup_turn", fake_dispatch)
    monkeypatch.setattr(service, "_spawn_dispatch", fake_spawn)
    monkeypatch.setattr(service, "_latest_hub_task_seq_for", lambda *a, **k: 0)

    await service._maybe_watchdog_close(home, "mira", _pipe_wg(True), recent)
    assert spawned == ["wg1"]
    assert calls and calls[0].get("continuation") is True
    assert calls[0].get("closure_only", False) is False
    assert calls[0].get("pipeline") is True  # longer turn budget plumbed
    assert calls[0].get("next_phase") == "design"  # core computed the next slug

    # Same state again → no redispatch (already fired for seq 3 + cooldown).
    await service._maybe_watchdog_close(home, "mira", _pipe_wg(True), recent)
    assert spawned == ["wg1"]


@pytest.mark.asyncio
async def test_watchdog_no_continuation_for_non_pipeline(
    short_tmp: Path, monkeypatch,
) -> None:
    home = short_tmp / "vera"; home.mkdir()
    old = (
        _dt.datetime.now(tz=_dt.timezone.utc) - _dt.timedelta(minutes=10)
    ).strftime("%Y-%m-%dT%H:%M:%SZ")
    recent = [
        {"seq": 1, "from": "HUB", "text": "#task #adr decide", "ts": old},
        {"seq": 2, "from": "BOB", "text": "my take", "ts": old},
        {"seq": 3, "from": "HUB", "text": "#done synthesis", "ts": old},
    ]
    spawned: list[str] = []
    monkeypatch.setattr(service, "_spawn_dispatch", lambda *a, **k: spawned.append(a))
    monkeypatch.setattr(service, "_latest_hub_task_seq_for", lambda *a, **k: 0)
    await service._maybe_watchdog_close(home, "vera", _pipe_wg(False), recent)
    assert spawned == []


@pytest.mark.asyncio
async def test_continuation_prompt_permits_task_not_closure_only(
    short_tmp: Path, monkeypatch,
) -> None:
    home = short_tmp / "mira2"; home.mkdir()
    captured: dict = {}

    async def fake_exec(*argv, env=None, **kw):
        captured["argv"] = argv
        captured["env"] = env or {}
        raise OSError("blocked in test")

    monkeypatch.setattr(service.asyncio, "create_subprocess_exec", fake_exec)
    await service._dispatch_workgroup_turn(
        home, "mira", "wg1", "proj", "task closed", continuation=True,
    )
    prompt = captured["argv"][-1]
    assert "#task" in prompt
    assert "ALPI_WORKGROUP_CLOSURE_ONLY" not in captured["env"]


@pytest.mark.asyncio
async def test_closure_prompt_sets_closure_only_env(
    short_tmp: Path, monkeypatch,
) -> None:
    home = short_tmp / "mira3"; home.mkdir()
    captured: dict = {}

    async def fake_exec(*argv, env=None, **kw):
        captured["env"] = env or {}
        raise OSError("blocked in test")

    monkeypatch.setattr(service.asyncio, "create_subprocess_exec", fake_exec)
    await service._dispatch_workgroup_turn(
        home, "mira", "wg1", "proj", "stalled", closure_only=True,
    )
    assert captured["env"].get("ALPI_WORKGROUP_CLOSURE_ONLY") == "1"


@pytest.mark.asyncio
async def test_watchdog_repair_mode_on_second_nudge_for_pipeline(
    short_tmp: Path, monkeypatch,
) -> None:
    """First closure nudge is closure-only; a second nudge on the same
    stalled seq in a pipeline workgroup escalates to REPAIR (normal mode,
    can re-task) instead of burning closure-only turns forever."""
    home = short_tmp / "mirar"; home.mkdir()
    old = (
        _dt.datetime.now(tz=_dt.timezone.utc) - _dt.timedelta(minutes=10)
    ).strftime("%Y-%m-%dT%H:%M:%SZ")
    recent = [
        {"seq": 1, "from": "HUB", "text": "@atlas #task #seo produce keywords", "ts": old},
        {"seq": 2, "from": "ATLAS", "text": "wrote seo/keywords-es.yaml", "ts": old},
    ]
    calls: list[dict] = []

    def fake_dispatch(*a, **kw):
        calls.append(kw)
        async def _noop():
            return None
        return _noop()

    monkeypatch.setattr(service, "_dispatch_workgroup_turn", fake_dispatch)
    monkeypatch.setattr(
        service, "_spawn_dispatch",
        lambda wid, coro: (None, coro.close())[0],
    )
    monkeypatch.setattr(service, "_latest_hub_task_seq_for", lambda *a, **k: 0)
    wg = _pipe_wg(True)

    # First nudge → closure-only.
    await service._maybe_watchdog_close(home, "mira", wg, recent)
    assert calls and calls[0].get("closure_only") is True

    # Age the last-dispatch stamp so the 5-min refire guard passes.
    st = service._load_poller_state(home)
    sixmin = (
        _dt.datetime.now(tz=_dt.timezone.utc) - _dt.timedelta(minutes=6)
    ).strftime("%Y-%m-%dT%H:%M:%SZ")
    st.setdefault("hub_last_dispatch_at", {})[wg.meta.id] = sixmin
    service._save_poller_state(home, st)

    # Second nudge on the same seq → repair (normal mode, not closure-only).
    await service._maybe_watchdog_close(home, "mira", wg, recent)
    assert len(calls) == 2
    assert calls[1].get("closure_only") is False
    assert calls[1].get("pipeline") is True

    # Third nudge on the same seq → FINAL REPAIR (still normal mode): one last
    # deterministic close-or-BLOCK wake before the task is abandoned. This is
    # the lost-handoff safety net — a green artifact can be on disk while the
    # member's `#done` was stripped.
    sixmin2 = (
        _dt.datetime.now(tz=_dt.timezone.utc) - _dt.timedelta(minutes=6)
    ).strftime("%Y-%m-%dT%H:%M:%SZ")
    st = service._load_poller_state(home)
    st.setdefault("hub_last_dispatch_at", {})[wg.meta.id] = sixmin2
    service._save_poller_state(home, st)
    await service._maybe_watchdog_close(home, "mira", wg, recent)
    assert len(calls) == 3
    assert calls[2].get("closure_only") is False

    # Fourth nudge on the same seq → capped: both recovery wakes spent, no
    # further dispatch (wg.blocked stays the visible state until the transcript
    # moves).
    sentinel = (
        _dt.datetime.now(tz=_dt.timezone.utc) - _dt.timedelta(minutes=6)
    ).strftime("%Y-%m-%dT%H:%M:%SZ")
    st = service._load_poller_state(home)
    st.setdefault("hub_last_dispatch_at", {})[wg.meta.id] = sentinel
    service._save_poller_state(home, st)
    await service._maybe_watchdog_close(home, "mira", wg, recent)
    assert len(calls) == 3
    # Capped path does NOT dispatch, so it must NOT touch hub_last_dispatch_at
    # (otherwise it injects a fake cooldown that delays a real later dispatch).
    st2 = service._load_poller_state(home)
    assert st2["hub_last_dispatch_at"][wg.meta.id] == sentinel


@pytest.mark.asyncio
async def test_watchdog_no_repair_for_non_pipeline(
    short_tmp: Path, monkeypatch,
) -> None:
    """A non-pipeline workgroup stays closure-only even on the 2nd nudge."""
    home = short_tmp / "verar"; home.mkdir()
    old = (
        _dt.datetime.now(tz=_dt.timezone.utc) - _dt.timedelta(minutes=10)
    ).strftime("%Y-%m-%dT%H:%M:%SZ")
    recent = [
        {"seq": 1, "from": "HUB", "text": "#task #adr decide", "ts": old},
        {"seq": 2, "from": "BOB", "text": "my take", "ts": old},
    ]
    calls: list[dict] = []

    def fake_dispatch(*a, **kw):
        calls.append(kw)
        async def _noop():
            return None
        return _noop()

    monkeypatch.setattr(service, "_dispatch_workgroup_turn", fake_dispatch)
    monkeypatch.setattr(
        service, "_spawn_dispatch",
        lambda wid, coro: (None, coro.close())[0],
    )
    monkeypatch.setattr(service, "_latest_hub_task_seq_for", lambda *a, **k: 0)
    wg = _pipe_wg(False)

    await service._maybe_watchdog_close(home, "vera", wg, recent)
    st = service._load_poller_state(home)
    sixmin = (
        _dt.datetime.now(tz=_dt.timezone.utc) - _dt.timedelta(minutes=6)
    ).strftime("%Y-%m-%dT%H:%M:%SZ")
    st.setdefault("hub_last_dispatch_at", {})[wg.meta.id] = sixmin
    service._save_poller_state(home, st)
    await service._maybe_watchdog_close(home, "vera", wg, recent)
    assert len(calls) == 2
    assert calls[1].get("closure_only") is True


def test_turn_timeout_longer_for_pipeline() -> None:
    """Pipeline workgroups get the longer production wall-clock budget;
    deliberation workgroups keep the short convergence budget."""
    assert service._turn_timeout_for(True) == service._PIPELINE_TURN_TIMEOUT_SECONDS
    assert service._turn_timeout_for(True) == 900
    assert service._turn_timeout_for(False) == service._TURN_TIMEOUT_SECONDS
    assert service._turn_timeout_for(False) == 300


@pytest.mark.asyncio
async def test_continuation_bounded_retry_then_stops(
    short_tmp: Path, monkeypatch,
) -> None:
    """Continuation retries a bounded number of times per `#done` seq —
    enough to recover from a wake that whiffed (didn't open the next task)
    — then stops (never the unbounded every-5-min re-fire of the original
    bug)."""
    home = short_tmp / "mirac"; home.mkdir()
    old = (
        _dt.datetime.now(tz=_dt.timezone.utc) - _dt.timedelta(minutes=10)
    ).strftime("%Y-%m-%dT%H:%M:%SZ")
    recent = [
        {"seq": 1, "from": "HUB", "text": "@scout #task #intake go", "ts": old},
        {"seq": 2, "from": "SCOUT", "text": "intake done", "ts": old},
        {"seq": 3, "from": "HUB", "text": "#done verified", "ts": old},
    ]
    calls: list[dict] = []

    def fake_dispatch(*a, **kw):
        calls.append(kw)
        async def _noop():
            return None
        return _noop()

    monkeypatch.setattr(service, "_dispatch_workgroup_turn", fake_dispatch)
    monkeypatch.setattr(
        service, "_spawn_dispatch", lambda wid, coro: (None, coro.close())[0],
    )
    monkeypatch.setattr(service, "_latest_hub_task_seq_for", lambda *a, **k: 0)
    wg = _pipe_wg(True)

    def age_last_dispatch():
        st = service._load_poller_state(home)
        st.setdefault("hub_last_dispatch_at", {})[wg.meta.id] = (
            _dt.datetime.now(tz=_dt.timezone.utc) - _dt.timedelta(minutes=6)
        ).strftime("%Y-%m-%dT%H:%M:%SZ")
        service._save_poller_state(home, st)

    # Fires up to _CONTINUATION_MAX_FIRES times on the same seq...
    for _ in range(service._CONTINUATION_MAX_FIRES + 3):
        await service._maybe_watchdog_close(home, "mira", wg, recent)
        age_last_dispatch()
    assert len(calls) == service._CONTINUATION_MAX_FIRES
    assert all(c.get("continuation") is True for c in calls)
    # After the cap, the count does NOT keep growing — capped ticks must
    # not bump/write `poller_state` each poll (it stays at the cap value).
    seq_stored, count_stored = service._continuation_state(home, wg.meta.id)
    assert (seq_stored, count_stored) == (3, service._CONTINUATION_MAX_FIRES)


def test_next_pipeline_phase_deterministic() -> None:
    """The core computes the next phase from the ordered list + the latest
    closed slug — no guessing, no LLM."""
    wg = _pipe_wg(["intake", "design", "content", "translation"])
    # closed `intake` → next is `design`
    recent = [
        {"seq": 1, "from": "HUB", "text": "@scout #task #intake go"},
        {"seq": 2, "from": "HUB", "text": "#done intake verified"},
    ]
    nxt, latest, known = service._next_pipeline_phase(wg, recent)
    assert (nxt, latest, known) == ("design", "intake", True)


def test_next_pipeline_phase_complete_and_unknown() -> None:
    wg = _pipe_wg(["intake", "design"])
    # closed the LAST phase → no successor
    recent = [
        {"seq": 1, "from": "HUB", "text": "@canvas #task #design go"},
        {"seq": 2, "from": "HUB", "text": "#done design verified"},
    ]
    assert service._next_pipeline_phase(wg, recent) == (None, "design", True)
    # closed a slug NOT in the pipeline → unknown, do not guess
    recent2 = [
        {"seq": 1, "from": "HUB", "text": "#task #build-blockers fix it"},
        {"seq": 2, "from": "HUB", "text": "#done build-blockers"},
    ]
    assert service._next_pipeline_phase(wg, recent2) == (None, "build-blockers", False)


def test_next_pipeline_phase_ignores_offpipeline_variant() -> None:
    """A re-task with a variant slug (`#build-recheck`) doesn't break
    continuation — the next phase is computed from the latest CANONICAL
    phase closed (`build` → `qa`)."""
    wg = _pipe_wg(["intake", "design", "content", "translation", "seo", "build", "qa"])
    recent = [
        {"seq": 1, "from": "HUB", "text": "@pixel #task #build wire it"},
        {"seq": 2, "from": "HUB", "text": "@pixel #task #build-recheck re-verify"},  # preempts #build
        {"seq": 3, "from": "PIXEL", "text": "@mira build complete"},
        {"seq": 4, "from": "HUB", "text": "#done build verified"},
    ]
    nxt, latest, known = service._next_pipeline_phase(wg, recent)
    assert (nxt, latest, known) == ("qa", "build", True)


def test_next_pipeline_phase_terminal_fail_reopens_rebuild() -> None:
    """A terminal-phase (qa) FAIL must not complete the pipeline. When qa was
    superseded by a fix-loop (an off-pipeline `*-fix` opened after it), reopen
    the phase BEFORE the terminal (build) so qa re-audits a fresh artifact."""
    wg = _pipe_wg(["intake", "content", "translation", "build", "qa"])
    recent = [
        {"seq": 1, "from": "HUB", "text": "@pixel #task #build wire it"},
        {"seq": 2, "from": "PIXEL", "text": "@hub build done"},
        {"seq": 3, "from": "HUB", "text": "#done build green"},
        {"seq": 4, "from": "HUB", "text": "@lens #task #qa audit dist"},
        {"seq": 5, "from": "LENS", "text": "FAIL placeholder content"},
        {"seq": 6, "from": "HUB", "text": "@quill #task #content-fix remove placeholders"},
        {"seq": 7, "from": "QUILL", "text": "@hub fixed"},
        {"seq": 8, "from": "HUB", "text": "#done content-fix"},
    ]
    nxt, latest, known = service._next_pipeline_phase(wg, recent)
    assert (nxt, latest, known) == ("build", "qa", True)


def test_next_pipeline_phase_terminal_recheck_green_completes() -> None:
    wg = _pipe_wg(["intake", "content", "translation", "build", "qa"])
    recent = [
        {"seq": 1, "from": "HUB", "text": "@pixel #task #build wire it"},
        {"seq": 2, "from": "HUB", "text": "#done build green"},
        {"seq": 3, "from": "HUB", "text": "@lens #task #qa audit dist"},
        {"seq": 4, "from": "LENS", "text": "FAIL placeholder content"},
        {"seq": 5, "from": "HUB", "text": "@quill #task #content-fix remove placeholders"},
        {"seq": 6, "from": "HUB", "text": "#done content-fix verified"},
        {"seq": 7, "from": "HUB", "text": "@pixel #task #build-recheck rebuild"},
        {"seq": 8, "from": "HUB", "text": "#done build-recheck verified"},
        {"seq": 9, "from": "HUB", "text": "@lens #task #qa-recheck re-audit"},
        {"seq": 10, "from": "HUB", "text": "#done QA green / PASS"},
    ]
    nxt, latest, known = service._next_pipeline_phase(wg, recent)
    assert (nxt, latest, known) == (None, "qa", True)


def test_canonical_pipeline_slug_maps_variants() -> None:
    pipe = ["intake", "content", "build", "qa"]
    assert service._canonical_pipeline_slug("qa", pipe) == "qa"
    assert service._canonical_pipeline_slug("qa-recheck", pipe) == "qa"
    assert service._canonical_pipeline_slug("content-fix", pipe) == "content"
    assert service._canonical_pipeline_slug("design", pipe) is None
    # Longest-prefix wins so a `qa-final` phase isn't shadowed by `qa`.
    assert service._canonical_pipeline_slug("qa-final-recheck", ["qa", "qa-final"]) == "qa-final"


def test_is_success_result() -> None:
    assert service._is_success_result("QA green / PASS")
    assert service._is_success_result("verde")
    assert service._is_success_result("verified · dist ok")
    # Negatives win even when "pass"/"green" appear in the text.
    assert not service._is_success_result("FAIL placeholder content")
    assert not service._is_success_result("preempted by #content-fix")
    assert not service._is_success_result("did not pass")
    assert not service._is_success_result("not passing yet")
    assert not service._is_success_result("FAIL: pass criteria not met")
    assert not service._is_success_result("BLOCKED · qa · green build missing")


def test_next_pipeline_phase_terminal_pass_completes() -> None:
    """A clean terminal pass (qa #done, no fix-loop after) completes — no reopen."""
    wg = _pipe_wg(["intake", "content", "translation", "build", "qa"])
    recent = [
        {"seq": 1, "from": "HUB", "text": "@pixel #task #build wire it"},
        {"seq": 2, "from": "HUB", "text": "#done build green"},
        {"seq": 3, "from": "HUB", "text": "@lens #task #qa audit dist"},
        {"seq": 4, "from": "LENS", "text": "@hub PASS all green"},
        {"seq": 5, "from": "HUB", "text": "#done qa green"},
    ]
    nxt, latest, known = service._next_pipeline_phase(wg, recent)
    assert (nxt, latest, known) == (None, "qa", True)


def test_next_pipeline_phase_blocked_halts_mid_pipeline() -> None:
    """`#done BLOCKED · ...` mid-pipeline halts — it must NOT advance to the
    next phase with incomplete data (a translation block doesn't go to build)."""
    wg = _pipe_wg(["intake", "content", "translation", "build", "qa"])
    recent = [
        {"seq": 1, "from": "HUB", "text": "@lingua #task #translation translate all"},
        {"seq": 2, "from": "LINGUA", "text": "@hub de,nl x 5 entries"},
        {"seq": 3, "from": "HUB", "text": "#done BLOCKED · translation · @lingua · missing de/nl files"},
    ]
    assert service._next_pipeline_phase(wg, recent) == (None, "translation", True)


def test_next_pipeline_phase_blocked_on_variant_halts_over_fixloop() -> None:
    """`#done BLOCKED` lands on an off-pipeline variant (`#qa-recheck`) and still
    halts — overriding the terminal-fail reopen guardrail. An explicit block
    stops the pipeline; it does not bounce back to build."""
    wg = _pipe_wg(["intake", "content", "translation", "build", "qa"])
    recent = [
        {"seq": 1, "from": "HUB", "text": "@pixel #task #build wire it"},
        {"seq": 2, "from": "HUB", "text": "#done build green"},
        {"seq": 3, "from": "HUB", "text": "@lens #task #qa audit"},
        {"seq": 4, "from": "LENS", "text": "FAIL template i18n leak"},
        {"seq": 5, "from": "HUB", "text": "@pixel #task #build-fix re-render"},
        {"seq": 6, "from": "HUB", "text": "#done build-fix"},
        {"seq": 7, "from": "HUB", "text": "@lens #task #qa-recheck re-audit"},
        {"seq": 8, "from": "LENS", "text": "FAIL still leaking zh-Hans"},
        {"seq": 9, "from": "HUB", "text": "#done BLOCKED · template · zh-Hans chrome leak"},
    ]
    assert service._next_pipeline_phase(wg, recent) == (None, "qa-recheck", True)


# `_supervise_turn` — idle-based kill (ALP.3.I-a).


class _FakeProc:

    def __init__(self) -> None:
        self.pid = 4321
        self.signals: list[str] = []
        self._exit: asyncio.Future[int] = asyncio.Future()

    async def wait(self) -> int:
        return await self._exit

    def terminate(self) -> None:
        self.signals.append("term")
        if not self._exit.done():
            self._exit.set_result(-15)

    def kill(self) -> None:
        self.signals.append("kill")
        if not self._exit.done():
            self._exit.set_result(-9)

    def exit(self, rc: int = 0) -> None:
        if not self._exit.done():
            self._exit.set_result(rc)


@pytest.mark.asyncio
async def test_supervise_turn_active_survives_to_natural_exit() -> None:
    proc = _FakeProc()
    start = time.monotonic()
    last = [start]

    async def driver() -> None:
        for _ in range(8):  # bump every 50ms < idle(300ms) for ~0.4s
            await asyncio.sleep(0.05)
            last[0] = time.monotonic()
        proc.exit(0)

    drv = asyncio.ensure_future(driver())
    rc, timed_out, reason = await service._supervise_turn(
        proc, last, idle_timeout=0.3, backstop=5.0, started_at=start,
    )
    await drv
    assert (rc, timed_out, reason) == (0, False, None)
    assert proc.signals == []  # never signalled


@pytest.mark.asyncio
async def test_supervise_turn_idle_kills_silent_turn() -> None:
    proc = _FakeProc()
    start = time.monotonic()
    last = [start]
    rc, timed_out, reason = await service._supervise_turn(
        proc, last, idle_timeout=0.2, backstop=5.0, started_at=start,
    )
    assert timed_out and reason == "idle"
    assert "term" in proc.signals
    assert time.monotonic() - start < 1.0  # prompt, well before backstop


@pytest.mark.asyncio
async def test_supervise_turn_backstop_caps_noisy_turn() -> None:
    proc = _FakeProc()
    start = time.monotonic()
    last = [start]
    stop = asyncio.Event()

    async def noisy() -> None:
        while not stop.is_set():
            await asyncio.sleep(0.05)
            last[0] = time.monotonic()

    drv = asyncio.ensure_future(noisy())
    try:
        rc, timed_out, reason = await service._supervise_turn(
            proc, last, idle_timeout=1.0, backstop=0.4, started_at=start,
        )
    finally:
        stop.set()
        await drv
    assert timed_out and reason == "backstop"
    assert 0.3 < time.monotonic() - start < 1.0  # killed at backstop, not idle


@pytest.mark.asyncio
async def test_kill_proc_escalates_to_sigkill(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(service, "_TURN_SIGTERM_GRACE_SECONDS", 0.1)
    proc = _FakeProc()
    proc.terminate = lambda: proc.signals.append("term")  # swallow SIGTERM
    wait_task: asyncio.Future[int] = asyncio.ensure_future(proc.wait())
    rc = await service._kill_proc(proc, wait_task)
    assert proc.signals == ["term", "kill"]
    assert rc == -9


@pytest.mark.asyncio
async def test_stdout_activity_keeps_turn_alive_via_drain() -> None:
    from alpi._proc_io import drain_tail

    reader = asyncio.StreamReader()
    proc = _FakeProc()
    start = time.monotonic()
    last = [start]
    drain = asyncio.ensure_future(
        drain_tail(reader, on_activity=lambda: last.__setitem__(0, time.monotonic())),
    )

    async def feeder() -> None:
        for i in range(8):  # a line every 50ms < idle(0.3) for ~0.4s
            await asyncio.sleep(0.05)
            reader.feed_data(f"{{\"kind\": \"tool_state\", \"name\": \"terminal\"}} {i}\n".encode())
        reader.feed_eof()
        proc.exit(0)

    feed = asyncio.ensure_future(feeder())
    rc, timed_out, reason = await service._supervise_turn(
        proc, last, idle_timeout=0.3, backstop=5.0, started_at=start,
    )
    await feed
    await drain
    assert (rc, timed_out, reason) == (0, False, None)
    assert proc.signals == []  # never killed — stdout activity kept it alive


def test_turn_idle_timeout_for_pipeline_is_wider() -> None:
    assert service._turn_idle_timeout_for(True) > service._turn_idle_timeout_for(False)


# Paused workgroups run no automatic turns (control-plane gate).


def test_subscription_paused_round_trips(short_tmp: Path) -> None:
    home = short_tmp / "mira"; home.mkdir()
    (home / "alp").mkdir()
    sub = sub_mod.Subscription(
        wg_id="wg_x", name="x", hub_id="h", hub_pubkey="k", paused=True,
    )
    sub_mod.upsert(home, sub)
    reloaded = sub_mod.get(home, "wg_x")
    assert reloaded is not None and reloaded.paused is True


def _fake_hub_wg(paused: bool):
    from types import SimpleNamespace
    return SimpleNamespace(meta=SimpleNamespace(
        paused=paused, hub_pubkey="hub_pk", id="wg_x", name="proj-x", pipeline=(),
    ))


@pytest.mark.asyncio
async def test_watchdog_skips_paused_workgroup(short_tmp: Path, monkeypatch) -> None:
    calls: list = []
    monkeypatch.setattr(service, "_spawn_dispatch", lambda *a, **k: calls.append(a))
    wg = _fake_hub_wg(paused=True)
    recent = [{"seq": 1, "from": "hub_pk", "text": "#task #x do it"}]  # open task → would normally nudge
    await service._maybe_watchdog_close(short_tmp, "mira", wg, recent)
    assert calls == []


@pytest.mark.asyncio
async def test_hub_dispatch_skips_paused_workgroup(short_tmp: Path, monkeypatch) -> None:
    calls: list = []
    monkeypatch.setattr(service, "_spawn_dispatch", lambda *a, **k: calls.append(a))
    wg = _fake_hub_wg(paused=True)
    recent = [{"seq": 1, "from": "peer_pk", "text": "@mira please act"}]
    await service._maybe_dispatch_for_hub(short_tmp, "mira", wg, recent)
    assert calls == []


@pytest.mark.asyncio
async def test_member_dispatch_skips_paused_sub(short_tmp: Path, monkeypatch) -> None:
    from types import SimpleNamespace
    calls: list = []
    monkeypatch.setattr(service, "_spawn_dispatch", lambda *a, **k: calls.append(a))
    sub = SimpleNamespace(
        paused=True, wg_id="wg_x", hub_pubkey="hub_pk", last_responded_seq=0,
        recent_posts=[{"seq": 1, "from": "hub_pk", "text": "@quill #task #content go"}],
    )
    await service._maybe_dispatch_for_sub(short_tmp, "quill", sub)
    assert calls == []


def test_resume_resets_poller_state_for_wg(short_tmp: Path) -> None:
    home = short_tmp / "mira"; home.mkdir()
    service._set_hub_watchdog_seq(home, "wg_x", 7)
    service._bump_hub_watchdog_count(home, "wg_x", 7)
    service._set_hub_responded_seq(home, "wg_x", 7)
    service._bump_hub_continuation_count(home, "wg_x", 5)
    service._mark_hub_dispatched(home, "wg_x")
    service._set_hub_watchdog_seq(home, "wg_y", 3)  # bystander

    service.reset_workgroup_poller_state(home, "wg_x")

    st = service._load_poller_state(home)
    for table in service._RESUMABLE_POLLER_TABLES:
        assert "wg_x" not in st.get(table, {}), table
    # re-fireable on the same seq after resume
    assert service._get_hub_watchdog_seq(home, "wg_x") == 0
    assert service._get_hub_responded_seq(home, "wg_x") == 0
    # other workgroup untouched
    assert st.get("hub_watchdog_fired_seq", {}).get("wg_y") == 3
    assert service._get_hub_watchdog_seq(home, "wg_y") == 3


def test_poller_start_offset_is_deterministic_and_staggered() -> None:
    a1 = service._poller_start_offset("quill")
    a2 = service._poller_start_offset("quill")
    assert a1 == a2  # deterministic across restarts
    assert 0.0 <= a1 < service.WORKGROUP_TICK_SECONDS
    spread = {
        service._poller_start_offset(p)
        for p in ("quill", "muse", "lens", "scout", "mira", "atlas")
    }
    assert len(spread) >= 4  # distinct profiles land on distinct offsets


@pytest.mark.asyncio
async def test_poller_yields_between_subs(monkeypatch) -> None:
    import types
    from alpi.alp import subscription as sub_mod
    from alpi.alp import workgroup as wg_mod
    from alpi.alp import workgroup_client as wc

    subs = [types.SimpleNamespace(wg_id=f"wg{i}") for i in range(10)]
    beats = {"n": 0}
    samples: list[int] = []

    async def fake_pull(home, wg_id):
        samples.append(beats["n"])  # local hubs resolve with no real I/O yield
        return [], None

    monkeypatch.setattr(service, "_poller_start_offset", lambda _p: 0.0)
    monkeypatch.setattr(sub_mod, "load", lambda home: subs)
    monkeypatch.setattr(sub_mod, "get", lambda home, wid: types.SimpleNamespace(wg_id=wid))
    monkeypatch.setattr(wc, "pull", fake_pull)
    monkeypatch.setattr(wg_mod, "list_workgroups", lambda home: [])

    async def fake_dispatch(home, profile, sub):
        return None

    monkeypatch.setattr(service, "_maybe_dispatch_for_sub", fake_dispatch)

    async def heartbeat() -> None:
        while True:
            beats["n"] += 1
            await asyncio.sleep(0)

    hb = asyncio.create_task(heartbeat())
    poller = asyncio.create_task(
        service._run_workgroup_poller(Path("/tmp/does-not-matter"), "alice")
    )
    try:
        # Stop after one tick's sub loop, before the 30s sleep, so samples are in-tick only.
        for _ in range(200):
            await asyncio.sleep(0)
            if len(samples) >= len(subs):
                break
    finally:
        poller.cancel()
        hb.cancel()

    assert len(samples) == len(subs)
    # Heartbeat advanced while the poller walked its subs → it yielded per sub.
    assert samples[-1] - samples[0] >= 5


def test_wg_backoff_schedule() -> None:
    # Steady cadence for the first ticks, then exponential backoff capped.
    assert service._wg_backoff_mult(0) == 1
    assert service._wg_backoff_mult(2) == 1
    assert service._wg_backoff_mult(3) == 2
    assert service._wg_backoff_mult(4) == service._WG_POLL_BACKOFF_MAX
    assert service._wg_backoff_mult(5) == service._WG_POLL_BACKOFF_MAX  # capped
    assert service._wg_backoff_mult(99) == service._WG_POLL_BACKOFF_MAX
    base = service.WORKGROUP_TICK_SECONDS
    assert base * service._wg_backoff_mult(99) <= 120  # dormant wg still polled >= every 2 min


def test_hub_transcript_decrypt_is_cached_by_mtime(short_tmp: Path, monkeypatch) -> None:
    import json as _json
    import types
    from alpi.alp import keys as keys_mod
    from alpi.alp import workgroup as wg_mod

    home = short_tmp / "mira"
    (home / "alp" / "workgroups" / "wg_x").mkdir(parents=True)
    tpath = home / "alp" / "workgroups" / "wg_x" / "transcript.jsonl"
    tpath.write_text(
        _json.dumps({"key_version": 1, "nonce": "n", "ciphertext": "c", "seq": 1}) + "\n",
    )

    fake_kp = types.SimpleNamespace(pubkey_b64=lambda: "me")
    monkeypatch.setattr(keys_mod, "load_or_generate", lambda _home: fake_kp)
    wg = types.SimpleNamespace(meta=types.SimpleNamespace(id="wg_x"), member=lambda _pk: object())
    monkeypatch.setattr(wg_mod, "hub_group_keys", lambda _h, _w, _k: {1: b"k"})
    calls = {"n": 0}

    def fake_decrypt(_group_key, _nonce, _ct):
        calls["n"] += 1
        return b"hello"

    monkeypatch.setattr(wg_mod, "decrypt_post", fake_decrypt)
    service._HUB_DECRYPT_CACHE.clear()

    a = service._all_hub_posts_decrypted(home, wg)
    b = service._all_hub_posts_decrypted(home, wg)
    assert calls["n"] == 1  # second call served from cache, no re-decrypt
    assert a == b and len(a) == 1 and a[0]["text"] == "hello"

    tpath.write_text(
        _json.dumps({"key_version": 1, "nonce": "n", "ciphertext": "c", "seq": 1}) + "\n"
        + _json.dumps({"key_version": 1, "nonce": "n2", "ciphertext": "c2", "seq": 2}) + "\n",
    )
    c = service._all_hub_posts_decrypted(home, wg)
    assert calls["n"] == 3  # transcript changed → re-decrypted both posts
    assert len(c) == 2


def test_sub_with_open_task_stays_hot_no_backoff() -> None:
    import types
    open_task = [{"seq": 1, "from": "hub_pk", "text": "@quill #task #x do it"}]
    closed = open_task + [{"seq": 2, "from": "hub_pk", "text": "#done shipped"}]
    # Open task → keep base cadence even with no new posts (peer wakeup + #working recovery).
    assert service._sub_stays_hot([], types.SimpleNamespace(recent_posts=open_task)) is True
    # Resolved (all #done) → eligible to back off.
    assert service._sub_stays_hot([], types.SimpleNamespace(recent_posts=closed)) is False
    # A fresh post is always hot, regardless of task state.
    assert service._sub_stays_hot([{"seq": 9}], types.SimpleNamespace(recent_posts=[])) is True
    # Missing/None cache must not crash.
    assert service._sub_stays_hot([], None) is False


def test_sub_stays_hot_ignores_member_authored_markers() -> None:
    import types
    # hub_pubkey makes a member's own "#done" prose non-closing, so the task stays open.
    posts = [
        {"seq": 1, "from": "hub_pk", "text": "@quill #task #x do it"},
        {"seq": 2, "from": "quill_pk", "text": "are we #done with this?"},
    ]
    sub = types.SimpleNamespace(recent_posts=posts, hub_pubkey="hub_pk")
    assert service._sub_stays_hot([], sub) is True
    # The hub's own #done genuinely closes it → eligible to back off.
    closed = posts + [{"seq": 3, "from": "hub_pk", "text": "#done shipped"}]
    assert service._sub_stays_hot([], types.SimpleNamespace(recent_posts=closed, hub_pubkey="hub_pk")) is False
