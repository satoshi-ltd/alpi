from __future__ import annotations

import json
import shutil
import tempfile
import types
from pathlib import Path

import pytest

from alpi import service
from alpi.alp import pipeline_gates as gates

_STEPS = {
    "media-build": {
        "owner": "pixel", "task": "rebuild",
        "gate": {"argv": ["true"], "cwd": "projects/casa"},
        "paths": ["work/status.yaml"],
    },
    "media-qa": {"owner": "lens", "task": "audit"},
}


def _wg(wg_id: str = "wg_paths", steps: dict | None = None):
    return types.SimpleNamespace(meta=types.SimpleNamespace(
        id=wg_id, name="site", hub_pubkey="HUB", paused=False,
        pipelines={"media-build": ("media-build", "media-qa")},
        launch_pipeline=None,
        pipeline_steps=steps or _STEPS,
    ))


def _project(workspace: Path) -> Path:
    root = workspace / "projects" / "casa"
    (root / "assets").mkdir(parents=True)
    (root / "work").mkdir()
    (root / "assets" / "manifest.yaml").write_text("slots: {logo: placeholder}\n")
    (root / "work" / "status.yaml").write_text("phase: media-build\n")
    (root / "node_modules").mkdir()
    (root / "node_modules" / "big.js").write_text("x" * 10)
    return root


def _step(wg):
    return gates.step_for(wg.meta, "media-build")


def test_step_for_carries_the_declared_paths():
    step = _step(_wg())
    assert step.paths == ("work/status.yaml",)


def test_snapshot_is_written_once_and_prunes_heavy_dirs(tmp_path: Path):
    workspace = tmp_path / "ws"
    _project(workspace)
    wg_dir = tmp_path / "wgdir"
    step = _step(_wg())

    gates.snapshot_baseline(wg_dir, step, workspace)
    bp = gates._baseline_path(wg_dir, "media-build")
    assert bp.exists()
    snapshot = json.loads(bp.read_text())
    assert "assets/manifest.yaml" in snapshot
    assert not any(rel.startswith("node_modules") for rel in snapshot)

    stamp = bp.stat().st_mtime_ns
    gates.snapshot_baseline(wg_dir, step, workspace)
    assert bp.stat().st_mtime_ns == stamp


def test_out_of_paths_edit_reds_with_the_file_and_the_owner(tmp_path: Path):
    workspace = tmp_path / "ws"
    root = _project(workspace)
    wg_dir = tmp_path / "wgdir"
    step = _step(_wg())
    gates.snapshot_baseline(wg_dir, step, workspace)

    (root / "assets" / "manifest.yaml").write_text("slots: {logo: logo.webp}\n")
    out = gates.paths_violations(wg_dir, step, workspace)
    assert "BOUNDARY media-build" in out
    assert "assets/manifest.yaml" in out
    assert "@pixel" in out


def test_in_paths_edits_and_gate_outputs_stay_clean(tmp_path: Path):
    workspace = tmp_path / "ws"
    root = _project(workspace)
    wg_dir = tmp_path / "wgdir"
    step = _step(_wg())
    gates.snapshot_baseline(wg_dir, step, workspace)

    (root / "work" / "status.yaml").write_text("phase: media-build\nresult: green\n")
    (root / "dist").mkdir()
    (root / "dist" / "index.html").write_text("<html/>")
    assert gates.paths_violations(wg_dir, step, workspace) == ""


def test_owned_paths_changed_distinguishes_a_handoff_from_no_progress(
    tmp_path: Path,
):
    workspace = tmp_path / "ws"
    root = _project(workspace)
    wg_dir = tmp_path / "wgdir"
    step = _step(_wg())

    assert gates.owned_paths_changed(wg_dir, step, workspace) is None
    gates.snapshot_baseline(wg_dir, step, workspace)
    assert gates.owned_paths_changed(wg_dir, step, workspace) is False

    (root / "assets" / "manifest.yaml").write_text("outside: changed\n")
    assert gates.owned_paths_changed(wg_dir, step, workspace) is False

    (root / "work" / "status.yaml").write_text("phase: complete\n")
    assert gates.owned_paths_changed(wg_dir, step, workspace) is True


def test_deletion_outside_paths_is_a_violation(tmp_path: Path):
    workspace = tmp_path / "ws"
    root = _project(workspace)
    wg_dir = tmp_path / "wgdir"
    step = _step(_wg())
    gates.snapshot_baseline(wg_dir, step, workspace)

    (root / "assets" / "manifest.yaml").unlink()
    out = gates.paths_violations(wg_dir, step, workspace)
    assert "deleted" in out and "assets/manifest.yaml" in out


