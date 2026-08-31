import { beforeEach, describe, expect, it, vi } from 'vitest';

const h = vi.hoisted(() => ({
  store: new Map(),
  fireMock: vi.fn(async () => true),
  permMock: vi.fn(async () => 'granted'),
}));

vi.mock('expo-secure-store', () => ({
  getItemAsync: vi.fn(async (k) => (h.store.has(k) ? h.store.get(k) : null)),
  setItemAsync: vi.fn(async (k, v) => { h.store.set(k, v); }),
  deleteItemAsync: vi.fn(async (k) => { h.store.delete(k); }),
}));

vi.mock('./notify', () => ({ fireForEvent: h.fireMock, getPermissionStatus: h.permMock }));

import { deliverEvents } from './deliver';
import { loadState, saveState, stateKey } from './state';

const CONN = { id: 'c1', name: 'home', deviceId: 'mac' };
const KEY = 'daemon:mac';

const msg = (seq) => ({ event: 'agent.message', seq, data: {} });

const ANCHORED = { afterSeq: 0, anchored: true, seenIds: [], lastPollMs: 0, lastSuccessMs: 0, lastError: '' };

beforeEach(async () => {
  h.store.clear();
  h.fireMock.mockReset();
  h.fireMock.mockImplementation(async () => true);
  h.permMock.mockReset();
  h.permMock.mockImplementation(async () => 'granted');
  // Every test below is about steady state; first-contact anchoring has its own describe.
  await saveState(KEY, ANCHORED);
});

describe('deliverEvents', () => {
  it('fires each unseen event once and advances the cursor to the last delivered seq', async () => {
    const fired = await deliverEvents([msg(10), msg(11)], CONN);

    expect(fired).toBe(2);
    expect(h.fireMock).toHaveBeenCalledTimes(2);
    const s = await loadState(KEY);
    expect(s.afterSeq).toBe(11);
    expect(s.seenIds).toEqual(['agent.message:10', 'agent.message:11']);
  });

  it('consumes an already-seen event without re-notifying, so the cursor stops re-downloading it', async () => {
    await deliverEvents([msg(10)], CONN, { advanceCursor: false });
    expect((await loadState(KEY)).afterSeq).toBe(0);
    h.fireMock.mockClear();

    const fired = await deliverEvents([msg(10), msg(11)], CONN);

    expect(fired).toBe(1);
    expect(h.fireMock).toHaveBeenCalledTimes(1);
    expect(h.fireMock.mock.calls[0][0].seq).toBe(11);
    expect((await loadState(KEY)).afterSeq).toBe(11);
  });

  it('advances past a page that is entirely already seen', async () => {
    await deliverEvents([msg(10), msg(11)], CONN, { advanceCursor: false });
    h.fireMock.mockClear();

    const fired = await deliverEvents([msg(10), msg(11)], CONN);

    expect(fired).toBe(0);
    expect(h.fireMock).not.toHaveBeenCalled();
    expect((await loadState(KEY)).afterSeq).toBe(11);
  });

  it('stops the batch on a failed fire and leaves the cursor below it', async () => {
    h.fireMock.mockResolvedValueOnce(true).mockResolvedValueOnce(false);

    const fired = await deliverEvents([msg(10), msg(11), msg(12)], CONN);

    expect(fired).toBe(1);
    expect(h.fireMock).toHaveBeenCalledTimes(2);
    const s = await loadState(KEY);
    expect(s.afterSeq).toBe(10);
    expect(s.seenIds).toEqual(['agent.message:10']);
  });

  it('treats a throwing fire like a failure rather than propagating', async () => {
    h.fireMock.mockRejectedValueOnce(new Error('scheduler down'));

    await expect(deliverEvents([msg(10)], CONN)).resolves.toBe(0);
    expect((await loadState(KEY)).afterSeq).toBe(0);
  });

  it('seen-only mode records the id but never moves afterSeq', async () => {
    await saveState(KEY, { ...ANCHORED, afterSeq: 5 });

    await deliverEvents([msg(400)], CONN, { advanceCursor: false });

    const s = await loadState(KEY);
    expect(s.afterSeq).toBe(5);
    expect(s.seenIds).toEqual(['agent.message:400']);
  });

  it('consumes an expired approval without notifying', async () => {
    const expired = {
      event: 'approval.request',
      seq: 20,
      data: { ts: Date.now() / 1000 - 600, timeout_s: 60 },
    };

    const fired = await deliverEvents([expired, msg(21)], CONN);

    expect(fired).toBe(1);
    expect(h.fireMock).toHaveBeenCalledTimes(1);
    expect(h.fireMock.mock.calls[0][0].seq).toBe(21);
    expect((await loadState(KEY)).afterSeq).toBe(21);
  });

  it('ignores a seq-less frame instead of poisoning seenIds', async () => {
    const fired = await deliverEvents([{ event: 'agent.message', seq: null }], CONN);

    expect(fired).toBe(0);
    expect(h.fireMock).not.toHaveBeenCalled();
    expect((await loadState(KEY)).seenIds).toEqual([]);
  });

  it('is inert without a deviceId', async () => {
    expect(await deliverEvents([msg(1)], { id: 'legacy' })).toBe(0);
    expect(h.fireMock).not.toHaveBeenCalled();
  });
});

