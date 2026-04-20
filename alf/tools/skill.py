"""skill — propose, edit, delete, or list skills under ~/.alf/skills/."""

from __future__ import annotations

import os
import re
import shutil
from datetime import date
from pathlib import Path

from alf.home import get_home
from alf.tools.base import Tool, ToolResult


CATEGORIES = {
    "software", "data", "research", "productivity", "communication",
    "media", "system", "finance", "personal", "creative", "security", "meta",
}

ALLOWED_SUBDIRS = {"scripts", "references", "assets", "secrets"}

_NAME_RE = re.compile(r"^[a-z][a-z0-9-]{1,60}$")
_FILENAME_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._-]{0,100}$")

MAX_AGENT_SKILLS = 40


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
    return [label for pat, label in _DANGER_PATTERNS if pat.search(body)]


def all_skills(home: Path) -> list[Path]:
    root = home / "skills"
    if not root.exists():
        return []
    out: list[Path] = []
    for cat in sorted(root.iterdir()):
        if not cat.is_dir() or cat.name.startswith("_"):
            continue
        for skill in sorted(cat.iterdir()):
            if skill.is_dir():
                out.append(skill)
    return out


def live_skill_names(home: Path) -> set[str]:
    return {p.name for p in all_skills(home)}


def agent_skill_count(home: Path) -> int:
    n = 0
    for p in all_skills(home):
        meta = _frontmatter(p / "SKILL.md")
        if meta.get("origin") == "agent":
            n += 1
    return n


def _find_skill(home: Path, name: str) -> Path | None:
    for p in all_skills(home):
        if p.name == name:
            return p
    return None


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


class Skill(Tool):
    name = "skill"
    description = (
        "Create, edit, delete, list, or augment reusable skills under "
        "~/.alf/skills/<category>/<name>/. A skill is a directory with a "
        "REQUIRED SKILL.md (prose instructions) plus up to four OPTIONAL "
        "subdirectories:\n"
        "\n"
        "  scripts/     executable code the skill invokes via terminal\n"
        "  references/  markdown docs the skill reads via read_file\n"
        "  assets/      templates, data files (non-executable)\n"
        "  secrets/     per-skill credentials. Mode 0700, gitignored.\n"
        "               Created on demand when stores_secrets=true.\n"
        "\n"
        "Each subdirectory is flat — no nested folders. Filenames must "
        "match ``[a-zA-Z0-9][a-zA-Z0-9._-]{0,100}``. No DESCRIPTION.md "
        "at the category level. No hidden files. Every skill delete "
        "removes the whole directory including secrets/.\n"
        "\n"
        "**Secrets path convention** (when stores_secrets=true): scripts "
        "inside the skill MUST read and write runtime secrets via\n"
        "    Path(__file__).parent.parent / 'secrets' / '<filename>'\n"
        "— NOT $HOME paths, NOT absolute ~/.alf/... paths, NOT a global "
        "dir. The secrets/ subdir lives alongside scripts/ so a skill "
        "delete wipes everything cleanly and there is ONE canonical place "
        "for the user to find or wipe credentials.\n"
        "\n"
        "**Prefer Python stdlib in scripts.** `urllib.request`, "
        "`http.server`, `json`, `threading`, `socketserver` cover most "
        "cases (HTTP calls, local callback servers, JSON parsing). If a "
        "third-party library is genuinely required (e.g. pandas, lxml), "
        "add an explicit install command to SKILL.md under a '## Setup' "
        "section so the user can prepare their environment before "
        "running the script. Do NOT import `requests`, `httpx`, or other "
        "extras silently.\n"
        "\n"
        "Actions:\n"
        "  create      — create a new skill. Writes SKILL.md only, goes\n"
        "                live immediately under <category>/<name>/. Pass\n"
        "                stores_secrets=true to pre-create secrets/.\n"
        "  edit        — rewrite SKILL.md body. Preserves frontmatter.\n"
        "  add_file    — write a file under scripts/references/assets/secrets/.\n"
        "                Creates OR overwrites. Security scanner runs on\n"
        "                every call (skipped for secrets/ by design). Use\n"
        "                this for both initial writes and later edits.\n"
        "                NEVER use `edit_file`/`write_file` on paths inside\n"
        "                a skill directory — that bypasses the scanner.\n"
        "  remove_file — remove one file from a subdirectory.\n"
        "  delete      — remove the whole skill directory.\n"
        "  list        — show every skill grouped by category.\n"
        "\n"
        "User-owned skills require confirm_user_skill=true for edit, "
        "add_file, remove_file, and delete."
    )
    parameters = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": [
                    "create", "edit", "add_file", "remove_file", "delete", "list",
                ],
            },
            "name": {"type": "string", "description": "Skill name (kebab-case)."},
            "category": {"type": "string", "enum": sorted(CATEGORIES)},
            "description": {
                "type": "string",
                "description": "One line, ≤150 chars, starts with a verb (create only).",
            },
            "body": {
                "type": "string",
                "description": "SKILL.md body (create / edit).",
            },
            "requires_env": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Pre-provisioned env vars in ~/.alf/.env (create only).",
                "default": [],
            },
            "tools": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Tools the skill is allowed to call (create only).",
                "default": [],
            },
            "stores_secrets": {
                "type": "boolean",
                "description": "Create a 0700 secrets/ subdir for runtime credentials.",
                "default": False,
            },
            "subdir": {
                "type": "string",
                "enum": ["scripts", "references", "assets", "secrets"],
                "description": "Subdirectory for add_file / remove_file.",
            },
            "filename": {
                "type": "string",
                "description": "Flat filename under subdir (add_file / remove_file).",
            },
            "content": {
                "type": "string",
                "description": "File contents (add_file only).",
            },
            "confirm_user_skill": {
                "type": "boolean",
                "description": "Required for edits/deletes on an origin: user skill.",
                "default": False,
            },
        },
        "required": ["action"],
    }

    def run(
        self,
        action: str,
        name: str = "",
        category: str = "",
        description: str = "",
        body: str = "",
        requires_env: list[str] | None = None,
        tools: list[str] | None = None,
        stores_secrets: bool = False,
        subdir: str = "",
        filename: str = "",
        content: str = "",
        confirm_user_skill: bool = False,
    ) -> ToolResult:
        home = get_home()

        if action == "list":
            return _list(home)
        if action == "create":
            return _create(home, name, category, description, body,
                           requires_env or [], tools or [], stores_secrets)
        if action == "edit":
            return _edit(home, name, body, confirm_user_skill)
        if action == "add_file":
            return _add_file(home, name, subdir, filename, content, confirm_user_skill)
        if action == "remove_file":
            return _remove_file(home, name, subdir, filename, confirm_user_skill)
        if action == "delete":
            return _delete(home, name, confirm_user_skill)
        return ToolResult(ok=False, output="", error=f"unknown action: {action}")


