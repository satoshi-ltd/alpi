"""research — spawn a read-only sub-agent for deep investigation."""

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
    research_cfg = (cfg.raw.get("tools") or {}).get("research") or {}
    key = f"{depth}_steps"
    val = research_cfg.get(key, DEPTH_STEPS_DEFAULTS[depth])
    try:
        n = int(val)
    except (TypeError, ValueError):
        n = DEPTH_STEPS_DEFAULTS[depth]
    return max(1, n)


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
        "The exact iteration count per depth is a user knob in "
        "~/.alf/config.yaml under `tools.research.{quick,normal,deep}_steps` "
        "(defaults: quick=8, normal=15, deep=30). Don't pass the step count "
        "— pick the depth name."
    )
    parameters = {
        "type": "object",
        "properties": {
            "brief": {
                "type": "string",
                "description": "The research question / goal. Be specific.",
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
        },
        "required": ["brief"],
    }

    def run(self, brief: str, depth: str = "normal") -> ToolResult:
        from alf.tools import execute, schemas as all_schemas

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
                        payload = payload[:10_000]
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
