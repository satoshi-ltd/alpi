"""Engine surfaces the `peer` tool reply as the assistant message."""

from __future__ import annotations

from alpi.engine import _last_peer_reply
from alpi.session import ToolLog


def _log(name: str, ok: bool, result: str = "") -> ToolLog:
    return ToolLog(
        at=0.0, name=name, args={}, result=result, ok=ok, duration_s=0.0,
    )


def test_returns_reply_when_last_successful_tool_is_peer() -> None:
    logs = [_log("peer", True, "Hola, tu jefe es Jose.")]
    assert _last_peer_reply(logs) == "Hola, tu jefe es Jose."


def test_strips_trailing_usage_block() -> None:
    logs = [_log(
        "peer", True,
        "El equipo es Mirai.\n\n---\ntokens: in=10 out=20 · cost=$0.01",
    )]
    assert _last_peer_reply(logs) == "El equipo es Mirai."


def test_returns_empty_when_last_successful_tool_is_not_peer() -> None:
    logs = [
        _log("peer", True, "Hola"),
        _log("web_search", True, "..."),
    ]
    assert _last_peer_reply(logs) == ""


def test_skips_failed_tools_to_find_last_successful() -> None:
    logs = [
        _log("peer", True, "Hola"),
        _log("web_search", False),
    ]
    assert _last_peer_reply(logs) == "Hola"


def test_returns_empty_when_no_tools() -> None:
    assert _last_peer_reply([]) == ""


def test_returns_empty_when_peer_failed() -> None:
    logs = [_log("peer", False, "")]
    assert _last_peer_reply(logs) == ""
