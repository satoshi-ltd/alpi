"""The gate is level-triggered where the transcript alone would strand a run."""

from __future__ import annotations

import asyncio
import types
from pathlib import Path

import pytest

from alpi import service
from alpi.alp import peers as peers_mod
from alpi.alp import workgroup as wg_mod
from alpi.alp import workgroup_client as wc
from alpi.alp.keys import load_or_generate
from alpi.alp.peers import Peer

_OLD = "2026-01-01T00:00:00Z"

_STEPS = {
    "content": {
        "owner": "quill", "task": "write it",
        "gate": {"argv": ["true"], "cwd": ""},
    },
    "translation": {"owner": "lingua", "task": "translate it"},
}


def _gated_wg(wg_id: str = "wg_lvl"):
    return types.SimpleNamespace(meta=types.SimpleNamespace(
        id=wg_id, name="site", hub_pubkey="HUB", paused=False,
        pipelines={"content": ("content", "translation")},
        launch_pipeline="content",
        pipeline_steps=_STEPS,
    ))


def _recent():
    return [
        {"seq": 1, "from": "HUB", "ts": _OLD, "text": "@quill #task #content write it"},
        {"seq": 2, "from": "QUILLPK", "ts": _OLD, "text": "content complete · 24 files"},
    ]


def _clear_gate_state():
    service._GATE_ATTEMPTED.clear()
    service._GATE_REPAIRS.clear()


@pytest.fixture(autouse=True)
def _isolate_gate_state():
    _clear_gate_state()
    yield
    _clear_gate_state()


def _mock_owner(monkeypatch):
    monkeypatch.setattr(
        "alpi.alp.peers.load",
        lambda h: [types.SimpleNamespace(id="quill", pubkey="QUILLPK")],
    )


@pytest.mark.asyncio
async def test_forced_rerun_recovers_a_silent_fixer(tmp_path, monkeypatch):
    home = tmp_path / "hub"
    home.mkdir()
    wg = _gated_wg()
    _mock_owner(monkeypatch)
    verdict = {"passed": False}
    monkeypatch.setattr(
        "alpi.alp.pipeline_gates.run_gate",
        lambda step, ws: (verdict["passed"], "9 FAILs" if not verdict["passed"] else "clean"),
    )
    posted: list[str] = []

    async def fake_post(h, wid, text, cost=None):
        posted.append(text.decode())
        return {"seq": 10 + len(posted)}

    monkeypatch.setattr("alpi.alp.workgroup_client.post", fake_post)
    monkeypatch.setattr(service, "_set_hub_responded_seq", lambda *a: None)

    assert await service._maybe_gate_advance(home, wg, _recent(), "HUB") is True
    assert "repair round 1/3" in posted[0]

    verdict["passed"] = True
    assert await service._maybe_gate_advance(home, wg, _recent(), "HUB") is None

    posted.clear()
    out = await service._maybe_gate_advance(home, wg, _recent(), "HUB", force=True)
    assert out is True
    assert posted[0].startswith("#done content verified")
    assert posted[1].startswith("@lingua #task #translation")


@pytest.mark.asyncio
async def test_watchdog_reruns_the_gate_instead_of_waking(tmp_path, monkeypatch):
    home = tmp_path / "hub"
    home.mkdir()
    (home / "config.yaml").write_text("{}\n")
    wg = _gated_wg("wg_wd1")
    _mock_owner(monkeypatch)
    monkeypatch.setattr(
        "alpi.alp.pipeline_gates.run_gate", lambda step, ws: (True, "clean now"),
    )
    posted: list[str] = []

    async def fake_post(h, wid, text, cost=None):
        posted.append(text.decode())
        return {"seq": 10 + len(posted)}

    monkeypatch.setattr("alpi.alp.workgroup_client.post", fake_post)
    monkeypatch.setattr(service, "_set_hub_responded_seq", lambda *a: None)
    spawned: list = []
    monkeypatch.setattr(
        service, "_spawn_dispatch", lambda wid, coro: (coro.close(), spawned.append(wid)),
    )
    service._GATE_ATTEMPTED[(str(home), "wg_wd1", 2)] = True

    await service._maybe_watchdog_close(home, "mira", wg, _recent())
    assert spawned == []
    assert posted and posted[0].startswith("#done content verified")