def test_missing_baseline_fails_closed(tmp_path: Path):
    workspace = tmp_path / "ws"
    _project(workspace)
    step = _step(_wg())
    assert "baseline is missing" in gates.paths_violations(
        tmp_path / "nowhere", step, workspace,
    )


def _escaping_step(cwd: str):
    steps = {
        "media-build": {**_STEPS["media-build"], "gate": {"argv": ["true"], "cwd": cwd}},
        "media-qa": _STEPS["media-qa"],
    }
    return gates.step_for(_wg(steps=steps).meta, "media-build")


@pytest.mark.parametrize("cwd", ["../outside", "/etc", "projects/../../outside"])
def test_escaping_cwd_is_never_scanned(tmp_path: Path, cwd: str):
    workspace = tmp_path / "ws"
    workspace.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "secret.txt").write_text("s")
    step = _escaping_step(cwd)

    assert gates._project_root(step, workspace) is None
    gates.snapshot_baseline(tmp_path / "wgdir", step, workspace)
    assert not (tmp_path / "wgdir" / "phase_baselines").exists()
    assert gates.paths_violations(tmp_path / "wgdir", step, workspace) == ""
    passed, out = gates.run_gate(step, workspace)
    assert passed is False and "escapes the workspace" in out


def test_symlinked_cwd_escaping_the_workspace_is_rejected(tmp_path: Path):
    workspace = tmp_path / "ws"
    (workspace / "projects").mkdir(parents=True)
    outside = tmp_path / "outside"
    outside.mkdir()
    (workspace / "projects" / "casa").symlink_to(outside)
    step = _step(_wg())

    assert gates._project_root(step, workspace) is None
    gates.snapshot_baseline(tmp_path / "wgdir", step, workspace)
    assert not (tmp_path / "wgdir" / "phase_baselines").exists()


def test_gate_side_effects_refresh_boundary_without_hiding_later_agent_edits(tmp_path: Path):
    workspace = tmp_path / "ws"
    root = _project(workspace)
    wg_dir = tmp_path / "wgdir"
    step = _step(_wg())

    assert gates.snapshot_baseline(wg_dir, step, workspace) is True
    generated = root / "src" / "env.d.ts"
    generated.parent.mkdir(parents=True, exist_ok=True)
    generated.write_text('/// <reference path="../.astro/types.d.ts" />\n')

    assert "src/env.d.ts" in gates.paths_violations(wg_dir, step, workspace)
    assert gates.refresh_baseline(wg_dir, step, workspace) is True
    assert gates.paths_violations(wg_dir, step, workspace) == ""

    (root / "src" / "runtime.js").write_text("changed after the gate\n")
    assert "src/runtime.js" in gates.paths_violations(wg_dir, step, workspace)


@pytest.mark.asyncio
async def test_gate_advance_reds_on_a_boundary_violation(tmp_path: Path, monkeypatch):
    home = tmp_path / "hub"
    home.mkdir()
    workspace = tmp_path / "ws"
    root = _project(workspace)
    wg = _wg("wg_gate_paths")
    monkeypatch.setattr(
        "alpi.alp.peers.load",
        lambda h: [types.SimpleNamespace(id="pixel", pubkey="PIXELPK")],
    )
    cfg = types.SimpleNamespace(workspace_path=workspace)
    monkeypatch.setattr("alpi.config.load", lambda h: cfg)
    ran = {"gate": False}

    def fake_run(step, ws):
        ran["gate"] = True
        return True, "clean"

    monkeypatch.setattr("alpi.alp.pipeline_gates.run_gate", fake_run)
    monkeypatch.setattr(service, "_set_hub_responded_seq", lambda *a: None)
    service._GATE_ATTEMPTED.clear()
    service._GATE_REPAIRS.clear()

    recent = [
        {"seq": 1, "from": "HUB", "text": "@pixel #task #media-build rebuild"},
        {"seq": 2, "from": "PIXELPK", "text": "rebuilt, dist green"},
    ]
    await service._ensure_phase_baseline(home, wg, recent)
    (root / "assets" / "manifest.yaml").write_text("slots: {logo: filled-by-pixel}\n")

    notes: list[str] = []

    async def fake_post(h, wid, text, cost=None):
        notes.append(text.decode())
        return {"seq": 10 + len(notes)}

    monkeypatch.setattr("alpi.alp.workgroup_client.post", fake_post)
    out = await service._maybe_gate_advance(home, wg, recent, "HUB")
    assert out is True, "boundary red enters the same repair-note flow"
    assert ran["gate"] is False, "the command never runs over a boundary violation"
    assert "BOUNDARY media-build" in notes[0]
    assert "assets/manifest.yaml" in notes[0]

    log = home / "alp" / "workgroups" / "wg_gate_paths" / "gates" / "media-build-2.log"
    assert log.exists(), "the violation is auditable like any other red"


