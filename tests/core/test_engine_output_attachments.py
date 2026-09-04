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


def test_attach_file_out_becomes_output_attachment(bootstrapped_home, monkeypatch):
    md = bootstrapped_home / "report.md"
    md.write_text("# Report\n\nHello.\n")
    engine, events = _run(
        bootstrapped_home, monkeypatch, "attach_file",
        f'{{"path": "{md}"}}', md,
    )
    final = [e for e in events if e.kind == "assistant_done" and e.final]
    assert final and len(final[-1].attachments) == 1
    att = final[-1].attachments[0]
    assert att["path"] == str(md) and att["kind"] == "text" and att["producer"] == "attach_file"


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


def _reply_only(text="ok"):
    frames = [{"text_delta": text, "reasoning_delta": "", "tool_calls_delta": []},
              {"final": True, "tool_calls": [], "input_tokens": 1, "output_tokens": 1, "cost_usd": 0.0}]

    def _stream(*_a, **_kw):
        yield from frames
    return _stream


def test_chat_turn_persists_inbound_attachment_path(bootstrapped_home, monkeypatch):
    from alpi import engine as engine_mod
    img = bootstrapped_home / "shot.png"
    img.write_bytes(b"\x89PNG\r\n\x1a\nfake-png-bytes")
    monkeypatch.setattr(engine_mod.llm, "stream", _reply_only())
    monkeypatch.setattr("alpi.attachments.vision_status", lambda _m: "yes")

    engine = Engine(home=bootstrapped_home, cfg=config.load(bootstrapped_home))
    engine.run_turn("look at this", lambda _e: None,
                    attachments=[{"path": str(img), "mime": "image/png"}])

    att = engine.session.turns[-1].attachments
    assert att and att[0]["path"] == str(img)
    assert att[0]["name"] == "shot.png" and "size" in att[0]


def _reasoning_then_reply(reasoning: str, reply: str):
    frames = [
        {"text_delta": "", "reasoning_delta": reasoning, "tool_calls_delta": []},
        {"text_delta": reply, "reasoning_delta": "", "tool_calls_delta": []},
        {"final": True, "tool_calls": [], "input_tokens": 1, "output_tokens": 1, "cost_usd": 0.0},
    ]

    def _stream(*_a, **_kw):
        yield from frames
    return _stream


def test_reasoning_delta_persisted_for_no_tool_turn(bootstrapped_home, monkeypatch):
    from alpi import engine as engine_mod
    monkeypatch.setattr(engine_mod.llm, "stream",
                        _reasoning_then_reply("I will reason step by step.", "The answer."))

    engine = Engine(home=bootstrapped_home, cfg=config.load(bootstrapped_home))
    engine.run_turn("think hard", lambda _e: None)

    turn = engine.session.turns[-1]
    assert turn.reasoning == "I will reason step by step."
    assert turn.assistant == "The answer."
    assert turn.reasoned_s >= 0

    engine.session.save()
    import json
    data = session_mod.load_turns(
        json.loads((bootstrapped_home / "sessions" / f"{engine.session.id}.json").read_text())
    )
    assert data[-1].reasoning == "I will reason step by step."


def test_reasoned_s_excludes_tool_execution(bootstrapped_home, monkeypatch):
    from alpi import engine as engine_mod
    clock = {"t": 1000.0}
    monkeypatch.setattr(engine_mod.time, "time", lambda: clock["t"])
    monkeypatch.setattr(engine_mod.llm, "stream",
                        _tool_then_reply("write_file", '{"path": "x", "content": "y"}'))

    def jumpy_execute(_name, _args, **_kw):
        clock["t"] += 100.0
        return ToolResult(ok=True, output="ok")
    monkeypatch.setattr(engine_mod.tools, "execute", jumpy_execute)

    engine = Engine(home=bootstrapped_home, cfg=config.load(bootstrapped_home))
    engine.run_turn("do it", lambda _e: None)

    assert engine.session.turns[-1].reasoned_s == 0.0


def test_reasoned_s_excludes_final_answer_streaming(bootstrapped_home, monkeypatch):
    from alpi import engine as engine_mod
    clock = {"t": 1000.0}
    monkeypatch.setattr(engine_mod.time, "time", lambda: clock["t"])

    def _stream(*_a, **_kw):
        clock["t"] = 1000.0
        yield {"text_delta": "", "reasoning_delta": "thinking", "tool_calls_delta": []}
        clock["t"] = 1005.0
        yield {"text_delta": "the long final answer", "reasoning_delta": "", "tool_calls_delta": []}
        clock["t"] = 1020.0
        yield {"final": True, "tool_calls": [], "input_tokens": 1, "output_tokens": 1, "cost_usd": 0.0}
    monkeypatch.setattr(engine_mod.llm, "stream", _stream)

    engine = Engine(home=bootstrapped_home, cfg=config.load(bootstrapped_home))
    engine.run_turn("think", lambda _e: None)

    turn = engine.session.turns[-1]
    assert turn.reasoned_s == 5.0
    assert turn.reasoning == "thinking"


