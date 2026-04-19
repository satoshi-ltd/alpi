"""HOME_DIR resolution for alf.

Resolves which ~/.alf/ directory the current invocation should use.

Default profile lives at ``~/.alf``. Named profiles live at
``~/.alf/profiles/<name>`` and are fully isolated (own config, memories,
skills, sessions, schedule, gateway).

Resolution order (no sticky state — explicit on every call):

1. ``ALF_HOME`` env var           → absolute override, skips profile logic
2. ``--profile/-p`` CLI flag      → ``~/.alf/profiles/<name>``
3. ``ALF_PROFILE`` env var        → ``~/.alf/profiles/<name>``
4. ``~/.alf`` (default profile)

If a user wants "always this profile" they set up a shell alias
(``alias alfw='alf -p work'``) or export ``ALF_PROFILE`` in their
rc file. No hidden file, no surprise switches between terminals.
"""

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
    """Bootstrap the home directory tree on first run.

    Creates the full subtree. Seed files (PERSONALITY.md, config.yaml, memories/*.md)
    are written by their respective modules when they first need them.
    """
    for sub in (
        "memories",
        "sessions",
        "skills",
        "schedule/output",
        "gateway/logs",
    ):
        (home / sub).mkdir(parents=True, exist_ok=True)


def personality_path(home: Path) -> Path:
    """Return the canonical PERSONALITY.md path for this profile."""
    return home / "PERSONALITY.md"