describe('deliverEvents concurrency', () => {
  it('schedules exactly once when the live path and the poll path race on the same event', async () => {
    let releaseFire;
    const blockedFire = new Promise((r) => { releaseFire = r; });
    h.fireMock.mockImplementationOnce(async () => {
      await blockedFire;
      return true;
    });

    const live = deliverEvents([msg(10)], CONN, { advanceCursor: false });
    // The poll path enters while the live fire is still in flight; the lock must hold it back.
    const poll = deliverEvents([msg(10)], CONN);

    releaseFire();
    const [liveFired, pollFired] = await Promise.all([live, poll]);

    expect(h.fireMock).toHaveBeenCalledTimes(1);
    expect(liveFired).toBe(1);
    expect(pollFired).toBe(0);
    expect((await loadState(KEY)).afterSeq).toBe(10);
  });

  it('does not lose the cursor when two poll pages overlap', async () => {
    await Promise.all([
      deliverEvents([msg(10)], CONN),
      deliverEvents([msg(11)], CONN),
    ]);

    const s = await loadState(KEY);
    expect(s.afterSeq).toBe(11);
    expect(s.seenIds).toEqual(['agent.message:10', 'agent.message:11']);
  });
});

describe('deliverEvents first contact', () => {
  it('anchors a fresh daemon to the head of the page instead of replaying its backlog', async () => {
    h.store.clear();
    const backlog = Array.from({ length: 180 }, (_, i) => msg(i + 1));

    const fired = await deliverEvents(backlog, CONN);

    expect(fired).toBe(0);
    expect(h.fireMock).not.toHaveBeenCalled();
    const s = await loadState(KEY);
    expect(s.afterSeq).toBe(180);
    expect(s.anchored).toBe(true);
  });

  it('delivers normally on the very next poll once anchored', async () => {
    h.store.clear();
    await deliverEvents([msg(1), msg(2)], CONN);
    h.fireMock.mockClear();

    const fired = await deliverEvents([msg(3)], CONN);

    expect(fired).toBe(1);
    expect((await loadState(KEY)).afterSeq).toBe(3);
  });

  it('does not anchor from the live path — a stream event on a fresh pairing still notifies', async () => {
    h.store.clear();

    const fired = await deliverEvents([msg(500)], CONN, { advanceCursor: false });

    expect(fired).toBe(1);
    const s = await loadState(KEY);
    expect(s.anchored).toBe(false);
    expect(s.afterSeq).toBe(0);
  });
});

describe('deliverEvents ordering', () => {
  it('sorts the page ascending so a failed fire cannot strand a lower seq below the cursor', async () => {
    h.fireMock.mockImplementation(async (ev) => ev.seq !== 5);

    const fired = await deliverEvents([msg(6), msg(5)], CONN);

    expect(fired).toBe(0);
    const s = await loadState(KEY);
    expect(s.afterSeq).toBe(0);
    expect(s.seenIds).toEqual([]);
  });

  it('delivers an out-of-order page in seq order', async () => {
    await deliverEvents([msg(12), msg(10), msg(11)], CONN);

    expect(h.fireMock.mock.calls.map((c) => c[0].seq)).toEqual([10, 11, 12]);
  });
});

