import { describe, expect, it } from 'vitest';

import {
  deepLinkFor,
  formatNotification,
  NOTIFIABLE_KINDS,
} from './kinds';

describe('NOTIFIABLE_KINDS', () => {
  it('contains the curated set, excluding chatty plumbing', () => {
    expect(NOTIFIABLE_KINDS).toContain('agent.message');
    expect(NOTIFIABLE_KINDS).toContain('approval.request');
    expect(NOTIFIABLE_KINDS).toContain('schedule.failed');
    expect(NOTIFIABLE_KINDS).not.toContain('wg.post');
    expect(NOTIFIABLE_KINDS).not.toContain('config_changed');
    expect(NOTIFIABLE_KINDS).not.toContain('approval.resolved');
  });

  it('excludes chat.turn_done — every assistant turn fires this; for a foreground user it is redundant noise that pollutes the lock screen', () => {
    expect(NOTIFIABLE_KINDS).not.toContain('chat.turn_done');
  });

  it('excludes wg.mention from native notifications — peer mentions are intermediate activity, not interrupt-worthy', () => {
    expect(NOTIFIABLE_KINDS).not.toContain('wg.mention');
  });

  it('excludes schedule.done from native notifications — schedule success is not an interrupt; if a job wants to notify it calls send_message explicitly', () => {
    expect(NOTIFIABLE_KINDS).not.toContain('schedule.done');
  });
});

describe('formatNotification', () => {
  const conn = { id: 'c1', name: 'home' };

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

  it('renders agent.message with custom title + body', () => {
    const ev = {
      event: 'agent.message',
      data: {
        profile: 'abby',
        title: 'Meeting in 10 min',
        body: 'Standup with the design team at 10:30.',
        severity: 'important',
        kind: 'reminder',
      },
    };
    const { title, body } = formatNotification(ev, conn);
    expect(title).toBe('Meeting in 10 min');
    expect(body).toBe('Standup with the design team at 10:30.');
  });

  it('falls back to conn + profile + severity when agent.message has no title', () => {
    const ev = {
      event: 'agent.message',
      data: { profile: 'abby', body: 'hello', severity: 'urgent' },
    };
    const { title } = formatNotification(ev, conn);
    expect(title).toContain('home');
    expect(title).toContain('abby');
    expect(title).toContain('urgent');
  });

});

describe('deepLinkFor', () => {
  it('routes wg.done to the workgroup screen', () => {
    expect(deepLinkFor({ event: 'wg.done', data: { wg_id: 'wg-xyz' } })).toBe('/wg/wg-xyz');
  });

  it('routes schedule.failed via explicit deep_link to the failed output row', () => {
    expect(deepLinkFor({
      event: 'schedule.failed',
      data: { profile: 'vera', deep_link: '/outputs/vera/abc123', output_id: 'abc123' },
    })).toBe('/outputs/vera/abc123');
  });

  it('falls back to the profile schedule when schedule.failed has no deep_link (older daemons)', () => {
    expect(deepLinkFor({ event: 'schedule.failed', data: { profile: 'vera' } })).toBe('/profile/vera/schedule');
  });

  it('routes agent.message via explicit deep_link to the output row', () => {
    expect(deepLinkFor({
      event: 'agent.message',
      data: { deep_link: '/outputs/abby/abc123', output_id: 'abc123' },
    })).toBe('/outputs/abby/abc123');
  });

  it('routes agent.message to the profile chat when no explicit deep_link', () => {
    expect(deepLinkFor({
      event: 'agent.message',
      data: { profile: 'abby', session_id: 'sess-1' },
    })).toBe('/chat/abby');
    expect(deepLinkFor({ event: 'agent.message', data: {} })).toBe('/');
  });

  it('falls back to root for unknown kinds', () => {
    expect(deepLinkFor({ event: 'unknown', data: {} })).toBe('/');
  });
});
