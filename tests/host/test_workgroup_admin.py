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
