"""skill — manage reusable skills under ~/.alf/skills/."""

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
    "miscellaneous",
}

ALLOWED_SUBDIRS = {"scripts", "references", "assets", "secrets", "state"}

NO_SCAN_SUBDIRS = {"secrets", "state"}

_NAME_RE = re.compile(r"^[a-z][a-z0-9-]{1,60}$")
_FILENAME_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._-]{0,100}$")

MAX_AGENT_SKILLS = 40
MAX_FILE_BYTES = 1_048_576
MAX_BODY_CHARS = 100_000


_DANGER_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\brm\s+-rf\s+(?:/|\$HOME|~)"),        "rm -rf on root/home"),
    (re.compile(r":\(\)\s*\{\s*:\|:&\s*\};:"),          "fork bomb"),
    (re.compile(r"\bmkfs\.\w+\b", re.I),                "mkfs"),
    (re.compile(r"\bdd\s+[^|;&]*\bof=/dev/", re.I),     "dd to disk device"),
    (re.compile(r"chmod\s+777"),                        "chmod 777"),
    (re.compile(r"(?:>+|tee)\s+/(?:etc|var|usr|boot|sys|proc)/"),
                                                         "write to system dir"),
    (re.compile(r"shutil\.rmtree\s*\(\s*[\"\'/~]"),     "rmtree on root/home"),

    (re.compile(r"curl\s+[^\n|]*\$\{?\w*(?:KEY|TOKEN|SECRET|PASSWORD|CREDENTIAL)", re.I),
                                                         "curl leaking secret env"),
    (re.compile(r"wget\s+[^\n|]*\$\{?\w*(?:KEY|TOKEN|SECRET|PASSWORD|CREDENTIAL)", re.I),
                                                         "wget leaking secret env"),
    (re.compile(r"(?:curl|wget|fetch)[^|]*\|\s*(?:bash|sh|zsh|python|perl|ruby|node)\b"),
                                                         "pipe to interpreter"),
    (re.compile(r"(?:\$HOME|~)/\.ssh/(?!known_hosts|config\b)"),
                                                         "reads ~/.ssh"),
    (re.compile(r"(?:\$HOME|~)/\.aws/credentials"),     "reads ~/.aws/credentials"),
    (re.compile(r"(?:\$HOME|~)/\.gnupg"),               "reads ~/.gnupg"),
    (re.compile(r"(?:\$HOME|~)/\.alf/\.env"),           "reads alf .env"),
    (re.compile(r"(?:cat|head|tail|less|more|cp|mv)\s+[^\n]*(?:\.env\b|credentials\b|\.netrc\b|\.pgpass\b|\.npmrc\b|\.pypirc\b)"),
                                                         "reads known secrets file"),
    (re.compile(r"\bprintenv\b|\benv\s*\|"),            "dumps all env"),
    (re.compile(r"os\.getenv\s*\(\s*[\"'][^\"']*(?:KEY|TOKEN|SECRET|PASSWORD|CREDENTIAL)", re.I),
                                                         "python reads secret env"),
    (re.compile(r"process\.env\[\s*[\"'][^\"']*(?:KEY|TOKEN|SECRET|PASSWORD)", re.I),
                                                         "node reads secret env"),

    (re.compile(r"ignore\s+(?:\w+\s+)*(?:previous|all|above|prior)\s+instructions", re.I),
                                                         "prompt injection: ignore instructions"),
    (re.compile(r"disregard\s+(?:\w+\s+)*(?:your|all|any)\s+(?:\w+\s+)*(?:instructions|rules|guidelines)", re.I),
                                                         "prompt injection: disregard rules"),
    (re.compile(r"system\s+prompt\s+(?:override|leak|dump)", re.I),
                                                         "prompt injection: system prompt override"),
    (re.compile(r"<!--[^>]*(?:ignore|override|system\s+prompt|hidden)[^>]*-->", re.I),
                                                         "hidden instructions in html comment"),

    (re.compile(r"\bcrontab\b"),                        "modifies crontab"),
    (re.compile(r"authorized_keys\b"),                  "modifies ssh authorized_keys"),
    (re.compile(r"/etc/sudoers|\bvisudo\b"),            "modifies sudoers"),
    (re.compile(r"LaunchAgents|LaunchDaemons|\blaunchctl\s+load"),
                                                         "macos launchd persistence"),
    (re.compile(r"systemctl\s+(?:enable|start)\s+"),    "systemd enable/start"),
    (re.compile(r"\.(?:bashrc|zshrc|profile|bash_profile|zprofile|zlogin)\b"),
                                                         "shell rc file"),

    (re.compile(r"\bnc\s+-[lp]|\bncat\s+-[lp]|\bsocat\b"),
                                                         "reverse shell listener"),
    (re.compile(r"/bin/(?:ba)?sh\s+-i[^|]*>/dev/tcp/"), "bash reverse shell via /dev/tcp"),
    (re.compile(r"python[23]?\s+-c\s+[\"']import\s+socket"),
                                                         "python socket one-liner"),
    (re.compile(r"\bngrok\b|\bcloudflared\b|\blocaltunnel\b|\bserveo\b"),
                                                         "tunneling service"),
    (re.compile(r"webhook\.site|requestbin\.com|pipedream\.net|hookbin\.com"),
                                                         "exfiltration webhook service"),
    (re.compile(r"0\.0\.0\.0:\d+|\bINADDR_ANY\b"),      "binds to all interfaces"),

    (re.compile(r"\beval\s*\(\s*[\"']"),                "eval() with string"),
    (re.compile(r"\bexec\s*\(\s*[\"']"),                "exec() with string"),
    (re.compile(r"__import__\s*\("),                    "__import__()"),
    (re.compile(r"\bcompile\s*\([^)]+,\s*[\"'][^\"']*[\"']\s*,\s*[\"']exec[\"']\s*\)"),
                                                         "compile with exec mode"),
    (re.compile(r"base64\s+(?:-d|--decode)[^\n|]*\|\s*(?:bash|sh|python|perl|node)"),
                                                         "base64 decode to interpreter"),
    (re.compile(r"echo\s+[^\n]*\|\s*(?:bash|sh|python|perl|ruby|node)"),
                                                         "echo piped to interpreter"),
    (re.compile(r"getattr\s*\(\s*__builtins__"),        "dynamic access to __builtins__"),
    (re.compile(r"codecs\.decode\s*\(\s*[\"'][^\"']{12,}"),
                                                         "codecs.decode on long literal"),

    (re.compile(r"os\.system\s*\("),                    "os.system()"),
    (re.compile(r"os\.popen\s*\("),                     "os.popen()"),
    (re.compile(r"child_process\.(?:exec|spawn|fork)\s*\("),
                                                         "node child_process exec"),
    (re.compile(r"Runtime\.getRuntime\(\)\.exec\("),    "java runtime exec"),

    (re.compile(r"(?i)api[_-]?key\s*[:=]\s*['\"][A-Za-z0-9_\-]{16,}"),
                                                         "hardcoded api key"),
    (re.compile(r"(?i)(?:password|secret|token)\s*[:=]\s*['\"][^'\"\n]{8,}"),
                                                         "hardcoded secret"),
    (re.compile(r"sk-[A-Za-z0-9_\-]{20,}"),             "openai-style key"),
    (re.compile(r"ghp_[A-Za-z0-9]{20,}"),               "github pat"),
    (re.compile(r"AKIA[0-9A-Z]{16}"),                   "aws access key id"),

    (re.compile(r"/etc/passwd\b|/etc/shadow\b"),        "system password files"),
    (re.compile(r"\.\./\.\./\.\.(?:/|\\)"),             "deep path traversal"),
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


