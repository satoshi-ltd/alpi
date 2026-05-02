"""Tests for ``alpi._log``."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from alpi import _log


def test_log_dir_and_path_are_consistent(tmp_path: Path) -> None:
    assert _log.log_dir(tmp_path) == tmp_path / "logs"
    assert _log.log_path(tmp_path, "gateway") == tmp_path / "logs" / "gateway.log"


def test_get_subsystem_logger_writes_file(tmp_path: Path) -> None:
    subsystem = f"unit_{uuid4().hex}"
    logger = _log.get_subsystem_logger(tmp_path, subsystem)
    logger.info("hello world")

    for handler in logger.handlers:
        handler.flush()

    path = _log.log_path(tmp_path, subsystem)
    assert path.exists()
    assert "hello world" in path.read_text()
    assert logger.name == f"alpi.{subsystem}"
    assert logger.propagate is False


def test_get_subsystem_logger_is_idempotent(tmp_path: Path) -> None:
    subsystem = f"unit_{uuid4().hex}"
    first = _log.get_subsystem_logger(tmp_path, subsystem)
    second = _log.get_subsystem_logger(tmp_path, subsystem)
    assert first is second
