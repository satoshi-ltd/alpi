"""``data.providers.*`` + ``data.peers.*`` — control-plane CRUD."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from alpi import config as cfg_mod
from alpi.host import server as host_server
from alpi.alp.keys import load_or_generate
from alpi.host import config as data_config
from alpi.host import handlers as data_handlers


def _bootstrap(tmp_path: Path) -> Path:
    home = tmp_path / "h"
    home.mkdir()
    cfg = cfg_mod.Config(home=home, model="x")
    cfg_mod.save(cfg)
    return home


@pytest.mark.asyncio
async def test_providers_set_and_unset_key(tmp_path: Path, monkeypatch) -> None:
    home = _bootstrap(tmp_path)
    monkeypatch.setattr(data_handlers, "_resolve_home", lambda p: home)

    srv = host_server.Server(home=home)
    data_config.register(srv)

    body = {
        "id": "r",
        "method": "host.providers.set_key",
        "params": {"profile": "default", "key": "MY_KEY", "value": "abc"},
    }
    resp = await srv._dispatch(body)
    assert resp["result"]["ok"] is True
    assert "MY_KEY=abc" in (home / ".env").read_text()

    body["method"] = "host.providers.unset_key"
    body["params"] = {"profile": "default", "key": "MY_KEY"}
    resp = await srv._dispatch(body)
    assert resp["result"]["ok"] is True
    assert "MY_KEY" not in (home / ".env").read_text()


@pytest.mark.asyncio
async def test_providers_add_remove_ollama(tmp_path: Path, monkeypatch) -> None:
    home = _bootstrap(tmp_path)
    monkeypatch.setattr(data_handlers, "_resolve_home", lambda p: home)

    srv = host_server.Server(home=home)
    data_config.register(srv)

    add = {"id": "1", "method": "host.providers.add_ollama",
           "params": {"profile": "default", "name": "local", "url": "http://x:11434"}}
    assert (await srv._dispatch(add))["result"]["ok"] is True

    cfg = cfg_mod.load(home)
    assert cfg.providers["ollama"][0] == {"name": "local", "url": "http://x:11434"}

    # Adding the same name again must fail with a structured error.
    dup = await srv._dispatch(add)
    assert dup["error"]["code"] == -32008

    rm = {"id": "2", "method": "host.providers.remove_ollama",
          "params": {"profile": "default", "name": "local"}}
    assert (await srv._dispatch(rm))["result"]["ok"] is True
    cfg = cfg_mod.load(home)
    assert cfg.providers.get("ollama", []) == []


@pytest.mark.asyncio
async def test_providers_openrouter_model(tmp_path: Path, monkeypatch) -> None:
    home = _bootstrap(tmp_path)
    monkeypatch.setattr(data_handlers, "_resolve_home", lambda p: home)

    srv = host_server.Server(home=home)
    data_config.register(srv)

    add = {"id": "1", "method": "host.providers.add_openrouter_model",
           "params": {"profile": "default", "model": "openrouter/anthropic/claude"}}
    assert (await srv._dispatch(add))["result"]["ok"] is True
    cfg = cfg_mod.load(home)
    assert cfg.providers["openrouter"]["models"] == ["anthropic/claude"]


@pytest.mark.asyncio
async def test_peers_add_remove(tmp_path: Path, monkeypatch) -> None:
    from alpi.alp import peers as peers_mod

    home = _bootstrap(tmp_path)
    load_or_generate(home)
    monkeypatch.setattr(data_handlers, "_resolve_home", lambda p: home)

    srv = host_server.Server(home=home)
    data_config.register(srv)

    add = {
        "id": "1",
        "method": "host.peers.add",
        "params": {
            "profile": "default",
            "id": "alice",
            "pubkey": "AAAA",
            "allow": ["link.ask"],
        },
    }
    assert (await srv._dispatch(add))["result"]["ok"] is True
    p = peers_mod.get_by_id(home, "alice")
    assert p is not None
    assert p.allow == ["link.ask"]

    rm = {"id": "2", "method": "host.peers.remove",
          "params": {"profile": "default", "id": "alice"}}
    assert (await srv._dispatch(rm))["result"]["ok"] is True
    assert peers_mod.get_by_id(home, "alice") is None

    miss = await srv._dispatch({
        "id": "3", "method": "host.peers.remove",
        "params": {"profile": "default", "id": "ghost"},
    })
    assert miss["error"]["code"] == -32004


@pytest.mark.asyncio
async def test_mcp_add_remove(tmp_path: Path, monkeypatch) -> None:
    home = _bootstrap(tmp_path)
    monkeypatch.setattr(data_handlers, "_resolve_home", lambda p: home)

    srv = host_server.Server(home=home)
    data_config.register(srv)

    add = {"id": "1", "method": "host.mcp.add", "params": {
        "profile": "default", "name": "fs", "command": "uvx",
        "args": ["mcp-server-filesystem"],
        "env": {"FOO": "bar"},
    }}
    assert (await srv._dispatch(add))["result"]["ok"] is True
    cfg = cfg_mod.load(home)
    assert cfg.raw["mcp"]["servers"]["fs"]["command"] == "uvx"
    assert cfg.raw["mcp"]["servers"]["fs"]["args"] == ["mcp-server-filesystem"]
    assert cfg.raw["mcp"]["servers"]["fs"]["env"] == {"FOO": "bar"}

    rm = {"id": "2", "method": "host.mcp.remove",
          "params": {"profile": "default", "name": "fs"}}
    assert (await srv._dispatch(rm))["result"]["ok"] is True

    miss = await srv._dispatch({
        "id": "3", "method": "host.mcp.remove",
        "params": {"profile": "default", "name": "ghost"},
    })
    assert miss["error"]["code"] == -32004


@pytest.mark.asyncio
async def test_sandbox_set_disables_network(tmp_path: Path, monkeypatch) -> None:
    home = _bootstrap(tmp_path)
    cfg = cfg_mod.load(home)
    cfg.tools.terminal.sandbox = True
    cfg.tools.terminal.allow_network = True
    cfg_mod.save(cfg)

    monkeypatch.setattr(data_handlers, "_resolve_home", lambda p: home)
    srv = host_server.Server(home=home)
    data_config.register(srv)

    body = {"id": "1", "method": "host.sandbox.set",
            "params": {"profile": "default", "state": "off"}}
    assert (await srv._dispatch(body))["result"]["ok"] is True

    cfg = cfg_mod.load(home)
    assert cfg.tools.terminal.sandbox is False
    # Disabling sandbox forces network off too (CLI invariant).
    assert cfg.tools.terminal.allow_network is False


@pytest.mark.asyncio
async def test_sandbox_network_requires_sandbox(tmp_path: Path, monkeypatch) -> None:
    home = _bootstrap(tmp_path)
    monkeypatch.setattr(data_handlers, "_resolve_home", lambda p: home)
    srv = host_server.Server(home=home)
    data_config.register(srv)

    body = {"id": "1", "method": "host.sandbox.network",
            "params": {"profile": "default", "state": "on"}}
    resp = await srv._dispatch(body)
    assert resp["error"]["code"] == -32008


@pytest.mark.asyncio
async def test_voice_set_voice_and_autoplay(tmp_path: Path, monkeypatch) -> None:
    home = _bootstrap(tmp_path)
    monkeypatch.setattr(data_handlers, "_resolve_home", lambda p: home)
    srv = host_server.Server(home=home)
    data_config.register(srv)

    set_v = {"id": "1", "method": "host.voice.set_voice",
             "params": {"profile": "default", "voice_id": "es-ES-ElviraNeural"}}
    assert (await srv._dispatch(set_v))["result"]["ok"] is True

    auto = {"id": "2", "method": "host.voice.autoplay",
            "params": {"profile": "default", "state": "on"}}
    assert (await srv._dispatch(auto))["result"]["ok"] is True

    cfg = cfg_mod.load(home)
    assert cfg.tools.tts.voice == "es-ES-ElviraNeural"
    assert cfg.tools.tts.autoplay is True


@pytest.mark.asyncio
async def test_gateway_remove_drops_env(tmp_path: Path, monkeypatch) -> None:
    home = _bootstrap(tmp_path)
    (home / ".env").write_text(
        "TELEGRAM_BOT_TOKEN=abc\nTELEGRAM_ALLOWED_CHAT_IDS=1\nOTHER=keep\n"
    )
    monkeypatch.setattr(data_handlers, "_resolve_home", lambda p: home)
    srv = host_server.Server(home=home)
    data_config.register(srv)

    body = {"id": "1", "method": "host.gateway.remove",
            "params": {"profile": "default", "name": "telegram"}}
    assert (await srv._dispatch(body))["result"]["ok"] is True
    text = (home / ".env").read_text()
    assert "TELEGRAM_BOT_TOKEN" not in text
    assert "OTHER=keep" in text
