import { createElement, useState } from 'react';
import { act, renderHook, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('../lib/rpc', () => ({ call: vi.fn() }));
vi.mock('./useEvents', () => ({ useEventEffect: () => {} }));

import { EndpointContext } from '../lib/EndpointContext';
import { call as rpcCall } from '../lib/rpc';
import { adminConnectionsOf, connectionsSignature, fetchConnectionOutputs, isMemberOnly, markAllUnifiedRead, mergeOutputs, outputsEmptyState, outputsSubtitle, useUnifiedOutputs } from './useUnifiedOutputs';

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
  it('reports ok when every profile list answers', async () => {
    const rpc = vi.fn(async (_c, method) => {
      if (method === 'host.profile.summaries') return { profiles: [{ name: 'vera' }] };
      return { outputs: [] };
    });
    expect(await fetchConnectionOutputs(conn, undefined, rpc)).toEqual({ rows: [], ok: true });
  });

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
    const { rows, ok } = await fetchConnectionOutputs(conn, 'unread', rpc);
    expect(ok).toBe(true);
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
    const { rows } = await fetchConnectionOutputs(conn, undefined, rpc);
    expect(rows).toHaveLength(1);
    expect(rows[0].profile).toBe('default');
  });

  it('reports ok=false when the daemon is unreachable (summaries throws)', async () => {
    const rpc = vi.fn(async () => { throw new Error('timeout'); });
    expect(await fetchConnectionOutputs(conn, undefined, rpc)).toEqual({ rows: [], ok: false });
  });

  it('skips a profile whose outputs.list fails but keeps the rest', async () => {
    const rpc = vi.fn(async (_c, method, params) => {
      if (method === 'host.profile.summaries') {
        return { profiles: [{ name: 'ok' }, { name: 'bad' }] };
      }
      if (params.profile === 'bad') throw new Error('boom');
      return { outputs: [{ id: 'ok-1', created_at: 2 }] };
    });
    const { rows, ok } = await fetchConnectionOutputs(conn, undefined, rpc);
    expect(rows.map((r) => r.profile)).toEqual(['ok']);
    expect(ok).toBe(false);
  });

  it('reports ok=false for a connection without ip/port', async () => {
    const rpc = vi.fn();
    expect(await fetchConnectionOutputs({ id: 'x' }, undefined, rpc)).toEqual({ rows: [], ok: false });
    expect(rpc).not.toHaveBeenCalled();
  });
});

describe('adminConnectionsOf', () => {
  const conns = [{ id: 'c1' }, { id: 'c2' }, { id: 'c3' }];

  it('keeps only admin-role connections', () => {
    const roles = new Map([['c1', 'admin'], ['c2', 'member'], ['c3', 'admin']]);
    expect(adminConnectionsOf(conns, roles).map((c) => c.id)).toEqual(['c1', 'c3']);
  });

  it('excludes unprobed (null) connections — strict admin, not "not member"', () => {
    const roles = new Map([['c1', 'admin']]);
    expect(adminConnectionsOf(conns, roles).map((c) => c.id)).toEqual(['c1']);
  });

  it('returns [] when roleState is empty or missing', () => {
    expect(adminConnectionsOf(conns, new Map())).toEqual([]);
    expect(adminConnectionsOf(conns, null)).toEqual([]);
    expect(adminConnectionsOf(undefined, new Map())).toEqual([]);
  });
});

