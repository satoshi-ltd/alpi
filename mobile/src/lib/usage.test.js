import { describe, expect, it } from 'vitest';

import {
  barHeights,
  costOf,
  hasUsage,
  pctLeft,
  todayOf,
  tokensOf,
  toUsageDays,
  usageScale,
  usageTotals,
} from '../../../common/usage.mjs';

const RPC = [
  { iso: '2026-09-27', tokIn: 1000, tokOut: 200, cost: 0.5 },
  { iso: '2026-09-28', tokIn: 3000, tokOut: 500, cost: 1.25 },
];

describe('toUsageDays', () => {
  it('derives label, day and today from the daemon rows', () => {
    const days = toUsageDays(RPC);
    expect(days.map((d) => d.day)).toEqual(['9/27', '9/28']);
    expect(days.map((d) => d.today)).toEqual([false, true]);
    expect(days[0].label).toHaveLength(1);
  });

  it('tolerates a missing payload', () => {
    expect(toUsageDays(undefined)).toEqual([]);
  });
});

describe('math', () => {
  it('prefers the daemon cost and falls back to list prices', () => {
    expect(costOf({ cost: 0.4 })).toBe(0.4);
    expect(costOf({ tokIn: 1e6, tokOut: 1e6 })).toBeCloseTo(0.75);
  });

  it('sums tokens and totals', () => {
    expect(tokensOf(RPC[0])).toBe(1200);
    expect(usageTotals(RPC)).toEqual({ cost: 1.75, tokIn: 4000, tokOut: 700 });
  });

  it('picks today, or the last day, or nothing', () => {
    const days = toUsageDays(RPC);
    expect(todayOf(days).iso).toBe('2026-09-28');
    expect(todayOf([{ iso: 'x', tokIn: 1 }]).iso).toBe('x');
    expect(todayOf([])).toBeNull();
  });

  it('scales to the busiest day with headroom and never divides by zero', () => {
    expect(usageScale(RPC)).toBeCloseTo(3500 * 1.08);
    expect(usageScale([{ tokIn: 0, tokOut: 0 }])).toBeCloseTo(1.08);
  });

  it('reports budget left only with a positive cap', () => {
    expect(pctLeft(0.42, 2)).toBe(79);
    expect(pctLeft(3, 2)).toBe(0);
    expect(pctLeft(1, 0)).toBeNull();
    expect(pctLeft(1, null)).toBeNull();
  });

  it('keeps a hairline bar for any traffic and none for an idle day', () => {
    const scale = usageScale(RPC);
    expect(barHeights({ tokIn: 1, tokOut: 0 }, scale, 100).total).toBe(3);
    expect(barHeights({ tokIn: 0, tokOut: 0 }, scale, 100).total).toBe(0);
    const busy = barHeights(RPC[1], scale, 100);
    expect(busy.total).toBeCloseTo(100 / 1.08);
    expect(busy.out).toBeCloseTo((500 / scale) * 100);
  });
});

describe('hasUsage', () => {
  it('is false for an empty or all-zero range and true once any day carries tokens or cost', () => {
    expect(hasUsage([])).toBe(false);
    expect(hasUsage(undefined)).toBe(false);
    expect(hasUsage([{ tokIn: 0, tokOut: 0, cost: 0 }])).toBe(false);
    expect(hasUsage([{ tokIn: 0, tokOut: 0, cost: 0 }, { tokIn: 0, tokOut: 3 }])).toBe(true);
    expect(hasUsage([{ cost: 0.01 }])).toBe(true);
  });
});
