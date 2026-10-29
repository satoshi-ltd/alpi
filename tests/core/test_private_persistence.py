from __future__ import annotations

import logging
import os
import uuid
from pathlib import Path

import pytest

from alpi import audit, backup, outputs
from alpi._log import get_subsystem_logger
from alpi.host import _chat_events as chat_events
from alpi.host import events as host_events

posix_only = pytest.mark.skipif(os.name != "posix", reason="POSIX file modes")

SECRET = "sk-" + "A1b2C3d4E5f6G7h8I9j0"


def _mode(path: Path) -> int:
    return path.stat().st_mode & 0o777


@pytest.fixture(autouse=True)
def _isolate(monkeypatch, tmp_path: Path) -> None:
    import alpi.home as home_mod

    monkeypatch.setattr(home_mod, "_ROOT", tmp_path)
    monkeypatch.delenv("ALPI_HOME", raising=False)
    monkeypatch.delenv("ALPI_PROFILE", raising=False)


@posix_only
def test_replay_sidecar_is_redacted_and_private(tmp_path: Path) -> None:
    chat_events.reset_for_turn(tmp_path, "s1", "r1")
    chat_events.append(tmp_path, "s1", "r1", {"event": "tool_end", "output": f"key={SECRET}"})
    chat_events.append(tmp_path, "s1", "r1", {"event": "tool_end", "output": {
        "headers": {"Cookie": "sid=abcdef0123", "x-api-key": "k-0123456789abcdefgh"},
    }})
    path = chat_events._file_for(tmp_path, "s1")
    text = path.read_text()
    assert SECRET not in text
    assert "abcdef0123" not in text and "k-0123456789abcdefgh" not in text
    assert _mode(path) == 0o600


@posix_only
def test_existing_loose_sidecar_is_tightened_on_append(tmp_path: Path) -> None:
    path = chat_events._file_for(tmp_path, "s2")
    path.parent.mkdir(parents=True)
    path.write_text("")
    path.chmod(0o644)
    chat_events.append(tmp_path, "s2", "r1", {"event": "assistant_delta", "text": "hi"})
    assert _mode(path) == 0o600


@posix_only
def test_subsystem_log_is_redacted_and_private(tmp_path: Path) -> None:
    name = f"test-{uuid.uuid4().hex[:8]}"
    logger = get_subsystem_logger(tmp_path, name)
    logger.info("cmd=%r", f"docker login -p {SECRET}")
    logger.info("request Cookie: session=abcdef0123 x-api-key: k-0123456789abcdefgh")
    try:
        raise RuntimeError("Cookie: crash=abcdef0123")
    except RuntimeError:
        logger.exception("failed")
    for handler in logger.handlers:
        handler.flush()
    path = tmp_path / "logs" / f"{name}.log"
    text = path.read_text()
    assert SECRET not in text
    assert "abcdef0123" not in text and "k-0123456789abcdefgh" not in text
    assert _mode(path) == 0o600
    for handler in list(logger.handlers):
        handler.close()
        logger.removeHandler(handler)
    logging.getLogger(f"alpi.{name}")._alpi_configured = False


@posix_only
def test_outputs_store_is_redacted_and_private(tmp_path: Path) -> None:
    stored = outputs.append(tmp_path, profile="default", body=f"token {SECRET}")
    path = tmp_path / "outputs" / "outputs.jsonl"
    assert SECRET not in path.read_text()
    assert SECRET in stored["body"]
    assert _mode(path) == 0o600


@posix_only
def test_host_event_history_is_redacted_and_private(monkeypatch, tmp_path: Path) -> None:
    path = tmp_path / "host" / "events.jsonl"
    monkeypatch.setattr(host_events, "_history_path", path)
    host_events._append_history({"event": "x", "data": {"error": SECRET}, "seq": 1})
    assert SECRET not in path.read_text()
    assert _mode(path) == 0o600


@posix_only
def test_alp_turn_log_is_redacted_and_private(tmp_path: Path) -> None:
    from alpi import service

    service._append_turn_event(tmp_path, {"event_tail": f"Authorization: Bearer {SECRET}xyz"})
    path = service.turn_log_path(tmp_path)
    assert SECRET not in path.read_text()
    assert _mode(path) == 0o600


@posix_only
def test_approval_always_writes_config_atomically_private(tmp_path: Path) -> None:
    from alpi.tools import _approval

    _approval._persist_always("sudo")
    path = tmp_path / "config.yaml"
    assert "sudo" in path.read_text()
    assert _mode(path) == 0o600


