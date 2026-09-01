"""The gate is level-triggered where the transcript alone would strand a run."""

from __future__ import annotations

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
    service._GATE_RECHECK_AT.clear()
    service._GATE_RED_SIGNATURE.clear()
    service._GATE_RED_RETRY.clear()


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


def _mock_workspace(monkeypatch, tmp_path):
    project = tmp_path / "ws"
    project.mkdir(exist_ok=True)
    (project / "a.txt").write_text("one")
    monkeypatch.setattr(
        "alpi.config.load",
        lambda h: types.SimpleNamespace(workspace_path=project),
    )
    counter = {"n": 0}

    def touch():
        counter["n"] += 1
        (project / "a.txt").write_text(f"edit-{counter['n']}")

    return project, touch


def _real_recent(home: Path, wg) -> list[dict]:
    keys = wg_mod.hub_group_keys(home, wg, load_or_generate(home))
    recent: list[dict] = []
    for entry in wg_mod._read_transcript(wg_mod._wg_dir(home, wg.meta.id)):
        text = wg_mod.decrypt_post(
            keys[int(entry.get("key_version", 1))],
            entry["nonce"],
            entry["ciphertext"],
        ).decode()
        recent.append({**entry, "text": text})
    return recent


def _append_member_post(home: Path, wg, pubkey: str, text: str) -> None:
    keys = wg_mod.hub_group_keys(home, wg, load_or_generate(home))
    version = max(keys)
    nonce, ciphertext = wg_mod.encrypt_post(keys[version], text.encode())
    wg_mod.append_with_seq(wg_mod._wg_dir(home, wg.meta.id), {
        "ts": "2026-08-13T00:00:00Z",
        "from": pubkey,
        "key_version": version,
        "nonce": nonce,
        "ciphertext": ciphertext,
    })


@pytest.mark.asyncio
async def test_a_silent_fixer_is_recovered_without_a_wake(tmp_path, monkeypatch):
    home = tmp_path / "hub"
    home.mkdir()
    wg = _gated_wg()
    _mock_owner(monkeypatch)
    _, touch = _mock_workspace(monkeypatch, tmp_path)
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

    posted.clear()
    verdict["passed"] = True
    touch()
    monkeypatch.setattr(service, "_GATE_RECHECK_SECONDS", 0)
    out = await service._maybe_gate_advance(home, wg, _recent(), "HUB")
    assert out is True
    assert posted[0].startswith("#done content verified")
    assert posted[1].startswith("@lingua #task #translation")


@pytest.mark.asyncio
async def test_green_gate_advances_through_the_real_workgroup_sdk(tmp_path, monkeypatch):
    from alpi import home as home_mod

    root = tmp_path / "root"
    monkeypatch.setattr(home_mod, "_ROOT", root)
    home = root / "profiles" / "mira"
    home.mkdir(parents=True)
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    quill_home = root / "profiles" / "quill"
    lingua_home = root / "profiles" / "lingua"
    quill_home.mkdir(parents=True)
    lingua_home.mkdir(parents=True)
    quill_pk = load_or_generate(quill_home).pubkey_b64()
    lingua_pk = load_or_generate(lingua_home).pubkey_b64()
    peers_mod.add(home, Peer(id="quill", pubkey=quill_pk, allow=["workgroup.post"]))
    peers_mod.add(home, Peer(id="lingua", pubkey=lingua_pk, allow=["workgroup.post"]))
    wg = wg_mod.create(
        home,
        name="site",
        hub_kp=load_or_generate(home),
        member_pubkeys=[quill_pk, lingua_pk],
        pipelines={"content": ["content", "translation"]},
        launch_pipeline="content",
        pipeline_steps=_STEPS,
    )
    monkeypatch.setattr(
        "alpi.config.load",
        lambda h: types.SimpleNamespace(workspace_path=workspace),
    )
    monkeypatch.setattr(
        "alpi.alp.pipeline_gates.run_gate",
        lambda step, ws: (True, "clean"),
    )

    await wc.post(home, wg.meta.id, b"@quill #task #content write it")
    _append_member_post(home, wg, quill_pk, "content complete")

    assert await service._maybe_gate_advance(
        home, wg, _real_recent(home, wg), wg.meta.hub_pubkey,
    ) is True
    texts = [post["text"] for post in _real_recent(home, wg)]
    assert texts[-2].startswith("#done content verified")
    assert texts[-1].startswith("@lingua #task #translation")


