"""research — spawn a read-only sub-agent for deep investigation."""

from __future__ import annotations

import contextlib
import contextvars
import math
import threading
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from alpi import config as cfg_mod
from alpi import llm
from alpi.home import get_home
from alpi.tools import _args as tool_args
from alpi.tools import _policy as _tool_policy
from alpi.tools._budget import apply as _budget_apply
from alpi.tools.base import Tool, ToolResult, failure_payload
from alpi.tools import _state as tool_state_mod

MAX_PARALLEL_TASKS = 3
DEFAULT_MAX_USD = 1.0
SYNTHESIS_RESERVE = 0.25
PARENT_RESERVE = 0.10
PARTIAL_ITEMS = 10
PARTIAL_EXCERPT_CHARS = 600


SUB_AGENT_TOOLS = {
    "web_search", "web_fetch", "web_extract",
    "read_file", "search",
}

DEPTH_STEPS_DEFAULTS = {"fast": 8, "normal": 15, "deep": 30}
# fast/deep double as tier names; normal (and unconfigured tiers) resolve to the main model.

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


def max_usd(cfg: cfg_mod.Config) -> float | None:
    raw = (cfg.raw.get("tools") or {}).get("research") or {}
    value = raw.get("max_usd", DEFAULT_MAX_USD) if isinstance(raw, dict) else DEFAULT_MAX_USD
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
        return DEFAULT_MAX_USD
    return float(value) or None


_call_budget: contextvars.ContextVar["_CallBudget | None"] = contextvars.ContextVar("research_call_budget", default=None)


class _CallBudget:
    def __init__(self, cap_usd: float | None) -> None:
        self.cap = cap_usd
        self.spent = 0.0
        self._lock = threading.Lock()

    def charge(self, usd: Any) -> None:
        try:
            amount = max(0.0, float(usd or 0.0))
        except (TypeError, ValueError):
            return
        with self._lock:
            self.spent += amount

    def stop_reason(self, cfg: cfg_mod.Config, *, synthesis: bool) -> str:
        from alpi import ledger
        limit = self.cap if synthesis or self.cap is None else self.cap * (1 - SYNTHESIS_RESERVE)
        if limit is not None and self.spent >= limit:
            return f"the per-call cost cap (${self.cap:.2f})"
        fraction = ledger.spend_fraction(get_home(), cfg.budget)
        if fraction is not None and fraction >= 1 - PARENT_RESERVE:
            return "the daily budget headroom reserved for the main answer"
        return ""


