"""search — unified filename + content search, ripgrep-backed with stdlib fallback."""

from __future__ import annotations

import fnmatch
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

from alf.tools._paths import check_path
from alf.tools.base import Tool, ToolResult


_EXCLUDES = (
    ".git", ".hg", ".svn", "node_modules", ".venv", "venv",
    "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache",
    "dist", "build", ".next", ".cache",
)


def _case_insensitive_default() -> bool:
    return sys.platform == "darwin" or os.name == "nt"


class Search(Tool):
    name = "search"
    description = (
        "Search file contents or find files by name. Use this instead "
        "of grep/rg/find/ls in terminal. Ripgrep-backed, workspace-"
        "sandboxed, skips noise dirs (.git, node_modules, .venv, "
        "build, dist, etc.).\n"
        "\n"
        "Content search (target='content', default): Regex search "
        "inside files. Restrict scanned files with file_glob='*.py'.\n"
        "\n"
        "File search (target='files'): Find files by glob pattern "
        "(e.g., '*.py', '*config*', 'src/**/*.ts'). Also use this "
        "instead of ls.\n"
        "\n"
        "Case-insensitive by default on macOS/Windows, case-sensitive "
        "on Linux. Override with case_sensitive."
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
                "description": "Override the platform default.",
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
            root = check_path(path)
        except ValueError as e:
            return ToolResult(ok=False, output="", error=str(e))
        if case_sensitive is None:
            case_sensitive = not _case_insensitive_default()
        if target == "files":
            return _search_filenames(pattern, root, case_sensitive, limit, include_noise)
        if target == "content":
            return _search_content(
                pattern, root, file_glob, case_sensitive, limit, include_noise,
            )
        return ToolResult(ok=False, output="", error=f"unknown target: {target}")


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
        return ToolResult(
            ok=False, output="",
            error=f"path {str(root)!r} does not exist. Check the path argument you passed.",
        )
    if not root.is_dir():
        return ToolResult(ok=False, output="", error=f"not a directory: {root}")

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
    if shutil.which("rg") is not None:
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
    cmd = ["rg", "--line-number", "--no-heading", "-m", str(limit)]
    if not case_sensitive:
        cmd.append("-i")
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
        return ToolResult(ok=False, output=proc.stdout, error=proc.stderr.strip())
    return ToolResult(ok=True, output=proc.stdout or "(no matches)")


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
        return ToolResult(
            ok=False, output="",
            error=f"path {str(root)!r} does not exist. Check the path argument you passed.",
        )
    if root.is_file():
        candidates = [root]
    else:
        candidates = [p for p in root.rglob("*") if p.is_file()]
    for p in candidates:
        if not include_noise and _is_excluded(p, root):
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
