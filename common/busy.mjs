import { ALPACA_FOLD, foldFacets } from "./folds.mjs";

export const BUSY_DELAY_MS = 300;
export const BUSY_MIN_MS = 400;
export const BUSY_WAVE_S = 1.6;
export const BUSY_DIM = 0.28;
export const BUSY_MIN_MARK_PX = 18;
export const BUSY_LABEL = "Loading";

const TAIL = [22, 65];
const HEAD = [70, 10];

export function busyFacetOrder() {
  const axis = [HEAD[0] - TAIL[0], HEAD[1] - TAIL[1]];
  const along = foldFacets(ALPACA_FOLD).map(({ points }, i) => {
    const [x, y] = points.reduce(([a, b], [px, py]) => [a + px / points.length, b + py / points.length], [0, 0]);
    return { i, t: (x - TAIL[0]) * axis[0] + (y - TAIL[1]) * axis[1] };
  });
  return along.sort((a, b) => a.t - b.t || a.i - b.i).map(({ i }) => i);
}

export function busyFacetDelays(count = foldFacets(ALPACA_FOLD).length) {
  const order = busyFacetOrder();
  const rank = new Map(order.map((facet, r) => [facet, r]));
  return Array.from({ length: count }, (_, i) => {
    const r = order.length === count ? rank.get(i) : i;
    return Number((-(1 - r / count) * BUSY_WAVE_S * 0.7).toFixed(2));
  });
}

export function busyPlan({ active, startedAt = null, shownAt = null }, now) {
  if (active) {
    if (shownAt != null) return { visible: true, wakeIn: null };
    const wait = BUSY_DELAY_MS - Math.max(0, now - (startedAt ?? now));
    return wait <= 0 ? { visible: true, wakeIn: null } : { visible: false, wakeIn: wait };
  }
  if (shownAt == null) return { visible: false, wakeIn: null };
  const left = BUSY_MIN_MS - Math.max(0, now - shownAt);
  return left > 0 ? { visible: true, wakeIn: left } : { visible: false, wakeIn: null };
}
