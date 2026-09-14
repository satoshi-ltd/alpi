from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from alpi.config import Config, ToolsConfig
from alpi.engine import Engine

MODEL = "openrouter/deepseek/deepseek-v4.1-flash:nitro"


def _write_config(home: Path, ignore: list[str] | None) -> None:
    openrouter: dict = {"models": ["deepseek/deepseek-v4.1-flash:nitro"]}
    if ignore is not None:
        openrouter["ignore"] = ignore
    (home / "config.yaml").write_text(yaml.safe_dump({
        "model": MODEL,
        "providers": {"openrouter": openrouter},
    }))


@pytest.fixture
def engine(monkeypatch, tmp_path: Path) -> Engine:
    home = tmp_path / "h"
    home.mkdir()
    (home / "sessions").mkdir()
    _write_config(home, ["old"])
    monkeypatch.setattr("alpi.engine._maybe_load_mcps", lambda _cfg: [])
    monkeypatch.setattr(Engine, "_build_system_prompt", lambda self: "alpi")
    monkeypatch.setattr("alpi.ctx_window.resolve", lambda _h, _c, _m: 400_000)
    monkeypatch.setattr("alpi.ledger.check", lambda *a, **kw: None)
    monkeypatch.setattr("alpi.ledger.record", lambda *a, **kw: None)
    cfg = Config(
        home=home, model=MODEL,
        tools=ToolsConfig(max_steps_per_turn=6),
        providers={"openrouter": {"models": ["deepseek/deepseek-v4.1-flash:nitro"], "ignore": ["old"]}},
        raw={},
    )
    return Engine(home=home, cfg=cfg)


def _stream_one(text: str):
    yield {"text_delta": text}
    yield {
        "final": True,
        "input_tokens": 1, "output_tokens": 1, "cost_usd": 0.0,
        "tool_calls": [],
    }


def _ignore_sent(kwargs: dict) -> list[str] | None:
    return ((kwargs.get("extra_body") or {}).get("provider") or {}).get("ignore")


@pytest.fixture
def sent(monkeypatch) -> list[dict]:
    seen: list[dict] = []

    def capturing_stream(messages, tools, **kwargs):
        seen.append(kwargs)
        yield from _stream_one("ok")

    monkeypatch.setattr("alpi.llm.stream", capturing_stream)
    return seen


def test_first_turn_sends_the_ignore_list_from_disk(engine: Engine, sent: list[dict]) -> None:
    engine.run_turn("first", emit=lambda _e: None)
    assert _ignore_sent(sent[0]) == ["old"]


def test_changed_ignore_list_reaches_the_next_turn(engine: Engine, sent: list[dict]) -> None:
    engine.run_turn("first", emit=lambda _e: None)
    _write_config(engine.home, ["together"])
    engine.run_turn("second", emit=lambda _e: None)
    assert _ignore_sent(sent[0]) == ["old"]
    assert _ignore_sent(sent[1]) == ["together"]


def test_added_ignore_list_reaches_the_next_turn(engine: Engine, sent: list[dict]) -> None:
    _write_config(engine.home, None)
    engine.run_turn("first", emit=lambda _e: None)
    assert _ignore_sent(sent[0]) is None
    _write_config(engine.home, ["together"])
    engine.run_turn("second", emit=lambda _e: None)
    assert _ignore_sent(sent[1]) == ["together"]


def test_removed_ignore_list_stops_being_sent(engine: Engine, sent: list[dict]) -> None:
    engine.run_turn("first", emit=lambda _e: None)
    assert _ignore_sent(sent[0]) == ["old"]
    _write_config(engine.home, None)
    engine.run_turn("second", emit=lambda _e: None)
    assert _ignore_sent(sent[1]) is None
    assert "ignore" not in engine.cfg.providers["openrouter"]
    assert engine.cfg.providers["openrouter"]["models"] == ["deepseek/deepseek-v4.1-flash:nitro"]


def test_refresh_keeps_the_saved_models_list(engine: Engine, sent: list[dict]) -> None:
    _write_config(engine.home, ["together", "Together", " fireworks "])
    engine.run_turn("first", emit=lambda _e: None)
    assert _ignore_sent(sent[0]) == ["together", "fireworks"]
    assert engine.cfg.providers["openrouter"]["models"] == ["deepseek/deepseek-v4.1-flash:nitro"]
