"""Shared pytest fixtures and markers.

Markers
-------
- ``llm`` — test performs real LLM calls. Skipped by default. Enable with
  ``pytest --llm`` or set ``ALPI_LLM=1``.

Fixtures
--------
- ``tmp_home`` — a fresh, isolated ``~/.alpi/`` rooted at a temp dir. Copies
  the real ``~/.alpi/.env`` in so LLM calls work for integration tests.
- ``tmp_home_no_env`` — same as above but without copying ``.env``. Use for
  unit tests that must not talk to any LLM.
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path

import pytest


# --------------------------------------------------------------------
# --llm option and automatic skipping
# --------------------------------------------------------------------

def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--llm",
        action="store_true",
        default=bool(os.environ.get("ALPI_LLM")),
        help="Run tests that make real LLM API calls (costs money).",
    )


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line(
        "markers",
        "llm: test makes real LLM calls; requires --llm or ALPI_LLM=1",
    )


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    if config.getoption("--llm"):
        return
    skip = pytest.mark.skip(reason="needs --llm flag to make real LLM calls")
    for item in items:
        if "llm" in item.keywords:
            item.add_marker(skip)


# --------------------------------------------------------------------
# Fixtures
# --------------------------------------------------------------------

@pytest.fixture
def tmp_home_no_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A clean alpi home directory (no API keys). Safe for unit tests.

    Chdirs into the tmp dir AND points ALPI_HOME at it, so file-tool tests
    exercising paths under tmp_path pass the cwd sandbox and don't read
    the developer's real ~/.alpi/config.yaml (which may have a workspace
    that contradicts the tmp path).
    """
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("ALPI_HOME", str(tmp_path))
    return tmp_path


@pytest.fixture
def tmp_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """An alpi home with the user's real .env copied (for LLM tests)."""
    src_env = Path.home() / ".alpi" / ".env"
    if src_env.exists():
        (tmp_path / ".env").write_text(src_env.read_text())
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("ALPI_HOME", str(tmp_path))
    return tmp_path


@pytest.fixture(autouse=True)
def _disable_scheduler_autoinstall(monkeypatch: pytest.MonkeyPatch) -> None:
    """Prevent tests from writing launchd plists / systemd units on the dev box."""
    monkeypatch.setenv("ALPI_SKIP_AUTO_INSTALL", "1")


@pytest.fixture(autouse=True)
def _reset_session_search_state() -> None:
    """Avoid state leaking between tests that use session_search."""
    try:
        from alpi.tools import session_search
        session_search.set_current_session_id(None)
    except Exception:
        pass
