"""Crash-safe member dispatch + repair-path guards (workgroup-crash-recovery spec)."""

from __future__ import annotations

import inspect
import shutil
import tempfile
import types
from pathlib import Path

import pytest

from alpi import service
from alpi.alp import subscription as sub_mod
from alpi.alp import workgroup_client as wc


@pytest.fixture
def short_tmp() -> Path:
    d = Path(tempfile.mkdtemp(prefix="alpi-crash-", dir="/tmp"))
    try:
        yield d
    finally:
        shutil.rmtree(d, ignore_errors=True)


def _post(seq: int, from_: str, text: str) -> dict:
    return {"seq": seq, "from": from_, "text": text}


def _sub(home: Path, *, last_responded_seq: int = 0, last_dispatch_at: str = "") -> sub_mod.Subscription:
    sub = sub_mod.Subscription(
        wg_id="wg_crash", name="proj", hub_id="mira", hub_pubkey="HUB",
        last_responded_seq=last_responded_seq,
        last_dispatch_at=last_dispatch_at,
        pipeline=("intake", "assets"),
        recent_posts=[_post(5, "HUB", "@scout #task #intake produce work/intake.md")],
    )
    sub_mod.upsert(home, sub)
    return sub


@pytest.mark.asyncio
async def test_crashed_dispatch_redispatches_and_cursor_stays_behind(
    short_tmp: Path, monkeypatch,
) -> None:
    home = short_tmp / "h"
    home.mkdir(parents=True)
    sub = _sub(home, last_responded_seq=0, last_dispatch_at="2026-07-22T00:00:00Z")

    monkeypatch.setattr(
        "alpi.alp.keys.load_or_generate",
        lambda h: types.SimpleNamespace(pubkey_b64=lambda: "SCOUT_PK"),
    )
    captured: dict = {}

    async def fake_dispatch(*a, **kw):
        captured["kwargs"] = kw

    monkeypatch.setattr(service, "_dispatch_workgroup_turn", fake_dispatch)
    monkeypatch.setattr(
        service, "_latest_hub_task_seq_for", lambda h, w, hp: 5,
    )

    await service._maybe_dispatch_for_sub(home, "scout", sub)
    for t in list(service._BG_TASKS):
        await t

    assert captured, "open task addressed to this member must re-dispatch after a crash"
    assert captured["kwargs"]["member_responded_seq"] == 5
    on_disk = sub_mod.get(home, "wg_crash")
    assert on_disk.last_responded_seq == 0, "cursor must NOT advance at dispatch time"
    assert on_disk.last_dispatch_at != "2026-07-22T00:00:00Z"


def test_cursor_advances_only_via_completion_helper(short_tmp: Path) -> None:
    home = short_tmp / "h"
    home.mkdir(parents=True)
    _sub(home, last_responded_seq=0)

    service._advance_member_cursor(home, "wg_crash", 5)
    assert sub_mod.get(home, "wg_crash").last_responded_seq == 5

    service._advance_member_cursor(home, "wg_crash", 3)
    assert sub_mod.get(home, "wg_crash").last_responded_seq == 5, "cursor never regresses"


def _pipeline_wg() -> types.SimpleNamespace:
    return types.SimpleNamespace(
        meta=types.SimpleNamespace(pipeline=("intake", "assets")),
        members=[types.SimpleNamespace(pubkey="SCOUT_PK")],
    )


def _patch_peer_ids(monkeypatch) -> None:
    monkeypatch.setattr(
        wc.peers_mod, "get_by_pubkey",
        lambda home, pk: types.SimpleNamespace(id="scout") if pk == "SCOUT_PK" else None,
    )


def test_done_on_phase_with_zero_owner_posts_is_rejected(monkeypatch) -> None:
    _patch_peer_ids(monkeypatch)
    posts = [_post(1, "HUB", "@scout #task #intake produce work/intake.md")]
    with pytest.raises(ValueError, match="phase-owner-missing"):
        wc._check_pipeline_close_owner(
            Path("/nonexistent"), _pipeline_wg(), posts, "#done stalled", "HUB",
        )


def test_done_skipped_and_blocked_overrides_pass(monkeypatch) -> None:
    _patch_peer_ids(monkeypatch)
    posts = [_post(1, "HUB", "@scout #task #intake produce work/intake.md")]
    wc._check_pipeline_close_owner(
        Path("/nonexistent"), _pipeline_wg(), posts,
        "#done skipped · owner unreachable, phase waived", "HUB",
    )
    wc._check_pipeline_close_owner(
        Path("/nonexistent"), _pipeline_wg(), posts,
        "#done BLOCKED · intake · owner never delivered", "HUB",
    )


