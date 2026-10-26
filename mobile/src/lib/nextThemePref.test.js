import { describe, expect, it } from 'vitest';

import { nextThemePref } from './nextThemePref';

describe('nextThemePref', () => {
  it('cycles System, Light, Dark and back', () => {
    expect(nextThemePref('system')).toBe('light');
    expect(nextThemePref('light')).toBe('dark');
    expect(nextThemePref('dark')).toBe('system');
  });

  it('restarts from System on an unknown value', () => {
    expect(nextThemePref('sepia')).toBe('system');
    expect(nextThemePref(undefined)).toBe('system');
  });
});
