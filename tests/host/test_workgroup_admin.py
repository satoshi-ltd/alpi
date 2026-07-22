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


@pytest.mark.asyncio
async def test_remove_archives_spend_before_deleting(short_tmp: Path, monkeypatch) -> None:
    home = short_tmp / "h"
    _seed(home)
    from alpi import home as home_mod
    monkeypatch.setattr(home_mod, "_ROOT", short_tmp)
    monkeypatch.setattr(home_mod, "home_for", lambda profile: home)

    srv = host_server.Server(home=home)
    workgroup_admin.register(srv)
    create = await srv._dispatch({
        "id": "a1", "method": "host.workgroup.create",
        "params": {"profile": "default", "name": "research", "members": []},
    })
    wg_id = create["result"]["wg_id"]
    import json as json_mod
    (home / "alp" / "workgroups" / wg_id / "transcript.jsonl").write_text(
        json_mod.dumps({
            "seq": 1, "ts": 1.0, "from": "x", "key_version": 1,
            "nonce": "n", "ciphertext": "c",
            "cost": {"usd": 0.5, "tokens_in": 10, "tokens_out": 5},
        }) + "\n"
    )

    remove = await srv._dispatch({
        "id": "a2", "method": "host.workgroup.remove",
        "params": {"profile": "default", "wg_id": wg_id},
    })
    assert remove["result"]["ok"]

    from alpi import ledger
    records = ledger.read_archive(home)
    rec = next((r for r in records if r["kind"] == "workgroup" and r["id"] == wg_id), None)
    assert rec is not None
    assert rec["cost_usd"] == 0.5


@pytest.mark.asyncio
async def test_remove_aborts_when_spend_archive_fails(short_tmp: Path, monkeypatch) -> None:
    home = short_tmp / "h"
    _seed(home)
    from alpi import home as home_mod
    monkeypatch.setattr(home_mod, "_ROOT", short_tmp)
    monkeypatch.setattr(home_mod, "home_for", lambda profile: home)

    srv = host_server.Server(home=home)
    workgroup_admin.register(srv)
    create = await srv._dispatch({
        "id": "f1", "method": "host.workgroup.create",
        "params": {"profile": "default", "name": "research", "members": []},
    })
    wg_id = create["result"]["wg_id"]
    wg_dir = home / "alp" / "workgroups" / wg_id

    def boom(*_a, **_kw):
        raise OSError("disk full")

    monkeypatch.setattr("alpi.ledger.archive_entity", boom)
    resp = await srv._dispatch({
        "id": "f2", "method": "host.workgroup.remove",
        "params": {"profile": "default", "wg_id": wg_id},
    })
    assert "error" in resp
    assert "spend archive failed" in str(resp["error"])
    assert wg_dir.exists()


@pytest.mark.asyncio
async def test_remove_aborts_when_delete_fails(short_tmp: Path, monkeypatch) -> None:
    from alpi import home as home_mod
    from alpi.host import events as host_events

    home = short_tmp / "h"
    _seed(home)
    monkeypatch.setattr(home_mod, "_ROOT", short_tmp)
    monkeypatch.setattr(home_mod, "home_for", lambda profile: home)
    srv = host_server.Server(home=home)
    workgroup_admin.register(srv)

    create = await srv._dispatch({
        "id": "d1", "method": "host.workgroup.create",
        "params": {"profile": "default", "name": "research", "members": []},
    })
    wg_id = create["result"]["wg_id"]
    wg_dir = home / "alp" / "workgroups" / wg_id

    captured: list[tuple[str, dict]] = []
    monkeypatch.setattr(
        host_events, "emit",
        lambda kind, data=None: captured.append((kind, data or {})),
    )

    import shutil as real_shutil
    real_rmtree = real_shutil.rmtree

    def boom(path, *a, **kw):
        if str(path).rstrip("/").endswith(wg_id):
            raise OSError("permission denied")
        return real_rmtree(path, *a, **kw)

    monkeypatch.setattr("alpi.alp.workgroup._shutil.rmtree", boom)
    resp = await srv._dispatch({
        "id": "d2", "method": "host.workgroup.remove",
        "params": {"profile": "default", "wg_id": wg_id},
    })

    assert "error" in resp
    assert "permission denied" in str(resp["error"])
    assert wg_dir.exists()
    assert not any(
        k == "workgroup_changed" and d.get("action") == "removed"
        for k, d in captured
    )
