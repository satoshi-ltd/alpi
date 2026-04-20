"""edit_skill — rewrite an existing skill's body."""

from __future__ import annotations

import shutil
from pathlib import Path

from alf.home import get_home
from alf.tools.base import Tool, ToolResult
from alf.tools.create_skill import scan_skill_body


def _find_skill(home: Path, name: str) -> Path | None:
    root = home / "skills"
    if not root.exists():
        return None
    for cat in root.iterdir():
        if not cat.is_dir() or cat.name.startswith("_"):
            continue
        candidate = cat / name
        if candidate.is_dir():
            return candidate
    pending = root / "_pending" / name
    return pending if pending.is_dir() else None


def _frontmatter(md_path: Path) -> dict[str, str]:
    if not md_path.exists():
        return {}
    text = md_path.read_text()
    if not text.startswith("---"):
        return {}
    try:
        _, raw, _ = text.split("---", 2)
    except ValueError:
        return {}
    out: dict[str, str] = {}
    for line in raw.strip().splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            out[k.strip()] = v.strip()
    return out


class EditSkill(Tool):
    name = "edit_skill"
    description = (
        "Rewrite the body of an existing skill. Use for agent-created "
        "skills; user-owned skills require confirm_user_skill=true."
    )
    parameters = {
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "Skill name (kebab-case)."},
            "body": {"type": "string", "description": "New SKILL.md body."},
            "confirm_user_skill": {
                "type": "boolean",
                "description": "Required when editing an origin: user skill.",
                "default": False,
            },
        },
        "required": ["name", "body"],
    }

    def run(self, name: str, body: str,
            confirm_user_skill: bool = False) -> ToolResult:
        home = get_home()
        skill_dir = _find_skill(home, name)
        if skill_dir is None:
            return ToolResult(ok=False, output="", error=f"skill not found: {name}")

        md = skill_dir / "SKILL.md"
        meta = _frontmatter(md)
        origin = meta.get("origin", "user")  # treat unknown as user-owned
        if origin != "agent" and not confirm_user_skill:
            return ToolResult(ok=False, output="",
                              error=(f"{name} is origin: {origin}. Pass "
                                     "confirm_user_skill=true to edit."))

        flags = scan_skill_body(body)
        if flags:
            return ToolResult(ok=False, output="",
                              error=f"security scan blocked edit: {', '.join(flags)}")

        # Preserve frontmatter, replace body only.
        text = md.read_text() if md.exists() else ""
        if text.startswith("---"):
            try:
                _, front, _ = text.split("---", 2)
                header = f"---{front}---\n"
            except ValueError:
                header = text.split("\n\n", 1)[0] + "\n"
        else:
            header = ""

        shutil.copy2(md, md.with_suffix(".md.bak"))
        md.write_text(header + body.strip() + "\n")
        return ToolResult(ok=True, output=f"edited {md} (backup: {md}.bak)")


TOOL = EditSkill