@pytest.mark.asyncio
async def test_a_still_red_recheck_stays_silent(tmp_path, monkeypatch):
    home = tmp_path / "hub"
    home.mkdir()
    wg = _gated_wg()
    _mock_owner(monkeypatch)
    monkeypatch.setattr(
        "alpi.alp.pipeline_gates.run_gate", lambda step, ws: (False, "9 FAILs"),
    )
    posted: list[str] = []

    async def fake_post(h, wid, text, cost=None):
        posted.append(text.decode())
        return {"seq": 10 + len(posted)}

    monkeypatch.setattr("alpi.alp.workgroup_client.post", fake_post)
    monkeypatch.setattr(service, "_set_hub_responded_seq", lambda *a: None)

    assert await service._maybe_gate_advance(home, wg, _recent(), "HUB") is True
    assert len(posted) == 1

    monkeypatch.setattr(service, "_GATE_RECHECK_SECONDS", 0)
    for _ in range(3):
        assert await service._maybe_gate_advance(home, wg, _recent(), "HUB") is None
    assert len(posted) == 1
    assert max(service._GATE_REPAIRS.values()) == 1


@pytest.mark.asyncio
async def test_an_unchanged_workspace_is_never_re_gated(tmp_path, monkeypatch):
    home = tmp_path / "hub"
    home.mkdir()
    project = tmp_path / "ws"
    project.mkdir()
    (project / "a.txt").write_text("one")
    wg = _gated_wg()
    _mock_owner(monkeypatch)
    monkeypatch.setattr(
        "alpi.config.load",
        lambda h: types.SimpleNamespace(workspace_path=project),
    )
    runs = {"n": 0}

    def _run(step, ws):
        runs["n"] += 1
        return False, "still thin"

    monkeypatch.setattr("alpi.alp.pipeline_gates.run_gate", _run)

    async def fake_post(h, wid, text, cost=None):
        return {"seq": 11}

    monkeypatch.setattr("alpi.alp.workgroup_client.post", fake_post)
    monkeypatch.setattr(service, "_set_hub_responded_seq", lambda *a: None)
    monkeypatch.setattr(service, "_GATE_RECHECK_SECONDS", 0)

    await service._maybe_gate_advance(home, wg, _recent(), "HUB")
    assert runs["n"] == 1

    for _ in range(4):
        assert await service._maybe_gate_advance(home, wg, _recent(), "HUB") is None
    assert runs["n"] == 1, "an unchanged workspace must not respawn the gate"

    (project / "a.txt").write_text("two")
    assert await service._maybe_gate_advance(home, wg, _recent(), "HUB") is None
    assert runs["n"] == 2, "a changed workspace earns exactly one new attempt"
    for _ in range(3):
        await service._maybe_gate_advance(home, wg, _recent(), "HUB")
    assert runs["n"] == 2


@pytest.mark.parametrize("tree", ["dist", "public", ".astro"])
def test_the_signature_sees_the_outputs_a_gate_reads(tmp_path, tree):
    from alpi.alp import pipeline_gates as gates

    project = tmp_path / "ws"
    (project / "src").mkdir(parents=True)
    (project / "src" / "a.json").write_text("x")
    (project / tree).mkdir()
    (project / tree / "index.html").write_text("v1")
    step = gates.GateStep(
        phase="build", owner="pixel", next_phase="", next_owner="", next_task="",
        argv=("true",), cwd="", paths=("src/**",),
    )
    before = gates.workspace_signature(step, project)
    (project / tree / "index.html").write_text("v2-fixed")
    assert gates.workspace_signature(step, project) != before, (
        f"a build gate reads {tree}/, so a fix there must move the signature"
    )


def test_the_signature_sees_a_mode_change(tmp_path):
    import os
    from alpi.alp import pipeline_gates as gates

    project = tmp_path / "ws"
    project.mkdir()
    script = project / "check.sh"
    script.write_text("#!/bin/sh\n")
    os.chmod(script, 0o644)
    step = gates.GateStep(
        phase="build", owner="pixel", next_phase="", next_owner="", next_task="",
        argv=("true",), cwd="", paths=("src/**",),
    )
    before = gates.workspace_signature(step, project)
    os.chmod(script, 0o755)
    assert gates.workspace_signature(step, project) != before, (
        "a gate that failed on a non-executable script must see the chmod"
    )


