import { describe, expect, it } from 'vitest';

import { fmtRelative, openChatTarget, REPLY_QUOTE_MAX, replyDraft, rowTitle, severityTag, stripPreviewMarkdown } from './outputsFormat';

describe('rowTitle', () => {
  it('prefers the persisted title over body', () => {
    expect(rowTitle({ title: 'Build done', body: 'lots of stuff\n more' })).toBe('Build done');
  });

  it('strips markdown noise from the persisted title', () => {
    expect(rowTitle({ title: '**Alert** ~~stale~~', body: 'x' })).toBe('Alert stale');
  });

  it('falls back to the first meaningful body line when title is missing', () => {
    expect(rowTitle({ body: '\n# Heading\nrest' })).toBe('Heading');
  });

  it('falls back to em-dash when both title and body are empty', () => {
    expect(rowTitle({ title: '', body: '' })).toBe('—');
    expect(rowTitle({})).toBe('—');
  });

  it('ignores whitespace-only persisted title', () => {
    expect(rowTitle({ title: '   ', body: 'real content' })).toBe('real content');
  });
});

describe('severityTag', () => {
  it('labels warning and error from the real type contract', () => {
    expect(severityTag({ type: 'warning' })).toBe('WARNING');
    expect(severityTag({ type: 'error' })).toBe('ERROR');
  });

  it('returns null for info and missing type (no badge on routine notifications)', () => {
    expect(severityTag({ type: 'info' })).toBeNull();
    expect(severityTag({})).toBeNull();
    expect(severityTag(null)).toBeNull();
  });

  it('ignores the legacy kind/severity schema that never shipped on the daemon', () => {
    expect(severityTag({ kind: 'alert' })).toBeNull();
    expect(severityTag({ severity: 'urgent' })).toBeNull();
  });
});

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

describe('stripPreviewMarkdown', () => {
  it('handles null/undefined safely', () => {
    expect(stripPreviewMarkdown(null)).toBe('');
    expect(stripPreviewMarkdown(undefined)).toBe('');
  });

  it('strips code spans, emphasis, blockquotes, headings', () => {
    expect(stripPreviewMarkdown('`code` *em* > quote # title')).toBe('code em quote title');
  });

  it('preserves link text', () => {
    expect(stripPreviewMarkdown('see [docs](https://x)')).toBe('see docs');
  });
});

describe('replyDraft', () => {
  it('quotes the title and the body, leaving a blank line to write under', () => {
    expect(replyDraft({ title: 'Daily mail digest', body: 'Line one\n\nLine two' }))
      .toBe('> **Daily mail digest**\n>\n> Line one\n>\n> Line two\n\n');
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

describe('fmtRelative', () => {
  it('steps from now through minutes, hours, days and weeks', () => {
    const now = 1_000_000_000_000;
    const at = (s) => now / 1000 - s;
    expect(fmtRelative(at(10), now)).toBe('now');
    expect(fmtRelative(at(600), now)).toBe('10m');
    expect(fmtRelative(at(7200), now)).toBe('2h');
    expect(fmtRelative(at(86400 * 3), now)).toBe('3d');
    expect(fmtRelative(at(86400 * 14), now)).toBe('2w');
    expect(fmtRelative(0, now)).toBe('');
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
