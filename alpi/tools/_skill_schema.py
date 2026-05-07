"""SKILL.md frontmatter schema — errors block, warnings inform; one ``Issue`` per problem."""

from __future__ import annotations

import re
from dataclasses import dataclass


_NAME_RE = re.compile(r"^[a-z][a-z0-9-]{1,60}$")
_VERSION_RE = re.compile(r"^\d+\.\d+\.\d+(?:[+-][\w.+-]+)?$")
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_ENV_VAR_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

_VALID_ORIGINS = frozenset({"agent", "user", "bundled"})

DESC_MAX = 150
NAME_MIN = 2


@dataclass(frozen=True)
class Issue:
    field: str
    severity: str  # "error" or "warning"
    message: str

    def render(self) -> str:
        prefix = "✗" if self.severity == "error" else "⚠"
        return f"{prefix} {self.field}: {self.message}"


def validate_frontmatter(
    meta: dict[str, str],
    *,
    categories: set[str],
) -> list[Issue]:
    """``categories`` injected so adding one in ``skill.CATEGORIES`` doesn't drift here."""
    issues: list[Issue] = []

    issues.extend(_check_name(meta))
    issues.extend(_check_description(meta))
    issues.extend(_check_category(meta, categories))
    issues.extend(_check_version(meta))
    issues.extend(_check_origin(meta))
    issues.extend(_check_requires_env(meta))
    issues.extend(_check_tools(meta))
    issues.extend(_check_keywords(meta))
    issues.extend(_check_created_at(meta))

    return issues


def errors(issues: list[Issue]) -> list[Issue]:
    return [i for i in issues if i.severity == "error"]


def warnings(issues: list[Issue]) -> list[Issue]:
    return [i for i in issues if i.severity == "warning"]


def render_issues(issues: list[Issue]) -> str:
    return "\n".join(i.render() for i in issues)


# Per-field validators

def _check_name(meta: dict[str, str]) -> list[Issue]:
    name = (meta.get("name") or "").strip()
    if not name:
        return [Issue("name", "error", "required")]
    if not _NAME_RE.match(name):
        return [Issue(
            "name", "error",
            f"must be kebab-case, {NAME_MIN}-61 chars, lowercase letters / "
            f"digits / hyphens (got {name!r})",
        )]
    return []


def _check_description(meta: dict[str, str]) -> list[Issue]:
    desc = (meta.get("description") or "").strip()
    if not desc:
        return [Issue("description", "error", "required")]
    out: list[Issue] = []
    if len(desc) > DESC_MAX:
        # Warning only — bundled instructional descriptions can exceed it legitimately.
        out.append(Issue(
            "description", "warning",
            f"long ({len(desc)} chars; soft limit {DESC_MAX}) — descriptions "
            "are headlines, keep them short unless the skill is bundled and "
            "instructional",
        ))
    if desc.endswith("."):
        out.append(Issue(
            "description", "warning",
            "drop the trailing period — descriptions are headlines, not sentences",
        ))
    return out


def _check_category(meta: dict[str, str], categories: set[str]) -> list[Issue]:
    cat = (meta.get("category") or "").strip()
    valid = sorted(categories)
    if not cat:
        return [Issue("category", "error", f"required; one of: {valid}")]
    if cat not in categories:
        return [Issue(
            "category", "error",
            f"unknown {cat!r}; valid: {valid}",
        )]
    return []


def _check_version(meta: dict[str, str]) -> list[Issue]:
    ver = (meta.get("version") or "").strip()
    if not ver:
        return []
    if not _VERSION_RE.match(ver):
        return [Issue(
            "version", "warning",
            f"not semver-shaped (X.Y.Z): {ver!r}",
        )]
    return []


def _check_origin(meta: dict[str, str]) -> list[Issue]:
    origin = (meta.get("origin") or "").strip()
    if not origin:
        return []
    if origin not in _VALID_ORIGINS:
        return [Issue(
            "origin", "error",
            f"must be one of {sorted(_VALID_ORIGINS)} (got {origin!r})",
        )]
    return []


def _check_requires_env(meta: dict[str, str]) -> list[Issue]:
    raw = (meta.get("requires_env") or "").strip().strip("[]")
    if not raw:
        return []
    out: list[Issue] = []
    for part in raw.split(","):
        item = part.strip().strip("'\"")
        if not item:
            continue
        if not _ENV_VAR_RE.match(item):
            out.append(Issue(
                "requires_env", "error",
                f"{item!r} is not a valid env-var name (alnum + underscore, "
                "must not start with a digit)",
            ))
    return out


def _check_keywords(meta: dict[str, str]) -> list[Issue]:
    """Lowercase alnum+hyphen tokens; the booster doesn't normalise punctuation."""
    raw = (meta.get("keywords") or "").strip().strip("[]")
    if not raw:
        return []
    out: list[Issue] = []
    seen: set[str] = set()
    for part in raw.split(","):
        item = part.strip().strip("'\"")
        if not item:
            continue
        if not re.match(r"^[a-z0-9][a-z0-9-]*$", item):
            out.append(Issue(
                "keywords", "warning",
                f"{item!r} should be lowercase alnum+hyphen — the matcher "
                "lower-cases the user's message but does no further "
                "normalisation",
            ))
        if item.lower() in seen:
            out.append(Issue(
                "keywords", "warning",
                f"duplicate keyword {item!r}",
            ))
        seen.add(item.lower())
    return out


def _check_tools(meta: dict[str, str]) -> list[Issue]:
    raw = (meta.get("tools") or "").strip().strip("[]")
    if not raw:
        return []
    out: list[Issue] = []
    for part in raw.split(","):
        item = part.strip().strip("'\"")
        if not item:
            continue
        if not re.match(r"^[a-z][a-zA-Z0-9_]*(__[a-zA-Z][a-zA-Z0-9_]*)?$", item):
            out.append(Issue(
                "tools", "warning",
                f"{item!r} doesn't match alpi tool naming "
                "(snake_case for built-ins, name__method for MCP) — typo?",
            ))
    return out


def _check_created_at(meta: dict[str, str]) -> list[Issue]:
    raw = (meta.get("created_at") or "").strip()
    if not raw:
        return []
    if not _DATE_RE.match(raw):
        return [Issue(
            "created_at", "warning",
            f"expected YYYY-MM-DD (got {raw!r})",
        )]
    return []
