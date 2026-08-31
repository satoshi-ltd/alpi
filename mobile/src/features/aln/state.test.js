import { describe, expect, it, vi, beforeEach } from 'vitest';

const store = new Map();

function secureStoreKey(key) {
  if (typeof key !== 'string' || !/^[\w.-]+$/.test(key)) {
    throw new Error('Invalid key provided to SecureStore. Keys must not be empty and contain only alphanumeric characters, ".", "-", and "_".');
  }
  return key;
}

vi.mock('expo-secure-store', () => ({
  getItemAsync: vi.fn(async (k) => (store.has(secureStoreKey(k)) ? store.get(k) : null)),
  setItemAsync: vi.fn(async (k, v) => { store.set(secureStoreKey(k), v); }),
  deleteItemAsync: vi.fn(async (k) => { store.delete(secureStoreKey(k)); }),
}));

import {
  alnStateKey,
  clearState,
  eventId,
  loadFlag,
  loadState,
  mutateState,
  recordSeen,
  saveFlag,
  saveState,
  stateKey,
} from './state';

describe('stateKey', () => {
  it('namespaces per connection so two daemons stay independent', () => {
    expect(stateKey('a')).toBe('aln.state.a');
    expect(stateKey('b')).toBe('aln.state.b');
    expect(stateKey('a')).not.toBe(stateKey('b'));
  });

  it('composes a key SecureStore accepts', () => {
    const key = stateKey(alnStateKey({ deviceId: 'a3f9c2e14b7d48a19f0c5e6b2d8a1f34' }));
    expect(key).toMatch(/^[\w.-]+$/);
  });

  it('keeps two daemons independent after sanitizing', () => {
    const a = stateKey(alnStateKey({ deviceId: 'mac-uuid-a' }));
    const b = stateKey(alnStateKey({ deviceId: 'mac-uuid-b' }));
    expect(a).not.toBe(b);
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

  it('round-trips under the key the background poll actually uses', async () => {
    const key = alnStateKey({ deviceId: 'a3f9c2e14b7d48a19f0c5e6b2d8a1f34' });
    await saveState(key, { afterSeq: 12, seenIds: ['wg.done:3'] });
    const s = await loadState(key);
    expect(s.afterSeq).toBe(12);
    expect(s.seenIds).toEqual(['wg.done:3']);
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

describe('eventId', () => {
  it('builds kind:seq for a usable frame', () => {
    expect(eventId({ event: 'wg.done', seq: 7 })).toBe('wg.done:7');
  });

  it('is empty for a seq-less frame so it can never be stored as "kind:"', () => {
    expect(eventId({ event: 'wg.done', seq: null })).toBe('');
    expect(eventId({ event: 'wg.done' })).toBe('');
    expect(eventId({ seq: 3 })).toBe('');
  });
});

describe('mutateState serialization', () => {
  beforeEach(() => { store.clear(); });

  it('does not lose an update when two read-modify-writes overlap', async () => {
    await saveState('c1', { afterSeq: 0, seenIds: [], lastPollMs: 0, lastSuccessMs: 0, lastError: '' });

    await Promise.all([
      mutateState('c1', (s) => ({ ...s, afterSeq: 42 })),
      mutateState('c1', (s) => ({ ...s, lastSuccessMs: 99 })),
    ]);

    const s = await loadState('c1');
    expect(s.afterSeq).toBe(42);
    expect(s.lastSuccessMs).toBe(99);
  });

  it('a concurrent seen-only write cannot roll the cursor back', async () => {
    await saveState('c1', { afterSeq: 120, seenIds: [], lastPollMs: 0, lastSuccessMs: 0, lastError: '' });

    await Promise.all([
      mutateState('c1', (s) => recordSeen(s, 'agent.message:400')),
      mutateState('c1', (s) => ({ ...s, afterSeq: 130 })),
    ]);

    const s = await loadState('c1');
    expect(s.afterSeq).toBe(130);
    expect(s.seenIds).toEqual(['agent.message:400']);
  });

  it('a forget landing mid-delivery is not resurrected by the in-flight write', async () => {
    await saveState('c1', { afterSeq: 1, seenIds: [], lastPollMs: 0, lastSuccessMs: 0, lastError: '' });

    let release;
    const parked = new Promise((r) => { release = r; });
    const inFlight = mutateState('c1', async (st) => {
      await parked;
      return { ...st, afterSeq: 77 };
    });
    const forget = clearState('c1');
    release();
    await Promise.all([inFlight, forget]);

    expect(store.has('aln.state.c1')).toBe(false);
  });

  it('survives a throwing mutation without poisoning later writes on the same key', async () => {
    await saveState('c1', { afterSeq: 1, seenIds: [], lastPollMs: 0, lastSuccessMs: 0, lastError: '' });

    await expect(mutateState('c1', () => { throw new Error('boom'); })).rejects.toThrow('boom');
    await mutateState('c1', (s) => ({ ...s, afterSeq: 2 }));

    expect((await loadState('c1')).afterSeq).toBe(2);
  });
});

describe('flags', () => {
  beforeEach(() => { store.clear(); });

  it('round-trips a value and falls back when unset', async () => {
    expect(await loadFlag('wakeIndex', 0)).toBe(0);
    await saveFlag('wakeIndex', 2);
    expect(await loadFlag('wakeIndex', 0)).toBe(2);
  });

  it('stores booleans distinctly from the fallback', async () => {
    expect(await loadFlag('permissionAsked', false)).toBe(false);
    await saveFlag('permissionAsked', true);
    expect(await loadFlag('permissionAsked', false)).toBe(true);
  });
});
