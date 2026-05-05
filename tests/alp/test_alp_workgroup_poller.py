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
        {"seq": 1, "text": "#task research peptides", "from": "user_pk"},
    ]
    reason, _ = service._should_dispatch("bob", "bob_pk", posts, 0)
    assert reason and "collective" in reason


def test_targeted_task_does_not_wake_unmentioned_peer() -> None:
    """A task aimed at @alice must not wake bob."""
    posts = [
        {"seq": 1, "text": "#task @alice take lit review", "from": "user_pk"},
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
        {"seq": 1, "text": "#task @alice take lit review", "from": "user_pk"},
    ]
    reason, _ = service._should_dispatch("alice", "alice_pk", posts, 0)
    assert reason and "@alice mentioned" in reason


def test_participant_in_active_task_wakes_on_latest_other_post() -> None:
    """Named tasks keep waking on later peer replies."""
    posts = [
        {"seq": 1, "text": "#task @alice @bob analyze the stack", "from": "user_pk"},
        {"seq": 2, "text": "I'd lean toward FastAPI + SQLite", "from": "alice_pk"},
    ]
    # seq 1 is already consumed; seq 2 should wake Bob.
    reason, new_seq = service._should_dispatch("bob", "bob_pk", posts, 1)
    assert reason and "active task" in reason
    assert new_seq == 2


def test_collective_task_wakes_any_member_on_peer_reply() -> None:
    """Collective tasks wake any member on peer replies."""
    posts = [
        {"seq": 1, "text": "#task pick stack for our tracker", "from": "alice_pk"},
        {"seq": 2, "text": "FastAPI + SQLite", "from": "alice_pk"},
    ]
    reason, new_seq = service._should_dispatch("bob", "bob_pk", posts, 1)
    assert reason and "active task" in reason
    assert new_seq == 2


def test_participant_silent_when_not_named_in_task() -> None:
    """Bob stays silent if he was not named."""
    posts = [
        {"seq": 1, "text": "#task @alice take lit review", "from": "user_pk"},
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
        {"seq": 1, "text": "#task @alice @bob analyze the stack", "from": "user_pk"},
        {"seq": 2, "text": "I'd lean toward FastAPI + SQLite", "from": "alice_pk"},
    ]
    # Bob already handled seq 2, so no re-dispatch.
    reason, new_seq = service._should_dispatch("bob", "bob_pk", posts, 2)
    assert reason is None
    assert new_seq == 2


def test_re_fires_when_new_content_arrives_after_response() -> None:
    """New peer content wakes us again."""
    posts = [
        {"seq": 1, "text": "#task @alice @bob analyze", "from": "user_pk"},
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
        {"seq": 1, "text": "#task analyze the architecture", "from": "hub_pk"},
        {"seq": 2, "text": "#done synthesis: pick option A", "from": "hub_pk"},
    ]
    reason, _ = service._should_dispatch("alice", "alice_pk", posts, 0)
    assert reason is None


def test_mention_silent_when_inside_done_post() -> None:
    """A `@<peer>` mention buried in a `#done` body is not a handoff —
    the task is closed; the mention is just part of the synthesis."""
    posts = [
        {"seq": 1, "text": "#task analyze", "from": "hub_pk"},
        {"seq": 2, "text": "#done @alice owns the writeup", "from": "hub_pk"},
    ]
    reason, _ = service._should_dispatch("alice", "alice_pk", posts, 0)
    assert reason is None


def test_collective_task_still_wakes_when_open_after_substantive() -> None:
    """Regression guard: a `#task` that's still open (no `#done`) must
    keep waking peers even when there are intermediate substantive
    posts. The closed-task gate must not over-shoot."""
    posts = [
        {"seq": 1, "text": "#task analyze the architecture", "from": "hub_pk"},
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
