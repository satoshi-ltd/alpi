"""HOME_DIR resolution for alpi."""

from __future__ import annotations

import os
from contextvars import ContextVar
from pathlib import Path
from typing import Optional

_ROOT = Path.home() / ".alpi"


# Active-home context for concurrent daemon turns.
_HOME_CTX: ContextVar[Optional[Path]] = ContextVar(
    "alpi_active_home", default=None,
)


def set_active_home(home: Optional[Path]) -> object:
    """Bind ``home`` to the current context and return the reset token."""
    return _HOME_CTX.set(home)


def reset_active_home(token: object) -> None:
    _HOME_CTX.reset(token)


def get_home(profile: Optional[str] = None) -> Path:
    # Context binding wins; env fallback is for one-shot commands.
    active = _HOME_CTX.get()
    if active is not None:
        return active

    override = os.environ.get("ALPI_HOME")
    if override:
        return Path(override).expanduser()

    name = profile or os.environ.get("ALPI_PROFILE")
    if name and name != "default":
        return _ROOT / "profiles" / name
    return _ROOT


def home_for(name: str) -> Path:
    """Resolve a profile literally; never honour ``ALPI_HOME``."""
    if not name or name == "default":
        return _ROOT
    return _ROOT / "profiles" / name


def alpi_root() -> Path:
    """Return the alpi home root, honoring ``ALPI_HOME`` — ignores any profile selection."""
    override = os.environ.get("ALPI_HOME")
    if override:
        return Path(override).expanduser()
    return _ROOT


def profile_name(home: Path) -> str:
    """Inverse of ``home_for``: ``~/.alpi`` → ``default``; ``~/.alpi/profiles/<n>`` → ``<n>``."""
    parts = home.parts
    if "profiles" in parts:
        i = parts.index("profiles")
        if i + 1 < len(parts):
            return parts[i + 1]
    return "default"


def list_profiles(root: Path | None = None) -> list[str]:
    """Return ``default`` plus each profile directory under ``<root>``."""
    base = root or _ROOT
    out = ["default"]
    sub = base / "profiles"
    if sub.exists():
        for p in sorted(sub.iterdir(), key=lambda x: x.name):
            if p.is_dir() and not p.name.startswith("."):
                out.append(p.name)
    return out


def ensure_home(home: Path) -> None:
    """Bootstrap the home directory tree on first run."""
    for sub in (
        "memories",
        "secrets",
        "sessions",
        "skills",
        "schedule/output",
        "logs",
    ):
        (home / sub).mkdir(parents=True, exist_ok=True)
    gi = home / ".gitignore"
    if not gi.exists():
        gi.write_text(
            ".env\n"
            "secrets/\n"
            "sessions/\n"
            "mentions/\n"
            "gateway/sessions/\n"
            "schedule/output/\n"
            "logs/\n"
            "cache/\n"
            "skills/**/secrets/\n"
        )


def agent_path(home: Path) -> Path:
    return home / "memories" / "AGENT.md"


def format_bytes(n: int) -> str:
    if n < 1024:
        return f"{n}B"
    if n < 1024 ** 2:
        return f"{n / 1024:.0f}KB"
    if n < 1024 ** 3:
        return f"{n / 1024 ** 2:.1f}MB"
    return f"{n / 1024 ** 3:.2f}GB"


_SIZE_CACHE: dict[Path, tuple[float, str]] = {}
_SIZE_TTL = 30.0


def profile_size_label(home_dir: Path) -> str:
    import time
    now = time.time()
    cached = _SIZE_CACHE.get(home_dir)
    if cached and (now - cached[0]) < _SIZE_TTL:
        return cached[1]
    excluded = home_dir / "profiles"
    total = 0
    try:
        for p in home_dir.rglob("*"):
            if excluded in p.parents or p == excluded:
                continue
            if p.is_file():
                try:
                    total += p.stat().st_size
                except OSError:
                    pass
    except OSError:
        return ""
    label = format_bytes(total)
    _SIZE_CACHE[home_dir] = (now, label)
    return label


def shorten_home(path: Path | str) -> str:
    s = str(path)
    home = str(Path.home())
    if s == home:
        return "~"
    if s.startswith(home + "/") or s.startswith(home + "\\"):
        return "~" + s[len(home):]
    return s
