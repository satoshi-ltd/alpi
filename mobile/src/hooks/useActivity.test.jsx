import React from 'react';
import { act, cleanup, render } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const h = vi.hoisted(() => ({
  call: vi.fn(),
  endpoint: { id: 'c1' },
  listeners: new Set(),
  appState: null,
}));

vi.mock('react-native', () => ({
  AppState: {
    addEventListener: (_name, fn) => {
      h.appState = fn;
      return { remove: () => { h.appState = null; } };
    },
  },
}));

vi.mock('../lib/EndpointContext', () => ({ useEndpoint: () => ({ endpoint: h.endpoint, call: h.call }) }));

vi.mock('./useEvents', () => ({
  useEventEffect: (kinds, fn) => {
    React.useEffect(() => {
      const listener = (ev) => { if (kinds.includes(ev.event)) fn(ev); };
      h.listeners.add(listener);
      return () => h.listeners.delete(listener);
    });
  },
}));

import {
  _resetActivityForTests,
  ACTIVITY_DEBOUNCE_MS,
  isMissingVerb,
  normalizeActivity,
  rowStateFor,
  rowStates,
  toEpochSeconds,
  useActivity,
} from './useActivity';

const NOW = 1_800_000_000;

const LIST = {
  needs_you: [{ kind: 'approval', request_id: 'r1', profile: 'builder', title: 'rm -rf dist', ts: NOW - 12, timeout_s: 60 }],
  running: [
    { kind: 'turn', profile: 'alpi', session_id: 's1', title: 'deploy summary', started_at: NOW - 42, source: 'chat' },
    { kind: 'workgroup', profile: 'alpi', workgroup_id: 'launch-crew', name: 'launch-crew', phase: 'analyze', phases_done: 2, phases_total: 4 },
  ],
  scheduled: [
    { profile: 'doc', job_id: 'j1', title: 'weekly labs', next_fire: null, last_run_at: NOW - 3600, last_run_status: 'error' },
    { profile: 'abby', job_id: 'j2', title: 'daily brief', next_fire: '2027-01-01T08:00:00Z', last_run_at: NOW - 3 * 86400, last_run_status: 'error' },
  ],
};

let seen = null;
function Probe() {
  seen = useActivity();
  return null;
}

function emit(event) {
  for (const fn of [...h.listeners]) fn({ event, data: {} });
}

beforeEach(() => {
  _resetActivityForTests();
  h.call.mockReset();
  h.listeners.clear();
  h.endpoint = { id: 'c1' };
  seen = null;
});

afterEach(() => {
  cleanup();
  vi.useRealTimers();
});

