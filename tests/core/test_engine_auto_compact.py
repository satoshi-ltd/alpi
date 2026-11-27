"""End-to-end test: engine fires the auto-compact pipeline before LLM call."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace


from alpi.engine import Engine


def _huge_messages(count: int, char_per_msg: int) -> list[dict]:
    out = []
    for i in range(count):
        out.append({"role": "user", "content": f"u{i} " + "x" * char_per_msg})
        out.append({"role": "assistant", "content": f"a{i} " + "y" * char_per_msg})
    return out


def test_engine_emits_auto_compact_before_first_llm_call(monkeypatch, tmp_path: Path) -> None:
    home = tmp_path / "h"
    home.mkdir()

    # Bypass MCP loading + system-prompt build (both touch disk and the network).
    monkeypatch.setattr("alpi.engine._maybe_load_mcps", lambda _cfg: [])
    monkeypatch.setattr(Engine, "_build_system_prompt", lambda self: "you are alpi")

    # Pretend any model resolves to a 400k window so the threshold is predictable.
    monkeypatch.setattr(
        "alpi.ctx_window.resolve", lambda _h, _c, _m: 400_000,
    )

    # Stub ``llm.stream`` so the engine doesn't actually call a provider.
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
        lambda **kw: SimpleNamespace(content="[BRIEFING from stub]"),
    )

    # Avoid budget side-effects on disk.
    monkeypatch.setattr("alpi.ledger.check", lambda *a, **kw: None)
    monkeypatch.setattr("alpi.ledger.record", lambda *a, **kw: None)

    from alpi.config import Config, ToolsConfig
    cfg = Config(
        home=home,
        model="gpt-5.4-mini",
        tools=ToolsConfig(max_steps_per_turn=2),
        raw={},
    )
    engine = Engine(home=home, cfg=cfg)

    # Seed a fat history that crosses the trigger ratio (0.75 of 400k = 300k).
    # 80 messages * ~40k chars / 4 = ~800k tokens — well past threshold.
    engine.session.messages = (
        [{"role": "system", "content": "you are alpi"}]
        + _huge_messages(40, 40_000)
    )

    events: list = []
    engine.run_turn("una pregunta corta", emit=events.append)

    kinds = [e.kind for e in events]
    assert "auto_compact" in kinds, kinds
    compact_event = next(e for e in events if e.kind == "auto_compact")
    assert compact_event.tokens_in > compact_event.tokens_out > 0
    assert "compacted" in compact_event.text.lower()


def test_engine_does_not_compact_when_under_threshold(monkeypatch, tmp_path: Path) -> None:
    home = tmp_path / "h"
    home.mkdir()

    monkeypatch.setattr("alpi.engine._maybe_load_mcps", lambda _cfg: [])
    monkeypatch.setattr(Engine, "_build_system_prompt", lambda self: "you are alpi")
    monkeypatch.setattr(
        "alpi.ctx_window.resolve", lambda _h, _c, _m: 400_000,
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
    summary_called = {"n": 0}

    def _surprise(**_kw):
        summary_called["n"] += 1
        return SimpleNamespace(content="should not run")

    monkeypatch.setattr("alpi.llm.complete", _surprise)
    monkeypatch.setattr("alpi.ledger.check", lambda *a, **kw: None)
    monkeypatch.setattr("alpi.ledger.record", lambda *a, **kw: None)

    from alpi.config import Config, ToolsConfig
    cfg = Config(
        home=home,
        model="gpt-5.4-mini",
        tools=ToolsConfig(max_steps_per_turn=2),
        raw={},
    )
    engine = Engine(home=home, cfg=cfg)

    events: list = []
    engine.run_turn("hola", emit=events.append)

    kinds = [e.kind for e in events]
    assert "auto_compact" not in kinds, kinds
    assert summary_called["n"] == 0


def test_a_turn_budgets_and_sends_one_ollama_context_size(monkeypatch, tmp_path: Path) -> None:
    import importlib

    ollama = importlib.import_module("alpi.providers.ollama")
    home = tmp_path / "h"
    home.mkdir()
    monkeypatch.setattr("alpi.engine._maybe_load_mcps", lambda _cfg: [])
    monkeypatch.setattr(Engine, "_build_system_prompt", lambda self: "you are alpi")
    monkeypatch.setattr("alpi.ledger.check", lambda *a, **kw: None)
    monkeypatch.setattr("alpi.ledger.record", lambda *a, **kw: None)
    answers = iter([32768, 8192, 8192])
    monkeypatch.setattr(ollama, "_num_ctx", lambda key: next(answers))
    sent: list[int] = []

    def fake_stream(messages, tools, **kwargs):
        sent.append(ollama.call_kwargs(kwargs)["num_ctx"])
        yield {"text_delta": "ok"}
        yield {"final": True, "input_tokens": 10, "output_tokens": 5, "cost_usd": 0.0, "tool_calls": []}

    monkeypatch.setattr("alpi.llm.stream", fake_stream)
    budgets: list[int] = []
    real_should = __import__("alpi.compaction", fromlist=["should_compact"]).should_compact
    monkeypatch.setattr(
        "alpi.compaction.should_compact",
        lambda messages, extra, window, policy: budgets.append(window) or real_should(messages, extra, window, policy),
    )

    from alpi.config import Config, ToolsConfig
    cfg = Config(
        home=home, model="box/qwen3:8b", tools=ToolsConfig(max_steps_per_turn=2), raw={},
        providers={"ollama": [{"name": "box", "url": "http://box:11434"}]},
    )
    engine = Engine(home=home, cfg=cfg)
    engine.run_turn("hi", lambda event: None)

    assert budgets and set(budgets) == {32768} and sent == [32768]
    assert ollama._TURN_SIZES.get() is None
