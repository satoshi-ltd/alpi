"""relay mode: the engine hard-gates each turn on consulting the designated peer before it can finalize."""

from __future__ import annotations

from pathlib import Path

from alpi import config as config_mod
from alpi.engine import Engine
from alpi.tools.base import ToolResult

FALLBACK_PREFIX = "I can only answer using 'agora'"


def _engine(home: Path, monkeypatch, relay_peer: str | None, max_steps: int | None = None) -> Engine:
    monkeypatch.setattr("alpi.engine._maybe_load_mcps", lambda _cfg: [])
    monkeypatch.setattr(Engine, "_build_system_prompt", lambda self: "you are alpi")
    monkeypatch.setattr("alpi.ctx_window.resolve", lambda _h, _c, _m: 400_000)
    monkeypatch.setattr("alpi.ledger.check", lambda *a, **kw: None)
    monkeypatch.setattr("alpi.ledger.record", lambda *a, **kw: None)
    yaml = "model: gpt-5.4-mini\n"
    if relay_peer:
        yaml += f"relay:\n  peer: {relay_peer}\n"
    if max_steps is not None:
        yaml += f"tools:\n  max_steps_per_turn: {max_steps}\n"
    (home / "config.yaml").write_text(yaml)
    cfg = config_mod.load(home)
    return Engine(home=home, cfg=cfg)


def _mock_peer(monkeypatch, answer: str = "AGORA: an AM owns the account.") -> None:
    def fake_execute(name, args, deny=frozenset()):
        if name == "peer":
            return ToolResult(ok=True, output=answer)
        return ToolResult(ok=True, output="ok")

    monkeypatch.setattr("alpi.tools.execute", fake_execute)


def _final_chunk(text: str, tool_calls=None) -> dict:
    return {
        "final": True, "text": text,
        "input_tokens": 10, "output_tokens": 5, "cost_usd": 0.0,
        "tool_calls": tool_calls or [],
    }


def _peer_call(peer_id: str = "agora") -> list[dict]:
    return [{
        "id": "tc1", "name": "peer",
        "arguments": '{"peer_id": "%s", "prompt": "q"}' % peer_id,
    }]


def _stub_stream(monkeypatch, chunks: list[dict]) -> dict:
    calls = {"i": 0}

    def fake_stream(messages, tools, **kwargs):
        idx = calls["i"]
        if idx >= len(chunks):
            yield _final_chunk("")
            return
        calls["i"] += 1
        chunk = dict(chunks[idx])
        text = chunk.pop("text", "")
        if text:
            yield {"text_delta": text}
        yield chunk

    monkeypatch.setattr("alpi.llm.stream", fake_stream)
    return calls


def _finals(events) -> list[str]:
    return [e.text for e in events if e.kind == "assistant_done" and e.final]


def test_consulting_peer_lets_the_answer_through(tmp_path, monkeypatch) -> None:
    home = tmp_path / "h"
    home.mkdir()
    eng = _engine(home, monkeypatch, "agora")
    _mock_peer(monkeypatch)
    _stub_stream(monkeypatch, [
        _final_chunk("", tool_calls=_peer_call()),
    ])

    events = []
    eng.run_turn("what does an AM do?", emit=events.append)

    assert _finals(events) == ["AGORA: an AM owns the account."]


def test_answering_without_consulting_fails_closed(tmp_path, monkeypatch) -> None:
    home = tmp_path / "h"
    home.mkdir()
    eng = _engine(home, monkeypatch, "agora")
    _mock_peer(monkeypatch)
    _stub_stream(monkeypatch, [
        _final_chunk("An AM does X — straight from my own head."),
        _final_chunk("Still answering from my head."),
    ])

    events = []
    eng.run_turn("what does an AM do?", emit=events.append)

    finals = _finals(events)
    assert len(finals) == 1
    assert finals[0].startswith(FALLBACK_PREFIX)
    assert "from my head" not in finals[0]
    forced = [
        m for m in eng.session.messages
        if m.get("role") == "user" and "must consult peer 'agora'" in str(m.get("content"))
    ]
    assert len(forced) == 1


