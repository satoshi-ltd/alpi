from __future__ import annotations

import subprocess

from alf.tools._paths import check_path
from alf.tools.base import Tool, ToolResult


_DEFAULT_EXCLUDES = (
    ".git", ".hg", ".svn", "node_modules", ".venv", "venv",
    "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache",
    "dist", "build", ".next", ".cache",
)


class Grep(Tool):
    name = "grep"
    description = (
        "Search file contents with ripgrep (fast, regex). Returns matching "
        "lines with line numbers. Use this instead of "
        "`terminal grep/rg/ack`.\n"
        "\n"
        "Filter by file type via `glob` (e.g. '*.py'). Cap via `max_results`. "
        "Skips noise dirs (.git, node_modules, .venv, build, etc.) by "
        "default; `include_noise=true` to include them.\n"
        "\n"
        "Paths outside the workspace are rejected."
    )
    parameters = {
        "type": "object",
        "properties": {
            "pattern": {"type": "string"},
            "path": {"type": "string", "description": "Directory or file (default: cwd).", "default": "."},
            "glob": {"type": "string", "description": "File glob filter, e.g. '*.py'."},
            "max_results": {"type": "integer", "default": 200},
            "include_noise": {
                "type": "boolean",
                "description": "Search inside node_modules / .venv / .git etc.",
                "default": False,
            },
        },
        "required": ["pattern"],
    }

    def run(self, pattern: str, path: str = ".", glob: str | None = None,
            max_results: int = 200, include_noise: bool = False) -> ToolResult:
        try:
            resolved = check_path(path)
        except ValueError as e:
            return ToolResult(ok=False, output="", error=str(e))
        cmd = ["rg", "--line-number", "--no-heading", "-m", str(max_results),
               pattern, str(resolved)]
        if glob:
            cmd.extend(["--glob", glob])
        if not include_noise:
            for d in _DEFAULT_EXCLUDES:
                cmd.extend(["--glob", f"!{d}"])
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        except FileNotFoundError:
            return ToolResult(ok=False, output="", error="ripgrep (rg) not installed")
        if proc.returncode not in (0, 1):
            return ToolResult(ok=False, output=proc.stdout, error=proc.stderr)
        return ToolResult(ok=True, output=proc.stdout or "(no matches)")


TOOL = Grep
