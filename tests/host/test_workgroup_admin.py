"""Workgroup admin host verbs — create / update / add_member / remove."""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

import pytest

from alpi.alp.keys import load_or_generate
from alpi.host import server as host_server
from alpi.host import workgroup_admin


@pytest.fixture
def short_tmp():
    d = Path(tempfile.mkdtemp(prefix="alp-host-wgadmin-", dir="/tmp"))
    try:
        yield d
    finally:
        shutil.rmtree(d, ignore_errors=True)


def _seed(home: Path) -> None:
    home.mkdir(parents=True, exist_ok=True)
    load_or_generate(home)


@pytest.mark.asyncio
async def test_create_workgroup_returns_id(short_tmp: Path, monkeypatch) -> None:
    home = short_tmp / "h"
    _seed(home)
    from alpi import home as home_mod
    monkeypatch.setattr(home_mod, "_ROOT", short_tmp)
    monkeypatch.setattr(home_mod, "home_for", lambda profile: home)

    srv = host_server.Server(home=home)
    workgroup_admin.register(srv)

    body = {
        "id": "r",
        "method": "host.workgroup.create",
        "params": {"profile": "default", "name": "research", "members": []},
    }
    resp = await srv._dispatch(body)
    assert "result" in resp, resp
    assert resp["result"]["wg_id"]
    assert resp["result"]["members"] == 1  # hub itself


@pytest.mark.asyncio
async def test_create_workgroup_assigns_pipeline(short_tmp: Path, monkeypatch) -> None:
    home = short_tmp / "h"
    _seed(home)
    from alpi import home as home_mod
    from alpi.alp import workgroup as wg_mod
    monkeypatch.setattr(home_mod, "_ROOT", short_tmp)
    monkeypatch.setattr(home_mod, "home_for", lambda profile: home)

    srv = host_server.Server(home=home)
    workgroup_admin.register(srv)

    # Comma-separated string — the shape a desktop/mobile UI field sends.
    resp = await srv._dispatch({
        "id": "r", "method": "host.workgroup.create",
        "params": {"profile": "default", "name": "factory", "members": [],
                   "pipeline": "intake, content, build, qa"},
    })
    wg = wg_mod.load(home, resp["result"]["wg_id"])
    assert wg.meta.pipeline == ("intake", "content", "build", "qa")

    # A list is accepted too (and normalised/lowercased by the core).
    resp2 = await srv._dispatch({
        "id": "r2", "method": "host.workgroup.create",
        "params": {"profile": "default", "name": "factory2", "members": [],
                   "pipeline": ["Intake", "QA"]},
    })
    wg2 = wg_mod.load(home, resp2["result"]["wg_id"])
    assert wg2.meta.pipeline == ("intake", "qa")

    # Absent pipeline → a normal deliberation workgroup.
    resp3 = await srv._dispatch({
        "id": "r3", "method": "host.workgroup.create",
        "params": {"profile": "default", "name": "talk", "members": []},
    })
    wg3 = wg_mod.load(home, resp3["result"]["wg_id"])
    assert wg3.meta.pipeline == ()


@pytest.mark.asyncio
async def test_create_rejects_empty_name(short_tmp: Path, monkeypatch) -> None:
    home = short_tmp / "h"
    _seed(home)
    from alpi import home as home_mod
    monkeypatch.setattr(home_mod, "_ROOT", short_tmp)
    monkeypatch.setattr(home_mod, "home_for", lambda profile: home)

    srv = host_server.Server(home=home)
    workgroup_admin.register(srv)

    resp = await srv._dispatch({
        "id": "r",
        "method": "host.workgroup.create",
        "params": {"profile": "default", "name": "", "members": []},
    })
    assert resp["error"]["code"] == -32602


@pytest.mark.asyncio
async def test_update_briefing_round_trip(short_tmp: Path, monkeypatch) -> None:
    home = short_tmp / "h"
    _seed(home)
    from alpi import home as home_mod
    monkeypatch.setattr(home_mod, "_ROOT", short_tmp)
    monkeypatch.setattr(home_mod, "home_for", lambda profile: home)

    srv = host_server.Server(home=home)
    workgroup_admin.register(srv)

    create = await srv._dispatch({
        "id": "r1",
        "method": "host.workgroup.create",
        "params": {"profile": "default", "name": "research", "members": []},
    })
    wg_id = create["result"]["wg_id"]

    update = await srv._dispatch({
        "id": "r2",
        "method": "host.workgroup.update",
        "params": {"profile": "default", "wg_id": wg_id, "briefing": "scope: weekly menu"},
    })
    assert update["result"]["ok"]
    assert "briefing" in update["result"]["changes"]


