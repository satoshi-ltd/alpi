"""Tests for home.get_home / profile resolution."""

from __future__ import annotations

import os
from pathlib import Path

from alpi import home


def test_default_is_home_alpi(monkeypatch) -> None:
    monkeypatch.delenv("ALPI_HOME", raising=False)
    monkeypatch.delenv("ALPI_PROFILE", raising=False)
    assert home.get_home() == Path.home() / ".alpi"


def test_alpi_home_env_overrides(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("ALPI_HOME", str(tmp_path))
    assert home.get_home() == tmp_path


def test_named_profile_goes_to_subdir(monkeypatch) -> None:
    monkeypatch.delenv("ALPI_HOME", raising=False)
    monkeypatch.delenv("ALPI_PROFILE", raising=False)
    assert home.get_home("work") == Path.home() / ".alpi" / "profiles" / "work"


def test_ensure_home_creates_subtree(tmp_path: Path) -> None:
    home.ensure_home(tmp_path)
    for sub in ("memories", "sessions", "skills", "schedule/output", "logs"):
        assert (tmp_path / sub).is_dir()


def test_alpi_profile_env_resolves(monkeypatch) -> None:
    monkeypatch.delenv("ALPI_HOME", raising=False)
    monkeypatch.setenv("ALPI_PROFILE", "work")
    assert home.get_home() == Path.home() / ".alpi" / "profiles" / "work"


def test_explicit_flag_beats_env(monkeypatch) -> None:
    monkeypatch.delenv("ALPI_HOME", raising=False)
    monkeypatch.setenv("ALPI_PROFILE", "work")
    # Explicit argument wins.
    assert home.get_home("personal") == Path.home() / ".alpi" / "profiles" / "personal"


def test_get_home_ignores_unknown_files_at_root(tmp_path: Path, monkeypatch) -> None:
    # Nothing on disk should influence resolution — only env + argument.
    monkeypatch.delenv("ALPI_HOME", raising=False)
    monkeypatch.delenv("ALPI_PROFILE", raising=False)
    monkeypatch.setattr(home, "_ROOT", tmp_path)
    (tmp_path / "some-random-marker").write_text("x")
    assert home.get_home() == tmp_path
