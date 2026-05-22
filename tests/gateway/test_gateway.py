"""Gateway tests."""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

from alpi import config
from alpi.gateway import run as gw_run
from alpi.tui.formatting import arg_hint
from alpi.gateway.base import IncomingMessage, OutgoingMessage, Platform


class FakePlatform(Platform):
    name = "fake"

    def __init__(self, home: Path) -> None:
        super().__init__(home)
        self.sent: list[OutgoingMessage] = []
        self.typing_pings: list[str] = []

    async def listen(self):  # pragma: no cover — unused here
        if False:
            yield  # type: ignore[misc]

    async def send(self, message: OutgoingMessage) -> None:
        self.sent.append(message)

    async def send_typing(self, chat_id: str) -> None:
        self.typing_pings.append(chat_id)


@dataclass
class FakeProc:
    lines: list[bytes]
    returncode: int = 0
    stderr_bytes: bytes = b""

    def __post_init__(self) -> None:
        self.stdout = _FakeStream(list(self.lines))
        self.stderr = _FakeStream([self.stderr_bytes] if self.stderr_bytes else [])

    async def wait(self) -> int:
        return self.returncode


class _FakeStream:
    def __init__(self, chunks: list[bytes]) -> None:
        self._chunks = chunks

    async def readline(self) -> bytes:
        if not self._chunks:
            return b""
        return self._chunks.pop(0)

    async def read(self) -> bytes:
        data = b"".join(self._chunks)
        self._chunks.clear()
        return data


def _event_lines(events: list[dict[str, Any]]) -> list[bytes]:
    return [(json.dumps(e) + "\n").encode() for e in events]


@pytest.mark.asyncio
async def test_run_agent_streams_tool_traces(monkeypatch, tmp_home_no_env: Path) -> None:
    events = [
        {"kind": "tool_start", "name": "memory", "preview": "update USER.md"},
        {"kind": "tool_start", "name": "web_search", "preview": "madrid weather"},
        {"kind": "reply", "text": "done"},
    ]
    monkeypatch.setattr(
        gw_run.asyncio, "create_subprocess_exec",
        _fake_subprocess(_event_lines(events)),
    )

    platform = FakePlatform(tmp_home_no_env)
    msg = IncomingMessage(platform="fake", external_user_id="u", external_chat_id="c", text="hi")
    reply = await gw_run._run_agent(msg, platform, tmp_home_no_env, show_trace=True)

    assert reply == "done"
    assert [m.text for m in platform.sent] == [
        "◆ memory · update USER.md",
        "◆ web_search · madrid weather",
    ]


@pytest.mark.asyncio
async def test_run_agent_hides_traces_when_muted(monkeypatch, tmp_home_no_env: Path) -> None:
    events = [
        {"kind": "tool_start", "name": "memory", "preview": "x"},
        {"kind": "reply", "text": "done"},
    ]
    monkeypatch.setattr(
        gw_run.asyncio, "create_subprocess_exec",
        _fake_subprocess(_event_lines(events)),
    )

    platform = FakePlatform(tmp_home_no_env)
    msg = IncomingMessage(platform="fake", external_user_id="u", external_chat_id="c", text="hi")
    reply = await gw_run._run_agent(msg, platform, tmp_home_no_env, show_trace=False)

    assert reply == "done"
    assert platform.sent == []


@pytest.mark.asyncio
async def test_run_agent_reemits_child_agent_message(
    monkeypatch, tmp_home_no_env: Path,
) -> None:
    events = [
        {
            "kind": "tool_start",
            "name": "send_message",
            "args": {
                "text": "Background task finished.",
                "title": "Task done",
                "channel": "alpi",
                "severity": "important",
                "kind": "result",
            },
        },
        {"kind": "tool_end", "name": "send_message", "ok": True},
        {"kind": "reply", "text": "done"},
    ]
    monkeypatch.setattr(
        gw_run.asyncio, "create_subprocess_exec",
        _fake_subprocess(_event_lines(events)),
    )
    captured = []
    from alpi.host import events as host_events
    monkeypatch.setattr(
        host_events, "emit",
        lambda kind, data=None: captured.append((kind, dict(data or {}))),
    )

    platform = FakePlatform(tmp_home_no_env)
    msg = IncomingMessage(platform="fake", external_user_id="u", external_chat_id="c", text="hi")
    reply = await gw_run._run_agent(msg, platform, tmp_home_no_env, show_trace=False)

    assert reply == "done"
    assert captured == [("agent.message", {
        "profile": "default",
        "title": "Task done",
        "body": "Background task finished.",
        "severity": "important",
        "kind": "result",
    })]


