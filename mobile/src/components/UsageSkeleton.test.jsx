import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { act, cleanup, render } from '@testing-library/react';

import { CHART_H, NARROW_TILES_W, usageMetrics } from './UsageChart';
import { BAR_SHAPES } from './UsageSkeleton';
import { space } from '../theme/tokens';

const h = vi.hoisted(() => ({ onLayout: null, sizes: { xs: 11, sm: 12, md: 14, xl: 18, display: 28 } }));

vi.mock('react-native', async () => {
  const R = await import('react');
  const flat = (style) => Object.assign({}, ...[style].flat(Infinity).filter(Boolean));
  const host = (extra = {}) => ({ children, onLayout, style, accessibilityLabel, accessibilityRole, accessible, ...p }) => {
    if (onLayout) h.onLayout = onLayout;
    return R.createElement('div', { ...p, ...extra, 'data-style': JSON.stringify(flat(style)), role: accessibilityRole, 'aria-label': accessibilityLabel }, children);
  };
  return { View: host(), Pressable: host(), Text: host({ 'data-text': '' }) };
});
vi.mock('./SkeletonBar', () => ({
  STAGGER_MS: 90,
  SkeletonBar: ({ width, height, delay = 0 }) => React.createElement('i', { 'data-bar': `${width}x${height}@${delay}`, 'data-h': height }),
}));
vi.mock('../theme/ThemeContext', () => ({
  useTheme: () => ({
    colors: { line2: '#ddd', ink: '#000', ink3: '#666', ink4: '#999', accent: '#c90' },
    fonts: { mono: 'm', monoMedium: 'mm', monoSemibold: 'ms', sans: { regular: 'r', semibold: 's' } },
    fontSizes: h.sizes,
  }),
}));
vi.mock('./groupTone', () => ({ useGroundTone: () => '#fff' }));

const { UsageSkeleton } = await import('./UsageSkeleton');
const { UsageChart } = await import('./UsageChart');

afterEach(() => {
  cleanup();
  h.onLayout = null;
  h.sizes = { xs: 11, sm: 12, md: 14, xl: 18, display: 28 };
});

const measure = (width) => act(() => h.onLayout({ nativeEvent: { layout: { width } } }));
const bars = (c) => [...c.querySelectorAll('[data-bar]')].map((b) => b.dataset.bar);

describe('UsageSkeleton', () => {
  it('stays a labelled progressbar', () => {
    const { container } = render(<UsageSkeleton />);
    const root = container.querySelector('[data-skeleton="usage"]');
    expect(root.getAttribute('role')).toBe('progressbar');
    expect(root.getAttribute('aria-label')).toBe('Loading usage');
  });

  it('draws the narrow layout under the tile breakpoint: two rows of two tiles', () => {
    const { container } = render(<UsageSkeleton />);
    measure(NARROW_TILES_W - 1);
    const rows = container.querySelectorAll('[data-row]');
    expect(rows).toHaveLength(2);
    expect([...rows].map((r) => r.querySelectorAll('[data-tile]').length)).toEqual([2, 2]);
    expect(bars(container).slice(0, 2)).toEqual(['34x8@0', '84x22@0']);
  });

  it('draws four tiles in one row at and above the breakpoint', () => {
    const { container } = render(<UsageSkeleton />);
    measure(NARROW_TILES_W);
    const rows = container.querySelectorAll('[data-row]');
    expect(rows).toHaveLength(1);
    expect(rows[0].querySelectorAll('[data-tile]')).toHaveLength(4);
    expect(bars(container).slice(0, 2)).toEqual(['34x8@0', '96x22@0']);
  });

  it('draws fourteen day bars of varied heights inside the chart height, and a legend of two bones', () => {
    const { container } = render(<UsageSkeleton />);
    const day = [...container.querySelector('[data-bars]').querySelectorAll('[data-bar]')];
    expect(day).toHaveLength(14);
    const heights = day.map((b) => Number(b.dataset.bar.split('x')[1].split('@')[0]));
    expect(new Set(heights).size).toBeGreaterThan(8);
    expect(Math.max(...heights)).toBeLessThanOrEqual(CHART_H);
    expect(BAR_SHAPES).toHaveLength(14);
    expect(container.querySelector('[data-legend]').querySelectorAll('[data-bar]')).toHaveLength(2);
    expect(container.querySelector('[data-days]').querySelectorAll('[data-bar]')).toHaveLength(14);
  });

  it('staggers the day bars by 90 ms', () => {
    const { container } = render(<UsageSkeleton />);
    const delays = [...container.querySelector('[data-bars]').querySelectorAll('[data-bar]')].map((b) => Number(b.dataset.bar.split('@')[1]));
    expect(delays.slice(0, 3)).toEqual([0, 90, 180]);
  });

  it('is not a single full-width slab', () => {
    const { container } = render(<UsageSkeleton />);
    expect(bars(container)).not.toContain(`100%x${CHART_H}@0`);
    expect(bars(container).length).toBeGreaterThan(14);
  });
});