describe('isMemberOnly', () => {
  const roles = (pairs) => new Map(pairs);

  it('true only when every connection is a KNOWN member', () => {
    const conns = [{ id: 'a' }, { id: 'b' }];
    expect(isMemberOnly({ id: 'a' }, conns, roles([['a', 'member'], ['b', 'member']]))).toBe(true);
  });

  it('false when any role is unknown (unprobed/offline) — not proof of member', () => {
    const conns = [{ id: 'a' }, { id: 'b' }];
    expect(isMemberOnly({ id: 'a' }, conns, roles([['a', 'member']]))).toBe(false);
  });

  it('false when any connection is admin, and false without an endpoint or connections', () => {
    const conns = [{ id: 'a' }, { id: 'b' }];
    expect(isMemberOnly({ id: 'a' }, conns, roles([['a', 'member'], ['b', 'admin']]))).toBe(false);
    expect(isMemberOnly(null, conns, roles([['a', 'member']]))).toBe(false);
    expect(isMemberOnly({ id: 'a' }, [], new Map())).toBe(false);
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

  it('passing admin-only connections skips a member-connection row', async () => {
    const rows = [
      { connectionId: 'c1', profile: 'vera' },
      { connectionId: 'c2', profile: 'secret' },
    ];
    const rpc = vi.fn(async () => ({ count: 1 }));
    const total = await markAllUnifiedRead(rows, [conn], rpc);
    expect(rpc).toHaveBeenCalledTimes(1);
    expect(rpc.mock.calls[0][0].id).toBe('c1');
    expect(total).toBe(1);
  });
});

describe('useUnifiedOutputs · unreachable', () => {
  const adminValue = (ids) => ({
    connections: ids.map((id) => ({ id, name: id, ip: '1.1.1.1', port: 80 })),
    probeState: new Map(),
    roleState: new Map(ids.map((id) => [id, 'admin'])),
  });

  const wrap = (value) => function Wrapper({ children }) {
    return createElement(EndpointContext.Provider, { value }, children);
  };

  beforeEach(() => {
    rpcCall.mockReset();
  });

  it('flags unreachable when the only admin daemon does not answer', async () => {
    rpcCall.mockImplementation(async () => { throw new Error('timeout'); });
    const { result } = renderHook(() => useUnifiedOutputs(), { wrapper: wrap(adminValue(['c1'])) });

    await waitFor(() => expect(result.current.unreachable).toBe(true));
    expect(result.current.rows).toEqual([]);
    expect(result.current.unreachableCount).toBe(1);
  });

  it('a reachable daemon with nothing to show is a plain empty inbox', async () => {
    rpcCall.mockImplementation(async (_c, method) => {
      if (method === 'host.profile.summaries') return { profiles: [{ name: 'p' }] };
      return { outputs: [] };
    });
    const { result } = renderHook(() => useUnifiedOutputs(), { wrapper: wrap(adminValue(['c1'])) });

    await waitFor(() => expect(rpcCall.mock.calls.some((c) => c[1] === 'host.outputs.list')).toBe(true));
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.rows).toEqual([]);
    expect(result.current.unreachable).toBe(false);
    expect(result.current.unreachableCount).toBe(0);
  });

  it('keeps the rows one daemon returned while flagging the one that failed', async () => {
    rpcCall.mockImplementation(async (c, method) => {
      if (c.id === 'c2') throw new Error('timeout');
      if (method === 'host.profile.summaries') return { profiles: [{ name: 'p' }] };
      return { outputs: [{ id: 'o1', created_at: 1 }] };
    });
    const { result } = renderHook(() => useUnifiedOutputs(), { wrapper: wrap(adminValue(['c1', 'c2'])) });

    await waitFor(() => expect(result.current.rows).toHaveLength(1));
    expect(result.current.unreachable).toBe(true);
    expect(result.current.unreachableCount).toBe(1);
  });

  it('resets unreachable when the last admin connection drops away', async () => {
    rpcCall.mockImplementation(async () => { throw new Error('timeout'); });
    const connections = [{ id: 'c1', name: 'home', ip: '1.1.1.1', port: 80 }];
    let setRoleState;
    function Provider({ children }) {
      const [roleState, setter] = useState(new Map([['c1', 'admin']]));
      setRoleState = setter;
      const value = { connections, probeState: new Map(), roleState };
      return createElement(EndpointContext.Provider, { value }, children);
    }
    const { result } = renderHook(() => useUnifiedOutputs(), { wrapper: Provider });

    await waitFor(() => expect(result.current.unreachable).toBe(true));
    await act(async () => { setRoleState(new Map([['c1', 'member']])); });

    expect(result.current.unreachable).toBe(false);
    expect(result.current.unreachableCount).toBe(0);
  });
});

describe('outputsEmptyState', () => {
  it('says the daemon could not be reached instead of claiming an empty inbox', () => {
    const state = outputsEmptyState({
      hasAdmin: true,
      paired: true,
      unreachable: true,
      unreachableCount: 1,
      connectionCount: 1,
    });
    expect(state.title).toBe('Daemon unreachable');
    expect(state.detail).toMatch(/could not reach/);
  });

  it('counts the daemons that did not answer when others did', () => {
    const state = outputsEmptyState({
      hasAdmin: true,
      paired: true,
      unreachable: true,
      unreachableCount: 1,
      connectionCount: 3,
    });
    expect(state.title).toBe('Some daemons did not answer');
    expect(state.detail).toMatch(/1 of 3 daemons/);
  });

  it('reads as empty when every daemon answered', () => {
    const state = outputsEmptyState({ hasAdmin: true, paired: true, unreachable: false });
    expect(state.title).toBe('Nothing here yet');
    expect(state.detail).toMatch(/Notifications land here/);
  });

  it('member and unpaired copy wins over the reachability copy', () => {
    expect(outputsEmptyState({ memberOnly: true, unreachable: true }).detail).toMatch(/paired as a member/);
    expect(outputsEmptyState({ hasAdmin: false, paired: false }).detail).toMatch(/Pair this phone/);
  });
});

describe('outputsSubtitle', () => {
  it('never reads INBOX ZERO while a daemon is unreachable', () => {
    expect(outputsSubtitle({
      unreachable: true, unreachableCount: 1, connectionCount: 1, unreadCount: 0, hasRows: false,
    })).toBe('UNREACHABLE');
    expect(outputsSubtitle({
      unreachable: true, unreachableCount: 1, connectionCount: 3, unreadCount: 0, hasRows: false,
    })).toBe('PARTIAL');
    expect(outputsSubtitle({
      unreachable: true, unreachableCount: 1, connectionCount: 3, unreadCount: 2, hasRows: true,
    })).toBe('2 UNREAD · PARTIAL');
  });

  it('reads INBOX ZERO only when the daemons answered and had nothing', () => {
    expect(outputsSubtitle({ unreachable: false, unreadCount: 0, hasRows: false })).toBe('INBOX ZERO');
    expect(outputsSubtitle({ unreachable: false, unreadCount: 2, hasRows: true })).toBe('2 UNREAD');
    expect(outputsSubtitle({ memberOnly: true, unreachable: true, unreadCount: 0, hasRows: false })).toBe('MEMBER');
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
