"""Guardrails on what ``alpi --help`` shows the user.

The CLI is deliberately thin: everything configurable lives in
``alpi setup``, logs are unified under ``alpi logs``, and
service-invoked daemon commands (``gateway start`` / ``schedule
start``) are hidden from help. This test locks that surface.
"""

from __future__ import annotations

from click.testing import CliRunner

from alpi import cli


def test_top_level_help_shows_only_canonical_commands() -> None:
    result = CliRunner().invoke(cli.main, ["--help"])
    assert result.exit_code == 0
    out = result.output

    for name in ("chat", "setup", "doctor", "logs", "profile", "gateway", "schedule"):
        assert name in out, f"{name!r} missing from top-level --help"

    # mcp is fully absorbed by `alpi setup → MCPs`.
    assert "\n  mcp " not in out and "\n  mcp\n" not in out


def test_chat_help_does_not_expose_emit_events() -> None:
    result = CliRunner().invoke(cli.main, ["chat", "--help"])
    assert result.exit_code == 0
    assert "--once" in result.output
    assert "--emit-events" not in result.output


def test_chat_emit_events_still_works_when_invoked_directly() -> None:
    result = CliRunner().invoke(cli.main, ["chat", "--emit-events", "--help"])
    assert result.exit_code == 0


def test_gateway_help_lists_start_and_stop() -> None:
    result = CliRunner().invoke(cli.main, ["gateway", "--help"])
    assert result.exit_code == 0
    assert "start" in result.output
    assert "stop" in result.output
    # Dropped: status/install/uninstall/logs live in `alpi setup` / `alpi logs`.
    for gone in ("status", "install", "uninstall", "logs"):
        assert f"\n  {gone}" not in result.output, f"gateway {gone} should be gone"


def test_schedule_help_lists_manual_controls() -> None:
    result = CliRunner().invoke(cli.main, ["schedule", "--help"])
    assert result.exit_code == 0
    for sub in ("start", "stop", "run-once"):
        assert sub in result.output
    for gone in ("status", "install", "uninstall", "logs"):
        assert f"\n  {gone}" not in result.output, f"schedule {gone} should be gone"


def test_dropped_commands_are_gone() -> None:
    for argv in (
        ["gateway", "status"],
        ["gateway", "install"],
        ["gateway", "uninstall"],
        ["gateway", "logs"],
        ["schedule", "status"],
        ["schedule", "install"],
        ["schedule", "uninstall"],
        ["schedule", "logs"],
        ["mcp"],
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


# ----------------------------------------------------------------------
# Daemon workspace validation — fail fast before the daemon loops
# ----------------------------------------------------------------------


def test_gateway_start_rejects_missing_workspace(tmp_path, monkeypatch) -> None:
    """Unset ``workspace`` must stop ``alpi gateway start`` before it
    writes a PID file or touches the network."""
    monkeypatch.setenv("ALPI_HOME", str(tmp_path))
    (tmp_path / "config.yaml").write_text("model: openrouter/foo/bar\n")

    result = CliRunner().invoke(cli.main, ["gateway", "start"])
    assert result.exit_code != 0
    assert "No workspace configured" in result.output
    assert not (tmp_path / "gateway" / "gateway.pid").exists()


def test_gateway_start_rejects_nonexistent_workspace(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("ALPI_HOME", str(tmp_path))
    (tmp_path / "config.yaml").write_text(
        "model: openrouter/foo/bar\nworkspace: /no/such/dir\n"
    )

    result = CliRunner().invoke(cli.main, ["gateway", "start"])
    assert result.exit_code != 0
    assert "does not exist" in result.output
    assert "/no/such/dir" in result.output


def test_schedule_start_rejects_missing_workspace(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("ALPI_HOME", str(tmp_path))
    (tmp_path / "config.yaml").write_text("model: openrouter/foo/bar\n")

    result = CliRunner().invoke(cli.main, ["schedule", "start"])
    assert result.exit_code != 0
    assert "No workspace configured" in result.output
