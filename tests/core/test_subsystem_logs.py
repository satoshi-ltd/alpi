"""Approval audit log + cross-session agent log."""

from __future__ import annotations

import logging
from pathlib import Path

from alpi._log import get_subsystem_logger
from alpi.tools import _approval


def _reset_logger(name: str) -> None:
    """Tear down the cached handlers so a test-local ``home`` is picked up."""
    logger = logging.getLogger(name)
    for h in list(logger.handlers):
        logger.removeHandler(h)
        try:
            h.close()
        except Exception:  # noqa: BLE001
            pass
    if hasattr(logger, "_alpi_configured"):
        delattr(logger, "_alpi_configured")


def test_subsystem_logger_writes_to_expected_path(tmp_path: Path) -> None:
    _reset_logger("alpi.demo")
    logger = get_subsystem_logger(tmp_path, "demo")
    logger.info("hello world")
    for h in logger.handlers:
        h.flush()

    log_file = tmp_path / "logs" / "demo.log"
    assert log_file.exists()
    content = log_file.read_text()
    assert "hello world" in content
    # Same format as gateway/scheduler — timestamp 19 chars + level + name + msg.
    assert content[4] == "-" and content[7] == "-" and content[10] == " "
    assert "INFO" in content
    assert "alpi.demo" in content


def test_approval_logs_caution_decision(tmp_path: Path, monkeypatch) -> None:
    _reset_logger("alpi.approval")
    from alpi import home as home_mod
    monkeypatch.setattr(home_mod, "get_home", lambda: tmp_path)

    _approval.clear_session_allowlist()
    # No interactive approver in this surface — caution => DENY.
    _approval.set_prompt_callback(None)

    decision = _approval.check("rm -rf build/")
    assert decision.allowed is False
    assert decision.severity == _approval.Severity.CAUTION

    log_file = tmp_path / "logs" / "approval.log"
    assert log_file.exists()
    content = log_file.read_text()
    assert "DENY" in content
    assert "rm -rf build/" in content
    assert "caution" in content


def test_approval_does_not_log_safe_commands(tmp_path: Path, monkeypatch) -> None:
    _reset_logger("alpi.approval")
    from alpi import home as home_mod
    monkeypatch.setattr(home_mod, "get_home", lambda: tmp_path)

    _approval.check("ls -la")
    _approval.check("echo hi")

    log_file = tmp_path / "logs" / "approval.log"
    # File might not even be created when nothing is logged.
    assert not log_file.exists() or log_file.read_text() == ""


def test_approval_logs_allow_when_user_approves(tmp_path: Path, monkeypatch) -> None:
    _reset_logger("alpi.approval")
    from alpi import home as home_mod
    monkeypatch.setattr(home_mod, "get_home", lambda: tmp_path)

    _approval.clear_session_allowlist()
    _approval.set_prompt_callback(lambda cmd, desc, sev: "session")

    decision = _approval.check("sudo -s")
    assert decision.allowed is True

    content = (tmp_path / "logs" / "approval.log").read_text()
    assert "ALLOW" in content
    assert "sudo" in content


def test_agent_log_emits_one_line_per_turn(tmp_path: Path, monkeypatch) -> None:
    """End-to-end: the engine's _log_agent_turn helper must write to agent.log."""
    _reset_logger("alpi.agent")

    # Minimal fake session object — only the attributes the helper reads.
    class _FakeSession:
        id = "abc123"
        cost_usd = 0.0042

    class _FakeTool:
        def __init__(self, n: str) -> None:
            self.name = n

    class _FakeEngine:
        home = tmp_path
        session = _FakeSession()

    from alpi.engine import Engine
    Engine._log_agent_turn(
        _FakeEngine(), "what time is it?", "It's 10:00.",
        [_FakeTool("get_time")], elapsed=0.5,
    )

    content = (tmp_path / "logs" / "agent.log").read_text()
    assert "session=abc123" in content
    assert "tools=get_time" in content
    assert "what time is it?" in content
    assert "cost=$0.0042" in content
