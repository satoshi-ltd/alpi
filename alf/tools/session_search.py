"""session_search — let alf look up past conversations."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from alf.home import get_home
from alf.tools.base import Tool, ToolResult

# Cap on the user+assistant thread returned per session match. The tail
# of the conversation is preserved (most recent turns matter most for
# "continue where we left off"). Sized so 3 matches stay well under the
# engine's 10K tool-result truncation.
MAX_THREAD_CHARS = 2500

# Set by the CLI so searches exclude the currently-active session file.
_CURRENT_SESSION_ID: str | None = None


def set_current_session_id(sid: str | None) -> None:
    global _CURRENT_SESSION_ID
    _CURRENT_SESSION_ID = sid


class SessionSearch(Tool):
    name = "session_search"
    description = (
        "Search past conversations (under ~/.alf/sessions). Returns the "
        "user/assistant thread of matching sessions (tail-prioritized).\n"
        "\n"
        "Use PROACTIVELY when the user references the past: \"remember "
        "when\", \"continue where we left off\", \"we agreed on X\".\n"
        "\n"
        "Do NOT use speculatively. If a session matches, TRUST the thread "
        "it returns — don't re-run web_search/web_extract to rediscover "
        "info that's already there."
    )
    parameters = {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Keywords or topic to look up."},
            "max_results": {"type": "integer", "default": 3},
        },
        "required": ["query"],
    }

    def run(self, query: str, max_results: int = 3) -> ToolResult:
        home = get_home()
        sessions_dir = home / "sessions"
        if not sessions_dir.exists():
            return ToolResult(ok=True, output="(no past sessions)")

        terms = [t for t in query.lower().split() if len(t) > 2]
        if not terms:
            return ToolResult(ok=False, output="", error="query too short — give at least one 3+ char term")

        scored: list[tuple[int, Path, dict]] = []
        for path in sessions_dir.glob("*.json"):
            try:
                data = json.loads(path.read_text())
            except Exception:
                continue
            if data.get("id") == _CURRENT_SESSION_ID:
                continue  # never match the currently-active session
            text = _session_text(data).lower()
            score = sum(text.count(t) for t in terms)
            if score:
                scored.append((score, path, data))

        if not scored:
            return ToolResult(ok=True, output=f"no past sessions matching {query!r}")

        scored.sort(key=lambda x: (-x[0], -x[2].get("started_at", 0)))
        top = scored[: max(1, max_results)]

        blocks: list[str] = []
        for score, path, data in top:
            when = _fmt_when(data.get("started_at"))
            thread = _thread_tail(data, MAX_THREAD_CHARS)
            blocks.append(
                f"## session {data.get('id', path.stem)}  ·  {when}  ·  score {score}\n\n"
                f"{thread}"
            )
        return ToolResult(ok=True, output="\n\n---\n\n".join(blocks))


def _session_text(data: dict) -> str:
    parts: list[str] = []
    for t in data.get("turns", []):
        user = (t.get("user") or "").strip()
        assistant = (t.get("assistant") or "").strip()
        if user:
            parts.append(user)
        if assistant:
            parts.append(assistant)
    return "\n".join(parts)


def _thread_tail(data: dict, cap: int) -> str:
    turns: list[str] = []
    for t in data.get("turns", []):
        user = (t.get("user") or "").strip()
        assistant = (t.get("assistant") or "").strip()
        if user:
            turns.append(f"user: {user}")
        tool_names = [tl.get("name", "") for tl in (t.get("tools") or []) if tl.get("name")]
        if tool_names:
            turns.append(f"tools: {', '.join(tool_names)}")
        if assistant:
            turns.append(f"alf: {assistant}")
    joined = "\n\n".join(turns)
    if len(joined) <= cap:
        return joined
    # Over cap → keep the tail. Drop whole turns from the head to avoid
    # showing a broken sentence, then fall back to a char-level cut.
    while turns and len("\n\n".join(turns)) > cap:
        turns.pop(0)
    tail = "\n\n".join(turns)
    if not tail or len(tail) > cap:
        tail = "…" + joined[-(cap - 1):]
    else:
        tail = "…\n\n" + tail
    return tail


def _fmt_when(ts) -> str:
    if not ts:
        return "?"
    try:
        return datetime.fromtimestamp(float(ts)).strftime("%Y-%m-%d %H:%M")
    except Exception:
        return "?"


TOOL = SessionSearch