@pytest.mark.asyncio
async def test_process_starts_and_stops_typing_on_telegram(
    monkeypatch, tmp_home_no_env: Path,
) -> None:
    """telegram → typing on, hardcoded."""
    events = [{"kind": "reply", "text": "hi"}]
    monkeypatch.setattr(gw_run, "_TYPING_REFRESH_SECONDS", 0.01)
    monkeypatch.setattr(
        gw_run.asyncio, "create_subprocess_exec",
        _fake_subprocess(_event_lines(events), read_delay=0.05),
    )

    FakePlatform.name = "telegram"
    platform = FakePlatform(tmp_home_no_env)
    msg = IncomingMessage(platform="telegram", external_user_id="u", external_chat_id="c", text="hi")
    try:
        await gw_run._process(platform, msg, tmp_home_no_env)
    finally:
        FakePlatform.name = "fake"

    assert platform.sent[-1].text == "hi"
    assert len(platform.typing_pings) >= 1


@pytest.mark.asyncio
async def test_process_never_starts_typing_on_email(
    monkeypatch, tmp_home_no_env: Path,
) -> None:
    """imap/gmail → typing off, hardcoded; legacy YAML key ignored."""
    (tmp_home_no_env / "config.yaml").write_text(
        "gateway:\n  imap:\n    typing_indicator: true\n"
    )
    events = [{"kind": "reply", "text": "final"}]
    monkeypatch.setattr(gw_run, "_TYPING_REFRESH_SECONDS", 0.01)
    monkeypatch.setattr(
        gw_run.asyncio, "create_subprocess_exec",
        _fake_subprocess(_event_lines(events), read_delay=0.03),
    )

    FakePlatform.name = "imap"
    platform = FakePlatform(tmp_home_no_env)
    msg = IncomingMessage(platform="imap", external_user_id="u", external_chat_id="c", text="hi")
    try:
        await gw_run._process(platform, msg, tmp_home_no_env)
    finally:
        FakePlatform.name = "fake"

    assert platform.typing_pings == []
    assert [m.text for m in platform.sent] == ["final"]


@pytest.mark.asyncio
async def test_process_respects_telegram_show_tool_trace_false(
    monkeypatch, tmp_home_no_env: Path,
) -> None:
    """gateway.telegram.show_tool_trace stays configurable per profile."""
    (tmp_home_no_env / "config.yaml").write_text(
        "gateway:\n  telegram:\n    show_tool_trace: false\n"
    )
    events = [
        {"kind": "tool_start", "name": "memory", "preview": "x"},
        {"kind": "reply", "text": "final"},
    ]
    monkeypatch.setattr(gw_run, "_TYPING_REFRESH_SECONDS", 0.01)
    monkeypatch.setattr(
        gw_run.asyncio, "create_subprocess_exec",
        _fake_subprocess(_event_lines(events), read_delay=0.03),
    )

    FakePlatform.name = "telegram"
    platform = FakePlatform(tmp_home_no_env)
    msg = IncomingMessage(platform="telegram", external_user_id="u", external_chat_id="c", text="hi")
    try:
        await gw_run._process(platform, msg, tmp_home_no_env)
    finally:
        FakePlatform.name = "fake"

    # No tool trace, just the final reply.
    assert [m.text for m in platform.sent] == ["final"]


def test_gateway_config_defaults_nested(tmp_home_no_env: Path) -> None:
    """post-suppression DEFAULT_CONFIG: chat platforms keep show_tool_trace only."""
    cfg = config.load(tmp_home_no_env)
    assert cfg.gateway["telegram"]["show_tool_trace"] is True
    assert cfg.gateway["matrix"]["show_tool_trace"] is True
    assert cfg.gateway["imap"]["poll_interval"] == 60
    assert cfg.gateway["imap"]["mark_as_read"] is True
    for chat in ("telegram", "matrix"):
        assert "typing_indicator" not in cfg.gateway[chat]
    for email in ("imap", "gmail"):
        assert "typing_indicator" not in cfg.gateway[email]
        assert "show_tool_trace" not in cfg.gateway[email]


