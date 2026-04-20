"""Tool-call formatting helpers — shared by widgets and screens."""

from __future__ import annotations

from pathlib import Path
from urllib.parse import urlparse

from rich.markup import escape as _escape_markup


def truncate(s: str, n: int) -> str:
    s = (s or "").replace("\n", " ").strip()
    return s if len(s) <= n else s[: n - 1] + "…"


def shorten_path(p: str) -> str:
    home = str(Path.home())
    if p.startswith(home):
        p = "~" + p[len(home):]
    return truncate(p, 50)


def shorten_url(u: str) -> str:
    try:
        parsed = urlparse(u)
        short = parsed.netloc + parsed.path
        if parsed.query:
            short += "?…"
        return truncate(short, 50)
    except Exception:
        return truncate(u, 50)


def fmt_duration(seconds: float) -> str:
    if seconds < 1:
        return f"{int(seconds * 1000)}ms"
    if seconds < 60:
        return f"{seconds:.1f}s"
    mins = int(seconds // 60)
    secs = int(seconds % 60)
    return f"{mins}m{secs}s"


def fmt_count(n: int) -> str:
    if n >= 1000:
        return f"{n / 1000:.1f}K"
    return str(n)


def bar_10(n: int, total: int) -> str:
    if total <= 0:
        return "▓" + "░" * 9
    filled = max(0, min(10, n * 10 // total))
    return "▓" * filled + "░" * (10 - filled)


def arg_hint(tool_name: str, args: dict) -> str:
    if not args:
        return ""
    if tool_name == "terminal":
        action = args.get("action", "run")
        if action in ("run", "background"):
            prefix = "bg " if action == "background" else ""
            return prefix + truncate(str(args.get("command", "")), 40)
        pid = args.get("pid", "")
        return f"{action} pid={pid}"
    if tool_name in {"read_file", "write_file", "edit_file"}:
        return shorten_path(str(args.get("path", "")))
    if tool_name in {"web_fetch", "web_extract"}:
        url = shorten_url(str(args.get("url", "")))
        q = str(args.get("question", ""))
        if q:
            return f'{url} · "{truncate(q, 30)}"'
        return url
    if tool_name in {"grep", "glob"}:
        return truncate(str(args.get("pattern", "")), 40)
    if tool_name == "memory":
        action = args.get("action", "")
        target = args.get("target", "")
        payload = args.get("content") or args.get("match") or ""
        payload = truncate(str(payload), 28) if payload else ""
        base = f"{action} {target}"
        return f"{base}  {payload}".rstrip()
    if tool_name == "session_search":
        return truncate(str(args.get("query", "")), 40)
    if tool_name == "create_skill":
        return f"{args.get('name', '')} · {args.get('category', '')}"
    if tool_name == "todo":
        action = args.get("action", "")
        content = str(args.get("content", ""))
        return f"{action} {truncate(content, 30)}" if content else action
    if tool_name == "schedule":
        action = str(args.get("action", ""))
        if action == "add":
            kind = args.get("kind", "cron")
            detail = args.get("expression") or f"{args.get('after_hours', '?')}h"
            return f"add · {kind} · {detail}"
        return action
    if tool_name == "email":
        action = str(args.get("action", ""))
        parts = [action]
        for key in ("from_", "subject", "uid", "dest_folder", "attachment_name"):
            if args.get(key):
                parts.append(truncate(str(args[key]), 30))
                break
        if action == "send" and args.get("recipients"):
            parts.append(truncate(", ".join(args["recipients"]), 30))
        return " · ".join(parts)
    if tool_name == "delegate":
        return truncate(str(args.get("brief", "")), 60)
    k, v = next(iter(args.items()))
    return truncate(f"{k}={v}", 40)


def result_hint(tool_name: str, output: str) -> str:
    """One-line result summary, with Rich markup."""
    text = output.strip()
    if not text:
        return "[dim]ok[/dim]"

    if tool_name == "terminal":
        lines = [ln for ln in text.splitlines() if not ln.startswith("[exit ")]
        if not lines:
            return "[dim]ok[/dim]"
        extra = len(lines) - 1
        hint = _escape_markup(truncate(lines[0], 60))
        return f"{hint}" + (f"  [dim]+{extra} lines[/dim]" if extra else "")

    if tool_name == "read_file":
        n = text.count("\n") + 1
        return f"[dim]{n} lines[/dim]"

    if tool_name == "write_file":
        return _escape_markup(truncate(text, 60))

    if tool_name == "edit_file":
        return _escape_markup(truncate(text, 60))

    if tool_name == "web_fetch":
        lines = text.count("\n") + 1
        return f"[dim]{lines} lines · {len(output):,} chars[/dim]"

    if tool_name == "web_extract":
        lines = text.count("\n") + 1
        return f"[dim]{lines} lines · {len(output):,} chars extracted[/dim]"

    if tool_name == "grep":
        if "(no matches)" in text:
            return "[dim]0 matches[/dim]"
        n = text.count("\n") + 1
        return f"[dim]{n} matches[/dim]"

    if tool_name == "glob":
        if "(no matches)" in text:
            return "[dim]0 files[/dim]"
        n = text.count("\n") + 1
        return f"[dim]{n} files[/dim]"

    if tool_name == "memory":
        return _escape_markup(truncate(text.splitlines()[0], 60))

    if tool_name == "session_search":
        if "no past sessions" in text.lower():
            return "[dim]no matches[/dim]"
        hits = max(text.count("  score"), text.count("] session "))
        return f"[dim]{hits or 1} past session(s)[/dim]"

    if tool_name == "todo":
        lines = text.splitlines()
        return _escape_markup(truncate(lines[0] if lines else "", 60))

    if tool_name == "schedule":
        return _escape_markup(truncate(text.splitlines()[0], 60))

    if tool_name == "create_skill":
        return _escape_markup(truncate(text, 60))

    lines = text.splitlines()
    hint = _escape_markup(truncate(lines[0], 60))
    extra = len(lines) - 1
    return hint + (f"  [dim]+{extra} more[/dim]" if extra else "")
