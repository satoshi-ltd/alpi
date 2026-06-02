"""Workgroup poller tests."""

from __future__ import annotations

import datetime as _dt
import shutil
import tempfile
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
        # Use a trivial `python -c "pass"` command.
        return await real_create(
            _sys.executable, "-c", "pass",
            stdout=service.asyncio.subprocess.DEVNULL,
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
            _sys.executable, "-c", "import time; time.sleep(30)",
            stdout=service.asyncio.subprocess.DEVNULL,
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
