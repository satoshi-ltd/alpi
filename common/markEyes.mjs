import { EXPRESSIONS, EYE_CAP, EYE_GAP_PX, EYE_MIN_PX, EYE_PILL_HALF, SHAPES, SMALL, STILL } from "./agentMarks.mjs";

export function eyePair(spec, size, key = STILL.idle) {
  const [, gx, gy, left, right] = key;
  const reach = size < SMALL ? 0.7 : 1;
  const grow = Math.min(EYE_CAP, Math.max(1, (EYE_MIN_PX * 50) / (EYE_PILL_HALF * size)));
  const gap = Math.max(3, (EYE_GAP_PX * 100) / size) / 2;
  return [[-1, left], [1, right]].map(([side, [name, s, dy]]) => {
    const pts = EXPRESSIONS[name];
    const inner = -Math.min(...pts.map((p) => p[0]));
    const scale = inner > 0 ? Math.min(grow * s, (spec.eyeDx - gap) / inner) : grow * s;
    const x0 = spec.eyeX + reach * gx + side * spec.eyeDx;
    const y0 = spec.eyeY + reach * (gy + dy);
    return pts.map(([x, y]) => [x0 + side * x * scale, y0 + y * scale]);
  });
}

export const eyePath = (points) => `M${points.map(([x, y]) => `${x.toFixed(1)} ${y.toFixed(1)}`).join(" ")}Z`;

export const stillMarkPath = (shape, size) => `${SHAPES[shape].d}${eyePair(SHAPES[shape], size).map(eyePath).join("")}`;
