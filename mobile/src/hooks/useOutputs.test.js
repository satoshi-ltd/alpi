import { describe, expect, it } from 'vitest';

import { resolveReadTarget } from './useOutputs';

const conns = [
  { id: 'c1', name: 'home' },
  { id: 'c2', name: 'work' },
];

describe('resolveReadTarget', () => {
  it('reads the matching daemon when connectionId resolves', () => {
    expect(resolveReadTarget(conns, 'c2')).toEqual({
      mode: 'connection',
      connection: { id: 'c2', name: 'work' },
    });
  });

  it('falls back to the active daemon when no connectionId (legacy path)', () => {
    expect(resolveReadTarget(conns, undefined)).toEqual({ mode: 'active' });
    expect(resolveReadTarget(conns, '')).toEqual({ mode: 'active' });
  });

  it('reports unknown — never the active daemon — when connectionId does not resolve', () => {
    expect(resolveReadTarget(conns, 'gone')).toEqual({ mode: 'unknown' });
    expect(resolveReadTarget(null, 'c1')).toEqual({ mode: 'unknown' });
  });
});
