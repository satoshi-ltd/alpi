from __future__ import annotations

import os
from pathlib import Path

from alf.tools._paths import check_path
from alf.tools.base import Tool, ToolResult


class WriteFile(Tool):
    name = "write_file"
    description = (
        "Create or OVERWRITE a file (atomic: tmp + rename). Workspace only.\n"
        "\n"
        "Use `edit_file` for targeted changes — don't read + rewrite.\n"
        "\n"
        "DO NOT use write_file for:\n"
        "  • USER.md / MEMORY.md / PERSONALITY.md → use `memory(add/replace)`\n"
        "  • skill SKILL.md → use `create_skill` (new) or `edit_skill` (change)\n"
        "  • paths outside the workspace → the call will be rejected"
    )
    parameters = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Absolute file path."},
            "content": {"type": "string", "description": "Full file content."},
        },
        "required": ["path", "content"],
    }

    def run(self, path: str, content: str) -> ToolResult:
        try:
            p = check_path(path)
        except ValueError as e:
            return ToolResult(ok=False, output="", error=str(e))
        p.parent.mkdir(parents=True, exist_ok=True)
        # Atomic overwrite: write to a sibling tmp file and os.replace onto
        # the target. If we crash mid-write the original is untouched.
        # No `.bak` sibling — git (or the user's own backups) covers that.
        tmp = p.with_suffix(p.suffix + ".tmp")
        tmp.write_text(content)
        os.replace(tmp, p)
        return ToolResult(ok=True, output=f"Wrote {len(content):,} chars to {p}")


TOOL = WriteFile
