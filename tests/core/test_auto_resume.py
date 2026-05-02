"""Tests for `tui.auto_resume` config flag."""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml
from click.testing import CliRunner

from alpi import cli


@pytest.fixture(autouse=True)
def _isolate_profile_env(monkeypatch):
    """``main`` writes ``ALPI_PROFILE`` via ``os.environ`` directly (not
    monkeypatch), so snapshot + restore around every test."""
    before = os.environ.get("ALPI_PROFILE")
    monkeypatch.delenv("ALPI_PROFILE", raising=False)
    yield
    if before is None:
        os.environ.pop("ALPI_PROFILE", None)
    else:
        os.environ["ALPI_PROFILE"] = before


def _run_bare_alpi(tmp_path: Path, auto_resume: bool | None) -> bool | None:
    """Invoke bare `alpi` with the config's auto_resume set, return continue_last."""
    if auto_resume is not None:
        (tmp_path / "config.yaml").write_text(
            yaml.safe_dump({"tui": {"auto_resume": auto_resume}})
        )
    captured: dict[str, bool] = {}

    def _stub(h, continue_last=False, **_kw):
        captured["continue_last"] = continue_last

    with patch.object(cli, "_run_chat", _stub):
        CliRunner().invoke(cli.main, [], obj={}, env={"ALPI_HOME": str(tmp_path)})
    return captured.get("continue_last")


def test_default_config_does_not_auto_resume(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("ALPI_HOME", str(tmp_path))
    assert _run_bare_alpi(tmp_path, auto_resume=None) is False


def test_auto_resume_true_makes_bare_alpi_continue(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("ALPI_HOME", str(tmp_path))
    assert _run_bare_alpi(tmp_path, auto_resume=True) is True


def test_auto_resume_false_does_not_continue(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("ALPI_HOME", str(tmp_path))
    assert _run_bare_alpi(tmp_path, auto_resume=False) is False


def test_continue_flag_still_wins_when_auto_resume_off(tmp_path: Path, monkeypatch) -> None:
    """Explicit ``-c`` is still an override even when auto_resume is off."""
    monkeypatch.setenv("ALPI_HOME", str(tmp_path))
    (tmp_path / "config.yaml").write_text(
        yaml.safe_dump({"tui": {"auto_resume": False}})
    )
    captured: dict[str, bool] = {}

    def _stub(h, continue_last=False, **_kw):
        captured["continue_last"] = continue_last

    with patch.object(cli, "_run_chat", _stub):
        CliRunner().invoke(cli.main, ["-c"], obj={}, env={"ALPI_HOME": str(tmp_path)})
    assert captured.get("continue_last") is True


def test_malformed_config_falls_back_to_off(tmp_path: Path, monkeypatch) -> None:
    """A broken config.yaml must not crash bare ``alpi``; default = don't resume."""
    monkeypatch.setenv("ALPI_HOME", str(tmp_path))
    (tmp_path / "config.yaml").write_text("{{{ not yaml")
    captured: dict[str, bool] = {}

    def _stub(h, continue_last=False, **_kw):
        captured["continue_last"] = continue_last

    with patch.object(cli, "_run_chat", _stub):
        result = CliRunner().invoke(
            cli.main, [], obj={}, env={"ALPI_HOME": str(tmp_path)},
        )
    assert result.exit_code == 0
    assert captured.get("continue_last") is False