def _k_tools_then_reply(k: int):
    steps = []
    for i in range(k):
        steps.append([
            {"text_delta": "", "reasoning_delta": "", "tool_calls_delta": []},
            {"final": True, "tool_calls": [{"id": f"t{i}", "name": "noop", "arguments": "{}"}],
             "input_tokens": 1, "output_tokens": 1, "cost_usd": 0.0},
        ])
    steps.append([
        {"text_delta": "done", "reasoning_delta": "", "tool_calls_delta": []},
        {"final": True, "tool_calls": [], "input_tokens": 1, "output_tokens": 1, "cost_usd": 0.0},
    ])
    call = {"i": 0}

    def _stream(*_a, **_kw):
        idx = call["i"]
        call["i"] += 1
        yield from steps[idx]
    return _stream


def test_free_model_keeps_default_step_ceiling(bootstrapped_home, monkeypatch):
    from alpi import engine as engine_mod
    cfg = config.load(bootstrapped_home)
    assert cfg.tools.max_steps_per_turn == 100
    monkeypatch.setattr(engine_mod.llm, "is_free_model", lambda _m: True)
    monkeypatch.setattr(engine_mod.llm, "stream", _k_tools_then_reply(150))
    monkeypatch.setattr(engine_mod.tools, "execute", lambda *_a, **_k: ToolResult(ok=True, output="ok"))

    engine = Engine(home=bootstrapped_home, cfg=cfg)
    engine.run_turn("do it", lambda _e: None)

    assert len(engine.session.turns[-1].tools) == 100


def test_budget_capped_profile_keeps_default_step_ceiling(bootstrapped_home, monkeypatch):
    from alpi import engine as engine_mod
    cfg_path = bootstrapped_home / "config.yaml"
    cfg_path.write_text(cfg_path.read_text() + "\nbudget:\n  daily_usd: 12.0\n")
    cfg = config.load(bootstrapped_home)
    assert cfg.tools.max_steps_per_turn == 100
    assert cfg.budget == {"daily_usd": 12.0}
    monkeypatch.setattr(engine_mod.llm, "is_free_model", lambda _m: False)
    monkeypatch.setattr(engine_mod.llm, "stream", _k_tools_then_reply(150))
    monkeypatch.setattr(engine_mod.tools, "execute", lambda *_a, **_k: ToolResult(ok=True, output="ok"))

    engine = Engine(home=bootstrapped_home, cfg=cfg)
    engine.run_turn("do it", lambda _e: None)

    assert len(engine.session.turns[-1].tools) == 100


def test_no_budget_paid_model_keeps_default_ceiling(bootstrapped_home, monkeypatch):
    from alpi import engine as engine_mod
    cfg = config.load(bootstrapped_home)
    assert cfg.tools.max_steps_per_turn == 100
    cfg.budget = {}
    monkeypatch.setattr(engine_mod.llm, "is_free_model", lambda _m: False)
    monkeypatch.setattr(engine_mod.llm, "stream", _k_tools_then_reply(150))
    monkeypatch.setattr(engine_mod.tools, "execute", lambda *_a, **_k: ToolResult(ok=True, output="ok"))

    engine = Engine(home=bootstrapped_home, cfg=cfg)
    engine.run_turn("do it", lambda _e: None)

    assert len(engine.session.turns[-1].tools) == 100


def test_explicit_cap_respected_even_with_budget(bootstrapped_home, monkeypatch):
    from alpi import engine as engine_mod
    cfg = config.load(bootstrapped_home)
    cfg.tools.max_steps_per_turn = 3
    cfg.raw["tools"] = {"max_steps_per_turn": 3}
    cfg.budget = {"daily_usd": 12.0}
    monkeypatch.setattr(engine_mod.llm, "is_free_model", lambda _m: False)
    monkeypatch.setattr(engine_mod.llm, "stream", _k_tools_then_reply(10))
    monkeypatch.setattr(engine_mod.tools, "execute", lambda *_a, **_k: ToolResult(ok=True, output="ok"))

    engine = Engine(home=bootstrapped_home, cfg=cfg)
    engine.run_turn("do it", lambda _e: None)

    assert len(engine.session.turns[-1].tools) == 3


def test_explicit_cap_respected_even_for_free_model(bootstrapped_home, monkeypatch):
    from alpi import engine as engine_mod
    cfg = config.load(bootstrapped_home)
    cfg.tools.max_steps_per_turn = 3
    cfg.raw["tools"] = {"max_steps_per_turn": 3}
    monkeypatch.setattr(engine_mod.llm, "is_free_model", lambda _m: True)
    monkeypatch.setattr(engine_mod.llm, "stream", _k_tools_then_reply(10))
    monkeypatch.setattr(engine_mod.tools, "execute", lambda *_a, **_k: ToolResult(ok=True, output="ok"))

    engine = Engine(home=bootstrapped_home, cfg=cfg)
    engine.run_turn("do it", lambda _e: None)

    assert len(engine.session.turns[-1].tools) == 3


def test_non_default_cap_with_empty_raw_is_not_lifted(bootstrapped_home, monkeypatch):
    from alpi import engine as engine_mod
    cfg = config.load(bootstrapped_home)
    cfg.tools.max_steps_per_turn = 3
    cfg.raw = {}
    monkeypatch.setattr(engine_mod.llm, "is_free_model", lambda _m: True)
    monkeypatch.setattr(engine_mod.llm, "stream", _k_tools_then_reply(10))
    monkeypatch.setattr(engine_mod.tools, "execute", lambda *_a, **_k: ToolResult(ok=True, output="ok"))

    engine = Engine(home=bootstrapped_home, cfg=cfg)
    engine.run_turn("do it", lambda _e: None)

    assert len(engine.session.turns[-1].tools) == 3