const DAYS = Array.from({ length: 14 }, (_, i) => ({
  iso: `2026-10-${String(i + 1).padStart(2, '0')}`,
  label: 'M',
  day: `10/${i + 1}`,
  tokIn: 1000 * (i + 1),
  tokOut: 500 * (i + 1),
  cost: 0.1 * (i + 1),
  today: i === 13,
}));

const own = (el) => JSON.parse(el.dataset.style ?? '{}');
function heightOf(el) {
  if (el.dataset.h != null) return Number(el.dataset.h);
  const st = own(el);
  const margin = (st.marginTop ?? 0) + (st.marginBottom ?? 0);
  if ('data-text' in el.attributes || el.hasAttribute('data-text')) return st.lineHeight + margin;
  if (typeof st.height === 'number') return st.height + margin;
  const kids = [...el.children].map(heightOf);
  const inner = st.flexDirection === 'row'
    ? Math.max(0, ...kids)
    : kids.reduce((a, b) => a + b, 0) + (st.gap ?? 0) * Math.max(0, kids.length - 1);
  return inner + (st.paddingTop ?? 0) + (st.paddingBottom ?? 0) + (st.borderBottomWidth ?? 0) + margin;
}

const skeletonHeight = (w) => {
  const { container } = render(<UsageSkeleton />);
  measure(w);
  const height = heightOf(container.firstChild);
  cleanup();
  return height;
};
const chartHeight = (w) => {
  const { container } = render(<UsageChart days={DAYS} />);
  measure(w);
  const height = heightOf(container.firstChild);
  cleanup();
  return height;
};

const expected = (m, narrow) => {
  const tile = (value) => m.label + space.s2 + value;
  const tiles = narrow ? tile(m.today) + space.s6 + tile(m.mono) : tile(m.today);
  return tiles + space.s6 + 0.5 + space.s8 + CHART_H + space.s3 + m.dayLabel + space.s6 + m.legend;
};

describe.each([
  ['default text size', { xs: 11, sm: 12, md: 14, xl: 18, display: 28 }],
  ['large text size', { xs: 14, sm: 16, md: 18, xl: 23, display: 36 }],
])('UsageSkeleton height at %s', (_name, sizes) => {
  it.each([
    ['narrow', NARROW_TILES_W - 1, true],
    ['wide', NARROW_TILES_W, false],
  ])('equals the formula built from the chart constants and the real chart, %s', (_n, width, narrow) => {
    h.sizes = sizes;
    const want = expected(usageMetrics(sizes), narrow);
    expect(skeletonHeight(width)).toBe(want);
    expect(chartHeight(width)).toBe(want);
  });

  it('keeps tile slots at the real line boxes with bones inside them', () => {
    h.sizes = sizes;
    const m = usageMetrics(sizes);
    const { container } = render(<UsageSkeleton />);
    measure(NARROW_TILES_W);
    const tile = container.querySelector('[data-tile]');
    const slots = [...tile.children].map((slot) => own(slot).height);
    expect(slots).toEqual([m.label, m.today]);
    expect(own(tile).gap).toBe(space.s2);
    expect(own(container.querySelector('[data-legend]')).height).toBe(m.legend);
  });
});
