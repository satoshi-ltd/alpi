import { describe, expect, it } from "vitest";
import * as busy from "../../../common/busy.mjs";
import { BUSY_DELAY_MS, BUSY_MIN_MS, busyPlan } from "../../../common/busy.mjs";

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

  it("keeps only the timing and the label: the busy mark is Twin, with no facet wave", () => {
    expect(Object.keys(busy).sort()).toEqual(["BUSY_CYCLE_S", "BUSY_DELAY_MS", "BUSY_LABEL", "BUSY_MIN_MARK_PX", "BUSY_MIN_MS", "busyPlan"]);
  });
});
