"""Shared pytest fixtures and markers.

Markers
-------
- ``llm`` — test performs real LLM calls. Skipped by default. Enable with
  ``pytest --llm`` or set ``ALPI_LLM=1``.

Fixtures
--------
- ``tmp_home`` — fresh isolated ``~/.alpi/`` at a temp dir, **no** real
  ``.env`` copied. Default for every unit test.
- ``tmp_home_no_env`` — alias of ``tmp_home`` (kept so older tests keep
  passing without churn).
- ``tmp_home_with_real_env`` — copies the developer's real
  ``~/.alpi/.env`` in. Only ``--llm`` integration tests should ask for
  this; an autouse fixture below scrubs sensitive vars from
  ``os.environ`` at the start of every test, so even if a stray one
  imports something that reads a token, it sees an empty string.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest


_SENSITIVE_ENV_VARS = (
    "TELEGRAM_BOT_TOKEN",
    "TELEGRAM_ALLOWED_CHAT_IDS",
    "OPENAI_API_KEY",
    "ANTHROPIC_API_KEY",
    "GROQ_API_KEY",
    "MISTRAL_API_KEY",
    "DEEPSEEK_API_KEY",
    "TOGETHER_API_KEY",
    "FIREWORKS_API_KEY",
    "OPENROUTER_API_KEY",
    "GEMINI_API_KEY",
    "GOOGLE_API_KEY",
    "GMAIL_CLIENT_ID",
    "GMAIL_CLIENT_SECRET",
    "IMAP_ADDRESS",
    "IMAP_PASSWORD",
    "IMAP_HOST",
    "IMAP_PORT",
    "SMTP_HOST",
    "SMTP_PORT",
    "IMAP_ALLOWED_SENDERS",
    "GMAIL_ALLOWED_SENDERS",
)


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

@pytest.fixture(autouse=True)
def _scrub_sensitive_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Deny secrets to every test by default. The developer's shell may
    have ``TELEGRAM_BOT_TOKEN`` / API keys exported, and ``config.load``
    paths run ``load_dotenv`` which would otherwise import the profile
    ``.env``. Tests that genuinely need real creds opt back in via
    ``tmp_home_with_real_env`` (used only by ``@pytest.mark.llm``)."""
    for var in _SENSITIVE_ENV_VARS:
        monkeypatch.delenv(var, raising=False)


@pytest.fixture
def tmp_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Clean alpi home (no API keys). The default for unit tests."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("ALPI_HOME", str(tmp_path))
    return tmp_path


@pytest.fixture
def tmp_home_no_env(tmp_home: Path) -> Path:
    return tmp_home


@pytest.fixture
def tmp_home_with_real_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Real ``~/.alpi/.env`` copied in + loaded into ``os.environ``.
    Only for ``--llm`` integration tests — do NOT use elsewhere."""
    src_env = Path.home() / ".alpi" / ".env"
    if src_env.exists():
        (tmp_path / ".env").write_text(src_env.read_text())
        from dotenv import dotenv_values
        for k, v in dotenv_values(src_env).items():
            if v is not None:
                monkeypatch.setenv(k, v)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("ALPI_HOME", str(tmp_path))
    return tmp_path


@pytest.fixture(autouse=True)
def _disable_scheduler_autoinstall(monkeypatch: pytest.MonkeyPatch) -> None:
    """Prevent tests from writing launchd plists / systemd units on the dev box."""
    monkeypatch.setenv("ALPI_SKIP_AUTO_INSTALL", "1")


@pytest.fixture(autouse=True)
def _disable_update_check(monkeypatch: pytest.MonkeyPatch) -> None:
    """Stop the updater's background daemon thread from reaching PyPI
    during the unit suite. The check spawns from ``cli.py::main`` on
    every alpi invocation; tests that import alpi shouldn't trigger
    network traffic."""
    monkeypatch.setenv("ALPI_SKIP_UPDATE_CHECK", "1")


@pytest.fixture(autouse=True)
def _reset_session_search_state() -> None:
    """Avoid state leaking between tests that use session_search."""
    try:
        from alpi.tools import session_search
        session_search.set_current_session_id(None)
    except Exception:
        pass
