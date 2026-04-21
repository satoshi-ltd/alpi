"""delegate — spawn a write-capable sub-agent for bounded work.

Batch/parallel mode (ROADMAP R.3) is intentionally NOT implemented here.
`alf/tools/_state.py` exposes `_emit`, `_interrupt_getter` and
`_usage_sink` as module-level globals; spawning multiple sub-agent
threads in parallel would race on them. The refactor required to ship
batch mode is: move those globals to `contextvars.ContextVar` so each
thread gets its own view, then layer a `tasks: [{goal, toolsets}]`
param with `ThreadPoolExecutor(max_workers=N)` on top of the loop
below. The loop itself needs no structural change — only the state
layer.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from alpi import config as cfg_mod
from alpi import llm
from alpi.home import get_home
from alpi.tools.base import Tool, ToolResult
from alpi.tools import _state as tool_state_mod


TOOLSET_PRESETS: dict[str, set[str]] = {
    "file": {"read_file", "write_file", "edit_file", "search"},
    "terminal": {"terminal"},
    "web": {"web_search", "web_fetch", "web_extract"},
}

BLOCKED_FOR_DELEGATE: frozenset[str] = frozenset({
    "delegate",
    "memory",
    "schedule",
    "send_message",
    "skill",
    "config",
    "session_search",
    "email",
    # _TODOS is a module-level global shared with the main agent; a
    # sub-agent adding/clearing items would pollute the outer session.
    "todo",
})

MAX_STEPS = 30


def _system_prompt(workspace: Path | None) -> str:
    ws_block = (
        f"\nWorkspace root: {workspace}\n"
        "Relative paths resolve under this root. Absolute paths go where the goal says.\n"
        if workspace else ""
    )
    return (
        "You are a sub-agent spawned by the main agent to complete a specific goal.\n"
        f"{ws_block}"
        "\nConstraints:\n"
        "- Stay focused on the goal; do not wander off-topic.\n"
        "- Only use the tools in your list. Do not invent tool names.\n"
        "- Write only to paths the goal or context explicitly mentions. Never\n"
        "  touch sensitive system paths (~/.ssh, /etc, credentials, etc.).\n"
        "- Do not assume container-style roots like /workspace/... unless the\n"
        "  goal explicitly gives that path.\n"
        "- Return a concise final summary — the parent only sees your last\n"
        "  reply, not your tool trace.\n"
    )


def _resolve_tools(toolsets: list[str] | None) -> tuple[set[str], list[str]]:
    if not toolsets:
        toolsets = ["file", "web"]
    names: set[str] = set()
    unknown: list[str] = []
    for ts in toolsets:
        preset = TOOLSET_PRESETS.get(ts)
        if preset is None:
            unknown.append(ts)
            continue
        names.update(preset)
    names -= BLOCKED_FOR_DELEGATE
    return names, unknown


class Delegate(Tool):
    name = "delegate"
    description = (
        "Spawn a write-capable sub-agent to complete a focused goal in an "
        "isolated context. Only the final summary returns to you — the "
        "sub-agent's tool trace never enters your context window.\n"
        "\n"
        "Use when the task would otherwise flood your context with "
        "intermediate data (multi-file refactors, pipelines that chain "
        "fetch + parse + write, skills that generate several output files, "
        "iterative debug loops with test runs). For read-only investigation, "
        "prefer `research`; for a single tool call, just call the tool.\n"
        "\n"
        "`toolsets` picks the capabilities the sub-agent gets:\n"
        "  - file     — read_file, write_file, edit_file, search\n"
        "  - terminal — shell execution\n"
        "  - web      — web_search, web_fetch, web_extract\n"
        "Default: ['file', 'web'].\n"
        "\n"
        "The sub-agent CANNOT call: delegate (no recursion), memory, "
        "skill, schedule, send_message, email, config, session_search.\n"
        "\n"
        "IMPORTANT: the sub-agent knows nothing about your conversation. "
        "Pass every relevant fact (file paths, error messages, decisions, "
        "project structure) via `context`."
    )
    parameters = {
        "type": "object",
        "properties": {
            "goal": {
                "type": "string",
                "description": (
                    "What to accomplish. Specific and self-contained; "
                    "the sub-agent has no memory of your chat."
                ),
            },
            "context": {
                "type": "string",
                "description": (
                    "Background: file paths, constraints, prior decisions, "
                    "relevant project structure. More specific = better results."
                ),
            },
            "toolsets": {
                "type": "array",
                "items": {"type": "string", "enum": ["file", "terminal", "web"]},
                "description": (
                    "Capabilities the sub-agent gets. Default: ['file', 'web']."
                ),
            },
        },
        "required": ["goal"],
    }

    def run(
        self,
        goal: str,
        context: str = "",
        toolsets: list[str] | None = None,
    ) -> ToolResult:
        from alpi.tools import execute, schemas as all_schemas

        tool_names, unknown = _resolve_tools(toolsets)
        if unknown:
            return ToolResult(
                ok=False, output="",
                error=f"unknown toolset(s): {unknown}. "
                      f"Available: {sorted(TOOLSET_PRESETS)}",
            )
        if not tool_names:
            return ToolResult(
                ok=False, output="",
                error="no tools resolved from toolsets — sub-agent needs at least one",
            )

        cfg = cfg_mod.load(get_home())
        call_kwargs = cfg_mod.resolve_model(cfg)

        tools_schema = [
            s for s in all_schemas()
            if s.get("function", {}).get("name") in tool_names
        ]

        user_content = goal if not context else f"{goal}\n\n# Context\n\n{context}"
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": _system_prompt(cfg.workspace_path)},
            {"role": "user", "content": user_content},
        ]

        iteration = 0
        final_text = ""
        while iteration < MAX_STEPS:
            if tool_state_mod.is_interrupted():
                return ToolResult(ok=True, output=(
                    "[delegate: interrupted by user before completing]"
                ))
            iteration += 1
            prefix = f"step {iteration}/{MAX_STEPS}"
            tool_state_mod.emit_state(prefix)
            try:
                out = llm.complete(
                    messages=messages, tools=tools_schema, **call_kwargs
                )
            except Exception as e:  # noqa: BLE001
                return ToolResult(ok=False, output="",
                                  error=f"delegate LLM call failed: {e}")
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

            outer_emit = tool_state_mod._emit  # noqa: SLF001

            def _prefixed(label: str, error: bool = False,
                          _outer: Any = outer_emit, _p: str = prefix) -> None:
                if _outer is not None:
                    _outer(f"{_p} · {label}", error)

            tool_state_mod.set_emit(_prefixed)
            try:
                for tc in tool_calls:
                    if tool_state_mod.is_interrupted():
                        return ToolResult(ok=True, output=(
                            "[delegate: interrupted by user mid-task]"
                        ))
                    name = tc["name"]
                    if name not in tool_names:
                        payload = (
                            f"ERROR: tool '{name}' is not available in this "
                            f"sub-agent's toolsets"
                        )
                    else:
                        try:
                            args = json.loads(tc["arguments"]) if tc["arguments"] else {}
                        except json.JSONDecodeError:
                            args = {}
                        result = execute(name, args)
                        payload = result.output if result.ok else f"ERROR: {result.error}"
                        payload = payload[:10_000]
                    messages.append({
                        "role": "tool", "tool_call_id": tc["id"],
                        "name": name, "content": payload,
                    })
            finally:
                tool_state_mod.set_emit(outer_emit)

        if not final_text:
            tool_state_mod.emit_state("writing summary…")
            messages.append({
                "role": "user",
                "content": (
                    f"You've used your {MAX_STEPS}-step budget. Stop working "
                    "and write your final summary now with what you accomplished. "
                    "Do not call any tools."
                ),
            })
            try:
                out = llm.complete(messages=messages, **call_kwargs)
                final_text = out.content or ""
            except Exception as e:  # noqa: BLE001
                return ToolResult(ok=False, output="",
                                  error=f"delegate synthesis failed: {e}")
            tool_state_mod.record_usage(
                out.input_tokens, out.output_tokens, out.cost_usd,
            )
            if not final_text:
                final_text = f"[delegate: {MAX_STEPS}-step budget exhausted, no summary]"
        return ToolResult(ok=True, output=final_text)


TOOL = Delegate
