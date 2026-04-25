"""Path resolution + sensitive-path denylist shared by file tools."""

from __future__ import annotations

import re
from pathlib import Path


_SENSITIVE_PATH_PREFIXES: tuple[str, ...] = (
    "/etc/", "/boot/", "/sys/", "/proc/",
    "/usr/lib/systemd/", "/System/",
    "/private/etc/",
)

_SENSITIVE_EXACT_PATHS: frozenset[str] = frozenset({
    "/var/run/docker.sock",
    "/run/docker.sock",
})

_SENSITIVE_PATH_REGEX: tuple[re.Pattern[str], ...] = (
    re.compile(r"(?:^|/)\.ssh/(?:id_|.*_key$|.*_ed25519$)", re.I),
    re.compile(r"\.(?:pem|p12|pfx)$", re.I),
    re.compile(r"(?:^|/)\.aws/credentials$", re.I),
    re.compile(r"(?:^|/)\.gnupg/", re.I),
    # Profile secrets and config — must only be edited by hand or via
    # `alpi setup`, never through file tools or terminal redirection.
    re.compile(r"(?:^|/)\.alpi(?:/profiles/[^/]+)?/(?:\.env|config\.yaml)$"),
)


def _workspace_root() -> Path:
    from alpi.home import get_home
    try:
        from alpi import config as cfg_mod
        cfg = cfg_mod.load(get_home().resolve())
        wp = cfg.workspace_path
    except Exception:
        wp = None
    return wp if wp is not None else Path.cwd().resolve()


def _is_sensitive(*paths: Path | str) -> str | None:
    # Check each variant we were given: the user-typed path (pre-resolve)
    # can be /var/run/docker.sock on macOS while resolve() rewrites it to
    # /private/var/run/docker.sock via the /var symlink. Either form
    # should match.
    for p in paths:
        s = str(p)
        if s in _SENSITIVE_EXACT_PATHS:
            return s
        for prefix in _SENSITIVE_PATH_PREFIXES:
            if s.startswith(prefix):
                return prefix
        for rx in _SENSITIVE_PATH_REGEX:
            if rx.search(s):
                return rx.pattern
    return None


def resolve_path(path: str) -> Path:
    """Expand + resolve a path and refuse sensitive system locations.

    Relative paths root at the active workspace (matches the path rule
    in the system prompt). No workspace sandbox — reads and writes can
    reach anywhere on disk except the entries in the sensitive lists.
    """
    p = Path(path).expanduser()
    if not p.is_absolute():
        p = _workspace_root() / p
    resolved = p.resolve()
    hit = _is_sensitive(p, resolved)
    if hit is not None:
        raise ValueError(f"refusing to touch sensitive path: {path}")
    return resolved


def suggest_similar_paths(target: Path, limit: int = 5) -> list[str]:
    """List entries in the target's parent that fuzzy-match its basename."""
    parent = target.parent
    if not parent.exists() or not parent.is_dir():
        return []
    needle = target.name.lower()
    if not needle:
        return []
    scored: list[tuple[int, str]] = []
    try:
        for child in parent.iterdir():
            name = child.name
            nl = name.lower()
            if nl == needle:
                continue
            if needle in nl:
                scored.append((0, str(child)))
            elif nl.startswith(needle[: max(3, len(needle) // 2)]):
                scored.append((1, str(child)))
            elif needle in nl or nl in needle:
                scored.append((2, str(child)))
    except OSError:
        return []
    scored.sort(key=lambda t: (t[0], t[1]))
    return [s for _, s in scored[:limit]]


