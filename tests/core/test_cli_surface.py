"""Guardrails on what ``alpi --help`` shows the user.

The CLI is deliberately thin: everything configurable lives in
``alpi setup``, logs are unified under ``alpi logs``, and the
machine-wide lifecycle (install/start/stop/restart/status/uninstall)
lives under ``alpi daemon``. Per-profile services are toggled in
each profile's ``config.yaml`` (no CLI surface).
"""

from __future__ import annotations

from click.testing import CliRunner

from alpi import cli


def test_top_level_help_shows_only_canonical_commands() -> None:
    result = CliRunner().invoke(cli.main, ["--help"])
    assert result.exit_code == 0
    out = result.output

    for name in ("chat", "setup", "doctor", "logs", "profile", "daemon",
                 "schedule", "peers", "workgroup", "release", "gateway",
                 "mcp", "providers", "sandbox", "voice"):
        assert name in out, f"{name!r} missing from top-level --help"

    assert "\n  alp " not in out, "alp group should be gone"
    assert "\n  service " not in out, "service group should have been renamed to daemon"


def test_chat_help_does_not_expose_emit_events() -> None:
    result = CliRunner().invoke(cli.main, ["chat", "--help"])
    assert result.exit_code == 0
    assert "--once" in result.output
    assert "--emit-events" not in result.output


def test_chat_help_exposes_attach() -> None:
    result = CliRunner().invoke(cli.main, ["chat", "--help"])
    assert "--attach" in result.output


def test_run_once_forwards_attachments(tmp_path, monkeypatch) -> None:
    from types import SimpleNamespace

    captured = {}

    class FakeEngine:
        def __init__(self, *, home, cfg):  # noqa: ANN001
            self.session = SimpleNamespace(id="x", subdir="sessions")

        def run_turn(self, text, emit, *, persist_inflight=True, attachments=None, **kw):  # noqa: ANN001
            captured["text"] = text
            captured["attachments"] = attachments

        def request_interrupt(self, reason="unknown"):
            return None

    monkeypatch.setattr(cli, "Engine", FakeEngine)
    monkeypatch.setattr(cli, "_bootstrap", lambda h: None)
    monkeypatch.setattr(cli.config, "load", lambda h: SimpleNamespace(model="x"))
    img = tmp_path / "room.png"
    img.write_bytes(b"\x89PNG\r\n\x1a\n")

    cli._run_once(tmp_path, "improve it", attach=(str(img),))

    assert captured["text"] == "improve it"
    assert captured["attachments"][0]["path"].endswith("room.png")
    assert captured["attachments"][0]["name"] == "room.png"


def test_daemon_help_lists_lifecycle_verbs() -> None:
    result = CliRunner().invoke(cli.main, ["daemon", "--help"])
    assert result.exit_code == 0
    for sub in ("start", "stop", "restart", "status", "install", "uninstall"):
        assert sub in result.output


def test_schedule_help_lists_only_operational_verbs() -> None:
    """After unification, lifecycle moved to ``alpi daemon``; the
    ``schedule`` group keeps just ``run-once`` and ``fire``."""
    result = CliRunner().invoke(cli.main, ["schedule", "--help"])
    assert result.exit_code == 0
    for sub in ("run-once", "fire"):
        assert sub in result.output
    for gone in ("start", "stop", "restart", "status", "install", "uninstall"):
        assert f"\n  {gone}" not in result.output, f"schedule {gone} should be gone"


def test_dropped_commands_are_gone() -> None:
    for argv in (
        ["alp"],
        ["schedule", "start"],
        ["schedule", "stop"],
        ["schedule", "restart"],
    ):
        result = CliRunner().invoke(cli.main, argv)
        assert result.exit_code != 0, f"{argv} should not exist"


def test_profile_subcommands_include_remove() -> None:
    result = CliRunner().invoke(cli.main, ["profile", "--help"])
    assert result.exit_code == 0
    for sub in ("list", "create", "remove"):
        assert sub in result.output


def test_logs_help_lists_source_filter() -> None:
    result = CliRunner().invoke(cli.main, ["logs", "--help"])
    assert result.exit_code == 0
    assert "--source" in result.output
    assert "--follow" in result.output or "-f" in result.output


# Workspace validation — fail fast before the orchestrator loops


# Workspace validation moved per-profile / per-subsystem. The central
# daemon supervises every profile under ``~/.alpi`` and a bad
# workspace on one profile no longer blocks the whole start — the
# affected subsystems log + skip, siblings keep running. The previous
# ``test_service_start_rejects_*`` tests gated on the old per-profile
# workspace check at ``service start`` and have been removed.
