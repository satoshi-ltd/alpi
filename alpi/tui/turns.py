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


def reasoning_first(tools: list, turn_reasoning: str | None) -> bool:
    per_tool = [str(_field(t, "reasoning") or "").strip() for t in tools]
    if not per_tool or per_tool[0]:
        return True
    later = next((seg for seg in per_tool if seg), "")
    return not (later and str(turn_reasoning or "").strip().startswith(later))


def _spans(turn: Any) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for sp in _field(turn, "reasoning_spans") or []:
        try:
            out.append({
                "seconds": float(_field(sp, "seconds") or 0),
                "before_tool": int(_field(sp, "before_tool") or 0),
                "text": str(_field(sp, "text") or "").strip(),
            })
        except (TypeError, ValueError):
            continue
    return out


def _span_texts(tools: list, spans: list[dict[str, Any]]) -> dict[int, str]:
    out: dict[int, str] = {}
    for sp in spans:
        if sp["text"]:
            slot = min(max(int(sp["before_tool"]), 0), len(tools))
            out[slot] = "\n\n".join(x for x in (out.get(slot, ""), sp["text"]) if x)
    for i, t in enumerate(tools):
        prose = str(_field(t, "reasoning") or "").strip()
        if prose and prose not in out.get(i, ""):
            out[i] = "\n\n".join(x for x in (out.get(i, ""), prose) if x)
    return out


def reasoning_by_slot(tools: list, turn_reasoning: str | None, span_slots: Any = ()) -> dict[int, str]:
    slots = sorted(set(span_slots))
    rest = str(turn_reasoning or "").strip()
    out: dict[int, str] = {}

    def put(slot: int, text: str) -> None:
        if text:
            out[slot] = "\n\n".join(x for x in (out.get(slot, ""), text) if x)

    def home(lo: int, hi: int) -> int:
        return next((s for s in slots if lo < s <= hi), hi)

    prev = -1
    for i, t in enumerate(tools):
        seg = str(_field(t, "reasoning") or "").strip()
        if not seg:
            continue
        j = rest.find(seg)
        if j < 0:
            thinking, rest = rest, ""
        else:
            thinking, rest = rest[:j].strip(), rest[j + len(seg):].strip()
        put(home(prev, i), thinking)
        put(i, seg)
        prev = i
    put(home(prev, len(tools)), rest)
    return out


def process_rows(turn: Any, *, include_reasoning: bool = True) -> list[dict[str, Any]] | None:
    spans = _spans(turn)
    if not spans:
        return None
    tools = list(_field(turn, "tools") or [])
    seconds: dict[int, float] = {}
    for sp in spans if include_reasoning else ():
        slot = min(max(int(sp["before_tool"]), 0), len(tools))
        seconds[slot] = seconds.get(slot, 0.0) + float(sp["seconds"])
    texts: dict[int, str] = {}
    if include_reasoning:
        if any(sp["text"] for sp in spans):
            texts = _span_texts(tools, spans)
        else:
            texts = reasoning_by_slot(tools, _field(turn, "reasoning"), seconds)
    rows: list[dict[str, Any]] = []
    for slot in range(len(tools) + 1):
        if slot in seconds or slot in texts:
            rows.append({"kind": "thought", "text": texts.get(slot, ""), "seconds": seconds.get(slot)})
        if slot == len(tools):
            break
        t = tools[slot]
        if _field(t, "name") == "ask_user":
            result = str(_field(t, "output") or _field(t, "result") or "").strip()
            if result:
                question = str((_field(t, "args") or {}).get("question") or "")
                rows.append({"kind": "ask", "question": question, "result": result})
            continue
        if rows and rows[-1]["kind"] == "steps":
            rows[-1]["tools"].append(t)
        else:
            rows.append({"kind": "steps", "tools": [t]})
    return rows


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
        "reasoning_first": reasoning_first(all_tools, _field(turn, "reasoning")),
        "tools": tools,
        "ask_users": ask_users,
        "reasoning": consolidate_reasoning(all_tools, _field(turn, "reasoning")),
        "reasoned_s": float(seconds) if isinstance(seconds, (int, float)) else None,
    }


def steps_span(spans: list[tuple[float, float]]) -> float:
    if not spans:
        return 0.0
    return max(0.0, max(end for _, end in spans) - min(start for start, _ in spans))
