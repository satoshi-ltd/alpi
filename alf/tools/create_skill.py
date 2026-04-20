"""create_skill — the meta-tool that proposes a new skill."""

from __future__ import annotations

import re
from datetime import date
from pathlib import Path

from alf.home import get_home
from alf.tools.base import Tool, ToolResult

CATEGORIES = {
    "software", "data", "research", "productivity", "communication",
    "media", "system", "finance", "personal", "creative", "security", "meta",
}

_NAME_RE = re.compile(r"^[a-z][a-z0-9-]{1,60}$")

PENDING_QUOTA = 5  # max pending agent proposals at once


# Security scanner

# Patterns that smell dangerous in a SKILL.md body. Not a full sandbox —
# just a cheap first line of defense against the most obvious foot-guns.
_DANGER_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\brm\s+-rf\b", re.I),           "rm -rf"),
    (re.compile(r":\(\)\s*\{\s*:\|:&\s*\};:"),    "fork bomb"),
    (re.compile(r"\bmkfs\.\w+\b", re.I),          "mkfs"),
    (re.compile(r"\bdd\s+if=/dev/", re.I),        "dd to disk device"),
    (re.compile(r"curl[^|]*\|\s*(?:bash|sh)\b"),  "curl | sh"),
    (re.compile(r"wget[^|]*\|\s*(?:bash|sh)\b"),  "wget | sh"),
    (re.compile(r"\beval\s*\("),                  "eval()"),
    (re.compile(r"\bexec\s*\("),                  "exec()"),
    (re.compile(r"__import__\s*\("),              "__import__()"),
    (re.compile(r"(?i)api[_-]?key\s*[:=]\s*['\"][A-Za-z0-9_\-]{16,}"),
                                                   "hardcoded api key"),
    (re.compile(r"(?i)(password|secret|token)\s*[:=]\s*['\"][^'\"]{8,}"),
                                                   "hardcoded secret"),
    (re.compile(r"sk-[A-Za-z0-9]{20,}"),          "openai-style key"),
]


def scan_skill_body(body: str) -> list[str]:
    """Return a list of human-readable flags for dangerous patterns found."""
    flags: list[str] = []
    for pat, label in _DANGER_PATTERNS:
        if pat.search(body):
            flags.append(label)
    return flags


def pending_dir(home: Path) -> Path:
    return home / "skills" / "_pending"


def pending_skills(home: Path) -> list[Path]:
    root = pending_dir(home)
    if not root.exists():
        return []
    return sorted(p for p in root.iterdir() if p.is_dir())


def live_skill_names(home: Path) -> set[str]:
    """Every skill name already in use under ~/.alf/skills/ (any category)."""
    root = home / "skills"
    if not root.exists():
        return set()
    names: set[str] = set()
    for cat in root.iterdir():
        if not cat.is_dir() or cat.name.startswith("_"):
            continue
        for skill in cat.iterdir():
            if skill.is_dir():
                names.add(skill.name)
    return names


class CreateSkill(Tool):
    name = "create_skill"
    description = (
        "Propose a new skill. Lands in ~/.alf/skills/_pending/<name>/ for "
        "the user to review with /skills. Follow the spec: kebab-case name, "
        "closed category list, required frontmatter, secrets via requires_env."
    )
    parameters = {
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "kebab-case, e.g. 'telegram-notifier'."},
            "category": {"type": "string", "enum": sorted(CATEGORIES)},
            "description": {
                "type": "string",
                "description": "One line, <150 chars, starts with a verb.",
            },
            "body": {
                "type": "string",
                "description": "The SKILL.md body (instructions for the agent).",
            },
            "requires_env": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Env var names the skill needs (never values).",
                "default": [],
            },
            "tools": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Tools the skill is allowed to call.",
                "default": [],
            },
        },
        "required": ["name", "category", "description", "body"],
    }

    def run(
        self,
        name: str,
        category: str,
        description: str,
        body: str,
        requires_env: list[str] | None = None,
        tools: list[str] | None = None,
    ) -> ToolResult:
        if not _NAME_RE.match(name):
            return ToolResult(ok=False, output="", error="name must be kebab-case, 2-60 chars")
        if category not in CATEGORIES:
            return ToolResult(ok=False, output="",
                              error=f"category must be one of: {sorted(CATEGORIES)}")
        if len(description) > 150:
            return ToolResult(ok=False, output="", error="description must be ≤150 chars")

        flags = scan_skill_body(body)
        if flags:
            return ToolResult(ok=False, output="",
                              error=f"security scan blocked skill: {', '.join(flags)}")

        home = get_home()

        # Anti-duplication: check both live skills AND pending proposals.
        if name in live_skill_names(home):
            return ToolResult(ok=False, output="",
                              error=f"skill already exists: {name} (live). Edit it instead.")
        pending = pending_skills(home)
        if any(p.name == name for p in pending):
            return ToolResult(ok=False, output="",
                              error=f"already pending approval: {name} (use /skills to review)")

        # Quota: prevent unbounded proposals piling up.
        if len(pending) >= PENDING_QUOTA:
            return ToolResult(ok=False, output="",
                              error=(f"too many pending proposals ({len(pending)}/{PENDING_QUOTA}). "
                                     f"Ask the user to review with /skills first."))

        skill_dir = pending_dir(home) / name
        skill_dir.mkdir(parents=True)

        # Store the intended category in frontmatter — on approval the user
        # (or the approve flow) moves the dir into skills/<category>/<name>/.
        frontmatter = [
            "---",
            f"name: {name}",
            f"description: {description}",
            f"category: {category}",
            "version: 0.1.0",
            "origin: agent",
            f"requires_env: {list(requires_env or [])}",
            f"tools: {list(tools or [])}",
            f"created_at: {date.today().isoformat()}",
            "---",
            "",
        ]
        (skill_dir / "SKILL.md").write_text("\n".join(frontmatter) + body.strip() + "\n")

        if requires_env:
            example = "\n".join(f"{k}=" for k in requires_env) + "\n"
            (skill_dir / ".env.example").write_text(example)

        return ToolResult(
            ok=True,
            output=(
                f"Proposed skill '{name}' (category: {category}). "
                f"Pending approval at {skill_dir}. "
                f"The user can review and approve/reject with /skills."
            ),
        )


TOOL = CreateSkill
