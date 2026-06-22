import { describe, expect, it } from 'vitest';

import { rowTitle, stripPreviewMarkdown } from './outputsFormat';

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
