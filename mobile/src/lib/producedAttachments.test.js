import { describe, expect, it } from 'vitest';

import { compactProducedTool, stripProducedImageMarkdown } from './producedAttachments';

const img = { kind: 'image', name: 'hero.jpg', path: '/p/out/hero.jpg' };

describe('stripProducedImageMarkdown', () => {
  it('strips the markdown image and the redundant Path line, keeps prose', () => {
    const text = 'Saved here:\n\n![h](/p/out/hero.jpg)\n\nPath: `/p/out/hero.jpg`';
    const out = stripProducedImageMarkdown(text, [img]);
    expect(out).not.toContain('![');
    expect(out).not.toContain('/p/out/hero.jpg');
    expect(out).toContain('Saved here:');
  });

  it('only strips standalone Path: lines — prose before an inline Path: survives', () => {
    const out = stripProducedImageMarkdown('Saved successfully. Path: /p/out/hero.jpg', [img]);
    expect(out).toContain('Saved successfully.');
  });
});

describe('compactProducedTool', () => {
  it('replaces a tool result that produced an attachment', () => {
    const t = { name: 'skill', output: '{"out": "/p/out/hero.jpg", "cost_usd": 0.04}' };
    expect(compactProducedTool(t, [img]).output).toBe('Generated · hero.jpg');
  });

  it('leaves unrelated tool results untouched', () => {
    expect(compactProducedTool({ output: 'plain' }, [img]).output).toBe('plain');
    expect(compactProducedTool({ output: 'x' }, []).output).toBe('x');
  });
});
