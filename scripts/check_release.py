#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from versions import CHANGELOGS, PRODUCTS, VersionError, changelog_top, read_versions  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent
HEADING = re.compile(r"^v(?P<v>\d+\.\d+\.\d+)\b")


def check(root: Path) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    for product in PRODUCTS:
        try:
            found = read_versions(product, root)
        except (VersionError, OSError) as exc:
            errors.append(f"{product}: {exc}")
            continue
        distinct = {v for _, v in found}
        if len(distinct) != 1:
            detail = "; ".join(f"{spot.label} = {v}" for spot, v in found)
            errors.append(f"{product}: versions disagree: {detail}")
            continue
        version = distinct.pop()
        changelog = CHANGELOGS[product]
        try:
            top = changelog_top(root, product)
        except OSError as exc:
            errors.append(f"{product}: cannot read {changelog}: {exc}")
            continue
        if top is None:
            errors.append(f"{product}: {changelog} has no `## ` heading")
        elif top.lower().startswith("unreleased"):
            warnings.append(
                f"{product}: {changelog} top heading is `## {top}` (version {version} not released yet)"
            )
        else:
            m = HEADING.match(top)
            if not m:
                errors.append(
                    f"{product}: {changelog} top heading `## {top}` is neither `## vX.Y.Z` nor `## Unreleased`"
                )
            elif m.group("v") != version:
                errors.append(
                    f"{product}: {changelog} top heading is v{m.group('v')} but the version is {version}"
                )
    return errors, warnings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Check version locations and changelog headings agree."
    )
    parser.add_argument("--root", type=Path, default=REPO_ROOT)
    args = parser.parse_args(argv)
    errors, warnings = check(args.root.resolve())
    for w in warnings:
        print(f"warning: {w}", file=sys.stderr)
    if errors:
        for e in errors:
            print(f"error: {e}", file=sys.stderr)
        return 1
    print("ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
