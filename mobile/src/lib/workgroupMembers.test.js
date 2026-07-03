import { describe, it, expect } from 'vitest';
import { resolveMembers } from './workgroupMembers.js';

describe('resolveMembers', () => {
  it('returns the roster array when present', () => {
    const roster = [{ pubkey: 'a', voice: 'x' }];
    expect(resolveMembers({ members: roster })).toBe(roster);
  });

  it('returns [] before the RPC resolves (data is null)', () => {
    expect(resolveMembers(null)).toEqual([]);
  });

  it('returns [] when data is undefined', () => {
    expect(resolveMembers(undefined)).toEqual([]);
  });

  it('returns [] when members is a headcount number, not a roster (the crash case)', () => {
    expect(resolveMembers({ members: 3 })).toEqual([]);
  });

  it('returns [] when members is missing from the payload', () => {
    expect(resolveMembers({})).toEqual([]);
  });
});