def skills_index_block(home: Path) -> str:
    """Compact skills index suitable for injection into the system prompt.

    Empty string when the user has no skills yet. Otherwise a markdown
    block grouping skills by category, listing `name: description`
    entries the agent should consider before reaching for general tools.
    """
    skills = all_skills(home)
    if not skills:
        return ""
    by_cat: dict[str, list[tuple[str, str]]] = {}
    for p in skills:
        meta = _frontmatter(p / "SKILL.md")
        name = meta.get("name") or p.name
        desc = meta.get("description") or ""
        cat = meta.get("category") or "miscellaneous"
        by_cat.setdefault(cat, []).append((name, desc))
    lines = [
        "# AVAILABLE SKILLS",
        "Before reaching for general tools (web_search, terminal, "
        "research) check this list. When a skill matches the user's "
        "request, prefer it: load the SKILL.md with "
        "`skill(action='view', name=...)` and follow its instructions. "
        "Skills carry the user's preferred approach for recurring tasks "
        "and often hold cached state from previous runs.",
        "",
    ]
    for cat in sorted(by_cat):
        lines.append(f"  {cat}:")
        for name, desc in sorted(by_cat[cat]):
            if desc:
                lines.append(f"    - {name}: {desc}")
            else:
                lines.append(f"    - {name}")
    return "\n".join(lines)


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


