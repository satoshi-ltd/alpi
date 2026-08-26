"""search — unified filename + content search, ripgrep-backed with stdlib fallback."""

from __future__ import annotations

import fnmatch
import json
import re
import shutil
import subprocess
from pathlib import Path

from alpi.tools._paths import is_sensitive_path, resolve_path, suggest_similar_paths
from alpi.tools.base import Tool, ToolResult


_EXCLUDES = (
    ".git", ".hg", ".svn", "node_modules", ".venv", "venv",
    "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache",
    "dist", "build", ".next", ".cache",
)


_TARGET_ALIASES = {
    "content": "content", "grep": "content", "rg": "content",
    "files": "files", "find": "files", "glob": "files", "ls": "files",
}


def _not_found_error(root: Path) -> str:
    hints = suggest_similar_paths(root)
    msg = f"path {str(root)!r} does not exist"
    if hints:
        msg += ". Similar: " + ", ".join(hints)
    return msg


def _smart_case(pattern: str, override: bool | None) -> bool:
    if override is not None:
        return override
    return any(c.isupper() for c in pattern)


def _can_use_local_rg() -> bool:
    from alpi.core.execution_world import current

    world = current()
    return (world is None or world.backend == "local") and shutil.which("rg") is not None


class Search(Tool):
    name = "search"
    parallel_safe = True
    description = (
        "Literal-string / regex / glob search. Use instead of "
        "grep/rg/find/ls in terminal. Ripgrep-backed (content), "
        "stdlib glob (files). Skips noise dirs by default "
        "(.git, node_modules, .venv, build, dist, etc.).\n"
        "\n"
        "DO NOT use this when the user asks about the *content* of "
        "their notes, documents, labs, history, protocols, or any "
        "personal files described conceptually — that is "
        "`knowledge(action=\"search\")` when the content has been compiled "
        "into durable knowledge. Use this tool for: locating "
        "a known function/identifier in code, finding files by glob, "
        "literal regex matches, or code-base spelunking.\n"
        "\n"
        "Content search (target='content' | 'grep'): regex inside "
        "files. Restrict scanned files with file_glob='*.py'.\n"
        "\n"
        "File search (target='files' | 'find' | 'glob' | 'ls'): find "
        "files by glob pattern (e.g., '*.py', '*config*', "
        "'src/**/*.ts').\n"
        "\n"
        "Case: smart by default — lowercase pattern is case-insensitive, "
        "mixed-case is sensitive. Override with case_sensitive.\n"
        "\n"
        "Regex: the pattern is a regex in content mode. To match a literal "
        "`{` `}` `(` `)` `|` `.` `*` `+`, escape it with `\\`. If content "
        "search returns nothing and you expected hits, double-check the "
        "pattern isn't being interpreted as regex metacharacters."
    )
    parameters = {
        "type": "object",
        "properties": {
            "pattern": {"type": "string"},
            "path": {"type": "string", "default": "."},
            "target": {
                "type": "string",
                "enum": ["content", "files"],
                "default": "content",
            },
            "file_glob": {
                "type": "string",
                "description": "Restrict scanned files in content mode (glob).",
            },
            "case_sensitive": {
                "type": "boolean",
                "description": "Override smart-case.",
            },
            "limit": {"type": "integer", "default": 200},
            "include_noise": {"type": "boolean", "default": False},
        },
        "required": ["pattern"],
    }

    def run(
        self,
        pattern: str,
        path: str = ".",
        target: str = "content",
        file_glob: str | None = None,
        case_sensitive: bool | None = None,
        limit: int = 200,
        include_noise: bool = False,
    ) -> ToolResult:
        try:
            root = resolve_path(path)
        except ValueError as e:
            return ToolResult(ok=False, output="", error=str(e))
        resolved_target = _TARGET_ALIASES.get(target)
        if resolved_target is None:
            return ToolResult(
                ok=False, output="",
                error=f"unknown target {target!r}. Use 'content' or 'files'.",
            )
        case = _smart_case(pattern, case_sensitive)
        if resolved_target == "files":
            return _search_filenames(pattern, root, case, limit, include_noise)
        return _search_content(pattern, root, file_glob, case, limit, include_noise)


def _is_excluded(p: Path, root: Path) -> bool:
    try:
        rel = p.relative_to(root)
    except ValueError:
        rel = p
    return any(part in _EXCLUDES for part in rel.parts)


def _search_filenames(
    pattern: str,
    root: Path,
    case_sensitive: bool,
    limit: int,
    include_noise: bool,
) -> ToolResult:
    if not root.exists():
        return ToolResult(ok=False, output="", error=_not_found_error(root))
    if not root.is_dir():
        return ToolResult(ok=False, output="", error=f"not a directory: {root}")
    if _can_use_local_rg():
        rg_result = _search_filenames_rg(
            pattern, root, case_sensitive, limit, include_noise,
        )
        if rg_result is not None:
            return rg_result
    return _search_filenames_stdlib(
        pattern, root, case_sensitive, limit, include_noise,
    )