@posix_only
def test_pgp_and_mcp_config_writers_are_private(tmp_path: Path) -> None:
    from alpi.mail import pgp_setup
    from alpi.mcp import setup as mcp_setup

    pgp_setup._write_email_cfg(tmp_path, "ABCDEF", True)
    assert _mode(tmp_path / "config.yaml") == 0o600
    (tmp_path / "config.yaml").chmod(0o644)
    mcp_setup._persist(tmp_path, "srv", "npx", ["x"], {})
    assert _mode(tmp_path / "config.yaml") == 0o600
    assert "signing_key" in (tmp_path / "config.yaml").read_text()


@posix_only
@pytest.mark.parametrize("rel,label", [
    ("secrets", "secrets/"),
    ("host/connections.yaml", "host/connections.yaml"),
    ("skills/cat/demo/secrets", "skills/cat/demo/secrets/"),
    ("cache", "cache/"),
    ("browser", "browser/"),
])
def test_audit_covers_secret_stores(tmp_path: Path, rel: str, label: str) -> None:
    path = tmp_path / rel
    if rel.endswith(".yaml"):
        path.parent.mkdir(parents=True)
        path.write_text("x: 1\n")
        path.chmod(0o644)
    else:
        path.mkdir(parents=True)
        path.chmod(0o755)
    checks = audit._audit_permissions(tmp_path)
    assert any(c.name == label and c.status in {"fail", "warn"} for c in checks), checks


@posix_only
def test_ensure_home_tightens_existing_private_dirs(tmp_path: Path) -> None:
    from alpi.home import ensure_home

    for rel in ("alp", "cache", "browser", "secrets/gmail_tokens"):
        (tmp_path / rel).mkdir(parents=True)
        (tmp_path / rel).chmod(0o755)
    ensure_home(tmp_path)
    for rel in ("alp", "cache", "browser", "secrets/gmail_tokens"):
        assert _mode(tmp_path / rel) == 0o700, rel


@posix_only
def test_restore_leaves_files_and_dirs_private(tmp_path: Path) -> None:
    from tests.core.test_backup import _write_encrypted_tar

    archive = tmp_path / "a.alpi-backup"
    _write_encrypted_tar(archive, [("alpi-home/alp/secrets/key", b"k"), ("alpi-home/config.yaml", b"x: 1\n")])
    target = tmp_path / "restored"
    old = os.umask(0o022)
    try:
        backup.restore_backup(archive, target, "pw")
    finally:
        os.umask(old)
    assert _mode(target) == 0o700
    assert _mode(target / "alp") == 0o700
    assert _mode(target / "alp" / "secrets") == 0o700
    assert _mode(target / "alp" / "secrets" / "key") & 0o077 == 0
    assert _mode(target / "config.yaml") & 0o077 == 0


@posix_only
def test_schedule_daemon_log_is_private(monkeypatch, tmp_path: Path) -> None:
    from types import SimpleNamespace

    from alpi.scheduler import run as sched_run

    monkeypatch.setattr(sched_run, "running_pid", lambda home: None)
    monkeypatch.setattr(sched_run.subprocess, "Popen", lambda *a, **k: SimpleNamespace(pid=4242))
    assert sched_run.ensure_running(tmp_path) == 4242
    assert _mode(tmp_path / "logs" / "schedule.log") == 0o600


@posix_only
def test_private_open_does_not_follow_a_planted_symlink(tmp_path: Path) -> None:
    from alpi.secrets_io import open_private

    outside = tmp_path / "outside.txt"
    outside.write_text("keep")
    outside.chmod(0o644)
    link = tmp_path / "logs" / "agent.log"
    link.parent.mkdir()
    link.symlink_to(outside)
    with pytest.raises(OSError):
        open_private(link)
    assert _mode(outside) == 0o644


def test_daemon_and_container_loggers_redact(monkeypatch, tmp_path: Path) -> None:
    from alpi import pid1, service
    from alpi._log import RedactingFormatter

    root = logging.getLogger()
    saved = list(root.handlers)
    try:
        pid1._configure_logging()
        assert all(isinstance(h.formatter, RedactingFormatter) for h in root.handlers)
        service._configure_logging_daemon(tmp_path)
        assert all(isinstance(h.formatter, RedactingFormatter) for h in root.handlers)
    finally:
        for h in list(root.handlers):
            h.close()
            root.removeHandler(h)
        for h in saved:
            root.addHandler(h)
