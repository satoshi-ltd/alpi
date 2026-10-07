import React from 'react';
import { act, cleanup, render } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const h = vi.hoisted(() => ({ call: vi.fn(), listeners: new Set(), focus: null }));

vi.mock('expo-router', () => ({ useFocusEffect: (fn) => { React.useEffect(() => { h.focus = fn; return fn(); }, [fn]); } }));
vi.mock('../lib/EndpointContext', () => ({ useEndpoint: () => ({ call: h.call, endpoint: { id: 'e1' } }) }));
vi.mock('./useEvents', () => ({
  useEventEffect: (kinds, fn) => {
    React.useEffect(() => {
      const listener = (ev) => { if (kinds.includes(ev.event)) fn(ev); };
      h.listeners.add(listener);
      return () => h.listeners.delete(listener);
    });
  },
}));

import { _resetDaemonDataCache } from './useDaemonData';
import { useAttention } from './useAttention';

let seen;
function Probe({ profile = 'abby' }) {
  seen = useAttention(profile);
  return null;
}
const emit = (event, data = { profile: 'abby' }) => act(async () => { for (const l of h.listeners) l({ event, data }); });
const attCalls = () => h.call.mock.calls.filter(([m]) => m === 'host.profile.attention').length;
const flushed = () => act(async () => { await new Promise((r) => setTimeout(r, 0)); });

beforeEach(() => {
  _resetDaemonDataCache();
  h.call.mockReset();
  h.listeners.clear();
  seen = null;
});
afterEach(cleanup);

describe('useAttention', () => {
  it('fetches host.profile.attention for the profile', async () => {
    h.call.mockResolvedValue({ memory: [], skills: [], schedules: [], counts: {}, total: 0 });
    render(<Probe />);
    await flushed();
    expect(h.call).toHaveBeenCalledWith('host.profile.attention', { profile: 'abby' });
    expect(seen.att.total).toBe(0);
  });

  it.each(['attention.changed', 'memory_changed', 'schedule.changed', 'schedule.failed', 'schedule.done'])('refetches on %s', async (kind) => {
    h.call.mockResolvedValue({ total: 0 });
    render(<Probe />);
    await flushed();
    const before = attCalls();
    await emit(kind);
    await flushed();
    expect(attCalls()).toBe(before + 1);
  });

  it('refetches when the screen regains focus, not on first focus', async () => {
    h.call.mockResolvedValue({ total: 0 });
    render(<Probe />);
    await flushed();
    const before = attCalls();
    await act(async () => { h.focus(); });
    await flushed();
    expect(attCalls()).toBe(before + 1);
  });

  it('treats a daemon without the verb as absent', async () => {
    h.call.mockRejectedValue(Object.assign(new Error('method-not-found'), { code: -32601 }));
    render(<Probe />);
    await flushed();
    expect(seen.att).toBeNull();
  });

  it('keeps the last flags when a refetch fails', async () => {
    h.call.mockResolvedValueOnce({ total: 2, skills: [{ name: 'a' }] });
    render(<Probe />);
    await flushed();
    expect(seen.att.total).toBe(2);
    h.call.mockRejectedValue(new Error('network down'));
    await emit('attention.changed');
    await flushed();
    expect(seen.att.total).toBe(2);
  });

  it('runs one trailing refetch for events that arrive during an in-flight fetch', async () => {
    let release;
    h.call.mockImplementation(() => new Promise((r) => { release = () => r({ total: 0 }); }));
    render(<Probe />);
    await flushed();
    const before = attCalls();
    await emit('attention.changed');
    await emit('schedule.done');
    release();
    await flushed();
    release();
    await flushed();
    expect(attCalls()).toBe(before + 1);
  });
});
