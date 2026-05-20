"""skill — manage reusable skills under ~/.alpi/skills/."""

from __future__ import annotations

import os
import re
import shutil
import sys
import json
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from alpi.home import get_home
from alpi.tools.base import Tool, ToolResult


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

_SECRET_ENV_NAME_RE = re.compile(r"(?:KEY|TOKEN|SECRET|PASSWORD|CREDENTIAL)", re.I)
_PY_GETENV_RE = re.compile(r"os\.getenv\s*\(\s*[\"']([^\"']+)[\"']", re.I)
_NODE_ENV_RE = re.compile(
    r"process\.env(?:\[\s*[\"']([^\"']+)[\"']\s*\]|\.(\w+))",
    re.I,
)
_PY_PRINT_GETENV_RE = re.compile(
    r"print\s*\([^)]*os\.getenv\s*\(\s*[\"']([^\"']+)[\"']",
    re.I | re.S,
)
_NODE_LOG_ENV_RE = re.compile(
    r"console\.(?:log|error|warn)\s*\([^)]*process\.env"
    r"(?:\[\s*[\"']([^\"']+)[\"']\s*\]|\.(\w+))",
    re.I | re.S,
)
_EDIT_PLACEHOLDER_RE = re.compile(
    r"^\s*(?:\[?pending[_ -]?view\]?|todo|tbd|\.{3}|<placeholder>)\s*$",
    re.I,
)


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
    (re.compile(r"(?:\$HOME|~)/\.alpi/\.env"),           "reads alpi .env"),
    (re.compile(r"(?:cat|head|tail|less|more|cp|mv)\s+[^\n]*(?:\.env\b|credentials\b|\.netrc\b|\.pgpass\b|\.npmrc\b|\.pypirc\b)"),
                                                         "reads known secrets file"),
    (re.compile(r"\bprintenv\b|\benv\s*\|"),            "dumps all env"),
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
    (re.compile(
        r"\bngrok\s+(?:http|tcp|tls|start)\b|"
        r"\bcloudflared\s+tunnel\b|"
        r"\blocaltunnel\s+--port\b|"
        r"\blt\s+--port\b|"
        r"\bssh\s+-R\s+\d+:[^\s]+\s+serveo\.net\b",
        re.I,
    ),                                                   "tunneling service"),
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


def scan_skill_body(body: str, allowed_env: set[str] | None = None) -> list[str]:
    findings = [label for pat, label in _DANGER_PATTERNS if pat.search(body)]
    findings.extend(_scan_secret_env_reads(body, allowed_env or set()))
    return findings


def _scan_secret_env_reads(body: str, allowed_env: set[str]) -> list[str]:
    findings: list[str] = []
    for match in _PY_PRINT_GETENV_RE.finditer(body):
        var = match.group(1)
        if _SECRET_ENV_NAME_RE.search(var):
            findings.append("prints secret env")
    for match in _NODE_LOG_ENV_RE.finditer(body):
        var = match.group(1) or match.group(2) or ""
        if _SECRET_ENV_NAME_RE.search(var):
            findings.append("prints secret env")
    for match in _PY_GETENV_RE.finditer(body):
        var = match.group(1)
        if _SECRET_ENV_NAME_RE.search(var) and var not in allowed_env:
            findings.append("python reads undeclared secret env")
    for match in _NODE_ENV_RE.finditer(body):
        var = match.group(1) or match.group(2) or ""
        if _SECRET_ENV_NAME_RE.search(var) and var not in allowed_env:
            findings.append("node reads undeclared secret env")
    return findings


BUNDLED_PREFIX = "@alpi/"


def _bundled_root():
    try:
        from importlib.resources import files
        return files("alpi.skills")
    except (ModuleNotFoundError, FileNotFoundError):
        return None


def _bundled_skill(name: str):
    if not name.startswith(BUNDLED_PREFIX):
        return None
    base = _bundled_root()
    if base is None:
        return None
    target = base / name[len(BUNDLED_PREFIX):]
    return target if target.is_dir() else None


def bundled_skills() -> list[dict]:
    base = _bundled_root()
    if base is None:
        return []
    out: list[dict] = []
    for entry in sorted(base.iterdir(), key=lambda p: p.name):
        if entry.name.startswith("_") or not entry.is_dir():
            continue
        skill_md = entry / "SKILL.md"
        if not skill_md.is_file():
            continue
        meta = _frontmatter_from_text(skill_md.read_text())
        out.append({
            "name": f"{BUNDLED_PREFIX}{entry.name}",
            "category": meta.get("category") or "miscellaneous",
            "description": meta.get("description") or "",
            "path": entry,
            "meta": meta,
        })
    return out


def all_skills(home: Path) -> list[Path]:
    root = home / "skills"
    if not root.exists():
        return []
    out: list[Path] = []
    for cat in sorted(root.iterdir()):
        if (not cat.is_dir()
                or cat.name.startswith(("_", "@", "."))):
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


