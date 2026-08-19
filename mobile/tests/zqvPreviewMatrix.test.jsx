import React from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render, screen } from '@testing-library/react';

afterEach(cleanup);

const h = vi.hoisted(() => ({ profiles: [], workgroups: [] }));

vi.mock('../src/hooks/useEvents', () => ({ useEventEffect: () => {} }));
vi.mock('../src/hooks/useDaemonData', () => ({
  useProfileSummaries: () => ({ data: { profiles: h.profiles }, loading: false, error: null, refresh: vi.fn() }),
  useWorkgroups: () => ({ data: { workgroups: h.workgroups }, loading: false, error: null, refresh: vi.fn() }),
}));
vi.mock('../src/lib/EndpointContext', () => ({ useEndpoint: () => ({ endpoint: { id: 'c1' } }) }));
vi.mock('../src/lib/readState', () => ({
  useReadState: () => ({ checkProfile: () => false, checkWorkgroup: () => false }),
}));
vi.mock('../src/theme/accents', () => ({ accentForProfile: () => '#000000' }));

import { useInbox } from '../src/hooks/useInbox';
import { profileEmptyState } from '../src/lib/profileReady';

let seen;

function Probe() {
  seen = useInbox();
  return null;
}

const NOW = Math.floor(Date.now() / 1000);

// The expression HEAD shipped, transcribed from `git show HEAD:mobile/src/hooks/useInbox.js`.
function headProfilePreview(p) {
  const state = profileEmptyState(p);
  if (state === 'needs-provider') return 'needs a provider · tap to set up';
  if (state === 'needs-model') return 'pick a model · tap to set up';
  const latest = p.latest_session;
  if (!latest) return '';
  return latest.last_assistant || latest.last_user || latest.first_user || latest.title || '';
}

function headWorkgroupPreview(w) {
  return w.last_body || w.briefing || '';
}

const SESSIONS = [
  ['no session', undefined],
  ['empty session', {}],
  ['assistant reply', { last_assistant: 'shipped it' }],
  ['user only', { last_user: 'ping' }],
  ['legacy first_user', { first_user: 'topic' }],
  ['title only', { title: 'thread title' }],
  ['assistant beats user', { last_assistant: 'a', last_user: 'u', first_user: 'f', title: 't' }],
  ['padded reply', { last_assistant: '  shipped it \n' }],
  ['whitespace only', { last_assistant: '\n  \t ' }],
  ['empty strings', { last_assistant: '', last_user: '', first_user: '', title: '' }],
];

const CONFIGS = [
  ['ready', { model: 'anthropic/claude-opus-5', provider_keys: ['anthropic'] }],
  ['needs-model', { provider_keys: ['anthropic'] }],
  ['needs-provider', {}],
  ['needs-provider via flag', { has_any_provider: false }],
];

const PROFILE_FIXTURES = [];
for (const [cfgName, cfg] of CONFIGS) {
  for (const [sesName, session] of SESSIONS) {
    for (const paused of [false, true]) {
      PROFILE_FIXTURES.push({
        label: `${cfgName} / ${sesName} / ${paused ? 'paused' : 'live'}`,
        profile: {
          name: 'p',
          ...cfg,
          paused,
          ...(session ? { latest_session: { updated_at: NOW - 60, ...session } } : {}),
        },
      });
    }
  }
}

const WG_FIXTURES = [];
for (const [bodyName, last_body] of [['no body', undefined], ['body', 'done'], ['blank body', '   '], ['empty body', '']]) {
  for (const [briefName, briefing] of [['no briefing', undefined], ['briefing', 'audit the fleet'], ['blank briefing', '\n'], ['empty briefing', '']]) {
    for (const paused of [false, true]) {
      WG_FIXTURES.push({
        label: `${bodyName} / ${briefName} / ${paused ? 'paused' : 'live'}`,
        workgroup: { id: 'w', name: 'alpha', profile: 'doc', mtime: NOW - 60, last_body, briefing, paused },
      });
    }
  }
}

