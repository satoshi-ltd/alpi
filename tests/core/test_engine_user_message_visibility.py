"""Pin contract: a paired client reading session.json mid-turn sees the user message immediately, not when the LLM finishes."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from alpi.config import Config, ToolsConfig
from alpi.engine import Engine


@pytest.fixture
def engine(monkeypatch, tmp_path: Path) -> Engine:
    home = tmp_path / "h"
    home.mkdir()
    (home / "sessions").mkdir()
    monkeypatch.setattr("alpi.engine._maybe_load_mcps", lambda _cfg: [])
    monkeypatch.setattr(Engine, "_build_system_prompt", lambda self: "alpi")
    monkeypatch.setattr("alpi.ctx_window.resolve", lambda _h, _c, _m: 400_000)
    monkeypatch.setattr("alpi.ledger.check", lambda *a, **kw: None)
    monkeypatch.setattr("alpi.ledger.record", lambda *a, **kw: None)
    cfg = Config(
        home=home, model="gpt-5.4-mini",
        tools=ToolsConfig(max_steps_per_turn=6), raw={},
    )
    return Engine(home=home, cfg=cfg)


def _final(text: str, tool_calls=None):
    return {
        "final": True, "text": text,
        "input_tokens": 1, "output_tokens": 1, "cost_usd": 0.0,
        "tool_calls": tool_calls or [],
    }


def _stream_one(text: str, tool_calls=None):
    # text_delta BEFORE final — engine accumulates from text_delta; a final-only stub yields empty content.
    if text:
        yield {"text_delta": text}
    chunk = dict(_final(text, tool_calls))
    chunk.pop("text", None)
    yield chunk


def test_user_message_is_persisted_before_assistant_runs(
    engine: Engine, monkeypatch,
) -> None:
    snapshots: list[dict] = []
    sess_path = engine.home / engine.session.subdir / f"{engine.session.id}.json"

    def snapshotting_stream(messages, tools, **kwargs):
        if sess_path.exists():
            snapshots.append(json.loads(sess_path.read_text()))
        yield from _stream_one("done")

    monkeypatch.setattr("alpi.llm.stream", snapshotting_stream)

    engine.run_turn("research awake", emit=lambda _e: None)

    assert snapshots, "session.json must exist before the LLM stream starts"
    mid = snapshots[0]
    assert len(mid["turns"]) == 1
    assert mid["turns"][0]["user"] == "research awake"
    assert mid["turns"][0]["assistant"] == ""
    assert mid["turns"][0]["tools"] == []


def test_no_save_callers_do_not_persist_inflight_stub(
    engine: Engine, monkeypatch,
) -> None:
    # CLI --no-save (schedules) must not create session files for ephemeral runs.
    sess_path = engine.home / engine.session.subdir / f"{engine.session.id}.json"
    snapshots: list[bool] = []

    def snapshotting_stream(messages, tools, **kwargs):
        snapshots.append(sess_path.exists())
        yield from _stream_one("done")

    monkeypatch.setattr("alpi.llm.stream", snapshotting_stream)

    engine.run_turn(
        "scheduled work", emit=lambda _e: None, persist_inflight=False,
    )

    assert snapshots == [False]
    assert not sess_path.exists()


def test_final_turn_replaces_stub_not_appends(engine: Engine, monkeypatch) -> None:
    def fake_stream(messages, tools, **kwargs):
        yield from _stream_one("reply text")

    monkeypatch.setattr("alpi.llm.stream", fake_stream)

    engine.run_turn("hello", emit=lambda _e: None)
    engine.save_session()

    sess_path = engine.home / engine.session.subdir / f"{engine.session.id}.json"
    final = json.loads(sess_path.read_text())
    assert len(final["turns"]) == 1
    assert final["turns"][0]["user"] == "hello"
    assert final["turns"][0]["assistant"] == "reply text"


def test_interrupted_turn_still_leaves_one_turn(
    engine: Engine, monkeypatch,
) -> None:
    def fake_stream(messages, tools, **kwargs):
        engine.request_interrupt()
        yield from _stream_one("partial")

    monkeypatch.setattr("alpi.llm.stream", fake_stream)
    engine.run_turn("research", emit=lambda _e: None)
    engine.save_session()

    sess_path = engine.home / engine.session.subdir / f"{engine.session.id}.json"
    final = json.loads(sess_path.read_text())
    assert len(final["turns"]) == 1
    assert final["turns"][0]["user"] == "research"