def _search_filenames_rg(
    pattern: str,
    root: Path,
    case_sensitive: bool,
    limit: int,
    include_noise: bool,
) -> ToolResult | None:
    cmd = ["rg", "--files"]
    cmd.extend(["--glob" if case_sensitive else "--iglob", pattern])
    if not include_noise:
        for d in _EXCLUDES:
            cmd.extend(["--glob", f"!{d}"])
    cmd.append(str(root))
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    except FileNotFoundError:
        return None
    if proc.returncode not in (0, 1):
        return ToolResult(ok=False, output=proc.stdout, error=proc.stderr.strip())
    lines = [ln for ln in proc.stdout.splitlines() if ln]
    lines.sort()
    lines = lines[:limit]
    return ToolResult(ok=True, output="\n".join(lines) or "(no matches)")


def _search_filenames_stdlib(
    pattern: str,
    root: Path,
    case_sensitive: bool,
    limit: int,
    include_noise: bool,
) -> ToolResult:
    flags = 0 if case_sensitive else re.IGNORECASE
    name_regex = re.compile(fnmatch.translate(pattern), flags)
    path_regex = re.compile(fnmatch.translate(pattern.lstrip("./")), flags)

    matches: list[str] = []
    for p in root.rglob("*"):
        if not p.is_file():
            continue
        if not include_noise and _is_excluded(p, root):
            continue
        try:
            rel = p.relative_to(root)
        except ValueError:
            rel = p
        if name_regex.match(p.name) or path_regex.match(str(rel)):
            matches.append(str(p))
            if len(matches) >= limit:
                break
    matches.sort()
    return ToolResult(ok=True, output="\n".join(matches) or "(no matches)")


def _search_content(
    pattern: str,
    root: Path,
    file_glob: str | None,
    case_sensitive: bool,
    limit: int,
    include_noise: bool,
) -> ToolResult:
    if _can_use_local_rg():
        rg_result = _search_content_rg(
            pattern, root, file_glob, case_sensitive, limit, include_noise,
        )
        if rg_result is not None:
            return rg_result
    return _search_content_stdlib(
        pattern, root, file_glob, case_sensitive, limit, include_noise,
    )


def _search_content_rg(
    pattern: str,
    root: Path,
    file_glob: str | None,
    case_sensitive: bool,
    limit: int,
    include_noise: bool,
) -> ToolResult | None:
    cmd = ["rg", "--json", "-m", str(limit)]
    cmd.append("-s" if case_sensitive else "-i")
    if file_glob:
        cmd.extend(["--glob", file_glob])
    if not include_noise:
        for d in _EXCLUDES:
            cmd.extend(["--glob", f"!{d}"])
    cmd.extend([pattern, str(root)])
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    except FileNotFoundError:
        return None
    if proc.returncode not in (0, 1):
        return ToolResult(ok=False, output="", error=proc.stderr.strip())
    matches: list[str] = []
    checked: dict[str, bool] = {}
    for raw in proc.stdout.splitlines():
        try:
            event = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if event.get("type") != "match":
            continue
        data = event.get("data") or {}
        path_text = str((data.get("path") or {}).get("text") or "")
        if not path_text:
            continue
        candidate = Path(path_text)
        if not candidate.is_absolute():
            candidate = root / candidate
        key = str(candidate)
        denied = checked.setdefault(key, is_sensitive_path(candidate))
        if denied:
            continue
        line_text = str((data.get("lines") or {}).get("text") or "").rstrip("\r\n")
        line_number = int(data.get("line_number") or 0)
        matches.append(f"{path_text}:{line_number}:{line_text}")
        if len(matches) >= limit:
            break
    return ToolResult(ok=True, output="\n".join(matches) or "(no matches)")


def _search_content_stdlib(
    pattern: str,
    root: Path,
    file_glob: str | None,
    case_sensitive: bool,
    limit: int,
    include_noise: bool,
) -> ToolResult:
    flags = 0 if case_sensitive else re.IGNORECASE
    try:
        regex = re.compile(pattern, flags)
    except re.error as e:
        return ToolResult(ok=False, output="", error=f"bad regex: {e}")
    file_regex = None
    if file_glob:
        file_regex = re.compile(fnmatch.translate(file_glob), flags)

    matches: list[str] = []
    if not root.exists():
        return ToolResult(ok=False, output="", error=_not_found_error(root))
    if root.is_file():
        candidates = [root]
    else:
        candidates = [p for p in root.rglob("*") if p.is_file()]
    for p in candidates:
        if not include_noise and _is_excluded(p, root):
            continue
        if is_sensitive_path(p):
            continue
        if file_regex and not file_regex.match(p.name):
            continue
        try:
            rel = p.relative_to(root) if root.is_dir() else p.name
        except ValueError:
            rel = p
        try:
            with p.open("r", encoding="utf-8", errors="replace") as f:
                for i, line in enumerate(f, start=1):
                    if regex.search(line):
                        matches.append(f"{rel}:{i}:{line.rstrip()}")
                        if len(matches) >= limit:
                            return ToolResult(ok=True, output="\n".join(matches))
        except OSError:
            continue
    return ToolResult(ok=True, output="\n".join(matches) or "(no matches)")


TOOL = Search
