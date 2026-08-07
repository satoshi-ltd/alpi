"""Device-facing host-plane state verbs."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from alpi import __version__ as alpi_version
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
    (home / ".env").write_text("OPENAI_API_KEY=sk-test\n")
    from alpi.mail import accounts as accounts_mod
    accounts_mod.add_imap(
        home, address="me@x.com", password="pw-secret",
        imap_host="imap.x.com", smtp_host="smtp.x.com",
    )
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
async def test_host_version_returns_alpi_runtime(tmp_path: Path) -> None:
    srv = host_server.Server(home=tmp_path)
    host_device_state.register(srv)
    resp = await srv._dispatch({
        "id": "v",
        "method": "host.version",
        "params": {},
    })
    assert resp["result"]["agent_name"] == "alpi"
    assert resp["result"]["version"] == alpi_version
    assert "device_name" in resp["result"]
    assert "device_id" in resp["result"]


@pytest.mark.asyncio
async def test_host_version_reports_member_for_an_invalid_presented_token(
    monkeypatch, tmp_path: Path,
) -> None:
    from alpi.host import connections

    monkeypatch.setattr(host_device_state.home_mod, "_ROOT", tmp_path)
    connections.invalidate_cache()
    srv = host_server.Server(home=tmp_path)
    host_device_state.register(srv)

    resp = await srv._dispatch({
        "id": "v",
        "method": "host.version",
        "params": {"auth_token": "invalid-token"},
    })

    assert resp["result"]["role"] == "member"


@pytest.mark.asyncio
async def test_host_version_device_id_is_stable_across_calls(tmp_path: Path) -> None:
    srv = host_server.Server(home=tmp_path)
    host_device_state.register(srv)

    first = await srv._dispatch({"id": "v1", "method": "host.version", "params": {}})
    second = await srv._dispatch({"id": "v2", "method": "host.version", "params": {}})

    assert first["result"]["device_id"]
    assert first["result"]["device_id"] == second["result"]["device_id"]
    persisted = (tmp_path / "host" / "device_id").read_text(encoding="utf-8").strip()
    assert persisted == first["result"]["device_id"]


@pytest.mark.asyncio
async def test_host_version_device_id_survives_restart(tmp_path: Path) -> None:
    (tmp_path / "host").mkdir(parents=True, exist_ok=True)
    (tmp_path / "host" / "device_id").write_text("preexisting-id-42", encoding="utf-8")

    srv = host_server.Server(home=tmp_path)
    host_device_state.register(srv)
    resp = await srv._dispatch({"id": "v", "method": "host.version", "params": {}})

    assert resp["result"]["device_id"] == "preexisting-id-42"


@pytest.mark.asyncio
async def test_host_version_device_id_is_atomic_under_concurrent_first_call(tmp_path: Path) -> None:
    """Two clients hitting host.version at the same first-call moment must agree on one device_id. O_EXCL create means the loser's open raises FileExistsError and it re-reads the winner's value, instead of overwriting it."""
    import asyncio

    srv = host_server.Server(home=tmp_path)
    host_device_state.register(srv)

    results = await asyncio.gather(*[
        srv._dispatch({"id": f"v{i}", "method": "host.version", "params": {}})
        for i in range(8)
    ])
    ids = {r["result"]["device_id"] for r in results}
    assert len(ids) == 1, f"concurrent first-call minted {len(ids)} distinct ids: {ids}"
    persisted = (tmp_path / "host" / "device_id").read_text(encoding="utf-8").strip()
    assert persisted == next(iter(ids))


@pytest.mark.asyncio
async def test_host_version_device_id_is_per_home_so_two_daemons_get_distinct_ids(tmp_path: Path) -> None:
    home_a = tmp_path / "a"
    home_b = tmp_path / "b"
    home_a.mkdir()
    home_b.mkdir()

    srv_a = host_server.Server(home=home_a)
    host_device_state.register(srv_a)
    srv_b = host_server.Server(home=home_b)
    host_device_state.register(srv_b)

    a = await srv_a._dispatch({"id": "va", "method": "host.version", "params": {}})
    b = await srv_b._dispatch({"id": "vb", "method": "host.version", "params": {}})

    assert a["result"]["device_id"]
    assert b["result"]["device_id"]
    assert a["result"]["device_id"] != b["result"]["device_id"]


@pytest.mark.asyncio
async def test_host_version_surfaces_device_name_from_config(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    home = tmp_path / "h"
    home.mkdir()
    (home / "config.yaml").write_text(
        "host:\n  device_name: Macbook.Pro\n  tcp_host: 100.64.0.1\n",
    )
    monkeypatch.setattr("alpi.home.get_home", lambda: home)
    srv = host_server.Server(home=home)
    host_device_state.register(srv)
    resp = await srv._dispatch({
        "id": "v",
        "method": "host.version",
        "params": {},
    })
    assert resp["result"]["device_name"] == "Macbook.Pro"


@pytest.mark.asyncio
async def test_host_version_blank_device_name_when_unset(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    home = tmp_path / "h"
    home.mkdir()
    (home / "config.yaml").write_text("host:\n  tcp_host: 100.64.0.1\n")
    monkeypatch.setattr("alpi.home.get_home", lambda: home)
    srv = host_server.Server(home=home)
    host_device_state.register(srv)
    resp = await srv._dispatch({
        "id": "v",
        "method": "host.version",
        "params": {},
    })
    assert resp["result"]["device_name"] == ""


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
    assert profile["latest_session"]["id"] == "abc"
    assert profile["latest_session"]["kind"] == "chat"
    assert profile["counts"]["sessions"] == 2
    assert profile["counts"]["skills"] == 1
    assert profile["pubkey_b64"]
    # The lightweight summary must NOT carry the heavy fields anymore — those moved to host.profile.detail.
    assert "provider_keys" not in profile
    assert "peers" not in profile
    assert "models" not in profile
    assert "mcps" not in profile
    assert "subsystems" not in profile

    detail = await srv._dispatch({
        "id": "d",
        "method": "host.profile.detail",
        "params": {"profile": "default"},
    })
    detail_payload = detail["result"]
    assert "voice_id" in profile
    assert profile["voice_id"] == detail_payload["voice_id"]
    assert detail_payload["workspace"] == "/tmp/work"
    assert detail_payload["provider_keys"][0]["env"] == "OPENAI_API_KEY"
    assert "peers" in detail_payload
    assert "mcps" in detail_payload
    assert "models" in detail_payload


def test_daemon_running_uses_os_signal_not_external_kill(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    import subprocess

    home = tmp_path / "h"
    home.mkdir()
    (home / "service.pid").write_text("123\n")
    monkeypatch.setattr(host_device_state.home_mod, "_ROOT", home)
    calls = []

    def fake_kill(pid: int, sig: int) -> None:
        calls.append((pid, sig))

    monkeypatch.setattr(host_device_state.os, "kill", fake_kill)
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *_args, **_kwargs: pytest.fail("subprocess.run should not be used"),
    )

    assert host_device_state._daemon_running() is True
    assert calls == [(123, 0)]


def test_daemon_running_reads_new_pidfile_format(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Pidfile is "<pid> <starttime>" — int(strip()) would choke on the space.
    from alpi import service
    home = tmp_path / "h"
    home.mkdir()
    (home / "service.pid").write_text("123 99999999\n")
    monkeypatch.setattr(host_device_state.home_mod, "_ROOT", home)
    monkeypatch.setattr(host_device_state.os, "kill", lambda *_a, **_k: None)
    monkeypatch.setattr(service, "_proc_starttime", lambda pid: "99999999")
    assert host_device_state._daemon_pid() == 123
    assert host_device_state._daemon_running() is True


def test_models_hides_entries_of_providers_without_keys(tmp_path: Path) -> None:
    home = tmp_path / "h"
    home.mkdir()
    cfg = cfg_mod.Config(home=home, model="anthropic/claude-sonnet-4-6")
    cfg.providers = {"openrouter": {"models": ["meta/llama-3"]}}
    (home / ".env").write_text("OPENAI_API_KEY=sk-test\n")

    models = host_device_state._models(cfg, home)
    assert "anthropic/claude-sonnet-4-6" not in models
    assert "openrouter/meta/llama-3" not in models
    assert any(m.startswith("openai/") for m in models)


def test_models_lists_entries_when_provider_keys_present(tmp_path: Path) -> None:
    home = tmp_path / "h"
    home.mkdir()
    cfg = cfg_mod.Config(home=home, model="anthropic/claude-sonnet-4-6")
    cfg.providers = {"openrouter": {"models": ["meta/llama-3"]}}
    (home / ".env").write_text(
        "ANTHROPIC_API_KEY=sk-a\nOPENROUTER_API_KEY=sk-or\n",
    )

    models = host_device_state._models(cfg, home)
    assert models[0] == "anthropic/claude-sonnet-4-6"
    assert "openrouter/meta/llama-3" in models


def test_models_keeps_ollama_selected_model_without_any_key(tmp_path: Path) -> None:
    home = tmp_path / "h"
    home.mkdir()
    cfg = cfg_mod.Config(home=home, model="local/llama3:8b")
    assert host_device_state._models(cfg, home) == ["local/llama3:8b"]


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
    assert bad["error"]["code"] == -32001


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

    # No half-written tmp left behind by the atomic writer.
    cfg_path = home / "config.yaml"
    assert not cfg_path.with_suffix(cfg_path.suffix + ".tmp").exists()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("method", "key"),
    [
        ("host.config.set_field", "service.schedule"),
        ("host.config.unset_field", "service"),
    ],
)
async def test_config_verbs_reject_removed_service_switches(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, method: str, key: str,
) -> None:
    home = _bootstrap(tmp_path / "h")
    monkeypatch.setattr(host_handlers, "_resolve_home", lambda profile: home)
    srv = host_server.Server(home=home)
    host_device_state.register(srv)

    response = await srv._dispatch({
        "id": "removed",
        "method": method,
        "params": {"profile": "default", "key": key, "value": "false"},
    })

    assert response["error"]["code"] == -32602
    assert "always available" in response["error"]["data"]["detail"]
    assert "service" not in cfg_mod.load(home).raw


@pytest.mark.asyncio
async def test_config_set_rejects_host_endpoints_but_unset_can_repair_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    home = _bootstrap(tmp_path / "h")
    cfg = cfg_mod.load(home)
    cfg.host = {"endpoints": "wss://client.example.com"}
    cfg_mod.save(cfg)
    monkeypatch.setattr(host_handlers, "_resolve_home", lambda profile: home)
    srv = host_server.Server(home=home)
    host_device_state.register(srv)

    rejected = await srv._dispatch({
        "id": "set",
        "method": "host.config.set_field",
        "params": {
            "profile": "default",
            "key": "host.endpoints",
            "value": "[]",
        },
    })
    assert rejected["error"]["code"] == -32602
    assert "host.network.set_advertised" in rejected["error"]["data"]["detail"]

    repaired = await srv._dispatch({
        "id": "unset",
        "method": "host.config.unset_field",
        "params": {"profile": "default", "key": "host.endpoints"},
    })
    assert repaired["result"]["ok"] is True
    assert "endpoints" not in cfg_mod.load(home).host


@pytest.mark.asyncio
async def test_reasoning_effort_set_and_auto_clear_on_model_swap(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """host.config.set_field model_reasoning.effort validates + persists; switching `model` to an unsupported one auto-clears the effort so a stale value can't survive."""
    home = _bootstrap(tmp_path / "h")
    monkeypatch.setattr(host_handlers, "_resolve_home", lambda profile: home)
    srv = host_server.Server(home=home)
    host_device_state.register(srv)

    # Land on a reasoning model first.
    await srv._dispatch({
        "id": "set-model",
        "method": "host.config.set_field",
        "params": {"profile": "default", "key": "model", "value": "openai/o3-mini"},
    })
    set_effort = await srv._dispatch({
        "id": "set-eff",
        "method": "host.config.set_field",
        "params": {"profile": "default", "key": "model_reasoning.effort", "value": "high"},
    })
    assert set_effort["result"]["ok"] is True
    assert cfg_mod.load(home).model_reasoning.effort == "high"

    # Invalid effort is dropped, not stored as garbage.
    await srv._dispatch({
        "id": "bad-eff",
        "method": "host.config.set_field",
        "params": {"profile": "default", "key": "model_reasoning.effort", "value": "wibble"},
    })
    assert cfg_mod.load(home).model_reasoning.effort == ""

    # Set effort again, then switch to a non-reasoning model — effort must auto-clear.
    await srv._dispatch({
        "id": "set-eff-2",
        "method": "host.config.set_field",
        "params": {"profile": "default", "key": "model_reasoning.effort", "value": "medium"},
    })
    assert cfg_mod.load(home).model_reasoning.effort == "medium"

    await srv._dispatch({
        "id": "swap-model",
        "method": "host.config.set_field",
        "params": {"profile": "default", "key": "model", "value": "openai/gpt-4o"},
    })
    reloaded = cfg_mod.load(home)
    assert reloaded.model == "openai/gpt-4o"
    assert reloaded.model_reasoning.effort == ""


