from __future__ import annotations

from pathlib import Path

import pytest

from alpi.config import Config, ToolsConfig
from alpi.engine import Engine
from alpi.host import activity
from alpi.host import events as host_events


@pytest.fixture
def engine(monkeypatch, tmp_home: Path) -> Engine:
    home = tmp_home / "profiles" / "smith"
    home.mkdir(parents=True)
    monkeypatch.setattr("alpi.engine._maybe_load_mcps", lambda _cfg: [])
    monkeypatch.setattr(Engine, "_build_system_prompt", lambda self: "you are alpi")
    monkeypatch.setattr("alpi.ctx_window.resolve", lambda _h, _c, _m: 400_000)
    monkeypatch.setattr("alpi.ledger.check", lambda *a, **kw: None)
    monkeypatch.setattr("alpi.ledger.record", lambda *a, **kw: None)
    cfg = Config(home=home, model="gpt-5.4-mini", tools=ToolsConfig(max_steps_per_turn=3), raw={})
    return Engine(home=home, cfg=cfg)


@pytest.fixture
def captured(monkeypatch):
    activity._reset_for_tests()
    monkeypatch.setattr(activity, "DEBOUNCE_S", 0.0)
    activity._enabled = True
    rows: list[tuple[str, dict]] = []

    def listener(kind: str, data: dict) -> None:
        rows.append((kind, dict(data)))

    host_events.add_listener(listener)
    yield rows
    host_events.remove_listener(listener)
    activity._reset_for_tests()


def test_turn_is_listed_while_running_and_session_changed_tracks_in_flight(
    engine: Engine, monkeypatch, captured,
) -> None:
    seen: dict = {}

    def fake_stream(messages, tools, **kwargs):  # noqa: ANN001
        seen["running"] = activity._running_turns(admin=True)
        yield {"text_delta": "hello"}
        yield {"final": True, "text": "hello", "input_tokens": 1, "output_tokens": 1,
               "cost_usd": 0.0, "tool_calls": []}

    monkeypatch.setattr("alpi.llm.stream", fake_stream)
    engine.run_turn("summarise the deploy", emit=lambda e: None)
    engine.save_session()

    [row] = seen["running"]
    assert row["profile"] == "smith"
    assert row["session_id"] == engine.session.id
    assert row["title"] == "summarise the deploy"
    assert row["source"] == "chat"
    assert activity._running_turns(admin=True) == []

    flights = [d["in_flight"] for k, d in captured if k == "session_changed"]
    assert flights[0] is True
    assert flights[-1] is False
    changes = [d["profile"] for k, d in captured if k == "activity.changed"]
    assert changes == ["smith", "smith"]


def test_turn_leaves_the_activity_list_when_the_turn_raises(
    engine: Engine, monkeypatch, captured,
) -> None:
    def boom(*a, **kw):  # noqa: ANN002, ANN003
        raise RuntimeError("provider down")

    monkeypatch.setattr(Engine, "_run_turn_locked", boom)
    with pytest.raises(RuntimeError):
        engine.run_turn("x", emit=lambda e: None)
    assert activity._running_turns(admin=True) == []
    assert engine.turn_in_flight is False
