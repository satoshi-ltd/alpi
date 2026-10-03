import { FOLDS, FOLD_IDS, FOLD_MODELS, MAX_FACETS, MIN_ASPECT, WORKGROUP_FOLD, foldFacets } from "./folds.mjs";

const SQUARE = 100;
const touches = (a, b, tolerance) => a.some(([px, py]) => edges(b).some(([[x1, y1], [x2, y2]]) => distanceToSegment(px, py, x1, y1, x2, y2) <= tolerance));
const edges = (poly) => poly.map((p, i) => [p, poly[(i + 1) % poly.length]]);

function distanceToSegment(px, py, x1, y1, x2, y2) {
  const [dx, dy] = [x2 - x1, y2 - y1];
  const t = dx === 0 && dy === 0 ? 0 : Math.max(0, Math.min(1, ((px - x1) * dx + (py - y1) * dy) / (dx * dx + dy * dy)));
  return Math.hypot(px - (x1 + t * dx), py - (y1 + t * dy));
}

function onePiece(polys, tolerance = 1.5) {
  const seen = new Set([0]);
  const todo = [0];
  while (todo.length) {
    const i = todo.pop();
    polys.forEach((poly, j) => {
      if (!seen.has(j) && (touches(polys[i], poly, tolerance) || touches(poly, polys[i], tolerance))) {
        seen.add(j);
        todo.push(j);
      }
    });
  }
  return seen.size === polys.length;
}

function fourFoldChiral(id) {
  const key = (facets) => new Set(facets.flatMap(({ points }) => points.map(([x, y]) => `${Math.round(x)},${Math.round(y)}`)));
  const base = FOLDS[id]();
  const rotated = base.map(({ tone, points }) => ({ tone, points: points.map(([x, y]) => [50 - (y - 50), 50 + (x - 50)]) }));
  const mirrored = base.map(({ tone, points }) => ({ tone, points: points.map(([x, y]) => [100 - x, y]) }));
  const [a, r, m] = [key(base), key(rotated), key(mirrored)];
  const same = (p, q) => p.size === q.size && [...p].every((v) => q.has(v));
  return same(a, r) && !same(a, m);
}

export function foldProblems() {
  const problems = [];
  const ids = [...FOLD_IDS, WORKGROUP_FOLD];
  if (FOLD_IDS.length !== 12) problems.push(`there are ${FOLD_IDS.length} folds, not twelve`);
  for (const id of ids) {
    if (!FOLD_MODELS[id]) problems.push(`${id}: no named origami model`);
    const facets = foldFacets(id);
    if (facets.length < 2 || facets.length > MAX_FACETS) problems.push(`${id}: ${facets.length} facets`);
    const points = facets.flatMap((f) => f.points);
    const xs = points.map((p) => p[0]);
    const ys = points.map((p) => p[1]);
    const [w, h] = [Math.max(...xs) - Math.min(...xs), Math.max(...ys) - Math.min(...ys)];
    if (Math.min(w, h) / Math.max(w, h) < MIN_ASPECT) problems.push(`${id}: fills too little of the square`);
    if (Math.max(...xs) > SQUARE || Math.min(...xs) < 0 || Math.max(...ys) > SQUARE || Math.min(...ys) < 0) problems.push(`${id}: leaves the square`);
    if (!onePiece(facets.map((f) => f.points))) problems.push(`${id}: more than one piece of paper`);
    if (!facets.every((f) => [0, 1, 2].includes(f.tone))) problems.push(`${id}: more than three flat tones`);
    if (fourFoldChiral(id)) problems.push(`${id}: a four-fold turning motif`);
  }
  return problems;
}
