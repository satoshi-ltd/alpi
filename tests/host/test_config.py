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
async def test_voice_set_voice(tmp_path: Path, monkeypatch) -> None:
    home = _bootstrap(tmp_path)
    monkeypatch.setattr(data_handlers, "_resolve_home", lambda p: home)
    srv = host_server.Server(home=home)
    data_config.register(srv)

    set_v = {"id": "1", "method": "host.voice.set_voice",
             "params": {"profile": "default", "voice_id": "es-ES-ElviraNeural"}}
    assert (await srv._dispatch(set_v))["result"]["ok"] is True

    cfg = cfg_mod.load(home)
    assert cfg.tools.tts.voice == "es-ES-ElviraNeural"


@pytest.mark.asyncio
async def test_voice_autoplay_verb_is_unregistered(tmp_path: Path, monkeypatch) -> None:
    home = _bootstrap(tmp_path)
    monkeypatch.setattr(data_handlers, "_resolve_home", lambda p: home)
    srv = host_server.Server(home=home)
    data_config.register(srv)

    resp = await srv._dispatch({
        "id": "1", "method": "host.voice.autoplay",
        "params": {"profile": "default", "state": "on"},
    })
    assert resp["error"]["message"] == "method-not-found"


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
async def test_gmail_begin_writes_env_and_returns_auth_url(
    tmp_path: Path, monkeypatch,
) -> None:
    home = _bootstrap(tmp_path)
    monkeypatch.setattr(data_handlers, "_resolve_home", lambda p: home)
    # Strip env vars that might have leaked in from the developer's shell.
    for key in ("GMAIL_CLIENT_ID", "GMAIL_CLIENT_SECRET", "GMAIL_ALLOWED_SENDERS"):
        monkeypatch.delenv(key, raising=False)
    # Clear any pending state from a previous test.
    data_config._pending_gmail.clear()

    result = await data_config._gmail_begin(
        {
            "profile": "default",
            "client_id": "cid-123",
            "client_secret": "sec-456",
            "allowed_senders": " Bob@Example.com , carol@x.com ",
            "redirect_uri": "http://127.0.0.1:55555",
        },
        None,
    )

    env_text = (home / ".env").read_text()
    assert "GMAIL_CLIENT_ID=cid-123" in env_text
    assert "GMAIL_CLIENT_SECRET=sec-456" in env_text
    assert "GMAIL_ALLOWED_SENDERS=bob@example.com,carol@x.com" in env_text
    # No os.environ shadow: prepare reads creds from the profile's .env on demand.
    import os
    assert "GMAIL_CLIENT_ID" not in os.environ
    assert "GMAIL_CLIENT_SECRET" not in os.environ

    assert result["auth_url"].startswith("https://accounts.google.com/o/oauth2/v2/auth?")
    assert "redirect_uri=http%3A%2F%2F127.0.0.1%3A55555" in result["auth_url"]
    assert result["state"] and result["state"] in data_config._pending_gmail


@pytest.mark.asyncio
async def test_gmail_begin_missing_creds_raises(
    tmp_path: Path, monkeypatch,
) -> None:
    home = _bootstrap(tmp_path)
    monkeypatch.setattr(data_handlers, "_resolve_home", lambda p: home)
    for key in ("GMAIL_CLIENT_ID", "GMAIL_CLIENT_SECRET", "GMAIL_ALLOWED_SENDERS"):
        monkeypatch.delenv(key, raising=False)
    data_config._pending_gmail.clear()

    with pytest.raises(host_server.HandlerError) as ei:
        await data_config._gmail_begin(
            {
                "profile": "default", "client_id": "", "client_secret": "",
                "redirect_uri": "http://127.0.0.1:1",
            },
            None,
        )
    assert "required" in (ei.value.data or {}).get("detail", "")
    assert not (home / ".env").exists() or "GMAIL_CLIENT_ID" not in (home / ".env").read_text()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "bad_uri",
    [
        "https://evil.example.com/cb",          # non-http scheme
        "http://evil.example.com:80/cb",        # non-loopback host
        "http://127.0.0.1",                     # no port
        "http://127.0.0.1:0",                   # port 0
        "http://[::1]:55555",                   # IPv6 loopback not in allowlist (fine — keep strict)
        "ftp://127.0.0.1:55555",                # wrong scheme
        "127.0.0.1:55555",                      # missing scheme
    ],
)
async def test_gmail_begin_rejects_non_loopback_redirect_uri(
    bad_uri: str, tmp_path: Path, monkeypatch,
) -> None:
    home = _bootstrap(tmp_path)
    monkeypatch.setattr(data_handlers, "_resolve_home", lambda p: home)
    for key in ("GMAIL_CLIENT_ID", "GMAIL_CLIENT_SECRET", "GMAIL_ALLOWED_SENDERS"):
        monkeypatch.delenv(key, raising=False)
    data_config._pending_gmail.clear()

    with pytest.raises(host_server.HandlerError):
        await data_config._gmail_begin(
            {
                "profile": "default", "client_id": "x", "client_secret": "y",
                "redirect_uri": bad_uri,
            },
            None,
        )


