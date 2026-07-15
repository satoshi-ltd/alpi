from __future__ import annotations

import os
from pathlib import Path

from alpi.tools._paths import resolve_path
from alpi.tools.base import Tool, ToolResult


class WriteFile(Tool):
    name = "write_file"
    description = (
        "Create or OVERWRITE a file (atomic: tmp + rename).\n"
        "\n"
        "Relative paths root at the workspace; absolute paths work anywhere "
        "except sensitive locations (/etc, SSH keys, .env files, etc.). Use "
        "`edit_file` for targeted changes — don't read + rewrite.\n"
        "\n"
        "If the user asked you to PRODUCE a file for them to keep or download "
        "(a document, report, export) — not edit a project file — follow the "
        "write with `attach_file(path)` so it rides on your reply as a "
        "downloadable chip. A workspace-only file is unreachable from the chat "
        "client: mobile, desktop, and remote members can't browse the workspace.\n"
        "\n"
        "DO NOT use write_file for:\n"
        "  • USER.md / MEMORY.md / AGENT.md → use `memory(add/replace)`\n"
        "  • skill files (SKILL.md or anything in scripts/references/"
        "assets/secrets/) → use `skill(action='create'|'edit'|'add_file')`. "
        "Direct writes skip the security scanner."
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
            p = resolve_path(path, for_write=True)
        except ValueError as e:
            return ToolResult(ok=False, output="", error=str(e))
        if _is_skill_path(p):
            return ToolResult(
                ok=False, output="",
                error=(
                    "path is inside a skill directory — use "
                    "`skill(action='create'|'edit'|'add_file')` so the "
                    "security scanner runs. Direct writes skip the scan."
                ),
            )
        from alpi.tools._lint import lint_content
        lint_err = lint_content(p, content)
        if lint_err:
            return ToolResult(
                ok=False, output="",
                error=f"refused — content would be unparseable: {lint_err}",
            )
        before: str | None
        try:
            before = p.read_text() if p.exists() else None
        except OSError:
            before = None
        p.parent.mkdir(parents=True, exist_ok=True)
        # Atomic overwrite: write to a sibling tmp file and os.replace onto
        # the target. If we crash mid-write the original is untouched.
        # No `.bak` sibling — git (or the user's own backups) covers that.
        tmp = p.with_suffix(p.suffix + ".tmp")
        tmp.write_text(content)
        os.replace(tmp, p)
        from alpi.tools import _mutations
        _mutations.record_mutation(_mutations.build_record(p, before, content))
        return ToolResult(ok=True, output=f"Wrote {len(content):,} chars to {p}")


def _is_skill_path(p: Path) -> bool:
    from alpi.home import get_home
    skills_root = (get_home() / "skills").resolve()
    try:
        p.resolve().relative_to(skills_root)
        return True
    except ValueError:
        return False


TOOL = WriteFile
