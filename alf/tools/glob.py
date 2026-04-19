from __future__ import annotations

from pathlib import Path

from alf.tools._paths import check_path
from alf.tools.base import Tool, ToolResult

# Noise directories to skip by default. Pass include_noise=True to recurse
# into them (needed if the user genuinely wants to search inside a venv).
_DEFAULT_EXCLUDES = frozenset({
    ".git", ".hg", ".svn",
    "node_modules",
    ".venv", "venv", "__pycache__",
    ".pytest_cache", ".mypy_cache", ".ruff_cache",
    "dist", "build", ".next", ".cache",
})


def _is_excluded(p: Path) -> bool:
    return any(part in _DEFAULT_EXCLUDES for part in p.parts)


class Glob(Tool):
    name = "glob"
    description = (
        "Find files matching a glob pattern (e.g. '**/*.py', 'src/*.ts'). "
        "Use this instead of `terminal find/ls`.\n"
        "\n"
        "By default skips noise dirs: .git, node_modules, .venv, "
        "__pycache__, .pytest_cache, dist, build, .next, .cache. Pass "
        "`include_noise=true` to recurse into them (rarely needed).\n"
        "\n"
        "Paths outside the workspace are rejected."
    )
    parameters = {
        "type": "object",
        "properties": {
            "pattern": {"type": "string"},
            "path": {"type": "string", "description": "Root directory.", "default": "."},
            "include_noise": {
                "type": "boolean",
                "description": "Include node_modules / .venv / .git etc.",
                "default": False,
            },
        },
        "required": ["pattern"],
    }

    def run(self, pattern: str, path: str = ".",
            include_noise: bool = False) -> ToolResult:
        try:
            root = check_path(path)
        except ValueError as e:
            return ToolResult(ok=False, output="", error=str(e))
        matches = []
        for p in root.glob(pattern):
            if not p.is_file():
                continue
            rel = p.relative_to(root) if p.is_relative_to(root) else p
            if not include_noise and _is_excluded(rel):
                continue
            matches.append(str(p))
        matches.sort()
        return ToolResult(ok=True, output="\n".join(matches) or "(no matches)")


TOOL = Glob