@pytest.mark.asyncio
async def test_no_progress_delivery_continues_without_spending_repairs(
    tmp_path: Path, monkeypatch,
):
    home = tmp_path / "hub"
    home.mkdir()
    workspace = tmp_path / "ws"
    _project(workspace)
    wg = _wg("wg_no_progress")
    monkeypatch.setattr(
        "alpi.alp.peers.load",
        lambda h: [types.SimpleNamespace(id="pixel", pubkey="PIXELPK")],
    )
    monkeypatch.setattr(
        "alpi.config.load",
        lambda h: types.SimpleNamespace(workspace_path=workspace),
    )
    monkeypatch.setattr(
        "alpi.alp.pipeline_gates.run_gate",
        lambda step, ws: (False, "work/status.yaml is unchanged"),
    )
    monkeypatch.setattr(service, "_set_hub_responded_seq", lambda *a: None)
    posted: list[str] = []

    async def fake_post(h, wid, text, cost=None):
        posted.append(text.decode())
        return {"seq": 20 + len(posted)}

    monkeypatch.setattr("alpi.alp.workgroup_client.post", fake_post)
    service._GATE_ATTEMPTED.clear()
    service._GATE_REPAIRS.clear()
    service._GATE_NO_PROGRESS.clear()
    opener = {"seq": 1, "from": "HUB", "text": "@pixel #task #media-build rebuild"}
    await service._ensure_phase_baseline(home, wg, [opener])

    for seq in (2, 3):
        out = await service._maybe_gate_advance(
            home, wg,
            [opener, {"seq": seq, "from": "PIXELPK", "text": "not delivered"}],
            "HUB",
        )
        assert out is True

    out = await service._maybe_gate_advance(
        home, wg,
        [opener, {"seq": 4, "from": "PIXELPK", "text": "still not delivered"}],
        "HUB",
    )

    assert isinstance(out, service._GateRepairExhausted)
    assert service._GATE_REPAIRS == {}
    assert "continuation 1/2" in posted[0]
    assert "continuation 2/2" in posted[1]
    assert "No gate repair round was consumed" in out


@pytest.mark.asyncio
async def test_repeated_red_delivery_counts_as_no_progress(
    tmp_path: Path, monkeypatch,
):
    home = tmp_path / "hub"
    home.mkdir()
    workspace = tmp_path / "ws"
    root = _project(workspace)
    wg = _wg("wg_repeated_red")
    monkeypatch.setattr(
        "alpi.alp.peers.load",
        lambda h: [types.SimpleNamespace(id="pixel", pubkey="PIXELPK")],
    )
    monkeypatch.setattr(
        "alpi.config.load",
        lambda h: types.SimpleNamespace(workspace_path=workspace),
    )
    monkeypatch.setattr(service, "_set_hub_responded_seq", lambda *a: None)
    posted: list[str] = []

    async def fake_post(h, wid, text, cost=None):
        posted.append(text.decode())
        return {"seq": 20 + len(posted)}

    monkeypatch.setattr("alpi.alp.workgroup_client.post", fake_post)
    service._GATE_ATTEMPTED.clear()
    service._GATE_RED_SIGNATURE.clear()
    service._GATE_REPAIRS.clear()
    service._GATE_NO_PROGRESS.clear()
    opener = {"seq": 1, "from": "HUB", "text": "@pixel #task #media-build rebuild"}
    await service._ensure_phase_baseline(home, wg, [opener])
    (root / "work" / "status.yaml").write_text("phase: attempted\n")
    (root / "assets" / "manifest.yaml").write_text("outside: changed\n")

    first = await service._maybe_gate_advance(
        home, wg,
        [opener, {"seq": 2, "from": "PIXELPK", "text": "first delivery"}],
        "HUB",
    )
    second = await service._maybe_gate_advance(
        home, wg,
        [opener, {"seq": 3, "from": "PIXELPK", "text": "same delivery again"}],
        "HUB",
    )

    assert first is True
    assert second is True
    assert len(service._GATE_REPAIRS) == 1
    assert "repair round 1/3" in posted[0]
    assert "continuation 1/2" in posted[1]


