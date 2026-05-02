"""Per-tool result budget tests."""

from __future__ import annotations

from pathlib import Path

import yaml

from alpi.tools import _budget


def _write_cfg(home: Path, data: dict) -> None:
    (home / "config.yaml").write_text(yaml.safe_dump(data))


def test_default_cap_applies_when_no_config(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("ALPI_HOME", str(tmp_path))
    import alpi.home as home_mod
    monkeypatch.setattr(home_mod, "_ROOT", tmp_path)

    short = "x" * 50
    assert _budget.apply("terminal", short) == short  # under 100K default

    long = "x" * 250_000
    out = _budget.apply("terminal", long)
    assert len(out) < len(long)
    assert out.startswith("x" * 100_000)
    assert "chars elided" in out


def test_per_tool_override_lower(monkeypatch, tmp_path: Path) -> None:
    """A smaller cap for a specific tool is respected."""
    monkeypatch.setenv("ALPI_HOME", str(tmp_path))
    import alpi.home as home_mod
    monkeypatch.setattr(home_mod, "_ROOT", tmp_path)
    _write_cfg(tmp_path, {
        "model": "openrouter/xiaomi/mimo-v2-flash",
        "tools": {"terminal": {"max_result_chars": 100}},
    })
    out = _budget.apply("terminal", "x" * 500)
    assert out.startswith("x" * 100)
    assert "elided" in out


def test_per_tool_override_unlimited(monkeypatch, tmp_path: Path) -> None:
    """Negative caps disable truncation."""
    monkeypatch.setenv("ALPI_HOME", str(tmp_path))
    import alpi.home as home_mod
    monkeypatch.setattr(home_mod, "_ROOT", tmp_path)
    _write_cfg(tmp_path, {
        "model": "openrouter/xiaomi/mimo-v2-flash",
        "tools": {"read_file": {"max_result_chars": -1}},
    })
    huge = "x" * 500_000
    assert _budget.apply("read_file", huge) == huge


def test_global_budget_per_result(monkeypatch, tmp_path: Path) -> None:
    """`tools.budget.per_result_chars` applies when no per-tool override."""
    monkeypatch.setenv("ALPI_HOME", str(tmp_path))
    import alpi.home as home_mod
    monkeypatch.setattr(home_mod, "_ROOT", tmp_path)
    _write_cfg(tmp_path, {
        "model": "openrouter/xiaomi/mimo-v2-flash",
        "tools": {"budget": {"per_result_chars": 200}},
    })
    out = _budget.apply("web_fetch", "y" * 1000)
    assert out.startswith("y" * 200)
    assert "elided" in out


def test_per_tool_override_beats_global(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("ALPI_HOME", str(tmp_path))
    import alpi.home as home_mod
    monkeypatch.setattr(home_mod, "_ROOT", tmp_path)
    _write_cfg(tmp_path, {
        "model": "openrouter/xiaomi/mimo-v2-flash",
        "tools": {
            "budget": {"per_result_chars": 200},
            "read_file": {"max_result_chars": -1},
        },
    })
    huge = "z" * 10_000
    assert _budget.apply("read_file", huge) == huge           # override wins
    assert len(_budget.apply("web_fetch", huge)) < len(huge)  # global applies
