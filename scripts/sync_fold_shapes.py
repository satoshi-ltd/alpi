#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
TARGET = REPO / "alpi" / "fold_shapes.py"

NODE = """
const { FOLD_IDS, WORKGROUP_FOLD, ALPACA_FOLD, foldFacets } = await import(process.argv[1]);
const ids = [...FOLD_IDS, WORKGROUP_FOLD, ALPACA_FOLD];
process.stdout.write(JSON.stringify(Object.fromEntries(ids.map((id) => [id, foldFacets(id)]))));
"""


def facets_from_node() -> dict[str, list[dict]]:
    source = (REPO / "common" / "folds.mjs").as_uri()
    out = subprocess.run(
        ["node", "--input-type=module", "-e", NODE, source],
        capture_output=True, text=True, check=True,
    )
    return json.loads(out.stdout)


def render(shapes: dict[str, list[dict]]) -> str:
    lines = [
        "from __future__ import annotations",
        "",
        "Point = tuple[float, float]",
        "Facet = tuple[int, tuple[Point, ...]]",
        "",
        "SHAPES: dict[str, tuple[Facet, ...]] = {",
    ]
    for fold, facets in shapes.items():
        lines.append(f'    "{fold}": (')
        for facet in facets:
            points = ", ".join(f"({x:.2f}, {y:.2f})" for x, y in facet["points"])
            lines.append(f"        ({facet['tone']}, ({points},)),")
        lines.append("    ),")
    lines.append("}")
    return "\n".join(lines) + "\n"


def main(argv: list[str]) -> int:
    text = render(facets_from_node())
    if "--check" in argv:
        if not TARGET.exists() or TARGET.read_text() != text:
            print("alpi/fold_shapes.py is stale: run scripts/sync_fold_shapes.py", file=sys.stderr)
            return 1
        return 0
    TARGET.write_text(text)
    print(f"wrote {TARGET.relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
