from __future__ import annotations

import json
from pathlib import Path

import yaml

from alpi.config import Config, ToolsConfig
from alpi.engine import Engine


def test_a_turn_that_calls_pdf_ends_with_the_pdf_attached(monkeypatch, tmp_path: Path) -> None:
    home = tmp_path / "h"
    (home / "sessions").mkdir(parents=True)
    (home / "config.yaml").write_text(yaml.safe_dump({"model": "gpt-5.4-mini"}))
    monkeypatch.setenv("ALPI_HOME", str(home))
    monkeypatch.setattr("alpi.engine._maybe_load_mcps", lambda _cfg: [])
    monkeypatch.setattr(Engine, "_build_system_prompt", lambda self: "alpi")
    monkeypatch.setattr("alpi.ctx_window.resolve", lambda _h, _c, _m: 400_000)
    monkeypatch.setattr("alpi.ledger.check", lambda *a, **kw: None)
    monkeypatch.setattr("alpi.ledger.record", lambda *a, **kw: None)
    engine = Engine(home=home, cfg=Config(home=home, model="gpt-5.4-mini", tools=ToolsConfig(), raw={}))
    calls = {"n": 0}

    def stream(messages, tools, **kwargs):
        calls["n"] += 1
        if calls["n"] == 1:
            yield {
                "final": True, "input_tokens": 1, "output_tokens": 1, "cost_usd": 0.0,
                "tool_calls": [{"id": "p", "name": "pdf", "arguments": json.dumps({
                    "markdown": "# Informe\n\nhola", "name": "informe",
                })}],
            }
        else:
            yield {"final": True, "input_tokens": 1, "output_tokens": 1, "cost_usd": 0.0, "tool_calls": []}

    monkeypatch.setattr("alpi.llm.stream", stream)
    events = []
    engine.run_turn("hazme un pdf", emit=events.append)
    done = [e for e in events if e.kind == "assistant_done"]
    assert done, [e.kind for e in events]
    attached = done[-1].attachments
    assert [(a["name"], a["kind"], a["producer"]) for a in attached] == [("informe.pdf", "pdf", "pdf")]
    assert Path(attached[0]["path"]).read_bytes().startswith(b"%PDF-1.7")
    assert calls["n"] == 2
