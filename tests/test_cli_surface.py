"""Guardrails on what ``alpi --help`` shows the user.

The CLI is deliberately thin: everything configurable lives in
``alpi setup``, logs are unified under ``alpi logs``, and lifecycle
commands (start/stop/restart/status) all live under ``alpi service``
since the unification refactor — there's only one process per
profile, supervised together.
"""

from __future__ import annotations

from click.testing import CliRunner

from alpi import cli


def test_top_level_help_shows_only_canonical_commands() -> None:
    result = CliRunner().invoke(cli.main, ["--help"])
    assert result.exit_code == 0
    out = result.output

    for name in ("chat", "setup", "doctor", "logs", "profile", "service",
                 "schedule", "peers", "workgroup", "release"):
        assert name in out, f"{name!r} missing from top-level --help"

    # mcp is fully absorbed by `alpi setup → MCPs`.
    assert "\n  mcp " not in out and "\n  mcp\n" not in out
    # Lifecycle groups removed.
    assert "\n  gateway " not in out, "gateway group should be gone"
    assert "\n  alp " not in out, "alp group should be gone"


def test_chat_help_does_not_expose_emit_events() -> None:
    result = CliRunner().invoke(cli.main, ["chat", "--help"])
    assert result.exit_code == 0
    assert "--once" in result.output
    assert "--emit-events" not in result.output


def test_service_help_lists_lifecycle_verbs() -> None:
    result = CliRunner().invoke(cli.main, ["service", "--help"])
    assert result.exit_code == 0
    for sub in ("start", "stop", "restart", "status"):
        assert sub in result.output


def test_schedule_help_lists_only_operational_verbs() -> None:
    """After unification, lifecycle moved to ``alpi service``; the
    ``schedule`` group keeps just ``run-once`` and ``fire``."""
    result = CliRunner().invoke(cli.main, ["schedule", "--help"])
    assert result.exit_code == 0
    for sub in ("run-once", "fire"):
        assert sub in result.output
    for gone in ("start", "stop", "restart", "status", "install", "uninstall"):
        assert f"\n  {gone}" not in result.output, f"schedule {gone} should be gone"


def test_dropped_commands_are_gone() -> None:
    for argv in (
        ["gateway"],
        ["alp"],
        ["mcp"],
        ["schedule", "start"],
        ["schedule", "stop"],
        ["schedule", "restart"],
        ["service", "install"],     # install lives in setup wizard, not CLI
        ["service", "uninstall"],
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


def test_service_start_rejects_missing_workspace(tmp_path, monkeypatch) -> None:
    """Unset ``workspace`` must stop ``alpi service start`` before it
    writes a PID file or boots subsystems."""
    monkeypatch.setenv("ALPI_HOME", str(tmp_path))
    (tmp_path / "config.yaml").write_text("model: openrouter/foo/bar\n")

    result = CliRunner().invoke(cli.main, ["service", "start"])
    assert result.exit_code != 0
    assert "No workspace configured" in result.output
    assert not (tmp_path / "service.pid").exists()


def test_service_start_rejects_nonexistent_workspace(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("ALPI_HOME", str(tmp_path))
    (tmp_path / "config.yaml").write_text(
        "model: openrouter/foo/bar\nworkspace: /no/such/dir\n"
    )

    result = CliRunner().invoke(cli.main, ["service", "start"])
    assert result.exit_code != 0
    assert "does not exist" in result.output
    assert "/no/such/dir" in result.output