def skills_index_block(home: Path, cfg_raw: dict[str, Any] | None = None) -> str:
    """Compact skills index for system-prompt injection.

    User skills first, bundled (`@alpi/*`) after with a `[bundled]`
    marker. Empty string when neither is present.
    """
    from alpi.home import effective_profile_env

    user_skills = all_skills(home)
    bundled = bundled_skills()
    if not user_skills and not bundled:
        return ""

    if cfg_raw is None:
        cfg_raw = _load_cfg_raw(home)
    profile_env = effective_profile_env(home)

    lines = [
        "# AVAILABLE SKILLS",
        "Before reaching for general tools (web_search, terminal, "
        "research) check this list. When a skill matches the user's "
        "request, prefer it: load the SKILL.md with "
        "`skill(action='view', name=...)` and follow its instructions. "
        "User skills (listed first) carry the user's preferred approach "
        "and often hold cached state from previous runs; bundled skills "
        "(marked `[bundled]`, prefix `@alpi/`) ship with alpi and are "
        "read-only.",
        "",
    ]

    from alpi.tools import _skill_schema as _schema
    by_cat: dict[str, list[tuple[str, str]]] = {}
    for p in user_skills:
        meta = _frontmatter(p / "SKILL.md")
        # Schema-invalid skills stay out of the prompt regardless of eligibility — malformed frontmatter is unsafe to expose.
        if _schema.errors(_schema.validate_frontmatter(meta, categories=CATEGORIES)):
            continue
        eligible, _missing = skill_eligibility(meta, env=profile_env, cfg_raw=cfg_raw)
        if not eligible:
            continue
        name = meta.get("name") or p.name
        desc = meta.get("description") or ""
        cat = meta.get("category") or "miscellaneous"
        by_cat.setdefault(cat, []).append((name, desc))
    for cat in sorted(by_cat):
        lines.append(f"  {cat}:")
        for name, desc in sorted(by_cat[cat]):
            lines.append(f"    - {name}: {desc}" if desc else f"    - {name}")

    eligible_bundled = [
        b for b in bundled
        if skill_eligibility(b.get("meta", {}), env=profile_env, cfg_raw=cfg_raw)[0]
    ]

    if eligible_bundled:
        if by_cat:
            lines.append("")
        lines.append("  @alpi/ [bundled]:")
        for b in eligible_bundled:
            desc = b["description"]
            lines.append(
                f"    - {b['name']}: {desc}" if desc else f"    - {b['name']}"
            )

        if any(b["name"] == "@alpi/knowledge" for b in eligible_bundled):
            lines.append("")
            lines.append(
                "RULE — alpi self-knowledge: if the user's question "
                "mentions ``alpi`` (the project — config, commands, "
                "protocol, skills, deployment, install), CALL "
                "``skill(action='view', name='@alpi/knowledge')`` "
                "FIRST and read the routing table inside. Then read "
                "the relevant ``references/<topic>.md``. The bundled "
                "docs are authoritative; your training is not — alpi "
                "shipped after your cutoff. Do NOT answer alpi "
                "questions from general knowledge."
            )
    return "\n".join(lines)


def _find_skill(home: Path, name: str):
    bundled = _bundled_skill(name)
    if bundled is not None:
        return bundled
    for p in all_skills(home):
        if p.name == name:
            return p
    return None


def _frontmatter(md_path: Path) -> dict[str, str]:
    if not md_path.exists():
        return {}
    return _frontmatter_from_text(md_path.read_text())


def _is_pinned(skill_dir: Path) -> bool:
    meta = _frontmatter(skill_dir / "SKILL.md")
    return (meta.get("pinned") or "").strip().lower() == "true"


def _frontmatter_from_text(text: str) -> dict[str, str]:
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


def _parse_env_list(raw: str) -> list[str]:
    s = (raw or "").strip().strip("[]")
    if not s:
        return []
    out: list[str] = []
    for part in s.split(","):
        name = part.strip().strip("'\"")
        if name and all(c.isalnum() or c == "_" for c in name):
            out.append(name)
    return out


def _parse_str_list(raw: str) -> list[str]:
    """Permissive list-of-strings parser; no charset enforcement."""
    s = (raw or "").strip().strip("[]")
    if not s:
        return []
    out: list[str] = []
    for part in s.split(","):
        item = part.strip().strip("'\"")
        if item:
            out.append(item)
    return out


def skill_keywords(meta: dict[str, str]) -> list[str]:
    return [k.lower() for k in _parse_str_list(meta.get("keywords", ""))]


_VALID_PLATFORMS = frozenset({"macos", "linux", "windows"})

# sys.platform → ALPI canonical platform identifier
_SYS_PLATFORM_MAP = {
    "darwin": "macos",
    "linux": "linux",
    "linux2": "linux",
    "win32": "windows",
    "cygwin": "windows",
}


def _current_platform() -> str:
    return _SYS_PLATFORM_MAP.get(sys.platform, sys.platform)


_BIN_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._+-]*$")


def _parse_bin_list(raw: str) -> list[str]:
    return [b for b in _parse_str_list(raw) if _BIN_NAME_RE.match(b)]


def _parse_config_path_list(raw: str) -> list[str]:
    return [p for p in _parse_str_list(raw) if re.match(r"^[A-Za-z_][A-Za-z0-9_.]*$", p)]


def _parse_platform_list(raw: str) -> list[str]:
    return [p.lower() for p in _parse_str_list(raw) if p.lower() in _VALID_PLATFORMS]


def _config_path_set(cfg_raw: dict[str, Any], dotted: str) -> bool:
    cur: Any = cfg_raw
    for part in dotted.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return False
        cur = cur[part]
    return cur not in (None, "", [], {})


def _load_cfg_raw(home: Path) -> dict[str, Any]:
    try:
        from alpi import config as _cfg_mod
        return _cfg_mod.load(home).raw or {}
    except Exception:  # noqa: BLE001
        return {}


def skill_requirements(meta: dict[str, str]) -> dict[str, list[str]]:
    return {
        "env": _parse_env_list(meta.get("requires_env", "")),
        "bins": _parse_bin_list(meta.get("requires_bins", "")),
        "config": _parse_config_path_list(meta.get("requires_config", "")),
        "platforms": _parse_platform_list(meta.get("platforms", "")),
    }


def _declared_env_for_skill(skill_dir: Path) -> set[str]:
    meta = _frontmatter(skill_dir / "SKILL.md")
    return set(_parse_env_list(meta.get("requires_env", ""))) | set(
        _parse_env_list(meta.get("env", ""))
    )


