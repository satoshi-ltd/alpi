"""CH.3 — compaction emits promotion candidates into the queue."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from alpi import compaction, promotion
from alpi.config import Config, ToolsConfig
from alpi.engine import Engine


def _huge_messages(count: int, char_per_msg: int) -> list[dict]:
    out: list[dict] = []
    for i in range(count):
        out.append({"role": "user", "content": f"u{i} " + "x" * char_per_msg})
        out.append({"role": "assistant", "content": f"a{i} " + "y" * char_per_msg})
    return out


def _patch_engine(monkeypatch, *, summary: str, candidates_json: str | None) -> None:
    monkeypatch.setattr("alpi.engine._maybe_load_mcps", lambda _cfg: [])
    monkeypatch.setattr(Engine, "_build_system_prompt", lambda self: "you are alpi")
    monkeypatch.setattr("alpi.ctx_window.resolve", lambda _h, _c, _m: 400_000)

    def fake_stream(messages, tools, **kwargs):
        yield {"text_delta": "ok"}
        yield {"final": True, "input_tokens": 10, "output_tokens": 5,
               "cost_usd": 0.0, "tool_calls": []}

    monkeypatch.setattr("alpi.llm.stream", fake_stream)
    monkeypatch.setattr("alpi.ledger.check", lambda *a, **kw: None)
    monkeypatch.setattr("alpi.ledger.record", lambda *a, **kw: None)

    # The engine makes two llm.complete calls during compaction:
    #   1. summary (system=COMPACT_PROMPT)
    #   2. candidates (system=CANDIDATE_PROMPT)
    # Switch on the system content to return the right text.
    call_log: list[str] = []

    def fake_complete(*, messages, **kwargs):
        system_content = ""
        for m in messages:
            if m.get("role") == "system":
                system_content = m.get("content", "")
                break
        if "promote" in system_content.lower() or "candidates" in system_content.lower():
            call_log.append("candidate")
            return SimpleNamespace(content=candidates_json or "")
        call_log.append("summary")
        return SimpleNamespace(content=summary)

    monkeypatch.setattr("alpi.llm.complete", fake_complete)
    return call_log


def test_parse_candidates_handles_plain_json() -> None:
    raw = (
        '{"candidates": [{"target": "USER.md", "text": "User is X", "confidence": "high"}]}'
    )
    out = compaction.parse_candidates(raw)
    assert out == [{"target": "USER.md", "text": "User is X", "confidence": "high"}]


def test_parse_candidates_handles_fenced_output() -> None:
    raw = '```json\n{"candidates": [{"target": "AGENT.md", "text": "Be concise"}]}\n```'
    out = compaction.parse_candidates(raw)
    assert out and out[0]["target"] == "AGENT.md" and out[0]["confidence"] == "normal"


def test_parse_candidates_rejects_invalid_targets_and_empty_text() -> None:
    raw = (
        '{"candidates": ['
        ' {"target": "USER.md", "text": "good"},'
        ' {"target": "OTHER", "text": "bad-target"},'
        ' {"target": "MEMORY.md", "text": ""}'
        ']}'
    )
    out = compaction.parse_candidates(raw)
    assert [c["text"] for c in out] == ["good"]


def test_parse_candidates_caps_at_five() -> None:
    raw = (
        '{"candidates": ['
        + ",".join(
            f'{{"target":"MEMORY.md","text":"fact {i}"}}' for i in range(10)
        )
        + ']}'
    )
    out = compaction.parse_candidates(raw)
    assert len(out) == 5


def test_parse_candidates_handles_junk() -> None:
    assert compaction.parse_candidates("not json") == []
    assert compaction.parse_candidates("") == []
    assert compaction.parse_candidates('{"candidates": "not a list"}') == []


def test_emit_candidates_pushes_into_queue(tmp_path: Path) -> None:
    raw = (
        '{"candidates": ['
        '{"target":"USER.md","text":"User uses neovim","confidence":"normal"},'
        '{"target":"MEMORY.md","text":"repo uses bun, not npm","confidence":"high"}'
        ']}'
    )

    def fake_llm(_messages, _max_tokens):
        return raw

    n = compaction.emit_candidates_from_summary(
        tmp_path,
        "Briefing: user uses neovim and repo uses bun.",
        call_llm=fake_llm,
        session_id="sess-xyz",
        model="gpt-5.4-mini",
    )
    assert n == 2
    pending = promotion.list_pending(tmp_path)
    assert {c.target for c in pending} == {"USER.md", "MEMORY.md"}
    assert {c.text for c in pending} == {"User uses neovim", "repo uses bun, not npm"}
    assert all(c.source == "compaction" for c in pending)
    assert all(c.session_id == "sess-xyz" for c in pending)


def test_emit_candidates_attaches_operational_state_warning(tmp_path: Path) -> None:
    """Warnings are computed on enqueue so ``promotion_list`` previews are useful."""
    raw = (
        '{"candidates": [{"target":"MEMORY.md",'
        '"text":"chat_id 9876 saw a heartbeat at 2026-05-13T08:00:00Z",'
        '"confidence":"normal"}]}'
    )
    compaction.emit_candidates_from_summary(
        tmp_path,
        "Briefing: heartbeat checks.",
        call_llm=lambda _m, _n: raw,
        session_id="sess-xyz",
        model="m",
    )
    pending = promotion.list_pending(tmp_path)
    assert len(pending) == 1
    assert pending[0].warnings  # at least one warning present
    assert any("operational" in w.lower() or "session" in w.lower() or "id" in w.lower()
               for w in pending[0].warnings)


def test_emit_candidates_swallows_llm_errors(tmp_path: Path) -> None:
    def _boom(*_a, **_kw):
        raise RuntimeError("provider 500")

    n = compaction.emit_candidates_from_summary(
        tmp_path,
        "anything",
        call_llm=_boom,
        session_id="s",
        model="m",
    )
    assert n == 0
    # Queue stays empty — no rows written.
    assert promotion.list_pending(tmp_path) == []


def test_emit_candidates_returns_zero_for_empty_summary(tmp_path: Path) -> None:
    called = []
    def _fn(*_a, **_kw):
        called.append(1)
        return "{}"
    n = compaction.emit_candidates_from_summary(
        tmp_path, "", call_llm=_fn, session_id="s", model="m",
    )
    assert n == 0
    assert called == []  # never called LLM


def test_engine_compaction_emits_candidates_to_queue(
    monkeypatch, tmp_path: Path,
) -> None:
    home = tmp_path / "h"
    home.mkdir()
    candidates_json = (
        '{"candidates": [{"target":"USER.md",'
        '"text":"User works in Madrid","confidence":"high"}]}'
    )
    _patch_engine(monkeypatch, summary="[BRIEFING]", candidates_json=candidates_json)

    cfg = Config(
        home=home,
        model="gpt-5.4-mini",
        tools=ToolsConfig(max_steps_per_turn=2),
        raw={},
    )
    engine = Engine(home=home, cfg=cfg)
    engine.session.messages = (
        [{"role": "system", "content": "you are alpi"}]
        + _huge_messages(40, 40_000)
    )

    engine.run_turn("hola", emit=lambda _ev: None)

    pending = promotion.list_pending(home)
    assert len(pending) == 1
    assert pending[0].target == "USER.md"
    assert pending[0].text == "User works in Madrid"
    assert pending[0].source == "compaction"
    assert pending[0].session_id == engine.session.id


def test_engine_compaction_survives_candidate_llm_failure(
    monkeypatch, tmp_path: Path,
) -> None:
    """A flaky candidate-extraction LLM call must not break compaction itself."""
    home = tmp_path / "h"
    home.mkdir()
    _patch_engine(monkeypatch, summary="[BRIEFING]", candidates_json=None)

    cfg = Config(
        home=home,
        model="gpt-5.4-mini",
        tools=ToolsConfig(max_steps_per_turn=2),
        raw={},
    )
    engine = Engine(home=home, cfg=cfg)
    engine.session.messages = (
        [{"role": "system", "content": "you are alpi"}]
        + _huge_messages(40, 40_000)
    )

    events: list = []
    engine.run_turn("hola", emit=events.append)

    # Compaction event still fires.
    kinds = [e.kind for e in events]
    assert "auto_compact" in kinds
    # No candidates added (empty raw).
    assert promotion.list_pending(home) == []
    # Compaction log still written.
    log = compaction.event_log_path(home)
    assert log.exists()
    line = json.loads(log.read_text(encoding="utf-8").splitlines()[0])
    assert line["fired"] is True
