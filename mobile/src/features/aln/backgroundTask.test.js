import { beforeEach, describe, expect, it, vi } from 'vitest';

const hoisted = vi.hoisted(() => ({
  fireMock: vi.fn(async () => true),
  pollMock: vi.fn(),
  commitMock: vi.fn(async () => {}),
  permMock: vi.fn(async () => 'granted'),
  loadConnectionsMock: vi.fn(async () => ({ connections: [] })),
}));

vi.mock('./notify', () => ({
  fireForEvent: hoisted.fireMock,
  getPermissionStatus: hoisted.permMock,
}));

vi.mock('./poll', () => ({
  pollConnection: hoisted.pollMock,
  commitDelivered: hoisted.commitMock,
  WAKE_BUDGET_MS: 25_000,
}));

vi.mock('./state', () => ({
  alnStateKey: (conn) => (conn?.deviceId ? `daemon:${conn.deviceId}` : ''),
}));

vi.mock('../../lib/store', () => ({
  loadConnections: hoisted.loadConnectionsMock,
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

import { groupConnectionsByDaemon, runPollOnce } from './backgroundTask';

beforeEach(() => {
  hoisted.fireMock.mockReset();
  hoisted.fireMock.mockImplementation(async () => true);
  hoisted.pollMock.mockReset();
  hoisted.commitMock.mockReset();
  hoisted.commitMock.mockImplementation(async () => {});
  hoisted.permMock.mockReset();
  hoisted.permMock.mockImplementation(async () => 'granted');
  hoisted.loadConnectionsMock.mockReset();
  hoisted.loadConnectionsMock.mockImplementation(async () => ({ connections: [] }));
});

describe('groupConnectionsByDaemon', () => {
  it('groups multiple routes to the same daemon under one group', () => {
    const conns = [
      { id: 'a', ip: '100.114.140.25', port: 49200, deviceId: 'mac', added_at: 1 },
      { id: 'b', ip: '192.168.1.10', port: 49200, deviceId: 'mac', added_at: 2 },
      { id: 'c', ip: '10.0.0.5', port: 49200, deviceId: 'umbrel', added_at: 3 },
    ];
    const groups = groupConnectionsByDaemon(conns);
    expect(groups).toHaveLength(2);
    const macGroup = groups.find((g) => g[0].deviceId === 'mac');
    expect(macGroup).toHaveLength(2);
    expect(macGroup.map((c) => c.id).sort()).toEqual(['a', 'b']);
  });

  it('orders routes within a group by added_at descending — most recently added is tried first', () => {
    const conns = [
      { id: 'old', ip: '192.168.x', port: 49200, deviceId: 'mac', added_at: 100 },
      { id: 'new', ip: '100.x', port: 49200, deviceId: 'mac', added_at: 200 },
      { id: 'mid', ip: '10.x', port: 49200, deviceId: 'mac', added_at: 150 },
    ];
    const [group] = groupConnectionsByDaemon(conns);
    expect(group.map((c) => c.id)).toEqual(['new', 'mid', 'old']);
  });

  it('drops connections without deviceId — no legacy fallback by design', () => {
    const conns = [
      { id: 'a', ip: '100.x', port: 49200 },
      { id: 'b', ip: '192.168.x', port: 49200, deviceId: 'mac' },
    ];
    const groups = groupConnectionsByDaemon(conns);
    expect(groups).toHaveLength(1);
    expect(groups[0][0].id).toBe('b');
  });

  it('drops malformed entries (missing id/ip/port)', () => {
    const conns = [
      { id: 'a', ip: '1.1.1.1', port: 80, deviceId: 'd1' },
      { id: 'b', ip: '', port: 80, deviceId: 'd2' },
      { ip: '1.1.1.1', port: 80, deviceId: 'd3' },
      { id: 'c', ip: '1.1.1.1', deviceId: 'd4' },
    ];
    const groups = groupConnectionsByDaemon(conns).flat();
    expect(groups.map((c) => c.id)).toEqual(['a']);
  });

  it('tolerates non-array input', () => {
    expect(groupConnectionsByDaemon(null)).toEqual([]);
    expect(groupConnectionsByDaemon(undefined)).toEqual([]);
    expect(groupConnectionsByDaemon({})).toEqual([]);
  });
});

describe('runPollOnce', () => {
  const conn = { id: 'c1', ip: '100.64.0.1', port: 49200, deviceId: 'mac', token: 't', added_at: 1 };
  const ev1 = { event: 'agent.message', seq: 10, data: { profile: 'abby' } };
  const ev2 = { event: 'agent.message', seq: 11, data: { profile: 'abby' } };

  it('commits the events BEFORE firing notifications — claim-before-fire so an OS-kill mid-task cannot re-fire the same event next wake', async () => {
    hoisted.loadConnectionsMock.mockResolvedValueOnce({ connections: [conn] });
    hoisted.pollMock.mockResolvedValueOnce({ ok: true, events: [ev1, ev2] });

    const order = [];
    hoisted.commitMock.mockImplementation(async (key, evs) => {
      order.push(['commit', key, evs.length]);
    });
    hoisted.fireMock.mockImplementation(async (ev) => {
      order.push(['fire', ev.seq]);
      return true;
    });

    await runPollOnce();

    expect(order).toEqual([
      ['commit', 'daemon:mac', 2],
      ['fire', 10],
      ['fire', 11],
    ]);
  });

  it('keeps firing later events even if an earlier fire returns false (foreground gate)', async () => {
    hoisted.loadConnectionsMock.mockResolvedValueOnce({ connections: [conn] });
    hoisted.pollMock.mockResolvedValueOnce({ ok: true, events: [ev1, ev2] });
    hoisted.fireMock
      .mockResolvedValueOnce(false)
      .mockResolvedValueOnce(true);

    const result = await runPollOnce();

    expect(hoisted.fireMock).toHaveBeenCalledTimes(2);
    expect(result.notifications).toBe(1);
  });

  it('fails over to the next route in the same daemon group when the first route returns ok=false', async () => {
    const lan = { id: 'lan', ip: '192.168.x', port: 49200, deviceId: 'mac', added_at: 200, token: 'lan-tok' };
    const ts  = { id: 'ts',  ip: '100.x',     port: 49200, deviceId: 'mac', added_at: 100, token: 'ts-tok' };
    hoisted.loadConnectionsMock.mockResolvedValueOnce({ connections: [lan, ts] });
    hoisted.pollMock
      .mockResolvedValueOnce({ ok: false, events: [] })
      .mockResolvedValueOnce({ ok: true, events: [ev1] });

    await runPollOnce();

    expect(hoisted.pollMock).toHaveBeenCalledTimes(2);
    expect(hoisted.pollMock.mock.calls[0][0].id).toBe('lan');
    expect(hoisted.pollMock.mock.calls[1][0].id).toBe('ts');
    expect(hoisted.commitMock).toHaveBeenCalledWith('daemon:mac', [ev1]);
    expect(hoisted.fireMock).toHaveBeenCalledTimes(1);
  });

  it('stops trying routes for a daemon as soon as one route succeeds — failover does NOT cascade beyond the first ok=true', async () => {
    const a = { id: 'a', ip: '1.x', port: 49200, deviceId: 'mac', added_at: 200 };
    const b = { id: 'b', ip: '2.x', port: 49200, deviceId: 'mac', added_at: 100 };
    hoisted.loadConnectionsMock.mockResolvedValueOnce({ connections: [a, b] });
    hoisted.pollMock.mockResolvedValueOnce({ ok: true, events: [] });

    await runPollOnce();

    expect(hoisted.pollMock).toHaveBeenCalledTimes(1);
    expect(hoisted.pollMock.mock.calls[0][0].id).toBe('a');
  });

  it('skips the whole daemon group when every route fails (no spurious commit, no spurious notification)', async () => {
    const a = { id: 'a', ip: '1.x', port: 49200, deviceId: 'mac', added_at: 2 };
    const b = { id: 'b', ip: '2.x', port: 49200, deviceId: 'mac', added_at: 1 };
    hoisted.loadConnectionsMock.mockResolvedValueOnce({ connections: [a, b] });
    hoisted.pollMock.mockResolvedValue({ ok: false, events: [] });

    const result = await runPollOnce();

    expect(hoisted.pollMock).toHaveBeenCalledTimes(2);
    expect(hoisted.commitMock).not.toHaveBeenCalled();
    expect(hoisted.fireMock).not.toHaveBeenCalled();
    expect(result.notifications).toBe(0);
  });

  it('refuses to run when another runPollOnce is already in flight (anti-overlap mutex)', async () => {
    hoisted.loadConnectionsMock.mockResolvedValueOnce({ connections: [conn] });
    let resolvePoll;
    const blockedPoll = new Promise((r) => { resolvePoll = r; });
    hoisted.pollMock.mockImplementation(async () => {
      await blockedPoll;
      return { ok: true, events: [] };
    });

    const first = runPollOnce();
    try {
      const second = await runPollOnce();
      expect(second.skipped).toBe('in-flight');
    } finally {
      resolvePoll();
      await first;
    }
  });

  it('skips commit when poll returns no events (avoids a no-op write)', async () => {
    hoisted.loadConnectionsMock.mockResolvedValueOnce({ connections: [conn] });
    hoisted.pollMock.mockResolvedValueOnce({ ok: true, events: [] });

    await runPollOnce();

    expect(hoisted.commitMock).not.toHaveBeenCalled();
    expect(hoisted.fireMock).not.toHaveBeenCalled();
  });

  it('bails early with skipped=no-permission when notifications are denied', async () => {
    hoisted.permMock.mockResolvedValueOnce('denied');
    const result = await runPollOnce();
    expect(result).toEqual({ groups: 0, notifications: 0, skipped: 'no-permission' });
    expect(hoisted.pollMock).not.toHaveBeenCalled();
  });

  it('skips connections without deviceId entirely (no legacy fallback)', async () => {
    hoisted.loadConnectionsMock.mockResolvedValueOnce({
      connections: [
        { id: 'legacy', ip: '100.x', port: 49200, added_at: 1 },
      ],
    });

    const result = await runPollOnce();
    expect(hoisted.pollMock).not.toHaveBeenCalled();
    expect(result.groups).toBe(0);
  });
});