@pytest.mark.asyncio
async def test_watchdog_wake_carries_the_fresh_red_findings(tmp_path, monkeypatch):
    home = tmp_path / "hub"
    home.mkdir()
    (home / "config.yaml").write_text("{}\n")
    wg = _gated_wg("wg_wd2")
    _mock_owner(monkeypatch)
    monkeypatch.setattr(
        "alpi.alp.pipeline_gates.run_gate",
        lambda step, ws: (False, "still red: deluxe summary missing"),
    )
    monkeypatch.setattr(service, "_set_hub_responded_seq", lambda *a: None)
    service._GATE_ATTEMPTED[(str(home), "wg_wd2", 2)] = True
    service._GATE_REPAIRS[(str(home), "wg_wd2", "content", 1)] = 3

    captured: list[str] = []

    def fake_dispatch(h, profile, wg_id, wg_name, reason, **kwargs):
        captured.append(reason)

        async def _noop():
            return None
        return _noop()

    monkeypatch.setattr(service, "_dispatch_workgroup_turn", fake_dispatch)
    monkeypatch.setattr(service, "_spawn_dispatch", lambda wid, coro: coro.close())
    monkeypatch.setattr(service, "_emit_wg_blocked", lambda *a, **k: None)

    await service._maybe_watchdog_close(home, "mira", wg, _recent())
    assert captured, "the wake must still fire when the forced re-run stays red"
    assert "GATE content FAILED" in captured[0]
    assert "deluxe summary missing" in captured[0]


def test_resume_level_triggers_the_gate(tmp_path):
    home = tmp_path / "hub"
    home.mkdir()
    service._GATE_ATTEMPTED[(str(home), "wg_a", 7)] = True
    service._GATE_ATTEMPTED[(str(home), "wg_b", 7)] = True
    service._GATE_REPAIRS[(str(home), "wg_a", "content", 1)] = 2
    service._GATE_REPAIRS[(str(home), "wg_b", "content", 1)] = 2

    service.reset_workgroup_poller_state(home, "wg_a")

    assert (str(home), "wg_a", 7) not in service._GATE_ATTEMPTED
    assert (str(home), "wg_a", "content", 1) not in service._GATE_REPAIRS
    assert (str(home), "wg_b", 7) in service._GATE_ATTEMPTED
    assert (str(home), "wg_b", "content", 1) in service._GATE_REPAIRS


@pytest.mark.parametrize("result, needs", [
    ("QA FAIL · 8 content entries missing from the intake table", True),
    ("FAIL: three placeholder alts on /en/", True),
    ("qa verified · gate:npm · 2 errors in the locale table", True),
    ("build did not pass on /es/", True),
    ("QA PASS · all checks green", False),
    ("QA PASS · 0 errors", False),
    ("PASS · error-free build across locales", False),
    ("verified · no failures in the audit", False),
    ("qa verified · gate:npm · clean", False),
    ("BLOCKED · template cannot build", False),
    ("skipped · nothing to audit", False),
    ("preempted by #media-update", False),
    ("", False),
])
def test_terminal_close_needs_routing(result, needs):
    assert service._terminal_close_needs_routing(result) is needs


@pytest.mark.asyncio
async def test_failing_terminal_close_gets_one_routing_wake(tmp_path, monkeypatch):
    home = tmp_path / "hub"
    home.mkdir()
    (home / "config.yaml").write_text("{}\n")
    wg = _gated_wg("wg_route")
    recent = [
        {"seq": 1, "from": "HUB", "ts": _OLD, "text": "@lingua #task #translation go"},
        {"seq": 2, "from": "LINGUAPK", "ts": _OLD, "text": "locales delivered"},
        {"seq": 3, "from": "HUB", "ts": _OLD,
         "text": "#done QA FAIL · 8 entries missing from the intake table"},
    ]
    captured: list[dict] = []

    def fake_dispatch(h, profile, wg_id, wg_name, reason, **kwargs):
        captured.append({"reason": reason, **kwargs})

        async def _noop():
            return None
        return _noop()

    monkeypatch.setattr(service, "_dispatch_workgroup_turn", fake_dispatch)
    monkeypatch.setattr(service, "_spawn_dispatch", lambda wid, coro: coro.close())
    blocked: list = []
    monkeypatch.setattr(
        service, "_emit_wg_blocked_once", lambda *a, **k: blocked.append(a),
    )

    await service._maybe_watchdog_close(home, "mira", wg, recent)
    assert len(captured) == 1
    assert "terminal phase closed FAILING" in captured[0]["reason"]
    assert captured[0]["continuation"] is True
    assert captured[0]["next_phase"] == ""

    await service._maybe_watchdog_close(home, "mira", wg, recent)
    assert len(captured) == 1, "no re-fire inside the refire window"

    monkeypatch.setattr(service, "_HUB_WATCHDOG_REFIRE_SECONDS", 0)
    monkeypatch.setattr(service, "_in_cooldown_str", lambda *a, **k: False)
    await service._maybe_watchdog_close(home, "mira", wg, recent)
    assert len(captured) == 1, "the routing wake is bounded to one"
    assert blocked, "past the single wake the stall surfaces as wg.blocked"


