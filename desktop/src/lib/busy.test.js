import { describe, expect, it } from "vitest";
import { ALPACA_FOLD, foldFacets } from "../../../common/folds.mjs";
import { BUSY_DELAY_MS, BUSY_MIN_MS, BUSY_WAVE_S, busyFacetDelays, busyFacetOrder, busyPlan } from "../../../common/busy.mjs";

describe("busy mark timing", () => {
  it("waits the delay before showing", () => {
    expect(busyPlan({ active: true, startedAt: 0 }, 100)).toEqual({ visible: false, wakeIn: BUSY_DELAY_MS - 100 });
    expect(busyPlan({ active: true, startedAt: 0 }, BUSY_DELAY_MS)).toEqual({ visible: true, wakeIn: null });
  });

  it("never shows a wait that ends inside the delay", () => {
    expect(busyPlan({ active: false, startedAt: 0, shownAt: null }, 200)).toEqual({ visible: false, wakeIn: null });
  });

  it("once shown stays the minimum time, then goes", () => {
    expect(busyPlan({ active: false, shownAt: 1000 }, 1100)).toEqual({ visible: true, wakeIn: BUSY_MIN_MS - 100 });
    expect(busyPlan({ active: false, shownAt: 1000 }, 1000 + BUSY_MIN_MS)).toEqual({ visible: false, wakeIn: null });
    expect(busyPlan({ active: true, shownAt: 1000 }, 5000)).toEqual({ visible: true, wakeIn: null });
  });

  it("treats a missing start as now and never trusts a clock that went backwards", () => {
    expect(busyPlan({ active: true, startedAt: null }, 5000)).toEqual({ visible: false, wakeIn: BUSY_DELAY_MS });
    expect(busyPlan({ active: true, startedAt: 9000 }, 5000)).toEqual({ visible: false, wakeIn: BUSY_DELAY_MS });
    expect(busyPlan({ active: false, shownAt: 2000 }, 1000)).toEqual({ visible: true, wakeIn: BUSY_MIN_MS });
    expect(busyPlan({ active: false, shownAt: 3_600_000 }, 0).wakeIn).toBeLessThanOrEqual(BUSY_MIN_MS);
  });

  it("staggers every alpaca facet from tail to head inside one loop", () => {
    const facets = foldFacets(ALPACA_FOLD);
    const delays = busyFacetDelays();
    expect(delays).toHaveLength(facets.length);
    expect(delays.every((d) => d <= 0 && d > -BUSY_WAVE_S)).toBe(true);
    const centre = ({ points }) => points.reduce(([a, b], [x, y]) => [a + x / points.length, b + y / points.length], [0, 0]);
    const along = facets.map((f, i) => {
      const [x, y] = centre(f);
      return { delay: delays[i], t: (x - 22) * 48 + (y - 65) * -55 };
    }).sort((a, b) => a.t - b.t);
    for (let k = 1; k < along.length; k++) expect(along[k].delay).toBeGreaterThan(along[k - 1].delay);
  });

  it("starts the wave at the rear and ends it at the head", () => {
    const order = busyFacetOrder();
    expect(order).toHaveLength(foldFacets(ALPACA_FOLD).length);
    const [x0] = foldFacets(ALPACA_FOLD)[order[0]].points[0];
    const lastY = foldFacets(ALPACA_FOLD)[order.at(-1)].points.reduce((m, [, y]) => Math.min(m, y), 100);
    expect(x0).toBeLessThan(40);
    expect(lastY).toBeLessThan(20);
  });
});
