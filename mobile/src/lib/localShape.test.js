import { describe, expect, it } from 'vitest';

import { FALLBACK_ACCENT } from '../../../common/shapes.mjs';
import { accentForPubkey, shapeForPubkey } from './localShape';

const summaries = { data: { profiles: [{ name: 'doc', pubkey_b64: 'AAA', shape: 'bell', accent: '#3ac9f3' }, { name: 'abby', pubkey_b64: 'BBB' }] } };

describe('shapeForPubkey', () => {
  it('finds the shape of the local profile that owns the key', () => {
    expect(shapeForPubkey(summaries, 'AAA')).toBe('bell');
  });

  it('gives nothing for a remote key, a profile without a shape or missing data', () => {
    expect(shapeForPubkey(summaries, 'CCC')).toBeUndefined();
    expect(shapeForPubkey(summaries, 'BBB')).toBeUndefined();
    expect(shapeForPubkey(undefined, 'AAA')).toBeUndefined();
    expect(shapeForPubkey(summaries, null)).toBeUndefined();
  });
});

describe('accentForPubkey', () => {
  it('finds the accent of the local profile that owns the key', () => {
    expect(accentForPubkey(summaries, 'AAA')).toBe('#3ac9f3');
  });

  it('falls back to the shared accent for a remote key, an accentless profile or missing data', () => {
    expect(accentForPubkey(summaries, 'CCC')).toBe(FALLBACK_ACCENT);
    expect(accentForPubkey(summaries, 'BBB')).toBe(FALLBACK_ACCENT);
    expect(accentForPubkey(undefined, 'AAA')).toBe(FALLBACK_ACCENT);
    expect(accentForPubkey(summaries, null)).toBe(FALLBACK_ACCENT);
  });
});