@pytest.mark.asyncio
async def test_update_pipeline_round_trip(short_tmp: Path, monkeypatch) -> None:
    home = short_tmp / "h"
    _seed(home)
    from alpi import home as home_mod
    from alpi.alp import workgroup as wg_mod
    monkeypatch.setattr(home_mod, "_ROOT", short_tmp)
    monkeypatch.setattr(home_mod, "home_for", lambda profile: home)

    srv = host_server.Server(home=home)
    workgroup_admin.register(srv)

    create = await srv._dispatch({
        "id": "r1", "method": "host.workgroup.create",
        "params": {"profile": "default", "name": "factory", "members": []},
    })
    wg_id = create["result"]["wg_id"]

    # Assign a pipeline on an existing workgroup (the settings-page path).
    upd = await srv._dispatch({
        "id": "r2", "method": "host.workgroup.update",
        "params": {"profile": "default", "wg_id": wg_id,
                   "pipeline": "intake, build, qa"},
    })
    assert "pipeline" in upd["result"]["changes"]
    assert wg_mod.load(home, wg_id).meta.pipeline == ("intake", "build", "qa")

    # An empty string clears it (back to a deliberation workgroup).
    upd2 = await srv._dispatch({
        "id": "r3", "method": "host.workgroup.update",
        "params": {"profile": "default", "wg_id": wg_id, "pipeline": ""},
    })
    assert "pipeline" in upd2["result"]["changes"]
    assert wg_mod.load(home, wg_id).meta.pipeline == ()


def test_workgroup_list_rows_include_pipeline(short_tmp: Path) -> None:
    home = short_tmp / "h"
    _seed(home)
    from alpi.alp import workgroup as wg_mod
    from alpi.host.device_state import _hub_workgroups

    kp = load_or_generate(home)
    wg_mod.create(
        home,
        name="factory",
        hub_kp=kp,
        member_pubkeys=[],
        pipeline=["intake", "build", "qa"],
    )

    rows = _hub_workgroups(home, "default")
    assert rows[0]["pipeline"] == ["intake", "build", "qa"]


@pytest.mark.asyncio
async def test_remove_workgroup_clears_dir(short_tmp: Path, monkeypatch) -> None:
    home = short_tmp / "h"
    _seed(home)
    from alpi import home as home_mod
    monkeypatch.setattr(home_mod, "_ROOT", short_tmp)
    monkeypatch.setattr(home_mod, "home_for", lambda profile: home)

    srv = host_server.Server(home=home)
    workgroup_admin.register(srv)

    create = await srv._dispatch({
        "id": "r1",
        "method": "host.workgroup.create",
        "params": {"profile": "default", "name": "research", "members": []},
    })
    wg_id = create["result"]["wg_id"]
    wg_dir = home / "alp" / "workgroups" / wg_id
    assert wg_dir.exists()

    remove = await srv._dispatch({
        "id": "r2",
        "method": "host.workgroup.remove",
        "params": {"profile": "default", "wg_id": wg_id},
    })
    assert remove["result"]["ok"]
    assert not wg_dir.exists()


@pytest.mark.asyncio
async def test_create_emits_workgroup_changed(short_tmp: Path, monkeypatch) -> None:
    from alpi import home as home_mod
    from alpi.host import events as host_events

    home = short_tmp / "h"
    _seed(home)
    monkeypatch.setattr(home_mod, "_ROOT", short_tmp)
    monkeypatch.setattr(home_mod, "home_for", lambda profile: home)
    srv = host_server.Server(home=home)
    workgroup_admin.register(srv)

    captured: list[tuple[str, dict]] = []
    monkeypatch.setattr(
        host_events, "emit",
        lambda kind, data=None: captured.append((kind, data or {})),
    )

    resp = await srv._dispatch({
        "id": "r",
        "method": "host.workgroup.create",
        "params": {"profile": "default", "name": "research", "members": []},
    })
    wg_id = resp["result"]["wg_id"]
    assert any(
        k == "workgroup_changed" and d.get("wg_id") == wg_id
        and d.get("action") == "created"
        for k, d in captured
    )


@pytest.mark.asyncio
async def test_action_rejects_unknown(short_tmp: Path, monkeypatch) -> None:
    home = short_tmp / "h"
    _seed(home)
    from alpi import home as home_mod
    monkeypatch.setattr(home_mod, "_ROOT", short_tmp)
    monkeypatch.setattr(home_mod, "home_for", lambda profile: home)

    srv = host_server.Server(home=home)
    workgroup_admin.register(srv)

    resp = await srv._dispatch({
        "id": "r",
        "method": "host.workgroup.action",
        "params": {"profile": "default", "wg_id": "deadbeef", "action": "explode"},
    })
    assert resp["error"]["code"] == -32602