def test_retry_then_consult_lets_the_answer_through(tmp_path, monkeypatch) -> None:
    home = tmp_path / "h"
    home.mkdir()
    eng = _engine(home, monkeypatch, "agora")
    _mock_peer(monkeypatch)
    _stub_stream(monkeypatch, [
        _final_chunk("From my own head."),
        _final_chunk("", tool_calls=_peer_call()),
    ])

    events = []
    eng.run_turn("what does an AM do?", emit=events.append)

    assert _finals(events) == ["AGORA: an AM owns the account."]


def test_wrong_peer_is_not_executed_and_fails_closed(tmp_path, monkeypatch) -> None:
    home = tmp_path / "h"
    home.mkdir()
    eng = _engine(home, monkeypatch, "agora")
    executed: list = []

    def fake_execute(name, args, deny=frozenset()):
        executed.append((name, args.get("peer_id")))
        return ToolResult(ok=True, output="AGORA: leaked reply")

    monkeypatch.setattr("alpi.tools.execute", fake_execute)
    _stub_stream(monkeypatch, [
        _final_chunk("", tool_calls=_peer_call("someone-else")),
        _final_chunk("Answer from the wrong source."),
    ])

    events = []
    eng.run_turn("q", emit=events.append)

    assert ("peer", "someone-else") not in executed
    finals = _finals(events)
    assert len(finals) == 1
    assert finals[0].startswith(FALLBACK_PREFIX)


def test_empty_peer_reply_fails_closed(tmp_path, monkeypatch) -> None:
    home = tmp_path / "h"
    home.mkdir()
    eng = _engine(home, monkeypatch, "agora")
    monkeypatch.setattr(
        "alpi.tools.execute",
        lambda name, args, deny=frozenset(): ToolResult(ok=True, output=""),
    )
    _stub_stream(monkeypatch, [
        _final_chunk("", tool_calls=_peer_call()),
        _final_chunk("Answering anyway from my head."),
    ])

    events = []
    eng.run_turn("q", emit=events.append)

    finals = _finals(events)
    assert len(finals) == 1
    assert finals[0].startswith(FALLBACK_PREFIX)


def test_step_limit_without_consult_fails_closed(tmp_path, monkeypatch) -> None:
    home = tmp_path / "h"
    home.mkdir()
    eng = _engine(home, monkeypatch, "agora", max_steps=2)
    monkeypatch.setattr(
        "alpi.tools.execute",
        lambda name, args, deny=frozenset(): ToolResult(ok=True, output=""),
    )

    def always_peer(messages, tools, **kwargs):
        yield _final_chunk("", tool_calls=_peer_call())

    monkeypatch.setattr("alpi.llm.stream", always_peer)

    events = []
    eng.run_turn("q", emit=events.append)

    finals = _finals(events)
    assert finals
    assert finals[-1].startswith(FALLBACK_PREFIX)
    assert not any(e.kind == "error" for e in events)


def test_relay_removes_alternative_info_tools_from_the_offer(tmp_path, monkeypatch) -> None:
    home = tmp_path / "h"
    home.mkdir()
    eng = _engine(home, monkeypatch, "agora")
    _mock_peer(monkeypatch)
    captured: dict = {}

    def fake_stream(messages, tools, **kwargs):
        captured["tools"] = tools
        yield _final_chunk("", tool_calls=_peer_call())

    monkeypatch.setattr("alpi.llm.stream", fake_stream)
    eng.run_turn("q", emit=lambda e: None)

    names = {
        (t.get("function") or {}).get("name") or t.get("name")
        for t in captured["tools"]
    }
    assert names == {"peer", "decline"}


def _relay_blocks(eng: Engine) -> list[str]:
    # CL.4 — the relay instruction rides each turn's host-context suffix on the user message; system-message relay blocks no longer exist.
    return [
        str(m.get("content")) for m in eng.session.messages
        if m.get("role") == "user" and "[relay] " in str(m.get("content"))
    ]


