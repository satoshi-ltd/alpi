"""Workgroup poller tests."""

from __future__ import annotations

import asyncio
import datetime as _dt
import shutil
import tempfile
import time
import types
from pathlib import Path

import pytest

from alpi import service
from alpi.alp import subscription as sub_mod
from alpi.alp import workgroup as wg_mod


@pytest.fixture
def short_tmp() -> Path:
    d = Path(tempfile.mkdtemp(prefix="alpi-poll-", dir="/tmp"))
    try:
        yield d
    finally:
        shutil.rmtree(d, ignore_errors=True)


@pytest.fixture(autouse=True)
def _clear_turn_end_stamps():
    service._LAST_TURN_END.clear()
    yield
    service._LAST_TURN_END.clear()


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


def test_old_mention_does_not_cross_into_a_new_active_task() -> None:
    posts = [
        {"seq": 102, "from": "HUB", "text": "@muse gate red on #review-media"},
        {"seq": 103, "from": "HUB", "text": "@mira #task #review triage notes"},
        {"seq": 104, "from": "HUB", "text": "Triage complete"},
    ]
    reason, new_seq = service._should_dispatch(
        "muse", "MUSE", posts, 101, hub_pubkey="HUB", pipeline=True,
    )
    assert reason is None
    assert new_seq == 104


def test_deliberation_old_mention_does_not_cross_into_a_new_active_task() -> None:
    posts = [
        {"seq": 1, "from": "bob_pk", "text": "@alice review the old proposal"},
        {"seq": 2, "from": "hub_pk", "text": "@carol #task #new discuss a new proposal"},
    ]

    reason, new_seq = service._should_dispatch(
        "alice", "alice_pk", posts, 0, hub_pubkey="hub_pk", pipeline=False,
    )

    assert reason is None
    assert new_seq == 2


def test_pipeline_sideways_mention_does_not_wake_peer() -> None:
    posts = [
        {"seq": 1, "from": "HUB", "text": "@pixel #task #build ship it"},
        {"seq": 2, "from": "PIXEL", "text": "blocked — @quill and @lingua must fill legal/"},
    ]
    trigger, _ = service._should_dispatch(
        "quill", "QUILL", posts, 0, hub_pubkey="HUB", pipeline=True,
    )
    assert trigger is None


def test_pipeline_hub_prose_does_not_wake_member_outside_active_task() -> None:
    posts = [
        {"seq": 1, "from": "HUB", "text": "@quill #task #content write"},
        {"seq": 2, "from": "QUILL", "text": "content complete; Lingua follows later"},
        {"seq": 3, "from": "HUB", "text": "Quill delivered; @lingua remains downstream"},
    ]
    trigger, new_seq = service._should_dispatch(
        "lingua", "LINGUA", posts, 0, hub_pubkey="HUB", pipeline=True,
    )
    assert trigger is None
    assert new_seq == 3


def test_pipeline_hub_repair_mention_wakes_active_owner() -> None:
    posts = [
        {"seq": 1, "from": "HUB", "text": "@quill #task #content write"},
        {"seq": 2, "from": "QUILL", "text": "content complete"},
        {"seq": 3, "from": "HUB", "text": "@quill gate red: remove duplicate entry"},
    ]
    trigger, _ = service._should_dispatch(
        "quill", "QUILL", posts, 1, hub_pubkey="HUB", pipeline=True,
    )
    assert trigger == "@quill mentioned (seq #3)"


def test_pipeline_member_mention_of_hub_still_wakes_hub() -> None:
    posts = [
        {"seq": 1, "from": "HUB", "text": "@pixel #task #build ship it"},
        {"seq": 2, "from": "PIXEL", "text": "@mira blocked on legal content"},
    ]
    trigger, _ = service._should_dispatch(
        "mira", "HUB", posts, 0, hub_pubkey="HUB", pipeline=True,
    )
    assert trigger is not None


def test_hub_owned_pipeline_task_wakes_the_hub_immediately() -> None:
    posts = [
        {"seq": 1, "from": "HUB", "text": "@mira #task #review triage notes"},
    ]
    trigger, new_seq = service._should_dispatch(
        "mira", "HUB", posts, 0, hub_pubkey="HUB", pipeline=True,
        hub_owned_phases=frozenset({"review"}),
    )
    assert trigger == "hub-owned #task opened (seq #1)"
    assert new_seq == 1


def test_hub_owned_recovery_task_wakes_the_hub_immediately() -> None:
    meta = _types.SimpleNamespace(
        pipelines={"review": ("review", "review-close")},
        pipeline_steps={"review-close": {"owner": "mira"}},
    )
    posts = [
        {
            "seq": 1,
            "from": "HUB",
            "text": "@mira #task #review-close-recheck close dispositions",
        },
    ]
    trigger, new_seq = service._should_dispatch(
        "mira", "HUB", posts, 0, hub_pubkey="HUB", pipeline=True,
        hub_owned_phases=frozenset({"review-close"}), pipeline_meta=meta,
    )
    assert trigger == "hub-owned #task opened (seq #1)"
    assert new_seq == 1


def test_self_addressed_task_without_declared_hub_ownership_stays_silent() -> None:
    posts = [
        {"seq": 1, "from": "HUB", "text": "@mira #task #content write copy"},
    ]
    trigger, new_seq = service._should_dispatch(
        "mira", "HUB", posts, 0, hub_pubkey="HUB", pipeline=True,
        hub_owned_phases=frozenset(),
    )
    assert trigger is None
    assert new_seq == 1


def test_closed_hub_owned_pipeline_task_does_not_wake_the_hub() -> None:
    posts = [
        {"seq": 1, "from": "HUB", "text": "@mira #task #review triage notes"},
        {"seq": 2, "from": "HUB", "text": "review delivered"},
        {"seq": 3, "from": "HUB", "text": "#done review triaged"},
    ]
    trigger, new_seq = service._should_dispatch(
        "mira", "HUB", posts, 0, hub_pubkey="HUB", pipeline=True,
        hub_owned_phases=frozenset({"review"}),
    )
    assert trigger is None
    assert new_seq == 3


@pytest.mark.asyncio
async def test_gate_opened_task_bypasses_member_cooldown(
    short_tmp: Path, monkeypatch,
) -> None:
    home = short_tmp / "lingua"
    home.mkdir()
    posts = [
        {"seq": 1, "from": "HUB", "text": "@quill #task #content write"},
        {"seq": 2, "from": "QUILL", "text": "content complete"},
        {"seq": 3, "from": "HUB", "text": "#done content verified · gate:npm · ok"},
        {"seq": 4, "from": "HUB", "text": "@lingua #task #translation translate"},
    ]
    sub = types.SimpleNamespace(
        wg_id="wg_fast", name="project", hub_pubkey="HUB",
        pipelines={"content": ("content", "translation")},
        launch_pipeline="content", pipeline_mode=True, recent_posts=posts,
        last_responded_seq=2, last_dispatch_at=service._utcnow_iso(), paused=False,
    )
    kp = types.SimpleNamespace(pubkey_b64=lambda: "LINGUA")
    monkeypatch.setattr("alpi.alp.keys.load_or_generate", lambda home: kp)
    monkeypatch.setattr(sub_mod, "upsert", lambda *args: None)
    monkeypatch.setattr(service, "_in_cooldown_str", lambda *args: True)
    monkeypatch.setattr(service, "_latest_hub_task_seq_for", lambda *args: 4)

    async def fake_turn(*args, **kwargs):
        return None

    spawned: list[str] = []

    def fake_spawn(wg_id, coro):
        spawned.append(wg_id)
        coro.close()

    monkeypatch.setattr(service, "_dispatch_workgroup_turn", fake_turn)
    monkeypatch.setattr(service, "_spawn_dispatch", fake_spawn)
    await service._maybe_dispatch_for_sub(home, "lingua", sub, hot=True)
    assert spawned == ["wg_fast"]


@pytest.mark.asyncio
async def test_member_dispatch_uses_its_decision_snapshot_for_preemption(
    short_tmp: Path, monkeypatch,
) -> None:
    home = short_tmp / "muse"
    home.mkdir()
    posts = [
        {"seq": 98, "from": "HUB", "text": "@muse #task #review-media apply notes"},
        {"seq": 102, "from": "HUB", "text": "@muse gate red on #review-media"},
    ]
    sub = types.SimpleNamespace(
        wg_id="wg_stale", name="project", hub_pubkey="HUB",
        pipeline_mode=True, phase_map={}, recent_posts=posts,
        last_responded_seq=101, last_dispatch_at="", paused=False,
    )
    kp = types.SimpleNamespace(pubkey_b64=lambda: "MUSE")
    monkeypatch.setattr("alpi.alp.keys.load_or_generate", lambda home: kp)
    monkeypatch.setattr(sub_mod, "upsert", lambda *args: None)
    monkeypatch.setattr(service, "_budget_blocks_dispatch", lambda *args: False)
    monkeypatch.setattr(service, "_latest_hub_task_seq_for", lambda *args: 103)
    captured: dict = {}

    def fake_turn(*args, **kwargs):
        captured.update(kwargs)
        return asyncio.sleep(0)

    def fake_spawn(wg_id, coro):
        coro.close()

    monkeypatch.setattr(service, "_dispatch_workgroup_turn", fake_turn)
    monkeypatch.setattr(service, "_spawn_dispatch", fake_spawn)
    await service._maybe_dispatch_for_sub(home, "muse", sub, hot=True)
    assert captured["started_against_task_seq"] == 98


def test_non_pipeline_sideways_mention_still_wakes() -> None:
    posts = [
        {"seq": 1, "from": "HUB", "text": "#task #debate go"},
        {"seq": 2, "from": "BOB", "text": "@carol what do you think?"},
    ]
    trigger, _ = service._should_dispatch(
        "carol", "CAROL", posts, 0, hub_pubkey="HUB", pipeline=False,
    )
    assert trigger is not None


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
    assert len(events[0]["turn_id"]) == 32
    assert len(events[0]["run_id"]) == 32
    assert events[1]["event"] == "end"
    assert events[1]["turn_id"] == events[0]["turn_id"]
    assert events[1]["run_id"] == events[0]["run_id"]
    assert events[1]["rc"] == 0
    assert "duration_s" in events[1]
    assert events[1]["posts_added"] == 0
    assert events[1]["event_tail"] == '{"kind":"tool_start"}'


@pytest.mark.asyncio
async def test_dispatch_counts_only_accepted_posts_for_its_workgroup(
    short_tmp: Path,
) -> None:
    import json
    import sys as _sys

    home = short_tmp / "alice"
    home.mkdir()
    (home / "alp").mkdir()
    lines = [
        {"kind": "tool_end", "name": "workgroup_post", "ok": True, "wg_id": "wg_x"},
        {"kind": "tool_end", "name": "workgroup_post", "ok": False, "wg_id": "wg_x"},
        {"kind": "tool_end", "name": "workgroup_post", "ok": True, "wg_id": "wg_other"},
        {"kind": "tool_end", "name": "workgroup_post", "ok": True, "wg_id": "wg_x"},
    ]
    script = "import json\nfor row in " + repr(lines) + ": print(json.dumps(row), flush=True)"
    real_create = service.asyncio.create_subprocess_exec

    async def fake_create(*argv, **kw):
        return await real_create(
            _sys.executable, "-c", script,
            stdout=service.asyncio.subprocess.PIPE,
            stderr=service.asyncio.subprocess.PIPE,
        )

    service.asyncio.create_subprocess_exec = fake_create
    try:
        await service._dispatch_workgroup_turn(
            home, profile="alice", wg_id="wg_x", wg_name="design",
            reason="count exact deliveries",
        )
    finally:
        service.asyncio.create_subprocess_exec = real_create

    events = [json.loads(line) for line in service.turn_log_path(home).read_text().splitlines()]
    assert events[-1]["posts_added"] == 2


