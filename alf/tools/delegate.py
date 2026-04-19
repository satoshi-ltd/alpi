"""delegate — spawn a sub-agent for deep research.

Runs a bounded mini-agent loop with its own tool subset (read-only web +
search + extract) against the main LLM. Returns a synthesized report.
The main conversation's context is preserved because the sub-agent has
its own message list.

Scope:
- Tools available to the sub-agent: ``web_search``, ``web_fetch``,
  ``web_extract``, ``read_file``, ``grep``, ``glob``. No write tools, no
  memory tool, no terminal — a research assistant, not a worker.
- Hard cap on tool steps (default 12) to avoid runaway cost.
- Final assistant message is returned as the tool output.
"""

from __future__ import annotations

import json
from typing import Any

from alf import config as cfg_mod
from alf import llm
from alf.home import get_home
from alf.tools.base import Tool, ToolResult
from alf.tools import _state as tool_state_mod


SUB_AGENT_TOOLS = {
    "web_search", "web_fetch", "web_extract",
    "read_file", "grep", "glob",
}

DEFAULT_MAX_STEPS = 12

SYSTEM_PROMPT = """\
You are a research sub-agent. You were spawned by the main agent to go
deep on a specific topic and return a synthesized answer.

Constraints:
- You have access to read-only tools only: web_search, web_fetch,
  web_extract, read_file, grep, glob.
- You must not call memory, terminal, or any write tool.
- Work focused: answer the research brief and stop. Do not exceed the
  tool-step budget.
- Cite your sources inline (URLs) when relevant.
- Final reply should be a concise, structured report — not a chat turn.
"""


class Delegate(Tool):
    name = "delegate"
    description = (
        "Spawn a read-only research sub-agent with its own context. Use for "
        "open-ended investigations (several searches + fetches) so they do "
        "not pollute the main conversation. Returns a synthesized report."
    )
    parameters = {
        "type": "object",
        "properties": {
            "brief": {
                "type": "string",
                "description": "The research question / goal. Be specific.",
            },
            "max_steps": {
                "type": "integer",
                "description": f"Hard cap on tool-steps (default {DEFAULT_MAX_STEPS}).",
                "default": DEFAULT_MAX_STEPS,
            },
        },
        "required": ["brief"],
    }

    def run(self, brief: str, max_steps: int = DEFAULT_MAX_STEPS) -> ToolResult:
        from alf.tools import execute, schemas as all_schemas

        cfg = cfg_mod.load(get_home())
        call_kwargs = cfg_mod.resolve_model(cfg)

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
                    "[delegate: interrupted by user before completing research]"
                ))
            iteration += 1
            tool_state_mod.emit_state(f"researching · step {iteration}/{max_steps}")
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

            # Execute every tool call in this turn — they count as one
            # iteration total (not one each). Hard cap is the number of
            # LLM round-trips, not individual tool executions.
            for tc in tool_calls:
                if tool_state_mod.is_interrupted():
                    return ToolResult(ok=True, output=(
                        "[delegate: interrupted by user mid-research]"
                    ))
                name = tc["name"]
                if name not in SUB_AGENT_TOOLS:
                    payload = f"ERROR: tool '{name}' not available to delegate"
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

        if not final_text:
            # Cap hit — force one last synthesis call (no tools) so the
            # main agent gets useful findings instead of "gave up".
            tool_state_mod.emit_state("writing final report…")
            messages.append({
                "role": "user",
                "content": (
                    f"You've used your {max_steps}-iteration research budget. "
                    "Stop investigating and write your final report now with "
                    "what you've gathered. Cite URLs. Do not call any tools."
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
                final_text = f"[delegate: {max_steps}-step budget exhausted, no synthesis available]"
        return ToolResult(ok=True, output=final_text)


TOOL = Delegate
