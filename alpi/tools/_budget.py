"""Per-tool output truncation so a single big read doesn't blow up context."""

from __future__ import annotations

_DEFAULT_PER_RESULT = 100_000


def max_result_chars(tool_name: str) -> int:
    """Return the per-result char cap for *tool_name*.

    Negative → unlimited (no truncation). Reads from config on every call;
    no caching, since turns are short and config tweaks during a session
    should take effect immediately.
    """
    try:
        from alpi import config as cfg_mod
        from alpi.home import get_home
        cfg = cfg_mod.load(get_home())
    except Exception:
        return _DEFAULT_PER_RESULT
    tools_raw = cfg.raw.get("tools") or {}
    per_tool = tools_raw.get(tool_name) or {}
    if "max_result_chars" in per_tool:
        return int(per_tool["max_result_chars"])
    budget = tools_raw.get("budget") or {}
    return int(budget.get("per_result_chars", _DEFAULT_PER_RESULT))


def apply(tool_name: str, text: str) -> str:
    """Truncate *text* to the per-result cap for *tool_name*, with an ellipsis."""
    cap = max_result_chars(tool_name)
    if cap < 0 or len(text) <= cap:
        return text
    elided = len(text) - cap
    return text[:cap].rstrip() + f"\n… [{elided:,} chars elided by tool budget]"