@pytest.mark.asyncio
async def test_pipeline_silent_success_keeps_its_dispatch_cursor(
    short_tmp: Path, monkeypatch,
) -> None:
    import sys as _sys

    home = short_tmp / "alice"
    home.mkdir()
    (home / "alp").mkdir()
    advanced = []
    real_create = service.asyncio.create_subprocess_exec

    async def fake_create(*argv, **kw):
        return await real_create(
            _sys.executable, "-c", "pass",
            stdout=service.asyncio.subprocess.PIPE,
            stderr=service.asyncio.subprocess.PIPE,
        )

    monkeypatch.setattr(service.asyncio, "create_subprocess_exec", fake_create)
    monkeypatch.setattr(
        service, "_advance_member_cursor",
        lambda _home, _wg_id, seq: advanced.append(seq),
    )

    await service._dispatch_workgroup_turn(
        home, profile="alice", wg_id="wg_x", wg_name="design",
        reason="pipeline task", pipeline=True, member_responded_seq=7,
    )
    await service._dispatch_workgroup_turn(
        home, profile="alice", wg_id="wg_y", wg_name="discussion",
        reason="deliberation task", pipeline=False, member_responded_seq=8,
    )

    assert advanced == [8]


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
    assert len(captured["env"].get("ALPI_WORKGROUP_TURN_ID", "")) == 32
    assert len(captured["env"].get("ALPI_RUN_ID", "")) == 32
    assert captured["env"].get("ALPI_TURN_BUDGET_S") == "240"


@pytest.mark.asyncio
async def test_finalize_workgroup_run_closes_and_settles_recorded_usage(
    short_tmp: Path, monkeypatch,
) -> None:
    home = short_tmp / "quill"
    home.mkdir()
    closed = []
    settled = []

    monkeypatch.setattr(
        "alpi.runs.finish_if_running",
        lambda target, run_id, outcome: closed.append((target, run_id, outcome)),
    )
    monkeypatch.setattr(
        "alpi.runs.usage_summary",
        lambda target, run_id: {
            "usd": 0.31, "tokens": 900,
            "tokens_in": 800, "tokens_out": 100,
        },
    )

    async def fake_settle(target, wg_id, turn_id, cost):
        settled.append((target, wg_id, turn_id, cost))
        return {"settled": True}

    monkeypatch.setattr(
        "alpi.alp.workgroup_client.settle_turn", fake_settle,
    )

    await service._finalize_workgroup_run(
        home, "wg_x", "a" * 32, "run_x", "interrupted",
    )

    assert closed == [(home, "run_x", "interrupted")]
    assert settled == [(
        home, "wg_x", "a" * 32,
        {"usd": 0.31, "tokens": 900, "tokens_in": 800, "tokens_out": 100},
    )]


@pytest.mark.asyncio
async def test_dispatch_explains_non_owner_phase_denial_as_temporary(
    short_tmp: Path, monkeypatch,
) -> None:
    import sys as _sys

    home = short_tmp / "lingua"
    home.mkdir()
    (home / "alp").mkdir()
    captured: dict = {}
    real_create = service.asyncio.create_subprocess_exec

    async def fake_create(*argv, **kw):
        captured["argv"] = argv
        return await real_create(
            _sys.executable, "-c", "pass",
            stdout=service.asyncio.subprocess.PIPE,
            stderr=service.asyncio.subprocess.PIPE,
        )

    monkeypatch.setattr(service.asyncio, "create_subprocess_exec", fake_create)
    await service._dispatch_workgroup_turn(
        home, profile="lingua", wg_id="wg_x", wg_name="hotel",
        reason="new task", pipeline=True,
        write_scope={
            "root": "", "paths": [], "phase": "media-qa", "owner": "lens",
        },
    )

    prompt = captured["argv"][-1]
    assert "#media-qa` is owned by @lens, not by @lingua" in prompt
    assert "not a denial in this profile's config.yaml" in prompt


@pytest.mark.asyncio
async def test_dispatch_explains_scoped_terminal_policy_in_docker(
    short_tmp: Path, monkeypatch,
) -> None:
    import sys as _sys

    home = short_tmp / "quill"
    home.mkdir()
    (home / "alp").mkdir()
    captured: dict = {}
    real_create = service.asyncio.create_subprocess_exec

    async def fake_create(*argv, **kw):
        captured["argv"] = argv
        return await real_create(
            _sys.executable, "-c", "pass",
            stdout=service.asyncio.subprocess.PIPE,
            stderr=service.asyncio.subprocess.PIPE,
        )

    monkeypatch.setenv("ALPI_PLATFORM", "docker")
    monkeypatch.setattr(service.asyncio, "create_subprocess_exec", fake_create)
    await service._dispatch_workgroup_turn(
        home, profile="quill", wg_id="wg_x", wg_name="hotel",
        reason="new task", pipeline=True,
        write_scope={
            "root": "projects/hotel", "paths": ["src/content/**"],
            "phase": "content", "owner": "quill",
        },
    )

    prompt = captured["argv"][-1]
    assert "Terminal is unavailable during scoped phases in Docker" in prompt
    assert "Daemon gates still run" in prompt


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