def _list(home: Path) -> ToolResult:
    root = home / "skills"
    if not root.exists():
        return ToolResult(ok=True, output="(no skills)")
    lines: list[str] = []
    for cat in sorted(root.iterdir()):
        if not cat.is_dir() or cat.name.startswith("_"):
            continue
        skills = sorted(s.name for s in cat.iterdir() if s.is_dir())
        if not skills:
            continue
        lines.append(f"{cat.name}:")
        lines.extend(f"  - {n}" for n in skills)
    if not lines:
        lines.append("(no skills)")
    return ToolResult(ok=True, output="\n".join(lines))


def _create(
    home: Path,
    name: str,
    category: str,
    description: str,
    body: str,
    requires_env: list[str],
    tools: list[str],
    stores_secrets: bool = False,
) -> ToolResult:
    if not _NAME_RE.match(name):
        return ToolResult(ok=False, output="", error="name must be kebab-case, 2-60 chars")
    if category not in CATEGORIES:
        return ToolResult(ok=False, output="",
                          error=f"category must be one of: {sorted(CATEGORIES)}")
    if not description:
        return ToolResult(ok=False, output="", error="'description' is required")
    if len(description) > 150:
        return ToolResult(ok=False, output="", error="description must be ≤150 chars")
    if not body:
        return ToolResult(ok=False, output="", error="'body' is required")

    flags = scan_skill_body(body)
    if flags:
        return ToolResult(ok=False, output="",
                          error=f"security scan blocked skill: {', '.join(flags)}")

    if name in live_skill_names(home):
        return ToolResult(ok=False, output="",
                          error=f"skill already exists: {name}. Edit it instead.")
    agent_count = agent_skill_count(home)
    if agent_count >= MAX_AGENT_SKILLS:
        return ToolResult(
            ok=False, output="",
            error=(f"too many agent-created skills ({agent_count}/{MAX_AGENT_SKILLS}). "
                   f"Ask the user to prune with /skills first."),
        )

    skill_dir = home / "skills" / category / name
    skill_dir.mkdir(parents=True)

    frontmatter = [
        "---",
        f"name: {name}",
        f"description: {description}",
        f"category: {category}",
        "version: 0.1.0",
        "origin: agent",
        f"requires_env: {list(requires_env)}",
        f"tools: {list(tools)}",
        f"stores_secrets: {bool(stores_secrets)}",
        f"created_at: {date.today().isoformat()}",
        "---",
        "",
    ]
    (skill_dir / "SKILL.md").write_text("\n".join(frontmatter) + body.strip() + "\n")

    if requires_env:
        example = "\n".join(f"{k}=" for k in requires_env) + "\n"
        (skill_dir / ".env.example").write_text(example)

    if stores_secrets:
        secrets = skill_dir / "secrets"
        secrets.mkdir(mode=0o700, exist_ok=True)

    return ToolResult(
        ok=True,
        output=(
            f"Created skill '{name}' (category: {category}) at {skill_dir}. "
            f"It is live immediately. Use `skill(action='add_file', ...)` "
            f"to flesh out scripts/references/assets."
        ),
    )


