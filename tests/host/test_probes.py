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
async def test_email_probe_unknown_id(short_tmp: Path, monkeypatch) -> None:
    home = short_tmp / "h"
    home.mkdir()
    from alpi import home as home_mod
    monkeypatch.setattr(home_mod, "_ROOT", short_tmp)
    monkeypatch.setattr(home_mod, "home_for", lambda profile: home)

    srv = host_server.Server(home=home)
    probes.register(srv)
    resp = await srv._dispatch({
        "id": "r",
        "method": "host.email.probe",
        "params": {"profile": "default", "id": "nobody_x_com"},
    })
    assert resp["error"]["code"] == -32602


@pytest.mark.asyncio
async def test_email_probe_off_when_token_missing(short_tmp: Path, monkeypatch) -> None:
    home = short_tmp / "h"
    home.mkdir()
    from alpi import home as home_mod
    monkeypatch.setattr(home_mod, "_ROOT", short_tmp)
    monkeypatch.setattr(home_mod, "home_for", lambda profile: home)
    from alpi.mail import accounts as accounts_mod
    gmail_id = accounts_mod.add_gmail(home, address="me@gmail.com")

    srv = host_server.Server(home=home)
    probes.register(srv)
    resp = await srv._dispatch({
        "id": "r",
        "method": "host.email.probe",
        "params": {"profile": "default", "id": gmail_id},
    })
    assert resp["result"]["status"] == "off", resp


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
async def test_peers_ping_uses_short_tcp_timeout(
    short_tmp: Path, monkeypatch,
) -> None:
    home = short_tmp / "h"
    home.mkdir()
    from alpi import home as home_mod
    monkeypatch.setattr(home_mod, "_ROOT", short_tmp)
    monkeypatch.setattr(home_mod, "home_for", lambda profile: home)

    from alpi.alp import client as alp_client
    from alpi.alp import peers as peers_mod

    captured: dict = {}

    async def fake_call_tcp(**kwargs):
        captured.update(kwargs)
        return {"agent_name": "x", "version": "x", "nonce": "n"}

    monkeypatch.setattr(alp_client, "call_tcp", fake_call_tcp)

    class FakePeer:
        address = "100.64.0.1:49000"
        pubkey = "x" * 44

    monkeypatch.setattr(peers_mod, "get_by_id", lambda *_a, **_k: FakePeer())

    srv = host_server.Server(home=home)
    probes.register(srv)
    resp = await srv._dispatch({
        "id": "r",
        "method": "host.peers.ping",
        "params": {"profile": "default", "peer_id": "anything"},
    })
    assert resp["result"]["status"] == "on"
    assert "timeout" in captured
    assert captured["timeout"] <= 10.0


@pytest.mark.asyncio
async def test_peers_ping_unix_socket_uses_short_timeout(
    short_tmp: Path, monkeypatch,
) -> None:
    home = short_tmp / "h"
    home.mkdir()
    from alpi import home as home_mod
    monkeypatch.setattr(home_mod, "_ROOT", short_tmp)
    monkeypatch.setattr(home_mod, "home_for", lambda profile: home)

    from alpi.alp import client as alp_client
    from alpi.alp import peers as peers_mod

    captured: dict = {}

    async def fake_call(**kwargs):
        captured.update(kwargs)
        return {"agent_name": "x", "version": "x", "nonce": "n"}

    monkeypatch.setattr(alp_client, "call", fake_call)

    class FakePeer:
        id = "_probe_test_peer"
        address = ""  # empty address forces the Unix-socket branch
        pubkey = "x" * 44

    monkeypatch.setattr(peers_mod, "get_by_id", lambda *_a, **_k: FakePeer())

    profiles_dir = short_tmp / "profiles" / "_probe_test_peer"
    sock = profiles_dir / "alp" / "alp.sock"
    sock.parent.mkdir(parents=True, exist_ok=True)
    sock.touch()
    try:
        srv = host_server.Server(home=home)
        probes.register(srv)
        resp = await srv._dispatch({
            "id": "r",
            "method": "host.peers.ping",
            "params": {"profile": "default", "peer_id": "_probe_test_peer"},
        })
        assert resp["result"]["status"] == "on"
        assert captured.get("timeout", 30.0) <= 10.0
    finally:
        try:
            sock.unlink()
            sock.parent.rmdir()
            profiles_dir.rmdir()
        except OSError:
            pass


@pytest.mark.asyncio
async def test_peers_ping_resolves_colocated_profile_by_pubkey(
    short_tmp: Path, monkeypatch,
) -> None:
    # peer.id is a user-chosen alias; the socket must come from pubkey lookup.
    root = short_tmp / ".alpi"
    root.mkdir()
    home = root  # default profile
    target_profile = root / "profiles" / "real_name"
    target_profile.mkdir(parents=True)

    from alpi import home as home_mod
    from alpi.alp import keys as keys_mod
    monkeypatch.setattr(home_mod, "_ROOT", root)
    monkeypatch.setattr(home_mod, "home_for", lambda profile: home)
    keys_mod.load_or_generate(home)
    target_kp = keys_mod.load_or_generate(target_profile)

    from alpi.alp import client as alp_client
    from alpi.alp import peers as peers_mod

    captured: dict = {}

    async def fake_call(**kwargs):
        captured.update(kwargs)
        return {"agent_name": "x", "version": "x", "nonce": "n"}

    monkeypatch.setattr(alp_client, "call", fake_call)

    class FakePeer:
        address = ""
        pubkey = target_kp.pubkey_b64()

    monkeypatch.setattr(peers_mod, "get_by_id", lambda *_a, **_k: FakePeer())

    sock = target_profile / "alp" / "alp.sock"
    sock.parent.mkdir(parents=True, exist_ok=True)
    sock.touch()

    srv = host_server.Server(home=home)
    probes.register(srv)
    resp = await srv._dispatch({
        "id": "r",
        "method": "host.peers.ping",
        "params": {"profile": "default", "peer_id": "arbitrary_alias"},
    })
    assert resp["result"]["status"] == "on"
    assert str(captured["socket_path"]) == str(sock)


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