def _latest_relay(eng: Engine) -> str:
    blocks = _relay_blocks(eng)
    return blocks[-1] if blocks else ""


def test_relay_directive_rides_each_turn_suffix_once(tmp_path, monkeypatch) -> None:
    home = tmp_path / "h"
    home.mkdir()
    eng = _engine(home, monkeypatch, "agora")
    _mock_peer(monkeypatch)
    for q in ("q1", "q2", "q3"):
        _stub_stream(monkeypatch, [_final_chunk("", tool_calls=_peer_call())])
        eng.run_turn(q, emit=lambda e: None)
    blocks = _relay_blocks(eng)
    assert len(blocks) == 3, "one per turn, riding each user suffix"
    assert all(b.count("[relay] ") == 1 for b in blocks)


def test_disabling_relay_stops_new_directives_and_keeps_history(tmp_path, monkeypatch) -> None:
    home = tmp_path / "h"
    home.mkdir()
    eng = _engine(home, monkeypatch, "agora")
    _mock_peer(monkeypatch)
    _stub_stream(monkeypatch, [_final_chunk("", tool_calls=_peer_call())])
    eng.run_turn("q1", emit=lambda e: None)

    (home / "config.yaml").write_text("model: gpt-5.4-mini\n")
    _stub_stream(monkeypatch, [_final_chunk("Direct answer now.")])
    eng.run_turn("q2", emit=lambda e: None)

    latest_user = [m for m in eng.session.messages if m.get("role") == "user"][-1]
    content = str(latest_user.get("content"))
    assert "read-only relay" not in content, (
        "disabling relay stops the directive from entering new turns; old turns stay history"
    )
    assert "Relay mode is OFF" in content, (
        "an explicit revocation supersedes the stale directives still in history"
    )


def test_changing_relay_peer_targets_new_peer_in_latest_suffix(tmp_path, monkeypatch) -> None:
    home = tmp_path / "h"
    home.mkdir()
    eng = _engine(home, monkeypatch, "agora")
    _mock_peer(monkeypatch)
    _stub_stream(monkeypatch, [_final_chunk("", tool_calls=_peer_call())])
    eng.run_turn("q1", emit=lambda e: None)

    (home / "config.yaml").write_text("model: gpt-5.4-mini\nrelay:\n  peer: beta\n")
    _stub_stream(monkeypatch, [_final_chunk("", tool_calls=_peer_call("beta"))])
    eng.run_turn("q2", emit=lambda e: None)

    latest = _latest_relay(eng)
    assert "'beta'" in latest
    assert "'agora'" not in latest, "the newest turn instructs for the new peer only"


def test_valid_peer_reply_records_run_as_completed(tmp_path, monkeypatch) -> None:
    home = tmp_path / "h"
    home.mkdir()
    eng = _engine(home, monkeypatch, "agora")
    _mock_peer(monkeypatch)
    captured: dict = {}
    monkeypatch.setattr(Engine, "_record_run", lambda self, **kw: captured.update(kw))
    _stub_stream(monkeypatch, [_final_chunk("", tool_calls=_peer_call())])

    eng.run_turn("q", emit=lambda e: None)

    assert captured["turn_completed"] is True


def test_fallback_records_run_as_incomplete(tmp_path, monkeypatch) -> None:
    home = tmp_path / "h"
    home.mkdir()
    eng = _engine(home, monkeypatch, "agora")
    _mock_peer(monkeypatch)
    captured: dict = {}
    monkeypatch.setattr(Engine, "_record_run", lambda self, **kw: captured.update(kw))
    _stub_stream(monkeypatch, [
        _final_chunk("from my head"),
        _final_chunk("still from my head"),
    ])

    eng.run_turn("q", emit=lambda e: None)

    assert captured["turn_completed"] is False


def test_no_relay_means_no_gate(tmp_path, monkeypatch) -> None:
    home = tmp_path / "h"
    home.mkdir()
    eng = _engine(home, monkeypatch, None)
    _mock_peer(monkeypatch)
    _stub_stream(monkeypatch, [_final_chunk("Direct answer, no peer.")])

    events = []
    eng.run_turn("q", emit=events.append)

    assert _finals(events) == ["Direct answer, no peer."]


