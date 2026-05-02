from __future__ import annotations

from pathlib import Path

from alpi import config
from alpi.engine import _maybe_load_mcps


def test_maybe_load_mcps_skips_when_no_servers(tmp_path: Path) -> None:
    cfg = config.Config(home=tmp_path, model="", raw={})
    assert _maybe_load_mcps(cfg) == []


def test_maybe_load_mcps_delegates_to_registry(monkeypatch, tmp_path: Path) -> None:
    cfg = config.Config(
        home=tmp_path,
        model="",
        raw={"mcp": {"servers": {"demo": {"command": "echo"}}}},
    )
    seen = {}

    def fake_load_and_register(received):
        seen["cfg"] = received
        return ["client-a"]

    monkeypatch.setattr("alpi.mcp.registry.load_and_register", fake_load_and_register)

    assert _maybe_load_mcps(cfg) == ["client-a"]
    assert seen["cfg"] is cfg
