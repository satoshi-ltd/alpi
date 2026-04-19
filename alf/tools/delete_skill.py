"""delete_skill — remove a skill directory.

Safety rules:
- Only deletes ``origin: agent`` skills by default.
- ``origin: user`` requires ``confirm_user_skill=True`` — the agent should
  ask you out loud first.
"""

from __future__ import annotations

import shutil

from alf.home import get_home
from alf.tools.base import Tool, ToolResult
from alf.tools.edit_skill import _find_skill, _frontmatter


class DeleteSkill(Tool):
    name = "delete_skill"
    description = (
        "Delete a skill directory. Agent-owned skills delete directly; "
        "user-owned skills require confirm_user_skill=true."
    )
    parameters = {
        "type": "object",
        "properties": {
            "name": {"type": "string"},
            "confirm_user_skill": {
                "type": "boolean",
                "description": "Required when deleting an origin: user skill.",
                "default": False,
            },
        },
        "required": ["name"],
    }

    def run(self, name: str, confirm_user_skill: bool = False) -> ToolResult:
        home = get_home()
        skill_dir = _find_skill(home, name)
        if skill_dir is None:
            return ToolResult(ok=False, output="", error=f"skill not found: {name}")
        meta = _frontmatter(skill_dir / "SKILL.md")
        origin = meta.get("origin", "user")
        if origin != "agent" and not confirm_user_skill:
            return ToolResult(ok=False, output="",
                              error=(f"{name} is origin: {origin}. Pass "
                                     "confirm_user_skill=true to delete."))
        shutil.rmtree(skill_dir, ignore_errors=True)
        return ToolResult(ok=True, output=f"deleted {skill_dir}")


TOOL = DeleteSkill