def test_gateway_config_deep_merge(tmp_home_no_env: Path) -> None:
    # Override one configurable flag and keep the rest by deep merge.
    (tmp_home_no_env / "config.yaml").write_text(
        "gateway:\n"
        "  telegram:\n"
        "    show_tool_trace: false\n"
        "  imap:\n"
        "    poll_interval: 30\n"
    )
    cfg = config.load(tmp_home_no_env)
    assert cfg.gateway["telegram"]["show_tool_trace"] is False
    assert cfg.gateway["imap"]["poll_interval"] == 30
    assert cfg.gateway["imap"]["mark_as_read"] is True  # default kept
    assert cfg.gateway["imap"]["mark_as_read"] is True          # default kept


def test_is_allowed_uses_per_profile_env(tmp_path, monkeypatch) -> None:
    from alpi.gateway import delivery

    # Global env grants chat 12345 — must NOT leak into a profile that hasn't.
    monkeypatch.setenv("TELEGRAM_ALLOWED_CHAT_IDS", "12345")

    home_doc = tmp_path / "doc"
    home_doc.mkdir()
    (home_doc / ".env").write_text("TELEGRAM_ALLOWED_CHAT_IDS=99999\n")
    platform = FakePlatform(home_doc)
    assert platform.env["TELEGRAM_ALLOWED_CHAT_IDS"] == "99999"

    # 12345 is in process env but NOT in doc/.env — must be rejected.
    assert delivery.is_allowed("telegram", "12345", env=platform.env) is False
    # 99999 comes from the profile .env — must be allowed.
    assert delivery.is_allowed("telegram", "99999", env=platform.env) is True

    # Sibling profile with its own allowlist sees only its own.
    home_mirai = tmp_path / "mirai"
    home_mirai.mkdir()
    (home_mirai / ".env").write_text("TELEGRAM_ALLOWED_CHAT_IDS=77777\n")
    sibling = FakePlatform(home_mirai)
    assert delivery.is_allowed("telegram", "99999", env=sibling.env) is False
    assert delivery.is_allowed("telegram", "77777", env=sibling.env) is True

    # Webhook env must not bleed into Telegram.
    monkeypatch.setenv("WEBHOOK_ALLOWED_CHAT_IDS", "12345")
    monkeypatch.setenv("TELEGRAM_ALLOWED_CHAT_IDS", "")
    home_empty = tmp_path / "empty"
    home_empty.mkdir()
    bare = FakePlatform(home_empty)
    assert delivery.is_allowed("telegram", "12345", env=bare.env) is False


def test_arg_hint_handles_research_brief() -> None:
    # Regression: research used to show the wrong field.
    hint = arg_hint("research", {"depth": "deep", "brief": "best beach hours"})
    assert "best beach hours" in hint
    assert "deep" not in hint


def test_arg_hint_known_tools() -> None:
    assert arg_hint("read_file", {"path": "/tmp/x.py"}) == "/tmp/x.py"
    assert arg_hint("session_search", {"query": "madrid"}) == "madrid"
    assert arg_hint("grep", {"pattern": "TODO"}) == "TODO"
# Helpers


def _fake_subprocess(lines: list[bytes], read_delay: float = 0.0):
    """Drop-in fake for ``asyncio.create_subprocess_exec``."""

    class _DelayStream(_FakeStream):
        async def readline(self) -> bytes:
            if read_delay:
                await asyncio.sleep(read_delay)
            return await super().readline()

    async def _creator(*args, **kwargs):  # noqa: ANN001
        proc = FakeProc(lines)
        proc.stdout = _DelayStream(list(lines))
        return proc

    return _creator


def test_arg_hint_terminal_detects_skill_in_default_home() -> None:
    # Only the skill name should be captured.
    cmd = "cd /Users/foo/.alpi/skills/creative/joker && python3 scripts/run.py"
    hint = arg_hint("terminal", {"command": cmd})
    assert "skill: joker" in hint


def test_arg_hint_terminal_detects_skill_with_full_script_path() -> None:
    cmd = "python3 /Users/foo/.alpi/skills/software/lint/scripts/check.py"
    hint = arg_hint("terminal", {"command": cmd})
    assert "skill: lint" in hint
    assert "check.py" in hint


def test_arg_hint_terminal_detects_skill_in_profile_home() -> None:
    cmd = "python3 /Users/foo/.alpi/profiles/work/skills/software/lint/scripts/check.py"
    hint = arg_hint("terminal", {"command": cmd})
    assert "skill: lint" in hint
    assert "check.py" in hint


def test_arg_hint_terminal_falls_back_when_no_skill_path() -> None:
    hint = arg_hint("terminal", {"command": "ls /tmp"})
    assert "skill" not in hint.lower()
    assert "ls /tmp" in hint
