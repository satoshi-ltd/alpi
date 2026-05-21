import { beforeEach, describe, expect, it, vi } from 'vitest';

const hoisted = vi.hoisted(() => ({
  store: new Map(),
}));

vi.mock('expo-secure-store', () => ({
  getItemAsync: vi.fn(async (k) => (hoisted.store.has(k) ? hoisted.store.get(k) : null)),
  setItemAsync: vi.fn(async (k, v) => { hoisted.store.set(k, v); }),
  deleteItemAsync: vi.fn(async (k) => { hoisted.store.delete(k); }),
}));

import { commitDelivered } from './poll';
import { loadState } from './state';

beforeEach(() => { hoisted.store.clear(); });

describe('commitDelivered', () => {
  it('advances afterSeq to the max seq of delivered events only', async () => {
    await commitDelivered('c1', [
      { event: 'wg.mention', seq: 7 },
      { event: 'wg.done', seq: 12 },
    ]);

    const s = await loadState('c1');
    expect(s.afterSeq).toBe(12);
    expect(s.seenIds).toEqual(['wg.mention:7', 'wg.done:12']);
  });

  it('committing only the delivered prefix keeps undelivered seqs re-fetchable', async () => {
    await commitDelivered('c1', [
      { event: 'wg.mention', seq: 10 },
      { event: 'wg.done', seq: 11 },
    ]);
    const s = await loadState('c1');
    expect(s.afterSeq).toBe(11);
    expect(s.seenIds).toEqual(['wg.mention:10', 'wg.done:11']);
  });

  it('never advances the cursor backwards when later commits are out of order', async () => {
    await commitDelivered('c1', [{ event: 'a', seq: 50 }]);
    await commitDelivered('c1', [{ event: 'b', seq: 30 }]);

    const s = await loadState('c1');
    expect(s.afterSeq).toBe(50);
    expect(s.seenIds).toEqual(['a:50', 'b:30']);
  });

  it('is a no-op for an empty event list — state stays unchanged', async () => {
    await commitDelivered('c1', []);
    const s = await loadState('c1');
    expect(s.afterSeq).toBe(0);
    expect(s.seenIds).toEqual([]);
  });
});