def test_the_signature_sees_an_empty_directory(tmp_path):
    from alpi.alp import pipeline_gates as gates

    project = tmp_path / "ws"
    project.mkdir()
    (project / "a.txt").write_text("x")
    step = gates.GateStep(
        phase="build", owner="pixel", next_phase="", next_owner="", next_task="",
        argv=("true",), cwd="", paths=("src/**",),
    )
    before = gates.workspace_signature(step, project)
    (project / "expected-dir").mkdir()
    assert gates.workspace_signature(step, project) != before


def test_the_signature_ignores_dependencies(tmp_path):
    from alpi.alp import pipeline_gates as gates

    project = tmp_path / "ws"
    (project / "src").mkdir(parents=True)
    (project / "src" / "a.json").write_text("x")
    (project / "node_modules" / "pkg").mkdir(parents=True)
    (project / "node_modules" / "pkg" / "i.js").write_text("v1")
    step = gates.GateStep(
        phase="build", owner="pixel", next_phase="", next_owner="", next_task="",
        argv=("true",), cwd="", paths=("src/**",),
    )
    before = gates.workspace_signature(step, project)
    (project / "node_modules" / "pkg" / "i.js").write_text("v2")
    assert gates.workspace_signature(step, project) == before


@pytest.mark.asyncio
async def test_a_fix_landing_mid_run_is_retried(tmp_path, monkeypatch):
    home = tmp_path / "hub"
    home.mkdir()
    wg = _gated_wg()
    _mock_owner(monkeypatch)
    project, touch = _mock_workspace(monkeypatch, tmp_path)
    runs = {"n": 0}

    def _run(step, ws):
        runs["n"] += 1
        touch()
        return False, "9 FAILs"

    monkeypatch.setattr("alpi.alp.pipeline_gates.run_gate", _run)

    async def fake_post(h, wid, text, cost=None):
        return {"seq": 11}

    monkeypatch.setattr("alpi.alp.workgroup_client.post", fake_post)
    monkeypatch.setattr(service, "_set_hub_responded_seq", lambda *a: None)
    monkeypatch.setattr(service, "_GATE_RECHECK_SECONDS", 0)

    await service._maybe_gate_advance(home, wg, _recent(), "HUB")
    assert runs["n"] == 1
    await service._maybe_gate_advance(home, wg, _recent(), "HUB")
    assert runs["n"] == 2, "the file changed during the failing run; the next poll must retry"

    for _ in range(4):
        await service._maybe_gate_advance(home, wg, _recent(), "HUB")
    assert runs["n"] == 2, "a gate that rewrites its own output must not re-arm itself"


@pytest.mark.asyncio
async def test_a_fix_landing_during_a_later_recheck_is_retried(tmp_path, monkeypatch):
    home = tmp_path / "hub"
    home.mkdir()
    wg = _gated_wg()
    _mock_owner(monkeypatch)
    project, touch = _mock_workspace(monkeypatch, tmp_path)
    runs = {"n": 0}

    def _run(step, ws):
        runs["n"] += 1
        if runs["n"] == 2:
            touch()
        return False, "9 FAILs"

    monkeypatch.setattr("alpi.alp.pipeline_gates.run_gate", _run)

    async def fake_post(h, wid, text, cost=None):
        return {"seq": 11}

    monkeypatch.setattr("alpi.alp.workgroup_client.post", fake_post)
    monkeypatch.setattr(service, "_set_hub_responded_seq", lambda *a: None)
    monkeypatch.setattr(service, "_GATE_RECHECK_SECONDS", 0)

    await service._maybe_gate_advance(home, wg, _recent(), "HUB")
    assert runs["n"] == 1

    touch()
    await service._maybe_gate_advance(home, wg, _recent(), "HUB")
    assert runs["n"] == 2, "an external change must earn a run"

    await service._maybe_gate_advance(home, wg, _recent(), "HUB")
    assert runs["n"] == 3, "the fix that landed during run 2 must still earn a retry"

    for _ in range(3):
        await service._maybe_gate_advance(home, wg, _recent(), "HUB")
    assert runs["n"] == 3, "and that retry is not re-armed by itself"


