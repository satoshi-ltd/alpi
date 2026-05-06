"""Device-facing host-plane state verbs."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from alpi import config as cfg_mod
from alpi.alp.keys import load_or_generate
from alpi.host import device_state as host_device_state
from alpi.host import handlers as host_handlers
from alpi.host import server as host_server


def _bootstrap(home: Path) -> Path:
    home.mkdir()
    cfg = cfg_mod.Config(home=home, model="openai/gpt-5.4-mini")
    cfg.workspace = "/tmp/work"
    cfg.public_bio = "desktop test profile"
    cfg.providers = {
        "ollama": [{"name": "local", "url": "http://127.0.0.1:11434"}],
        "openrouter": {"models": ["openai/gpt-5.4-mini"]},
    }
    cfg_mod.save(cfg)
    (home / ".env").write_text("OPENAI_API_KEY=sk-test\nTELEGRAM_BOT_TOKEN=tg-secret\n")
    (home / "memories").mkdir()
    (home / "memories" / "USER.md").write_text("hello\n")
    (home / "sessions").mkdir()
    (home / "sessions" / "abc.json").write_text(json.dumps({
        "started_at": 1.0,
        "model": "openai/gpt-5.4-mini",
        "turns": [{"user": "hi"}],
        "input_tokens": 10,
        "output_tokens": 20,
        "cost_usd": 0.03,
    }))
    (home / "sessions" / "zzz.json").write_text(json.dumps({
        "started_at": 2.0,
        "model": "openai/gpt-5.4-mini",
        "turns": [{"user": "[workgroup-poller] keep going"}],
    }))
    (home / "skills" / "demo").mkdir(parents=True)
    (home / "skills" / "demo" / "SKILL.md").write_text(
        "---\ndescription: Demo skill\n---\n",
    )
    load_or_generate(home)
    return home


@pytest.mark.asyncio
async def test_device_profile_summaries_are_served_by_host(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    home = _bootstrap(tmp_path / "h")
    monkeypatch.setattr(host_device_state.home_mod, "_ROOT", home)
    monkeypatch.setattr(host_handlers, "_resolve_home", lambda profile: home)

    srv = host_server.Server(home=home)
    host_device_state.register(srv)
    resp = await srv._dispatch({
        "id": "r",
        "method": "host.profile.summaries",
        "params": {},
    })

    profile = resp["result"]["profiles"][0]
    assert profile["name"] == "default"
    assert profile["model"] == "openai/gpt-5.4-mini"
    assert profile["workspace"] == "/tmp/work"
    assert profile["latest_session"]["id"] == "abc"
    assert profile["latest_session"]["kind"] == "chat"
    assert profile["counts"]["sessions"] == 2
    assert profile["counts"]["skills"] == 1
    assert profile["provider_keys"][0]["env"] == "OPENAI_API_KEY"
    assert profile["pubkey_b64"]


@pytest.mark.asyncio
async def test_device_read_file_rejects_escape(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    home = _bootstrap(tmp_path / "h")
    monkeypatch.setattr(host_handlers, "_resolve_home", lambda profile: home)
    srv = host_server.Server(home=home)
    host_device_state.register(srv)

    ok = await srv._dispatch({
        "id": "ok",
        "method": "host.profile.read_file",
        "params": {"profile": "default", "rel_path": "memories/USER.md"},
    })
    assert ok["result"]["text"] == "hello\n"

    bad = await srv._dispatch({
        "id": "bad",
        "method": "host.profile.read_file",
        "params": {"profile": "default", "rel_path": "../outside.txt"},
    })
    assert bad["error"]["code"] == -32004


@pytest.mark.asyncio
async def test_device_config_field_mutations_go_through_host(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    home = _bootstrap(tmp_path / "h")
    monkeypatch.setattr(host_handlers, "_resolve_home", lambda profile: home)
    srv = host_server.Server(home=home)
    host_device_state.register(srv)

    set_resp = await srv._dispatch({
        "id": "set",
        "method": "host.config.set_field",
        "params": {"profile": "default", "key": "alp.tcp_port", "value": "4242"},
    })
    assert set_resp["result"]["ok"] is True
    assert cfg_mod.load(home).alp["tcp_port"] == 4242

    unset_resp = await srv._dispatch({
        "id": "unset",
        "method": "host.config.unset_field",
        "params": {"profile": "default", "key": "alp.tcp_port"},
    })
    assert unset_resp["result"]["ok"] is True
    assert "tcp_port" not in cfg_mod.load(home).alp

    host_set = await srv._dispatch({
        "id": "host-set",
        "method": "host.config.set_field",
        "params": {"profile": "default", "key": "host.tcp_port", "value": "49200"},
    })
    assert host_set["result"]["ok"] is True
    assert cfg_mod.load(home).host["tcp_port"] == 49200


@pytest.mark.asyncio
async def test_device_gateway_and_skills_views(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    home = _bootstrap(tmp_path / "h")
    monkeypatch.setattr(host_handlers, "_resolve_home", lambda profile: home)
    srv = host_server.Server(home=home)
    host_device_state.register(srv)

    status = await srv._dispatch({
        "id": "gateways",
        "method": "host.gateway.status",
        "params": {"profile": "default"},
    })
    assert {"name": "telegram", "configured": True} in status["result"]["gateways"]

    config = await srv._dispatch({
        "id": "gateway-config",
        "method": "host.gateway.config",
        "params": {"profile": "default", "name": "telegram"},
    })
    assert config["result"]["config"]["TELEGRAM_BOT_TOKEN"].startswith("tg-")

    skills = await srv._dispatch({
        "id": "skills",
        "method": "host.skills.list",
        "params": {"profile": "default"},
    })
    assert skills["result"]["skills"] == [{
        "category": None,
        "name": "demo",
        "description": "Demo skill",
    }]
