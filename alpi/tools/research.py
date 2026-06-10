"""research — spawn a read-only sub-agent for deep investigation."""

from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from alpi import config as cfg_mod
from alpi import llm
from alpi.home import get_home
from alpi.tools._budget import apply as _budget_apply
from alpi.tools.base import Tool, ToolResult
from alpi.tools import _state as tool_state_mod

MAX_PARALLEL_TASKS = 3


SUB_AGENT_TOOLS = {
    "web_search", "web_fetch", "web_extract",
    "read_file", "search",
}

DEPTH_STEPS_DEFAULTS = {"quick": 8, "normal": 15, "deep": 30}

SYSTEM_PROMPT = """\
You are a research sub-agent. You were spawned by the main agent to go
deep on a specific topic and return a synthesized answer.

Constraints:
- You have access to read-only tools only: web_search, web_fetch,
  web_extract, read_file, search.
- You must not call memory, terminal, or any write tool.
- Work focused: answer the research brief and stop. Do not exceed the
  tool-step budget.
- Cite your sources inline (URLs) when relevant.
- Final reply should be a concise, structured report — not a chat turn.
"""


def _resolve_depth(cfg: cfg_mod.Config, depth: str) -> int:
    return max(1, DEPTH_STEPS_DEFAULTS[depth])


