#!/usr/bin/env python3
"""Sync user-facing docs into the bundled @alpi/knowledge skill.

The bundled skill ships its documentation as package resources so
``@alpi/knowledge`` works after a fresh ``uv tool install
alpi-agent`` without needing the source tree. The references live
under ``alpi/skills/knowledge/references/`` and are kept in lockstep
with ``docs/`` and the top-level ``README.md`` / ``CHANGELOG.md`` /
``QUICKSTART.md`` by running this script before commit.

Run::

    uv run python scripts/sync_knowledge.py

The script is idempotent — it copies each source file into the
bundled directory only if the content differs, so a clean run
produces no changes when the docs are already in sync.

Files NOT bundled (internal-only):
- docs/ROADMAP.md (planning, not user-facing)
- docs/RELEASE.md (maintainer's cut checklist)
- LICENSE (legal, not knowledge)
"""

from __future__ import annotations

import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
TARGET = REPO_ROOT / "alpi" / "skills" / "knowledge" / "references"

# Source paths relative to REPO_ROOT.
SOURCES = [
    "README.md",
    "QUICKSTART.md",
    "docs/INSTALL.md",
    "docs/PROFILES.md",
    "docs/SKILLS.md",
    "docs/MODELS.md",
    "docs/ALP.md",
    "docs/ARCHITECTURE.md",
    "docs/CONFIG.md",
    "docs/SECURITY.md",
    "docs/DEPLOYMENTS.md",
    "docs/OPERATIONS.md",
]
# Deliberately NOT bundled: CHANGELOG.md (stales every release;
# `alpi update --check` and the GitHub release page are the live
# answer to "what changed?"); ROADMAP.md (internal planning,
# not user knowledge); RELEASE.md (maintainer-only); LICENSE
# (legal, not knowledge).


def _flatten_name(rel_path: str) -> str:
    """``docs/ALP.md`` → ``alp.md``, ``README.md`` → ``readme.md``.
    Lowercase + flat layout so the references/ dir is a single file
    per topic, easy to enumerate from SKILL.md."""
    return Path(rel_path).name.lower()


def main() -> int:
    TARGET.mkdir(parents=True, exist_ok=True)
    expected: set[str] = set()
    changed = 0

    for rel in SOURCES:
        src = REPO_ROOT / rel
        if not src.exists():
            print(f"  ! missing: {rel}", file=sys.stderr)
            continue
        dst_name = _flatten_name(rel)
        expected.add(dst_name)
        dst = TARGET / dst_name
        new = src.read_text()
        old = dst.read_text() if dst.exists() else None
        if old != new:
            dst.write_text(new)
            print(f"  + {dst_name} ← {rel}")
            changed += 1

    for f in TARGET.iterdir():
        if f.name.startswith("_") or not f.is_file():
            continue
        if f.name not in expected:
            f.unlink()
            print(f"  - {f.name} (no longer in source set)")
            changed += 1

    if changed == 0:
        print("references/ already in sync")
    else:
        print(f"\n{changed} file(s) updated")
    return 0


if __name__ == "__main__":
    sys.exit(main())