describe('row states', () => {
  it('ranks needs you over failed over working and keeps a workgroup phase count', () => {
    const states = rowStates(normalizeActivity({
      ...LIST,
      running: [...LIST.running, { kind: 'turn', profile: 'builder', session_id: 's2' }],
      scheduled: [...LIST.scheduled, { profile: 'builder', job_id: 'j3', last_run_status: 'error', last_run_at: NOW }],
    }), NOW);
    expect(rowStateFor(states, { kind: 'profile', id: 'builder' })).toEqual({ state: 'needs-you' });
    expect(rowStateFor(states, { kind: 'profile', id: 'doc' })).toEqual({ state: 'failed' });
    expect(rowStateFor(states, { kind: 'profile', id: 'alpi' })).toEqual({ state: 'working' });
    expect(rowStateFor(states, { kind: 'workgroup', id: 'launch-crew' })).toEqual({ state: 'working', phases: '2/4' });
    expect(rowStateFor(states, { kind: 'profile', id: 'abby' })).toBeNull();
  });

  it('reads a failed job that is running again as working, but not another failed job of the profile', () => {
    const failed = (job_id) => ({ profile: 'smith', job_id, last_run_status: 'error', last_run_at: NOW - 600 });
    const rerun = { kind: 'turn', source: 'schedule', profile: 'smith', job_id: 'audit', started_at: NOW - 60 };
    const state = (raw) => rowStateFor(rowStates(normalizeActivity(raw), NOW), { kind: 'profile', id: 'smith' });
    expect(state({ running: [rerun], scheduled: [failed('audit')] })).toEqual({ state: 'working' });
    expect(state({ running: [rerun], scheduled: [failed('audit'), failed('digest')] })).toEqual({ state: 'failed' });
    expect(state({ needs_you: [{ kind: 'approval', profile: 'smith' }], running: [rerun], scheduled: [failed('audit')] })).toEqual({ state: 'needs-you' });
    expect(state({ running: [{ ...rerun, profile: 'doc' }], scheduled: [failed('audit')] })).toEqual({ state: 'failed' });
    const { job_id: _, ...older } = rerun;
    expect(state({ running: [older], scheduled: [failed('audit')] })).toEqual({ state: 'failed' });
  });

  it('keeps a failure older than a day off the row', () => {
    const states = rowStates(normalizeActivity(LIST), NOW);
    expect(states.has('profile:abby')).toBe(false);
  });

  it('reads epoch seconds, epoch milliseconds and ISO stamps alike', () => {
    expect(toEpochSeconds(NOW)).toBe(NOW);
    expect(toEpochSeconds(NOW * 1000)).toBe(NOW);
    expect(toEpochSeconds('2027-01-15T08:00:00Z')).toBe(Date.parse('2027-01-15T08:00:00Z') / 1000);
    expect(toEpochSeconds(null)).toBeNull();
  });

  it('survives a malformed payload', () => {
    expect(normalizeActivity(null)).toEqual({ needsYou: [], running: [], scheduled: [] });
    expect(normalizeActivity({ needs_you: 'x', running: [null, 3] }).running).toEqual([]);
  });
});