def _pipe_wg(pipeline=True, hub: str = "HUB", dormant=None, steps=None):
    # `pipeline` is the launch chain: True → a default phase list, False → launchless.
    if pipeline is True:
        pipeline = ("intake", "design", "content")
    elif not pipeline:
        pipeline = ()
    launch = tuple(pipeline)[0] if pipeline else None
    pipelines = {launch: tuple(pipeline)} if launch else {}
    for key, phases in (dormant or {}).items():
        pipelines[key] = tuple(phases)
    return _types.SimpleNamespace(
        meta=wg_mod.Meta(
            id="wg1", name="proj", hub_pubkey=hub, created_at="",
            pipelines=pipelines, launch_pipeline=launch,
            pipeline_steps=steps or {},
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
async def test_final_repair_sets_its_dispatch_capability(
    short_tmp: Path, monkeypatch,
) -> None:
    home = short_tmp / "mirafinal"
    home.mkdir()
    captured: dict = {}

    async def fake_exec(*argv, env=None, **kw):
        captured["env"] = env or {}
        raise OSError("blocked in test")

    monkeypatch.setattr(service.asyncio, "create_subprocess_exec", fake_exec)
    await service._dispatch_workgroup_turn(
        home, "mira", "wg1", "proj", "final repair", final_repair=True,
    )
    assert captured["env"].get("ALPI_WORKGROUP_FINAL_REPAIR") == "1"


@pytest.mark.asyncio
async def test_transient_provider_failure_restores_watchdog_attempt(
    short_tmp: Path, monkeypatch,
) -> None:
    import json
    import sys as _sys

    home = short_tmp / "miratransient"
    home.mkdir()
    (home / "alp").mkdir()
    attempt = service._bump_hub_watchdog_count(home, "wg1", 9)
    real_create = service.asyncio.create_subprocess_exec

    async def fake_create(*argv, **kw):
        return await real_create(
            _sys.executable, "-c",
            "print('{\"kind\":\"error\",\"text\":\"provider 500\",\"transient\":true}')",
            stdout=service.asyncio.subprocess.PIPE,
            stderr=service.asyncio.subprocess.PIPE,
        )

    monkeypatch.setattr(service.asyncio, "create_subprocess_exec", fake_create)
    await service._dispatch_workgroup_turn(
        home, "mira", "wg1", "proj", "watchdog",
        recovery_kind="watchdog", recovery_seq=9, recovery_attempt=attempt,
    )

    assert service._peek_hub_watchdog_count(home, "wg1", 9) == 0
    events = [
        json.loads(line)
        for line in service.turn_log_path(home).read_text().splitlines()
    ]
    assert events[-1]["transient_failure"] is True


def test_recovery_restore_does_not_rollback_a_newer_attempt(short_tmp: Path) -> None:
    home = short_tmp / "mirarace"
    home.mkdir()
    assert service._bump_hub_watchdog_count(home, "wg1", 9) == 1
    assert service._bump_hub_watchdog_count(home, "wg1", 9) == 2

    service._restore_recovery_attempt(
        home, "hub_watchdog_fire_count", "wg1", 9, 1,
    )

    assert service._peek_hub_watchdog_count(home, "wg1", 9) == 2


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
    assert calls[2].get("final_repair") is True

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
    assert service._soft_turn_budget(1800) == 1620
    assert service._soft_turn_budget(300) == 240
    assert service._soft_turn_budget(60) == 0


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
    assert service._canonical_pipeline_slug("qa-final-recheck", ["qa", "qa-final"]) == "qa-final"
    assert service._canonical_pipeline_slug("qa-final-recheck", ["qa"]) is None
    assert service._canonical_pipeline_slug("content-update", pipe) is None
    assert service._canonical_pipeline_slug("content-fix-recheck", pipe) is None


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


def test_malformed_blocked_close_does_not_halt_mid_pipeline() -> None:
    wg = _pipe_wg(["intake", "content", "translation", "build", "qa"])
    recent = [
        {"seq": 1, "from": "HUB", "text": "@lingua #task #translation translate all"},
        {"seq": 2, "from": "LINGUA", "text": "locales delivered"},
        {"seq": 3, "from": "HUB", "text": "#done BLOCKED·not-the-contract"},
    ]
    assert service._next_pipeline_phase(wg, recent) == ("build", "translation", True)


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

    @property
    def returncode(self) -> int | None:
        return self._exit.result() if self._exit.done() else None


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
async def test_model_progress_keeps_turn_alive_via_drain() -> None:
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
            reader.feed_data(f"{{\"kind\": \"model_state\"}} {i}\n".encode())
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
        paused=paused, hub_pubkey="hub_pk", id="wg_x", name="proj-x",
        pipelines={}, launch_pipeline=None,
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
async def test_poller_starts_subscription_pulls_concurrently(monkeypatch) -> None:
    import types
    from alpi.alp import subscription as sub_mod
    from alpi.alp import workgroup as wg_mod
    from alpi.alp import workgroup_client as wc

    subs = [types.SimpleNamespace(wg_id=f"wg{i}") for i in range(3)]
    entered: set[str] = set()
    all_entered = asyncio.Event()
    release = asyncio.Event()

    async def fake_pull(home, wg_id, wait_s=0.0):
        entered.add(wg_id)
        if len(entered) == len(subs):
            all_entered.set()
        await release.wait()
        return [], None

    monkeypatch.setattr(service, "_poller_start_offset", lambda _p: 0.0)
    monkeypatch.setattr(sub_mod, "load", lambda home: subs)
    monkeypatch.setattr(
        sub_mod, "get",
        lambda home, wid: types.SimpleNamespace(
            wg_id=wid, recent_posts=[], hub_pubkey="hub", last_responded_seq=0,
            last_dispatch_at="", paused=False, pipeline_mode=False,
        ),
    )
    monkeypatch.setattr(wc, "pull", fake_pull)
    monkeypatch.setattr(wg_mod, "list_workgroups", lambda home: [])
    poller = asyncio.create_task(
        service._run_workgroup_poller(Path("/tmp/does-not-matter"), "alice")
    )
    try:
        await asyncio.wait_for(all_entered.wait(), timeout=1)
    finally:
        release.set()
        poller.cancel()
        await asyncio.gather(poller, return_exceptions=True)

    assert entered == {"wg0", "wg1", "wg2"}


@pytest.mark.asyncio
async def test_subscription_empty_pull_reopens_without_idle_backoff(monkeypatch) -> None:
    import types
    from alpi.alp import subscription as sub_mod
    from alpi.alp import workgroup_client as wc

    calls: list[float] = []
    second_started = asyncio.Event()

    async def fake_pull(home, wg_id, wait_s=0.0):
        calls.append(wait_s)
        if len(calls) == 1:
            return [], 0
        second_started.set()
        await asyncio.Event().wait()

    sub = types.SimpleNamespace(
        wg_id="wg_cold", recent_posts=[], hub_pubkey="hub",
        last_responded_seq=0, last_dispatch_at="", paused=False, pipeline_mode=False,
    )
    monkeypatch.setattr(sub_mod, "get", lambda home, wid: sub)
    monkeypatch.setattr(wc, "pull", fake_pull)
    monkeypatch.setattr(service, "_WG_HOT_TICK_SECONDS", 0)
    monkeypatch.setattr(service, "_maybe_dispatch_for_sub", lambda *a, **k: asyncio.sleep(0))

    worker = asyncio.create_task(
        service._run_subscription_poller(Path("/tmp/none"), "alice", "wg_cold")
    )
    try:
        await asyncio.wait_for(second_started.wait(), timeout=1)
    finally:
        worker.cancel()
        await asyncio.gather(worker, return_exceptions=True)

    assert calls == [service._WG_LONG_POLL_SECONDS, service._WG_LONG_POLL_SECONDS]


@pytest.mark.asyncio
async def test_removed_subscription_cancels_held_pull(monkeypatch) -> None:
    import types
    from alpi.alp import subscription as sub_mod
    from alpi.alp import workgroup as wg_mod
    from alpi.alp import workgroup_client as wc

    subs = [types.SimpleNamespace(wg_id="wg_gone")]
    entered = asyncio.Event()
    cancelled = asyncio.Event()

    async def fake_pull(home, wg_id, wait_s=0.0):
        entered.set()
        try:
            await asyncio.Event().wait()
        finally:
            cancelled.set()

    monkeypatch.setattr(service, "_poller_start_offset", lambda _p: 0.0)
    monkeypatch.setattr(service, "WORKGROUP_TICK_SECONDS", 0.01)
    monkeypatch.setattr(sub_mod, "load", lambda home: list(subs))
    monkeypatch.setattr(sub_mod, "get", lambda home, wid: subs[0] if subs else None)
    monkeypatch.setattr(wc, "pull", fake_pull)
    monkeypatch.setattr(wg_mod, "list_workgroups", lambda home: [])

    poller = asyncio.create_task(
        service._run_workgroup_poller(Path("/tmp/none"), "alice")
    )
    try:
        await asyncio.wait_for(entered.wait(), timeout=1)
        subs.clear()
        await asyncio.wait_for(cancelled.wait(), timeout=1)
    finally:
        poller.cancel()
        await asyncio.gather(poller, return_exceptions=True)


@pytest.mark.asyncio
async def test_hub_scan_does_not_block_the_host_loop(monkeypatch) -> None:
    wg = types.SimpleNamespace(meta=types.SimpleNamespace(id="wg1"))

    def slow_posts(_home, _wg):
        time.sleep(0.25)
        return []

    monkeypatch.setattr(service, "_poller_start_offset", lambda _p: 0.0)
    monkeypatch.setattr(sub_mod, "load", lambda _home: [])
    monkeypatch.setattr(wg_mod, "list_workgroups", lambda _home: [wg])
    monkeypatch.setattr(service, "_all_hub_posts_decrypted", slow_posts)

    started = time.monotonic()
    poller = asyncio.create_task(
        service._run_workgroup_poller(Path("/tmp/none"), "alice")
    )
    try:
        await asyncio.sleep(0.05)
        assert time.monotonic() - started < 0.15
    finally:
        poller.cancel()
        await asyncio.gather(poller, return_exceptions=True)


@pytest.mark.asyncio
async def test_post_wake_rescans_only_the_changed_hub(monkeypatch) -> None:
    from alpi.alp import wakes

    home = Path("/tmp/targeted-wake")
    workgroups = [
        types.SimpleNamespace(meta=types.SimpleNamespace(id="wg1")),
        types.SimpleNamespace(meta=types.SimpleNamespace(id="wg2")),
    ]
    scans: list[str] = []
    initial = asyncio.Event()
    targeted = asyncio.Event()

    def posts(_home, wg):
        scans.append(wg.meta.id)
        return [{"seq": 1}]

    async def dispatch(*_args, **_kwargs):
        if len(scans) == 2:
            initial.set()
        elif len(scans) == 3:
            targeted.set()

    monkeypatch.setattr(service, "_poller_start_offset", lambda _p: 0.0)
    monkeypatch.setattr(sub_mod, "load", lambda _home: [])
    monkeypatch.setattr(wg_mod, "list_workgroups", lambda _home: workgroups)
    monkeypatch.setattr(service, "_all_hub_posts_decrypted", posts)
    monkeypatch.setattr(service, "_hub_stays_hot", lambda *_args: False)
    monkeypatch.setattr(service, "_maybe_dispatch_for_hub", dispatch)

    poller = asyncio.create_task(service._run_workgroup_poller(home, "alice"))
    try:
        await asyncio.wait_for(initial.wait(), timeout=1)
        wakes.fire(home, "wg2")
        await asyncio.wait_for(targeted.wait(), timeout=1)
    finally:
        poller.cancel()
        await asyncio.gather(poller, return_exceptions=True)

    assert scans == ["wg1", "wg2", "wg2"]


def test_wg_backoff_schedule() -> None:
    assert service._wg_backoff_mult(0) == 1
    assert service._wg_backoff_mult(2) == 1
    assert service._wg_backoff_mult(3) == 2
    assert service._wg_backoff_mult(4) == 4
    assert service._wg_backoff_mult(7) == service._WG_POLL_BACKOFF_MAX  # capped
    assert service._wg_backoff_mult(99) == service._WG_POLL_BACKOFF_MAX
    base = service.WORKGROUP_TICK_SECONDS
    assert base * service._wg_backoff_mult(99) <= 15 * 60  # failed transport retries never wait past 15 min


def test_wg_inflight_dispatch_keeps_workgroup_hot(monkeypatch) -> None:
    now = 1000.0
    monkeypatch.setitem(service._INFLIGHT, ("wg_b", "mira"), {"proc": None})
    try:
        assert service._wg_is_hot("wg_b", {}, now) is True
    finally:
        service._INFLIGHT.pop(("wg_b", "mira"), None)


def test_hub_stays_hot_on_pipeline_continuation() -> None:
    wg = _pipe_wg(["intake", "build"])
    recent = [
        {"seq": 1, "from": "HUB", "text": "@bob #task #intake go"},
        {"seq": 2, "from": "BOB", "text": "intake complete"},
        {"seq": 3, "from": "HUB", "text": "#done intake verified"},
    ]
    assert service._hub_stays_hot(False, wg, recent) is True


def test_hub_goes_idle_after_terminal_close() -> None:
    wg = _pipe_wg(False)
    recent = [
        {"seq": 1, "from": "HUB", "text": "#task #x go"},
        {"seq": 2, "from": "BOB", "text": "answer"},
        {"seq": 3, "from": "HUB", "text": "#done synthesized"},
    ]
    assert service._hub_stays_hot(False, wg, recent) is False


def test_hub_goes_idle_after_terminal_pipeline_phase() -> None:
    wg = _pipe_wg(["intake", "qa"])
    recent = [
        {"seq": 1, "from": "HUB", "text": "@bob #task #qa verify"},
        {"seq": 2, "from": "BOB", "text": "verified"},
        {"seq": 3, "from": "HUB", "text": "#done PASS verified"},
    ]
    assert service._hub_stays_hot(False, wg, recent) is False


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

MEDIA_CHAIN = {"media-update": ["media-update", "media-config", "media-build", "media-qa"]}
LAUNCH = ["setup", "intake", "build", "qa"]


def _closed(*pairs):
    recent = []
    for slug, seq in pairs:
        recent.append({"seq": seq - 1, "from": "HUB", "text": f"@x #task #{slug} go"})
        recent.append({"seq": seq, "from": "HUB", "text": f"#done {slug} verified"})
    return recent


def _closed_chain(chain, upto):
    return _closed(*[(slug, 2 + 2 * n) for n, slug in enumerate(chain[:upto])])


def test_launch_chain_is_the_derived_pipeline_view() -> None:
    wg = _pipe_wg(LAUNCH, dormant=MEDIA_CHAIN)
    assert wg.meta.launch_pipeline == "setup"
    assert wg.meta.launch_chain == tuple(LAUNCH)
    assert wg_mod.dormant_pipelines(wg.meta) == {
        "media-update": tuple(MEDIA_CHAIN["media-update"]),
    }


def test_pipeline_successor_is_shared_and_terminal_is_empty() -> None:
    wg = _pipe_wg(LAUNCH, dormant=MEDIA_CHAIN)
    for chain in (LAUNCH, MEDIA_CHAIN["media-update"]):
        for phase, nxt in zip(chain, chain[1:]):
            assert wg_mod.pipeline_successor(wg.meta, phase) == nxt
        assert wg_mod.pipeline_successor(wg.meta, chain[-1]) == ""
    assert wg_mod.pipeline_successor(wg.meta, "hotfix") == ""


def test_continuation_takes_the_shared_successor_for_every_phase() -> None:
    wg = _pipe_wg(LAUNCH, dormant=MEDIA_CHAIN)
    for chain in (LAUNCH, MEDIA_CHAIN["media-update"]):
        for i, phase in enumerate(chain[:-1]):
            got = service._next_pipeline_phase(wg, _closed_chain(chain, i + 1))
            assert got == (chain[i + 1], phase, True), f"after {phase}: got {got!r}"
            assert got[0] == wg_mod.pipeline_successor(wg.meta, phase)


def test_gate_step_and_continuation_agree_on_the_successor() -> None:
    from alpi.alp import pipeline_gates as gates

    steps = {
        slug: {
            "owner": "pixel", "task": f"run {slug}",
            "gate": {"argv": ["true"], "cwd": ""},
        }
        for slug in LAUNCH
    }
    wg = _pipe_wg(LAUNCH, steps=steps)
    for i, phase in enumerate(LAUNCH[:-1]):
        nxt, _latest, known = service._next_pipeline_phase(
            wg, _closed_chain(LAUNCH, i + 1),
        )
        step = gates.step_for(wg.meta, phase)
        assert known and step is not None
        assert step.next_phase == nxt
    assert gates.step_for(wg.meta, LAUNCH[-1]).next_phase == ""


def test_launchless_workgroup_is_idle_then_continues_its_opened_chain() -> None:
    wg = _pipe_wg(False, dormant=MEDIA_CHAIN)
    assert wg.meta.launch_pipeline is None
    assert wg.meta.launch_chain == ()
    assert service._wg_is_pipeline(wg) is True
    assert service._next_pipeline_phase(wg, []) == (None, "", True)
    recent = _closed(("media-update", 2))
    assert service._pipeline_continuation_due(wg, recent, None) is True
    assert service._next_pipeline_phase(wg, recent) == ("media-config", "media-update", True)
    adhoc = _closed(("hotfix", 20))
    assert service._next_pipeline_phase(wg, adhoc) == (None, "hotfix", False)


def test_dormant_chain_step_chains_within_its_own_chain() -> None:
    wg = _pipe_wg(LAUNCH, dormant=MEDIA_CHAIN)
    recent = _closed(("setup", 2), ("intake", 4), ("build", 6), ("qa", 8), ("media-update", 10))
    assert service._next_pipeline_phase(wg, recent) == ("media-config", "media-update", True)


def test_dormant_chain_runs_to_its_last_step_then_completes() -> None:
    wg = _pipe_wg(LAUNCH, dormant=MEDIA_CHAIN)
    steps = ["media-update", "media-config", "media-build", "media-qa"]
    expected = ["media-config", "media-build", "media-qa", None]
    for i, want in enumerate(expected):
        recent = _closed(("qa", 8), *[(s, 10 + 2 * n) for n, s in enumerate(steps[: i + 1])])
        nxt, latest, known = service._next_pipeline_phase(wg, recent)
        assert (nxt, known) == (want, True), f"after {steps[i]}: got {nxt!r}"
        assert latest == steps[i]


def test_launch_terminal_does_not_leak_into_a_dormant_chain() -> None:
    wg = _pipe_wg(LAUNCH, dormant=MEDIA_CHAIN)
    recent = _closed(("setup", 2), ("intake", 4), ("build", 6))
    recent += [
        {"seq": 7, "from": "HUB", "text": "@lens #task #qa go"},
        {"seq": 8, "from": "HUB", "text": "#done qa · QA PASS ready for internal review"},
    ]
    nxt, latest, known = service._next_pipeline_phase(wg, recent)
    assert (nxt, latest, known) == (None, "qa", True)


def test_undeclared_chain_close_is_unknown_not_guessed() -> None:
    wg = _pipe_wg(LAUNCH)
    recent = _closed(("media-update", 10))
    nxt, latest, known = service._next_pipeline_phase(wg, recent)
    assert (nxt, latest, known) == (None, "media-update", False)


def test_dormant_chain_blocked_close_halts_the_chain() -> None:
    wg = _pipe_wg(LAUNCH, dormant=MEDIA_CHAIN)
    recent = _closed(("qa", 8), ("media-update", 10))
    recent += [
        {"seq": 11, "from": "HUB", "text": "@scout #task #media-config go"},
        {"seq": 12, "from": "HUB", "text": "#done BLOCKED · template gap"},
    ]
    nxt, _latest, known = service._next_pipeline_phase(wg, recent)
    assert (nxt, known) == (None, True)


def test_dormant_chain_can_run_twice_for_a_second_media_drop() -> None:
    wg = _pipe_wg(LAUNCH, dormant=MEDIA_CHAIN)
    first = _closed(("qa", 8), ("media-update", 10), ("media-config", 12),
                    ("media-build", 14), ("media-qa", 16))
    assert service._next_pipeline_phase(wg, first)[0] is None
    again = first + _closed(("media-update", 20))
    assert service._next_pipeline_phase(wg, again) == ("media-config", "media-update", True)


def test_adhoc_close_after_launch_completes_resurrects_nothing() -> None:
    wg = _pipe_wg(LAUNCH, dormant=MEDIA_CHAIN)
    recent = _closed(("setup", 2), ("intake", 4), ("build", 6), ("qa", 8), ("hotfix", 10))
    assert service._next_pipeline_phase(wg, recent) == (None, "hotfix", False)


def test_adhoc_close_after_a_dormant_chain_completes_resurrects_nothing() -> None:
    wg = _pipe_wg(LAUNCH, dormant=MEDIA_CHAIN)
    recent = _closed(
        ("qa", 8), ("media-update", 10), ("media-config", 12),
        ("media-build", 14), ("media-qa", 16), ("hotfix", 18),
    )
    assert service._next_pipeline_phase(wg, recent) == (None, "hotfix", False)


def test_variant_close_selects_its_chain_without_advancing_it() -> None:
    wg = _pipe_wg(LAUNCH, dormant=MEDIA_CHAIN)
    recent = _closed(("qa", 8), ("media-update", 10))
    recent += [
        {"seq": 11, "from": "HUB", "text": "@scout #task #media-config-fix go"},
        {"seq": 12, "from": "HUB", "text": "#done media-config-fix verified"},
    ]
    assert service._next_pipeline_phase(wg, recent) == ("media-config", "media-update", True)


CONTENT_CHAIN = {"content-update": ["content-update", "content-qa"]}
CONTENT_LAUNCH = ["content", "qa"]


def test_declared_phase_resolves_to_its_own_chain_not_a_suffix_base() -> None:
    wg = _pipe_wg(CONTENT_LAUNCH, dormant=CONTENT_CHAIN)
    recent = _closed(("content", 2), ("qa", 4), ("content-update", 6))
    assert service._next_pipeline_phase(wg, recent) == ("content-qa", "content-update", True)


def test_content_update_close_never_advances_the_content_chain() -> None:
    wg = _pipe_wg(CONTENT_LAUNCH, dormant=CONTENT_CHAIN)
    assert wg_mod.canonical_pipeline_phase(wg.meta, "content-update") == (
        "content-update", "content-update",
    )
    nxt, latest, known = service._next_pipeline_phase(wg, _closed(("content-update", 2)))
    assert (nxt, latest, known) == ("content-qa", "content-update", True)
    assert latest != "content"
    assert nxt != "qa"


def test_recovery_suffix_resolves_by_exact_base_membership() -> None:
    wg = _pipe_wg(CONTENT_LAUNCH, dormant=CONTENT_CHAIN)
    recent = _closed(("qa", 4), ("content-update", 6), ("content-update-fix", 8))
    assert service._next_pipeline_phase(wg, recent) == ("content-qa", "content-update", True)


def test_an_invented_suffix_keeps_the_run_representable() -> None:
    """An unmapped slug returned known=False, and the watchdog then had no phase to wake anyone about."""
    wg = _pipe_wg(CONTENT_LAUNCH, dormant=CONTENT_CHAIN)
    assert wg_mod.canonical_pipeline_phase(wg.meta, "content-update-tweak") == (
        "content-update", "content-update",
    )
    recent = _closed(("content", 2), ("qa", 4), ("content-tweak", 6))
    assert service._next_pipeline_phase(wg, recent)[2] is True


def test_launch_phase_chains_even_when_a_dormant_chain_shares_its_prefix() -> None:
    wg = _pipe_wg(CONTENT_LAUNCH, dormant=CONTENT_CHAIN)
    assert service._next_pipeline_phase(wg, _closed(("content", 2))) == ("qa", "content", True)


def test_blocked_on_an_undeclared_slug_stays_unknown() -> None:
    wg = _pipe_wg(LAUNCH, dormant=MEDIA_CHAIN)
    recent = _closed(("qa", 8))
    recent += [
        {"seq": 9, "from": "HUB", "text": "@x #task #hotfix go"},
        {"seq": 10, "from": "HUB", "text": "#done BLOCKED · hotfix · unrelated"},
    ]
    assert service._next_pipeline_phase(wg, recent) == (None, "hotfix", False)


def test_blocked_on_a_declared_dormant_phase_halts_it() -> None:
    wg = _pipe_wg(LAUNCH, dormant=MEDIA_CHAIN)
    recent = _closed(("qa", 8), ("media-update", 10))
    recent += [
        {"seq": 11, "from": "HUB", "text": "@scout #task #media-config go"},
        {"seq": 12, "from": "HUB", "text": "#done BLOCKED · media-config · gap"},
    ]
    assert service._next_pipeline_phase(wg, recent) == (None, "media-config", True)


class _FakeTurnProc:
    returncode = None

    def __init__(self) -> None:
        self.terminated = False

    def terminate(self) -> None:
        self.terminated = True


def _inflight_member(home: Path, wg_id: str, hub_pk: str, posts: list[dict]) -> dict:
    sub = sub_mod.Subscription(
        wg_id=wg_id, name="site", hub_id="mira", hub_pubkey=hub_pk,
    )
    sub.recent_posts = posts
    sub_mod.upsert(home, sub)
    return {
        "proc": _FakeTurnProc(), "profile": "alice", "wg_name": "site",
        "hub_pubkey": hub_pk, "started_against_task_seq": 3,
    }


async def _watch_ticks(home: Path, seconds: float) -> None:
    task = asyncio.create_task(service._run_preempt_watcher(home, "alice"))
    try:
        await asyncio.sleep(seconds)
    finally:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass


@pytest.mark.asyncio
async def test_preempt_watcher_sigterms_a_dispatch_started_against_an_older_task(
    short_tmp: Path, monkeypatch,
) -> None:
    home = short_tmp / "alice"; home.mkdir()
    hub_pk = "hub_pk"
    info = _inflight_member(home, "wg_p", hub_pk, [
        {"seq": 3, "text": "@alice #task #setup · go", "from": hub_pk},
        {"seq": 5, "text": "@alice #task #qa · audit", "from": hub_pk},
    ])
    service._INFLIGHT[("wg_p", "alice")] = info
    monkeypatch.setattr(service, "_PREEMPT_TICK_SECONDS", 0.01)
    try:
        await _watch_ticks(home, 0.1)
        assert info["proc"].terminated is True
        assert info["preempted"] is True
        assert info["preempted_by_seq"] == 5
    finally:
        service._INFLIGHT.pop(("wg_p", "alice"), None)


@pytest.mark.asyncio
async def test_preempt_watcher_ignores_a_hub_done(
    short_tmp: Path, monkeypatch,
) -> None:
    """Only a fresh `#task` preempts; a `#done` is left to the SDK `stale-round` check."""
    home = short_tmp / "alice"; home.mkdir()
    hub_pk = "hub_pk"
    info = _inflight_member(home, "wg_d", hub_pk, [
        {"seq": 3, "text": "@alice #task #setup · go", "from": hub_pk},
        {"seq": 6, "text": "#done wrapped", "from": hub_pk},
    ])
    service._INFLIGHT[("wg_d", "alice")] = info
    monkeypatch.setattr(service, "_PREEMPT_TICK_SECONDS", 0.01)
    try:
        await _watch_ticks(home, 0.1)
        assert info["proc"].terminated is False
        assert "preempted" not in info
    finally:
        service._INFLIGHT.pop(("wg_d", "alice"), None)


@pytest.mark.asyncio
async def test_preempt_watcher_stops_a_paused_workgroup(
    short_tmp: Path, monkeypatch,
) -> None:
    home = short_tmp / "alice"; home.mkdir()
    info = _inflight_member(home, "wg_pause", "hub_pk", [])
    sub = sub_mod.get(home, "wg_pause")
    sub.paused = True
    sub_mod.upsert(home, sub)
    service._INFLIGHT[("wg_pause", "alice")] = info
    monkeypatch.setattr(service, "_PREEMPT_TICK_SECONDS", 0.01)
    try:
        await _watch_ticks(home, 0.1)
        assert info["proc"].terminated is True
        assert info["cancelled"] is True
        assert info["cancel_reason"] == "workgroup-paused"
    finally:
        service._INFLIGHT.pop(("wg_pause", "alice"), None)


@pytest.mark.asyncio
async def test_preempt_watcher_stops_a_removed_workgroup(
    short_tmp: Path, monkeypatch,
) -> None:
    home = short_tmp / "alice"; home.mkdir()
    info = _inflight_member(home, "wg_removed", "hub_pk", [])
    sub_mod.tombstone(home, "wg_removed")
    service._INFLIGHT[("wg_removed", "alice")] = info
    monkeypatch.setattr(service, "_PREEMPT_TICK_SECONDS", 0.01)
    try:
        await _watch_ticks(home, 0.1)
        assert info["proc"].terminated is True
        assert info["cancelled"] is True
        assert info["cancel_reason"] == "workgroup-removed"
    finally:
        service._INFLIGHT.pop(("wg_removed", "alice"), None)


@pytest.mark.asyncio
async def test_watchdog_stall_path_defers_to_an_inflight_member_turn(
    short_tmp: Path, monkeypatch,
) -> None:
    """An in-flight dispatch is progress; the stall watchdog must not re-task over it."""
    import datetime as _dt

    home = short_tmp / "hub"; home.mkdir()
    old = (
        _dt.datetime.now(tz=_dt.timezone.utc) - _dt.timedelta(hours=2)
    ).strftime("%Y-%m-%dT%H:%M:%SZ")
    wg = types.SimpleNamespace(meta=types.SimpleNamespace(
        id="wg_ff", name="site", hub_pubkey="HUB", paused=False,
        pipelines={"intake": ("intake", "qa")}, launch_pipeline="intake",
        pipeline_steps={}, quorum_timeout_seconds=0,
    ))
    recent = [
        {"seq": 1, "from": "HUB", "text": "@scout #task #intake go", "ts": old},
        {"seq": 2, "from": "SCOUTPK", "text": "#working reading files", "ts": old},
    ]
    spawned: list[str] = []
    monkeypatch.setattr(service, "_spawn_dispatch", lambda wid, coro: spawned.append(wid))
    monkeypatch.setattr(service, "_dispatch_workgroup_turn", lambda *a, **k: None)
    monkeypatch.setattr(service, "_budget_blocks_dispatch", lambda *a, **k: False)

    service._INFLIGHT[("wg_ff", "scout")] = {"profile": "scout"}
    try:
        await service._maybe_watchdog_close(home, "mira", wg, recent)
        assert spawned == []
    finally:
        service._INFLIGHT.pop(("wg_ff", "scout"), None)

    await service._maybe_watchdog_close(home, "mira", wg, recent)
    assert spawned == ["wg_ff"]


@pytest.mark.asyncio
async def test_watchdog_working_grace_covers_the_phase_turn_budget(
    short_tmp: Path, monkeypatch,
) -> None:
    """900s of hardwired grace under an 1800s turn_budget_s read live work as a stall (abad-v22)."""
    import datetime as _dt

    home = short_tmp / "hub"; home.mkdir()

    def _ts(seconds_ago: int) -> str:
        return (
            _dt.datetime.now(tz=_dt.timezone.utc) - _dt.timedelta(seconds=seconds_ago)
        ).strftime("%Y-%m-%dT%H:%M:%SZ")

    wg = types.SimpleNamespace(meta=types.SimpleNamespace(
        id="wg_budget", name="site", hub_pubkey="HUB", paused=False,
        pipelines={"intake": ("content", "qa")}, launch_pipeline="intake",
        pipeline_steps={"content": {"owner": "quill", "task": "write", "turn_budget_s": 1800}},
        quorum_timeout_seconds=0,
    ))
    spawned: list[str] = []
    monkeypatch.setattr(service, "_spawn_dispatch", lambda wid, coro: spawned.append(wid))
    monkeypatch.setattr(service, "_dispatch_workgroup_turn", lambda *a, **k: None)
    monkeypatch.setattr(service, "_budget_blocks_dispatch", lambda *a, **k: False)

    recent = [
        {"seq": 1, "from": "HUB", "text": "@quill #task #content write", "ts": _ts(2000)},
        {"seq": 2, "from": "QUILLPK", "text": "#working drafting", "ts": _ts(1000)},
    ]
    await service._maybe_watchdog_close(home, "mira", wg, recent)
    assert spawned == []

    recent[1]["ts"] = _ts(1900)
    await service._maybe_watchdog_close(home, "mira", wg, recent)
    assert spawned == ["wg_budget"]


@pytest.mark.asyncio
async def test_watchdog_default_working_grace_unchanged_without_budget(
    short_tmp: Path, monkeypatch,
) -> None:
    import datetime as _dt

    home = short_tmp / "hub"; home.mkdir()
    old = (
        _dt.datetime.now(tz=_dt.timezone.utc) - _dt.timedelta(seconds=1000)
    ).strftime("%Y-%m-%dT%H:%M:%SZ")
    wg = types.SimpleNamespace(meta=types.SimpleNamespace(
        id="wg_nobudget", name="site", hub_pubkey="HUB", paused=False,
        pipelines={"intake": ("content", "qa")}, launch_pipeline="intake",
        pipeline_steps={}, quorum_timeout_seconds=0,
    ))
    recent = [
        {"seq": 1, "from": "HUB", "text": "@quill #task #content write", "ts": old},
        {"seq": 2, "from": "QUILLPK", "text": "#working drafting", "ts": old},
    ]
    spawned: list[str] = []
    monkeypatch.setattr(service, "_spawn_dispatch", lambda wid, coro: spawned.append(wid))
    monkeypatch.setattr(service, "_dispatch_workgroup_turn", lambda *a, **k: None)
    monkeypatch.setattr(service, "_budget_blocks_dispatch", lambda *a, **k: False)

    await service._maybe_watchdog_close(home, "mira", wg, recent)
    assert spawned == ["wg_nobudget"]


@pytest.mark.asyncio
async def test_only_a_delivered_turn_stamps_the_settle_window(
    short_tmp: Path, monkeypatch,
) -> None:
    """A silently looping turn must not re-arm the settle window, or the escalation ladder starves forever."""
    import sys as _sys

    home = short_tmp / "mirastamp"; home.mkdir()
    real_create = service.asyncio.create_subprocess_exec

    def _fake_create_printing(line: str):
        async def fake_create(*argv, **kw):
            return await real_create(
                _sys.executable, "-c", f"print('{line}')" if line else "pass",
                stdout=service.asyncio.subprocess.PIPE,
                stderr=service.asyncio.subprocess.PIPE,
            )
        return fake_create

    monkeypatch.setattr(
        service.asyncio, "create_subprocess_exec", _fake_create_printing(""),
    )
    await service._dispatch_workgroup_turn(home, "mira", "wg_silent", "proj", "go")
    assert "wg_silent" not in service._LAST_TURN_END

    post_event = (
        '{"kind":"tool_end","name":"workgroup_post","ok":true,"wg_id":"wg_loud"}'
    )
    monkeypatch.setattr(
        service.asyncio, "create_subprocess_exec",
        _fake_create_printing(post_event.replace('"', '\\"')),
    )
    await service._dispatch_workgroup_turn(home, "mira", "wg_loud", "proj", "go")
    assert "wg_loud" in service._LAST_TURN_END


@pytest.mark.asyncio
async def test_turn_stays_inflight_until_the_settle_stamp_lands(
    short_tmp: Path, monkeypatch,
) -> None:
    """A drain delayed past process exit must not open a window where neither watchdog guard holds."""
    import sys as _sys

    home = short_tmp / "mirarace"; home.mkdir()
    real_create = service.asyncio.create_subprocess_exec
    child = (
        "import subprocess, sys; "
        "print('{\\\"kind\\\":\\\"tool_end\\\",\\\"name\\\":\\\"workgroup_post\\\","
        "\\\"ok\\\":true,\\\"wg_id\\\":\\\"wg_race\\\"}'); "
        "sys.stdout.flush(); subprocess.Popen(['sleep', '2'])"
    )

    async def fake_create(*argv, **kw):
        return await real_create(
            _sys.executable, "-c", child,
            stdout=service.asyncio.subprocess.PIPE,
            stderr=service.asyncio.subprocess.PIPE,
        )

    monkeypatch.setattr(service.asyncio, "create_subprocess_exec", fake_create)
    turn = asyncio.create_task(
        service._dispatch_workgroup_turn(home, "mira", "wg_race", "proj", "go"),
    )
    await asyncio.sleep(1.0)
    try:
        assert ("wg_race", "mira") in service._INFLIGHT
        assert "wg_race" not in service._LAST_TURN_END
    finally:
        await asyncio.wait_for(turn, timeout=15)
    assert ("wg_race", "mira") not in service._INFLIGHT
    assert "wg_race" in service._LAST_TURN_END


@pytest.mark.asyncio
async def test_a_pipe_holding_descendant_cannot_hold_the_workgroup_inflight(
    short_tmp: Path, monkeypatch,
) -> None:
    """EOF may never arrive when a descendant inherits the pipes; the drain must be bounded or _INFLIGHT blocks the workgroup forever."""
    import sys as _sys

    home = short_tmp / "mirahold"; home.mkdir()
    monkeypatch.setattr(service, "_POST_EXIT_DRAIN_SECONDS", 1)
    real_create = service.asyncio.create_subprocess_exec
    child = (
        "import subprocess, sys; "
        "print('{\\\"kind\\\":\\\"tool_end\\\",\\\"name\\\":\\\"workgroup_post\\\","
        "\\\"ok\\\":true,\\\"wg_id\\\":\\\"wg_hold\\\"}'); "
        "sys.stdout.flush(); subprocess.Popen(['sleep', '6'])"
    )

    async def fake_create(*argv, **kw):
        return await real_create(
            _sys.executable, "-c", child,
            stdout=service.asyncio.subprocess.PIPE,
            stderr=service.asyncio.subprocess.PIPE,
        )

    monkeypatch.setattr(service.asyncio, "create_subprocess_exec", fake_create)
    await asyncio.wait_for(
        service._dispatch_workgroup_turn(home, "mira", "wg_hold", "proj", "go"),
        timeout=5,
    )
    assert ("wg_hold", "mira") not in service._INFLIGHT
    assert "wg_hold" in service._LAST_TURN_END
    import json as _json
    events = [
        _json.loads(line)
        for line in service.turn_log_path(home).read_text().splitlines()
    ]
    assert events[-1]["event"] == "end"
    assert events[-1]["posts_added"] == 1
    await asyncio.sleep(4)  # descendant EOF lands in this loop so the transport finalizes cleanly


def test_stamp_turn_end_keeps_live_entries_at_the_cap() -> None:
    import time as _time

    service._LAST_TURN_END.clear()
    now = _time.monotonic()
    for i in range(service._TURN_END_CAP):
        service._LAST_TURN_END[f"wg_{i}"] = now
    service._stamp_turn_end("wg_5")
    assert len(service._LAST_TURN_END) == service._TURN_END_CAP

    for i in range(0, 100):
        service._LAST_TURN_END[f"wg_{i}"] = now - service._TURN_SETTLE_SECONDS - 1
    service._stamp_turn_end("wg_new")
    assert "wg_new" in service._LAST_TURN_END
    assert "wg_200" in service._LAST_TURN_END
    assert "wg_3" not in service._LAST_TURN_END


@pytest.mark.asyncio
async def test_watchdog_waits_for_a_just_finished_turn_to_settle(
    short_tmp: Path, monkeypatch,
) -> None:
    """A nudge in the end→redispatch gap counts the whole execution as silence and re-tasks over it."""
    import datetime as _dt
    import time as _time

    home = short_tmp / "hub"; home.mkdir()
    old = (
        _dt.datetime.now(tz=_dt.timezone.utc) - _dt.timedelta(hours=2)
    ).strftime("%Y-%m-%dT%H:%M:%SZ")
    wg = types.SimpleNamespace(meta=types.SimpleNamespace(
        id="wg_settle", name="site", hub_pubkey="HUB", paused=False,
        pipelines={"intake": ("intake", "qa")}, launch_pipeline="intake",
        pipeline_steps={}, quorum_timeout_seconds=0,
    ))
    recent = [
        {"seq": 1, "from": "HUB", "text": "@scout #task #intake go", "ts": old},
        {"seq": 2, "from": "SCOUTPK", "text": "#working reading files", "ts": old},
    ]
    spawned: list[str] = []
    monkeypatch.setattr(service, "_spawn_dispatch", lambda wid, coro: spawned.append(wid))
    monkeypatch.setattr(service, "_dispatch_workgroup_turn", lambda *a, **k: None)
    monkeypatch.setattr(service, "_budget_blocks_dispatch", lambda *a, **k: False)

    service._LAST_TURN_END["wg_settle"] = _time.monotonic()
    try:
        await service._maybe_watchdog_close(home, "mira", wg, recent)
        assert spawned == []

        service._LAST_TURN_END["wg_settle"] = (
            _time.monotonic() - service._TURN_SETTLE_SECONDS - 1
        )
        await service._maybe_watchdog_close(home, "mira", wg, recent)
        assert spawned == ["wg_settle"]
    finally:
        service._LAST_TURN_END.pop("wg_settle", None)


def test_phase_turn_budget_reads_the_active_phase_spec() -> None:
    phase_map = {"intake": {"owner": "scout", "turn_budget_s": 1800}, "qa": {"owner": "lens"}}
    posts = [
        {"seq": 1, "from": "HUB", "text": "@scout #task #intake go"},
        {"seq": 2, "from": "SCOUTPK", "text": "#working"},
    ]
    assert service._phase_turn_budget(phase_map, posts, "HUB") == 1800
    posts.append({"seq": 3, "from": "HUB", "text": "#done wrapped"})
    posts.append({"seq": 4, "from": "HUB", "text": "@lens #task #qa audit"})
    assert service._phase_turn_budget(phase_map, posts, "HUB") == 0
    assert service._phase_turn_budget({}, posts, "HUB") == 0
    assert service._phase_turn_budget(phase_map, [], "HUB") == 0


def test_phase_turn_budget_recovery_slugs_inherit_the_declared_phase() -> None:
    phase_map = {
        "intake": {"owner": "scout", "turn_budget_s": 1800},
        "intake-recheck": {"owner": "scout", "turn_budget_s": 600},
    }
    fix = [
        {"seq": 1, "from": "HUB", "text": "@scout #task #intake-fix redo the intake"},
        {"seq": 2, "from": "SCOUTPK", "text": "#working"},
    ]
    assert service._phase_turn_budget(phase_map, fix, "HUB") == 1800
    recheck = [
        {"seq": 1, "from": "HUB", "text": "@scout #task #intake-recheck verify"},
    ]
    assert service._phase_turn_budget(phase_map, recheck, "HUB") == 600
    unrelated = [
        {"seq": 1, "from": "HUB", "text": "@scout #task #intakeplus other"},
    ]
    assert service._phase_turn_budget(phase_map, unrelated, "HUB") == 0


def test_phase_write_scope_is_owner_only_and_canonicalizes_recovery_slug() -> None:
    phase_map = {
        "content": {
            "owner": "quill", "cwd": "projects/hotel",
            "paths": ["src/content/**"],
        },
    }
    posts = [{"seq": 1, "from": "HUB", "text": "@quill #task #content-recheck fix"}]

    assert service._phase_write_scope(phase_map, posts, "HUB", "quill") == {
        "root": "projects/hotel", "paths": ["src/content/**"],
        "phase": "content", "owner": "quill",
    }
    assert service._phase_write_scope(phase_map, posts, "HUB", "mira") == {
        "root": "", "paths": [], "phase": "content", "owner": "quill",
    }


def test_phase_write_scope_fails_closed_for_legacy_unroutable_slug() -> None:
    phase_map = {
        "content": {
            "owner": "quill", "cwd": "projects/hotel",
            "paths": ["src/content/**"],
        },
    }
    posts = [{"seq": 1, "from": "HUB", "text": "@quill #task #fix-locales repair"}]

    assert service._phase_write_scope(phase_map, posts, "HUB", "quill") == {
        "root": "", "paths": [], "phase": "fix-locales", "owner": "",
    }


def test_phase_write_scope_does_not_restrict_deliberation_workgroups() -> None:
    posts = [{"seq": 1, "from": "HUB", "text": "@quill #task #content write"}]

    assert service._phase_write_scope({}, posts, "HUB", "quill") is None
    assert service._phase_write_scope({}, posts, "HUB", "mira") is None


def test_a_green_repair_of_the_terminal_phase_completes_the_pipeline() -> None:
    """A chain-local suffix allowlist reopened build after a verified `#qa-repair`."""
    wg = _pipe_wg(LAUNCH, dormant=MEDIA_CHAIN)
    recent = _closed(("setup", 2), ("intake", 4), ("build", 6))
    recent += [
        {"seq": 7, "from": "HUB", "text": "@lens #task #qa audit"},
        {"seq": 8, "from": "HUB", "text": "#done QA FAIL · 3 findings"},
        {"seq": 9, "from": "HUB", "text": "@scout #task #qa-repair fix them"},
        {"seq": 10, "from": "HUB", "text": "#done qa-repair verified · gate:npm · clean"},
    ]
    assert wg_mod.canonical_pipeline_phase(wg.meta, "qa-repair")[1] == "qa"
    assert service._next_pipeline_phase(wg, recent) == (None, "qa", True)


def test_working_heartbeat_does_not_wake_the_hub() -> None:
    posts = [
        {"seq": 1, "from": "HUB", "text": "@scout #task #intake produce site.json"},
        {"seq": 2, "from": "SCOUT", "text": "#working authoring intake from brief (write_file)"},
    ]
    trigger, _ = service._should_dispatch(
        "mira", "HUB", posts, 1, hub_pubkey="HUB", pipeline=True,
    )
    assert trigger is None


def test_working_heartbeat_mentioning_the_hub_still_wakes_it() -> None:
    posts = [
        {"seq": 1, "from": "HUB", "text": "@scout #task #intake produce site.json"},
        {"seq": 2, "from": "SCOUT", "text": "#working @mira the brief lacks a tax id — confirm placeholder?"},
    ]
    trigger, _ = service._should_dispatch(
        "mira", "HUB", posts, 1, hub_pubkey="HUB", pipeline=True,
    )
    assert trigger and "mentioned" in trigger


def test_working_heartbeat_with_a_blocker_wakes_the_hub() -> None:
    posts = [
        {"seq": 1, "from": "HUB", "text": "@scout #task #intake produce site.json"},
        {
            "seq": 2,
            "from": "SCOUT",
            "text": "#working checking the brief\nBLOCKER missing canonical room rows",
        },
    ]
    trigger, _ = service._should_dispatch(
        "mira", "HUB", posts, 1, hub_pubkey="HUB", pipeline=True,
    )
    assert trigger and "blocker in active task" in trigger


def test_working_marker_with_a_delivery_wakes_the_hub() -> None:
    posts = [
        {"seq": 1, "from": "HUB", "text": "@scout #task #intake produce site.json"},
        {
            "seq": 2,
            "from": "SCOUT",
            "text": "#working writing intake\ndelivered site.json and work/intake.md",
        },
    ]
    trigger, _ = service._should_dispatch(
        "mira", "HUB", posts, 1, hub_pubkey="HUB", pipeline=True,
    )
    assert trigger and "active task we opened" in trigger


def test_substantive_delivery_still_wakes_the_hub() -> None:
    posts = [
        {"seq": 1, "from": "HUB", "text": "@scout #task #intake produce site.json"},
        {"seq": 2, "from": "SCOUT", "text": "intake complete · site.json + work/intake.md written, check green. Handing off."},
    ]
    trigger, _ = service._should_dispatch(
        "mira", "HUB", posts, 1, hub_pubkey="HUB", pipeline=True,
    )
    assert trigger and "active task we opened" in trigger


@pytest.mark.asyncio
async def test_subscription_poller_reads_subscriptions_off_the_event_loop(
    monkeypatch,
) -> None:
    import threading
    from alpi.alp import workgroup_client as wc

    loop_thread = threading.get_ident()
    threads: list[int] = []
    second_started = asyncio.Event()

    sub = types.SimpleNamespace(
        wg_id="wg_hot", recent_posts=[], hub_pubkey="hub",
        last_responded_seq=0, last_dispatch_at="", paused=False, pipeline_mode=False,
    )

    def fake_get(home, wid):
        threads.append(threading.get_ident())
        return sub

    async def fake_pull(home, wg_id, wait_s=0.0):
        if threads.count(loop_thread) or len(threads) >= 3:
            second_started.set()
            await asyncio.Event().wait()
        return [], 0

    monkeypatch.setattr(sub_mod, "get", fake_get)
    monkeypatch.setattr(wc, "pull", fake_pull)
    monkeypatch.setattr(service, "_WG_HOT_TICK_SECONDS", 0)
    monkeypatch.setattr(
        service, "_maybe_dispatch_for_sub", lambda *a, **k: asyncio.sleep(0),
    )

    worker = asyncio.create_task(
        service._run_subscription_poller(Path("/tmp/none"), "alice", "wg_hot")
    )
    try:
        await asyncio.wait_for(second_started.wait(), timeout=2)
    finally:
        worker.cancel()
        await asyncio.gather(worker, return_exceptions=True)

    assert len(threads) >= 3
    assert loop_thread not in threads


@pytest.mark.asyncio
async def test_subscription_poller_keeps_polling_when_engine_turns_saturate_the_default_pool(
    monkeypatch,
) -> None:
    import threading
    from concurrent.futures import ThreadPoolExecutor
    from alpi.alp import workgroup_client as wc

    loop = asyncio.get_running_loop()
    hog_pool = ThreadPoolExecutor(max_workers=1)
    loop.set_default_executor(hog_pool)
    release = threading.Event()
    occupied = threading.Event()

    def hog() -> None:
        occupied.set()
        release.wait(30)

    hog_future = loop.run_in_executor(None, hog)
    while not occupied.is_set():
        await asyncio.sleep(0.01)

    iterations = 0
    third_pull = asyncio.Event()
    sub = types.SimpleNamespace(
        wg_id="wg_hot", recent_posts=[], hub_pubkey="hub",
        last_responded_seq=0, last_dispatch_at="", paused=False, pipeline_mode=False,
    )

    async def fake_pull(home, wg_id, wait_s=0.0):
        nonlocal iterations
        iterations += 1
        if iterations >= 3:
            third_pull.set()
            await asyncio.Event().wait()
        return [], 0

    monkeypatch.setattr(sub_mod, "get", lambda home, wid: sub)
    monkeypatch.setattr(wc, "pull", fake_pull)
    monkeypatch.setattr(service, "_WG_HOT_TICK_SECONDS", 0)
    monkeypatch.setattr(
        service, "_maybe_dispatch_for_sub", lambda *a, **k: asyncio.sleep(0),
    )

    worker = asyncio.create_task(
        service._run_subscription_poller(Path("/tmp/none"), "alice", "wg_hot")
    )
    try:
        await asyncio.wait_for(third_pull.wait(), timeout=5)
    finally:
        worker.cancel()
        await asyncio.gather(worker, return_exceptions=True)
        release.set()
        await hog_future
        hog_pool.shutdown(wait=True)

    assert iterations >= 3




# A repeated definitive hub rejection retires the subscription; everything else retries forever.


_FINISHED_RUN = [
    {"seq": 1, "from": "hub_pk", "text": "@alice #task #build ship the site"},
    {"seq": 2, "from": "alice_pk", "text": "#done build · dist/ written"},
    {"seq": 3, "from": "hub_pk", "text": "#done build · gate: green"},
    {"seq": 4, "from": "hub_pk", "text": "@alice #task #qa audit it"},
    {"seq": 5, "from": "alice_pk", "text": "#done qa · 0 findings"},
    {"seq": 6, "from": "hub_pk", "text": "#done qa · gate: green"},
]
_PIPELINE = {"main": ("build", "qa")}


def _idle_sub(wg_id: str = "wg_cold", posts: list | None = None, **extra):
    fields = dict(
        wg_id=wg_id, name=wg_id, recent_posts=posts or [], hub_pubkey="hub_pk",
        last_responded_seq=0, last_dispatch_at="", paused=False,
        pipeline_mode=False, pipelines={}, phase_map={},
    )
    fields.update(extra)
    return types.SimpleNamespace(**fields)


async def _no_dispatch(*args, **kwargs) -> bool:
    return False


def _record_sleeps(monkeypatch) -> list[float]:
    slept: list[float] = []
    real = asyncio.sleep

    async def fake(delay, *args, **kwargs):
        slept.append(float(delay))
        return await real(0, *args, **kwargs)

    monkeypatch.setattr(asyncio, "sleep", fake)
    return slept


def _persisted_sub(home: Path, wg_id: str, hub_pubkey: str = "hub_pk") -> None:
    sub_mod.upsert(home, sub_mod.Subscription(
        wg_id=wg_id, name=wg_id, hub_id="hub", hub_pubkey=hub_pubkey,
        sealed_keys=[sub_mod.SealedKey(version=1, sealed="secret")],
    ))


async def _drive_failing_poller(
    home: Path, wg_id: str, monkeypatch, errors, *, expect_exit: bool,
    pause_after: int = 0, pause: float = 0.0,
) -> int:
    from alpi.alp import workgroup_client as wc

    _record_sleeps(monkeypatch)
    attempts = 0
    parked = asyncio.Event()

    async def fake_pull(h, wid, wait_s=0.0):
        nonlocal attempts
        if attempts >= len(errors):
            parked.set()
            await asyncio.Event().wait()
        # Blocking on purpose: the recorded asyncio.sleep no longer advances the clock the time floor is measured against.
        if pause and attempts == pause_after:
            time.sleep(pause)
        err = errors[attempts]
        attempts += 1
        if err is None:
            return [], 0
        raise err

    monkeypatch.setattr(wc, "pull", fake_pull)
    monkeypatch.setattr(service, "_maybe_dispatch_for_sub", _no_dispatch)
    worker = asyncio.create_task(
        service._run_subscription_poller(home, "alice", wg_id)
    )
    try:
        if expect_exit:
            await asyncio.wait_for(worker, timeout=5)
        else:
            await asyncio.wait_for(parked.wait(), timeout=5)
    finally:
        worker.cancel()
        await asyncio.gather(worker, return_exceptions=True)
    return attempts


def test_definitive_pull_rejection_recognised_only_for_the_two_codes() -> None:
    from alpi.alp.client import ClientError, RemoteError

    assert service._is_definitive_pull_rejection(
        RemoteError(-32009, "workgroup-not-found")) is True
    assert service._is_definitive_pull_rejection(
        RemoteError(-32008, "workgroup-not-member")) is True
    # Same code, different reason — the hub still holds the workgroup.
    assert service._is_definitive_pull_rejection(
        RemoteError(-32008, "workgroup-not-hub")) is False
    assert service._is_definitive_pull_rejection(
        RemoteError(-32008, "workgroup-not-joined")) is False
    assert service._is_definitive_pull_rejection(
        RemoteError(-32005, "rate-limited")) is False
    assert service._is_definitive_pull_rejection(
        RemoteError(-32005, "budget-exceeded")) is False
    assert service._is_definitive_pull_rejection(
        RemoteError(-32603, "internal-error")) is False
    assert service._is_definitive_pull_rejection(
        RemoteError(-32001, "capability-denied")) is False
    assert service._is_definitive_pull_rejection(ClientError("transport failed")) is False
    assert service._is_definitive_pull_rejection(asyncio.TimeoutError()) is False


def test_both_retirement_gates_are_non_degenerate() -> None:
    # A single rejection must never be able to retire: a hub that restarted and has not loaded its workgroups yet answers definitively for seconds.
    assert service._WG_RETIRE_AFTER_REJECTIONS >= 2
    assert service._WG_RETIRE_MIN_SECONDS > 0.0


def test_the_shipped_backoff_puts_retirement_well_past_the_time_floor() -> None:
    elapsed = 0.0
    at: list[float] = []
    for failure in range(1, 12):
        at.append(elapsed)
        elapsed += service.WORKGROUP_TICK_SECONDS * service._wg_backoff_mult(failure)
    retire_index = next(
        i for i, t in enumerate(at, start=1)
        if i >= service._WG_RETIRE_AFTER_REJECTIONS
        and t >= service._WG_RETIRE_MIN_SECONDS
    )
    # 30/30/60/120/240s of backoff: the 5th rejection lands at 240s, under the floor, so retirement is the 6th at 480s.
    assert (retire_index, at[retire_index - 1]) == (6, 480.0)


@pytest.mark.asyncio
async def test_one_definitive_rejection_never_retires_at_shipped_constants(
    short_tmp: Path, monkeypatch,
) -> None:
    from alpi.alp.client import RemoteError

    home = short_tmp / "member"
    _persisted_sub(home, "wg_dead")

    attempts = await _drive_failing_poller(
        home, "wg_dead", monkeypatch,
        [RemoteError(-32009, "workgroup-not-found")],
        expect_exit=False,
    )

    assert attempts == 1
    assert sub_mod.get(home, "wg_dead") is not None
    assert "secret" in sub_mod.path(home).read_text()
    assert sub_mod.retired(home) == set()


@pytest.mark.asyncio
@pytest.mark.parametrize("code,message", [
    (-32009, "workgroup-not-found"),
    (-32008, "workgroup-not-member"),
])
async def test_repeated_definitive_rejection_retires_and_archives_the_keys(
    short_tmp: Path, monkeypatch, code: int, message: str,
) -> None:
    from alpi.alp.client import RemoteError

    home = short_tmp / "member"
    _persisted_sub(home, "wg_dead")
    monkeypatch.setattr(service, "_WG_RETIRE_MIN_SECONDS", 0.0)

    n = service._WG_RETIRE_AFTER_REJECTIONS
    attempts = await _drive_failing_poller(
        home, "wg_dead", monkeypatch,
        [RemoteError(code, message) for _ in range(n + 3)],
        expect_exit=True,
    )

    assert attempts == n
    assert sub_mod.get(home, "wg_dead") is None
    assert "secret" not in sub_mod.path(home).read_text()
    # The inference is reversible: the sealed keys survive in the archive, so a wrong call costs a re-join, not the transcript history.
    assert sub_mod.retired(home) == {"wg_dead"}
    assert "secret" in sub_mod.retired_path(home).read_text()


@pytest.mark.asyncio
async def test_retirement_never_tombstones_so_the_hub_can_still_heal_it(
    short_tmp: Path, monkeypatch,
) -> None:
    from alpi.alp.client import RemoteError

    home = short_tmp / "member"
    _persisted_sub(home, "wg_dead")
    monkeypatch.setattr(service, "_WG_RETIRE_MIN_SECONDS", 0.0)

    n = service._WG_RETIRE_AFTER_REJECTIONS
    await _drive_failing_poller(
        home, "wg_dead", monkeypatch,
        [RemoteError(-32009, "workgroup-not-found") for _ in range(n)],
        expect_exit=True,
    )

    assert sub_mod.tombstones(home) == set()
    # `_auto_join_local_members` heals through upsert; a tombstone would make that a permanent silent no-op.
    sub_mod.upsert(home, sub_mod.Subscription(
        wg_id="wg_dead", name="wg_dead", hub_id="hub", hub_pubkey="hub_pk",
        sealed_keys=[sub_mod.SealedKey(version=1, sealed="resealed")],
    ))
    restored = sub_mod.get(home, "wg_dead")
    assert restored is not None
    assert restored.sealed_for(1) == "resealed"


@pytest.mark.asyncio
async def test_a_live_local_hub_outranks_its_own_definitive_rejection(
    short_tmp: Path, monkeypatch,
) -> None:
    from alpi.alp import keys as keys_mod
    from alpi.alp.client import RemoteError

    root = short_tmp / "alpi"
    monkeypatch.setenv("ALPI_HOME", str(root))
    hub_home = root / "profiles" / "hub"
    hub_home.mkdir(parents=True)
    hub_kp = keys_mod.load_or_generate(hub_home)
    wg_mod._save_meta(
        hub_home / "alp" / "workgroups" / "wg_torn",
        wg_mod.Meta(
            id="wg_torn", name="torn", hub_pubkey=hub_kp.pubkey_b64(),
            created_at="2026-08-01T00:00:00Z", current_key_version=1,
        ),
    )
    # An interrupted roster write is indistinguishable from a deletion over the wire: an empty members.yaml answers workgroup-not-member forever.
    (hub_home / "alp" / "workgroups" / "wg_torn" / "members.yaml").write_text("")

    member = root / "profiles" / "alice"
    _persisted_sub(member, "wg_torn", hub_pubkey=hub_kp.pubkey_b64())
    monkeypatch.setattr(service, "_WG_RETIRE_MIN_SECONDS", 0.0)

    n = service._WG_RETIRE_AFTER_REJECTIONS
    await _drive_failing_poller(
        member, "wg_torn", monkeypatch,
        [RemoteError(-32008, "workgroup-not-member") for _ in range(n * 3)],
        expect_exit=False,
    )

    assert sub_mod.get(member, "wg_torn") is not None
    assert sub_mod.retired(member) == set()


@pytest.mark.asyncio
async def test_retirement_waits_for_the_time_floor_then_fires(
    short_tmp: Path, monkeypatch,
) -> None:
    from alpi.alp.client import RemoteError

    home = short_tmp / "member"
    _persisted_sub(home, "wg_dead")
    monkeypatch.setattr(service, "_WG_RETIRE_MIN_SECONDS", 0.2)

    n = service._WG_RETIRE_AFTER_REJECTIONS
    attempts = await _drive_failing_poller(
        home, "wg_dead", monkeypatch,
        [RemoteError(-32009, "workgroup-not-found") for _ in range(n + 4)],
        expect_exit=True, pause_after=n, pause=0.25,
    )

    # The count gate is met on the Nth, but only the rejection after the floor elapsed may retire.
    assert attempts == n + 1
    assert sub_mod.get(home, "wg_dead") is None
    assert sub_mod.retired(home) == {"wg_dead"}


@pytest.mark.asyncio
async def test_one_short_of_n_definitive_rejections_keeps_the_subscription(
    short_tmp: Path, monkeypatch,
) -> None:
    from alpi.alp.client import RemoteError

    home = short_tmp / "member"
    _persisted_sub(home, "wg_dead")
    monkeypatch.setattr(service, "_WG_RETIRE_MIN_SECONDS", 0.0)

    n = service._WG_RETIRE_AFTER_REJECTIONS
    attempts = await _drive_failing_poller(
        home, "wg_dead", monkeypatch,
        [RemoteError(-32009, "workgroup-not-found") for _ in range(n - 1)],
        expect_exit=False,
    )

    assert attempts == n - 1
    assert sub_mod.get(home, "wg_dead") is not None
    assert sub_mod.retired(home) == set()


@pytest.mark.asyncio
async def test_transport_failures_never_retire_however_many_repeat(
    short_tmp: Path, monkeypatch,
) -> None:
    from alpi.alp.client import ClientError, TargetOffline

    home = short_tmp / "member"
    _persisted_sub(home, "wg_live")
    monkeypatch.setattr(service, "_WG_RETIRE_MIN_SECONDS", 0.0)

    errors: list[BaseException] = []
    for _ in range(10):
        errors += [
            TargetOffline("socket gone"),
            ClientError("transport failed"),
            asyncio.TimeoutError(),
            ValueError("[decrypt failed: no sealed key for version 3]"),
        ]
    attempts = await _drive_failing_poller(
        home, "wg_live", monkeypatch, errors, expect_exit=False,
    )

    assert attempts == 40
    assert sub_mod.get(home, "wg_live") is not None
    assert sub_mod.retired(home) == set()


@pytest.mark.asyncio
async def test_a_successful_pull_resets_the_definitive_rejection_run(
    short_tmp: Path, monkeypatch,
) -> None:
    from alpi.alp.client import RemoteError

    home = short_tmp / "member"
    _persisted_sub(home, "wg_flap")
    monkeypatch.setattr(service, "_WG_RETIRE_MIN_SECONDS", 0.0)
    monkeypatch.setattr(sub_mod, "get", lambda h, wid: _idle_sub("wg_flap"))

    n = service._WG_RETIRE_AFTER_REJECTIONS
    reject = RemoteError(-32009, "workgroup-not-found")
    errors: list = [reject] * (n - 1) + [None] + [reject] * (n - 1)
    attempts = await _drive_failing_poller(
        home, "wg_flap", monkeypatch, errors, expect_exit=False,
    )

    assert attempts == 2 * n - 1
    monkeypatch.undo()
    assert sub_mod.get(home, "wg_flap") is not None
    assert sub_mod.retired(home) == set()


@pytest.mark.asyncio
async def test_a_transport_error_also_breaks_the_definitive_run(
    short_tmp: Path, monkeypatch,
) -> None:
    from alpi.alp.client import ClientError, RemoteError

    home = short_tmp / "member"
    _persisted_sub(home, "wg_flap")
    monkeypatch.setattr(service, "_WG_RETIRE_MIN_SECONDS", 0.0)

    n = service._WG_RETIRE_AFTER_REJECTIONS
    reject = RemoteError(-32008, "workgroup-not-member")
    errors: list = [reject] * (n - 1) + [ClientError("hub unreachable")] + [reject] * (n - 1)
    await _drive_failing_poller(home, "wg_flap", monkeypatch, errors, expect_exit=False)

    assert sub_mod.get(home, "wg_flap") is not None
    assert sub_mod.retired(home) == set()


@pytest.mark.asyncio
async def test_the_count_alone_cannot_retire_before_the_time_floor(
    short_tmp: Path, monkeypatch,
) -> None:
    from alpi.alp.client import RemoteError

    home = short_tmp / "member"
    _persisted_sub(home, "wg_dead")
    # A hub that restarted behind a slow mount rejects fast and often; only elapsed time separates it from a deleted workgroup.
    monkeypatch.setattr(service, "_WG_RETIRE_AFTER_REJECTIONS", 2)
    monkeypatch.setattr(service, "_WG_RETIRE_MIN_SECONDS", 3600.0)

    await _drive_failing_poller(
        home, "wg_dead", monkeypatch,
        [RemoteError(-32009, "workgroup-not-found") for _ in range(20)],
        expect_exit=False,
    )

    assert sub_mod.get(home, "wg_dead") is not None
    assert sub_mod.retired(home) == set()


def test_a_retired_workgroup_cancels_an_in_flight_dispatch(short_tmp: Path) -> None:
    home = short_tmp / "member"
    _persisted_sub(home, "wg_dead")
    assert service._dispatch_cancel_reason(home, "wg_dead") == ""
    assert sub_mod.retire(home, "wg_dead") is True
    assert service._dispatch_cancel_reason(home, "wg_dead") == "workgroup-removed"


# Idle subscriptions cool their cadence; live ones keep full rate.


def test_the_cold_cap_stays_inside_the_hub_stall_window() -> None:
    # A cooled member must pull, and dispatch, before `_maybe_watchdog_close` reads its silence as a stall and burns a rung of the bounded recovery ladder.
    assert (
        service._WG_COLD_SLEEP_MAX_SECONDS + service._WG_LONG_POLL_SECONDS
        < service._TURN_SETTLE_SECONDS
    )


def test_cold_sleep_ladder_holds_full_rate_then_escalates_to_the_cap() -> None:
    k = service._WG_COLD_AFTER_EMPTY_PULLS
    cap = service._WG_COLD_SLEEP_MAX_SECONDS
    assert [service._wg_cold_sleep(i) for i in range(k)] == [0.0] * k
    assert service._wg_cold_sleep(k) == 30.0
    assert service._wg_cold_sleep(k + 1) == 60.0
    assert service._wg_cold_sleep(k + 2) == cap
    assert service._wg_cold_sleep(k + 3) == cap
    # Days of silence must not overflow the shift into an unreachable sleep.
    assert service._wg_cold_sleep(k + 100_000) == cap


async def _drive_polling_poller(
    monkeypatch, sub, answers: list[list], *, hot_tick: float | None = 0.0,
    fast_hub: bool = True, dispatch=None,
) -> tuple[list[float], list[float]]:
    from alpi.alp import workgroup_client as wc

    slept = _record_sleeps(monkeypatch)
    waits: list[float] = []
    parked = asyncio.Event()

    async def fake_pull(h, wid, wait_s=0.0):
        if len(waits) >= len(answers):
            parked.set()
            await asyncio.Event().wait()
        waits.append(float(wait_s))
        return answers[len(waits) - 1], 0

    monkeypatch.setattr(sub_mod, "get", lambda h, wid: sub)
    monkeypatch.setattr(wc, "pull", fake_pull)
    monkeypatch.setattr(service, "_maybe_dispatch_for_sub", dispatch or _no_dispatch)
    if hot_tick is not None:
        monkeypatch.setattr(service, "_WG_HOT_TICK_SECONDS", hot_tick)
    if not fast_hub:
        # A hub that honours wait_s returns after ~25s, so the poller must reach the cold sleep on its own.
        monkeypatch.setattr(service, "_WG_FAST_HUB_SECONDS", 0.0)

    worker = asyncio.create_task(
        service._run_subscription_poller(Path("/tmp/none"), "alice", sub.wg_id)
    )
    try:
        await asyncio.wait_for(parked.wait(), timeout=5)
    finally:
        worker.cancel()
        await asyncio.gather(worker, return_exceptions=True)
    return slept, waits


@pytest.mark.asyncio
async def test_a_long_polling_hub_cools_on_the_escalating_ladder(monkeypatch) -> None:
    k = service._WG_COLD_AFTER_EMPTY_PULLS
    cap = service._WG_COLD_SLEEP_MAX_SECONDS
    slept, waits = await _drive_polling_poller(
        monkeypatch, _idle_sub(), [[] for _ in range(k + 4)],
        hot_tick=None, fast_hub=False,
    )

    assert len(waits) == k + 4
    assert set(waits) == {service._WG_LONG_POLL_SECONDS}
    # K empty pulls of full rate first, then the ladder — nothing sleeps before that.
    assert slept == [30.0, 60.0, cap, cap, cap]


@pytest.mark.asyncio
async def test_a_pre_long_poll_hub_paces_at_the_hot_tick_then_cools(
    monkeypatch,
) -> None:
    k = service._WG_COLD_AFTER_EMPTY_PULLS
    cap = service._WG_COLD_SLEEP_MAX_SECONDS
    slept, waits = await _drive_polling_poller(
        monkeypatch, _idle_sub(), [[] for _ in range(k + 3)], hot_tick=None,
    )

    assert set(waits) == {service._WG_LONG_POLL_SECONDS}
    assert slept == [service._WG_HOT_TICK_SECONDS] * (k - 1) + [30.0, 60.0, cap, cap]


@pytest.mark.asyncio
async def test_a_finished_pipeline_run_cools(monkeypatch) -> None:
    k = service._WG_COLD_AFTER_EMPTY_PULLS
    sub = _idle_sub(
        "wg_shipped", posts=list(_FINISHED_RUN),
        pipelines=_PIPELINE, pipeline_mode=True, last_responded_seq=6,
    )
    slept, _waits = await _drive_polling_poller(
        monkeypatch, sub, [[] for _ in range(k + 2)],
        hot_tick=None, fast_hub=False,
    )

    assert slept == [30.0, 60.0, service._WG_COLD_SLEEP_MAX_SECONDS]


@pytest.mark.asyncio
async def test_a_closed_phase_awaiting_its_successor_keeps_full_rate(
    monkeypatch,
) -> None:
    k = service._WG_COLD_AFTER_EMPTY_PULLS
    # The hub closed #build and has not opened #qa yet: cooling here delays the phase handoff by a whole cold sleep.
    sub = _idle_sub(
        "wg_handoff", posts=list(_FINISHED_RUN[:3]),
        pipelines=_PIPELINE, pipeline_mode=True, last_responded_seq=3,
    )
    slept, _waits = await _drive_polling_poller(
        monkeypatch, sub, [[] for _ in range(k * 3)],
        hot_tick=None, fast_hub=False,
    )

    assert slept == []


@pytest.mark.asyncio
async def test_a_single_post_returns_a_cooled_subscription_to_full_rate(
    monkeypatch,
) -> None:
    k = service._WG_COLD_AFTER_EMPTY_PULLS
    answers: list[list] = [[] for _ in range(k + 2)]
    answers.append([{"seq": 4, "from": "hub_pk", "text": "#done shipped"}])
    answers += [[] for _ in range(3)]

    slept, _waits = await _drive_polling_poller(
        monkeypatch, _idle_sub(), answers, hot_tick=None, fast_hub=False,
    )

    assert slept == [30.0, 60.0, service._WG_COLD_SLEEP_MAX_SECONDS]


@pytest.mark.asyncio
async def test_an_open_task_keeps_full_rate_however_long_the_hub_stays_quiet(
    monkeypatch,
) -> None:
    sub = _idle_sub("wg_open", posts=[
        {"seq": 1, "from": "hub_pk", "text": "@alice #task #build ship it"},
    ])
    k = service._WG_COLD_AFTER_EMPTY_PULLS
    slept, waits = await _drive_polling_poller(
        monkeypatch, sub, [[] for _ in range(k * 3)],
        hot_tick=None, fast_hub=False,
    )

    assert set(waits) == {service._WG_LONG_POLL_SECONDS}
    assert slept == []


@pytest.mark.asyncio
async def test_a_transcript_older_than_the_recovery_ladder_cools_anyway(
    monkeypatch,
) -> None:
    stale = (
        _dt.datetime.now(tz=_dt.timezone.utc)
        - _dt.timedelta(seconds=service._WG_HOT_TRANSCRIPT_HORIZON_SECONDS + 60)
    ).strftime("%Y-%m-%dT%H:%M:%SZ")
    # An abandoned run leaves its #task open forever; past the hub's whole recovery ladder that is not evidence of live work.
    sub = _idle_sub("wg_abandoned", posts=[
        {"seq": 1, "from": "hub_pk", "text": "@alice #task #build ship it", "ts": stale},
    ])
    k = service._WG_COLD_AFTER_EMPTY_PULLS
    slept, _waits = await _drive_polling_poller(
        monkeypatch, sub, [[] for _ in range(k + 2)],
        hot_tick=None, fast_hub=False,
    )

    assert slept == [30.0, 60.0, service._WG_COLD_SLEEP_MAX_SECONDS]


@pytest.mark.asyncio
async def test_a_fresh_open_task_still_keeps_full_rate(monkeypatch) -> None:
    fresh = _dt.datetime.now(tz=_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    sub = _idle_sub("wg_working", posts=[
        {"seq": 1, "from": "hub_pk", "text": "@alice #task #build ship it", "ts": fresh},
    ])
    k = service._WG_COLD_AFTER_EMPTY_PULLS
    slept, _waits = await _drive_polling_poller(
        monkeypatch, sub, [[] for _ in range(k + 2)],
        hot_tick=None, fast_hub=False,
    )

    assert slept == []


@pytest.mark.asyncio
async def test_an_undispatched_trigger_keeps_full_rate(monkeypatch) -> None:
    async def _pending(*args, **kwargs) -> bool:
        return True

    k = service._WG_COLD_AFTER_EMPTY_PULLS
    slept, _waits = await _drive_polling_poller(
        monkeypatch, _idle_sub(), [[] for _ in range(k + 2)],
        hot_tick=None, fast_hub=False, dispatch=_pending,
    )

    # A trigger blocked on cooldown or budget is work outstanding; `hot` alone does not see it.
    assert slept == []


@pytest.mark.asyncio
async def test_a_stream_of_posts_never_sleeps_at_all(monkeypatch) -> None:
    answers = [
        [{"seq": i, "from": "hub_pk", "text": f"#done step {i}"}]
        for i in range(1, 13)
    ]
    slept, waits = await _drive_polling_poller(
        monkeypatch, _idle_sub(), answers, hot_tick=None, fast_hub=False,
    )

    assert set(waits) == {service._WG_LONG_POLL_SECONDS}
    assert slept == []


@pytest.mark.asyncio
async def test_the_idle_run_restarts_from_zero_after_a_post(monkeypatch) -> None:
    # Zero hot window isolates the counter reset from the 120s hot hold that would otherwise mask it.
    monkeypatch.setattr(service, "_WG_HOT_WINDOW_SECONDS", 0.0)
    k = service._WG_COLD_AFTER_EMPTY_PULLS
    answers: list[list] = [[] for _ in range(k + 2)]
    answers.append([{"seq": 9, "from": "hub_pk", "text": "#done shipped"}])
    answers += [[] for _ in range(k)]

    slept, _waits = await _drive_polling_poller(
        monkeypatch, _idle_sub(), answers, hot_tick=None, fast_hub=False,
    )

    assert slept == [30.0, 60.0, service._WG_COLD_SLEEP_MAX_SECONDS, 30.0]


@pytest.mark.asyncio
async def test_an_outage_restarts_the_idle_ladder_at_full_rate(monkeypatch) -> None:
    from alpi.alp import workgroup_client as wc
    from alpi.alp.client import ClientError

    monkeypatch.setattr(service, "_WG_HOT_WINDOW_SECONDS", 0.0)
    monkeypatch.setattr(service, "_WG_FAST_HUB_SECONDS", 0.0)
    monkeypatch.setattr(service, "_WG_HOT_TICK_SECONDS", 0.0)
    k = service._WG_COLD_AFTER_EMPTY_PULLS
    slept = _record_sleeps(monkeypatch)
    script: list = [[] for _ in range(k + 2)] + [ClientError("hub gone")] \
        + [[] for _ in range(k)]
    calls = 0
    parked = asyncio.Event()

    async def fake_pull(h, wid, wait_s=0.0):
        nonlocal calls
        if calls >= len(script):
            parked.set()
            await asyncio.Event().wait()
        step = script[calls]
        calls += 1
        if isinstance(step, BaseException):
            raise step
        return step, 0

    monkeypatch.setattr(sub_mod, "get", lambda h, wid: _idle_sub())
    monkeypatch.setattr(wc, "pull", fake_pull)
    monkeypatch.setattr(service, "_maybe_dispatch_for_sub", _no_dispatch)

    worker = asyncio.create_task(
        service._run_subscription_poller(Path("/tmp/none"), "alice", "wg_cold")
    )
    try:
        await asyncio.wait_for(parked.wait(), timeout=5)
    finally:
        worker.cancel()
        await asyncio.gather(worker, return_exceptions=True)

    # The ladder, then the transport backoff tick, then the ladder from zero.
    assert slept == [
        30.0, 60.0, service._WG_COLD_SLEEP_MAX_SECONDS,
        float(service.WORKGROUP_TICK_SECONDS), 30.0,
    ]


def test_a_pull_wider_than_the_recent_cache_still_finds_its_own_task() -> None:
    pulled = [
        {"seq": 100, "from": "HUB", "text": "@alice #task #phase-2 build it"},
    ] + [
        {"seq": s, "from": "BOB", "text": f"#working step {s}"}
        for s in range(101, 126)
    ]
    # `append_recent` keeps only the newest RECENT_POSTS_CACHE, so the cached window has lost the opener.
    cached = pulled[-sub_mod.RECENT_POSTS_CACHE:]
    assert all(int(p["seq"]) > 100 for p in cached)

    merged = service._merged_posts(cached, pulled)
    trigger, responded = service._should_dispatch(
        "alice", "ALICE", merged, 99, hub_pubkey="HUB", pipeline=True,
    )
    assert trigger and "@alice mentioned" in trigger
    assert responded == 125
    # Scanning the trimmed cache alone loses the task and advances the cursor past it.
    blind, blind_responded = service._should_dispatch(
        "alice", "ALICE", cached, 99, hub_pubkey="HUB", pipeline=True,
    )
    assert blind is None
    assert blind_responded == 125


@pytest.mark.asyncio
async def test_the_poller_hands_the_pulled_window_to_the_dispatch_decision(
    short_tmp: Path, monkeypatch,
) -> None:
    from alpi.alp import workgroup_client as wc

    home = short_tmp / "alice"
    home.mkdir()
    pulled = [
        {"seq": 100, "from": "HUB", "text": "@alice #task #phase-2 build it"},
    ] + [
        {"seq": s, "from": "BOB", "text": f"#working step {s}"}
        for s in range(101, 126)
    ]
    sub = _idle_sub(
        "wg_burst", posts=pulled[-sub_mod.RECENT_POSTS_CACHE:],
        hub_pubkey="HUB", last_responded_seq=99, pipeline_mode=True,
    )
    kp = types.SimpleNamespace(pubkey_b64=lambda: "ALICE")
    monkeypatch.setattr("alpi.alp.keys.load_or_generate", lambda home: kp)
    monkeypatch.setattr(sub_mod, "get", lambda h, wid: sub)
    monkeypatch.setattr(sub_mod, "mutate", lambda *a, **k: None)
    monkeypatch.setattr(service, "_budget_blocks_dispatch", lambda *a: False)
    _record_sleeps(monkeypatch)
    spawned: list[str] = []

    def fake_spawn(wg_id, coro):
        spawned.append(wg_id)
        coro.close()

    def fake_turn(*args, **kwargs):
        return asyncio.sleep(0)

    monkeypatch.setattr(service, "_dispatch_workgroup_turn", fake_turn)
    monkeypatch.setattr(service, "_spawn_dispatch", fake_spawn)

    pulls = 0
    parked = asyncio.Event()

    async def fake_pull(h, wid, wait_s=0.0):
        nonlocal pulls
        if pulls:
            parked.set()
            await asyncio.Event().wait()
        pulls += 1
        return pulled, 125

    monkeypatch.setattr(wc, "pull", fake_pull)
    worker = asyncio.create_task(
        service._run_subscription_poller(home, "alice", "wg_burst")
    )
    try:
        await asyncio.wait_for(parked.wait(), timeout=5)
    finally:
        worker.cancel()
        await asyncio.gather(worker, return_exceptions=True)

    assert spawned == ["wg_burst"]