def test_relay_revocation_survives_the_engine_boundary(tmp_path, monkeypatch) -> None:
    """The host builds a fresh Engine per message — the revocation must come from persisted history, not from in-memory state."""
    from alpi.cli import _hydrate_from_path

    home = tmp_path / "h"
    home.mkdir()
    eng = _engine(home, monkeypatch, "agora")
    _mock_peer(monkeypatch)
    _stub_stream(monkeypatch, [_final_chunk("", tool_calls=_peer_call())])
    eng.run_turn("q1", emit=lambda e: None)
    path = eng.session.save()
    assert path is not None

    (home / "config.yaml").write_text("model: gpt-5.4-mini\n")
    fresh = _engine(home, monkeypatch, None)
    assert _hydrate_from_path(fresh, path) is True
    assert fresh._last_relay_peer == "agora", "relay state recovered from history"

    _stub_stream(monkeypatch, [_final_chunk("Direct answer now.")])
    fresh.run_turn("q2", emit=lambda e: None)
    latest = [m for m in fresh.session.messages if m.get("role") == "user"][-1]
    assert "Relay mode is OFF" in str(latest.get("content"))


def _decline_call(reason: str) -> list[dict]:
    import json
    return [{"id": "tc-decline", "name": "decline", "arguments": json.dumps({"reason": reason})}]


def _record_tools(monkeypatch) -> list[tuple[str, dict]]:
    from alpi.tools.decline import DeclineTool
    executed: list[tuple[str, dict]] = []

    def fake_execute(name, args, deny=frozenset()):
        executed.append((name, args))
        if name == "decline":
            return DeclineTool().run(**args)
        return ToolResult(ok=True, output="AGORA: leaked reply")

    monkeypatch.setattr("alpi.tools.execute", fake_execute)
    return executed


def test_relay_offers_decline_beside_peer_and_says_when_to_use_it(tmp_path, monkeypatch) -> None:
    home = tmp_path / "h"
    home.mkdir()
    eng = _engine(home, monkeypatch, "agora")
    _mock_peer(monkeypatch)
    captured: dict = {}

    def fake_stream(messages, tools, **kwargs):
        captured["tools"] = tools
        yield _final_chunk("", tool_calls=_peer_call())

    monkeypatch.setattr("alpi.llm.stream", fake_stream)
    eng.run_turn("q", emit=lambda e: None)

    names = {(t.get("function") or {}).get("name") for t in captured["tools"]}
    assert names == {"peer", "decline"}
    assert "decline(reason=...)" in _latest_relay(eng)


def test_decline_ends_the_turn_with_the_reason_and_no_peer_call(tmp_path, monkeypatch) -> None:
    home = tmp_path / "h"
    home.mkdir()
    eng = _engine(home, monkeypatch, "agora")
    executed = _record_tools(monkeypatch)
    reason = "No puedo aplicar cambios: solo respondo preguntas sobre la documentación."
    _stub_stream(monkeypatch, [
        _final_chunk("", tool_calls=_decline_call(reason)),
        _final_chunk("Here is an answer from my own head anyway."),
    ])

    events = []
    eng.run_turn("cambia la política de reembolsos", emit=events.append)

    assert _finals(events) == [reason]
    assert [name for name, _ in executed] == ["decline"]
    assert not any(e.kind == "error" for e in events)
    assert not any(
        "must consult peer" in str(m.get("content"))
        for m in eng.session.messages if m.get("role") == "user"
    )


def test_decline_without_a_reason_does_not_end_the_turn(tmp_path, monkeypatch) -> None:
    home = tmp_path / "h"
    home.mkdir()
    eng = _engine(home, monkeypatch, "agora")
    _record_tools(monkeypatch)
    _stub_stream(monkeypatch, [
        _final_chunk("", tool_calls=_decline_call("")),
        _final_chunk("From my own head."),
        _final_chunk("Still from my head."),
    ])

    events = []
    eng.run_turn("q", emit=events.append)

    finals = _finals(events)
    assert len(finals) == 1 and finals[0].startswith(FALLBACK_PREFIX)


