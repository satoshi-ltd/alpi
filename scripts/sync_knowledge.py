#!/usr/bin/env python3
"""Validate the alpi_knowledge reference set.

The answer packs in ``alpi/knowledge/references/`` are hand-tuned
for the LLM (shorter, denser, topic-routed) — NOT raw copies of
``docs/``. This script does not copy or overwrite anything; it just
asserts the on-disk set matches ``alpi.knowledge.TOPICS`` so the
tool, the docs, and the wheel never silently drift apart.

Run::

    uv run python scripts/sync_knowledge.py

Exits 0 when in sync, 2 on drift.
"""

from __future__ import annotations

import sys
from pathlib import Path

from alpi.knowledge import TOPICS


REPO_ROOT = Path(__file__).resolve().parent.parent
REFS = REPO_ROOT / "alpi" / "knowledge" / "references"


def main() -> int:
    on_disk = {p.name for p in REFS.iterdir() if p.is_file() and not p.name.startswith("_")}
    expected = set(TOPICS.values())

    missing = expected - on_disk
    extra = on_disk - expected
    if missing or extra:
        if missing:
            print(f"  ! TOPICS without a reference file: {sorted(missing)}", file=sys.stderr)
        if extra:
            print(f"  ! reference file without a TOPICS entry: {sorted(extra)}", file=sys.stderr)
        return 2

    print(f"references/ in sync ({len(expected)} topics)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
