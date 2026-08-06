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
        pipelines={"intake": ("intake", "assets")},
        launch_pipeline="intake",
        pipeline_mode=True,
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
        meta=types.SimpleNamespace(
            pipelines={"intake": ("intake", "assets")},
            launch_pipeline="intake",
        ),
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
        pipelines={"intake": ("intake", "assets")},
        launch_pipeline="intake",
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


def _dormant_pipeline_wg() -> types.SimpleNamespace:
    return types.SimpleNamespace(
        meta=types.SimpleNamespace(
            pipelines={
                "intake": ("intake", "assets"),
                "media-update": ("media-update", "media-qa"),
            },
            launch_pipeline="intake",
        ),
        members=[types.SimpleNamespace(pubkey="SCOUT_PK")],
    )


def test_dormant_pipeline_declares_its_own_chain_beside_the_launch_one() -> None:
    from alpi.alp import workgroup as wg_mod

    meta = _dormant_pipeline_wg().meta
    assert wg_mod.dormant_pipelines(meta) == {
        "media-update": ("media-update", "media-qa"),
    }
    assert meta.pipelines[meta.launch_pipeline] == ("intake", "assets")
    assert wg_mod.pipeline_for_phase(meta, "media-qa") == (
        "media-update", ("media-update", "media-qa"),
    )


def test_dormant_phase_close_without_owner_delivery_is_rejected(monkeypatch) -> None:
    _patch_peer_ids(monkeypatch)
    posts = [_post(1, "HUB", "@scout #task #media-update map the client media")]
    with pytest.raises(ValueError, match="phase-owner-missing"):
        wc._check_pipeline_close_owner(
            Path("/nonexistent"), _dormant_pipeline_wg(), posts, "#done media-update", "HUB",
        )


def test_dormant_phase_close_allowed_once_the_owner_delivers(monkeypatch) -> None:
    _patch_peer_ids(monkeypatch)
    posts = [
        _post(1, "HUB", "@scout #task #media-update map the client media"),
        _post(2, "SCOUT_PK", "manifest complete · 20 files mapped"),
    ]
    assert wc._check_pipeline_close_owner(
        Path("/nonexistent"), _dormant_pipeline_wg(), posts,
        "#done media-update verified", "HUB",
    ) is False


def test_dormant_phase_blocked_override_waives_quorum(monkeypatch) -> None:
    _patch_peer_ids(monkeypatch)
    posts = [_post(1, "HUB", "@scout #task #media-update map the client media")]
    assert wc._check_pipeline_close_owner(
        Path("/nonexistent"), _dormant_pipeline_wg(), posts,
        "#done BLOCKED · media-update · template gap", "HUB",
    ) is True


def test_dormant_phase_skipped_override_waives_quorum(monkeypatch) -> None:
    _patch_peer_ids(monkeypatch)
    posts = [_post(1, "HUB", "@scout #task #media-qa audit the rebuild")]
    assert wc._check_pipeline_close_owner(
        Path("/nonexistent"), _dormant_pipeline_wg(), posts,
        "#done skipped · no media changed", "HUB",
    ) is True


def test_dormant_phase_owner_unresolved_is_rejected(monkeypatch) -> None:
    monkeypatch.setattr(wc.peers_mod, "get_by_pubkey", lambda home, pk: None)
    posts = [_post(1, "HUB", "@scout #task #media-update map it")]
    with pytest.raises(ValueError, match="phase-owner-unresolved"):
        wc._check_pipeline_close_owner(
            Path("/nonexistent"), _dormant_pipeline_wg(), posts, "#done media-update", "HUB",
        )


def _gated_wg() -> types.SimpleNamespace:
    return types.SimpleNamespace(
        meta=types.SimpleNamespace(
            id="wg_gated",
            pipelines={"intake": ("intake", "assets")},
            launch_pipeline="intake",
            pipeline_steps={
                "intake": {
                    "owner": "scout",
                    "gate": {"argv": ["npm", "run", "check:config"], "cwd": "p"},
                },
                "assets": {"owner": "scout"},
            },
        ),
        members=[types.SimpleNamespace(pubkey="SCOUT_PK")],
    )


