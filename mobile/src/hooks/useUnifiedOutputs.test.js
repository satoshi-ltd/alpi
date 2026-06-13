import { describe, expect, it, vi } from 'vitest';

import { connectionsSignature, fetchConnectionOutputs, markAllUnifiedRead, mergeOutputs } from './useUnifiedOutputs';

const conn = { id: 'c1', name: 'home', ip: '100.0.0.1', port: 8838, token: 't' };

describe('mergeOutputs', () => {
  it('flattens and sorts by created_at desc', () => {
    const merged = mergeOutputs([
      [{ id: 'a', created_at: 10 }],
      [{ id: 'b', created_at: 30 }, { id: 'c', created_at: 20 }],
    ]);
    expect(merged.map((r) => r.id)).toEqual(['b', 'c', 'a']);
  });
});

describe('fetchConnectionOutputs', () => {
  it('discovers profiles then lists outputs, tagging rows with the connection', async () => {
    const rpc = vi.fn(async (_c, method, params) => {
      if (method === 'host.profile.summaries') {
        return { profiles: [{ name: 'vera', accent: '#f00' }, { name: 'abby', accent: '#0f0' }] };
      }
      if (method === 'host.outputs.list') {
        return { outputs: [{ id: `${params.profile}-1`, created_at: 5 }] };
      }
      return {};
    });
    const rows = await fetchConnectionOutputs(conn, 'unread', rpc);
    expect(rows).toHaveLength(2);
    expect(rows[0]).toMatchObject({
      profile: 'vera',
      accent: '#f00',
      connectionId: 'c1',
      connectionName: 'home',
    });
    // status threads through to host.outputs.list
    const listCall = rpc.mock.calls.find((c) => c[1] === 'host.outputs.list');
    expect(listCall[2]).toMatchObject({ profile: 'vera', status: 'unread' });
  });

  it('falls back to the default profile when summaries is empty', async () => {
    const rpc = vi.fn(async (_c, method) => {
      if (method === 'host.profile.summaries') return { profiles: [] };
      return { outputs: [{ id: 'd1', created_at: 1 }] };
    });
    const rows = await fetchConnectionOutputs(conn, undefined, rpc);
    expect(rows).toHaveLength(1);
    expect(rows[0].profile).toBe('default');
  });

  it('returns [] when the daemon is unreachable (summaries throws)', async () => {
    const rpc = vi.fn(async () => { throw new Error('timeout'); });
    expect(await fetchConnectionOutputs(conn, undefined, rpc)).toEqual([]);
  });

  it('skips a profile whose outputs.list fails but keeps the rest', async () => {
    const rpc = vi.fn(async (_c, method, params) => {
      if (method === 'host.profile.summaries') {
        return { profiles: [{ name: 'ok' }, { name: 'bad' }] };
      }
      if (params.profile === 'bad') throw new Error('boom');
      return { outputs: [{ id: 'ok-1', created_at: 2 }] };
    });
    const rows = await fetchConnectionOutputs(conn, undefined, rpc);
    expect(rows.map((r) => r.profile)).toEqual(['ok']);
  });

  it('returns [] for a connection without ip/port', async () => {
    const rpc = vi.fn();
    expect(await fetchConnectionOutputs({ id: 'x' }, undefined, rpc)).toEqual([]);
    expect(rpc).not.toHaveBeenCalled();
  });
});

describe('markAllUnifiedRead', () => {
  it('marks each unique (connection, profile) pair once and sums counts', async () => {
    const connections = [conn, { id: 'c2', name: 'work', ip: '100.0.0.2', port: 8838, token: 't2' }];
    const rows = [
      { connectionId: 'c1', profile: 'vera' },
      { connectionId: 'c1', profile: 'vera' },
      { connectionId: 'c1', profile: 'abby' },
      { connectionId: 'c2', profile: 'default' },
    ];
    const rpc = vi.fn(async () => ({ count: 2 }));
    const total = await markAllUnifiedRead(rows, connections, rpc);
    expect(rpc).toHaveBeenCalledTimes(3);
    expect(total).toBe(6);
    const profilesMarked = rpc.mock.calls.map((c) => `${c[0].id}:${c[2].profile}`).sort();
    expect(profilesMarked).toEqual(['c1:abby', 'c1:vera', 'c2:default']);
  });

  it('skips rows whose connection is no longer known', async () => {
    const rpc = vi.fn(async () => ({ count: 1 }));
    const total = await markAllUnifiedRead([{ connectionId: 'gone', profile: 'x' }], [conn], rpc);
    expect(rpc).not.toHaveBeenCalled();
    expect(total).toBe(0);
  });
});

describe('connectionsSignature', () => {
  it('changes when a connection is renamed (same id/ip/port)', () => {
    const a = [{ id: 'c1', name: 'home', ip: '1.1.1.1', port: 80 }];
    const b = [{ id: 'c1', name: 'casa', ip: '1.1.1.1', port: 80 }];
    expect(connectionsSignature(a)).not.toBe(connectionsSignature(b));
  });

  it('changes when a connection probe status flips', () => {
    const conns = [{ id: 'c1', name: 'home', ip: '1.1.1.1', port: 80 }];
    const online = new Map([['c1', 'online']]);
    const offline = new Map([['c1', 'offline']]);
    expect(connectionsSignature(conns, online)).not.toBe(connectionsSignature(conns, offline));
  });

  it('is stable for the same connections + status', () => {
    const conns = [{ id: 'c1', name: 'home', ip: '1.1.1.1', port: 80 }];
    const probe = new Map([['c1', 'online']]);
    expect(connectionsSignature(conns, probe)).toBe(connectionsSignature(conns, probe));
  });
});
