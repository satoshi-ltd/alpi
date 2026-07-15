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
    re.compile(r"(?:^|/)\.ssh/authorized_keys$", re.I),
    re.compile(r"\.(?:pem|p12|pfx)$", re.I),
    re.compile(r"(?:^|/)\.aws/(?:credentials|config)$", re.I),
    re.compile(r"(?:^|/)\.gnupg/", re.I),
    re.compile(r"(?:^|/)\.(?:netrc|npmrc|pypirc|pgpass)$", re.I),
    re.compile(r"(?:^|/)\.config/(?:gh|gcloud)/", re.I),
    # Shell rc / login files and launchd plists — persistence write vectors.
    re.compile(r"(?:^|/)\.(?:bashrc|zshrc|bash_profile|zprofile|zlogin|profile)$", re.I),
    re.compile(r"(?:^|/)Library/Launch(?:Agents|Daemons)/", re.I),
    # Profile secrets and config must only be edited by hand or setup.
    re.compile(r"(?:^|/)\.alpi(?:/profiles/[^/]+)?/config\.yaml$"),
    # .env* blocked except .env.example/.sample/.template/.dist
    re.compile(r"(?:^|/)\.env(?!\.(?:example|sample|template|dist)$)[^/]*$", re.I),
    # Skill secrets dir (mode 0700, scanner-skipped) — never via file tools.
    re.compile(r"(?:^|/)skills/[^/]+/[^/]+/secrets/", re.I),
)


# Off-limits to members for READ as well as write — reading host/ would leak an admin token and escalate.
_MEMBER_HOME_AREA: frozenset[str] = frozenset({
    "host", "secrets", "gateway", "cache", "logs", "outputs",
    "sessions", "memories", "schedule", "skills", "alp",
})
_MEMBER_HOME_REGEX = re.compile(
    r"(?:^|/)\.alpi(?:/profiles/[^/]+)?/"
    r"(host|secrets|gateway|cache|logs|outputs|sessions|memories|schedule|skills|alp)(?:/|$)"
)
_ALP_SECRETS_RE = re.compile(r"(?:^|/)alp/secrets(?:/|$)")


def _member_home_area(*paths: Path | str) -> str | None:
    for p in paths:
        m = _MEMBER_HOME_REGEX.search(str(p))
        if m:
            return m.group(1)
    # Fallback for a custom ALPI_HOME whose dir is not literally named ``.alpi``.
    from alpi.home import get_home
    try:
        home = get_home().resolve()
    except Exception:
        return None
    for p in paths:
        try:
            rel = Path(p).resolve().relative_to(home)
        except (ValueError, OSError):
            continue
        if rel.parts and rel.parts[0] in _MEMBER_HOME_AREA:
            return rel.parts[0]
    return None


def _member_denied_area(p: Path | str, resolved: Path, *, for_write: bool) -> str | None:
    area = _member_home_area(p, resolved)
    if area is None:
        return None
    # Members may READ alp/ (peer mentions, workgroup transcripts) — never the keypair, never on write.
    if area == "alp" and not for_write:
        if not (_ALP_SECRETS_RE.search(str(p)) or _ALP_SECRETS_RE.search(str(resolved))):
            return None
    return area


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
    # Check both the typed path and the resolved path.
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


def resolve_path(path: str, *, for_write: bool = False) -> Path:
    """Expand + resolve a path and refuse sensitive system locations.

    Relative paths root at the active workspace (matches the path rule
    in the system prompt). No workspace sandbox — reads and writes can
    reach anywhere on disk except the entries in the sensitive lists.
    Member file tools are also fenced out of the home private area, except
    read-only alp/ transcripts.
    """
    p = Path(path).expanduser()
    if not p.is_absolute():
        p = _workspace_root() / p
    resolved = p.resolve()
    hit = _is_sensitive(p, resolved)
    if hit is not None:
        raise ValueError(f"refusing to touch sensitive path: {path}")
    from alpi.host.connection_context import current
    if current().role != "admin":
        area = _member_denied_area(p, resolved, for_write=for_write)
        if area is not None:
            verb = "write to" if for_write else "read"
            raise ValueError(
                f"members cannot {verb} the profile {area}/ area; "
                f"this requires an admin device: {path}"
            )
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