def skill_eligibility(
    meta: dict[str, str],
    *,
    env: dict[str, str] | None = None,
    cfg_raw: dict[str, Any] | None = None,
) -> tuple[bool, list[str]]:
    """``(ok, [reasons, …])`` — eligible iff every declared requires_* resolves now.

    ``requires_env`` / ``requires_bins`` / ``platforms`` are always checked.
    ``requires_config`` is checked only when ``cfg_raw`` is passed; legacy
    callers that omit it skip the config check rather than silently hiding
    skills that depend on profile config keys.
    """
    env_map = env if env is not None else os.environ
    reqs = skill_requirements(meta)
    missing: list[str] = []

    for var in reqs["env"]:
        if not env_map.get(var):
            missing.append(f"env var {var}")

    for bin_name in reqs["bins"]:
        if shutil.which(bin_name) is None:
            missing.append(f"binary {bin_name}")

    if reqs["platforms"]:
        current = _current_platform()
        if current not in reqs["platforms"]:
            missing.append(
                f"platform {'/'.join(reqs['platforms'])} (this is {current})"
            )

    if cfg_raw is not None and reqs["config"]:
        for path in reqs["config"]:
            if not _config_path_set(cfg_raw, path):
                missing.append(f"config key {path}")

    return (not missing, missing)


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
        "Save, load, or maintain a reusable recipe. Use when a "
        "multi-step workflow would otherwise have to be re-explained "
        "from scratch next time, or when you discover a non-trivial "
        "approach worth preserving.\n"
        "\n"
        "Language: write SKILL.md (body + frontmatter + every file "
        "in the skill dir) in ENGLISH, regardless of the chat "
        "language. Skill bodies reload into the system prompt every "
        "time the skill is opened — non-English content biases "
        "replies forever. Translate before writing.\n"
        "\n"
        "Skills live under ~/.alpi/skills/<category>/<name>/. Each "
        "skill is a directory with a REQUIRED SKILL.md (prose "
        "instructions the LLM loads into context) plus up to five "
        "OPTIONAL subdirectories:\n"
        "\n"
        "  scripts/     executable code the skill invokes via terminal\n"
        "  references/  markdown docs the skill reads via read_file\n"
        "  assets/      templates, data files (non-executable)\n"
        "  secrets/     per-skill credentials. Created lazily, mode 0700. Gitignored.\n"
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
        "script itself — NOT $HOME paths, NOT absolute ~/.alpi/... paths:\n"
        "    here = Path(__file__).parent.parent\n"
        "    here / 'secrets' / 'token'\n"
        "    here / 'state' / 'history.jsonl'\n"
        "This way a skill invoked from any profile (alpi -p work, -p home, "
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
        "  edit        — REPLACE the entire SKILL.md PROSE body. The "
        "                existing frontmatter (the ``---`` block at "
        "                the top) is preserved verbatim. Do NOT "
        "                include ``---`` lines or YAML metadata in "
        "                your ``body`` argument — to update "
        "                frontmatter fields use ``set_meta``. To "
        "                ADD to existing prose without losing what's "
        "                there: call ``view`` first, build the full "
        "                new body, then ``edit``. For a surgical "
        "                insertion use ``patch`` instead. Obvious "
        "                placeholder bodies are rejected. .bak + atomic.\n"
        "  set_meta    — update frontmatter fields without touching "
        "                the prose. Prefer ``fields={'requires_env': "
        "                ['VAR'], 'tools': ['db'], 'keywords': "
        "                ['foo']}``. For "
        "                compatibility, top-level ``requires_env`` / "
        "                ``tools`` / ``keywords`` / ``description`` / "
        "                ``category`` are also accepted on set_meta. "
        "                Only provided keys overwrite; everything else "
        "                stays. Schema-validated; surfaces warnings. "
        "                .bak + atomic.\n"
        "  patch       — targeted replace: find old_string in a skill "
        "                file (SKILL.md or subdir file) and swap it for "
        "                new_string. To patch SKILL.md, omit both "
        "                subdir and filename. To patch subfiles, pass "
        "                subdir + filename. Match must be unique. .bak "
        "                + atomic.\n"
        "  add_file    — write a file under scripts/references/assets/"
        "                secrets/state/. Create or overwrite. Scanner "
        "                runs except for secrets/ and state/. Writing "
        "                to secrets/ creates it mode 0700; secret files "
        "                are mode 0600. Atomic.\n"
        "  remove_file — remove one file from a subdirectory.\n"
        "  delete      — archive the skill (move to "
        "                ``skills/.archive/<category>/<name>__<UTC>/``). "
        "                Recoverable: ``mv`` it back. Pinned skills "
        "                (``pinned: True`` in frontmatter) refuse to "
        "                archive — unpin via ``set_meta`` first.\n"
        "  list        — show every skill grouped by category.\n"
        "  view        — return SKILL.md (no file= arg) or a specific "
        "                skill file. With file=, output starts with "
        "                absolute_path; use that path to run scripts, "
        "                never scripts/foo.py relative to the workspace. "
        "                Read-only, cheaper than read_file.\n"
        "  validate    — run cheap correctness checks on a skill's "
        "                scripts/*.py: syntax, missing imports "
        "                (AST + find_spec), OAuth race patterns "
        "                (webbrowser.open before serve_forever), and port "
        "                coherence between SKILL.md and bind() calls. "
        "                Non-blocking: just reports findings.\n"
        "  reset_state — wipe everything under <skill>/state/ (e.g. db.sqlite, "
        "                .jsonl logs) without touching scripts/secrets/SKILL.md. "
        "                Use after a schema change leaves the DB inconsistent.\n"
        "  run         — execute a skill end-to-end. If the skill has "
        "                ``scripts/run.py``, runs it via terminal under the "
        "                skill's declared env and returns stdout. Otherwise "
        "                returns SKILL.md so you follow it step-by-step. "
        "                Use this instead of `view` + manual `terminal` — "
        "                it handles cwd, env, and timeouts. Optional ``args`` "
        "                pass extra CLI arguments to the script.\n"
        "  test        — exercise the scripted runtime (`scripts/run.py`) "
        "                using the same path as `run`, then validate stdout "
        "                against `output_schema` when the skill declares one. "
        "                This is only for scripted skills; prose-only skills "
        "                should be tested by running the real tools in chat.\n"
        "  invoke      — structured skill-to-skill composition. Same runtime "
        "                as `run`, but stricter: only scripted skills with "
        "                `output_schema` are allowed. Stdout must be JSON "
        "                matching that schema.\n"
        "\n"
        "**When to create scripts/run.py.** Do it only for deterministic "
        "local code: parsing files, transforming data, calling normal "
        "Python libraries, or maintaining skill-local state. Do NOT create "
        "a script for skills that depend on agent tools or MCP methods "
        "(`memory`, `schedule`, `send_message`, `bitbucket__…`, etc.). "
        "Those are agent-run skills: keep the instructions in SKILL.md and "
        "let `skill(action='run')` return them so the agent calls the real "
        "tools. Tools and MCP methods are not importable Python APIs.\n"
        "\n"
        "**Persistent SQLite.** Skills that need structured state (more "
        "than a single JSON blob) use the ``db`` tool: "
        "``db(action='exec'|'query', skill=<name>, sql='…', params=[…])``. "
        "It opens ``<skill>/state/db.sqlite`` lazily — no schema "
        "registration here, just call ``CREATE TABLE IF NOT EXISTS …`` "
        "the first time. Quotas: 50 MB file, 10k rows per query, 5 s "
        "busy timeout. Use ``skill(action='reset_state')`` to wipe.\n"
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
                    "delete", "list", "view", "validate", "reset_state",
                    "set_meta", "run", "test", "invoke",
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
                "description": (
                    "Env vars the skill needs to run. ENFORCED at "
                    "system-prompt build time: a skill missing any of "
                    "these is hidden from the LLM until the user "
                    "populates ~/.alpi/.env. Surfaced in "
                    "skill(action='list') with an [inactive: …] tag."
                ),
                "default": [],
            },
            "requires_bins": {
                "type": "array",
                "items": {"type": "string"},
                "description": (
                    "Executables the skill needs on PATH (e.g. 'gh', "
                    "'ffmpeg', 'sqlite3'). Same enforcement as "
                    "requires_env: missing bins hide the skill from "
                    "the prompt; surfaced in list with [inactive: …]."
                ),
                "default": [],
            },
            "requires_config": {
                "type": "array",
                "items": {"type": "string"},
                "description": (
                    "Profile config keys (dotted paths, e.g. "
                    "'home_assistant.url') the user must set explicitly "
                    "in ``~/.alpi/config.yaml``. Only user-written keys "
                    "count — alpi defaults do not satisfy this gate. "
                    "Missing keys hide the skill from the prompt."
                ),
                "default": [],
            },
            "platforms": {
                "type": "array",
                "items": {"type": "string", "enum": ["macos", "linux", "windows"]},
                "description": (
                    "Operating systems where the skill works. Empty list "
                    "= portable. Skills declaring platforms incompatible "
                    "with the current OS are hidden from the prompt."
                ),
                "default": [],
            },
            "tools": {
                "type": "array",
                "items": {"type": "string"},
                "description": (
                    "Minimal list of tools this skill actually calls "
                    "(create only). Metadata only — it's NOT enforced at "
                    "runtime. Include ONLY the tools the body strictly "
                    "needs; do not pad with tools that MIGHT be useful. "
                    "Example: a notify skill that runs a shell command "
                    "and sends one Telegram message is `['terminal', "
                    "'send_message']`, nothing more."
                ),
                "default": [],
            },
            "keywords": {
                "type": "array",
                "items": {"type": "string"},
                "description": (
                    "Optional lowercase tokens that boost this skill in "
                    "the system-prompt index when the user's message "
                    "mentions one. Helps small models with discovery; "
                    "big models pick from descriptions just fine. Use "
                    "concrete domain terms (e.g. ['whoop', 'workout']) "
                    "— common verbs (do, run, fetch) match too often."
                ),
                "default": [],
            },
            "output_schema": {
                "type": "string",
                "description": (
                    "Optional one-line JSON schema for stdout produced by "
                    "scripts/run.py. Use a small JSON Schema subset: "
                    "`type`, `properties`, `required`, `items`, `enum`."
                ),
                "default": "",
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
            "fields": {
                "type": "object",
                "description": (
                    "Frontmatter fields to overwrite (set_meta only). "
                    "Each key replaces the same-named line in the "
                    "existing frontmatter; keys not provided keep "
                    "their current value. List values are written as "
                    "Python repr (``['a', 'b']``) for round-trip "
                    "compatibility with the existing parser."
                ),
                "additionalProperties": True,
            },
            "args": {
                "type": "array",
                "items": {"type": "string"},
                "description": (
                    "Extra CLI arguments forwarded to scripts/run.py "
                    "(run only). Empty list = no extra args."
                ),
                "default": [],
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
        requires_bins: list[str] | None = None,
        requires_config: list[str] | None = None,
        platforms: list[str] | None = None,
        tools: list[str] | None = None,
        keywords: list[str] | None = None,
        output_schema: str = "",
        fields: dict | None = None,
        subdir: str = "",
        filename: str = "",
        content: str = "",
        old_string: str = "",
        new_string: str = "",
        file: str = "",
        confirm_user_skill: bool = False,
        args: list[str] | None = None,
    ) -> ToolResult:
        home = get_home()

        if action == "list":
            return _list(home)
        if action == "view":
            return _view(home, name, file)
        mutating = {"create", "edit", "patch", "add_file",
                    "remove_file", "delete"}
        if action in mutating and name.startswith(BUNDLED_PREFIX):
            return ToolResult(
                ok=False, output="",
                error=(
                    f"{name!r} is a bundled skill — read-only. Create "
                    f"your own variant with a different name in another "
                    f"category (e.g. category='personal')."
                ),
            )
        if action == "create":
            return _create(home, name, category, description, body,
                           requires_env or [], tools or [],
                           keywords or [], output_schema,
                           requires_bins=requires_bins or [],
                           requires_config=requires_config or [],
                           platforms=platforms or [])
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
        if action == "validate":
            return _validate(home, name)
        if action == "reset_state":
            return _reset_state(home, name, confirm_user_skill)
        if action == "run":
            return _run(home, name, args or [])
        if action == "test":
            return _test(home, name, args or [])
        if action == "invoke":
            return _invoke(home, name, args or [])
        if action == "set_meta":
            meta_fields = dict(fields or {})
            if description:
                meta_fields["description"] = description
            if category:
                meta_fields["category"] = category
            if requires_env is not None:
                meta_fields["requires_env"] = requires_env
            if requires_bins is not None:
                meta_fields["requires_bins"] = requires_bins
            if requires_config is not None:
                meta_fields["requires_config"] = requires_config
            if platforms is not None:
                meta_fields["platforms"] = platforms
            if tools is not None:
                meta_fields["tools"] = tools
            if keywords is not None:
                meta_fields["keywords"] = keywords
            if output_schema:
                meta_fields["output_schema"] = output_schema
            return _set_meta(home, name, meta_fields, confirm_user_skill)
        return ToolResult(ok=False, output="", error=f"unknown action: {action}")


def _state_tag(
    meta: dict[str, str],
    *,
    env: dict[str, str] | None = None,
    cfg_raw: dict[str, Any] | None = None,
) -> str:
    """``""`` | ``[invalid: …]`` | ``[inactive: …]``; runtime ``broken`` lives in ``validate``."""
    from alpi.tools import _skill_schema as _schema
    schema_errors = _schema.errors(
        _schema.validate_frontmatter(meta, categories=CATEGORIES)
    )
    if schema_errors:
        first = schema_errors[0]
        more = f", +{len(schema_errors) - 1} more" if len(schema_errors) > 1 else ""
        return f"  [invalid: {first.field} ({first.message}){more}]"
    ok, missing = skill_eligibility(meta, env=env, cfg_raw=cfg_raw)
    if not ok:
        return f"  [inactive: missing {', '.join(missing)}]"
    return ""


def _list(home: Path) -> ToolResult:
    """List every skill tagged via ``_state_tag``; ``validate`` runs the deeper checks."""
    from alpi.home import effective_profile_env
    cfg_raw = _load_cfg_raw(home)
    env = effective_profile_env(home)
    lines: list[str] = []
    root = home / "skills"
    if root.exists():
        for cat in sorted(root.iterdir()):
            if (not cat.is_dir()
                    or cat.name.startswith(("_", "@", "."))):
                continue
            skill_dirs = sorted(s for s in cat.iterdir() if s.is_dir())
            if not skill_dirs:
                continue
            lines.append(f"{cat.name}:")
            for s in skill_dirs:
                meta = _frontmatter(s / "SKILL.md")
                lines.append(f"  - {s.name}{_state_tag(meta, env=env, cfg_raw=cfg_raw)}")
    bundled = bundled_skills()
    if bundled:
        if lines:
            lines.append("")
        lines.append("@alpi/ [bundled]:")
        for b in bundled:
            lines.append(f"  - {b['name']}{_state_tag(b.get('meta', {}), env=env, cfg_raw=cfg_raw)}")
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
    if not target.is_file():
        return ToolResult(ok=False, output="", error=f"not found: {file or 'SKILL.md'}")
    try:
        body = target.read_text()
    except (OSError, UnicodeDecodeError) as e:
        return ToolResult(ok=False, output="", error=f"read failed: {e}")
    if not file:
        # ``env`` is legacy alias for ``requires_env`` — both forwarded to terminal subprocess.
        from alpi.tools import _state
        meta = _frontmatter_from_text(body)
        env_decl = _parse_env_list(meta.get("requires_env", ""))
        env_decl += _parse_env_list(meta.get("env", ""))
        if env_decl:
            _state.add_skill_env(env_decl)
        return ToolResult(ok=True, output=body)
    body = f"absolute_path: {target}\n\n{body}"
    return ToolResult(ok=True, output=body)


def _create(
    home: Path,
    name: str,
    category: str,
    description: str,
    body: str,
    requires_env: list[str],
    tools: list[str],
    keywords: list[str],
    output_schema: str,
    *,
    requires_bins: list[str] | None = None,
    requires_config: list[str] | None = None,
    platforms: list[str] | None = None,
) -> ToolResult:
    from alpi.tools import _skill_schema as _schema

    requires_bins = list(requires_bins or [])
    requires_config = list(requires_config or [])
    platforms = [p.lower() for p in (platforms or [])]

    if not body:
        return ToolResult(ok=False, output="", error="'body' is required")
    if len(body) > MAX_BODY_CHARS:
        return ToolResult(ok=False, output="",
                          error=f"body too long ({len(body)}); limit is {MAX_BODY_CHARS}")

    pseudo_meta = {
        "name": name,
        "description": description,
        "category": category,
        "requires_env": str(list(requires_env)),
        "requires_bins": str(requires_bins),
        "requires_config": str(requires_config),
        "platforms": str(platforms),
        "tools": str(list(tools)),
        "keywords": str(list(keywords)),
        "output_schema": output_schema,
    }
    issues = _schema.validate_frontmatter(pseudo_meta, categories=CATEGORIES)
    blocking = _schema.errors(issues)
    if blocking:
        return ToolResult(
            ok=False, output="",
            error="invalid frontmatter:\n" + _schema.render_issues(blocking),
        )
    schema_warnings = _schema.warnings(issues)

    flags = scan_skill_body(body, allowed_env=set(requires_env))
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
    ]
    if requires_bins:
        frontmatter.append(f"requires_bins: {requires_bins}")
    if requires_config:
        frontmatter.append(f"requires_config: {requires_config}")
    if platforms:
        frontmatter.append(f"platforms: {platforms}")
    frontmatter.extend([
        f"tools: {list(tools)}",
        f"keywords: {[k.lower() for k in keywords]}",
        f"created_at: {date.today().isoformat()}",
    ])
    if output_schema:
        frontmatter.append(f"output_schema: {output_schema}")
    frontmatter.extend(["---", ""])
    _atomic_write(skill_dir / "SKILL.md", "\n".join(frontmatter) + body.strip() + "\n")
    _ensure_gitignore(skill_dir)

    if requires_env:
        example = "\n".join(f"{k}=" for k in requires_env) + "\n"
        _atomic_write(skill_dir / ".env.example", example)

    base_msg = (
        f"Created skill '{name}' (category: {category}) at {skill_dir}. "
        f"It is live immediately. Use `skill(action='add_file', ...)` "
        f"to flesh out scripts/references/assets/secrets."
    )
    if schema_warnings:
        base_msg += (
            "\n\nschema warnings (non-blocking — consider `skill(action='edit')` to fix):\n"
            + _schema.render_issues(schema_warnings)
        )
    return ToolResult(
        ok=True,
        output=_annotate_with_validation(base_msg, skill_dir),
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
        flags = scan_skill_body(
            content,
            allowed_env=_declared_env_for_skill(skill_dir),
        )
        if flags:
            return ToolResult(
                ok=False, output="",
                error=f"security scan blocked file: {', '.join(flags)}",
            )

    if subdir == "scripts" and filename.endswith(".py"):
        osv_err = _osv_scan_python(content)
        if osv_err:
            return ToolResult(ok=False, output="", error=osv_err)

    sub_path = skill_dir / subdir
    if subdir == "secrets":
        sub_path.mkdir(mode=0o700, exist_ok=True)
    else:
        sub_path.mkdir(exist_ok=True)

    file_path = sub_path / filename
    mode = 0o600 if subdir == "secrets" else 0o644
    _atomic_write(file_path, content, mode=mode)
    return ToolResult(
        ok=True,
        output=_annotate_with_validation(f"wrote {file_path}", skill_dir),
    )


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
    return ToolResult(
        ok=True,
        output=_annotate_with_validation(f"removed {file_path}", skill_dir),
    )


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
    # ``edit`` REPLACES — placeholder body would nuke real prose.
    if _EDIT_PLACEHOLDER_RE.match(body):
        return ToolResult(
            ok=False, output="",
            error=(
                "body looks like a placeholder. ``edit`` REPLACES the "
                "entire SKILL.md prose — it does not append. To add to "
                "existing content, call ``skill(action='view', name=…)`` "
                "first and ``edit`` with the complete new body, OR use "
                "``skill(action='patch', name=…, old_string=…, "
                "new_string=…)`` for a surgical insertion."
            ),
        )
    # ``edit`` body must be prose-only — frontmatter goes through ``set_meta``.
    if re.match(r"\s*---\s*\n.*?\n---\s*", body, re.DOTALL):
        return ToolResult(
            ok=False, output="",
            error=(
                "body contains a ``---`` frontmatter block. ``edit`` "
                "only rewrites the prose body — frontmatter is preserved "
                "automatically. Either drop the ``---`` block from your "
                "body, or use ``skill(action='set_meta', name=…, "
                "fields={…})`` to update individual frontmatter fields "
                "without touching the prose."
            ),
        )
    skill_dir = _find_skill(home, name)
    if skill_dir is None:
        return ToolResult(ok=False, output="", error=f"skill not found: {name}")

    md = skill_dir / "SKILL.md"
    err = _require_confirmation(skill_dir, confirm_user_skill)
    if err:
        return ToolResult(ok=False, output="", error=err)

    flags = scan_skill_body(body, allowed_env=_declared_env_for_skill(skill_dir))
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
    return ToolResult(
        ok=True,
        output=_annotate_with_validation(
            f"edited {md} (backup: {md}.bak)", skill_dir,
        ),
    )


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
        flags = scan_skill_body(
            new_string,
            allowed_env=_declared_env_for_skill(skill_dir),
        )
        if flags:
            return ToolResult(ok=False, output="",
                              error=f"security scan blocked patch: {', '.join(flags)}")

    shutil.copy2(target, target.with_suffix(target.suffix + ".bak"))
    mode = 0o600 if effective_subdir == "secrets" else 0o644
    _atomic_write(target, patched, mode=mode)
    return ToolResult(
        ok=True,
        output=_annotate_with_validation(
            f"patched {target} (backup: {target}.bak)", skill_dir,
        ),
    )


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
    if _is_pinned(skill_dir):
        return ToolResult(
            ok=False, output="",
            error=(
                f"{name!r} is pinned and protected from deletion. Unpin "
                f"first with skill(action='set_meta', name={name!r}, "
                f"fields={{'pinned': False}})."
            ),
        )
    # Auto-archive: move to skills/.archive/<category>/<name>__<UTC>/ rather
    # than destroy. Recoverable via `mv` back to skills/<category>/<name>/.
    category = skill_dir.parent.name
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    archive_dir = home / "skills" / ".archive" / category
    archive_dir.mkdir(parents=True, exist_ok=True)
    dest = archive_dir / f"{name}__{timestamp}"
    shutil.move(str(skill_dir), str(dest))
    return ToolResult(
        ok=True,
        output=(
            f"archived {skill_dir} → {dest}\n"
            f"(recover with: mv {dest} {skill_dir})"
        ),
    )


def _osv_scan_python(source: str) -> str | None:
    """Return an error string if the source imports a malicious PyPI pkg."""
    import sys
    from alpi.tools._osv import check, extract_pypi_imports
    imports = extract_pypi_imports(source)
    thirdparty = {
        m for m in imports
        if m not in sys.stdlib_module_names and m != "alpi"
    }
    if not thirdparty:
        return None
    advisories = [a for a in check("PyPI", thirdparty) if a.startswith("✗")]
    if advisories:
        return "OSV malware check blocked save:\n" + "\n".join(advisories)
    return None


def _validate(home: Path, name: str) -> ToolResult:
    if not name:
        return ToolResult(ok=False, output="", error="'name' is required")
    skill_dir = _find_skill(home, name)
    if skill_dir is None:
        return ToolResult(ok=False, output="", error=f"skill not found: {name}")
    findings = _run_validate(skill_dir)
    if not findings:
        return ToolResult(ok=True, output="(no issues)")
    has_errors = any(f.startswith("✗") for f in findings)
    return ToolResult(ok=not has_errors, output="\n".join(findings))


_RUN_TIMEOUT_SECONDS = 600


def _run(home: Path, name: str, args: list[str]) -> ToolResult:
    """Execute a skill end-to-end. Skill execution model:

    1. ``scripts/run.py`` exists → spawn it with the skill's declared env,
       cwd = skill dir, capture stdout/stderr, return combined output.
    2. No script → return SKILL.md prefixed with a directive so the agent
       knows to follow the prose itself instead of ``view``-then-improvise.
    """
    return _run_or_test(home, name, args, mode="run")


def _test(home: Path, name: str, args: list[str]) -> ToolResult:
    return _run_or_test(home, name, args, mode="test")


def _invoke(home: Path, name: str, args: list[str]) -> ToolResult:
    return _run_or_test(home, name, args, mode="invoke")


def _run_or_test(home: Path, name: str, args: list[str], *, mode: str) -> ToolResult:
    import subprocess
    import sys

    if not name:
        return ToolResult(ok=False, output="", error="'name' is required")
    skill_dir = _find_skill(home, name)
    if skill_dir is None:
        return ToolResult(ok=False, output="", error=f"skill not found: {name}")

    skill_md = skill_dir / "SKILL.md"
    eligibility_meta = _frontmatter(skill_md) if skill_md.is_file() else {}
    from alpi.home import effective_profile_env
    ok, missing = skill_eligibility(
        eligibility_meta,
        env=effective_profile_env(home),
        cfg_raw=_load_cfg_raw(home),
    )
    if not ok:
        return ToolResult(
            ok=False, output="",
            error=(
                f"skill {name!r} is inactive: missing {', '.join(missing)}. "
                f"Resolve the missing requirements before calling {mode}."
            ),
        )

    script = skill_dir / "scripts" / "run.py"

    if not script.is_file():
        if mode in {"test", "invoke"}:
            return ToolResult(
                ok=False, output="",
                error=(
                    f"skill {name!r} has no scripts/run.py; only scripted skills "
                    f"support {mode}"
                ),
            )
        if not skill_md.is_file():
            return ToolResult(
                ok=False, output="",
                error=f"skill {name!r} has neither scripts/run.py nor SKILL.md",
            )
        body = skill_md.read_text()
        return ToolResult(
            ok=True,
            output=(
                f"[skill {name!r} has no scripts/run.py — follow these "
                f"instructions to execute it manually]\n\n{body}"
            ),
        )

    meta = eligibility_meta
    declared_env = _parse_env_list(meta.get("requires_env", ""))
    declared_env += _parse_env_list(meta.get("env", ""))

    from alpi.tools import _skill_schema as _schema
    from alpi.tools._skill_validate import validate_skill

    blockers = [f for f in validate_skill(skill_dir) if f.startswith("✗")]
    if blockers:
        return ToolResult(
            ok=False, output="\n".join(blockers),
            error=f"skill {name!r} failed validation",
        )

    output_schema = None
    raw_schema = (meta.get("output_schema") or "").strip()
    if raw_schema:
        output_schema, schema_error = _schema.parse_output_schema(raw_schema)
        if schema_error:
            return ToolResult(
                ok=False, output="",
                error=f"skill {name!r} has invalid output_schema: {schema_error}",
            )
    elif mode == "invoke":
        return ToolResult(
            ok=False, output="",
            error=f"skill {name!r} has no output_schema; invoke requires a structured contract",
        )

    from alpi.home import effective_profile_env
    env = effective_profile_env(home, extra={
        "ALPI_HOME": str(home),
        "ALPI_SKILL_NAME": name,
        "ALPI_SKILL_DIR": str(skill_dir),
    })

    missing = [v for v in declared_env if v and not env.get(v)]
    if missing:
        return ToolResult(
            ok=False, output="",
            error=(
                f"skill {name!r} requires env vars not set: "
                f"{', '.join(missing)}. Populate ~/.alpi/.env first."
            ),
        )

    try:
        proc = subprocess.run(
            [sys.executable, str(script), *args],
            cwd=str(skill_dir),
            env=env,
            capture_output=True,
            text=True,
            timeout=_RUN_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired:
        return ToolResult(
            ok=False, output="",
            error=f"skill {name!r} timed out after {_RUN_TIMEOUT_SECONDS}s",
        )
    except OSError as e:
        return ToolResult(ok=False, output="", error=f"failed to spawn: {e}")

    out = (proc.stdout or "").rstrip()
    err = (proc.stderr or "").rstrip()
    combined = out
    if err:
        combined = f"{out}\n[stderr]\n{err}" if out else err

    if proc.returncode != 0:
        return ToolResult(
            ok=False, output=combined,
            error=f"script exited rc={proc.returncode}",
        )

    if output_schema is not None:
        try:
            payload = json.loads(out or "null")
        except json.JSONDecodeError as e:
            return ToolResult(
                ok=False, output=combined,
                error=(
                    f"skill {name!r} declared output_schema but stdout was not JSON "
                    f"({e.msg})"
                ),
            )
        findings = _schema.validate_output_data(output_schema, payload)
        if findings:
            return ToolResult(
                ok=False,
                output=combined,
                error="output_schema mismatch:\n" + "\n".join(findings),
            )

    if mode == "test":
        if output_schema is not None:
            header = f"[test ok] {name}: scripts/run.py output matches output_schema"
        else:
            header = f"[test ok] {name}: scripts/run.py exited successfully (no output_schema declared)"
        return ToolResult(ok=True, output=f"{header}\n\n{combined or '(no output)'}")
    if mode == "invoke":
        return ToolResult(ok=True, output=combined or "null")
    return ToolResult(ok=True, output=combined or "(no output)")


def _reset_state(
    home: Path, name: str, confirm_user_skill: bool,
) -> ToolResult:
    """Wipe ``<skill>/state/`` contents; dir + mode preserved."""
    if not name:
        return ToolResult(ok=False, output="", error="'name' is required")
    if name.startswith(BUNDLED_PREFIX):
        return ToolResult(
            ok=False, output="",
            error=f"{name!r} is bundled — read-only, no state to reset",
        )
    skill_dir = _find_skill(home, name)
    if skill_dir is None:
        return ToolResult(ok=False, output="", error=f"skill not found: {name}")
    err = _require_confirmation(skill_dir, confirm_user_skill)
    if err:
        return ToolResult(ok=False, output="", error=err)
    state = skill_dir / "state"
    if not state.exists():
        return ToolResult(ok=True, output=f"no state to reset for {name}")
    removed = 0
    for entry in list(state.iterdir()):
        if entry.is_file() or entry.is_symlink():
            entry.unlink()
            removed += 1
        elif entry.is_dir():
            shutil.rmtree(entry)
            removed += 1
    return ToolResult(
        ok=True,
        output=f"reset_state: removed {removed} entr{'y' if removed == 1 else 'ies'} from {state}",
    )


_HINT_MAX_SKILLS = 3


def _keyword_matches(text_tokens: set[str], keywords: list[str]) -> bool:
    """Whole-token match (no substring); hyphenated keywords stay one token."""
    return any(kw and kw in text_tokens for kw in keywords)


def _keyword_tokens(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+(?:-[a-z0-9]+)*", text.lower()))


_META_KEY_ORDER = (
    "name", "description", "category", "version", "origin",
    "requires_env", "requires_bins", "requires_config", "platforms",
    "tools", "keywords", "output_schema",
    "pinned", "created_at",
    "env",  # legacy alias
)


def _format_meta_value(key: str, value: object) -> str:
    """Render for the flat-dict parser: lists → repr, bools → ``True``/``False``."""
    if isinstance(value, list):
        return repr([str(v) for v in value])
    if isinstance(value, bool):
        return str(value)
    return str(value)


def _set_meta(
    home: Path,
    name: str,
    fields: dict,
    confirm_user_skill: bool,
) -> ToolResult:
    """Surgical frontmatter update — prose preserved byte-for-byte; schema-validated."""
    if not name:
        return ToolResult(ok=False, output="", error="'name' is required")
    if not fields:
        return ToolResult(
            ok=False, output="",
            error="'fields' must be a non-empty dict of frontmatter keys to update",
        )
    unknown = sorted(k for k in fields if k not in _META_KEY_ORDER)
    if unknown:
        return ToolResult(
            ok=False, output="",
            error=f"unknown frontmatter field(s): {', '.join(unknown)}",
        )
    if name.startswith(BUNDLED_PREFIX):
        return ToolResult(
            ok=False, output="",
            error=f"{name!r} is bundled — read-only",
        )
    skill_dir = _find_skill(home, name)
    if skill_dir is None:
        return ToolResult(ok=False, output="", error=f"skill not found: {name}")
    err = _require_confirmation(skill_dir, confirm_user_skill)
    if err:
        return ToolResult(ok=False, output="", error=err)

    md = skill_dir / "SKILL.md"
    if not md.exists():
        return ToolResult(ok=False, output="", error="SKILL.md not found")
    text = md.read_text()
    if not text.startswith("---"):
        return ToolResult(
            ok=False, output="",
            error="SKILL.md has no frontmatter block to update",
        )
    try:
        _, raw_front, body = text.split("---", 2)
    except ValueError:
        return ToolResult(ok=False, output="", error="malformed frontmatter")

    # Preserve file order; only changed keys move.
    lines: list[tuple[str, str]] = []
    seen: set[str] = set()
    for line in raw_front.strip().splitlines():
        if ":" not in line:
            lines.append(("__raw__", line))
            continue
        k, v = line.split(":", 1)
        k = k.strip()
        v = v.strip()
        lines.append((k, v))
        seen.add(k)

    overrides: dict[str, str] = {
        k: _format_meta_value(k, v) for k, v in fields.items()
    }
    new_lines: list[tuple[str, str]] = []
    handled: set[str] = set()
    for k, v in lines:
        if k in overrides:
            new_lines.append((k, overrides[k]))
            handled.add(k)
        else:
            new_lines.append((k, v))
    for k in _META_KEY_ORDER:
        if k in overrides and k not in handled:
            new_lines.append((k, overrides[k]))
            handled.add(k)
    pseudo_meta = {k: v for k, v in new_lines if k != "__raw__"}
    from alpi.tools import _skill_schema as _schema
    issues = _schema.validate_frontmatter(pseudo_meta, categories=CATEGORIES)
    blocking = _schema.errors(issues)
    if blocking:
        return ToolResult(
            ok=False, output="",
            error="invalid frontmatter after update:\n"
                  + _schema.render_issues(blocking),
        )

    rebuilt = ["---"]
    for k, v in new_lines:
        rebuilt.append(v if k == "__raw__" else f"{k}: {v}")
    rebuilt.append("---")
    new_text = "\n".join(rebuilt) + body

    shutil.copy2(md, md.with_suffix(".md.bak"))
    _atomic_write(md, new_text)

    msg = f"set_meta: updated {sorted(overrides)} on {name}"
    schema_warnings = _schema.warnings(issues)
    if schema_warnings:
        msg += "\n\nschema warnings (non-blocking):\n" + _schema.render_issues(schema_warnings)
    return ToolResult(
        ok=True,
        output=_annotate_with_validation(msg, skill_dir),
    )


def keyword_match_hint(
    home: Path,
    user_text: str,
    cfg_raw: dict[str, Any] | None = None,
) -> str:
    """Per-turn skill boost; ``""`` when no eligible skill matches; cap ``_HINT_MAX_SKILLS``."""
    if not user_text or not user_text.strip():
        return ""
    tokens = _keyword_tokens(user_text)
    if not tokens:
        return ""
    if cfg_raw is None:
        cfg_raw = _load_cfg_raw(home)
    from alpi.home import effective_profile_env
    from alpi.tools import _skill_schema as _schema
    env = effective_profile_env(home)
    hits: list[str] = []
    for path in all_skills(home):
        meta = _frontmatter(path / "SKILL.md")
        if _schema.errors(_schema.validate_frontmatter(meta, categories=CATEGORIES)):
            continue
        if not skill_eligibility(meta, env=env, cfg_raw=cfg_raw)[0]:
            continue
        if _keyword_matches(tokens, skill_keywords(meta)):
            hits.append(meta.get("name") or path.name)
    for b in bundled_skills():
        meta = b.get("meta", {})
        if _schema.errors(_schema.validate_frontmatter(meta, categories=CATEGORIES)):
            continue
        if not skill_eligibility(meta, env=env, cfg_raw=cfg_raw)[0]:
            continue
        if _keyword_matches(tokens, skill_keywords(meta)):
            hits.append(b["name"])
    if not hits:
        return ""
    unique = sorted(set(hits))[:_HINT_MAX_SKILLS]
    return (
        "# SKILL HINT (this turn only)\n"
        f"The user's message matches keywords from: {', '.join(unique)}. "
        "If the task fits, prefer ``skill(action='view', name=…)`` over the "
        "general tools."
    )


def _run_validate(skill_dir: Path) -> list[str]:
    """Schema (frontmatter) + runtime (syntax/imports/oauth/ports) findings."""
    from alpi.tools import _skill_schema as _schema
    from alpi.tools._skill_validate import validate_skill

    out: list[str] = []
    md = skill_dir / "SKILL.md"
    if md.exists():
        meta = _frontmatter(md)
        for issue in _schema.validate_frontmatter(meta, categories=CATEGORIES):
            out.append(issue.render())
    out.extend(validate_skill(skill_dir))
    return out


def _annotate_with_validation(message: str, skill_dir: Path) -> str:
    findings = _run_validate(skill_dir)
    if not findings:
        return message
    return f"{message}\n\nvalidation:\n  " + "\n  ".join(findings)


TOOL = Skill
