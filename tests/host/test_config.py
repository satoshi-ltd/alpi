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


@pytest.mark.asyncio
async def test_gmail_authorize_writes_env_and_streams_authorized(
    tmp_path: Path, monkeypatch,
) -> None:
    home = _bootstrap(tmp_path)
    monkeypatch.setattr(data_handlers, "_resolve_home", lambda p: home)
    # Strip env vars that might have leaked in from the developer's shell.
    for key in ("GMAIL_CLIENT_ID", "GMAIL_CLIENT_SECRET", "GMAIL_ALLOWED_SENDERS"):
        monkeypatch.delenv(key, raising=False)

    fake_token = type(
        "FakeToken", (), {"email": "alice@example.com"},
    )()
    from alpi.mail import gmail_auth as ga

    monkeypatch.setattr(ga, "first_run", lambda h: fake_token)

    frames: list[dict] = []

    async def collect(frame):
        frames.append(frame)

    await data_config._gmail_authorize(
        {
            "profile": "default",
            "client_id": "cid-123",
            "client_secret": "sec-456",
            "allowed_senders": " Bob@Example.com , carol@x.com ",
        },
        None,
        collect,
    )

    env_text = (home / ".env").read_text()
    assert "GMAIL_CLIENT_ID=cid-123" in env_text
    assert "GMAIL_CLIENT_SECRET=sec-456" in env_text
    assert "GMAIL_ALLOWED_SENDERS=bob@example.com,carol@x.com" in env_text
    # os.environ must be set so first_run can read the credentials.
    import os
    assert os.environ["GMAIL_CLIENT_ID"] == "cid-123"
    assert os.environ["GMAIL_CLIENT_SECRET"] == "sec-456"
    assert frames == [
        {"event": "browser_opened"},
        {"event": "authorized", "email": "alice@example.com"},
    ]


@pytest.mark.asyncio
async def test_gmail_authorize_missing_creds_emits_error(
    tmp_path: Path, monkeypatch,
) -> None:
    home = _bootstrap(tmp_path)
    monkeypatch.setattr(data_handlers, "_resolve_home", lambda p: home)
    for key in ("GMAIL_CLIENT_ID", "GMAIL_CLIENT_SECRET", "GMAIL_ALLOWED_SENDERS"):
        monkeypatch.delenv(key, raising=False)

    frames: list[dict] = []

    async def collect(frame):
        frames.append(frame)

    await data_config._gmail_authorize(
        {"profile": "default", "client_id": "", "client_secret": ""},
        None,
        collect,
    )

    assert len(frames) == 1
    assert frames[0]["event"] == "error"
    assert "required" in frames[0]["text"]
    # No .env file should have been written.
    assert not (home / ".env").exists() or "GMAIL_CLIENT_ID" not in (home / ".env").read_text()


@pytest.mark.asyncio
async def test_gmail_authorize_reuses_stored_creds_on_blank_input(
    tmp_path: Path, monkeypatch,
) -> None:
    """Re-authorize without re-typing the secret falls back to .env."""
    home = _bootstrap(tmp_path)
    (home / ".env").write_text(
        "GMAIL_CLIENT_ID=stored-id\nGMAIL_CLIENT_SECRET=stored-sec\n"
        "GMAIL_ALLOWED_SENDERS=existing@x.com\n"
    )
    monkeypatch.setattr(data_handlers, "_resolve_home", lambda p: home)
    for key in ("GMAIL_CLIENT_ID", "GMAIL_CLIENT_SECRET", "GMAIL_ALLOWED_SENDERS"):
        monkeypatch.delenv(key, raising=False)

    fake_token = type("FakeToken", (), {"email": "bob@example.com"})()
    from alpi.mail import gmail_auth as ga

    monkeypatch.setattr(ga, "first_run", lambda h: fake_token)

    frames: list[dict] = []

    async def collect(frame):
        frames.append(frame)

    # All inputs blank — should reuse stored values.
    await data_config._gmail_authorize(
        {"profile": "default", "client_id": "", "client_secret": ""},
        None,
        collect,
    )

    assert frames[-1] == {"event": "authorized", "email": "bob@example.com"}
    import os
    assert os.environ["GMAIL_CLIENT_ID"] == "stored-id"
    assert os.environ["GMAIL_CLIENT_SECRET"] == "stored-sec"


@pytest.mark.asyncio
async def test_gmail_authorize_propagates_oauth_error(
    tmp_path: Path, monkeypatch,
) -> None:
    home = _bootstrap(tmp_path)
    monkeypatch.setattr(data_handlers, "_resolve_home", lambda p: home)
    for key in ("GMAIL_CLIENT_ID", "GMAIL_CLIENT_SECRET", "GMAIL_ALLOWED_SENDERS"):
        monkeypatch.delenv(key, raising=False)

    from alpi.mail import gmail_auth as ga

    def boom(_h):
        raise ga.GmailAuthError("OAuth denied: access_denied")

    monkeypatch.setattr(ga, "first_run", boom)

    frames: list[dict] = []

    async def collect(frame):
        frames.append(frame)

    await data_config._gmail_authorize(
        {"profile": "default", "client_id": "x", "client_secret": "y"},
        None,
        collect,
    )

    assert frames[0] == {"event": "browser_opened"}
    assert frames[1]["event"] == "error"
    assert "access_denied" in frames[1]["text"]


@pytest.mark.asyncio
async def test_providers_set_key_rejects_duplicate_telegram_token(
    tmp_path: Path, monkeypatch,
) -> None:
    from alpi import home as home_mod
    root = tmp_path / "alpi-root"
    (root / "profiles" / "doc").mkdir(parents=True)
    (root / "profiles" / "teacher").mkdir(parents=True)
    cfg = cfg_mod.Config(home=root / "profiles" / "doc", model="x")
    cfg_mod.save(cfg)
    cfg = cfg_mod.Config(home=root / "profiles" / "teacher", model="x")
    cfg_mod.save(cfg)
    (root / "profiles" / "doc" / ".env").write_text("TELEGRAM_BOT_TOKEN=bot-shared\n")

    monkeypatch.setattr(
        data_handlers, "_resolve_home",
        lambda p: root / "profiles" / (p or "doc"),
    )
    monkeypatch.setattr(home_mod, "_ROOT", root)

    srv = host_server.Server(home=root / "profiles" / "teacher")
    data_config.register(srv)

    body = {
        "id": "r",
        "method": "host.providers.set_key",
        "params": {
            "profile": "teacher",
            "key": "TELEGRAM_BOT_TOKEN",
            "value": "bot-shared",
        },
    }
    resp = await srv._dispatch(body)
    assert "error" in resp
    assert "already used by profile 'doc'" in resp["error"]["data"]["detail"]

    body["params"]["value"] = "bot-fresh"
    resp = await srv._dispatch(body)
    assert resp["result"]["ok"] is True