@pytest.fixture
def short_tmp() -> Path:
    d = Path(tempfile.mkdtemp(prefix="alp-paths-", dir="/tmp"))
    try:
        yield d
    finally:
        shutil.rmtree(d, ignore_errors=True)


def _factory(short_tmp: Path, monkeypatch, budget: dict | None = None):
    from alpi import home as home_mod
    from alpi.alp import peers as peers_mod
    from alpi.alp import workgroup as wg_mod
    from alpi.alp.keys import load_or_generate
    from alpi.alp.peers import Peer

    root = short_tmp / "root"
    home = root / "profiles" / "mira"
    home.mkdir(parents=True)
    monkeypatch.setattr(home_mod, "_ROOT", root)
    kp = load_or_generate(home)

    pixel_home = root / "profiles" / "pixel"
    pixel_home.mkdir(parents=True)
    pixel_pk = load_or_generate(pixel_home).pubkey_b64()
    peers_mod.add(home, Peer(id="pixel", pubkey=pixel_pk, allow=["workgroup.post"]))

    workspace = short_tmp / "ws"
    _project(workspace)
    from alpi import config as cfg_mod

    real_load = cfg_mod.load

    def _load(h):
        cfg = real_load(h)
        cfg.workspace = str(workspace)
        return cfg

    monkeypatch.setattr("alpi.config.load", _load)
    wg = wg_mod.create(
        home, name="site", hub_kp=kp, member_pubkeys=[pixel_pk],
        budget=budget,
        pipelines={
            "media-build": ["media-build", "media-qa"],
            "content": ["content"],
        },
        launch_pipeline=None,
        pipeline_steps={
            "media-build": {
                "owner": "pixel", "task": "rebuild",
                "gate": {"argv": ["true"], "cwd": "projects/casa"},
                "paths": ["work/**"],
            },
            "media-qa": {"owner": "pixel", "task": "audit"},
            "content": {
                "owner": "pixel", "task": "write",
                "gate": {"argv": ["true"], "cwd": "projects/casa"},
                "paths": ["work/**"],
            },
        },
    )
    wg_dir = home / "alp" / "workgroups" / wg.meta.id
    return home, wg, wg_dir, workspace


@pytest.mark.asyncio
async def test_opener_post_snapshots_the_baseline_synchronously(
    short_tmp: Path, monkeypatch,
) -> None:
    from alpi.alp import workgroup_client as wc

    home, wg, wg_dir, _ = _factory(short_tmp, monkeypatch)
    await wc.trigger_pipeline(home, wg.meta.id, "media-build")
    assert gates._baseline_path(wg_dir, "media-build").exists(), \
        "no service tick ran — the accept path itself wrote it"


@pytest.mark.asyncio
async def test_same_phase_retask_preserves_the_run_baseline(
    short_tmp: Path, monkeypatch,
) -> None:
    from alpi.alp import workgroup_client as wc

    home, wg, wg_dir, workspace = _factory(short_tmp, monkeypatch)
    await wc.trigger_pipeline(home, wg.meta.id, "media-build")

    (workspace / "projects" / "casa" / "assets" / "manifest.yaml").write_text(
        "slots: {logo: whitewash-attempt}\n",
    )
    await wc.post(home, wg.meta.id, b"@pixel #task #media-build re-deliver the build", operator_abandon=True)

    step = gates.step_for(wg.meta, "media-build")
    out = gates.paths_violations(wg_dir, step, workspace)
    assert "assets/manifest.yaml" in out, "the re-task must not whitewash the edit"


@pytest.mark.asyncio
async def test_done_close_clears_the_run_baseline(short_tmp: Path, monkeypatch) -> None:
    from alpi.alp import workgroup_client as wc

    home, wg, wg_dir, _ = _factory(short_tmp, monkeypatch)
    await wc.trigger_pipeline(home, wg.meta.id, "media-build")
    assert gates._baseline_path(wg_dir, "media-build").exists()

    await wc.post(home, wg.meta.id, b"#done skipped \xc2\xb7 rebuild not needed")
    assert not gates._baseline_path(wg_dir, "media-build").exists()