def _write_gate(home: Path, phase: str, seq: int, passed: bool) -> None:
    from alpi.alp import pipeline_gates as gates
    from alpi.alp import workgroup as wg_mod

    step = gates.GateStep(
        phase=phase, owner="scout", next_phase="", next_owner="", next_task="",
        argv=("npm", "run", "check:config"), cwd="p",
    )
    wg_dir = wg_mod._wg_dir(home, "wg_gated")
    wg_dir.mkdir(parents=True, exist_ok=True)
    gates.write_gate_log(wg_dir, step, seq, passed, "output")


def _delivered() -> list[dict]:
    return [
        _post(1, "HUB", "@scout #task #intake produce site.json"),
        _post(2, "SCOUT_PK", "delivered src/config/site.json"),
    ]


def test_gated_phase_cannot_close_without_a_gate_log(short_tmp: Path, monkeypatch) -> None:
    _patch_peer_ids(monkeypatch)
    home = short_tmp / "h"; home.mkdir(parents=True)
    with pytest.raises(ValueError, match="phase-gate-unverified"):
        wc._check_pipeline_close_owner(
            home, _gated_wg(), _delivered(), "#done intake complete", "HUB",
        )


def test_gated_phase_cannot_close_over_a_red_gate(short_tmp: Path, monkeypatch) -> None:
    _patch_peer_ids(monkeypatch)
    home = short_tmp / "h"; home.mkdir(parents=True)
    _write_gate(home, "intake", 2, passed=False)
    with pytest.raises(ValueError, match="phase-gate-failed.*seq #2"):
        wc._check_pipeline_close_owner(
            home, _gated_wg(), _delivered(),
            "#done intake verified — gate failure fixed", "HUB",
        )


def test_gated_phase_closes_on_a_green_gate(short_tmp: Path, monkeypatch) -> None:
    _patch_peer_ids(monkeypatch)
    home = short_tmp / "h"; home.mkdir(parents=True)
    _write_gate(home, "intake", 2, passed=True)
    wc._check_pipeline_close_owner(
        home, _gated_wg(), _delivered(), "#done intake verified · gate:npm", "HUB",
    )


def test_a_green_gate_goes_stale_when_the_owner_posts_again(
    short_tmp: Path, monkeypatch,
) -> None:
    _patch_peer_ids(monkeypatch)
    home = short_tmp / "h"; home.mkdir(parents=True)
    _write_gate(home, "intake", 2, passed=True)
    posts = [*_delivered(), _post(3, "SCOUT_PK", "amended site.json after review")]
    with pytest.raises(ValueError, match="phase-gate-unverified"):
        wc._check_pipeline_close_owner(
            home, _gated_wg(), posts, "#done intake complete", "HUB",
        )


def test_blocked_override_still_closes_a_red_gated_phase(
    short_tmp: Path, monkeypatch,
) -> None:
    _patch_peer_ids(monkeypatch)
    home = short_tmp / "h"; home.mkdir(parents=True)
    _write_gate(home, "intake", 2, passed=False)
    wc._check_pipeline_close_owner(
        home, _gated_wg(), _delivered(),
        "#done BLOCKED · check:config cannot pass without the engine id", "HUB",
    )


def test_working_heartbeat_is_not_the_judged_post(short_tmp: Path, monkeypatch) -> None:
    _patch_peer_ids(monkeypatch)
    home = short_tmp / "h"; home.mkdir(parents=True)
    _write_gate(home, "intake", 2, passed=True)
    posts = [*_delivered(), _post(3, "SCOUT_PK", "#working still tidying up")]
    wc._check_pipeline_close_owner(
        home, _gated_wg(), posts, "#done intake verified", "HUB",
    )


def _gated_hub_wg() -> types.SimpleNamespace:
    wg = _gated_wg()
    wg.meta.hub_pubkey = "HUB"
    return wg