class Research(Tool):
    name = "research"
    description = (
        "Spawn a read-only sub-agent to investigate a topic and return a "
        "synthesized report with citations. Use for questions that would "
        "otherwise flood your context with intermediate search / fetch "
        "results.\n"
        "\n"
        "The sub-agent has web_search, web_fetch, web_extract, read_file, "
        "search. It CANNOT write, use terminal, or call memory / skill / "
        "send_message. It returns a single final report — you do not see "
        "its intermediate tool trace.\n"
        "\n"
        "Pick `depth` based on the user's intent:\n"
        "  - quick   — single-answer lookups (\"find docs for X\", \"what's\n"
        "              the syntax of Y\"). Fastest, cheapest.\n"
        "  - normal  — comparative / multi-source research (\"compare X\n"
        "              vs Y\", \"free APIs for Z\"). Default.\n"
        "  - deep    — exhaustive surveys (\"comprehensive analysis of X\",\n"
        "              \"survey state of the art for Y\", \"haz un estudio\n"
        "              profundo sobre Z\"). Most tokens, most wall time.\n"
        "\n"
        "Iteration ceilings per depth (quick=8, normal=15, deep=30) are "
        "internal — pick the depth name, never a step count.\n"
        "\n"
        "For multiple independent investigations, pass `tasks: [{brief, depth}]` "
        "(up to 3) to run them in parallel. Use single-task mode otherwise."
    )
    parameters = {
        "type": "object",
        "properties": {
            "brief": {
                "type": "string",
                "description": "The research question / goal. Single-task mode. Required unless `tasks` is set.",
            },
            "depth": {
                "type": "string",
                "enum": ["quick", "normal", "deep"],
                "default": "normal",
                "description": (
                    "Budget tier. quick = single-answer, normal = "
                    "comparative, deep = exhaustive."
                ),
            },
            "tasks": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "brief": {"type": "string"},
                        "depth": {
                            "type": "string",
                            "enum": ["quick", "normal", "deep"],
                        },
                    },
                    "required": ["brief"],
                },
                "description": (
                    f"Up to {MAX_PARALLEL_TASKS} independent briefs to "
                    "investigate in parallel. Mutually exclusive with "
                    "top-level brief/depth."
                ),
            },
        },
    }

    def run(
        self,
        brief: str = "",
        depth: str = "normal",
        tasks: list[dict] | None = None,
    ) -> ToolResult:
        if tasks:
            return self._run_batch(tasks)
        if not brief:
            return ToolResult(
                ok=False, output="",
                error="'brief' required when not using 'tasks'",
            )
        return self._run_single(brief, depth)

    def _run_batch(self, tasks: list[dict]) -> ToolResult:
        if len(tasks) > MAX_PARALLEL_TASKS:
            return ToolResult(
                ok=False, output="",
                error=f"max {MAX_PARALLEL_TASKS} parallel tasks; got {len(tasks)}",
            )
        for i, t in enumerate(tasks):
            if not isinstance(t, dict) or not t.get("brief"):
                return ToolResult(
                    ok=False, output="",
                    error=f"task {i} missing 'brief'",
                )

        parent_emit = tool_state_mod.get_emit()
        parent_interrupt = tool_state_mod.get_interrupt_getter()
        parent_usage = tool_state_mod.get_usage_sink()
        total = len(tasks)

        def _worker(idx: int, task: dict) -> ToolResult:
            tool_state_mod.set_interrupt_getter(parent_interrupt)
            tool_state_mod.set_usage_sink(parent_usage)
            label = f"[{idx + 1}/{total}]"
            tag = task.get("brief", "")[:30]

            def _prefixed(msg: str, error: bool = False,
                          _p: str = label, _tag: str = tag,
                          _outer: Any = parent_emit) -> None:
                if _outer is not None:
                    _outer(f"{_p} {_tag} · {msg}", error)

            tool_state_mod.set_emit(_prefixed)
            return self._run_single(task["brief"], task.get("depth", "normal"))

        with ThreadPoolExecutor(max_workers=min(MAX_PARALLEL_TASKS, total)) as ex:
            results = list(ex.map(
                lambda it: _worker(it[0], it[1]),
                enumerate(tasks),
            ))

        parts: list[str] = []
        for i, (task, r) in enumerate(zip(tasks, results)):
            body = r.output if r.ok else f"[failed: {r.error}]"
            parts.append(f"## Task {i + 1}: {task['brief']}\n\n{body}")
        return ToolResult(ok=True, output="\n\n---\n\n".join(parts))

    def _run_single(self, brief: str, depth: str = "normal") -> ToolResult:
        from alpi.tools import execute, schemas as all_schemas

        if depth not in DEPTH_STEPS_DEFAULTS:
            return ToolResult(
                ok=False, output="",
                error=f"depth must be one of: {sorted(DEPTH_STEPS_DEFAULTS)}",
            )

        cfg = cfg_mod.load(get_home())
        call_kwargs = cfg_mod.resolve_model(cfg)
        max_steps = _resolve_depth(cfg, depth)

        tools_schema = [
            s for s in all_schemas()
            if s.get("function", {}).get("name") in SUB_AGENT_TOOLS
        ]

        messages: list[dict[str, Any]] = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": brief},
        ]

        iteration = 0
        final_text = ""
        while iteration < max_steps:
            if tool_state_mod.is_interrupted():
                return ToolResult(ok=True, output=(
                    "[research: interrupted by user before completing]"
                ))
            iteration += 1
            prefix = f"step {iteration}/{max_steps}"
            tool_state_mod.emit_state(f"{depth} · {prefix}")
            try:
                out = llm.complete(
                    messages=messages, tools=tools_schema, **call_kwargs
                )
            except Exception as e:  # noqa: BLE001
                return ToolResult(ok=False, output="",
                                  error=f"research LLM call failed: {e}")
            tool_state_mod.record_usage(
                out.input_tokens, out.output_tokens, out.cost_usd,
            )

            content = out.content or ""
            tool_calls = out.tool_calls or []

            assistant_msg: dict[str, Any] = {"role": "assistant", "content": content}
            if tool_calls:
                assistant_msg["tool_calls"] = [
                    {"id": tc["id"], "type": "function",
                     "function": {"name": tc["name"], "arguments": tc["arguments"]}}
                    for tc in tool_calls
                ]
            messages.append(assistant_msg)

            if not tool_calls:
                final_text = content
                break

            outer_emit = tool_state_mod.get_emit()

            def _prefixed(label: str, error: bool = False,
                          _outer: Any = outer_emit, _p: str = prefix) -> None:
                if _outer is not None:
                    _outer(f"{_p} · {label}", error)

            tool_state_mod.set_emit(_prefixed)
            try:
                for tc in tool_calls:
                    if tool_state_mod.is_interrupted():
                        return ToolResult(ok=True, output=(
                            "[research: interrupted by user mid-investigation]"
                        ))
                    name = tc["name"]
                    if name not in SUB_AGENT_TOOLS:
                        payload = f"ERROR: tool '{name}' not available to research sub-agent"
                    else:
                        try:
                            args = json.loads(tc["arguments"]) if tc["arguments"] else {}
                        except json.JSONDecodeError:
                            args = {}
                        result = execute(name, args)
                        payload = result.output if result.ok else f"ERROR: {result.error}"
                        payload = _budget_apply(name, payload)
                        from alpi.tools._sanitizer import sanitize_tool_payload
                        payload = sanitize_tool_payload(name, payload, is_error=not result.ok)
                    messages.append({
                        "role": "tool", "tool_call_id": tc["id"],
                        "name": name, "content": payload,
                    })
            finally:
                tool_state_mod.set_emit(outer_emit)

        if not final_text:
            tool_state_mod.emit_state("writing final report…")
            messages.append({
                "role": "user",
                "content": (
                    f"You've used your {max_steps}-iteration budget. "
                    "Stop investigating and write your final report now with "
                    "what you've gathered. Cite URLs. Do not call any tools."
                ),
            })
            try:
                out = llm.complete(messages=messages, **call_kwargs)
                final_text = out.content or ""
            except Exception as e:  # noqa: BLE001
                return ToolResult(ok=False, output="",
                                  error=f"research synthesis failed: {e}")
            tool_state_mod.record_usage(
                out.input_tokens, out.output_tokens, out.cost_usd,
            )
            if not final_text:
                final_text = f"[research: {max_steps}-step budget exhausted, no synthesis]"
        return ToolResult(ok=True, output=final_text)


TOOL = Research
