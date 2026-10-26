import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render } from '@testing-library/react';

import { ICONS } from '../../../common/iconPaths.mjs';
import { iconSizes, iconStrokeFor } from '../theme/tokens';

afterEach(cleanup);

vi.mock('../theme/ThemeContext', () => ({
  useTheme: () => ({ colors: { ink2: '#333' } }),
}));

const { Icon } = await import('./Icon');

function draw(props) {
  return render(<Icon {...props} />).container.querySelector('svg');
}

describe('Icon defaults', () => {
  it('lands on the md step when no size is given', () => {
    const svg = draw({ name: 'search' });
    expect(svg.getAttribute('width')).toBe(String(iconSizes.md));
    expect(svg.getAttribute('height')).toBe(String(iconSizes.md));
  });

  it('draws on desktop lucide 24x24 grid', () => {
    expect(draw({ name: 'search' }).getAttribute('viewBox')).toBe('0 0 24 24');
  });
});

describe('Icon size scale', () => {
  it('offers only xs 12 and md 16', () => {
    expect(iconSizes).toEqual({ xs: 12, md: 16 });
  });

  it.each([[16], ['sm'], ['lg'], ['xl'], ['jumbo']])('draws an unknown size %s at the md step', (size) => {
    expect(draw({ name: 'check', size }).getAttribute('width')).toBe(String(iconSizes.md));
  });

  it.each(Object.entries(iconSizes))('resolves the %s step to %i', (step, px) => {
    expect(draw({ name: 'check', size: step }).getAttribute('width')).toBe(String(px));
  });

  it.each(['sm', 'lg', 'xl', 'hero', 20, 33, 'jumbo'])('folds %s onto md', (size) => {
    expect(draw({ name: 'check', size }).getAttribute('width')).toBe(String(iconSizes.md));
  });
});

describe('Icon stroke', () => {
  it.each(Object.values(iconSizes))('renders a constant 1.33 pt stroke at %i pt', (px) => {
    const step = px === iconSizes.xs ? 'xs' : 'md';
    for (const name of ['search', 'gear', 'plus', 'chevron-down']) {
      const sw = Number(draw({ name, size: step }).getAttribute('stroke-width'));
      expect(sw).toBeCloseTo(iconStrokeFor(px), 5);
      expect((sw * px) / 24).toBeCloseTo(1.33, 5);
      cleanup();
    }
  });

  it('ignores a stroke override', () => {
    const svg = draw({ name: 'check', size: 'md', strokeWidth: 3 });
    expect(Number(svg.getAttribute('stroke-width'))).toBeCloseTo(iconStrokeFor(16), 5);
  });

  it('allows no size other than xs and md in any source', async () => {
    const { readdirSync, readFileSync, statSync } = await import('node:fs');
    const { join } = await import('node:path');
    const root = join(import.meta.dirname, '../..');
    const hits = [];
    const walk = (dir) => {
      for (const name of readdirSync(dir)) {
        const path = join(dir, name);
        if (statSync(path).isDirectory()) walk(path);
        else if (/\.jsx$/.test(name) && !/\.test\./.test(name)) {
          const text = readFileSync(path, 'utf8');
          for (const m of text.matchAll(/<Icon\b[^>]*?\bsize=(\S+)/gs)) if (!/^"(xs|md)"$/.test(m[1])) hits.push(`${path}:${m[1]}`);
        }
      }
    };
    walk(join(root, 'src'));
    walk(join(root, 'app'));
    expect(hits).toEqual([]);
  });
});

describe('Icon geometry', () => {
  it('renders nothing for a name the map does not know', () => {
    expect(render(<Icon name="nope" />).container.querySelector('svg')).toBeNull();
  });

  it('honours a per-glyph stroke override, so the filled alpi mark stays filled', () => {
    const svg = draw({ name: 'alpi' });
    expect(svg.getAttribute('stroke')).toBe('none');
    expect(svg.getAttribute('fill')).toBe('#333');
  });

  it('routes the mobile nav aliases to chevrons, not desktop arrows', () => {
    expect(draw({ name: 'back' }).querySelector('path').getAttribute('d')).toBe(ICONS['chevron-left'][0][1].d);
    cleanup();
    expect(draw({ name: 'forward' }).querySelector('path').getAttribute('d')).toBe(ICONS['chevron-right'][0][1].d);
  });
});
