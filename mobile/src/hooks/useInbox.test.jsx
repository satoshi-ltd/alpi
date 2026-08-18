import React from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { act, cleanup, render } from '@testing-library/react';

afterEach(cleanup);

const h = vi.hoisted(() => ({
  profiles: [],
  workgroups: [],
  unread: new Set(),
  listeners: [],
  endpointId: 'c1',
}));

const DAEMON_WG_EVENTS = ['wg.post', 'wg.done', 'wg.mention', 'wg.blocked'];

vi.mock('./useEvents', () => ({
  useEventEffect: (kinds, fn) => {
    h.listeners.push({ kinds: Array.isArray(kinds) ? kinds : [kinds], fn });
  },
}));

function emit(event, data) {
  if (!DAEMON_WG_EVENTS.includes(event)) {
    throw new Error(
      `no alpi daemon code path emits ${event} — see alpi/alp/workgroup.py, alpi/alp/workgroup_client.py, alpi/alp/workgroup_files.py, alpi/service.py`,
    );
  }
  act(() => {
    for (const l of h.listeners) {
      if (l.kinds.includes(event)) l.fn({ event, data });
    }
  });
}

vi.mock('./useDaemonData', () => ({
  useProfileSummaries: () => ({ data: { profiles: h.profiles }, loading: false, error: null, refresh: vi.fn() }),
  useWorkgroups: () => ({ data: { workgroups: h.workgroups }, loading: false, error: null, refresh: vi.fn() }),
}));

vi.mock('../lib/EndpointContext', () => ({ useEndpoint: () => ({ endpoint: { id: h.endpointId } }) }));
vi.mock('../lib/readState', () => ({
  useReadState: () => ({
    checkProfile: (name) => h.unread.has(name),
    checkWorkgroup: (profile, id) => h.unread.has(id),
  }),
}));
vi.mock('../lib/profileReady', () => ({
  profileEmptyState: (p) => (p?.incomplete ? 'needs-provider' : 'ready'),
}));
vi.mock('../lib/profileLabel', () => ({ profileLabel: (name) => name }));
vi.mock('../theme/accents', () => ({ accentForProfile: () => '#000000' }));

import { useInbox } from './useInbox';

let seen;

function Probe() {
  seen = useInbox();
  return null;
}

const NOW = Math.floor(Date.now() / 1000);
const withSession = (name, ago) => ({ name, latest_session: { updated_at: NOW - ago } });
const fresh = (name) => ({ name });
const halfConfigured = (name, ago) => ({ ...withSession(name, ago), incomplete: true });
const wg = (id, ago) => ({ id, name: id, profile: 'doc', mtime: NOW - ago });
const ids = () => seen.items.map((i) => i.id);

beforeEach(() => {
  h.profiles = [];
  h.workgroups = [];
  h.unread = new Set();
  h.listeners = [];
  h.endpointId = 'c1';
  seen = null;
});

describe('useInbox roster membership', () => {
  it('lists a profile that has never held a session', () => {
    h.profiles = [fresh('brand-new')];
    render(<Probe />);
    expect(seen.items.map((i) => i.id)).toEqual(['brand-new']);
  });

  it('shows no timestamp for a profile with no session instead of a bogus one', () => {
    h.profiles = [fresh('brand-new')];
    render(<Probe />);
    expect(seen.items[0].ts).toBeNull();
    expect(seen.items[0].sortKey).toBe(0);
  });

  it('sorts a sessionless profile after every profile that has one', () => {
    h.profiles = [fresh('brand-new'), withSession('older', 7200), withSession('recent', 60)];
    render(<Probe />);
    expect(seen.items.map((i) => i.id)).toEqual(['recent', 'older', 'brand-new']);
  });

  it('keeps a paused profile last even when it is the most recent', () => {
    h.profiles = [{ ...withSession('paused-recent', 10), paused: true }, withSession('active', 3600)];
    render(<Probe />);
    expect(seen.items.map((i) => i.id)).toEqual(['active', 'paused-recent']);
  });

  it('lists a workgroup with no posts alongside the profiles', () => {
    h.profiles = [withSession('doc', 60)];
    h.workgroups = [{ id: 'wg1', name: 'alpha', profile: 'doc' }];
    render(<Probe />);
    expect(seen.items.map((i) => i.id)).toEqual(['doc', 'wg1']);
  });
});

