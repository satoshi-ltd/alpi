from pathlib import Path

import pytest

from alpi import home as home_mod
from alpi.host import config as data_config
from alpi.host import server as host_server


@pytest.mark.asyncio
@pytest.mark.parametrize("name", ["work", "personal", "build.debug", "a-b_c"])
async def test_host_profile_create_accepts_valid_names(
    monkeypatch, tmp_path: Path, name: str,
) -> None:
    monkeypatch.setattr(home_mod, "_ROOT", tmp_path)
    srv = host_server.Server(home=tmp_path)
    data_config.register(srv)

    body = {"id": "r", "method": "host.profile.create", "params": {"name": name}}
    resp = await srv._dispatch(body)
    assert "error" not in resp, resp
    assert resp["result"]["ok"] is True
    assert (tmp_path / "profiles" / name).is_dir()


@pytest.mark.asyncio
@pytest.mark.parametrize("name", [
    "../escape", "..", ".hidden", "a/b", "a\\b", "/abs",
    "-leading-dash", "..foo", "foo/..", "name with space",
    " work", "work ", " work ", "\twork", "work\n",
])
async def test_host_profile_create_rejects_traversal(
    monkeypatch, tmp_path: Path, name: str,
) -> None:
    monkeypatch.setattr(home_mod, "_ROOT", tmp_path)
    srv = host_server.Server(home=tmp_path)
    data_config.register(srv)

    body = {"id": "r", "method": "host.profile.create", "params": {"name": name}}
    resp = await srv._dispatch(body)
    assert "error" in resp, resp
    assert resp["error"]["code"] == -32602
    assert "invalid profile name" in resp["error"]["data"]["detail"].lower()


@pytest.mark.asyncio
@pytest.mark.parametrize("name", ["default", "alpi"])
async def test_host_profile_create_rejects_reserved(
    monkeypatch, tmp_path: Path, name: str,
) -> None:
    monkeypatch.setattr(home_mod, "_ROOT", tmp_path)
    srv = host_server.Server(home=tmp_path)
    data_config.register(srv)

    body = {"id": "r", "method": "host.profile.create", "params": {"name": name}}
    resp = await srv._dispatch(body)
    assert "error" in resp, resp
    assert resp["error"]["code"] == -32602
    detail = resp["error"]["data"]["detail"].lower()
    assert "reserved" in detail or "invalid profile name" in detail


@pytest.mark.asyncio
async def test_host_profile_create_rejects_empty_name(
    monkeypatch, tmp_path: Path,
) -> None:
    monkeypatch.setattr(home_mod, "_ROOT", tmp_path)
    srv = host_server.Server(home=tmp_path)
    data_config.register(srv)

    body = {"id": "r", "method": "host.profile.create", "params": {"name": ""}}
    resp = await srv._dispatch(body)
    assert "error" in resp
    assert resp["error"]["code"] == -32602
    assert "name required" in resp["error"]["data"]["detail"].lower()
