import { describe, expect, it, vi, beforeEach } from 'vitest';

const store = new Map();

vi.mock('expo-secure-store', () => ({
  getItemAsync: vi.fn(async (k) => (store.has(k) ? store.get(k) : null)),
  setItemAsync: vi.fn(async (k, v) => { store.set(k, v); }),
  deleteItemAsync: vi.fn(async (k) => { store.delete(k); }),
}));

import {
  alnStateKey,
  clearState,
  loadState,
  recordSeen,
  saveState,
  stateKey,
} from './state';

describe('stateKey', () => {
  it('namespaces per connection so two daemons stay independent', () => {
    expect(stateKey('a')).toBe('aln.state.a');
    expect(stateKey('b')).toBe('aln.state.b');
    expect(stateKey('a')).not.toBe(stateKey('b'));
  });
});

describe('alnStateKey', () => {
  it('keys by deviceId so different connections to the same daemon share one state file', () => {
    const a = { id: 'conn-1', deviceId: 'mac-uuid' };
    const b = { id: 'conn-2', deviceId: 'mac-uuid' };
    expect(alnStateKey(a)).toBe(alnStateKey(b));
    expect(alnStateKey(a)).toBe('daemon:mac-uuid');
  });

  it('returns empty string when deviceId is missing — no legacy fallback to connection id', () => {
    expect(alnStateKey({ id: 'conn-no-deviceid' })).toBe('');
    expect(alnStateKey(null)).toBe('');
    expect(alnStateKey(undefined)).toBe('');
    expect(alnStateKey({})).toBe('');
  });
});

describe('loadState', () => {
  beforeEach(() => { store.clear(); });

  it('returns defaults when nothing persisted yet', async () => {
    const s = await loadState('fresh');
    expect(s.afterSeq).toBe(0);
    expect(s.seenIds).toEqual([]);
    expect(s.lastError).toBe('');
  });

  it('round-trips persisted state', async () => {
    await saveState('rt', {
      afterSeq: 42, seenIds: ['wg.done:7'],
      lastPollMs: 1, lastSuccessMs: 2, lastError: 'x',
    });
    const s = await loadState('rt');
    expect(s.afterSeq).toBe(42);
    expect(s.seenIds).toEqual(['wg.done:7']);
    expect(s.lastError).toBe('x');
  });

  it('coerces malformed persisted data to defaults', async () => {
    store.set('aln.state.bad', 'this is not json');
    const s = await loadState('bad');
    expect(s.afterSeq).toBe(0);
    expect(s.seenIds).toEqual([]);
  });

  it('clears via clearState', async () => {
    await saveState('rm', { afterSeq: 5 });
    await clearState('rm');
    const s = await loadState('rm');
    expect(s.afterSeq).toBe(0);
  });
});

describe('recordSeen', () => {
  it('appends new ids', () => {
    const s = recordSeen({ afterSeq: 0, seenIds: ['a'] }, 'b');
    expect(s.seenIds).toEqual(['a', 'b']);
  });

  it('drops duplicates silently', () => {
    const s = recordSeen({ afterSeq: 0, seenIds: ['a', 'b'] }, 'a');
    expect(s.seenIds).toEqual(['a', 'b']);
  });

  it('caps the ring buffer at 500 to prevent unbounded growth', () => {
    let s = { afterSeq: 0, seenIds: Array.from({ length: 500 }, (_, i) => `e:${i}`) };
    s = recordSeen(s, 'e:new');
    expect(s.seenIds.length).toBe(500);
    expect(s.seenIds[499]).toBe('e:new');
    expect(s.seenIds[0]).toBe('e:1');
  });
});
