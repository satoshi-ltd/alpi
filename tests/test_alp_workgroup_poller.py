"""Workgroup poller — `_should_dispatch` + cooldown + responded-seq.

The poller lives in ``alpi.service`` (it's a subsystem of the
unified per-profile orchestrator). These tests cover the pure
helpers — the wake decision (which uses the on-disk cache, NOT the
per-tick delta, so a missed cooldown window doesn't lose the
trigger), the cooldown gate, and the responded-seq tracking that
gates re-dispatch.
"""

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


# _should_dispatch — wake decision. New signature:
#   _should_dispatch(profile, own_pubkey, recent_posts, last_responded_seq)
#   -> (reason | None, new_responded_seq)


def test_self_mention_wakes() -> None:
    posts = [
        {"seq": 1, "text": "@alice please review", "from": "bob_pk"},
    ]
    reason, new_seq = service._should_dispatch("alice", "alice_pk", posts, 0)
    assert reason and "@alice mentioned" in reason
    assert new_seq == 1


def test_collective_task_with_no_mentions_wakes() -> None:
    """A `#task` post with no specific peers wakes everyone — it's a
    workgroup-wide call."""
    posts = [
        {"seq": 1, "text": "#task research peptides", "from": "user_pk"},
    ]
    reason, _ = service._should_dispatch("bob", "bob_pk", posts, 0)
    assert reason and "collective" in reason


def test_targeted_task_does_not_wake_unmentioned_peer() -> None:
    """A `#task` aimed at @alice must NOT wake bob — the task is for
    her. Bob still wakes if alice tags him directly later."""
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
    # Latest is bob's own post → no dispatch but advance pointer
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
    """Once the active #task tagged us by name, the latest post from
    someone else wakes us — keeps multi-round dialogue alive without
    forcing peers to spam @-mentions on every reply."""
    posts = [
        {"seq": 1, "text": "#task @alice @bob analyze the stack", "from": "user_pk"},
        {"seq": 2, "text": "I'd lean toward FastAPI + SQLite", "from": "alice_pk"},
    ]
    reason, new_seq = service._should_dispatch("bob", "bob_pk", posts, 0)
    assert reason and "active task" in reason
    assert new_seq == 2


def test_participant_silent_when_not_named_in_task() -> None:
    """If the active #task only tagged @alice (not bob), bob does NOT
    wake when alice replies — the task is alice's problem."""
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
    """The fix for the cursor/cooldown race — once we've responded to
    a seq, the same content doesn't keep firing on every tick."""
    posts = [
        {"seq": 1, "text": "#task @alice @bob analyze the stack", "from": "user_pk"},
        {"seq": 2, "text": "I'd lean toward FastAPI + SQLite", "from": "alice_pk"},
    ]
    # Mark bob as having responded up to seq 2 → no re-dispatch.
    reason, new_seq = service._should_dispatch("bob", "bob_pk", posts, 2)
    assert reason is None
    assert new_seq == 2


def test_re_fires_when_new_content_arrives_after_response() -> None:
    """If we responded to seq 2 and seq 3 lands from another peer in a
    workgroup we participate in, we wake again."""
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
