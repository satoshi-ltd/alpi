from __future__ import annotations

from pathlib import Path

import pytest

from alpi.config import Config, ToolsConfig
from alpi.engine import Engine
from alpi.host.connection_context import ConnectionContext, use


def _final_chunk(text: str, tool_calls=None):
    return {
        "final": True, "text": text,
        "input_tokens": 10, "output_tokens": 5, "cost_usd": 0.0,
        "tool_calls": tool_calls or [],
    }


def _stub_stream(monkeypatch, scripted):
    calls = {"i": 0, "captured_messages": []}

    def fake_stream(messages, tools, **kwargs):
        calls["captured_messages"].append([dict(m) for m in messages])
        idx = calls["i"]
        if idx >= len(scripted):
            yield _final_chunk("")
            return
        calls["i"] += 1
        chunk = dict(scripted[idx])
        text = chunk.pop("text", "")
        if text:
            yield {"text_delta": text}
        yield chunk

    monkeypatch.setattr("alpi.llm.stream", fake_stream)
    return calls


def test_member_role_reaches_tool_execution_through_run_turn(tmp_path: Path, monkeypatch) -> None:
    home = tmp_path / "h"
    home.mkdir()
    monkeypatch.setattr("alpi.engine._maybe_load_mcps", lambda _cfg: [])
    monkeypatch.setattr(Engine, "_build_system_prompt", lambda self: "you are alpi")
    monkeypatch.setattr("alpi.ctx_window.resolve", lambda _h, _c, _m: 400_000)
    monkeypatch.setattr("alpi.ledger.check", lambda *a, **kw: None)
    monkeypatch.setattr("alpi.ledger.record", lambda *a, **kw: None)
    cfg = Config(home=home, model="gpt-5.4-mini", tools=ToolsConfig(max_steps_per_turn=4), raw={})

    member = ConnectionContext(connection_id="c1", device_id="d1", source="remote", role="member")
    with use(member):
        engine = Engine(home=home, cfg=cfg)
    assert engine.connection_context.role == "member"

    calls = _stub_stream(monkeypatch, [
        _final_chunk("creating a skill", tool_calls=[{
            "id": "tc1", "name": "skill",
            "arguments": '{"action": "create", "name": "x", "category": "personal"}',
        }]),
        _final_chunk("understood — I can't do that as a member"),
    ])

    engine.run_turn("make a skill", emit=lambda _e: None)

    tool_msgs = [m for m in calls["captured_messages"][1] if m.get("role") == "tool"]
    joined = " ".join(str(m.get("content", "")) for m in tool_msgs).lower()
    assert "admin" in joined, f"skill create was not role-refused in the turn: {tool_msgs}"
    assert not (home / "skills" / "personal" / "x").exists()


def test_admin_turn_is_not_gated(tmp_path: Path, monkeypatch) -> None:
    home = tmp_path / "h"
    home.mkdir()
    monkeypatch.setattr("alpi.engine._maybe_load_mcps", lambda _cfg: [])
    monkeypatch.setattr(Engine, "_build_system_prompt", lambda self: "you are alpi")
    monkeypatch.setattr("alpi.ctx_window.resolve", lambda _h, _c, _m: 400_000)
    monkeypatch.setattr("alpi.ledger.check", lambda *a, **kw: None)
    monkeypatch.setattr("alpi.ledger.record", lambda *a, **kw: None)
    cfg = Config(home=home, model="gpt-5.4-mini", tools=ToolsConfig(max_steps_per_turn=4), raw={})

    engine = Engine(home=home, cfg=cfg)
    assert engine.connection_context.role == "admin"

    calls = _stub_stream(monkeypatch, [
        _final_chunk("listing", tool_calls=[{
            "id": "tc1", "name": "skill", "arguments": '{"action": "create", "name": "x", "category": "personal"}',
        }]),
        _final_chunk("done"),
    ])
    engine.run_turn("make a skill", emit=lambda _e: None)

    tool_msgs = [m for m in calls["captured_messages"][1] if m.get("role") == "tool"]
    joined = " ".join(str(m.get("content", "")) for m in tool_msgs).lower()
    assert "requires an admin device" not in joined