@pytest.mark.asyncio
async def test_an_unknowable_workspace_is_still_only_spawned_once(tmp_path, monkeypatch):
    home = tmp_path / "hub"
    home.mkdir()
    wg = _gated_wg()
    _mock_owner(monkeypatch)
    _mock_workspace(monkeypatch, tmp_path)
    monkeypatch.setattr(
        "alpi.alp.pipeline_gates.workspace_signature", lambda step, ws: "",
    )
    runs = {"n": 0}

    def _run(step, ws):
        runs["n"] += 1
        return False, "9 FAILs"

    monkeypatch.setattr("alpi.alp.pipeline_gates.run_gate", _run)

    async def fake_post(h, wid, text, cost=None):
        return {"seq": 11}

    monkeypatch.setattr("alpi.alp.workgroup_client.post", fake_post)
    monkeypatch.setattr(service, "_set_hub_responded_seq", lambda *a: None)
    monkeypatch.setattr(service, "_GATE_RECHECK_SECONDS", 0)

    await service._maybe_gate_advance(home, wg, _recent(), "HUB")
    for _ in range(4):
        await service._maybe_gate_advance(home, wg, _recent(), "HUB")
    assert runs["n"] == 1, "an unknown signature must not loop the subprocess forever"


@pytest.mark.asyncio
async def test_an_abandoned_stall_stops_bumping_and_logging(tmp_path, monkeypatch, caplog):
    home = tmp_path / "hub"
    home.mkdir()
    (home / "config.yaml").write_text("{}\n")
    wg = _gated_wg("wg_stall")
    _mock_owner(monkeypatch)
    monkeypatch.setattr(
        "alpi.alp.pipeline_gates.run_gate", lambda step, ws: (False, "9 FAILs"),
    )
    monkeypatch.setattr(service, "_set_hub_responded_seq", lambda *a: None)
    monkeypatch.setattr(service, "_emit_wg_blocked", lambda *a, **k: None)

    async def fake_post(h, wid, text, cost=None):
        return {"seq": 11}

    monkeypatch.setattr("alpi.alp.workgroup_client.post", fake_post)

    def fake_dispatch(h, profile, wg_id, wg_name, reason, **kwargs):
        async def _noop():
            return None
        return _noop()

    monkeypatch.setattr(service, "_dispatch_workgroup_turn", fake_dispatch)
    monkeypatch.setattr(service, "_spawn_dispatch", lambda wid, coro: coro.close())
    monkeypatch.setattr(service, "_in_cooldown_str", lambda *a, **k: False)
    monkeypatch.setattr(service, "_HUB_WATCHDOG_REFIRE_SECONDS", 0)

    bumps = {"n": 0}
    real_bump = service._bump_hub_watchdog_count

    def counting_bump(h, wid, seq):
        bumps["n"] += 1
        return real_bump(h, wid, seq)

    monkeypatch.setattr(service, "_bump_hub_watchdog_count", counting_bump)

    for _ in range(5):
        await service._maybe_watchdog_close(home, "mira", wg, _recent())
    assert bumps["n"] == 4, "the recovery evaluations each earn a bump (call 1 goes to the gate's repair note)"

    import logging
    caplog.clear()
    with caplog.at_level(logging.WARNING):
        for _ in range(6):
            await service._maybe_watchdog_close(home, "mira", wg, _recent())
    assert bumps["n"] == 4, "an abandoned stall must never bump again"
    assert "task stalled" not in caplog.text


@pytest.mark.asyncio
async def test_a_recheck_waits_out_its_interval(tmp_path, monkeypatch):
    home = tmp_path / "hub"
    home.mkdir()
    wg = _gated_wg()
    _mock_owner(monkeypatch)
    _, touch = _mock_workspace(monkeypatch, tmp_path)
    runs = {"n": 0}

    def _run(step, ws):
        runs["n"] += 1
        return False, "9 FAILs"

    monkeypatch.setattr("alpi.alp.pipeline_gates.run_gate", _run)

    async def fake_post(h, wid, text, cost=None):
        return {"seq": 11}

    monkeypatch.setattr("alpi.alp.workgroup_client.post", fake_post)
    monkeypatch.setattr(service, "_set_hub_responded_seq", lambda *a: None)

    await service._maybe_gate_advance(home, wg, _recent(), "HUB")
    assert runs["n"] == 1
    for _ in range(5):
        touch()
        assert await service._maybe_gate_advance(home, wg, _recent(), "HUB") is None
    assert runs["n"] == 1, "the interval must hold the subprocess off even when files move"

    monkeypatch.setattr(service, "_GATE_RECHECK_SECONDS", 0)
    touch()
    assert await service._maybe_gate_advance(home, wg, _recent(), "HUB") is None
    assert runs["n"] == 2


