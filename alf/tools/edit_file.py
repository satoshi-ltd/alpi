from __future__ import annotations

from pathlib import Path

from alf.tools._paths import check_path
from alf.tools.base import Tool, ToolResult


class EditFile(Tool):
    name = "edit_file"
    description = (
        "Targeted edit: replace an exact string with a new one in a file. "
        "The match must be unique in the file (single occurrence). Writes "
        "a `.bak` sibling before overwriting. Workspace only.\n"
        "\n"
        "Use this instead of `terminal sed/awk/perl -i`.\n"
        "\n"
        "If `old_string` matches 0 or >1 times → the call fails. In that "
        "case, widen the context in `old_string` with surrounding lines "
        "until it's unique, then retry.\n"
        "\n"
        "DO NOT use edit_file for:\n"
        "  • memory files → use `memory(replace)`\n"
        "  • skill bodies → use `edit_skill`"
    )
    parameters = {
        "type": "object",
        "properties": {
            "path": {"type": "string"},
            "old_string": {"type": "string"},
            "new_string": {"type": "string"},
        },
        "required": ["path", "old_string", "new_string"],
    }

    def run(self, path: str, old_string: str, new_string: str) -> ToolResult:
        try:
            p = check_path(path)
        except ValueError as e:
            return ToolResult(ok=False, output="", error=str(e))
        if not p.exists():
            return ToolResult(ok=False, output="", error=f"File not found: {p}")
        text = p.read_text()
        count = text.count(old_string)
        if count == 0:
            return ToolResult(ok=False, output="", error="old_string not found")
        if count > 1:
            return ToolResult(ok=False, output="",
                              error=f"old_string matches {count} times; make it unique")
        p.write_text(text.replace(old_string, new_string, 1))
        return ToolResult(ok=True, output=f"Edited {p}")


TOOL = EditFile
