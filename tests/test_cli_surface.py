"""Guardrails on what ``alf --help`` shows the user.

Dropped commands should be gone; hidden options should not appear.
This test locks the CLI surface so a future refactor doesn't
accidentally re-expose ``alf model`` or ``--emit-events``.
"""

from __future__ import annotations

from click.testing import CliRunner

from alf import cli


def test_top_level_help_shows_only_canonical_commands() -> None:
    result = CliRunner().invoke(cli.main, ["--help"])
    assert result.exit_code == 0
    out = result.output

    # Canonical commands — present.
    for name in ("chat", "setup", "profile", "gateway", "schedule", "mcp"):
        assert name in out, f"{name!r} missing from top-level --help"

    # Dropped — must not appear.
    for gone in ("model",):
        # Check that "model" isn't listed as a top-level command. It
        # may still appear in prose ("model, gateways, MCPs") so we
        # look for the "  model  " listing pattern.
        assert "\n  model " not in out and "\n  model\n" not in out, (
            f"{gone!r} should be removed from top-level --help"
        )


def test_chat_help_does_not_expose_emit_events() -> None:
    result = CliRunner().invoke(cli.main, ["chat", "--help"])
    assert result.exit_code == 0
    assert "--once" in result.output
    # Internal gateway contract — hidden, must not show in --help.
    assert "--emit-events" not in result.output


def test_chat_emit_events_still_works_when_invoked_directly() -> None:
    # The option is hidden, not removed — the gateway still spawns
    # ``alf chat --once "..." --emit-events``. Smoke-check parsing.
    result = CliRunner().invoke(cli.main, ["chat", "--emit-events", "--help"])
    assert result.exit_code == 0


def test_gateway_subcommands_no_setup() -> None:
    result = CliRunner().invoke(cli.main, ["gateway", "--help"])
    assert result.exit_code == 0
    for sub in ("start", "stop", "status", "logs", "install", "uninstall"):
        assert sub in result.output
    # 'setup' was removed — use `alf setup → Gateways → Telegram` instead.
    # A lingering 'setup' here would be a regression.
    assert "\n  setup " not in result.output


def test_profile_subcommands_include_remove() -> None:
    result = CliRunner().invoke(cli.main, ["profile", "--help"])
    assert result.exit_code == 0
    for sub in ("list", "create", "remove"):
        assert sub in result.output


# ----------------------------------------------------------------------
# Daemon workspace validation — fail fast before the daemon loops
# ----------------------------------------------------------------------


def test_gateway_start_rejects_missing_workspace(tmp_path, monkeypatch) -> None:
    """Unset ``workspace`` must stop ``alf gateway start`` before it
    writes a PID file or touches the network.

    Rationale: a gateway with no workspace is a daemon that rejects
    every tool call silently. Discovering that via ``tail -f`` an hour
    later is strictly worse than a UsageError at the command boundary.
    """
    monkeypatch.setenv("ALF_HOME", str(tmp_path))
    # Bare-minimum config: no workspace key at all.
    (tmp_path / "config.yaml").write_text("model: openrouter/foo/bar\n")

    result = CliRunner().invoke(cli.main, ["gateway", "start"])
    assert result.exit_code != 0
    assert "No workspace configured" in result.output
    # Critical: PID file must NOT exist — the daemon aborted before
    # ``_write_pid`` could fire.
    assert not (tmp_path / "gateway" / "gateway.pid").exists()


def test_gateway_start_rejects_nonexistent_workspace(tmp_path, monkeypatch) -> None:
    """``workspace`` set but the directory is gone (typo, moved mount).

    Same rationale as above — fail loudly, not silently.
    """
    monkeypatch.setenv("ALF_HOME", str(tmp_path))
    (tmp_path / "config.yaml").write_text(
        "model: openrouter/foo/bar\nworkspace: /no/such/dir\n"
    )

    result = CliRunner().invoke(cli.main, ["gateway", "start"])
    assert result.exit_code != 0
    assert "does not exist" in result.output
    assert "/no/such/dir" in result.output


def test_schedule_start_rejects_missing_workspace(tmp_path, monkeypatch) -> None:
    """Schedule daemon carries the same invariant as the gateway.

    Scheduled jobs spawn ``alf chat --once`` subprocesses — each one
    needs a workspace. A silent daemon that never runs a single job is
    a worse failure mode than refusing to start.
    """
    monkeypatch.setenv("ALF_HOME", str(tmp_path))
    (tmp_path / "config.yaml").write_text("model: openrouter/foo/bar\n")

    result = CliRunner().invoke(cli.main, ["schedule", "start"])
    assert result.exit_code != 0
    assert "No workspace configured" in result.output
