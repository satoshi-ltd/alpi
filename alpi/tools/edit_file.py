from __future__ import annotations

from pathlib import Path

from alpi.tools._paths import resolve_path, suggest_similar_paths
from alpi.tools.base import Tool, ToolResult


class EditFile(Tool):
    name = "edit_file"
    description = (
        "Targeted edit: replace an exact string with a new one in a file. "
        "The match must be unique in the file (single occurrence). Writes "
        "a `.bak` sibling before overwriting.\n"
        "\n"
        "Relative paths root at the workspace; absolute paths work anywhere "
        "except sensitive locations (SSH keys, .env files, etc.). Use this instead of "
        "`terminal sed/awk/perl -i`.\n"
        "\n"
        "If `old_string` matches 0 or >1 times → the call fails. In that "
        "case, widen the context in `old_string` with surrounding lines "
        "until it's unique, then retry.\n"
        "\n"
        "DO NOT use edit_file for:\n"
        "  • memory files → use `memory(replace)`\n"
        "  • skill files (SKILL.md or anything in scripts/references/"
        "assets/secrets/) → use `skill(action='edit'|'add_file')`. Direct "
        "edits skip the security scanner."
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
            p = resolve_path(path)
        except ValueError as e:
            return ToolResult(ok=False, output="", error=str(e))
        if _is_skill_path(p):
            return ToolResult(
                ok=False, output="",
                error=(
                    "path is inside a skill directory — use "
                    "`skill(action='edit')` for SKILL.md or "
                    "`skill(action='add_file')` for scripts/references/"
                    "assets/secrets. Direct edits bypass the security scanner."
                ),
            )
        if not p.exists():
            hints = suggest_similar_paths(p)
            msg = f"File not found: {p}"
            if hints:
                msg += ". Similar: " + ", ".join(hints)
            return ToolResult(ok=False, output="", error=msg)
        text = p.read_text()
        count = text.count(old_string)
        if count == 0:
            return ToolResult(ok=False, output="", error="old_string not found")
        if count > 1:
            return ToolResult(ok=False, output="",
                              error=f"old_string matches {count} times; make it unique")
        new_content = text.replace(old_string, new_string, 1)
        from alpi.tools._lint import lint_content
        lint_err = lint_content(p, new_content)
        if lint_err:
            return ToolResult(
                ok=False, output="",
                error=f"refused — edit would make {p.name} unparseable: {lint_err}",
            )
        p.write_text(new_content)
        from alpi.tools import _mutations
        _mutations.record_mutation(_mutations.build_record(p, text, new_content, op_hint="edit"))
        return ToolResult(ok=True, output=f"Edited {p}")


def _is_skill_path(p: Path) -> bool:
    from alpi.home import get_home
    skills_root = (get_home() / "skills").resolve()
    try:
        p.resolve().relative_to(skills_root)
        return True
    except ValueError:
        return False


TOOL = EditFile
