"""Auto-generate a CHANGELOG from git history.

Convention: commit subjects are ``<type>: <subject>`` (see recent
log for types). Every version bump lands a commit that touches the
``version = "..."`` line in ``pyproject.toml`` — those are treated
as version boundaries. Commits between two bumps belong to the
later version. Commits before the first bump go into a "pre-release"
section.

We intentionally keep the renderer simple (no Conventional Commits,
no breaking-change markers, no sub-grouping beyond prefix) because
this repo's history already follows a clean ``type: subject`` shape.
"""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass, field


_PYPROJECT_VERSION_RE = re.compile(r'^version = "([^"]+)"', re.MULTILINE)
_SUBJECT_PREFIX_RE = re.compile(r"^([a-z0-9][\w.+/-]*)\s*:\s*(.+)$", re.IGNORECASE)
# Subjects that don't carry user-visible value (release ritual, meta-tidy).
_SKIP_PREFIXES = {"version", "bump", "release"}
# Trailer lines to strip from commit bodies before quoting the subject.
_TRAILER_RE = re.compile(
    r"\n+(?:Co-Authored-By|Signed-off-by|Co-authored-by):.*|"
    r"\n+🤖 Generated with.*",
    re.IGNORECASE,
)


@dataclass
class Commit:
    sha: str          # short hash
    date: str         # YYYY-MM-DD
    subject: str      # raw subject line, no trailing newline


@dataclass
class Release:
    version: str | None   # None for the pre-release bucket
    date: str | None      # YYYY-MM-DD of the bump commit, or None
    commits: list[Commit] = field(default_factory=list)


def collect(since: str | None = None) -> list[Release]:
    """Return releases oldest-first. ``since`` is an optional git rev."""
    rev_range = f"{since}..HEAD" if since else "HEAD"
    commits = _git_log(rev_range)
    bumps = _find_version_bumps(rev_range)
    return _group(commits, bumps)


def render_markdown(releases: list[Release]) -> str:
    """Newest-first markdown, grouped by prefix within each version."""
    parts: list[str] = ["# Changelog", ""]
    for rel in reversed(releases):
        if rel.version:
            header = f"## v{rel.version}"
            if rel.date:
                header += f" — {rel.date}"
        else:
            header = "## Unreleased"
        parts.append(header)
        parts.append("")

        if not rel.commits:
            parts.append("_No user-visible changes._")
            parts.append("")
            continue

        by_group: dict[str, list[Commit]] = {}
        misc: list[Commit] = []
        for c in rel.commits:
            prefix, _ = _split_prefix(c.subject)
            if prefix:
                by_group.setdefault(prefix.lower(), []).append(c)
            else:
                misc.append(c)

        for group in sorted(by_group.keys()):
            parts.append(f"### {group}")
            for c in by_group[group]:
                _, rest = _split_prefix(c.subject)
                parts.append(f"- {rest or c.subject} (`{c.sha}`)")
            parts.append("")

        if misc:
            parts.append("### misc")
            for c in misc:
                parts.append(f"- {c.subject} (`{c.sha}`)")
            parts.append("")

    return "\n".join(parts).rstrip() + "\n"


# git plumbing


def _git_log(rev_range: str) -> list[Commit]:
    """Return commits oldest-first, excluding merges and pure version bumps."""
    fmt = "%h%x1f%ad%x1f%s%x1e"
    out = _run(
        ["git", "log", "--reverse", "--no-merges",
         "--date=short", f"--pretty=format:{fmt}", rev_range]
    )
    commits: list[Commit] = []
    for record in out.split("\x1e"):
        record = record.strip("\n ")
        if not record:
            continue
        sha, date, subject = record.split("\x1f", 2)
        subject = _clean_subject(subject)
        if _is_skippable(subject):
            continue
        commits.append(Commit(sha=sha, date=date, subject=subject))
    return commits


def _find_version_bumps(rev_range: str) -> list[tuple[str, str, str]]:
    """Return (sha, version, date) for each commit that lands a new version.

    Detected by looking for `+version = "X.Y.Z"` additions in pyproject.toml
    touched by the commit.
    """
    fmt = "%h%x1f%ad"
    out = _run(
        ["git", "log", "--reverse", "--no-merges", "--date=short",
         f"--pretty=format:{fmt}", "-p", "--", "pyproject.toml", rev_range]
    )
    bumps: list[tuple[str, str, str]] = []
    current: tuple[str, str] | None = None
    for line in out.splitlines():
        if "\x1f" in line:
            sha, date = line.split("\x1f", 1)
            current = (sha, date)
            continue
        if current and line.startswith('+version = "'):
            m = _PYPROJECT_VERSION_RE.match(line.lstrip("+"))
            if m:
                bumps.append((current[0], m.group(1), current[1]))
                current = None
    return bumps


def _group(commits: list[Commit], bumps: list[tuple[str, str, str]]) -> list[Release]:
    """Walk commits in order, closing a bucket at each bump.

    Our convention is that the feature commit ALSO bumps the version,
    so the bump commit itself belongs to its own release bucket — not
    the next one.
    """
    bump_by_sha = {sha: (version, date) for sha, version, date in bumps}
    releases: list[Release] = [Release(version=None, date=None)]
    for c in commits:
        releases[-1].commits.append(c)
        if c.sha in bump_by_sha:
            version, date = bump_by_sha[c.sha]
            releases[-1].version = version
            releases[-1].date = date
            releases.append(Release(version=None, date=None))

    # Drop the trailing unreleased bucket if empty.
    if releases[-1].version is None and not releases[-1].commits:
        releases.pop()
    return releases


# Helpers


def _clean_subject(subject: str) -> str:
    return _TRAILER_RE.split(subject, maxsplit=1)[0].strip()


def _split_prefix(subject: str) -> tuple[str, str]:
    m = _SUBJECT_PREFIX_RE.match(subject)
    if not m:
        return "", subject
    return m.group(1), m.group(2).strip()


def _is_skippable(subject: str) -> bool:
    prefix, _ = _split_prefix(subject)
    return prefix.lower() in _SKIP_PREFIXES


def _run(cmd: list[str]) -> str:
    res = subprocess.run(cmd, capture_output=True, text=True, check=True)
    return res.stdout
