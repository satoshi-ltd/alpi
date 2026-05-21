"""CF.2 — Engine.run_turn actually drains the mutation buffer, emits the
host event with profile + session_id, and injects the footer before the
next model step."""

from __future__ import annotations

from pathlib import Path

import pytest

from alpi import config, home, memory
from alpi.engine import Engine


@pytest.fixture
def bootstrapped_home(tmp_home_no_env: Path) -> Path:
    home.ensure_home(tmp_home_no_env)
    config.seed_defaults(tmp_home_no_env)
    memory.MemoryStore(tmp_home_no_env).seed_defaults()
    return tmp_home_no_env


def _two_step_stream(write_path: str, write_content: str):
    steps = [
        # Step 1: model decides to call write_file
        [
            {"text_delta": "", "reasoning_delta": "", "tool_calls_delta": []},
            {
                "final": True,
                "tool_calls": [{
                    "id": "tc1",
                    "name": "write_file",
                    "arguments": (
                        '{"path": "' + write_path + '", '
                        '"content": "' + write_content + '"}'
                    ),
                }],
                "input_tokens": 1,
                "output_tokens": 1,
                "cost_usd": 0.0,
            },
        ],
        # Step 2: model wraps with a final assistant message
        [
            {"text_delta": "done", "reasoning_delta": "", "tool_calls_delta": []},
            {
                "final": True,
                "tool_calls": [],
                "input_tokens": 1,
                "output_tokens": 1,
                "cost_usd": 0.0,
            },
        ],
    ]
    call = {"i": 0}

    def _stream(*_a, **_kw):
        idx = call["i"]
        call["i"] += 1
        for frame in steps[idx]:
            yield frame
    return _stream


def test_run_turn_emits_event_with_profile_session_and_injects_footer(
    bootstrapped_home: Path, monkeypatch
) -> None:
    target = bootstrapped_home / "notes.txt"
    captured: list[tuple[str, dict]] = []

    from alpi import engine as engine_mod
    from alpi.host import events as host_events
    monkeypatch.setattr(
        engine_mod.llm, "stream",
        _two_step_stream(str(target), "hello from the engine"),
    )

    def fake_emit(kind: str, data: dict | None = None) -> None:
        captured.append((kind, data or {}))
    monkeypatch.setattr(host_events, "emit", fake_emit)

    cfg = config.load(bootstrapped_home)
    engine = Engine(home=bootstrapped_home, cfg=cfg)
    baseline = len(engine.session.messages)

    engine.run_turn("write notes please", lambda _ev: None)

    assert target.exists()
    assert target.read_text() == "hello from the engine"

    mut_events = [(k, d) for k, d in captured if k == "file_mutations"]
    assert len(mut_events) == 1
    _, payload = mut_events[0]
    assert payload["profile"] == "default"
    assert payload["session_id"] == engine.session.id
    assert len(payload["mutations"]) == 1
    assert payload["mutations"][0]["op"] == "create"
    assert payload["mutations"][0]["path"] == str(target)

    new_msgs = engine.session.messages[baseline:]
    footers = [
        m for m in new_msgs
        if m["role"] == "system" and m["content"].startswith("[file_mutations]")
    ]
    assert len(footers) == 1
    assert str(target) in footers[0]["content"]

    tool_msgs = [m for m in new_msgs if m["role"] == "tool"]
    assert tool_msgs, "tool result should be in messages"
    assert new_msgs.index(tool_msgs[-1]) < new_msgs.index(footers[0])


def test_run_turn_with_no_mutations_emits_nothing_and_appends_no_footer(
    bootstrapped_home: Path, monkeypatch
) -> None:
    captured: list[tuple[str, dict]] = []

    from alpi import engine as engine_mod
    from alpi.host import events as host_events

    def _stream_final(*_a, **_kw):
        yield {"text_delta": "ok", "reasoning_delta": "", "tool_calls_delta": []}
        yield {
            "final": True, "tool_calls": [],
            "input_tokens": 1, "output_tokens": 1, "cost_usd": 0.0,
        }
    monkeypatch.setattr(engine_mod.llm, "stream", _stream_final)

    def fake_emit(kind: str, data: dict | None = None) -> None:
        captured.append((kind, data or {}))
    monkeypatch.setattr(host_events, "emit", fake_emit)

    cfg = config.load(bootstrapped_home)
    engine = Engine(home=bootstrapped_home, cfg=cfg)
    baseline = len(engine.session.messages)

    engine.run_turn("hola", lambda _ev: None)

    assert not any(k == "file_mutations" for k, _ in captured)
    new_msgs = engine.session.messages[baseline:]
    assert not any(
        m["role"] == "system" and m["content"].startswith("[file_mutations]")
        for m in new_msgs
    )