def _add_file(
    home: Path,
    name: str,
    subdir: str,
    filename: str,
    content: str,
    confirm_user_skill: bool,
) -> ToolResult:
    skill_dir = _find_skill(home, name)
    if skill_dir is None:
        return ToolResult(ok=False, output="", error=f"skill not found: {name}")

    origin = _frontmatter(skill_dir / "SKILL.md").get("origin", "user")
    if origin != "agent" and not confirm_user_skill:
        return ToolResult(
            ok=False, output="",
            error=(f"{name} is origin: {origin}. Pass "
                   "confirm_user_skill=true to add files."),
        )

    if subdir not in ALLOWED_SUBDIRS:
        return ToolResult(
            ok=False, output="",
            error=f"subdir must be one of {sorted(ALLOWED_SUBDIRS)}",
        )
    if not filename or not _FILENAME_RE.match(filename):
        return ToolResult(
            ok=False, output="",
            error=("filename must be flat (no '/'), start with alphanumeric, "
                   "only [a-zA-Z0-9._-], ≤100 chars"),
        )
    if not content:
        return ToolResult(ok=False, output="", error="'content' is required")

    if subdir != "secrets":
        flags = scan_skill_body(content)
        if flags:
            return ToolResult(
                ok=False, output="",
                error=f"security scan blocked file: {', '.join(flags)}",
            )

    sub_path = skill_dir / subdir
    if subdir == "secrets":
        sub_path.mkdir(mode=0o700, exist_ok=True)
    else:
        sub_path.mkdir(exist_ok=True)

    file_path = sub_path / filename
    file_path.write_text(content)
    if subdir == "secrets":
        os.chmod(file_path, 0o600)
    return ToolResult(ok=True, output=f"wrote {file_path}")


def _remove_file(
    home: Path,
    name: str,
    subdir: str,
    filename: str,
    confirm_user_skill: bool,
) -> ToolResult:
    skill_dir = _find_skill(home, name)
    if skill_dir is None:
        return ToolResult(ok=False, output="", error=f"skill not found: {name}")

    origin = _frontmatter(skill_dir / "SKILL.md").get("origin", "user")
    if origin != "agent" and not confirm_user_skill:
        return ToolResult(
            ok=False, output="",
            error=(f"{name} is origin: {origin}. Pass "
                   "confirm_user_skill=true to remove files."),
        )

    if subdir not in ALLOWED_SUBDIRS:
        return ToolResult(
            ok=False, output="",
            error=f"subdir must be one of {sorted(ALLOWED_SUBDIRS)}",
        )
    if not filename or not _FILENAME_RE.match(filename):
        return ToolResult(ok=False, output="", error="invalid filename")

    file_path = skill_dir / subdir / filename
    if not file_path.exists():
        return ToolResult(ok=False, output="", error=f"not found: {file_path}")
    file_path.unlink()
    return ToolResult(ok=True, output=f"removed {file_path}")


def _edit(
    home: Path,
    name: str,
    body: str,
    confirm_user_skill: bool,
) -> ToolResult:
    if not name:
        return ToolResult(ok=False, output="", error="'name' is required")
    if not body:
        return ToolResult(ok=False, output="", error="'body' is required")
    skill_dir = _find_skill(home, name)
    if skill_dir is None:
        return ToolResult(ok=False, output="", error=f"skill not found: {name}")

    md = skill_dir / "SKILL.md"
    meta = _frontmatter(md)
    origin = meta.get("origin", "user")
    if origin != "agent" and not confirm_user_skill:
        return ToolResult(
            ok=False, output="",
            error=(f"{name} is origin: {origin}. Pass "
                   "confirm_user_skill=true to edit."),
        )

    flags = scan_skill_body(body)
    if flags:
        return ToolResult(ok=False, output="",
                          error=f"security scan blocked edit: {', '.join(flags)}")

    text = md.read_text() if md.exists() else ""
    if text.startswith("---"):
        try:
            _, front, _ = text.split("---", 2)
            header = f"---{front}---\n"
        except ValueError:
            header = text.split("\n\n", 1)[0] + "\n"
    else:
        header = ""

    if md.exists():
        shutil.copy2(md, md.with_suffix(".md.bak"))
    md.write_text(header + body.strip() + "\n")
    return ToolResult(ok=True, output=f"edited {md} (backup: {md}.bak)")


def _delete(
    home: Path,
    name: str,
    confirm_user_skill: bool,
) -> ToolResult:
    if not name:
        return ToolResult(ok=False, output="", error="'name' is required")
    skill_dir = _find_skill(home, name)
    if skill_dir is None:
        return ToolResult(ok=False, output="", error=f"skill not found: {name}")
    meta = _frontmatter(skill_dir / "SKILL.md")
    origin = meta.get("origin", "user")
    if origin != "agent" and not confirm_user_skill:
        return ToolResult(
            ok=False, output="",
            error=(f"{name} is origin: {origin}. Pass "
                   "confirm_user_skill=true to delete."),
        )
    shutil.rmtree(skill_dir, ignore_errors=True)
    return ToolResult(ok=True, output=f"deleted {skill_dir}")


TOOL = Skill
