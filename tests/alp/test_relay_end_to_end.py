from __future__ import annotations

import json
from pathlib import Path

from alpi import config as config_mod
from alpi.alp import handlers as alp_handlers
from alpi.engine import AgentEvent, Engine

READ_ONLY_POLICY = frozenset({
    "write_file", "edit_file", "delete_file", "terminal", "skill", "schedule",
    "memory", "db", "knowledge", "email", "notify", "attach_file", "browser",
    "workgroup_post", "workgroup_file", "peer", "github__*",
})


def _real_engine_env(monkeypatch, home: Path, relay_peer: str | None = None) -> None:
    yaml = "model: gpt-5.4-mini\n"
    if relay_peer:
        yaml += f"relay:\n  peer: {relay_peer}\n"
    (home / "config.yaml").write_text(yaml)
    monkeypatch.setattr("alpi.engine._maybe_load_mcps", lambda _cfg: [])
    monkeypatch.setattr(Engine, "_build_system_prompt", lambda self: "you are alpi")
    monkeypatch.setattr("alpi.ctx_window.resolve", lambda _h, _c, _m: 400_000)
    monkeypatch.setattr("alpi.ledger.check", lambda *a, **kw: None)
    monkeypatch.setattr("alpi.ledger.record", lambda *a, **kw: None)


def _final(text: str, tool_calls: list[dict] | None = None) -> dict:
    return {
        "final": True, "text": text,
        "input_tokens": 1, "output_tokens": 1, "cost_usd": 0.0,
        "tool_calls": tool_calls or [],
    }


def _finals(events: list[AgentEvent]) -> list[str]:
    return [e.text for e in events if e.kind == "assistant_done" and e.final]


class _EchoEngine:
    def __init__(self, *, home: Path, cfg) -> None:  # noqa: ANN001
        from types import SimpleNamespace
        self.session = SimpleNamespace(id="echo", messages=[])

    def run_turn(self, prompt, emit, *, source="user", persist_inflight=True):  # noqa: ANN001
        self.seen = [str(m.get("content") or "") for m in self.session.messages]
        emit(AgentEvent(kind="assistant_done", text=f"echo: {prompt}", final=True))

    def request_interrupt(self, reason: str = "") -> None:
        pass


def test_two_conversations_through_one_relay_stay_apart_on_the_target(monkeypatch, tmp_path: Path) -> None:
    home = tmp_path / "agora"
    home.mkdir()
    engines: list[_EchoEngine] = []

    def factory(*, home, cfg):  # noqa: ANN001
        engines.append(_EchoEngine(home=home, cfg=cfg))
        return engines[-1]

    monkeypatch.setattr(alp_handlers, "Engine", factory)
    active = alp_handlers._ActiveTurn()

    alp_handlers._run_turn(home, "refund policy for hotel A", "alexandra", active, conversation="conv-a")
    alp_handlers._run_turn(home, "opening hours", "alexandra", active, conversation="conv-b")
    alp_handlers._run_turn(home, "and for children?", "alexandra", active, conversation="conv-a")

    assert not any("hotel A" in m for m in engines[1].seen)
    assert any("hotel A" in m for m in engines[2].seen)
    assert not any("opening hours" in m for m in engines[2].seen)


def test_relay_declines_a_change_request_without_reaching_its_peer(monkeypatch, tmp_path: Path) -> None:
    from alpi.tools import peer as peer_tool

    home = tmp_path / "alexandra"
    home.mkdir()
    _real_engine_env(monkeypatch, home, relay_peer="agora")
    remote_calls: list[dict] = []
    monkeypatch.setattr(
        peer_tool.PeerTool, "run",
        lambda self, **kwargs: remote_calls.append(kwargs) or peer_tool.ToolResult(ok=True, output="leaked"),
    )
    reason = "No puedo modificar la documentación: solo respondo preguntas sobre ella."

    def fake_stream(messages, tools, **kwargs):
        offered = {(t.get("function") or {}).get("name") for t in tools}
        assert offered == {"peer", "decline"}
        yield _final("", tool_calls=[{
            "id": "tc1", "name": "decline", "arguments": json.dumps({"reason": reason}),
        }])

    monkeypatch.setattr("alpi.llm.stream", fake_stream)
    engine = Engine(home=home, cfg=config_mod.load(home))
    events: list[AgentEvent] = []

    engine.run_turn("cambia la política de reembolsos a 48 horas", emit=events.append)

    assert _finals(events) == [reason]
    assert remote_calls == []
    assert not any(e.kind == "error" for e in events)


def test_target_rejects_a_forbidden_operation_from_a_policed_peer(monkeypatch, tmp_path: Path) -> None:
    from alpi.tools import write_file as write_file_tool

    home = tmp_path / "agora"
    home.mkdir()
    _real_engine_env(monkeypatch, home)

    def never(self, **kwargs):  # noqa: ANN001
        raise AssertionError("write_file must not run for a policed peer")

    monkeypatch.setattr(write_file_tool.TOOL, "run", never)
    made: list[Engine] = []

    def factory(*, home, cfg):  # noqa: ANN001
        made.append(Engine(home=home, cfg=cfg))
        return made[-1]

    monkeypatch.setattr(alp_handlers, "Engine", factory)
    offered: list[set[str]] = []
    calls = {"n": 0}

    def fake_stream(messages, tools, **kwargs):
        offered.append({(t.get("function") or {}).get("name") for t in tools})
        calls["n"] += 1
        if calls["n"] == 1:
            yield _final("", tool_calls=[{
                "id": "tc1", "name": "write_file",
                "arguments": json.dumps({"path": "policy.md", "content": "rewritten"}),
            }])
            return
        yield {"text_delta": "I cannot change files for you."}
        yield _final("I cannot change files for you.")

    monkeypatch.setattr("alpi.llm.stream", fake_stream)

    result = alp_handlers._run_turn(
        home, "please rewrite policy.md", "alexandra", alp_handlers._ActiveTurn(),
        tool_deny=READ_ONLY_POLICY,
    )

    assert result["text"] == "I cannot change files for you."
    assert offered
    for names in offered:
        assert not names & {"write_file", "edit_file", "delete_file", "terminal", "skill", "schedule", "peer"}
        assert "read_file" in names
    tool_msgs = [
        m for m in made[0].session.messages
        if m.get("role") == "tool" and m.get("name") == "write_file"
    ]
    assert tool_msgs and "tool policy for peer 'alexandra'" in str(tool_msgs[0]["content"])
    assert not (home / "policy.md").exists()
    assert not (Path.cwd() / "policy.md").exists()