describe('deliverEvents guards', () => {
  it('refuses to deliver — or to mark seen — while notification permission is not granted', async () => {
    h.permMock.mockImplementation(async () => 'denied');

    const fired = await deliverEvents([msg(42)], CONN, { advanceCursor: false });

    expect(fired).toBe(0);
    expect(h.fireMock).not.toHaveBeenCalled();
    const s = await loadState(KEY);
    expect(s.seenIds).toEqual([]);
    expect(s.afterSeq).toBe(0);
  });

  it('persists after every fire so an OS kill mid-batch cannot replay what was already shown', async () => {
    const seenAfterEachFire = [];
    h.fireMock.mockImplementation(async (ev) => {
      seenAfterEachFire.push((await loadState(KEY)).afterSeq);
      return ev.seq !== 12;
    });

    await deliverEvents([msg(10), msg(11), msg(12)], CONN);

    expect(seenAfterEachFire).toEqual([0, 10, 11]);
    expect((await loadState(KEY)).afterSeq).toBe(11);
  });

  it('stops the batch when the wake deadline passes', async () => {
    const fired = await deliverEvents([msg(10), msg(11)], CONN, { deadline: Date.now() - 1 });

    expect(fired).toBe(0);
    expect(h.fireMock).not.toHaveBeenCalled();
  });

  it('a failed state write stops the batch instead of rejecting out of the wake', async () => {
    const store = await import('expo-secure-store');
    store.setItemAsync.mockImplementationOnce(async () => { throw new Error('keychain locked'); });

    await expect(deliverEvents([msg(10), msg(11)], CONN)).resolves.toBe(0);
    expect(h.fireMock).toHaveBeenCalledTimes(1);
  });

  it('treats a hung scheduler as a failed fire rather than wedging the daemon lock', async () => {
    vi.useFakeTimers();
    try {
      h.fireMock.mockImplementationOnce(() => new Promise(() => {}));
      const pending = deliverEvents([msg(10)], CONN);
      await vi.advanceTimersByTimeAsync(6000);
      await expect(pending).resolves.toBe(0);
    } finally {
      vi.useRealTimers();
    }
    expect((await loadState(KEY)).afterSeq).toBe(0);
  });
});

describe('deliverEvents anchoring migration and empty first page', () => {
  it('a legacy record with a cursor but no anchored field is treated as already known', async () => {
    h.store.clear();
    // Exactly what the shipped version persisted: no `anchored` key at all.
    h.store.set(stateKey(KEY), JSON.stringify({
      afterSeq: 40, seenIds: [], lastPollMs: 0, lastSuccessMs: 0, lastError: '',
    }));

    const fired = await deliverEvents([msg(41)], CONN);

    expect(fired).toBe(1);
    const s = await loadState(KEY);
    expect(s.afterSeq).toBe(41);
  });

  it('anchors from next_seq when the first page is empty', async () => {
    h.store.clear();

    const fired = await deliverEvents([], CONN, { nextSeq: 40 });

    expect(fired).toBe(0);
    const s = await loadState(KEY);
    expect(s.anchored).toBe(true);
    expect(s.afterSeq).toBe(40);
  });

  it('then delivers the very next event instead of mistaking it for backlog', async () => {
    h.store.clear();
    await deliverEvents([], CONN, { nextSeq: 40 });

    const fired = await deliverEvents([msg(41)], CONN, { nextSeq: 41 });

    expect(fired).toBe(1);
    expect(h.fireMock.mock.calls[0][0].seq).toBe(41);
  });

  it('takes the higher of the page head and next_seq when anchoring', async () => {
    h.store.clear();

    await deliverEvents([msg(10)], CONN, { nextSeq: 99 });

    expect((await loadState(KEY)).afterSeq).toBe(99);
  });

  it('an empty page from a member route does not anchor over an admin route', async () => {
    h.store.clear();

    const fired = await deliverEvents([], CONN, { advanceCursor: false, nextSeq: 40 });

    expect(fired).toBe(0);
    const s = await loadState(KEY);
    expect(s.anchored).toBe(false);
    expect(s.afterSeq).toBe(0);
  });

  it('a live event on a denied permission is neither delivered nor anchored, and arrives once granted', async () => {
    h.store.clear();
    h.permMock.mockImplementation(async () => 'denied');
    await deliverEvents([msg(7)], CONN, { advanceCursor: false });
    expect(h.fireMock).not.toHaveBeenCalled();
    expect((await loadState(KEY)).anchored).toBe(false);

    // Granting permission starts delivery: the first poll anchors, and everything after it arrives.
    h.permMock.mockImplementation(async () => 'granted');
    await deliverEvents([msg(7)], CONN, { nextSeq: 7 });
    const fired = await deliverEvents([msg(8)], CONN, { nextSeq: 8 });

    expect(fired).toBe(1);
    expect(h.fireMock.mock.calls.map((c) => c[0].seq)).toEqual([8]);
  });
});