def test_delivery_survives_a_daemon_restart_for_the_gate() -> None:
    from alpi.alp import pipeline_gates as gates

    posts = [
        _post(1, "HUB", "@scout #task #intake produce site.json"),
        _post(2, "SCOUT_PK", "wrote src/config/site.json"),
        _post(3, "HUB", "noted, one clarification on scope follows"),
        _post(4, "SCOUT_PK", "#working re-reading the brief"),
    ]
    service._GATE_ATTEMPTED.clear()
    assert gates.owner_post_under_gate(posts, {"SCOUT_PK"}, "HUB", 1) == 2


async def _drive_hub(home: Path, wg, posts: list[dict], monkeypatch) -> None:
    monkeypatch.setattr(
        "alpi.alp.keys.load_or_generate",
        lambda h: types.SimpleNamespace(pubkey_b64=lambda: "HUB"),
    )
    monkeypatch.setattr(service, "_should_dispatch", lambda *a, **k: (None, 0))

    async def _noop(*a, **k):
        return None

    monkeypatch.setattr(service, "_maybe_watchdog_close", _noop)
    await service._maybe_dispatch_for_hub(home, "mira", wg, posts)


@pytest.mark.asyncio
async def test_gate_overdue_reports_an_unpinned_owner(
    short_tmp: Path, monkeypatch, caplog,
) -> None:
    home = short_tmp / "h"; home.mkdir(parents=True)
    monkeypatch.setattr("alpi.alp.peers.load", lambda h: [])
    service._GATE_OVERDUE_WARNED.clear()
    service._GATE_ATTEMPTED.clear()

    with caplog.at_level("WARNING"):
        await _drive_hub(home, _gated_hub_wg(), _delivered(), monkeypatch)

    said = [r.getMessage() for r in caplog.records if "gate cannot start" in r.getMessage()]
    assert said, "an unpinned owner must be reported as such"
    assert "@scout is not pinned" in said[0]
    assert "seq" not in said[0], (
        "no post may be attributed to an owner that does not resolve"
    )


@pytest.mark.asyncio
async def test_gate_overdue_reports_a_run_that_left_no_log(
    short_tmp: Path, monkeypatch, caplog,
) -> None:
    home = short_tmp / "h"; home.mkdir(parents=True)
    monkeypatch.setattr(
        "alpi.alp.peers.load",
        lambda h: [types.SimpleNamespace(id="scout", pubkey="SCOUT_PK")],
    )
    service._GATE_OVERDUE_WARNED.clear()
    service._GATE_ATTEMPTED.clear()
    service._GATE_ATTEMPTED[(str(home), "wg_gated", 2)] = True

    with caplog.at_level("WARNING"):
        await _drive_hub(home, _gated_hub_wg(), _delivered(), monkeypatch)

    said = [r.getMessage() for r in caplog.records if "gate overdue" in r.getMessage()]
    assert said and "died mid-flight" in said[0]
    service._GATE_ATTEMPTED.clear()


@pytest.mark.asyncio
async def test_gate_overdue_silent_once_the_gate_reported(
    short_tmp: Path, monkeypatch, caplog,
) -> None:
    home = short_tmp / "h"; home.mkdir(parents=True)
    monkeypatch.setattr(
        "alpi.alp.peers.load",
        lambda h: [types.SimpleNamespace(id="scout", pubkey="SCOUT_PK")],
    )
    _write_gate(home, "intake", 2, passed=False)
    service._GATE_OVERDUE_WARNED.clear()
    service._GATE_ATTEMPTED.clear()
    service._GATE_ATTEMPTED[(str(home), "wg_gated", 2)] = True

    with caplog.at_level("WARNING"):
        await _drive_hub(home, _gated_hub_wg(), _delivered(), monkeypatch)

    assert not [r for r in caplog.records if "gate overdue" in r.getMessage()], (
        "a red gate already woke the hub with its error; that is not an overdue gate"
    )
    service._GATE_ATTEMPTED.clear()


