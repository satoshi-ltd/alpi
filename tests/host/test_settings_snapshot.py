from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from alpi import config as cfg_mod
from alpi.alp.keys import load_or_generate
from alpi.host import device_state as host_device_state
from alpi.host import handlers as host_handlers
from alpi.host import server as host_server


def _bootstrap(home: Path) -> Path:
    home.mkdir(parents=True)
    cfg = cfg_mod.Config(home=home, model="openai/gpt-5.4-mini")
    cfg.workspace = "/tmp/work"
    cfg_mod.save(cfg)
    (home / ".env").write_text("OPENAI_API_KEY=sk-test\n")
    from alpi.mail import accounts as accounts_mod
    accounts_mod.add_imap(
        home, address="me@x.com", password="pw-secret",
        imap_host="imap.x.com", smtp_host="smtp.x.com",
    )
    load_or_generate(home)
    return home


def _seed(home: Path, monkeypatch: pytest.MonkeyPatch) -> host_server.Server:
    monkeypatch.setattr(host_device_state.home_mod, "_ROOT", home)
    monkeypatch.setattr(host_handlers, "_resolve_home", lambda profile: home)
    srv = host_server.Server(home=home)
    host_device_state.register(srv)
    return srv


async def _snapshot(srv: host_server.Server, profile: str = "default") -> dict:
    return await srv._dispatch({
        "id": "s", "method": "host.settings.profile_snapshot",
        "params": {"profile": profile},
    })


@pytest.mark.asyncio
async def test_profile_snapshot_aggregates_all_sections(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    home = _bootstrap(tmp_path / "h")
    srv = _seed(home, monkeypatch)

    result = (await _snapshot(srv))["result"]

    assert set(result) == {"detail", "usage", "schedules", "workgroups", "email", "storage"}
    assert result["detail"]["workspace"] == "/tmp/work"
    assert "models" in result["detail"]
    assert "days" in result["usage"] and "priceOut" in result["usage"]
    assert result["schedules"]["jobs"] == []
    assert isinstance(result["workgroups"]["workgroups"], list)
    assert result["email"]["accounts"][0]["address"] == "me@x.com"
    assert any(r["key"] == "sessions" for r in result["storage"]["storage"])


@pytest.mark.asyncio
async def test_profile_snapshot_matches_individual_handler_shapes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    home = _bootstrap(tmp_path / "h")
    srv = _seed(home, monkeypatch)

    snap = (await _snapshot(srv))["result"]
    detail = (await srv._dispatch({
        "id": "d", "method": "host.profile.detail", "params": {"profile": "default"},
    }))["result"]
    storage = (await srv._dispatch({
        "id": "st", "method": "host.profile.storage", "params": {"profile": "default"},
    }))["result"]
    email = (await srv._dispatch({
        "id": "e", "method": "host.email.status", "params": {"profile": "default"},
    }))["result"]

    assert snap["detail"] == detail
    assert snap["storage"] == storage
    assert snap["email"] == email


@pytest.mark.asyncio
async def test_profile_snapshot_unknown_profile_is_not_found(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    home = _bootstrap(tmp_path / "h")
    monkeypatch.setattr(host_device_state.home_mod, "_ROOT", home)
    monkeypatch.setattr(host_handlers, "_resolve_home", lambda profile: tmp_path / "nope")
    srv = host_server.Server(home=home)
    host_device_state.register(srv)

    resp = await _snapshot(srv, "ghost")
    assert resp["error"]["code"] == -32004


@pytest.mark.asyncio
async def test_corrupt_schedules_surface_structured_error_per_section(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    home = _bootstrap(tmp_path / "h")
    (home / "schedule").mkdir()
    (home / "schedule" / "jobs.json").write_text("{not valid json")
    srv = _seed(home, monkeypatch)

    result = (await _snapshot(srv))["result"]

    assert "jobs" not in result["schedules"]
    assert result["schedules"]["error"]["code"] == -32603
    assert "corrupt" in result["schedules"]["error"]["data"]["detail"]
    # A bad section must not nuke the rest.
    assert result["detail"]["workspace"] == "/tmp/work"


@pytest.mark.asyncio
async def test_snapshot_runs_off_the_event_loop(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    home = _bootstrap(tmp_path / "h")
    srv = _seed(home, monkeypatch)
    seen: list[str] = []
    real = asyncio.to_thread

    async def spy(fn, *args, **kwargs):
        seen.append(getattr(fn, "__name__", ""))
        return await real(fn, *args, **kwargs)

    monkeypatch.setattr(host_device_state.asyncio, "to_thread", spy)
    await _snapshot(srv)
    assert "_snapshot_payload" in seen


def test_member_redaction_strips_admin_sections_and_redacts_detail() -> None:
    full = {
        "result": {
            "detail": {"models": ["a/b"], "voice_id": "v", "workspace": "/secret", "peers": ["x"]},
            "usage": {"days": [], "priceOut": 1.0},
            "schedules": {"jobs": []},
            "workgroups": {"workgroups": [{"profile": "default", "id": "w1"}]},
            "email": {"accounts": [{"address": "me@x.com"}]},
            "storage": {"storage": []},
        },
    }
    out = host_server._redact_payload_by_role("host.settings.profile_snapshot", full)["result"]

    assert set(out) == {"detail", "workgroups"}
    assert out["detail"] == {"models": ["a/b"], "voice_id": "v"}
    assert out["workgroups"]["workgroups"][0]["id"] == "w1"


def test_scope_filter_prunes_snapshot_workgroups() -> None:
    payload = {
        "result": {
            "workgroups": {"workgroups": [
                {"profile": "default", "id": "keep"},
                {"profile": "other", "id": "drop"},
            ]},
        },
    }
    out = host_server._filter_payload_by_scope(
        "host.settings.profile_snapshot", payload, ["default"],
    )["result"]

    ids = [w["id"] for w in out["workgroups"]["workgroups"]]
    assert ids == ["keep"]

@pytest.mark.asyncio
async def test_snapshot_sections_param_limits_computed_sections(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    home = _bootstrap(tmp_path / "h")
    srv = _seed(home, monkeypatch)
    walked = {"n": 0}
    real_rows = host_device_state._storage_rows

    def counting(home_arg):
        walked["n"] += 1
        return real_rows(home_arg)

    monkeypatch.setattr(host_device_state, "_storage_rows", counting)

    resp = await srv._dispatch({
        "id": "s", "method": "host.settings.profile_snapshot",
        "params": {
            "profile": "default",
            "sections": ["detail", "usage", "workgroups", "email", "schedules"],
        },
    })
    result = resp["result"]
    assert set(result) == {"detail", "usage", "workgroups", "email", "schedules"}
    assert walked["n"] == 0


@pytest.mark.asyncio
async def test_snapshot_without_sections_param_returns_everything(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    home = _bootstrap(tmp_path / "h")
    srv = _seed(home, monkeypatch)
    result = (await _snapshot(srv))["result"]
    assert set(result) == {"detail", "usage", "schedules", "workgroups", "email", "storage"}
