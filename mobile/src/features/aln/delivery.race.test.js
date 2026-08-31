import { beforeEach, describe, expect, it, vi } from 'vitest';

const h = vi.hoisted(() => ({
  store: new Map(),
  fireMock: vi.fn(async () => true),
  callMock: vi.fn(),
}));

vi.mock('expo-secure-store', () => ({
  getItemAsync: vi.fn(async (k) => (h.store.has(k) ? h.store.get(k) : null)),
  setItemAsync: vi.fn(async (k, v) => { h.store.set(k, v); }),
  deleteItemAsync: vi.fn(async (k) => { h.store.delete(k); }),
}));

vi.mock('expo-background-task', () => ({
  BackgroundTaskResult: { Success: 'success', Failed: 'failed' },
  BackgroundTaskStatus: { Restricted: 'restricted' },
  getStatusAsync: vi.fn(async () => 'available'),
  registerTaskAsync: vi.fn(async () => {}),
  unregisterTaskAsync: vi.fn(async () => {}),
}));

vi.mock('expo-task-manager', () => ({
  isTaskDefined: vi.fn(() => true),
  defineTask: vi.fn(),
  isTaskRegisteredAsync: vi.fn(async () => true),
}));

vi.mock('./notify', () => ({
  fireForEvent: h.fireMock,
  getPermissionStatus: vi.fn(async () => 'granted'),
}));

vi.mock('../../lib/rpc', () => ({ call: h.callMock }));

const CONN = { id: 'c1', name: 'home', ip: '100.64.0.1', port: 49200, deviceId: 'mac', token: 't', added_at: 1 };

vi.mock('../../lib/store', () => ({ loadConnections: vi.fn(async () => ({ connections: [CONN] })) }));

import { runPollOnce } from './backgroundTask';
import { deliverEvents } from './deliver';
import { loadState, saveState } from './state';

const KEY = 'daemon:mac';
const EVENT = { event: 'agent.message', seq: 42, at: 1, data: { profile: 'abby' } };

async function waitFor(predicate) {
  for (let i = 0; i < 200; i += 1) {
    if (predicate()) return;
    await new Promise((r) => setTimeout(r, 0));
  }
  throw new Error('timed out waiting for condition');
}

beforeEach(async () => {
  h.store.clear();
  h.fireMock.mockReset();
  h.fireMock.mockImplementation(async () => true);
  h.callMock.mockReset();
  // Past first contact: the anchoring branch has its own coverage in deliver.test.js.
  await saveState(KEY, { afterSeq: 0, anchored: true, seenIds: [], lastPollMs: 0, lastSuccessMs: 0, lastError: '' });
});

describe('live stream racing the background poll', () => {
  it('notifies once and reconciles the cursor when the poll resumes with the same frame', async () => {
    let releaseRpc;
    const blockedRpc = new Promise((r) => { releaseRpc = r; });
    h.callMock.mockImplementation(async () => {
      await blockedRpc;
      return { events: [EVENT], next_seq: 42 };
    });

    // Poll enters and parks in the RPC with afterSeq still at 0.
    const poll = runPollOnce();
    try {
      await waitFor(() => h.callMock.mock.calls.length === 1);

      // The same event arrives live and completes end to end while the poll is still blocked.
      await deliverEvents([EVENT], CONN, { advanceCursor: false });
      expect(h.fireMock).toHaveBeenCalledTimes(1);
      expect((await loadState(KEY)).afterSeq).toBe(0);
    } finally {
      releaseRpc();
    }
    const result = await poll;

    expect(h.fireMock).toHaveBeenCalledTimes(1);
    expect(result.notifications).toBe(0);
    const state = await loadState(KEY);
    expect(state.afterSeq).toBe(42);
    expect(state.seenIds).toEqual(['agent.message:42']);
  });

  it('still delivers a poll-only event that the stream never saw', async () => {
    h.callMock.mockResolvedValue({ events: [EVENT], next_seq: 42 });

    const result = await runPollOnce();

    expect(h.fireMock).toHaveBeenCalledTimes(1);
    expect(result.notifications).toBe(1);
    expect((await loadState(KEY)).afterSeq).toBe(42);
  });

  it('a second poll over the same page notifies nothing and keeps the cursor put', async () => {
    h.callMock.mockResolvedValue({ events: [EVENT], next_seq: 42 });

    await runPollOnce();
    h.fireMock.mockClear();
    await runPollOnce();

    expect(h.fireMock).not.toHaveBeenCalled();
    expect((await loadState(KEY)).afterSeq).toBe(42);
  });
});

describe('a member route cannot advance the cursor past admin-only events', () => {
  const ADMIN = { id: 'admin', name: 'home', ip: '192.168.1.9', port: 49200, deviceId: 'mac', token: 'a', added_at: 100, role: 'admin' };
  const MEMBER = { id: 'member', name: 'home', ip: '100.64.0.1', port: 49200, deviceId: 'mac', token: 'm', added_at: 200, role: 'member' };

  it('leaves the cursor where the admin route can still reach the events it was never shown', async () => {
    const store = await import('../../lib/store');
    store.loadConnections.mockResolvedValueOnce({ connections: [ADMIN, MEMBER] });
    await saveState(KEY, { afterSeq: 99, anchored: true, seenIds: [], lastPollMs: 0, lastSuccessMs: 0, lastError: '' });

    // Admin route is off-LAN and fails; the member route answers with its role-filtered page.
    h.callMock
      .mockRejectedValueOnce(new Error('unreachable'))
      .mockResolvedValueOnce({ events: [{ event: 'wg.done', seq: 102, data: {} }], next_seq: 102 });

    await runPollOnce();

    const state = await loadState(KEY);
    expect(h.fireMock).toHaveBeenCalledTimes(1);
    expect(state.seenIds).toEqual(['wg.done:102']);
    // 100 and 101 were stripped for the member; the admin route must still be able to fetch them.
    expect(state.afterSeq).toBe(99);
  });

  it('the admin route then delivers what the member never saw, without repeating the member\'s event', async () => {
    const store = await import('../../lib/store');
    store.loadConnections.mockResolvedValue({ connections: [ADMIN] });
    await saveState(KEY, { afterSeq: 99, anchored: true, seenIds: ['wg.done:102'], lastPollMs: 0, lastSuccessMs: 0, lastError: '' });

    h.callMock.mockResolvedValue({
      events: [
        { event: 'agent.message', seq: 100, data: {} },
        { event: 'wg.done', seq: 102, data: {} },
      ],
      next_seq: 102,
    });

    const result = await runPollOnce();

    expect(result.notifications).toBe(1);
    expect(h.fireMock.mock.calls.map((c) => c[0].seq)).toEqual([100]);
    expect((await loadState(KEY)).afterSeq).toBe(102);
  });
});