def _atomic_write(path: Path, content: str, mode: int = 0o644) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(content)
    os.chmod(tmp, mode)
    os.replace(tmp, path)


def _ensure_gitignore(skill_dir: Path) -> None:
    gi = skill_dir / ".gitignore"
    if not gi.exists():
        _atomic_write(gi, "secrets/\nstate/\n")


def _check_size(subdir: str, content: str) -> str | None:
    encoded = content.encode("utf-8", errors="replace")
    if len(encoded) > MAX_FILE_BYTES:
        return f"file too large ({len(encoded):,} bytes); limit is {MAX_FILE_BYTES:,}"
    return None


def _require_confirmation(
    skill_dir: Path, confirm_user_skill: bool,
) -> str | None:
    origin = _frontmatter(skill_dir / "SKILL.md").get("origin", "user")
    if origin != "agent" and not confirm_user_skill:
        return (
            f"{skill_dir.name} is origin: {origin}. Pass "
            "confirm_user_skill=true to modify."
        )
    return None


class Skill(Tool):
    name = "skill"
    description = (
        "Manage reusable skills under ~/.alf/skills/<category>/<name>/. "
        "A skill is a directory with a REQUIRED SKILL.md (prose "
        "instructions the LLM loads into context) plus up to five "
        "OPTIONAL subdirectories:\n"
        "\n"
        "  scripts/     executable code the skill invokes via terminal\n"
        "  references/  markdown docs the skill reads via read_file\n"
        "  assets/      templates, data files (non-executable)\n"
        "  secrets/     per-skill credentials. Mode 0700. Gitignored.\n"
        "               Scanner SKIPPED (opaque credential material).\n"
        "  state/       runtime persistence (caches, counters, histories).\n"
        "               Gitignored. Scanner SKIPPED. Scripts read/write\n"
        "               freely; do NOT store code here.\n"
        "               Conventions (not enforced): `.jsonl` for append-\n"
        "               only logs, `.json` for structured snapshots,\n"
        "               `.db` for SQLite. Document what lives in state/\n"
        "               under a '## State' section in SKILL.md so the\n"
        "               LLM sees it without reading the scripts.\n"
        "\n"
        "Each subdirectory is flat — no nested folders. Filenames must "
        "match ``[a-zA-Z0-9][a-zA-Z0-9._-]{0,100}``. Every skill delete "
        "removes the whole directory including secrets/ and state/.\n"
        "\n"
        "**Path conventions for scripts inside a skill.** To read or "
        "write secrets / state at runtime, resolve paths relative to the "
        "script itself — NOT $HOME paths, NOT absolute ~/.alf/... paths:\n"
        "    here = Path(__file__).parent.parent\n"
        "    here / 'secrets' / 'token'\n"
        "    here / 'state' / 'history.jsonl'\n"
        "This way a skill invoked from any profile (alf -p work, -p home, "
        "...) always finds its own data.\n"
        "\n"
        "**Prefer Python stdlib in scripts.** `urllib.request`, "
        "`http.server`, `json`, `threading`, `socketserver` cover most "
        "cases. If a third-party library is genuinely required "
        "(pandas, lxml, etc.) add a '## Setup' section to SKILL.md with "
        "the install command.\n"
        "\n"
        "Actions:\n"
        "  create      — new skill. Scans body, writes SKILL.md + "
        "                .gitignore. Live immediately.\n"
        "  edit        — rewrite SKILL.md body. Preserves frontmatter, "
        "                writes .bak, atomic.\n"
        "  patch       — targeted replace: find old_string in a skill "
        "                file (SKILL.md or subdir file) and swap it for "
        "                new_string. Match must be unique. .bak + atomic.\n"
        "  add_file    — write a file under scripts/references/assets/"
        "                secrets/state/. Create or overwrite. Scanner "
        "                runs except for secrets/ and state/. Atomic.\n"
        "  remove_file — remove one file from a subdirectory.\n"
        "  delete      — remove the whole skill directory.\n"
        "  list        — show every skill grouped by category.\n"
        "  view        — return SKILL.md (no file= arg) or a specific "
        "                skill file. Read-only, cheaper than read_file.\n"
        "\n"
        "NEVER use `edit_file`/`write_file` on paths inside a skill "
        "directory — they bypass the scanner. Always go through this "
        "tool.\n"
        "\n"
        "User-owned skills (origin: user) require "
        "confirm_user_skill=true for edit, patch, add_file, remove_file, "
        "and delete. Agent-owned skills (origin: agent) edit freely."
    )
    parameters = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": [
                    "create", "edit", "patch", "add_file", "remove_file",
                    "delete", "list", "view",
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
                "description": "Pre-create a 0700 secrets/ subdir.",
                "default": False,
            },
            "subdir": {
                "type": "string",
                "enum": sorted(ALLOWED_SUBDIRS),
                "description": "Subdirectory (add_file / remove_file / patch).",
            },
            "filename": {
                "type": "string",
                "description": "Flat filename under subdir (add_file / remove_file / patch).",
            },
            "content": {
                "type": "string",
                "description": "File contents (add_file only).",
            },
            "old_string": {
                "type": "string",
                "description": "Exact string to find (patch only). Must be unique in the file.",
            },
            "new_string": {
                "type": "string",
                "description": "Replacement (patch only).",
            },
            "file": {
                "type": "string",
                "description": "Skill file to view (view only). Empty → SKILL.md. "
                               "Otherwise '<subdir>/<filename>'.",
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
        old_string: str = "",
        new_string: str = "",
        file: str = "",
        confirm_user_skill: bool = False,
    ) -> ToolResult:
        home = get_home()

        if action == "list":
            return _list(home)
        if action == "view":
            return _view(home, name, file)
        if action == "create":
            return _create(home, name, category, description, body,
                           requires_env or [], tools or [], stores_secrets)
        if action == "edit":
            return _edit(home, name, body, confirm_user_skill)
        if action == "patch":
            return _patch(home, name, subdir, filename, old_string,
                          new_string, confirm_user_skill)
        if action == "add_file":
            return _add_file(home, name, subdir, filename, content,
                             confirm_user_skill)
        if action == "remove_file":
            return _remove_file(home, name, subdir, filename,
                                confirm_user_skill)
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


