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