def test_done_passes_once_the_owner_posted(monkeypatch) -> None:
    _patch_peer_ids(monkeypatch)
    posts = [
        _post(1, "HUB", "@scout #task #intake produce work/intake.md"),
        _post(2, "SCOUT_PK", "delivered work/intake.md · summary attached"),
    ]
    wc._check_pipeline_close_owner(
        Path("/nonexistent"), _pipeline_wg(), posts, "#done intake complete", "HUB",
    )


def test_done_guard_ignores_non_pipeline_slugs(monkeypatch) -> None:
    _patch_peer_ids(monkeypatch)
    posts = [_post(1, "HUB", "@scout #task #adhoc one-off question")]
    wc._check_pipeline_close_owner(
        Path("/nonexistent"), _pipeline_wg(), posts, "#done answered", "HUB",
    )


def test_hub_may_retask_same_slug_when_owner_never_posted() -> None:
    posts = [
        _post(1, "HUB", "@scout #task #intake produce work/intake.md"),
        _post(2, "HUB", "nudge — any progress?"),
    ]
    wc._check_hub_rotation(
        posts, "HUB", "@scout #task #intake retry with the correct path", ["SCOUT_PK"],
        allow_stalled_retask=True,
    )


def test_stalled_retask_stays_rejected_in_non_pipeline_workgroups() -> None:
    posts = [
        _post(1, "HUB", "@scout #task #intake produce work/intake.md"),
        _post(2, "HUB", "nudge — any progress?"),
    ]
    with pytest.raises(ValueError, match="task-already-active"):
        wc._check_hub_rotation(
            posts, "HUB", "@scout #task #intake retry", ["SCOUT_PK"],
        )


def test_duplicate_slug_still_rejected_once_members_responded() -> None:
    posts = [
        _post(1, "HUB", "@scout #task #intake produce work/intake.md"),
        _post(2, "SCOUT_PK", "#working reading the brief"),
    ]
    with pytest.raises(ValueError, match="task-already-active"):
        wc._check_hub_rotation(
            posts, "HUB", "@scout #task #intake do it again", ["SCOUT_PK"],
        )


def test_repair_trigger_text_teaches_the_retask_move() -> None:
    src = inspect.getsource(service)
    assert "RE-TASK the owner: post a NEW" in src
    assert "#task #<same-phase>" in src
    assert "owner never delivered is forbidden" in src


def test_override_syntax_is_strict(monkeypatch) -> None:
    _patch_peer_ids(monkeypatch)
    posts = [_post(1, "HUB", "@scout #task #intake produce work/intake.md")]
    for bad in (
        "#done skipped-card complete",
        "#done blocked routes fixed",
        "#done skipped",
        "#done BLOCKED",
        "#done skipped ·   ",
    ):
        with pytest.raises(ValueError, match="phase-owner-missing"):
            wc._check_pipeline_close_owner(
                Path("/nonexistent"), _pipeline_wg(), posts, bad, "HUB",
            )


def test_unresolvable_owner_fails_closed(monkeypatch) -> None:
    monkeypatch.setattr(wc.peers_mod, "get_by_pubkey", lambda home, pk: None)
    posts = [
        _post(1, "HUB", "@scout #task #intake produce work/intake.md"),
        _post(2, "OTHER_PK", "unrelated member chatter"),
    ]
    with pytest.raises(ValueError, match="phase-owner-unresolved"):
        wc._check_pipeline_close_owner(
            Path("/nonexistent"), _pipeline_wg(), posts, "#done stalled", "HUB",
        )
    wc._check_pipeline_close_owner(
        Path("/nonexistent"), _pipeline_wg(), posts,
        "#done skipped · owner unpinned, waiving phase", "HUB",
    )


def test_cursor_advance_matrix() -> None:
    ok = service._should_advance_cursor
    assert ok(rc=0, posts_added=0, preempted=False, timed_out=False), "silent success advances"
    assert ok(rc=0, posts_added=2, preempted=False, timed_out=False)
    assert ok(rc=1, posts_added=1, preempted=False, timed_out=False), "error after delivery advances"
    assert not ok(rc=1, posts_added=0, preempted=False, timed_out=False), "error without post re-dispatches"
    assert not ok(rc=0, posts_added=0, preempted=False, timed_out=True), "timeout without post re-dispatches even at rc 0"
    assert not ok(rc=-15, posts_added=0, preempted=False, timed_out=True)
    assert ok(rc=-15, posts_added=1, preempted=False, timed_out=True), "timeout after delivery advances"
    assert not ok(rc=0, posts_added=1, preempted=True, timed_out=False), "preempted never advances"


