import { describe, expect, it } from 'vitest';

import { openChatTarget, REPLY_QUOTE_MAX, replyDraft } from './outputsFormat';

describe('openChatTarget', () => {
  it('carries the originating connection and session so the right chat opens', () => {
    expect(openChatTarget({ profile: 'vera', session_id: 's-9' }, 'c-A')).toEqual({
      pathname: '/chat/[id]',
      params: { id: 'vera', sid: 's-9', connectionId: 'c-A' },
    });
  });

  it('omits connectionId when the notification has none', () => {
    expect(openChatTarget({ profile: 'vera', session_id: 's-9' })).toEqual({
      pathname: '/chat/[id]',
      params: { id: 'vera', sid: 's-9' },
    });
  });

  it('returns null when there is no session to open', () => {
    expect(openChatTarget({ profile: 'vera' }, 'c-A')).toBeNull();
    expect(openChatTarget(null, 'c-A')).toBeNull();
  });
});

describe('replyDraft', () => {
  it('quotes the title and the body, leaving a blank line to write under', () => {
    expect(replyDraft({ title: 'Daily mail digest', body: 'Line one\n\nLine two' }))
      .toBe('> **Daily mail digest**\n>\n> Line one\n>\n> Line two\n\n');
  });

  it('quotes the stored title as written, decorative emoji aside', () => {
    expect(replyDraft({ title: 'Fix snake_case keys ✅', body: 'x' })).toBe('> **Fix snake_case keys**\n>\n> x\n\n');
  });

  it('quotes a given summary ahead of the body, and only once when the body opens with it', () => {
    expect(replyDraft({ title: 'T', summary: 'Moved to 11.', body: '## Detail' })).toBe('> **T**\n>\n> Moved to 11.\n>\n> ## Detail\n\n');
    expect(replyDraft({ title: 'T', summary: 'Moved to 11.', body: 'Moved to 11.' })).toBe('> **T**\n>\n> Moved to 11.\n\n');
  });

  it('quotes the body alone when there is no title', () => {
    expect(replyDraft({ body: 'Only body' })).toBe('> Only body\n\n');
  });

  it('clips a long body so the composer stays usable', () => {
    const draft = replyDraft({ title: 'T', body: 'x'.repeat(REPLY_QUOTE_MAX * 3) });
    expect(draft.length).toBeLessThan(REPLY_QUOTE_MAX + 40);
    expect(draft.trimEnd().endsWith('…')).toBe(true);
  });

  it('is empty for nothing to quote', () => {
    expect(replyDraft(null)).toBe('');
    expect(replyDraft({ title: '', body: '' })).toBe('');
  });
});

describe('replyDraft clipping', () => {
  it('never cuts a character in half', () => {
    const body = `${'x'.repeat(REPLY_QUOTE_MAX - 2)}😀${'y'.repeat(50)}`;
    const draft = replyDraft({ title: '', body });
    expect(draft.isWellFormed()).toBe(true);
    expect(draft).toContain('😀…');
  });
});