@pytest.mark.asyncio
async def test_preempting_trigger_swaps_the_baselines(short_tmp: Path, monkeypatch) -> None:
    from alpi.alp import workgroup_client as wc

    home, wg, wg_dir, _ = _factory(short_tmp, monkeypatch)
    await wc.trigger_pipeline(home, wg.meta.id, "media-build")
    assert gates._baseline_path(wg_dir, "media-build").exists()

    await wc.trigger_pipeline(home, wg.meta.id, "content")
    assert not gates._baseline_path(wg_dir, "media-build").exists(), \
        "a preempted run's baseline must not leak into the phase's next run"
    assert gates._baseline_path(wg_dir, "content").exists()


@pytest.mark.asyncio
async def test_rejected_opener_leaves_no_baseline_and_no_post(
    short_tmp: Path, monkeypatch,
) -> None:
    from alpi.alp import workgroup_client as wc

    home, wg, wg_dir, workspace = _factory(
        short_tmp, monkeypatch, budget={"max_usd": 0.05},
    )
    with pytest.raises(ValueError, match="budget-exceeded"):
        await wc.post(
            home, wg.meta.id,
            b"@pixel #task #media-build rebuild", cost={"usd": 1.0}, operator_abandon=True,
        )
    assert not gates._baseline_path(wg_dir, "media-build").exists()
    assert (wg_dir / "transcript.jsonl").read_text().strip() == ""

    (workspace / "projects" / "casa" / "assets" / "manifest.yaml").write_text(
        "slots: {logo: edited-before-the-real-open}\n",
    )
    await wc.post(home, wg.meta.id, b"@pixel #task #media-build rebuild", operator_abandon=True)
    step = gates.step_for(wg.meta, "media-build")
    assert gates.paths_violations(wg_dir, step, workspace) == "", \
        "the retry's baseline captures the state at the accepted open, not the rejected one"


@pytest.mark.asyncio
async def test_admission_failure_rolls_back_a_fresh_baseline(
    short_tmp: Path, monkeypatch,
) -> None:
    from alpi.alp import workgroup_client as wc

    home, wg, wg_dir, _ = _factory(short_tmp, monkeypatch)

    def boom(*a, **kw):
        raise OSError("simulated append failure")

    monkeypatch.setattr("alpi.alp.workgroup._admit_post_locked", boom)
    with pytest.raises(ValueError, match="simulated append failure"):
        await wc.post(home, wg.meta.id, b"@pixel #task #media-build rebuild", operator_abandon=True)
    assert not gates._baseline_path(wg_dir, "media-build").exists()


@pytest.mark.asyncio
async def test_ledger_failure_leaves_transcript_ledger_and_baseline_intact(
    short_tmp: Path, monkeypatch,
) -> None:
    from alpi.alp import workgroup as wg_mod
    from alpi.alp import workgroup_client as wc

    home, wg, wg_dir, _ = _factory(short_tmp, monkeypatch)

    def boom(*a, **kw):
        raise OSError("simulated ledger write failure")

    with pytest.MonkeyPatch.context() as mp_ctx:
        mp_ctx.setattr("alpi.alp.workgroup._save_ledger", boom)
        with pytest.raises(ValueError, match="simulated ledger write failure"):
            await wc.post(home, wg.meta.id, b"@pixel #task #media-build rebuild", operator_abandon=True)

    assert (wg_dir / "transcript.jsonl").read_text().strip() == "", \
        "a post whose accounting failed must not stay in the transcript"
    assert wg_mod._load_ledger(wg_dir)["posts"] == 0
    assert not gates._baseline_path(wg_dir, "media-build").exists()

    out = await wc.post(home, wg.meta.id, b"@pixel #task #media-build rebuild", operator_abandon=True)
    assert out["seq"] == 1
    assert wg_mod._load_ledger(wg_dir)["posts"] == 1
    assert gates._baseline_path(wg_dir, "media-build").exists()


@pytest.mark.asyncio
async def test_encryption_failure_rolls_back_a_fresh_baseline(
    short_tmp: Path, monkeypatch,
) -> None:
    from alpi.alp import workgroup_client as wc

    home, wg, wg_dir, _ = _factory(short_tmp, monkeypatch)

    def boom(*a, **kw):
        raise RuntimeError("simulated encrypt failure")

    monkeypatch.setattr("alpi.alp.workgroup.encrypt_post", boom)
    with pytest.raises(ValueError, match="simulated encrypt failure"):
        await wc.post(home, wg.meta.id, b"@pixel #task #media-build rebuild", operator_abandon=True)
    assert not gates._baseline_path(wg_dir, "media-build").exists()
    assert (wg_dir / "transcript.jsonl").read_text().strip() == ""
