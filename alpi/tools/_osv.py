"""OSV malware checks for PyPI/npm package names.

Fail-closed on MAL-* advisories (refuse to save/install), fail-open on
network errors (warn but continue — a flaky network shouldn't block
the user more than the risk the check covers).
"""

from __future__ import annotations

import re
from typing import Iterable

import httpx

_OSV_URL = "https://api.osv.dev/v1/query"
_OSV_BATCH_URL = "https://api.osv.dev/v1/querybatch"

_PYPI_IMPORT_RE = re.compile(r"^\s*(?:from\s+([a-zA-Z_][a-zA-Z0-9_]*)|import\s+([a-zA-Z_][a-zA-Z0-9_]*))", re.M)
_NPM_PKG_RE = re.compile(r"^(@[a-z0-9][\w.-]*\/[a-z0-9][\w.-]*|[a-z0-9][\w.-]*)$", re.I)


def extract_pypi_imports(source: str) -> set[str]:
    """Return the set of top-level module names imported in *source*."""
    names: set[str] = set()
    for m in _PYPI_IMPORT_RE.finditer(source):
        mod = (m.group(1) or m.group(2) or "").split(".", 1)[0]
        if mod:
            names.add(mod)
    return names


def extract_npm_args(args: Iterable[str]) -> set[str]:
    """Extract npm package names from an argv list (e.g. ``npx -y @scope/pkg``)."""
    names: set[str] = set()
    for a in args or []:
        if a.startswith("-") or a.startswith("npx") or not a:
            continue
        if _NPM_PKG_RE.match(a):
            names.add(a)
    return names


def check(ecosystem: str, names: Iterable[str]) -> list[str]:
    """Return a list of human-readable advisories for *names*.

    Empty list = clean. Non-empty = at least one MAL-* hit. Network
    failure is logged via the returned 'warning' string, not raised.
    """
    advisories: list[str] = []
    for name in names:
        hits = _query(ecosystem, name)
        if hits is None:
            advisories.append(f"⚠ OSV unreachable; could not verify {name} ({ecosystem})")
            continue
        for hit in hits:
            advisory_id = hit.get("id", "")
            if advisory_id.startswith("MAL-"):
                summary = hit.get("summary") or "malicious package"
                url = f"https://osv.dev/vulnerability/{advisory_id}"
                advisories.append(f"✗ {name} ({ecosystem}): {advisory_id} — {summary} ({url})")
    return advisories


def check_versions(ecosystem: str, packages: list[tuple[str, str]]) -> dict[str, list[str]] | None:
    """Map package name → advisory IDs affecting its installed version.

    None on network failure (fail-open); empty dict = all clean.
    """
    if not packages:
        return {}
    queries = [
        {"package": {"name": name, "ecosystem": ecosystem}, "version": version}
        for name, version in packages
    ]
    try:
        with httpx.Client(timeout=10.0) as client:
            r = client.post(_OSV_BATCH_URL, json={"queries": queries})
            r.raise_for_status()
            data = r.json() or {}
    except Exception:
        return None
    results = data.get("results") or []
    out: dict[str, list[str]] = {}
    for (name, _version), res in zip(packages, results):
        ids = [v.get("id") for v in (res.get("vulns") or []) if v.get("id")]
        if ids:
            out.setdefault(name, []).extend(ids)
    return out


def _query(ecosystem: str, package: str) -> list[dict] | None:
    body = {"package": {"name": package, "ecosystem": ecosystem}}
    try:
        with httpx.Client(timeout=3.0) as client:
            r = client.post(_OSV_URL, json=body)
            r.raise_for_status()
            data = r.json() or {}
    except Exception:
        return None
    return data.get("vulns") or []
