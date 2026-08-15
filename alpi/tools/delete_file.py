from __future__ import annotations

from alpi.tools._paths import resolve_workspace_path, suggest_similar_paths
from alpi.tools.base import Tool, ToolResult


class DeleteFile(Tool):
    name = "delete_file"
    description = (
        "Delete one regular file inside the active workspace. Use this to "
        "remove an obsolete file you could otherwise create or edit. "
        "Directories, symlinks, and paths outside the workspace are refused."
    )
    parameters = {
        "type": "object",
        "properties": {"path": {"type": "string"}},
        "required": ["path"],
    }

    def run(self, path: str) -> ToolResult:
        try:
            target = resolve_workspace_path(path, for_write=True)
        except ValueError as exc:
            return ToolResult(ok=False, output="", error=str(exc))
        if not target.exists():
            hints = suggest_similar_paths(target)
            error = f"File not found: {target}"
            if hints:
                error += ". Similar: " + ", ".join(hints)
            return ToolResult(ok=False, output="", error=error)
        if not target.is_file():
            return ToolResult(ok=False, output="", error=f"Not a regular file: {target}")
        try:
            before = target.read_text(errors="replace")
            target.unlink()
        except OSError as exc:
            return ToolResult(ok=False, output="", error=f"Delete failed: {exc}")
        from alpi.tools import _mutations
        _mutations.record_mutation(
            _mutations.build_record(target, before, None, op_hint="delete"),
        )
        return ToolResult(ok=True, output=f"Deleted {target}")


TOOL = DeleteFile
