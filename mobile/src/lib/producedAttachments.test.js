import { describe, expect, it } from 'vitest';

import { compactProducedTool } from './producedAttachments';

const img = { kind: 'image', name: 'hero.jpg', path: '/p/out/hero.jpg' };

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
