"""host.identity.draft verb."""

from __future__ import annotations

import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path

import pytest

from alpi.host import config as host_config
from alpi.host import server as host_server


@pytest.fixture
def short_tmp():
    d = Path(tempfile.mkdtemp(prefix="alp-host-identity-", dir="/tmp"))
    try:
        yield d
    finally:
        shutil.rmtree(d, ignore_errors=True)


@dataclass
class _StubResult:
    content: str


def _seed_profile(root: Path, name: str, *, model: str, agent_text: str) -> Path:
    home = root / "profiles" / name
    (home / "memories").mkdir(parents=True, exist_ok=True)
    (home / "memories" / "AGENT.md").write_text(agent_text)
    cfg = home / "config.yaml"
    cfg.write_text(f"model: {model}\n")
    return home


def _wire_home(monkeypatch, root: Path):
    from alpi import home as home_mod
    monkeypatch.setattr(home_mod, "_ROOT", root)
    monkeypatch.setattr(
        home_mod,
        "home_for",
        lambda profile: root / "profiles" / profile,
    )


@pytest.mark.asyncio
async def test_draft_returns_bio_on_success(short_tmp: Path, monkeypatch) -> None:
    home = _seed_profile(short_tmp, "doc", model="x", agent_text="agent body")
    _wire_home(monkeypatch, short_tmp)
    monkeypatch.setattr(
        "alpi.llm.complete",
        lambda model, messages: _StubResult(content="the librarian"),
    )

    srv = host_server.Server(home=home)
    host_config.register(srv)
    resp = await srv._dispatch({
        "id": "r",
        "method": "host.identity.draft",
        "params": {"profile": "doc"},
    })
    assert "result" in resp, resp
    assert resp["result"] == {"bio": "the librarian"}


@pytest.mark.asyncio
async def test_draft_missing_profile_param(short_tmp: Path, monkeypatch) -> None:
    _seed_profile(short_tmp, "doc", model="x", agent_text="x")
    _wire_home(monkeypatch, short_tmp)
    srv = host_server.Server(home=short_tmp)
    host_config.register(srv)
    resp = await srv._dispatch({
        "id": "r",
        "method": "host.identity.draft",
        "params": {"profile": ""},
    })
    assert resp["error"]["code"] == -32602


@pytest.mark.asyncio
async def test_draft_unknown_profile(short_tmp: Path, monkeypatch) -> None:
    _wire_home(monkeypatch, short_tmp)
    srv = host_server.Server(home=short_tmp)
    host_config.register(srv)
    resp = await srv._dispatch({
        "id": "r",
        "method": "host.identity.draft",
        "params": {"profile": "ghost"},
    })
    assert resp["error"]["code"] == -32004


@pytest.mark.asyncio
async def test_draft_empty_agent_md_returns_handler_error(
    short_tmp: Path, monkeypatch,
) -> None:
    _seed_profile(short_tmp, "doc", model="x", agent_text="   ")
    _wire_home(monkeypatch, short_tmp)
    srv = host_server.Server(home=short_tmp)
    host_config.register(srv)
    resp = await srv._dispatch({
        "id": "r",
        "method": "host.identity.draft",
        "params": {"profile": "doc"},
    })
    assert resp["error"]["code"] == -32010
    assert "AGENT.md is empty" in resp["error"]["data"]["detail"]


@pytest.mark.asyncio
async def test_draft_no_model_configured(short_tmp: Path, monkeypatch) -> None:
    _seed_profile(short_tmp, "doc", model="", agent_text="agent body")
    _wire_home(monkeypatch, short_tmp)
    srv = host_server.Server(home=short_tmp)
    host_config.register(srv)
    resp = await srv._dispatch({
        "id": "r",
        "method": "host.identity.draft",
        "params": {"profile": "doc"},
    })
    assert resp["error"]["code"] == -32010
    assert "no model configured" in resp["error"]["data"]["detail"]


@pytest.mark.asyncio
async def test_draft_llm_failure_wraps_to_handler_error(
    short_tmp: Path, monkeypatch,
) -> None:
    _seed_profile(short_tmp, "doc", model="x", agent_text="agent body")
    _wire_home(monkeypatch, short_tmp)

    def boom(model, messages):
        raise RuntimeError("upstream timeout")

    monkeypatch.setattr("alpi.llm.complete", boom)
    srv = host_server.Server(home=short_tmp)
    host_config.register(srv)
    resp = await srv._dispatch({
        "id": "r",
        "method": "host.identity.draft",
        "params": {"profile": "doc"},
    })
    assert resp["error"]["code"] == -32010
    assert "upstream timeout" in resp["error"]["data"]["detail"]
