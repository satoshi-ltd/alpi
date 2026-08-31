import { beforeEach, describe, expect, it, vi } from 'vitest';

const hoisted = vi.hoisted(() => ({
  deliverMock: vi.fn(async (events) => events.length),
  pollMock: vi.fn(),
  healthMock: vi.fn(async () => {}),
  permMock: vi.fn(async () => 'granted'),
  loadConnectionsMock: vi.fn(async () => ({ connections: [] })),
  loadFlagMock: vi.fn(async (_name, fallback) => fallback),
  saveFlagMock: vi.fn(async () => {}),
}));

vi.mock('./notify', () => ({
  getPermissionStatus: hoisted.permMock,
}));

vi.mock('./deliver', () => ({
  deliverEvents: hoisted.deliverMock,
}));

vi.mock('./poll', () => ({
  pollConnection: hoisted.pollMock,
  recordGroupHealth: hoisted.healthMock,
  WAKE_BUDGET_MS: 25_000,
  POLL_TIMEOUT_MS: 8_000,
}));

vi.mock('./state', () => ({
  alnStateKey: (conn) => (conn?.deviceId ? `daemon:${conn.deviceId}` : ''),
  loadFlag: hoisted.loadFlagMock,
  saveFlag: hoisted.saveFlagMock,
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
  hoisted.deliverMock.mockReset();
  hoisted.deliverMock.mockImplementation(async (events) => events.length);
  hoisted.pollMock.mockReset();
  hoisted.healthMock.mockReset();
  hoisted.healthMock.mockImplementation(async () => {});
  hoisted.permMock.mockReset();
  hoisted.permMock.mockImplementation(async () => 'granted');
  hoisted.loadConnectionsMock.mockReset();
  hoisted.loadConnectionsMock.mockImplementation(async () => ({ connections: [] }));
  hoisted.loadFlagMock.mockReset();
  hoisted.loadFlagMock.mockImplementation(async (_name, fallback) => fallback);
  hoisted.saveFlagMock.mockReset();
  hoisted.saveFlagMock.mockImplementation(async () => {});
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

  it('keeps member routes but ranks them behind admin — a member-only pairing must still poll its permitted kinds', () => {
    const conns = [
      { id: 'm', ip: '100.x', port: 49200, deviceId: 'mac', added_at: 200, role: 'member' },
      { id: 'a', ip: '192.x', port: 49200, deviceId: 'mac', added_at: 100, role: 'admin' },
    ];
    const groups = groupConnectionsByDaemon(conns);
    expect(groups).toHaveLength(1);
    expect(groups[0].map((c) => c.id)).toEqual(['a', 'm']);
  });

  it('groups a member-only daemon instead of dropping it', () => {
    const conns = [{ id: 'm', ip: '100.x', port: 49200, deviceId: 'mac', added_at: 1, role: 'member' }];
    expect(groupConnectionsByDaemon(conns).flat().map((c) => c.id)).toEqual(['m']);
  });

  it('keeps routes whose role is unknown (unprobed)', () => {
    const conns = [{ id: 'u', ip: '100.x', port: 49200, deviceId: 'mac', added_at: 1 }];
    expect(groupConnectionsByDaemon(conns).flat().map((c) => c.id)).toEqual(['u']);
  });
});

describe('runPollOnce', () => {
  const conn = { id: 'c1', ip: '100.64.0.1', port: 49200, deviceId: 'mac', token: 't', added_at: 1 };
  const ev1 = { event: 'agent.message', seq: 10, data: { profile: 'abby' } };
  const ev2 = { event: 'agent.message', seq: 11, data: { profile: 'abby' } };

  it('hands the whole page to the single delivery coordinator, untouched and in order', async () => {
    hoisted.loadConnectionsMock.mockResolvedValueOnce({ connections: [conn] });
    hoisted.pollMock.mockResolvedValueOnce({ ok: true, events: [ev1, ev2] });

    const result = await runPollOnce();

    expect(hoisted.deliverMock).toHaveBeenCalledTimes(1);
    const [events, route] = hoisted.deliverMock.mock.calls[0];
    expect(events).toEqual([ev1, ev2]);
    expect(route.id).toBe('c1');
    expect(result.notifications).toBe(2);
  });

  it('counts only what the coordinator actually notified', async () => {
    hoisted.loadConnectionsMock.mockResolvedValueOnce({ connections: [conn] });
    hoisted.pollMock.mockResolvedValueOnce({ ok: true, events: [ev1, ev2] });
    hoisted.deliverMock.mockResolvedValueOnce(1);

    const result = await runPollOnce();

    expect(result.notifications).toBe(1);
  });

  it('rotates the starting daemon group across wakes so a budget cut never starves the same one', async () => {
    const d1 = { id: 'd1', ip: '1.x', port: 49200, deviceId: 'one', added_at: 1 };
    const d2 = { id: 'd2', ip: '2.x', port: 49200, deviceId: 'two', added_at: 1 };
    const d3 = { id: 'd3', ip: '3.x', port: 49200, deviceId: 'three', added_at: 1 };
    hoisted.loadConnectionsMock.mockResolvedValue({ connections: [d1, d2, d3] });
    hoisted.pollMock.mockResolvedValue({ ok: true, events: [], nextSeq: null });

    let stored = 0;
    hoisted.loadFlagMock.mockImplementation(async () => stored);
    hoisted.saveFlagMock.mockImplementation(async (_name, value) => { stored = value; });

    await runPollOnce();
    const firstWake = hoisted.pollMock.mock.calls.map((c) => c[0].id);
    hoisted.pollMock.mockClear();
    await runPollOnce();
    const secondWake = hoisted.pollMock.mock.calls.map((c) => c[0].id);

    expect(firstWake[0]).toBe('d1');
    expect(secondWake[0]).toBe('d2');
    expect(stored).toBe(2);
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
    expect(hoisted.deliverMock).toHaveBeenCalledTimes(1);
    expect(hoisted.deliverMock.mock.calls[0][0]).toEqual([ev1]);
  });

  it('a route WITH events wins immediately and stops the search', async () => {
    const a = { id: 'a', ip: '1.x', port: 49200, deviceId: 'mac', added_at: 200 };
    const b = { id: 'b', ip: '2.x', port: 49200, deviceId: 'mac', added_at: 100 };
    hoisted.loadConnectionsMock.mockResolvedValueOnce({ connections: [a, b] });
    hoisted.pollMock.mockResolvedValueOnce({ ok: true, events: [ev1] });

    await runPollOnce();

    expect(hoisted.pollMock).toHaveBeenCalledTimes(1);
    expect(hoisted.pollMock.mock.calls[0][0].id).toBe('a');
  });

  it('an ok+empty route does not stop the search — a legacy member (unknown role) cannot shadow an admin with events', async () => {
    const member = { id: 'member', ip: '100.x', port: 49200, deviceId: 'mac', added_at: 200, token: 'm' };
    const admin = { id: 'admin', ip: '192.168.x', port: 49200, deviceId: 'mac', added_at: 100, token: 'a' };
    hoisted.loadConnectionsMock.mockResolvedValueOnce({ connections: [member, admin] });
    hoisted.pollMock
      .mockResolvedValueOnce({ ok: true, events: [] })
      .mockResolvedValueOnce({ ok: true, events: [ev1] });

    await runPollOnce();

    expect(hoisted.pollMock).toHaveBeenCalledTimes(2);
    expect(hoisted.pollMock.mock.calls[0][0].id).toBe('member');
    expect(hoisted.pollMock.mock.calls[1][0].id).toBe('admin');
    expect(hoisted.deliverMock).toHaveBeenCalledTimes(1);
    expect(hoisted.deliverMock.mock.calls[0][0]).toEqual([ev1]);
  });

  it('skips the whole daemon group when every route fails (no spurious commit, no spurious notification)', async () => {
    const a = { id: 'a', ip: '1.x', port: 49200, deviceId: 'mac', added_at: 2 };
    const b = { id: 'b', ip: '2.x', port: 49200, deviceId: 'mac', added_at: 1 };
    hoisted.loadConnectionsMock.mockResolvedValueOnce({ connections: [a, b] });
    hoisted.pollMock.mockResolvedValue({ ok: false, events: [] });

    const result = await runPollOnce();

    expect(hoisted.pollMock).toHaveBeenCalledTimes(2);
    expect(hoisted.deliverMock).not.toHaveBeenCalled();
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

  it('still calls the coordinator on an empty page so a fresh daemon can anchor', async () => {
    hoisted.loadConnectionsMock.mockResolvedValueOnce({ connections: [conn] });
    hoisted.pollMock.mockResolvedValueOnce({ ok: true, events: [], nextSeq: 40 });

    const result = await runPollOnce();

    expect(hoisted.deliverMock).toHaveBeenCalledTimes(1);
    const [events, , opts] = hoisted.deliverMock.mock.calls[0];
    expect(events).toEqual([]);
    expect(opts.nextSeq).toBe(40);
    expect(result.notifications).toBe(0);
  });

  it('reports a daemon reachable only through a member fallback as degraded', async () => {
    const admin = { id: 'admin', ip: '192.168.x', port: 49200, deviceId: 'mac', added_at: 100, role: 'admin' };
    const member = { id: 'member', ip: '100.x', port: 49200, deviceId: 'mac', added_at: 200, role: 'member' };
    hoisted.loadConnectionsMock.mockResolvedValueOnce({ connections: [admin, member] });
    hoisted.pollMock
      .mockResolvedValueOnce({ ok: false, events: [], error: 'unreachable' })
      .mockResolvedValueOnce({ ok: true, events: [], nextSeq: 5 });

    await runPollOnce();

    expect(hoisted.healthMock.mock.calls[0][1].degraded).toBe(true);
  });

  it('is not degraded once the admin route answers', async () => {
    const admin = { id: 'admin', ip: '192.168.x', port: 49200, deviceId: 'mac', added_at: 100, role: 'admin' };
    const member = { id: 'member', ip: '100.x', port: 49200, deviceId: 'mac', added_at: 200, role: 'member' };
    hoisted.loadConnectionsMock.mockResolvedValueOnce({ connections: [admin, member] });
    hoisted.pollMock.mockResolvedValue({ ok: true, events: [], nextSeq: 5 });

    await runPollOnce();

    expect(hoisted.healthMock.mock.calls[0][1].degraded).toBe(false);
  });

  it('bails early with skipped=no-permission when notifications are denied', async () => {
    hoisted.permMock.mockResolvedValueOnce('denied');
    const result = await runPollOnce();
    expect(result).toEqual({ groups: 0, notifications: 0, skipped: 'no-permission' });
    expect(hoisted.pollMock).not.toHaveBeenCalled();
  });

  it('a recent member route does not shadow the same daemon\'s older admin route', async () => {
    const member = { id: 'member', ip: '100.x', port: 49200, deviceId: 'mac', added_at: 200, role: 'member', token: 'm' };
    const admin = { id: 'admin', ip: '192.168.x', port: 49200, deviceId: 'mac', added_at: 100, role: 'admin', token: 'a' };
    hoisted.loadConnectionsMock.mockResolvedValueOnce({ connections: [member, admin] });
    hoisted.pollMock.mockResolvedValueOnce({ ok: true, events: [ev1] });

    await runPollOnce();

    expect(hoisted.pollMock).toHaveBeenCalledTimes(1);
    expect(hoisted.pollMock.mock.calls[0][0].id).toBe('admin');
    expect(hoisted.deliverMock).toHaveBeenCalledTimes(1);
    expect(hoisted.deliverMock.mock.calls[0][0]).toEqual([ev1]);
  });

  it('polls a member-only daemon at all — dropping it produced zero notifications forever', async () => {
    const member = { id: 'm', ip: '100.x', port: 49200, deviceId: 'mac', added_at: 1, role: 'member', token: 'm' };
    hoisted.loadConnectionsMock.mockResolvedValueOnce({ connections: [member] });
    hoisted.pollMock.mockResolvedValueOnce({ ok: true, events: [] });

    await runPollOnce();

    expect(hoisted.pollMock).toHaveBeenCalledTimes(1);
    expect(hoisted.pollMock.mock.calls[0][0].id).toBe('m');
  });

  it('delivers a member-only daemon\'s page — wg.done survives the daemon\'s role filter, agent.message would not', async () => {
    const member = { id: 'm', ip: '100.x', port: 49200, deviceId: 'mac', added_at: 1, role: 'member', token: 'm' };
    const permitted = { event: 'wg.done', seq: 12, data: { wg_id: 'wg1' } };
    hoisted.loadConnectionsMock.mockResolvedValueOnce({ connections: [member] });
    hoisted.pollMock.mockResolvedValueOnce({ ok: true, events: [permitted] });

    const result = await runPollOnce();

    expect(hoisted.deliverMock.mock.calls[0][0]).toEqual([permitted]);
    expect(result.notifications).toBe(1);
  });

  it('a member route winning a group that HAS an admin route must not advance the shared cursor', async () => {
    const admin = { id: 'admin', ip: '192.168.x', port: 49200, deviceId: 'mac', added_at: 100, role: 'admin' };
    const member = { id: 'member', ip: '100.x', port: 49200, deviceId: 'mac', added_at: 200, role: 'member' };
    hoisted.loadConnectionsMock.mockResolvedValueOnce({ connections: [admin, member] });
    hoisted.pollMock
      .mockResolvedValueOnce({ ok: false, events: [], error: 'unreachable' })
      .mockResolvedValueOnce({ ok: true, events: [{ event: 'wg.done', seq: 102 }] });

    await runPollOnce();

    expect(hoisted.deliverMock.mock.calls[0][1].id).toBe('member');
    expect(hoisted.deliverMock.mock.calls[0][2].advanceCursor).toBe(false);
  });

  it('an admin route always advances the cursor', async () => {
    const admin = { id: 'admin', ip: '192.168.x', port: 49200, deviceId: 'mac', added_at: 100, role: 'admin' };
    hoisted.loadConnectionsMock.mockResolvedValueOnce({ connections: [admin] });
    hoisted.pollMock.mockResolvedValueOnce({ ok: true, events: [ev1] });

    await runPollOnce();

    expect(hoisted.deliverMock.mock.calls[0][2].advanceCursor).toBe(true);
  });

  it('a member-only group advances its own cursor — there is no fuller view to lose', async () => {
    const member = { id: 'm', ip: '100.x', port: 49200, deviceId: 'mac', added_at: 1, role: 'member' };
    hoisted.loadConnectionsMock.mockResolvedValueOnce({ connections: [member] });
    hoisted.pollMock.mockResolvedValueOnce({ ok: true, events: [{ event: 'wg.done', seq: 12 }] });

    await runPollOnce();

    expect(hoisted.deliverMock.mock.calls[0][2].advanceCursor).toBe(true);
  });

  it('writes health once per daemon, marking it reached when ANY route answered', async () => {
    const lan = { id: 'lan', ip: '192.168.x', port: 49200, deviceId: 'mac', added_at: 200 };
    const ts = { id: 'ts', ip: '100.x', port: 49200, deviceId: 'mac', added_at: 100 };
    hoisted.loadConnectionsMock.mockResolvedValueOnce({ connections: [lan, ts] });
    hoisted.pollMock
      .mockResolvedValueOnce({ ok: false, events: [], error: 'unreachable' })
      .mockResolvedValueOnce({ ok: true, events: [] });

    await runPollOnce();

    expect(hoisted.healthMock).toHaveBeenCalledTimes(1);
    expect(hoisted.healthMock.mock.calls[0][1]).toEqual({ ok: true, error: 'unreachable', degraded: false });
  });

  it('reports a daemon as unreached only when every route failed', async () => {
    hoisted.loadConnectionsMock.mockResolvedValueOnce({ connections: [conn] });
    hoisted.pollMock.mockResolvedValueOnce({ ok: false, events: [], error: 'unreachable' });

    await runPollOnce();

    expect(hoisted.healthMock.mock.calls[0][1]).toEqual({ ok: false, error: 'unreachable', degraded: false });
  });

  it('one daemon throwing does not abort the rest of the wake', async () => {
    const d1 = { id: 'd1', ip: '1.x', port: 49200, deviceId: 'one', added_at: 1 };
    const d2 = { id: 'd2', ip: '2.x', port: 49200, deviceId: 'two', added_at: 1 };
    hoisted.loadConnectionsMock.mockResolvedValueOnce({ connections: [d1, d2] });
    hoisted.pollMock.mockImplementation(async (route) => {
      if (route.id === 'd1') throw new Error('boom');
      return { ok: true, events: [ev1] };
    });

    const result = await runPollOnce();

    expect(result.notifications).toBe(1);
  });

  it('stops polling further daemons once the wake budget cannot fit another poll', async () => {
    const many = Array.from({ length: 6 }, (_, i) => (
      { id: `d${i}`, ip: `${i}.x`, port: 49200, deviceId: `dev${i}`, added_at: 1 }
    ));
    hoisted.loadConnectionsMock.mockResolvedValueOnce({ connections: many });
    let now = 0;
    const spy = vi.spyOn(Date, 'now').mockImplementation(() => now);
    try {
      hoisted.pollMock.mockImplementation(async () => { now += 4000; return { ok: true, events: [] }; });
      await runPollOnce({ budgetMs: 20_000 });
    } finally {
      spy.mockRestore();
    }

    expect(hoisted.pollMock.mock.calls.length).toBeLessThan(6);
  });

  it('caps how many daemon groups are polled at once', async () => {
    const many = Array.from({ length: 8 }, (_, i) => (
      { id: `d${i}`, ip: `${i}.x`, port: 49200, deviceId: `dev${i}`, added_at: 1 }
    ));
    hoisted.loadConnectionsMock.mockResolvedValueOnce({ connections: many });
    let inFlight = 0;
    let peak = 0;
    hoisted.pollMock.mockImplementation(async () => {
      inFlight += 1;
      peak = Math.max(peak, inFlight);
      await new Promise((r) => setTimeout(r, 0));
      inFlight -= 1;
      return { ok: true, events: [] };
    });

    await runPollOnce();

    expect(peak).toBe(3);
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
