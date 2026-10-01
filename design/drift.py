#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def snapshot(root: Path) -> dict[str, str]:
    return {
        str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted((root / "design").rglob("*"))
        if p.is_file() and "__pycache__" not in p.parts
    }


def main(root: Path = REPO_ROOT) -> int:
    before = snapshot(root)
    build = subprocess.run([sys.executable, str(root / "design" / "build.py")], cwd=root)
    if build.returncode:
        return build.returncode
    after = snapshot(root)
    changed = sorted(k for k in before.keys() | after.keys() if before.get(k) != after.get(k))
    if changed:
        print("design/ was stale; the build regenerated these files, review and stage them:", file=sys.stderr)
        for name in changed:
            print(f"  {name}", file=sys.stderr)
        return 1
    print("design/ matches its sources")
    return 0


if __name__ == "__main__":
    sys.exit(main())
