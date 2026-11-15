#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
TARGET = REPO / "alpi" / "mark_shapes.py"

NODE = """
const marks = await import(process.argv[1]);
const wg = await import(process.argv[2]);
process.stdout.write(JSON.stringify({
  shapes: marks.SHAPES, order: marks.SHAPE_ORDER, expressions: marks.EXPRESSIONS,
  still: marks.STILL, small: marks.SMALL, eyeMin: marks.EYE_MIN_PX, eyeCap: marks.EYE_CAP,
  eyeHalf: marks.EYE_PILL_HALF, eyeGap: marks.EYE_GAP_PX,
  cells: wg.WG_CELLS, wgOrder: wg.WG_ORDER, wgGap: wg.WG_GAP, wgGapPx: wg.WG_GAP_PX,
}));
"""

_NUMBER = re.compile(r"-?\d+(?:\.\d+)?")


def _cubic(p0, p1, p2, p3, t):
    u = 1 - t
    return tuple(u ** 3 * a + 3 * u * u * t * b + 3 * u * t * t * c + t ** 3 * d for a, b, c, d in zip(p0, p1, p2, p3))


def flatten(d: str) -> list[tuple[float, float]]:
    if re.search(r"[A-BD-LN-Ya-y]", d) or d.count("M") != 1:
        raise ValueError("outlines must be one M…C…Z subpath")
    numbers = [float(n) for n in _NUMBER.findall(d)]
    current = (numbers[0], numbers[1])
    points = [current]
    rest = numbers[2:]
    for i in range(0, len(rest), 6):
        c1, c2, end = (rest[i], rest[i + 1]), (rest[i + 2], rest[i + 3]), (rest[i + 4], rest[i + 5])
        points.append(_cubic(current, c1, c2, end, 0.5))
        points.append(end)
        current = end
    if points[-1] == points[0]:
        points.pop()
    return points


def from_node() -> dict:
    out = subprocess.run(
        ["node", "--input-type=module", "-e", NODE,
         (REPO / "common" / "agentMarks.mjs").as_uri(), (REPO / "common" / "workgroupMark.mjs").as_uri()],
        capture_output=True, text=True, check=True,
    )
    data = json.loads(out.stdout)
    sys.path.insert(0, str(REPO / "design" / "src"))
    import agent_marks

    return {**data, "legacy": agent_marks.LEGACY_SHAPE}


def _points(points) -> str:
    return "(" + ", ".join(f"({x:.2f}, {y:.2f})" for x, y in points) + ",)"


def render(data: dict) -> str:
    lines = [
        "from __future__ import annotations",
        "",
        "Point = tuple[float, float]",
        "",
        f"SMALL = {data['small']}",
        f"EYE_MIN_PX = {data['eyeMin']}",
        f"EYE_CAP = {data['eyeCap']}",
        f"EYE_PILL_HALF = {data['eyeHalf']}",
        f"EYE_GAP_PX = {data['eyeGap']}",
        f"WG_GAP = {data['wgGap']}",
        f"WG_GAP_PX = {data['wgGapPx']}",
        f"WG_ORDER = {tuple(data['wgOrder'])!r}",
        f"SHAPE_ORDER = {tuple(data['order'])!r}",
        f"LEGACY_SHAPE = {data['legacy']!r}",
        "",
        "EYES: dict[str, tuple[float, float, float]] = {",
    ]
    for name, spec in data["shapes"].items():
        lines.append(f'    "{name}": ({spec["eyeX"]}, {spec["eyeY"]}, {spec["eyeDx"]}),')
    lines += ["}", "", "STILL: dict[str, tuple] = {"]
    for state, (_t, gx, gy, left, right) in data["still"].items():
        lines.append(f'    "{state}": ({gx}, {gy}, {tuple(left)!r}, {tuple(right)!r}),')
    lines += ["}", "", "EXPRESSIONS: dict[str, tuple[Point, ...]] = {"]
    for name, points in data["expressions"].items():
        lines.append(f'    "{name}": {_points(points)},')
    lines += ["}", "", "OUTLINES: dict[str, tuple[Point, ...]] = {"]
    for name, spec in data["shapes"].items():
        lines.append(f'    "{name}": {_points(flatten(spec["d"]))},')
    lines += ["}", "", "HONEYCOMB: dict[float, dict[str, tuple[Point, ...]]] = {"]
    for gap, cells in data["cells"].items():
        lines.append(f"    {float(gap)}: {{")
        for cell in data["wgOrder"]:
            lines.append(f'        "{cell}": {_points(flatten(cells[cell]))},')
        lines.append("    },")
    lines.append("}")
    return "\n".join(lines) + "\n"


def main(argv: list[str]) -> int:
    text = render(from_node())
    if "--check" in argv:
        if not TARGET.exists() or TARGET.read_text() != text:
            print("alpi/mark_shapes.py is stale: run scripts/sync_marks.py", file=sys.stderr)
            return 1
        return 0
    TARGET.write_text(text)
    print(f"wrote {TARGET.relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