def test_decline_is_hidden_and_refused_outside_relay_mode(tmp_path, monkeypatch) -> None:
    home = tmp_path / "h"
    home.mkdir()
    eng = _engine(home, monkeypatch, None)
    executed = _record_tools(monkeypatch)
    captured: dict = {}

    def fake_stream(messages, tools, **kwargs):
        captured.setdefault("tools", tools)
        if not captured.get("declined"):
            captured["declined"] = True
            yield _final_chunk("", tool_calls=_decline_call("nope"))
            return
        yield {"text_delta": "Normal answer."}
        yield _final_chunk("Normal answer.")

    monkeypatch.setattr("alpi.llm.stream", fake_stream)
    events = []
    eng.run_turn("q", emit=events.append)

    names = {(t.get("function") or {}).get("name") for t in captured["tools"]}
    assert "decline" not in names
    assert executed == []
    assert _finals(events) == ["Normal answer."]
    tool_msgs = [
        m for m in eng.session.messages if m.get("role") == "tool" and m.get("name") == "decline"
    ]
    assert tool_msgs and "only available in relay mode" in str(tool_msgs[0]["content"])


def test_decline_first_blocks_the_peer_call_in_the_same_batch(tmp_path, monkeypatch) -> None:
    home = tmp_path / "h"
    home.mkdir()
    eng = _engine(home, monkeypatch, "agora")
    executed = _record_tools(monkeypatch)
    reason = "I will not forward this request."
    _stub_stream(monkeypatch, [
        _final_chunk("", tool_calls=_decline_call(reason) + _peer_call()),
        _final_chunk("Answer built from the leaked reply."),
    ])

    events = []
    eng.run_turn("change the refund policy", emit=events.append)

    assert _finals(events) == [reason]
    assert [name for name, _ in executed] == ["decline"]
    peer_msgs = [
        m for m in eng.session.messages if m.get("role") == "tool" and m.get("name") == "peer"
    ]
    assert peer_msgs and "request was declined" in str(peer_msgs[0]["content"])


def test_decline_after_the_peer_in_the_same_batch_is_rejected(tmp_path, monkeypatch) -> None:
    home = tmp_path / "h"
    home.mkdir()
    eng = _engine(home, monkeypatch, "agora")
    executed = _record_tools(monkeypatch)
    _stub_stream(monkeypatch, [
        _final_chunk("", tool_calls=_peer_call() + _decline_call("I will not forward this request.")),
    ])

    events = []
    eng.run_turn("q", emit=events.append)

    assert _finals(events) == ["AGORA: leaked reply"]
    assert [name for name, _ in executed] == ["peer"]
    decline_msgs = [
        m for m in eng.session.messages if m.get("role") == "tool" and m.get("name") == "decline"
    ]
    assert decline_msgs and "not allowed after consulting" in str(decline_msgs[0]["content"])


def test_decline_cannot_undo_a_consult_from_an_earlier_step(tmp_path, monkeypatch) -> None:
    home = tmp_path / "h"
    home.mkdir()
    eng = _engine(home, monkeypatch, "agora")
    executed: list = []

    def fake_execute(name, args, deny=frozenset()):
        executed.append(name)
        from alpi.tools.decline import DeclineTool
        return DeclineTool().run(**args) if name == "decline" else ToolResult(ok=True, output="")

    monkeypatch.setattr("alpi.tools.execute", fake_execute)
    _stub_stream(monkeypatch, [
        _final_chunk("", tool_calls=_peer_call()),
        _final_chunk("", tool_calls=_decline_call("Never mind, declined.")),
        _final_chunk("From my own head."),
        _final_chunk("Still from my head."),
    ])

    events = []
    eng.run_turn("q", emit=events.append)

    finals = _finals(events)
    assert executed == ["peer"]
    assert len(finals) == 1 and finals[0].startswith(FALLBACK_PREFIX)
    assert "Never mind" not in finals[0]
