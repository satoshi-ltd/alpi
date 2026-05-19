"""host.providers.ollama_models — verify the per-server errors envelope."""

from __future__ import annotations

import io
import json
import urllib.error
from pathlib import Path

import pytest

from alpi import config as cfg_mod
from alpi.host import device_state as host_device_state
from alpi.host import handlers as host_handlers
from alpi.host import server as host_server


def _bootstrap(home: Path, ollamas: list[dict[str, str]]) -> Path:
    home.mkdir()
    cfg = cfg_mod.Config(home=home, model="openai/gpt-5.4-mini")
    cfg.providers = {"ollama": ollamas}
    cfg_mod.save(cfg)
    return home


class _FakeResp:
    def __init__(self, payload: str) -> None:
        self._buf = io.BytesIO(payload.encode("utf-8"))

    def read(self) -> bytes:
        return self._buf.read()

    def __enter__(self) -> "_FakeResp":
        return self

    def __exit__(self, *args: object) -> None:
        self._buf.close()


@pytest.mark.asyncio
async def test_ollama_models_returns_both_models_and_errors(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    home = _bootstrap(
        tmp_path / "h",
        [
            {"name": "good", "url": "http://127.0.0.1:11434"},
            {"name": "down", "url": "http://10.0.0.99:11434"},
            {"name": "bad-json", "url": "http://127.0.0.1:11435"},
        ],
    )
    monkeypatch.setattr(host_handlers, "_resolve_home", lambda profile: home)

    # urllib lives at module level inside _ollama_models so we patch the
    # urlopen used at call-time via a closure that branches on host.
    def fake_urlopen(url: str, timeout: float = 0):  # noqa: ARG001
        if "10.0.0.99" in url:
            raise urllib.error.URLError("connection refused")
        if "11435" in url:
            return _FakeResp("not-json{")
        return _FakeResp(json.dumps({"models": [{"name": "llama3:8b"}, {"name": "mistral:7b"}]}))

    monkeypatch.setattr(
        "urllib.request.urlopen",
        fake_urlopen,
    )

    srv = host_server.Server(home=home)
    host_device_state.register(srv)
    resp = await srv._dispatch({
        "id": "om",
        "method": "host.providers.ollama_models",
        "params": {"profile": "default"},
    })

    result = resp["result"]
    assert result["models"] == ["good/llama3:8b", "good/mistral:7b"]
    errors = {e["name"]: e for e in result["errors"]}
    assert set(errors) == {"down", "bad-json"}
    assert "connection refused" in errors["down"]["detail"]
    assert errors["down"]["url"] == "http://10.0.0.99:11434"
    assert errors["bad-json"]["detail"].startswith("bad json:")


@pytest.mark.asyncio
async def test_ollama_models_no_configured_servers_returns_empty_envelope(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    home = _bootstrap(tmp_path / "h", [])
    monkeypatch.setattr(host_handlers, "_resolve_home", lambda profile: home)

    srv = host_server.Server(home=home)
    host_device_state.register(srv)
    resp = await srv._dispatch({
        "id": "om",
        "method": "host.providers.ollama_models",
        "params": {"profile": "default"},
    })

    assert resp["result"] == {"models": [], "errors": []}
