"""Gateway tests — event streaming, typing indicator, trace muting."""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest

from alf import config
from alf.gateway import run as gw_run
from alf.tui.formatting import arg_hint
from alf.gateway.base import IncomingMessage, OutgoingMessage, Platform


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
async def test_process_starts_and_stops_typing(monkeypatch, tmp_home_no_env: Path) -> None:
    events = [{"kind": "reply", "text": "hi"}]
    # Give the typing loop at least one tick by slowing the subprocess.
    monkeypatch.setattr(gw_run, "_TYPING_REFRESH_SECONDS", 0.01)

    real_create = gw_run.asyncio.create_subprocess_exec
    fake = _fake_subprocess(_event_lines(events), read_delay=0.05)
    monkeypatch.setattr(gw_run.asyncio, "create_subprocess_exec", fake)

    platform = FakePlatform(tmp_home_no_env)
    msg = IncomingMessage(platform="fake", external_user_id="u", external_chat_id="c", text="hi")

    await gw_run._process(platform, msg, tmp_home_no_env)

    assert platform.sent[-1].text == "hi"
    assert len(platform.typing_pings) >= 1


@pytest.mark.asyncio
async def test_process_respects_typing_indicator_false(monkeypatch, tmp_home_no_env: Path) -> None:
    # Write a config.yaml that disables both Telegram-specific flags.
    (tmp_home_no_env / "config.yaml").write_text(
        "gateway:\n"
        "  telegram:\n"
        "    typing_indicator: false\n"
        "    show_tool_trace: false\n"
    )
    # FakePlatform's name is "fake" by default — make it look like
    # telegram so the run loop picks up the telegram config bucket.
    FakePlatform.name = "telegram"
    events = [
        {"kind": "tool_start", "name": "memory", "preview": "x"},
        {"kind": "reply", "text": "final"},
    ]
    monkeypatch.setattr(gw_run, "_TYPING_REFRESH_SECONDS", 0.01)
    monkeypatch.setattr(
        gw_run.asyncio, "create_subprocess_exec",
        _fake_subprocess(_event_lines(events), read_delay=0.03),
    )

    platform = FakePlatform(tmp_home_no_env)
    msg = IncomingMessage(platform="telegram", external_user_id="u", external_chat_id="c", text="hi")
    try:
        await gw_run._process(platform, msg, tmp_home_no_env)
    finally:
        FakePlatform.name = "fake"

    # Only the final reply — no trace, no typing pings.
    assert platform.typing_pings == []
    assert [m.text for m in platform.sent] == ["final"]


def test_gateway_config_defaults_nested(tmp_home_no_env: Path) -> None:
    cfg = config.load(tmp_home_no_env)
    assert cfg.gateway["telegram"]["show_tool_trace"] is True
    assert cfg.gateway["telegram"]["typing_indicator"] is True
    assert cfg.gateway["email"]["poll_interval"] == 60
    assert cfg.gateway["email"]["mark_as_read"] is True
    # Email-specific defaults — tool trace OFF (one trace = one email
    # = spam) and typing_indicator OFF (IMAP has no such concept).
    assert cfg.gateway["email"]["show_tool_trace"] is False
    assert cfg.gateway["email"]["typing_indicator"] is False


def test_gateway_config_deep_merge(tmp_home_no_env: Path) -> None:
    # User overrides ONE telegram flag — all other flags across both
    # platforms must keep their defaults (deep merge, not shallow).
    (tmp_home_no_env / "config.yaml").write_text(
        "gateway:\n"
        "  telegram:\n"
        "    show_tool_trace: false\n"
        "  email:\n"
        "    poll_interval: 30\n"
    )
    cfg = config.load(tmp_home_no_env)
    assert cfg.gateway["telegram"]["show_tool_trace"] is False
    assert cfg.gateway["telegram"]["typing_indicator"] is True  # default kept
    assert cfg.gateway["email"]["poll_interval"] == 30
    assert cfg.gateway["email"]["mark_as_read"] is True          # default kept


def test_is_allowed_env_based(monkeypatch) -> None:
    msg = IncomingMessage(
        platform="telegram", external_user_id="u",
        external_chat_id="12345", text="hi",
    )
    # Unset → rejected (fail closed).
    monkeypatch.delenv("TELEGRAM_ALLOWED_CHAT_IDS", raising=False)
    assert gw_run._is_allowed(msg) is False

    # Not in list → rejected.
    monkeypatch.setenv("TELEGRAM_ALLOWED_CHAT_IDS", "99999")
    assert gw_run._is_allowed(msg) is False

    # In comma-separated list → allowed.
    monkeypatch.setenv("TELEGRAM_ALLOWED_CHAT_IDS", "99999, 12345 ,88888")
    assert gw_run._is_allowed(msg) is True

    # Per-platform: webhook var must not bleed into telegram.
    monkeypatch.setenv("WEBHOOK_ALLOWED_CHAT_IDS", "12345")
    monkeypatch.setenv("TELEGRAM_ALLOWED_CHAT_IDS", "")
    assert gw_run._is_allowed(msg) is False


def test_arg_hint_handles_research_brief() -> None:
    # Regression: research used to fall through to the generic first-arg
    # fallback and show another field instead of the actual brief.
    hint = arg_hint("research", {"depth": "deep", "brief": "best beach hours"})
    assert "best beach hours" in hint
    assert "deep" not in hint


def test_arg_hint_known_tools() -> None:
    assert arg_hint("read_file", {"path": "/tmp/x.py"}) == "/tmp/x.py"
    assert arg_hint("session_search", {"query": "madrid"}) == "madrid"
    assert arg_hint("grep", {"pattern": "TODO"}) == "TODO"


# --------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------


def _fake_subprocess(lines: list[bytes], read_delay: float = 0.0):
    """Return a drop-in for ``asyncio.create_subprocess_exec``.

    The fake yields the given stdout lines (one per ``readline``) then EOF,
    optionally with a small delay so callers that race a typing loop can
    observe at least one tick.
    """

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
    # cd-then-relative-script pattern: only the skill name is captured
    # (the script comes from a relative path after the cd, not from the
    # absolute /skills/.../scripts/foo.py shape).
    cmd = "cd /Users/foo/.alf/skills/creative/joker && python3 scripts/run.py"
    hint = arg_hint("terminal", {"command": cmd})
    assert "skill: joker" in hint


def test_arg_hint_terminal_detects_skill_with_full_script_path() -> None:
    cmd = "python3 /Users/foo/.alf/skills/software/lint/scripts/check.py"
    hint = arg_hint("terminal", {"command": cmd})
    assert "skill: lint" in hint
    assert "check.py" in hint


def test_arg_hint_terminal_detects_skill_in_profile_home() -> None:
    cmd = "python3 /Users/foo/.alf/profiles/work/skills/software/lint/scripts/check.py"
    hint = arg_hint("terminal", {"command": cmd})
    assert "skill: lint" in hint
    assert "check.py" in hint


def test_arg_hint_terminal_falls_back_when_no_skill_path() -> None:
    hint = arg_hint("terminal", {"command": "ls /tmp"})
    assert "skill" not in hint.lower()
    assert "ls /tmp" in hint