@pytest.mark.asyncio
async def test_gmail_begin_accepts_localhost_loopback(
    tmp_path: Path, monkeypatch,
) -> None:
    home = _bootstrap(tmp_path)
    monkeypatch.setattr(data_handlers, "_resolve_home", lambda p: home)
    for key in ("GMAIL_CLIENT_ID", "GMAIL_CLIENT_SECRET", "GMAIL_ALLOWED_SENDERS"):
        monkeypatch.delenv(key, raising=False)
    data_config._pending_gmail.clear()

    result = await data_config._gmail_begin(
        {
            "profile": "default", "client_id": "x", "client_secret": "y",
            "redirect_uri": "http://localhost:42424",
        },
        None,
    )
    assert "redirect_uri=http%3A%2F%2Flocalhost%3A42424" in result["auth_url"]


@pytest.mark.asyncio
async def test_gmail_begin_missing_redirect_uri_raises(
    tmp_path: Path, monkeypatch,
) -> None:
    home = _bootstrap(tmp_path)
    monkeypatch.setattr(data_handlers, "_resolve_home", lambda p: home)
    for key in ("GMAIL_CLIENT_ID", "GMAIL_CLIENT_SECRET", "GMAIL_ALLOWED_SENDERS"):
        monkeypatch.delenv(key, raising=False)
    data_config._pending_gmail.clear()

    with pytest.raises(host_server.HandlerError) as ei:
        await data_config._gmail_begin(
            {"profile": "default", "client_id": "x", "client_secret": "y"},
            None,
        )
    assert "redirect_uri" in (ei.value.data or {}).get("detail", "")