def test_working_heartbeat_does_not_block_the_stalled_retask() -> None:
    posts = [
        _post(1, "HUB", "@scout #task #intake produce work/intake.md"),
        _post(2, "SCOUT_PK", "#working reading the brief"),
    ]
    wc._check_hub_rotation(
        posts, "HUB", "@scout #task #intake retry with the correct path", ["SCOUT_PK"],
        allow_stalled_retask=True,
    )


def test_skip_blocks_the_stalled_retask() -> None:
    posts = [
        _post(1, "HUB", "@scout #task #intake produce work/intake.md"),
        _post(2, "SCOUT_PK", "#skip nothing to add"),
    ]
    with pytest.raises(ValueError, match="task-already-active"):
        wc._check_hub_rotation(
            posts, "HUB", "@scout #task #intake retry", ["SCOUT_PK"],
            allow_stalled_retask=True,
        )


def test_substantive_reply_blocks_the_stalled_retask() -> None:
    posts = [
        _post(1, "HUB", "@scout #task #intake produce work/intake.md"),
        _post(2, "SCOUT_PK", "delivered a first draft of work/intake.md"),
    ]
    with pytest.raises(ValueError, match="task-already-active"):
        wc._check_hub_rotation(
            posts, "HUB", "@scout #task #intake do it again", ["SCOUT_PK"],
            allow_stalled_retask=True,
        )


def test_override_requires_an_active_pipeline_phase(monkeypatch) -> None:
    _patch_peer_ids(monkeypatch)
    closed = [
        _post(1, "HUB", "@scout #task #intake produce work/intake.md"),
        _post(2, "HUB", "#done skipped · owner unreachable"),
    ]
    assert wc._check_pipeline_close_owner(
        Path("/nonexistent"), _pipeline_wg(), closed,
        "#done skipped · again", "HUB",
    ) is False

    adhoc = [_post(1, "HUB", "@scout #task #adhoc one-off question")]
    assert wc._check_pipeline_close_owner(
        Path("/nonexistent"), _pipeline_wg(), adhoc,
        "#done skipped · not a phase", "HUB",
    ) is False

    open_phase = [_post(1, "HUB", "@scout #task #intake produce work/intake.md")]
    assert wc._check_pipeline_close_owner(
        Path("/nonexistent"), _pipeline_wg(), open_phase,
        "#done skipped · owner unreachable", "HUB",
    ) is True


@pytest.mark.asyncio
async def test_override_survives_the_full_hub_post_chain(short_tmp: Path) -> None:
    from alpi.alp import peers as peers_mod
    from alpi.alp import workgroup as wg_mod
    from alpi.alp.keys import load_or_generate
    from alpi.alp.peers import Peer

    hub_home = short_tmp / "mira"; hub_home.mkdir()
    scout_home = short_tmp / "scout"; scout_home.mkdir()
    hub_kp = load_or_generate(hub_home)
    scout_kp = load_or_generate(scout_home)
    peers_mod.add(hub_home, Peer(
        id="scout", pubkey=scout_kp.pubkey_b64(),
        allow=["workgroup.join", "workgroup.post", "workgroup.pull"],
    ))
    wg = wg_mod.create(
        hub_home, name="proj", hub_kp=hub_kp,
        member_pubkeys=[scout_kp.pubkey_b64()],
        pipeline=("intake", "assets"),
    )

    await wc.post(
        hub_home, wg.meta.id, b"@scout #task #intake produce work/intake.md",
    )

    with pytest.raises(ValueError, match="phase-owner-missing"):
        await wc.post(hub_home, wg.meta.id, b"#done stalled")

    retask = await wc.post(
        hub_home, wg.meta.id,
        b"@scout #task #intake retry with the correct path",
    )
    assert retask.get("seq")

    closed = await wc.post(
        hub_home, wg.meta.id,
        b"#done skipped \xc2\xb7 owner never delivered, phase waived",
    )
    assert closed.get("seq")

    with pytest.raises(ValueError, match="no active task"):
        await wc.post(
            hub_home, wg.meta.id,
            b"#done skipped \xc2\xb7 there is nothing left to close",
        )
