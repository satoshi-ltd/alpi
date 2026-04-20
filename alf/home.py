"""HOME_DIR resolution for alf."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

_ROOT = Path.home() / ".alf"


def get_home(profile: Optional[str] = None) -> Path:
    override = os.environ.get("ALF_HOME")
    if override:
        return Path(override).expanduser()

    name = profile or os.environ.get("ALF_PROFILE")
    if name and name != "default":
        return _ROOT / "profiles" / name
    return _ROOT


def ensure_home(home: Path) -> None:
    """Bootstrap the home directory tree on first run."""
    for sub in (
        "memories",
        "sessions",
        "skills",
        "schedule/output",
        "gateway/logs",
    ):
        (home / sub).mkdir(parents=True, exist_ok=True)
    gi = home / ".gitignore"
    if not gi.exists():
        gi.write_text(
            ".env\n"
            "sessions/\n"
            "schedule/output/\n"
            "gateway/logs/\n"
            "cache/\n"
            "skills/**/secrets/\n"
        )


def personality_path(home: Path) -> Path:
    """Return the canonical PERSONALITY.md path for this profile."""
    return home / "PERSONALITY.md"