@pytest.mark.asyncio
async def test_gmail_begin_reuses_stored_creds_on_blank_input(
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
    data_config._pending_gmail.clear()

    result = await data_config._gmail_begin(
        {
            "profile": "default", "client_id": "", "client_secret": "",
            "redirect_uri": "http://127.0.0.1:42",
        },
        None,
    )
    assert "client_id=stored-id" in result["auth_url"]
    env_text = (home / ".env").read_text()
    assert "GMAIL_CLIENT_ID=stored-id" in env_text
    assert "GMAIL_CLIENT_SECRET=stored-sec" in env_text


@pytest.mark.asyncio
async def test_gmail_exchange_runs_auth_exchange_with_stored_verifier(
    tmp_path: Path, monkeypatch,
) -> None:
    home = _bootstrap(tmp_path)
    monkeypatch.setattr(data_handlers, "_resolve_home", lambda p: home)
    for key in ("GMAIL_CLIENT_ID", "GMAIL_CLIENT_SECRET", "GMAIL_ALLOWED_SENDERS"):
        monkeypatch.delenv(key, raising=False)
    data_config._pending_gmail.clear()

    # First: seed a pending state via begin.
    begin = await data_config._gmail_begin(
        {
            "profile": "default", "client_id": "x", "client_secret": "y",
            "redirect_uri": "http://127.0.0.1:9999",
        },
        None,
    )
    state = begin["state"]

    fake_token = type("FakeToken", (), {"email": "alice@example.com"})()
    captured: dict = {}
    from alpi.mail import gmail_auth as ga

    def fake_exchange(h, *, code, code_verifier, redirect_uri):
        captured["home"] = h
        captured["code"] = code
        captured["code_verifier"] = code_verifier
        captured["redirect_uri"] = redirect_uri
        return fake_token

    monkeypatch.setattr(ga, "exchange", fake_exchange)

    result = await data_config._gmail_exchange(
        {"state": state, "code": "the-google-code"},
        None,
    )

    assert result == {"email": "alice@example.com"}
    assert captured["code"] == "the-google-code"
    assert captured["redirect_uri"] == "http://127.0.0.1:9999"
    assert len(captured["code_verifier"]) >= 43  # PKCE min length
    # State should be consumed exactly once.
    assert state not in data_config._pending_gmail


@pytest.mark.asyncio
async def test_gmail_exchange_unknown_state_raises(
    tmp_path: Path, monkeypatch,
) -> None:
    home = _bootstrap(tmp_path)
    monkeypatch.setattr(data_handlers, "_resolve_home", lambda p: home)
    data_config._pending_gmail.clear()

    with pytest.raises(host_server.HandlerError) as ei:
        await data_config._gmail_exchange(
            {"state": "ghost-state", "code": "irrelevant"},
            None,
        )
    assert "expired" in (ei.value.data or {}).get("detail", "")


@pytest.mark.asyncio
async def test_gmail_exchange_propagates_oauth_error(
    tmp_path: Path, monkeypatch,
) -> None:
    home = _bootstrap(tmp_path)
    monkeypatch.setattr(data_handlers, "_resolve_home", lambda p: home)
    for key in ("GMAIL_CLIENT_ID", "GMAIL_CLIENT_SECRET", "GMAIL_ALLOWED_SENDERS"):
        monkeypatch.delenv(key, raising=False)
    data_config._pending_gmail.clear()

    begin = await data_config._gmail_begin(
        {
            "profile": "default", "client_id": "x", "client_secret": "y",
            "redirect_uri": "http://127.0.0.1:42",
        },
        None,
    )
    state = begin["state"]

    from alpi.mail import gmail_auth as ga

    def boom(_h, **_kw):
        raise ga.GmailAuthError("OAuth denied: access_denied")

    monkeypatch.setattr(ga, "exchange", boom)

    with pytest.raises(host_server.HandlerError) as ei:
        await data_config._gmail_exchange(
            {"state": state, "code": "anything"},
            None,
        )
    assert "access_denied" in (ei.value.data or {}).get("detail", "")
    # State was consumed even on failure — the user must restart the flow.
    assert state not in data_config._pending_gmail


def test_gc_pending_gmail_purges_old_entries(monkeypatch) -> None:
    import time as _t
    data_config._pending_gmail.clear()
    data_config._pending_gmail["fresh"] = {
        "code_verifier": "v", "redirect_uri": "u",
        "home": Path("/x"), "created": _t.time(),
    }
    data_config._pending_gmail["stale"] = {
        "code_verifier": "v", "redirect_uri": "u",
        "home": Path("/x"), "created": _t.time() - data_config._GMAIL_BEGIN_TTL - 1,
    }
    data_config._gc_pending_gmail()
    assert "fresh" in data_config._pending_gmail
    assert "stale" not in data_config._pending_gmail


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


@pytest.mark.asyncio
async def test_mutators_emit_config_changed(tmp_path: Path, monkeypatch) -> None:
    """Every cfg.save in alpi/host/config.py is paired with an emit so remote clients can react without polling. Tests one mutator per scope to keep the surface small."""
    from alpi.host import events as host_events

    home = _bootstrap(tmp_path)
    monkeypatch.setattr(data_handlers, "_resolve_home", lambda p: home)
    srv = host_server.Server(home=home)
    data_config.register(srv)

    captured: list[tuple[str, dict]] = []
    monkeypatch.setattr(
        host_events, "emit",
        lambda kind, data=None: captured.append((kind, data or {})),
    )

    cases = [
        ("host.providers.add_ollama",
         {"profile": "default", "name": "local", "url": "http://x:11434"},
         "providers"),
        ("host.mcp.add",
         {"profile": "default", "name": "fs", "command": "ls", "args": []},
         "mcp"),
        ("host.sandbox.set",
         {"profile": "default", "state": "on"}, "sandbox"),
        ("host.voice.set_voice",
         {"profile": "default", "voice_id": "en-US-AndrewMultilingualNeural"},
         "voice"),
    ]
    for method, params, scope in cases:
        captured.clear()
        resp = await srv._dispatch({
            "id": "r", "method": method, "params": params,
        })
        assert resp.get("result", {}).get("ok") is True, resp
        assert any(
            k == "config_changed" and d.get("scope") == scope
            for k, d in captured
        ), f"no config_changed/{scope} after {method}; got {captured!r}"


@pytest.mark.asyncio
async def test_gateway_remove_emits_gateway_changed(
    tmp_path: Path, monkeypatch,
) -> None:
    from alpi.host import events as host_events

    home = _bootstrap(tmp_path)
    monkeypatch.setattr(data_handlers, "_resolve_home", lambda p: home)
    (home / ".env").write_text(
        "TELEGRAM_BOT_TOKEN=secret\nTELEGRAM_ALLOWED_CHAT_IDS=1\n",
    )
    srv = host_server.Server(home=home)
    data_config.register(srv)

    captured: list[tuple[str, dict]] = []
    monkeypatch.setattr(
        host_events, "emit",
        lambda kind, data=None: captured.append((kind, data or {})),
    )

    resp = await srv._dispatch({
        "id": "r", "method": "host.gateway.remove",
        "params": {"profile": "default", "name": "telegram"},
    })
    assert resp["result"]["ok"] is True
    assert ("gateway_changed", {
        "profile": "default", "name": "telegram", "action": "removed",
    }) in captured


@pytest.mark.asyncio
async def test_set_gateway_key_emits_gateway_changed_not_config(
    tmp_path: Path, monkeypatch,
) -> None:
    """Routing matters: a TELEGRAM_BOT_TOKEN rewrite is gateway-shaped (brings a poller online), not generic env. Clients refresh different surfaces on each."""
    from alpi.host import events as host_events

    home = _bootstrap(tmp_path)
    monkeypatch.setattr(data_handlers, "_resolve_home", lambda p: home)
    srv = host_server.Server(home=home)
    data_config.register(srv)

    captured: list[tuple[str, dict]] = []
    monkeypatch.setattr(
        host_events, "emit",
        lambda kind, data=None: captured.append((kind, data or {})),
    )

    resp = await srv._dispatch({
        "id": "r", "method": "host.providers.set_key",
        "params": {
            "profile": "default", "key": "TELEGRAM_BOT_TOKEN", "value": "v",
        },
    })
    assert resp["result"]["ok"] is True
    kinds = {k for k, _ in captured}
    assert "gateway_changed" in kinds
    assert "config_changed" not in kinds
