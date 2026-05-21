"""CF.1 — Engine.run_turn wraps tool payloads with the untrusted-data
boundary before they re-enter the model's message history. The event /
log surfaces shown to the user keep the raw payload (no marker noise in UI)."""

from __future__ import annotations

from pathlib import Path

import pytest

from alpi import config, home, memory
from alpi.engine import Engine, AgentEvent


@pytest.fixture
def bootstrapped_home(tmp_home_no_env: Path) -> Path:
    home.ensure_home(tmp_home_no_env)
    config.seed_defaults(tmp_home_no_env)
    memory.MemoryStore(tmp_home_no_env).seed_defaults()
    return tmp_home_no_env


def _tool_then_done_stream(write_path: str):
    steps = [
        [
            {"text_delta": "", "reasoning_delta": "", "tool_calls_delta": []},
            {
                "final": True,
                "tool_calls": [{
                    "id": "tc1",
                    "name": "read_file",
                    "arguments": '{"path": "' + write_path + '"}',
                }],
                "input_tokens": 1, "output_tokens": 1, "cost_usd": 0.0,
            },
        ],
        [
            {"text_delta": "done", "reasoning_delta": "", "tool_calls_delta": []},
            {"final": True, "tool_calls": [], "input_tokens": 1, "output_tokens": 1, "cost_usd": 0.0},
        ],
    ]
    call = {"i": 0}

    def _stream(*_a, **_kw):
        idx = call["i"]
        call["i"] += 1
        for frame in steps[idx]:
            yield frame
    return _stream


def test_tool_message_is_wrapped_with_markers(
    bootstrapped_home: Path, monkeypatch
) -> None:
    target = bootstrapped_home / "doc.md"
    target.write_text("# clean content\nno injection here\n")

    from alpi import engine as engine_mod
    monkeypatch.setattr(
        engine_mod.llm, "stream", _tool_then_done_stream(str(target)),
    )

    cfg = config.load(bootstrapped_home)
    engine = Engine(home=bootstrapped_home, cfg=cfg)
    baseline = len(engine.session.messages)

    engine.run_turn("read it", lambda _ev: None)

    new_msgs = engine.session.messages[baseline:]
    tool_msgs = [m for m in new_msgs if m["role"] == "tool"]
    assert tool_msgs, "the tool result should land in messages"
    content = tool_msgs[-1]["content"]
    assert content.startswith("[UNTRUSTED OUTPUT tool=read_file kind=data")
    assert content.rstrip().endswith("[END OUTPUT tool=read_file]")
    assert "# clean content" in content
    assert "SECURITY WARNING" not in content


def test_tool_event_payload_stays_unwrapped(
    bootstrapped_home: Path, monkeypatch
) -> None:
    """Markers are for the model context only. Event streams (desktop, mobile,
    TUI) must keep the original payload so the UI doesn't show marker noise."""
    target = bootstrapped_home / "doc.md"
    target.write_text("plain body\n")

    from alpi import engine as engine_mod
    monkeypatch.setattr(
        engine_mod.llm, "stream", _tool_then_done_stream(str(target)),
    )

    events: list[AgentEvent] = []
    cfg = config.load(bootstrapped_home)
    engine = Engine(home=bootstrapped_home, cfg=cfg)
    engine.run_turn("read it", events.append)

    tool_ends = [e for e in events if e.kind == "tool_end"]
    assert tool_ends, "should see a tool_end event"
    assert tool_ends[-1].output is not None
    assert not tool_ends[-1].output.startswith("[UNTRUSTED OUTPUT")
    assert "plain body" in tool_ends[-1].output


def test_tool_error_message_is_wrapped_with_error_kind(
    bootstrapped_home: Path, monkeypatch
) -> None:
    """Failed tools used to inject `ERROR: ...` into messages without any
    marker. CF.1 wraps the error too — stderr / DB errors / MCP failures are
    also untrusted text from outside the trusted channel."""
    missing = bootstrapped_home / "does_not_exist.md"

    from alpi import engine as engine_mod
    monkeypatch.setattr(
        engine_mod.llm, "stream", _tool_then_done_stream(str(missing)),
    )

    cfg = config.load(bootstrapped_home)
    engine = Engine(home=bootstrapped_home, cfg=cfg)
    baseline = len(engine.session.messages)

    engine.run_turn("read missing", lambda _ev: None)

    new_msgs = engine.session.messages[baseline:]
    tool_msgs = [m for m in new_msgs if m["role"] == "tool"]
    assert tool_msgs
    content = tool_msgs[-1]["content"]
    assert "kind=error" in content.splitlines()[0]
    assert "ERROR:" in content
