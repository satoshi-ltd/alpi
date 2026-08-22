import { describe, expect, it } from 'vitest';

import { deadlineFor } from './useRequestQueue';

describe('deadlineFor', () => {
  it('is null without a numeric timeout', () => {
    expect(deadlineFor({})).toBeNull();
    expect(deadlineFor({ timeout_s: '60' })).toBeNull();
  });

  it('anchors on the daemon ts, not on arrival, and clamps a negative window', () => {
    expect(deadlineFor({ ts: 1_000_000, timeout_s: 60 })).toBe(1_000_060_000);
    expect(deadlineFor({ ts: 1_000_000, timeout_s: -30 })).toBe(1_000_000_000);
  });

  it('falls back to the local clock when ts is missing', () => {
    expect(deadlineFor({ timeout_s: 60 }) - Date.now()).toBeGreaterThan(55_000);
  });
});