def _view(home: Path, name: str, file: str) -> ToolResult:
    if not name:
        return ToolResult(ok=False, output="", error="'name' is required")
    skill_dir = _find_skill(home, name)
    if skill_dir is None:
        return ToolResult(ok=False, output="", error=f"skill not found: {name}")
    if not file:
        target = skill_dir / "SKILL.md"
    else:
        if "/" not in file:
            return ToolResult(
                ok=False, output="",
                error="file must be '<subdir>/<filename>' (e.g. 'references/foo.md')",
            )
        sub, _, fn = file.partition("/")
        if sub not in ALLOWED_SUBDIRS or not _FILENAME_RE.match(fn):
            return ToolResult(ok=False, output="", error=f"invalid file: {file}")
        target = skill_dir / sub / fn
    if not target.exists():
        return ToolResult(ok=False, output="", error=f"not found: {target}")
    try:
        return ToolResult(ok=True, output=target.read_text())
    except (OSError, UnicodeDecodeError) as e:
        return ToolResult(ok=False, output="", error=f"read failed: {e}")


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
    if len(body) > MAX_BODY_CHARS:
        return ToolResult(ok=False, output="",
                          error=f"body too long ({len(body)}); limit is {MAX_BODY_CHARS}")

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
    _atomic_write(skill_dir / "SKILL.md", "\n".join(frontmatter) + body.strip() + "\n")
    _ensure_gitignore(skill_dir)

    if requires_env:
        example = "\n".join(f"{k}=" for k in requires_env) + "\n"
        _atomic_write(skill_dir / ".env.example", example)

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

    err = _require_confirmation(skill_dir, confirm_user_skill)
    if err:
        return ToolResult(ok=False, output="", error=err)

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

    size_err = _check_size(subdir, content)
    if size_err:
        return ToolResult(ok=False, output="", error=size_err)

    if subdir not in NO_SCAN_SUBDIRS:
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
    mode = 0o600 if subdir == "secrets" else 0o644
    _atomic_write(file_path, content, mode=mode)
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

    err = _require_confirmation(skill_dir, confirm_user_skill)
    if err:
        return ToolResult(ok=False, output="", error=err)

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
    if len(body) > MAX_BODY_CHARS:
        return ToolResult(ok=False, output="",
                          error=f"body too long ({len(body)}); limit is {MAX_BODY_CHARS}")
    skill_dir = _find_skill(home, name)
    if skill_dir is None:
        return ToolResult(ok=False, output="", error=f"skill not found: {name}")

    md = skill_dir / "SKILL.md"
    err = _require_confirmation(skill_dir, confirm_user_skill)
    if err:
        return ToolResult(ok=False, output="", error=err)

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
    _atomic_write(md, header + body.strip() + "\n")
    return ToolResult(ok=True, output=f"edited {md} (backup: {md}.bak)")