@pytest.mark.asyncio
async def test_reasoning_effort_rejected_when_current_model_unsupported(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """profile.detail would report effort=high + supported=false otherwise; the host RPC refuses to persist effort on a model that can't use it."""
    home = _bootstrap(tmp_path / "h")
    monkeypatch.setattr(host_handlers, "_resolve_home", lambda profile: home)
    srv = host_server.Server(home=home)
    host_device_state.register(srv)

    # Land on a model that genuinely doesn't support reasoning (gpt-4o-mini stays out of the catalog and out of the regex fallback).
    await srv._dispatch({
        "id": "to-nonreasoning",
        "method": "host.config.set_field",
        "params": {"profile": "default", "key": "model", "value": "openai/gpt-4o-mini"},
    })

    resp = await srv._dispatch({
        "id": "set-eff",
        "method": "host.config.set_field",
        "params": {"profile": "default", "key": "model_reasoning.effort", "value": "high"},
    })
    assert resp["result"]["ok"] is True
    assert cfg_mod.load(home).model_reasoning.effort == ""

    # Now switch to a reasoning model, then setting effort works.
    await srv._dispatch({
        "id": "swap-model",
        "method": "host.config.set_field",
        "params": {"profile": "default", "key": "model", "value": "openai/o3-mini"},
    })
    await srv._dispatch({
        "id": "set-eff-2",
        "method": "host.config.set_field",
        "params": {"profile": "default", "key": "model_reasoning.effort", "value": "high"},
    })
    assert cfg_mod.load(home).model_reasoning.effort == "high"


@pytest.mark.asyncio
async def test_profile_detail_exposes_reasoning_state(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    home = _bootstrap(tmp_path / "h")
    cfg = cfg_mod.load(home)
    cfg.model = "openai/o3-mini"
    cfg.model_reasoning.effort = "high"
    cfg_mod.save(cfg)

    monkeypatch.setattr(host_handlers, "_resolve_home", lambda profile: home)
    srv = host_server.Server(home=home)
    host_device_state.register(srv)

    resp = await srv._dispatch({
        "id": "detail",
        "method": "host.profile.detail",
        "params": {"profile": "default"},
    })
    detail = resp["result"]
    assert detail["model_reasoning_effort"] == "high"
    assert detail["model_reasoning_supported"] is True


@pytest.mark.asyncio
async def test_profile_detail_reports_unsupported_for_non_reasoning_model(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    home = _bootstrap(tmp_path / "h")
    cfg = cfg_mod.load(home)
    cfg.model = "openai/gpt-4o"
    cfg_mod.save(cfg)

    monkeypatch.setattr(host_handlers, "_resolve_home", lambda profile: home)
    srv = host_server.Server(home=home)
    host_device_state.register(srv)

    resp = await srv._dispatch({
        "id": "detail",
        "method": "host.profile.detail",
        "params": {"profile": "default"},
    })
    detail = resp["result"]
    assert detail["model_reasoning_supported"] is False
    assert detail["model_reasoning_effort"] == ""


@pytest.mark.asyncio
async def test_config_set_field_emits_config_changed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Without an emit, desktop/mobile would never know a dotted-key edit landed and the UI would lag behind reality until the next manual reload."""
    from alpi.host import events as host_events

    home = _bootstrap(tmp_path / "h")
    monkeypatch.setattr(host_handlers, "_resolve_home", lambda profile: home)
    srv = host_server.Server(home=home)
    host_device_state.register(srv)

    captured: list[tuple[str, dict]] = []
    monkeypatch.setattr(
        host_events, "emit",
        lambda kind, data=None: captured.append((kind, data or {})),
    )

    await srv._dispatch({
        "id": "set",
        "method": "host.config.set_field",
        "params": {"profile": "default", "key": "alp.tcp_port", "value": "4242"},
    })
    await srv._dispatch({
        "id": "unset",
        "method": "host.config.unset_field",
        "params": {"profile": "default", "key": "alp.tcp_port"},
    })

    kinds = [k for k, _ in captured]
    assert kinds.count("config_changed") == 2
    assert {d["scope"] for k, d in captured if k == "config_changed"} == {"alp"}


@pytest.mark.asyncio
async def test_device_gateway_and_skills_views(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    home = _bootstrap(tmp_path / "h")
    monkeypatch.setattr(host_handlers, "_resolve_home", lambda profile: home)
    srv = host_server.Server(home=home)
    host_device_state.register(srv)

    status = await srv._dispatch({
        "id": "accounts",
        "method": "host.email.status",
        "params": {"profile": "default"},
    })
    assert {"id": "me_x_com", "type": "imap", "address": "me@x.com",
            "configured": True} in status["result"]["accounts"]

    config = await srv._dispatch({
        "id": "email-config",
        "method": "host.email.config",
        "params": {"profile": "default", "id": "me_x_com"},
    })
    assert config["result"]["config"]["address"] == "me@x.com"
    assert config["result"]["config"]["imap_host"] == "imap.x.com"
    assert config["result"]["config"]["password_set"] is True

    skills = await srv._dispatch({
        "id": "skills",
        "method": "host.skills.list",
        "params": {"profile": "default"},
    })
    rows = skills["result"]["skills"]
    assert len(rows) == 1
    row = rows[0]
    assert row["category"] is None
    assert row["name"] == "demo"
    assert row["description"] == "Demo skill"
    assert "path" in row
    # Default listing must NOT carry the SKILL.md body — saves ~32KB/skill on the wire.
    assert "body" not in row

    # Detail path returns the body on demand (empty here — fixture has only frontmatter).
    detail = await srv._dispatch({
        "id": "skill-read",
        "method": "host.skill.read",
        "params": {"profile": "default", "name": "demo"},
    })
    assert "body" in detail["result"]["skill"]
    assert detail["result"]["skill"]["description"] == "Demo skill"

    # Opt-in legacy: clients that explicitly request bodies still get them.
    legacy = await srv._dispatch({
        "id": "skills-with-body",
        "method": "host.skills.list",
        "params": {"profile": "default", "include_body": True},
    })
    assert "body" in legacy["result"]["skills"][0]


@pytest.mark.asyncio
async def test_profile_summaries_does_not_block_loop(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A slow _profile_summary (e.g. a profile whose ledger.json is on a stale NFS mount) must not freeze every other coroutine on the host loop. Same root cause as scheduler.serve()'s old inline tick."""
    import asyncio
    import time as _time

    home = _bootstrap(tmp_path / "h")
    monkeypatch.setattr(host_device_state.home_mod, "_ROOT", home)
    monkeypatch.setattr(host_handlers, "_resolve_home", lambda profile: home)
    block_s = 0.4

    def slow_summary(row):
        _time.sleep(block_s)
        return {**row, "blocked": True}

    monkeypatch.setattr(host_device_state, "_profile_summary", slow_summary)

    srv = host_server.Server(home=home)
    host_device_state.register(srv)

    counter = {"wakes": 0}

    async def heartbeat(stop: asyncio.Event) -> None:
        while not stop.is_set():
            await asyncio.sleep(0.05)
            counter["wakes"] += 1

    stop = asyncio.Event()
    hb_task = asyncio.create_task(heartbeat(stop))

    dispatch_task = asyncio.create_task(srv._dispatch({
        "id": "r", "method": "host.profile.summaries", "params": {},
    }))
    resp = await asyncio.wait_for(dispatch_task, timeout=block_s + 2.0)
    stop.set()
    try:
        await hb_task
    except (asyncio.CancelledError, Exception):  # noqa: BLE001
        pass

    assert resp["result"]["profiles"][0]["blocked"] is True
    assert counter["wakes"] >= 3, (
        f"host loop starved during host.profile.summaries — only {counter['wakes']} "
        "heartbeats fired while _profile_summary blocked; handler must run it in a thread"
    )


@pytest.mark.asyncio
async def test_profile_summaries_cache_collapses_repeat_polls(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    home = _bootstrap(tmp_path / "h")
    monkeypatch.setattr(host_device_state.home_mod, "_ROOT", home)
    host_device_state.invalidate_summary()

    calls = {"n": 0}
    real = host_device_state._profile_summary

    def counting(row):
        calls["n"] += 1
        return real(row)

    monkeypatch.setattr(host_device_state, "_profile_summary", counting)

    srv = host_server.Server(home=home)
    host_device_state.register(srv)

    async def summaries():
        return await srv._dispatch(
            {"id": "s", "method": "host.profile.summaries", "params": {}},
        )

    r1 = await summaries()
    n_profiles = len(r1["result"]["profiles"])
    assert n_profiles >= 1
    r2 = await summaries()
    assert calls["n"] == n_profiles, "second poll re-walked profiles instead of serving cache"
    assert r2["result"]["profiles"] == r1["result"]["profiles"]

    host_device_state.invalidate_summary()
    await summaries()
    assert calls["n"] == 2 * n_profiles, "clearing the cache must force a fresh walk"


@pytest.mark.asyncio
async def test_profile_storage_lists_all_known_categories(
    tmp_path: Path, monkeypatch,
) -> None:
    home = _bootstrap(tmp_path / "h")
    # Seed a representative file under each storage scope so file_count > 0 and the row is non-trivial.
    (home / "knowledge.sqlite").write_bytes(b"\x00" * 16)
    (home / "outputs").mkdir(parents=True)
    (home / "outputs" / "outputs.jsonl").write_text("{}\n")
    (home / "logs").mkdir(parents=True)
    (home / "logs" / "service.log").write_text("seed\n")
    (home / "cache" / "tts").mkdir(parents=True)
    (home / "cache" / "tts" / "blob.bin").write_bytes(b"abc")
    (home / "schedule" / "output").mkdir(parents=True)
    (home / "schedule" / "output" / "job.log").write_text("ok\n")
    (home / "alp" / "workgroups").mkdir(parents=True)
    (home / "mentions").mkdir(parents=True)
    (home / "mentions" / "peer-a.json").write_text("{}")
    (home / "out").mkdir(parents=True, exist_ok=True)
    (home / "out" / "chart.png").write_bytes(b"\x89PNG generated")
    stage = home / "host" / "attachments" / "tmp" / "abc"
    stage.mkdir(parents=True)
    (stage / "scan.pdf").write_bytes(b"%PDF staged")

    monkeypatch.setattr(host_handlers, "_resolve_home", lambda p: home)
    srv = host_server.Server(home=home)
    host_device_state.register(srv)

    resp = await srv._dispatch({
        "id": "r", "method": "host.profile.storage",
        "params": {"profile": "default"},
    })
    keys = {row["key"] for row in resp["result"]["storage"]}
    assert keys == {
        "sessions", "skills", "memories", "knowledge", "outputs", "generated",
        "audio", "logs", "schedule", "workgroups", "mentions", "attachments",
    }
    by_key = {row["key"]: row for row in resp["result"]["storage"]}
    assert by_key["skills"]["file_count"] > 0, "skills row should pick up SKILL.md"
    assert by_key["memories"]["file_count"] > 0, "memories row should pick up USER.md"
    assert by_key["knowledge"]["file_count"] > 0, "knowledge row should pick up knowledge.sqlite"
    assert by_key["outputs"]["file_count"] > 0, "outputs row should pick up outputs.jsonl"
    assert by_key["generated"]["file_count"] > 0, "generated row should pick up out/ files"
    assert by_key["attachments"]["file_count"] > 0, "attachments row should pick up staged uploads"

@pytest.fixture(autouse=True)
def _fresh_storage_cache():
    host_device_state._clear_storage_cache()
    yield
    host_device_state._clear_storage_cache()


@pytest.mark.asyncio
async def test_profile_storage_serves_cached_rows_within_ttl(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    home = _bootstrap(tmp_path / "h")
    monkeypatch.setattr(host_handlers, "_resolve_home", lambda p: home)
    calls = {"n": 0}
    real_rows = host_device_state._storage_rows

    def counting(home_arg):
        calls["n"] += 1
        return real_rows(home_arg)

    monkeypatch.setattr(host_device_state, "_storage_rows", counting)
    srv = host_server.Server(home=home)
    host_device_state.register(srv)

    body = {"id": "s", "method": "host.profile.storage", "params": {"profile": "default"}}
    first = await srv._dispatch(dict(body))
    second = await srv._dispatch(dict(body))
    assert calls["n"] == 1
    assert first["result"] == second["result"]


@pytest.mark.asyncio
async def test_cleanup_apply_invalidates_storage_cache(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    home = _bootstrap(tmp_path / "h")
    (home / "cache" / "tts").mkdir(parents=True)
    (home / "cache" / "tts" / "blob.mp3").write_bytes(b"x" * 128)
    monkeypatch.setattr(host_handlers, "_resolve_home", lambda p: home)
    srv = host_server.Server(home=home)
    host_device_state.register(srv)

    await srv._dispatch({"id": "1", "method": "host.profile.storage", "params": {"profile": "default"}})
    assert host_device_state._storage_cache

    resp = await srv._dispatch({
        "id": "2", "method": "host.cleanup.apply",
        "params": {"profile": "default", "keys": ["tts"]},
    })
    assert any(r["removed"] for r in resp["result"]["results"])
    assert host_device_state._storage_cache == {}


@pytest.mark.asyncio
async def test_profile_storage_cache_expires_after_ttl(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    home = _bootstrap(tmp_path / "h")
    monkeypatch.setattr(host_handlers, "_resolve_home", lambda p: home)
    monkeypatch.setattr(host_device_state, "_STORAGE_TTL_S", 0.0)
    calls = {"n": 0}
    real_rows = host_device_state._storage_rows

    def counting(home_arg):
        calls["n"] += 1
        return real_rows(home_arg)

    monkeypatch.setattr(host_device_state, "_storage_rows", counting)
    srv = host_server.Server(home=home)
    host_device_state.register(srv)

    body = {"id": "s", "method": "host.profile.storage", "params": {"profile": "default"}}
    await srv._dispatch(dict(body))
    await srv._dispatch(dict(body))
    assert calls["n"] == 2


@pytest.mark.asyncio
async def test_profile_storage_cached_rows_are_copies(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    home = _bootstrap(tmp_path / "h")
    monkeypatch.setattr(host_handlers, "_resolve_home", lambda p: home)
    srv = host_server.Server(home=home)
    host_device_state.register(srv)

    body = {"id": "s", "method": "host.profile.storage", "params": {"profile": "default"}}
    first = await srv._dispatch(dict(body))
    first["result"]["storage"][0]["size_bytes"] = -999
    second = await srv._dispatch(dict(body))
    assert second["result"]["storage"][0]["size_bytes"] != -999


@pytest.mark.asyncio
async def test_ollama_models_runs_off_the_event_loop(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    import asyncio as _asyncio
    home = _bootstrap(tmp_path / "h")
    monkeypatch.setattr(host_handlers, "_resolve_home", lambda p: home)
    monkeypatch.setattr(
        host_device_state, "_poll_ollama_models",
        lambda h: {"models": [], "errors": []},
    )
    seen: list[str] = []
    real = _asyncio.to_thread

    async def spy(fn, *args, **kwargs):
        seen.append(getattr(fn, "__name__", ""))
        return await real(fn, *args, **kwargs)

    monkeypatch.setattr(host_device_state.asyncio, "to_thread", spy)
    srv = host_server.Server(home=home)
    host_device_state.register(srv)
    resp = await srv._dispatch({
        "id": "om", "method": "host.providers.ollama_models",
        "params": {"profile": "default"},
    })
    assert resp["result"] == {"models": [], "errors": []}
    assert "<lambda>" in seen


@pytest.mark.asyncio
async def test_tier_config_set_field_validates_and_prunes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    home = _bootstrap(tmp_path / "h")
    monkeypatch.setattr(host_handlers, "_resolve_home", lambda profile: home)
    srv = host_server.Server(home=home)
    host_device_state.register(srv)

    async def _set(key, value):
        resp = await srv._dispatch({
            "id": f"t-{key}-{value}",
            "method": "host.config.set_field",
            "params": {"profile": "default", "key": key, "value": value},
        })
        assert resp["result"]["ok"] is True

    await _set("tiers.fast.model", "openai/o3-mini")
    await _set("tiers.fast.effort", "low")
    cfg = cfg_mod.load(home)
    assert cfg.tiers.fast.model == "openai/o3-mini"
    assert cfg.tiers.fast.effort == "low"

    # Effort on a tier whose model can't reason is dropped, not stored.
    await _set("tiers.deep.model", "openai/gpt-4o-mini")
    await _set("tiers.deep.effort", "high")
    assert cfg_mod.load(home).tiers.deep.effort == ""

    # Swapping the tier model to a non-reasoning one auto-clears its effort.
    await _set("tiers.fast.model", "openai/gpt-4o-mini")
    cfg = cfg_mod.load(home)
    assert cfg.tiers.fast.model == "openai/gpt-4o-mini"
    assert cfg.tiers.fast.effort == ""

    # Empty model clears the whole tier; clearing both prunes the tiers block.
    await _set("tiers.fast.model", "")
    await _set("tiers.deep.model", "")
    cfg = cfg_mod.load(home)
    assert cfg.tiers.fast.model == "" and cfg.tiers.deep.model == ""
    import yaml as _yaml
    raw = _yaml.safe_load((home / "config.yaml").read_text()) or {}
    assert "tiers" not in raw


@pytest.mark.asyncio
async def test_profile_detail_exposes_tiers(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    home = _bootstrap(tmp_path / "h")
    cfg = cfg_mod.load(home)
    cfg.tiers.fast = cfg_mod.TierConfig(model="openai/o3-mini", effort="low")
    cfg_mod.save(cfg)

    monkeypatch.setattr(host_handlers, "_resolve_home", lambda profile: home)
    srv = host_server.Server(home=home)
    host_device_state.register(srv)

    resp = await srv._dispatch({
        "id": "detail",
        "method": "host.profile.detail",
        "params": {"profile": "default"},
    })
    tiers = resp["result"]["tiers"]
    assert tiers["fast"] == {
        "model": "openai/o3-mini", "effort": "low", "reasoning_supported": True,
    }
    assert tiers["deep"] == {"model": "", "effort": "", "reasoning_supported": False}


@pytest.mark.asyncio
async def test_unset_field_clears_tier_and_prunes_block(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    home = _bootstrap(tmp_path / "h")
    monkeypatch.setattr(host_handlers, "_resolve_home", lambda profile: home)
    srv = host_server.Server(home=home)
    host_device_state.register(srv)

    await srv._dispatch({
        "id": "set", "method": "host.config.set_field",
        "params": {"profile": "default", "key": "tiers.fast.model", "value": "openai/o3-mini"},
    })
    resp = await srv._dispatch({
        "id": "unset", "method": "host.config.unset_field",
        "params": {"profile": "default", "key": "tiers.fast"},
    })
    assert resp["result"]["ok"] is True
    assert cfg_mod.load(home).tiers.fast.model == ""
    import yaml as _yaml
    raw = _yaml.safe_load((home / "config.yaml").read_text()) or {}
    assert "tiers" not in raw


@pytest.mark.asyncio
async def test_cleanup_plan_and_apply_rpc(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    home = _bootstrap(tmp_path / "h")
    (home / "cache/tts").mkdir(parents=True)
    (home / "cache/tts/a.mp3").write_bytes(b"x" * 64)
    monkeypatch.setattr(host_handlers, "_resolve_home", lambda profile: home)
    srv = host_server.Server(home=home)
    host_device_state.register(srv)

    resp = await srv._dispatch({
        "id": "plan", "method": "host.cleanup.plan",
        "params": {"profile": "default"},
    })
    cats = resp["result"]["categories"]
    tts = next(c for c in cats if c["key"] == "tts")
    assert tts["size"] == 64 and tts["count"] == 1

    resp = await srv._dispatch({
        "id": "apply", "method": "host.cleanup.apply",
        "params": {"profile": "default", "keys": ["tts"]},
    })
    results = resp["result"]["results"]
    assert results[0]["ok"] and results[0]["removed"] == 1
    assert not (home / "cache/tts/a.mp3").exists()

    resp = await srv._dispatch({
        "id": "bad", "method": "host.cleanup.apply",
        "params": {"profile": "default"},
    })
    assert resp.get("error")


def test_cleanup_verbs_are_admin_gated() -> None:
    assert "host.cleanup.plan" in host_server._ADMIN_METHODS
    assert "host.cleanup.apply" in host_server._ADMIN_METHODS


@pytest.mark.asyncio
async def test_profile_memory_usage_reports_pct_for_all_three(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    from alpi import memory as mem_mod

    home = tmp_path / "h"
    (home / "memories").mkdir(parents=True)
    (home / "memories" / "USER.md").write_text("x" * 300)
    (home / "memories" / "MEMORY.md").write_text("")
    (home / "memories" / "AGENT.md").write_text("y" * 4000)
    monkeypatch.setattr(host_device_state.home_mod, "_ROOT", home)
    monkeypatch.setattr(host_handlers, "_resolve_home", lambda profile: home)
    srv = host_server.Server(home=home)
    host_device_state.register(srv)

    resp = await srv._dispatch({
        "id": "m", "method": "host.profile.memory_usage",
        "params": {"profile": "default"},
    })
    files = resp["result"]["files"]
    assert set(files) == {"AGENT.md", "USER.md", "MEMORY.md"}
    assert files["USER.md"]["limit"] == mem_mod.USER_CHAR_LIMIT
    assert files["USER.md"]["pct"] == round(300 / mem_mod.USER_CHAR_LIMIT * 100)
    assert files["AGENT.md"]["limit"] == mem_mod.AGENT_CHAR_LIMIT
    assert files["AGENT.md"]["pct"] == round(4000 / mem_mod.AGENT_CHAR_LIMIT * 100)
    assert isinstance(files["USER.md"]["updated_at"], (int, float))


@pytest.mark.asyncio
async def test_profile_memory_write_persists_and_rejects_unknown(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    home = tmp_path / "h"
    (home / "memories").mkdir(parents=True)
    monkeypatch.setattr(host_device_state.home_mod, "_ROOT", home)
    monkeypatch.setattr(host_handlers, "_resolve_home", lambda profile: home)
    srv = host_server.Server(home=home)
    host_device_state.register(srv)

    read = await srv._dispatch({
        "id": "r", "method": "host.profile.memory_read",
        "params": {"profile": "default", "name": "AGENT.md"},
    })
    rev0 = read["result"]["rev"]
    ok = await srv._dispatch({
        "id": "w", "method": "host.profile.memory_write",
        "params": {"profile": "default", "name": "AGENT.md", "text": "I am helpful.", "rev": rev0},
    })
    assert ok["result"]["ok"] is True
    assert (home / "memories" / "AGENT.md").read_text() == "I am helpful."

    missing = await srv._dispatch({
        "id": "w2", "method": "host.profile.memory_write",
        "params": {"profile": "default", "name": "USER.md", "text": "hi"},
    })
    assert missing["error"]["code"] == -32602

    bad = await srv._dispatch({
        "id": "w3", "method": "host.profile.memory_write",
        "params": {"profile": "default", "name": "../.env", "text": "x", "rev": "abc"},
    })
    assert bad["error"]["code"] == -32602


@pytest.mark.asyncio
async def test_profile_memory_read_returns_full_text_and_rev(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    home = tmp_path / "h"
    (home / "memories").mkdir(parents=True)
    (home / "memories" / "AGENT.md").write_text("full body here")
    monkeypatch.setattr(host_device_state.home_mod, "_ROOT", home)
    monkeypatch.setattr(host_handlers, "_resolve_home", lambda profile: home)
    srv = host_server.Server(home=home)
    host_device_state.register(srv)

    resp = await srv._dispatch({
        "id": "r", "method": "host.profile.memory_read",
        "params": {"profile": "default", "name": "AGENT.md"},
    })
    assert resp["result"]["text"] == "full body here"
    assert resp["result"]["rev"]


@pytest.mark.asyncio
async def test_profile_memory_write_conflicts_on_stale_rev(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    home = tmp_path / "h"
    (home / "memories").mkdir(parents=True)
    monkeypatch.setattr(host_device_state.home_mod, "_ROOT", home)
    monkeypatch.setattr(host_handlers, "_resolve_home", lambda profile: home)
    srv = host_server.Server(home=home)
    host_device_state.register(srv)

    r0 = await srv._dispatch({
        "id": "r0", "method": "host.profile.memory_read",
        "params": {"profile": "default", "name": "AGENT.md"},
    })
    first = await srv._dispatch({
        "id": "w1", "method": "host.profile.memory_write",
        "params": {"profile": "default", "name": "AGENT.md", "text": "v1", "rev": r0["result"]["rev"]},
    })
    stale = first["result"]["rev"]
    await srv._dispatch({
        "id": "w2", "method": "host.profile.memory_write",
        "params": {"profile": "default", "name": "AGENT.md", "text": "v2", "rev": stale},
    })
    conflict = await srv._dispatch({
        "id": "w3", "method": "host.profile.memory_write",
        "params": {"profile": "default", "name": "AGENT.md", "text": "v3", "rev": stale},
    })
    assert conflict["error"]["code"] == -32009
    assert (home / "memories" / "AGENT.md").read_text() == "v2"


@pytest.mark.asyncio
async def test_memory_usage_over_flag_at_boundary(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    from alpi import memory as mem_mod
    home = tmp_path / "h"
    (home / "memories").mkdir(parents=True)
    (home / "memories" / "AGENT.md").write_text("z" * (mem_mod.AGENT_CHAR_LIMIT + 1))
    monkeypatch.setattr(host_device_state.home_mod, "_ROOT", home)
    monkeypatch.setattr(host_handlers, "_resolve_home", lambda profile: home)
    srv = host_server.Server(home=home)
    host_device_state.register(srv)

    resp = await srv._dispatch({
        "id": "u", "method": "host.profile.memory_usage",
        "params": {"profile": "default"},
    })
    ag = resp["result"]["files"]["AGENT.md"]
    assert ag["over"] is True


@pytest.mark.asyncio
async def test_summaries_burst_collapses_and_frees_the_executor(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    import asyncio
    import time as _time

    home = _bootstrap(tmp_path / "h")
    monkeypatch.setattr(host_device_state.home_mod, "_ROOT", home)
    host_device_state.invalidate_summary()

    calls = {"n": 0}
    real = host_device_state._profile_summary

    def slow(row):
        calls["n"] += 1
        _time.sleep(0.25)
        return real(row)

    monkeypatch.setattr(host_device_state, "_profile_summary", slow)
    srv = host_server.Server(home=home)
    host_device_state.register(srv)

    async def summaries():
        return await srv._dispatch(
            {"id": "s", "method": "host.profile.summaries", "params": {}},
        )

    burst = [asyncio.create_task(summaries()) for _ in range(40)]
    await asyncio.sleep(0.05)

    started = _time.monotonic()
    await asyncio.wait_for(asyncio.to_thread(lambda: None), timeout=2.0)
    unrelated_latency = _time.monotonic() - started

    results = await asyncio.gather(*burst)
    n_profiles = len(results[0]["result"]["profiles"])

    assert calls["n"] == n_profiles, (
        f"burst of 40 polls walked {calls['n']} times for {n_profiles} profile(s) — "
        "the single-flight is not collapsing them"
    )
    assert unrelated_latency < 0.15, (
        f"an unrelated to_thread waited {unrelated_latency*1000:.0f}ms — the burst is "
        "parking executor threads, which is what starves every other host call"
    )


@pytest.mark.asyncio
async def test_config_change_invalidates_the_summary_before_emitting(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    from alpi.host import config as host_config

    home = _bootstrap(tmp_path / "h")
    monkeypatch.setattr(host_device_state.home_mod, "_ROOT", home)
    host_device_state.invalidate_summary()

    calls = {"n": 0}
    real = host_device_state._profile_summary

    def counting(row):
        calls["n"] += 1
        return real(row)

    monkeypatch.setattr(host_device_state, "_profile_summary", counting)
    srv = host_server.Server(home=home)
    host_device_state.register(srv)

    async def summaries():
        return await srv._dispatch(
            {"id": "s", "method": "host.profile.summaries", "params": {}},
        )

    r1 = await summaries()
    n_profiles = len(r1["result"]["profiles"])
    await summaries()
    assert calls["n"] == n_profiles, "cache did not warm"

    host_config._emit_config_changed(home, scope="providers")

    await summaries()
    assert calls["n"] == 2 * n_profiles, (
        "a config mutation left the sidebar serving the cached summary — the "
        "desktop's reload would show stale state until the TTL expired"
    )


@pytest.mark.asyncio
async def test_invalidation_during_a_walk_is_not_overwritten(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    import asyncio
    import threading as _threading

    home = _bootstrap(tmp_path / "h")
    monkeypatch.setattr(host_device_state.home_mod, "_ROOT", home)
    host_device_state.invalidate_summary()

    entered = _threading.Event()
    release = _threading.Event()
    state = {"value": "old"}

    def gated(row):
        snapshot = state["value"]
        entered.set()
        release.wait(timeout=5)
        return {**row, "marker": snapshot}

    monkeypatch.setattr(host_device_state, "_profile_summary", gated)
    srv = host_server.Server(home=home)
    host_device_state.register(srv)

    async def summaries():
        return await srv._dispatch(
            {"id": "s", "method": "host.profile.summaries", "params": {}},
        )

    inflight = asyncio.create_task(summaries())
    await asyncio.to_thread(entered.wait, 5)

    state["value"] = "new"
    host_device_state.invalidate_summary("default")
    release.set()
    await inflight

    monkeypatch.setattr(
        host_device_state, "_profile_summary", lambda row: {**row, "marker": state["value"]},
    )
    reload_resp = await summaries()
    markers = [p["marker"] for p in reload_resp["result"]["profiles"]]
    assert "old" not in markers, (
        "the in-flight walk re-cached the pre-mutation summary, so the reload the "
        f"event triggered still served it: {markers}"
    )


@pytest.mark.asyncio
async def test_set_field_rpc_refreshes_the_summary(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    home = _bootstrap(tmp_path / "h")
    monkeypatch.setattr(host_device_state.home_mod, "_ROOT", home)
    monkeypatch.setattr(host_handlers, "_resolve_home", lambda profile: home)
    host_device_state.invalidate_summary()

    srv = host_server.Server(home=home)
    host_device_state.register(srv)

    async def summaries():
        return await srv._dispatch(
            {"id": "s", "method": "host.profile.summaries", "params": {}},
        )

    before = await summaries()
    assert before["result"]["profiles"][0]["paused"] is not True

    await srv._dispatch({
        "id": "f", "method": "host.config.set_field",
        "params": {"profile": "default", "key": "paused", "value": True},
    })

    after = await summaries()
    assert after["result"]["profiles"][0]["paused"] is True, (
        "host.config.set_field emitted its event without dropping the cached "
        "summary — the desktop's reload would show the pre-edit value"
    )
