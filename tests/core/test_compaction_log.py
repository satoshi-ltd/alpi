"""CH.5 — compaction event log appended to ~/.alpi/profiles/<name>/logs/compaction.jsonl."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from alpi import compaction
from alpi.config import Config, ToolsConfig
from alpi.engine import Engine


def _huge_messages(count: int, char_per_msg: int) -> list[dict]:
    out: list[dict] = []
    for i in range(count):
        out.append({"role": "user", "content": f"u{i} " + "x" * char_per_msg})
        out.append({"role": "assistant", "content": f"a{i} " + "y" * char_per_msg})
    return out


def _patch_engine_deps(monkeypatch, *, ctx_window: int = 400_000) -> None:
    monkeypatch.setattr("alpi.engine._maybe_load_mcps", lambda _cfg: [])
    monkeypatch.setattr(Engine, "_build_system_prompt", lambda self: "you are alpi")
    monkeypatch.setattr(
        "alpi.ctx_window.resolve", lambda _h, _c, _m: ctx_window,
    )

    def fake_stream(messages, tools, **kwargs):
        yield {"text_delta": "ok"}
        yield {
            "final": True,
            "input_tokens": 10,
            "output_tokens": 5,
            "cost_usd": 0.0,
            "tool_calls": [],
        }

    monkeypatch.setattr("alpi.llm.stream", fake_stream)
    monkeypatch.setattr(
        "alpi.llm.complete",
        lambda **kw: SimpleNamespace(content="[BRIEFING]"),
    )
    monkeypatch.setattr("alpi.ledger.check", lambda *a, **kw: None)
    monkeypatch.setattr("alpi.ledger.record", lambda *a, **kw: None)


def test_record_event_appends_jsonl_to_logs(tmp_path: Path) -> None:
    home = tmp_path / "h"
    result = compaction.CompactionResult(
        fired=True,
        tool_truncated=1,
        summarized_messages=12,
        tokens_before=320_000,
        tokens_after=120_000,
    )
    compaction.record_event(
        home,
        result=result,
        trigger="auto",
        session_id="sess-123",
        model="gpt-5.4-mini",
        ctx_window=400_000,
    )

    path = compaction.event_log_path(home)
    assert path == home / "logs" / "compaction.jsonl"
    assert path.exists()

    lines = path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    record = json.loads(lines[0])
    assert record["trigger"] == "auto"
    assert record["session_id"] == "sess-123"
    assert record["model"] == "gpt-5.4-mini"
    assert record["fired"] is True
    assert record["tokens_before"] == 320_000
    assert record["tokens_after"] == 120_000
    assert record["summarized_messages"] == 12
    assert record["tool_truncated"] == 1
    assert isinstance(record["ts"], (int, float))


def test_record_event_is_append_only(tmp_path: Path) -> None:
    home = tmp_path / "h"
    result = compaction.CompactionResult(
        fired=True, tokens_before=100, tokens_after=50,
        summarized_messages=2, tool_truncated=0,
    )
    for _ in range(3):
        compaction.record_event(
            home, result=result, trigger="auto",
            session_id="s", model="m", ctx_window=1000,
        )
    lines = compaction.event_log_path(home).read_text(encoding="utf-8").splitlines()
    assert len(lines) == 3


def test_record_event_never_raises_on_oserror(monkeypatch, tmp_path: Path) -> None:
    home = tmp_path / "h"

    def _boom(*_a, **_kw):
        raise OSError("disk full")

    monkeypatch.setattr(Path, "mkdir", lambda *a, **kw: None)
    monkeypatch.setattr(Path, "open", _boom)

    result = compaction.CompactionResult(
        fired=True, tokens_before=10, tokens_after=5,
        summarized_messages=1, tool_truncated=0,
    )
    compaction.record_event(
        home, result=result, trigger="auto",
        session_id="s", model="m", ctx_window=100,
    )


def test_engine_writes_compaction_log_after_auto_compact(
    monkeypatch, tmp_path: Path,
) -> None:
    home = tmp_path / "h"
    home.mkdir()
    _patch_engine_deps(monkeypatch)

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

    engine.run_turn("una pregunta", emit=lambda _ev: None)

    log_path = compaction.event_log_path(home)
    assert log_path.exists(), "compaction.jsonl must be written"
    lines = log_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) >= 1
    record = json.loads(lines[0])
    assert record["trigger"] == "auto"
    assert record["session_id"] == engine.session.id
    assert record["model"] == "gpt-5.4-mini"
    assert record["fired"] is True
    assert record["ctx_window"] == 400_000