describe('useActivity', () => {
  it('stays hidden until the first list lands, so an old daemon never flashes the entry', async () => {
    h.call.mockResolvedValue(LIST);
    render(<Probe />);
    expect(seen.supported).toBe(false);
    await act(async () => {});
    expect(seen.supported).toBe(true);
  });

  it('fetches on connect and exposes the needs-you count', async () => {
    h.call.mockResolvedValue(LIST);
    render(<Probe />);
    await act(async () => {});
    expect(h.call).toHaveBeenCalledWith('host.activity.list', {});
    expect(seen.supported).toBe(true);
    expect(seen.needsYouCount).toBe(1);
    expect(seen.activity.running).toHaveLength(2);
  });

  it('refetches once per burst of activity.changed, after the debounce', async () => {
    h.call.mockResolvedValue(LIST);
    render(<Probe />);
    await act(async () => {});
    vi.useFakeTimers();
    h.call.mockClear();
    act(() => { emit('activity.changed'); emit('activity.changed'); emit('session_changed'); emit('activity.changed'); });
    expect(h.call).not.toHaveBeenCalled();
    await act(async () => { vi.advanceTimersByTime(ACTIVITY_DEBOUNCE_MS); });
    expect(h.call).toHaveBeenCalledTimes(1);
  });

  it('refetches when the app returns to the foreground', async () => {
    h.call.mockResolvedValue(LIST);
    render(<Probe />);
    await act(async () => {});
    h.call.mockClear();
    await act(async () => { h.appState('active'); });
    expect(h.call).toHaveBeenCalledTimes(1);
  });

  it('hides itself on a daemon that predates the verb and stops asking on its own events', async () => {
    h.call.mockRejectedValue(Object.assign(new Error('unknown method: host.activity.list'), { code: -32601 }));
    render(<Probe />);
    await act(async () => {});
    expect(seen.supported).toBe(false);
    expect(seen.needsYouCount).toBe(0);
    vi.useFakeTimers();
    h.call.mockClear();
    act(() => { emit('activity.changed'); });
    await act(async () => { vi.advanceTimersByTime(ACTIVITY_DEBOUNCE_MS); });
    expect(h.call).not.toHaveBeenCalled();
  });

  it('stops asking a daemon that forbids the verb to a profile-scoped device', async () => {
    h.call.mockRejectedValue(new Error('forbidden'));
    render(<Probe />);
    await act(async () => {});
    expect(seen.unsupported).toBe(true);
    vi.useFakeTimers();
    h.call.mockClear();
    act(() => { emit('activity.changed'); });
    await act(async () => { vi.advanceTimersByTime(ACTIVITY_DEBOUNCE_MS); });
    expect(h.call).not.toHaveBeenCalled();
  });

  it('asks again when the user refreshes by hand after the daemon was upgraded', async () => {
    h.call.mockRejectedValueOnce(Object.assign(new Error('unknown method: host.activity.list'), { code: -32601 }));
    render(<Probe />);
    await act(async () => {});
    expect(seen.unsupported).toBe(true);
    h.call.mockResolvedValue(LIST);
    await act(async () => { await seen.refresh(); });
    expect(seen.supported).toBe(true);
  });

  it('comes back when the app returns to the foreground after the daemon was upgraded', async () => {
    h.call.mockRejectedValueOnce(Object.assign(new Error('unknown method: host.activity.list'), { code: -32601 }));
    render(<Probe />);
    await act(async () => {});
    expect(seen.unsupported).toBe(true);
    h.call.mockResolvedValue(LIST);
    await act(async () => { h.appState('active'); });
    expect(seen.unsupported).toBe(false);
    expect(seen.supported).toBe(true);
    expect(seen.needsYouCount).toBe(1);
  });

  it('comes back when the event stream reconnects after the daemon was upgraded', async () => {
    h.call.mockRejectedValueOnce(Object.assign(new Error('unknown method: host.activity.list'), { code: -32601 }));
    render(<Probe />);
    await act(async () => {});
    expect(seen.unsupported).toBe(true);
    h.call.mockResolvedValue(LIST);
    await act(async () => { emit('stream.connected'); });
    expect(seen.supported).toBe(true);
  });

  it('a reconnect of the stream asks nothing while Activity is already supported', async () => {
    h.call.mockResolvedValue(LIST);
    render(<Probe />);
    await act(async () => {});
    h.call.mockClear();
    await act(async () => { emit('stream.connected'); });
    expect(h.call).not.toHaveBeenCalled();
  });

  it('keeps asking nothing on activity.changed while the verb is still missing', async () => {
    h.call.mockRejectedValue(Object.assign(new Error('unknown method'), { code: -32601 }));
    render(<Probe />);
    await act(async () => {});
    vi.useFakeTimers();
    h.call.mockClear();
    act(() => { emit('activity.changed'); });
    await act(async () => { vi.advanceTimersByTime(ACTIVITY_DEBOUNCE_MS); });
    expect(h.call).not.toHaveBeenCalled();
  });

  it('keeps the last good list through a transient failure', async () => {
    h.call.mockResolvedValueOnce(LIST).mockRejectedValueOnce(new Error('timeout'));
    render(<Probe />);
    await act(async () => {});
    await act(async () => { await seen.refresh(); });
    expect(seen.supported).toBe(true);
    expect(seen.needsYouCount).toBe(1);
  });

  it('shares one request between every mounted consumer', async () => {
    h.call.mockResolvedValue(LIST);
    render(<><Probe /><Probe /><Probe /></>);
    await act(async () => {});
    expect(h.call).toHaveBeenCalledTimes(1);
  });
});

describe('isMissingVerb', () => {
  it.each([
    [{ code: -32601 }, true],
    [new Error('method-not-found'), true],
    [new Error('method_not_found: host.activity.list'), true],
    [new Error('Unknown method host.activity.list'), true],
    [new Error('forbidden'), true],
    [new Error('timeout'), false],
    [null, false],
  ])('%s → %s', (error, expected) => {
    expect(isMissingVerb(error)).toBe(expected);
  });
});
