"""HOME_DIR resolution for alpi."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

_ROOT = Path.home() / ".alpi"


def get_home(profile: Optional[str] = None) -> Path:
    override = os.environ.get("ALPI_HOME")
    if override:
        return Path(override).expanduser()

    name = profile or os.environ.get("ALPI_PROFILE")
    if name and name != "default":
        return _ROOT / "profiles" / name
    return _ROOT


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