@pytest.mark.asyncio
async def test_successful_terminal_close_stays_silent(tmp_path, monkeypatch):
    home = tmp_path / "hub"
    home.mkdir()
    (home / "config.yaml").write_text("{}\n")
    wg = _gated_wg("wg_done")
    recent = [
        {"seq": 1, "from": "HUB", "ts": _OLD, "text": "@lingua #task #translation go"},
        {"seq": 2, "from": "LINGUAPK", "ts": _OLD, "text": "locales delivered"},
        {"seq": 3, "from": "HUB", "ts": _OLD, "text": "#done translation verified · green"},
    ]
    spawned: list = []
    monkeypatch.setattr(
        service, "_spawn_dispatch", lambda wid, coro: (coro.close(), spawned.append(wid)),
    )
    await service._maybe_watchdog_close(home, "mira", wg, recent)
    assert spawned == []


def test_phase_owner_may_deliver_in_pieces():
    posts = [
        {"seq": 5, "from": "HUB", "text": "@lingua gate red on #translation (repair round 1/3)"},
        {"seq": 6, "from": "ME", "text": "fixed the drip findings, re-checking"},
    ]
    with pytest.raises(ValueError, match="turn-rotation"):
        wc._check_member_rotation(posts, "ME", "HUB", "re-delivery: locales at parity")
    wc._check_member_rotation(
        posts, "ME", "HUB", "re-delivery: locales at parity", phase_owner=True,
    )
    posts.append({"seq": 7, "from": "ME", "text": "#working re-running the check"})
    with pytest.raises(ValueError, match="already posted `#working`"):
        wc._check_member_rotation(posts, "ME", "HUB", "#working again", phase_owner=True)


def _member_sub(tmp_path: Path, profile: str, monkeypatch):
    from alpi import home as home_mod
    from alpi.alp import subscription as sub_mod

    root = tmp_path / "root"
    monkeypatch.setattr(home_mod, "_ROOT", root)
    hub_home = root / "profiles" / "mira"
    hub_home.mkdir(parents=True)
    hub_kp = load_or_generate(hub_home)
    member_home = root / "profiles" / profile
    member_home.mkdir(parents=True)
    member_kp = load_or_generate(member_home)

    wg = wg_mod.create(
        hub_home, name="site", hub_kp=hub_kp,
        member_pubkeys=[member_kp.pubkey_b64()],
    )
    sealed = wg.member(member_kp.pubkey_b64()).sealed_key
    hub_pk = hub_kp.pubkey_b64()
    sub = sub_mod.Subscription(
        wg_id=wg.meta.id, name="site", hub_id="mira", hub_pubkey=hub_pk,
        sealed_keys=[sub_mod.SealedKey(version=1, sealed=sealed)],
        pipeline_mode=True,
        pipelines={"translation": ("translation", "qa")},
        phase_map={"translation": {"owner": "lingua"}, "qa": {"owner": "muse"}},
        recent_posts=[
            {"seq": 5, "from": hub_pk,
             "text": "@lingua @muse #task #translation locales for the fleet"},
            {"seq": 6, "from": member_kp.pubkey_b64(), "text": "first delivery"},
        ],
    )
    sub_mod.save(member_home, [sub])

    async def _no_pull(home, wg_id, **kw):
        return [], 0

    calls: list[dict] = []

    async def _fake_call(home, kp, hub_id, method, params, **kw):
        calls.append({"method": method, **params})
        return {"seq": 7}

    monkeypatch.setattr(wc, "pull", _no_pull)
    monkeypatch.setattr(wc, "_call", _fake_call)
    return member_home, wg.meta.id, calls


@pytest.mark.asyncio
async def test_declared_owner_iterates_freely_through_post(tmp_path, monkeypatch):
    member_home, wg_id, calls = _member_sub(tmp_path, "lingua", monkeypatch)
    out = await wc.post(member_home, wg_id, b"re-delivery: locales at parity")
    assert out == {"seq": 7}
    assert calls and calls[0]["method"] == "workgroup.post"


