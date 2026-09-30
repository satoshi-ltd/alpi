#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from versions import (
    PRODUCTS,
    VersionError,
    load,
    mobile_counter_spots,
    next_version,
    read_versions,
    save,
)  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent


def bump(product: str, part: str, root: Path) -> tuple[str, str, dict[str, str]]:
    found = read_versions(product, root)
    distinct = {v for _, v in found}
    if len(distinct) != 1:
        detail = "\n".join(f"  {spot.label}: {v}" for spot, v in found)
        raise VersionError(f"{product} versions disagree, fix them before bumping:\n{detail}")
    current = distinct.pop()
    new = next_version(current, part)
    texts: dict[str, str] = {}
    for spot, _ in found:
        texts.setdefault(spot.path, load(root / spot.path))
        texts[spot.path] = spot.write(texts[spot.path], new)
    if product == "mobile":
        for spot in mobile_counter_spots():
            texts.setdefault(spot.path, load(root / spot.path))
            texts[spot.path] = spot.write(
                texts[spot.path], str(int(spot.read(texts[spot.path])) + 1)
            )
    staged = []
    try:
        for rel, text in texts.items():
            tmp = root / f"{rel}.bump-tmp"
            save(tmp, text)
            staged.append((tmp, root / rel))
    except OSError:
        for tmp, _ in staged:
            tmp.unlink(missing_ok=True)
        raise
    for tmp, dest in staged:
        shutil.copymode(dest, tmp)
        os.replace(tmp, dest)
    return current, new, texts


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Bump every version location of one product.")
    parser.add_argument("product", choices=PRODUCTS)
    parser.add_argument("part", nargs="?", default="patch", choices=("patch", "minor", "major"))
    parser.add_argument("--root", type=Path, default=REPO_ROOT)
    parser.add_argument("--no-lock", action="store_true", help="alpi: skip `uv lock` after editing")
    args = parser.parse_args(argv)
    root = args.root.resolve()
    try:
        current, new, texts = bump(args.product, args.part, root)
    except VersionError as exc:
        print(f"bump: {exc}", file=sys.stderr)
        return 1
    for rel in texts:
        print(f"  updated {rel}", file=sys.stderr)
    print(f"  {args.product} {current} -> {new}", file=sys.stderr)
    if args.product == "alpi" and not args.no_lock:
        if shutil.which("uv") is None:
            print(
                "  uv not found; uv.lock was edited textually, run `uv lock` later", file=sys.stderr
            )
        else:
            rc = subprocess.run(["uv", "lock"], cwd=root).returncode
            if rc:
                print(f"bump: `uv lock` failed with exit code {rc}", file=sys.stderr)
                return rc
    print(new)
    return 0


if __name__ == "__main__":
    sys.exit(main())
