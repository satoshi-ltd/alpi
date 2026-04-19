"""Tests for home.get_home / profile resolution."""

from __future__ import annotations

import os
from pathlib import Path

from alf import home


def test_default_is_home_alf(monkeypatch) -> None:
    monkeypatch.delenv("ALF_HOME", raising=False)
    monkeypatch.delenv("ALF_PROFILE", raising=False)
    assert home.get_home() == Path.home() / ".alf"


def test_alf_home_env_overrides(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("ALF_HOME", str(tmp_path))
    assert home.get_home() == tmp_path


def test_named_profile_goes_to_subdir(monkeypatch) -> None:
    monkeypatch.delenv("ALF_HOME", raising=False)
    monkeypatch.delenv("ALF_PROFILE", raising=False)
    assert home.get_home("work") == Path.home() / ".alf" / "profiles" / "work"


def test_ensure_home_creates_subtree(tmp_path: Path) -> None:
    home.ensure_home(tmp_path)
    for sub in ("memories", "sessions", "skills", "cron/output", "gateway/logs"):
        assert (tmp_path / sub).is_dir()
