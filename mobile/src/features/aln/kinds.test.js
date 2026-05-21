import { describe, expect, it } from 'vitest';

import {
  deepLinkFor,
  formatNotification,
  NOTIFIABLE_KINDS,
} from './kinds';

describe('NOTIFIABLE_KINDS', () => {
  it('contains the curated set, excluding chatty plumbing', () => {
    expect(NOTIFIABLE_KINDS).toContain('wg.mention');
    expect(NOTIFIABLE_KINDS).toContain('chat.turn_done');
    expect(NOTIFIABLE_KINDS).toContain('approval.request');
    expect(NOTIFIABLE_KINDS).toContain('schedule.done');
    expect(NOTIFIABLE_KINDS).not.toContain('wg.post');
    expect(NOTIFIABLE_KINDS).not.toContain('config_changed');
    expect(NOTIFIABLE_KINDS).not.toContain('approval.resolved');
  });
});

describe('formatNotification', () => {
  const conn = { id: 'c1', name: 'home' };

  it('renders wg.mention with summary', () => {
    const ev = { event: 'wg.mention', data: { profile: 'vera', summary: '@vera look at this' } };
    const { title, body } = formatNotification(ev, conn);
    expect(title).toBe('home · vera · mention');
    expect(body).toBe('@vera look at this');
  });

  it('falls back to a generic title for unknown kinds', () => {
    const ev = { event: 'wild.unknown', data: {} };
    const { title } = formatNotification(ev, conn);
    expect(title).toBe('home');
  });

  it('uses the connection name when profile is absent', () => {
    const ev = { event: 'approval.request', data: { command: 'rm -rf /' } };
    const { title, body } = formatNotification(ev, conn);
    expect(title).toBe('home · approval needed');
    expect(body).toBe('rm -rf /');
  });

  it('renders chat.turn_done with tool and duration meta', () => {
    const ev = {
      event: 'chat.turn_done',
      data: {
        profile: 'vera',
        session_id: 'sess-1',
        summary: 'Research complete: top 5 vendors ranked.',
        tool_count: 12,
        duration_s: 187.3,
      },
    };
    const { title, body } = formatNotification(ev, conn);
    expect(title).toBe('home · vera · reply ready');
    expect(body).toContain('Research complete');
    expect(body).toContain('12 tools');
    expect(body).toContain('187s');
  });
});

describe('deepLinkFor', () => {
  it('routes wg events to the workgroup screen', () => {
    expect(deepLinkFor({ event: 'wg.mention', data: { wg_id: 'wg-abc' } })).toBe('/wg/wg-abc');
    expect(deepLinkFor({ event: 'wg.done', data: { wg_id: 'wg-xyz' } })).toBe('/wg/wg-xyz');
  });

  it('routes schedule events to the profile schedule', () => {
    expect(deepLinkFor({ event: 'schedule.done', data: { profile: 'vera' } })).toBe('/profile/vera/schedule');
  });

  it('routes chat.turn_done to the session', () => {
    expect(deepLinkFor({ event: 'chat.turn_done', data: { session_id: 'sess-9' } })).toBe('/chat/sess-9');
    expect(deepLinkFor({ event: 'chat.turn_done', data: {} })).toBe('/');
  });

  it('falls back to root for unknown kinds', () => {
    expect(deepLinkFor({ event: 'unknown', data: {} })).toBe('/');
  });
});
