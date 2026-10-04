import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render } from '@testing-library/react';

import { BRAND_INK, FOLD_IDS, foldFacets, foldTones } from '../../../common/folds.mjs';

const h = vi.hoisted(() => ({ mode: 'light', reduce: false, delays: [], timings: [], loops: [], started: 0, stopped: 0 }));

afterEach(() => {
  cleanup();
  h.reduce = false;
  Object.assign(h, { delays: [], timings: [], loops: [], started: 0, stopped: 0 });
});

vi.mock('react-native', () => {
  const View = ({ children }) => React.createElement('div', {}, children);
  const Animated = {
    Value: class {
      constructor(value) {
        this.value = value;
      }
      setValue(next) {
        this.value = next;
      }
    },
    timing: (value, config) => {
      h.timings.push({ value, ...config });
      return {};
    },
    delay: (ms) => {
      h.delays.push(ms);
      return {};
    },
    sequence: () => ({ start: () => { h.started += 1; }, stop: () => { h.stopped += 1; } }),
    loop: () => {
      h.loops.push(true);
      return { start: () => { h.started += 1; }, stop: () => { h.stopped += 1; } };
    },
    View,
  };
  return { Animated, Easing: { inOut: (fn) => fn, ease: 'ease' }, View };
});

vi.mock('../lib/reduceMotion', () => ({ useReduceMotion: () => h.reduce }));

vi.mock('../theme/ThemeContext', () => ({
  useTheme: () => ({ colors: { ink3: '#828b97', ink4: '#b4b4b4' }, mode: h.mode }),
}));

const { Fold } = await import('./Fold');

const draw = (props) => render(<Fold {...props} />).container;

