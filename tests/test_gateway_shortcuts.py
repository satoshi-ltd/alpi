"""Gateway shortcut parser + handlers."""

from __future__ import annotations

import json
from pathlib import Path

import yaml

from alpi import session_map
from alpi.gateway import shortcuts


# Parser


def test_parse_none_without_slash_prefix() -> None:
    assert shortcuts.parse("hola alpi") is None
    assert shortcuts.parse("") is None


def test_parse_returns_command_for_known_shortcut() -> None:
    cmd = shortcuts.parse("/help")
    assert cmd is not None
    assert cmd.name == "help"
    assert cmd.arg == ""


def test_parse_captures_inline_argument() -> None:
    cmd = shortcuts.parse("/model gpt-4")
    assert cmd is not None
    assert cmd.name == "model"
    assert cmd.arg == "gpt-4"


def test_parse_is_case_insensitive_on_command() -> None:
    cmd = shortcuts.parse("/HELP")
    assert cmd is not None and cmd.name == "help"


def test_parse_ignores_unknown_slash_commands() -> None:
    """`/compact` is a TUI command but not a gateway shortcut — don't intercept."""
    assert shortcuts.parse("/compact") is None
    assert shortcuts.parse("/delete everything") is None


def test_parse_only_looks_at_first_line() -> None:
    """Multi-line inputs still dispatch on the first line command."""
    cmd = shortcuts.parse("/help\nPlease?")
    assert cmd is not None and cmd.name == "help"


# Handlers


def test_help_lists_every_shortcut(tmp_path: Path) -> None:
    reply = shortcuts.handle(shortcuts.Shortcut("help", ""), "chat-1", tmp_path)
    for name in shortcuts.SHORTCUTS:
        assert f"/{name}" in reply


def test_new_forgets_pointer_and_reports(tmp_path: Path) -> None:
    session_map.set(tmp_path, "chat-1", "sess-abc")
    reply = shortcuts.handle(shortcuts.Shortcut("new", ""), "chat-1", tmp_path)
    assert "new session" in reply.lower()
    assert session_map.get(tmp_path, "chat-1") is None


def test_new_without_active_session(tmp_path: Path) -> None:
    reply = shortcuts.handle(shortcuts.Shortcut("new", ""), "chat-1", tmp_path)
    assert "no active" in reply.lower()


def test_continue_shows_session_id_when_bound(tmp_path: Path) -> None:
    session_map.set(tmp_path, "chat-1", "sess-abc")
    reply = shortcuts.handle(shortcuts.Shortcut("continue", ""), "chat-1", tmp_path)
    assert "sess-abc" in reply


def test_continue_hints_when_no_session_yet(tmp_path: Path) -> None:
    reply = shortcuts.handle(shortcuts.Shortcut("continue", ""), "chat-1", tmp_path)
    assert "no active" in reply.lower()


def test_status_reads_session_file(tmp_path: Path) -> None:
    (tmp_path / "sessions").mkdir()
    (tmp_path / "sessions" / "sess-abc.json").write_text(json.dumps({
        "id": "sess-abc",
        "model": "anthropic/claude-sonnet-4-6",
        "turns": [{"at": 0, "user": "u", "assistant": "a", "tools": []}],
        "input_tokens": 1234,
        "output_tokens": 567,
        "cost_usd": 0.0042,
    }))
    session_map.set(tmp_path, "chat-1", "sess-abc")
    reply = shortcuts.handle(shortcuts.Shortcut("status", ""), "chat-1", tmp_path)
    assert "sess-abc" in reply
    assert "claude-sonnet-4-6" in reply
    assert "1,234" in reply
    assert "$0.0042" in reply


def test_status_without_session(tmp_path: Path) -> None:
    reply = shortcuts.handle(shortcuts.Shortcut("status", ""), "chat-1", tmp_path)
    assert "no active" in reply.lower()


def test_model_shows_config_value(tmp_path: Path) -> None:
    (tmp_path / "config.yaml").write_text(yaml.safe_dump({"model": "openai/gpt-4o"}))
    reply = shortcuts.handle(shortcuts.Shortcut("model", ""), "chat-1", tmp_path)
    assert "openai/gpt-4o" in reply


def test_catalog_matches_parser() -> None:
    """setMyCommands source = parser source — no drift."""
    names = {name for name, _ in shortcuts.catalog()}
    assert names == set(shortcuts.SHORTCUTS)


def test_catalog_descriptions_nonempty() -> None:
    """Telegram's setMyCommands rejects empty descriptions."""
    for name, desc in shortcuts.catalog():
        assert desc.strip(), f"empty description for /{name}"
