import { describe, it, expect, vi } from 'vitest';
import { renderHook, waitFor, act } from '@testing-library/react';

import { EndpointContext } from '../lib/EndpointContext';
import { EventsProvider } from './useEvents';
import { useMarkAllOutputsRead, useOutput, useOutputs } from './useOutputs';


function makeProvider({ call = vi.fn(), callStream = vi.fn(() => ({ cancel: () => {} })) } = {}) {
  const endpoint = { id: 'e1', name: 'home' };
  function Wrapper({ children }) {
    return (
      <EndpointContext.Provider value={{ endpoint, call, callStream }}>
        <EventsProvider>{children}</EventsProvider>
      </EndpointContext.Provider>
    );
  }
  return { Wrapper, call, callStream };
}


describe('useOutputs', () => {
  it('fans out one host.outputs.list call per profile and concatenates the rows newest-first', async () => {
    const rowsByProfile = {
      abby: [
        { id: 'a1', profile: 'abby', created_at: 100, body: 'a1', status: 'unread' },
        { id: 'a2', profile: 'abby', created_at: 300, body: 'a2', status: 'unread' },
      ],
      vera: [
        { id: 'v1', profile: 'vera', created_at: 200, body: 'v1', status: 'unread' },
      ],
    };
    const call = vi.fn(async (_method, params) => ({
      outputs: rowsByProfile[params.profile] ?? [],
    }));
    const { Wrapper } = makeProvider({ call });

    const { result } = renderHook(
      () => useOutputs({ profiles: ['abby', 'vera'], status: 'unread' }),
      { wrapper: Wrapper },
    );

    await waitFor(() => expect(result.current.rows).toHaveLength(3));
    expect(result.current.rows.map((r) => r.id)).toEqual(['a2', 'v1', 'a1']);
    expect(call).toHaveBeenCalledWith('host.outputs.list', {
      profile: 'abby', status: 'unread', limit: 100,
    });
    expect(call).toHaveBeenCalledWith('host.outputs.list', {
      profile: 'vera', status: 'unread', limit: 100,
    });
  });

  it('omits status when not provided so the daemon returns the full list', async () => {
    const call = vi.fn(async () => ({ outputs: [] }));
    const { Wrapper } = makeProvider({ call });
    renderHook(() => useOutputs({ profiles: ['abby'] }), { wrapper: Wrapper });
    await waitFor(() => expect(call).toHaveBeenCalled());
    expect(call.mock.calls[0][1]).toEqual({ profile: 'abby', limit: 100 });
  });

  it('refreshes on output.updated so cross-client mark_read propagates to this surface', async () => {
    let listCalls = 0;
    const call = vi.fn(async (method, params) => {
      if (method === 'host.outputs.list') {
        listCalls += 1;
        return { outputs: [{ id: 'a1', profile: params.profile, created_at: 1, status: 'unread' }] };
      }
      return null;
    });
    const provider = makeProvider({ call });
    const { Wrapper, callStream } = provider;

    let frameDispatcher = null;
    callStream.mockImplementation((_method, _params, { onFrame }) => {
      onFrame({ event: 'subscribed', next_seq: 0 });
      frameDispatcher = onFrame;
      return { cancel: () => {} };
    });

    renderHook(() => useOutputs({ profiles: ['abby'] }), { wrapper: Wrapper });
    await waitFor(() => expect(listCalls).toBe(1));

    act(() => {
      frameDispatcher({ event: 'output.updated', data: { profile: 'abby', id: 'a1', status: 'read' }, seq: 1, at: 1 });
    });
    await waitFor(() => expect(listCalls).toBe(2));
  });

  it('survives a per-profile RPC failure: rows from other profiles still surface', async () => {
    const call = vi.fn(async (_method, params) => {
      if (params.profile === 'broken') throw new Error('auth-failed');
      return { outputs: [{ id: 'v1', profile: params.profile, created_at: 1, body: params.profile, status: 'unread' }] };
    });
    const { Wrapper } = makeProvider({ call });
    const { result } = renderHook(
      () => useOutputs({ profiles: ['abby', 'broken', 'vera'] }),
      { wrapper: Wrapper },
    );
    await waitFor(() => expect(result.current.rows.length).toBe(2));
    expect(result.current.rows.map((r) => r.profile).sort()).toEqual(['abby', 'vera']);
    expect(result.current.unreachable).toBe(true);
  });

  it('flags unreachable when the daemon answers nothing, so no rows never reads as an empty inbox', async () => {
    const call = vi.fn(async () => { throw new Error('timeout'); });
    const { Wrapper } = makeProvider({ call });
    const { result } = renderHook(() => useOutputs({ profiles: ['abby'] }), { wrapper: Wrapper });

    await waitFor(() => expect(result.current.unreachable).toBe(true));
    expect(result.current.rows).toEqual([]);
  });

  it('leaves unreachable false when the daemon answers with an empty list', async () => {
    const call = vi.fn(async () => ({ outputs: [] }));
    const { Wrapper } = makeProvider({ call });
    const { result } = renderHook(() => useOutputs({ profiles: ['abby'] }), { wrapper: Wrapper });

    await waitFor(() => expect(call).toHaveBeenCalled());
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.rows).toEqual([]);
    expect(result.current.unreachable).toBe(false);
  });
});