def _patch(
    home: Path,
    name: str,
    subdir: str,
    filename: str,
    old_string: str,
    new_string: str,
    confirm_user_skill: bool,
) -> ToolResult:
    if not name:
        return ToolResult(ok=False, output="", error="'name' is required")
    if not old_string:
        return ToolResult(ok=False, output="", error="'old_string' is required")
    skill_dir = _find_skill(home, name)
    if skill_dir is None:
        return ToolResult(ok=False, output="", error=f"skill not found: {name}")

    err = _require_confirmation(skill_dir, confirm_user_skill)
    if err:
        return ToolResult(ok=False, output="", error=err)

    if not subdir and not filename:
        target = skill_dir / "SKILL.md"
        effective_subdir = ""
    else:
        if subdir not in ALLOWED_SUBDIRS:
            return ToolResult(
                ok=False, output="",
                error=f"subdir must be one of {sorted(ALLOWED_SUBDIRS)} (or omit both subdir+filename to patch SKILL.md)",
            )
        if not _FILENAME_RE.match(filename or ""):
            return ToolResult(ok=False, output="", error="invalid filename")
        target = skill_dir / subdir / filename
        effective_subdir = subdir

    if not target.exists():
        return ToolResult(ok=False, output="", error=f"not found: {target}")

    original = target.read_text()
    count = original.count(old_string)
    if count == 0:
        return ToolResult(ok=False, output="", error="old_string not found")
    if count > 1:
        return ToolResult(
            ok=False, output="",
            error=f"old_string matches {count} times; widen with surrounding lines to make it unique",
        )

    patched = original.replace(old_string, new_string, 1)

    size_err = _check_size(effective_subdir or "references", patched)
    if size_err:
        return ToolResult(ok=False, output="", error=size_err)

    if effective_subdir not in NO_SCAN_SUBDIRS:
        flags = scan_skill_body(new_string)
        if flags:
            return ToolResult(ok=False, output="",
                              error=f"security scan blocked patch: {', '.join(flags)}")

    shutil.copy2(target, target.with_suffix(target.suffix + ".bak"))
    mode = 0o600 if effective_subdir == "secrets" else 0o644
    _atomic_write(target, patched, mode=mode)
    return ToolResult(ok=True, output=f"patched {target} (backup: {target}.bak)")


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
    err = _require_confirmation(skill_dir, confirm_user_skill)
    if err:
        return ToolResult(ok=False, output="", error=err)
    shutil.rmtree(skill_dir, ignore_errors=True)
    return ToolResult(ok=True, output=f"deleted {skill_dir}")


TOOL = Skill