@pytest.mark.asyncio
async def test_a_live_owner_turn_defers_the_recheck(tmp_path, monkeypatch):
    home = tmp_path / "hub"
    home.mkdir()
    wg = _gated_wg()
    _mock_owner(monkeypatch)
    _, touch = _mock_workspace(monkeypatch, tmp_path)
    verdict = {"passed": False}
    monkeypatch.setattr(
        "alpi.alp.pipeline_gates.run_gate",
        lambda step, ws: (verdict["passed"], "clean" if verdict["passed"] else "9 FAILs"),
    )

    async def fake_post(h, wid, text, cost=None):
        return {"seq": 11}

    monkeypatch.setattr("alpi.alp.workgroup_client.post", fake_post)
    monkeypatch.setattr(service, "_set_hub_responded_seq", lambda *a: None)

    await service._maybe_gate_advance(home, wg, _recent(), "HUB")
    verdict["passed"] = True
    touch()
    monkeypatch.setattr(service, "_GATE_RECHECK_SECONDS", 0)
    service._INFLIGHT[(wg.meta.id, "lingua")] = {}
    try:
        assert await service._maybe_gate_advance(home, wg, _recent(), "HUB") is None
    finally:
        service._INFLIGHT.pop((wg.meta.id, "lingua"), None)
    assert await service._maybe_gate_advance(home, wg, _recent(), "HUB") is True


@pytest.mark.asyncio
async def test_new_owner_delivery_gets_a_fresh_gate_verdict(tmp_path, monkeypatch):
    home = tmp_path / "hub"
    home.mkdir()
    wg = _gated_wg("wg_fresh_delivery")
    _mock_owner(monkeypatch)
    verdicts = iter([(False, "first delivery is red"), (True, "second delivery is green")])
    runs: list[int] = []

    def fake_gate(step, workspace):
        runs.append(1)
        return next(verdicts)

    monkeypatch.setattr("alpi.alp.pipeline_gates.run_gate", fake_gate)
    posted: list[str] = []

    async def fake_post(home_arg, wg_id, text, cost=None):
        posted.append(text.decode())
        return {"seq": 10 + len(posted)}

    monkeypatch.setattr("alpi.alp.workgroup_client.post", fake_post)
    monkeypatch.setattr(service, "_set_hub_responded_seq", lambda *args: None)

    first = _recent()
    assert await service._maybe_gate_advance(home, wg, first, "HUB") is True
    assert posted == [
        "@quill gate red on #content (repair round 1/3) — fix these and "
        "re-deliver on this same task:\nfirst delivery is red",
    ]

    second = [
        *first,
        {"seq": 3, "from": "HUB", "ts": _OLD, "text": posted[0]},
        {"seq": 4, "from": "QUILLPK", "ts": _OLD, "text": "content repaired"},
    ]
    assert await service._maybe_gate_advance(home, wg, second, "HUB") is True

    assert len(runs) == 2
    assert posted[1].startswith("#done content verified")
    assert posted[2].startswith("@lingua #task #translation")
    gate_dir = home / "alp" / "workgroups" / "wg_fresh_delivery" / "gates"
    assert '"passed": false' in (gate_dir / "content-2.log").read_text()
    assert '"passed": true' in (gate_dir / "content-4.log").read_text()


