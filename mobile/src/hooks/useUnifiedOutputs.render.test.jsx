import { useState } from 'react';
import { describe, expect, it, vi, beforeEach } from 'vitest';
import { renderHook, waitFor, act } from '@testing-library/react';

vi.mock('../lib/rpc', () => ({ call: vi.fn() }));
vi.mock('./useEvents', () => ({ useEventEffect: () => {} }));

import { call as rpcCall } from '../lib/rpc';
import { EndpointContext } from '../lib/EndpointContext';
import { useUnifiedOutputs } from './useUnifiedOutputs';

function wrap(value) {
  return function Wrapper({ children }) {
    return <EndpointContext.Provider value={value}>{children}</EndpointContext.Provider>;
  };
}

beforeEach(() => {
  rpcCall.mockReset();
});

describe('useUnifiedOutputs · admin-only fan-out', () => {
  it('fetches outputs from admin connections and never from members', async () => {
    rpcCall.mockImplementation(async (c, method) => {
      if (method === 'host.profile.summaries') return { profiles: [{ name: 'p' }] };
      if (method === 'host.outputs.list') return { outputs: [{ id: `${c.id}-o`, created_at: 1 }] };
      return {};
    });
    const value = {
      connections: [
        { id: 'c1', name: 'home', ip: '1.1.1.1', port: 80 },
        { id: 'c2', name: 'work', ip: '1.1.1.2', port: 80 },
      ],
      probeState: new Map(),
      roleState: new Map([['c1', 'admin'], ['c2', 'member']]),
    };
    const { result } = renderHook(() => useUnifiedOutputs(), { wrapper: wrap(value) });

    await waitFor(() => expect(result.current.rows.length).toBe(1));
    expect(result.current.rows[0].id).toBe('c1-o');
    expect(result.current.hasAdmin).toBe(true);
    const targets = rpcCall.mock.calls
      .filter((c) => c[1] === 'host.profile.summaries')
      .map((c) => c[0].id);
    expect(targets).toEqual(['c1']);
  });

  it('hasAdmin=false and no RPC when every connection is a member', async () => {
    const value = {
      connections: [{ id: 'c1', name: 'home', ip: '1.1.1.1', port: 80 }],
      probeState: new Map(),
      roleState: new Map([['c1', 'member']]),
    };
    const { result } = renderHook(() => useUnifiedOutputs(), { wrapper: wrap(value) });

    await waitFor(() => expect(result.current.hasAdmin).toBe(false));
    expect(result.current.rows).toEqual([]);
    expect(rpcCall).not.toHaveBeenCalled();
  });

  it('a fetch started while admin does not restore rows after demotion to member', async () => {
    let resolveList;
    rpcCall.mockImplementation(async (_c, method) => {
      if (method === 'host.profile.summaries') return { profiles: [{ name: 'p' }] };
      if (method === 'host.outputs.list') return new Promise((r) => { resolveList = r; });
      return {};
    });
    const connections = [{ id: 'c1', name: 'home', ip: '1.1.1.1', port: 80 }];
    let setRoleState;
    function Provider({ children }) {
      const [roleState, setter] = useState(new Map([['c1', 'admin']]));
      setRoleState = setter;
      const value = { connections, probeState: new Map(), roleState };
      return <EndpointContext.Provider value={value}>{children}</EndpointContext.Provider>;
    }
    const { result } = renderHook(() => useUnifiedOutputs(), { wrapper: Provider });

    await waitFor(() => expect(typeof resolveList).toBe('function'));
    await act(async () => { setRoleState(new Map([['c1', 'member']])); });

    await act(async () => {
      resolveList({ outputs: [{ id: 'stale', created_at: 1 }] });
      await new Promise((r) => setTimeout(r, 10));
    });

    expect(result.current.hasAdmin).toBe(false);
    expect(result.current.rows).toEqual([]);
    expect(result.current.loading).toBe(false);
  });
});
