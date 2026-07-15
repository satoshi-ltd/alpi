from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from alpi.home import get_home
from alpi.tools.base import Tool, ToolResult
from alpi.tools.session_search import current_session_id

MAX_OUTPUT_CHARS = 6000
MAX_TURN_CHARS = 600


class SessionRead(Tool):
    name = "session_read"
    description = (
        "Browse past conversations without an LLM call. Two modes:\n"
        "- no `session`: list recent sessions (id, when, turn count, preview).\n"
        "- with `session`: read a window of turns — around an exact `phrase`, "
        "or from a `start` index — to see the surrounding context.\n"
        "\n"
        "Pair with `session_search`: search finds the session, this opens the "
        "exact message window. Use `start` to scroll (page) through a thread."
    )
    parameters = {
        "type": "object",
        "properties": {
            "session": {"type": "string", "description": "Session id (omit to list recent sessions)."},
            "phrase": {"type": "string", "description": "Exact text to anchor the window on (case-insensitive)."},
            "start": {"type": "integer", "description": "Turn index to start from when paging."},
            "window": {"type": "integer", "default": 3, "description": "Turns of context each side of the anchor."},
            "limit": {"type": "integer", "default": 20, "description": "Max turns to return when paging."},
        },
        "required": [],
    }

    def run(self, session: str = "", phrase: str = "", start: int | None = None,
            window: int = 3, limit: int = 20) -> ToolResult:
        sessions_dir = get_home() / "sessions"
        if not sessions_dir.exists():
            return ToolResult(ok=True, output="(no past sessions)")

        if not session:
            return _list_recent(sessions_dir)

        data = _load(sessions_dir, session)
        if data is None:
            return ToolResult(ok=False, output="", error=f"no session with id {session!r}")

        turns = data.get("turns", []) or []
        total = len(turns)
        if total == 0:
            return ToolResult(ok=True, output=f"session {session} has no turns")

        if phrase:
            anchor = _find_anchor(turns, phrase)
            if anchor is None:
                return ToolResult(ok=True, output=f"no turn in session {session} contains {phrase!r}")
            lo = max(0, anchor - window)
            hi = min(total, anchor + window + 1)
        elif start is not None:
            lo = max(0, min(start, total))
            hi = min(total, lo + max(1, limit))
            anchor = None
        else:
            lo = 0
            hi = min(total, max(1, limit))
            anchor = None

        return ToolResult(ok=True, output=_render(session, turns, lo, hi, total, anchor))


def _load(sessions_dir: Path, session: str) -> dict | None:
    from alpi.host.connection_context import can_read_connection
    for path in sessions_dir.glob("*.json"):
        if path.stem != session:
            continue
        try:
            data = json.loads(path.read_text())
        except Exception:
            return None
        return data if can_read_connection(data.get("connection_id")) else None
    for path in sessions_dir.glob("*.json"):
        try:
            data = json.loads(path.read_text())
        except Exception:
            continue
        if data.get("id") == session:
            return data if can_read_connection(data.get("connection_id")) else None
    return None


def _find_anchor(turns: list[dict], phrase: str) -> int | None:
    needle = phrase.lower()
    for i, t in enumerate(turns):
        hay = f"{t.get('user') or ''}\n{t.get('assistant') or ''}".lower()
        if needle in hay:
            return i
    return None


def _render(session: str, turns: list[dict], lo: int, hi: int, total: int, anchor: int | None) -> str:
    head = f"session {session} · turns {lo}–{hi - 1} of {total}"
    if hi < total:
        head += f" · more below (start={hi})"
    if lo > 0:
        head += f" · more above (start={max(0, lo - 20)})"
    blocks = [head, ""]
    for i in range(lo, hi):
        t = turns[i]
        mark = " ◀ match" if i == anchor else ""
        user = _clip((t.get("user") or "").strip())
        assistant = _clip((t.get("assistant") or "").strip())
        tools = [tl.get("name", "") for tl in (t.get("tools") or []) if tl.get("name")]
        if user:
            blocks.append(f"[#{i}]{mark} user: {user}")
        if tools:
            blocks.append(f"[#{i}] tools: {', '.join(tools)}")
        if assistant:
            blocks.append(f"[#{i}] alpi: {assistant}")
    out = "\n".join(blocks)
    if len(out) > MAX_OUTPUT_CHARS:
        out = out[:MAX_OUTPUT_CHARS] + "\n…(truncated — narrow the window or page with start)"
    return out


def _clip(text: str) -> str:
    if len(text) <= MAX_TURN_CHARS:
        return text
    return text[:MAX_TURN_CHARS] + "…"


def _list_recent(sessions_dir: Path, limit: int = 15) -> ToolResult:
    from alpi.host.connection_context import can_read_connection
    cur = current_session_id()
    rows: list[tuple[float, str]] = []
    for path in sessions_dir.glob("*.json"):
        try:
            data = json.loads(path.read_text())
        except Exception:
            continue
        if not can_read_connection(data.get("connection_id")):
            continue
        sid = data.get("id", path.stem)
        if sid == cur:
            continue
        turns = data.get("turns", []) or []
        preview = ""
        for t in turns:
            u = (t.get("user") or "").strip()
            if u:
                preview = u[:80] + ("…" if len(u) > 80 else "")
                break
        started = _as_ts(data.get("started_at"), path)
        rows.append((started,
                     f"{sid}  ·  {_fmt_when(started)}  ·  {len(turns)} turns  ·  {preview}"))
    if not rows:
        return ToolResult(ok=True, output="(no past sessions)")
    rows.sort(key=lambda r: -r[0])
    lines = [r[1] for r in rows[:limit]]
    return ToolResult(ok=True, output="recent sessions:\n\n" + "\n".join(lines))


def _as_ts(value, path: Path) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        try:
            return path.stat().st_mtime
        except OSError:
            return 0.0


def _fmt_when(ts) -> str:
    if not ts:
        return "?"
    try:
        return datetime.fromtimestamp(float(ts)).strftime("%Y-%m-%d %H:%M")
    except Exception:
        return "?"


TOOL = SessionRead