@pytest.mark.asyncio
async def test_hub_routed_gate_failure_does_not_retask_read_only_owner(
    tmp_path, monkeypatch,
):
    home = tmp_path / "hub-routed"
    home.mkdir()
    steps = {
        "qa": {
            "owner": "lens", "task": "audit it",
            "gate": {"argv": ["false"], "cwd": "", "repair": "hub"},
        },
    }
    wg = types.SimpleNamespace(meta=types.SimpleNamespace(
        id="wg_hub_repair", name="site", hub_pubkey="HUB", paused=False,
        pipelines={"setup": ("qa",)}, launch_pipeline="setup",
        pipeline_steps=steps,
    ))
    monkeypatch.setattr(
        "alpi.alp.peers.load",
        lambda h: [types.SimpleNamespace(id="lens", pubkey="LENSPK")],
    )
    monkeypatch.setattr(
        "alpi.config.load",
        lambda h: types.SimpleNamespace(workspace_path=tmp_path),
    )
    recent = [
        {"seq": 1, "from": "HUB", "ts": _OLD, "text": "@lens #task #qa audit it"},
        {"seq": 2, "from": "LENSPK", "ts": _OLD, "text": "QA FAIL · content is invalid"},
    ]
    posted = []

    async def fake_post(*args, **kwargs):
        posted.append(args)

    monkeypatch.setattr("alpi.alp.workgroup_client.post", fake_post)

    result = await service._maybe_gate_advance(home, wg, recent, "HUB")

    assert isinstance(result, str)
    assert "declares hub-routed repair" in result
    assert "Do not re-task @lens" in result
    assert posted == []
    assert service._GATE_REPAIRS == {}


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
    from alpi.alp import pipeline_gates as gates_mod
    step = gates_mod.step_for(wg.meta, "content")
    gates_mod.write_gate_log(
        home / "alp" / "workgroups" / "wg_wd1", step, 2, False, "9 FAILs",
    )
    service._GATE_ATTEMPTED[(str(home), "wg_wd1", 2)] = True
    monkeypatch.setattr(service, "_GATE_RECHECK_SECONDS", 0)

    await service._maybe_watchdog_close(home, "mira", wg, _recent())
    assert spawned == []
    assert posted and posted[0].startswith("#done content verified")


@pytest.mark.asyncio
async def test_a_stalled_red_gate_is_not_respawned_per_watchdog_pass(tmp_path, monkeypatch):
    home = tmp_path / "hub"
    home.mkdir()
    (home / "config.yaml").write_text("{}\n")
    wg = _gated_wg("wg_wd2")
    _mock_owner(monkeypatch)
    runs = {"n": 0}

    def _run(step, ws):
        runs["n"] += 1
        return False, "still red: deluxe summary missing"

    monkeypatch.setattr("alpi.alp.pipeline_gates.run_gate", _run)
    monkeypatch.setattr(service, "_set_hub_responded_seq", lambda *a: None)
    from alpi.alp import pipeline_gates as gates_mod
    step = gates_mod.step_for(wg.meta, "content")
    gates_mod.write_gate_log(
        home / "alp" / "workgroups" / "wg_wd2", step, 2, False, "9 FAILs",
    )
    service._GATE_ATTEMPTED[(str(home), "wg_wd2", 2)] = True
    service._GATE_REPAIRS[(str(home), "wg_wd2", "content", 1)] = 3
    monkeypatch.setattr(service, "_GATE_RECHECK_SECONDS", 0)

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
    assert captured, "the wake must still fire when the recheck stays red"
    assert runs["n"] == 1
    assert max(service._GATE_REPAIRS.values()) == 3, "a silent recheck spends no repair round"

    for _ in range(4):
        await service._maybe_watchdog_close(home, "mira", wg, _recent())
    assert runs["n"] == 1, "an unchanged stalled workspace must never respawn the gate"


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


def test_malformed_close_overrides_have_no_special_routing_semantics() -> None:
    assert service._terminal_close_needs_routing("BLOCKED·template incomplete") is False
    assert service._terminal_close_needs_routing("skipped·nothing to audit") is False
    assert service._blocked_close_names_owner(
        "BLOCKED·broken in @quill", {"quill"},
    ) == ""


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


def test_the_session_separates_unreported_from_a_measured_miss(tmp_path):
    from alpi.session import Session
    s = Session(home=tmp_path, model="m")
    s.record(input_tokens=1000, output_tokens=50, cost=0.01)
    assert (s.cached_input_tokens, s.cache_measured_input_tokens) == (0, 0)
    s.record(input_tokens=1000, output_tokens=50, cost=0.01, cached_input_tokens=0)
    assert (s.cached_input_tokens, s.cache_measured_input_tokens) == (0, 1000)
    s.record(input_tokens=1000, output_tokens=50, cost=0.01, cached_input_tokens=800)
    assert (s.cached_input_tokens, s.cache_measured_input_tokens) == (800, 2000)
    assert s.input_tokens == 3000
