import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render } from '@testing-library/react';

import { FOLD_SIZES, foldFacets } from '../../../common/folds.mjs';

afterEach(() => {
  cleanup();
  h.delays.length = 0;
});

const h = vi.hoisted(() => ({ delays: [] }));

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
    timing: () => ({}),
    delay: (ms) => {
      h.delays.push(ms);
      return {};
    },
    sequence: () => ({ start: () => {}, stop: () => {} }),
    loop: () => ({ start: () => {}, stop: () => {} }),
    View,
  };
  return { Animated, Easing: { inOut: (fn) => fn, ease: 'ease' }, View };
});

vi.mock('../theme/ThemeContext', () => ({
  useTheme: () => ({ colors: { ink3: '#828b97', ink4: '#b4b4b4' } }),
}));

const { Glyph } = await import('./Glyph');

const draw = (props) => render(<Glyph kind="profile" {...props} />).container;

describe('Glyph profile fold', () => {
  it('draws the profile fold in the profile colour', () => {
    const root = draw({ fold: 'shield', color: '#3899e2' });
    const polygons = root.querySelectorAll('polygon');
    expect(polygons).toHaveLength(foldFacets('shield').length);
    expect([...polygons].some((p) => p.getAttribute('fill') === '#3899e2')).toBe(true);
  });

  it('ripples a working profile fold facet by facet, and holds one that needs a model still', () => {
    expect(draw({ fold: 'shield', color: '#3899e2', working: true }).querySelectorAll('svg').length).toBe(foldFacets('shield').length);
    cleanup();
    expect(draw({ fold: 'shield', color: '#3899e2', working: true, needsProvider: true }).querySelectorAll('svg').length).toBe(1);
  });

  it('draws a roster profile at the shared row size, as the desktop rows and the design boards do', () => {
    expect(draw({ fold: 'shield', color: '#3899e2' }).querySelector('svg').getAttribute('width')).toBe(String(FOLD_SIZES.row));
  });

  it('draws the kite-base origami for a profile that never chose a fold', () => {
    expect(draw({ color: '#3899e2' }).querySelectorAll('polygon').length).toBeGreaterThan(1);
  });

  it('draws the kite-base origami for an unknown fold from a newer daemon', () => {
    expect(draw({ fold: 'pencil', color: '#3899e2' }).querySelectorAll('polygon').length).toBeGreaterThan(1);
  });

  it('outlines the fold of a profile that needs a model', () => {
    const polygon = draw({ fold: 'shield', color: '#3899e2', needsProvider: true }).querySelector('polygon');
    expect(polygon.getAttribute('fill-opacity')).toBe('0.22');
    expect(polygon.getAttribute('stroke')).toBe(polygon.getAttribute('fill'));
  });

  it('leaves a ready profile filled', () => {
    const polygon = draw({ fold: 'shield', color: '#3899e2' }).querySelector('polygon');
    expect(polygon.getAttribute('fill-opacity')).toBe('1');
    expect(polygon.getAttribute('stroke')).toBeNull();
  });

  it('draws a workgroup as the honeycomb in its hub colour whatever the fold', () => {
    const root = render(<Glyph kind="workgroup" fold="shield" color="#3899e2" />).container;
    const polygons = root.querySelectorAll('polygon');
    expect(polygons).toHaveLength(foldFacets('honeycomb').length);
    expect([...polygons].some((p) => p.getAttribute('fill') === '#3899e2')).toBe(true);
    expect(root.querySelector('svg').getAttribute('width')).toBe(String(FOLD_SIZES.row));
    expect(polygons[0].getAttribute('fill-opacity')).toBe('1');
  });

  it('unfolds a paused workgroup and a paused profile in grey', () => {
    for (const glyph of [<Glyph kind="workgroup" color="#3899e2" paused />, <Glyph kind="profile" fold="heart" color="#3899e2" paused />]) {
      const polygon = render(glyph).container.querySelector('polygon');
      expect(polygon.getAttribute('fill')).toBe('none');
      expect(polygon.getAttribute('stroke')).toBe('#828b97');
      cleanup();
    }
  });

  it('ripples a working workgroup and stills a paused one', () => {
    render(<Glyph kind="workgroup" color="#3899e2" working />);
    expect(h.delays).toEqual([0, 600, 1200]);
    cleanup();
    h.delays.length = 0;
    render(<Glyph kind="workgroup" color="#3899e2" working paused />);
    expect(h.delays).toEqual([]);
  });
});
