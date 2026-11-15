import { describe, expect, it } from 'vitest';

import { HIGH_USE, profileHeaderFlag, workgroupHeaderFlag } from './headerFlag';

describe('header flag', () => {
  it('flags a profile once its context or daily budget passes 80 %, budget first, never while paused', () => {
    expect(HIGH_USE).toBe(0.8);
    expect(profileHeaderFlag({ ctxPct: 0.79, budgetPct: 0.5 })).toBeNull();
    expect(profileHeaderFlag({ ctxPct: 0.85 })).toEqual({ label: 'Context 85% full', tone: 'warning' });
    expect(profileHeaderFlag({ ctxPct: 0.9, budgetPct: 0.8 })).toEqual({ label: 'Daily budget 80% used', tone: 'warning' });
    expect(profileHeaderFlag({ budgetPct: 1.4 })).toEqual({ label: 'Daily budget 100% used', tone: 'danger' });
    expect(profileHeaderFlag({ budgetPct: 0.95, paused: true })).toBeNull();
  });

  it('flags a workgroup that waits on the user or failed, never a running or paused one', () => {
    expect(workgroupHeaderFlag({ mark: { state: 'needs' }, status: 'Needs you · approval · @yuri' })).toEqual({ label: 'Needs you · approval · @yuri', tone: 'warning' });
    expect(workgroupHeaderFlag({ mark: { state: 'failed' } })).toEqual({ label: 'Failed', tone: 'danger' });
    expect(workgroupHeaderFlag({ mark: { state: 'running' } })).toBeNull();
    expect(workgroupHeaderFlag({ mark: { state: 'needs' }, paused: true })).toBeNull();
  });
});
