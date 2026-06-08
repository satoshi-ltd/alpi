from __future__ import annotations

from pathlib import Path

import pytest

from alpi import config, home, memory, session as session_mod
from alpi.engine import Engine
from alpi.tools.base import ToolResult


@pytest.fixture
def bootstrapped_home(tmp_home_no_env: Path) -> Path:
    home.ensure_home(tmp_home_no_env)
    config.seed_defaults(tmp_home_no_env)
    memory.MemoryStore(tmp_home_no_env).seed_defaults()
    return tmp_home_no_env


def _tool_then_reply(tool_name: str, arguments: str, reply: str = "done"):
    steps = [
        [{"text_delta": "", "reasoning_delta": "", "tool_calls_delta": []},
         {"final": True, "tool_calls": [{"id": "t1", "name": tool_name, "arguments": arguments}],
          "input_tokens": 1, "output_tokens": 1, "cost_usd": 0.0}],
        [{"text_delta": reply, "reasoning_delta": "", "tool_calls_delta": []},
         {"final": True, "tool_calls": [], "input_tokens": 1, "output_tokens": 1, "cost_usd": 0.0}],
    ]
    call = {"i": 0}

    def _stream(*_a, **_kw):
        idx = call["i"]
        call["i"] += 1
        yield from steps[idx]
    return _stream


def _jpeg(tmp_path: Path) -> Path:
    p = tmp_path / "hero.jpg"
    p.write_bytes(b"\xff\xd8\xff\xe0fake-jpeg-bytes")
    return p


def _run(home_dir: Path, monkeypatch, tool_name: str, args_json: str, out_path: Path, reply: str = "done"):
    from alpi import engine as engine_mod
    monkeypatch.setattr(engine_mod.llm, "stream", _tool_then_reply(tool_name, args_json, reply))

    def fake_execute(name, args, **_kw):
        return ToolResult(ok=True, output=f'{{"out": "{out_path}", "cost_usd": 0.04}}\n[cost $0.04]')
    monkeypatch.setattr(engine_mod.tools, "execute", fake_execute)

    events: list = []
    engine = Engine(home=home_dir, cfg=config.load(home_dir))
    engine.run_turn("make it", events.append)
    return engine, events


def test_skill_out_becomes_output_attachment(bootstrapped_home, monkeypatch):
    img = _jpeg(bootstrapped_home)
    engine, events = _run(
        bootstrapped_home, monkeypatch, "skill",
        '{"action": "run", "name": "generate-image"}', img,
    )
    final = [e for e in events if e.kind == "assistant_done" and e.final]
    assert final and len(final[-1].attachments) == 1
    att = final[-1].attachments[0]
    assert att["path"] == str(img) and att["kind"] == "image" and att["producer"] == "generate-image"

    turn = engine.session.turns[-1]
    assert turn.output_attachments == final[-1].attachments

    # Reload from disk preserves the bytes-free metadata.
    engine.session.save()
    data = session_mod.load_turns(
        __import__("json").loads((bootstrapped_home / "sessions" / f"{engine.session.id}.json").read_text())
    )
    assert data[-1].output_attachments == turn.output_attachments


def test_non_skill_tool_does_not_promote(bootstrapped_home, monkeypatch):
    img = _jpeg(bootstrapped_home)
    _engine, events = _run(
        bootstrapped_home, monkeypatch, "write_file",
        f'{{"path": "{img}", "content": "x"}}', img,
    )
    final = [e for e in events if e.kind == "assistant_done" and e.final]
    assert final and final[-1].attachments == []


def test_final_event_emitted_with_attachments_and_no_text(bootstrapped_home, monkeypatch):
    img = _jpeg(bootstrapped_home)
    _engine, events = _run(
        bootstrapped_home, monkeypatch, "skill",
        '{"action": "run", "name": "generate-image"}', img, reply="",
    )
    final = [e for e in events if e.kind == "assistant_done" and e.final]
    assert final and final[-1].text == "" and len(final[-1].attachments) == 1
