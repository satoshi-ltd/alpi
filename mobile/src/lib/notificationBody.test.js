import { describe, expect, it } from 'vitest';

import { inlineSegments, parseNotificationBody } from './notificationBody';

describe('parseNotificationBody labels and paragraphs', () => {
  it('treats a whole-line bold phrase as a standalone label', () => {
    expect(parseNotificationBody('**Verdict**')).toEqual([{ kind: 'label', label: 'Verdict' }]);
    expect(parseNotificationBody('**Verdict:**')).toEqual([{ kind: 'label', label: 'Verdict' }]);
  });

  it('splits inline label bodies with the colon inside or outside the bold span', () => {
    expect(parseNotificationBody('**Verdict:** Normal day.')).toEqual([
      { kind: 'labelBody', label: 'Verdict', body: 'Normal day.' },
    ]);
    expect(parseNotificationBody('**Verdict**: Normal day.')).toEqual([
      { kind: 'labelBody', label: 'Verdict', body: 'Normal day.' },
    ]);
  });

  it('leaves long bold lead-ins as paragraphs', () => {
    const long = '**This lead-in is definitely far too long to be a label:** rest';
    expect(parseNotificationBody(long)).toEqual([{ kind: 'p', text: long }]);
    expect(parseNotificationBody('**one two three four five six:** rest')).toEqual([
      { kind: 'p', text: '**one two three four five six:** rest' },
    ]);
  });

  it('drops blank lines and empty input', () => {
    expect(parseNotificationBody('a\n\nb')).toEqual([
      { kind: 'p', text: 'a' },
      { kind: 'p', text: 'b' },
    ]);
    expect(parseNotificationBody('')).toEqual([]);
    expect(parseNotificationBody(null)).toEqual([]);
  });
});

describe('parseNotificationBody structure', () => {
  it('maps shallow headings to headings and deep headings to labels', () => {
    expect(parseNotificationBody('# Top')).toEqual([{ kind: 'heading', text: 'Top' }]);
    expect(parseNotificationBody('## Operations')).toEqual([{ kind: 'heading', text: 'Operations' }]);
    expect(parseNotificationBody('### Status')).toEqual([{ kind: 'label', label: 'Status' }]);
  });

  it('groups unordered, ordered, and status-marker lists', () => {
    expect(parseNotificationBody('- a\n• b\n* c')).toEqual([
      {
        kind: 'list',
        ordered: false,
        items: [
          { marker: '•', text: 'a' },
          { marker: '•', text: 'b' },
          { marker: '•', text: 'c' },
        ],
      },
    ]);
    expect(parseNotificationBody('1. a\n2. b')).toEqual([
      {
        kind: 'list',
        ordered: true,
        items: [
          { marker: '1.', text: 'a' },
          { marker: '2.', text: 'b' },
        ],
      },
    ]);
    expect(parseNotificationBody('🔴 down\n🟢 recovered')).toEqual([
      {
        kind: 'list',
        ordered: false,
        items: [
          { marker: '🔴', text: 'down' },
          { marker: '🟢', text: 'recovered' },
        ],
      },
    ]);
  });

  it('parses quote, code, and GFM table blocks', () => {
    expect(parseNotificationBody('> first\n> second')).toEqual([{ kind: 'quote', text: 'first second' }]);
    expect(parseNotificationBody('```\nline 1\n  line 2\n```')).toEqual([
      { kind: 'code', text: 'line 1\n  line 2' },
    ]);
    expect(parseNotificationBody('| Channel | Volume |\n| --- | --- |\n| Jaime | 94 |')).toEqual([
      {
        kind: 'table',
        headers: ['Channel', 'Volume'],
        rows: [['Jaime', '94']],
      },
    ]);
  });
});

describe('inlineSegments', () => {
  it('extracts code, bold, and italic segments', () => {
    expect(inlineSegments('a **b** *i* `c` d')).toEqual([
      { t: 'text', v: 'a ' },
      { t: 'bold', v: 'b' },
      { t: 'text', v: ' ' },
      { t: 'italic', v: 'i' },
      { t: 'text', v: ' ' },
      { t: 'code', v: 'c' },
      { t: 'text', v: ' d' },
    ]);
  });

  it('does not mistake bold syntax for italic syntax', () => {
    expect(inlineSegments('**bold**')).toEqual([{ t: 'bold', v: 'bold' }]);
  });
});
