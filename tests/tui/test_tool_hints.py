from __future__ import annotations

from pathlib import Path

from alpi import tool_hints

ROOT = Path(__file__).resolve().parents[2]


def test_arg_and_result_hints_live_in_the_neutral_module() -> None:
    assert tool_hints.arg_hint("terminal", {"command": "ls -la"}) == "ls -la"
    assert tool_hints.arg_hint("read_file", {"path": "/etc/hosts"}) == "/etc/hosts"
    assert tool_hints.result_hint("grep", "a\nb\nc", muted="dim") == "[dim]3 matches[/dim]"


def test_daemon_and_cli_do_not_import_hints_from_the_tui() -> None:
    for rel in ("alpi/host/chat.py", "alpi/cli.py"):
        assert "alpi.tui.formatting" not in (ROOT / rel).read_text(), rel
