from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from alpi import service
from alpi.alp import pipeline_queue


def _config(home: Path, limit: int) -> None:
    home.mkdir(parents=True, exist_ok=True)
    (home / "config.yaml").write_text(
        f"model: ''\nalp:\n  max_active_workgroups: {limit}\n",
        encoding="utf-8",
    )


def test_queue_is_persistent_fifo_and_requeue_moves_to_the_tail(tmp_path: Path) -> None:
    home = tmp_path / "hub"
    _config(home, 2)

    first = pipeline_queue.enqueue(home, "wg_one", "setup")
    pipeline_queue.enqueue(home, "wg_two", "setup")
    moved = pipeline_queue.enqueue(home, "wg_one", "media")

    assert first["position"] == 1
    assert moved["position"] == 2
    assert [
        (item["wg_id"], item["pipeline"])
        for item in pipeline_queue.entries(home)
    ] == [("wg_two", "setup"), ("wg_one", "media")]
    assert pipeline_queue.positions(home)["wg_one"]["position"] == 2


def test_exact_remove_does_not_drop_a_replaced_entry(tmp_path: Path) -> None:
    home = tmp_path / "hub"
    _config(home, 1)
    old = pipeline_queue.enqueue(home, "wg_one", "setup")
    pipeline_queue.enqueue(home, "wg_one", "media")

    assert pipeline_queue.remove(
        home, "wg_one", "setup", enqueued_at=old["enqueued_at"],
    ) is False
    assert pipeline_queue.positions(home)["wg_one"]["pipeline"] == "media"


def test_paused_running_pipeline_does_not_consume_an_admission_slot(
    tmp_path: Path, monkeypatch,
) -> None:
    running = SimpleNamespace(meta=SimpleNamespace(id="wg_running", paused=False))
    paused = SimpleNamespace(meta=SimpleNamespace(id="wg_paused", paused=True))
    monkeypatch.setattr(
        "alpi.alp.workgroup.list_workgroups", lambda _home: [running, paused],
    )
    monkeypatch.setattr(
        "alpi.host.workgroup.fold_task_state",
        lambda _home, _wid: {"pipeline_run": {"status": "running"}},
    )

    assert service._active_workgroup_ids(tmp_path) == {"wg_running"}


@pytest.mark.asyncio
async def test_daemon_admits_only_the_available_fifo_slots(
    tmp_path: Path, monkeypatch,
) -> None:
    home = tmp_path / "hub"
    _config(home, 2)
    for wid in ("wg_one", "wg_two", "wg_three"):
        pipeline_queue.enqueue(home, wid, "setup")

    monkeypatch.setattr(service, "_active_workgroup_ids", lambda _home: {"wg_live"})
    monkeypatch.setattr(
        "alpi.alp.workgroup.load",
        lambda _home, wid: SimpleNamespace(meta=SimpleNamespace(paused=False, id=wid)),
    )
    admitted = []

    async def fake_trigger(_home, wid, pipeline, **kwargs):
        admitted.append((wid, pipeline, kwargs))
        return {"ok": True}

    monkeypatch.setattr("alpi.alp.workgroup_client.trigger_pipeline", fake_trigger)
    monkeypatch.setattr(
        "alpi.alp.workgroup_client._emit_workgroup_changed", lambda *args: None,
    )

    assert await service._drain_pipeline_queue(home) == 1
    assert [item[:2] for item in admitted] == [("wg_one", "setup")]
    assert [item["wg_id"] for item in pipeline_queue.entries(home)] == [
        "wg_two", "wg_three",
    ]


@pytest.mark.asyncio
async def test_daemon_flushes_the_queue_when_the_limit_is_disabled(
    tmp_path: Path, monkeypatch,
) -> None:
    home = tmp_path / "hub"
    _config(home, 0)
    for wid in ("wg_one", "wg_two"):
        pipeline_queue.enqueue(home, wid, "setup")
    monkeypatch.setattr(service, "_active_workgroup_ids", lambda _home: set())
    monkeypatch.setattr(
        "alpi.alp.workgroup.load",
        lambda _home, wid: SimpleNamespace(meta=SimpleNamespace(paused=False, id=wid)),
    )

    async def fake_trigger(*args, **kwargs):
        return {"ok": True}

    monkeypatch.setattr("alpi.alp.workgroup_client.trigger_pipeline", fake_trigger)
    monkeypatch.setattr(
        "alpi.alp.workgroup_client._emit_workgroup_changed", lambda *args: None,
    )

    assert await service._drain_pipeline_queue(home) == 2
    assert pipeline_queue.entries(home) == []


