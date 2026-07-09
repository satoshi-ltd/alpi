import { describe, expect, it } from 'vitest';
import { segmentBlocks, splitRow } from './markdownBlocks';

describe('segmentBlocks', () => {
  it('parses a GFM table into a table block', () => {
    const blocks = segmentBlocks('| Día | RHR |\n| --- | --- |\n| Lun | 50 |\n| Mar | 49 |');
    expect(blocks).toHaveLength(1);
    expect(blocks[0]).toEqual({
      type: 'table',
      header: ['Día', 'RHR'],
      rows: [['Lun', '50'], ['Mar', '49']],
    });
  });

  it('parses a fenced code block with its language', () => {
    const blocks = segmentBlocks("```python\nprint('hi')\nx = 1\n```");
    expect(blocks).toHaveLength(1);
    expect(blocks[0]).toEqual({ type: 'code', lang: 'python', code: "print('hi')\nx = 1" });
  });

  it('labels a bare fence as empty lang (renderer shows "text")', () => {
    const blocks = segmentBlocks('```\nplain\n```');
    expect(blocks[0]).toEqual({ type: 'code', lang: '', code: 'plain' });
  });

  it('does not treat pipe text without a separator row as a table', () => {
    const blocks = segmentBlocks('a | b but not a table');
    expect(blocks[0].type).toBe('p');
  });

  it('parses a standalone local image into an image block with note', () => {
    const blocks = segmentBlocks('![a room](/tmp/room.png "generated")');
    expect(blocks[0]).toEqual({ type: 'image', path: '/tmp/room.png', alt: 'a room', note: 'generated' });
  });

  it('ignores remote/relative images (stays a paragraph)', () => {
    expect(segmentBlocks('![x](https://e.test/a.png)')[0].type).toBe('p');
    expect(segmentBlocks('![x](room.png)')[0].type).toBe('p');
  });

  it('does not inline svg (logos are linked, not rendered)', () => {
    expect(segmentBlocks('![logo](/tmp/logo.svg)')[0].type).toBe('p');
  });

  it('still segments headings, lists and paragraphs', () => {
    const blocks = segmentBlocks('# Title\n\n- one\n- two\n\nbody');
    expect(blocks.map((b) => b.type)).toEqual(['heading', 'space', 'list', 'space', 'p']);
    expect(blocks[2].items).toEqual(['one', 'two']);
  });

  it('parses consecutive blockquote lines into one quote block', () => {
    expect(segmentBlocks('> Hola me llamo `javi`\n> encantado')[0]).toEqual({
      type: 'quote',
      text: 'Hola me llamo `javi` encantado',
    });
  });
});

describe('splitRow', () => {
  it('trims cells and drops the outer pipes', () => {
    expect(splitRow('|  a |  b  | c |')).toEqual(['a', 'b', 'c']);
  });
});
