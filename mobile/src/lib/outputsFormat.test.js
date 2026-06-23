import { describe, expect, it } from 'vitest';

import { openChatTarget, rowTitle, severityTag, stripPreviewMarkdown } from './outputsFormat';

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
