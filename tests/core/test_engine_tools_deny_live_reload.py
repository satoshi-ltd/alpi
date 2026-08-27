"""Pin contract: ``tools.deny`` is re-read from disk on every turn, and the per-turn refresh path does not bind names it then fails to reference (regression for a ``fresh_budget`` typo that crashed every run)."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from alpi.config import Config, ToolsConfig
from alpi.engine import Engine
from alpi.tools.base import Tool, ToolResult


@pytest.fixture
def engine(monkeypatch, tmp_path: Path) -> Engine:
    home = tmp_path / "h"
    home.mkdir()
    (home / "sessions").mkdir()
    (home / "config.yaml").write_text(yaml.safe_dump({
        "model": "gpt-5.4-mini",
        "tools": {"deny": ["write_file"]},
    }))
    monkeypatch.setattr("alpi.engine._maybe_load_mcps", lambda _cfg: [])
    monkeypatch.setattr(Engine, "_build_system_prompt", lambda self: "alpi")
    monkeypatch.setattr("alpi.ctx_window.resolve", lambda _h, _c, _m: 400_000)
    monkeypatch.setattr("alpi.ledger.check", lambda *a, **kw: None)
    monkeypatch.setattr("alpi.ledger.record", lambda *a, **kw: None)
    cfg = Config(
        home=home, model="gpt-5.4-mini",
        tools=ToolsConfig(max_steps_per_turn=6, deny=["write_file"]),
        raw={},
    )
    return Engine(home=home, cfg=cfg)


def _stream_one(text: str):
    if text:
        yield {"text_delta": text}
    yield {
        "final": True,
        "input_tokens": 1, "output_tokens": 1, "cost_usd": 0.0,
        "tool_calls": [],
    }


def test_turn_runs_without_nameerror_on_refresh_block(
    engine: Engine, monkeypatch,
) -> None:
    """Smoke test: the per-turn config refresh must not reference an undefined name. A typo here used to crash every turn before any tool ran."""
    monkeypatch.setattr(
        "alpi.llm.stream", lambda *a, **kw: _stream_one("ok"),
    )
    engine.run_turn("ping", emit=lambda _e: None)


def test_tools_deny_refreshes_from_disk_each_turn(
    engine: Engine, monkeypatch,
) -> None:
    schema_names: list[set[str]] = []

    def capturing_stream(messages, tools, **kwargs):
        schema_names.append({s["function"]["name"] for s in tools})
        yield from _stream_one("ok")

    monkeypatch.setattr("alpi.llm.stream", capturing_stream)

    engine.run_turn("first", emit=lambda _e: None)
    assert "write_file" not in schema_names[0]
    assert "terminal" in schema_names[0]

    (engine.home / "config.yaml").write_text(yaml.safe_dump({
        "model": "gpt-5.4-mini",
        "tools": {"deny": ["terminal"]},
    }))

    engine.run_turn("second", emit=lambda _e: None)
    assert "terminal" not in schema_names[1]
    assert "write_file" in schema_names[1]


def test_removed_deny_is_also_removed_from_executor(
    engine: Engine, monkeypatch,
) -> None:
    from alpi import tools

    executed = []

    class FakeWrite(Tool):
        name = "write_file"
        description = "test"

        def run(self, **kwargs) -> ToolResult:
            executed.append(kwargs)
            return ToolResult(True, "written")

    monkeypatch.setitem(tools._TOOLS, FakeWrite.name, FakeWrite)
    (engine.home / "config.yaml").write_text(yaml.safe_dump({
        "model": "gpt-5.4-mini",
        "tools": {"deny": []},
    }))
    calls = {"count": 0}

    def stream(messages, tools, **kwargs):
        calls["count"] += 1
        if calls["count"] == 1:
            yield {
                "final": True, "input_tokens": 1, "output_tokens": 1,
                "cost_usd": 0.0, "tool_calls": [{
                    "id": "write", "name": "write_file",
                    "arguments": '{"path":"note.txt","content":"ok"}',
                }],
            }
        else:
            yield from _stream_one("done")

    monkeypatch.setattr("alpi.llm.stream", stream)

    engine.run_turn("write", emit=lambda _e: None)

    assert executed == [{"path": "note.txt", "content": "ok"}]


def test_non_owner_pipeline_turn_hides_mutating_tools(
    engine: Engine, monkeypatch,
) -> None:
    schema_names: list[set[str]] = []

    def capturing_stream(messages, tools, **kwargs):
        schema_names.append({s["function"]["name"] for s in tools})
        yield from _stream_one("ok")

    monkeypatch.setenv(
        "ALPI_WORKGROUP_WRITE_SCOPE", '{"root":"","paths":[]}',
    )
    monkeypatch.setattr("alpi.llm.stream", capturing_stream)

    engine.run_turn("observe", emit=lambda _e: None)

    assert {"delete_file", "edit_file", "write_file"}.isdisjoint(
        schema_names[0],
    )
    assert "terminal" in schema_names[0]


def test_stale_non_owner_tool_call_reports_phase_policy_not_profile_config(
    engine: Engine, monkeypatch,
) -> None:
    import json

    (engine.home / "config.yaml").write_text(yaml.safe_dump({
        "model": "gpt-5.4-mini", "tools": {"deny": []},
    }))
    monkeypatch.setenv(
        "ALPI_WORKGROUP_WRITE_SCOPE",
        json.dumps({
            "root": "", "paths": [], "phase": "media-qa", "owner": "lens",
        }),
    )
    calls = {"count": 0}

    def stream(messages, tools, **kwargs):
        calls["count"] += 1
        if calls["count"] == 1:
            yield {
                "final": True, "input_tokens": 1, "output_tokens": 1,
                "cost_usd": 0.0, "tool_calls": [{
                    "id": "write", "name": "write_file",
                    "arguments": '{"path":"note.txt","content":"no"}',
                }],
            }
        else:
            yield from _stream_one("done")

    monkeypatch.setattr("alpi.llm.stream", stream)
    engine.run_turn("write", emit=lambda _e: None)

    journal = engine.home / "runs" / f"{engine.last_run_id}.jsonl"
    rows = [json.loads(line) for line in journal.read_text().splitlines()]
    finished = next(
        row for row in rows
        if row["kind"] == "tool.finished" and row["data"]["name"] == "write_file"
    )
    assert "#media-qa" in finished["data"]["error"]
    assert "@lens" in finished["data"]["error"]
    assert "not tools.deny" in finished["data"]["error"]


def test_stale_tool_call_reports_both_profile_and_phase_denials(
    engine: Engine, monkeypatch,
) -> None:
    import json

    (engine.home / "config.yaml").write_text(yaml.safe_dump({
        "model": "gpt-5.4-mini", "tools": {"deny": ["write_file"]},
    }))
    monkeypatch.setenv(
        "ALPI_WORKGROUP_WRITE_SCOPE",
        json.dumps({
            "root": "", "paths": [], "phase": "media-qa", "owner": "lens",
        }),
    )
    calls = {"count": 0}

    def stream(messages, tools, **kwargs):
        calls["count"] += 1
        if calls["count"] == 1:
            yield {
                "final": True, "input_tokens": 1, "output_tokens": 1,
                "cost_usd": 0.0, "tool_calls": [{
                    "id": "write", "name": "write_file",
                    "arguments": '{"path":"note.txt","content":"no"}',
                }],
            }
        else:
            yield from _stream_one("done")

    monkeypatch.setattr("alpi.llm.stream", stream)
    engine.run_turn("write", emit=lambda _e: None)

    journal = engine.home / "runs" / f"{engine.last_run_id}.jsonl"
    rows = [json.loads(line) for line in journal.read_text().splitlines()]
    finished = next(
        row for row in rows
        if row["kind"] == "tool.finished" and row["data"]["name"] == "write_file"
    )
    assert "tools.deny in config.yaml" in finished["data"]["error"]
    assert "#media-qa" in finished["data"]["error"]


def test_owner_pipeline_turn_uses_path_checked_write_tools(
    engine: Engine, monkeypatch,
) -> None:
    schema_names: list[set[str]] = []

    def capturing_stream(messages, tools, **kwargs):
        schema_names.append({s["function"]["name"] for s in tools})
        yield from _stream_one("ok")

    monkeypatch.setenv(
        "ALPI_WORKGROUP_WRITE_SCOPE",
        '{"root":"projects/demo","paths":["src/content/**"]}',
    )
    (engine.home / "config.yaml").write_text(yaml.safe_dump({
        "model": "gpt-5.4-mini",
        "tools": {"deny": []},
    }))
    monkeypatch.setattr("alpi.llm.stream", capturing_stream)

    engine.run_turn("author", emit=lambda _e: None)

    assert {"delete_file", "edit_file", "write_file"} <= schema_names[0]
    assert "terminal" in schema_names[0]


def test_docker_owner_pipeline_turn_hides_terminal(
    engine: Engine, monkeypatch,
) -> None:
    schema_names: list[set[str]] = []

    def capturing_stream(messages, tools, **kwargs):
        schema_names.append({s["function"]["name"] for s in tools})
        yield from _stream_one("ok")

    monkeypatch.setenv("ALPI_PLATFORM", "docker")
    monkeypatch.setenv(
        "ALPI_WORKGROUP_WRITE_SCOPE",
        '{"root":"projects/demo","paths":["src/content/**"],'
        '"phase":"content","owner":"quill"}',
    )
    (engine.home / "config.yaml").write_text(yaml.safe_dump({
        "model": "gpt-5.4-mini",
        "tools": {"deny": []},
    }))
    monkeypatch.setattr("alpi.llm.stream", capturing_stream)

    engine.run_turn("author", emit=lambda _e: None)

    assert {"delete_file", "edit_file", "write_file"} <= schema_names[0]
    assert "terminal" not in schema_names[0]


def test_budget_exceeded_mid_turn_aborts(engine: Engine, monkeypatch) -> None:
    """A turn that crosses the daily cap mid-flight aborts instead of
    spending all the way to max_steps (the gate is re-checked per step)."""
    import alpi.ledger as ledger

    calls = {"n": 0}

    def fake_check(*_a, **_kw):
        calls["n"] += 1
        # Turn-start (1) and step-0 (2) checks pass; the step-1 check (3) trips.
        if calls["n"] >= 3:
            raise ledger.BudgetExceeded("usd", 1.0, 2.0)

    monkeypatch.setattr("alpi.ledger.check", fake_check)

    steps = {"n": 0}

    def stream(messages, tools, **kwargs):
        steps["n"] += 1
        # Always request a denied tool so the loop would keep going forever
        # if the mid-turn budget check did not stop it.
        yield {
            "final": True, "input_tokens": 1, "output_tokens": 1, "cost_usd": 0.0,
            "tool_calls": [{"id": f"t{steps['n']}", "name": "write_file",
                            "arguments": "{\"path\": \"x\", \"content\": \"y\"}"}],
        }

    monkeypatch.setattr("alpi.llm.stream", stream)

    events: list = []
    engine.run_turn("go", emit=lambda e: events.append(e))

    assert any(e.kind == "error" and "budget" in (e.text or "").lower() for e in events)
    assert steps["n"] == 1  # stopped after the first step, not max_steps (6)