class Research(Tool):
    name = "research"
    description = (
        "Spawn a read-only sub-agent to investigate a topic and return a "
        "synthesized report with citations. Use for questions that would "
        "otherwise flood your context with intermediate search / fetch "
        "results.\n"
        "\n"
        "The sub-agent has web_search, web_fetch, web_extract, read_file, "
        "search. It CANNOT write, use terminal, or call memory / skill. "
        "It returns a single final report — you do not see "
        "its intermediate tool trace.\n"
        "\n"
        "Pick `depth` based on the user's intent (depth also picks the "
        "model tier of the same name, when the profile configures tiers):\n"
        "  - fast  — single-answer lookups (\"find docs for X\", \"what's\n"
        "            the syntax of Y\"). Fastest, cheapest.\n"
        "  - normal — comparative / multi-source research (\"compare X\n"
        "            vs Y\", \"free APIs for Z\"). Default.\n"
        "  - deep  — exhaustive surveys (\"comprehensive analysis of X\",\n"
        "            \"survey state of the art for Y\", \"haz un estudio\n"
        "            profundo sobre Z\"). Most tokens, most wall time.\n"
        "\n"
        "Iteration ceilings per depth (fast=8, normal=15, deep=30) are "
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
                "enum": ["fast", "normal", "deep"],
                "default": "normal",
                "description": (
                    "Budget + model tier. fast = single-answer, normal = "
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
                            "enum": ["fast", "normal", "deep"],
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
        parent_tally = tool_state_mod.get_turn_usage_ref()
        from alpi.host.connection_context import current
        parent_connection = current()
        total = len(tasks)

        def _worker(idx: int, task: dict) -> ToolResult:
            tool_state_mod.set_interrupt_getter(parent_interrupt)
            tool_state_mod.set_usage_sink(parent_usage)
            tool_state_mod.adopt_turn_usage(parent_tally)
            label = f"[{idx + 1}/{total}]"
            tag = task.get("brief", "")[:30]

            def _prefixed(msg: str, error: bool = False,
                          _p: str = label, _tag: str = tag,
                          _outer: Any = parent_emit) -> None:
                if _outer is not None:
                    _outer(f"{_p} {_tag} · {msg}", error)

            tool_state_mod.set_emit(_prefixed)
            from alpi.host.connection_context import use
            with use(parent_connection):
                return self._run_single(task["brief"], task.get("depth", "normal"))

        budget_token = _call_budget.set(_CallBudget(max_usd(cfg_mod.load(get_home()))))
        try:
            with ThreadPoolExecutor(max_workers=min(MAX_PARALLEL_TASKS, total)) as ex:
                contexts = [contextvars.copy_context() for _task in tasks]
                futures = [
                    ex.submit(contexts[idx].run, _worker, idx, task)
                    for idx, task in enumerate(tasks)
                ]
                results = [future.result() for future in futures]
        finally:
            _call_budget.reset(budget_token)

        parts: list[str] = []
        for i, (task, r) in enumerate(zip(tasks, results)):
            body = r.output if r.ok else f"[failed: {r.error}]"
            parts.append(f"## Task {i + 1}: {task['brief']}\n\n{body}")
        return ToolResult(ok=True, output="\n\n---\n\n".join(parts))

    def _run_single(self, brief: str, depth: str = "normal") -> ToolResult:
        budget = _call_budget.get() or _CallBudget(max_usd(cfg_mod.load(get_home())))
        with _charging(budget):
            return self._investigate(brief, depth, budget)

    def _investigate(self, brief: str, depth: str, budget: _CallBudget) -> ToolResult:
        from alpi.tools import execute, schemas as all_schemas

        depth = (depth or "normal").strip().lower()
        if depth not in DEPTH_STEPS_DEFAULTS:
            return ToolResult(
                ok=False, output="",
                error=f"depth must be one of: {sorted(DEPTH_STEPS_DEFAULTS)}",
            )

        cfg = cfg_mod.load(get_home())
        call_kwargs = cfg_mod.resolve_model(cfg, tier=depth)
        max_steps = _resolve_depth(cfg, depth)
        deny_tools = _tool_policy.effective_denies(cfg.tools.deny)

        tools_schema = [
            s for s in all_schemas(deny=deny_tools)
            if s.get("function", {}).get("name") in SUB_AGENT_TOOLS
        ]

        messages: list[dict[str, Any]] = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": brief},
        ]

        iteration = 0
        final_text = ""
        stopped = ""
        notes: list[str] = []
        gathered: list[tuple[str, str]] = []
        while iteration < max_steps:
            if tool_state_mod.is_interrupted():
                return ToolResult(ok=True, output=(
                    "[research: interrupted by user before completing]"
                ))
            stopped = budget.stop_reason(cfg, synthesis=False)
            if stopped:
                if iteration == 0:
                    return ToolResult(ok=False, output="", error=f"research skipped: no room under {stopped}")
                break
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
            tool_state_mod.record_completion_usage(out)

            content = out.content or ""
            tool_calls = out.tool_calls or []
            if tool_calls and content.strip():
                notes.append(content.strip())

            cut_index = len(tool_calls) - 1 if getattr(out, "finish_reason", None) == "length" else -1
            decoded_args = [
                tool_args.prepare(tc["name"], tc.get("arguments"))
                for tc in tool_calls
            ]
            assistant_msg: dict[str, Any] = {"role": "assistant", "content": content}
            if tool_calls:
                assistant_msg["tool_calls"] = [
                    {"id": tc["id"], "type": "function",
                     "function": {"name": tc["name"],
                                  "arguments": tool_args.wire(tc.get("arguments"), call_args)}}
                    for tc, (call_args, _) in zip(tool_calls, decoded_args)
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
                for i, tc in enumerate(tool_calls):
                    if tool_state_mod.is_interrupted():
                        return ToolResult(ok=True, output=(
                            "[research: interrupted by user mid-investigation]"
                        ))
                    name = tc["name"]
                    if budget.stop_reason(cfg, synthesis=False):
                        payload = "ERROR: skipped, the research cost budget is reached"
                    elif name not in SUB_AGENT_TOOLS:
                        payload = f"ERROR: tool '{name}' not available to research sub-agent"
                    else:
                        args, args_error = decoded_args[i]
                        if args_error is None:
                            result = execute(name, args, deny=deny_tools)
                        else:
                            result = ToolResult(ok=False, output="", error=tool_args.refusal(
                                name, args_error, cut=i == cut_index,
                            ))
                        payload = result.output if result.ok else failure_payload(result)
                        payload = _budget_apply(name, payload)
                        from alpi.tools._sanitizer import sanitize_tool_payload
                        payload = sanitize_tool_payload(name, payload, is_error=not result.ok)
                        if result.ok:
                            gathered.append((_visited_line(name, args), payload))
                    messages.append({
                        "role": "tool", "tool_call_id": tc["id"],
                        "name": name, "content": payload,
                    })
            finally:
                tool_state_mod.set_emit(outer_emit)

        if not final_text:
            synthesis_stop = budget.stop_reason(cfg, synthesis=True)
            if synthesis_stop:
                return ToolResult(ok=True, output=_partial_report(notes, gathered, stopped or synthesis_stop))
            tool_state_mod.emit_state("writing final report…")
            reached = "reached your research cost budget" if stopped else f"used your {max_steps}-iteration budget"
            messages.append({
                "role": "user",
                "content": (
                    f"You've {reached}. "
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
            tool_state_mod.record_completion_usage(out)
            if not final_text:
                final_text = (
                    f"[research: stopped by {stopped}, no synthesis]" if stopped
                    else f"[research: {max_steps}-step budget exhausted, no synthesis]"
                )
            elif stopped:
                final_text += f"\n\n[research: stopped early by {stopped}; the report covers what was gathered so far]"
        return ToolResult(ok=True, output=final_text)


@contextlib.contextmanager
def _charging(budget: _CallBudget):
    parent = tool_state_mod.get_usage_sink()

    def sink(input_tokens, output_tokens, cost_usd, *rest, **kwargs):
        budget.charge(cost_usd)
        if parent is not None:
            parent(input_tokens, output_tokens, cost_usd, *rest, **kwargs)

    tool_state_mod.set_usage_sink(sink)
    try:
        yield
    finally:
        tool_state_mod.set_usage_sink(parent)


def _visited_line(name: str, args: Any) -> str:
    detail = ""
    if isinstance(args, dict):
        detail = str(args.get("url") or args.get("query") or args.get("path") or args.get("pattern") or "")
    return f"{name}: {detail[:160]}" if detail else name


def _partial_report(notes: list[str], gathered: list[tuple[str, str]], stopped: str) -> str:
    parts = [f"[research: stopped by {stopped} before a final report; partial findings follow]"]
    if notes:
        parts.append("\n\n".join(notes[-5:]))
    if gathered:
        lines = [f"- {source}\n  {' '.join(excerpt.split())[:PARTIAL_EXCERPT_CHARS]}" for source, excerpt in gathered[-PARTIAL_ITEMS:]]
        parts.append("Gathered so far:\n" + "\n".join(lines))
    return "\n\n".join(parts)


TOOL = Research