describe('Fold', () => {
  it.each(FOLD_IDS.filter((id) => id !== 'diamond'))('draws %s as its own polygons in the profile colour', (fold) => {
    const root = draw({ fold, color: '#3899e2' });
    const polygons = root.querySelectorAll('polygon');
    expect(polygons).toHaveLength(foldFacets(fold).length);
    expect([...polygons].some((p) => p.getAttribute('fill') === '#3899e2')).toBe(true);
  });

  it('draws the kite-base origami for the diamond or an unknown fold', () => {
    for (const fold of [undefined, null, '', 'diamond', 'pencil']) {
      expect(draw({ fold, color: '#3899e2' }).querySelectorAll('polygon').length, String(fold)).toBeGreaterThan(1);
      cleanup();
    }
  });

  it('outlines a fold that needs a model', () => {
    const polygon = draw({ fold: 'heart', color: '#f36a8a', outlined: true }).querySelector('polygon');
    expect(polygon.getAttribute('fill-opacity')).toBe('0.22');
    expect(polygon.getAttribute('stroke')).toBe(polygon.getAttribute('fill'));
  });

  it('unfolds into the dashed crease pattern with no fill and no ripple when its daemon is away', () => {
    const root = draw({ fold: 'shield', color: '#3899e2', pulse: true, unfolded: true });
    expect(root.querySelector('[data-unfolded]')).toBeTruthy();
    for (const polygon of root.querySelectorAll('polygon')) {
      expect(polygon.getAttribute('fill')).toBe('none');
      expect(polygon.getAttribute('stroke')).toBe('#828b97');
      expect(polygon.getAttribute('stroke-dasharray') ?? polygon.getAttribute('strokeDasharray')).toBeTruthy();
    }
    expect(h.loops).toHaveLength(0);
  });

  it('draws in a neutral grey when the colour is not a hex', () => {
    const root = draw({ fold: 'tree', color: 'var(--accent)' });
    expect(root.querySelector('polygon')).not.toBeNull();
    expect(root.innerHTML).not.toContain('var(--accent)');
  });

  it('draws a shield at an explicit pixel size', () => {
    const svg = draw({ fold: 'shield', color: '#3899e2', size: 28 }).querySelector('svg');
    expect(svg.getAttribute('width')).toBe('28');
    expect(svg.getAttribute('height')).toBe('28');
  });

  it.each(['light', 'dark'])('paints the alpaca in the brand ink of the %s theme', (mode) => {
    h.mode = mode;
    const fills = [...draw({ fold: 'alpaca', color: '#123456', size: 72 }).querySelectorAll('polygon')].map((p) => p.getAttribute('fill'));
    expect(new Set(fills)).toEqual(new Set(foldTones(BRAND_INK[mode])));
    h.mode = 'light';
  });

  it('paints the alpaca in the brand ink when no colour is given', () => {
    const fills = [...draw({ fold: 'alpaca', size: 72 }).querySelectorAll('polygon')].map((p) => p.getAttribute('fill'));
    expect(fills.length).toBe(12);
    expect(fills).not.toContain('#828b97');
  });

  it('draws the alpaca larger than its slot in rows and headers, and as given at a pixel size', () => {
    expect(Number(draw({ fold: 'alpaca' }).querySelector('svg').getAttribute('width'))).toBeCloseTo(16 * 1.3);
    cleanup();
    expect(Number(draw({ fold: 'alpaca', size: 'md' }).querySelector('svg').getAttribute('width'))).toBeCloseTo(20 * 1.3);
    cleanup();
    expect(draw({ fold: 'alpaca', size: 72 }).querySelector('svg').getAttribute('width')).toBe('72');
    cleanup();
    expect(draw({ fold: 'shield' }).querySelector('svg').getAttribute('width')).toBe('16');
  });

  it('draws the alpaca as twelve facets in one flat ink', () => {
    const root = draw({ fold: 'alpaca', color: '#f0b447', size: 72 });
    expect(root.querySelectorAll('polygon')).toHaveLength(12);
    expect(new Set([...root.querySelectorAll('polygon')].map((p) => p.getAttribute('fill'))).size).toBe(1);
  });

  it('draws the diamond as its kite-base origami at a pixel size', () => {
    expect(draw({ fold: 'diamond', color: '#3899e2', size: 28 }).querySelectorAll('polygon').length).toBeGreaterThan(1);
  });

  it('draws the honeycomb as three cells in the colour it is given', () => {
    const polygons = draw({ fold: 'honeycomb', color: '#3899e2', size: 'md' }).querySelectorAll('polygon');
    expect(polygons).toHaveLength(3);
    expect(new Set([...polygons].map((p) => p.getAttribute('fill'))).size).toBe(3);
  });

  it('sizes the honeycomb at row and header sizes', () => {
    expect(draw({ fold: 'honeycomb', color: '#3899e2' }).querySelector('svg').getAttribute('width')).toBe('16');
    cleanup();
    expect(draw({ fold: 'honeycomb', color: '#3899e2', size: 'md' }).querySelector('svg').getAttribute('width')).toBe('20');
  });

  it('outlines a paused honeycomb', () => {
    const polygon = draw({ fold: 'honeycomb', color: '#3899e2', outlined: true }).querySelector('polygon');
    expect(polygon.getAttribute('fill-opacity')).toBe('0.22');
  });

  describe('working pulse', () => {
    it('ripples the honeycomb cell by cell, each delayed a third of the loop', () => {
      const root = draw({ fold: 'honeycomb', color: '#3899e2', pulse: true });
      expect(root.querySelectorAll('svg')).toHaveLength(3);
      expect(root.querySelectorAll('polygon')).toHaveLength(3);
      expect(h.delays).toEqual([0, 600, 1200]);
      expect(h.loops).toHaveLength(3);
      expect(h.timings.map((t) => t.duration)).toEqual([900, 900, 900, 900, 900, 900]);
      expect(h.started).toBe(3);
    });

    it('stops the ripple when the glyph unmounts', () => {
      const view = render(<Fold fold="honeycomb" color="#3899e2" pulse />);
      view.unmount();
      expect(h.stopped).toBe(3);
    });

    it('draws the honeycomb in one still svg when idle', () => {
      const root = draw({ fold: 'honeycomb', color: '#3899e2' });
      expect(root.querySelectorAll('svg')).toHaveLength(1);
      expect(h.delays).toEqual([]);
      expect(h.started).toBe(0);
    });

    it('does not ripple under reduced motion', () => {
      h.reduce = true;
      const root = draw({ fold: 'honeycomb', color: '#3899e2', pulse: true });
      expect(root.querySelectorAll('svg')).toHaveLength(1);
      expect(root.querySelectorAll('polygon')).toHaveLength(3);
      expect(h.started).toBe(0);
    });

    it('ripples a working profile fold facet by facet, like the honeycomb', () => {
      const root = draw({ fold: 'shield', color: '#3899e2', pulse: true });
      expect(root.querySelectorAll('svg').length).toBeGreaterThan(1);
      expect(h.delays.length).toBeGreaterThan(1);
    });

    it('does not pulse a profile fold under reduced motion', () => {
      h.reduce = true;
      draw({ fold: 'shield', color: '#3899e2', pulse: true });
      expect(h.started).toBe(0);
    });
  });
});
