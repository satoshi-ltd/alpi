"""HOME_DIR resolution for alf.

Resolves which ~/.alf/ directory the current invocation should use.

Default profile lives at ``~/.alf``. Named profiles live at
``~/.alf/profiles/<name>`` and are fully isolated (own config, memories,
skills, sessions, schedule, gateway).

Resolution order:
1. ``ALF_HOME`` env var (absolute override, skips profile logic)
2. ``--profile/-p`` CLI flag  → ``~/.alf/profiles/<name>``
3. ``ALF_PROFILE`` env var    → ``~/.alf/profiles/<name>``
4. sticky default stored in  ``~/.alf/.current-profile``
5. ``~/.alf`` (default profile)
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

_ROOT = Path.home() / ".alf"
_CURRENT_PROFILE_FILE = _ROOT / ".current-profile"


def get_home(profile: Optional[str] = None) -> Path:
    override = os.environ.get("ALF_HOME")
    if override:
        return Path(override).expanduser()

    name = profile or os.environ.get("ALF_PROFILE") or _sticky_profile()
    if name and name != "default":
        return _ROOT / "profiles" / name
    return _ROOT


def _sticky_profile() -> Optional[str]:
    if _CURRENT_PROFILE_FILE.exists():
        value = _CURRENT_PROFILE_FILE.read_text().strip()
        return value or None
    return None


def ensure_home(home: Path) -> None:
    """Bootstrap the home directory tree on first run.

    Creates the full subtree. Seed files (PERSONALITY.md, config.yaml, memories/*.md)
    are written by their respective modules when they first need them.
    """
    # One-time migration: v0.1 wrote jobs + logs under ``cron/``. We now
    # use ``schedule/`` to match the user-facing terminology. If the old
    # dir exists and the new one doesn't, move it. Safe to remove after
    # everyone has run a v0.2+ alf at least once.
    legacy = home / "cron"
    target = home / "schedule"
    if legacy.exists() and not target.exists():
        legacy.rename(target)

    for sub in (
        "memories",
        "sessions",
        "skills",
        "schedule/output",
        "gateway/logs",
    ):
        (home / sub).mkdir(parents=True, exist_ok=True)


def personality_path(home: Path) -> Path:
    """Return the canonical PERSONALITY.md path, migrating legacy names in-place.

    Legacy names (in order of precedence): ``SOUL.md``, ``personality.md``.
    """
    canonical = home / "PERSONALITY.md"
    if canonical.exists():
        return canonical
    for legacy_name in ("personality.md", "SOUL.md"):
        legacy = home / legacy_name
        if legacy.exists():
            legacy.rename(canonical)
            return canonical
    return canonical
