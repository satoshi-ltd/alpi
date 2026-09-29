import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { connectionMeta, deviceMeta, deviceTitle, pairingLink, relativeSeen, scopeLabel, sessionScopeLabel } from './format';

describe('relativeSeen', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date('2026-09-29T12:00:00Z'));
  });
  afterEach(() => vi.useRealTimers());

  it('buckets seconds into now, minutes, hours and days', () => {
    const now = Math.floor(Date.now() / 1000);
    expect(relativeSeen(null)).toBe('never');
    expect(relativeSeen(now - 5)).toBe('now');
    expect(relativeSeen(now - 5 * 60)).toBe('5m ago');
    expect(relativeSeen(now - 3 * 3600)).toBe('3h ago');
    expect(relativeSeen(now - 2 * 86400)).toBe('2d ago');
  });
});

describe('device rows', () => {
  it('names a device after itself, else its client', () => {
    expect(deviceTitle({ name: 'Pixel', client: 'mobile' })).toBe('Pixel');
    expect(deviceTitle({ client: 'desktop' })).toBe('desktop device');
    expect(deviceTitle({})).toBe('unknown device');
  });

  it('lists client, version, recency and the flags that matter', () => {
    const meta = deviceMeta({ client: 'web', app_version: '1.2', last_seen: null, provisioner: true, expired: true });
    expect(meta).toBe('web · 1.2 · never · provisioner · expired');
  });
});

describe('scopes', () => {
  it('reads an admin or an empty scope as every profile', () => {
    expect(scopeLabel({ role: 'admin', profile_scope: ['doc'] })).toBe('all profiles');
    expect(scopeLabel({ role: 'member', profile_scope: [] })).toBe('all profiles');
    expect(scopeLabel({ role: 'member', profile_scope: ['doc', 'abby'] })).toBe('doc, abby');
  });

  it('labels the session scope', () => {
    expect(sessionScopeLabel({ session_scope: 'device' })).toBe('per device');
    expect(sessionScopeLabel({})).toBe('per connection');
  });
});

describe('pairingLink', () => {
  const payload = {
    connection_id: 'conn_1',
    pairing_token: 'tok',
    label: 'Support',
    endpoints: [{ url: 'wss://a.example.com', label: 'public' }, { url: 'ws://10.0.0.2:49200', label: 'lan' }],
  };

  it('uses the first endpoint unless one is chosen', () => {
    const link = new URL(pairingLink(payload));
    expect(link.protocol).toBe('alpi:');
    expect(link.searchParams.get('url')).toBe('wss://a.example.com');
    expect(link.searchParams.get('pairing_token')).toBe('tok');
    expect(link.searchParams.get('connection_id')).toBe('conn_1');
    expect(link.searchParams.get('name')).toBe('Support');
    expect(new URL(pairingLink(payload, 'ws://10.0.0.2:49200')).searchParams.get('url')).toBe('ws://10.0.0.2:49200');
  });

  it('carries a device token when the payload has no grant', () => {
    const link = new URL(pairingLink({ url: 'ws://h:1', token: 'dev', label: 'x' }));
    expect(link.searchParams.get('token')).toBe('dev');
    expect(link.searchParams.get('pairing_token')).toBeNull();
  });

  it('is empty without an endpoint or credential', () => {
    expect(pairingLink({ pairing_token: 'tok' })).toBe('');
    expect(pairingLink({ url: 'ws://h:1' })).toBe('');
  });
});

describe('connectionMeta', () => {
  it('reads role · scope · devices · sessions · seen, singular where it counts one', () => {
    expect(connectionMeta({ role: 'member', profile_scope: ['doc'], devices: [{}], sessions: 1, last_seen: 0 })).toBe(
      'member · doc · 1 device · 1 session · seen never',
    );
    expect(connectionMeta({ role: 'admin', devices: [{}, {}], sessions: 0 })).toBe('admin · all profiles · 2 devices · 0 sessions · seen never');
  });
});
