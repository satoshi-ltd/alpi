from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import urlparse

from rich.markup import escape as _escape_markup


def plural(n: int, word: str, many: str | None = None) -> str:
    return f"{n} {word if n == 1 else (many or word + 's')}"


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


_SKILL_PATH_RE = re.compile(
    r"\.alpi/(?:profiles/[^/\s]+/)?skills/[^/\s]+/([^/\s]+)(?:/scripts/([^\s/]+))?",
)


def _skill_hint_from_terminal(command: str) -> str | None:
    m = _SKILL_PATH_RE.search(command)
    if not m:
        return None
    name = m.group(1)
    script = m.group(2) or ""
    if script:
        return f"skill: {name} · {script}"
    return f"skill: {name}"


def arg_hint(tool_name: str, args: dict) -> str:
    if not args:
        return ""
    if tool_name == "terminal":
        action = args.get("action", "run")
        if action in ("run", "background"):
            prefix = "bg " if action == "background" else ""
            cmd = str(args.get("command", ""))
            skill_hint = _skill_hint_from_terminal(cmd)
            if skill_hint:
                return prefix + skill_hint
            return prefix + truncate(cmd, 40)
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
    if tool_name == "skill":
        action = args.get("action", "")
        name = args.get("name", "")
        cat = args.get("category", "")
        if action == "create":
            return f"create · {name} · {cat}".rstrip(" ·")
        if action in ("edit", "delete", "validate", "view"):
            return f"{action} · {name}".rstrip(" ·")
        return action
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
    if tool_name == "research":
        return truncate(str(args.get("brief", "")), 60)
    if tool_name == "tts":
        text = str(args.get("text", ""))
        voice = str(args.get("voice", "")).strip()
        if not voice:
            try:
                from alpi import config as _cfg
                from alpi.home import get_home as _gh
                voice = _cfg.load(_gh()).tools.tts.voice
            except Exception:
                voice = ""
        short = voice or "?"
        if "-" in voice:
            for part in voice.split("-"):
                if part.endswith("Neural"):
                    short = part[:-6]
                    break
        return f"{short} · {len(text)} chars"
    if tool_name == "stt":
        return shorten_path(str(args.get("path", "")))
    if tool_name == "browser":
        action = str(args.get("action", ""))
        if action == "navigate":
            return f"navigate · {shorten_url(str(args.get('url', '')))}"
        if action in ("click", "type"):
            label = args.get("name") or args.get("text") or args.get("role") or ""
            return f"{action} · {truncate(str(label), 40)}"
        if action == "scroll":
            return f"scroll · {args.get('direction', 'down')}"
        if action == "press":
            return f"press · {args.get('key', '')}"
        return action
    k, v = next(iter(args.items()))
    return truncate(f"{k}={v}", 40)


def result_hint(tool_name: str, output: str, muted: str = "dim") -> str:
    text = output.strip()
    if not text:
        return f"[{muted}]ok[/{muted}]"

    if tool_name == "terminal":
        lines = [ln for ln in text.splitlines() if not ln.startswith("[exit ")]
        if not lines:
            return f"[{muted}]ok[/{muted}]"
        extra = len(lines) - 1
        hint = _escape_markup(truncate(lines[0], 60))
        return f"{hint}" + (f"  [{muted}]+{plural(extra, 'line')}[/{muted}]" if extra else "")

    if tool_name == "read_file":
        n = text.count("\n") + 1
        return f"[{muted}]{plural(n, 'line')}[/{muted}]"

    if tool_name == "write_file":
        return _escape_markup(truncate(text, 60))

    if tool_name == "edit_file":
        return _escape_markup(truncate(text, 60))

    if tool_name == "web_fetch":
        lines = text.count("\n") + 1
        return f"[{muted}]{plural(lines, 'line')} · {len(output):,} chars[/{muted}]"

    if tool_name == "web_extract":
        lines = text.count("\n") + 1
        return f"[{muted}]{plural(lines, 'line')} · {len(output):,} chars extracted[/{muted}]"

    if tool_name == "grep":
        if "(no matches)" in text:
            return f"[{muted}]0 matches[/{muted}]"
        n = text.count("\n") + 1
        return f"[{muted}]{plural(n, 'match', 'matches')}[/{muted}]"

    if tool_name == "glob":
        if "(no matches)" in text:
            return f"[{muted}]0 files[/{muted}]"
        n = text.count("\n") + 1
        return f"[{muted}]{plural(n, 'file')}[/{muted}]"

    if tool_name == "memory":
        return _escape_markup(truncate(text.splitlines()[0], 60))

    if tool_name == "session_search":
        if "no past sessions" in text.lower():
            return f"[{muted}]no matches[/{muted}]"
        hits = max(text.count("  score"), text.count("] session "))
        return f"[{muted}]{plural(hits or 1, 'past session')}[/{muted}]"

    if tool_name == "todo":
        lines = text.splitlines()
        return _escape_markup(truncate(lines[0] if lines else "", 60))

    if tool_name == "schedule":
        return _escape_markup(truncate(text.splitlines()[0], 60))

    if tool_name == "skill":
        return _escape_markup(truncate(text, 60))

    if tool_name == "tts":
        if "→" in text:
            prefix, path = text.split("→", 1)
            verb = prefix.strip().split(" ", 1)[0]
            return _escape_markup(f"{verb} · {path.strip()}")
        return _escape_markup(text)

    lines = text.splitlines()
    hint = _escape_markup(truncate(lines[0], 60))
    extra = len(lines) - 1
    return hint + (f"  [{muted}]+{extra} more[/{muted}]" if extra else "")


_FAMILIES: tuple[tuple[str, frozenset[str]], ...] = (
    ("memory", frozenset({"memory", "session_search"})),
    ("file", frozenset({
        "read_file", "write_file", "edit_file", "edit", "list_dir", "glob", "patch",
    })),
    ("terminal", frozenset({"terminal", "shell", "run", "process"})),
    ("globe", frozenset({"web_fetch", "web_search", "web_extract", "browser", "research"})),
    ("search", frozenset({"grep", "search", "find", "knowledge_search"})),
    ("link", frozenset({"peer", "alp", "send_message", "notify"})),
)

FAMILY_GLYPHS: dict[str, str] = {
    "file": "▤",
    "terminal": "❯",
    "globe": "◍",
    "search": "⌕",
    "link": "⇄",
    "memory": "✱",
    "chip": "◆",
}


def tool_family(tool_name: str) -> str:
    name = (tool_name or "").split(":")[-1].lower()
    for family, names in _FAMILIES:
        if name in names:
            return family
    if name.startswith(("web_", "browser")):
        return "globe"
    if name.endswith(("_file", "_dir")):
        return "file"
    return "chip"
