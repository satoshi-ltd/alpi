import { describe, expect, it } from 'vitest';

import { shouldFetchPreview } from './fileKind';

const img = { name: 'hero.jpg', mime: 'image/jpeg', path: '/p/out/hero.jpg' };

describe('shouldFetchPreview', () => {
  it('fetches a produced image (path, no localUri) in a message', () => {
    expect(shouldFetchPreview(img, { message: true, profile: 'muse' })).toBe(true);
  });

  it('does not fetch when a localUri is present, or for non-image / no-profile / composer', () => {
    expect(shouldFetchPreview({ ...img, localUri: 'file://x' }, { message: true, profile: 'muse' })).toBe(false);
    expect(shouldFetchPreview({ name: 'r.csv', mime: 'text/csv', path: '/p/r.csv' }, { message: true, profile: 'muse' })).toBe(false);
    expect(shouldFetchPreview(img, { message: true, profile: null })).toBe(false);
    expect(shouldFetchPreview(img, { message: false, profile: 'muse' })).toBe(false);
  });
});
