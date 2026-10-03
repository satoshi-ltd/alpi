import { describe, expect, it } from 'vitest';

import { FALLBACK_ACCENT } from '../../../common/folds.mjs';
import { accentForPubkey, foldForPubkey } from './localFold';

const summaries = { data: { profiles: [{ name: 'doc', pubkey_b64: 'AAA', fold: 'shield', accent: '#3ac9f3' }, { name: 'abby', pubkey_b64: 'BBB' }] } };

describe('foldForPubkey', () => {
  it('finds the fold of the local profile that owns the key', () => {
    expect(foldForPubkey(summaries, 'AAA')).toBe('shield');
  });

  it('gives nothing for a remote key, a profile without a fold or missing data', () => {
    expect(foldForPubkey(summaries, 'CCC')).toBeUndefined();
    expect(foldForPubkey(summaries, 'BBB')).toBeUndefined();
    expect(foldForPubkey(undefined, 'AAA')).toBeUndefined();
    expect(foldForPubkey(summaries, null)).toBeUndefined();
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
