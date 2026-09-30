from __future__ import annotations

from typing import Any


def reasoning_duration(seconds: float) -> str:
    n = int(round(seconds or 0))
    if n < 60:
        return f"{n}s"
    m, r = divmod(n, 60)
    return f"{m}m {r}s" if r else f"{m}m"


def thought_label(seconds: float | None) -> str:
    if seconds is not None and seconds >= 1:
        return f"Thought for {reasoning_duration(seconds)}"
    return "Thought"


def _field(obj: Any, name: str, default: Any = None) -> Any:
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


def consolidate_reasoning(tools: list, turn_reasoning: str | None) -> str:
    per_tool = [str(_field(t, "reasoning") or "").strip() for t in tools]
    per_tool = [s for s in per_tool if s]
    trailing = str(turn_reasoning or "").strip()
    for seg in per_tool:
        rest = trailing.lstrip()
        if rest.startswith(seg):
            trailing = rest[len(seg):]
        else:
            break
    return "\n\n".join(s for s in [*per_tool, trailing.strip()] if s)


def turn_parts(turn: Any) -> dict[str, Any]:
    all_tools = list(_field(turn, "tools") or [])
    tools = [t for t in all_tools if _field(t, "name") != "ask_user"]
    ask_users = []
    for t in all_tools:
        if _field(t, "name") != "ask_user":
            continue
        result = str(_field(t, "output") or _field(t, "result") or "").strip()
        if result:
            args = _field(t, "args") or {}
            ask_users.append({"question": str(args.get("question") or ""), "result": result})
    seconds = _field(turn, "reasoned_s")
    return {
        "tools": tools,
        "ask_users": ask_users,
        "reasoning": consolidate_reasoning(all_tools, _field(turn, "reasoning")),
        "reasoned_s": float(seconds) if isinstance(seconds, (int, float)) else None,
    }


def steps_span(spans: list[tuple[float, float]]) -> float:
    if not spans:
        return 0.0
    return max(0.0, max(end for _, end in spans) - min(start for start, _ in spans))