function previewFor(profile, workgroup) {
  h.profiles = profile ? [profile] : [];
  h.workgroups = workgroup ? [workgroup] : [];
  const view = render(<Probe />);
  const value = seen.items[0]?.preview;
  view.unmount();
  return value;
}

beforeEach(() => {
  h.profiles = [];
  h.workgroups = [];
});

describe('no state that already said something loses its message', () => {
  it.each(PROFILE_FIXTURES.map((f) => [f.label, f]))('profile: %s', (_label, f) => {
    const before = headProfilePreview(f.profile).trim();
    const after = previewFor(f.profile, null);
    expect(after.length, 'every row says something').toBeGreaterThan(0);
    if (before) expect(after, 'pre-fix message preserved').toBe(before);
  });

  it.each(WG_FIXTURES.map((f) => [f.label, f]))('workgroup: %s', (_label, f) => {
    const before = headWorkgroupPreview(f.workgroup).trim();
    const after = previewFor(null, f.workgroup);
    expect(after.length, 'every row says something').toBeGreaterThan(0);
    if (before) expect(after, 'pre-fix message preserved').toBe(before);
  });
});

describe('precedence of the new invitation', () => {
  it.each([
    ['needs-provider outranks paused and history', { name: 'p', paused: true, latest_session: { updated_at: NOW, last_assistant: 'hi' } }, 'needs a provider · tap to set up'],
    ['needs-model outranks paused and history', { name: 'p', provider_keys: ['anthropic'], paused: true, latest_session: { updated_at: NOW, last_assistant: 'hi' } }, 'pick a model · tap to set up'],
    ['history outranks paused', { name: 'p', model: 'm', paused: true, latest_session: { updated_at: NOW, last_assistant: 'hi' } }, 'hi'],
    ['paused outranks the invitation', { name: 'p', model: 'm', paused: true }, 'paused · resume to chat'],
    ['ready and empty invites', { name: 'p', model: 'm' }, 'tap to start a thread'],
  ])('%s', (_n, profile, expected) => {
    expect(previewFor(profile, null)).toBe(expected);
  });

  it.each([
    ['last post outranks briefing and paused', { id: 'w', profile: 'd', mtime: NOW, last_body: 'done', briefing: 'b', paused: true }, 'done'],
    ['briefing outranks paused', { id: 'w', profile: 'd', mtime: NOW, briefing: 'audit the fleet', paused: true }, 'audit the fleet'],
    ['paused outranks the invitation', { id: 'w', profile: 'd', mtime: NOW, paused: true }, 'paused · resume to post'],
    ['live and empty invites', { id: 'w', profile: 'd', mtime: NOW }, 'tap to open a #task'],
  ])('workgroup: %s', (_n, workgroup, expected) => {
    expect(previewFor(null, workgroup)).toBe(expected);
  });

  it('never dresses an invitation as a blocked row', () => {
    for (const f of PROFILE_FIXTURES) {
      h.profiles = [f.profile];
      h.workgroups = [];
      const view = render(<Probe />);
      const item = seen.items[0];
      const invitation = item.preview === 'tap to start a thread' || item.preview === 'paused · resume to chat';
      if (invitation) expect(item.needsProvider, f.label).toBe(false);
      view.unmount();
    }
  });

  it('gives a sessionless ready profile copy but no timestamp', () => {
    h.profiles = [{ name: 'p', model: 'm' }];
    render(<Probe />);
    expect(seen.items[0].preview).toBe('tap to start a thread');
    expect(seen.items[0].ts).toBeNull();
    expect(seen.items[0].unread).toBe(false);
  });
});

describe('roster search now matches the invitation copy', () => {
  it('surfaces an empty profile when the query hits its invitation', async () => {
    const { matchesQuery } = await import('../src/lib/roster');
    h.profiles = [{ name: 'p', model: 'm' }];
    render(<Probe />);
    expect(matchesQuery(seen.items[0], 'thread')).toBe(true);
    expect(matchesQuery(seen.items[0], 'zzz')).toBe(false);
  });
});
