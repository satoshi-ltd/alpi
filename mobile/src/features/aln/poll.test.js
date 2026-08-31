import { beforeEach, describe, expect, it, vi } from 'vitest';

const hoisted = vi.hoisted(() => ({
  store: new Map(),
  callMock: vi.fn(async () => ({ events: [] })),
}));

vi.mock('expo-secure-store', () => ({
  getItemAsync: vi.fn(async (k) => (hoisted.store.has(k) ? hoisted.store.get(k) : null)),
  setItemAsync: vi.fn(async (k, v) => { hoisted.store.set(k, v); }),
  deleteItemAsync: vi.fn(async (k) => { hoisted.store.delete(k); }),
}));

vi.mock('../../lib/rpc', () => ({ call: hoisted.callMock }));

import { pollConnection, recordGroupHealth } from './poll';
import { loadState, saveState } from './state';

const CONN = { id: 'c1', ip: '100.64.0.1', port: 49200, deviceId: 'mac', token: 't' };
const KEY = 'daemon:mac';

beforeEach(() => {
  hoisted.store.clear();
  hoisted.callMock.mockReset();
  hoisted.callMock.mockImplementation(async () => ({ events: [] }));
});

describe('pollConnection', () => {
  it('asks from the persisted cursor and for the daemon-clamped page size', async () => {
    await saveState(KEY, { afterSeq: 17, seenIds: [], lastPollMs: 0, lastSuccessMs: 0, lastError: '' });

    await pollConnection(CONN);

    const [, method, params] = hoisted.callMock.mock.calls[0];
    expect(method).toBe('host.events.history');
    expect(params.after_seq).toBe(17);
    expect(params.limit).toBe(500);
    expect(params.kinds).toContain('approval.request');
  });

  it('returns the whole page including events already seen — dedupe belongs to deliverEvents', async () => {
    await saveState(KEY, {
      afterSeq: 0,
      seenIds: ['agent.message:10'],
      lastPollMs: 0,
      lastSuccessMs: 0,
      lastError: '',
    });
    hoisted.callMock.mockResolvedValueOnce({
      events: [{ event: 'agent.message', seq: 10 }, { event: 'agent.message', seq: 11 }],
    });

    const result = await pollConnection(CONN);

    expect(result.ok).toBe(true);
    expect(result.events.map((e) => e.seq)).toEqual([10, 11]);
  });

  it('reports the failure without writing health or touching the cursor', async () => {
    await saveState(KEY, { afterSeq: 9, seenIds: [], lastPollMs: 0, lastSuccessMs: 0, lastError: '' });
    hoisted.callMock.mockRejectedValueOnce(new Error('unreachable'));

    const result = await pollConnection(CONN);

    expect(result.ok).toBe(false);
    expect(result.events).toEqual([]);
    expect(result.error).toContain('unreachable');
    const s = await loadState(KEY);
    expect(s.lastError).toBe('');
    expect(s.afterSeq).toBe(9);
  });

  it('resets a cursor left above the daemon counter after a seq reset', async () => {
    await saveState(KEY, { afterSeq: 312, anchored: true, seenIds: ['agent.message:300'], lastPollMs: 0, lastSuccessMs: 0, lastError: '' });
    hoisted.callMock.mockResolvedValueOnce({ events: [], next_seq: 3 });

    await pollConnection(CONN);

    const s = await loadState(KEY);
    expect(s.afterSeq).toBe(0);
    expect(s.seenIds).toEqual([]);
    expect(s.anchored).toBe(true);
  });

  it('leaves the cursor alone when next_seq is merely ahead', async () => {
    await saveState(KEY, { afterSeq: 10, anchored: true, seenIds: [], lastPollMs: 0, lastSuccessMs: 0, lastError: '' });
    hoisted.callMock.mockResolvedValueOnce({ events: [], next_seq: 40 });

    await pollConnection(CONN);

    expect((await loadState(KEY)).afterSeq).toBe(10);
  });

  it('tolerates a malformed events field', async () => {
    hoisted.callMock.mockResolvedValueOnce({ events: 'nope' });

    const result = await pollConnection(CONN);

    expect(result.ok).toBe(true);
    expect(result.events).toEqual([]);
  });
});

describe('recordGroupHealth', () => {
  it('records a reachable daemon and clears a stale error', async () => {
    await saveState(KEY, { afterSeq: 0, seenIds: [], lastPollMs: 0, lastSuccessMs: 0, lastError: 'old' });

    await recordGroupHealth(CONN, { ok: true, error: '' });

    const s = await loadState(KEY);
    expect(s.lastSuccessMs).toBeGreaterThan(0);
    expect(s.lastError).toBe('');
  });

  it('records the error only when no route reached the daemon', async () => {
    await recordGroupHealth(CONN, { ok: false, error: 'unreachable' });

    const s = await loadState(KEY);
    expect(s.lastError).toBe('unreachable');
    expect(s.lastSuccessMs).toBe(0);
  });
});
