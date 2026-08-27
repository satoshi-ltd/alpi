from __future__ import annotations

import json
from pathlib import Path

from alpi import tools
from alpi.core.run_context import RunContext
from alpi.core.tool_executor import ToolCall, ToolExecutor, current, use
from alpi.tools.base import Tool, ToolResult


def _context(tmp_path: Path) -> RunContext:
    return RunContext.create(
        home=tmp_path,
        workspace=tmp_path,
        profile="default",
        source="user",
        session_id="session-1",
        connection_id="host",
    )


def test_public_execute_routes_through_bound_executor(monkeypatch, tmp_path: Path) -> None:
    executor = ToolExecutor(_context(tmp_path))
    seen = []

    def fake_execute(name, arguments, deny=None):
        seen.append((name, arguments, deny))
        return ToolResult(ok=True, output="routed")

    monkeypatch.setattr(executor, "execute", fake_execute)

    with use(executor):
        result = tools.execute("read_file", {"path": "x"}, deny={"terminal"})

    assert result.output == "routed"
    assert seen == [("read_file", {"path": "x"}, {"terminal"})]
    assert current() is None


def test_executor_preserves_registry_errors(tmp_path: Path) -> None:
    executor = ToolExecutor(_context(tmp_path))

    result = executor.execute("missing_tool", {})

    assert not result.ok
    assert result.error is not None and result.error.startswith("unknown tool:")


def test_executor_never_journals_terminal_commands(monkeypatch, tmp_path: Path) -> None:
    executor = ToolExecutor(_context(tmp_path))
    monkeypatch.setattr(
        tools, "_execute_registered",
        lambda name, arguments, deny=None, deny_reasons=None: ToolResult(ok=True, output="done"),
    )

    executor.execute("terminal", {
        "action": "run", "command": "export PRIVATE_VALUE=not-shaped-like-a-token",
        "cwd": "/workspace",
    })

    rows = [
        json.loads(line)
        for line in (tmp_path / "runs" / f"{executor.context.run_id}.jsonl").read_text().splitlines()
    ]
    dispatched = next(row for row in rows if row["kind"] == "tool.dispatched")
    assert dispatched["data"]["arguments"] == {"action": "run", "cwd": "/workspace"}
    assert "not-shaped-like-a-token" not in str(rows)


def test_executor_reports_phase_denial_separately_from_profile_config(tmp_path: Path) -> None:
    reason = (
        "tool unavailable in this workgroup turn: #media-qa is owned by @lens; "
        "this is a temporary phase boundary, not tools.deny in config.yaml"
    )
    executor = ToolExecutor(
        _context(tmp_path), deny={"write_file"},
        deny_reasons={"write_file": reason},
    )

    result = executor.execute("write_file", {"path": "x", "content": "y"})

    assert not result.ok
    assert result.error == reason


def test_parallel_calls_overlap_and_keep_input_order(monkeypatch, tmp_path: Path) -> None:
    import threading
    import time

    executor = ToolExecutor(_context(tmp_path))
    barrier = threading.Barrier(2)

    class ParallelTool(Tool):
        name = "test_parallel"
        description = "test"
        parallel_safe = True

        def run(self, value: str) -> ToolResult:
            barrier.wait(timeout=1)
            time.sleep(0.01 if value == "first" else 0)
            return ToolResult(ok=True, output=value)

    monkeypatch.setitem(tools._TOOLS, ParallelTool.name, ParallelTool)
    calls = [
        ToolCall("1", ParallelTool.name, {"value": "first"}),
        ToolCall("2", ParallelTool.name, {"value": "second"}),
    ]

    outcomes = executor.execute_parallel(calls, max_workers=2)

    assert [item.result.output for item in outcomes] == ["first", "second"]


def test_exclusive_call_forces_serial_batch(monkeypatch, tmp_path: Path) -> None:
    executor = ToolExecutor(_context(tmp_path))
    order = []

    class ExclusiveTool(Tool):
        name = "test_exclusive"
        description = "test"

        def run(self, value: str) -> ToolResult:
            order.append(value)
            return ToolResult(ok=True, output=value)

    monkeypatch.setitem(tools._TOOLS, ExclusiveTool.name, ExclusiveTool)
    calls = [
        ToolCall("1", ExclusiveTool.name, {"value": "first"}),
        ToolCall("2", ExclusiveTool.name, {"value": "second"}),
    ]

    outcomes = executor.execute_parallel(calls, max_workers=2)

    assert order == ["first", "second"]
    assert [item.result.output for item in outcomes] == order