def test_gate_overdue_names_which_family_of_cause(
    short_tmp: Path, monkeypatch, caplog,
) -> None:
    home = short_tmp / "h"; home.mkdir(parents=True)
    monkeypatch.setattr(
        "alpi.alp.peers.load",
        lambda h: [types.SimpleNamespace(id="scout", pubkey="SCOUT_PK")],
    )

    service._GATE_OVERDUE_WARNED.clear()
    service._GATE_ATTEMPTED.clear()
    with caplog.at_level("WARNING"):
        service._warn_gate_overdue(home, _gated_hub_wg(), _delivered(), "HUB")
    never = [r.getMessage() for r in caplog.records if "gate overdue" in r.getMessage()]
    assert never and "a precondition declined it" in never[0]

    caplog.clear()
    service._GATE_OVERDUE_WARNED.clear()
    service._GATE_ATTEMPTED[(str(home), "wg_gated", 2)] = True
    with caplog.at_level("WARNING"):
        service._warn_gate_overdue(home, _gated_hub_wg(), _delivered(), "HUB")
    died = [r.getMessage() for r in caplog.records if "gate overdue" in r.getMessage()]
    assert died and "died mid-flight" in died[0]
    service._GATE_ATTEMPTED.clear()


@pytest.mark.asyncio
async def test_a_failure_before_the_run_leaves_the_gate_retryable(
    short_tmp: Path, monkeypatch,
) -> None:
    home = short_tmp / "h"; home.mkdir(parents=True)
    monkeypatch.setattr(
        "alpi.alp.peers.load",
        lambda h: [types.SimpleNamespace(id="scout", pubkey="SCOUT_PK")],
    )

    def unreadable(_home):
        raise OSError("config.yaml unreadable")

    monkeypatch.setattr("alpi.config.load", unreadable)
    service._GATE_ATTEMPTED.clear()

    with pytest.raises(OSError):
        await service._maybe_gate_advance(
            home, _gated_hub_wg(), _delivered(), "HUB",
        )

    assert not service._GATE_ATTEMPTED, (
        "a failure before the run consumed this post's only attempt, so the gate "
        "could never run again and the phase would be stuck for good"
    )


def _gated_open_wg():
    wg = _gated_wg()
    wg.meta.hub_pubkey = "HUB"
    return wg


def test_a_gated_phase_cannot_be_left_behind_by_renaming_it(monkeypatch) -> None:
    posts = [
        _post(1, "HUB", "@scout #task #intake produce site.json"),
        _post(2, "SCOUT_PK", "wrote src/config/site.json"),
    ]
    with pytest.raises(ValueError, match="phase-gate-abandoned"):
        wc._check_gated_phase_not_abandoned(
            _gated_open_wg(), posts, "@muse #task #manifest-fix drop the slots", "HUB",
        )


def test_re_tasking_the_same_gated_phase_stays_allowed(monkeypatch) -> None:
    posts = [
        _post(1, "HUB", "@scout #task #intake produce site.json"),
        _post(2, "SCOUT_PK", "wrote src/config/site.json"),
    ]
    wc._check_gated_phase_not_abandoned(
        _gated_open_wg(), posts, "@scout #task #intake fix the footer shape", "HUB",
    )


def test_neither_another_declared_phase_nor_a_variant_may_preempt_a_gated_phase() -> None:
    posts = [
        _post(1, "HUB", "@scout #task #intake produce site.json"),
        _post(2, "SCOUT_PK", "wrote src/config/site.json"),
    ]
    for slug in ("assets", "intake-fix", "manifest-fix", "rebuild"):
        with pytest.raises(ValueError, match="phase-gate-abandoned"):
            wc._check_gated_phase_not_abandoned(
                _gated_open_wg(), posts, f"@muse #task #{slug} go", "HUB",
            )


def test_a_gateless_phase_may_be_preempted_freely(monkeypatch) -> None:
    wg = _gated_open_wg()
    posts = [
        _post(1, "HUB", "@scout #task #assets map the slots"),
        _post(2, "SCOUT_PK", "manifest written"),
    ]
    wc._check_gated_phase_not_abandoned(wg, posts, "@muse #task #anything go", "HUB")