@pytest.mark.asyncio
async def test_prepare_failure_drops_only_that_queue_entry(
    tmp_path: Path, monkeypatch,
) -> None:
    from alpi.alp import workgroup_client as wc

    home = tmp_path / "hub"
    _config(home, 2)
    pipeline_queue.enqueue(home, "wg_bad", "media-update")
    pipeline_queue.enqueue(home, "wg_good", "setup")
    monkeypatch.setattr(service, "_active_workgroup_ids", lambda _home: set())
    monkeypatch.setattr(
        "alpi.alp.workgroup.load",
        lambda _home, wid: SimpleNamespace(meta=SimpleNamespace(paused=False, id=wid)),
    )
    triggered = []

    async def fake_trigger(_home, wid, pipeline, **kwargs):
        triggered.append((wid, pipeline))
        if wid == "wg_bad":
            raise wc.TriggerError("pipeline-prepare-failed", "inventory command failed")
        return {"ok": True}

    actions = []
    monkeypatch.setattr("alpi.alp.workgroup_client.trigger_pipeline", fake_trigger)
    monkeypatch.setattr(
        "alpi.alp.workgroup_client._emit_workgroup_changed",
        lambda _home, wid, action: actions.append((wid, action)),
    )

    assert await service._drain_pipeline_queue(home) == 1
    assert triggered == [("wg_bad", "media-update"), ("wg_good", "setup")]
    assert pipeline_queue.entries(home) == []
    assert ("wg_bad", "admission_failed") in actions
    assert ("wg_good", "admitted") in actions


def test_limit_resolves_profile_then_default_then_builtin(tmp_path: Path) -> None:
    root = tmp_path / "root"
    hub = root / "profiles" / "mira"
    hub.mkdir(parents=True)
    root.mkdir(exist_ok=True)

    assert pipeline_queue.limit_origin(hub) == (0, "built-in")

    (root / "config.yaml").write_text("alp:\n  max_active_workgroups: 2\n", encoding="utf-8")
    assert pipeline_queue.limit_origin(hub) == (2, "default")

    (hub / "config.yaml").write_text("alp:\n  max_active_workgroups: 0\n", encoding="utf-8")
    assert pipeline_queue.limit_origin(hub) == (0, "profile")
    assert pipeline_queue.limit(hub) == 0

    (hub / "config.yaml").write_text("alp:\n  max_active_workgroups: -1\n", encoding="utf-8")
    assert pipeline_queue.limit_origin(hub) == (2, "default")


def test_a_deliberation_workgroup_with_an_open_task_holds_a_slot(tmp_path: Path, monkeypatch) -> None:
    talking = SimpleNamespace(meta=SimpleNamespace(id="wg_talking", paused=False))
    idle = SimpleNamespace(meta=SimpleNamespace(id="wg_idle", paused=False))
    monkeypatch.setattr("alpi.alp.workgroup.list_workgroups", lambda _home: [talking, idle])
    monkeypatch.setattr(
        "alpi.host.workgroup.fold_task_state",
        lambda _home, wid: {"active": {"slug": "plan"}, "pipeline_run": None} if wid == "wg_talking" else {"active": None, "pipeline_run": None},
    )

    assert service._active_workgroup_ids(tmp_path) == {"wg_talking"}


def test_saving_an_unrelated_setting_keeps_the_inherited_cap(tmp_path: Path) -> None:
    from alpi import config as cfg_mod
    from alpi import yamlfast

    root = tmp_path / "root"
    hub = root / "profiles" / "mira"
    hub.mkdir(parents=True)
    (root / "config.yaml").write_text("alp:\n  max_active_workgroups: 5\n", encoding="utf-8")
    (hub / "config.yaml").write_text("model: ''\n", encoding="utf-8")
    assert pipeline_queue.limit_origin(hub) == (5, "default")

    cfg = cfg_mod.load(hub)
    cfg.workspace = str(tmp_path / "ws")
    cfg_mod.save(cfg)

    assert pipeline_queue.limit_origin(hub) == (5, "default")
    assert "max_active_workgroups" not in (yamlfast.safe_load((hub / "config.yaml").read_text()).get("alp") or {})