describe('useInbox working state', () => {
  const stateOf = (id) => seen.items.find((i) => i.id === id)?.state;

  it('emits no state until the daemon says a workgroup is posting', () => {
    h.workgroups = [wg('wg1', 60)];
    render(<Probe />);
    expect(stateOf('wg1')).toBeUndefined();
  });

  it('marks a workgroup working while its posts arrive', () => {
    h.workgroups = [wg('wg1', 60), wg('wg2', 60)];
    render(<Probe />);
    emit('wg.post', { profile: 'doc', wg_id: 'wg1' });
    expect(stateOf('wg1')).toBe('working');
    expect(stateOf('wg2')).toBeUndefined();
  });

  it('reads a post from any profile — the roster keeps one row per workgroup', () => {
    h.workgroups = [wg('wg1', 60)];
    render(<Probe />);
    emit('wg.post', { profile: 'ghost', wg_id: 'wg1' });
    expect(stateOf('wg1')).toBe('working');
  });

  it('subscribes to no event name the daemon never emits — alpi publishes wg.post, wg.done, wg.mention and wg.blocked, nothing else', () => {
    h.workgroups = [wg('wg1', 60)];
    render(<Probe />);
    const subscribed = h.listeners.flatMap((l) => l.kinds);
    expect(subscribed.length).toBeGreaterThan(0);
    for (const kind of subscribed) expect(DAEMON_WG_EVENTS).toContain(kind);
  });

  it('takes a mention and a done marker as activity too', () => {
    h.workgroups = [wg('wg1', 60), wg('wg2', 60)];
    render(<Probe />);
    emit('wg.mention', { profile: 'doc', wg_id: 'wg1' });
    emit('wg.done', { profile: 'doc', wg_id: 'wg2' });
    expect(stateOf('wg1')).toBe('working');
    expect(stateOf('wg2')).toBe('working');
  });

  it('lights the pip on a mention — a member device never sees wg.post for a post made on the hub', () => {
    h.workgroups = [wg('wg1', 60)];
    render(<Probe />);
    emit('wg.mention', { profile: 'doc', wg_id: 'wg1' });
    expect(stateOf('wg1')).toBe('working');
  });

  it('leaves a blocked workgroup dark — wg.blocked reports a task stalled on repeated nudges, not work in progress', () => {
    h.workgroups = [wg('wg1', 60)];
    render(<Probe />);
    emit('wg.blocked', { profile: 'doc', wg_id: 'wg1', nudges: 3 });
    expect(stateOf('wg1')).toBeUndefined();
  });

  it('ignores an event with no workgroup to attach it to', () => {
    h.workgroups = [wg('wg1', 60)];
    render(<Probe />);
    emit('wg.post', { profile: 'doc' });
    expect(stateOf('wg1')).toBeUndefined();
  });

  it('never marks a profile working — no client signal exists for one', () => {
    h.profiles = [withSession('doc', 60)];
    h.workgroups = [wg('wg1', 60)];
    render(<Probe />);
    emit('wg.post', { profile: 'doc', wg_id: 'wg1' });
    expect(stateOf('doc')).toBeUndefined();
  });

  it('drops the state when the paired daemon changes', () => {
    h.workgroups = [wg('wg1', 60)];
    const { rerender } = render(<Probe />);
    emit('wg.post', { profile: 'doc', wg_id: 'wg1' });
    expect(stateOf('wg1')).toBe('working');
    h.endpointId = 'c2';
    act(() => {
      rerender(<Probe />);
    });
    expect(stateOf('wg1')).toBeUndefined();
  });

  it('lets the state expire instead of pinning a stale pip forever', () => {
    vi.useFakeTimers();
    try {
      h.workgroups = [wg('wg1', 60)];
      render(<Probe />);
      emit('wg.post', { profile: 'doc', wg_id: 'wg1' });
      expect(stateOf('wg1')).toBe('working');
      act(() => {
        vi.advanceTimersByTime(15000);
      });
      expect(stateOf('wg1')).toBeUndefined();
    } finally {
      vi.useRealTimers();
    }
  });
});

describe('useInbox order matches the desktop sidebar', () => {
  it('leaves an unread profile behind a more recent read one', () => {
    h.unread = new Set(['stale-unread']);
    h.profiles = [withSession('stale-unread', 7200), withSession('recent-read', 60)];
    render(<Probe />);
    expect(ids()).toEqual(['recent-read', 'stale-unread']);
    expect(seen.items[1].unread).toBe(true);
  });

  it('leaves an unread workgroup behind a more recent read one', () => {
    h.unread = new Set(['wg-stale']);
    h.workgroups = [wg('wg-stale', 7200), wg('wg-recent', 60)];
    render(<Probe />);
    expect(ids()).toEqual(['wg-recent', 'wg-stale']);
    expect(seen.items[1].unread).toBe(true);
  });

  it('ignores unread when ordering inside the paused group', () => {
    h.unread = new Set(['paused-unread']);
    h.profiles = [
      { ...withSession('paused-unread', 7200), paused: true },
      { ...withSession('paused-read', 60), paused: true },
    ];
    render(<Probe />);
    expect(ids()).toEqual(['paused-read', 'paused-unread']);
  });

  it('sorts a half-configured profile below every healthy one', () => {
    h.profiles = [halfConfigured('needs-provider', 60), withSession('healthy', 7200)];
    render(<Probe />);
    expect(ids()).toEqual(['healthy', 'needs-provider']);
  });

  it('sorts a half-configured profile below a healthy one that never held a session', () => {
    h.profiles = [halfConfigured('needs-provider', 60), fresh('brand-new')];
    render(<Probe />);
    expect(ids()).toEqual(['brand-new', 'needs-provider']);
  });

  it('never treats a workgroup as half-configured', () => {
    h.profiles = [halfConfigured('needs-provider', 60)];
    h.workgroups = [wg('wg-old', 7200)];
    render(<Probe />);
    expect(ids()).toEqual(['wg-old', 'needs-provider']);
  });

  it('orders the whole roster paused-last, half-configured next-to-last, then by recency', () => {
    h.unread = new Set(['half-recent', 'healthy-older']);
    h.profiles = [
      { ...withSession('paused-recent', 10), paused: true },
      halfConfigured('half-recent', 30),
      { ...fresh('half-never'), incomplete: true },
      fresh('healthy-never'),
      withSession('healthy-older', 7200),
      withSession('healthy-recent', 60),
    ];
    render(<Probe />);
    expect(ids()).toEqual([
      'healthy-recent',
      'healthy-older',
      'healthy-never',
      'half-recent',
      'half-never',
      'paused-recent',
    ]);
  });
});
