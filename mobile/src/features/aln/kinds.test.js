import { describe, expect, it } from 'vitest';

import {
  deepLinkFor,
  formatNotification,
  NOTIFIABLE_KINDS,
} from './kinds';

describe('NOTIFIABLE_KINDS', () => {
  it('contains the curated set, excluding chatty plumbing', () => {
    expect(NOTIFIABLE_KINDS).toContain('agent.message');
    expect(NOTIFIABLE_KINDS).toContain('chat.turn_done');
    expect(NOTIFIABLE_KINDS).toContain('approval.request');
    expect(NOTIFIABLE_KINDS).toContain('schedule.failed');
    expect(NOTIFIABLE_KINDS).not.toContain('wg.post');
    expect(NOTIFIABLE_KINDS).not.toContain('config_changed');
    expect(NOTIFIABLE_KINDS).not.toContain('approval.resolved');
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

  it('schedule.done prefers reply over message (reply is clean agent output)', () => {
    const ev = {
      event: 'schedule.done',
      data: {
        profile: 'vera',
        message: 'Job ran',
        reply: 'Inbox cleaned, 3 priorities flagged.',
      },
    };
    const { body } = formatNotification(ev, conn);
    expect(body).toBe('Inbox cleaned, 3 priorities flagged.');
  });

  it('schedule.done falls back to message when no reply', () => {
    const ev = {
      event: 'schedule.done',
      data: { profile: 'vera', message: 'briefing delivered' },
    };
    const { body } = formatNotification(ev, conn);
    expect(body).toBe('briefing delivered');
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

  it('routes chat.turn_done to the profile chat', () => {
    expect(deepLinkFor({ event: 'chat.turn_done', data: { profile: 'abby', session_id: 'sess-9' } })).toBe('/chat/abby');
    expect(deepLinkFor({ event: 'chat.turn_done', data: {} })).toBe('/');
  });

  it('routes agent.message via explicit deep_link when present', () => {
    expect(deepLinkFor({
      event: 'agent.message',
      data: { deep_link: '/profile/abby', session_id: 'sess-1' },
    })).toBe('/profile/abby');
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
