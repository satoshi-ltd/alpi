from __future__ import annotations

import re
from typing import Any

_CLAUDE = re.compile(r"claude-(opus|sonnet|haiku|fable|mythos)-(\d+)(?:[-.](\d{1,2}))?(?!\d)")
_THINKING_ALWAYS_FROM = {"opus": (5, 5), "sonnet": (5, 5), "fable": (0, 0), "mythos": (0, 0)}


def _asks_for_reasoning(call_kwargs: dict[str, Any] | None) -> bool:
    if not call_kwargs:
        return False
    extra = call_kwargs.get("extra_body")
    return bool(call_kwargs.get("reasoning_effort")) or (isinstance(extra, dict) and bool(extra.get("reasoning")))


def forced_tool_choice(model: str, call_kwargs: dict[str, Any] | None = None) -> bool:
    match = _CLAUDE.search((model or "").lower())
    if not match:
        return True
    family, major, minor = match.group(1), int(match.group(2)), int(match.group(3) or 0)
    floor = _THINKING_ALWAYS_FROM.get(family)
    if floor is not None and (major, minor) >= floor:
        return False
    return not _asks_for_reasoning(call_kwargs)
