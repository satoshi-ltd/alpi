"""Probe verbs over the host control plane (gateway / peers / model)."""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

import pytest

from alpi.host import probes
from alpi.host import server as host_server


@pytest.fixture
def short_tmp():
    d = Path(tempfile.mkdtemp(prefix="alp-host-probes-", dir="/tmp"))
    try:
        yield d
    finally:
        shutil.rmtree(d, ignore_errors=True)


@pytest.mark.asyncio
async def test_gateway_probe_unknown_name(short_tmp: Path, monkeypatch) -> None:
    home = short_tmp / "h"
    home.mkdir()
    from alpi import home as home_mod
    monkeypatch.setattr(home_mod, "_ROOT", short_tmp)
    monkeypatch.setattr(home_mod, "home_for", lambda profile: home)

    srv = host_server.Server(home=home)
    probes.register(srv)
    resp = await srv._dispatch({
        "id": "r",
        "method": "host.gateway.probe",
        "params": {"profile": "default", "name": "foo"},
    })
    assert resp["error"]["code"] == -32602


@pytest.mark.asyncio
async def test_gateway_probe_off_when_unconfigured(short_tmp: Path, monkeypatch) -> None:
    home = short_tmp / "h"
    home.mkdir()
    from alpi import home as home_mod
    monkeypatch.setattr(home_mod, "_ROOT", short_tmp)
    monkeypatch.setattr(home_mod, "home_for", lambda profile: home)

    srv = host_server.Server(home=home)
    probes.register(srv)
    for name in ("telegram", "imap", "gmail", "matrix"):
        resp = await srv._dispatch({
            "id": "r",
            "method": "host.gateway.probe",
            "params": {"profile": "default", "name": name},
        })
        assert resp["result"]["status"] == "off", (name, resp)


@pytest.mark.asyncio
async def test_peers_ping_unknown_peer(short_tmp: Path, monkeypatch) -> None:
    home = short_tmp / "h"
    home.mkdir()
    from alpi import home as home_mod
    monkeypatch.setattr(home_mod, "_ROOT", short_tmp)
    monkeypatch.setattr(home_mod, "home_for", lambda profile: home)

    srv = host_server.Server(home=home)
    probes.register(srv)
    resp = await srv._dispatch({
        "id": "r",
        "method": "host.peers.ping",
        "params": {"profile": "default", "peer_id": "nobody"},
    })
    assert resp["result"]["status"] == "off"
    assert "no peer" in (resp["result"].get("reason") or "")


@pytest.mark.asyncio
async def test_peers_ping_requires_id(short_tmp: Path, monkeypatch) -> None:
    home = short_tmp / "h"
    home.mkdir()
    from alpi import home as home_mod
    monkeypatch.setattr(home_mod, "_ROOT", short_tmp)
    monkeypatch.setattr(home_mod, "home_for", lambda profile: home)

    srv = host_server.Server(home=home)
    probes.register(srv)
    resp = await srv._dispatch({
        "id": "r",
        "method": "host.peers.ping",
        "params": {"profile": "default"},
    })
    assert resp["error"]["code"] == -32602


@pytest.mark.asyncio
async def test_model_ctx_window_returns_int(short_tmp: Path, monkeypatch) -> None:
    home = short_tmp / "h"
    home.mkdir()
    from alpi import home as home_mod
    monkeypatch.setattr(home_mod, "_ROOT", short_tmp)
    monkeypatch.setattr(home_mod, "home_for", lambda profile: home)

    srv = host_server.Server(home=home)
    probes.register(srv)
    resp = await srv._dispatch({
        "id": "r",
        "method": "host.model.ctx_window",
        "params": {"profile": "default", "model": "openai/gpt-4o-mini"},
    })
    assert "result" in resp, resp
    assert isinstance(resp["result"]["ctx_window"], int)
    assert resp["result"]["ctx_window"] > 0
