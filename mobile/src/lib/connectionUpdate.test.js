import { describe, it, expect } from 'vitest';

import { canUpdateConnection } from './connectionUpdate';

describe('canUpdateConnection', () => {
  it('allows an admin when an update is available', () => {
    expect(canUpdateConnection('admin', '0.9.6')).toBe(true);
  });

  it('hides for a member even when an update is available (backend would forbid)', () => {
    expect(canUpdateConnection('member', '0.9.6')).toBe(false);
  });

  it('hides for an admin with no update available', () => {
    expect(canUpdateConnection('admin', null)).toBe(false);
  });

  it('hides when the daemon says it cannot update itself', () => {
    expect(canUpdateConnection('admin', '0.9.6', false)).toBe(false);
  });

  it('keeps the action for a daemon that says it can, or does not say', () => {
    expect(canUpdateConnection('admin', '0.9.6', true)).toBe(true);
    expect(canUpdateConnection('admin', '0.9.6', null)).toBe(true);
    expect(canUpdateConnection('admin', '0.9.6', undefined)).toBe(true);
  });

  it('hides while the role is still unknown (probe pending)', () => {
    expect(canUpdateConnection(null, '0.9.6')).toBe(false);
    expect(canUpdateConnection(undefined, '0.9.6')).toBe(false);
  });
});