describe('useOutput', () => {
  it('calls host.outputs.read with profile + id and exposes the row', async () => {
    const call = vi.fn(async (method, params) => {
      if (method === 'host.outputs.read') {
        return { output: { id: params.id, profile: params.profile, body: 'hi', status: 'unread' } };
      }
      throw new Error(`unexpected ${method}`);
    });
    const { Wrapper } = makeProvider({ call });

    const { result } = renderHook(() => useOutput('abby', 'abc123'), { wrapper: Wrapper });
    await waitFor(() => expect(result.current.row?.id).toBe('abc123'));
    expect(call).toHaveBeenCalledWith('host.outputs.read', { profile: 'abby', id: 'abc123' });
  });

  it('markRead calls host.outputs.mark_read and updates the local row', async () => {
    const call = vi.fn(async (method, params) => {
      if (method === 'host.outputs.read') {
        return { output: { id: params.id, profile: params.profile, body: 'hi', status: 'unread' } };
      }
      if (method === 'host.outputs.mark_read') {
        return { ok: true, output: { id: params.id, profile: params.profile, body: 'hi', status: 'read' } };
      }
      throw new Error(`unexpected ${method}`);
    });
    const { Wrapper } = makeProvider({ call });

    const { result } = renderHook(() => useOutput('abby', 'abc123'), { wrapper: Wrapper });
    await waitFor(() => expect(result.current.row?.status).toBe('unread'));
    await act(async () => {
      await result.current.markRead();
    });
    expect(result.current.row?.status).toBe('read');
    expect(call).toHaveBeenCalledWith('host.outputs.mark_read', { profile: 'abby', id: 'abc123' });
  });
});


describe('useMarkAllOutputsRead', () => {
  it('invokes host.outputs.mark_all_read for the profile passed at call time and returns the touched count', async () => {
    const call = vi.fn(async () => ({ ok: true, count: 4 }));
    const { Wrapper } = makeProvider({ call });

    const { result } = renderHook(() => useMarkAllOutputsRead(), { wrapper: Wrapper });
    const touched = await result.current('abby');
    expect(touched).toBe(4);
    expect(call).toHaveBeenCalledWith('host.outputs.mark_all_read', { profile: 'abby' });
  });

  it('fans out across multiple profiles when called repeatedly — guards against the closure-over-first-profile regression', async () => {
    const call = vi.fn(async (_method, params) => ({
      ok: true,
      count: params.profile === 'abby' ? 2 : 3,
    }));
    const { Wrapper } = makeProvider({ call });
    const { result } = renderHook(() => useMarkAllOutputsRead(), { wrapper: Wrapper });

    const a = await result.current('abby');
    const v = await result.current('vera');
    expect(a).toBe(2);
    expect(v).toBe(3);
    expect(call).toHaveBeenCalledWith('host.outputs.mark_all_read', { profile: 'abby' });
    expect(call).toHaveBeenCalledWith('host.outputs.mark_all_read', { profile: 'vera' });
  });
});
