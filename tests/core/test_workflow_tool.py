from __future__ import annotations

import json
from pathlib import Path

from alpi import tools
from alpi.core.run_context import RunContext
from alpi.core.tool_executor import ToolExecutor, use
from alpi.tools.base import Tool, ToolResult
from alpi.tools.workflow import Workflow, _expand


class Echo(Tool):
    name = "test_workflow_echo"
    description = "test"
    parallel_safe = True

    def run(self, value="") -> ToolResult:  # noqa: ANN001
        return ToolResult(True, str(value))


class Fail(Tool):
    name = "test_workflow_fail"
    description = "test"

    def run(self) -> ToolResult:
        return ToolResult(False, "", "boom")


def _executor(tmp_path: Path) -> ToolExecutor:
    context = RunContext("run", tmp_path, tmp_path, "default", "user", "s", "host")
    return ToolExecutor(context)


def test_workflow_rejects_non_object_step() -> None:
    result = Workflow().run(["not-an-object"])

    assert not result.ok
    assert result.error == "invalid workflow step: expected an object"


def test_workflow_routes_steps_through_executor_and_expands_values(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setitem(tools._TOOLS, Echo.name, Echo)
    executor = _executor(tmp_path)
    with use(executor):
        result = Workflow().run([
            {"id": "first", "tool": Echo.name, "arguments": {"value": "hello"}},
            {"id": "second", "tool": Echo.name, "depends_on": ["first"], "arguments": {"value": "${first.output} world"}},
        ])
    assert result.ok
    assert json.loads(result.output)["second"]["output"] == "hello world"
    kinds = [json.loads(line)["kind"] for line in (tmp_path / "runs" / "run.jsonl").read_text().splitlines()]
    assert kinds.count("tool.dispatched") == 2


def test_workflow_stops_on_failure_and_rejects_recursion(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setitem(tools._TOOLS, Fail.name, Fail)
    with use(_executor(tmp_path)):
        failed = Workflow().run([
            {"id": "bad", "tool": Fail.name, "arguments": {}},
            {"id": "later", "tool": Fail.name, "depends_on": ["bad"], "arguments": {}},
        ])
    assert not failed.ok
    assert "bad" in failed.error
    recursive = Workflow().run([{"id": "x", "tool": "workflow", "arguments": {}}])
    assert not recursive.ok


def test_workflow_nested_steps_honor_executor_denylist(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setitem(tools._TOOLS, Echo.name, Echo)
    with use(ToolExecutor(_executor(tmp_path).context, deny={Echo.name})):
        result = Workflow().run([
            {"id": "blocked", "tool": Echo.name, "arguments": {"value": "secret"}},
        ])
    assert not result.ok
    assert "tool denied" in result.output


def test_workflow_uses_executor_parallel_limit(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setitem(tools._TOOLS, Echo.name, Echo)
    executor = ToolExecutor(_executor(tmp_path).context, max_workers=1)
    seen = []
    original = executor.execute_parallel

    def captured(calls, **kwargs):
        seen.append(kwargs.get("max_workers"))
        return original(calls, **kwargs)

    monkeypatch.setattr(executor, "execute_parallel", captured)
    with use(executor):
        result = Workflow().run([
            {"id": "a", "tool": Echo.name, "arguments": {"value": "a"}},
            {"id": "b", "tool": Echo.name, "arguments": {"value": "b"}},
        ])

    assert result.ok
    assert seen == [None]


def test_workflow_embedded_false_is_not_erased(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setitem(tools._TOOLS, Echo.name, Echo)
    with use(_executor(tmp_path)):
        result = Workflow().run([
            {"id": "first", "tool": Echo.name, "arguments": {"value": ""}},
            {
                "id": "second", "tool": Echo.name, "depends_on": ["first"],
                "arguments": {"value": "ok=${first.ok}; error=${first.error}"},
            },
        ])

    assert result.ok
    assert json.loads(result.output)["second"]["output"] == "ok=True; error="

    expanded = _expand("ok=${first.ok}", {"first": {"ok": False}})
    assert expanded == "ok=False"