@pytest.mark.asyncio
async def test_mentioned_participant_still_rotates_through_post(tmp_path, monkeypatch):
    member_home, wg_id, calls = _member_sub(tmp_path, "muse", monkeypatch)
    with pytest.raises(ValueError, match="turn-rotation"):
        await wc.post(member_home, wg_id, b"one more thought on the locales")
    assert calls == []


@pytest.mark.asyncio
async def test_rewind_past_a_blocked_phase_is_allowed(tmp_path):
    home = tmp_path / "hub"
    home.mkdir()
    muse_home = tmp_path / "muse"
    muse_home.mkdir()
    muse_pk = load_or_generate(muse_home).pubkey_b64()
    peers_mod.add(home, Peer(id="muse", pubkey=muse_pk, allow=["workgroup.post"]))
    wg = wg_mod.create(
        home, name="site", hub_kp=load_or_generate(home),
        member_pubkeys=[muse_pk],
        pipelines={"intake": ["intake", "assets", "qa"]},
        launch_pipeline="intake",
        pipeline_steps={
            "intake": {"owner": "muse", "task": "gather"},
            "assets": {"owner": "muse", "task": "map media"},
            "qa": {"owner": "muse", "task": "audit"},
        },
    )
    await wc.post(home, wg.meta.id, "@muse #task #assets · map".encode())
    await wc.post(home, wg.meta.id, "#done BLOCKED · intake shipped the untouched scaffold".encode())

    with pytest.raises(ValueError, match="blocked-phase-not-cleared"):
        await wc.post(home, wg.meta.id, "@muse #task #qa · audit anyway".encode())

    result = await wc.post(home, wg.meta.id, "@muse #task #intake · redo the intake".encode())
    assert result.get("seq")


def test_phase_owner_exemption_survives_the_post_window():
    import types
    sub = types.SimpleNamespace(
        pipeline_mode=True,
        hub_pubkey="HUB",
        pipelines={"media-update": ("media-update", "media-config")},
        phase_map={
            "media-update": {"owner": "muse"},
            "media-config": {"owner": "scout"},
        },
        recent_posts=[
            {"seq": 61, "from": "SCOUTPK", "text": "manifest slots pointed"},
            {"seq": 62, "from": "HUB", "text": "@scout gate red on #media-config (repair round 3/3)"},
            {"seq": 63, "from": "SCOUTPK", "text": "restored the file"},
        ],
    )
    assert wc._member_owns_active_phase(sub, None, "scout") is True
    assert wc._member_owns_active_phase(sub, None, "muse") is False
    sub.recent_posts = [{"seq": 70, "from": "HUB", "text": "@scout no phase named here"}]
    assert wc._member_owns_active_phase(sub, None, "scout") is False


def test_unroutable_task_slug_is_refused_at_post_time():
    import types
    wg = types.SimpleNamespace(meta=types.SimpleNamespace(
        pipelines={"setup": ("intake", "content"), "media-update": ("media-update",)},
        launch_pipeline="setup",
    ))
    wc._check_task_slug_is_routable(wg, "@scout #task #intake-fix go")
    wc._check_task_slug_is_routable(wg, "@scout #task #intake do it")
    with pytest.raises(ValueError, match="task-slug-unroutable"):
        wc._check_task_slug_is_routable(wg, "@scout #task #table-fix rename rows")
    try:
        wc._check_task_slug_is_routable(wg, "@scout #task #nope go")
    except ValueError as e:
        assert "intake" in str(e) and "content" in str(e)
    else:
        raise AssertionError("an unroutable slug must be refused")


def test_blocked_close_naming_another_owner_draws_a_routing_wake():
    owners = {"quill", "lingua", "muse", "pixel"}
    assert service._terminal_close_needs_routing(
        "BLOCKED · #build halted — schema mismatch in @quill/@lingua's domain", owners,
    ) is True
    assert service._terminal_close_needs_routing(
        "BLOCKED · template gap in document-head generation, nobody can act", owners,
    ) is False
    assert service._terminal_close_needs_routing(
        "BLOCKED · waiting on @client media", owners,
    ) is False
    assert service._terminal_close_needs_routing("qa verified · gate:npm · clean", owners) is False


def test_blocked_naming_its_own_owner_is_just_a_halt():
    owners = {"lens", "quill", "muse"}
    assert service._terminal_close_needs_routing(
        "BLOCKED · @lens cannot complete the audit", owners, "lens",
    ) is False
    assert service._terminal_close_needs_routing(
        "BLOCKED · @lens cannot audit — schema is @quill's", owners, "lens",
    ) is True
